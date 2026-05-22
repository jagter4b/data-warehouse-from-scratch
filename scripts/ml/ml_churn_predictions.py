import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE
import xgboost as xgb
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score, confusion_matrix
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    conn_str = (
        f"mssql+pyodbc://@{os.getenv('DEST_DB_HOST')}:{os.getenv('DEST_DB_PORT')}"
        f"/{os.getenv('DEST_DB_NAME').strip()}?"
        "driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
    )
    return create_engine(conn_str)

def load_data(engine):
    query = """
    SELECT 
        customer_unique_id,
        last_order_date,
        total_orders,
        total_spend,
        avg_order_value,
        avg_review_score,
        pct_late_deliveries,
        customer_tenure_days,
        avg_installments,
        distinct_categories_bought,
        pct_1star_reviews,
        any_seller_from_mql
    FROM gold.obt_customers
    """
    df = pd.read_sql(query, engine)
    return df

def run_models(df):
    # Recalculate true days_since_last_order relative to dataset max date
    df['last_order_date'] = pd.to_datetime(df['last_order_date'])
    max_date = df['last_order_date'].max()
    df['days_since_last_order'] = (max_date - df['last_order_date']).dt.days
    
    # Adjust churn threshold to 120 days
    df['churned'] = (df['days_since_last_order'] > 120).astype(int)
    
    features = [
        'total_orders', 'total_spend', 'avg_order_value', 'avg_review_score',
        'pct_late_deliveries', 'customer_tenure_days', 'avg_installments',
        'distinct_categories_bought', 'pct_1star_reviews', 'any_seller_from_mql'
    ]
    
    # Drop rows with nulls in features
    df_clean = df.dropna(subset=features).copy()
    
    X = df_clean[features]
    y = df_clean['churned']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)
    
    # Track class distribution
    pre_smote_dist = y_train.value_counts().to_dict()
    
    # SMOTE
    smote = SMOTE(random_state=42)
    X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)
    
    post_smote_dist = y_train_sm.value_counts().to_dict()
    
    # Model 1: XGBoost
    xgb_clf = xgb.XGBClassifier(random_state=42, use_label_encoder=False, eval_metric='logloss')
    xgb_clf.fit(X_train_sm, y_train_sm)
    xgb_prob = xgb_clf.predict_proba(X_test)[:, 1]
    xgb_auc = roc_auc_score(y_test, xgb_prob)
    
    # Model 2: Random Forest
    from sklearn.ensemble import RandomForestClassifier
    rf_clf = RandomForestClassifier(random_state=42, n_jobs=-1)
    rf_clf.fit(X_train_sm, y_train_sm)
    rf_prob = rf_clf.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, rf_prob)
    
    # Select best model
    best_clf = xgb_clf if xgb_auc >= rf_auc else rf_clf
    best_name = 'XGBoost' if xgb_auc >= rf_auc else 'Random Forest'
    best_auc = max(xgb_auc, rf_auc)
    
    # Predict on entire dataset using best model
    df_clean['churn_probability'] = best_clf.predict_proba(X_scaled)[:, 1]
    
    # Thresholding logic for risk tiers
    df_clean['churn_predicted'] = (df_clean['churn_probability'] > 0.5).astype(int)
    
    def get_risk_tier(prob):
        if prob > 0.7:
            return 'High'
        elif prob >= 0.4:
            return 'Medium'
        else:
            return 'Low'
            
    df_clean['risk_tier'] = df_clean['churn_probability'].apply(get_risk_tier)
    df_clean['model_version'] = 'v2.0'
    df_clean['scored_at'] = datetime.now()
    
    # Print metrics on test set
    y_pred = best_clf.predict(X_test)
    y_prob = best_clf.predict_proba(X_test)[:, 1]
    
    metrics = {
        'Best Model': best_name,
        'XGBoost AUC': xgb_auc,
        'Random Forest AUC': rf_auc,
        'AUC-ROC': roc_auc_score(y_test, y_prob),
        'F1 Score': f1_score(y_test, y_pred),
        'Precision': precision_score(y_test, y_pred),
        'Recall': recall_score(y_test, y_pred),
        'Confusion Matrix': confusion_matrix(y_test, y_pred).tolist(),
        'Pre-SMOTE Class Dist': pre_smote_dist,
        'Post-SMOTE Class Dist': post_smote_dist,
        'Feature Importances': list(zip(features, best_clf.feature_importances_))
    }
    
    return df_clean, metrics

def print_diagnostics(df, metrics):
    print("=== MODEL 2: CHURN PREDICTION ===")
    for k, v in metrics.items():
        if k != 'Feature Importances':
            print(f"{k}: {v}")
    
    print("\nFeature Importances Ranked:")
    sorted_fi = sorted(metrics['Feature Importances'], key=lambda x: x[1], reverse=True)
    for f, imp in sorted_fi:
        print(f"  {f}: {imp:.4f}")
        
    print("\nSample Output:")
    print(df[['customer_unique_id', 'churn_probability', 'risk_tier']].head(5).to_string(index=False))

def execute_write(df, engine):
    output_cols = [
        'customer_unique_id', 'churn_probability', 'churn_predicted', 
        'risk_tier', 'model_version', 'scored_at'
    ]
    df_out = df[output_cols]
    
    print("\nExecuting persistent write to gold.ml_churn_predictions...")
    with engine.begin() as conn:
        check_query = text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'gold' AND TABLE_NAME = 'ml_churn_predictions'")
        exists = conn.execute(check_query).fetchone()
        
        if exists:
            conn.execute(text("TRUNCATE TABLE gold.ml_churn_predictions"))
        
        df_out.to_sql('ml_churn_predictions', conn, schema='gold', if_exists='append', index=False)
        print(f"Successfully populated {len(df_out)} rows within transaction.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write to database")
    args = parser.parse_args()
    
    engine = get_engine()
    print("Loading data from gold.obt_customers...")
    df = load_data(engine)
    
    print("Training XGBoost and scoring Churn...")
    df_scored, metrics = run_models(df)
    
    print_diagnostics(df_scored, metrics)
    
    if args.execute:
        execute_write(df_scored, engine)
    else:
        print("\nDry-run complete. Use --execute to save results.")
