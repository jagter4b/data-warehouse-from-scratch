"""
pages/2_Delivery_Analytics.py
──────────────────────────────
Delivery performance analysis and XGBoost delay risk predictions.
"""

import os, sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(
    page_title="Delivery Analytics — Olist Analytics",
    page_icon="🚚",
    layout="wide",
)

css_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")
with open(css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from components.db import load_obt, demo_banner

df_raw, is_demo = load_obt()
if is_demo:
    demo_banner()

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style='text-align:center; padding: 1rem 0 1.5rem;'>
  <div style='font-size:2rem;'>🏭</div>
  <div style='font-family:"Space Grotesk",sans-serif; font-size:1.1rem; font-weight:700;
              background:linear-gradient(135deg,#8b5cf6,#14b8a6);
              -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>
    Olist Analytics
  </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("## 🔍 Filters")
years = sorted(df_raw["purchase_year"].dropna().unique().astype(int).tolist())
sel_years = st.sidebar.multiselect("Purchase Year", years, default=years)
df = df_raw[
    df_raw["purchase_year"].isin(sel_years) &
    (df_raw["order_status"] == "delivered")
].copy() if sel_years else df_raw[df_raw["order_status"] == "delivered"].copy()

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class='page-header'>
  <h1>🚚 Delivery Analytics</h1>
  <p>Delivery performance KPIs, delay risk prediction (XGBoost AUC 0.80), and category-level insights.</p>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
on_time_pct     = df["is_delivered_on_time"].mean() * 100 if "is_delivered_on_time" in df else 0
avg_deliver     = df["days_to_deliver"].mean()
avg_variance    = df["days_delivery_variance"].mean()
late_orders     = (~df["is_delivered_on_time"].astype(bool)).sum()
high_risk       = (df["delay_risk_tier"] == "High").sum() if "delay_risk_tier" in df.columns else 0
avg_risk_score  = df["delay_risk_score"].mean() if "delay_risk_score" in df.columns else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("✅ On-Time Delivery",   f"{on_time_pct:.0f}%")
k2.metric("📅 Avg Delivery Days",  f"{avg_deliver:.0f} days")
k3.metric("⏱️ Avg Variance",       f"{avg_variance:.0f} days",
          delta=f"{'early' if avg_variance < 0 else 'late'}")
k4.metric("❌ Late Orders",         f"{late_orders:,}")
k5.metric("🔴 High Delay Risk",     f"{high_risk:,}")

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 1: Delay risk tier + On-time gauge ────────────────────────────────────
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("<div class='section-title'>⚠️ Delay Risk Score Distribution (XGBoost)</div>", unsafe_allow_html=True)
    if "delay_risk_score" in df.columns and df["delay_risk_score"].notna().any():
        fig_hist = px.histogram(
            df.dropna(subset=["delay_risk_score"]),
            x="delay_risk_score", nbins=50,
            color="delay_risk_tier" if "delay_risk_tier" in df.columns else None,
            color_discrete_map={"Low": "#22c55e", "Medium": "#f59e0b", "High": "#f43f5e"},
            labels={"delay_risk_score": "Delay Probability", "count": "Orders"},
            barmode="overlay",
        )
        fig_hist.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=320, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(title="Risk", orientation="h", y=-0.15),
            font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Run `ml_delivery_risk.py --execute` to populate delay risk data.")

with col2:
    st.markdown("<div class='section-title'>🎯 Risk Tier Breakdown</div>", unsafe_allow_html=True)
    if "delay_risk_tier" in df.columns and df["delay_risk_tier"].notna().any():
        tier_counts = df["delay_risk_tier"].value_counts().reset_index()
        tier_counts.columns = ["tier", "count"]
        fig_pie = px.pie(
            tier_counts, names="tier", values="count",
            color="tier",
            color_discrete_map={"Low": "#22c55e", "Medium": "#f59e0b", "High": "#f43f5e"},
            hole=0.55,
        )
        fig_pie.update_traces(textinfo="label+percent", textfont_size=11)
        fig_pie.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            height=280, margin=dict(l=0, r=0, t=10, b=10),
            showlegend=False, font=dict(family="Inter", color="#94a3b8"),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with col3:
    st.markdown("<div class='section-title'>📊 On-Time Gauge</div>", unsafe_allow_html=True)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=on_time_pct,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "On-Time Rate", "font": {"size": 14, "color": "#94a3b8"}},
        number={"suffix": "%", "font": {"size": 28, "color": "#f1f5f9"}},
        delta={"reference": 90, "relative": False, "valueformat": ".1f"},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#475569"},
            "bar":  {"color": "#8b5cf6"},
            "steps": [
                {"range": [0, 70],   "color": "rgba(244,63,94,0.15)"},
                {"range": [70, 90],  "color": "rgba(245,158,11,0.15)"},
                {"range": [90, 100], "color": "rgba(34,197,94,0.15)"},
            ],
            "threshold": {"line": {"color": "#22c55e", "width": 2}, "value": 90},
            "bgcolor": "rgba(0,0,0,0)",
        },
    ))
    fig_gauge.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        height=280, margin=dict(l=20, r=20, t=20, b=10),
        font=dict(family="Inter"),
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 2: Delivery days histogram + Category performance ─────────────────────
col4, col5 = st.columns(2)

