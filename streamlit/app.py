"""
app.py — Overview / Landing Page
─────────────────────────────────
Main entry point for the Olist Analytics Streamlit dashboard.
Shows business-level KPIs and trends.
"""

import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Olist Analytics — Overview",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject CSS ────────────────────────────────────────────────────────────────
css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
with open(css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from components.db import load_obt, demo_banner

# ── Load data ─────────────────────────────────────────────────────────────────
df_raw, is_demo = load_obt()
if is_demo:
    demo_banner()

df = df_raw.copy()

# Sidebar brand
st.sidebar.markdown("""
<div style='text-align:center; padding: 1rem 0 1.5rem;'>
  <div style='font-size:2rem;'>🏭</div>
  <div style='font-family:"Space Grotesk",sans-serif; font-size:1.1rem; font-weight:700; 
              background:linear-gradient(135deg,#8b5cf6,#14b8a6);
              -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>
    Olist Analytics
  </div>
  <div style='color:#475569; font-size:0.72rem; margin-top:0.25rem;'>ML-Powered Intelligence</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar year filter ───────────────────────────────────────────────────────
st.sidebar.markdown("## 🔍 Filters")
years = sorted(df["purchase_year"].dropna().unique().astype(int).tolist())
selected_years = st.sidebar.multiselect("Purchase Year", options=years, default=years)
df = df[df["purchase_year"].isin(selected_years)] if selected_years else df

delivered = df[df["order_status"] == "delivered"]

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class='page-header'>
  <h1>📊 Business Overview</h1>
  <p>End-to-end view of Olist marketplace performance — orders, revenue, delivery and satisfaction.</p>
</div>
""", unsafe_allow_html=True)

# ── Top KPI row ───────────────────────────────────────────────────────────────
total_orders    = len(delivered)
total_revenue   = delivered["total_order_value"].sum()
avg_order_val   = delivered["total_order_value"].mean()
on_time_pct     = delivered["is_delivered_on_time"].mean() * 100 if "is_delivered_on_time" in delivered.columns else 0
avg_review      = delivered["review_score"].mean()
total_customers = delivered["customer_unique_id"].nunique()

k1, k2, k3, k4, k5, k6 = st.columns(6)
metrics = [
    (k1, "Total Orders",     f"{total_orders:,}",           "📦"),
    (k2, "Total Revenue",    f"R${total_revenue/1e6:.0f}M", "💰"),
    (k3, "Avg Order Value",  f"R${avg_order_val:.0f}",      "🛒"),
    (k4, "On-Time Rate",     f"{on_time_pct:.0f}%",         "🚚"),
    (k5, "Avg Review Score", f"{avg_review:.0f} ⭐",         "⭐"),
    (k6, "Unique Customers", f"{total_customers:,}",        "👥"),
]
for col, label, value, icon in metrics:
    col.metric(label=f"{icon} {label}", value=value)

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 1: Orders over time + Revenue by state ────────────────────────────────
col_left, col_right = st.columns([2, 1])

with col_left:
    st.markdown("<div class='section-title'>📅 Orders Over Time</div>", unsafe_allow_html=True)
    monthly = (
        delivered
        .groupby(["purchase_year", "purchase_month"])
        .agg(orders=("order_id", "count"), revenue=("total_order_value", "sum"))
        .reset_index()
    )
    monthly["period"] = pd.to_datetime(
        monthly["purchase_year"].astype(str) + "-" + monthly["purchase_month"].astype(str).str.zfill(2)
    )
    monthly = monthly.sort_values("period")

    fig_time = go.Figure()
    fig_time.add_trace(go.Scatter(
        x=monthly["period"], y=monthly["orders"],
        mode="lines+markers", name="Orders",
        line=dict(color="#8b5cf6", width=2.5),
        marker=dict(size=5),
        fill="tozeroy",
        fillcolor="rgba(139,92,246,0.08)",
    ))
    fig_time.add_trace(go.Scatter(
        x=monthly["period"], y=monthly["revenue"] / 1000,
        mode="lines", name="Revenue (R$K)",
        line=dict(color="#14b8a6", width=2, dash="dot"),
        yaxis="y2"
    ))
    fig_time.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=0, r=10, t=10, b=0),
        legend=dict(orientation="h", y=-0.15),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)", title="Orders"),
        yaxis2=dict(title="Revenue (R$K)", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
        font=dict(family="Inter", color="#94a3b8"),
    )
    st.plotly_chart(fig_time, use_container_width=True)

