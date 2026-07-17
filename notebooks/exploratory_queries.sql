-- ============================================================================
-- exploratory_queries.sql
-- Sprint 1 Day 07 — 10 exploratory SQL queries for manual DQ review
-- Run against: data/nifty100.db
-- How to run one query: python -c "import sqlite3; ..."
-- Or open nifty100.db in DB Browser for SQLite and paste each block.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Q01: Row counts for all 10 tables (Sprint 1 exit gate: companies=92)
-- ----------------------------------------------------------------------------
SELECT 'companies'    AS tbl, COUNT(*) AS rows FROM companies
UNION ALL SELECT 'profitandloss',  COUNT(*) FROM profitandloss
UNION ALL SELECT 'balancesheet',   COUNT(*) FROM balancesheet
UNION ALL SELECT 'cashflow',       COUNT(*) FROM cashflow
UNION ALL SELECT 'analysis',       COUNT(*) FROM analysis
UNION ALL SELECT 'documents',      COUNT(*) FROM documents
UNION ALL SELECT 'prosandcons',    COUNT(*) FROM prosandcons
UNION ALL SELECT 'sectors',        COUNT(*) FROM sectors
UNION ALL SELECT 'stock_prices',   COUNT(*) FROM stock_prices
UNION ALL SELECT 'market_cap',     COUNT(*) FROM market_cap;

-- ----------------------------------------------------------------------------
-- Q02: Year coverage per company in P&L
-- Shows min year, max year, and number of distinct years for every company.
-- DQ-16 flag: companies with fewer than 5 years of history.
-- ----------------------------------------------------------------------------
SELECT
    p.company_id,
    c.company_name,
    COUNT(DISTINCT p.year)  AS year_count,
    MIN(p.year)             AS earliest_year,
    MAX(p.year)             AS latest_year
FROM profitandloss p
JOIN companies c ON p.company_id = c.id
GROUP BY p.company_id
ORDER BY year_count ASC, p.company_id;

-- ----------------------------------------------------------------------------
-- Q03: Companies with fewer than 5 years of P&L history (DQ-16 candidates)
-- ----------------------------------------------------------------------------
SELECT
    p.company_id,
    c.company_name,
    COUNT(DISTINCT p.year) AS year_count
FROM profitandloss p
JOIN companies c ON p.company_id = c.id
GROUP BY p.company_id
HAVING COUNT(DISTINCT p.year) < 5
ORDER BY year_count ASC;

-- ----------------------------------------------------------------------------
-- Q04: NULL counts for key financial columns in P&L
-- Helps identify data gaps that could affect KPI computation in Sprint 2.
-- ----------------------------------------------------------------------------
SELECT
    'sales'             AS col, SUM(CASE WHEN sales IS NULL THEN 1 ELSE 0 END)             AS nulls FROM profitandloss
UNION ALL
SELECT 'net_profit',            SUM(CASE WHEN net_profit IS NULL THEN 1 ELSE 0 END)            FROM profitandloss
UNION ALL
SELECT 'operating_profit',      SUM(CASE WHEN operating_profit IS NULL THEN 1 ELSE 0 END)      FROM profitandloss
UNION ALL
SELECT 'eps',                   SUM(CASE WHEN eps IS NULL THEN 1 ELSE 0 END)                   FROM profitandloss
UNION ALL
SELECT 'tax_percentage',        SUM(CASE WHEN tax_percentage IS NULL THEN 1 ELSE 0 END)        FROM profitandloss
UNION ALL
SELECT 'borrowings (BS)',       SUM(CASE WHEN borrowings IS NULL THEN 1 ELSE 0 END)            FROM balancesheet
UNION ALL
SELECT 'total_assets (BS)',     SUM(CASE WHEN total_assets IS NULL THEN 1 ELSE 0 END)          FROM balancesheet
UNION ALL
SELECT 'operating_activity(CF)',SUM(CASE WHEN operating_activity IS NULL THEN 1 ELSE 0 END)    FROM cashflow;

