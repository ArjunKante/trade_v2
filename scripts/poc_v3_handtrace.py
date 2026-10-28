"""PREREGISTRATION_POC_V3.md Process Step 2: hand-trace 5 real DEV-window
trades/skips before any aggregate number is computed -- at minimum one
ENTERED trade showing the hourly touch/confirm candles and the
bucket_end-derived fill timestamp, and one FILL_OUTSIDE_WINDOW skip
(demonstrating the stated consequence that hourly confirmation consumes
far more of the session) -- the remaining three from whatever other
shapes (STOP_TOO_WIDE, a second ENTERED with a different exit outcome,
NO_CONFIRMATION, POC_FAILED) the real DEV data actually contains.
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

from fvg.bars import aggregate_to_1hour

from poc.backtest import build_universe, _build_trend_lookup_for_entity
from poc.context import build_poc_context
from poc.resolution import resolve_exit
from poc.v2 import compute_lookback_low
from poc.v3 import find_entry_v3

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

WANTED = {
    "ENTERED_1": None, "FILL_OUTSIDE_WINDOW": None, "STOP_TOO_WIDE": None,
    "ENTERED_2_OTHER_OUTCOME": None, "NO_CONFIRMATION_OR_POC_FAILED": None,
}


def _print_hourly_candle(label: str, row) -> None:
    print(f"  {label} (ts={row['ts']}, bucket_end={row['bucket_end']}): "
          f"O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f}")


def trace_entity(intraday_con, warehouse_con, entity_id, years, rank_lookup, jump_dates, found,
                  first_entered_outcome):
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

            day_raw = ctx["today_day_raw"]
            candles5 = ctx["today_candles5"]
            poc_price, prev_high = ctx["poc_price"], ctx["prev_high"]
            candles_hourly = aggregate_to_1hour(day_raw)

            entry = find_entry_v3(candles_hourly, day_raw, poc_price, prev_high, lookback_low)
            status = entry["status"]

            if status in ("NO_CONFIRMATION", "POC_FAILED") and found["NO_CONFIRMATION_OR_POC_FAILED"] is None:
                print(f"\n=== FOUND {status}: {entity_id} {day} ===")
                print(f"  POC_PRICE={poc_price:.4f}  PREV_HIGH={prev_high:.4f}  LOOKBACK_LOW={lookback_low:.4f}")
                _print_hourly_candle("touch candle", candles_hourly.iloc[entry["touch_idx"]])
                if "confirm_idx" in entry:
                    _print_hourly_candle("confirm candle", candles_hourly.iloc[entry["confirm_idx"]])
                print(f"  n hourly candles this day: {len(candles_hourly)} "
                      f"(touch_idx={entry['touch_idx']} of 0..{len(candles_hourly)-1})")
                found["NO_CONFIRMATION_OR_POC_FAILED"] = True

            if status == "STOP_TOO_WIDE" and found["STOP_TOO_WIDE"] is None:
                touch_candle = candles_hourly.iloc[entry["touch_idx"]]
                confirm_candle = candles_hourly.iloc[entry["confirm_idx"]]
                risk_pct = (entry["entry_price"] - entry["stop_price"]) / entry["entry_price"]
                print(f"\n=== FOUND STOP_TOO_WIDE: {entity_id} {day} ===")
                print(f"  POC_PRICE={poc_price:.4f}  PREV_HIGH={prev_high:.4f}  LOOKBACK_LOW={lookback_low:.4f}")
                _print_hourly_candle("touch candle", touch_candle)
                _print_hourly_candle(f"confirm candle (kind={entry.get('confirm_kind','?')})", confirm_candle)
                print(f"  fill_ts={entry['fill_ts']}  entry_price={entry['entry_price']:.4f}")
                print(f"  stop_price (=LOOKBACK_LOW)={entry['stop_price']:.4f}  risk_pct={risk_pct*100:.3f}%  "
                      f"(>5% ceiling)")
                found["STOP_TOO_WIDE"] = True

            if status == "FILL_OUTSIDE_WINDOW" and found["FILL_OUTSIDE_WINDOW"] is None:
                touch_candle = candles_hourly.iloc[entry["touch_idx"]]
                confirm_candle = candles_hourly.iloc[entry["confirm_idx"]]
                print(f"\n=== FOUND FILL_OUTSIDE_WINDOW: {entity_id} {day} ===")
                print(f"  POC_PRICE={poc_price:.4f}")
                _print_hourly_candle("touch candle", touch_candle)
                _print_hourly_candle(f"confirm candle (kind={entry.get('confirm_kind','?')})", confirm_candle)
                print(f"  confirm candle bucket_end={confirm_candle['bucket_end']}  "
                      f"fill_ts={entry['fill_ts']}  fill_time={entry['fill_ts'].time()}  "
                      f"(entry window is 09:45-14:30)")
                found["FILL_OUTSIDE_WINDOW"] = True

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
            if found["ENTERED_1"] is None:
                want_key = "ENTERED_1"
                first_entered_outcome[0] = outcome
            elif found["ENTERED_2_OTHER_OUTCOME"] is None and outcome != first_entered_outcome[0]:
                want_key = "ENTERED_2_OTHER_OUTCOME"

            if want_key:
                touch_candle = candles_hourly.iloc[entry["touch_idx"]]
                confirm_candle = candles_hourly.iloc[entry["confirm_idx"]]
                risk_pct = (entry_price - stop_price) / entry_price
                print(f"\n=== FOUND {want_key} (outcome={outcome}): {entity_id} {day} ===")
                print(f"  POC_PRICE={poc_price:.4f}  PREV_HIGH={prev_high:.4f}  LOOKBACK_LOW={lookback_low:.4f}  "
                      f"band={ctx['band']} rank={ctx['rank']}")
                _print_hourly_candle("touch candle", touch_candle)
                _print_hourly_candle(f"confirm candle (kind={entry['confirm_kind']})", confirm_candle)
                print(f"  fill_ts={entry['fill_ts']} (= confirm candle's own bucket_end)  "
                      f"entry_price={entry_price:.4f}")
                print(f"  stop_price (=LOOKBACK_LOW)={stop_price:.4f}  stop_distance_pct={risk_pct*100:.3f}%  "
                      f"target_price={entry['target_price']:.4f}  qty={qty}")
                print(f"  exit: outcome={outcome} exit_price={exit_res['exit_price']:.4f} "
                      f"exit_ts={exit_res['exit_ts']} time_exit_fallback={exit_res['time_exit_fallback']}")
                print(f"  pnl_rs={pnl_rs:.2f}  position_size_rs={position_size_rs:.2f}  cost_rs={cost_rs:.2f}  "
                      f"cost_pct={cost_rs/position_size_rs*100:.4f}%  net_return_pct={net_return_pct*100:.4f}%")
                print(f"  entry_above_poc_frac={(entry_price-poc_price)/entry_price*100:.4f}%")
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
    first_entered_outcome = [None]
    for i, entity_id in enumerate(ordered_entities):
        print(f"[{i+1}/{len(ordered_entities)}] scanning {entity_id} ... "
              f"(found so far: {[k for k,v in found.items() if v is not None]})", flush=True)
        done = trace_entity(intraday_con, warehouse_con, entity_id, entity_years[entity_id],
                             rank_lookup, jump_dates_by_entity.get(entity_id, set()), found,
                             first_entered_outcome)
        if done:
            print("\n=== ALL 5 SHAPES FOUND ===")
            break
    else:
        missing = [k for k, v in found.items() if v is None]
        print(f"\n=== EXHAUSTED SAMPLE, still missing: {missing} ===")


if __name__ == "__main__":
    main()
