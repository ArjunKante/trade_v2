"""Minimal entity-aware feature helper, for validating the entity-spanning
invariant only. NOT the Phase 2 momentum factor (which needs the
Jegadeesh-Titman skip-month convention, built when Phase 2 starts). This
exists so the data layer can prove, before any real factor is computed,
that a long lookback window correctly reads across an ISIN change rather
than truncating at it.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from data_layer.adjustment import read_adjusted_prices


def trailing_return(con: duckdb.DuckDBPyConnection, entity_id: str, as_of: dt.date, lookback_days: int) -> dict:
    """Simple trailing N-trading-day return on entity-adjusted close, as of a
    given date. Returns a dict with the return plus how many distinct raw
    ISINs contributed to the lookback window, so a test can assert that
    number is >1 when the window is known to cross a lineage boundary."""
    df = read_adjusted_prices(con, entity_id)
    df = df[df["trade_date"] <= pd.Timestamp(as_of)].sort_values("trade_date").reset_index(drop=True)
    if len(df) <= lookback_days:
        return {"return": None, "n_isins_in_window": None, "window_start": None, "window_end": None}

    window = df.iloc[-(lookback_days + 1):]
    ret = window["adjusted_close"].iloc[-1] / window["adjusted_close"].iloc[0] - 1
    return {
        "return": ret,
        "n_isins_in_window": window["isin"].nunique(),
        "window_start": window["trade_date"].iloc[0],
        "window_end": window["trade_date"].iloc[-1],
    }
