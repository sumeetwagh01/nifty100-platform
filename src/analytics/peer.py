"""
src/analytics/peer.py
=====================
Sprint 3 Day 18 — Peer Percentile Rankings.

Computes PERCENT_RANK for 10 metrics within each of 11 peer groups
and writes results to the peer_percentiles SQLite table.

Peer Groups (11)
----------------
Derived from sectors.broad_sector + sectors.sub_sector:
  1.  Financials — Banking
  2.  Financials — NBFC
  3.  Financials — Insurance
  4.  Technology — IT Services
  5.  Consumer — FMCG
  6.  Consumer — Retail
  7.  Industrials — Manufacturing
  8.  Industrials — Infrastructure
  9.  Energy
  10. Healthcare
  11. Materials

Companies not matching any peer group → logged as "No peer group assigned"

Metrics ranked (10)
-------------------
  ROE              higher is better
  ROCE             higher is better
  Net Profit Margin higher is better
  D/E              lower is better  → percentile inverted (1 - PERCENT_RANK)
  FCF              higher is better
  PAT CAGR 5yr     higher is better
  Revenue CAGR 5yr higher is better
  EPS CAGR 5yr     higher is better
  Interest Coverage higher is better
  Asset Turnover   higher is better

PERCENT_RANK formula
--------------------
  rank = (number of values strictly less than current) / (total - 1)
  Result is 0.0–1.0, stored as percentage 0–100 in DB.
  For D/E: stored percentile = (1 - rank) * 100
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent.parent.parent / "db" / "schema_peer.sql"

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

PEER_METRICS = {
    "return_on_equity_pct":      {"label": "ROE",              "invert": False},
    "roce_pct":                  {"label": "ROCE",             "invert": False},
    "net_profit_margin_pct":     {"label": "Net Profit Margin","invert": False},
    "debt_to_equity":            {"label": "D/E",              "invert": True},
    "free_cash_flow_cr":         {"label": "FCF",              "invert": False},
    "pat_cagr_5yr":              {"label": "PAT CAGR 5yr",     "invert": False},
    "revenue_cagr_5yr":          {"label": "Revenue CAGR 5yr", "invert": False},
    "eps_cagr_5yr":              {"label": "EPS CAGR 5yr",     "invert": False},
    "interest_coverage":         {"label": "Interest Coverage","invert": False},
    "asset_turnover":            {"label": "Asset Turnover",   "invert": False},
}

NO_PEER_GROUP = "No peer group assigned"

# ---------------------------------------------------------------------------
# Peer group assignment
# ---------------------------------------------------------------------------

def assign_peer_group(broad_sector: str | None, sub_sector: str | None) -> str:
    """
    Map broad_sector + sub_sector to one of 11 peer group names.

    Returns NO_PEER_GROUP if no match found.

    >>> assign_peer_group("Financials", "Banking")
    'Financials — Banking'
    >>> assign_peer_group("Technology", "IT Services")
    'Technology — IT Services'
    >>> assign_peer_group("Unknown", "Unknown")
    'No peer group assigned'
    """
    bs = (broad_sector or "").strip().lower()
    ss = (sub_sector  or "").strip().lower()

    # Financials sub-groups
    if bs == "financials":
        if any(k in ss for k in ["bank", "banking"]):
            return "Financials — Banking"
        if any(k in ss for k in ["nbfc", "finance", "financial services"]):
            return "Financials — NBFC"
        if "insurance" in ss:
            return "Financials — Insurance"
        return "Financials — NBFC"   # default for unclassified financials

    # Technology
    if bs == "technology":
        return "Technology — IT Services"

    # Consumer
    if bs in ("consumer", "consumer goods", "consumer staples", "consumer discretionary"):
        if any(k in ss for k in ["fmcg", "food", "beverage", "household"]):
            return "Consumer — FMCG"
        if "retail" in ss:
            return "Consumer — Retail"
        return "Consumer — FMCG"   # default

    # Industrials
    if bs == "industrials":
        if any(k in ss for k in ["infra", "infrastructure", "construction", "cement"]):
            return "Industrials — Infrastructure"
        return "Industrials — Manufacturing"

    # Energy
    if bs in ("energy", "oil", "gas", "power", "utilities"):
        return "Energy"

    # Healthcare
    if bs in ("healthcare", "pharma", "pharmaceuticals", "health care"):
        return "Healthcare"

    # Materials
    if bs in ("materials", "metals", "mining", "chemicals"):
        return "Materials"

    return NO_PEER_GROUP


# ---------------------------------------------------------------------------
# PERCENT_RANK computation
# ---------------------------------------------------------------------------

def percent_rank(series: pd.Series, invert: bool = False) -> pd.Series:
    """
    Compute PERCENT_RANK for each value in series (0–100 scale).

    rank_i = count(values < value_i) / (n - 1) * 100

    NaN values receive NaN rank (not ranked).
    If only one non-null value, rank = 50.0 (neutral).

    Parameters
    ----------
    invert : if True, return (100 - rank) so lower values score higher

    >>> import pandas as pd
    >>> s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    >>> percent_rank(s).tolist()
    [0.0, 25.0, 50.0, 75.0, 100.0]
    >>> percent_rank(s, invert=True).tolist()
    [100.0, 75.0, 50.0, 25.0, 0.0]
    """
    valid = series.dropna()
    n = len(valid)

    if n == 0:
        return pd.Series(float("nan"), index=series.index)
    if n == 1:
        result = pd.Series(float("nan"), index=series.index)
        result[valid.index] = 50.0
        return result

    ranks = pd.Series(float("nan"), index=series.index)
    for idx, val in valid.items():
        count_less = (valid < val).sum()
        ranks[idx] = (count_less / (n - 1)) * 100.0

    if invert:
        ranks = 100.0 - ranks

    return ranks.round(2)


# ---------------------------------------------------------------------------
# Main peer engine
# ---------------------------------------------------------------------------

class PeerEngine:
    """
    Compute peer percentile rankings for all companies.

    Parameters
    ----------
    conn : sqlite3.Connection to nifty100.db
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def apply_schema(self) -> None:
        """Create peer_percentiles table from schema_peer.sql."""
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        self.conn.executescript(sql)
        self.conn.commit()
        log.info("peer_percentiles table ready")

    def load_data(self, year: int | None = None) -> pd.DataFrame:
        """
        Load financial_ratios joined with sector data.

        Parameters
        ----------
        year : specific year to load; if None uses latest year per company
        """
        if year is not None:
            year_filter = f"AND fr.year = {year}"
        else:
            year_filter = """AND fr.year = (
                SELECT MAX(year) FROM financial_ratios
                WHERE company_id = fr.company_id
            )"""

        query = f"""
            SELECT
                fr.company_id,
                fr.year,
                c.company_name,
                COALESCE(s.broad_sector, '') AS broad_sector,
                COALESCE(s.sub_sector, '')   AS sub_sector,
                fr.return_on_equity_pct,
                fr.roce_pct,
                fr.net_profit_margin_pct,
                fr.debt_to_equity,
                fr.free_cash_flow_cr,
                fr.pat_cagr_5yr,
                fr.revenue_cagr_5yr,
                fr.eps_cagr_5yr,
                fr.interest_coverage,
                fr.asset_turnover
            FROM financial_ratios fr
            JOIN companies c ON c.id = fr.company_id
            LEFT JOIN sectors s ON s.company_id = fr.company_id
            WHERE 1=1 {year_filter}
        """
        df = pd.read_sql_query(query, self.conn)

        # Assign peer groups
        df["peer_group_name"] = df.apply(
            lambda r: assign_peer_group(r["broad_sector"], r["sub_sector"]),
            axis=1,
        )

        no_peer = df[df["peer_group_name"] == NO_PEER_GROUP]
        if not no_peer.empty:
            for _, row in no_peer.iterrows():
                log.warning(
                    f"No peer group assigned: company_id={row['company_id']} "
                    f"({row['company_name']}) broad_sector='{row['broad_sector']}' "
                    f"sub_sector='{row['sub_sector']}'"
                )

        return df

    def compute_percentiles(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute PERCENT_RANK for each metric within each peer group.

        Returns long-format DataFrame with columns:
            company_id, peer_group_name, metric, value, percentile_rank, year
        """
        records = []

        for group_name, grp in df.groupby("peer_group_name"):
            if group_name == NO_PEER_GROUP:
                continue

            for col, meta in PEER_METRICS.items():
                if col not in grp.columns:
                    continue

                values  = pd.to_numeric(grp[col], errors="coerce")
                ranks   = percent_rank(values, invert=meta["invert"])

                for idx in grp.index:
                    records.append({
                        "company_id":      int(grp.loc[idx, "company_id"]),
                        "peer_group_name": group_name,
                        "metric":          meta["label"],
                        "value":           values[idx] if pd.notna(values[idx]) else None,
                        "percentile_rank": ranks[idx]  if pd.notna(ranks[idx])  else None,
                        "year":            int(grp.loc[idx, "year"]),
                    })

        return pd.DataFrame(records)

    def insert_percentiles(self, df: pd.DataFrame) -> int:
        """INSERT OR REPLACE into peer_percentiles. Returns row count."""
        if df.empty:
            return 0

        sql = """
            INSERT OR REPLACE INTO peer_percentiles
                (company_id, peer_group_name, metric, value, percentile_rank, year)
            VALUES
                (:company_id, :peer_group_name, :metric, :value, :percentile_rank, :year)
        """
        self.conn.executemany(sql, df.to_dict("records"))
        self.conn.commit()
        return len(df)

    def run(self, year: int | None = None) -> dict:
        """
        Full pipeline: schema → load → percentiles → insert.

        Returns summary dict.
        """
        self.apply_schema()
        df = self.load_data(year=year)

        peer_groups = df[df["peer_group_name"] != NO_PEER_GROUP]["peer_group_name"].nunique()
        no_peer_count = (df["peer_group_name"] == NO_PEER_GROUP).sum()

        percentile_df = self.compute_percentiles(df)
        inserted = self.insert_percentiles(percentile_df)

        summary = {
            "companies_loaded":    len(df),
            "peer_groups_found":   peer_groups,
            "no_peer_assigned":    no_peer_count,
            "rows_inserted":       inserted,
        }
        log.info(f"Peer engine complete: {summary}")
        return summary
