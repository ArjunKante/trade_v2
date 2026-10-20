"""PREREGISTRATION_FVG.md Section 8: TIMING and SELECTION nulls, matched
on NET R (same cost model as the real strategy).

TIMING null: restricted to the exact (entity_id, entry trade_date) pairs
a configuration actually traded. A random 1-hour candle on that SAME day
replaces the real entry trigger; the STOP DISTANCE (rupee amount) is
carried over unchanged from the real trade ("same stop distance and 3R
target" -- the 0.5% floor is NOT re-applied here, since the null has no
gap_low of its own to check a ratio against; the risk amount is simply
inherited).

SELECTION null: random (entity, day) pairs from the same universe-year
eligible population (fvg.context.build_entity_timeline's own "every
eligible day" output, including days that never formed or touched any
gap), matched count per calendar month to the real strategy's own trade
count that month. Stop distance is drawn (with replacement) from the real
strategy's own empirical room_pct distribution for that configuration,
applied proportionally to the null's own random entry price.

PERFORMANCE, found live at this study's real scale (54,482 Configuration-A
trades, 279 distinct entities) and fixed in TWO stages before committing
to 1000 seeds, per the preregistration's own measure-before-committing
discipline:

  1. First version re-ran `.to_numpy()` extraction, a pandas boolean-mask
     fill lookup, and `dt.datetime.combine`/`pd.Timestamp` cutoff
     construction INSIDE the per-draw path. Paid on every one of up to
     ~10^7-10^8 draws, it projected to ~31 hours for the real pool. Fixed
     by extracting every numpy array and every per-day time-exit cutoff
     ONCE, at pool-build time -- same fix `box_theory.nulls.prepare_ctx`
     already applies for box theory's own nulls.

  2. That fix's FIRST implementation then SLICED a fresh, bounded
     `bars1` copy per TRADE (to keep the resolve scan itself bounded to
     ~12 days rather than an entity's full multi-year span). That traded
     the timing problem for a MEMORY one: the real pool's preflight
     measurement showed peak working set at **7.46 GB** for Configuration
     A's 54,482-trade pool -- adjacent trades on the same entity have
     heavily overlapping 12-day windows, so most of that memory was pure
     duplication. Fixed by sharing ONE array per ENTITY across every
     trade-context that entity contributes (no per-trade copy at all),
     and bounding each draw's resolve scan via `np.searchsorted` on the
     (already time-sorted) shared array instead of a physical slice --
     O(log n) to find the window, then numpy ops only touch the few
     hundred bars inside it, regardless of how long the entity's own
     shared array is.

Built and consumed one month (SELECTION) or one entity (TIMING) at a
time -- same streaming discipline as `box_theory.nulls`.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from fvg.context import build_entity_timeline, group_by_day
from fvg.holiday import nth_next_nse_trading_day
from fvg.resolution import (
    FIXED_RISK_RS, TARGET_R_MULTIPLE, TIME_EXIT_TRADING_DAYS, TIME_EXIT_TIME, STOP_SCAN_END_TIME,
)

MAX_FILL_RETRY = 10
FORWARD_BUFFER_DAYS = 12  # >= 5 NSE trading days' worth of calendar slack for time-exit resolution


def _prepare_entity_arrays(candles: pd.DataFrame, bars1: pd.DataFrame) -> dict:
    """Extracted ONCE per entity and SHARED (same dict object) across
    every trade/day-context that entity contributes -- never copied or
    re-extracted per context, per draw, or per seed."""
    return {
        "c_ts": candles["ts"].to_numpy(), "c_bucket_end": candles["bucket_end"].to_numpy(),
        "c_close": candles["close"].to_numpy(),
        "b_ts": bars1["ts"].to_numpy(), "b_open": bars1["open"].to_numpy(),
        "b_high": bars1["high"].to_numpy(), "b_low": bars1["low"].to_numpy(),
    }


def _cutoffs_for_day(day: dt.date) -> tuple:
    """(cutoff_1519, cutoff_1515) as np.datetime64, computed ONCE per
    (entity, day) context at pool-build time."""
    time_exit_date = nth_next_nse_trading_day(day, TIME_EXIT_TRADING_DAYS)
    cutoff_1519 = np.datetime64(pd.Timestamp(dt.datetime.combine(time_exit_date, STOP_SCAN_END_TIME)))
    cutoff_1515 = np.datetime64(pd.Timestamp(dt.datetime.combine(time_exit_date, TIME_EXIT_TIME)))
    return cutoff_1519, cutoff_1515


def _resolve_exit_fast(base: dict, fill_idx: int, stop_price: float, target_price: float,
                        cutoff_1519, cutoff_1515) -> float:
    """Pure-numpy stop/target/time-exit resolution, semantically identical
    to `fvg.resolution.resolve_exit` (STOP wins a same-bar tie; time-exit
    falls back to the latest candle at/before the 15:15 cutoff).
    `fill_idx` is the fill bar's own position in the SHARED, entity-wide
    `b_ts` array; the scan window is bounded via `searchsorted` (O(log n)
    to locate, then numpy ops only touch the small slice in between) --
    never a boolean mask over the whole shared array."""
    b_ts, b_open, b_high, b_low = base["b_ts"], base["b_open"], base["b_high"], base["b_low"]
    end_idx = int(np.searchsorted(b_ts, cutoff_1519, side="right"))
    seg_low, seg_high, seg_open = b_low[fill_idx:end_idx], b_high[fill_idx:end_idx], b_open[fill_idx:end_idx]
    hit = np.flatnonzero((seg_low <= stop_price) | (seg_high >= target_price))
    if len(hit):
        j = int(hit[0])
        if seg_low[j] <= stop_price:
            return float(seg_open[j]) if seg_open[j] <= stop_price else stop_price
        return float(seg_open[j]) if seg_open[j] >= target_price else target_price

    c_ts, c_close = base["c_ts"], base["c_close"]
    ci = int(np.searchsorted(c_ts, cutoff_1515, side="right")) - 1
    if ci < 0:
        return float(b_open[fill_idx])  # defensive only -- forward buffer always covers the horizon
    return float(c_close[ci])


def _draw_trade_fast(ctx: dict, rng: np.random.Generator, risk: float | None = None) -> float | None:
    """One null draw against a single (entity, day) context. `risk`
    overrides `ctx["risk"]` when given (SELECTION null samples a fresh
    risk per draw; TIMING null uses the context's own fixed, carried-over
    risk when `risk` is None)."""
    risk = ctx["risk"] if risk is None else risk
    day_candle_idx = ctx["day_candle_idx"]
    if risk is None or risk <= 0 or len(day_candle_idx) == 0:
        return None

    base = ctx["base"]
    c_bucket_end, b_ts, b_open = base["c_bucket_end"], base["b_ts"], base["b_open"]

    for _ in range(MAX_FILL_RETRY):
        idx = int(day_candle_idx[rng.integers(0, len(day_candle_idx))])
        bucket_end = c_bucket_end[idx]
        fi = int(np.searchsorted(b_ts, bucket_end))
        if fi >= len(b_ts) or b_ts[fi] != bucket_end:
            continue
        entry_price = float(b_open[fi])
        if entry_price <= 0:
            continue
        qty = int(FIXED_RISK_RS // risk)
        if qty < 1:
            return None
        stop_price = entry_price - risk
        target_price = entry_price + TARGET_R_MULTIPLE * risk
        exit_price = _resolve_exit_fast(base, fi, stop_price, target_price, ctx["cutoff_1519"], ctx["cutoff_1515"])
        pnl_rs = qty * (exit_price - entry_price)
        position_size_rs = qty * entry_price
        cost_rs = round_trip_cost_rs(position_size_rs, ctx["band"])
        return (pnl_rs - cost_rs) / FIXED_RISK_RS
    return None


# ---------------------------------------------------------------------
# TIMING null
# ---------------------------------------------------------------------

def build_timing_pool(intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
                       trades: pd.DataFrame, rank_lookup: dict, jump_dates_by_entity: dict) -> list[dict]:
    """One prepared context per real trade -- {"base" (SHARED numpy arrays
    per entity, not copied per trade), "day_candle_idx", "cutoff_1519",
    "cutoff_1515", "risk", "band"}. `trades` must already be restricted
    to ONE configuration. Fetched ONCE PER ENTITY (spanning that entity's
    own min-to-max real trade date, + a forward buffer); every trade for
    that entity references the SAME base arrays -- see module docstring
    for why a per-trade copy is NOT taken."""
    pool = []
    for entity_id, grp in trades.groupby("entity_id"):
        days = sorted(grp["trade_date"].unique())
        start, end = min(days), max(days)
        fetch_end = end + dt.timedelta(days=FORWARD_BUFFER_DAYS)
        bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(start.year - 1, 1, 1), fetch_end)
        ex_dates = fetch_ex_dates(warehouse_con, entity_id)
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        block = fetch_bars_range(intraday_con, entity_id, start, fetch_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        timeline = build_entity_timeline(
            intraday_con, entity_id, day_groups, bhav, ex_dates, jump_dates, {}, rank_lookup,
        )
        candles, bars1 = timeline["candles"], timeline["bars1"]
        if candles.empty:
            continue
        base = _prepare_entity_arrays(candles, bars1)
        c_dates = candles["trade_date"].to_numpy()

        for _, row in grp.iterrows():
            day = row["trade_date"]
            day_idx = np.flatnonzero(c_dates == day)
            if len(day_idx) == 0:
                continue  # should not happen (day was tradeable for real); defensive only
            cutoff_1519, cutoff_1515 = _cutoffs_for_day(day)
            risk = float(row["entry_price"] - row["gap_low"])
            pool.append({
                "base": base, "day_candle_idx": day_idx, "cutoff_1519": cutoff_1519,
                "cutoff_1515": cutoff_1515, "risk": risk, "band": row["band"],
            })
    return pool


def timing_null_seed_mean(pool: list[dict], rng: np.random.Generator) -> float:
    draws = [r for ctx in pool if (r := _draw_trade_fast(ctx, rng)) is not None]
    return float(np.mean(draws)) if draws else float("nan")


def timing_null_seed_sum_count(pool: list[dict], rng: np.random.Generator) -> tuple[float, int]:
    """Same per-seed draw as `timing_null_seed_mean`, returning (sum,
    count) instead of the mean -- lets a caller accumulate across
    ENTITY BATCHES (see `fvg_dev_run.py`'s batched TIMING null, needed
    because holding every entity's own shared array alive simultaneously
    for the full real-trade population measured at several GB peak
    working set on this machine's 15.7GB/5.6GB-free budget). Pooling via
    (sum, count) across batches gives the same pooled mean a single
    unbatched pass over the whole population would, exactly mirroring how
    `selection_null_seed_mean`'s caller already pools across MONTHS."""
    draws = [r for ctx in pool if (r := _draw_trade_fast(ctx, rng)) is not None]
    return float(sum(draws)), len(draws)


# ---------------------------------------------------------------------
# SELECTION null
# ---------------------------------------------------------------------

def build_month_pool(intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
                      universe: pd.DataFrame, year: int, month: int, rank_lookup: dict,
                      jump_dates_by_entity: dict) -> list[dict]:
    """Every eligible day, for every universe member of `year`, restricted
    to calendar `month` -- including days with no gap at all, per
    instruction. One month, one call; the caller discards this before
    building the next. Base numpy arrays are prepared ONCE PER ENTITY and
    SHARED (same object) across every day-context that entity contributes
    this month -- only the per-day cutoffs and candle-index subset differ."""
    month_start = dt.date(year, month, 1)
    month_end = (pd.Timestamp(month_start) + pd.offsets.MonthEnd(0)).date()
    fetch_end = month_end + dt.timedelta(days=FORWARD_BUFFER_DAYS)
    members = universe.loc[universe["year"] == year, "entity_id"].tolist()

    pool = []
    for entity_id in members:
        bhav = fetch_bhav_daily(warehouse_con, entity_id, month_start - dt.timedelta(days=10), fetch_end)
        ex_dates = fetch_ex_dates(warehouse_con, entity_id)
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        single_day_cache: dict = {}
        block = fetch_bars_range(intraday_con, entity_id, month_start, fetch_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        timeline = build_entity_timeline(
            intraday_con, entity_id, day_groups, bhav, ex_dates, jump_dates, single_day_cache, rank_lookup,
        )
        candles, bars1 = timeline["candles"], timeline["bars1"]
        if candles.empty:
            continue
        base = _prepare_entity_arrays(candles, bars1)
        c_dates = candles["trade_date"].to_numpy()
        bands = candles["band"].to_numpy()

        for day in timeline["eligible_days"]:
            if not (month_start <= day <= month_end):
                continue
            day_idx = np.flatnonzero(c_dates == day)
            if len(day_idx) == 0:
                continue
            cutoff_1519, cutoff_1515 = _cutoffs_for_day(day)
            pool.append({
                "base": base, "day_candle_idx": day_idx, "cutoff_1519": cutoff_1519,
                "cutoff_1515": cutoff_1515, "band": str(bands[day_idx[0]]), "risk": None,
            })
    return pool


def selection_null_seed_mean(month_pool: list[dict], count: int, rng: np.random.Generator,
                              room_pct_pool: np.ndarray) -> list[float]:
    """Draws `count` random (entity, day) pairs WITH REPLACEMENT from
    `month_pool`; each draw's stop distance is sampled (with replacement)
    from `room_pct_pool` (the real strategy's own empirical `(entry -
    gap_low) / entry` values for this configuration) and applied
    proportionally to that draw's own random entry price. Returns the raw
    list (caller pools across months, matching Section 7's "pooled mean
    net R" language)."""
    if not month_pool or len(room_pct_pool) == 0:
        return []
    draws = []
    n = len(month_pool)
    for _ in range(count):
        ctx = month_pool[int(rng.integers(0, n))]
        day_idx = ctx["day_candle_idx"]
        if len(day_idx) == 0:
            continue
        base = ctx["base"]
        c_bucket_end, b_ts, b_open = base["c_bucket_end"], base["b_ts"], base["b_open"]
        for _ in range(MAX_FILL_RETRY):
            idx = int(day_idx[rng.integers(0, len(day_idx))])
            bucket_end = c_bucket_end[idx]
            fi = int(np.searchsorted(b_ts, bucket_end))
            if fi >= len(b_ts) or b_ts[fi] != bucket_end:
                continue
            entry_price = float(b_open[fi])
            if entry_price <= 0:
                continue
            sampled_pct = float(room_pct_pool[int(rng.integers(0, len(room_pct_pool)))])
            risk = entry_price * sampled_pct
            exit_price = _resolve_exit_fast(base, fi, entry_price - risk, entry_price + TARGET_R_MULTIPLE * risk,
                                             ctx["cutoff_1519"], ctx["cutoff_1515"])
            qty = int(FIXED_RISK_RS // risk)
            if qty < 1:
                break
            pnl_rs = qty * (exit_price - entry_price)
            position_size_rs = qty * entry_price
            cost_rs = round_trip_cost_rs(position_size_rs, ctx["band"])
            draws.append((pnl_rs - cost_rs) / FIXED_RISK_RS)
            break
    return draws
