"""
visualization.py — Auto Chart Selection & Plotly Rendering
────────────────────────────────────────────────────────────
Detects the best chart type for a DataFrame and renders it
using Plotly with a dark, branded theme consistent with the app.
"""

import logging
from typing import Optional, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)

# ── Brand palette ────────────────────────────────────────────────────────────
PALETTE = ["#7c3aed", "#0ea5e9", "#10b981", "#f59e0b", "#f43f5e", "#8b5cf6", "#14b8a6"]
DARK_BG = "rgba(0,0,0,0)"
GRID_COLOR = "rgba(255,255,255,0.06)"
FONT = dict(family="Inter", color="#94a3b8", size=12)

_LAYOUT_DEFAULTS = dict(
    template="plotly_dark",
    paper_bgcolor=DARK_BG,
    plot_bgcolor=DARK_BG,
    margin=dict(l=20, r=20, t=40, b=20),
    font=FONT,
    colorway=PALETTE,
    legend=dict(orientation="h", y=-0.15),
)


# ── Auto-detect chart type ───────────────────────────────────────────────────

def detect_chart_type(df: pd.DataFrame, hint: Optional[str] = None) -> str:
    """
    Automatically determine the most suitable chart type.

    Priority order:
    1. Use hint from AI if valid
    2. KPI card — single numeric cell
    3. Pie — two columns, second is numeric, ≤ 8 categories
    4. Line — time-like first column + numeric
    5. Bar — categorical + numeric
    6. Table — fallback
    """
    valid_hints = {"bar", "line", "pie", "scatter", "table", "kpi"}
    if hint and hint.lower() in valid_hints:
        return hint.lower()

    if df is None or df.empty:
        return "table"

    rows, cols = df.shape

    # KPI: single value
    if rows == 1 and cols == 1:
        return "kpi"

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    non_numeric = [c for c in df.columns if c not in numeric_cols]

    if not numeric_cols:
        return "table"

    # Pie: exactly 2 cols, ≤8 unique categories
    if cols == 2 and non_numeric and rows <= 8:
        return "pie"

    # Line: first column looks like a date/year
    if non_numeric:
        first_col = non_numeric[0].lower()
        if any(k in first_col for k in ("date", "year", "month", "week", "period", "time", "quarter")):
            return "line"

    # Bar: categorical + numeric
    if non_numeric and numeric_cols:
        return "bar"

    return "table"


# ── Renderers ────────────────────────────────────────────────────────────────

def render_kpi_cards(df: pd.DataFrame) -> None:
    """Render a row of metric cards for small numeric result sets."""
    cols = st.columns(min(len(df.columns), 6))
    for i, col_name in enumerate(df.columns):
        val = df[col_name].iloc[0]
        if isinstance(val, float):
            display = f"{val:,.2f}"
        elif isinstance(val, int):
            display = f"{val:,}"
        else:
            display = str(val)
        with cols[i % len(cols)]:
            st.metric(label=col_name, value=display)


def render_bar(df: pd.DataFrame, title: str = "") -> go.Figure:
    non_numeric = df.select_dtypes(exclude="number").columns.tolist()
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    x_col = non_numeric[0] if non_numeric else df.columns[0]
    y_col = numeric_cols[0] if numeric_cols else df.columns[1]

    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        color=y_col,
        color_continuous_scale=["#1e1b4b", "#7c3aed", "#0ea5e9"],
        title=title,
    )
    fig.update_layout(**_LAYOUT_DEFAULTS, height=420)
    fig.update_layout(
        xaxis=dict(gridcolor=GRID_COLOR, tickangle=-30),
        yaxis=dict(gridcolor=GRID_COLOR),
        coloraxis_showscale=False,
    )
    return fig


def render_line(df: pd.DataFrame, title: str = "") -> go.Figure:
    non_numeric = df.select_dtypes(exclude="number").columns.tolist()
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    x_col = non_numeric[0] if non_numeric else df.columns[0]
    fig = go.Figure()

    for i, y_col in enumerate(numeric_cols[:4]):
        fig.add_trace(go.Scatter(
            x=df[x_col],
            y=df[y_col],
            mode="lines+markers",
            name=y_col,
            line=dict(color=PALETTE[i % len(PALETTE)], width=2.5),
            marker=dict(size=5),
            fill="tozeroy" if i == 0 else None,
            fillcolor=f"rgba(124,58,237,0.08)" if i == 0 else None,
        ))

    fig.update_layout(**_LAYOUT_DEFAULTS, title=title, height=420)
    fig.update_layout(
        xaxis=dict(gridcolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR),
    )
    return fig


def render_pie(df: pd.DataFrame, title: str = "") -> go.Figure:
    non_numeric = df.select_dtypes(exclude="number").columns.tolist()
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    names_col = non_numeric[0] if non_numeric else df.columns[0]
    values_col = numeric_cols[0] if numeric_cols else df.columns[1]

    fig = px.pie(
        df,
        names=names_col,
        values=values_col,
        hole=0.5,
        color_discrete_sequence=PALETTE,
        title=title,
    )
    fig.update_traces(textfont_size=11, textinfo="label+percent")
    fig.update_layout(**_LAYOUT_DEFAULTS, height=420, showlegend=True)
    return fig


def render_scatter(df: pd.DataFrame, title: str = "") -> go.Figure:
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if len(numeric_cols) < 2:
        return render_bar(df, title)

    fig = px.scatter(
        df,
        x=numeric_cols[0],
        y=numeric_cols[1],
        color_discrete_sequence=[PALETTE[0]],
        title=title,
        opacity=0.7,
    )
    fig.update_layout(**_LAYOUT_DEFAULTS, height=420)
    return fig


# ── Main dispatcher ──────────────────────────────────────────────────────────

def render_visualization(
    df: pd.DataFrame,
    chart_type: Optional[str] = None,
    hint: Optional[str] = None,
    title: str = "Query Results",
) -> None:
    """
    Auto-select and render the best visualization for a DataFrame.
    Also renders the raw data table below the chart.
    """
    if df is None or df.empty:
        st.info("No data to visualize.")
        return

    ct = chart_type or detect_chart_type(df, hint)
    logger.info("Rendering chart type: %s", ct)

    if ct == "kpi":
        render_kpi_cards(df)
    elif ct == "bar":
        st.plotly_chart(render_bar(df, title), use_container_width=True)
    elif ct == "line":
        st.plotly_chart(render_line(df, title), use_container_width=True)
    elif ct == "pie":
        st.plotly_chart(render_pie(df, title), use_container_width=True)
    elif ct == "scatter":
        st.plotly_chart(render_scatter(df, title), use_container_width=True)
    else:
        pass  # table only — handled outside
