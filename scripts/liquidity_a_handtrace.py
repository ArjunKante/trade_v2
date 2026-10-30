"""PREREGISTRATION_LIQUIDITY_A.md Process Step 2: hand-trace 5 real
DEV-window trades/skips before any aggregate number is computed -- one
reaching the full 3R target, one stopping out before the half exit, one
taking the half exit then stopping out on the remainder, one 15:15 time
exit with the second half still open, one NO_CONFLUENCE skip. Shows the
six levels and which clustered for every found case.
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

from box_theory.context import eligible_day_context, group_by_day
from box_theory.holiday import previous_nse_trading_day

from poc.backtest import build_universe
from poc.v4 import _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity

from liquidity.a import (
    DEV_END, _build_level_lookup_for_entity, find_confluence_zone, find_entry_a,
    hypothetical_single_exit_cost_rs, resolve_scaled_exit_a, three_order_cost_rs,
)

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

DEV_START = dt.date(2016, 10, 4)

WANTED = {
    "FULL_TARGET": None, "STOP_BEFORE_HALF": None, "HALF_THEN_STOP": None,
    "TIME_EXIT_SECOND_HALF_OPEN": None, "NO_CONFLUENCE": None,
}


def trace_entity(intraday_con, warehouse_con, entity_id, years, rank_lookup, jump_dates, found):
    bhav = None
    ex_dates = None
    single_day_cache = {}
    level_lookup = _build_level_lookup_for_entity(warehouse_con, entity_id)
    atr_adjusted_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)

    from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates
    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), DEV_END)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)

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
            dctx = eligible_day_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup,
            )
            if dctx["skip"] is not None:
                continue

            lv = level_lookup.get(day)
            factor_today = factor_lookup.get(day)
            if lv is None or pd.isna(lv["lo_3m"]) or factor_today is None:
                continue

            prev_day = previous_nse_trading_day(day)
            atr_adjusted = atr_adjusted_lookup.get(prev_day)
            if atr_adjusted is None or pd.isna(atr_adjusted):
                continue
            atr_raw = to_raw_scale(atr_adjusted, factor_today)

            lo_3m_raw = to_raw_scale(lv["lo_3m"], factor_today)
            lo_1w_raw = to_raw_scale(lv["lo_1w"], factor_today)
            lo_1d_raw = to_raw_scale(lv["lo_1d"], factor_today)
            hi_3m_raw = to_raw_scale(lv["hi_3m"], factor_today)
            hi_1w_raw = to_raw_scale(lv["hi_1w"], factor_today)
            hi_1d_raw = to_raw_scale(lv["hi_1d"], factor_today)
            prev_close_raw = (
                to_raw_scale(lv["prev_close"], factor_today) if not pd.isna(lv["prev_close"]) else float("nan")
            )

            zone = find_confluence_zone(lo_3m_raw, lo_1w_raw, lo_1d_raw, atr_raw, prev_close_raw)

            def print_levels(tag):
                print(f"\n=== FOUND {tag}: {entity_id} {day} ===")
                print(f"  LOW levels:  3m={lo_3m_raw:.4f}  1w={lo_1w_raw:.4f}  1d={lo_1d_raw:.4f}  "
                      f"ATR_raw={atr_raw:.4f}  tol=0.5xATR={0.5*atr_raw:.4f}")
                print(f"  HIGH levels (computed, unused): 3m={hi_3m_raw:.4f}  1w={hi_1w_raw:.4f}  "
                      f"1d={hi_1d_raw:.4f}")
                print(f"  band={dctx['band']} rank={dctx['rank']}  prev_close_raw={prev_close_raw:.4f}")

            if zone["status"] == "NO_CONFLUENCE" and found["NO_CONFLUENCE"] is None:
                print_levels("NO_CONFLUENCE")
                print(f"  pairwise diffs: 3m-1w={abs(lo_3m_raw-lo_1w_raw):.4f} "
                      f"3m-1d={abs(lo_3m_raw-lo_1d_raw):.4f} 1w-1d={abs(lo_1w_raw-lo_1d_raw):.4f} "
                      f"(all > tol={0.5*atr_raw:.4f})")
                found["NO_CONFLUENCE"] = True
                if all(found[k] is not None for k in found):
                    return True
                continue

            if zone["status"] != "CONFLUENCE":
                continue

            today_day_raw, today_candles5 = dctx["day_raw"], dctx["candles5"]
            entry = find_entry_a(today_candles5, today_day_raw, zone["zone_price"], atr_raw)
            if entry["status"] != "ENTERED":
                continue

            exit_res = resolve_scaled_exit_a(
                today_day_raw, today_candles5, entry["fill_ts"], entry["entry_price"],
                entry["stop_price"], entry["half_target_price"], entry["full_target_price"], entry["qty"],
            )

            want_key = None
            if exit_res["outcome"] == "FULL_EXIT" and found["FULL_TARGET"] is None:
                want_key = "FULL_TARGET"
            elif exit_res["outcome"] == "STOP_NO_HALF" and found["STOP_BEFORE_HALF"] is None:
                want_key = "STOP_BEFORE_HALF"
            elif exit_res["outcome"] == "HALF_THEN_STOP" and found["HALF_THEN_STOP"] is None:
                want_key = "HALF_THEN_STOP"
            elif exit_res["outcome"] == "HALF_THEN_TIME_EXIT" and found["TIME_EXIT_SECOND_HALF_OPEN"] is None:
                want_key = "TIME_EXIT_SECOND_HALF_OPEN"

            if want_key:
                print_levels(want_key)
                print(f"  zone members={zone['members']} zone_price={zone['zone_price']:.4f} "
                      f"multi_cluster={zone['multi_cluster']}")
                qty = entry["qty"]
                entry_price = entry["entry_price"]
                legs = exit_res["legs"]
                pnl_rs = sum(leg["qty"] * (leg["price"] - entry_price) for leg in legs)
                position_size_rs = qty * entry_price
                total_cost_rs = three_order_cost_rs(entry_price, qty, legs, dctx["band"])
                hypo_cost_rs = hypothetical_single_exit_cost_rs(entry_price, qty, dctx["band"])
                net_return_pct = (pnl_rs - total_cost_rs) / position_size_rs
                sweep_candle = today_candles5.iloc[entry["sweep_idx"]]
                reclaim_candle = today_candles5.iloc[entry["reclaim_idx"]]
                print(f"  sweep (idx {entry['sweep_idx']}, ts={sweep_candle['ts']}): L={sweep_candle['low']:.4f}  "
                      f"sweep_depth_atr={entry['sweep_depth_atr']:.4f}  "
                      f"new_low_during_reclaim={entry['new_low_during_reclaim']}")
                print(f"  reclaim (idx {entry['reclaim_idx']}, ts={reclaim_candle['ts']}): "
                      f"C={reclaim_candle['close']:.4f}")
                print(f"  fill_ts={entry['fill_ts']}  entry={entry_price:.4f}  stop={entry['stop_price']:.4f}  "
                      f"half_target={entry['half_target_price']:.4f}  full_target={entry['full_target_price']:.4f}  "
                      f"qty={qty}  half_qty={entry['half_qty']}")
                print(f"  outcome={exit_res['outcome']}  legs={legs}")
                print(f"  pnl_rs={pnl_rs:.2f}  position_size_rs={position_size_rs:.2f}  "
                      f"total_cost_rs={total_cost_rs:.2f}  hypothetical_cost_rs={hypo_cost_rs:.2f}  "
                      f"extra_cost_rs={total_cost_rs-hypo_cost_rs:.2f}  net_return_pct={net_return_pct*100:.4f}%")
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


if __name__ == "__main__":
    main()
