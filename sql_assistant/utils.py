"""
utils.py — Shared Utilities
─────────────────────────────
Logging setup, export helpers, formatting, and session-state helpers.
"""

import io
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st


# ── Logging setup ────────────────────────────────────────────────────────────

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── Export helpers ───────────────────────────────────────────────────────────

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Convert a DataFrame to UTF-8 CSV bytes."""
    return df.to_csv(index=False).encode("utf-8")


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Convert a DataFrame to Excel (.xlsx) bytes."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    return buffer.getvalue()


def render_export_buttons(df: pd.DataFrame, label: str = "results") -> None:
    """Render CSV and Excel download buttons for a DataFrame."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="Download CSV / تحميل ملف CSV",
            data=df_to_csv_bytes(df),
            file_name=f"bi_ai_{label}_{ts}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        try:
            st.download_button(
                label="Download Excel / تحميل ملف Excel",
                data=df_to_excel_bytes(df),
                file_name=f"bi_ai_{label}_{ts}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except ImportError:
            st.caption("Install openpyxl for Excel export: `pip install openpyxl`")


# ── Session-state helpers ────────────────────────────────────────────────────

def init_session_state() -> None:
    """Initialise all required Streamlit session-state keys."""
    defaults = {
        "db_engine": None,
        "db_config": {},
        "db_connected": False,
        "schema": None,
        "schema_context": "",
        "chat_history": [],
        "last_sql": "",
        "last_df": None,
        "last_elapsed": 0.0,
        "last_ai_result": None,
        "query_count": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Formatting helpers ───────────────────────────────────────────────────────

def format_elapsed(seconds: float) -> str:
    """Human-readable elapsed time."""
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.2f} s"


def truncate_text(text: str, max_chars: int = 300) -> str:
    """Truncate long strings with an ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def confidence_badge(score: int) -> str:
    """Return a styled span based on confidence score."""
    if score >= 80:
        return '<span style="color: var(--accent-green); font-weight: 600;">High / مرتفع</span>'
    if score >= 50:
        return '<span style="color: #eab308; font-weight: 600;">Medium / متوسط</span>'
    return '<span style="color: var(--accent-rose); font-weight: 600;">Low / منخفض</span>'


# ── Export directory ─────────────────────────────────────────────────────────

def ensure_exports_dir() -> str:
    """Create the exports/ directory next to this file if it doesn't exist."""
    exports = os.path.join(os.path.dirname(__file__), "exports")
    os.makedirs(exports, exist_ok=True)
    return exports
