import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
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
        seller_id,
        avg_review_score,
        pct_late_deliveries,
        total_orders_fulfilled,
        total_revenue,
        total_distinct_customers_served,
        pct_1star_reviews,
        pct_5star_reviews,
        avg_days_to_deliver
    FROM gold.obt_sellers
    """
    df = pd.read_sql(query, engine)
    return df

def generate_scores(df):
    df_clean = df.fillna(0).copy()
    
    scaler_minmax = MinMaxScaler()
    
    # Normalize review score (1-5 to 0-1)
    rev_scaled = scaler_minmax.fit_transform(df_clean[['avg_review_score']])
    
    # On time %
    pct_on_time = (100 - df_clean['pct_late_deliveries']) / 100
    
    # Log revenue (handle 0s)
    log_rev = np.log1p(df_clean['total_revenue'])
    rev_log_scaled = scaler_minmax.fit_transform(log_rev.values.reshape(-1, 1))
    
    # Pct 5 stars (0-100 to 0-1)
    pct_5_scaled = df_clean['pct_5star_reviews'] / 100
    
    # Composite Score (0-100)
    df_clean['composite_score'] = (
        (rev_scaled.flatten() * 0.40) +
        (pct_on_time.values * 0.30) +
        (rev_log_scaled.flatten() * 0.20) +
        (pct_5_scaled.values * 0.10)
    ) * 100
    
    features = [
        'avg_review_score', 'pct_late_deliveries', 'total_orders_fulfilled',
        'total_revenue', 'total_distinct_customers_served', 'pct_1star_reviews',
        'pct_5star_reviews', 'avg_days_to_deliver', 'composite_score'
    ]
    
    scaler_std = StandardScaler()
    X_scaled = scaler_std.fit_transform(df_clean[features])
    
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df_clean['cluster_id'] = kmeans.fit_predict(X_scaled)
    
    sil_score = silhouette_score(X_scaled, df_clean['cluster_id'], random_state=42)
    
    # Label clusters based on average composite score
    cluster_scores = df_clean.groupby('cluster_id')['composite_score'].mean().sort_values(ascending=False)
    sorted_clusters = cluster_scores.index.tolist()
    
    label_map = {
        sorted_clusters[0]: 'Top Performer',
        sorted_clusters[1]: 'Average Seller',
        sorted_clusters[2]: 'Underperformer'
    }
    
    df_clean['cluster_label'] = df_clean['cluster_id'].map(label_map)
    df_clean['performance_tier'] = df_clean['cluster_label']
    df_clean['model_version'] = 'v1.0'
    df_clean['scored_at'] = datetime.now()
    
    return df_clean, sil_score

def print_diagnostics(df, sil_score):
    print("=== MODEL 4: SELLER SCORES ===")
    print(f"Silhouette Score: {sil_score:.4f}\n")
    print("Cluster Distribution:")
    print(df['cluster_label'].value_counts())
    
    print("\nSample Output:")
    print(df[['seller_id', 'composite_score', 'cluster_label']].head(5).to_string(index=False))

def execute_write(df, engine):
    output_cols = [
        'seller_id', 'composite_score', 'performance_tier', 'cluster_id', 
        'cluster_label', 'avg_review_score', 'pct_late_deliveries', 
        'total_revenue', 'model_version', 'scored_at'
    ]
    df_out = df[output_cols]
    
    print("\nExecuting persistent write to gold.ml_seller_scores...")
    with engine.begin() as conn:
        check_query = text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'gold' AND TABLE_NAME = 'ml_seller_scores'")
        exists = conn.execute(check_query).fetchone()
        
        if exists:
            conn.execute(text("TRUNCATE TABLE gold.ml_seller_scores"))
        
        df_out.to_sql('ml_seller_scores', conn, schema='gold', if_exists='append', index=False)
        print(f"Successfully populated {len(df_out)} rows within transaction.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write to database")
    args = parser.parse_args()
    
    engine = get_engine()
    print("Loading data from gold.obt_sellers...")
    df = load_data(engine)
    
    print("Scoring sellers and clustering...")
    df_scored, sil_score = generate_scores(df)
    
    print_diagnostics(df_scored, sil_score)
    
    if args.execute:
        execute_write(df_scored, engine)
    else:
        print("\nDry-run complete. Use --execute to save results.")
