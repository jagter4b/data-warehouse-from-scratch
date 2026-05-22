import streamlit as st
import pandas as pd
from components.db import get_delivery_risk, get_review_predictions, get_obt_orders
from components.charts import make_bar_chart, make_scatter_plot, make_histogram, make_donut_chart
from components.filters import render_sidebar_header, render_multiselect, render_slider, render_reset_button, render_last_updated

st.set_page_config(page_title="Order Intelligence", page_icon="📦", layout="wide")

import os
css_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'style.css')
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.title("📦 Order Intelligence")

with st.spinner("Loading Order Data..."):
    df_deliv = get_delivery_risk()
    df_rev = get_review_predictions()
    df_obt = get_obt_orders()

if df_deliv.empty or df_rev.empty or df_obt.empty:
    st.error("Failed to load one or more order datasets.")
    st.stop()

last_updated = df_deliv['scored_at'].iloc[0] if 'scored_at' in df_deliv.columns and not df_deliv.empty else "Unknown"

render_sidebar_header()

tab1, tab2 = st.tabs(["Delivery Risk", "Review Prediction"])

with tab1:
    st.header("Delivery Risk")
    
    st.sidebar.markdown("### Delivery Risk Filters")
    all_tiers = sorted(df_deliv['risk_tier'].unique().tolist())
    selected_tiers = render_multiselect("Select Risk Tiers", all_tiers)
    
    selected_prob = render_slider("Delay Probability Range", 0.0, 1.0)
    
    df_deliv_merged = pd.merge(df_deliv, df_obt[['order_id', 'total_order_value']], on='order_id', how='left')
    
    df_filtered = df_deliv_merged[
        (df_deliv_merged['risk_tier'].isin(selected_tiers)) &
        (df_deliv_merged['delay_probability'] >= selected_prob[0]) &
        (df_deliv_merged['delay_probability'] <= selected_prob[1])
    ]
    
    high = len(df_filtered[df_filtered['risk_tier'] == 'High'])
    late_rate = df_filtered['delay_predicted'].mean() * 100 if len(df_filtered) > 0 else 0
    avg_prob = df_filtered['delay_probability'].mean() if len(df_filtered) > 0 else 0
    total = len(df_filtered)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("High Risk Orders", f"{high:,}")
    c2.metric("Overall Predicted Late Rate", f"{late_rate:.1f}%")
    c3.metric("Avg Delay Probability", f"{avg_prob:.2f}")
    c4.metric("Total Orders Scored", f"{total:,}")
    
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        tier_counts = df_filtered['risk_tier'].value_counts().reset_index()
        tier_counts.columns = ['risk_tier', 'count']
        st.plotly_chart(make_bar_chart(tier_counts, 'risk_tier', 'count', "Orders by Risk Tier"), use_container_width=True)
    with r1c2:
        st.plotly_chart(make_histogram(df_filtered, 'delay_probability', "Delay Probability Distribution"), use_container_width=True)
        
    st.plotly_chart(make_scatter_plot(df_filtered, 'total_order_value', 'delay_probability', 'risk_tier', "Delay Probability vs Total Order Value"), use_container_width=True)
    
    st.subheader("Delivery Risk Data")
    st.dataframe(df_filtered[['order_id', 'delay_probability', 'delay_predicted', 'risk_tier']], use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df_filtered.to_csv(index=False), "delivery_risk.csv", "text/csv")


with tab2:
    st.header("Review Prediction")
    
    st.sidebar.markdown("### Review Prediction Filters")
    all_sat = sorted(df_rev['satisfaction_tier'].unique().tolist())
    selected_sat = render_multiselect("Select Satisfaction Tiers", all_sat)
    
    selected_score = render_slider("Predicted Score Range", 1.0, 5.0)
    
    df_rev_merged = pd.merge(df_rev, df_obt[['order_id', 'purchase_month']], on='order_id', how='left')
    
    df_rev_filtered = df_rev_merged[
        (df_rev_merged['satisfaction_tier'].isin(selected_sat)) &
        (df_rev_merged['predicted_review_score'] >= selected_score[0]) &
        (df_rev_merged['predicted_review_score'] <= selected_score[1])
    ]
    
    exc = len(df_rev_filtered[df_rev_filtered['satisfaction_tier'] == 'Excellent'])
    avg_score = df_rev_filtered['predicted_review_score'].mean() if len(df_rev_filtered) > 0 else 0
    poor = len(df_rev_filtered[df_rev_filtered['satisfaction_tier'].isin(['Poor', 'Very Poor'])])
    tot_rev = len(df_rev_filtered)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Excellent Orders Count", f"{exc:,}")
    c2.metric("Avg Predicted Review Score", f"{avg_score:.2f}")
    c3.metric("Poor + Very Poor Orders", f"{poor:,}")
    c4.metric("Total Orders Scored", f"{tot_rev:,}")
    
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        sat_counts = df_rev_filtered['satisfaction_tier'].value_counts().reset_index()
        sat_counts.columns = ['satisfaction_tier', 'count']
        st.plotly_chart(make_donut_chart(sat_counts, 'satisfaction_tier', 'count', "Orders by Satisfaction Tier"), use_container_width=True)
    with r1c2:
        st.plotly_chart(make_histogram(df_rev_filtered, 'predicted_review_score', "Predicted Review Score Distribution", nbins=5), use_container_width=True)
        
    avg_by_month = df_rev_filtered.groupby('purchase_month')['predicted_review_score'].mean().reset_index()
    # Map month numbers to names for better UI
    month_map = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
    avg_by_month['Month Name'] = avg_by_month['purchase_month'].map(month_map)
    st.plotly_chart(make_bar_chart(avg_by_month, 'Month Name', 'predicted_review_score', "Avg Predicted Score by Purchase Month"), use_container_width=True)
    
    st.subheader("Review Prediction Data")
    st.dataframe(df_rev_filtered[['order_id', 'predicted_review_score', 'satisfaction_tier']], use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df_rev_filtered.to_csv(index=False), "review_predictions.csv", "text/csv")


render_reset_button()
render_last_updated(last_updated)
