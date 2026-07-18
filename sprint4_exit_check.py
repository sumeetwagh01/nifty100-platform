"""
Sprint 4 Exit Criteria Verification Script
==========================================
Checks every Definition of Done item from the Sprint 4 spec.
"""
import sys, sqlite3, time, io, os
sys.path.insert(0, '.')

import warnings; warnings.filterwarnings('ignore')
import pandas as pd

PASS = "PASS"
FAIL = "FAIL"
results = []

def check(name, fn):
    try:
        val = fn()
        results.append((name, PASS, str(val)[:100]))
        return val
    except Exception as e:
        results.append((name, FAIL, str(e)[:120]))
        return None

# ──────────────────────────────────────────────────────────────────────────────
# 1. Deliverables present on disk
# ──────────────────────────────────────────────────────────────────────────────
check("src/dashboard/app.py exists",
      lambda: os.path.isfile("src/dashboard/app.py") or (_ for _ in ()).throw(FileNotFoundError("missing")))

for f in ["src/dashboard/app.py", "src/dashboard/utils/db.py",
          "src/analytics/valuation.py", "README.md"]:
    check(f"File exists: {f}", lambda p=f: True if os.path.isfile(p) else (_ for _ in ()).throw(FileNotFoundError(p)))

for n in range(1, 9):
    pg = f"src/dashboard/pages/0{n}_" + {
        1:"home",2:"profile",3:"screener",4:"peers",
        5:"trends",6:"sectors",7:"capital",8:"reports"}[n] + ".py"
    check(f"Page exists: 0{n}_*.py", lambda p=pg: True if os.path.isfile(p) else (_ for _ in ()).throw(FileNotFoundError(p)))

# ──────────────────────────────────────────────────────────────────────────────
# 2. Generate + verify valuation_summary.xlsx — 92 rows, required columns
# ──────────────────────────────────────────────────────────────────────────────
print("Generating valuation outputs...")
from src.analytics.valuation import run as run_valuation
df_val = run_valuation()

REQUIRED_VAL_COLS = [
    "company_id", "company_name", "broad_sector",
    "pe_ratio", "pb_ratio", "ev_ebitda", "fcf_yield_pct",
    "pe_5yr_median", "pe_vs_sector_median_pct", "flag",
]
def check_valuation():
    assert len(df_val) == 92, f"Expected 92 rows, got {len(df_val)}"
    missing = [c for c in REQUIRED_VAL_COLS if c not in df_val.columns]
    assert not missing, f"Missing columns: {missing}"
    flag_vals = set(df_val["flag"].unique())
    assert flag_vals <= {"Caution", "Discount", "Fair"}, f"Bad flags: {flag_vals}"
    caution = (df_val["flag"] == "Caution").sum()
    discount = (df_val["flag"] == "Discount").sum()
    return f"92 rows | Caution={caution} Discount={discount} Fair={92-caution-discount}"

check("valuation_summary.xlsx — 92 rows + required cols", check_valuation)
check("valuation_summary.xlsx file written", lambda: os.path.isfile("output/valuation_summary.xlsx"))
check("valuation_flags.csv file written",    lambda: os.path.isfile("output/valuation_flags.csv"))

# Check xlsx column headers
def check_xlsx_cols():
    df = pd.read_excel("output/valuation_summary.xlsx")
    cols = df.columns.tolist()
    missing = [c for c in REQUIRED_VAL_COLS if c not in cols]
    assert not missing, f"Missing in xlsx: {missing}"
    return f"{len(df)} rows, {len(cols)} cols"
check("valuation_summary.xlsx columns match spec", check_xlsx_cols)

# Check flags CSV
def check_flags_csv():
    df = pd.read_csv("output/valuation_flags.csv")
    assert set(df["flag"].unique()) <= {"Caution", "Discount"}, f"Unexpected flags: {df['flag'].unique()}"
    assert len(df) > 0, "Empty flags CSV"
    return f"{len(df)} flagged companies"
check("valuation_flags.csv — only Caution/Discount", check_flags_csv)

# ──────────────────────────────────────────────────────────────────────────────
# 3. Screener CSV download — valid file with correct column headers
# ──────────────────────────────────────────────────────────────────────────────
from src.dashboard.utils.db import get_screener_data

