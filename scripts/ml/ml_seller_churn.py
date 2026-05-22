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
    # Load sellers
    query_sellers = """
    SELECT 
        seller_id,
        total_orders_fulfilled,
        total_revenue,
        avg_review_score,
        pct_late_deliveries,
        avg_days_to_deliver,
        distinct_categories_sold,
        total_distinct_customers_served,
        was_acquired_via_mql,
        COALESCE(declared_monthly_revenue, 0) as declared_monthly_revenue,
        has_company,
        has_gtin
    FROM gold.obt_sellers
    """
    df_sellers = pd.read_sql(query_sellers, engine)
    
    # Load max order date per seller to determine churn
    query_orders = """
    SELECT 
        seller_id,
        MAX(purchase_date) as last_order_date
    FROM gold.obt_orders
    WHERE seller_id IS NOT NULL
    GROUP BY seller_id
    """
    df_orders = pd.read_sql(query_orders, engine)
    
    return df_sellers, df_orders

def run_xgboost(df_sellers, df_orders):
    # Derive churn label based on max global date
    df = df_sellers.merge(df_orders, on='seller_id', how='left')
    
    # Fill missing dates with very old date (churned)
    max_global_date = pd.to_datetime(df['last_order_date']).max()
    df['last_order_date'] = pd.to_datetime(df['last_order_date'])
    df['days_since_last_order'] = (max_global_date - df['last_order_date']).dt.days
    
    # Fill missing with 999
    df['days_since_last_order'] = df['days_since_last_order'].fillna(999)
    df['seller_churned'] = (df['days_since_last_order'] > 180).astype(int)
    
    features = [
        'total_orders_fulfilled', 'total_revenue', 'avg_review_score', 
        'pct_late_deliveries', 'avg_days_to_deliver', 'distinct_categories_sold',
        'total_distinct_customers_served', 'was_acquired_via_mql', 
        'declared_monthly_revenue', 'has_company', 'has_gtin'
    ]
    
    # Fill NaNs for all missing features (e.g., avg_days_to_deliver for sellers with no completed deliveries)
    df_clean = df.fillna(0).copy()
    
    X = df_clean[features]
    y = df_clean['seller_churned']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)
    
    # SMOTE - dynamically adjust k_neighbors if minority class is very small
    minority_count = y_train.value_counts().min()
    k_neighbors = min(5, minority_count - 1)
    
    if k_neighbors > 0:
        smote = SMOTE(random_state=42, k_neighbors=k_neighbors)
        X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)
    else:
        # Not enough samples for SMOTE, use original
        X_train_sm, y_train_sm = X_train, y_train

    
    clf = xgb.XGBClassifier(random_state=42, use_label_encoder=False, eval_metric='logloss')
    clf.fit(X_train_sm, y_train_sm)
    
    df_clean['churn_probability'] = clf.predict_proba(X_scaled)[:, 1]
    df_clean['churn_predicted'] = (df_clean['churn_probability'] > 0.5).astype(int)
    
    def get_risk_tier(prob):
        if prob > 0.7: return 'High'
        elif prob >= 0.4: return 'Medium'
        else: return 'Low'
            
    df_clean['risk_tier'] = df_clean['churn_probability'].apply(get_risk_tier)
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
        'Feature Importances': list(zip(features, clf.feature_importances_))
    }
    
    return df_clean, metrics

def print_diagnostics(df, metrics):
    print("=== MODEL 5: SELLER CHURN ===")
    for k, v in metrics.items():
        if k != 'Feature Importances':
            print(f"{k}: {v}")
    
    print("\nTop 3 Important Features:")
    sorted_fi = sorted(metrics['Feature Importances'], key=lambda x: x[1], reverse=True)
    for f, imp in sorted_fi[:3]:
        print(f"  {f}: {imp:.4f}")
        
    print("\nSample Output:")
    print(df[['seller_id', 'churn_probability', 'risk_tier']].head(5).to_string(index=False))

def execute_write(df, engine):
    output_cols = [
        'seller_id', 'churn_probability', 'churn_predicted', 
        'risk_tier', 'model_version', 'scored_at'
    ]
    df_out = df[output_cols]
    
    print("\nExecuting persistent write to gold.ml_seller_churn...")
    with engine.begin() as conn:
        check_query = text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'gold' AND TABLE_NAME = 'ml_seller_churn'")
        exists = conn.execute(check_query).fetchone()
        
        if exists:
            conn.execute(text("TRUNCATE TABLE gold.ml_seller_churn"))
        
        df_out.to_sql('ml_seller_churn', conn, schema='gold', if_exists='append', index=False)
        print(f"Successfully populated {len(df_out)} rows within transaction.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write to database")
    args = parser.parse_args()
    
    engine = get_engine()
    print("Loading data from gold.obt_sellers and gold.obt_orders...")
    df_sellers, df_orders = load_data(engine)
    
    print("Training XGBoost and scoring Seller Churn...")
    df_scored, metrics = run_xgboost(df_sellers, df_orders)
    
    print_diagnostics(df_scored, metrics)
    
    if args.execute:
        execute_write(df_scored, engine)
    else:
        print("\nDry-run complete. Use --execute to save results.")
