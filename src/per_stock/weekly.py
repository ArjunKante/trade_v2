"""Point-in-time weekly OHLC + trailing-52-week realized-vol (sigma) panel
for the per-stock weekly study. Built from each stock's own daily adjusted
OHLC history (src/fibo/daily_ohlc.py::build_daily_ohlc_panel) -- the same
adjusted-price source the Fibo study already relies on, read-only, never
modified here.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from fibo.daily_ohlc import build_daily_ohlc_panel

SIGMA_WINDOW_WEEKS = 52


def build_weekly_panel(con: duckdb.DuckDBPyConnection, entity_ids: list[str]) -> pd.DataFrame:
    """[entity_id, week_start, week_open, week_close, n_days, week_return]
    -- one row per (entity_id, ISO week) with at least one traded day.
    week_start is that ISO week's Monday DATE (a label, not necessarily a
    traded day itself); week_open/week_close are the FIRST/LAST actually-
    traded day's adjusted open/close that week -- a holiday Monday or
    Friday is handled automatically (whichever day traded first/last that
    week stands in), never assumed to be Monday/Friday literally."""
    daily = build_daily_ohlc_panel(con, entity_ids=entity_ids)
    daily = daily.sort_values(["entity_id", "trade_date"]).copy()
    daily["week_start"] = daily["trade_date"] - pd.to_timedelta(daily["trade_date"].dt.weekday, unit="D")

    grouped = daily.groupby(["entity_id", "week_start"], sort=True)
    weekly = grouped.agg(
        week_open=("adjusted_open", "first"),
        week_close=("adjusted_close", "last"),
        n_days=("trade_date", "count"),
    ).reset_index()
    weekly["week_return"] = weekly["week_close"] / weekly["week_open"] - 1.0
    return weekly.sort_values(["entity_id", "week_start"]).reset_index(drop=True)


def add_trailing_sigma(weekly: pd.DataFrame, window_weeks: int = SIGMA_WINDOW_WEEKS) -> pd.DataFrame:
    """Adds `sigma`: the trailing `window_weeks`-week (default 52) sample
    standard deviation (ddof=1) of week_return, evaluated AT each week
    (i.e. the window [week-51 .. week] INCLUDES that week's own return as
    its most recent observation) -- NaN until `window_weeks` weeks of
    history exist for that entity.

    POINT-IN-TIME BY CONSTRUCTION: a trading decision for week W+1 reads
    row W's own sigma and week_return (both already fully known at week
    W's close, before week W+1's Monday open) -- never row W+1's own
    values. This module only labels each week with its OWN trailing
    sigma; it is per_stock.rules that decides which week's row feeds which
    later week's trade, and never looks forward when doing so."""
    out = weekly.sort_values(["entity_id", "week_start"]).copy()
    out["sigma"] = out.groupby("entity_id")["week_return"].transform(
        lambda s: s.rolling(window_weeks, min_periods=window_weeks).std(ddof=1)
    )
    return out


def build_weekly_panel_with_sigma(con: duckdb.DuckDBPyConnection, entity_ids: list[str],
                                   window_weeks: int = SIGMA_WINDOW_WEEKS) -> pd.DataFrame:
    return add_trailing_sigma(build_weekly_panel(con, entity_ids), window_weeks=window_weeks)
