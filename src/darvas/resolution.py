"""Position resolution and trailing-stop engine, PREREGISTRATION_DARVAS.md
Section 2. Consumes ONE entity's `boxes.detect_boxes` output plus its own
daily OHLC rows and produces this entity's own trade list -- box detection
itself has no notion of a position; this module is where "flat" vs. "long"
state, entry/exit timing, and the two trailing-stop sub-rules actually
live.

`_run_position` is the one place the exit/trailing mechanics are written.
`simulate_entity` (the real strategy) and `darvas.nulls`'s TIMING null
(Section "Nulls") both call it -- the TIMING null needs the IDENTICAL
exit/trailing logic from a different entry point, per PREREGISTRATION_
DARVAS.md's own instruction ("same stop logic"); duplicating the loop
there would risk the two silently drifting apart.

Ordering, every day while LONG (Section 2's own stated order, never
varied): (1) check EXIT first, against the stop level fixed using data
only through YESTERDAY's close -- a trade is never exited and have its
own exit-day stop simultaneously "raised" using same-day information;
(2) only if not exited, update the stop for TOMORROW using today's data
(Sub-rule 1, new box above, checked first; Sub-rule 2, run well above
with no new box, checked only if Sub-rule 1 did not itself raise the
stop today).
"""
from __future__ import annotations

import bisect

import pandas as pd

from darvas.boxes import COMPLETE_OUTCOMES, detect_boxes
from darvas.costs import net_r, position_size_shares, round_trip_cost_rs_midpoint

RUN_THRESHOLD_R = 2.0  # PREREGISTRATION_DARVAS.md Section 2, Sub-rule 2 -- a filled gap, not a tuned value

EXIT_STOP = "STOP"
EXIT_FORCED_WINDOW_CLOSE = "FORCED_WINDOW_CLOSE"


def sorted_complete_boxes(boxes: list[dict]) -> list[dict]:
    """Every box with a confirmed bottom (Section 1d's COMPLETE_* outcomes),
    ordered by when that bottom confirmed -- the order Sub-rule 1 (new box
    above) needs to walk forward through. Shared helper so `simulate_
    entity` and `darvas.nulls`'s TIMING null build this list identically."""
    return sorted((b for b in boxes if b["outcome"] in COMPLETE_OUTCOMES),
                  key=lambda b: b["bottom_confirm_idx"])


def _run_position(dates, opens, closes, n, entity_id,
                   entry_idx: int, entry_price: float, initial_stop: float, entry_box_top: float,
                   entry_box_ref, complete_boxes: list[dict], cb_ptr_start: int,
                   use_new_box_rule: bool) -> dict | None:
    """Runs the LONG state starting the day AFTER `entry_idx` (the fill
    day itself has no exit/stop-update check -- the stop in effect on the
    fill day is simply `initial_stop`) until exit or the data runs out.
    Returns None if `qty` would be 0 (Section 3's ZERO_QTY_SKIP -- the
    caller must check for this and count it; this function never raises
    for a legitimately-zero quantity, only for a malformed entry/stop
    pair). `use_new_box_rule=False` is the nulls' own stated
    simplification (PREREGISTRATION_DARVAS.md "Nulls" section): Sub-rule 2
    (run well above) only, since a synthetic entry has no real box
    lineage to search forward through for Sub-rule 1."""
    qty = position_size_shares(entry_price, initial_stop)
    if qty <= 0:
        return None

    rho = (entry_price - initial_stop) / entry_price
    current_stop = initial_stop
    stop_history = [{"date": pd.Timestamp(dates[entry_idx]), "stop": initial_stop,
                      "reason": "INITIAL", "box": entry_box_ref}]
    cb_ptr = cb_ptr_start
    run_trigger = entry_box_top + RUN_THRESHOLD_R * (entry_price - initial_stop)

    t = entry_idx + 1
    while True:
        if t >= n:
            t = n - 1  # data ended exactly at entry with nothing after -- force-close at entry's own close
            return _finalize_trade(entity_id, entry_idx, entry_price, initial_stop, current_stop,
                                    entry_box_top, rho, qty, stop_history, t, float(closes[t]),
                                    EXIT_FORCED_WINDOW_CLOSE, dates)

        if closes[t] < current_stop:
            return _finalize_trade(entity_id, entry_idx, entry_price, initial_stop, current_stop,
                                    entry_box_top, rho, qty, stop_history, t, float(closes[t]),
                                    EXIT_STOP, dates)

        if t == n - 1:
            return _finalize_trade(entity_id, entry_idx, entry_price, initial_stop, current_stop,
                                    entry_box_top, rho, qty, stop_history, t, float(closes[t]),
                                    EXIT_FORCED_WINDOW_CLOSE, dates)

        raised_today = False
        if use_new_box_rule:
            while cb_ptr < len(complete_boxes) and complete_boxes[cb_ptr]["bottom_confirm_idx"] <= t:
                cb = complete_boxes[cb_ptr]
                cb_ptr += 1
                if cb is entry_box_ref:
                    continue
                if cb["bottom_price"] > current_stop:
                    current_stop = float(cb["bottom_price"])
                    raised_today = True
                    stop_history.append({"date": pd.Timestamp(dates[t]), "stop": current_stop,
                                          "reason": "NEW_BOX", "box": cb})

        if not raised_today and closes[t] >= run_trigger:
            candidate = float(closes[t] * (1 - rho))
            if candidate > current_stop:
                current_stop = candidate
                stop_history.append({"date": pd.Timestamp(dates[t]), "stop": candidate,
                                      "reason": "RUN_UP", "box": None})
        t += 1


