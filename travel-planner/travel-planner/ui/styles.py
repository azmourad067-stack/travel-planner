"""ui/styles.py — Feuille de style légère pour une interface claire et pro."""

import streamlit as st

CUSTOM_CSS = """
<style>
    .main > div { padding-top: 1.5rem; }
    .package-card {
        border: 1px solid #e6e6e6;
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 1rem;
        background-color: #ffffff;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .package-card.top-pick {
        border: 2px solid #1f8a70;
        background-color: #f3fbf9;
    }
    .badge {
        display: inline-block;
        background-color: #eef3ff;
        color: #1f4fd6;
        border-radius: 20px;
        padding: 2px 12px;
        font-size: 0.78rem;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    .score-pill {
        font-weight: 700;
        font-size: 1.2rem;
        color: #1f8a70;
    }
    .muted { color: #7a7a7a; font-size: 0.85rem; }
</style>
"""


def inject_custom_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
