import streamlit as st
import pandas as pd

st.set_page_config(page_title="Order Intelligence", page_icon="📦", layout="wide")

from components.filters import load_css, sidebar_header, multiselect, range_slider, sidebar_divider, reset_btn, last_updated
from components.db import get_delivery, get_reviews
from components.charts import bar, funnel, donut, scatter, hist, line, RISK_COLORS, SAT_COLORS

load_css()

with st.spinner("Loading order data…"):
    df_del = get_delivery()
    df_rev = get_reviews()

if df_del.empty or df_rev.empty:
    st.error("Failed to load order data."); st.stop()

ts = df_del["scored_at"].iloc[0] if "scored_at" in df_del.columns else "Unknown"

MONTH_MAP = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
             7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
DOW_MAP   = {0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri",5:"Sat",6:"Sun"}

sidebar_header("Order Intelligence")
st.title("Order Intelligence")

tab1, tab2 = st.tabs(["🚚  Delivery Risk", "⭐  Review Prediction"])


# ════════════════════════════════════════════════════════════════════
#  TAB 1 — DELIVERY RISK
# ════════════════════════════════════════════════════════════════════
with tab1:
    sidebar_divider("Delivery Risk Filters")
    all_risk = sorted(df_del["risk_tier"].dropna().unique())
    sel_risk = multiselect("Risk Tiers", all_risk)
    sel_prob = range_slider("Delay Probability", 0.0, 1.0, step=0.01)

    fd = df_del[
        df_del["risk_tier"].isin(sel_risk) &
        df_del["delay_probability"].between(sel_prob[0], sel_prob[1])
    ]
    nd = len(fd)

    high = (fd["risk_tier"]=="High").sum()
    med  = (fd["risk_tier"]=="Medium").sum()
    low  = (fd["risk_tier"]=="Low").sum()
    d_rate = fd["delay_predicted"].mean()*100 if nd else 0

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Orders",       f"{nd:,}")
    c2.metric("🔴 High Risk",       f"{high:,}", f"{high/nd*100:.2f}%" if nd else None)
    c3.metric("🟡 Medium Risk",     f"{med:,}",  f"{med/nd*100:.1f}%" if nd else None)
    c4.metric("🟢 Low Risk",        f"{low:,}",  f"{low/nd*100:.1f}%" if nd else None)
    c5.metric("Predicted Late Rate", f"{d_rate:.1f}%")

    st.markdown("")

    if nd:
        st.info(
            f"**{high:,}** orders ({high/nd*100:.2f}%) are flagged High Risk. "
            "Key drivers: seller late-delivery history, product weight, "
            "days to approve, and purchase timing.",
            icon="ℹ️",
        )

    # Row 1: Funnel | Histogram
    r1a, r1b = st.columns(2)
    with r1a:
        tc = fd["risk_tier"].value_counts().reset_index()
        tc.columns = ["risk_tier","count"]
        st.plotly_chart(funnel(tc,"risk_tier","count",
                               "Orders by Delivery Risk Tier", cmap=RISK_COLORS),
                        use_container_width=True)
    with r1b:
        st.plotly_chart(hist(fd,"delay_probability",
                             "Delay Probability Distribution", bins=50),
                        use_container_width=True)

    # Row 2: Category risk bar | Monthly trend
    r2a, r2b = st.columns(2)
    with r2a:
        if "primary_category" in fd.columns:
            cat_r = (fd.groupby("primary_category")["delay_probability"]
                     .mean().nlargest(12).reset_index())
            cat_r.columns = ["Category","Avg Delay Prob"]
            fig = bar(cat_r,"Avg Delay Prob","Category",
                      "Top 12 Categories — Avg Delay Probability", h=True)
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)
    with r2b:
        if "purchase_month" in fd.columns:
            monthly = (fd.groupby("purchase_month")["delay_probability"]
                       .mean().reset_index().sort_values("purchase_month"))
            monthly["Month"] = monthly["purchase_month"].map(MONTH_MAP)
            st.plotly_chart(
                line(monthly,"Month","delay_probability",
                     "Avg Delay Probability by Purchase Month"),
                use_container_width=True)

    # Row 3: Order value vs delay probability scatter
    if "total_order_value" in fd.columns:
        st.plotly_chart(
            scatter(fd,"total_order_value","delay_probability","risk_tier",
                    "Order Value vs Delay Probability (5k sample)",
                    cmap=RISK_COLORS, n=5000),
            use_container_width=True)

    st.subheader("Delivery Risk Data")
    show = [c for c in ["order_id","delay_probability","delay_predicted","risk_tier",
                         "total_order_value","primary_category","purchase_month"]
            if c in fd.columns]
    st.dataframe(fd[show], use_container_width=True, hide_index=True)
    st.download_button("📥 Export CSV", fd.to_csv(index=False),
                       "delivery_risk.csv","text/csv")


