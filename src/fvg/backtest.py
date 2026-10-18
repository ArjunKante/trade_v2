"""Orchestration: streams the DEV (or, once authorized, TEST) window one
entity at a time, assembles each entity's continuous 1-hour-candle /
1-minute-bar timeline per contiguous run of calendar-consecutive universe-
membership years (Section 3), detects every valid FVG (Section 4), and
evaluates both Configuration A and Configuration B (Section 5-6)
independently against each one.

Reused read-only: fibo.universe, fibo.jump_guard.combined_unexplained_
jump_dates, box_theory.universe_data.* , box_theory.costs.round_trip_
cost_rs -- see PREREGISTRATION_FVG.md Section 0.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import (
    reconstitute_annually, effective_universe, restrict_to_universe, assert_universe_membership,
)

from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from fvg.context import build_entity_timeline, group_by_day, SKIP_REASONS
from fvg.patterns import find_valid_gaps
from fvg.resolution import evaluate_config_a, evaluate_config_b, resolve_exit, FIXED_RISK_RS

TOP_N = 200
STUB_YEAR = 2016
CONFIG_NAMES = ("A", "B")

EVALUATORS = {"A": evaluate_config_a, "B": evaluate_config_b}

DIAG_KEYS = (
    "expired_unused", "touched_never_confirmed", "superseded_by_newer_gap",
    "invalidated_before_retest", "no_fill_bar", "zero_qty", "stop_too_tight",
)


def build_universe(warehouse_con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Point-in-time top-200 universe, stub year 2016 filled from 2017 --
    identical in construction to box_theory.backtest.build_universe
    (same fibo.universe calls, same arguments); written here rather than
    imported cross-study per Section 0."""
    universe = reconstitute_annually(warehouse_con, top_n=TOP_N)
    return effective_universe(universe, stub_year=STUB_YEAR)


def _entity_years(universe: pd.DataFrame, start: dt.date, end: dt.date) -> dict:
    in_window = universe[(universe["year"] >= start.year) & (universe["year"] <= end.year)]
    out: dict[str, list[int]] = {}
    for eid, grp in in_window.groupby("entity_id"):
        out[eid] = sorted(grp["year"].unique().tolist())
    return out


def _consecutive_runs(years: list[int]) -> list[list[int]]:
    """Split a sorted distinct-years list into runs of calendar-
    consecutive years. A genuine multi-year membership gap (entity drops
    out of the top-200 for >=1 full year, later returns) is a HARD BREAK
    between separate timelines -- only a data-quality-ineligible DAY is
    excised/bridged (Section 3); a year the entity was never a declared
    universe member for is a different kind of absence and is not
    bridged."""
    if not years:
        return []
    runs = [[years[0]]]
    for y in years[1:]:
        if y == runs[-1][-1] + 1:
            runs[-1].append(y)
        else:
            runs.append([y])
    return runs


def _record_non_entry(config: str, gap: dict, result: dict, diagnostics: dict) -> None:
    status = result["status"]
    if status == "EXPIRED_UNUSED":
        if config == "B" and result.get("touched"):
            diagnostics[config]["touched_never_confirmed"] += 1
        else:
            diagnostics[config]["expired_unused"] += 1
    elif status == "SUPERSEDED":
        diagnostics[config]["superseded_by_newer_gap"] += 1
    elif status == "INVALIDATED":
        diagnostics[config]["invalidated_before_retest"] += 1
    elif status == "NO_FILL_BAR":
        diagnostics[config]["no_fill_bar"] += 1
    elif status == "ZERO_QTY":
        diagnostics[config]["zero_qty"] += 1
    elif status == "STOP_TOO_TIGHT":
        diagnostics[config]["stop_too_tight"] += 1
    else:
        raise ValueError(f"unrecognized non-entry status {status!r}")


