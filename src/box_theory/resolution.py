"""The mechanical trade-management core of PREREGISTRATION_BOX.md Section
3: touch, FAST/SLOW confirmation, entry fill, the 3% stop (checked on
1-minute bars), arming (5-minute candle high vs. 0.995 x PREV_HIGH), the
FAST/SLOW red-candle armed exit, and the 15:15-candle time exit.

All price arguments are assumed already converted to day D's RAW rupee
scale (fibo.scale_probe's scale factor applied upstream, by the caller --
see src/box_theory/backtest.py and PREREGISTRATION_BOX.md Section 2b).
Every function here is pure (no DB access), to make the 5-hand-traced
examples (PREREGISTRATION_BOX.md Process Step 2) reproducible in
isolation and unit-testable without a live warehouse connection.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

FIXED_RISK_RS = 500.0
STOP_PCT = 0.03
ARMING_PCT = 0.995
ROOM_PCT = 0.01

ENTRY_WINDOW_START = dt.time(9, 30)
ENTRY_WINDOW_END = dt.time(14, 30)
TIME_EXIT_CANDLE_TS = dt.time(15, 15)
# last 1-minute bar still checked for a stop before the 15:15 candle's own
# close forces a time exit (the 15:15 candle covers 15:15-15:20)
STOP_SCAN_END_TIME = dt.time(15, 19)

CONFIG_NAMES = ("FAST", "SLOW")


# ---------------------------------------------------------------------
# Touch and confirmation (Section 3a/3b)
# ---------------------------------------------------------------------

def find_touch_idx(candles5: pd.DataFrame, prev_low: float) -> int | None:
    """Index (into candles5, 0-based, session order) of the first 5-minute
    candle with low <= prev_low. None if the day never touches."""
    hits = candles5.index[candles5["low"] <= prev_low]
    return int(hits[0]) if len(hits) else None


def find_fast_confirmation(candles5: pd.DataFrame, after_idx: int) -> int | None:
    """FAST: index of the first green candle strictly after `after_idx`.
    Reads the `is_green` column into a plain numpy array ONCE rather than
    using `.iloc[i]` per candle inside the loop -- `.iloc` row access
    profiled at a significant fraction of total runtime at this study's
    scale (~10^5-10^6 entity-days), since every row-slice forces pandas
    to build a fresh, mixed-dtype Series each call."""
    is_green = candles5["is_green"].to_numpy()
    for i in range(after_idx + 1, len(is_green)):
        if is_green[i]:
            return i
    return None


def find_slow_confirmation(candles5: pd.DataFrame, after_idx: int) -> tuple[int, int] | None:
    """SLOW: (i, i+1) of the first two consecutive green candles, both
    strictly after `after_idx`, where candle i+1's close also exceeds
    candle i's close."""
    is_green = candles5["is_green"].to_numpy()
    closes = candles5["close"].to_numpy()
    for i in range(after_idx + 1, len(is_green) - 1):
        if is_green[i] and is_green[i + 1] and closes[i + 1] > closes[i]:
            return i, i + 1
    return None


def find_fast_exit(candles5: pd.DataFrame, after_idx: int) -> int | None:
    """FAST armed exit: index of the first red candle strictly after
    `after_idx` (the arming candle)."""
    is_red = candles5["is_red"].to_numpy()
    for i in range(after_idx + 1, len(is_red)):
        if is_red[i]:
            return i
    return None


def find_slow_exit(candles5: pd.DataFrame, after_idx: int) -> tuple[int, int] | None:
    """SLOW armed exit: (i, i+1) of the first two consecutive red candles,
    both strictly after `after_idx`. No close-relationship condition is
    applied here -- the instruction states one only for SLOW's entry pair
    (PREREGISTRATION_BOX.md Section 3e)."""
    is_red = candles5["is_red"].to_numpy()
    for i in range(after_idx + 1, len(is_red) - 1):
        if is_red[i] and is_red[i + 1]:
            return i, i + 1
    return None


