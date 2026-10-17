"""Orchestration: streams the DEV (or, once authorized, TEST) window one
entity-year at a time, applies every eligibility check from
PREREGISTRATION_BOX.md Section 2b in order (jump guard, ex-date, previous-
session validity, scale resolution), runs both FAST and SLOW signal/entry/
exit resolution per day, and returns a trade list plus skip-reason counts
per configuration.

Reused read-only: fibo.universe (reconstitute_annually/effective_universe/
restrict_to_universe/assert_universe_membership), fibo.jump_guard
(combined_unexplained_jump_dates), fibo.scale_probe (probe_scale,
passes_gap_guard -- see universe_data.py's docstring for why `decide_
scale_for_day` itself is not called directly).
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import (
    reconstitute_annually, effective_universe, restrict_to_universe, assert_universe_membership,
)

from box_theory.context import eligible_day_context, group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.resolution import find_entry, resolve_exit, CONFIG_NAMES
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

TOP_N = 200
STUB_YEAR = 2016

SKIP_REASONS = ("no_room", "bad_previous_session", "ex_date", "jump_guard")


def build_universe(warehouse_con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Point-in-time top-200 universe, stub year 2016 filled from 2017,
    exactly as PREREGISTRATION_BOX.md Section 2a specifies."""
    universe = reconstitute_annually(warehouse_con, top_n=TOP_N)
    return effective_universe(universe, stub_year=STUB_YEAR)


def _entity_years(universe: pd.DataFrame, start: dt.date, end: dt.date) -> dict:
    """entity_id -> sorted list of years in [start.year, end.year] this
    entity is a declared member for."""
    in_window = universe[(universe["year"] >= start.year) & (universe["year"] <= end.year)]
    out: dict[str, list[int]] = {}
    for eid, grp in in_window.groupby("entity_id"):
        out[eid] = sorted(grp["year"].unique().tolist())
    return out


def evaluate_entity(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict,
) -> dict:
    """Runs every eligible day for one entity across `years` (clipped to
    [start, end]), for every config in CONFIG_NAMES. Returns {"trades":
    [...], "skips": {reason: count}, "diagnostics": {reason: count}}."""
    trades: list[dict] = []
    skips = {r: 0 for r in SKIP_REASONS}
    diagnostics = {"no_touch": 0, "no_confirmation": 0, "no_fill_bar": 0,
                    "fill_outside_window": 0, "zero_qty": 0}
    errors: list[dict] = []

    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache: dict[dt.date, pd.DataFrame] = {}

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
            ctx = eligible_day_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup,
            )
            if ctx["skip"] is not None:
                skips[ctx["skip"]] += 1
                continue

            day_raw, candles5 = ctx["day_raw"], ctx["candles5"]
            prev_high, prev_low = ctx["prev_high"], ctx["prev_low"]
            band, rank, year_of_day = ctx["band"], ctx["rank"], ctx["year"]

            for config in CONFIG_NAMES:
                entry = find_entry(candles5, day_raw, prev_high, prev_low, config)
                status = entry["status"]
                if status == "NO_TOUCH":
                    diagnostics["no_touch"] += 1
                    continue
                if status == "NO_CONFIRMATION":
                    diagnostics["no_confirmation"] += 1
                    continue
                if status == "NO_FILL_BAR":
                    diagnostics["no_fill_bar"] += 1
                    continue
                if status == "FILL_OUTSIDE_WINDOW":
                    diagnostics["fill_outside_window"] += 1
                    continue
                if status == "NO_ROOM":
                    skips["no_room"] += 1
                    continue
                if status == "ZERO_QTY":
                    diagnostics["zero_qty"] += 1
                    continue

                # A single unanticipated per-day edge case must not cost a
                # multi-hour run: caught, recorded with enough detail to
                # reproduce and fix, and the day is skipped -- never
                # silently absorbed into a trade count. (Lost one real run
                # to exactly this before this guard existed -- an entity-
                # day whose archive didn't reach 15:15, now handled
                # properly in resolve_exit itself; this except is for
                # whatever the NEXT unanticipated case turns out to be.)
                try:
                    exit_res = resolve_exit(
                        candles5, day_raw, entry["entry_candle_idx"], entry["fill_ts"],
                        entry["entry_price"], prev_high, config,
                    )
                except Exception as e:
                    errors.append({
                        "entity_id": entity_id, "trade_date": day, "config": config,
                        "error": f"{type(e).__name__}: {e}",
                    })
                    continue
                qty = entry["qty"]
                entry_price = entry["entry_price"]
                pnl_rs = qty * (exit_res["exit_price"] - entry_price)
                position_size_rs = qty * entry_price
                cost_rs = round_trip_cost_rs(position_size_rs, band)
                net_r = (pnl_rs - cost_rs) / 500.0
                gross_r = pnl_rs / 500.0

                trades.append({
                    "config": config, "entity_id": entity_id, "trade_date": day,
                    "year": year_of_day, "band": band, "rank": rank,
                    "prev_high": prev_high, "prev_low": prev_low,
                    "touch_idx": entry["touch_idx"], "confirm_end_idx": entry["confirm_end_idx"],
                    "fill_ts": entry["fill_ts"], "entry_price": entry_price, "qty": qty,
                    "stop_price": entry_price * 0.97,
                    "outcome": exit_res["outcome"], "armed": exit_res["armed"],
                    "time_exit_fallback": exit_res["time_exit_fallback"],
                    "exit_ts": exit_res["exit_ts"], "exit_price": exit_res["exit_price"],
                    "position_size_rs": position_size_rs, "cost_rs": cost_rs,
                    "pnl_rs": pnl_rs, "gross_r": gross_r, "net_r": net_r,
                })

    return {"trades": trades, "skips": skips, "diagnostics": diagnostics, "errors": errors}


