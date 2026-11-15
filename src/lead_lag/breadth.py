"""Decision 10: the follower-basket breadth diagnostic -- a per-minute,
present-valid-only count of how much of the follower tier has a usable
bar, mirroring the leader-side `n_t_breadth` convention (Section 8).

**Deliberately separate from the primary regression and from Option 2's
own Stage-A 70% threshold (Decision 19)** -- Section 23 of the
preregistration states explicitly that these are two distinct
mechanisms that happen to share a number, not one mechanism. This
module never filters, freezes, or discards an observation; it only
measures and reports. It never computes `S_L`, `R_F`, `Momentum_F`, or
`Y`, and never fits any regression -- there is no primary-outcome
leakage risk here by construction.

`PRESENT_VALID_SQL` is a SQL boolean expression reproducing
`validity.is_present_valid` exactly (Decision 17), so this module's
breadth counts use the same bar-validity rule as every other part of
this family, not a second, independently-invented one.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import duckdb
import pandas as pd

FOLLOWER_BREADTH_FLOOR = 0.70  # Decision 10, Section 23

PRESENT_VALID_SQL = """
    (open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL AND volume IS NOT NULL
     AND NOT isnan(open) AND NOT isnan(high) AND NOT isnan(low) AND NOT isnan(close) AND NOT isnan(volume)
     AND NOT isinf(open) AND NOT isinf(high) AND NOT isinf(low) AND NOT isinf(close) AND NOT isinf(volume)
     AND open > 0 AND high > 0 AND low > 0 AND close > 0
     AND high >= low AND open BETWEEN low AND high AND close BETWEEN low AND high
     AND volume >= 0
     AND (volume > 0 OR (volume = 0 AND open = high AND high = low AND low = close)))
"""


def compute_follower_breadth(
    con: duckdb.DuckDBPyConnection,
    follower_entity_ids: tuple[str, ...],
    start_date: dt.date,
    end_date: dt.date,
) -> pd.DataFrame:
    """Per-(trade_date, ts) count of PRESENT-VALID bars among
    `follower_entity_ids`, restricted to `[start_date, end_date]`
    inclusive. Read-only; does not filter or exclude anything -- the
    caller decides what to do with the result. Columns: `trade_date`,
    `ts`, `n_present_valid`, `n_follower_tier`, `breadth`."""
    if not follower_entity_ids:
        return pd.DataFrame(columns=["trade_date", "ts", "n_present_valid", "n_follower_tier", "breadth"])
    placeholders = ",".join(["?"] * len(follower_entity_ids))
    q = f"""
        SELECT trade_date, ts,
               SUM(CASE WHEN {PRESENT_VALID_SQL} THEN 1 ELSE 0 END) AS n_present_valid
        FROM bars_1min
        WHERE entity_id IN ({placeholders})
          AND trade_date BETWEEN ? AND ?
        GROUP BY trade_date, ts
        ORDER BY trade_date, ts
    """
    df = con.execute(q, [*follower_entity_ids, start_date, end_date]).fetchdf()
    df["n_follower_tier"] = len(follower_entity_ids)
    df["breadth"] = df["n_present_valid"] / df["n_follower_tier"]
    return df


@dataclass(frozen=True)
class BreadthSummary:
    n_minutes: int
    n_below_floor: int
    pct_below_floor: float
    min_breadth: float
    median_breadth: float
    floor: float


def summarize_breadth(df: pd.DataFrame, floor: float = FOLLOWER_BREADTH_FLOOR) -> BreadthSummary:
    if df.empty:
        return BreadthSummary(0, 0, 0.0, float("nan"), float("nan"), floor)
    below = df[df["breadth"] < floor]
    return BreadthSummary(
        n_minutes=len(df),
        n_below_floor=len(below),
        pct_below_floor=100.0 * len(below) / len(df),
        min_breadth=float(df["breadth"].min()),
        median_breadth=float(df["breadth"].median()),
        floor=floor,
    )
