import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler, LabelEncoder
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
        order_id,
        is_late,
        total_order_value,
        total_items,
        total_distinct_products,
        avg_product_weight_g,
        payment_installments,
        days_to_approve,
        seller_avg_review_score,
        seller_pct_late_deliveries,
        purchase_day_of_week,
        purchase_month,
        primary_category,
        distinct_categories
    FROM gold.obt_orders
    """
    df = pd.read_sql(query, engine)
    return df

def run_xgboost(df):
    features = [
        'total_order_value', 'total_items', 'total_distinct_products', 
        'avg_product_weight_g', 'payment_installments', 'days_to_approve',
        'seller_avg_review_score', 'seller_pct_late_deliveries', 
        'purchase_day_of_week', 'purchase_month', 'primary_category', 
        'distinct_categories'
    ]
    
    # Drop rows with nulls
    df_clean = df.dropna(subset=features + ['is_late']).copy()
    
    # Label encode primary category
    le = LabelEncoder()
    df_clean['primary_category_encoded'] = le.fit_transform(df_clean['primary_category'])
    
    encoded_features = features.copy()
    encoded_features.remove('primary_category')
    encoded_features.append('primary_category_encoded')
    
    X = df_clean[encoded_features]
    y = df_clean['is_late']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)
    
    # SMOTE
    smote = SMOTE(random_state=42)
    X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)
    
    clf = xgb.XGBClassifier(random_state=42, use_label_encoder=False, eval_metric='logloss')
    clf.fit(X_train_sm, y_train_sm)
    
    df_clean['delay_probability'] = clf.predict_proba(X_scaled)[:, 1]
    df_clean['delay_predicted'] = (df_clean['delay_probability'] > 0.5).astype(int)
    
    def get_risk_tier(prob):
        if prob > 0.7: return 'High'
        elif prob >= 0.4: return 'Medium'
        else: return 'Low'
            
    df_clean['risk_tier'] = df_clean['delay_probability'].apply(get_risk_tier)
    df_clean['model_version'] = 'v1.0'
    df_clean['scored_at'] = datetime.now()
    
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]
    
    metrics = {
        'AUC-ROC': roc_auc_score(y_test, y_prob),
        'F1 Score': f1_score(y_test, y_pred),
        'Precision': precision_score(y_test, y_pred),
        'Recall': recall_score(y_test, y_pred),
        'Confusion Matrix': confusion_matrix(y_test, y_pred).tolist(),
        'Feature Importances': list(zip(encoded_features, clf.feature_importances_))
    }
    
    return df_clean, metrics

def print_diagnostics(df, metrics):
    print("=== MODEL 6: DELIVERY RISK ===")
    for k, v in metrics.items():
        if k != 'Feature Importances':
            print(f"{k}: {v}")
    
    print("\nTop 3 Important Features:")
    sorted_fi = sorted(metrics['Feature Importances'], key=lambda x: x[1], reverse=True)
    for f, imp in sorted_fi[:3]:
        print(f"  {f}: {imp:.4f}")
        
    print("\nSample Output:")
    print(df[['order_id', 'delay_probability', 'risk_tier']].head(5).to_string(index=False))

def execute_write(df, engine):
    output_cols = [
        'order_id', 'delay_probability', 'delay_predicted', 
        'risk_tier', 'model_version', 'scored_at'
    ]
    df_out = df[output_cols]
    
    print("\nExecuting persistent write to gold.ml_delivery_risk...")
    with engine.begin() as conn:
        check_query = text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'gold' AND TABLE_NAME = 'ml_delivery_risk'")
        exists = conn.execute(check_query).fetchone()
        
        if exists:
            conn.execute(text("TRUNCATE TABLE gold.ml_delivery_risk"))
        
        df_out.to_sql('ml_delivery_risk', conn, schema='gold', if_exists='append', index=False)
        print(f"Successfully populated {len(df_out)} rows within transaction.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write to database")
    args = parser.parse_args()
    
    engine = get_engine()
    print("Loading data from gold.obt_orders...")
    df = load_data(engine)
    
    print("Training XGBoost and scoring Delivery Risk...")
    df_scored, metrics = run_xgboost(df)
    
    print_diagnostics(df_scored, metrics)
    
    if args.execute:
        execute_write(df_scored, engine)
    else:
        print("\nDry-run complete. Use --execute to save results.")
