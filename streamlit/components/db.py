"""
db.py — Data loading layer for Olist ML Analytics.
Tries live DB (Streamlit secrets / .env) then falls back to CSV exports.
Each public getter returns an enriched DataFrame (ML result + relevant OBT columns).
"""
import os
import streamlit as st
import pandas as pd


# ── Engine ───────────────────────────────────────────────────────
def _engine():
    try:
        from sqlalchemy import create_engine
        host = st.secrets.get("DB_HOST", os.getenv("DEST_DB_HOST", ""))
        port = st.secrets.get("DB_PORT", os.getenv("DEST_DB_PORT", "1433"))
        db   = (st.secrets.get("DB_NAME", os.getenv("DEST_DB_NAME", "olist_dw")) or "").strip()
        if not host:
            return None
        cs = (f"mssql+pyodbc://@{host}:{port}/{db}"
              "?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes")
        return create_engine(cs)
    except Exception:
        return None


def _csv_dir():
    return os.path.join(os.path.dirname(__file__), "..", "data")


def _load(name: str) -> pd.DataFrame:
    """DB first, CSV fallback."""
    eng = _engine()
    if eng:
        try:
            return pd.read_sql(f"SELECT * FROM gold.{name}", eng)
        except Exception:
            pass
    path = os.path.join(_csv_dir(), f"{name}.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    st.error(f"Cannot load `{name}` — no DB and no CSV found in streamlit/data/")
    return pd.DataFrame()


# ── Raw cached loaders ────────────────────────────────────────────
@st.cache_data(ttl=86400)
def _ml_segments():    return _load("ml_customer_segments")
@st.cache_data(ttl=86400)
def _ml_churn():       return _load("ml_churn_predictions")
@st.cache_data(ttl=86400)
def _ml_clv():         return _load("ml_clv_predictions")
@st.cache_data(ttl=86400)
def _ml_seller_sc():   return _load("ml_seller_scores")
@st.cache_data(ttl=86400)
def _ml_seller_ch():   return _load("ml_seller_churn")
@st.cache_data(ttl=86400)
def _ml_delivery():    return _load("ml_delivery_risk")
@st.cache_data(ttl=86400)
def _ml_reviews():     return _load("ml_review_predictions")
@st.cache_data(ttl=86400)
def _obt_customers():  return _load("obt_customers")
@st.cache_data(ttl=86400)
def _obt_sellers():    return _load("obt_sellers")
@st.cache_data(ttl=86400)
def _obt_orders():     return _load("obt_orders")


# ── Public enriched getters ───────────────────────────────────────
@st.cache_data(ttl=86400)
def get_rfm() -> pd.DataFrame:
    ml  = _ml_segments()
    obt = _obt_customers()[["customer_unique_id", "total_spend",
                             "days_since_last_order", "customer_state",
                             "top_category", "total_orders"]]
    return ml.merge(obt, on="customer_unique_id", how="left")


@st.cache_data(ttl=86400)
def get_churn() -> pd.DataFrame:
    ml  = _ml_churn()
    obt = _obt_customers()[["customer_unique_id", "total_spend",
                             "total_orders", "customer_state",
                             "avg_review_score"]]
    return ml.merge(obt, on="customer_unique_id", how="left")


@st.cache_data(ttl=86400)
def get_clv() -> pd.DataFrame:
    ml  = _ml_clv()
    obt = _obt_customers()[["customer_unique_id", "total_spend",
                             "total_orders", "customer_tenure_days",
                             "distinct_months_active"]]
    return ml.merge(obt, on="customer_unique_id", how="left")


@st.cache_data(ttl=86400)
def get_seller_scores() -> pd.DataFrame:
    ml  = _ml_seller_sc()
    obt = _obt_sellers()[["seller_id", "was_acquired_via_mql",
                           "seller_state", "total_distinct_customers_served",
                           "total_items_sold", "pct_5star_reviews"]]
    return ml.merge(obt, on="seller_id", how="left")


@st.cache_data(ttl=86400)
def get_seller_churn() -> pd.DataFrame:
    ml  = _ml_seller_ch()
    obt = _obt_sellers()[["seller_id", "total_revenue",
                           "was_acquired_via_mql", "avg_review_score",
                           "total_orders_fulfilled"]]
    return ml.merge(obt, on="seller_id", how="left")


@st.cache_data(ttl=86400)
def get_delivery() -> pd.DataFrame:
    ml  = _ml_delivery()
    obt = _obt_orders()[["order_id", "total_order_value",
                          "primary_category", "purchase_month",
                          "purchase_day_of_week", "days_to_deliver",
                          "total_items"]]
    return ml.merge(obt, on="order_id", how="left")


@st.cache_data(ttl=86400)
def get_reviews() -> pd.DataFrame:
    ml  = _ml_reviews()
    obt = _obt_orders()[["order_id", "purchase_month",
                          "purchase_day_of_week", "days_to_deliver",
                          "is_late", "total_order_value", "c_scheduled_vs_actual_days"]]
    return ml.merge(obt, on="order_id", how="left")


# ── Home-page summary stats (light, just ML tables) ───────────────
@st.cache_data(ttl=86400)
def get_summary():
    seg  = _ml_segments()
    ch   = _ml_churn()
    ss   = _ml_seller_sc()
    dl   = _ml_delivery()
    rv   = _ml_reviews()
    return dict(
        n_customers = len(seg),
        n_sellers   = len(ss),
        n_orders    = len(dl),
        churn_rate  = ch["churn_predicted"].mean() * 100 if not ch.empty else 0,
        ontime_rate = (1 - dl["delay_predicted"].mean()) * 100 if not dl.empty else 0,
        avg_review  = rv["predicted_review_score"].mean() if not rv.empty else 0,
        scored_at   = seg["scored_at"].iloc[0] if "scored_at" in seg.columns else "Unknown",
    )
