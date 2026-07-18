# Nifty 100 Financial Intelligence Platform

A production-ready financial analytics platform for all **92 Nifty 100 companies**, built over 4 sprints. Provides a Streamlit dashboard with 8 interactive screens covering company profiles, stock screening, peer comparison, trend analysis, sector analysis, capital allocation, annual reports, and valuation.

---

## Quick Start

### Local Development

```bash
# Clone the repo
git clone https://github.com/sumeetwagh01/nifty100-platform.git
cd nifty100-platform

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Run the dashboard (recommended — from repo root)
streamlit run streamlit_app.py

# Alternative: run from the src/dashboard directory
streamlit run src/dashboard/app.py
```

The app will open at **http://localhost:8501**

### Streamlit Community Cloud

Deployed at: `https://nifty100-platform-ntakud5rjqkqxeisvwueqh.streamlit.app`

- **Repository:** `sumeetwagh01/nifty100-platform`
- **Branch:** `master`
- **Main file:** `streamlit_app.py`

---

## Project Structure

```
nifty100-platform/
├── streamlit_app.py           # Cloud entry point — self-contained app
├── requirements.txt           # Cloud runtime dependencies
├── requirements-dev.txt       # Dev + test dependencies
├── data/
│   └── nifty100.db            # SQLite database (92 companies, 13 tables)
├── src/
│   ├── analytics/             # Sprint 2–4 analytics engine
│   │   ├── ratios.py          # 50+ KPI formulas
│   │   ├── cagr.py            # CAGR with 6 edge-case sentinels
│   │   ├── cashflow_kpis.py   # FCF, CFO Quality, Capital Allocation (8 patterns)
│   │   ├── peer.py            # Peer percentile rankings
│   │   ├── radar.py           # Radar charts (8-axis)
│   │   ├── valuation.py       # Day 26 — FCF yield, sector P/E, Caution/Discount/Fair
│   │   └── peer_comparison.py # 11-sheet peer comparison Excel
│   ├── screener/              # Sprint 3 screener engine
│   │   ├── engine.py          # 15-metric screener with YAML config
│   │   └── presets.py         # 6 named preset screeners
│   ├── dashboard/
│   │   ├── app.py             # Local dev entry point
│   │   ├── utils/
│   │   │   └── db.py          # All database query functions (cached)
│   │   └── pages/
│   │       ├── 01_home.py     # Dashboard Home
│   │       ├── 02_profile.py  # Company Profile
│   │       ├── 03_screener.py # Stock Screener
│   │       ├── 04_peers.py    # Peer Comparison
│   │       ├── 05_trends.py   # Historical Trends
│   │       ├── 06_sectors.py  # Sector Analysis
│   │       ├── 07_capital.py  # Capital Allocation Map
│   │       └── 08_reports.py  # Annual Reports
│   └── etl/                   # Sprint 1 data pipeline
├── output/                    # Generated reports (gitignored)
│   ├── screener_output.xlsx
│   ├── peer_comparison.xlsx
│   ├── valuation_summary.xlsx
│   └── valuation_flags.csv
└── tests/                     # 443 passing unit + integration tests
```

---

## 8 Dashboard Screens

### 🏠 Home — Dashboard Overview
**File:** `src/dashboard/pages/01_home.py`

The landing screen showing a market-wide snapshot for any selected year (2019–2024).

- **6 KPI tiles**: Avg ROE, Median P/E, Median D/E, Total Companies, Median Rev CAGR 5yr, Debt-Free count
- **Sector Donut Chart**: 11 sectors with company counts (Plotly)
- **Top-5 by Quality Score**: Table of highest composite quality score companies
- **Year selector** in sidebar — all widgets update reactively

---

### 🏢 Company Profile
**File:** `src/dashboard/pages/02_profile.py`

Detailed single-company deep-dive. Type any company name or ticker in the search box.

- **Company card**: Name, NSE ticker badge, sector/sub-sector badges, about text
- **6 KPI tiles**: ROE, ROCE, NPM, D/E, Rev CAGR 5yr, FCF (latest year)
- **Revenue & Net Profit bar chart** (10 years) — Plotly
- **ROE & ROCE dual-axis line chart** (10 years)
- **Cash Flow waterfall** (operating, investing, financing)
- **Pros & Cons** from qualitative analysis

---

### 🔍 Stock Screener
**File:** `src/dashboard/pages/03_screener.py`

Filter all 92 companies by 10 financial metrics with 6 preset buttons.

- **10 slider filters**: ROE, D/E, FCF, Rev CAGR, PAT CAGR, NPM, P/E, P/B, Dividend Yield, ICR
- **6 presets**: Quality Compounder, Dividend Aristocrat, Growth Story, Turnaround Watch, Value Pick, Debt Free
- **Live result count** — updates instantly as sliders move
- **CSV download** of filtered results

---

### 👥 Peer Comparison
**File:** `src/dashboard/pages/04_peers.py`

