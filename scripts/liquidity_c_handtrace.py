"""PREREGISTRATION_LIQUIDITY_C.md Process Step 2: hand-trace 5 real
DEV-window Study C trades/skips PER SIDE (10 total) before any aggregate
number is computed -- one NO_RETEST, one RETEST_FAILED, one FULL_EXIT,
one STOP_NO_HALF, one HALF_THEN_TIME_EXIT, for LONG and for SHORT each.
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
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.backtest import build_universe
from poc.v4 import _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity

from liquidity.a import _build_level_lookup_for_entity, find_confluence_zone
from liquidity.b import find_confluence_zone_b
from liquidity.c import (
    DEV_END, find_entry_c_long, find_entry_c_short,
    resolve_scaled_exit_a, resolve_scaled_exit_b,
    three_order_cost_rs, three_order_cost_rs_b,
    hypothetical_single_exit_cost_rs, hypothetical_single_exit_cost_rs_b,
)

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

DEV_START = dt.date(2016, 10, 4)

WANTED = {"NO_RETEST": None, "RETEST_FAILED": None, "FULL_EXIT": None,
          "STOP_NO_HALF": None, "HALF_THEN_TIME_EXIT": None}


def trace_entity(side, intraday_con, warehouse_con, entity_id, years, rank_lookup, jump_dates, found):
    level_lookup = _build_level_lookup_for_entity(warehouse_con, entity_id)
    atr_adjusted_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)
    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), DEV_END)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache = {}

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
            level_key = "lo_3m" if side == "long" else "hi_3m"
            if lv is None or pd.isna(lv[level_key]) or factor_today is None:
                continue

            prev_day = previous_nse_trading_day(day)
            atr_adjusted = atr_adjusted_lookup.get(prev_day)
            if atr_adjusted is None or pd.isna(atr_adjusted):
                continue
            atr_raw = to_raw_scale(atr_adjusted, factor_today)

            prev_close_raw = (
                to_raw_scale(lv["prev_close"], factor_today) if not pd.isna(lv["prev_close"]) else float("nan")
            )

            if side == "long":
                lo_3m_raw = to_raw_scale(lv["lo_3m"], factor_today)
                lo_1w_raw = to_raw_scale(lv["lo_1w"], factor_today)
                lo_1d_raw = to_raw_scale(lv["lo_1d"], factor_today)
                zone = find_confluence_zone(lo_3m_raw, lo_1w_raw, lo_1d_raw, atr_raw, prev_close_raw)
            else:
                hi_3m_raw = to_raw_scale(lv["hi_3m"], factor_today)
                hi_1w_raw = to_raw_scale(lv["hi_1w"], factor_today)
                hi_1d_raw = to_raw_scale(lv["hi_1d"], factor_today)
                zone = find_confluence_zone_b(hi_3m_raw, hi_1w_raw, hi_1d_raw, atr_raw, prev_close_raw)
            if zone["status"] != "CONFLUENCE":
                continue

            today_day_raw, today_candles5 = dctx["day_raw"], dctx["candles5"]
            if side == "long":
                entry = find_entry_c_long(today_candles5, today_day_raw, zone["zone_price"], atr_raw)
            else:
                entry = find_entry_c_short(today_candles5, today_day_raw, zone["zone_price"], atr_raw)
            status = entry["status"]

            def print_common(tag):
                print(f"\n=== FOUND {tag} ({side}): {entity_id} {day} ===")
                print(f"  zone_price={zone['zone_price']:.4f} members={zone['members']} "
                      f"multi_cluster={zone['multi_cluster']} ATR_raw={atr_raw:.4f}")
                print(f"  sweep_idx={entry['sweep_idx']} reclaim_idx={entry.get('reclaim_idx')} "
                      f"sweep_depth_atr={entry['sweep_depth_atr']:.4f}")
                final_extreme = entry.get("final_sweep_low", entry.get("final_sweep_high"))
                print(f"  final_sweep_{'low' if side=='long' else 'high'}={final_extreme:.4f}")

            if status == "NO_RETEST" and found["NO_RETEST"] is None:
                print_common("NO_RETEST")
                found["NO_RETEST"] = True
            elif status == "RETEST_FAILED" and found["RETEST_FAILED"] is None:
                print_common("RETEST_FAILED")
                print(f"  retest_breach_idx={entry['retest_breach_idx']} "
                      f"breach candle: {today_candles5.iloc[entry['retest_breach_idx']][['ts','low','high','close']].to_dict()}")
                found["RETEST_FAILED"] = True
            elif status == "ENTERED":
                qty = entry["qty"]
                entry_price = entry["entry_price"]
                if side == "long":
                    exit_res = resolve_scaled_exit_a(
                        today_day_raw, today_candles5, entry["fill_ts"], entry_price, entry["stop_price"],
                        entry["half_target_price"], entry["full_target_price"], qty,
                    )
                else:
                    exit_res = resolve_scaled_exit_b(
                        today_day_raw, today_candles5, entry["fill_ts"], entry_price, entry["stop_price"],
                        entry["half_target_price"], entry["full_target_price"], qty,
                    )
                outcome = exit_res["outcome"]
                want_key = outcome if outcome in ("FULL_EXIT", "STOP_NO_HALF", "HALF_THEN_TIME_EXIT") else None
                if want_key and found[want_key] is None:
                    print_common(want_key)
                    retest_candle = today_candles5.iloc[entry["retest_idx"]]
                    reclaim_candle = today_candles5.iloc[entry["reclaim_idx"]]
                    print(f"  reclaim candle ts={reclaim_candle['ts']} close={reclaim_candle['close']:.4f}")
                    print(f"  retest candle (idx {entry['retest_idx']}) ts={retest_candle['ts']} "
                          f"low={retest_candle['low']:.4f} close={retest_candle['close']:.4f}")
                    delay_min = (entry["fill_ts"] - (reclaim_candle["ts"] + pd.Timedelta(minutes=5))).total_seconds() / 60.0
                    print(f"  fill_ts={entry['fill_ts']} entry={entry_price:.4f} stop={entry['stop_price']:.4f} "
                          f"half_target={entry['half_target_price']:.4f} full_target={entry['full_target_price']:.4f} "
                          f"qty={qty} half_qty={entry['half_qty']} delay_minutes={delay_min:.1f}")
                    legs = exit_res["legs"]
                    if side == "long":
                        pnl_rs = sum(leg["qty"] * (leg["price"] - entry_price) for leg in legs)
                        band = dctx["band"]
                        total_cost_rs = three_order_cost_rs(entry_price, qty, legs, band)
                        hypo_cost_rs = hypothetical_single_exit_cost_rs(entry_price, qty, band)
                    else:
                        pnl_rs = sum(leg["qty"] * (entry_price - leg["price"]) for leg in legs)
                        band = dctx["band"]
                        total_cost_rs = three_order_cost_rs_b(entry_price, qty, legs, band)
                        hypo_cost_rs = hypothetical_single_exit_cost_rs_b(entry_price, qty, band)
                    position_size_rs = qty * entry_price
                    net_return_pct = (pnl_rs - total_cost_rs) / position_size_rs
                    print(f"  outcome={outcome} legs={legs}")
                    print(f"  pnl_rs={pnl_rs:.2f} position_size_rs={position_size_rs:.2f} "
                          f"total_cost_rs={total_cost_rs:.2f} hypothetical_cost_rs={hypo_cost_rs:.2f} "
                          f"net_return_pct={net_return_pct*100:.4f}%")
                    found[want_key] = True

            if all(v is not None for v in found.values()):
                return True
    return False


def run_side(side):
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
    print(f"\n########## SIDE: {side.upper()} ##########")
    for i, entity_id in enumerate(ordered_entities):
        print(f"[{i+1}/{len(ordered_entities)}] scanning {entity_id} ... "
              f"(found so far: {[k for k,v in found.items() if v is not None]})", flush=True)
        done = trace_entity(side, intraday_con, warehouse_con, entity_id, entity_years[entity_id],
                             rank_lookup, jump_dates_by_entity.get(entity_id, set()), found)
        if done:
            print(f"\n=== ALL 5 {side.upper()} SHAPES FOUND ===")
            break
    else:
        missing = [k for k, v in found.items() if v is None]
        print(f"\n=== {side.upper()} EXHAUSTED SAMPLE, still missing: {missing} ===")

    warehouse_con.close()
    intraday_con.close()


if __name__ == "__main__":
    run_side("long")
    run_side("short")
