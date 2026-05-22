import streamlit as st
import pandas as pd

st.set_page_config(page_title="Customer Intelligence", page_icon="👥", layout="wide")

from components.filters import load_css, sidebar_header, multiselect, range_slider, sidebar_divider, reset_btn, last_updated
from components.db import get_rfm, get_churn, get_clv
from components.charts import bar, funnel, scatter, hist, box, treemap, SEG_COLORS, RISK_COLORS, CLV_COLORS

load_css()

with st.spinner("Loading customer data…"):
    df_rfm   = get_rfm()
    df_churn = get_churn()
    df_clv   = get_clv()

if df_rfm.empty or df_churn.empty or df_clv.empty:
    st.error("Failed to load customer data."); st.stop()

ts = df_rfm["scored_at"].iloc[0] if "scored_at" in df_rfm.columns else "Unknown"

sidebar_header("Customer Intelligence")
st.title("Customer Intelligence")

tab1, tab2, tab3 = st.tabs(["🗂️  RFM Segments", "⚠️  Churn Prediction", "💰  Lifetime Value"])


# ════════════════════════════════════════════════════════════════════
#  TAB 1 — RFM SEGMENTATION
# ════════════════════════════════════════════════════════════════════
with tab1:
    sidebar_divider("RFM Filters")
    all_segs = sorted(df_rfm["segment_label"].dropna().unique())
    sel_segs = multiselect("Segments", all_segs)
    rfm_min  = int(df_rfm["rfm_total_score"].min())
    rfm_max  = int(df_rfm["rfm_total_score"].max())
    sel_rfm  = range_slider("RFM Total Score", rfm_min, rfm_max)

    filt = df_rfm[
        df_rfm["segment_label"].isin(sel_segs) &
        df_rfm["rfm_total_score"].between(sel_rfm[0], sel_rfm[1])
    ]
    n = len(filt)

    champs = (filt["segment_label"] == "Champions").sum()
    loyal  = (filt["segment_label"] == "Loyal Customers").sum()
    risk   = (filt["segment_label"] == "At Risk").sum()
    lost   = (filt["segment_label"] == "Lost/Inactive").sum()
    avg_rfm = filt["rfm_total_score"].mean() if n else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Customers",  f"{n:,}")
    c2.metric("🏆 Champions",     f"{champs:,}", f"{champs/n*100:.1f}%" if n else None)
    c3.metric("💙 Loyal",         f"{loyal:,}",  f"{loyal/n*100:.1f}%" if n else None)
    c4.metric("🟡 At Risk",       f"{risk:,}",   f"{risk/n*100:.1f}%" if n else None)
    c5.metric("⚫ Lost/Inactive", f"{lost:,}",   f"{lost/n*100:.1f}%" if n else None)

    st.markdown("")

    # Row 1: Treemap  |  R/F/M grouped bar
    r1a, r1b = st.columns(2)
    with r1a:
        seg_c = filt["segment_label"].value_counts().reset_index()
        seg_c.columns = ["segment_label", "count"]
        st.plotly_chart(treemap(seg_c, "segment_label", "count",
                                "Segment Distribution", cmap=SEG_COLORS),
                        use_container_width=True)
    with r1b:
        avg_rfm_df = (
            filt.groupby("segment_label")[
                ["rfm_recency_score","rfm_frequency_score","rfm_monetary_score"]
            ].mean().reset_index()
            .melt(id_vars="segment_label", var_name="Metric", value_name="Avg Score")
        )
        avg_rfm_df["Metric"] = avg_rfm_df["Metric"].map({
            "rfm_recency_score":   "Recency",
            "rfm_frequency_score": "Frequency",
            "rfm_monetary_score":  "Monetary",
        })
        rfm_colors = {"Recency":"#06B6D4","Frequency":"#A78BFA","Monetary":"#10B981"}
        st.plotly_chart(
            bar(avg_rfm_df, "segment_label", "Avg Score",
                "Avg R / F / M Score by Segment",
                color_col="Metric", cmap=rfm_colors),
            use_container_width=True)

    # Row 2: Recency vs Monetary scatter  |  State breakdown
    r2a, r2b = st.columns([3,2])
    with r2a:
        st.plotly_chart(
            scatter(filt, "rfm_recency_score", "rfm_monetary_score",
                    "segment_label", "Recency vs Monetary (5k sample)",
                    cmap=SEG_COLORS, n=5000),
            use_container_width=True)
    with r2b:
        if "customer_state" in filt.columns:
            state_grp = (filt.groupby(["customer_state","segment_label"])
                         .size().reset_index(name="count"))
            top8 = state_grp.groupby("customer_state")["count"].sum().nlargest(8).index
            state_grp = state_grp[state_grp["customer_state"].isin(top8)]
            fig = bar(state_grp, "customer_state", "count",
                      "Top 8 States by Segment",
                      color_col="segment_label", cmap=SEG_COLORS, barmode="stack")
            fig.update_layout(height=360)
            st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.subheader("Segment Data")
    show = [c for c in ["customer_unique_id","segment_label","rfm_recency_score",
                         "rfm_frequency_score","rfm_monetary_score","rfm_total_score",
                         "total_spend","days_since_last_order","customer_state"]
            if c in filt.columns]
    st.dataframe(filt[show], use_container_width=True, hide_index=True)
    st.download_button("📥 Export CSV", filt.to_csv(index=False),
                       "customer_segments.csv", "text/csv")