def fill_bar_after_candle_close(bars1: pd.DataFrame, candle_close_ts: pd.Timestamp) -> pd.Series | None:
    """The 1-minute bar whose ts equals the confirming candle's own close
    time (= its bucket start + 5min, which is exactly the next bucket's
    first minute) -- "fill at the open of the next 1-minute bar after the
    confirming candle closes." None if no such bar exists (confirmation
    fell on the session's last candle)."""
    row = bars1[bars1["ts"] == candle_close_ts]
    return row.iloc[0] if len(row) else None


# ---------------------------------------------------------------------
# Position sizing (Section 4)
# ---------------------------------------------------------------------

def position_size_shares(entry_price: float, fixed_risk_rs: float = FIXED_RISK_RS,
                          stop_pct: float = STOP_PCT) -> int:
    """qty = floor(500 / (0.03 x entry)) -- whole shares only, floored
    (never rounded up, to never risk more than fixed_risk_rs)."""
    per_share_risk = stop_pct * entry_price
    if per_share_risk <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    return math.floor(fixed_risk_rs / per_share_risk)


# ---------------------------------------------------------------------
# Entry signal (Section 3a-3c): touch -> confirmation -> fill -> room filter
# ---------------------------------------------------------------------

def find_entry(candles5: pd.DataFrame, bars1: pd.DataFrame, prev_high: float, prev_low: float,
               config: str) -> dict:
    """Returns a dict with at least {"status": ...}. status is one of:
    "NO_TOUCH", "NO_CONFIRMATION", "NO_FILL_BAR", "FILL_OUTSIDE_WINDOW",
    "NO_ROOM", "ZERO_QTY", "ENTERED". On "ENTERED", also includes
    touch_idx, confirm_end_idx (index of the LAST confirming candle),
    entry_candle_idx (= confirm_end_idx + 1, the candle whose bucket
    contains the fill), fill_ts, entry_price, qty."""
    if config not in CONFIG_NAMES:
        raise ValueError(f"config must be one of {CONFIG_NAMES}, got {config!r}")

    touch_idx = find_touch_idx(candles5, prev_low)
    if touch_idx is None:
        return {"status": "NO_TOUCH"}

    if config == "FAST":
        confirm = find_fast_confirmation(candles5, touch_idx)
        confirm_end_idx = confirm
    else:
        pair = find_slow_confirmation(candles5, touch_idx)
        confirm_end_idx = pair[1] if pair else None

    if confirm_end_idx is None:
        return {"status": "NO_CONFIRMATION", "touch_idx": touch_idx}

    confirm_candle = candles5.iloc[confirm_end_idx]
    confirm_close_ts = confirm_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, confirm_close_ts)
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", "touch_idx": touch_idx, "confirm_end_idx": confirm_end_idx}

    fill_ts = pd.Timestamp(fill_bar["ts"])
    fill_time = fill_ts.time()
    if not (ENTRY_WINDOW_START <= fill_time <= ENTRY_WINDOW_END):
        return {
            "status": "FILL_OUTSIDE_WINDOW", "touch_idx": touch_idx,
            "confirm_end_idx": confirm_end_idx, "fill_ts": fill_ts,
        }

    entry_price = float(fill_bar["open"])
    if (prev_high - entry_price) / entry_price < ROOM_PCT:
        return {
            "status": "NO_ROOM", "touch_idx": touch_idx, "confirm_end_idx": confirm_end_idx,
            "fill_ts": fill_ts, "entry_price": entry_price,
        }

    qty = position_size_shares(entry_price)
    if qty < 1:
        return {
            "status": "ZERO_QTY", "touch_idx": touch_idx, "confirm_end_idx": confirm_end_idx,
            "fill_ts": fill_ts, "entry_price": entry_price,
        }

    return {
        "status": "ENTERED", "touch_idx": touch_idx, "confirm_end_idx": confirm_end_idx,
        "entry_candle_idx": confirm_end_idx + 1, "fill_ts": fill_ts,
        "entry_price": entry_price, "qty": qty,
    }


# ---------------------------------------------------------------------
# Exit resolution (Section 3d-3f): stop, arming + red-candle exit, time exit
# ---------------------------------------------------------------------

