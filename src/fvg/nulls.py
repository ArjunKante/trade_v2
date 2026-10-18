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
from fvg.resolution import fill_bar_after_close, resolve_exit, FIXED_RISK_RS, TARGET_R_MULTIPLE

MAX_FILL_RETRY = 10
FORWARD_BUFFER_DAYS = 12  # >= 5 NSE trading days' worth of calendar slack for time-exit resolution


def _draw_trade(candles: pd.DataFrame, bars1: pd.DataFrame, day_candle_idx: np.ndarray,
                 rng: np.random.Generator, risk: float, band: str) -> float | None:
    """One null draw against a single day's candle pool, given a FIXED
    per-share risk amount (rupees) -- shared logic for both null types
    once the risk amount is known (TIMING: carried over; SELECTION:
    sampled proportionally by the caller before calling this)."""
    if risk is None or risk <= 0 or len(day_candle_idx) == 0:
        return None
    for _ in range(MAX_FILL_RETRY):
        idx = int(day_candle_idx[rng.integers(0, len(day_candle_idx))])
        trigger = candles.iloc[idx]
        fill_bar = fill_bar_after_close(bars1, trigger["bucket_end"])
        if fill_bar is None:
            continue
        entry_price = float(fill_bar["open"])
        if entry_price <= 0:
            continue
        qty = int(FIXED_RISK_RS // risk)
        if qty < 1:
            return None
        stop_price = entry_price - risk
        target_price = entry_price + TARGET_R_MULTIPLE * risk
        fill_ts = pd.Timestamp(fill_bar["ts"])
        entry = {"fill_ts": fill_ts, "stop_price": stop_price, "target_price": target_price}
        exit_res = resolve_exit(candles, bars1, entry, fill_ts.date())
        pnl_rs = qty * (exit_res["exit_price"] - entry_price)
        position_size_rs = qty * entry_price
        cost_rs = round_trip_cost_rs(position_size_rs, band)
        return (pnl_rs - cost_rs) / FIXED_RISK_RS
    return None


# ---------------------------------------------------------------------
# TIMING null
# ---------------------------------------------------------------------

def build_timing_pool(intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
                       trades: pd.DataFrame, rank_lookup: dict, jump_dates_by_entity: dict) -> list[dict]:
    """One context per real trade -- {"day_candle_idx", "candles", "bars1",
    "risk", "band"}. `trades` must already be restricted to ONE
    configuration.

    Fetched per TRADE DAY, bounded to [day, day + FORWARD_BUFFER_DAYS]
    (not per entity's full trade-date span) -- an entity with real trades
    spread across the whole DEV window would otherwise hand every one of
    its draw contexts a multi-year-wide `bars1` series, and `resolve_exit`'s
    own boolean-mask scan over that array is paid on EVERY seed's draw,
    not once at pool-build time. Bounding each context to its own small
    forward window keeps that scan cheap at the ~10^3-seed scale this
    null runs at, the same lesson `box_theory.nulls.build_timing_pool`'s
    own docstring already records about retained-frame cost at scale."""
    pool = []
    ex_dates_cache: dict[str, set] = {}
    for _, row in trades.iterrows():
        entity_id, day = row["entity_id"], row["trade_date"]
        if entity_id not in ex_dates_cache:
            ex_dates_cache[entity_id] = fetch_ex_dates(warehouse_con, entity_id)
        ex_dates = ex_dates_cache[entity_id]
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        fetch_end = day + dt.timedelta(days=FORWARD_BUFFER_DAYS)
        bhav = fetch_bhav_daily(warehouse_con, entity_id, day - dt.timedelta(days=5), fetch_end)
        block = fetch_bars_range(intraday_con, entity_id, day, fetch_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        timeline = build_entity_timeline(
            intraday_con, entity_id, day_groups, bhav, ex_dates, jump_dates, {}, rank_lookup,
        )
        candles, bars1 = timeline["candles"], timeline["bars1"]
        if candles.empty:
            continue
        day_idx = candles.index[candles["trade_date"] == day].to_numpy()
        if len(day_idx) == 0:
            continue  # should not happen (day was tradeable for real); defensive only
        risk = float(row["entry_price"] - row["gap_low"])
        pool.append({
            "day_candle_idx": day_idx, "candles": candles, "bars1": bars1,
            "risk": risk, "band": row["band"],
        })
    return pool


def timing_null_seed_mean(pool: list[dict], rng: np.random.Generator) -> float:
    draws = [r for ctx in pool
             if (r := _draw_trade(ctx["candles"], ctx["bars1"], ctx["day_candle_idx"], rng,
                                   ctx["risk"], ctx["band"])) is not None]
    return float(np.mean(draws)) if draws else float("nan")


# ---------------------------------------------------------------------
# SELECTION null
# ---------------------------------------------------------------------

def build_month_pool(intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
                      universe: pd.DataFrame, year: int, month: int, rank_lookup: dict,
                      jump_dates_by_entity: dict) -> list[dict]:
    """Every eligible day, for every universe member of `year`, restricted
    to calendar `month` -- including days with no gap at all, per
    instruction. One month, one call; the caller discards this before
    building the next."""
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
        for day in timeline["eligible_days"]:
            if not (month_start <= day <= month_end):
                continue
            day_idx = candles.index[candles["trade_date"] == day].to_numpy()
            if len(day_idx) == 0:
                continue
            band = str(candles.iloc[int(day_idx[0])]["band"])
            pool.append({"day_candle_idx": day_idx, "candles": candles, "bars1": bars1, "band": band})
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
        for _ in range(MAX_FILL_RETRY):
            idx = int(day_idx[rng.integers(0, len(day_idx))])
            trigger = ctx["candles"].iloc[idx]
            fill_bar = fill_bar_after_close(ctx["bars1"], trigger["bucket_end"])
            if fill_bar is None:
                continue
            entry_price = float(fill_bar["open"])
            if entry_price <= 0:
                continue
            sampled_pct = float(room_pct_pool[int(rng.integers(0, len(room_pct_pool)))])
            risk = entry_price * sampled_pct
            r = _draw_trade(ctx["candles"], ctx["bars1"], np.array([idx]),
                             np.random.default_rng(0), risk, ctx["band"])
            # _draw_trade re-draws its own random candle from a 1-element
            # array (always `idx`) using a throwaway RNG -- deterministic
            # re-selection of the SAME candle we already picked and fit-
            # checked above, so the sampled stop/target are honored exactly
            # rather than redrawn a second time.
            if r is not None:
                draws.append(r)
            break
    return draws
