"""PREREGISTRATION_POC.md Section 10: TIMING and SELECTION nulls.

TIMING null: restricted to the exact (entity, T) pairs the real strategy
traded. A random 5-minute candle in [09:45, 14:30] replaces the real
touch+confirmation signal; the stop distance (rupee amount) and the
target (absolute price level) are both carried over unchanged from the
real trade -- only entry TIMING is randomized.

SELECTION null: random (entity, T) pairs from the same universe-year
population that passes Section 3's lookback-eligibility chain
(INCLUDING trend-filter failures and days that never touch the POC),
matched count per calendar month to the real strategy's own trade count
that month. Stop distance is drawn from the real strategy's own pooled
distribution; target is recomputed off the DRAWN day's own real
PREV_HIGH.

Built and consumed ONE MONTH AT A TIME for SELECTION (same streaming
discipline `box_theory.nulls.build_month_pool` already uses).
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from box_theory.context import group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.context import build_poc_context
from poc.backtest import _build_trend_lookup_for_entity
from poc.resolution import (
    FIXED_RISK_RS, MAX_RISK_PCT, TARGET_BELOW_PREV_HIGH_PCT,
    ENTRY_WINDOW_START, ENTRY_WINDOW_END, fill_bar_after_candle_close, position_size_shares, resolve_exit,
)

MAX_ROOM_RETRY = 20


def _valid_entry_idx(candles5: pd.DataFrame) -> np.ndarray:
    times = candles5["ts"].dt.time
    return candles5.index[(times >= ENTRY_WINDOW_START) & (times <= ENTRY_WINDOW_END)].to_numpy()


def _random_fill(candles5: pd.DataFrame, day_raw: pd.DataFrame, rng: np.random.Generator,
                  valid_idx: np.ndarray) -> tuple[float, pd.Timestamp] | tuple[None, None]:
    """One random valid candle -> its own fill bar (next 1-minute bar
    after that candle's close), retried up to MAX_ROOM_RETRY times if no
    fill bar exists or the fill lands outside [09:45, 14:30]."""
    if len(valid_idx) == 0:
        return None, None
    for _ in range(MAX_ROOM_RETRY):
        idx = int(valid_idx[rng.integers(0, len(valid_idx))])
        candle = candles5.iloc[idx]
        close_ts = candle["ts"] + pd.Timedelta(minutes=5)
        fill_bar = fill_bar_after_candle_close(day_raw, close_ts)
        if fill_bar is None:
            continue
        fill_ts = pd.Timestamp(fill_bar["ts"])
        if not (ENTRY_WINDOW_START <= fill_ts.time() <= ENTRY_WINDOW_END):
            continue
        return float(fill_bar["open"]), fill_ts
    return None, None


# ---------------------------------------------------------------------
# TIMING null
# ---------------------------------------------------------------------

def build_timing_pool(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    trades: pd.DataFrame, rank_lookup: dict, jump_dates_by_entity: dict,
) -> list[dict]:
    """One context per real trade: today's own candles5/day_raw (re-fetched
    via the SAME eligible_day_context the real backtest used -- POC/
    PREV_HIGH do not need to be re-derived, since the null carries the
    real trade's own stop distance and target level unchanged, Section
    10), plus the real trade's own entry/stop/target/band."""
    from box_theory.context import eligible_day_context

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
            dctx = eligible_day_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup,
            )
            if dctx["skip"] is not None:
                continue  # should not happen (day was tradeable for real); defensive only
            stop_distance = float(row["entry_price"]) - float(row["stop_price"])
            pool.append({
                "candles5": dctx["candles5"], "day_raw": dctx["day_raw"],
                "valid_idx": _valid_entry_idx(dctx["candles5"]),
                "stop_distance": stop_distance, "target_price": float(row["target_price"]),
                "band": row["band"],
            })
    return pool