def _stop_event(bars1: pd.DataFrame, fill_ts: pd.Timestamp, stop_price: float) -> pd.Series | None:
    """First 1-minute bar, starting with the entry bar itself (ts ==
    fill_ts) through STOP_SCAN_END_TIME, whose low <= stop_price.
    `bars1` is assumed already ts-sorted (every caller sources it from
    box_theory.context's day-grouped, ts-sorted frames) -- avoids a
    `.dt.time` extraction and a redundant `sort_values` per call, both
    measurable at this study's null-simulation scale."""
    ts = bars1["ts"].to_numpy()
    fill_ts64 = np.datetime64(pd.Timestamp(fill_ts))
    cutoff_ts64 = np.datetime64(pd.Timestamp(fill_ts).normalize() + pd.Timedelta(hours=15, minutes=19))
    lows = bars1["low"].to_numpy()
    mask = (ts >= fill_ts64) & (ts <= cutoff_ts64) & (lows <= stop_price)
    idx = np.flatnonzero(mask)
    return bars1.iloc[int(idx[0])] if len(idx) else None


def _arming_idx(candles5: pd.DataFrame, entry_candle_idx: int, prev_high: float) -> int | None:
    """First candle index >= entry_candle_idx, bounded to ts <=
    TIME_EXIT_CANDLE_TS, with high >= ARMING_PCT x prev_high. Vectorized
    (see find_fast_confirmation's docstring for why `.iloc`-per-candle is
    avoided here too)."""
    threshold = ARMING_PCT * prev_high
    cutoff_ts = candles5["ts"].iloc[0].normalize() + pd.Timedelta(hours=15, minutes=15)
    highs = candles5["high"].to_numpy()
    in_bounds = (candles5["ts"] <= cutoff_ts).to_numpy()
    for i in range(entry_candle_idx, len(highs)):
        if not in_bounds[i]:
            break
        if highs[i] >= threshold:
            return i
    return None


def _armed_exit_event(candles5: pd.DataFrame, bars1: pd.DataFrame, arming_idx: int, config: str) -> pd.Series | None:
    """The 1-minute fill bar for the armed red-candle exit, bounded so the
    confirming candle(s) close at or before the 15:15 candle's own close
    -- a confirmation that would only complete later is moot, since the
    time exit already closes the trade at that point (PREREGISTRATION_
    BOX.md Section 3f).

    `candles5` is time-ordered (aggregate_to_5min's own construction), so
    the ts<=cutoff mask is always a PREFIX -- bounding it is just a
    truncation, not a re-indexed sub-frame, so `arming_idx` needs no
    translation into a separate "bounded" index space (the previous
    version re-looked-up arming_idx by ts equality every call; avoided
    here, along with the `.dt.time` extraction -- both showed up as real
    cost at this study's null-simulation scale, ~10^7-10^8 calls)."""
    ts_col = candles5["ts"]
    cutoff_ts = ts_col.iloc[0].normalize() + pd.Timedelta(hours=15, minutes=15)
    in_bounds = ts_col.to_numpy() <= np.datetime64(cutoff_ts)
    last_valid = np.flatnonzero(in_bounds)
    if len(last_valid) == 0 or arming_idx >= last_valid[-1] + 1:
        return None
    bound_len = int(last_valid[-1]) + 1
    bounded = candles5.iloc[:bound_len]

    if config == "FAST":
        exit_idx = find_fast_exit(bounded, arming_idx)
    else:
        pair = find_slow_exit(bounded, arming_idx)
        exit_idx = pair[1] if pair else None
    if exit_idx is None:
        return None

    exit_close_ts = ts_col.iloc[exit_idx] + pd.Timedelta(minutes=5)
    return fill_bar_after_candle_close(bars1, exit_close_ts)


