"""PREREGISTRATION_POC_V4.md: POC family V4, liquidity sweep and reclaim.

ALL new logic for V4 lives in this one file, per instruction. V1's own
files (`src/poc/context.py`, `poc.py`, `trend.py`, `resolution.py`,
`backtest.py`, `nulls.py`, `test_seal.py`), V2's (`src/poc/v2.py`), and
V3's (`src/poc/v3.py`) are imported and reused READ-ONLY -- never
modified, so none of their closed results can be touched by anything in
this module.

V4 replaces V1-V3's touch/confirmation entirely with a liquidity-sweep-
and-reclaim entry (prereg Section 4): a 5-minute candle must sweep below
LOOKBACK_LOW (V2's own 5-day-window low) by 0.1x-1.0x ATR(14), then a
candle within the next 3 must CLOSE back above LOOKBACK_LOW. Stop =
sweep_low - 0.1x ATR. Sizing, both risk guards, target, resolution, cost
model, universe, and both nulls are ALL reused unchanged from `poc.v2`
(V4 is V2 with the entry condition replaced, nothing else).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import pandas as pd

from box_theory.context import group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from fibo.daily_ohlc import build_daily_ohlc_panel
from fibo.indicators import atr as compute_atr_panel
from fibo.price_scale import to_raw_scale

from poc.backtest import _build_trend_lookup_for_entity, _entity_years, build_universe
from poc.context import build_poc_context, lookback_dates
from poc.resolution import (
    ENTRY_WINDOW_END, ENTRY_WINDOW_START, MAX_RISK_PCT, TARGET_BELOW_PREV_HIGH_PCT,
    fill_bar_after_candle_close, resolve_exit,
)
from poc.v2 import CAPITAL_RS, MIN_RISK_PCT, compute_lookback_low, position_size_shares_v2

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import assert_universe_membership, restrict_to_universe

# ---------------------------------------------------------------------
# V4's own frozen parameters (Parameter Provenance: construction
# principles, not evidence -- see PREREGISTRATION_POC_V4.md)
# ---------------------------------------------------------------------

SWEEP_DEPTH_MIN_ATR = 0.1
SWEEP_DEPTH_MAX_ATR = 1.0
RECLAIM_WINDOW_CANDLES = 3
STOP_BUFFER_ATR = 0.1

SKIP_REASONS = (
    "lookback_incomplete", "trend_filter_failed", "atr_unavailable",
    "no_sweep", "touch_too_shallow", "breakdown_not_sweep", "not_reclaimed",
    "no_fill_bar", "fill_outside_window", "entry_below_stop", "stop_too_wide", "stop_too_tight", "no_room",
)


# ---------------------------------------------------------------------
# ATR lookup (per entity, raw-scale-converted PER TRADE DATE) -- same
# caching shape as poc.backtest._build_trend_lookup_for_entity
# ---------------------------------------------------------------------

def _build_atr_adjusted_lookup_for_entity(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, jump_dates: set,
) -> dict[dt.date, float]:
    """{trade_date: ATR(14)} on `fibo.daily_ohlc`'s own ENTITY-ADJUSTED
    scale -- NOT yet converted to any particular trade date's raw scale
    (that conversion needs a DIFFERENT factor per trade date, done by the
    caller via `_build_adjustment_factor_lookup_for_entity` below, never
    here). `fibo.indicators.atr`'s own built-in stale-gap/jump handling
    (NaN-and-carry-forward, not a dropped row) is used as-is -- passing
    `unexplained_jump_dates` directly, not pre-filtering rows, since that
    is the mechanism the indicator module itself was built with."""
    daily_panel = build_daily_ohlc_panel(warehouse_con, entity_ids=[entity_id])
    if daily_panel.empty:
        return {}
    atr_df = compute_atr_panel(daily_panel, unexplained_jump_dates={entity_id: jump_dates} if jump_dates else None)
    return dict(zip(atr_df["trade_date"].dt.date, atr_df["atr"]))


def _build_adjustment_factor_lookup_for_entity(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str,
) -> dict[dt.date, float]:
    """{trade_date: factor} for this entity, straight from the
    materialized `adjustment_factors` table (one query, not one per day
    -- `fibo.price_scale.get_adjustment_factor` does a single-row lookup
    per call, fine for the interactive chart tool it was built for, too
    slow called once per entity-day across a full DEV backtest)."""
    rows = warehouse_con.execute(
        "SELECT trade_date, factor FROM adjustment_factors WHERE entity_id = ?", [entity_id],
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------
# SWEEP and RECLAIM (prereg Section 4) -- replaces find_touch_idx/
# find_confirmation entirely
# ---------------------------------------------------------------------

def find_sweep(candles5: pd.DataFrame, lookback_low: float, atr_raw: float) -> dict:
    """Scans candles5 in session order from 09:45 onward. Returns
    {"status": "SWEEP", "idx": i, "sweep_low": float} or {"status":
    "BREAKDOWN_NOT_SWEEP"} or {"status": "TOUCH_TOO_SHALLOW"} or
    {"status": "NO_SWEEP"}."""
    times = candles5["ts"].dt.time
    in_window = candles5.index[times >= ENTRY_WINDOW_START]
    saw_shallow_touch = False
    for idx in in_window:
        low = float(candles5.loc[idx, "low"])
        if low >= lookback_low:
            continue
        depth = lookback_low - low
        if depth > SWEEP_DEPTH_MAX_ATR * atr_raw:
            return {"status": "BREAKDOWN_NOT_SWEEP"}
        if depth >= SWEEP_DEPTH_MIN_ATR * atr_raw:
            return {"status": "SWEEP", "idx": int(idx), "sweep_low": low}
        saw_shallow_touch = True
        # depth < SWEEP_DEPTH_MIN_ATR * atr_raw -- "not a sweep, keep watching"
    return {"status": "TOUCH_TOO_SHALLOW" if saw_shallow_touch else "NO_SWEEP"}


def find_reclaim(candles5: pd.DataFrame, sweep_idx: int, sweep_low: float, lookback_low: float) -> dict:
    """Checks up to RECLAIM_WINDOW_CANDLES candidates strictly after
    sweep_idx. Returns {"status": "RECLAIMED", "idx": i, "sweep_low":
    float (the FINAL, possibly-updated value)} or {"status":
    "NOT_RECLAIMED", "sweep_low": float, "new_low_seen": bool}.

    "do not reset" the 3-candle clock on a new low, per instruction: the
    loop always runs offsets 1..RECLAIM_WINDOW_CANDLES from the ORIGINAL
    sweep_idx, never from wherever a new low happened to occur."""
    n = len(candles5)
    new_low_seen = False
    for offset in range(1, RECLAIM_WINDOW_CANDLES + 1):
        idx = sweep_idx + offset
        if idx >= n:
            break
        row = candles5.iloc[idx]
        low = float(row["low"])
        if low < sweep_low:
            sweep_low = low
            new_low_seen = True
        if float(row["close"]) > lookback_low:
            return {"status": "RECLAIMED", "idx": idx, "sweep_low": sweep_low}
    return {"status": "NOT_RECLAIMED", "sweep_low": sweep_low, "new_low_seen": new_low_seen}


# ---------------------------------------------------------------------
# Entry (prereg Section 5) -- sweep/reclaim/fill are V4's own; stop
# guards, target, sizing are byte-identical to poc.v2.find_entry_v2
# ---------------------------------------------------------------------

def find_entry_v4(
    candles5: pd.DataFrame, bars1: pd.DataFrame, lookback_low: float, prev_high: float, atr_raw: float,
) -> dict:
    """Returns a dict with at least {"status": ...}, status one of:
    "NO_SWEEP", "TOUCH_TOO_SHALLOW", "BREAKDOWN_NOT_SWEEP", "NOT_
    RECLAIMED", "NO_FILL_BAR", "FILL_OUTSIDE_WINDOW", "ENTRY_BELOW_
    STOP", "STOP_TOO_WIDE", "STOP_TOO_TIGHT", "NO_ROOM", "ENTERED".
    On ENTERED (and several skip statuses), also carries diagnostic
    fields used by the Section 12 report: `sweep_depth_atr` (at
    detection), `new_low_during_reclaim` (bool)."""
    sweep = find_sweep(candles5, lookback_low, atr_raw)
    if sweep["status"] != "SWEEP":
        return {"status": sweep["status"]}

    sweep_idx, sweep_low_at_detection = sweep["idx"], sweep["sweep_low"]
    sweep_depth_atr = (lookback_low - sweep_low_at_detection) / atr_raw

    reclaim = find_reclaim(candles5, sweep_idx, sweep_low_at_detection, lookback_low)
    if reclaim["status"] == "NOT_RECLAIMED":
        return {
            "status": "NOT_RECLAIMED", "sweep_idx": sweep_idx, "sweep_depth_atr": sweep_depth_atr,
            "new_low_during_reclaim": reclaim["new_low_seen"],
        }

    reclaim_idx, final_sweep_low = reclaim["idx"], reclaim["sweep_low"]
    new_low_during_reclaim = final_sweep_low < sweep_low_at_detection

    reclaim_candle = candles5.iloc[reclaim_idx]
    reclaim_close_ts = reclaim_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, reclaim_close_ts)
    if fill_bar is None:
        return {
            "status": "NO_FILL_BAR", "sweep_idx": sweep_idx, "reclaim_idx": reclaim_idx,
            "sweep_depth_atr": sweep_depth_atr, "new_low_during_reclaim": new_low_during_reclaim,
        }

    fill_ts = pd.Timestamp(fill_bar["ts"])
    fill_time = fill_ts.time()
    if not (ENTRY_WINDOW_START <= fill_time <= ENTRY_WINDOW_END):
        return {
            "status": "FILL_OUTSIDE_WINDOW", "sweep_idx": sweep_idx, "reclaim_idx": reclaim_idx,
            "fill_ts": fill_ts, "sweep_depth_atr": sweep_depth_atr,
            "new_low_during_reclaim": new_low_during_reclaim,
        }

    entry_price = float(fill_bar["open"])
    stop_price = final_sweep_low - STOP_BUFFER_ATR * atr_raw  # Section 5's own stop formula

    common = {
        "sweep_idx": sweep_idx, "reclaim_idx": reclaim_idx, "fill_ts": fill_ts,
        "entry_price": entry_price, "stop_price": stop_price,
        "sweep_depth_atr": sweep_depth_atr, "new_low_during_reclaim": new_low_during_reclaim,
    }

    # from here, byte-identical order/guards to poc.v2.find_entry_v2:
    if entry_price <= stop_price:
        return {"status": "ENTRY_BELOW_STOP", **common}
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT:
        return {"status": "STOP_TOO_WIDE", **common}
    if risk_pct < MIN_RISK_PCT:
        return {"status": "STOP_TOO_TIGHT", **common}

    target_price = prev_high * (1 - TARGET_BELOW_PREV_HIGH_PCT)
    if target_price <= entry_price:
        return {"status": "NO_ROOM", "target_price": target_price, **common}

    qty = position_size_shares_v2(entry_price)

    return {"status": "ENTERED", "confirm_kind": "RECLAIM", "target_price": target_price, "qty": qty, **common}


# ---------------------------------------------------------------------
# Backtest orchestration -- same shape as poc.v2/v3's own
# ---------------------------------------------------------------------

_ENTRY_STATUS_TO_SKIP = {
    "NO_SWEEP": "no_sweep", "TOUCH_TOO_SHALLOW": "touch_too_shallow",
    "BREAKDOWN_NOT_SWEEP": "breakdown_not_sweep", "NOT_RECLAIMED": "not_reclaimed",
    "NO_FILL_BAR": "no_fill_bar", "FILL_OUTSIDE_WINDOW": "fill_outside_window",
    "ENTRY_BELOW_STOP": "entry_below_stop", "STOP_TOO_WIDE": "stop_too_wide",
    "STOP_TOO_TIGHT": "stop_too_tight", "NO_ROOM": "no_room",
}


def evaluate_entity_v4(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict,
) -> dict:
    trades: list[dict] = []
    skips = {r: 0 for r in SKIP_REASONS}
    lookback_incomplete_detail: dict[tuple, int] = {}
    sweep_depths_atr: list[float] = []  # EVERY day that reached SWEEP (any eventual outcome)
    new_low_during_reclaim_count = 0
    reached_reclaim_count = 0
    errors: list[dict] = []

    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache: dict[dt.date, pd.DataFrame] = {}
    eligible_ctx_cache: dict[dt.date, dict] = {}
    trend_lookup = _build_trend_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    atr_adjusted_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)

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

            # ATR "through the previous trading day" -- dates["L5"], the
            # same day the trend filter is itself evaluated at.
            l5 = lookback_dates(day)["L5"]
            atr_adjusted = atr_adjusted_lookup.get(l5)
            factor_today = factor_lookup.get(day)
            if atr_adjusted is None or pd.isna(atr_adjusted) or factor_today is None:
                skips["atr_unavailable"] += 1
                continue
            atr_raw = to_raw_scale(atr_adjusted, factor_today)

            today_day_raw, today_candles5 = ctx["today_day_raw"], ctx["today_candles5"]
            prev_high = ctx["prev_high"]
            band, rank, year_of_day = ctx["band"], ctx["rank"], ctx["year"]

            entry = find_entry_v4(today_candles5, today_day_raw, lookback_low, prev_high, atr_raw)
            status = entry["status"]
            if "sweep_depth_atr" in entry:
                sweep_depths_atr.append(entry["sweep_depth_atr"])
            # any status past the three sweep-detection failures means a
            # valid SWEEP was found and the reclaim-wait loop ran
            if status not in ("NO_SWEEP", "TOUCH_TOO_SHALLOW", "BREAKDOWN_NOT_SWEEP"):
                reached_reclaim_count += 1
                if entry.get("new_low_during_reclaim"):
                    new_low_during_reclaim_count += 1

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
                "prev_high": prev_high, "lookback_low": lookback_low, "atr_raw": atr_raw,
                "sweep_idx": entry["sweep_idx"], "reclaim_idx": entry["reclaim_idx"],
                "sweep_depth_atr": entry["sweep_depth_atr"],
                "new_low_during_reclaim": entry["new_low_during_reclaim"],
                "confirm_kind": entry["confirm_kind"], "fill_ts": entry["fill_ts"],
                "entry_price": entry_price, "stop_price": stop_price,
                "target_price": entry["target_price"], "qty": qty,
                "outcome": exit_res["outcome"], "exit_ts": exit_res["exit_ts"],
                "exit_price": exit_res["exit_price"], "time_exit_fallback": exit_res["time_exit_fallback"],
                "position_size_rs": position_size_rs, "cost_rs": cost_rs,
                "pnl_rs": pnl_rs, "gross_return_pct": gross_return_pct, "net_return_pct": net_return_pct,
                "stop_distance_pct": (entry_price - stop_price) / entry_price,
                "cost_pct": cost_rs / position_size_rs,
                "entry_above_lookback_low_frac": (entry_price - lookback_low) / entry_price,
            })

    return {
        "trades": trades, "skips": skips, "lookback_incomplete_detail": lookback_incomplete_detail,
        "sweep_depths_atr": sweep_depths_atr, "new_low_during_reclaim_count": new_low_during_reclaim_count,
        "reached_reclaim_count": reached_reclaim_count, "errors": errors,
    }


def run_backtest_v4(
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
                "lookback_incomplete_detail": {}, "sweep_depths_atr": [], "new_low_during_reclaim_count": 0,
                "reached_reclaim_count": 0, "errors": [], "universe": universe}
    candidates = restrict_to_universe(candidates, universe)
    entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    all_trades: list[dict] = []
    total_skips = {r: 0 for r in SKIP_REASONS}
    total_lookback_detail: dict[tuple, int] = {}
    all_sweep_depths: list[float] = []
    total_new_low_during_reclaim = 0
    total_reached_reclaim = 0
    all_errors: list[dict] = []

    for entity_id, years in entity_years.items():
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_entity_v4(
            intraday_con, warehouse_con, entity_id, years, start, end, jump_dates, rank_lookup,
        )
        all_trades.extend(result["trades"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        for key, v in result["lookback_incomplete_detail"].items():
            total_lookback_detail[key] = total_lookback_detail.get(key, 0) + v
        all_sweep_depths.extend(result["sweep_depths_atr"])
        total_new_low_during_reclaim += result["new_low_during_reclaim_count"]
        total_reached_reclaim += result["reached_reclaim_count"]
        all_errors.extend(result["errors"])

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label="poc v4 trade list")

    return {
        "trades": trades_df, "skips": total_skips, "lookback_incomplete_detail": total_lookback_detail,
        "sweep_depths_atr": all_sweep_depths, "new_low_during_reclaim_count": total_new_low_during_reclaim,
        "reached_reclaim_count": total_reached_reclaim, "errors": all_errors, "universe": universe,
    }


# ---------------------------------------------------------------------
# V4's own sealed TEST window -- own object, own log, shares nothing
# with poc.test_seal (V1), poc.v2, or poc.v3
# ---------------------------------------------------------------------

SEALED_AT = dt.date(2026, 10, 29)

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 18)

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "poc" / "v4" / "test_window_access_log.txt"


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside V4's own sealed test window."""


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
            f"requested range end {end} intersects POC V4's own sealed test window "
            f"(>= {TEST_START}). This is disallowed by default. If this really is the "
            f"one authorized end-of-study test evaluation, pass authorize_test=True "
            f"explicitly -- and only there."
        )