def run_backtest(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    start: dt.date, end: dt.date, entity_ids: list[str] | None = None,
) -> dict:
    """Top-level entry point. Does NOT itself call test_seal.guard_date_
    range -- the caller script is responsible for that (keeps this
    function usable for the hand-trace step, which deliberately probes
    single known entity-days without a window-level guard call)."""
    universe = build_universe(warehouse_con)

    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)

    raw_entity_years = _entity_years(universe, start, end)
    if entity_ids is not None:
        raw_entity_years = {e: y for e, y in raw_entity_years.items() if e in entity_ids}
    # THE FILTER (fibo.universe.restrict_to_universe), applied explicitly
    # rather than relying on _entity_years having derived its candidates
    # from the universe correctly -- same discipline Fibo's own universe.py
    # module docstring documents (a filter AND a separate guard, not one
    # fix per script).
    candidates = pd.DataFrame(
        [{"entity_id": e, "year": y} for e, years in raw_entity_years.items() for y in years]
    )
    if candidates.empty:
        return {"trades": pd.DataFrame(), "skips": {r: 0 for r in SKIP_REASONS},
                "diagnostics": {}, "errors": [], "universe": universe}
    candidates = restrict_to_universe(candidates, universe)
    entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    all_trades: list[dict] = []
    total_skips = {r: 0 for r in SKIP_REASONS}
    total_diag = {"no_touch": 0, "no_confirmation": 0, "no_fill_bar": 0,
                   "fill_outside_window": 0, "zero_qty": 0}
    all_errors: list[dict] = []

    for entity_id, years in entity_years.items():
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_entity(
            intraday_con, warehouse_con, entity_id, years, start, end, jump_dates, rank_lookup,
        )
        all_trades.extend(result["trades"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        for k in total_diag:
            total_diag[k] += result["diagnostics"][k]
        all_errors.extend(result["errors"])

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label="box_theory trade list")

    return {
        "trades": trades_df, "skips": total_skips, "diagnostics": total_diag,
        "errors": all_errors, "universe": universe,
    }
