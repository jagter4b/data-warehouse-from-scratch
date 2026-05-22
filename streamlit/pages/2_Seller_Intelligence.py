import streamlit as st
import pandas as pd

st.set_page_config(page_title="Seller Intelligence", page_icon="🏪", layout="wide")

from components.filters import load_css, sidebar_header, multiselect, range_slider, sidebar_divider, reset_btn, last_updated
from components.db import get_seller_scores, get_seller_churn
from components.charts import bar, funnel, scatter, hist, box, PERF_COLORS, RISK_COLORS

load_css()

with st.spinner("Loading seller data…"):
    df_sc = get_seller_scores()
    df_ch = get_seller_churn()

if df_sc.empty or df_ch.empty:
    st.error("Failed to load seller data."); st.stop()

ts = df_sc["scored_at"].iloc[0] if "scored_at" in df_sc.columns else "Unknown"

sidebar_header("Seller Intelligence")
st.title("Seller Intelligence")

tab1, tab2 = st.tabs(["📊  Performance Scoring", "⚠️  Churn Risk"])


# ════════════════════════════════════════════════════════════════════
#  TAB 1 — SELLER PERFORMANCE SCORING
# ════════════════════════════════════════════════════════════════════
with tab1:
    sidebar_divider("Performance Filters")
    all_labels = sorted(df_sc["cluster_label"].dropna().unique())
    sel_labels = multiselect("Performance Tier", all_labels)

    cs_lo = float(df_sc["composite_score"].min())
    cs_hi = float(df_sc["composite_score"].max())
    sel_cs = range_slider("Composite Score", round(cs_lo,1), round(cs_hi,1), step=0.1)

    mql_opt = st.sidebar.radio("MQL Acquisition", ["All","MQL Only","Non-MQL Only"])

    fs = df_sc[
        df_sc["cluster_label"].isin(sel_labels) &
        df_sc["composite_score"].between(sel_cs[0], sel_cs[1])
    ].copy()

    if "was_acquired_via_mql" in fs.columns:
        if mql_opt == "MQL Only":
            fs = fs[fs["was_acquired_via_mql"] == 1]
        elif mql_opt == "Non-MQL Only":
            fs = fs[fs["was_acquired_via_mql"] == 0]

    top   = (fs["cluster_label"]=="Top Performer").sum()
    avg_  = (fs["cluster_label"]=="Average Seller").sum()
    under = (fs["cluster_label"]=="Underperformer").sum()
    ns    = len(fs)

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Total Sellers",     f"{ns:,}")
    c2.metric("🏆 Top Performer",  f"{top:,}",   f"{top/ns*100:.1f}%" if ns else None)
    c3.metric("🔵 Average",        f"{avg_:,}",  f"{avg_/ns*100:.1f}%" if ns else None)
    c4.metric("🔴 Underperformer", f"{under:,}", f"{under/ns*100:.1f}%" if ns else None)
    c5.metric("Avg Composite Score", f"{fs['composite_score'].mean():.1f}" if ns else "—")
    c6.metric("Avg Late Delivery",
              f"{fs['pct_late_deliveries'].mean():.1f}%" if "pct_late_deliveries" in fs.columns and ns else "—")

    st.markdown("")

    if top < 30:
        st.info(
            f"Only **{top}** out of {ns:,} sellers are Top Performers "
            f"({top/ns*100:.1f}%). Composite score = 40% review quality + "
            "30% on-time delivery + 20% log-revenue + 10% 5★ rate.",
            icon="ℹ️",
        )

    # Row 1: Funnel | Scatter
    r1a, r1b = st.columns([1,2])
    with r1a:
        tc = fs["cluster_label"].value_counts().reset_index()
        tc.columns = ["cluster_label","count"]
        st.plotly_chart(funnel(tc,"cluster_label","count",
                               "Sellers by Tier", cmap=PERF_COLORS),
                        use_container_width=True)
    with r1b:
        sz = "total_revenue" if "total_revenue" in fs.columns else None
        st.plotly_chart(
            scatter(fs,"avg_review_score","composite_score","cluster_label",
                    "Review Score vs Composite Score  (bubble = Revenue)",
                    cmap=PERF_COLORS, size_col=sz),
            use_container_width=True)

    # Row 2: MQL bar | Top-15 horizontal
    r2a, r2b = st.columns(2)
    with r2a:
        if "was_acquired_via_mql" in df_sc.columns:
            mql_c = (df_sc.groupby("was_acquired_via_mql")["composite_score"]
                     .mean().reset_index())
            mql_c["Acquisition"] = mql_c["was_acquired_via_mql"].map({1:"MQL",0:"Non-MQL"})
            mql_colors = {"MQL":"#A78BFA","Non-MQL":"#06B6D4"}
            st.plotly_chart(
                bar(mql_c,"Acquisition","composite_score",
                    "Avg Composite Score: MQL vs Non-MQL",
                    cmap=mql_colors),
                use_container_width=True)
    with r2b:
        top15 = fs.nlargest(15,"composite_score").copy()
        top15["Seller"] = top15["seller_id"].str[:12] + "…"
        fig = bar(top15,"composite_score","Seller",
                  "Top 15 Sellers by Score",
                  color_col="cluster_label", cmap=PERF_COLORS, h=True)
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

    # Row 3: score histogram
    st.plotly_chart(hist(fs,"composite_score",
                         "Composite Score Distribution", bins=40),
                    use_container_width=True)

    st.subheader("Performance Data")
    show = [c for c in ["seller_id","cluster_label","composite_score",
                         "avg_review_score","pct_late_deliveries","total_revenue",
                         "was_acquired_via_mql","seller_state"]
            if c in fs.columns]
    st.dataframe(fs[show], use_container_width=True, hide_index=True)
    st.download_button("📥 Export CSV", fs.to_csv(index=False),
                       "seller_performance.csv","text/csv")


