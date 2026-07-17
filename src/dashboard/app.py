"""
src/dashboard/app.py
=====================
Main Streamlit entry point for the Nifty 100 Financial Intelligence Platform.

Launch:
    streamlit run src/dashboard/app.py

Configuration:
    - Wide layout
    - Page title: "Nifty 100 Analytics"
    - Sidebar expanded by default
    - Navigation: 8 screens via st.navigation()
"""

# ---------------------------------------------------------------------------
# sys.path fix — must come FIRST, before any project imports.
# Streamlit adds the directory containing app.py (src/dashboard/) to sys.path
# but NOT the repo root, so `from src.dashboard.utils.db import …` would fail
# on every page. Inserting the repo root here fixes all 8 pages at once since
# they all run inside the same Python process.
# Layout: src/dashboard/app.py → parents[0]=dashboard → parents[1]=src → parents[2]=repo root
# ---------------------------------------------------------------------------
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration — MUST be the first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — global theme tokens
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── Global font ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Sidebar brand header ── */
    .sidebar-brand {
        text-align: center;
        padding: 1rem 0 0.5rem;
        font-size: 1.1rem;
        font-weight: 700;
        color: #4f8ef7;
        letter-spacing: 0.04em;
    }
    .sidebar-sub {
        text-align: center;
        font-size: 0.75rem;
        color: #8a94a6;
        margin-bottom: 1rem;
    }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: #1a1f2e;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        border: 1px solid #2a3040;
    }

    /* ── Sidebar navigation items ── */
    [data-testid="stSidebarNav"] a {
        font-size: 0.92rem;
        padding: 0.45rem 0.75rem;
        border-radius: 6px;
        transition: background 0.15s ease;
    }
    [data-testid="stSidebarNav"] a:hover {
        background: rgba(79,142,247,0.12);
    }

    /* ── Dividers ── */
    hr { border-color: #2a3040; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0e1117; }
    ::-webkit-scrollbar-thumb { background: #2a3040; border-radius: 3px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar brand block
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand">📈 Nifty 100 Analytics</div>'
        '<div class="sidebar-sub">Financial Intelligence Platform</div>',
        unsafe_allow_html=True,
    )
    st.divider()

# ---------------------------------------------------------------------------
# Define the 8 pages using st.Page (Streamlit ≥ 1.36)
# ---------------------------------------------------------------------------
# Use absolute paths derived from __file__ so that st.Page() resolves
# correctly whether Streamlit's main script is streamlit_app.py (Cloud/root)
# or src/dashboard/app.py (local dev). Relative paths break on Cloud because
# Streamlit resolves them relative to the main entry-point script, not app.py.
_PAGES = Path(__file__).resolve().parent / "pages"

home_page = st.Page(
    str(_PAGES / "01_home.py"),
    title="🏠 Home",
    icon="🏠",
)
profile_page = st.Page(
    str(_PAGES / "02_profile.py"),
    title="🏢 Company Profile",
    icon="🏢",
)
screener_page = st.Page(
    str(_PAGES / "03_screener.py"),
    title="🔍 Screener",
    icon="🔍",
)
peers_page = st.Page(
    str(_PAGES / "04_peers.py"),
    title="👥 Peer Comparison",
    icon="👥",
)
trends_page = st.Page(
    str(_PAGES / "05_trends.py"),
    title="📊 Trends",
    icon="📊",
)
sectors_page = st.Page(
    str(_PAGES / "06_sectors.py"),
    title="🏭 Sectors",
    icon="🏭",
)
capital_page = st.Page(
    str(_PAGES / "07_capital.py"),
    title="💰 Capital Allocation",
    icon="💰",
)
reports_page = st.Page(
    str(_PAGES / "08_reports.py"),
    title="📄 Reports",
    icon="📄",
)

# ---------------------------------------------------------------------------
# Wire up navigation — Streamlit renders the selected page automatically
# ---------------------------------------------------------------------------
pg = st.navigation(
    {
        "Dashboard": [home_page],
        "Company": [profile_page],
        "Analysis": [screener_page, peers_page, trends_page],
        "Market": [sectors_page, capital_page],
        "Output": [reports_page],
    }
)

pg.run()
