"""PREREGISTRATION_FVG.md Section 4: scan a per-entity continuous 1-hour
candle timeline (`fvg.context.build_entity_timeline`'s own "candles"
frame, ONE contiguous run of calendar-consecutive eligible days -- see
`fvg.backtest`'s run-assembly) for every valid Fair Value Gap, apply the
inside-bar and no-overnight-pattern filters, and apply the most-recent-
gap-wins supersession rule (truncate an older live gap's window to end
right before the next gap's own formation).
"""
from __future__ import annotations

import pandas as pd

LIVE_WINDOW_CANDLES = 30


def find_valid_gaps(candles: pd.DataFrame) -> dict:
    """`candles`: one contiguous run's global-indexed 1-hour candles,
    columns include high/low/close/trade_date/band/rank/year (as built by
    `fvg.context.build_entity_timeline`). Returns {"gaps": [gap dict, ...]
    (ascending c3_idx, supersession already applied), "inside_bar_rejected":
    int, "overnight_excluded": int}. Each gap dict: {"c1_idx", "c2_idx",
    "c3_idx", "gap_low", "gap_high", "formed_trade_date", "band", "rank",
    "year", "live_start", "live_end" (post-supersession), "superseded"
    (bool)}."""
    n = len(candles)
    if n < 3:
        return {"gaps": [], "inside_bar_rejected": 0, "overnight_excluded": 0}

    highs = candles["high"].to_numpy()
    lows = candles["low"].to_numpy()
    trade_dates = candles["trade_date"].to_numpy()
    bands = candles["band"].to_numpy()
    ranks = candles["rank"].to_numpy()
    years = candles["year"].to_numpy()

    gaps: list[dict] = []
    inside_bar_rejected = 0
    overnight_excluded = 0

    for i in range(n - 2):
        j, k = i + 1, i + 2
        if not (highs[i] < lows[k]):
            continue
        if not (trade_dates[i] == trade_dates[j] and trade_dates[j] == trade_dates[k]):
            overnight_excluded += 1
            continue
        if highs[j] <= highs[i] and lows[j] >= lows[i]:
            inside_bar_rejected += 1
            continue

        live_start = k + 1
        live_end = min(k + LIVE_WINDOW_CANDLES, n - 1)
        gaps.append({
            "c1_idx": i, "c2_idx": j, "c3_idx": k,
            "gap_low": float(highs[i]), "gap_high": float(lows[k]),
            "formed_trade_date": trade_dates[k], "band": bands[k],
            "rank": ranks[k], "year": years[k],
            "live_start": live_start, "live_end": live_end,
            "superseded": False,
        })

    # most-recent-gap-wins: truncate each gap's window to end just before
    # its IMMEDIATE successor's formation, if that successor forms within
    # the current window -- sufficient because gaps are already in
    # ascending c3_idx order, so a gap can only ever be superseded by the
    # very next one (a later third gap's own truncation of the SECOND gap
    # is handled independently, on its own pass through this same loop).
    for idx in range(len(gaps) - 1):
        cur, nxt = gaps[idx], gaps[idx + 1]
        if nxt["c3_idx"] <= cur["live_end"]:
            cur["live_end"] = nxt["c3_idx"] - 1
            cur["superseded"] = True

    return {"gaps": gaps, "inside_bar_rejected": inside_bar_rejected, "overnight_excluded": overnight_excluded}