# ════════════════════════════════════════════════════════════════════
#  TAB 2 — SELLER CHURN RISK
# ════════════════════════════════════════════════════════════════════
with tab2:
    sidebar_divider("Churn Risk Filters")
    all_risk = sorted(df_ch["risk_tier"].dropna().unique())
    sel_risk = multiselect("Risk Tiers", all_risk)
    sel_prob = range_slider("Churn Probability", 0.0, 1.0, step=0.01)

    fc = df_ch[
        df_ch["risk_tier"].isin(sel_risk) &
        df_ch["churn_probability"].between(sel_prob[0], sel_prob[1])
    ]
    nc = len(fc)

    high_mql = 0
    if "was_acquired_via_mql" in fc.columns:
        high_mql = fc[(fc["risk_tier"]=="High") & (fc["was_acquired_via_mql"]==1)].shape[0]

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🔴 High Risk Sellers",   f"{(fc['risk_tier']=='High').sum():,}")
    c2.metric("Predicted Churn Rate",   f"{fc['churn_predicted'].mean()*100:.1f}%" if nc else "—")
    c3.metric("Avg Churn Probability",  f"{fc['churn_probability'].mean():.2f}" if nc else "—")
    c4.metric("MQL Sellers at High Risk", f"{high_mql:,}")

    st.markdown("")

    r1a, r1b = st.columns(2)
    with r1a:
        rc = fc["risk_tier"].value_counts().reset_index()
        rc.columns = ["risk_tier","count"]
        st.plotly_chart(funnel(rc,"risk_tier","count",
                               "Sellers by Churn Risk Tier", cmap=RISK_COLORS),
                        use_container_width=True)
    with r1b:
        st.plotly_chart(hist(fc,"churn_probability",
                             "Churn Probability Distribution", bins=40),
                        use_container_width=True)

    r2a, r2b = st.columns(2)
    with r2a:
        st.plotly_chart(box(fc,"risk_tier","churn_probability",
                            "Probability by Risk Tier", cmap=RISK_COLORS),
                        use_container_width=True)
    with r2b:
        if "total_revenue" in fc.columns:
            st.plotly_chart(
                scatter(fc,"total_revenue","churn_probability","risk_tier",
                        "Revenue vs Churn Probability",
                        cmap=RISK_COLORS, n=3000),
                use_container_width=True)

    st.subheader("Churn Risk Data")
    show = [c for c in ["seller_id","churn_probability","churn_predicted","risk_tier",
                         "total_revenue","was_acquired_via_mql"]
            if c in fc.columns]
    st.dataframe(fc[show], use_container_width=True, hide_index=True)
    st.download_button("📥 Export CSV", fc.to_csv(index=False),
                       "seller_churn.csv","text/csv")


reset_btn()
last_updated(ts)
