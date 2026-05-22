import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
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
        total_spend,
        total_orders,
        customer_tenure_days,
        distinct_months_active,
        avg_installments,
        distinct_categories_bought,
        pct_late_deliveries,
        avg_review_score,
        any_seller_from_mql
    FROM gold.obt_customers
    """
    df = pd.read_sql(query, engine)
    return df

def run_xgboost_regressor(df):
    features = [
        'total_orders', 'customer_tenure_days', 'distinct_months_active',
        'avg_installments', 'distinct_categories_bought', 'pct_late_deliveries',
        'avg_review_score', 'any_seller_from_mql'
    ]
    
    # Drop rows with nulls in features
    df_clean = df.dropna(subset=features + ['total_spend']).copy()
    
    # Remove outliers > 99th percentile on total_spend
    p99 = df_clean['total_spend'].quantile(0.99)
    df_clean = df_clean[df_clean['total_spend'] <= p99].copy()
    
    X = df_clean[features]
    y = df_clean['total_spend']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
    
    reg = xgb.XGBRegressor(random_state=42, objective='reg:squarederror')
    reg.fit(X_train, y_train)
    
    # Predict on entire dataset
    df_clean['predicted_clv'] = reg.predict(X_scaled)
    
    # Bin predictions into CLV tiers
    p90 = df_clean['predicted_clv'].quantile(0.90)
    p70 = df_clean['predicted_clv'].quantile(0.70)
    p40 = df_clean['predicted_clv'].quantile(0.40)
    
    def get_clv_tier(val):
        if val >= p90: return 'Platinum'
        elif val >= p70: return 'Gold'
        elif val >= p40: return 'Silver'
        else: return 'Bronze'
            
    df_clean['clv_tier'] = df_clean['predicted_clv'].apply(get_clv_tier)
    df_clean['model_version'] = 'v1.0'
    df_clean['scored_at'] = datetime.now()
    
    # Print metrics on test set
    y_pred = reg.predict(X_test)
    
    metrics = {
        'RMSE': np.sqrt(mean_squared_error(y_test, y_pred)),
        'MAE': mean_absolute_error(y_test, y_pred),
        'R2': r2_score(y_test, y_pred),
        'Tier Distribution': df_clean['clv_tier'].value_counts().to_dict(),
        'Feature Importances': list(zip(features, reg.feature_importances_))
    }
    
    return df_clean, metrics

def print_diagnostics(df, metrics):
    print("=== MODEL 3: CLV PREDICTION ===")
    for k, v in metrics.items():
        if k != 'Feature Importances' and k != 'Tier Distribution':
            print(f"{k}: {v:.4f}")
            
    print("\nTier Distribution:")
    for t, c in metrics['Tier Distribution'].items():
        print(f"  {t}: {c}")
    
    print("\nTop 3 Important Features:")
    sorted_fi = sorted(metrics['Feature Importances'], key=lambda x: x[1], reverse=True)
    for f, imp in sorted_fi[:3]:
        print(f"  {f}: {imp:.4f}")
        
    print("\nSample Output:")
    print(df[['customer_unique_id', 'predicted_clv', 'clv_tier']].head(5).to_string(index=False))

def execute_write(df, engine):
    output_cols = [
        'customer_unique_id', 'predicted_clv', 'clv_tier', 
        'model_version', 'scored_at'
    ]
    df_out = df[output_cols]
    
    print("\nExecuting persistent write to gold.ml_clv_predictions...")
    with engine.begin() as conn:
        check_query = text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'gold' AND TABLE_NAME = 'ml_clv_predictions'")
        exists = conn.execute(check_query).fetchone()
        
        if exists:
            conn.execute(text("TRUNCATE TABLE gold.ml_clv_predictions"))
        
        df_out.to_sql('ml_clv_predictions', conn, schema='gold', if_exists='append', index=False)
        print(f"Successfully populated {len(df_out)} rows within transaction.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write to database")
    args = parser.parse_args()
    
    engine = get_engine()
    print("Loading data from gold.obt_customers...")
    df = load_data(engine)
    
    print("Training XGBoost Regressor and scoring CLV...")
    df_scored, metrics = run_xgboost_regressor(df)
    
    print_diagnostics(df_scored, metrics)
    
    if args.execute:
        execute_write(df_scored, engine)
    else:
        print("\nDry-run complete. Use --execute to save results.")
