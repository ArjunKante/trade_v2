"""1-minute -> 15-minute bar aggregation, and 1-minute -> daily aggregation
(the latter feeds src/fibo/validation.py's bhavcopy cross-check).

15-minute buckets are anchored to the market open (09:15), which is itself
already on a 15-minute boundary (09:15, 09:30, ..., 15:15), so a plain
floor-to-15-minutes produces exactly the ORB (09:15-09:30) and entry-window
(09:15-11:30) buckets the frozen rule needs -- no separate anchoring logic
required. A bucket's OHLCV is standard: first open, max high, min low, last
close (by bar start time within the bucket), summed volume.
"""
from __future__ import annotations

import pandas as pd

BUCKET_MINUTES = 15


def aggregate_to_15min(bars_1min: pd.DataFrame) -> pd.DataFrame:
    """bars_1min: [entity_id, trade_date, ts, open, high, low, close,
    volume]. Returns the same shape, one row per (entity_id, trade_date,
    15-min bucket), `ts` = the bucket's START time."""
    df = bars_1min.copy()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values(["entity_id", "trade_date", "ts"])
    df["bucket_ts"] = df["ts"].dt.floor(f"{BUCKET_MINUTES}min")

    grouped = df.groupby(["entity_id", "trade_date", "bucket_ts"], sort=True)
    out = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index().rename(columns={"bucket_ts": "ts"})
    return out[["entity_id", "trade_date", "ts", "open", "high", "low", "close", "volume"]]


def aggregate_to_daily(bars_1min: pd.DataFrame) -> pd.DataFrame:
    """[entity_id, trade_date, open, high, low, close, volume] -- one row
    per (entity_id, trade_date), the day's full session collapsed to a
    single OHLCV bar, for comparison against bhavcopy (src/fibo/validation.py)."""
    df = bars_1min.copy()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values(["entity_id", "trade_date", "ts"])
    grouped = df.groupby(["entity_id", "trade_date"], sort=True)
    out = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index()
    return out
