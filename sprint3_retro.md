# Sprint 3 Retrospective
## Nifty 100 Financial Intelligence Platform
**Sprint:** 3 — Screener + Peer Engine
**Days:** 15–21 | **Story Points:** 49 SP | **Epics:** 03 & 04

---

## Sprint Goal — Achieved ✅

> By end of Sprint 3, the financial screener must be fully functional with
> 6 preset filters and custom threshold support. Peer percentile rankings
> must be computed for all 11 peer groups across 10 metrics.
> screener_output.xlsx and peer_comparison.xlsx must be generated and reviewed.
> All data quality unit tests must pass.

**Actual outcome:** 443 tests passing, screener engine with 15 filterable
metrics, 6 presets, composite scorer, peer percentile rankings across 11
groups, radar charts, and two Excel outputs fully generated.

---

## Exit Gate Results

| Gate | Target | Actual | Status |
|------|--------|--------|--------|
| Total tests passing | all | 443 | ✅ |
| DQ rule tests | 14 passing | 14 | ✅ |
| Screener metrics supported | 15 | 15 | ✅ |
| Preset screeners | 6 | 6 | ✅ |
| Peer groups | 11 | 11 | ✅ |
| Metrics ranked per group | 10 | 10 | ✅ |
| `screener_output.xlsx` generated | ✅ | ✅ | ✅ |
| `peer_comparison.xlsx` generated | ✅ | ✅ | ✅ |
| Radar charts generated | per company | per company | ✅ |
| Quality Compounder — ROE>15 D/E<1 | verified | verified | ✅ |
| IT Services — highest ROE = highest rank | verified | verified | ✅ |

---

## Daily Delivery Summary

| Day | Deliverable | Tests | Notes |
|-----|------------|-------|-------|
| 15 | `screener/engine.py` + `screener_config.yaml` | 25 | 15 metrics, D/E sector skip, ICR Debt Free rule |
| 16 | `screener/presets.py` — 6 named presets | 38 | Custom filter + D/E declining YoY for Turnaround Watch |
| 17 | `scorer.py` + `exporter.py` | 29 | P10/P90 winsorisation, sector-relative score, colour-coded Excel |
| 18 | `peer.py` + `schema_peer.sql` | 36 | 11 peer groups, PERCENT_RANK, D/E inverted |
| 19 | `radar.py` — polar charts | 12 | 8-axis radar + standalone bar for no-peer companies |
| 20 | `peer_comparison.py` | 12 | 11 sheets, green/yellow/red ranks, gold benchmark, median row |
| 21 | `test_integration.py` + retro | 33 | 14 DQ rules + preset + peer ranking verifications |

---

## Key Design Decisions

### Composite Score — weighted components
Spec required a 0–100 composite score. Implemented as 4 weighted buckets:
Profitability 35%, Cash Quality 30%, Growth 20%, Leverage 15%.
P10/P90 winsorisation applied per component before scaling ensures extreme
outliers (e.g. Nestle ROE=90%) don't compress the rest of the universe.

### Sector-relative score — within-group normalisation
Added alongside the absolute composite score. Normalises each company's score
relative to its `broad_sector` peers so a bank's composite score is compared
to other banks, not to IT companies. Stored as `sector_relative_score` column.

### D/E filter — Financials carve-out
Consistent with Sprint 2. `de_max` filter in `screener_config.yaml` has
`sector_skip: [Financials]`. Banks with D/E=8 pass through the D/E filter
because their leverage is structural, not a risk signal.

### ICR — Debt Free = infinity
Companies with `icr_label = "Debt Free"` always pass any ICR minimum threshold.
This prevents zero-debt companies from being excluded by ICR filters.

### PERCENT_RANK — D/E inverted
D/E is the only metric where lower is better. Implemented via `invert=True`
parameter in `percent_rank()`. Result: company with D/E=0 gets percentile=100,
company with highest D/E gets percentile=0.

### Peer group assignment — heuristic mapping
11 peer groups mapped from `broad_sector` + `sub_sector` combinations.
Unmatched companies assigned "No peer group assigned" — logged, not raised.
For Financials with unknown sub-sector, default is NBFC (most common).

### Benchmark company — highest composite score
Each peer group's benchmark (gold row) is the company with the highest
`composite_quality_score` in that group. This gives a clear quality anchor
for peer comparison without requiring manual selection.

### Radar charts — percentile ranks on axes
All 8 radar axes use percentile ranks (0–100), not raw values.
This makes axes comparable across metrics with very different scales
(e.g. FCF in crores vs ROE in %).

---

## Schema & Integration Notes

- `peer_percentiles` table added to SQLite — UNIQUE on (company_id, peer_group_name, metric, year)
- Both Excel outputs use `openpyxl` with merged headers, frozen panes, auto-width columns
- `screener_output.xlsx` — green/red based on preset threshold direction
- `peer_comparison.xlsx` — green/yellow/red based on percentile rank bands

---

## What Went Well

- **YAML config for screener** made adding/modifying metrics trivial — no code changes needed
- **Fixture-based testing** throughout — all tests run without touching real DB
- **P10/P90 winsorisation** worked cleanly — prevented outliers from distorting scores
- **Incremental build** — each day's module was independently testable before integration

## What Could Improve

- **Peer group assignment** is heuristic — a lookup table in the DB would be more robust
- **`screener_config.yaml`** doesn't yet support P/E, P/B, Market Cap (market data not in DB)
- **Radar charts** use percentile ranks — consider adding a raw-value mode for analysts

---

## Sprint 4 — What's Next

Per the project spec, Sprint 4 likely covers:
- Dashboard or reporting layer
- Historical trend analysis
- Alerts and watchlist engine

---

*Sprint 3 signed off — 443 tests, 11 peer groups, 6 presets, 2 Excel outputs, radar charts generated.*
