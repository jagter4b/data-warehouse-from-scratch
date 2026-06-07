"""
pages/3_Seller_Intelligence.py
───────────────────────────────
Seller performance scoring (Weighted KPI + K-Means) and geographic analysis.
"""

import os, sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Seller Intelligence — Olist Analytics",
    page_icon="🏪",
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

# Seller-level aggregation
seller_agg = (
    df.groupby("seller_id")
    .agg(
        total_orders    = ("order_id", "count"),
        total_revenue   = ("total_order_value", "sum"),
        avg_review      = ("review_score", "mean"),
        pct_on_time     = ("is_delivered_on_time", "mean"),
        seller_tier     = ("seller_tier", "first"),
        seller_score    = ("seller_performance_score", "first"),
        seller_state    = ("seller_state", "first"),
        seller_city     = ("seller_city", "first"),
        marketing_origin= ("marketing_origin", "first"),
    )
    .reset_index()
    .dropna(subset=["seller_id"])
)

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class='page-header'>
  <h1>🏪 Seller Intelligence</h1>
  <p>Seller performance scoring (Weighted KPI + K-Means), geographic distribution, and marketing acquisition analysis.</p>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_sellers  = seller_agg["seller_id"].nunique()
top_sellers    = (seller_agg["seller_tier"] == "Top Seller").sum()
avg_score      = seller_agg["seller_score"].mean() if "seller_score" in seller_agg else 0
avg_rev_seller = seller_agg["total_revenue"].mean()
avg_review_s   = seller_agg["avg_review"].mean()
mkt_sellers    = seller_agg["marketing_origin"].notna().sum()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("🏪 Total Sellers",         f"{total_sellers:,}")
k2.metric("⭐ Top Sellers",            f"{top_sellers:,}")
k3.metric("📊 Avg Performance Score", f"{avg_score:.0f}/100" if avg_score else "N/A")
k4.metric("💰 Avg Revenue/Seller",    f"R${avg_rev_seller:,.0f}")
k5.metric("⭐ Avg Review Score",       f"{avg_review_s:.0f}")
k6.metric("📣 Via Marketing",          f"{mkt_sellers:,}")

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 1: Tier distribution + Score scatter ──────────────────────────────────
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("<div class='section-title'>🏅 Performance Tier Distribution</div>", unsafe_allow_html=True)
    if "seller_tier" in seller_agg.columns and seller_agg["seller_tier"].notna().any():
        tier_counts = seller_agg["seller_tier"].value_counts().reset_index()
        tier_counts.columns = ["tier", "count"]
        tier_colors = {"Top Seller": "#22c55e", "Average": "#14b8a6", "Underperformer": "#f43f5e"}
        fig_tier = px.pie(
            tier_counts, names="tier", values="count",
            color="tier", color_discrete_map=tier_colors,
            hole=0.55,
        )
        fig_tier.update_traces(textinfo="label+percent+value", textfont_size=10)
        fig_tier.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            height=320, margin=dict(l=0, r=0, t=10, b=10),
            showlegend=False, font=dict(family="Inter", color="#94a3b8"),
        )
        st.plotly_chart(fig_tier, use_container_width=True)
    else:
        st.info("Run `ml_seller_performance.py --execute` to populate seller tier data.")

with col2:
    st.markdown("<div class='section-title'>🔢 Performance Score vs Revenue (by Tier)</div>", unsafe_allow_html=True)
    if "seller_score" in seller_agg.columns and seller_agg["seller_score"].notna().any():
        plot_data = seller_agg.dropna(subset=["seller_score", "total_revenue", "seller_tier"])
        plot_data = plot_data[plot_data["total_revenue"] > 0]

        fig_scatter = px.scatter(
            plot_data,
            x="seller_score", y="total_revenue",
            color="seller_tier",
            size="total_orders",
            color_discrete_map={"Top Seller": "#22c55e", "Average": "#14b8a6", "Underperformer": "#f43f5e"},
            hover_data=["seller_id", "avg_review", "pct_on_time"],
            labels={
                "seller_score": "Performance Score (0–100)",
                "total_revenue": "Total Revenue (R$)",
                "seller_tier": "Tier",
                "total_orders": "Orders",
            },
            log_y=True,
            opacity=0.75,
        )
        fig_scatter.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=320, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(title="Tier", orientation="h", y=-0.15),
            font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Run `ml_seller_performance.py --execute` to populate score data.")

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 2: Sellers by state + Marketing origin ───────────────────────────────
col3, col4 = st.columns(2)

