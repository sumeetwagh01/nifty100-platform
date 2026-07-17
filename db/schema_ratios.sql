-- db/schema_ratios.sql
-- Sprint 2 Day 12 — financial_ratios table
-- Run AFTER the main schema.sql (which creates companies, profitandloss, etc.)
-- Safe to re-run: DROP IF EXISTS before CREATE

DROP TABLE IF EXISTS financial_ratios;

CREATE TABLE financial_ratios (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id                  INTEGER NOT NULL,
    year                        INTEGER NOT NULL,

    -- Profitability
    net_profit_margin_pct       REAL,
    operating_profit_margin_pct REAL,
    return_on_equity_pct        REAL,
    return_on_assets_pct        REAL,
    roce_pct                    REAL,

    -- Leverage & Efficiency
    debt_to_equity              REAL,
    interest_coverage           REAL,
    icr_label                   TEXT,
    icr_warning_flag            INTEGER,        -- 0/1 boolean
    high_leverage_flag          INTEGER,        -- 0/1 boolean
    asset_turnover              REAL,
    net_debt_cr                 REAL,

    -- Cash Flow KPIs
    free_cash_flow_cr           REAL,
    capex_cr                    REAL,
    capex_intensity_pct         REAL,
    capex_intensity_label       TEXT,
    fcf_conversion_pct          REAL,
    cash_from_operations_cr     REAL,
    cfo_quality_score           TEXT,

    -- Capital Allocation
    capital_allocation_pattern  TEXT,

    -- CAGR — Revenue
    revenue_cagr_3yr            REAL,
    revenue_cagr_3yr_flag       TEXT,
    revenue_cagr_5yr            REAL,
    revenue_cagr_5yr_flag       TEXT,
    revenue_cagr_10yr           REAL,
    revenue_cagr_10yr_flag      TEXT,

    -- CAGR — PAT
    pat_cagr_3yr                REAL,
    pat_cagr_3yr_flag           TEXT,
    pat_cagr_5yr                REAL,
    pat_cagr_5yr_flag           TEXT,
    pat_cagr_10yr               REAL,
    pat_cagr_10yr_flag          TEXT,

    -- CAGR — EPS
    eps_cagr_3yr                REAL,
    eps_cagr_3yr_flag           TEXT,
    eps_cagr_5yr                REAL,
    eps_cagr_5yr_flag           TEXT,
    eps_cagr_10yr               REAL,
    eps_cagr_10yr_flag          TEXT,

    -- Pass-through fields from source tables (spec required columns)
    earnings_per_share          REAL,
    book_value_per_share        REAL,
    dividend_payout_ratio_pct   REAL,
    total_debt_cr               REAL,

    -- Composite
    composite_quality_score     REAL,

    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE (company_id, year)
);

CREATE INDEX IF NOT EXISTS idx_fr_company_year
    ON financial_ratios (company_id, year);