-- ----------------------------------------------------------------------------
-- Q05: 5 random companies — spot-check P&L latest year data
-- Manual verification: pick 5 and cross-check against Screener.in or BSE.
-- ----------------------------------------------------------------------------
SELECT
    p.company_id,
    p.year,
    p.sales,
    p.operating_profit,
    ROUND(p.opm_percentage, 2)  AS opm_pct,
    p.net_profit,
    p.eps
FROM profitandloss p
WHERE p.year = (SELECT MAX(year) FROM profitandloss WHERE company_id = p.company_id)
ORDER BY RANDOM()
LIMIT 5;

-- ----------------------------------------------------------------------------
-- Q06: Balance sheet sanity — total_assets vs total_liabilities gap
-- DQ-04: flag where the difference exceeds 1% of total_assets.
-- ----------------------------------------------------------------------------
SELECT
    company_id,
    year,
    total_assets,
    total_liabilities,
    ROUND(ABS(total_assets - total_liabilities) / total_assets * 100, 2) AS diff_pct
FROM balancesheet
WHERE total_assets > 0
  AND ABS(total_assets - total_liabilities) / total_assets >= 0.01
ORDER BY diff_pct DESC
LIMIT 20;

-- ----------------------------------------------------------------------------
-- Q07: Cash flow net check — does CFO + CFI + CFF = net_cash_flow?
-- DQ-09: flag where the gap > 10 Cr.
-- ----------------------------------------------------------------------------
SELECT
    company_id,
    year,
    operating_activity,
    investing_activity,
    financing_activity,
    net_cash_flow,
    ROUND(ABS(net_cash_flow -
        (operating_activity + investing_activity + financing_activity)), 1) AS gap_cr
FROM cashflow
WHERE operating_activity IS NOT NULL
  AND investing_activity IS NOT NULL
  AND financing_activity IS NOT NULL
  AND net_cash_flow IS NOT NULL
  AND ABS(net_cash_flow -
        (operating_activity + investing_activity + financing_activity)) > 10
ORDER BY gap_cr DESC
LIMIT 20;

-- ----------------------------------------------------------------------------
-- Q08: Sector distribution — how many companies per broad sector?
-- Verifies the 11-sector mapping is complete and covers all 92 companies.
-- ----------------------------------------------------------------------------
SELECT
    s.broad_sector,
    COUNT(*)            AS company_count,
    GROUP_CONCAT(s.company_id, ', ') AS tickers
FROM sectors s
GROUP BY s.broad_sector
ORDER BY company_count DESC;

-- ----------------------------------------------------------------------------
-- Q09: Documents coverage — annual report links per company
-- Identifies companies with the most missing reports (for Day 6 review).
-- ----------------------------------------------------------------------------
SELECT
    c.id            AS company_id,
    c.company_name,
    COUNT(d.year)   AS reports_available,
    (2024 - 2010 + 1) - COUNT(d.year) AS missing_years
FROM companies c
LEFT JOIN documents d ON c.id = d.company_id
GROUP BY c.id
ORDER BY missing_years DESC
LIMIT 20;

-- ----------------------------------------------------------------------------
-- Q10: Top 10 companies by latest-year sales (sanity check — should be
-- well-known large caps: RELIANCE, TCS, HDFCBANK, etc.)
-- ----------------------------------------------------------------------------
SELECT
    p.company_id,
    c.company_name,
    p.year          AS latest_year,
    p.sales         AS sales_cr,
    p.net_profit    AS net_profit_cr,
    ROUND(p.opm_percentage, 1) AS opm_pct
FROM profitandloss p
JOIN companies c ON p.company_id = c.id
WHERE p.year = (SELECT MAX(year) FROM profitandloss WHERE company_id = p.company_id)
ORDER BY p.sales DESC
LIMIT 10;