# ════════════════════════════════════════════════════════════════════
#  TAB 2 — CHURN PREDICTION
# ════════════════════════════════════════════════════════════════════
with tab2:
    st.info(
        "**Dataset context**: Churn = no purchase in the last 120 days (anchored to the 2018 "
        "dataset max date). Because Olist customers are overwhelmingly one-time buyers, an "
        "overall predicted churn rate of ~80% is **accurate and expected** — not a model "
        "defect. The model's value lies in *ranking* customers by churn probability.",
        icon="ℹ️",
    )

    sidebar_divider("Churn Filters")
    all_tiers = sorted(df_churn["risk_tier"].dropna().unique())
    sel_tiers = multiselect("Risk Tiers", all_tiers)
    sel_prob  = range_slider("Churn Probability", 0.0, 1.0, step=0.01)

    fc = df_churn[
        df_churn["risk_tier"].isin(sel_tiers) &
        df_churn["churn_probability"].between(sel_prob[0], sel_prob[1])
    ]
    nc = len(fc)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 High Risk",   f"{(fc['risk_tier']=='High').sum():,}")
    c2.metric("🟡 Medium Risk", f"{(fc['risk_tier']=='Medium').sum():,}")
    c3.metric("🟢 Low Risk",    f"{(fc['risk_tier']=='Low').sum():,}")
    c4.metric("Predicted Churn Rate",
              f"{fc['churn_predicted'].mean()*100:.1f}%" if nc else "—")

    st.markdown("")

    r1a, r1b = st.columns(2)
    with r1a:
        tc = fc["risk_tier"].value_counts().reset_index()
        tc.columns = ["risk_tier","count"]
        st.plotly_chart(funnel(tc,"risk_tier","count",
                               "Customers by Risk Tier", cmap=RISK_COLORS),
                        use_container_width=True)
    with r1b:
        st.plotly_chart(hist(fc,"churn_probability",
                             "Churn Probability Distribution",bins=50),
                        use_container_width=True)

    r2a, r2b = st.columns(2)
    with r2a:
        st.plotly_chart(box(fc,"risk_tier","churn_probability",
                            "Probability by Risk Tier", cmap=RISK_COLORS),
                        use_container_width=True)
    with r2b:
        if "total_spend" in fc.columns:
            st.plotly_chart(
                scatter(fc,"total_spend","churn_probability","risk_tier",
                        "Total Spend vs Churn Probability (5k sample)",
                        cmap=RISK_COLORS, n=5000),
                use_container_width=True)

    st.subheader("Churn Data")
    show = [c for c in ["customer_unique_id","churn_probability","churn_predicted",
                         "risk_tier","total_spend","total_orders","customer_state"]
            if c in fc.columns]
    st.dataframe(fc[show], use_container_width=True, hide_index=True)
    st.download_button("📥 Export CSV", fc.to_csv(index=False),
                       "churn_predictions.csv","text/csv")


# ════════════════════════════════════════════════════════════════════
#  TAB 3 — CUSTOMER LIFETIME VALUE
# ════════════════════════════════════════════════════════════════════
with tab3:
    sidebar_divider("CLV Filters")
    all_clv = sorted(df_clv["clv_tier"].dropna().unique())
    sel_clv = multiselect("CLV Tiers", all_clv)

    fv = df_clv[df_clv["clv_tier"].isin(sel_clv)]
    nv = len(fv)

    plat    = (fv["clv_tier"]=="Platinum").sum()
    avg_clv = fv["predicted_clv"].mean() if nv else 0
    max_clv = fv["predicted_clv"].max()  if nv else 0
    tot_clv = fv["predicted_clv"].sum()  if nv else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💎 Platinum",       f"{plat:,}")
    c2.metric("Avg Predicted CLV", f"R$ {avg_clv:,.0f}")
    c3.metric("Highest CLV",       f"R$ {max_clv:,.0f}")
    c4.metric("Total Portfolio",   f"R$ {tot_clv:,.0f}")

    st.markdown("")

    r1a, r1b = st.columns(2)
    with r1a:
        clv_c = fv["clv_tier"].value_counts().reset_index()
        clv_c.columns = ["clv_tier","count"]
        st.plotly_chart(funnel(clv_c,"clv_tier","count",
                               "Customers by CLV Tier", cmap=CLV_COLORS),
                        use_container_width=True)
    with r1b:
        st.plotly_chart(box(fv,"clv_tier","predicted_clv",
                            "CLV Distribution per Tier", cmap=CLV_COLORS),
                        use_container_width=True)

    r2a, r2b = st.columns(2)
    with r2a:
        if "total_orders" in fv.columns:
            st.plotly_chart(
                scatter(fv,"total_orders","predicted_clv","clv_tier",
                        "Orders vs Predicted CLV (5k sample)",
                        cmap=CLV_COLORS, n=5000),
                use_container_width=True)
    with r2b:
        avg_t = fv.groupby("clv_tier")["predicted_clv"].mean().reset_index()
        st.plotly_chart(
            bar(avg_t,"clv_tier","predicted_clv",
                "Avg Predicted CLV by Tier", cmap=CLV_COLORS),
            use_container_width=True)

    st.subheader("CLV Data")
    show = [c for c in ["customer_unique_id","predicted_clv","clv_tier",
                         "total_spend","total_orders","customer_tenure_days"]
            if c in fv.columns]
    st.dataframe(fv[show], use_container_width=True, hide_index=True)
    st.download_button("📥 Export CSV", fv.to_csv(index=False),
                       "clv_predictions.csv","text/csv")


reset_btn()
last_updated(ts)
