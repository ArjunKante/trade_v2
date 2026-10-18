"""1-minute -> 1-hour bar aggregation, PREREGISTRATION_FVG.md Section 3:
buckets anchored to the market OPEN (09:15), not to midnight -- 60 minutes
does not divide the session evenly from a midnight floor the way
`box_theory.bars.aggregate_to_5min`'s 5-minute buckets do (09:15 already
sits on a 5-minute boundary; it does not sit on an hour boundary). Buckets
are [09:15,10:15), [10:15,11:15), ..., [14:15,15:15), and one PARTIAL
15-minute bucket [15:15,15:30) -- the archive's last 1-minute bar is
ts=15:29, confirming the session ends at 15:30. The partial bucket counts
as one candle, identically to every full-hour candle, per the
preregistration.

Each row also carries `bucket_end` (the bucket's own close timestamp --
+60min for every bucket except the last, which is +15min) since
`PREREGISTRATION_FVG.md` Section 5's fill rule depends on this exact value
and cannot assume a fixed 60-minute offset for the day's final candle.

Written fresh (not reusing `box_theory.bars.aggregate_to_5min`) for the
anchor-offset reason above; same vectorized bucket-and-reduce technique,
independently verified against a plain groupby on real archive days.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SESSION_OPEN = pd.Timedelta(hours=9, minutes=15)
BUCKET_MINUTES = 60

_EMPTY_COLUMNS = ["ts", "bucket_end", "open", "high", "low", "close", "volume", "is_green", "is_red"]


def aggregate_to_1hour(bars_1min: pd.DataFrame) -> pd.DataFrame:
    """bars_1min: [ts, open, high, low, close, volume] for ONE entity's
    ONE day (any order; sorted here). Returns one row per 1-hour bucket
    (anchored at 09:15, last bucket partial [15:15,15:30)), columns
    [ts, bucket_end, open, high, low, close, volume, is_green, is_red]."""
    if bars_1min.empty:
        return pd.DataFrame(columns=_EMPTY_COLUMNS)

    df = bars_1min.sort_values("ts")
    ts = df["ts"].to_numpy()
    opens = df["open"].to_numpy(dtype="float64")
    highs = df["high"].to_numpy(dtype="float64")
    lows = df["low"].to_numpy(dtype="float64")
    closes = df["close"].to_numpy(dtype="float64")
    volumes = df["volume"].to_numpy(dtype="int64")

    day_start = ts[0].astype("datetime64[D]").astype("datetime64[m]")
    session_open = day_start + np.timedelta64(9 * 60 + 15, "m")
    minutes_since_open = (ts.astype("datetime64[m]") - session_open).astype(np.int64)
    bucket_id = minutes_since_open // BUCKET_MINUTES

    change = np.flatnonzero(np.diff(bucket_id)) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [len(bucket_id)]))  # exclusive end index per bucket

    bucket_ts = (session_open + bucket_id[starts] * BUCKET_MINUTES).astype("datetime64[us]")
    # bucket_end = min(bucket_start + 60min, next bucket's own start if this
    # is the day's last bucket and it is the partial 15:15-15:30 one) --
    # in practice the partial bucket is always the LAST bucket of the day
    # (the session ends at 15:30, which is exactly bucket_id boundary 6),
    # so bucket_end is simply bucket_start + 60min capped by this bucket's
    # own last bar's ts + 1 minute for the final (possibly partial) bucket.
    last_bar_idx = ends - 1
    last_bar_ts = ts[last_bar_idx].astype("datetime64[m]")
    full_end = (bucket_ts.astype("datetime64[m]") + np.timedelta64(60, "m"))
    bucket_end = np.minimum(full_end, last_bar_ts + np.timedelta64(1, "m")).astype("datetime64[us]")

    open_vals = opens[starts]
    close_vals = closes[last_bar_idx]
    high_vals = np.maximum.reduceat(highs, starts)
    low_vals = np.minimum.reduceat(lows, starts)
    vol_vals = np.add.reduceat(volumes, starts)

    out = pd.DataFrame({
        "ts": bucket_ts, "bucket_end": bucket_end, "open": open_vals, "high": high_vals,
        "low": low_vals, "close": close_vals, "volume": vol_vals,
    })
    out["is_green"] = out["close"] > out["open"]
    out["is_red"] = out["close"] < out["open"]
    return out
