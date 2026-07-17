"""
src/analytics/radar.py
======================
Sprint 3 Day 19 — Radar/Polar Charts for peer group companies.

For each company in a peer group:
  - 8-axis radar chart using percentile ranks from peer_percentiles table
  - Company polygon (filled, blue) + peer group average (dashed, orange)
  - Exported as PNG to reports/radar_charts/<ticker>_radar.png

For companies with no peer group:
  - Single-metric bar chart vs Nifty 100 universe average

Axes (8)
--------
  ROE, ROCE, NPM, D/E (inverted rank), FCF score,
  PAT CAGR 5yr, Revenue CAGR 5yr, Composite Score

All values are percentile ranks (0–100) so axes are comparable.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # non-interactive backend for file export
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

log = logging.getLogger(__name__)

OUTPUT_DIR = Path("reports/radar_charts")

# 8 radar axes — metric label → peer_percentiles.metric value
RADAR_AXES = [
    "ROE",
    "ROCE",
    "Net Profit Margin",
    "D/E",
    "FCF",
    "PAT CAGR 5yr",
    "Revenue CAGR 5yr",
    "Composite Score",
]

# Colours
COMPANY_COLOR  = "#1F77B4"   # blue
PEER_COLOR     = "#FF7F0E"   # orange
GRID_COLOR     = "#CCCCCC"


# ---------------------------------------------------------------------------
# Data loader
# ---------------------------------------------------------------------------

def load_peer_percentiles(
    conn: sqlite3.Connection,
    peer_group_name: str,
    year: int | None = None,
) -> pd.DataFrame:
    """
    Load peer_percentiles for a specific peer group.

    Returns wide-format DataFrame: one row per company, one col per metric.
    """
    year_filter = f"AND year = {year}" if year else ""
    rows = conn.execute(f"""
        SELECT
            pp.company_id,
            c.company_name,
            pp.metric,
            pp.percentile_rank
        FROM peer_percentiles pp
        JOIN companies c ON c.id = pp.company_id
        WHERE pp.peer_group_name = ?
          {year_filter}
        ORDER BY pp.company_id, pp.metric
    """, (peer_group_name,)).fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["company_id", "company_name", "metric", "percentile_rank"])
    wide = df.pivot_table(
        index=["company_id", "company_name"],
        columns="metric",
        values="percentile_rank",
    ).reset_index()
    wide.columns.name = None
    return wide


def load_composite_scores(
    conn: sqlite3.Connection,
    company_ids: list[int],
    year: int | None = None,
) -> dict[int, float]:
    """Load composite_quality_score from financial_ratios for given companies."""
    year_filter = f"AND year = {year}" if year else ""
    placeholders = ",".join("?" * len(company_ids))
    rows = conn.execute(f"""
        SELECT company_id, composite_quality_score
        FROM financial_ratios
        WHERE company_id IN ({placeholders})
          {year_filter}
        ORDER BY company_id
    """, company_ids).fetchall()
    return {r[0]: r[1] for r in rows}


def load_no_peer_companies(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Load companies with no peer group assigned.
    Returns DataFrame with company_id, company_name, and 8 KPI columns.
    """
    rows = conn.execute("""
        SELECT
            c.id AS company_id,
            c.company_name,
            fr.return_on_equity_pct,
            fr.roce_pct,
            fr.net_profit_margin_pct,
            fr.debt_to_equity,
            fr.free_cash_flow_cr,
            fr.pat_cagr_5yr,
            fr.revenue_cagr_5yr,
            fr.composite_quality_score
        FROM companies c
        JOIN financial_ratios fr ON fr.company_id = c.id
        LEFT JOIN sectors s ON s.company_id = c.id
        WHERE COALESCE(s.broad_sector, 'Unknown') = 'Unknown'
          AND fr.year = (
              SELECT MAX(year) FROM financial_ratios WHERE company_id = c.id
          )
    """).fetchall()
    if not rows:
        return pd.DataFrame()
    cols = ["company_id", "company_name", "roe", "roce", "npm", "de",
            "fcf", "pat_cagr", "rev_cagr", "composite_score"]
    return pd.DataFrame(rows, columns=cols)


def load_universe_averages(conn: sqlite3.Connection) -> dict[str, float]:
    """Load Nifty 100 universe averages for the 8 metrics."""
    row = conn.execute("""
        SELECT
            AVG(return_on_equity_pct),
            AVG(roce_pct),
            AVG(net_profit_margin_pct),
            AVG(debt_to_equity),
            AVG(free_cash_flow_cr),
            AVG(pat_cagr_5yr),
            AVG(revenue_cagr_5yr),
            AVG(composite_quality_score)
        FROM financial_ratios
        WHERE year = (SELECT MAX(year) FROM financial_ratios LIMIT 1)
    """).fetchone()
    keys = ["ROE", "ROCE", "NPM", "D/E", "FCF", "PAT CAGR 5yr", "Rev CAGR 5yr", "Composite Score"]
    return dict(zip(keys, [r or 0.0 for r in row]))


# ---------------------------------------------------------------------------
# Radar chart drawing
# ---------------------------------------------------------------------------

