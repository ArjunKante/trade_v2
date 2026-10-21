"""`PREREGISTRATION_IPO.md` Section 5's trade mechanics -- entry, stop,
target, time exit. Deliberately NOT an adaptation of `box_theory.
resolution`'s touch/arm/FAST-SLOW machinery, which this study's much
simpler single-day, fixed-percentage rule does not need: every trade
(or null draw) here is fully determined by ONE day's own 1-minute bars,
no multi-day lifecycle, no 5-minute candle layer.

All functions are pure (a day's own ts-sorted 1-minute bars in, a
decision out) -- no DB access, so the 5 hand-traced examples
(`PREREGISTRATION_IPO.md` Process Step 3) are reproducible in isolation.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

FIXED_RISK_RS = 500.0
STOP_PCT = 0.05
TARGET_PCT = 0.125

TIME_EXIT_TS = dt.time(15, 15)
TIMING_NULL_WINDOW_START = dt.time(9, 16)
TIMING_NULL_WINDOW_END = dt.time(15, 0)


def position_size_shares(entry_price: float, fixed_risk_rs: float = FIXED_RISK_RS,
                          stop_pct: float = STOP_PCT) -> int:
    """qty = floor(500 / (entry * 0.05)) -- `PREREGISTRATION_IPO.md`
    Section 5's sizing rule, structurally identical to
    `box_theory.resolution.position_size_shares` (same formula, this
    study's own 5% stop_pct passed explicitly rather than that module's
    3% default)."""
    per_share_risk = stop_pct * entry_price
    if per_share_risk <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    return math.floor(fixed_risk_rs / per_share_risk)


def find_entry(bars1_day: pd.DataFrame, ignore_color: bool = False) -> dict:
    """`bars1_day`: one listing day's own 1-minute bars, ts-sorted,
    columns [ts, open, high, low, close]. The FIRST row is "the first
    1-minute candle of the listing day present in the archive" per
    `PREREGISTRATION_IPO.md` Section 3c/5 -- not assumed to be 09:15.

    Returns a dict with "status" in {"SKIPPED_RED_OR_FLAT", "NO_FILL_BAR",
    "ZERO_QTY", "ENTERED"}. On "ENTERED": first_candle (the Series),
    is_green, fill_ts, entry_price, qty, stop, target.

    `ignore_color=True` is the SELECTION null's own alternate rule
    (`PREREGISTRATION_IPO.md` Section 8): enter at the open of the
    candle AFTER the first one regardless of its colour -- the same
    generalization of "first candle, whatever time it starts" already
    applied to the real ENTRY rule (user-approved), extended consistently
    to the null rather than left ambiguous at a literal "09:16" that may
    not exist that day."""
    if len(bars1_day) == 0:
        return {"status": "NO_FILL_BAR"}

    first_candle = bars1_day.iloc[0]
    is_green = bool(first_candle["close"] > first_candle["open"])
    if not ignore_color and not is_green:
        return {"status": "SKIPPED_RED_OR_FLAT", "first_candle": first_candle, "is_green": is_green}

    if len(bars1_day) < 2:
        return {"status": "NO_FILL_BAR", "first_candle": first_candle, "is_green": is_green}

    fill_bar = bars1_day.iloc[1]
    entry_price = float(fill_bar["open"])
    qty = position_size_shares(entry_price)
    if qty < 1:
        return {
            "status": "ZERO_QTY", "first_candle": first_candle, "is_green": is_green,
            "fill_ts": pd.Timestamp(fill_bar["ts"]), "entry_price": entry_price,
        }

    return {
        "status": "ENTERED", "first_candle": first_candle, "is_green": is_green,
        "fill_ts": pd.Timestamp(fill_bar["ts"]), "entry_price": entry_price, "qty": qty,
        "stop": entry_price * (1 - STOP_PCT), "target": entry_price * (1 + TARGET_PCT),
    }


def resolve_exit(bars1_day: pd.DataFrame, fill_ts: pd.Timestamp, entry_price: float,
                  stop: float, target: float) -> dict:
    """Scans 1-minute bars from `fill_ts` (inclusive, the entry fill bar
    itself) through the bar at `TIME_EXIT_TS` (15:15) inclusive, for the
    first bar whose low <= stop or high >= target. STOP wins a same-bar
    tie (same convention as `box_theory.resolution.resolve_exit`). If
    neither resolves by then, exits at the close of the 15:15 bar --
    the fallback (latest bar at or before 15:15) fires if the archive
    has no bar exactly at that timestamp that day, logged via
    `time_exit_fallback`.

    Returns {"outcome": "STOP"|"TARGET"|"TIME_EXIT", "exit_price",
    "exit_ts", "time_exit_fallback"}."""
    df = bars1_day[bars1_day["ts"] >= fill_ts].reset_index(drop=True)
    day_start = pd.Timestamp(bars1_day["ts"].iloc[0]).normalize()
    cutoff = day_start + pd.Timedelta(hours=TIME_EXIT_TS.hour, minutes=TIME_EXIT_TS.minute)
    scan = df[df["ts"] <= cutoff]

    for _, bar in scan.iterrows():
        hit_stop = bar["low"] <= stop
        hit_target = bar["high"] >= target
        if hit_stop and hit_target:
            exit_price = float(bar["open"]) if bar["open"] <= stop else stop
            return {"outcome": "STOP", "exit_price": exit_price, "exit_ts": pd.Timestamp(bar["ts"]),
                    "time_exit_fallback": False}
        if hit_stop:
            exit_price = float(bar["open"]) if bar["open"] <= stop else stop
            return {"outcome": "STOP", "exit_price": exit_price, "exit_ts": pd.Timestamp(bar["ts"]),
                    "time_exit_fallback": False}
        if hit_target:
            exit_price = float(bar["open"]) if bar["open"] >= target else target
            return {"outcome": "TARGET", "exit_price": exit_price, "exit_ts": pd.Timestamp(bar["ts"]),
                    "time_exit_fallback": False}

    te_rows = scan[scan["ts"] == cutoff]
    if len(te_rows):
        row = te_rows.iloc[-1]
        return {"outcome": "TIME_EXIT", "exit_price": float(row["close"]), "exit_ts": pd.Timestamp(row["ts"]),
                "time_exit_fallback": False}
    if len(scan):
        row = scan.iloc[-1]
        return {"outcome": "TIME_EXIT", "exit_price": float(row["close"]), "exit_ts": pd.Timestamp(row["ts"]),
                "time_exit_fallback": True}
    # entry bar itself is already past the 15:15 cutoff (only possible if
    # fill_ts > cutoff, which would mean no room for ENTRY_WINDOW at all --
    # not expected given find_entry always fills on the 2nd archived bar
    # of the day, but guarded rather than silently producing a KeyError.
    raise ValueError("no bar at or before the 15:15 cutoff found at/after fill_ts -- unexpected")
