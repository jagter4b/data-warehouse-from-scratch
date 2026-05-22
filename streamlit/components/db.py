import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
import time

def get_engine():
    try:
        # Check Streamlit secrets first, fallback to .env if local
        if "DB_HOST" in st.secrets:
            host = st.secrets["DB_HOST"]
            port = st.secrets.get("DB_PORT", "1433")
            db = st.secrets["DB_NAME"]
        else:
            host = os.getenv("DEST_DB_HOST", "localhost")
            port = os.getenv("DEST_DB_PORT", "1433")
            db = os.getenv("DEST_DB_NAME", "olist_dw")
            
        conn_str = f"mssql+pyodbc://@{host}:{port}/{db.strip()}?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
        return create_engine(conn_str)
    except Exception:
        return None

def load_table(table_name):
    # Try database first
    engine = get_engine()
    if engine:
        try:
            query = f"SELECT * FROM gold.{table_name}"
            df = pd.read_sql(query, engine)
            return df
        except Exception as e:
            pass # Fallback to CSV
            
    # Demo Mode Fallback
    file_path = os.path.join(os.path.dirname(__file__), '..', 'data', f"{table_name}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    
    st.error(f"Could not load data for {table_name}. Ensure DB is running or CSV exists in data/")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_customer_segments():
    return load_table('ml_customer_segments')

@st.cache_data(ttl=3600)
def get_churn_predictions():
    return load_table('ml_churn_predictions')

@st.cache_data(ttl=3600)
def get_clv_predictions():
    return load_table('ml_clv_predictions')

@st.cache_data(ttl=3600)
def get_seller_scores():
    return load_table('ml_seller_scores')

@st.cache_data(ttl=3600)
def get_seller_churn():
    return load_table('ml_seller_churn')

@st.cache_data(ttl=3600)
def get_delivery_risk():
    return load_table('ml_delivery_risk')

@st.cache_data(ttl=3600)
def get_review_predictions():
    return load_table('ml_review_predictions')

@st.cache_data(ttl=3600)
def get_obt_customers():
    return load_table('obt_customers')

@st.cache_data(ttl=3600)
def get_obt_sellers():
    return load_table('obt_sellers')

@st.cache_data(ttl=3600)
def get_obt_orders():
    return load_table('obt_orders')
