import streamlit as st
import pandas as pd
import os

st.set_page_config(
    page_title="Olist ML Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
css_path = os.path.join(os.path.dirname(__file__), 'assets', 'style.css')
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

from components.db import (
    get_customer_segments, get_churn_predictions, get_clv_predictions,
    get_seller_scores, get_seller_churn, get_delivery_risk, get_review_predictions
)

st.title("📊 Olist ML Analytics")
st.subheader("Predictive Intelligence across Customers, Sellers and Orders")

with st.spinner("Loading pipeline health..."):
    # Load just enough data to get counts
    df_cust = get_customer_segments()
    df_sell = get_seller_scores()
    df_ord = get_delivery_risk()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Customers Scored", f"{len(df_cust):,}" if not df_cust.empty else "N/A")
    with col2:
        st.metric("Total Sellers Scored", f"{len(df_sell):,}" if not df_sell.empty else "N/A")
    with col3:
        st.metric("Total Orders Scored", f"{len(df_ord):,}" if not df_ord.empty else "N/A")
    with col4:
        st.metric("Models Deployed", "7")

st.markdown("---")
st.markdown("### Model Performance Summary")

# Static summary table as per request
perf_data = [
    {"Model": "RFM Segmentation", "Domain": "Customer", "Algorithm": "K-Means", "Key Metric": "Silhouette", "Score": 0.4788, "Status": "🟩 Optimal"},
    {"Model": "Churn Prediction", "Domain": "Customer", "Algorithm": "Random Forest", "Key Metric": "AUC-ROC", "Score": 0.6829, "Status": "🟨 Acceptable"},
    {"Model": "CLV Prediction", "Domain": "Customer", "Algorithm": "XGBoost", "Key Metric": "R²", "Score": 0.1710, "Status": "🟩 Honest Baseline"},
    {"Model": "Seller Scores", "Domain": "Seller", "Algorithm": "K-Means", "Key Metric": "Silhouette", "Score": 0.5679, "Status": "🟩 Optimal"},
    {"Model": "Seller Churn", "Domain": "Seller", "Algorithm": "XGBoost", "Key Metric": "AUC-ROC", "Score": 0.7846, "Status": "🟩 Optimal"},
    {"Model": "Delivery Risk", "Domain": "Order", "Algorithm": "XGBoost", "Key Metric": "AUC-ROC", "Score": 0.7483, "Status": "🟨 Acceptable"},
    {"Model": "Review Prediction", "Domain": "Order", "Algorithm": "XGBoost", "Key Metric": "RMSE", "Score": 1.1311, "Status": "🟩 Acceptable"}
]
df_perf = pd.DataFrame(perf_data)
st.dataframe(df_perf, use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### Navigation")

colA, colB, colC = st.columns(3)
with colA:
    st.info("**Customer Intelligence**\n\nAnalyze segmentation, churn risk, and lifetime value.\n\n*Models: Segments, Churn, CLV*")
with colB:
    st.info("**Seller Intelligence**\n\nEvaluate seller performance clusters and dropout risks.\n\n*Models: Performance, Churn*")
with colC:
    st.info("**Order Intelligence**\n\nPredict delivery delays and forecast customer satisfaction.\n\n*Models: Delivery, Reviews*")

st.markdown("---")
st.caption("Built on Medallion Architecture | Gold Layer | Olist Dataset 2016-2018")
