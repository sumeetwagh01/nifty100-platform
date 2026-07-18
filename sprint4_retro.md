# Sprint 4 Retrospective
## Nifty 100 Financial Intelligence Platform
**Sprint:** 4 — Streamlit Dashboard
**Days:** 22–28 | **Story Points:** ~56 SP | **Epic:** 05 — Dashboard

---

## Sprint Goal — Achieved ✅

> By end of Sprint 4, all 8 Streamlit dashboard screens must be fully
> functional, accessible on Streamlit Community Cloud, displaying live data
> from the SQLite database for all 92 Nifty 100 companies.

**Actual outcome:** 8 screens fully implemented and deployed. Dashboard live
on Streamlit Community Cloud. 92 companies, 443 tests passing (inherited
from Sprint 3). Valuation module (Day 26) added with FCF yield, sector P/E
benchmarks, and Caution/Discount/Fair flags.

---

## Exit Gate Results

| Gate | Target | Actual | Status |
|------|--------|--------|--------|
| Screens delivered | 8 | 8 | ✅ |
| Deployed to Cloud | ✅ | ✅ | ✅ |
| Profile load time | < 3s | ~0.01s | ✅ |
| QA tickers tested | 10 | 10 | ✅ |
| QA failures | 0 | 0 | ✅ |
| Partial-data handled | ✅ | ✅ | ✅ |
| Screener extreme values | no crash | no crash | ✅ |
| Valuation companies | 92 | 92 | ✅ |
| Caution/Discount flagged | — | 44 | ✅ |
| README.md with run instructions | ✅ | ✅ | ✅ |

---

## Daily Delivery Summary

| Day | Deliverable | Notes |
|-----|------------|-------|
| 22 | `streamlit_app.py` scaffold + `pages/01_home.py` stub | Navigation skeleton, sys.path fix |
| 23 | Home page full + Company Profile page | 6 KPI tiles, bar+line charts, sector donut |
| 24 | Screener page + Peer Comparison page | 10 sliders, 6 presets, sector peer bar charts |
| 25 | Trends, Sectors, Capital, Reports pages | Bubble chart, treemap, BSE PDF links |
| 26 | `src/analytics/valuation.py` | FCF yield, sector median P/E, 44 flagged |
| 27 | Integration QA + bug fixes | 42 tests, 0 failures, all load times < 3s |
| 28 | README.md + retro + task board | Full documentation |

---

## Key Design Decisions

### Cloud Entry Point — `streamlit_app.py` is self-contained
Initially delegated to `src/dashboard/app.py` via `runpy.run_path()`, then
`exec()`. Both approaches broke Streamlit Cloud's script runner because
`st.navigation()` called inside nested exec() is not tracked by the runner.

**Resolution:** `streamlit_app.py` contains all navigation logic directly.
`src/dashboard/app.py` remains for local dev (identical logic). Pages use
`Path(__file__).resolve().parents[N]` for path resolution — works both on
Windows (local) and Linux (Cloud).

### st.Page() — relative vs absolute paths
Spent 3 deployment iterations discovering that `st.Page("relative/path")`
resolves relative to the main script (repo root), not the calling file.
Switched to relative paths in `streamlit_app.py`: `"src/dashboard/pages/01_home.py"`.
Absolute paths via `str(_PAGES / "01_home.py")` also work once the main
script is at the repo root.

### NaN Display — `_fmt()` helper pattern
Every page uses a `_fmt(val, suffix)` helper that returns `"—"` for
`None`/`NaN`. This prevents crashes on companies with partial data (e.g.,
ADANIGREEN with only 8 years of P&L history).

### Screener sliders — explicit min/max bounds
Slider bounds hardcoded based on actual DB data ranges (ROE_MAX=65, PE_MAX=80,
etc.). Setting `min_value=0.0, max_value=65.0` prevents float overflow on
extreme drag operations. Session state preserves values across preset button
clicks.

### Trends page — dual Y-axis for ratio vs absolute metrics
When overlaying Revenue (₹ Cr) and ROE (%) on the same chart, the scale
difference makes ratio metrics invisible. Resolved with `make_subplots(secondary_y=True)`:
ratio metrics (ROE, ROCE, D/E, NPM) on secondary axis when more than one
metric is selected.

### Capital Allocation Treemap — equal size per company
`values=[1] * len(df)` gives equal treemap tile area per company. This
prevents large-cap companies (Reliance, TCS) from visually dominating the
treemap at the expense of smaller companies, making pattern distribution
clearer.

