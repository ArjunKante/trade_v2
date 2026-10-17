"""PREREGISTRATION_BOX.md Section 6: TIMING, SELECTION, and BASELINE
nulls, matched on NET R (same cost model as the real strategy).

TIMING null: restricted to the exact (entity, day) pairs the real
strategy traded for a given configuration -- a random 5-minute entry bar
replaces the touch+confirmation signal, everything downstream (room
filter, stop, arming/exit, time exit, costs) is identical.

SELECTION null: random (entity, day) pairs from the SAME universe-year
population used by the real backtest (built via `box_theory.context.
eligible_day_context`, so it is exactly the same "is this day eligible
at all" definition, including days that never touched PREV_LOW), matched
count per calendar month to the real strategy's own trade count that
month. Built and consumed ONE MONTH AT A TIME (not the whole window held
in memory at once) -- PREREGISTRATION_BOX.md Section 2b's streaming
discipline, applied here too: a full-window pool across ~75 months x 200
entities x ~20 trading days, each carrying its own 1-minute/5-minute
frames, would be several GB held simultaneously for no reason when only
one month's pool is ever sampled from at a time.

BASELINE is a separate, simpler, non-seeded descriptive computation (see
`baseline_descriptive`) -- not fed into either percentile comparison.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from box_theory.context import eligible_day_context, group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.resolution import (
    ENTRY_WINDOW_START, ENTRY_WINDOW_END, resolve_exit_arrays, position_size_shares, ROOM_PCT,
)
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

MAX_ROOM_RETRY = 20
FIXED_RISK_RS = 500.0


def prepare_ctx(ctx: dict) -> dict:
    """Caches the random-draw inputs that would otherwise be recomputed
    on every retry and every seed: the entry-window-valid candle indices
    and the candle's own open/ts arrays. Call once per context, at pool-
    build time (build_timing_pool / build_month_pool already do this) --
    `.dt.time` extraction and per-draw `.iloc[idx]["open"]` row access
    both profiled as material cost at this study's ~10^7-10^8-draw null
    scale."""
    candles5, day_raw = ctx["candles5"], ctx["day_raw"]
    ts_arr = candles5["ts"].to_numpy()
    day_start = candles5["ts"].iloc[0].normalize()
    window_start = np.datetime64(day_start + pd.Timedelta(hours=9, minutes=30))
    window_end = np.datetime64(day_start + pd.Timedelta(hours=14, minutes=30))
    ctx["valid_entry_idx"] = np.flatnonzero((ts_arr >= window_start) & (ts_arr <= window_end))
    ctx["open_arr"] = candles5["open"].to_numpy()
    ctx["ts_arr"] = ts_arr
    ctx["high_arr"] = candles5["high"].to_numpy()
    ctx["close_arr"] = candles5["close"].to_numpy()
    ctx["is_red_arr"] = candles5["is_red"].to_numpy()
    ctx["b1_ts_arr"] = day_raw["ts"].to_numpy()
    ctx["b1_open_arr"] = day_raw["open"].to_numpy()
    ctx["b1_low_arr"] = day_raw["low"].to_numpy()
    return ctx


def _random_trade(ctx: dict, rng: np.random.Generator, config: str) -> float | None:
    """One null draw against a single day's context: random 5-minute
    entry bar, same room filter, stop/arming/exit/time-exit, same costs.
    Returns net_r, or None if no valid entry could be found (room filter
    exhausted its retries, or the day has no candle in the entry
    window)."""
    prev_high = ctx["prev_high"]
    valid_idx = ctx["valid_entry_idx"]
    if len(valid_idx) == 0:
        return None

    for _ in range(MAX_ROOM_RETRY):
        idx = int(valid_idx[rng.integers(0, len(valid_idx))])
        entry_price = float(ctx["open_arr"][idx])
        if entry_price <= 0:
            continue
        if (prev_high - entry_price) / entry_price < ROOM_PCT:
            continue
        qty = position_size_shares(entry_price)
        if qty < 1:
            continue
        fill_ts = ctx["ts_arr"][idx]
        break
    else:
        return None

    exit_res = resolve_exit_arrays(
        ctx["ts_arr"], ctx["open_arr"], ctx["high_arr"], ctx["close_arr"], ctx["is_red_arr"],
        ctx["b1_ts_arr"], ctx["b1_open_arr"], ctx["b1_low_arr"],
        idx, fill_ts, entry_price, prev_high, config,
    )
    pnl_rs = qty * (exit_res["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    cost_rs = round_trip_cost_rs(position_size_rs, ctx["band"])
    return (pnl_rs - cost_rs) / FIXED_RISK_RS


# ---------------------------------------------------------------------
# TIMING null
# ---------------------------------------------------------------------

def build_timing_pool(intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
                       trades: pd.DataFrame, rank_lookup: dict, jump_dates_by_entity: dict) -> list[dict]:
    """One context per real trade (entity_id, trade_date, config) --
    config is carried along since FAST/SLOW trades on the same day can
    differ (different confirmation path), but the underlying day context
    (box, scale, band) is identical; fetched once per entity even if that
    entity contributed multiple trade-days."""
    pool = []
    for entity_id, grp in trades.groupby("entity_id"):
        days = sorted(grp["trade_date"].unique())
        years = sorted({d.year for d in days})
        start, end = min(days), max(days)
        bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
        ex_dates = fetch_ex_dates(warehouse_con, entity_id)
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        single_day_cache: dict = {}
        block = fetch_bars_range(intraday_con, entity_id, start, end)
        day_groups = group_by_day(block)

        for _, row in grp.iterrows():
            day = row["trade_date"]
            ctx = eligible_day_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup,
            )
            if ctx["skip"] is not None:
                continue  # should not happen (day was tradeable for real); defensive only
            ctx["config"] = row["config"]
            ctx = prepare_ctx(ctx)
            # Unlike build_month_pool's contexts (still needed, whole, by
            # baseline_return), nothing downstream of this pool ever reads
            # day_raw/candles5 again -- _random_trade runs entirely off
            # prepare_ctx's cached numpy arrays. Dropping them here is not
            # a formality: at real DEV scale (one context per real trade,
            # tens of thousands for FAST/SLOW), keeping both the pandas
            # frames AND their numpy-array duplicates alive for the whole
            # 1000-seed run swelled the process to multiple GB -- found
            # live when a re-run of the same work came back ~3x slower
            # than the first, with no code change in between.
            del ctx["day_raw"], ctx["candles5"]
            pool.append(ctx)
    return pool


def timing_null_seed_mean(pool: list[dict], rng: np.random.Generator) -> float:
    draws = [r for ctx in pool if (r := _random_trade(ctx, rng, ctx["config"])) is not None]
    return float(np.mean(draws)) if draws else float("nan")


# ---------------------------------------------------------------------
# SELECTION null
# ---------------------------------------------------------------------

def build_month_pool(intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
                      universe: pd.DataFrame, year: int, month: int, rank_lookup: dict,
                      jump_dates_by_entity: dict) -> list[dict]:
    """Every valid box-day (eligible_day_context's skip is None) for
    EVERY universe member of `year`, restricted to calendar `month` --
    including days that never touched PREV_LOW, per instruction. One
    month, one call; the caller discards this before building the next."""
    month_start = dt.date(year, month, 1)
    month_end = (dt.date(year, month, 1) + pd.offsets.MonthEnd(0)).date()
    members = universe.loc[universe["year"] == year, "entity_id"].tolist()

    pool = []
    for entity_id in members:
        bhav = fetch_bhav_daily(warehouse_con, entity_id, month_start - dt.timedelta(days=10), month_end)
        ex_dates = fetch_ex_dates(warehouse_con, entity_id)
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        single_day_cache: dict = {}
        block = fetch_bars_range(intraday_con, entity_id, month_start, month_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        for day in sorted(day_groups.keys()):
            ctx = eligible_day_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup,
            )
            if ctx["skip"] is None:
                pool.append(prepare_ctx(ctx))
    return pool


def selection_null_seed_mean(month_pool: list[dict], count: int, rng: np.random.Generator,
                              config: str) -> list[float]:
    """Draws `count` random (entity, day) pairs WITH REPLACEMENT from
    `month_pool`, one net_r each -- returns the raw list (the caller
    pools across months before averaging, so a seed's overall mean is
    the POOLED mean across all months, matching Section 5's "pooled
    mean net R" language)."""
    if not month_pool:
        return []
    draws = []
    n = len(month_pool)
    for _ in range(count):
        ctx = month_pool[int(rng.integers(0, n))]
        r = _random_trade(ctx, rng, config)
        if r is not None:
            draws.append(r)
    return draws


# ---------------------------------------------------------------------
# BASELINE (descriptive only)
# ---------------------------------------------------------------------

def baseline_return(day_raw: pd.DataFrame, candles5: pd.DataFrame, band: str) -> float | None:
    """Buy at the 09:30 candle's open, sell at the 15:15 candle's close,
    net of the same cost model -- plain percentage return (no R concept
    here; there is no stop-derived risk unit for a buy-and-hold).
    Descriptive only, PREREGISTRATION_BOX.md Section 6.

    Sized the SAME way the real strategy sizes every position
    (`position_size_shares`, the fixed-Rs-500-at-3%-formula) even though
    there is no real stop here -- needed so the cost model's fixed Rs20
    brokerage cap/Rs5 floor is amortized over a realistic ~Rs16,700
    position like every other figure in this study, not over one share's
    value (which would wildly overstate brokerage as a fraction of a
    cheap stock and understate it for an expensive one)."""
    open_row = candles5[candles5["ts"].dt.time == ENTRY_WINDOW_START]
    close_row = candles5[candles5["ts"].dt.time == dt.time(15, 15)]
    if open_row.empty or close_row.empty:
        return None
    buy_price = float(open_row.iloc[0]["open"])
    sell_price = float(close_row.iloc[0]["close"])
    if buy_price <= 0:
        return None
    qty = position_size_shares(buy_price)
    if qty < 1:
        return None
    position_size_rs = qty * buy_price
    cost_rs = round_trip_cost_rs(position_size_rs, band)
    pnl_rs = qty * (sell_price - buy_price)
    return (pnl_rs - cost_rs) / position_size_rs