def evaluate_entity(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict,
) -> dict:
    """Runs every contiguous membership run for one entity. Returns
    {"trades": {"A": [...], "B": [...]}, "skips": {reason: count},
    "diagnostics": {"A": {...}, "B": {...}}, "total_gaps": int,
    "inside_bar_rejected": int, "overnight_excluded": int, "errors": [...]}."""
    trades: dict[str, list[dict]] = {c: [] for c in CONFIG_NAMES}
    skips = {r: 0 for r in SKIP_REASONS}
    diagnostics = {c: {k: 0 for k in DIAG_KEYS} for c in CONFIG_NAMES}
    total_gaps = 0
    inside_bar_rejected = 0
    overnight_excluded = 0
    errors: list[dict] = []

    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)

    for run in _consecutive_runs(years):
        run_start = max(dt.date(run[0], 1, 1), start)
        run_end = min(dt.date(run[-1], 12, 31), end)
        if run_start > run_end:
            continue
        block = fetch_bars_range(intraday_con, entity_id, run_start, run_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        single_day_cache: dict = {}
        timeline = build_entity_timeline(
            intraday_con, entity_id, day_groups, bhav, ex_dates, jump_dates, single_day_cache, rank_lookup,
        )
        for k in skips:
            skips[k] += timeline["skips"][k]
        candles, bars1 = timeline["candles"], timeline["bars1"]
        if len(candles) < 3:
            continue

        found = find_valid_gaps(candles)
        total_gaps += len(found["gaps"])
        inside_bar_rejected += found["inside_bar_rejected"]
        overnight_excluded += found["overnight_excluded"]

        for gap in found["gaps"]:
            for config in CONFIG_NAMES:
                try:
                    result = EVALUATORS[config](candles, bars1, gap)
                except Exception as e:
                    errors.append({
                        "entity_id": entity_id, "config": config, "c3_idx": gap["c3_idx"],
                        "stage": "entry", "error": f"{type(e).__name__}: {e}",
                    })
                    continue

                if result["status"] != "ENTERED":
                    _record_non_entry(config, gap, result, diagnostics)
                    continue

                entry_date = pd.Timestamp(result["fill_ts"]).date()
                try:
                    exit_res = resolve_exit(candles, bars1, result, entry_date)
                except Exception as e:
                    errors.append({
                        "entity_id": entity_id, "config": config, "c3_idx": gap["c3_idx"],
                        "stage": "exit", "error": f"{type(e).__name__}: {e}",
                    })
                    continue

                qty, entry_price = result["qty"], result["entry_price"]
                pnl_rs = qty * (exit_res["exit_price"] - entry_price)
                position_size_rs = qty * entry_price
                cost_rs = round_trip_cost_rs(position_size_rs, gap["band"])
                net_r = (pnl_rs - cost_rs) / FIXED_RISK_RS
                gross_r = pnl_rs / FIXED_RISK_RS

                trades[config].append({
                    "config": config, "entity_id": entity_id,
                    "gap_key": (entity_id, str(gap["formed_trade_date"]), gap["c1_idx"], gap["c3_idx"]),
                    "gap_formed_date": gap["formed_trade_date"], "band": gap["band"], "rank": gap["rank"],
                    "year": gap["year"], "gap_low": gap["gap_low"], "gap_high": gap["gap_high"],
                    "touched": result.get("touched", False), "trigger_idx": result["trigger_idx"],
                    "fill_ts": result["fill_ts"], "trade_date": entry_date, "entry_price": entry_price,
                    "room_pct": result["room_pct"], "qty": qty, "stop_price": result["stop_price"],
                    "target_price": result["target_price"], "outcome": exit_res["outcome"],
                    "exit_ts": exit_res["exit_ts"], "exit_price": exit_res["exit_price"],
                    "time_exit_date": exit_res["time_exit_date"],
                    "time_exit_fallback": exit_res["time_exit_fallback"],
                    "monitoring_gap_days": exit_res["monitoring_gap_days"],
                    "position_size_rs": position_size_rs, "cost_rs": cost_rs,
                    "pnl_rs": pnl_rs, "gross_r": gross_r, "net_r": net_r,
                })

    return {
        "trades": trades, "skips": skips, "diagnostics": diagnostics,
        "total_gaps": total_gaps, "inside_bar_rejected": inside_bar_rejected,
        "overnight_excluded": overnight_excluded, "errors": errors,
    }


def run_backtest(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    start: dt.date, end: dt.date, entity_ids: list[str] | None = None,
) -> dict:
    """Top-level entry point. Does NOT call fvg.test_seal.guard_date_range
    itself -- the caller script is responsible for that."""
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
        empty_trades = {c: pd.DataFrame() for c in CONFIG_NAMES}
        return {
            "trades": empty_trades, "skips": {r: 0 for r in SKIP_REASONS},
            "diagnostics": {c: {k: 0 for k in DIAG_KEYS} for c in CONFIG_NAMES},
            "total_gaps": 0, "inside_bar_rejected": 0, "overnight_excluded": 0,
            "errors": [], "universe": universe,
        }
    candidates = restrict_to_universe(candidates, universe)
    entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    all_trades: dict[str, list[dict]] = {c: [] for c in CONFIG_NAMES}
    total_skips = {r: 0 for r in SKIP_REASONS}
    total_diag = {c: {k: 0 for k in DIAG_KEYS} for c in CONFIG_NAMES}
    total_gaps = 0
    inside_bar_rejected = 0
    overnight_excluded = 0
    all_errors: list[dict] = []

    for entity_id, years in entity_years.items():
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_entity(
            intraday_con, warehouse_con, entity_id, years, start, end, jump_dates, rank_lookup,
        )
        for c in CONFIG_NAMES:
            all_trades[c].extend(result["trades"][c])
            for k in DIAG_KEYS:
                total_diag[c][k] += result["diagnostics"][c][k]
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        total_gaps += result["total_gaps"]
        inside_bar_rejected += result["inside_bar_rejected"]
        overnight_excluded += result["overnight_excluded"]
        all_errors.extend(result["errors"])

    trades_dfs = {}
    for c in CONFIG_NAMES:
        df = pd.DataFrame(all_trades[c])
        if not df.empty:
            check = df[["entity_id", "year"]].drop_duplicates()
            assert_universe_membership(check, universe, label=f"fvg trade list config {c}")
        trades_dfs[c] = df

    return {
        "trades": trades_dfs, "skips": total_skips, "diagnostics": total_diag,
        "total_gaps": total_gaps, "inside_bar_rejected": inside_bar_rejected,
        "overnight_excluded": overnight_excluded, "errors": all_errors, "universe": universe,
    }