def resolve_exit(candles5: pd.DataFrame, bars1: pd.DataFrame, entry_candle_idx: int, fill_ts: pd.Timestamp,
                  entry_price: float, prev_high: float, config: str) -> dict:
    """Returns {"outcome": "STOP"|"ARMED_EXIT"|"TIME_EXIT", "exit_price":
    float, "exit_ts": Timestamp, "armed": bool, "time_exit_fallback": bool}.
    `time_exit_fallback` is True only for a TIME_EXIT whose own day had no
    candle exactly at 15:15 (see that branch below) -- False for every
    other outcome, and False for a TIME_EXIT that found the real 15:15
    candle normally. Tracked so a caller can report how often the
    fallback actually fires, per PREREGISTRATION_BOX.md Section 8's
    reporting requirements."""
    stop_price = entry_price * (1 - STOP_PCT)

    stop_bar = _stop_event(bars1, fill_ts, stop_price)
    stop_ts = pd.Timestamp(stop_bar["ts"]) if stop_bar is not None else None

    arming_idx = _arming_idx(candles5, entry_candle_idx, prev_high)
    armed_bar = None
    armed_ts = None
    if arming_idx is not None:
        armed_bar = _armed_exit_event(candles5, bars1, arming_idx, config)
        armed_ts = pd.Timestamp(armed_bar["ts"]) if armed_bar is not None else None

    # STOP wins a same-bar tie, and wins outright whenever it occurs no
    # later than the armed exit (an earlier stop on a prior bar pre-empts
    # an armed exit that would only resolve later anyway)
    if stop_ts is not None and (armed_ts is None or stop_ts <= armed_ts):
        exit_price = float(stop_bar["open"]) if stop_bar["open"] <= stop_price else stop_price
        return {"outcome": "STOP", "exit_price": exit_price, "exit_ts": stop_ts, "armed": arming_idx is not None,
                "time_exit_fallback": False}

    if armed_ts is not None:
        return {
            "outcome": "ARMED_EXIT", "exit_price": float(armed_bar["open"]), "exit_ts": armed_ts,
            "armed": True, "time_exit_fallback": False,
        }

    day_start = candles5["ts"].iloc[0].normalize()
    time_exit_ts = np.datetime64(day_start + pd.Timedelta(hours=15, minutes=15))
    ts_arr = candles5["ts"].to_numpy()
    time_exit_rows = np.flatnonzero(ts_arr == time_exit_ts)
    used_fallback = False
    if len(time_exit_rows) > 0:
        row_idx = int(time_exit_rows[0])
    else:
        # The archive does not always reach 15:15 for a given stock-day
        # (an afternoon trading halt, or a genuine data gap after entry
        # but before close) -- not covered by any Section 2b eligibility
        # check, which only validates the PREVIOUS session's completeness,
        # not today's. Same fallback fibo.resolution.resolve_trade already
        # uses for its own "exit bar missing" case: take the latest candle
        # at or before the target time, rather than raising. An entry
        # already succeeded, so at minimum the entry candle itself is
        # <= 15:15 -- this can only be empty if that invariant is broken
        # elsewhere, so the ValueError below is a real defensive floor,
        # not a case expected to fire in practice.
        before_rows = np.flatnonzero(ts_arr <= time_exit_ts)
        if len(before_rows) == 0:
            raise ValueError("no candle at or before 15:15 for this day -- cannot resolve a time exit")
        row_idx = int(before_rows[-1])
        used_fallback = True
    row = candles5.iloc[row_idx]
    return {
        "outcome": "TIME_EXIT", "exit_price": float(row["close"]), "exit_ts": row["ts"] + pd.Timedelta(minutes=5),
        "armed": arming_idx is not None, "time_exit_fallback": used_fallback,
    }


# ---------------------------------------------------------------------
# Array-native fast path -- semantically identical to resolve_exit above,
# used ONLY by box_theory.nulls (PREREGISTRATION_BOX.md Section 6), which
# calls this on the order of 10^7-10^8 times across 1000 seeds x 2 null
# types x 2 configs. Every pandas DataFrame/Series operation in the
# resolve_exit path above (`.iloc`, `.to_numpy()`, `.dt.time`, boolean-
# mask sub-frames) carries fixed per-call overhead that is negligible
# once (per entity-day, in the main backtest) but dominates at null-draw
# scale -- this path takes plain numpy arrays, extracted ONCE per context
# by box_theory.nulls.prepare_ctx, not re-extracted per draw. Cross-
# checked for identical output against resolve_exit on real archive days
# before use (see tests/test_box_theory_resolution.py).
# ---------------------------------------------------------------------

def _array_fast_idx(bool_arr: np.ndarray, after_idx: int) -> int | None:
    for i in range(after_idx + 1, len(bool_arr)):
        if bool_arr[i]:
            return i
    return None


