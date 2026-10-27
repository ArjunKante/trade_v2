"""PREREGISTRATION_POC_V2.md Process Step 2: hand-trace 5 real DEV-window
trades/skips before any aggregate number is computed -- one TARGET exit,
one STOP exit (showing the 5-day LOOKBACK_LOW the stop came from), one
STOP_TOO_WIDE skip (expected to be common), plus two more from whatever
other shapes the real DEV data contains.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con
from fibo.jump_guard import combined_unexplained_jump_dates

from box_theory.context import group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.backtest import build_universe, _build_trend_lookup_for_entity
from poc.context import build_poc_context
from poc.resolution import resolve_exit
from poc.v2 import compute_lookback_low, find_entry_v2

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

WANTED = {"TARGET": None, "STOP": None, "STOP_TOO_WIDE": None, "TIME_EXIT": None, "HAMMER": None}


def trace_entity(intraday_con, warehouse_con, entity_id, years, rank_lookup, jump_dates, found):
    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), DEV_END)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache = {}
    eligible_ctx_cache = {}
    trend_lookup = _build_trend_lookup_for_entity(warehouse_con, entity_id, jump_dates)

    for year in years:
        year_start = max(dt.date(year, 1, 1), DEV_START)
        year_end = min(dt.date(year, 12, 31), DEV_END)
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
                continue

            lookback_low = compute_lookback_low(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup, eligible_ctx_cache,
            )
            if ctx["skip"] == "TREND_FILTER_FAILED":
                continue

            candles5, day_raw = ctx["today_candles5"], ctx["today_day_raw"]
            poc_price, prev_high = ctx["poc_price"], ctx["prev_high"]
            entry = find_entry_v2(candles5, day_raw, poc_price, prev_high, lookback_low)
            status = entry["status"]

            if status == "STOP_TOO_WIDE" and found["STOP_TOO_WIDE"] is None:
                touch_candle = candles5.iloc[entry["touch_idx"]]
                confirm_candle = candles5.iloc[entry["confirm_idx"]]
                risk_pct = (entry["entry_price"] - entry["stop_price"]) / entry["entry_price"]
                print(f"\n=== FOUND STOP_TOO_WIDE: {entity_id} {day} ===")
                print(f"  POC_PRICE={poc_price:.4f}  PREV_HIGH={prev_high:.4f}  LOOKBACK_LOW={lookback_low:.4f}")
                print(f"  touch candle (idx {entry['touch_idx']}): {touch_candle[['ts','open','high','low','close']].to_dict()}")
                print(f"  confirm candle (idx {entry['confirm_idx']}): {confirm_candle[['ts','open','high','low','close']].to_dict()}")
                print(f"  fill_ts={entry['fill_ts']}  entry_price={entry['entry_price']:.4f}")
                print(f"  stop_price (=LOOKBACK_LOW)={entry['stop_price']:.4f}  risk_pct={risk_pct*100:.3f}%  (>5% ceiling)")
                found["STOP_TOO_WIDE"] = True

            if status != "ENTERED":
                continue

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

            outcome = exit_res["outcome"]
            want_key = None
            if outcome == "TARGET" and found["TARGET"] is None:
                want_key = "TARGET"
            elif outcome == "STOP" and found["STOP"] is None:
                want_key = "STOP"
            elif outcome == "TIME_EXIT" and found["TIME_EXIT"] is None:
                want_key = "TIME_EXIT"

            if want_key or (entry["confirm_kind"] == "HAMMER" and found["HAMMER"] is None):
                touch_candle = candles5.iloc[entry["touch_idx"]]
                confirm_candle = candles5.iloc[entry["confirm_idx"]]
                tag = want_key or "HAMMER"
                risk_pct = (entry_price - stop_price) / entry_price
                print(f"\n=== FOUND {tag}: {entity_id} {day} ===")
                print(f"  POC_PRICE={poc_price:.4f}  PREV_HIGH={prev_high:.4f}  LOOKBACK_LOW={lookback_low:.4f}  "
                      f"band={ctx['band']} rank={ctx['rank']}")
                print(f"  touch candle (idx {entry['touch_idx']}, ts={touch_candle['ts']}): "
                      f"O={touch_candle['open']:.2f} H={touch_candle['high']:.2f} "
                      f"L={touch_candle['low']:.2f} C={touch_candle['close']:.2f}")
                print(f"  confirm candle (idx {entry['confirm_idx']}, ts={confirm_candle['ts']}, "
                      f"kind={entry['confirm_kind']}): O={confirm_candle['open']:.2f} "
                      f"H={confirm_candle['high']:.2f} L={confirm_candle['low']:.2f} C={confirm_candle['close']:.2f}")
                print(f"  fill_ts={entry['fill_ts']}  entry_price={entry_price:.4f}")
                print(f"  stop_price (=LOOKBACK_LOW)={stop_price:.4f}  stop_distance_pct={risk_pct*100:.3f}%  "
                      f"target_price={entry['target_price']:.4f}  qty={qty}")
                print(f"  exit: outcome={outcome} exit_price={exit_res['exit_price']:.4f} "
                      f"exit_ts={exit_res['exit_ts']} time_exit_fallback={exit_res['time_exit_fallback']}")
                print(f"  pnl_rs={pnl_rs:.2f}  position_size_rs={position_size_rs:.2f}  cost_rs={cost_rs:.2f}  "
                      f"cost_pct={cost_rs/position_size_rs*100:.4f}%  net_return_pct={net_return_pct*100:.4f}%")
                if want_key:
                    found[want_key] = True
                if entry["confirm_kind"] == "HAMMER" and found["HAMMER"] is None:
                    found["HAMMER"] = True

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
