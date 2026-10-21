"""`PREREGISTRATION_IPO.md` Section 8's two nulls.

TIMING null: the exact DEV-window listings the real strategy actually
entered (a green first candle, successfully filled). A random 1-minute
bar in [09:16, 15:00] (whichever bars are actually archived in that
window that day -- a listing day's own special pre-open session,
Section 3c, means this is not literally every clock-minute) replaces
the real entry trigger; its own OPEN is the entry price (same "fill at
open" convention as the real rule), same 5%/12.5% stop/target
PERCENTAGES (applied to the NEW random entry price, per instruction --
not the real trade's own stop distance), same cost model, same 15:15
time-exit mechanics (`ipo_listing.resolution.resolve_exit`, reused
unchanged -- a random entry ts is still a valid `fill_ts` to scan
forward from).

SELECTION null: NOT a seeded random draw (`PREREGISTRATION_IPO.md`
Section 8's own text: "all listings... entered at 09:16 regardless of
candle colour" is a single deterministic alternate strategy). Built via
`ipo_listing.backtest.run_backtest(..., ignore_color=True)` over ALL
DEV-window usable listings (not just the ones the real, green-filtered
strategy traded), then run through `box_theory.inference.
day_clustered_bootstrap` (unchanged) to produce a resampled-mean
distribution the real strategy's own observed DEV mean is located
within via `box_theory.inference.percentile_vs_null` (unchanged) --
exactly the operationalization `PREREGISTRATION_IPO.md` Section 8
states explicitly, reusing the inference machinery rather than
inventing new seed mechanics for an inherently non-random alternate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ipo_listing.costs import net_r, COST_SCENARIOS_BPS
from ipo_listing.resolution import resolve_exit, position_size_shares, STOP_PCT, TARGET_PCT, \
    TIMING_NULL_WINDOW_START, TIMING_NULL_WINDOW_END


def _run_timing_trial(bars1_day: pd.DataFrame, rng: np.random.Generator) -> float | None:
    """One random draw for one listing day. Returns net_r at 7bps, or
    None if this day has no bar in the random-entry window (not
    expected for a DEV-window entered trade, which by construction has
    at least two archived bars, but guarded rather than assumed)."""
    ts = bars1_day["ts"]
    in_window = (ts.dt.time >= TIMING_NULL_WINDOW_START) & (ts.dt.time <= TIMING_NULL_WINDOW_END)
    candidates = bars1_day[in_window]
    if candidates.empty:
        return None

    idx = rng.integers(0, len(candidates))
    draw = candidates.iloc[idx]
    entry_price = float(draw["open"])
    qty = position_size_shares(entry_price, stop_pct=STOP_PCT)
    if qty < 1:
        return None
    stop = entry_price * (1 - STOP_PCT)
    target = entry_price * (1 + TARGET_PCT)

    exit_ = resolve_exit(bars1_day, pd.Timestamp(draw["ts"]), entry_price, stop, target)
    pnl_rs = qty * (exit_["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    return net_r(pnl_rs, position_size_rs, 7.0)


def run_timing_null(bars_by_listing: dict[int, pd.DataFrame], n_seeds: int) -> np.ndarray:
    """`bars_by_listing`: {listing_id: day-bars df}, exactly the DEV-
    window listings the real strategy entered. Returns an array of
    `n_seeds` pooled-mean net_r (7bps) draws, one per seed -- each seed
    draws ONE random entry per listing and pools across all listings
    for that seed (same "one pooled mean per seed" shape
    `box_theory.inference.day_clustered_bootstrap`'s own resample_means
    has, so `percentile_vs_null` applies identically)."""
    listing_ids = list(bars_by_listing.keys())
    seed_means = np.empty(n_seeds)
    for s in range(n_seeds):
        rng = np.random.default_rng(s)
        vals = []
        for lid in listing_ids:
            v = _run_timing_trial(bars_by_listing[lid], rng)
            if v is not None:
                vals.append(v)
        seed_means[s] = float(np.mean(vals)) if vals else float("nan")
    return seed_means
