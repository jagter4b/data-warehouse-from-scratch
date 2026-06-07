"""
components/db.py
─────────────────
Database connection + data loader with automatic CSV fallback (demo mode).

If SQL Server is unreachable (e.g., on Streamlit Cloud), the app falls
back to loading from streamlit/data/obt_master.csv.
"""

from __future__ import annotations

import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "obt_master.csv")

# ─────────────────────────────────────────────
# Engine factory (cached so we only connect once)
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _get_engine():
    try:
        from sqlalchemy import create_engine
        host = os.getenv("DEST_DB_HOST", "localhost")
        port = os.getenv("DEST_DB_PORT", "1433")
        db   = os.getenv("DEST_DB_NAME", "BI_AI").strip()
        engine = create_engine(
            f"mssql+pyodbc://@{host}:{port}/{db}"
            f"?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes",
            pool_pre_ping=True,
            connect_args={"timeout": 5},
        )
        # Test connection
        with engine.connect() as c:
            c.execute(__import__("sqlalchemy").text("SELECT 1"))
        return engine, False   # (engine, is_demo)
    except Exception:
        return None, True      # demo mode


# ─────────────────────────────────────────────
# Main data loader
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Loading data...")
def load_obt() -> tuple[pd.DataFrame, bool]:
    """
    Returns (df, is_demo_mode).
    df contains every column from gold.obt_master.
    """
    engine, is_demo = _get_engine()

    if not is_demo:
        try:
            with engine.connect() as conn:
                df = pd.read_sql("SELECT * FROM gold.obt_master", conn)
            df["purchase_date"] = pd.to_datetime(df["purchase_date"])
            return df, False
        except Exception:
            pass

    # Fallback: CSV
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH, low_memory=False)
        df["purchase_date"] = pd.to_datetime(df["purchase_date"])
        return df, True

    raise FileNotFoundError(
        "Cannot reach SQL Server AND no CSV fallback found at "
        f"{CSV_PATH}. Run export_csv.py first."
    )


def demo_banner():
    """Display a banner if running in demo/CSV mode."""
    st.info(
        "📁 **Demo Mode** — Running from CSV snapshot. "
        "Connect to SQL Server for live data.",
        icon="ℹ️",
    )