# ════════════════════════════════════════════════════════════════════
#  TAB 2 — REVIEW PREDICTION
# ════════════════════════════════════════════════════════════════════
with tab2:
    sidebar_divider("Review Prediction Filters")
    all_sat = sorted(df_rev["satisfaction_tier"].dropna().unique())
    sel_sat = multiselect("Satisfaction Tiers", all_sat)
    sel_sc  = range_slider("Predicted Score", 1.0, 5.0, step=0.5)

    fr = df_rev[
        df_rev["satisfaction_tier"].isin(sel_sat) &
        df_rev["predicted_review_score"].between(sel_sc[0], sel_sc[1])
    ]
    nr = len(fr)

    exc  = (fr["satisfaction_tier"]=="Excellent").sum()
    good = (fr["satisfaction_tier"]=="Good").sum()
    poor = (fr["satisfaction_tier"].isin(["Poor","Very Poor"])).sum()
    avg_s = fr["predicted_review_score"].mean() if nr else 0

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Orders Scored", f"{nr:,}")
    c2.metric("🟢 Excellent",        f"{exc:,}", f"{exc/nr*100:.1f}%" if nr else None)
    c3.metric("🔵 Good",             f"{good:,}")
    c4.metric("🔴 Poor + Very Poor", f"{poor:,}")

    st.markdown("")

    # Row 1: Donut | Monthly trend
    r1a, r1b = st.columns(2)
    with r1a:
        sc = fr["satisfaction_tier"].value_counts().reset_index()
        sc.columns = ["satisfaction_tier","count"]
        st.plotly_chart(donut(sc,"satisfaction_tier","count",
                              "Orders by Satisfaction Tier", cmap=SAT_COLORS),
                        use_container_width=True)
    with r1b:
        if "purchase_month" in fr.columns:
            mo = (fr.groupby("purchase_month")["predicted_review_score"]
                  .mean().reset_index().sort_values("purchase_month"))
            mo["Month"] = mo["purchase_month"].map(MONTH_MAP)
            st.plotly_chart(
                line(mo,"Month","predicted_review_score",
                     "Avg Predicted Score by Purchase Month"),
                use_container_width=True)

    # Row 2: Days-to-deliver vs review score (key business insight) | Day of week
    r2a, r2b = st.columns(2)
    with r2a:
        if "days_to_deliver" in fr.columns:
            st.plotly_chart(
                scatter(fr,"days_to_deliver","predicted_review_score",
                        "satisfaction_tier",
                        "Delivery Days vs Review Score (5k sample) — later = worse",
                        cmap=SAT_COLORS, n=5000),
                use_container_width=True)
    with r2b:
        if "purchase_day_of_week" in fr.columns:
            dow = (fr.groupby("purchase_day_of_week")["predicted_review_score"]
                   .mean().reset_index().sort_values("purchase_day_of_week"))
            dow["Day"] = dow["purchase_day_of_week"].map(DOW_MAP)
            st.plotly_chart(
                bar(dow,"Day","predicted_review_score",
                    "Avg Predicted Score by Day of Week"),
                use_container_width=True)

    # Row 3: satisfaction tier bar
    if "c_scheduled_vs_actual_days" in fr.columns:
        tier_var = (
            fr.groupby("satisfaction_tier")["c_scheduled_vs_actual_days"]
            .mean().reset_index()
        )
        tier_var.columns = ["satisfaction_tier","Avg Schedule Variance (days)"]
        st.plotly_chart(
            bar(tier_var,"satisfaction_tier","Avg Schedule Variance (days)",
                "Avg Delivery Schedule Variance by Satisfaction Tier",
                cmap=SAT_COLORS),
            use_container_width=True)

    st.subheader("Review Prediction Data")
    show = [c for c in ["order_id","predicted_review_score","satisfaction_tier",
                         "days_to_deliver","is_late","total_order_value","purchase_month"]
            if c in fr.columns]
    st.dataframe(fr[show], use_container_width=True, hide_index=True)
    st.download_button("📥 Export CSV", fr.to_csv(index=False),
                       "review_predictions.csv","text/csv")


reset_btn()
last_updated(ts)
