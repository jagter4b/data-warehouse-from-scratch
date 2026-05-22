import pandas as pd
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

conn_str = f"mssql+pyodbc://@{os.getenv('DEST_DB_HOST')}:{os.getenv('DEST_DB_PORT')}/{os.getenv('DEST_DB_NAME').strip()}?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
engine = create_engine(conn_str)

tables = [
    'obt_customers', 'obt_sellers', 'obt_orders', 
    'ml_customer_segments', 'ml_churn_predictions', 'ml_clv_predictions', 
    'ml_seller_scores', 'ml_seller_churn', 'ml_delivery_risk', 'ml_review_predictions'
]

output_dir = 'streamlit/data'

for t in tables:
    print(f"Exporting {t}...")
    try:
        df = pd.read_sql(f"SELECT * FROM gold.{t}", engine)
        df.to_csv(f"{output_dir}/{t}.csv", index=False)
        print(f"Successfully exported {len(df)} rows to {t}.csv")
    except Exception as e:
        print(f"Error exporting {t}: {e}")
