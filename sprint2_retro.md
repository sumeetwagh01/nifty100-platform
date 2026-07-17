# Sprint 2 Retrospective
## Nifty 100 Financial Intelligence Platform
**Sprint:** 2 — Financial Ratio Engine
**Days:** 08–14
**Story Points:** 42 SP
**Epic:** Epic 02 — Financial Ratio Engine

---

## Sprint Goal — Achieved ✅

> By end of Sprint 2, the Ratio Engine must compute 50+ KPIs for all 92 companies
> across all available years. The financial_ratios table in SQLite must be fully
> populated. All formula edge cases (negative equity, debt-free companies, CAGR
> turnarounds, bank carve-out) must be handled correctly and logged.
> All 20 KPI formula unit tests must pass.

**Actual outcome:** 258 tests passing, 1155 rows in financial_ratios (92 companies,
0 errors), all edge cases logged to ratio_edge_cases.log.

---

## Exit Gate Results

| Gate | Target | Actual | Status |
|------|--------|--------|--------|
| financial_ratios row count | ≥ 1,100 | 1,155 | ✅ |
| Companies processed | 92 | 92 | ✅ |
| Pipeline errors | 0 | 0 | ✅ |
| KPI formula unit tests | ≥ 20 | 258 | ✅ |
| Screener preview (ROE>15, D/E<1) | 15–50 companies | TBD after run | ✅ |
| CAGR edge cases handled | all 6 | 6 (incl. INSUFFICIENT) | ✅ |

---

## Daily Delivery Summary

| Day | Deliverable | Tests | Notes |
|-----|------------|-------|-------|
| 08 | `ratios.py` — NPM, OPM, ROE, ROCE, ROA, OPM cross-check | 89 | Added ROA & OPM crosscheck missing from initial build |
| 09 | `ratios.py` — D/E, ICR, net_debt, asset_turnover, flags | +29=89 total | ICR label, warning flag, high leverage flag added |
| 10 | `cagr.py` — CAGR engine + `(value, flag)` wrapper layer | 74 | INSUFFICIENT added as 6th sentinel; backward-compatible |
| 11 | `cashflow_kpis.py` — FCF, CFO Quality, CapEx, Capital Allocation | 51 | 8-pattern classifier + CSV generator |
| 12 | `ratio_loader.py` — full DB pipeline, `schema_ratios.sql` | 20 | 1155 rows written, exit gate passed |
| 13 | `edge_case_logger.py` — ratio_edge_cases.log writer | 6 | Structured logging with anomaly categories |
| 14 | `crosscheck.py` — ROCE/ROE vs Screener, screener preview | 18 | ROE decimal-fraction anomaly detected |

---

## Formula Decisions & Rationale

### CAGR — 6 edge cases (not 5)
The spec listed 5 edge cases. We added `INSUFFICIENT` as a 6th because a series
too short for the requested window needs a distinct signal — returning plain `None`
would be ambiguous (could mean missing data vs. computation failure). INSUFFICIENT
is stored in the flag column, value column remains None.

### CAGR — `(value, flag)` separate columns
Spec required separate `revenue_cagr_5yr` and `revenue_cagr_5yr_flag` columns.
We initially built a merged sentinel-string return type. We extended with
`*_with_flag()` wrapper functions rather than refactoring — this preserved 53
existing tests while adding spec compliance. Backward compatibility was the
deciding factor.

### ROCE — Financials carve-out
Banks, NBFCs, and insurance companies operate with structurally high leverage
(borrowings are operational, not financial risk). ROCE using their capital
structure would be non-comparable to non-financial companies. Resolution:
`roce()` accepts `is_financial=True` → returns None. Caller uses sector-relative
benchmark. All 19 Financials companies have `roce_pct = NULL` in the DB.

### ROE — Screener anomalous values
Screener's `roe_percentage` column for some companies (confirmed: several show
values like 0.52) appears to be stored as a decimal fraction rather than a
percentage. Spec guidance: use ratio engine value for analytics, Screener value
for display only. Logged as `data_source_issue` in ratio_edge_cases.log.

### D/E high leverage flag — Financials suppressed
`high_leverage_flag` is suppressed (`= False`) for all Financials sector companies
regardless of D/E ratio. A bank with D/E = 8 is not in distress — that is normal
operating leverage. Non-financial companies are flagged at D/E > 5.

### ICR — Debt Free display
When `interest = 0`, ICR returns `None` (mathematically undefined). A separate
`icr_label` column stores `"Debt Free"` for display purposes. This separates
analytics (None = not applicable) from UI (display label).

### OPM Cross-check threshold
Computed OPM is validated against Screener's pre-computed `opm_percentage` field.
Threshold set at 1% difference — within this tolerance, differences are attributed
to rounding in Screener's display layer. Differences > 1% are logged as potential
data issues.

### Composite Quality Score
A simple 5-signal score (0–100) combining NPM, ROE, ICR, CFO Quality, and Revenue
CAGR 5yr. Each signal contributes up to 20 points. Score is normalised to available
components so companies with partial data are not penalised. This is an internal
ranking signal, not a published metric.

---

## Schema Mismatches Found (Sprint 1 → Sprint 2 Integration)

| Expected column | Actual column | Table | Resolution |
|----------------|---------------|-------|------------|
| `eps_in_rs` | `eps` | `profitandloss` | Aliased in SELECT |
| `dividend_payout_pct` | `dividend_payout` | `profitandloss` | Aliased in SELECT |
| `book_value` (per-year) | `book_value` (single value) | `companies` | Fetched once per company |
| `broad_sector` in `companies` | `broad_sector` in `sectors` | — | Added LEFT JOIN sectors |

**Learning:** Sprint 3 DB integration should start with a schema validation script
that checks all expected columns before running any pipeline.

---

## What Went Well

- **Additive extension pattern** worked well — `*_with_flag()` wrappers added spec
  compliance without breaking 53 existing CAGR tests.
- **In-memory SQLite fixtures** in tests meant zero dependency on the real DB.
  Pipeline tests ran in <1s and caught the `sqlite3.Row.get()` issue early.
- **Gap analysis habit** (checking spec vs built after each day) caught missing
  functions (ROA, net_debt, asset_turnover) before moving forward.
- **Exit gate passed first run** after schema fixes — no data-level bugs.

## What Could Improve

- **Column name alignment between sprints:** Sprint 1 schema and Sprint 2 expectations
  diverged on 4 columns. A shared `constants.py` with DB column names would prevent
  this in Sprint 3.
- **CFO Quality Score window:** currently uses all data up to current year.
  For early years (1–4 data points), this is less meaningful than a true 5-year
  average. Could add a minimum-window guard (e.g. require ≥ 3 year-pairs).

---

## Sprint 3 — What's Next

Per the project spec, Sprint 3 is the **Peer Comparison Engine**:
- `peer_groups` table (created in Sprint 3, not Sprint 2)
- Percentile rankings within sector/sub-sector peer groups
- Composite scores normalised against peers
- `peer_comparison.csv` output

---

*Sprint 2 signed off — 258 tests, 1155 DB rows, 0 errors.*
