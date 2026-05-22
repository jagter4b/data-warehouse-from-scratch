import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    # Use sqlalchemy for pandas writing
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
        days_since_last_order, 
        total_orders, 
        total_spend
    FROM gold.obt_customers
    """
    df = pd.read_sql(query, engine)
    return df

def assign_rfm_scores(df):
    # Handle NaNs
    df['days_since_last_order'] = df['days_since_last_order'].fillna(999)
    df['total_orders'] = df['total_orders'].fillna(0)
    df['total_spend'] = df['total_spend'].fillna(0)

    # Recency: Lower days is better, so quintile 5 is lowest days
    df['rfm_recency_score'] = pd.qcut(df['days_since_last_order'], 5, labels=[5, 4, 3, 2, 1])
    
    # Frequency: Higher orders is better. Since many customers have 1 order, qcut might fail due to non-unique edges.
    # We use rank method 'first' to force unique bins
    df['rfm_frequency_score'] = pd.qcut(df['total_orders'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
    
    # Monetary: Higher spend is better
    df['rfm_monetary_score'] = pd.qcut(df['total_spend'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
    
    # Convert to numeric
    df['rfm_recency_score'] = df['rfm_recency_score'].astype(int)
    df['rfm_frequency_score'] = df['rfm_frequency_score'].astype(int)
    df['rfm_monetary_score'] = df['rfm_monetary_score'].astype(int)

    
    df['rfm_total_score'] = df['rfm_recency_score'] + df['rfm_frequency_score'] + df['rfm_monetary_score']
    return df

def run_kmeans(df):
    features = ['days_since_last_order', 'total_orders', 'total_spend']
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(df[features])
    
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    df['cluster_id'] = kmeans.fit_predict(scaled_data)
    
    # Calculate Silhouette
    # Sample if dataset is too large to compute silhouette efficiently
    sample_size = min(len(scaled_data), 10000)
    sil_score = silhouette_score(scaled_data, df['cluster_id'], sample_size=sample_size, random_state=42)
    
    # Map clusters to labels based on centroids
    centroids = pd.DataFrame(scaler.inverse_transform(kmeans.cluster_centers_), columns=features)
    centroids['cluster_id'] = range(4)
    
    # Simple heuristic to assign labels based on RFM meaning
    # Champions: Low recency days, High frequency, High spend
    # We will score centroids
    centroids['c_score'] = -centroids['days_since_last_order'] + (centroids['total_orders'] * 10) + (centroids['total_spend'])
    sorted_clusters = centroids.sort_values('c_score', ascending=False)['cluster_id'].tolist()
    
    label_map = {
        sorted_clusters[0]: 'Champions',
        sorted_clusters[1]: 'Loyal Customers',
        sorted_clusters[2]: 'At Risk',
        sorted_clusters[3]: 'Lost/Inactive'
    }
    
    df['segment_label'] = df['cluster_id'].map(label_map)
    df['scored_at'] = datetime.now()
    
    return df, sil_score

def print_diagnostics(df, sil_score):
    print("=== MODEL 1: RFM SEGMENTATION ===")
    print(f"Silhouette Score (Sampled): {sil_score:.4f}\n")
    print("Segment Distribution:")
    print(df['segment_label'].value_counts())
    print("\nSample Output:")
    print(df[['customer_unique_id', 'rfm_total_score', 'cluster_id', 'segment_label']].head(5).to_string(index=False))

def execute_write(df, engine):
    output_cols = [
        'customer_unique_id', 'rfm_recency_score', 'rfm_frequency_score', 
        'rfm_monetary_score', 'rfm_total_score', 'cluster_id', 
        'segment_label', 'scored_at'
    ]
    df_out = df[output_cols]
    
    print("\nExecuting persistent write to gold.ml_customer_segments...")
    with engine.begin() as conn:
        # Check if table exists
        check_query = text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'gold' AND TABLE_NAME = 'ml_customer_segments'")
        exists = conn.execute(check_query).fetchone()
        
        if exists:
            conn.execute(text("TRUNCATE TABLE gold.ml_customer_segments"))
        
        # Append data
        df_out.to_sql('ml_customer_segments', conn, schema='gold', if_exists='append', index=False)
        print(f"Successfully populated {len(df_out)} rows within transaction.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write to database")
    args = parser.parse_args()
    
    engine = get_engine()
    print("Loading data from gold.obt_customers...")
    df = load_data(engine)
    
    print("Scoring RFM and clustering...")
    df = assign_rfm_scores(df)
    df, sil_score = run_kmeans(df)
    
    print_diagnostics(df, sil_score)
    
    if args.execute:
        execute_write(df, engine)
    else:
        print("\nDry-run complete. Use --execute to save results.")
