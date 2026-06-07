"""
pages/1_Customer_Intelligence.py
─────────────────────────────────
Customer segmentation, churn risk, and lifetime value analysis
powered by K-Means RFM and Random Forest ML outputs.
"""

import os, sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Customer Intelligence — Olist Analytics",
    page_icon="👥",
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

# ── Sidebar brand + filters ───────────────────────────────────────────────────
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

# Customer-level aggregation (one row per customer using latest order data)
cust = (
    df.sort_values("purchase_date", ascending=False)
    .drop_duplicates(subset="customer_unique_id", keep="first")
)

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class='page-header'>
  <h1>👥 Customer Intelligence</h1>
  <p>RFM segmentation (K-Means), churn risk (Random Forest), and customer value insights.</p>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_cust  = cust["customer_unique_id"].nunique()
avg_recency = cust["recency_days"].mean() if "recency_days" in cust else 0
avg_freq    = cust["frequency_orders"].mean() if "frequency_orders" in cust else 0
avg_mon     = cust["monetary_total"].mean() if "monetary_total" in cust else df["total_order_value"].mean()
high_churn  = (cust["churn_risk_tier"] == "High").sum() if "churn_risk_tier" in cust.columns else 0
churn_pct   = high_churn / total_cust * 100 if total_cust else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("👥 Unique Customers",   f"{total_cust:,}")
k2.metric("📅 Avg Recency",        f"{avg_recency:.0f} days" if avg_recency else "N/A")
k3.metric("🔁 Avg Orders/Customer",f"{avg_freq:.0f}" if avg_freq else "N/A")
k4.metric("💰 Avg Lifetime Value", f"R${avg_mon:.0f}")
k5.metric("⚠️ High Churn Risk",    f"{high_churn:,} ({churn_pct:.0f}%)")

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 1: Segment pie + Churn tier bar ──────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown("<div class='section-title'>🎯 RFM Customer Segments (K-Means)</div>", unsafe_allow_html=True)
    if "customer_segment" in cust.columns and cust["customer_segment"].notna().any():
        seg = cust["customer_segment"].value_counts().reset_index()
        seg.columns = ["segment", "count"]
        seg_colors = {
            "Champions":    "#22c55e",
            "Loyal":        "#14b8a6",
            "At Risk":      "#f59e0b",
            "Lost/Inactive":"#f43f5e",
        }
        colors = [seg_colors.get(s, "#8b5cf6") for s in seg["segment"]]
        fig_seg = px.pie(
            seg, names="segment", values="count",
            color="segment",
            color_discrete_map=seg_colors,
            hole=0.52,
        )
        fig_seg.update_traces(textinfo="label+percent", textfont_size=11)
        fig_seg.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            height=330, margin=dict(l=0, r=0, t=10, b=10),
            legend=dict(orientation="h", y=-0.12),
            font=dict(family="Inter", color="#94a3b8"),
        )
        st.plotly_chart(fig_seg, use_container_width=True)

        # Segment stats table
        seg_stats = (
            df[df["customer_segment"].notna()]
            .groupby("customer_segment")
            .agg(
                customers=("customer_unique_id", "nunique"),
                avg_order_value=("total_order_value", "mean"),
                avg_review=("review_score", "mean"),
            )
            .reset_index()
            .sort_values("avg_order_value", ascending=False)
        )
        seg_stats["avg_order_value"] = seg_stats["avg_order_value"].map("R${:.0f}".format)
        seg_stats["avg_review"] = seg_stats["avg_review"].map("{:.2f} ⭐".format)
        st.dataframe(
            seg_stats.rename(columns={
                "customer_segment": "Segment",
                "customers": "Customers",
                "avg_order_value": "Avg Order Value",
                "avg_review": "Avg Review",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Run `ml_customer_segments.py --execute` to populate segment data.")

with col2:
    st.markdown("<div class='section-title'>⚠️ Churn Risk Distribution (Random Forest)</div>", unsafe_allow_html=True)
    if "churn_risk_tier" in cust.columns and cust["churn_risk_tier"].notna().any():
        churn = cust["churn_risk_tier"].value_counts().reset_index()
        churn.columns = ["tier", "count"]
        tier_order = ["Low", "Medium", "High"]
        churn["tier"] = pd.Categorical(churn["tier"], categories=tier_order, ordered=True)
        churn = churn.sort_values("tier")
        tier_colors = {"Low": "#22c55e", "Medium": "#f59e0b", "High": "#f43f5e"}
        fig_churn = px.bar(
            churn, x="tier", y="count",
            color="tier", color_discrete_map=tier_colors,
            labels={"tier": "Risk Tier", "count": "Customers"},
            text="count",
        )
        fig_churn.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_churn.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
            font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig_churn, use_container_width=True)

        # Churn probability histogram
        if "churn_probability" in cust.columns:
            fig_prob = px.histogram(
                cust.dropna(subset=["churn_probability"]),
                x="churn_probability", nbins=40,
                color_discrete_sequence=["#8b5cf6"],
                labels={"churn_probability": "Churn Probability", "count": "Customers"},
                title="",
            )
            fig_prob.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=220, margin=dict(l=0, r=0, t=10, b=0),
                font=dict(family="Inter", color="#94a3b8"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            )
            st.plotly_chart(fig_prob, use_container_width=True)
    else:
        st.info("Run `ml_churn_prediction.py --execute` to populate churn data.")

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 2: RFM heatmap + State map ───────────────────────────────────────────
col3, col4 = st.columns([3, 2])

with col3:
    st.markdown("<div class='section-title'>📊 Revenue by Segment & State (Top 8)</div>", unsafe_allow_html=True)
    if "customer_segment" in df.columns and df["customer_segment"].notna().any():
        top_states = df["customer_state"].value_counts().head(8).index.tolist()
        pivot = (
            df[df["customer_state"].isin(top_states)]
            .groupby(["customer_state", "customer_segment"])["total_order_value"]
            .sum()
            .reset_index()
        )
        fig_heat = px.bar(
            pivot,
            x="customer_state", y="total_order_value",
            color="customer_segment",
            barmode="stack",
            color_discrete_map={
                "Champions":    "#22c55e",
                "Loyal":        "#14b8a6",
                "At Risk":      "#f59e0b",
                "Lost/Inactive":"#f43f5e",
            },
            labels={"total_order_value": "Revenue (R$)", "customer_state": "State",
                    "customer_segment": "Segment"},
        )
        fig_heat.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=320, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", y=-0.2),
            font=dict(family="Inter", color="#94a3b8"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Segment data not available yet.")

with col4:
    st.markdown("<div class='section-title'>📅 Customer Acquisition Trend</div>", unsafe_allow_html=True)
    first_orders = (
        df.groupby("customer_unique_id")["purchase_date"]
        .min().reset_index()
    )
    first_orders["month"] = first_orders["purchase_date"].dt.to_period("M").astype(str)
    monthly_new = first_orders.groupby("month").size().reset_index(name="new_customers")
    monthly_new = monthly_new[monthly_new["month"] >= "2017-01"]  # filter noise

    fig_acq = px.area(
        monthly_new, x="month", y="new_customers",
        color_discrete_sequence=["#14b8a6"],
        labels={"month": "", "new_customers": "New Customers"},
    )
    fig_acq.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=0, r=0, t=10, b=0),
        font=dict(family="Inter", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickangle=45),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig_acq, use_container_width=True)
