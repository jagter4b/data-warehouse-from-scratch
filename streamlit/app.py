import streamlit as st
import pandas as pd
import os

st.set_page_config(
    page_title="Olist ML Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from components.filters import load_css, sidebar_header, last_updated
from components.db import get_summary, _ml_segments, _ml_seller_sc
from components.charts import bar, gauge, PALETTE

load_css()
sidebar_header("Home · Overview")

# ─── Header ──────────────────────────────────────────────────────
st.title("Olist ML Analytics")
st.markdown(
    '<p style="color:#52525B;font-size:15px;margin-top:-8px;margin-bottom:28px;">'
    'Predictive Intelligence Dashboard &nbsp;·&nbsp; Brazilian E-Commerce Dataset 2016–2018'
    '</p>',
    unsafe_allow_html=True,
)

with st.spinner("Loading pipeline summary…"):
    s = get_summary()

# ─── KPI Row ─────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Customers Scored",    f"{s['n_customers']:,}")
c2.metric("Sellers Scored",      f"{s['n_sellers']:,}")
c3.metric("Orders Scored",       f"{s['n_orders']:,}")
c4.metric("Predicted Churn",     f"{s['churn_rate']:.1f}%",
          help="% of customers predicted inactive (>120 days). High because Olist buyers are typically one-time.")
c5.metric("On-Time Delivery",    f"{s['ontime_rate']:.1f}%")
c6.metric("Avg Predicted Score", f"{s['avg_review']:.2f} ★")

st.markdown("---")

# ─── Model Registry + Visual ─────────────────────────────────────
st.markdown("## 🧠 Model Registry")

MODELS = [
    {"Model":"RFM Segmentation",  "Domain":"Customer","Algorithm":"K-Means (k=4)",    "Metric":"Silhouette","Score":0.4788,"Rows":96097, "Status":"✅ Optimal"},
    {"Model":"Churn Prediction",  "Domain":"Customer","Algorithm":"XGBoost / RF",      "Metric":"AUC-ROC",   "Score":0.6829,"Rows":96096, "Status":"🟡 Acceptable"},
    {"Model":"CLV Prediction",    "Domain":"Customer","Algorithm":"XGBoost Regressor", "Metric":"R²",        "Score":0.1710,"Rows":95135, "Status":"ℹ️ Honest Baseline"},
    {"Model":"Seller Scoring",    "Domain":"Seller",  "Algorithm":"K-Means (k=3)",     "Metric":"Silhouette","Score":0.5679,"Rows":3096,  "Status":"✅ Optimal"},
    {"Model":"Seller Churn",      "Domain":"Seller",  "Algorithm":"XGBoost",           "Metric":"AUC-ROC",   "Score":0.7846,"Rows":3096,  "Status":"✅ Optimal"},
    {"Model":"Delivery Risk",     "Domain":"Order",   "Algorithm":"XGBoost",           "Metric":"AUC-ROC",   "Score":0.7483,"Rows":98651, "Status":"🟡 Acceptable"},
    {"Model":"Review Prediction", "Domain":"Order",   "Algorithm":"XGBoost Regressor", "Metric":"RMSE",      "Score":1.1311,"Rows":96460, "Status":"🟡 Acceptable"},
]
df_m = pd.DataFrame(MODELS)

col_chart, col_gauge = st.columns([3, 2])

with col_chart:
    dom_colors = {"Customer":"#7C3AED","Seller":"#06B6D4","Order":"#F59E0B"}
    fig = bar(df_m, "Model", "Score", "Model Performance Scores by Domain",
              color_col="Domain", cmap=dom_colors)
    fig.update_layout(height=320)
    # Add a reference line at 0.70
    fig.add_hline(y=0.70, line_dash="dot", line_color="#52525B", line_width=1.2,
                  annotation_text="AUC 0.70 target",
                  annotation_font_color="#52525B", annotation_font_size=11)
    st.plotly_chart(fig, use_container_width=True)

with col_gauge:
    auc_scores = [0.6829, 0.7846, 0.7483]
    avg_auc = sum(auc_scores) / len(auc_scores) * 100
    fig_g = gauge(round(avg_auc, 1), "Avg Classifier AUC",
                  lo=60, hi=75, c_lo="#F43F5E", c_mid="#F59E0B", c_hi="#10B981")
    st.plotly_chart(fig_g, use_container_width=True)

st.dataframe(df_m, use_container_width=True, hide_index=True)

st.markdown("---")

# ─── Navigation Cards ────────────────────────────────────────────
st.markdown("## 🗺️ Dashboards")

CARDS = [
    ("👥", "Customer Intelligence",
     "Explore RFM behavioral segments across 96k customers, rank churn risk by probability tier, and predict lifetime value with XGBoost.",
     ["RFM Segments", "Churn Risk", "CLV"]),
    ("🏪", "Seller Intelligence",
     "Composite performance scoring across 3,096 sellers with KMeans clustering. Identify the 24 top performers and predict dropout probability.",
     ["Performance", "Churn Risk"]),
    ("📦", "Order Intelligence",
     "Pre-dispatch delivery delay detection and post-delivery review score forecasting across 99k orders.",
     ["Delivery Risk", "Review Prediction"]),
]

cols = st.columns(3)
for col, (icon, title, desc, chips) in zip(cols, CARDS):
    chip_html = "".join(f'<span class="oc-chip">{c}</span>' for c in chips)
    with col:
        st.markdown(
            f"""
            <div class="olist-card">
              <span class="oc-icon">{icon}</span>
              <div class="oc-title">{title}</div>
              <div class="oc-desc">{desc}</div>
              <div class="oc-chips">{chip_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("")
st.caption(
    "Medallion Architecture: Bronze → Silver → Gold → ML  ·  "
    "7 predictive models  ·  3 One-Big-Tables  ·  ~300k scored records"
)

last_updated(s["scored_at"])
