"""PREREGISTRATION_POC_V2.md: POC bounce V2, fixed-capital sizing.

ALL new logic for V2 lives in this one file, per instruction. V1's own
files (`src/poc/context.py`, `poc.py`, `trend.py`, `resolution.py`,
`backtest.py`, `nulls.py`, `test_seal.py`) are imported and reused
READ-ONLY -- never modified, so V1's closed result (`POC_FINDINGS.md`)
cannot be touched by anything in this module.

Two changes from V1 (Section "TWO CHANGES FROM V1" of the prereg doc):
  1. FIXED-CAPITAL SIZING: qty = floor(25000 / entry_price), min 1 share.
  2. STOP = the same 5-trading-day lookback window's own LOW (pairs with
     V1's own PREV_HIGH = that window's own HIGH), with a 5% maximum and
     a NEW 0.5% minimum stop-distance floor (OPERATIONS.md's own
     standing rule, written specifically because of V1's failure).

Everything else -- universe, the six-day lookback-eligibility chain,
PROXY POC construction, the 50-day trend filter, touch/GREEN/HAMMER
confirmation, the fill mechanic, 1-minute-bar stop/target/time-exit
resolution, and the cost model -- is reused unchanged from V1.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from box_theory.context import eligible_day_context, group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.backtest import _build_trend_lookup_for_entity, _entity_years, build_universe
from poc.context import _cached_eligible_day_context, build_poc_context, lookback_dates
from poc.nulls import _random_fill, _valid_entry_idx, get_or_build_entity_setup
from poc.resolution import (
    MAX_RISK_PCT, TARGET_BELOW_PREV_HIGH_PCT, fill_bar_after_candle_close, find_confirmation,
    find_touch_idx, resolve_exit,
)

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import assert_universe_membership, restrict_to_universe

# ---------------------------------------------------------------------
# V2's own frozen parameters
# ---------------------------------------------------------------------

CAPITAL_RS = 25_000.0
MIN_RISK_PCT = 0.005  # NEW: OPERATIONS.md's standing minimum stop-distance floor

SKIP_REASONS = (
    "lookback_incomplete", "trend_filter_failed", "no_touch", "poc_failed", "no_confirmation",
    "no_fill_bar", "fill_outside_window", "entry_below_stop", "stop_too_wide", "stop_too_tight", "no_room",
)


def position_size_shares_v2(entry_price: float) -> int:
    """Change 1: qty = max(1, floor(25000 / entry_price)) -- does NOT
    depend on stop distance at all, which is exactly what structurally
    removes V1's sizing pathology (see PREREGISTRATION_POC_V2.md's own
    "TWO CHANGES FROM V1" section)."""
    if entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    return max(1, int(CAPITAL_RS // entry_price))


# ---------------------------------------------------------------------
# Lookback LOW (Section 4a) -- the mirror of V1's own PREV_HIGH
# ---------------------------------------------------------------------

def compute_lookback_low(
    intraday_con: duckdb.DuckDBPyConnection, entity_id: str, today: dt.date,
    day_groups: dict, bhav: pd.DataFrame, ex_dates: set, jump_dates: set,
    single_day_cache: dict, rank_lookup: dict, eligible_ctx_cache: dict | None,
) -> float:
    """MIN(low) across L1..L5's own RAW-scale 1-minute bars -- reuses
    `poc.context._cached_eligible_day_context` (the SAME per-day cache
    `poc.context.build_poc_context` already populated for this exact
    (entity, today) call, so this is a cache hit, not a second fetch)
    rather than touching `poc.context.py` itself to expose these frames
    directly."""
    dates = lookback_dates(today)
    lows = []
    for label in ("L1", "L2", "L3", "L4", "L5"):
        ctx = _cached_eligible_day_context(
            intraday_con, entity_id, dates[label], day_groups, bhav, ex_dates, jump_dates,
            single_day_cache, rank_lookup, eligible_ctx_cache,
        )
        lows.append(float(ctx["day_raw"]["low"].min()))
    return min(lows)


# ---------------------------------------------------------------------
# Entry (Section 7) -- touch/confirm/fill reused from poc.resolution;
# stop/sizing/checks are V2's own
# ---------------------------------------------------------------------

def find_entry_v2(candles5: pd.DataFrame, bars1: pd.DataFrame, poc_price: float, prev_high: float,
                   lookback_low: float) -> dict:
    """Same shape as `poc.resolution.find_entry`, with Change 2's stop
    and Change 1's sizing. Returns a dict with at least {"status": ...},
    status one of: "NO_TOUCH", "POC_FAILED", "NO_CONFIRMATION",
    "NO_FILL_BAR", "FILL_OUTSIDE_WINDOW", "ENTRY_BELOW_STOP",
    "STOP_TOO_WIDE", "STOP_TOO_TIGHT", "NO_ROOM", "ENTERED"."""
    touch_idx = find_touch_idx(candles5, poc_price)
    if touch_idx is None:
        return {"status": "NO_TOUCH"}

    confirm = find_confirmation(candles5, touch_idx, poc_price)
    if confirm["status"] == "NO_CONFIRMATION":
        return {"status": "NO_CONFIRMATION", "touch_idx": touch_idx}
    if confirm["status"] == "POC_FAILED":
        return {"status": "POC_FAILED", "touch_idx": touch_idx, "confirm_idx": confirm["confirm_idx"]}

    confirm_idx = confirm["confirm_idx"]
    confirm_candle = candles5.iloc[confirm_idx]
    confirm_close_ts = confirm_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, confirm_close_ts)
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", "touch_idx": touch_idx, "confirm_idx": confirm_idx}

    fill_ts = pd.Timestamp(fill_bar["ts"])
    fill_time = fill_ts.time()
    from poc.resolution import ENTRY_WINDOW_START, ENTRY_WINDOW_END
    if not (ENTRY_WINDOW_START <= fill_time <= ENTRY_WINDOW_END):
        return {
            "status": "FILL_OUTSIDE_WINDOW", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts,
        }

    entry_price = float(fill_bar["open"])
    stop_price = lookback_low  # Change 2

    # Section 7, checked in order:
    if entry_price <= stop_price:
        return {
            "status": "ENTRY_BELOW_STOP", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price,
        }
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT:
        return {
            "status": "STOP_TOO_WIDE", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price,
        }
    if risk_pct < MIN_RISK_PCT:
        return {
            "status": "STOP_TOO_TIGHT", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price,
        }

    target_price = prev_high * (1 - TARGET_BELOW_PREV_HIGH_PCT)
    if target_price <= entry_price:
        return {
            "status": "NO_ROOM", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price,
            "target_price": target_price,
        }

    qty = position_size_shares_v2(entry_price)  # Change 1 -- always >= 1, no ZERO_QTY possible

    return {
        "status": "ENTERED", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
        "confirm_kind": confirm["confirm_kind"], "fill_ts": fill_ts,
        "entry_price": entry_price, "stop_price": stop_price, "target_price": target_price, "qty": qty,
    }


# ---------------------------------------------------------------------
# Backtest orchestration (same shape as poc.backtest, percentage-return
# trade records instead of R)
# ---------------------------------------------------------------------

_ENTRY_STATUS_TO_SKIP = {
    "NO_TOUCH": "no_touch", "POC_FAILED": "poc_failed", "NO_CONFIRMATION": "no_confirmation",
    "NO_FILL_BAR": "no_fill_bar", "FILL_OUTSIDE_WINDOW": "fill_outside_window",
    "ENTRY_BELOW_STOP": "entry_below_stop", "STOP_TOO_WIDE": "stop_too_wide",
    "STOP_TOO_TIGHT": "stop_too_tight", "NO_ROOM": "no_room",
}


def evaluate_entity_v2(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict,
) -> dict:
    trades: list[dict] = []
    skips = {r: 0 for r in SKIP_REASONS}
    lookback_incomplete_detail: dict[tuple, int] = {}
    errors: list[dict] = []

    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache: dict[dt.date, pd.DataFrame] = {}
    eligible_ctx_cache: dict[dt.date, dict] = {}
    trend_lookup = _build_trend_lookup_for_entity(warehouse_con, entity_id, jump_dates)

    for year in years:
        year_start = max(dt.date(year, 1, 1), start)
        year_end = min(dt.date(year, 12, 31), end)
        if year_start > year_end:
            continue
        block = fetch_bars_range(intraday_con, entity_id, year_start, year_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        trade_dates = sorted(day_groups.keys())

        for day in trade_dates:
            ctx = build_poc_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup, trend_lookup, eligible_ctx_cache,
            )
            if ctx["skip"] == "LOOKBACK_INCOMPLETE":
                skips["lookback_incomplete"] += 1
                detail = ctx["detail"]
                key = (detail["failed_at"], detail["reason"])
                lookback_incomplete_detail[key] = lookback_incomplete_detail.get(key, 0) + 1
                continue

            lookback_low = compute_lookback_low(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup, eligible_ctx_cache,
            )

            if ctx["skip"] == "TREND_FILTER_FAILED":
                skips["trend_filter_failed"] += 1
                continue

            today_day_raw, today_candles5 = ctx["today_day_raw"], ctx["today_candles5"]
            poc_price, prev_high = ctx["poc_price"], ctx["prev_high"]
            band, rank, year_of_day = ctx["band"], ctx["rank"], ctx["year"]

            entry = find_entry_v2(today_candles5, today_day_raw, poc_price, prev_high, lookback_low)
            status = entry["status"]
            if status != "ENTERED":
                skips[_ENTRY_STATUS_TO_SKIP[status]] += 1
                continue

            try:
                exit_res = resolve_exit(
                    today_day_raw, today_candles5, entry["fill_ts"], entry["entry_price"],
                    entry["stop_price"], entry["target_price"],
                )
            except Exception as e:
                errors.append({"entity_id": entity_id, "trade_date": day, "error": f"{type(e).__name__}: {e}"})
                continue

            qty = entry["qty"]
            entry_price = entry["entry_price"]
            stop_price = entry["stop_price"]
            pnl_rs = qty * (exit_res["exit_price"] - entry_price)
            position_size_rs = qty * entry_price
            cost_rs = round_trip_cost_rs(position_size_rs, band)
            net_return_pct = (pnl_rs - cost_rs) / position_size_rs
            gross_return_pct = pnl_rs / position_size_rs

            trades.append({
                "entity_id": entity_id, "trade_date": day, "year": year_of_day,
                "band": band, "rank": rank,
                "poc_price": poc_price, "prev_high": prev_high, "lookback_low": lookback_low,
                "touch_idx": entry["touch_idx"], "confirm_idx": entry["confirm_idx"],
                "confirm_kind": entry["confirm_kind"], "fill_ts": entry["fill_ts"],
                "entry_price": entry_price, "stop_price": stop_price,
                "target_price": entry["target_price"], "qty": qty,
                "outcome": exit_res["outcome"], "exit_ts": exit_res["exit_ts"],
                "exit_price": exit_res["exit_price"], "time_exit_fallback": exit_res["time_exit_fallback"],
                "position_size_rs": position_size_rs, "cost_rs": cost_rs,
                "pnl_rs": pnl_rs, "gross_return_pct": gross_return_pct, "net_return_pct": net_return_pct,
                "stop_distance_pct": (entry_price - stop_price) / entry_price,
                "cost_pct": cost_rs / position_size_rs,
                "entry_above_poc_frac": (entry_price - poc_price) / entry_price,
            })

    return {"trades": trades, "skips": skips, "lookback_incomplete_detail": lookback_incomplete_detail,
            "errors": errors}


def run_backtest_v2(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    start: dt.date, end: dt.date, entity_ids: list[str] | None = None,
) -> dict:
    universe = build_universe(warehouse_con)
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)

    raw_entity_years = _entity_years(universe, start, end)
    if entity_ids is not None:
        raw_entity_years = {e: y for e, y in raw_entity_years.items() if e in entity_ids}
    candidates = pd.DataFrame(
        [{"entity_id": e, "year": y} for e, years in raw_entity_years.items() for y in years]
    )
    if candidates.empty:
        return {"trades": pd.DataFrame(), "skips": {r: 0 for r in SKIP_REASONS},
                "lookback_incomplete_detail": {}, "errors": [], "universe": universe}
    candidates = restrict_to_universe(candidates, universe)
    entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    all_trades: list[dict] = []
    total_skips = {r: 0 for r in SKIP_REASONS}
    total_lookback_detail: dict[tuple, int] = {}
    all_errors: list[dict] = []

    for entity_id, years in entity_years.items():
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_entity_v2(
            intraday_con, warehouse_con, entity_id, years, start, end, jump_dates, rank_lookup,
        )
        all_trades.extend(result["trades"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        for key, v in result["lookback_incomplete_detail"].items():
            total_lookback_detail[key] = total_lookback_detail.get(key, 0) + v
        all_errors.extend(result["errors"])

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label="poc v2 trade list")

    return {"trades": trades_df, "skips": total_skips, "lookback_incomplete_detail": total_lookback_detail,
            "errors": all_errors, "universe": universe}


# ---------------------------------------------------------------------
# TIMING null (Section 10)
# ---------------------------------------------------------------------

def build_timing_pool_v2(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    trades: pd.DataFrame, rank_lookup: dict, jump_dates_by_entity: dict,
) -> list[dict]:
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
                continue
            stop_distance = float(row["entry_price"]) - float(row["stop_price"])
            pool.append({
                "candles5": dctx["candles5"], "day_raw": dctx["day_raw"],
                "valid_idx": _valid_entry_idx(dctx["candles5"]),
                "stop_distance": stop_distance, "target_price": float(row["target_price"]),
                "band": row["band"],
            })
    return pool


def _timing_draw_v2(ctx: dict, rng: np.random.Generator) -> float | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = entry_price - ctx["stop_distance"]
    target_price = ctx["target_price"]
    if stop_price <= 0 or entry_price <= stop_price:
        return None
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT or risk_pct < MIN_RISK_PCT:
        return None
    if target_price <= entry_price:
        return None
    qty = position_size_shares_v2(entry_price)
    exit_res = resolve_exit(ctx["day_raw"], ctx["candles5"], fill_ts, entry_price, stop_price, target_price)
    pnl_rs = qty * (exit_res["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    cost_rs = round_trip_cost_rs(position_size_rs, ctx["band"])
    return (pnl_rs - cost_rs) / position_size_rs


def timing_null_seed_mean_v2(pool: list[dict], rng: np.random.Generator) -> float:
    draws = [r for ctx in pool if (r := _timing_draw_v2(ctx, rng)) is not None]
    return float(np.mean(draws)) if draws else float("nan")


# ---------------------------------------------------------------------
# SELECTION null (Section 10)
# ---------------------------------------------------------------------

def build_month_pool_v2(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    universe: pd.DataFrame, year: int, month: int, rank_lookup: dict, jump_dates_by_entity: dict,
    entity_setup_cache: dict, full_start: dt.date, full_end: dt.date,
) -> list[dict]:
    """Same population and per-entity-setup caching as `poc.nulls.
    build_month_pool` (reuses `poc.nulls.get_or_build_entity_setup`
    directly) -- each pooled day additionally carries its own
    `lookback_low`, computed the same way a real day's would be, so
    V2's SELECTION null can recompute STOP deterministically per draw
    (Section 10's own stated reasoning, mirroring how V1's own
    SELECTION null already recomputes TARGET fresh per draw)."""
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
            lookback_low = compute_lookback_low(
                intraday_con, entity_id, day, day_groups, setup["bhav"], setup["ex_dates"], jump_dates,
                single_day_cache, rank_lookup, eligible_ctx_cache,
            )
            pool.append({
                "candles5": ctx["today_candles5"], "day_raw": ctx["today_day_raw"],
                "valid_idx": _valid_entry_idx(ctx["today_candles5"]),
                "prev_high": ctx["prev_high"], "lookback_low": lookback_low, "band": ctx["band"],
            })
    return pool


def _selection_draw_v2(ctx: dict, rng: np.random.Generator) -> float | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = ctx["lookback_low"]  # deterministic, the drawn day's own real lookback low
    target_price = ctx["prev_high"] * (1 - TARGET_BELOW_PREV_HIGH_PCT)
    if entry_price <= stop_price:
        return None
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT or risk_pct < MIN_RISK_PCT:
        return None
    if target_price <= entry_price:
        return None
    qty = position_size_shares_v2(entry_price)
    exit_res = resolve_exit(ctx["day_raw"], ctx["candles5"], fill_ts, entry_price, stop_price, target_price)
    pnl_rs = qty * (exit_res["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    cost_rs = round_trip_cost_rs(position_size_rs, ctx["band"])
    return (pnl_rs - cost_rs) / position_size_rs


def selection_null_seed_mean_v2(month_pool: list[dict], count: int, rng: np.random.Generator) -> list[float]:
    """No `rho_pool` argument (unlike V1's own `selection_null_seed_
    mean`) -- V2's stop is deterministic per drawn day, not sampled from
    a distribution, per Section 10's own stated reasoning."""
    if not month_pool:
        return []
    draws = []
    n = len(month_pool)
    for _ in range(count):
        ctx = month_pool[int(rng.integers(0, n))]
        r = _selection_draw_v2(ctx, rng)
        if r is not None:
            draws.append(r)
    return draws


# ---------------------------------------------------------------------
# V2's own sealed TEST window -- own object, own log, shares nothing
# with poc.test_seal (V1's)
# ---------------------------------------------------------------------

SEALED_AT = dt.date(2026, 10, 28)

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 18)

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "poc" / "v2" / "test_window_access_log.txt"


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside V2's own sealed test window."""


def _log_test_window_access(start: dt.date, end: dt.date, caller: str, reason: str) -> None:
    ACCESS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ACCESS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            f"{dt.datetime.now().isoformat()} | range=[{start},{end}] | caller={caller} | "
            f"authorize_test=True | {reason}\n"
        )


def guard_date_range(start: dt.date, end: dt.date, authorize_test: bool = False,
                      caller: str = "", reason: str = "") -> None:
    if authorize_test:
        if end >= TEST_START:
            _log_test_window_access(start, end, caller or "(caller not specified)",
                                     reason or "(reason not specified)")
        return
    if end >= TEST_START:
        raise TestWindowViolationError(
            f"requested range end {end} intersects POC V2's own sealed test window "
            f"(>= {TEST_START}). This is disallowed by default. If this really is the "
            f"one authorized end-of-study test evaluation, pass authorize_test=True "
            f"explicitly -- and only there."
        )
