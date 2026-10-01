"""Daily-vs-bhavcopy cross-check for downloaded 1-minute intraday bars --
the free correctness check the Step 3 download plan calls for: aggregate a
day's 1-minute bars to a single daily OHLC (src/fibo.bars.aggregate_to_daily)
and compare against that same entity/date's bhavcopy-sourced raw OHLC
already sitting in data/warehouse.duckdb's prices_eod. If Angel One's feed
and NSE's own bhavcopy disagree beyond a small tolerance, that is worth
knowing BEFORE a single golden-zone level is trusted against these bars.

The comparison logic (`compare_daily_to_bhavcopy`) takes plain DataFrames,
not live connections, so it is fully testable on synthetic data now, before
any real Angel One download exists (Step 1 of this module's build has not
run yet). `run_validation_against_databases` is the thin, NOT-YET-RUN
wrapper that will be pointed at the two real DuckDB files once Step 3
downloads actual bars -- included now so the download step has validation
ready on day one, per the module's own stated plan ("do this before
trusting any intraday bar").

TOLERANCE is a stated, revisitable placeholder (0.1% on each of O/H/L/C),
not a validated threshold -- the whole point of Step 3's validation run is
to discover what the REAL mismatch rate looks like; this default may need
loosening or tightening once real numbers exist.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from fibo.bars import aggregate_to_daily

DEFAULT_TOLERANCE_PCT = 0.1  # percent, i.e. 0.1 = 0.1%


def compare_daily_to_bhavcopy(
    bars_1min: pd.DataFrame, bhavcopy_daily: pd.DataFrame, tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> pd.DataFrame:
    """bars_1min: [entity_id, trade_date, ts, open, high, low, close, volume].
    bhavcopy_daily: [entity_id, trade_date, open, high, low, close] (raw,
    from prices_eod -- NOT entity-adjusted; intraday bars are raw too, so
    this compares like with like, unlike every other cross-source
    comparison in this project which goes through adjusted prices).

    Returns one row per (entity_id, trade_date) present in BOTH inputs,
    with each field's absolute pct difference and an overall `mismatch`
    flag (any of O/H/L/C exceeds tolerance_pct)."""
    intraday_daily = aggregate_to_daily(bars_1min)
    merged = intraday_daily.merge(
        bhavcopy_daily, on=["entity_id", "trade_date"], suffixes=("_intraday", "_bhavcopy"), how="inner")

    rows = []
    for _, r in merged.iterrows():
        diffs = {}
        mismatch = False
        for field in ["open", "high", "low", "close"]:
            bhav = r[f"{field}_bhavcopy"]
            intr = r[f"{field}_intraday"]
            pct_diff = abs(intr - bhav) / bhav * 100.0 if bhav else float("nan")
            diffs[f"{field}_pct_diff"] = pct_diff
            if pd.isna(pct_diff) or pct_diff > tolerance_pct:
                mismatch = True
        rows.append({
            "entity_id": r["entity_id"], "trade_date": r["trade_date"],
            **diffs, "mismatch": mismatch,
        })
    return pd.DataFrame(rows)


def mismatch_rate(comparison: pd.DataFrame) -> float:
    """Fraction of compared (entity, day) pairs flagged as a mismatch --
    the single number Step 3's report is asked for."""
    if comparison.empty:
        return float("nan")
    return comparison["mismatch"].mean()


def run_validation_against_databases(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> pd.DataFrame:
    """NOT YET RUN against real data (no Angel One download exists yet --
    Step 1/3 of this module's build). Pulls every downloaded 1-minute bar
    from the intraday warehouse, every matching entity/date's raw OHLC from
    the main warehouse (via isin_lineage, same entity-aware join as every
    other cross-table read in this project), and calls
    compare_daily_to_bhavcopy. This is the function Step 3's validation
    report should call once real bars exist."""
    bars_1min = intraday_con.execute(
        "SELECT entity_id, trade_date, ts, open, high, low, close, volume FROM bars_1min"
    ).fetchdf()
    bhavcopy_daily = warehouse_con.execute(
        """
        SELECT l.entity_id, p.trade_date, p.open, p.high, p.low, p.close
        FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
        WHERE p.series = 'EQ'
        """
    ).fetchdf()
    comparison = compare_daily_to_bhavcopy(bars_1min, bhavcopy_daily, tolerance_pct=tolerance_pct)
    return comparison
