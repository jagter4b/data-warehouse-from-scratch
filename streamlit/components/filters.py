"""
components/filters.py
──────────────────────
Shared sidebar filter widget used across all pages.
Returns a filtered copy of the OBT dataframe.
"""

from __future__ import annotations
import pandas as pd
import streamlit as st


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renders sidebar filters and returns a filtered dataframe.
    Filters: Year, State (customer), Order Status, Product Category.
    """
    st.sidebar.markdown("## 🔍 Filters")

    # ── Year ──────────────────────────────────────────────────
    years = sorted(df["purchase_year"].dropna().unique().astype(int).tolist())
    selected_years = st.sidebar.multiselect(
        "Purchase Year",
        options=years,
        default=years,
        key="filter_year",
    )

    # ── Customer State ────────────────────────────────────────
    states = sorted(df["customer_state"].dropna().unique().tolist())
    selected_states = st.sidebar.multiselect(
        "Customer State",
        options=states,
        default=states,
        key="filter_state",
    )

    # ── Order Status ──────────────────────────────────────────
    statuses = sorted(df["order_status"].dropna().unique().tolist())
    selected_status = st.sidebar.multiselect(
        "Order Status",
        options=statuses,
        default=["delivered"],
        key="filter_status",
    )

    # ── Product Category ──────────────────────────────────────
    cats = sorted(df["product_category_name"].dropna().unique().tolist())
    selected_cats = st.sidebar.multiselect(
        "Product Category",
        options=cats,
        default=cats,
        key="filter_cat",
        placeholder="All categories",
    )

    # ── Apply ─────────────────────────────────────────────────
    mask = (
        df["purchase_year"].isin(selected_years)
        & df["customer_state"].isin(selected_states)
        & df["order_status"].isin(selected_status)
        & df["product_category_name"].isin(selected_cats)
    )

    filtered = df[mask].copy()

    st.sidebar.markdown("---")
    st.sidebar.metric("📦 Filtered Orders", f"{len(filtered):,}")
    st.sidebar.metric("👥 Unique Customers",
                      f"{filtered['customer_unique_id'].nunique():,}")

    if len(filtered) == 0:
        st.warning("⚠️ No data matches your filters. Adjust selections.")
        st.stop()

    return filtered