def _array_slow_pair(bool_arr: np.ndarray, after_idx: int) -> int | None:
    """Index of the SECOND candle of the first consecutive True-True pair
    strictly after `after_idx`. No close-relationship condition (matches
    find_slow_exit, the red-candle exit side -- see its own docstring)."""
    n = len(bool_arr)
    for i in range(after_idx + 1, n - 1):
        if bool_arr[i] and bool_arr[i + 1]:
            return i + 1
    return None


def resolve_exit_arrays(
    c5_ts: np.ndarray, c5_open: np.ndarray, c5_high: np.ndarray, c5_close: np.ndarray,
    c5_is_red: np.ndarray, b1_ts: np.ndarray, b1_open: np.ndarray, b1_low: np.ndarray,
    entry_candle_idx: int, fill_ts64: np.datetime64, entry_price: float, prev_high: float, config: str,
) -> dict:
    """Same rules as resolve_exit, operating on raw numpy arrays. Returns
    {"outcome", "exit_price", "exit_ts" (np.datetime64), "armed"}."""
    stop_price = entry_price * (1 - STOP_PCT)
    day_start = c5_ts[0].astype("datetime64[D]").astype(c5_ts.dtype)
    cutoff_1519 = day_start + np.timedelta64(15 * 60 + 19, "m")
    cutoff_1515 = day_start + np.timedelta64(15 * 60 + 15, "m")

    stop_mask = (b1_ts >= fill_ts64) & (b1_ts <= cutoff_1519) & (b1_low <= stop_price)
    stop_hits = np.flatnonzero(stop_mask)
    stop_idx = int(stop_hits[0]) if len(stop_hits) else None
    stop_ts = b1_ts[stop_idx] if stop_idx is not None else None

    in_bounds_5 = c5_ts <= cutoff_1515
    last_valid = np.flatnonzero(in_bounds_5)
    bound_len = int(last_valid[-1]) + 1 if len(last_valid) else 0

    threshold = ARMING_PCT * prev_high
    arming_idx = None
    for i in range(entry_candle_idx, bound_len):
        if c5_high[i] >= threshold:
            arming_idx = i
            break

    armed_ts = None
    armed_open = None
    if arming_idx is not None:
        if config == "FAST":
            exit_idx = _array_fast_idx(c5_is_red[:bound_len], arming_idx)
        else:
            exit_idx = _array_slow_pair(c5_is_red[:bound_len], arming_idx)
        if exit_idx is not None:
            exit_close_ts = c5_ts[exit_idx] + np.timedelta64(5, "m")
            fill_hits = np.flatnonzero(b1_ts == exit_close_ts)
            if len(fill_hits):
                fh = int(fill_hits[0])
                armed_ts = b1_ts[fh]
                armed_open = b1_open[fh]

    if stop_idx is not None and (armed_ts is None or stop_ts <= armed_ts):
        o = b1_open[stop_idx]
        exit_price = float(o) if o <= stop_price else stop_price
        return {"outcome": "STOP", "exit_price": exit_price, "exit_ts": stop_ts, "armed": arming_idx is not None,
                "time_exit_fallback": False}

    if armed_ts is not None:
        return {"outcome": "ARMED_EXIT", "exit_price": float(armed_open), "exit_ts": armed_ts, "armed": True,
                "time_exit_fallback": False}

    te_hits = np.flatnonzero(c5_ts == cutoff_1515)
    used_fallback = False
    if len(te_hits) > 0:
        i = int(te_hits[0])
    else:
        # see resolve_exit's identical fallback for why: the archive does
        # not always reach 15:15 for a given stock-day, and this is not
        # caught by any Section 2b eligibility check (those only validate
        # the PREVIOUS session). Take the latest candle at or before 15:15.
        before_hits = np.flatnonzero(c5_ts <= cutoff_1515)
        if len(before_hits) == 0:
            raise ValueError("no candle at or before 15:15 for this day -- cannot resolve a time exit")
        i = int(before_hits[-1])
        used_fallback = True
    return {
        "outcome": "TIME_EXIT", "exit_price": float(c5_close[i]), "exit_ts": c5_ts[i] + np.timedelta64(5, "m"),
        "armed": arming_idx is not None, "time_exit_fallback": used_fallback,
    }