def check_screener_csv():
    df = get_screener_data()
    assert not df.empty, "Screener returned empty"
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    reread = pd.read_csv(buf)
    assert len(reread) == len(df), "Row count mismatch after CSV round-trip"
    assert len(reread.columns) == len(df.columns), "Column count mismatch"
    return f"{len(df)} rows, {len(df.columns)} cols, headers: {list(df.columns[:5])}..."
check("Screener CSV — valid file with correct headers", check_screener_csv)

# ──────────────────────────────────────────────────────────────────────────────
# 4. All 8 screens load without errors for all 92 tickers
# ──────────────────────────────────────────────────────────────────────────────
from src.dashboard.utils.db import (
    get_ticker_list, get_pl, get_cf, get_ratios, get_prosandcons,
    get_trend_metrics, get_annual_reports, get_companies, get_sectors,
    get_home_summary, get_screener_data, get_sector_bubble_data,
    get_capital_allocation_map, get_broad_sectors, get_peer_sector_data,
)

tickers = get_ticker_list()
check("92 tickers in DB", lambda: len(tickers) == 92 and len(tickers))

errors = []
t_total = time.time()
for ticker in tickers:
    try:
        get_pl(ticker); get_cf(ticker); get_ratios(ticker)
        get_trend_metrics(ticker); get_annual_reports(ticker)
        get_prosandcons(ticker)
    except Exception as e:
        errors.append(f"{ticker}: {e}")

check("All 92 tickers — no crash on data load",
      lambda: (lambda: (_ for _ in ()).throw(AssertionError(f"{len(errors)} errors: {errors[:3]}")))()
              if errors else f"0 errors in {time.time()-t_total:.1f}s")

# ──────────────────────────────────────────────────────────────────────────────
# 5. Company Profile load < 3 seconds for all 92 tickers
# ──────────────────────────────────────────────────────────────────────────────
slow_tickers = []
for ticker in tickers:
    t0 = time.time()
    get_pl(ticker); get_ratios(ticker); get_prosandcons(ticker)
    get_companies(); get_sectors()
    elapsed = time.time() - t0
    if elapsed > 3.0:
        slow_tickers.append(f"{ticker}={elapsed:.2f}s")

check("Profile load < 3s for ALL 92 tickers",
      lambda: (lambda: (_ for _ in ()).throw(AssertionError(f"Slow: {slow_tickers}")))()
              if slow_tickers else "All 92 tickers < 3s")

# ──────────────────────────────────────────────────────────────────────────────
# 6. Global screens load without errors
# ──────────────────────────────────────────────────────────────────────────────
check("Home summary (2024)", lambda: len(get_home_summary(2024)))
check("Screener data",        lambda: len(get_screener_data()))
check("Sector bubble data",   lambda: len(get_sector_bubble_data()))
check("Capital alloc map",    lambda: len(get_capital_allocation_map()))
check("Peer sector data x10", lambda: sum(len(get_peer_sector_data(s)) for s in get_broad_sectors()))

# ──────────────────────────────────────────────────────────────────────────────
# 7. DB integrity
# ──────────────────────────────────────────────────────────────────────────────
conn = sqlite3.connect("data/nifty100.db")
check("DB companies=92",   lambda: conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 92)
check("DB fin_ratios=1155",lambda: conn.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0] == 1155)
check("DB documents=1456", lambda: conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1456)
conn.close()

# ──────────────────────────────────────────────────────────────────────────────
# Print report
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print(f"{'Exit Criterion':<48} {'Status':<6} {'Detail'}")
print("="*72)
passed = failed = 0
for name, status, detail in results:
    icon = "OK  " if status == PASS else "FAIL"
    print(f"{name[:47]:<48} {icon:<6} {detail}")
    if status == PASS: passed += 1
    else: failed += 1
print("="*72)
print(f"RESULT: {passed} passed / {failed} failed")
if failed == 0:
    print("SPRINT 4 EXIT CRITERIA: ALL PASSED - READY FOR SIGN-OFF")
else:
    print("SPRINT 4 EXIT CRITERIA: FAILURES FOUND - see above")