def _radar_plot(
    values: list[float],
    peer_avg: list[float],
    labels: list[str],
    title: str,
    output_path: Path,
) -> None:
    """
    Draw a filled radar/polar chart with peer group average overlay.

    Parameters
    ----------
    values    : company's percentile ranks (0–100) for each axis
    peer_avg  : peer group average percentile ranks for each axis
    labels    : axis labels
    title     : chart title (company name)
    output_path : PNG save path
    """
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    # Close the polygon
    angles += angles[:1]

    vals     = values + values[:1]
    avg_vals = peer_avg + peer_avg[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})

    # Draw grid rings
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=7, color="grey")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9, fontweight="bold")
    ax.grid(color=GRID_COLOR, linewidth=0.8)

    # Company polygon — filled
    ax.fill(angles, vals, color=COMPANY_COLOR, alpha=0.25)
    ax.plot(angles, vals, color=COMPANY_COLOR, linewidth=2, label="Company")

    # Peer average — dashed outline
    ax.plot(angles, avg_vals, color=PEER_COLOR, linewidth=1.5,
            linestyle="--", label="Peer Avg")

    # Legend & title
    ax.set_title(title, size=13, fontweight="bold", pad=20)
    legend = ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.15), fontsize=9)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


def _standalone_bar_chart(
    company_name: str,
    company_values: dict[str, float],
    universe_avg: dict[str, float],
    output_path: Path,
) -> None:
    """
    Bar chart for companies with no peer group.
    Shows company metric values vs Nifty 100 universe average.
    """
    metrics = list(company_values.keys())
    comp_vals = [company_values.get(m, 0) or 0 for m in metrics]
    avg_vals  = [universe_avg.get(m, 0)  or 0 for m in metrics]

    x = np.arange(len(metrics))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width/2, comp_vals, width, label=company_name,
           color=COMPANY_COLOR, alpha=0.8)
    ax.bar(x + width/2, avg_vals,  width, label="Nifty 100 Avg",
           color=PEER_COLOR, alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Value")
    ax.set_title(f"{company_name} — vs Nifty 100 Average", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

class RadarChartGenerator:
    """
    Generate radar charts for all peer group companies.

    Parameters
    ----------
    conn       : sqlite3.Connection
    output_dir : directory for PNG exports (default: reports/radar_charts/)
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        output_dir: Path = OUTPUT_DIR,
    ) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.output_dir = Path(output_dir)

    def _get_peer_groups(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT peer_group_name FROM peer_percentiles ORDER BY peer_group_name"
        ).fetchall()
        return [r[0] for r in rows]

    def _safe_filename(self, name: str) -> str:
        return name.replace(" ", "_").replace("/", "-").replace("—", "-")

    def generate_for_group(
        self,
        peer_group_name: str,
        year: int | None = None,
    ) -> int:
        """
        Generate one radar chart per company in the peer group.
        Returns number of charts generated.
        """
        wide_df = load_peer_percentiles(self.conn, peer_group_name, year)
        if wide_df.empty:
            log.warning(f"No percentile data for peer group: {peer_group_name}")
            return 0

        # Compute peer group average for each axis
        metric_cols = [m for m in RADAR_AXES if m in wide_df.columns]
        if not metric_cols:
            log.warning(f"No matching metric columns for {peer_group_name}")
            return 0

        # Add composite score from financial_ratios
        company_ids = wide_df["company_id"].tolist()
        comp_scores = load_composite_scores(self.conn, company_ids, year)
        if "Composite Score" not in wide_df.columns:
            wide_df["Composite Score"] = wide_df["company_id"].map(comp_scores)

        # Peer averages
        peer_avg = {
            m: wide_df[m].mean() if m in wide_df.columns else 50.0
            for m in RADAR_AXES
        }
        avg_values = [peer_avg.get(m, 50.0) or 50.0 for m in RADAR_AXES]

        charts = 0
        for _, row in wide_df.iterrows():
            company_name = row["company_name"]
            comp_values  = [float(row.get(m) or 50.0) for m in RADAR_AXES]

            safe_name   = self._safe_filename(company_name)
            output_path = self.output_dir / f"{safe_name}_radar.png"

            _radar_plot(
                values      = comp_values,
                peer_avg    = avg_values,
                labels      = RADAR_AXES,
                title       = f"{company_name}\n({peer_group_name})",
                output_path = output_path,
            )
            charts += 1
            log.debug(f"  Chart saved: {output_path}")

        return charts

    def generate_no_peer_charts(self) -> int:
        """
        Generate standalone bar charts for companies with no peer group.
        Returns number of charts generated.
        """
        no_peer_df = load_no_peer_companies(self.conn)
        if no_peer_df.empty:
            log.info("No companies without peer group found")
            return 0

        universe_avg = load_universe_averages(self.conn)

        charts = 0
        for _, row in no_peer_df.iterrows():
            company_name = row["company_name"]
            company_vals = {
                "ROE":          row.get("roe") or 0,
                "ROCE":         row.get("roce") or 0,
                "NPM":          row.get("npm") or 0,
                "D/E":          row.get("de") or 0,
                "FCF":          row.get("fcf") or 0,
                "PAT CAGR 5yr": row.get("pat_cagr") or 0,
                "Rev CAGR 5yr": row.get("rev_cagr") or 0,
                "Composite Score": row.get("composite_score") or 0,
            }
            safe_name   = self._safe_filename(company_name)
            output_path = self.output_dir / f"{safe_name}_radar.png"

            _standalone_bar_chart(
                company_name    = company_name,
                company_values  = company_vals,
                universe_avg    = universe_avg,
                output_path     = output_path,
            )
            charts += 1

        return charts

    def run_all(self, year: int | None = None) -> dict:
        """
        Generate radar charts for all peer groups + no-peer companies.
        Returns summary dict.
        """
        peer_groups = self._get_peer_groups()
        total_charts = 0

        for group in peer_groups:
            n = self.generate_for_group(group, year=year)
            log.info(f"  {group}: {n} charts")
            total_charts += n

        no_peer_charts = self.generate_no_peer_charts()

        summary = {
            "peer_groups_processed": len(peer_groups),
            "charts_generated":      total_charts,
            "no_peer_charts":        no_peer_charts,
            "output_dir":            str(self.output_dir),
        }
        log.info(f"Radar chart run complete: {summary}")
        return summary
