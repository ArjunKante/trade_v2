"""Box detection state machine, PREREGISTRATION_DARVAS.md Section 1 (and
its own recorded amendment to Section 1d). Walks ONE entity's own daily
OHLC history, in trading-day order, and produces every box that entity
forms, each resolved to exactly one of Section 1d's six outcomes. A pure
function of price history -- no position/sizing state (that is
resolution.py's job); the same box stream feeds both entry decisions and
trailing-stop raises there.

Implemented as two sequential phases per candidate, not one conditional
loop, because the mechanics genuinely differ before and after the top
confirms (Section 1c: "once the top is confirmed ... the top price is
FIXED -- it never rolls forward again, even if a later high exceeds it
... Bottom tracking continues ... until it confirms"):

  Phase A (top still rolling): both the top candidate (via HIGH) and the
    parallel bottom candidate (via LOW) can reset every day, in lockstep,
    exactly as Section 1c specifies, until the top's own 3-day count
    completes.
  Phase B (top fixed, trend filter already checked): only the bottom can
    still move (while unconfirmed); breakout/breakdown are judged on
    CLOSE alone, never on an intraday high/low, per Section 1d's literal
    wording ("adjusted_close[D'] > peak_price" / "<= trough_price").

Caller's responsibility, NOT this module's: slicing the input to
whichever window is currently authorized (DEV or, later, TEST) --
`darvas.test_seal` is never imported here, since this is a pure function
of whatever rows it is given; the backtest orchestration layer is where
the sealed-window guard actually lives.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BOX_LOOKBACK_DAYS = 200
CONFIRM_DAYS = 3
TREND_MA_DAYS = 50

OUTCOME_BROKE_OUT_BEFORE_BOTTOM = "BROKE_OUT_BEFORE_BOTTOM_CONFIRMED"
OUTCOME_COMPLETE_BREAKOUT = "COMPLETE_BREAKOUT"
OUTCOME_COMPLETE_BREAKDOWN = "COMPLETE_BREAKDOWN"
OUTCOME_COMPLETE_UNRESOLVED = "COMPLETE_UNRESOLVED_AT_WINDOW_END"
OUTCOME_TOP_NEVER_CONFIRMED = "TOP_NEVER_CONFIRMED_AT_WINDOW_END"
OUTCOME_BOTTOM_NEVER_CONFIRMED = "BOTTOM_NEVER_CONFIRMED_AT_WINDOW_END"
OUTCOME_TREND_FILTER_FAILED = "TREND_FILTER_FAILED"

# outcomes that leave a box with no confirmed bottom at all (no stop -> never tradeable)
INCOMPLETE_OUTCOMES = (OUTCOME_TREND_FILTER_FAILED, OUTCOME_BROKE_OUT_BEFORE_BOTTOM,
                       OUTCOME_TOP_NEVER_CONFIRMED, OUTCOME_BOTTOM_NEVER_CONFIRMED)
# outcomes with a fully confirmed top+bottom (a "complete" box, Section 1d)
COMPLETE_OUTCOMES = (OUTCOME_COMPLETE_BREAKOUT, OUTCOME_COMPLETE_BREAKDOWN, OUTCOME_COMPLETE_UNRESOLVED)


def detect_boxes(ohlc: pd.DataFrame) -> list[dict]:
    """`ohlc`: ONE entity's own daily rows, columns [trade_date,
    adjusted_open, adjusted_high, adjusted_low, adjusted_close], already
    sorted ascending by trade_date, with any jump-guard-flagged dates
    already dropped by the caller (PREREGISTRATION_DARVAS.md Section 0).
    Already clipped to whichever window is currently authorized to read
    (the caller's job, via darvas.test_seal) -- "window end" below always
    means "end of the rows actually passed in," nothing more.

    Returns a list of box dicts, in the order their 200-day-high triggers
    fired:
        peak_date, top_price, top_confirm_date (None if never confirmed),
        bottom_price (None if no bottom ever tracked to a level worth
        reporting), bottom_confirm_date (None unless confirmed),
        outcome, resolve_date (breakout/breakdown date, or None),
        same_day_top_bottom (bool).
    """
    n = len(ohlc)
    if n < BOX_LOOKBACK_DAYS:
        return []

    high = ohlc["adjusted_high"].to_numpy()
    low = ohlc["adjusted_low"].to_numpy()
    close = ohlc["adjusted_close"].to_numpy()
    dates = ohlc["trade_date"].to_numpy()

    # trailing 200-day high (inclusive of the day itself), only defined
    # once 200 full trading days of this entity's own history exist --
    # the warmup floor, Section 1 ("Warmup").
    roll_high200 = (
        ohlc["adjusted_high"].rolling(BOX_LOOKBACK_DAYS, min_periods=BOX_LOOKBACK_DAYS).max().to_numpy()
    )
    sma50 = ohlc["adjusted_close"].rolling(TREND_MA_DAYS, min_periods=TREND_MA_DAYS).mean().to_numpy()

    boxes: list[dict] = []
    i = BOX_LOOKBACK_DAYS - 1  # first index where roll_high200 is even defined

    while i < n:
        if np.isnan(roll_high200[i]) or high[i] < roll_high200[i]:
            i += 1
            continue

        box = _resolve_one_box(i, n, high, low, close, dates, sma50)
        boxes.append(box["record"])
        i = box["next_i"]

    return boxes


def _resolve_one_box(i: int, n: int, high, low, close, dates, sma50) -> dict:
    """Runs Phase A (top rolling) then, if the top confirms, checks the
    trend filter and runs Phase B (top fixed) to full resolution. Returns
    {"record": <box dict>, "next_i": <index to resume the outer scan at>}."""
    peak_idx = i
    peak_price = high[i]
    trough_idx = i
    trough_price = low[i]
    top_count = 0
    bottom_count = 0

    # ---- Phase A: top still rolling ----
    j = i + 1
    top_confirm_idx = None
    while j < n:
        if high[j] >= peak_price:
            peak_idx, peak_price = j, high[j]
            trough_idx, trough_price = j, low[j]
            top_count = 0
            bottom_count = 0
        else:
            top_count += 1
            if low[j] < trough_price:
                trough_idx, trough_price = j, low[j]
                bottom_count = 0
            else:
                bottom_count += 1
            if top_count == CONFIRM_DAYS:
                top_confirm_idx = j
                break
        j += 1

    if top_confirm_idx is None:
        # window ended while the top candidate was still rolling or still
        # within its own 3-day count -- nothing in this entity's
        # remaining history can form a NEW box either (it would need its
        # own fresh 200-day-high trigger, and there is no more data), so
        # the outer scan stops here.
        return {
            "record": _box_record(peak_idx, peak_price, None, None, None,
                                   OUTCOME_TOP_NEVER_CONFIRMED, None, False, dates),
            "next_i": n,
        }

    # ---- trend filter, Section 1b, evaluated at top_confirm_idx ----
    if np.isnan(sma50[top_confirm_idx]) or close[top_confirm_idx] <= sma50[top_confirm_idx]:
        return {
            "record": _box_record(peak_idx, peak_price, top_confirm_idx, None, None,
                                   OUTCOME_TREND_FILTER_FAILED, None, False, dates),
            "next_i": top_confirm_idx + 1,
        }

    same_day = bottom_count == CONFIRM_DAYS  # bottom already confirmed exactly when top did

    if same_day:
        bottom_confirm_idx = top_confirm_idx
        return _resolve_complete_box(peak_idx, peak_price, top_confirm_idx,
                                      trough_idx, trough_price, bottom_confirm_idx,
                                      True, n, close, dates)

    # ---- Phase B-pre-bottom: top fixed, bottom still tracking ----
    k = top_confirm_idx + 1
    while k < n:
        if close[k] > peak_price:
            return {
                "record": _box_record(peak_idx, peak_price, top_confirm_idx, trough_price, None,
                                       OUTCOME_BROKE_OUT_BEFORE_BOTTOM, k, False, dates),
                "next_i": k + 1,
            }
        if low[k] < trough_price:
            trough_idx, trough_price = k, low[k]
            bottom_count = 0
        else:
            bottom_count += 1
            if bottom_count == CONFIRM_DAYS:
                return _resolve_complete_box(peak_idx, peak_price, top_confirm_idx,
                                              trough_idx, trough_price, k,
                                              False, n, close, dates)
        k += 1

    # window ended with the top confirmed+valid but the bottom still
    # unresolved -- PREREGISTRATION_DARVAS.md Section 1d's amendment,
    # outcome 6.
    return {
        "record": _box_record(peak_idx, peak_price, top_confirm_idx, trough_price, None,
                               OUTCOME_BOTTOM_NEVER_CONFIRMED, None, False, dates),
        "next_i": n,
    }


def _resolve_complete_box(peak_idx, peak_price, top_confirm_idx, trough_idx, trough_price,
                           bottom_confirm_idx, same_day, n, close, dates) -> dict:
    """Phase B-post-bottom: both top and bottom fixed -- watch forward for
    a breakout or breakdown close, starting the day AFTER bottom confirms
    (the bottom-confirm day itself is the 3rd clean day; it cannot also
    be the breakout/breakdown day under this document's own rules, since
    a breakout/breakdown close would itself have reset or ended the
    bottom count before it ever reached 3 -- Phase B-pre-bottom's own
    loop already checks breakout on every candidate day before checking
    the low)."""
    m = bottom_confirm_idx + 1
    while m < n:
        if close[m] > peak_price:
            return {
                "record": _box_record(peak_idx, peak_price, top_confirm_idx, trough_price,
                                       bottom_confirm_idx, OUTCOME_COMPLETE_BREAKOUT, m, same_day, dates),
                "next_i": m + 1,
            }
        if close[m] <= trough_price:
            return {
                "record": _box_record(peak_idx, peak_price, top_confirm_idx, trough_price,
                                       bottom_confirm_idx, OUTCOME_COMPLETE_BREAKDOWN, m, same_day, dates),
                "next_i": m + 1,
            }
        m += 1

    return {
        "record": _box_record(peak_idx, peak_price, top_confirm_idx, trough_price,
                               bottom_confirm_idx, OUTCOME_COMPLETE_UNRESOLVED, None, same_day, dates),
        "next_i": n,
    }


def _box_record(peak_idx, top_price, top_confirm_idx, bottom_price, bottom_confirm_idx,
                 outcome, resolve_idx, same_day_top_bottom, dates) -> dict:
    """`*_idx` fields (alongside the `*_date` fields the pre-registration
    names) are plumbing for resolution.py -- integer positions into the
    SAME `ohlc` array `detect_boxes` was called with, avoiding a
    date-indexed lookup (and its ambiguity on a non-trading date) at the
    simulation layer."""
    return {
        "peak_date": pd.Timestamp(dates[peak_idx]), "peak_idx": peak_idx,
        "top_price": float(top_price),
        "top_confirm_date": pd.Timestamp(dates[top_confirm_idx]) if top_confirm_idx is not None else None,
        "top_confirm_idx": top_confirm_idx,
        "bottom_price": float(bottom_price) if bottom_price is not None else None,
        "bottom_confirm_date": pd.Timestamp(dates[bottom_confirm_idx]) if bottom_confirm_idx is not None else None,
        "bottom_confirm_idx": bottom_confirm_idx,
        "outcome": outcome,
        "resolve_date": pd.Timestamp(dates[resolve_idx]) if resolve_idx is not None else None,
        "resolve_idx": resolve_idx,
        "same_day_top_bottom": bool(same_day_top_bottom),
    }