def _finalize_trade(entity_id, entry_idx, entry_price, initial_stop, final_stop, entry_box_top,
                     rho, qty, stop_history, exit_idx, exit_price, exit_reason, dates) -> dict:
    pnl_rs = qty * (exit_price - entry_price)
    position_size_rs = qty * entry_price
    cost_rs = round_trip_cost_rs_midpoint(position_size_rs)
    r = net_r(pnl_rs, position_size_rs)
    entry_date = pd.Timestamp(dates[entry_idx])
    exit_date = pd.Timestamp(dates[exit_idx])
    return {
        "entity_id": entity_id,
        "trade_date": entry_date,  # the day-clustering key, box_theory.inference convention
        "entry_date": entry_date, "entry_price": entry_price,
        "exit_date": exit_date, "exit_price": exit_price, "exit_reason": exit_reason,
        "qty": qty, "position_size_rs": position_size_rs,
        "initial_stop": initial_stop, "final_stop": final_stop,
        "entry_box_top": entry_box_top, "entry_box_bottom": initial_stop,
        "rho": rho,
        "pnl_rs": pnl_rs, "cost_rs": cost_rs, "net_r": r,
        "holding_days": int((exit_date - entry_date).days),
        "holding_trading_days": exit_idx - entry_idx,
        "n_stop_raises": sum(1 for h in stop_history if h["reason"] != "INITIAL"),
        "stop_history": stop_history,
        "year": entry_date.year,
        "exit_idx": exit_idx,  # plumbing for the caller's own index-based resume; not a report field
    }


def simulate_entity(ohlc: pd.DataFrame, entity_id: str) -> dict:
    """`ohlc`: ONE entity's own daily rows (already clipped to whichever
    window is currently authorized -- the caller's job via darvas.
    test_seal; this module never imports it, same separation `boxes.py`
    already keeps). Returns {"trades": [...], "boxes": [...],
    "zero_qty_skips": int, "breakouts_skipped_in_position": int}."""
    boxes = detect_boxes(ohlc)
    n = len(ohlc)
    if n == 0:
        return {"trades": [], "boxes": boxes, "zero_qty_skips": 0, "breakouts_skipped_in_position": 0}

    dates = ohlc["trade_date"].to_numpy()
    opens = ohlc["adjusted_open"].to_numpy()
    closes = ohlc["adjusted_close"].to_numpy()

    complete_boxes = sorted_complete_boxes(boxes)
    breakout_boxes = sorted((b for b in boxes if b["outcome"] == "COMPLETE_BREAKOUT"),
                             key=lambda b: b["resolve_idx"])

    trades: list[dict] = []
    zero_qty_skips = 0
    breakouts_skipped_in_position = 0

    bo_ptr = 0
    t = 0

    # bottom_confirm_idx of every complete box, for a per-entry bisect --
    # PREREGISTRATION_DARVAS.md Section 2 Sub-rule 1's own amendment:
    # "later box" means confirmed STRICTLY AFTER the CURRENT position's
    # own entry date, recomputed fresh at each entry (never carried over
    # from a prior, already-closed position in this same entity).
    complete_bottom_idxs = [cb["bottom_confirm_idx"] for cb in complete_boxes]

    while t < n:
        while bo_ptr < len(breakout_boxes) and breakout_boxes[bo_ptr]["resolve_idx"] + 1 < t:
            breakouts_skipped_in_position += 1
            bo_ptr += 1
        if bo_ptr < len(breakout_boxes) and breakout_boxes[bo_ptr]["resolve_idx"] + 1 == t:
            box = breakout_boxes[bo_ptr]
            bo_ptr += 1
            entry_price = float(opens[t])
            initial_stop = float(box["bottom_price"])
            if entry_price <= initial_stop:
                # defensive only: should not occur on real data (a box's
                # own top > bottom always, and entry requires a close
                # above the top the day before) -- skip rather than
                # divide by a non-positive risk if it ever does.
                t += 1
                continue
            cb_ptr = bisect.bisect_right(complete_bottom_idxs, t)  # strictly after entry_idx == t
            trade = _run_position(dates, opens, closes, n, entity_id, t, entry_price, initial_stop,
                                   float(box["top_price"]), box, complete_boxes, cb_ptr, use_new_box_rule=True)
            if trade is None:
                zero_qty_skips += 1
                t += 1
                continue
            trades.append(trade)
            t = trade["exit_idx"] + 1
            continue
        t += 1

    return {
        "trades": trades, "boxes": boxes,
        "zero_qty_skips": zero_qty_skips,
        "breakouts_skipped_in_position": breakouts_skipped_in_position,
    }
