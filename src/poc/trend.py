"""PREREGISTRATION_POC.md Section 5: the 50-day daily SMA trend filter.

Operates on `fibo.daily_ohlc.build_daily_ohlc_panel`'s own entity-adjusted
daily close -- unchanged, reused read-only (PREREGISTRATION_POC.md
Section 0). A day without 50 full prior trading days of daily history
fails the filter outright (treated as a FAIL, not a skip), the identical
convention PREREGISTRATION_DARVAS.md Section 1b already states for its
own, differently-defined trend filter.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

SMA_WINDOW = 50


def build_trend_lookup(daily_panel: pd.DataFrame) -> dict:
    """`daily_panel`: one entity's own rows of `fibo.daily_ohlc`'s panel
    (any superset is fine -- filtered here), sorted by trade_date.
    Returns {trade_date (python date) -> bool}: True iff that date's own
    `adjusted_close` is strictly above its trailing 50-day SMA
    (`min_periods=50`, so a date without 50 full prior rows maps to
    False, never missing)."""
    df = daily_panel.sort_values("trade_date").reset_index(drop=True)
    sma = df["adjusted_close"].rolling(window=SMA_WINDOW, min_periods=SMA_WINDOW).mean()
    passes = df["adjusted_close"] > sma
    dates = pd.to_datetime(df["trade_date"]).dt.date
    return dict(zip(dates, passes.fillna(False)))


def trend_filter_passes(trend_lookup: dict, day: dt.date) -> bool:
    """False (fail) if `day` is not in the lookup at all (no daily row
    for that date) -- same fail-not-skip stance as a date with
    insufficient SMA history."""
    return bool(trend_lookup.get(day, False))
