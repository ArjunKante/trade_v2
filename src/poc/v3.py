"""PREREGISTRATION_POC_V3.md: POC bounce V3, hourly confirmation.

ALL new logic for V3 lives in this one file, per instruction. V1's own
files (`src/poc/context.py`, `poc.py`, `trend.py`, `resolution.py`,
`backtest.py`, `nulls.py`, `test_seal.py`) and V2's own file (`src/poc/
v2.py`) are imported and reused READ-ONLY -- never modified, so neither
study's closed result (`POC_FINDINGS.md`, `POC_V2_FINDINGS.md`) can be
touched by anything in this module.

ONE change from V2 (prereg doc's own "ONE CHANGE FROM V2" section): the
touch/confirmation timeframe moves from 5-minute candles to 1-hour
candles (`fvg.bars.aggregate_to_1hour`, anchored at the 09:15 session
open -- the day's last bucket is the PARTIAL 15:15-15:30 one). Stop
(the same 5-day lookback low), sizing (the same fixed Rs 25,000
capital), target, the 1-minute stop/target scan, the 15:15 time exit
(evaluated against the SAME 5-minute candle grid as V1/V2, never the
hourly one -- see `find_entry_v3`'s own docstring and Section 8 of the
prereg doc for why), the cost model, and both nulls (TIMING, SELECTION)
are ALL reused unchanged from `poc.v2`, called directly, not
reimplemented -- none of them depend on how the real entry's
confirmation was constructed.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import pandas as pd

from box_theory.context import group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from fvg.bars import aggregate_to_1hour

from poc.backtest import _build_trend_lookup_for_entity, _entity_years, build_universe
from poc.context import build_poc_context
from poc.resolution import (
    ENTRY_WINDOW_END, ENTRY_WINDOW_START, MAX_RISK_PCT, TARGET_BELOW_PREV_HIGH_PCT,
    fill_bar_after_candle_close, find_confirmation, find_touch_idx, resolve_exit,
)
from poc.v2 import (
    CAPITAL_RS, MIN_RISK_PCT, compute_lookback_low, position_size_shares_v2,
)

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import assert_universe_membership, restrict_to_universe

SKIP_REASONS = (
    "lookback_incomplete", "trend_filter_failed", "no_touch", "poc_failed", "no_confirmation",
    "no_fill_bar", "fill_outside_window", "entry_below_stop", "stop_too_wide", "stop_too_tight", "no_room",
)


# ---------------------------------------------------------------------
# Entry (prereg Section 7) -- touch/confirm on HOURLY candles (the one
# change); stop/target/sizing checks byte-identical to poc.v2.find_entry_v2
# ---------------------------------------------------------------------

def find_entry_v3(
    candles_hourly: pd.DataFrame, bars1: pd.DataFrame, poc_price: float, prev_high: float,
    lookback_low: float,
) -> dict:
    """Same shape as `poc.v2.find_entry_v2`. `candles_hourly`: this day's
    `fvg.bars.aggregate_to_1hour` output (has `ts`, `bucket_end`, open/
    high/low/close) -- used for touch and confirmation ONLY. `bars1`:
    this day's full 1-minute RAW bars, used for the fill lookup exactly
    as V1/V2 use it. Returns a dict with at least {"status": ...}, status
    one of: "NO_TOUCH", "POC_FAILED", "NO_CONFIRMATION", "NO_FILL_BAR",
    "FILL_OUTSIDE_WINDOW", "ENTRY_BELOW_STOP", "STOP_TOO_WIDE",
    "STOP_TOO_TIGHT", "NO_ROOM", "ENTERED". On any status past NO_TOUCH,
    `touch_idx`/`confirm_idx` index into `candles_hourly` (HOURLY bucket
    indices, NOT 5-minute candle indices the way V1/V2's own fields do --
    callers storing these for reporting should also store the hourly
    candle's own `ts` directly, to avoid ambiguity)."""
    touch_idx = find_touch_idx(candles_hourly, poc_price)
    if touch_idx is None:
        return {"status": "NO_TOUCH"}

    confirm = find_confirmation(candles_hourly, touch_idx, poc_price)
    if confirm["status"] == "NO_CONFIRMATION":
        return {"status": "NO_CONFIRMATION", "touch_idx": touch_idx}
    if confirm["status"] == "POC_FAILED":
        return {"status": "POC_FAILED", "touch_idx": touch_idx, "confirm_idx": confirm["confirm_idx"]}

    confirm_idx = confirm["confirm_idx"]
    confirm_candle = candles_hourly.iloc[confirm_idx]
    # the ONE other change from V2: an hourly candle's close is NOT
    # always ts+60min (the day's last bucket is the 15-minute partial) --
    # use the bucket's own actual bucket_end, never an assumed offset.
    confirm_close_ts = pd.Timestamp(confirm_candle["bucket_end"])
    fill_bar = fill_bar_after_candle_close(bars1, confirm_close_ts)
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", "touch_idx": touch_idx, "confirm_idx": confirm_idx}

    fill_ts = pd.Timestamp(fill_bar["ts"])
    fill_time = fill_ts.time()
    if not (ENTRY_WINDOW_START <= fill_time <= ENTRY_WINDOW_END):
        return {
            "status": "FILL_OUTSIDE_WINDOW", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
            "fill_ts": fill_ts,
        }

    entry_price = float(fill_bar["open"])
    stop_price = lookback_low  # unchanged from V2

    # Section 7, checked in this order, byte-identical to poc.v2.find_entry_v2:
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

    qty = position_size_shares_v2(entry_price)  # unchanged from V2 -- always >= 1

    return {
        "status": "ENTERED", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
        "confirm_kind": confirm["confirm_kind"], "fill_ts": fill_ts,
        "entry_price": entry_price, "stop_price": stop_price, "target_price": target_price, "qty": qty,
    }


# ---------------------------------------------------------------------
# Backtest orchestration -- identical SHAPE to poc.v2.evaluate_entity_v2/
# run_backtest_v2, calling find_entry_v3 against hourly-aggregated candles
# ---------------------------------------------------------------------

_ENTRY_STATUS_TO_SKIP = {
    "NO_TOUCH": "no_touch", "POC_FAILED": "poc_failed", "NO_CONFIRMATION": "no_confirmation",
    "NO_FILL_BAR": "no_fill_bar", "FILL_OUTSIDE_WINDOW": "fill_outside_window",
    "ENTRY_BELOW_STOP": "entry_below_stop", "STOP_TOO_WIDE": "stop_too_wide",
    "STOP_TOO_TIGHT": "stop_too_tight", "NO_ROOM": "no_room",
}


def evaluate_entity_v3(
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

            candles_hourly = aggregate_to_1hour(today_day_raw)

            entry = find_entry_v3(candles_hourly, today_day_raw, poc_price, prev_high, lookback_low)
            status = entry["status"]
            if status != "ENTERED":
                skips[_ENTRY_STATUS_TO_SKIP[status]] += 1
                continue

            try:
                # Section 8: UNCHANGED -- 1-minute scan + 5-minute time-exit
                # grid, never the hourly candles (see find_entry_v3's own
                # docstring / prereg Section 8 for why).
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

            touch_ts = pd.Timestamp(candles_hourly.iloc[entry["touch_idx"]]["ts"])
            confirm_ts = pd.Timestamp(candles_hourly.iloc[entry["confirm_idx"]]["ts"])

            trades.append({
                "entity_id": entity_id, "trade_date": day, "year": year_of_day,
                "band": band, "rank": rank,
                "poc_price": poc_price, "prev_high": prev_high, "lookback_low": lookback_low,
                "touch_idx": entry["touch_idx"], "confirm_idx": entry["confirm_idx"],
                "touch_ts": touch_ts, "confirm_ts": confirm_ts,
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


def run_backtest_v3(
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
        result = evaluate_entity_v3(
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
        assert_universe_membership(check, universe, label="poc v3 trade list")

    return {"trades": trades_df, "skips": total_skips, "lookback_incomplete_detail": total_lookback_detail,
            "errors": all_errors, "universe": universe}


# ---------------------------------------------------------------------
# V3's own sealed TEST window -- own object, own log, shares nothing
# with poc.test_seal (V1's) or poc.v2's
# ---------------------------------------------------------------------

SEALED_AT = dt.date(2026, 10, 28)

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 18)

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "poc" / "v3" / "test_window_access_log.txt"


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside V3's own sealed test window."""


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
            f"requested range end {end} intersects POC V3's own sealed test window "
            f"(>= {TEST_START}). This is disallowed by default. If this really is the "
            f"one authorized end-of-study test evaluation, pass authorize_test=True "
            f"explicitly -- and only there."
        )
