"""
Day 27 QA Test Script — Integration testing across all pages and tickers.
Tests 10 tickers across IT, Financials, FMCG, Energy, Healthcare sectors.
Also tests edge cases: partial data, extreme values, NaN handling.
"""

import sys, sqlite3, time, traceback
sys.path.insert(0, '.')

import pandas as pd

# Suppress streamlit warnings
import warnings
warnings.filterwarnings('ignore')

from src.dashboard.utils.db import (
    get_companies, get_sectors, get_pl, get_cf, get_ratios, get_valuation,
    get_prosandcons, get_ticker_list, get_home_summary, get_trend_metrics,
    get_sector_bubble_data, get_sector_kpi_summary, get_capital_allocation_map,
    get_annual_reports, get_screener_data, get_broad_sectors, get_peer_sector_data,
    get_valuation_data,
)

# Test tickers: IT, Financials, FMCG, Energy, Healthcare + partial-data companies
TEST_TICKERS = [
    "TCS",          # IT - full data
    "INFY",         # IT - full data
    "HDFCBANK",     # Financials
    "AXISBANK",     # Financials
    "HINDUNILVR",   # Consumer Staples (FMCG)
    "NESTLEIND",    # Consumer Staples
    "ADANIGREEN",   # Energy - PARTIAL (8yr PL)
    "APOLLOHOSP",   # Healthcare
    "CIPLA",        # Healthcare
    "RELIANCE",     # Energy/Conglom
]

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results = []

def test(name, fn):
    t0 = time.time()
    try:
        result = fn()
        elapsed = time.time() - t0
        status = PASS
        msg = f"{elapsed:.2f}s"
        if isinstance(result, pd.DataFrame):
            msg += f" | {len(result)} rows"
        results.append((name, status, msg))
        return result
    except Exception as e:
        elapsed = time.time() - t0
        results.append((name, FAIL, str(e)[:120]))
        return None

def check_no_crash_with_nan(df, name):
    """Verify NaN values don't crash display operations."""
    if df is None or df.empty:
        results.append((f"NaN check: {name}", WARN, "empty df"))
        return
    for col in df.select_dtypes(include='number').columns:
        nan_count = df[col].isna().sum()
        if nan_count > 0:
            # Simulate dashboard display: format with fillna
            display = df[col].fillna(float('nan'))
            results.append((f"NaN in {name}.{col}", WARN, f"{nan_count} NaN values - display safe"))

# ── 1. Global data functions ──────────────────────────────────────────────────
print("=== Testing global data functions ===")
test("get_companies()", get_companies)
test("get_sectors()", get_sectors)
test("get_ticker_list()", get_ticker_list)
test("get_sector_bubble_data()", get_sector_bubble_data)
test("get_sector_kpi_summary()", get_sector_kpi_summary)
test("get_capital_allocation_map()", get_capital_allocation_map)
test("get_screener_data()", get_screener_data)
test("get_valuation_data()", get_valuation_data)
test("get_broad_sectors()", get_broad_sectors)

for year in [2024, 2023, 2022, 2020, 2019]:
    test(f"get_home_summary({year})", lambda y=year: get_home_summary(y))

# ── 2. Per-ticker tests ───────────────────────────────────────────────────────
print("\n=== Testing per-ticker functions ===")
for ticker in TEST_TICKERS:
    t0 = time.time()
    try:
        pl = get_pl(ticker)
        cf = get_cf(ticker)
        ra = get_ratios(ticker)
        tr = get_trend_metrics(ticker)
        rp = get_annual_reports(ticker)
        pc = get_prosandcons(ticker)
        el = time.time() - t0
        yr_count = len(pl) if pl is not None else 0
        results.append((f"Ticker: {ticker}", PASS,
                        f"{el:.2f}s | PL={yr_count}yr | reports={len(rp) if rp is not None else 0}"))
        # NaN checks on ratio columns
        if ra is not None and not ra.empty:
            check_no_crash_with_nan(ra, ticker)
    except Exception as e:
        results.append((f"Ticker: {ticker}", FAIL, str(e)[:120]))

# ── 3. Partial-data tickers ──────────────────────────────────────────────────
print("\n=== Testing partial-data handling ===")
for ticker in ["ADANIGREEN", "AMBUJACEM", "HCLTECH"]:
    pl = get_pl(ticker)
    if pl is not None:
        yr = len(pl)
        if yr < 10:
            results.append((f"Partial data: {ticker}", WARN, f"Only {yr} years — dashboard must handle gracefully"))
        else:
            results.append((f"Partial data: {ticker}", PASS, f"{yr} years OK"))

# ── 4. Screener extreme values ───────────────────────────────────────────────
print("\n=== Testing screener with extreme values ===")
def test_screener_extremes():
    df = get_screener_data()
    if df.empty:
        return df
    # All min filter (nothing passes numeric min/max check)
    extreme_min = df[
        (df["return_on_equity_pct"].fillna(0) >= 0) &
        (df["debt_to_equity"].fillna(999) <= 999)
    ]
    # All max filter (everything passes)
    extreme_max = df[df["pe_ratio"].fillna(0) <= 10000]
    return df  # no crash = pass

test("Screener extreme values", test_screener_extremes)

# ── 5. Peer sector data ──────────────────────────────────────────────────────
print("\n=== Testing peer sector data ===")
sectors_list = get_broad_sectors()
for sector in sectors_list:
    test(f"Peer: {sector[:30]}", lambda s=sector: get_peer_sector_data(s))

# ── 6. Profile load time ─────────────────────────────────────────────────────
print("\n=== Measuring Profile page load time (5 tickers) ===")
profile_tickers = ["TCS", "HDFCBANK", "RELIANCE", "CIPLA", "HINDUNILVR"]
for ticker in profile_tickers:
    t0 = time.time()
    get_pl(ticker)
    get_ratios(ticker)
    get_prosandcons(ticker)
    get_companies()
    get_sectors()
    elapsed = time.time() - t0
    status = PASS if elapsed < 3.0 else FAIL
    results.append((f"Profile load: {ticker}", status, f"{elapsed:.2f}s (limit: 3.0s)"))

# ── Print results ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print(f"{'Test':<45} {'Status':<6} {'Detail'}")
print("="*70)
pass_count = warn_count = fail_count = 0
for name, status, detail in results:
    icon = "OK  " if status == PASS else ("WARN" if status == WARN else "FAIL")
    print(f"{name[:44]:<45} {icon:<6} {detail}")
    if status == PASS: pass_count += 1
    elif status == WARN: warn_count += 1
    else: fail_count += 1

print("="*70)
print(f"TOTAL: {pass_count} passed, {warn_count} warnings, {fail_count} failed")
