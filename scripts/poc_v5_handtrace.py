"""PREREGISTRATION_POC_V5.md Process Step 2: hand-trace 5 real DEV-window
trades/skips before any aggregate number is computed -- at minimum one
gap-through-stop exit and one 10-day-TIME_LIMIT exit (both required by
name), the remaining three chosen from whatever other shapes (entry-day
STOP/TARGET, an overnight clean-stop exit, a DEV_BOUNDARY_TRUNCATED case
if one exists near the window edge) the real DEV data actually contains.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con
from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.price_scale import to_raw_scale

from box_theory.context import group_by_day
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.backtest import build_universe, _build_trend_lookup_for_entity
from poc.context import build_poc_context, lookback_dates
from poc.v2 import compute_lookback_low
from poc.v4 import _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity
from poc.v5 import DEV_END, find_entry_v5, net_return_pct_range, resolve_multiday_exit

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

DEV_START = dt.date(2016, 10, 4)

WANTED = {
    "GAP_THROUGH_STOP": None, "TIME_LIMIT": None, "CLEAN_STOP_OVERNIGHT": None,
    "TARGET_HIT": None, "DEV_BOUNDARY_TRUNCATED": None,
}


def trace_entity(intraday_con, warehouse_con, entity_id, years, rank_lookup, jump_dates, found):
    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), DEV_END)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache = {}
    eligible_ctx_cache = {}
    trend_lookup = _build_trend_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    atr_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)

    for year in years:
        year_start = max(dt.date(year, 1, 1), DEV_START)
        year_end = min(dt.date(year, 12, 31), DEV_END)
        if year_start > year_end:
            continue
        block = fetch_bars_range(intraday_con, entity_id, year_start, year_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)

        for day in sorted(day_groups.keys()):
            ctx = build_poc_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup, trend_lookup, eligible_ctx_cache,
            )
            if ctx["skip"] == "LOOKBACK_INCOMPLETE":
                continue
            lookback_low = compute_lookback_low(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup, eligible_ctx_cache,
            )
            if ctx["skip"] == "TREND_FILTER_FAILED":
                continue

            l5 = lookback_dates(day)["L5"]
            atr_adj = atr_lookup.get(l5)
            factor_today = factor_lookup.get(day)
            if atr_adj is None or pd.isna(atr_adj) or factor_today is None:
                continue
            atr_raw = to_raw_scale(atr_adj, factor_today)

            candles5, day_raw = ctx["today_candles5"], ctx["today_day_raw"]
            entry = find_entry_v5(candles5, day_raw, lookback_low, atr_raw)
            if entry["status"] != "ENTERED":
                continue

            exit_res = resolve_multiday_exit(
                warehouse_con, entity_id, day, DEV_END, day_raw, entry["fill_ts"],
                entry["entry_price"], entry["stop_price"], entry["target_price"],
            )

            want_key = None
            if exit_res["outcome"] == "STOP" and exit_res["gap_through"] and found["GAP_THROUGH_STOP"] is None:
                want_key = "GAP_THROUGH_STOP"
            elif exit_res["outcome"] == "TIME_LIMIT" and found["TIME_LIMIT"] is None:
                want_key = "TIME_LIMIT"
            elif (exit_res["outcome"] == "STOP" and exit_res["held_overnight"] and not exit_res["gap_through"]
                  and found["CLEAN_STOP_OVERNIGHT"] is None):
                want_key = "CLEAN_STOP_OVERNIGHT"
            elif exit_res["outcome"] == "TARGET" and found["TARGET_HIT"] is None:
                want_key = "TARGET_HIT"
            elif exit_res["outcome"] == "DEV_BOUNDARY_TRUNCATED" and found["DEV_BOUNDARY_TRUNCATED"] is None:
                want_key = "DEV_BOUNDARY_TRUNCATED"

            if want_key:
                qty = entry["qty"]
                entry_price = entry["entry_price"]
                pnl_rs = qty * (exit_res["exit_price"] - entry_price)
                position_size_rs = qty * entry_price
                cost_info = net_return_pct_range(pnl_rs, position_size_rs)

                sweep_candle = candles5.iloc[entry["sweep_idx"]]
                reclaim_candle = candles5.iloc[entry["reclaim_idx"]]
                print(f"\n=== FOUND {want_key}: {entity_id} {day} ===")
                print(f"  LOOKBACK_LOW={lookback_low:.4f}  ATR_raw={atr_raw:.4f}  band={ctx['band']} rank={ctx['rank']}")
                print(f"  sweep candle (idx {entry['sweep_idx']}, ts={sweep_candle['ts']}): "
                      f"L={sweep_candle['low']:.4f}")
                print(f"  reclaim candle (idx {entry['reclaim_idx']}, ts={reclaim_candle['ts']}): "
                      f"C={reclaim_candle['close']:.4f}")
                print(f"  sweep_depth_atr={entry['sweep_depth_atr']:.4f}  "
                      f"new_low_during_reclaim={entry['new_low_during_reclaim']}")
                print(f"  fill_ts={entry['fill_ts']}  entry_price={entry_price:.4f}  "
                      f"stop_price={entry['stop_price']:.4f}  target_price={entry['target_price']:.4f}  qty={qty}")
                print(f"  stop_distance_pct={(entry_price-entry['stop_price'])/entry_price*100:.4f}%")
                print(f"  exit: {exit_res}")
                print(f"  pnl_rs={pnl_rs:.2f}  position_size_rs={position_size_rs:.2f}  "
                      f"cost_rs_mid={cost_info['cost_rs_mid']:.2f}  "
                      f"net_return_pct={cost_info['net_return_pct']*100:.4f}%  "
                      f"(lo-cost={cost_info['net_return_pct_hi_cost']*100:.4f}%, "
                      f"hi-cost={cost_info['net_return_pct_lo_cost']*100:.4f}%)")
                found[want_key] = True

            if all(found[k] is not None for k in found):
                return True
    return False


def main():
    warehouse_con = get_warehouse_con(WAREHOUSE_DB)
    intraday_con = get_intraday_con(INTRADAY_DB)

    universe = build_universe(warehouse_con)
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)

    in_window = universe[(universe["year"] >= DEV_START.year) & (universe["year"] <= DEV_END.year)]
    entity_years: dict[str, list[int]] = {}
    for eid, grp in in_window.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    archive_entities = {r[0] for r in intraday_con.execute("SELECT DISTINCT entity_id FROM bars_1min").fetchall()}
    entity_years = {e: y for e, y in entity_years.items() if e in archive_entities}
    ordered_entities = sorted(entity_years.keys(), key=lambda e: -len(entity_years[e]))

    found = dict(WANTED)
    for i, entity_id in enumerate(ordered_entities):
        print(f"[{i+1}/{len(ordered_entities)}] scanning {entity_id} ... "
              f"(found so far: {[k for k,v in found.items() if v is not None]})", flush=True)
        done = trace_entity(intraday_con, warehouse_con, entity_id, entity_years[entity_id],
                             rank_lookup, jump_dates_by_entity.get(entity_id, set()), found)
        if done:
            print("\n=== ALL 5 SHAPES FOUND ===")
            break
    else:
        missing = [k for k, v in found.items() if v is None]
        print(f"\n=== EXHAUSTED SAMPLE, still missing: {missing} ===")
        if "DEV_BOUNDARY_TRUNCATED" in missing and all(k == "DEV_BOUNDARY_TRUNCATED" for k in missing):
            print("Note: DEV_BOUNDARY_TRUNCATED may genuinely not occur for entries scanned this far from "
                  "the DEV window's own end -- not necessarily a bug. Will check entries near 2022-12-31 "
                  "specifically if still missing.")


if __name__ == "__main__":
    main()
