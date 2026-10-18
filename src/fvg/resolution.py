"""PREREGISTRATION_FVG.md Sections 5-6: Configuration A (breakout) and
Configuration B (retest) entry triggers, the fill mechanic, the 0.5%
stop-too-tight floor, position sizing (risk = rupee distance to GAP_LOW,
NOT a fixed percentage of entry -- `box_theory.resolution.position_size_
shares` is not reused, see Section 6), and 1-minute-bar stop/target/
time-exit resolution across the (already-excised-of-ineligible-days)
continuous per-entity series `fvg.context.build_entity_timeline` builds.

All price arguments are already RAW rupee scale (same upstream convention
as `box_theory.resolution`). Every function here is pure (no DB access),
for the same hand-trace-reproducibility reason box theory's own module
docstring gives.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

from fvg.holiday import nth_next_nse_trading_day

FIXED_RISK_RS = 500.0
TARGET_R_MULTIPLE = 3.0
STOP_TOO_TIGHT_PCT = 0.005
TIME_EXIT_TRADING_DAYS = 5
TIME_EXIT_TIME = dt.time(15, 15)
STOP_SCAN_END_TIME = dt.time(15, 19)


def position_size_shares(entry_price: float, gap_low: float, fixed_risk_rs: float = FIXED_RISK_RS) -> int:
    """qty = floor(500 / (entry - GAP_LOW)) -- whole shares, floored. Caller
    must have already checked the 0.5% floor (so per_share_risk > 0)."""
    per_share_risk = entry_price - gap_low
    if per_share_risk <= 0:
        raise ValueError(f"entry_price ({entry_price}) must exceed gap_low ({gap_low})")
    return math.floor(fixed_risk_rs / per_share_risk)


def fill_bar_after_close(bars1: pd.DataFrame, close_ts) -> pd.Series | None:
    """The 1-minute bar whose ts equals the trigger candle's own bucket_
    end -- "fill at the open of the next 1-minute bar after [the] candle
    closes." None if no such bar exists in the continuous series (the
    trigger candle is a day's own last (15:15-15:30) candle and the
    archive does not carry a bar at exactly the next session's open --
    same edge case, same NO_FILL_BAR handling, as `box_theory.resolution.
    fill_bar_after_candle_close`; no cross-day roll-forward is implemented,
    per PREREGISTRATION_FVG.md Section 5a)."""
    row = bars1[bars1["ts"] == close_ts]
    return row.iloc[0] if len(row) else None


def _entry_from_trigger(candles: pd.DataFrame, bars1: pd.DataFrame, trigger_idx: int, gap: dict) -> dict:
    """Shared fill + 0.5% floor + sizing step for both configurations,
    once a trigger candle index has been found. Returns a dict with
    `status` in {"NO_FILL_BAR", "STOP_TOO_TIGHT", "ZERO_QTY", "ENTERED"}."""
    trigger = candles.iloc[trigger_idx]
    fill_bar = fill_bar_after_close(bars1, trigger["bucket_end"])
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", "trigger_idx": trigger_idx}

    entry_price = float(fill_bar["open"])
    gap_low = gap["gap_low"]
    room_pct = (entry_price - gap_low) / entry_price if entry_price else -1.0
    if room_pct < STOP_TOO_TIGHT_PCT:
        return {
            "status": "STOP_TOO_TIGHT", "trigger_idx": trigger_idx,
            "fill_ts": pd.Timestamp(fill_bar["ts"]), "entry_price": entry_price, "room_pct": room_pct,
        }

    qty = position_size_shares(entry_price, gap_low)
    if qty < 1:
        return {
            "status": "ZERO_QTY", "trigger_idx": trigger_idx,
            "fill_ts": pd.Timestamp(fill_bar["ts"]), "entry_price": entry_price, "room_pct": room_pct,
        }

    return {
        "status": "ENTERED", "trigger_idx": trigger_idx, "fill_ts": pd.Timestamp(fill_bar["ts"]),
        "entry_price": entry_price, "room_pct": room_pct, "qty": qty,
        "stop_price": gap_low, "target_price": entry_price + TARGET_R_MULTIPLE * (entry_price - gap_low),
    }


# ---------------------------------------------------------------------
# Configuration A -- BREAKOUT (Section 5a)
# ---------------------------------------------------------------------

def evaluate_config_a(candles: pd.DataFrame, bars1: pd.DataFrame, gap: dict) -> dict:
    lo, hi = gap["live_start"], gap["live_end"]
    if lo > hi:
        return {"status": "SUPERSEDED" if gap["superseded"] else "EXPIRED_UNUSED"}

    closes = candles["close"].to_numpy()
    for idx in range(lo, hi + 1):
        if closes[idx] > gap["gap_high"]:
            return _entry_from_trigger(candles, bars1, idx, gap)

    return {"status": "SUPERSEDED" if gap["superseded"] else "EXPIRED_UNUSED"}


# ---------------------------------------------------------------------
# Configuration B -- RETEST (Section 5b)
# ---------------------------------------------------------------------

def evaluate_config_b(candles: pd.DataFrame, bars1: pd.DataFrame, gap: dict) -> dict:
    lo, hi = gap["live_start"], gap["live_end"]
    if lo > hi:
        status = "SUPERSEDED" if gap["superseded"] else "EXPIRED_UNUSED"
        return {"status": status, "touched": False}

    closes = candles["close"].to_numpy()
    lows = candles["low"].to_numpy()
    touched = False
    touch_idx = None

    for idx in range(lo, hi + 1):
        c = closes[idx]
        if c < gap["gap_low"]:
            return {"status": "INVALIDATED", "touched": touched, "invalidated_idx": idx}
        if not touched and lows[idx] <= gap["gap_high"]:
            touched = True
            touch_idx = idx
            continue  # the touch candle itself cannot also confirm
        if touched and idx > touch_idx and c > gap["gap_high"]:
            result = _entry_from_trigger(candles, bars1, idx, gap)
            result["touched"] = True
            return result

    status = "SUPERSEDED" if gap["superseded"] else "EXPIRED_UNUSED"
    return {"status": status, "touched": touched}


# ---------------------------------------------------------------------
# Exit resolution (Section 6): stop/target on 1-minute bars, time exit
# ---------------------------------------------------------------------

def resolve_exit(
    candles: pd.DataFrame, bars1: pd.DataFrame, entry: dict, entry_trade_date: dt.date,
) -> dict:
    """Scans the continuous 1-minute series from `entry["fill_ts"]`
    (inclusive) through the time-exit cutoff for the first bar whose
    low <= stop or high >= target -- STOP wins a same-bar tie. Falls back
    to the time exit (close of the 15:15 candle on the 5th NSE trading
    day after `entry_trade_date`, or the latest available candle at or
    before that time if the archive/continuous-series excision leaves a
    gap there) otherwise. Returns {"outcome": "STOP"|"TARGET"|"TIME_EXIT",
    "exit_price", "exit_ts", "time_exit_fallback": bool, "time_exit_date":
    date, "monitoring_gap_days": int}."""
    fill_ts = entry["fill_ts"]
    stop_price, target_price = entry["stop_price"], entry["target_price"]
    time_exit_date = nth_next_nse_trading_day(entry_trade_date, TIME_EXIT_TRADING_DAYS)

    ts_arr = bars1["ts"].to_numpy()
    lows = bars1["low"].to_numpy()
    highs = bars1["high"].to_numpy()
    opens = bars1["open"].to_numpy()

    fill_ts64 = np.datetime64(pd.Timestamp(fill_ts))
    cutoff_1519 = np.datetime64(pd.Timestamp(dt.datetime.combine(time_exit_date, STOP_SCAN_END_TIME)))

    window_mask = (ts_arr >= fill_ts64) & (ts_arr <= cutoff_1519)
    hit_idx = np.flatnonzero(window_mask & ((lows <= stop_price) | (highs >= target_price)))

    if len(hit_idx):
        i = int(hit_idx[0])
        hit_stop = lows[i] <= stop_price
        hit_target = highs[i] >= target_price
        if hit_stop:  # STOP wins a same-bar tie
            exit_price = float(opens[i]) if opens[i] <= stop_price else stop_price
            outcome = "STOP"
        else:
            exit_price = float(opens[i]) if opens[i] >= target_price else target_price
            outcome = "TARGET"
        return {
            "outcome": outcome, "exit_price": exit_price, "exit_ts": pd.Timestamp(ts_arr[i]),
            "time_exit_fallback": False, "time_exit_date": time_exit_date,
            "monitoring_gap_days": _monitoring_gap_days(candles, entry_trade_date, time_exit_date),
        }

    cutoff_1515 = np.datetime64(pd.Timestamp(dt.datetime.combine(time_exit_date, TIME_EXIT_TIME)))
    c_ts = candles["ts"].to_numpy()
    before = np.flatnonzero(c_ts <= cutoff_1515)
    if len(before) == 0:
        raise ValueError("no candle at or before the time-exit 15:15 cutoff -- cannot resolve a time exit")
    i = int(before[-1])
    used_fallback = bool(c_ts[i] != cutoff_1515)
    row = candles.iloc[i]
    return {
        "outcome": "TIME_EXIT", "exit_price": float(row["close"]), "exit_ts": pd.Timestamp(row["bucket_end"]),
        "time_exit_fallback": used_fallback, "time_exit_date": time_exit_date,
        "monitoring_gap_days": _monitoring_gap_days(candles, entry_trade_date, time_exit_date),
    }


def _monitoring_gap_days(candles: pd.DataFrame, entry_trade_date: dt.date, time_exit_date: dt.date) -> int:
    """How many NSE trading days strictly between entry and the time-exit
    date are MISSING from this entity's (already-excised) continuous
    candle series -- reported per PREREGISTRATION_FVG.md Section 6, near-
    zero expected since excision is rare (jump_guard/ex_date/bad_previous_
    session)."""
    present_dates = set(pd.Series(candles["trade_date"].to_numpy()).unique().tolist())
    expected = []
    cursor = entry_trade_date
    for _ in range(TIME_EXIT_TRADING_DAYS):
        cursor = nth_next_nse_trading_day(cursor, 1)
        expected.append(cursor)
    return sum(1 for day in expected if day not in present_dates)
