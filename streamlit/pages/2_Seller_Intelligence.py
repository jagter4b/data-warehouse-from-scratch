import streamlit as st
import pandas as pd
from components.db import get_seller_scores, get_seller_churn, get_obt_sellers
from components.charts import make_bar_chart, make_scatter_plot, make_histogram
from components.filters import render_sidebar_header, render_multiselect, render_slider, render_reset_button, render_last_updated

st.set_page_config(page_title="Seller Intelligence", page_icon="🏪", layout="wide")

import os
css_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'style.css')
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.title("🏪 Seller Intelligence")

with st.spinner("Loading Seller Data..."):
    df_scores = get_seller_scores()
    df_churn = get_seller_churn()
    df_obt = get_obt_sellers()

if df_scores.empty or df_churn.empty or df_obt.empty:
    st.error("Failed to load one or more seller datasets.")
    st.stop()

last_updated = df_scores['scored_at'].iloc[0] if 'scored_at' in df_scores.columns and not df_scores.empty else "Unknown"

render_sidebar_header()

tab1, tab2 = st.tabs(["Seller Performance", "Seller Churn Risk"])

with tab1:
    st.header("Seller Performance")
    
    st.sidebar.markdown("### Performance Filters")
    all_tiers = sorted(df_scores['cluster_label'].unique().tolist())
    selected_tiers = render_multiselect("Select Performance Tiers", all_tiers)
    
    min_score, max_score = float(df_scores['composite_score'].min()), float(df_scores['composite_score'].max())
    selected_score_range = render_slider("Composite Score Range", min_score, max_score)
    
    mql_option = st.sidebar.radio("Was Acquired via MQL", ["All", "MQL", "Non-MQL"])
    
    # Merge with OBT to get MQL flag
    df_merged = pd.merge(df_scores, df_obt[['seller_id', 'was_acquired_via_mql']], on='seller_id', how='left')
    
    df_filtered = df_merged[
        (df_merged['cluster_label'].isin(selected_tiers)) &
        (df_merged['composite_score'] >= selected_score_range[0]) &
        (df_merged['composite_score'] <= selected_score_range[1])
    ]
    
    if mql_option == "MQL":
        df_filtered = df_filtered[df_filtered['was_acquired_via_mql'] == 1]
    elif mql_option == "Non-MQL":
        df_filtered = df_filtered[df_filtered['was_acquired_via_mql'] == 0]
        
    top = len(df_filtered[df_filtered['cluster_label'] == 'Top Performer'])
    avg_comp = df_filtered['composite_score'].mean() if len(df_filtered) > 0 else 0
    avg_rev = df_filtered['avg_review_score'].mean() if len(df_filtered) > 0 else 0
    avg_late = df_filtered['pct_late_deliveries'].mean() if len(df_filtered) > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Top Performers Count", f"{top:,}")
    c2.metric("Avg Composite Score", f"{avg_comp:.1f}")
    c3.metric("Avg Review Score", f"{avg_rev:.2f}")
    c4.metric("Avg Late Delivery %", f"{avg_late:.1f}%")
    
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        tier_counts = df_filtered['cluster_label'].value_counts().reset_index()
        tier_counts.columns = ['cluster_label', 'count']
        st.plotly_chart(make_bar_chart(tier_counts, 'cluster_label', 'count', "Sellers by Performance Tier"), use_container_width=True)
    with r1c2:
        mql_comp = df_merged.groupby('was_acquired_via_mql')['composite_score'].mean().reset_index()
        mql_comp['MQL Status'] = mql_comp['was_acquired_via_mql'].map({1: 'MQL', 0: 'Non-MQL'})
        st.plotly_chart(make_bar_chart(mql_comp, 'MQL Status', 'composite_score', "Avg Composite Score: MQL vs Non-MQL"), use_container_width=True)
        
    st.plotly_chart(make_scatter_plot(df_filtered, 'avg_review_score', 'composite_score', 'cluster_label', "Composite Score vs Avg Review Score", size_col='total_revenue'), use_container_width=True)
    
    st.subheader("Performance Data")
    st.dataframe(df_filtered[['seller_id', 'composite_score', 'cluster_label', 'avg_review_score', 'pct_late_deliveries', 'total_revenue']], use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df_filtered.to_csv(index=False), "seller_performance.csv", "text/csv")


with tab2:
    st.header("Seller Churn Risk")
    
    st.sidebar.markdown("### Churn Filters")
    all_risk_tiers = sorted(df_churn['risk_tier'].unique().tolist())
    selected_risk_tiers = render_multiselect("Select Churn Risk Tiers", all_risk_tiers)
    
    selected_churn_prob = render_slider("Churn Probability", 0.0, 1.0)
    
    # Merge with OBT
    df_churn_merged = pd.merge(df_churn, df_obt[['seller_id', 'total_revenue', 'was_acquired_via_mql']], on='seller_id', how='left')
    
    df_churn_filtered = df_churn_merged[
        (df_churn_merged['risk_tier'].isin(selected_risk_tiers)) &
        (df_churn_merged['churn_probability'] >= selected_churn_prob[0]) &
        (df_churn_merged['churn_probability'] <= selected_churn_prob[1])
    ]
    
    ch_high = len(df_churn_filtered[df_churn_filtered['risk_tier'] == 'High'])
    ch_rate = df_churn_filtered['churn_predicted'].mean() * 100 if len(df_churn_filtered) > 0 else 0
    avg_prob = df_churn_filtered['churn_probability'].mean() if len(df_churn_filtered) > 0 else 0
    mql_high = len(df_churn_filtered[(df_churn_filtered['risk_tier'] == 'High') & (df_churn_filtered['was_acquired_via_mql'] == 1)])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("High Risk Sellers", f"{ch_high:,}")
    c2.metric("Overall Churn Rate", f"{ch_rate:.1f}%")
    c3.metric("Avg Churn Probability", f"{avg_prob:.2f}")
    c4.metric("MQL Sellers at High Risk", f"{mql_high:,}")
    
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        risk_counts = df_churn_filtered['risk_tier'].value_counts().reset_index()
        risk_counts.columns = ['risk_tier', 'count']
        st.plotly_chart(make_bar_chart(risk_counts, 'risk_tier', 'count', "Sellers by Risk Tier"), use_container_width=True)
    with r1c2:
        st.plotly_chart(make_histogram(df_churn_filtered, 'churn_probability', "Churn Probability Distribution"), use_container_width=True)
        
    st.plotly_chart(make_scatter_plot(df_churn_filtered, 'total_revenue', 'churn_probability', 'risk_tier', "Churn Probability vs Total Revenue"), use_container_width=True)
    
    st.subheader("Churn Risk Data")
    st.dataframe(df_churn_filtered[['seller_id', 'churn_probability', 'churn_predicted', 'risk_tier']], use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df_churn_filtered.to_csv(index=False), "seller_churn_risk.csv", "text/csv")


render_reset_button()
render_last_updated(last_updated)
