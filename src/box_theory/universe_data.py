"""Thin, box-theory-owned data-access helpers around tables `fibo.scale_
probe` and `fibo.jump_guard` already query -- batched PER ENTITY (one
query for a whole entity's history) rather than per entity-day, which is
what makes streaming ~200 entities x ~10 years tractable: this study
evaluates on the order of 10^5-10^6 entity-days, and a DB round trip per
entity-day would dominate runtime. `fibo.scale_probe`'s own per-call
primitives (`probe_scale`, `is_ex_date`, `passes_gap_guard`) are still
reused directly (see resolution usage in backtest.py) -- only the DATA
FETCHES around them are batched here, read-only, nothing in `src/fibo/`
is modified.

WHY `decide_scale_for_day` ITSELF IS NOT CALLED (reused only at the
primitive level, `probe_scale`/`is_ex_date`/`passes_gap_guard`, not the
convenience wrapper): `decide_scale_for_day` internally derives its own
"previous day" via `fibo.scale_probe.previous_trading_day` (entity E's
own most recent `prices_eod` row before D). PREREGISTRATION_BOX.md
Section 2b needs a DIFFERENT, market-wide "previous day" (`box_theory.
holiday.previous_nse_trading_day`, independently verified to have >= 350
archive bars) for an unrelated reason -- catching Muhurat/gap days. Using
`decide_scale_for_day` as-is would let two different notions of
"previous day" silently coexist in the same backtest (one deciding
whether the day is eligible at all, a different one deciding the scale
factor); composing the same primitives against ONE explicitly-computed
previous day keeps a single definition throughout.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd


def fetch_bhav_daily(warehouse_con: duckdb.DuckDBPyConnection, entity_id: str,
                      start: dt.date, end: dt.date) -> pd.DataFrame:
    """[trade_date, high, low, close] -- entity's full EQ-series daily
    history in [start, end], indexed by trade_date for O(1) lookup."""
    df = warehouse_con.execute(
        """SELECT p.trade_date, p.high, p.low, p.close
           FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
           WHERE l.entity_id = ? AND p.series = 'EQ' AND p.trade_date BETWEEN ? AND ?
           ORDER BY p.trade_date""",
        [entity_id, start, end],
    ).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df.set_index("trade_date")


def fetch_ex_dates(warehouse_con: duckdb.DuckDBPyConnection, entity_id: str) -> set:
    """Every ex_date across entity_id's full ISIN lineage chain -- same
    query `fibo.scale_probe.is_ex_date` issues per-call, batched here to
    one query per entity instead of one per (entity, day)."""
    rows = warehouse_con.execute(
        """SELECT DISTINCT ca.ex_date FROM corporate_actions ca JOIN isin_lineage l ON ca.isin = l.isin
           WHERE l.entity_id = ?""",
        [entity_id],
    ).fetchall()
    return {r[0] for r in rows}


def fetch_bars_range(intraday_con: duckdb.DuckDBPyConnection, entity_id: str,
                      start: dt.date, end: dt.date) -> pd.DataFrame:
    """[trade_date, ts, open, high, low, close, volume] -- entity's
    bars_1min rows in [start, end], ANGEL scale (not yet raw-converted).
    One query per (entity, year-ish block) -- see backtest.py's caller.

    `trade_date` is deliberately left as datetime64 (NOT converted to
    Python `datetime.date`, object-dtype column) -- repeated `==` scans
    against an object-dtype array go through pandas' slow
    comp_method_OBJECT_ARRAY element-by-element path (confirmed by
    profiling a 1-entity/1-year run at ~19s, ~3.9s of it in exactly that
    comparison). Callers group once by `trade_date` (box_theory.backtest's
    `_group_by_day`) instead of repeatedly filtering this frame."""
    df = intraday_con.execute(
        """SELECT trade_date, ts, open, high, low, close, volume FROM bars_1min
           WHERE entity_id = ? AND trade_date BETWEEN ? AND ? ORDER BY ts""",
        [entity_id, start, end],
    ).fetchdf()
    return df


def fetch_bars_single_day(intraday_con: duckdb.DuckDBPyConnection, entity_id: str,
                           day: dt.date) -> pd.DataFrame:
    """Same shape as fetch_bars_range, one day only -- the year-boundary
    fallback when a day's previous session falls in the prior streamed
    block (e.g. the first trading day of a year, whose previous session
    is in December)."""
    return fetch_bars_range(intraday_con, entity_id, day, day)