with col4:
    st.markdown("<div class='section-title'>📦 Delivery Time Distribution</div>", unsafe_allow_html=True)
    deliver_data = df["days_to_deliver"].dropna()
    deliver_data = deliver_data[deliver_data.between(0, 60)]

    fig_deliver = px.histogram(
        deliver_data, nbins=40,
        color_discrete_sequence=["#8b5cf6"],
        labels={"value": "Days to Deliver", "count": "Orders"},
    )
    fig_deliver.add_vline(
        x=deliver_data.mean(), line_dash="dot", line_color="#14b8a6",
        annotation_text=f"Mean: {deliver_data.mean():.1f}d",
        annotation_font_color="#14b8a6",
    )
    fig_deliver.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=0, r=0, t=10, b=0),
        font=dict(family="Inter", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig_deliver, use_container_width=True)

with col5:
    st.markdown("<div class='section-title'>📂 On-Time Rate by Product Category (Top 12)</div>", unsafe_allow_html=True)
    cat_perf = (
        df.groupby("product_category_name")
        .agg(orders=("order_id", "count"), on_time=("is_delivered_on_time", "mean"))
        .reset_index()
    )
    cat_perf = cat_perf[cat_perf["orders"] >= 100].sort_values("on_time", ascending=True).tail(12)
    cat_perf["on_time_pct"] = cat_perf["on_time"] * 100

    fig_cat = px.bar(
        cat_perf, x="on_time_pct", y="product_category_name",
        orientation="h",
        color="on_time_pct",
        color_continuous_scale=["#f43f5e", "#f59e0b", "#22c55e"],
        range_color=[85, 100],
        labels={"on_time_pct": "On-Time %", "product_category_name": ""},
        text="on_time_pct",
    )
    fig_cat.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_cat.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=0, r=60, t=10, b=0),
        coloraxis_showscale=False,
        font=dict(family="Inter", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", range=[0, 105]),
    )
    st.plotly_chart(fig_cat, use_container_width=True)

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 3: Variance over time + Predicted vs actual satisfaction ──────────────
col6, col7 = st.columns(2)

with col6:
    st.markdown("<div class='section-title'>📈 Delivery Variance Over Time</div>", unsafe_allow_html=True)
    monthly_var = (
        df.groupby(["purchase_year", "purchase_month"])["days_delivery_variance"]
        .mean().reset_index()
    )
    monthly_var["period"] = pd.to_datetime(
        monthly_var["purchase_year"].astype(str) + "-" +
        monthly_var["purchase_month"].astype(str).str.zfill(2)
    )
    monthly_var = monthly_var.sort_values("period")

    fig_var = go.Figure()
    fig_var.add_trace(go.Scatter(
        x=monthly_var["period"],
        y=monthly_var["days_delivery_variance"],
        mode="lines+markers",
        line=dict(color="#14b8a6", width=2),
        fill="tozeroy",
        fillcolor="rgba(20,184,166,0.08)",
        name="Avg Variance",
    ))
    fig_var.add_hline(y=0, line_dash="dot", line_color="#475569")
    fig_var.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
        font=dict(family="Inter", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)", title="Days (negative = early)"),
        annotations=[dict(text="🟢 Early delivery = negative", x=0.01, y=0.02,
                          xref="paper", yref="paper", showarrow=False,
                          font=dict(color="#475569", size=10))],
    )
    st.plotly_chart(fig_var, use_container_width=True)

with col7:
    st.markdown("<div class='section-title'>🔮 Predicted vs Actual Review Scores</div>", unsafe_allow_html=True)
    if "predicted_review_score" in df.columns and df["predicted_review_score"].notna().any():
        compare = df.dropna(subset=["review_score", "predicted_review_score"]).sample(
            min(3000, len(df)), random_state=42
        )
        fig_compare = px.scatter(
            compare,
            x="review_score", y="predicted_review_score",
            color="delay_risk_tier" if "delay_risk_tier" in df.columns else None,
            color_discrete_map={"Low": "#22c55e", "Medium": "#f59e0b", "High": "#f43f5e"},
            opacity=0.4,
            labels={"review_score": "Actual Score", "predicted_review_score": "Predicted Score"},
        )
        fig_compare.add_shape(
            type="line", x0=1, y0=1, x1=5, y1=5,
            line=dict(color="#475569", dash="dot"),
        )
        fig_compare.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=280, margin=dict(l=0, r=0, t=10, b=0),
            font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            legend=dict(title="Delay Risk"),
        )
        st.plotly_chart(fig_compare, use_container_width=True)
    else:
        st.info("Run `ml_review_prediction.py --execute` to populate prediction data.")
