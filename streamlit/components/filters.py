"""filters.py — Sidebar helpers and shared UI utilities."""
import os
import streamlit as st


def load_css():
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")
    if os.path.exists(path):
        with open(path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def sidebar_header(page_name=""):
    st.sidebar.markdown(
        f"""
        <div style="padding:6px 0 14px">
          <div style="font-size:16px;font-weight:800;color:#E4E4E7;letter-spacing:-0.02em">
            📊 Olist ML
          </div>
          <div style="font-size:11px;color:#52525B;margin-top:3px;font-weight:500;
                      text-transform:uppercase;letter-spacing:0.06em">
            {page_name}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")


def multiselect(label, options, default=None):
    return st.sidebar.multiselect(label, options,
                                  default=list(options) if default is None else default)


def range_slider(label, lo, hi, step=None):
    kw = dict(min_value=lo, max_value=hi, value=(lo, hi))
    if step is not None:
        kw["step"] = step
    return st.sidebar.slider(label, **kw)


def sidebar_divider(label=""):
    if label:
        st.sidebar.markdown(
            f'<p style="font-size:10px;font-weight:700;color:#52525B;'
            f'text-transform:uppercase;letter-spacing:0.1em;margin:10px 0 4px">'
            f'{label}</p>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown("---")


def reset_btn():
    st.sidebar.markdown("---")
    if st.sidebar.button("↺  Reset All Filters", use_container_width=True):
        st.rerun()


def last_updated(ts):
    st.sidebar.markdown("---")
    st.sidebar.caption(f"🕐 Data scored at: {ts}")


def section_label(text, icon=""):
    st.markdown(
        f'<p style="font-size:10px;font-weight:700;color:#52525B;'
        f'text-transform:uppercase;letter-spacing:0.10em;margin:0 0 6px">'
        f'{icon}&nbsp;{text}</p>',
        unsafe_allow_html=True,
    )
