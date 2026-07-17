-- db/schema_peer.sql
-- Sprint 3 Day 18 — peer_percentiles table
-- Safe to re-run: DROP IF EXISTS before CREATE

DROP TABLE IF EXISTS peer_percentiles;

CREATE TABLE peer_percentiles (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id        INTEGER NOT NULL,
    peer_group_name   TEXT    NOT NULL,
    metric            TEXT    NOT NULL,
    value             REAL,
    percentile_rank   REAL,
    year              INTEGER NOT NULL,

    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE (company_id, peer_group_name, metric, year)
);

CREATE INDEX IF NOT EXISTS idx_pp_group_metric
    ON peer_percentiles (peer_group_name, metric, year);

CREATE INDEX IF NOT EXISTS idx_pp_company
    ON peer_percentiles (company_id, year);