with col3:
    st.markdown("<div class='section-title'>🗺️ Revenue by Seller State</div>", unsafe_allow_html=True)
    state_data = (
        seller_agg.groupby("seller_state")
        .agg(sellers=("seller_id", "count"), revenue=("total_revenue", "sum"))
        .reset_index()
        .sort_values("revenue", ascending=False).head(15)
    )
    fig_states = px.bar(
        state_data,
        x="seller_state", y="revenue",
        color="revenue",
        color_continuous_scale=["#1e1b4b", "#8b5cf6", "#14b8a6"],
        labels={"seller_state": "State", "revenue": "Revenue (R$)"},
        text="sellers",
    )
    fig_states.update_traces(
        texttemplate="%{text} sellers", textposition="outside"
    )
    fig_states.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=0, r=0, t=10, b=0),
        coloraxis_showscale=False,
        font=dict(family="Inter", color="#94a3b8"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig_states, use_container_width=True)

with col4:
    st.markdown("<div class='section-title'>📣 Marketing Acquisition Channel</div>", unsafe_allow_html=True)
    mkt_data = seller_agg.dropna(subset=["marketing_origin"])
    if len(mkt_data) > 0:
        mkt_counts = mkt_data["marketing_origin"].value_counts().reset_index()
        mkt_counts.columns = ["channel", "sellers"]
        fig_mkt = px.bar(
            mkt_counts, x="sellers", y="channel",
            orientation="h",
            color="sellers",
            color_continuous_scale=["#1e1b4b", "#8b5cf6", "#14b8a6"],
            labels={"channel": "", "sellers": "Acquired Sellers"},
            text="sellers",
        )
        fig_mkt.update_traces(textposition="outside")
        fig_mkt.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=320, margin=dict(l=0, r=60, t=10, b=0),
            coloraxis_showscale=False,
            yaxis=dict(autorange="reversed"),
            font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig_mkt, use_container_width=True)
    else:
        st.info("No marketing funnel data for filtered sellers.")

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

# ── Row 3: Top sellers table ──────────────────────────────────────────────────
st.markdown("<div class='section-title'>🏆 Top 20 Sellers by Revenue</div>", unsafe_allow_html=True)
top20 = seller_agg.sort_values("total_revenue", ascending=False).head(20)
display_cols = {
    "seller_id": "Seller ID",
    "seller_state": "State",
    "total_orders": "Orders",
    "total_revenue": "Revenue (R$)",
    "avg_review": "Avg Review",
    "pct_on_time": "On-Time %",
    "seller_tier": "Tier",
    "seller_score": "Score",
}
top20_display = top20[[c for c in display_cols if c in top20.columns]].rename(columns=display_cols)

if "Revenue (R$)" in top20_display.columns:
    top20_display["Revenue (R$)"] = top20_display["Revenue (R$)"].map("R${:,.0f}".format)
if "Avg Review" in top20_display.columns:
    top20_display["Avg Review"] = top20_display["Avg Review"].map("{:.2f} ⭐".format)
if "On-Time %" in top20_display.columns:
    top20_display["On-Time %"] = top20_display["On-Time %"].map("{:.1%}".format)
if "Score" in top20_display.columns:
    top20_display["Score"] = top20_display["Score"].map("{:.1f}".format)

top20_display["Seller ID"] = top20_display["Seller ID"].str[:12] + "..."
st.dataframe(top20_display, use_container_width=True, hide_index=True, height=450)
