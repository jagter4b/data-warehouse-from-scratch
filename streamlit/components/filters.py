import streamlit as st

def render_sidebar_header():
    st.sidebar.title("📊 Olist ML Analytics")
    st.sidebar.markdown("---")

def render_multiselect(label, options, default=None):
    if default is None:
        default = options
    return st.sidebar.multiselect(label, options, default=default)

def render_slider(label, min_val, max_val, default=None):
    if default is None:
        default = (min_val, max_val)
    return st.sidebar.slider(label, min_val, max_val, default)

def render_reset_button():
    st.sidebar.markdown("---")
    if st.sidebar.button("Reset Filters", use_container_width=True):
        st.experimental_rerun()

def render_last_updated(scored_at_val):
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last updated: {scored_at_val}")
