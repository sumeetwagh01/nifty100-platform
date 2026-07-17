-- ============================================================================
-- Nifty 100 Financial Intelligence Platform — SQLite Schema
-- db/schema.sql (Module 1, Feature 1.6, Sprint 1 Day 4)
--
-- 10 tables, built from the 7 core source files + 3 of the 5 supplementary
-- files (sectors, stock_prices, market_cap). financial_ratios and
-- peer_groups are intentionally NOT created here — financial_ratios is
-- built fresh by the Ratio Engine in Sprint 2, and peer-related tables are
-- built by the Peer Comparison Engine in Sprint 3 (Section 19 lists exactly
-- these 10 table names as nifty100.db's contents).
--
-- All composite primary keys follow the (company_id, year) convention used
-- throughout the project document's Dataset Catalogue (Section 5). Year
-- columns store the Day 2 normalize_year() output format 'YYYY-MM', except
-- in `documents`, where the source column is a plain calendar year (int).
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. companies — Master Company Reference (Section 5.1)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    id                  TEXT PRIMARY KEY,      -- NSE ticker, normalised (Day 2)
    company_name        TEXT NOT NULL,
    company_logo        TEXT,
    chart_link          TEXT,
    about_company       TEXT,
    website             TEXT,
    nse_profile         TEXT,
    bse_profile         TEXT,
    face_value          REAL,
    book_value          REAL,
    roce_percentage     REAL,
    roe_percentage      REAL
);

-- ----------------------------------------------------------------------------
-- 2. profitandloss — Annual Profit & Loss Statements (Section 5.2)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profitandloss (
    company_id          TEXT NOT NULL,
    year                TEXT NOT NULL,         -- 'YYYY-MM', via normalize_year()
    source_row_id       INTEGER,               -- original 'id' column — not analytically meaningful
    sales               REAL,
    expenses            REAL,
    operating_profit    REAL,
    opm_percentage      REAL,
    other_income        REAL,
    interest            REAL,
    depreciation        REAL,
    profit_before_tax   REAL,
    tax_percentage      REAL,
    net_profit          REAL,
    eps                 REAL,
    dividend_payout     REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- 3. balancesheet — Annual Balance Sheet (Section 5.3)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS balancesheet (
    company_id          TEXT NOT NULL,
    year                TEXT NOT NULL,
    source_row_id       INTEGER,
    equity_capital       REAL,
    reserves             REAL,
    borrowings           REAL,
    other_liabilities    REAL,
    total_liabilities    REAL,
    fixed_assets         REAL,
    cwip                 REAL,
    investments          REAL,
    other_asset          REAL,
    total_assets          REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- 4. cashflow — Annual Cash Flow Statements (Section 5.4)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cashflow (
    company_id          TEXT NOT NULL,
    year                TEXT NOT NULL,
    source_row_id       INTEGER,
    operating_activity   REAL,
    investing_activity   REAL,
    financing_activity   REAL,
    net_cash_flow        REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- 5. analysis — Pre-Computed Growth Metrics, partial coverage (Section 5.5)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis (
    company_id                 TEXT PRIMARY KEY,
    source_row_id               INTEGER,
    compounded_sales_growth     TEXT,           -- raw text, e.g. '10 Years: 21%'
    compounded_profit_growth    TEXT,
    stock_price_cagr            TEXT,
    roe                          TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- 6. documents — Annual Report Repository (Section 5.6)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    company_id          TEXT NOT NULL,
    year                INTEGER NOT NULL,      -- calendar year, NOT a FY label
    source_row_id       INTEGER,
    annual_report_url   TEXT,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- 7. prosandcons — Qualitative Investment Insights (Section 5.7)
-- Multiple rows per company allowed, so PK is a surrogate id, not a
-- composite key (Section 5: "Primary Key id (auto)").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prosandcons (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          TEXT NOT NULL,
    pros                TEXT,
    cons                TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- 8. sectors — Company Sector Mapping (Section 6.1)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sectors (
    company_id              TEXT PRIMARY KEY,
    broad_sector            TEXT NOT NULL,
    sub_sector               TEXT,
    index_weight_pct         REAL,
    market_cap_category      TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- 9. stock_prices — Monthly OHLCV Price History, simulated (Section 6.2)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_prices (
    company_id          TEXT NOT NULL,
    date                TEXT NOT NULL,         -- 'YYYY-MM-DD', first of month
    open_price          REAL,
    high_price          REAL,
    low_price            REAL,
    close_price          REAL,
    volume               INTEGER,
    adjusted_close        REAL,
    PRIMARY KEY (company_id, date),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- 10. market_cap — Annual Valuation Multiples, simulated (Section 6.3)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_cap (
    company_id              TEXT NOT NULL,
    year                     INTEGER NOT NULL,  -- calendar year, 2019-2024
    market_cap_crore         REAL,
    enterprise_value_crore   REAL,
    pe_ratio                  REAL,
    pb_ratio                  REAL,
    ev_ebitda                 REAL,
    dividend_yield_pct        REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- ----------------------------------------------------------------------------
-- Indexes — speed up the most common lookup pattern (filter/join by
-- company_id) across every time-series table. The composite primary keys
-- above already cover (company_id, year)/(company_id, date) lookups; these
-- extra indexes help company_id-only queries (e.g. "all years for TCS").
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_profitandloss_company ON profitandloss(company_id);
CREATE INDEX IF NOT EXISTS idx_balancesheet_company ON balancesheet(company_id);
CREATE INDEX IF NOT EXISTS idx_cashflow_company ON cashflow(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_id);
CREATE INDEX IF NOT EXISTS idx_prosandcons_company ON prosandcons(company_id);
CREATE INDEX IF NOT EXISTS idx_stock_prices_company ON stock_prices(company_id);
CREATE INDEX IF NOT EXISTS idx_market_cap_company ON market_cap(company_id);
