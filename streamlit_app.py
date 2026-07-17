"""
streamlit_app.py — Main entry point (Streamlit Community Cloud + local dev).
=============================================================================
This file IS the app. No delegation, no exec(), no runpy.

Local dev:   streamlit run streamlit_app.py   (or src/dashboard/app.py)
Cloud:       Streamlit Cloud runs this file automatically.

All st.Page() paths are absolute (derived from __file__) so they resolve
correctly on both Windows (local) and Linux (Cloud), regardless of the
working directory at launch time.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path — insert repo root FIRST so all `src.*` imports resolve.
# This file lives at the repo root, so __file__.parent IS the repo root.
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .sidebar-brand {
        text-align: center; padding: 1rem 0 0.5rem;
        font-size: 1.1rem; font-weight: 700;
        color: #4f8ef7; letter-spacing: 0.04em;
    }
    .sidebar-sub {
        text-align: center; font-size: 0.75rem;
        color: #8a94a6; margin-bottom: 1rem;
    }

    [data-testid="stMetric"] {
        background: #1a1f2e; border-radius: 10px;
        padding: 0.75rem 1rem; border: 1px solid #2a3040;
    }

    [data-testid="stSidebarNav"] a {
        font-size: 0.92rem; padding: 0.45rem 0.75rem;
        border-radius: 6px; transition: background 0.15s ease;
    }
    [data-testid="stSidebarNav"] a:hover { background: rgba(79,142,247,0.12); }

    hr { border-color: #2a3040; }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0e1117; }
    ::-webkit-scrollbar-thumb { background: #2a3040; border-radius: 3px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar brand
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand">📈 Nifty 100 Analytics</div>'
        '<div class="sidebar-sub">Financial Intelligence Platform</div>',
        unsafe_allow_html=True,
    )
    st.divider()

# ---------------------------------------------------------------------------
# Page definitions — absolute paths so Cloud resolves them correctly.
# st.Page() resolves relative paths from the MAIN script dir (repo root here),
# so we always use absolute paths built from the pages directory.
# ---------------------------------------------------------------------------
_PAGES = _ROOT / "src" / "dashboard" / "pages"

home_page     = st.Page(str(_PAGES / "01_home.py"),     title="🏠 Home",              icon="🏠")
profile_page  = st.Page(str(_PAGES / "02_profile.py"),  title="🏢 Company Profile",   icon="🏢")
screener_page = st.Page(str(_PAGES / "03_screener.py"), title="🔍 Screener",          icon="🔍")
peers_page    = st.Page(str(_PAGES / "04_peers.py"),    title="👥 Peer Comparison",   icon="👥")
trends_page   = st.Page(str(_PAGES / "05_trends.py"),   title="📊 Trends",            icon="📊")
sectors_page  = st.Page(str(_PAGES / "06_sectors.py"),  title="🏭 Sectors",           icon="🏭")
capital_page  = st.Page(str(_PAGES / "07_capital.py"),  title="💰 Capital Allocation",icon="💰")
reports_page  = st.Page(str(_PAGES / "08_reports.py"),  title="📄 Reports",           icon="📄")

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
pg = st.navigation(
    {
        "Dashboard": [home_page],
        "Company":   [profile_page],
        "Analysis":  [screener_page, peers_page, trends_page],
        "Market":    [sectors_page, capital_page],
        "Output":    [reports_page],
    }
)

pg.run()