Compare a company against its sector peers across 10 KPIs.

- **Sector selector** — 11 peer groups (IT Services, NBFC, FMCG, etc.)
- **Bar charts** for each KPI with company highlighted
- **Percentile rank table** — where each company ranks within its peer group
- **Sector median benchmark** shown on all charts

---

### 📊 Historical Trends
**File:** `src/dashboard/pages/05_trends.py`

10-year multi-metric overlay chart with YoY % change annotations.

- **Multi-metric selector**: Choose up to 3 metrics to overlay (Revenue, Net Profit, EPS, ROE, ROCE, D/E, NPM, FCF)
- **YoY % change** shown on every data point as annotations
- **Dual Y-axis** — ratio metrics (%) on secondary axis to prevent scale distortion
- **Partial-data notice** for companies with fewer than 10 years of history

> **Edge cases handled**: Companies with fewer than 10 years (e.g., ADANIGREEN — 8yr) show an info banner. NaN values for CAGR metrics in early years display as blank — no crash.

---

### 🏭 Sector Analysis
**File:** `src/dashboard/pages/06_sectors.py`

Sector-wide bubble chart and KPI benchmarks.

- **Bubble chart**: X = Revenue, Y = ROE, bubble size = Market Cap, colour = sub-sector (Plotly scatter)
- **Sector filter**: View all sectors or drill into one
- **4 KPI summary tiles**: Companies, Avg ROE, Avg Revenue, Avg Market Cap
- **KPI bar chart**: Compare sectors by Avg ROE / ROCE / NPM / D/E (radio selector)
- **Company table** for selected sector, sorted by quality score

---

### 💰 Capital Allocation Map
**File:** `src/dashboard/pages/07_capital.py`

Treemap of 92 companies grouped by 8 capital allocation patterns (based on CFO/CFI/CFF signs).

- **Plotly treemap**: 3-level hierarchy — Pattern → Sector → Company
- **8 patterns**: Reinvestor, Shareholder Returns, Liquidating Assets, Distress Signal, Growth Funded by Debt, Cash Accumulator, Pre-Revenue, Mixed
- **Pattern legend**: Icon + description + company count per pattern
- **Filterable table**: Select any pattern to see all companies in it

---

### 📄 Annual Reports
**File:** `src/dashboard/pages/08_reports.py`

Annual report links for every company, sourced from the `documents` table.

- **Company selector**: Choose any of 92 companies
- **Year cards**: One card per year with ✅ Available / ❌ Unavailable badge
- **Clickable links**: Direct download links to BSE-hosted PDF annual reports
- **Summary**: Total years / available / unavailable counts

---

## Database Schema

The SQLite database (`data/nifty100.db`) contains 13 tables:

| Table | Rows | Description |
|-------|------|-------------|
| `companies` | 92 | Company metadata (name, website, BSE/NSE links) |
| `sectors` | 92 | Broad sector, sub-sector, index weight |
| `profitandloss` | 1,070 | Annual P&L (revenue, profit, EPS, margins) |
| `balancesheet` | 1,140 | Annual balance sheet (equity, debt, assets) |
| `cashflow` | 1,056 | Annual cash flows (operating, investing, financing) |
| `market_cap` | 552 | Annual market data (P/E, P/B, EV/EBITDA, market cap) |
| `financial_ratios` | 1,155 | Computed KPIs (50+ ratios, CAGR, quality score) |
| `peer_percentiles` | — | Peer group percentile rankings |
| `documents` | 1,456 | Annual report URLs |
| `prosandcons` | 14 | Qualitative pros/cons |
| `stock_prices` | 5,520 | Daily price history |
| `analysis` | 4 | Summary analytics |

---

## Running Analytics Scripts

```bash
# Generate valuation summary (output/valuation_summary.xlsx)
python src/analytics/valuation.py

# Generate peer comparison Excel (output/peer_comparison.xlsx)
python -m src.analytics.peer_comparison

# Generate screener output (output/screener_output.xlsx)
python -m src.screener.engine

# Generate capital allocation CSV
python generate_capital_allocation.py
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Sprint-specific
pytest tests/ -k "sprint2" -v
pytest tests/ -k "sprint3" -v
pytest tests/ -k "integration" -v
```

**443 tests passing** as of Sprint 3 sign-off.

---

## Sprint Retros

| Sprint | Days | Focus | Tests |
|--------|------|-------|-------|
| Sprint 1 | 1–7 | ETL Pipeline, DB schema, data ingestion | — |
| Sprint 2 | 8–14 | Financial Ratio Engine (50+ KPIs, edge cases) | 258 |
| Sprint 3 | 15–21 | Screener, Peer Engine, Excel outputs | 443 |
| Sprint 4 | 22–28 | Streamlit Dashboard (8 screens) | — |

---

## Dependencies

```
streamlit~=1.36.0
pandas~=2.2.0
plotly~=5.21.0
scipy~=1.13.0
numpy~=1.26.0
openpyxl~=3.1.0
```
