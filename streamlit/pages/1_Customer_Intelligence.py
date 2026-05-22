import streamlit as st
import pandas as pd
from components.db import get_customer_segments, get_churn_predictions, get_clv_predictions, get_obt_customers
from components.charts import make_donut_chart, make_bar_chart, make_scatter_plot, make_histogram, make_box_plot
from components.filters import render_sidebar_header, render_multiselect, render_slider, render_reset_button, render_last_updated

st.set_page_config(page_title="Customer Intelligence", page_icon="👥", layout="wide")

# Load CSS
import os
css_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'style.css')
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.title("👥 Customer Intelligence")

# Load data
with st.spinner("Loading Customer Data..."):
    df_seg = get_customer_segments()
    df_churn = get_churn_predictions()
    df_clv = get_clv_predictions()
    df_obt = get_obt_customers()

if df_seg.empty or df_churn.empty or df_clv.empty or df_obt.empty:
    st.error("Failed to load one or more customer datasets.")
    st.stop()

# Get timestamp for sidebar
last_updated = df_seg['scored_at'].iloc[0] if 'scored_at' in df_seg.columns and not df_seg.empty else "Unknown"

render_sidebar_header()

tab1, tab2, tab3 = st.tabs(["RFM Segmentation", "Churn Prediction", "Customer LTV"])

with tab1:
    st.header("RFM Segmentation")
    
    # Sidebar Filters
    st.sidebar.markdown("### Segmentation Filters")
    all_segments = sorted(df_seg['segment_label'].unique().tolist())
    selected_segments = render_multiselect("Select Segments", all_segments)
    
    min_rfm, max_rfm = int(df_seg['rfm_total_score'].min()), int(df_seg['rfm_total_score'].max())
    selected_rfm_range = render_slider("RFM Total Score", min_rfm, max_rfm)
    
    # Filter Data
    df_seg_filtered = df_seg[
        (df_seg['segment_label'].isin(selected_segments)) &
        (df_seg['rfm_total_score'] >= selected_rfm_range[0]) &
        (df_seg['rfm_total_score'] <= selected_rfm_range[1])
    ]
    
    # KPIs
    champions = len(df_seg_filtered[df_seg_filtered['segment_label'] == 'Champions'])
    at_risk = len(df_seg_filtered[df_seg_filtered['segment_label'] == 'At Risk'])
    lost = len(df_seg_filtered[df_seg_filtered['segment_label'].str.contains('Lost')])
    avg_rfm = df_seg_filtered['rfm_total_score'].mean() if len(df_seg_filtered) > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Champions Count", f"{champions:,}")
    c2.metric("At Risk Count", f"{at_risk:,}")
    c3.metric("Lost Count", f"{lost:,}")
    c4.metric("Avg RFM Score", f"{avg_rfm:.1f}")
    
    # Charts
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        seg_counts = df_seg_filtered['segment_label'].value_counts().reset_index()
        seg_counts.columns = ['segment_label', 'count']
        st.plotly_chart(make_donut_chart(seg_counts, 'segment_label', 'count', "Segment Distribution"), use_container_width=True)
    with r1c2:
        avg_scores = df_seg_filtered.groupby('segment_label')[['rfm_recency_score', 'rfm_frequency_score', 'rfm_monetary_score']].mean().reset_index()
        avg_scores_melted = pd.melt(avg_scores, id_vars=['segment_label'], var_name='Score_Type', value_name='Average Score')
        st.plotly_chart(make_bar_chart(avg_scores_melted, 'segment_label', 'Average Score', "Avg R, F, M Scores by Segment"), use_container_width=True)
        
    st.plotly_chart(make_scatter_plot(df_seg_filtered, 'rfm_recency_score', 'rfm_monetary_score', 'segment_label', "Recency vs Monetary Score"), use_container_width=True)
    
    # Data Table
    st.subheader("Segment Data")
    st.dataframe(df_seg_filtered[['customer_unique_id', 'segment_label', 'rfm_recency_score', 'rfm_frequency_score', 'rfm_monetary_score', 'rfm_total_score']], use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df_seg_filtered.to_csv(index=False), "customer_segments.csv", "text/csv")


