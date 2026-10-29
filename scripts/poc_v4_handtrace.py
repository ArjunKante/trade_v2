"""PREREGISTRATION_POC_V4.md Process Step 2: hand-trace 5 real DEV-window
trades/skips before any aggregate number is computed -- one TOUCH_TOO_
SHALLOW, one BREAKDOWN_NOT_SWEEP, and one NOT_RECLAIMED skip (all three
required by name), plus two more (an ENTERED trade and a NOT_RECLAIMED
with new_low_during_reclaim=True, to exercise and document the "do not
reset the clock" rule explicitly) from whatever the real DEV data
actually contains.
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
from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.backtest import build_universe, _build_trend_lookup_for_entity
from poc.context import build_poc_context, lookback_dates
from poc.resolution import resolve_exit
from poc.v2 import compute_lookback_low
from poc.v4 import (
    _build_atr_adjusted_lookup_for_entity, _build_adjustment_factor_lookup_for_entity, find_entry_v4,
)

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

WANTED = {
    "TOUCH_TOO_SHALLOW": None, "BREAKDOWN_NOT_SWEEP": None, "NOT_RECLAIMED": None,
    "NOT_RECLAIMED_NEW_LOW": None, "ENTERED": None,
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
            prev_high = ctx["prev_high"]
            entry = find_entry_v4(candles5, day_raw, lookback_low, prev_high, atr_raw)
            status = entry["status"]

            want_key = None
            if status == "TOUCH_TOO_SHALLOW" and found["TOUCH_TOO_SHALLOW"] is None:
                want_key = "TOUCH_TOO_SHALLOW"
            elif status == "BREAKDOWN_NOT_SWEEP" and found["BREAKDOWN_NOT_SWEEP"] is None:
                want_key = "BREAKDOWN_NOT_SWEEP"
            elif status == "NOT_RECLAIMED" and not entry["new_low_during_reclaim"] and found["NOT_RECLAIMED"] is None:
                want_key = "NOT_RECLAIMED"
            elif status == "NOT_RECLAIMED" and entry["new_low_during_reclaim"] and found["NOT_RECLAIMED_NEW_LOW"] is None:
                want_key = "NOT_RECLAIMED_NEW_LOW"

            if want_key:
                print(f"\n=== FOUND {want_key}: {entity_id} {day} ===")
                print(f"  LOOKBACK_LOW={lookback_low:.4f}  PREV_HIGH={prev_high:.4f}  ATR_raw={atr_raw:.4f}")
                print(f"  entry dict: {entry}")
                if "sweep_idx" in entry:
                    sweep_candle = candles5.iloc[entry["sweep_idx"]]
                    print(f"  sweep candle (idx {entry['sweep_idx']}, ts={sweep_candle['ts']}): "
                          f"O={sweep_candle['open']:.4f} H={sweep_candle['high']:.4f} "
                          f"L={sweep_candle['low']:.4f} C={sweep_candle['close']:.4f}")
                    n = len(candles5)
                    for offset in (1, 2, 3):
                        idx = entry["sweep_idx"] + offset
                        if idx < n:
                            row = candles5.iloc[idx]
                            print(f"  reclaim candidate offset={offset} (idx {idx}, ts={row['ts']}): "
                                  f"O={row['open']:.4f} H={row['high']:.4f} L={row['low']:.4f} C={row['close']:.4f}  "
                                  f"close>LOOKBACK_LOW? {row['close'] > lookback_low}")
                found[want_key] = True

            if status == "ENTERED" and found["ENTERED"] is None:
                try:
                    exit_res = resolve_exit(
                        day_raw, candles5, entry["fill_ts"], entry["entry_price"],
                        entry["stop_price"], entry["target_price"],
                    )
                except Exception as e:
                    print(f"  ERROR resolving {entity_id} {day}: {e}")
                    continue
                qty = entry["qty"]
                entry_price = entry["entry_price"]
                stop_price = entry["stop_price"]
                pnl_rs = qty * (exit_res["exit_price"] - entry_price)
                position_size_rs = qty * entry_price
                cost_rs = round_trip_cost_rs(position_size_rs, ctx["band"])
                net_return_pct = (pnl_rs - cost_rs) / position_size_rs

                sweep_candle = candles5.iloc[entry["sweep_idx"]]
                reclaim_candle = candles5.iloc[entry["reclaim_idx"]]
                print(f"\n=== FOUND ENTERED: {entity_id} {day} ===")
                print(f"  LOOKBACK_LOW={lookback_low:.4f}  PREV_HIGH={prev_high:.4f}  ATR_raw={atr_raw:.4f}  "
                      f"band={ctx['band']} rank={ctx['rank']}")
                print(f"  sweep candle (idx {entry['sweep_idx']}, ts={sweep_candle['ts']}): "
                      f"O={sweep_candle['open']:.4f} H={sweep_candle['high']:.4f} "
                      f"L={sweep_candle['low']:.4f} C={sweep_candle['close']:.4f}")
                print(f"  sweep_depth_atr={entry['sweep_depth_atr']:.4f}  "
                      f"new_low_during_reclaim={entry['new_low_during_reclaim']}")
                print(f"  reclaim candle (idx {entry['reclaim_idx']}, ts={reclaim_candle['ts']}): "
                      f"O={reclaim_candle['open']:.4f} H={reclaim_candle['high']:.4f} "
                      f"L={reclaim_candle['low']:.4f} C={reclaim_candle['close']:.4f}")
                print(f"  fill_ts={entry['fill_ts']}  entry_price={entry_price:.4f}")
                print(f"  stop_price={stop_price:.4f}  stop_distance_pct={(entry_price-stop_price)/entry_price*100:.4f}%  "
                      f"target_price={entry['target_price']:.4f}  qty={qty}")
                print(f"  exit: outcome={exit_res['outcome']} exit_price={exit_res['exit_price']:.4f} "
                      f"exit_ts={exit_res['exit_ts']} time_exit_fallback={exit_res['time_exit_fallback']}")
                print(f"  pnl_rs={pnl_rs:.2f}  position_size_rs={position_size_rs:.2f}  cost_rs={cost_rs:.2f}  "
                      f"net_return_pct={net_return_pct*100:.4f}%")
                print(f"  entry_above_lookback_low_frac={(entry_price-lookback_low)/entry_price*100:.4f}%")
                found["ENTERED"] = True

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
