"""1-minute -> 5-minute bar aggregation, PREREGISTRATION_BOX.md Section 2b:
"Aggregated to 5-minute candles for every signal decision ... No other
interval is to be tried." Written fresh rather than reusing `fibo.bars.
aggregate_to_15min` -- same bucket-floor technique, different, frozen
bucket width this study's own pre-registration commits to.

5-minute buckets are anchored to the market open (09:15), itself already
on a 5-minute boundary (09:15, 09:20, 09:25, ...), so flooring from
midnight (equivalently, from the Unix epoch, since 5 divides 60 evenly)
produces the right buckets with no separate anchoring logic.

IMPLEMENTATION NOTE: this is a plain-numpy bucket-and-reduce, not
`DataFrame.groupby(...).agg(...)` -- profiled on this environment's
pandas/pyarrow build, the groupby+named-aggregation form took ~18ms per
day-sized (~375-row) frame, dominated by pyarrow/string-array machinery
pandas' groupby internals pull in for this call shape. At this study's
scale (one call per entity-day, ~10^5-10^6 entity-days across DEV, TEST,
and null draws), that was the single largest cost in the whole backtest
-- this version does the same floor-and-reduce with `numpy.ufunc.reduceat`
over presorted, contiguous buckets, independently verified byte-for-byte
equal to the groupby version on real archive days before the switch."""
from __future__ import annotations

import numpy as np
import pandas as pd

BUCKET_MINUTES = 5

_EMPTY_COLUMNS = ["ts", "open", "high", "low", "close", "volume", "is_green", "is_red"]


def aggregate_to_5min(bars_1min: pd.DataFrame) -> pd.DataFrame:
    """bars_1min: [ts, open, high, low, close, volume] for ONE entity's
    ONE day (any order; sorted here). Returns one row per 5-minute bucket,
    `ts` = the bucket's START time, columns [ts, open, high, low, close,
    volume, is_green, is_red]."""
    if bars_1min.empty:
        return pd.DataFrame(columns=_EMPTY_COLUMNS)

    df = bars_1min.sort_values("ts")
    ts = df["ts"].to_numpy()
    opens = df["open"].to_numpy(dtype="float64")
    highs = df["high"].to_numpy(dtype="float64")
    lows = df["low"].to_numpy(dtype="float64")
    closes = df["close"].to_numpy(dtype="float64")
    volumes = df["volume"].to_numpy(dtype="int64")

    minutes_since_epoch = ts.astype("datetime64[m]").astype(np.int64)
    bucket_id = minutes_since_epoch // BUCKET_MINUTES

    change = np.flatnonzero(np.diff(bucket_id)) + 1
    starts = np.concatenate(([0], change))

    bucket_ts = (bucket_id[starts] * BUCKET_MINUTES).astype("datetime64[m]").astype("datetime64[us]")
    open_vals = opens[starts]
    close_vals = closes[np.concatenate((change - 1, [len(bucket_id) - 1]))]
    high_vals = np.maximum.reduceat(highs, starts)
    low_vals = np.minimum.reduceat(lows, starts)
    vol_vals = np.add.reduceat(volumes, starts)

    out = pd.DataFrame({
        "ts": bucket_ts, "open": open_vals, "high": high_vals, "low": low_vals,
        "close": close_vals, "volume": vol_vals,
    })
    out["is_green"] = out["close"] > out["open"]
    out["is_red"] = out["close"] < out["open"]
    return out