with col_right:
    st.markdown("<div class='section-title'>🗺️ Revenue by State</div>", unsafe_allow_html=True)
    state_rev = (
        delivered.groupby("customer_state")["total_order_value"]
        .sum().reset_index()
        .sort_values("total_order_value", ascending=True).tail(12)
    )
    fig_state = px.bar(
        state_rev, x="total_order_value", y="customer_state",
        orientation="h",
        color="total_order_value",
        color_continuous_scale=["#1e1b4b", "#8b5cf6", "#14b8a6"],
        labels={"total_order_value": "Revenue (R$)", "customer_state": "State"},
    )
    fig_state.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=0, r=0, t=10, b=0),
        coloraxis_showscale=False,
        font=dict(family="Inter", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig_state, use_container_width=True)

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 2: Review Distribution + Payment types + Top categories ───────────────
col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("<div class='section-title'>⭐ Review Score Distribution</div>", unsafe_allow_html=True)
    review_dist = delivered["review_score"].value_counts().sort_index().reset_index()
    review_dist.columns = ["score", "count"]
    colors = ["#f43f5e", "#f59e0b", "#facc15", "#14b8a6", "#22c55e"]
    fig_rev = px.bar(review_dist, x="score", y="count",
                     color="score", color_continuous_scale=colors,
                     labels={"score": "Stars", "count": "Orders"})
    fig_rev.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
        coloraxis_showscale=False,
        font=dict(family="Inter", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickmode="linear"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig_rev, use_container_width=True)

with col_b:
    st.markdown("<div class='section-title'>💳 Payment Method Mix</div>", unsafe_allow_html=True)
    pay_dist = delivered["payment_type"].value_counts().reset_index()
    pay_dist.columns = ["type", "count"]
    fig_pay = px.pie(pay_dist, names="type", values="count",
                     color_discrete_sequence=["#8b5cf6", "#14b8a6", "#f59e0b", "#f43f5e", "#22c55e"],
                     hole=0.55)
    fig_pay.update_traces(textfont_size=11, textinfo="label+percent")
    fig_pay.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        height=280, margin=dict(l=0, r=0, t=10, b=10),
        showlegend=False, font=dict(family="Inter", color="#94a3b8"),
    )
    st.plotly_chart(fig_pay, use_container_width=True)

with col_c:
    st.markdown("<div class='section-title'>📦 Top Product Categories</div>", unsafe_allow_html=True)
    top_cats = (
        delivered.groupby("product_category_name")["total_order_value"]
        .sum().reset_index()
        .sort_values("total_order_value", ascending=False).head(10)
    )
    fig_cats = px.bar(
        top_cats, x="total_order_value", y="product_category_name",
        orientation="h",
        color_discrete_sequence=["#8b5cf6"],
        labels={"total_order_value": "Revenue (R$)", "product_category_name": ""},
    )
    fig_cats.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=280, margin=dict(l=0, r=0, t=10, b=0),
        yaxis=dict(autorange="reversed"),
        font=dict(family="Inter", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig_cats, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center; color:#475569; font-size:0.75rem; margin-top:2rem; padding:1rem;
            border-top:1px solid rgba(255,255,255,0.06);'>
  Olist Analytics Platform · Built with Python, SQL Server & Streamlit · 2016–2018 Dataset
</div>
""", unsafe_allow_html=True)
