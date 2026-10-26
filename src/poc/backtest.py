"""PREREGISTRATION_POC.md orchestration: streams the DEV (or, once
authorized, TEST) window one entity-year at a time, builds each entity's
own multi-day lookback context (Section 3), trend filter (Section 5), and
runs touch/confirmation/entry/exit (Sections 6-8), returning a trade list
plus skip-reason counts.

Reused read-only: fibo.universe, fibo.jump_guard, fibo.daily_ohlc,
box_theory.context.group_by_day, box_theory.costs, box_theory.
universe_data (Section 0).
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fibo.daily_ohlc import build_daily_ohlc_panel
from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import (
    reconstitute_annually, effective_universe, restrict_to_universe, assert_universe_membership,
)

from box_theory.context import group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.context import build_poc_context
from poc.resolution import find_entry, resolve_exit, FIXED_RISK_RS
from poc.trend import build_trend_lookup

TOP_N = 200
STUB_YEAR = 2016

SKIP_REASONS = (
    "lookback_incomplete", "trend_filter_failed", "no_touch", "poc_failed", "no_confirmation",
    "no_fill_bar", "fill_outside_window", "entry_below_stop", "stop_too_wide", "no_room", "zero_qty",
)

_ENTRY_STATUS_TO_SKIP = {
    "NO_TOUCH": "no_touch", "POC_FAILED": "poc_failed", "NO_CONFIRMATION": "no_confirmation",
    "NO_FILL_BAR": "no_fill_bar", "FILL_OUTSIDE_WINDOW": "fill_outside_window",
    "ENTRY_BELOW_STOP": "entry_below_stop", "STOP_TOO_WIDE": "stop_too_wide",
    "NO_ROOM": "no_room", "ZERO_QTY": "zero_qty",
}


def build_universe(warehouse_con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    universe = reconstitute_annually(warehouse_con, top_n=TOP_N)
    return effective_universe(universe, stub_year=STUB_YEAR)


def _entity_years(universe: pd.DataFrame, start: dt.date, end: dt.date) -> dict:
    in_window = universe[(universe["year"] >= start.year) & (universe["year"] <= end.year)]
    out: dict[str, list[int]] = {}
    for eid, grp in in_window.groupby("entity_id"):
        out[eid] = sorted(grp["year"].unique().tolist())
    return out


def _build_trend_lookup_for_entity(warehouse_con: duckdb.DuckDBPyConnection, entity_id: str,
                                    jump_dates: set) -> dict:
    """Entity's full daily history (fibo.daily_ohlc), jump-guard-flagged
    days dropped before the 50-day SMA is computed -- same "exclude
    before any rolling computation touches it" convention
    PREREGISTRATION_DARVAS.md Section 1b already applies to its own trend
    filter."""
    daily_panel = build_daily_ohlc_panel(warehouse_con, entity_ids=[entity_id])
    if daily_panel.empty:
        return {}
    if jump_dates:
        flagged = pd.to_datetime(pd.Series(sorted(jump_dates)))
        daily_panel = daily_panel[~daily_panel["trade_date"].isin(flagged)]
    return build_trend_lookup(daily_panel)


def evaluate_entity(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict,
) -> dict:
    """Runs every candidate day for one entity across `years` (clipped to
    [start, end]). Returns {"trades": [...], "skips": {reason: count},
    "lookback_incomplete_detail": {(relative_day, reason): count},
    "errors": [...]}."""
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
            if ctx["skip"] == "TREND_FILTER_FAILED":
                skips["trend_filter_failed"] += 1
                continue

            today_day_raw, today_candles5 = ctx["today_day_raw"], ctx["today_candles5"]
            poc_price, prev_high = ctx["poc_price"], ctx["prev_high"]
            band, rank, year_of_day = ctx["band"], ctx["rank"], ctx["year"]

            entry = find_entry(today_candles5, today_day_raw, poc_price, prev_high)
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
                errors.append({
                    "entity_id": entity_id, "trade_date": day,
                    "error": f"{type(e).__name__}: {e}",
                })
                continue

            qty = entry["qty"]
            entry_price = entry["entry_price"]
            pnl_rs = qty * (exit_res["exit_price"] - entry_price)
            position_size_rs = qty * entry_price
            cost_rs = round_trip_cost_rs(position_size_rs, band)
            net_r = (pnl_rs - cost_rs) / FIXED_RISK_RS
            gross_r = pnl_rs / FIXED_RISK_RS

            trades.append({
                "entity_id": entity_id, "trade_date": day, "year": year_of_day,
                "band": band, "rank": rank,
                "poc_price": poc_price, "prev_high": prev_high,
                "touch_idx": entry["touch_idx"], "confirm_idx": entry["confirm_idx"],
                "confirm_kind": entry["confirm_kind"], "fill_ts": entry["fill_ts"],
                "entry_price": entry_price, "stop_price": entry["stop_price"],
                "target_price": entry["target_price"], "qty": qty,
                "outcome": exit_res["outcome"], "exit_ts": exit_res["exit_ts"],
                "exit_price": exit_res["exit_price"], "time_exit_fallback": exit_res["time_exit_fallback"],
                "position_size_rs": position_size_rs, "cost_rs": cost_rs,
                "pnl_rs": pnl_rs, "gross_r": gross_r, "net_r": net_r,
                "entry_above_poc_frac": (entry_price - poc_price) / entry_price,
            })

    return {
        "trades": trades, "skips": skips,
        "lookback_incomplete_detail": lookback_incomplete_detail, "errors": errors,
    }


def run_backtest(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    start: dt.date, end: dt.date, entity_ids: list[str] | None = None,
) -> dict:
    """Top-level entry point. Does NOT itself call test_seal.guard_date_
    range -- the caller script is responsible for that."""
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
        result = evaluate_entity(
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
        assert_universe_membership(check, universe, label="poc trade list")

    return {
        "trades": trades_df, "skips": total_skips,
        "lookback_incomplete_detail": total_lookback_detail, "errors": all_errors, "universe": universe,
    }
