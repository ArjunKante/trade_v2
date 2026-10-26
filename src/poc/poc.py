"""PREREGISTRATION_POC.md Section 4: PROXY POC and PREV_HIGH construction.

Pure functions only (no DB access) -- operate on the five lookback days'
own RAW-scale `day_raw` 1-minute-bar frames (`box_theory.context.
eligible_day_context`'s own output, Section 3's six-day chain), plus
today's own 09:15 open for the bucket-width reference price. Kept
separate from `poc.context` (which does the DB-facing eligibility
chaining) so this module is reproducible and unit-testable in isolation,
the same separation `box_theory.resolution` documents for its own pure
trade-management core.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

BUCKET_WIDTH_PCT = 0.0025  # 0.25% of today's own 09:15 open, per instruction


def bucket_width(open_today_raw: float) -> float:
    """PREREGISTRATION_POC.md Section 4: 0.25% of the stock's price on the
    calculation day -- operationalized as TODAY's own 09:15 open (RAW
    scale), the earliest price actually recorded on the calculation day
    itself, known before 09:45 and so free of lookahead even though it is
    only ever used as a WIDTH parameter, never as a bucketed price."""
    if open_today_raw <= 0:
        raise ValueError(f"open_today_raw must be positive, got {open_today_raw}")
    return BUCKET_WIDTH_PCT * open_today_raw


def compute_poc(lookback_bars: list[pd.DataFrame], width: float) -> dict:
    """`lookback_bars`: the five lookback days' own `day_raw` frames
    (RAW-scale 1-minute bars, columns at least [high, low, close, volume]),
    L1..L5 in any order (all five are pooled together -- POC is computed
    across the WHOLE 5-day window, not per-day). Returns {"poc_price":
    float, "poc_bucket_index": int, "poc_bucket_volume": int,
    "n_bars": int} -- bucket volumes are also exposed via `bucket_totals`
    (bucket_index -> summed volume) for the hand-trace step to show its
    own working.

    Every bar's WHOLE volume goes to ONE bucket (the proxy step named in
    PREREGISTRATION_POC.md's DATA LIMITATION section) -- never split
    across the bar's own high-low range."""
    frames = [b for b in lookback_bars if b is not None and not b.empty]
    if not frames:
        raise ValueError("compute_poc requires at least one non-empty lookback day")
    all_bars = pd.concat(frames, ignore_index=True)

    typical = (all_bars["high"].to_numpy(dtype="float64")
               + all_bars["low"].to_numpy(dtype="float64")
               + all_bars["close"].to_numpy(dtype="float64")) / 3.0
    bucket_idx = np.floor(typical / width).astype("int64")
    volume = all_bars["volume"].to_numpy(dtype="int64")

    totals: dict[int, int] = {}
    for idx, vol in zip(bucket_idx, volume):
        totals[int(idx)] = totals.get(int(idx), 0) + int(vol)

    max_vol = max(totals.values())
    # tie-break: the LOWER bucket_index, per instruction -- iterate sorted
    # ascending and take the first bucket reaching max_vol
    winning_idx = min(idx for idx, v in totals.items() if v == max_vol)

    return {
        "poc_price": winning_idx * width,
        "poc_bucket_index": winning_idx,
        "poc_bucket_volume": max_vol,
        "n_bars": int(len(all_bars)),
        "bucket_totals": totals,
    }


def compute_prev_high(lookback_bars: list[pd.DataFrame]) -> float:
    """PREREGISTRATION_POC.md Section 4: MAX(high) across every 1-minute
    bar in L1..L5 combined, RAW scale."""
    frames = [b for b in lookback_bars if b is not None and not b.empty]
    if not frames:
        raise ValueError("compute_prev_high requires at least one non-empty lookback day")
    return float(max(float(b["high"].max()) for b in frames))