### Sector Bubble chart — log scale for X-axis
Revenue spans 3 orders of magnitude (₹100 Cr to ₹900,000 Cr). Linear scale
compresses all small/mid-cap companies into a narrow band. Log scale (`xaxis.type="log"`)
spreads the distribution evenly and makes sub-sector patterns visible.

### Valuation flags — sector-relative thresholds
Absolute P/E thresholds (e.g., "P/E > 30 = expensive") are meaningless across
sectors. IT companies trade at 25–35x while energy companies trade at 8–12x.
Flags use `sector_median_PE × 1.5` for Caution and `× 0.7` for Discount,
making them sector-relative. Result: 48 Fair, 30 Discount, 14 Caution.

---

## Data Edge Cases Discovered

| Edge Case | Company | Handling |
|-----------|---------|----------|
| Only 8 years of P&L | ADANIGREEN | Info banner on Trends page |
| 11 years P&L (not 12) | HCLTECH, AMBUJACEM | Graceful — CAGR shows N/A for earliest years |
| ROE stored as decimal fraction | Multiple | Use ratio engine value for analytics only |
| ROCE = NULL for Financials sector | 23 banks/NBFCs | Display "—"; not compared cross-sector |
| ICR = NULL for debt-free | Multiple | Displayed as "Debt Free" label |
| Capital allocation pattern NULL | 0 companies | COALESCE to 'Unknown' in SQL |
| Annual report URL not starting with http | Edge case | Red "Unavailable" badge shown |
| Market cap data missing for some years | Screener | `LEFT JOIN` + NaN-safe sliders |

---

## Performance Findings

All `db.py` functions use `@st.cache_data(ttl=600)`. With caching:

| Function | First call | Cached |
|----------|-----------|--------|
| `get_companies()` | ~5ms | <1ms |
| `get_pl(ticker)` | ~10ms | <1ms |
| `get_ratios(ticker)` | ~10ms | <1ms |
| `get_screener_data()` | ~15ms | <1ms |
| `get_sector_bubble_data()` | ~20ms | <1ms |
| Profile page (5 functions) | ~25ms | <5ms |

**Target:** < 3s per page. Achieved: < 50ms for all pages. Cache eliminates
repeat DB hits within a 10-minute session window.

---

## UX Decisions

- **Dark theme** (`#0e1117` background, `#1a1f2e` cards): consistent with financial terminal aesthetics
- **Inter font** from Google Fonts: clean, professional, widely supported
- **Metric cards** styled with subtle border and slight blue tint: visually distinct from regular text
- **Plotly dark template**: all charts use `paper_bgcolor="#0e1117"` to match app background
- **Sidebar brand block**: "📈 Nifty 100 Analytics" header appears on all pages for spatial continuity
- **Dividers** (`st.divider()`) section each page into logical visual blocks
- **Spinner** on heavy loads: `with st.spinner("Loading...")` on Profile and Peers pages
- **`use_container_width=True`** on all charts: prevents overflow regardless of window width

---

## What Went Well

- **`db.py` as single source of truth**: all 8 pages import from one file — no duplicate SQL
- **`@st.cache_data`** made all pages feel instant after first load
- **Plotly dark styling** carried across all 8 pages consistently — no chart felt out of place
- **Relative `st.Page()` paths** from repo root eliminated all Cloud path issues once identified
- **QA script** (`day27_qa.py`) ran 42 tests in < 2 seconds — caught no failures

## What Could Improve

- **Cloud deployment debugging**: Generic "Oh no" screen hides all errors — diagnostic
  version with `try/except` + `st.code(traceback)` was essential but should be default
- **Peer percentiles table**: `peer_percentiles` table is empty (0 rows) — percentile
  computation pipeline was not re-run after Sprint 3. Peers page falls back to sector averages
- **Annual reports URL quality**: ~30% of `documents.annual_report_url` values are not
  valid HTTP links. Shown as Unavailable — acceptable but a data quality backlog item
- **`st.Page()` with absolute paths**: Streamlit Cloud behaviour differed from local on
  Windows. Always use repo-root-relative paths when `streamlit_app.py` is at repo root

---

## Sprint 4 — What's Next (Sprint 5 Candidates)

- **Alerts & Watchlist Engine**: Watch companies for KPI threshold breaches — email alerts
- **NLP summaries**: Auto-generate qualitative buy/sell commentary from `prosandcons` table
- **Peer percentiles re-population**: Run the peer pipeline to populate the empty table
- **Annual report URL validation**: Batch-check all 1,456 URLs and cache results
- **Mobile-responsive layout**: Streamlit defaults are not touch-friendly
- **Authentication**: Add `st.login()` for private deployments

---

*Sprint 4 signed off — 8 screens, Cloud deployed, 0 QA failures, README updated.*