def _timing_draw(ctx: dict, rng: np.random.Generator) -> float | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = entry_price - ctx["stop_distance"]
    target_price = ctx["target_price"]
    if stop_price <= 0 or (entry_price - stop_price) / entry_price > MAX_RISK_PCT:
        return None
    if target_price <= entry_price:
        return None
    qty = position_size_shares(entry_price, stop_price)
    if qty < 1:
        return None
    exit_res = resolve_exit(ctx["day_raw"], ctx["candles5"], fill_ts, entry_price, stop_price, target_price)
    pnl_rs = qty * (exit_res["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    cost_rs = round_trip_cost_rs(position_size_rs, ctx["band"])
    return (pnl_rs - cost_rs) / FIXED_RISK_RS


def timing_null_seed_mean(pool: list[dict], rng: np.random.Generator) -> float:
    draws = [r for ctx in pool if (r := _timing_draw(ctx, rng)) is not None]
    return float(np.mean(draws)) if draws else float("nan")


# ---------------------------------------------------------------------
# SELECTION null
# ---------------------------------------------------------------------

def get_or_build_entity_setup(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, jump_dates: set,
    full_start: dt.date, full_end: dt.date, setup_cache: dict,
) -> dict:
    """Memoized {"bhav", "ex_dates", "trend_lookup"} for one entity,
    across the ENTIRE run (not per year, not per month) -- `setup_cache`
    is a plain dict the caller keeps alive for the whole SELECTION null
    build. These three are all O(entity's daily history), a few KB to a
    few hundred KB each -- cheap to hold for every universe entity ever
    needed simultaneously, unlike the INTRADAY 1-minute/5-minute data
    (Section 3), which is NOT cached this broadly (see `build_month_
    pool`'s own docstring for why).

    PERFORMANCE NOTE, found live on the real archive: the original
    per-(entity, month) design re-ran `fetch_bhav_daily`/`fetch_ex_dates`/
    the full daily-OHLC-panel-plus-50-day-SMA computation from scratch
    for every month -- measured at 45-100s per month for just 15
    entities, projecting to low tens of hours at full universe x
    75-month DEV scale. Caching just these three cheap artifacts across
    the whole run removes that cost without holding a full year's worth
    of INTRADAY bars in memory at once (which an earlier, since-reverted
    per-year-cache design did, and which climbed to 3.5GB+ within one
    year against ~5.5GB available RAM on this machine -- a real OOM
    risk, not merely slow)."""
    if entity_id in setup_cache:
        return setup_cache[entity_id]
    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(full_start.year - 1, 1, 1), full_end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    trend_lookup = _build_trend_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    entry = {"bhav": bhav, "ex_dates": ex_dates, "trend_lookup": trend_lookup}
    setup_cache[entity_id] = entry
    return entry


def build_month_pool(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    universe: pd.DataFrame, year: int, month: int, rank_lookup: dict, jump_dates_by_entity: dict,
    entity_setup_cache: dict, full_start: dt.date, full_end: dt.date,
) -> list[dict]:
    """Every (entity, T) pair for EVERY universe member of `year`,
    restricted to calendar `month`, that passes Section 3's lookback-
    eligibility chain -- INCLUDING trend-filter failures and days that
    never touch the POC, per PREREGISTRATION_POC.md Section 10's own
    SELECTION null population.

    The cheap per-entity setup (bhav/ex_dates/trend_lookup) is memoized
    across the WHOLE run via `entity_setup_cache` (see `get_or_build_
    entity_setup`'s docstring). The INTRADAY data -- `day_groups`,
    `single_day_cache`, and Section 3's own `eligible_ctx_cache` -- is
    deliberately rebuilt FRESH for this one month and discarded when
    this call returns (bounded memory: at most one month's worth of
    1-minute/5-minute bars across the universe, at any time, not a
    whole year's)."""
    month_start = dt.date(year, month, 1)
    month_end = (dt.date(year, month, 1) + pd.offsets.MonthEnd(0)).date()
    members = universe.loc[universe["year"] == year, "entity_id"].tolist()

    pool = []
    for entity_id in members:
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        setup = get_or_build_entity_setup(warehouse_con, entity_id, jump_dates, full_start, full_end,
                                           entity_setup_cache)
        single_day_cache: dict = {}
        eligible_ctx_cache: dict = {}
        block = fetch_bars_range(intraday_con, entity_id, month_start, month_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        for day in sorted(day_groups.keys()):
            ctx = build_poc_context(
                intraday_con, entity_id, day, day_groups, setup["bhav"], setup["ex_dates"], jump_dates,
                single_day_cache, rank_lookup, setup["trend_lookup"], eligible_ctx_cache,
            )
            if ctx["skip"] == "LOOKBACK_INCOMPLETE":
                continue
            pool.append({
                "candles5": ctx["today_candles5"], "day_raw": ctx["today_day_raw"],
                "valid_idx": _valid_entry_idx(ctx["today_candles5"]),
                "prev_high": ctx["prev_high"], "band": ctx["band"],
            })
    return pool


def _selection_draw(ctx: dict, sampled_pct: float, rng: np.random.Generator) -> float | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = entry_price * (1 - sampled_pct)
    target_price = ctx["prev_high"] * (1 - TARGET_BELOW_PREV_HIGH_PCT)
    if stop_price <= 0 or (entry_price - stop_price) / entry_price > MAX_RISK_PCT:
        return None
    if target_price <= entry_price:
        return None
    qty = position_size_shares(entry_price, stop_price)
    if qty < 1:
        return None
    exit_res = resolve_exit(ctx["day_raw"], ctx["candles5"], fill_ts, entry_price, stop_price, target_price)
    pnl_rs = qty * (exit_res["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    cost_rs = round_trip_cost_rs(position_size_rs, ctx["band"])
    return (pnl_rs - cost_rs) / FIXED_RISK_RS


def selection_null_seed_mean(month_pool: list[dict], count: int, rng: np.random.Generator,
                              rho_pool: np.ndarray) -> list[float]:
    """Draws `count` random (entity, T) pairs WITH REPLACEMENT from
    `month_pool`. Returns the raw draw list (the caller pools across
    months before averaging)."""
    if not month_pool:
        return []
    draws = []
    n = len(month_pool)
    for _ in range(count):
        ctx = month_pool[int(rng.integers(0, n))]
        sampled_pct = float(rho_pool[int(rng.integers(0, len(rho_pool)))])
        r = _selection_draw(ctx, sampled_pct, rng)
        if r is not None:
            draws.append(r)
    return draws
