# Sprint 1 Retrospective — Data Foundation
**Sprint:** 1 · Days 01–07  
**Theme:** Data Engineering & ETL Pipeline  
**Date:** June 2026  

---

## Sprint Goal
> Build a fully loaded and validated SQLite database (`nifty100.db`) containing
> all 10 tables from 12 source files. All 16 data quality rules must have been
> run and any CRITICAL failures resolved.

## Exit Criteria — Status

| Gate | Criterion | Result |
|---|---|---|
| AC-01 | `SELECT COUNT(*) FROM companies` = 92 | ✅ 92 |
| AC-02 | ≥ 90% of companies have ≥ 10 years P&L/BS/CF | ✅ Verified Day 06 |
| AC-03 | `PRAGMA foreign_key_check` = 0 rows | ✅ 0 violations |
| AC-19 | `validation_failures.csv` exists with correct columns | ✅ Generated Day 03 |
| DQ rules | All 16 DQ rules implemented and tested | ✅ 35 tests passing |
| ETL tests | ≥ 35 ETL unit tests passing | ✅ 105 total tests |

---

## Deliverables Completed

| # | Deliverable | Status | Notes |
|---|---|---|---|
| D-01 | `nifty100.db` — 10 tables populated | ✅ | companies=92, P&L=1070, BS=1140, CF=1056 |
| D-02 | `load_audit.csv` | ✅ | Per-table row counts and rejections |
| D-03 | `validation_failures.csv` | ✅ | 1083 violations logged with severity |
| D-04 | `exploratory_queries.sql` | ✅ | 10 queries in notebooks/ |
| — | `src/etl/loader.py` | ✅ | header=1 for core, header=0 for supplementary |
| — | `src/etl/normaliser.py` | ✅ | normalize_year(), normalize_ticker() |
| — | `src/etl/validator.py` | ✅ | 16 DQ rules, run_all_dq_rules() |
| — | `src/etl/full_load.py` | ✅ | Full 12-file pipeline with --reset flag |
| — | `db/schema.sql` | ✅ | 10 tables, FK constraints, PRAGMA foreign_keys = ON |
| — | `db/loader.py` | ✅ | Per-table insert functions, parameterised queries |

---

## What Went Well
- Real data loaded cleanly first time for 7 of 10 tables
- Day 3 validator correctly identified all expected real-world data issues
  (TTM rows, scrape duplicates, 9 orphan companies) before they reached the DB
- Normalisation-before-FK-check pattern (discovered via real data) is now
  guarded by a dedicated regression test
- 105 unit tests covering ETL, DQ rules, and DB schema constraints

## Issues Found & Resolved

| Issue | Root Cause | Fix |
|---|---|---|
| `cp` not found on Windows | CMD uses `copy` not `cp` | Switched all instructions to Windows CMD syntax |
| `test_loader.py` not found | File missing from zip extraction | Delivered individually |
| 732 false CRITICAL violations (DQ-02/03) | Normalisation applied after FK check | Fixed order: normalise → then check |
| `face_value NOT NULL` constraint failure | Real data has blank face_value cells | Relaxed to nullable (spec: Nullable=Yes) |
| `opm_percentage NOT NULL` failure | Real data has blank OPM cells | Relaxed all financial numerics to nullable |
| `pytest` couldn't find `db.loader` | `db/__init__.py` conflicted with `pythonpath=.` | Removed `db/__init__.py` |

## Real Data Findings (Expected, Not Bugs)

| Finding | Count | Action |
|---|---|---|
| TTM / stub-period rows | 108 | Correctly rejected by DQ-07 |
| Scrape-induced duplicates | 232 | Correctly deduplicated by DQ-02 (keep last) |
| Orphan companies (not in master list) | 401 rows / 9 companies | Correctly rejected by DQ-03 |
| OPM cross-check mismatches | 216 | WARNING — logged, source field kept |
| BS balance mismatches > 1% | 1 | WARNING — analyst review |

---

## Sprint 2 Preview — Ratio Engine (Days 08–14)
- `src/analytics/ratios.py` — NPM, OPM, ROE, ROCE
- `src/analytics/cagr.py` — Revenue/PAT/EPS CAGR with turnaround flag
- `src/analytics/cashflow_kpis.py` — FCF, CFO Quality, CapEx Intensity
- Populate `financial_ratios` table: 14 KPI columns × ~1,100 company-year rows
- Cross-validate computed OPM vs `opm_percentage` source field (DQ-05 follow-up)
- All 20 KPI formula tests must pass before Day 14

---
*Sprint 1 signed off — Day 07*
