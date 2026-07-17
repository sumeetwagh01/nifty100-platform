"""
streamlit_app.py — Nifty 100 Financial Intelligence Platform
=============================================================
Entry point for Streamlit Community Cloud (and local dev).

Approach: use st.Page() with paths RELATIVE to this file's directory
(the repo root), which is the safest cross-platform method.
"""

import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path — repo root must be first so all `src.*` imports resolve.
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Validate critical paths before continuing — surface clear errors on Cloud
# ---------------------------------------------------------------------------
_PAGES = _ROOT / "src" / "dashboard" / "pages"
_DB    = _ROOT / "data" / "nifty100.db"

_errors = []
if not _PAGES.exists():
    _errors.append(f"❌ Pages directory not found: `{_PAGES}`")
if not _DB.exists():
    _errors.append(f"❌ Database not found: `{_DB}`")
for _name in [
    "01_home.py","02_profile.py","03_screener.py","04_peers.py",
    "05_trends.py","06_sectors.py","07_capital.py","08_reports.py"
]:
    if not (_PAGES / _name).exists():
        _errors.append(f"❌ Missing page file: `{_name}`")

if _errors:
    st.error("**Startup failed — path errors:**")
    for e in _errors:
        st.markdown(e)
    st.info(f"**Python:** `{sys.version}`\n\n**Repo root:** `{_ROOT}`\n\n**sys.path[0]:** `{sys.path[0]}`")
    st.stop()

# ---------------------------------------------------------------------------
# Test core import before wiring navigation
# ---------------------------------------------------------------------------
try:
    from src.dashboard.utils.db import get_ticker_list  # noqa: F401
except Exception as _e:
    st.error("**Import error in `src.dashboard.utils.db`:**")
    st.code(traceback.format_exc())
    st.stop()

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
# Pages — use RELATIVE paths (relative to this file = repo root).
# st.Page() resolves string paths relative to the main script's directory,
# which is the repo root when Cloud runs streamlit_app.py.
# ---------------------------------------------------------------------------
try:
    home_page     = st.Page("src/dashboard/pages/01_home.py",     title="🏠 Home",               icon="🏠")
    profile_page  = st.Page("src/dashboard/pages/02_profile.py",  title="🏢 Company Profile",    icon="🏢")
    screener_page = st.Page("src/dashboard/pages/03_screener.py", title="🔍 Screener",           icon="🔍")
    peers_page    = st.Page("src/dashboard/pages/04_peers.py",    title="👥 Peer Comparison",    icon="👥")
    trends_page   = st.Page("src/dashboard/pages/05_trends.py",   title="📊 Trends",             icon="📊")
    sectors_page  = st.Page("src/dashboard/pages/06_sectors.py",  title="🏭 Sectors",            icon="🏭")
    capital_page  = st.Page("src/dashboard/pages/07_capital.py",  title="💰 Capital Allocation", icon="💰")
    reports_page  = st.Page("src/dashboard/pages/08_reports.py",  title="📄 Reports",            icon="📄")
except Exception as _e:
    st.error("**Failed to register pages with st.Page():**")
    st.code(traceback.format_exc())
    st.stop()

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
try:
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
except Exception as _e:
    st.error("**Navigation error:**")
    st.code(traceback.format_exc())
