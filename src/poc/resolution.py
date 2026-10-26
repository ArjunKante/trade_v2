"""PREREGISTRATION_POC.md Sections 6-8: touch, hammer/green confirmation,
entry fill, sizing, and 1-minute-bar stop/target/time-exit resolution.

All price arguments are assumed already converted to RAW rupee scale
(`fibo.scale_probe`'s scale factor applied upstream by `box_theory.
context.eligible_day_context`, Section 0/3). Every function here is pure
(no DB access), to make the 5 hand-traced examples (Process Step 2)
reproducible in isolation.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

FIXED_RISK_RS = 500.0
STOP_BELOW_POC_PCT = 0.005
TARGET_BELOW_PREV_HIGH_PCT = 0.02
MAX_RISK_PCT = 0.05

TOUCH_WINDOW_START = dt.time(9, 45)
ENTRY_WINDOW_START = dt.time(9, 45)
ENTRY_WINDOW_END = dt.time(14, 30)
TIME_EXIT_CANDLE_TS = dt.time(15, 15)
STOP_SCAN_END_TIME = dt.time(15, 19)

HAMMER_LOWER_WICK_MULT = 2.0
DOJI_RANGE_MULT = 0.2  # = 2 * 0.1, PREREGISTRATION_POC.md Section 6's doji carve-out


# ---------------------------------------------------------------------
# Touch (Section 6)
# ---------------------------------------------------------------------

def find_touch_idx(candles5: pd.DataFrame, poc_price: float) -> int | None:
    """Index (into candles5, 0-based, session order) of the first
    5-minute candle with ts.time() >= 09:45 and low <= poc_price. None if
    no such candle exists."""
    times = candles5["ts"].dt.time
    in_window = times >= TOUCH_WINDOW_START
    hits = candles5.index[in_window & (candles5["low"] <= poc_price)]
    return int(hits[0]) if len(hits) else None


# ---------------------------------------------------------------------
# Hammer / green confirmation (Section 6)
# ---------------------------------------------------------------------

def candle_shape(row: pd.Series) -> dict:
    open_, high, low, close = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
    body = abs(close - open_)
    lower_wick = min(open_, close) - low
    upper_wick = high - max(open_, close)
    full_range = high - low
    return {"body": body, "lower_wick": lower_wick, "upper_wick": upper_wick, "full_range": full_range,
            "is_green": close > open_, "is_red": close < open_}


def is_hammer(shape: dict) -> bool:
    """PREREGISTRATION_POC.md Section 6's hammer test, including the
    doji carve-out and its amendment (full_range > 0 required)."""
    body, lower_wick, upper_wick, full_range = (
        shape["body"], shape["lower_wick"], shape["upper_wick"], shape["full_range"])
    if body > 0:
        return lower_wick >= HAMMER_LOWER_WICK_MULT * body and upper_wick <= body
    return full_range > 0 and lower_wick >= DOJI_RANGE_MULT * full_range


def classify_confirmation_candle(row: pd.Series, poc_price: float) -> str:
    """One of "ENTER_GREEN", "ENTER_HAMMER", "POC_FAILED", "LIVE" --
    PREREGISTRATION_POC.md Section 6's three-way (really four-way, since
    ENTER splits into green/hammer for the hand-trace step's own
    reporting) test, in order."""
    shape = candle_shape(row)
    if shape["is_green"]:
        return "ENTER_GREEN"
    if is_hammer(shape):
        return "ENTER_HAMMER"
    if shape["is_red"] and float(row["close"]) < poc_price:
        return "POC_FAILED"
    # RED-but-close-at-or-above-POC, or a non-hammer doji: a non-event,
    # the setup stays live (Section 6, point 3)
    return "LIVE"


def find_confirmation(candles5: pd.DataFrame, touch_idx: int, poc_price: float) -> dict:
    """Checks up to 2 candidates strictly after touch_idx. Returns
    {"status": "ENTERED", "confirm_idx": int, "confirm_kind": "GREEN"|
    "HAMMER"} or {"status": "POC_FAILED", "confirm_idx": int} or
    {"status": "NO_CONFIRMATION"}."""
    n = len(candles5)
    for offset in (1, 2):
        idx = touch_idx + offset
        if idx >= n:
            return {"status": "NO_CONFIRMATION"}
        row = candles5.iloc[idx]
        verdict = classify_confirmation_candle(row, poc_price)
        if verdict == "ENTER_GREEN":
            return {"status": "ENTERED", "confirm_idx": idx, "confirm_kind": "GREEN"}
        if verdict == "ENTER_HAMMER":
            return {"status": "ENTERED", "confirm_idx": idx, "confirm_kind": "HAMMER"}
        if verdict == "POC_FAILED":
            return {"status": "POC_FAILED", "confirm_idx": idx}
        # LIVE -> try the next candidate (offset 2); if offset was already
        # 2, the loop ends naturally -> NO_CONFIRMATION below
    return {"status": "NO_CONFIRMATION"}


# ---------------------------------------------------------------------
# Entry fill, sizing (Section 7)
# ---------------------------------------------------------------------

def fill_bar_after_candle_close(bars1: pd.DataFrame, candle_close_ts: pd.Timestamp) -> pd.Series | None:
    """The 1-minute bar whose ts equals the confirming candle's own close
    time (bucket start + 5min). None if no such bar exists."""
    row = bars1[bars1["ts"] == candle_close_ts]
    return row.iloc[0] if len(row) else None


def position_size_shares(entry_price: float, stop_price: float, fixed_risk_rs: float = FIXED_RISK_RS) -> int:
    per_share_risk = entry_price - stop_price
    if per_share_risk <= 0:
        raise ValueError(f"entry_price must exceed stop_price, got entry={entry_price} stop={stop_price}")
    return math.floor(fixed_risk_rs / per_share_risk)


def find_entry(candles5: pd.DataFrame, bars1: pd.DataFrame, poc_price: float, prev_high: float) -> dict:
    """Runs Section 6 (touch + confirmation) then Section 7 (fill, window,
    stop/target, risk-bound, no-room, sizing). Returns a dict with at
    least {"status": ...}. status is one of: "NO_TOUCH", "POC_FAILED",
    "NO_CONFIRMATION", "NO_FILL_BAR", "FILL_OUTSIDE_WINDOW",
    "STOP_TOO_WIDE", "NO_ROOM", "ZERO_QTY", "ENTERED". On "ENTERED", also
    includes touch_idx, confirm_idx, confirm_kind, fill_ts, entry_price,
    stop_price, target_price, qty."""
    touch_idx = find_touch_idx(candles5, poc_price)
    if touch_idx is None:
        return {"status": "NO_TOUCH"}

    confirm = find_confirmation(candles5, touch_idx, poc_price)
    if confirm["status"] == "NO_CONFIRMATION":
        return {"status": "NO_CONFIRMATION", "touch_idx": touch_idx}
    if confirm["status"] == "POC_FAILED":
        return {"status": "POC_FAILED", "touch_idx": touch_idx, "confirm_idx": confirm["confirm_idx"]}

    confirm_idx = confirm["confirm_idx"]
    confirm_candle = candles5.iloc[confirm_idx]
    confirm_close_ts = confirm_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, confirm_close_ts)
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", "touch_idx": touch_idx, "confirm_idx": confirm_idx}

    fill_ts = pd.Timestamp(fill_bar["ts"])
    fill_time = fill_ts.time()
    if not (ENTRY_WINDOW_START <= fill_time <= ENTRY_WINDOW_END):
        return {
            "status": "FILL_OUTSIDE_WINDOW", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts,
        }

    entry_price = float(fill_bar["open"])
    stop_price = poc_price * (1 - STOP_BELOW_POC_PCT)
    target_price = prev_high * (1 - TARGET_BELOW_PREV_HIGH_PCT)

    if entry_price <= stop_price:
        return {
            "status": "ENTRY_BELOW_STOP", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price,
        }
    if (entry_price - stop_price) / entry_price > MAX_RISK_PCT:
        return {
            "status": "STOP_TOO_WIDE", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price,
        }
    if target_price <= entry_price:
        return {
            "status": "NO_ROOM", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price,
            "target_price": target_price,
        }

    qty = position_size_shares(entry_price, stop_price)
    if qty < 1:
        return {
            "status": "ZERO_QTY", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price,
            "target_price": target_price,
        }

    return {
        "status": "ENTERED", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
        "confirm_kind": confirm["confirm_kind"], "fill_ts": fill_ts,
        "entry_price": entry_price, "stop_price": stop_price, "target_price": target_price, "qty": qty,
    }


# ---------------------------------------------------------------------
# Exit resolution (Section 8)
# ---------------------------------------------------------------------

def _stop_target_event(bars1: pd.DataFrame, fill_ts: pd.Timestamp, stop_price: float,
                        target_price: float) -> tuple[str, pd.Series] | tuple[None, None]:
    """First 1-minute bar, starting with the entry bar itself (ts ==
    fill_ts) through STOP_SCAN_END_TIME, whose low <= stop_price or high
    >= target_price. If both are true in the same bar, STOP wins, per
    instruction. Returns ("STOP"|"TARGET", bar) or (None, None)."""
    ts = bars1["ts"].to_numpy()
    fill_ts64 = np.datetime64(pd.Timestamp(fill_ts))
    cutoff_ts64 = np.datetime64(pd.Timestamp(fill_ts).normalize() + pd.Timedelta(hours=15, minutes=19))
    lows = bars1["low"].to_numpy()
    highs = bars1["high"].to_numpy()
    in_range = (ts >= fill_ts64) & (ts <= cutoff_ts64)
    stop_mask = in_range & (lows <= stop_price)
    target_mask = in_range & (highs >= target_price)
    stop_hits = np.flatnonzero(stop_mask)
    target_hits = np.flatnonzero(target_mask)
    stop_idx = int(stop_hits[0]) if len(stop_hits) else None
    target_idx = int(target_hits[0]) if len(target_hits) else None

    if stop_idx is None and target_idx is None:
        return None, None
    if stop_idx is not None and (target_idx is None or stop_idx <= target_idx):
        return "STOP", bars1.iloc[stop_idx]
    return "TARGET", bars1.iloc[target_idx]


def resolve_exit(bars1: pd.DataFrame, candles5: pd.DataFrame, fill_ts: pd.Timestamp,
                  entry_price: float, stop_price: float, target_price: float) -> dict:
    """Returns {"outcome": "STOP"|"TARGET"|"TIME_EXIT", "exit_price":
    float, "exit_ts": Timestamp, "time_exit_fallback": bool}."""
    outcome, bar = _stop_target_event(bars1, fill_ts, stop_price, target_price)
    if outcome == "STOP":
        exit_price = float(bar["open"]) if bar["open"] <= stop_price else stop_price
        return {"outcome": "STOP", "exit_price": exit_price, "exit_ts": pd.Timestamp(bar["ts"]),
                "time_exit_fallback": False}
    if outcome == "TARGET":
        return {"outcome": "TARGET", "exit_price": target_price, "exit_ts": pd.Timestamp(bar["ts"]),
                "time_exit_fallback": False}

    day_start = candles5["ts"].iloc[0].normalize()
    time_exit_ts = np.datetime64(day_start + pd.Timedelta(hours=15, minutes=15))
    ts_arr = candles5["ts"].to_numpy()
    time_exit_rows = np.flatnonzero(ts_arr == time_exit_ts)
    used_fallback = False
    if len(time_exit_rows) > 0:
        row_idx = int(time_exit_rows[0])
    else:
        before_rows = np.flatnonzero(ts_arr <= time_exit_ts)
        if len(before_rows) == 0:
            raise ValueError("no candle at or before 15:15 for this day -- cannot resolve a time exit")
        row_idx = int(before_rows[-1])
        used_fallback = True
    row = candles5.iloc[row_idx]
    return {
        "outcome": "TIME_EXIT", "exit_price": float(row["close"]), "exit_ts": row["ts"] + pd.Timedelta(minutes=5),
        "time_exit_fallback": used_fallback,
    }
