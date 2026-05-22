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
        order_id,
        review_score,
        has_review,
        total_order_value,
        total_items,
        days_to_deliver,
        days_to_approve,
        is_late,
        c_scheduled_vs_actual_days,
        avg_product_weight_g,
        avg_product_photos_qty,
        payment_installments,
        seller_avg_review_score,
        seller_pct_late_deliveries,
        purchase_month,
        purchase_day_of_week
    FROM gold.obt_orders
    WHERE has_review = 1
    """
    df = pd.read_sql(query, engine)
    return df

def run_xgboost_regressor(df):
    features = [
        'total_order_value', 'total_items', 'days_to_deliver', 'days_to_approve',
        'is_late', 'c_scheduled_vs_actual_days', 'avg_product_weight_g', 
        'avg_product_photos_qty', 'payment_installments', 'seller_avg_review_score',
        'seller_pct_late_deliveries', 'purchase_month', 'purchase_day_of_week'
    ]
    
    # Drop rows with nulls in features
    df_clean = df.dropna(subset=features + ['review_score']).copy()
    
    X = df_clean[features]
    y = df_clean['review_score']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
    
    reg = xgb.XGBRegressor(random_state=42, objective='reg:squarederror')
    reg.fit(X_train, y_train)
    
    # Predict on entire dataset
    raw_preds = reg.predict(X_scaled)
    # Clip to valid range and round to nearest 0.5
    df_clean['predicted_review_score'] = np.round(np.clip(raw_preds, 1.0, 5.0) * 2) / 2
    
    def get_satisfaction_tier(score):
        if score >= 4.5: return 'Excellent'
        elif score >= 3.5: return 'Good'
        elif score >= 2.5: return 'Poor'
        else: return 'Very Poor'
            
    df_clean['satisfaction_tier'] = df_clean['predicted_review_score'].apply(get_satisfaction_tier)
    df_clean['model_version'] = 'v1.0'
    df_clean['scored_at'] = datetime.now()
    
    y_pred = reg.predict(X_test)
    
    metrics = {
        'RMSE': np.sqrt(mean_squared_error(y_test, y_pred)),
        'MAE': mean_absolute_error(y_test, y_pred),
        'R2': r2_score(y_test, y_pred),
        'Tier Distribution': df_clean['satisfaction_tier'].value_counts().to_dict(),
        'Feature Importances': list(zip(features, reg.feature_importances_))
    }
    
    return df_clean, metrics

def print_diagnostics(df, metrics):
    print("=== MODEL 7: REVIEW PREDICTION ===")
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
    print(df[['order_id', 'predicted_review_score', 'satisfaction_tier']].head(5).to_string(index=False))

def execute_write(df, engine):
    output_cols = [
        'order_id', 'predicted_review_score', 'satisfaction_tier', 
        'model_version', 'scored_at'
    ]
    df_out = df[output_cols]
    
    print("\nExecuting persistent write to gold.ml_review_predictions...")
    with engine.begin() as conn:
        check_query = text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'gold' AND TABLE_NAME = 'ml_review_predictions'")
        exists = conn.execute(check_query).fetchone()
        
        if exists:
            conn.execute(text("TRUNCATE TABLE gold.ml_review_predictions"))
        
        df_out.to_sql('ml_review_predictions', conn, schema='gold', if_exists='append', index=False)
        print(f"Successfully populated {len(df_out)} rows within transaction.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write to database")
    args = parser.parse_args()
    
    engine = get_engine()
    print("Loading data from gold.obt_orders...")
    df = load_data(engine)
    
    print("Training XGBoost Regressor and scoring Reviews...")
    df_scored, metrics = run_xgboost_regressor(df)
    
    print_diagnostics(df_scored, metrics)
    
    if args.execute:
        execute_write(df_scored, engine)
    else:
        print("\nDry-run complete. Use --execute to save results.")
