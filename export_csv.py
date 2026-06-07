"""
export_csv.py
─────────────
Exports gold.obt_master to streamlit/data/obt_master.csv for Streamlit Cloud demo mode.
Run this after the ML pipeline to refresh the snapshot.
"""

import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

conn_str = (
    f"mssql+pyodbc://@{os.getenv('DEST_DB_HOST')}:{os.getenv('DEST_DB_PORT')}/"
    f"{os.getenv('DEST_DB_NAME').strip()}"
    f"?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
)
engine = create_engine(conn_str)

output_dir = os.path.join("streamlit", "data")
os.makedirs(output_dir, exist_ok=True)

print("Exporting gold.obt_master ...")
try:
    df = pd.read_sql("SELECT * FROM gold.obt_master", engine)
    out_path = os.path.join(output_dir, "obt_master.csv")
    df.to_csv(out_path, index=False)
    print(f"✅ Exported {len(df):,} rows → {out_path}")
except Exception as e:
    print(f"❌ Error: {e}")
