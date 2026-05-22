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

for t in tables:
    print(f"\n--- {t} ---")
    query = f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{t}' AND TABLE_SCHEMA = 'gold' ORDER BY ORDINAL_POSITION"
    try:
        df = pd.read_sql(query, engine)
        print(df.to_string(index=False))
    except Exception as e:
        print(e)