with tab2:
    st.header("Churn Prediction")
    
    st.sidebar.markdown("### Churn Filters")
    all_tiers = sorted(df_churn['risk_tier'].unique().tolist())
    selected_tiers = render_multiselect("Select Risk Tiers", all_tiers)
    
    selected_prob = render_slider("Churn Probability Range", 0.0, 1.0)
    
    df_churn_filtered = df_churn[
        (df_churn['risk_tier'].isin(selected_tiers)) &
        (df_churn['churn_probability'] >= selected_prob[0]) &
        (df_churn['churn_probability'] <= selected_prob[1])
    ]
    
    high = len(df_churn_filtered[df_churn_filtered['risk_tier'] == 'High'])
    medium = len(df_churn_filtered[df_churn_filtered['risk_tier'] == 'Medium'])
    low = len(df_churn_filtered[df_churn_filtered['risk_tier'] == 'Low'])
    rate = df_churn_filtered['churn_predicted'].mean() * 100 if len(df_churn_filtered) > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("High Risk Count", f"{high:,}")
    c2.metric("Medium Risk Count", f"{medium:,}")
    c3.metric("Low Risk Count", f"{low:,}")
    c4.metric("Predicted Churn Rate", f"{rate:.1f}%")
    
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        tier_counts = df_churn_filtered['risk_tier'].value_counts().reset_index()
        tier_counts.columns = ['risk_tier', 'count']
        st.plotly_chart(make_bar_chart(tier_counts, 'risk_tier', 'count', "Customers by Risk Tier"), use_container_width=True)
    with r1c2:
        st.plotly_chart(make_histogram(df_churn_filtered, 'churn_probability', "Churn Probability Distribution"), use_container_width=True)
    
    # Merge with OBT for scatter
    churn_obt = pd.merge(df_churn_filtered, df_obt[['customer_unique_id', 'total_spend']], on='customer_unique_id', how='left')
    st.plotly_chart(make_scatter_plot(churn_obt, 'total_spend', 'churn_probability', 'risk_tier', "Churn Probability vs Total Spend"), use_container_width=True)
    
    st.subheader("Churn Data")
    st.dataframe(df_churn_filtered[['customer_unique_id', 'churn_probability', 'churn_predicted', 'risk_tier']], use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df_churn_filtered.to_csv(index=False), "churn_predictions.csv", "text/csv")


with tab3:
    st.header("Customer Lifetime Value (CLV)")
    
    st.sidebar.markdown("### CLV Filters")
    all_clv_tiers = sorted(df_clv['clv_tier'].unique().tolist())
    selected_clv_tiers = render_multiselect("Select CLV Tiers", all_clv_tiers)
    
    df_clv_filtered = df_clv[df_clv['clv_tier'].isin(selected_clv_tiers)]
    
    plat = len(df_clv_filtered[df_clv_filtered['clv_tier'] == 'Platinum'])
    avg_clv = df_clv_filtered['predicted_clv'].mean() if len(df_clv_filtered) > 0 else 0
    max_clv = df_clv_filtered['predicted_clv'].max() if len(df_clv_filtered) > 0 else 0
    tot_clv = df_clv_filtered['predicted_clv'].sum() if len(df_clv_filtered) > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Platinum Count", f"{plat:,}")
    c2.metric("Avg Predicted CLV", f"R$ {avg_clv:,.2f}")
    c3.metric("Highest Predicted CLV", f"R$ {max_clv:,.2f}")
    c4.metric("Total Predicted CLV", f"R$ {tot_clv:,.2f}")
    
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        clv_counts = df_clv_filtered['clv_tier'].value_counts().reset_index()
        clv_counts.columns = ['clv_tier', 'count']
        st.plotly_chart(make_donut_chart(clv_counts, 'clv_tier', 'count', "Customers by CLV Tier"), use_container_width=True)
    with r1c2:
        avg_clv_tier = df_clv_filtered.groupby('clv_tier')['predicted_clv'].mean().reset_index()
        st.plotly_chart(make_bar_chart(avg_clv_tier, 'clv_tier', 'predicted_clv', "Avg Predicted CLV by Tier"), use_container_width=True)
    
    st.plotly_chart(make_box_plot(df_clv_filtered, 'clv_tier', 'predicted_clv', "CLV Distribution per Tier"), use_container_width=True)
    
    st.subheader("CLV Data")
    st.dataframe(df_clv_filtered[['customer_unique_id', 'predicted_clv', 'clv_tier']], use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df_clv_filtered.to_csv(index=False), "clv_predictions.csv", "text/csv")


render_reset_button()
render_last_updated(last_updated)
