"""PREREGISTRATION_LIQUIDITY_D.md: liquidity confluence, Study D
(ascending lows). Liquidity family, trial 4 -- Study A and Study B with
the reclaim-and-immediate-entry step REPLACED by a longer structural
requirement: after the sweep, price must form `n_required` (2 for
CONFIG 2LOW, 3 for CONFIG 3LOW) successive local lows/highs, each
strictly closer to the zone than the last, before entry fires.
`src/liquidity/a.py`, `src/liquidity/b.py`, and `src/liquidity/c.py` are
imported read-only, never modified; no closed study's own result is
touched by anything here.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from box_theory.context import eligible_day_context, group_by_day
from box_theory.holiday import previous_nse_trading_day
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.price_scale import to_raw_scale

from liquidity.a import (
    FULL_TARGET_R, HALF_TARGET_R, _build_level_lookup_for_entity, find_confluence_zone,
    hypothetical_single_exit_cost_rs, resolve_scaled_exit_a, three_order_cost_rs,
)
from liquidity.b import (
    find_confluence_zone_b, find_reclaim_short, find_sweep_short,
    hypothetical_single_exit_cost_rs_b, resolve_scaled_exit_b, three_order_cost_rs_b,
)
from liquidity.c import (
    _original_entry_long as _c_original_entry_long,
    _original_entry_short as _c_original_entry_short,
    _resolve_counterfactual_long as _c_resolve_counterfactual_long,
    _resolve_counterfactual_short as _c_resolve_counterfactual_short,
)

from poc.backtest import build_universe, _entity_years
from poc.nulls import _random_fill, _valid_entry_idx
from poc.resolution import ENTRY_WINDOW_END, ENTRY_WINDOW_START, MAX_RISK_PCT, fill_bar_after_candle_close
from poc.v2 import CAPITAL_RS, MIN_RISK_PCT
from poc.v4 import (
    STOP_BUFFER_ATR, find_reclaim, find_sweep,
    _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity,
)

CONFIG_N_REQUIRED = {"2LOW": 2, "3LOW": 3}

SKIP_REASONS_LONG = (
    "jump_guard", "ex_date", "bad_previous_session",
    "level_insufficient_history", "atr_unavailable",
    "no_confluence", "no_sweep", "touch_too_shallow", "breakdown_not_sweep",
    "pattern_broken", "pattern_incomplete",
    "no_fill_bar", "fill_outside_window", "entry_below_stop", "stop_too_wide", "stop_too_tight", "zero_qty",
)
SKIP_REASONS_SHORT = (
    "jump_guard", "ex_date", "bad_previous_session",
    "level_insufficient_history", "atr_unavailable",
    "no_confluence", "no_sweep", "touch_too_shallow", "breakout_not_sweep",
    "pattern_broken", "pattern_incomplete",
    "no_fill_bar", "fill_outside_window", "entry_above_stop", "stop_too_wide", "stop_too_tight", "zero_qty",
)

_ENTRY_STATUS_TO_SKIP_LONG = {
    "TOUCH_TOO_SHALLOW": "touch_too_shallow", "BREAKDOWN_NOT_SWEEP": "breakdown_not_sweep",
    "PATTERN_BROKEN": "pattern_broken", "PATTERN_INCOMPLETE": "pattern_incomplete",
    "NO_FILL_BAR": "no_fill_bar", "FILL_OUTSIDE_WINDOW": "fill_outside_window",
    "ENTRY_BELOW_STOP": "entry_below_stop", "STOP_TOO_WIDE": "stop_too_wide",
    "STOP_TOO_TIGHT": "stop_too_tight", "ZERO_QTY": "zero_qty",
}
_ENTRY_STATUS_TO_SKIP_SHORT = {
    "TOUCH_TOO_SHALLOW": "touch_too_shallow", "BREAKOUT_NOT_SWEEP": "breakout_not_sweep",
    "PATTERN_BROKEN": "pattern_broken", "PATTERN_INCOMPLETE": "pattern_incomplete",
    "NO_FILL_BAR": "no_fill_bar", "FILL_OUTSIDE_WINDOW": "fill_outside_window",
    "ENTRY_ABOVE_STOP": "entry_above_stop", "STOP_TOO_WIDE": "stop_too_wide",
    "STOP_TOO_TIGHT": "stop_too_tight", "ZERO_QTY": "zero_qty",
}


# ---------------------------------------------------------------------
# Section 3: ascending-lows detection -- new, direction-aware, mirrors
# each other exactly with every inequality flipped. Parameterized by
# n_required so one function serves both CONFIG 2LOW and CONFIG 3LOW.
# ---------------------------------------------------------------------

def find_ascending_lows_long(candles5: pd.DataFrame, sweep_idx: int, sweep_low: float,
                              zone_price: float, n_required: int) -> dict:
    """Scans candles STRICTLY AFTER sweep_idx, in order, for the rest of
    the day. A local low at candidate index i (confirmed once candle
    i+1 exists) is a candle whose LOW is below both its neighbours' own
    lows. Only local lows at or below zone_price count; a local low
    above zone_price is ignored entirely (does not count, reset, or
    advance anything). A qualifying local low that is NOT strictly
    higher than the last COUNTED one resets the running count to 1
    (itself becomes the new last-counted low) rather than killing the
    whole pattern -- PATTERN_BROKEN is reserved exclusively for a new
    extreme beyond the original sweep. Returns {"status":
    "PATTERN_BROKEN", "broken_idx": i}, {"status": "PATTERN_CONFIRMED",
    "confirm_idx": i, "final_low": float, "count": int}, or {"status":
    "PATTERN_INCOMPLETE", "count": int}."""
    n = len(candles5)
    last_counted_low = None
    count = 0
    for j in range(sweep_idx + 1, n):
        low_j = float(candles5.iloc[j]["low"])
        if low_j < sweep_low:
            return {"status": "PATTERN_BROKEN", "broken_idx": j}
        candidate_idx = j - 1
        if candidate_idx >= sweep_idx + 1:
            low_before = float(candles5.iloc[candidate_idx - 1]["low"])
            low_candidate = float(candles5.iloc[candidate_idx]["low"])
            if low_candidate < low_before and low_candidate < low_j and low_candidate <= zone_price:
                if last_counted_low is not None and low_candidate > last_counted_low:
                    count += 1
                else:
                    count = 1
                last_counted_low = low_candidate
                if count >= n_required:
                    return {
                        "status": "PATTERN_CONFIRMED", "confirm_idx": j,
                        "final_low": low_candidate, "count": count,
                    }
    return {"status": "PATTERN_INCOMPLETE", "count": count}


def find_ascending_highs_short(candles5: pd.DataFrame, sweep_idx: int, sweep_high: float,
                                zone_price: float, n_required: int) -> dict:
    """Mirror of find_ascending_lows_long: local highs, each qualifying
    high at/above zone_price, each successive counted high must be
    STRICTLY LOWER than the last to extend the count (descending high
    values = ascending toward the level from above)."""
    n = len(candles5)
    last_counted_high = None
    count = 0
    for j in range(sweep_idx + 1, n):
        high_j = float(candles5.iloc[j]["high"])
        if high_j > sweep_high:
            return {"status": "PATTERN_BROKEN", "broken_idx": j}
        candidate_idx = j - 1
        if candidate_idx >= sweep_idx + 1:
            high_before = float(candles5.iloc[candidate_idx - 1]["high"])
            high_candidate = float(candles5.iloc[candidate_idx]["high"])
            if high_candidate > high_before and high_candidate > high_j and high_candidate >= zone_price:
                if last_counted_high is not None and high_candidate < last_counted_high:
                    count += 1
                else:
                    count = 1
                last_counted_high = high_candidate
                if count >= n_required:
                    return {
                        "status": "PATTERN_CONFIRMED", "confirm_idx": j,
                        "final_high": high_candidate, "count": count,
                    }
    return {"status": "PATTERN_INCOMPLETE", "count": count}


# ---------------------------------------------------------------------
# Entry orchestration -- sweep is the ORIGINAL (poc.v4 / liquidity.b)
# function, unchanged; there is NO reclaim step. Ascending-lows and the
# later fill are new.
# ---------------------------------------------------------------------

def find_entry_d_long(candles5: pd.DataFrame, bars1: pd.DataFrame, zone_price: float,
                       atr_raw: float, n_required: int) -> dict:
    sweep = find_sweep(candles5, zone_price, atr_raw)
    if sweep["status"] != "SWEEP":
        return {"status": sweep["status"]}
    sweep_idx, sweep_low = sweep["idx"], sweep["sweep_low"]
    sweep_depth_atr = (zone_price - sweep_low) / atr_raw
    common = {"sweep_idx": sweep_idx, "sweep_depth_atr": sweep_depth_atr, "sweep_low": sweep_low}

    pattern = find_ascending_lows_long(candles5, sweep_idx, sweep_low, zone_price, n_required)
    if pattern["status"] == "PATTERN_INCOMPLETE":
        return {"status": "PATTERN_INCOMPLETE", "pattern_count": pattern["count"], **common}
    if pattern["status"] == "PATTERN_BROKEN":
        return {"status": "PATTERN_BROKEN", "broken_idx": pattern["broken_idx"], **common}

    confirm_idx = pattern["confirm_idx"]
    common["confirm_idx"] = confirm_idx
    common["pattern_count"] = pattern["count"]
    confirm_candle = candles5.iloc[confirm_idx]
    confirm_close_ts = confirm_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, confirm_close_ts)
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", **common}

    fill_ts = pd.Timestamp(fill_bar["ts"])
    if not (ENTRY_WINDOW_START <= fill_ts.time() <= ENTRY_WINDOW_END):
        return {"status": "FILL_OUTSIDE_WINDOW", "fill_ts": fill_ts, **common}

    entry_price = float(fill_bar["open"])
    stop_price = sweep_low - STOP_BUFFER_ATR * atr_raw
    common2 = {"fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price, **common}

    if entry_price <= stop_price:
        return {"status": "ENTRY_BELOW_STOP", **common2}
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT:
        return {"status": "STOP_TOO_WIDE", **common2}
    if risk_pct < MIN_RISK_PCT:
        return {"status": "STOP_TOO_TIGHT", **common2}

    r = entry_price - stop_price
    half_target_price = entry_price + HALF_TARGET_R * r
    full_target_price = entry_price + FULL_TARGET_R * r
    qty = int(CAPITAL_RS // entry_price)
    if qty < 1:
        return {
            "status": "ZERO_QTY", "half_target_price": half_target_price,
            "full_target_price": full_target_price, **common2,
        }

    return {
        "status": "ENTERED", "qty": qty, "half_qty": qty // 2,
        "half_target_price": half_target_price, "full_target_price": full_target_price, **common2,
    }


def find_entry_d_short(candles5: pd.DataFrame, bars1: pd.DataFrame, zone_price: float,
                        atr_raw: float, n_required: int) -> dict:
    sweep = find_sweep_short(candles5, zone_price, atr_raw)
    if sweep["status"] != "SWEEP":
        return {"status": sweep["status"]}
    sweep_idx, sweep_high = sweep["idx"], sweep["sweep_high"]
    sweep_depth_atr = (sweep_high - zone_price) / atr_raw
    common = {"sweep_idx": sweep_idx, "sweep_depth_atr": sweep_depth_atr, "sweep_high": sweep_high}

    pattern = find_ascending_highs_short(candles5, sweep_idx, sweep_high, zone_price, n_required)
    if pattern["status"] == "PATTERN_INCOMPLETE":
        return {"status": "PATTERN_INCOMPLETE", "pattern_count": pattern["count"], **common}
    if pattern["status"] == "PATTERN_BROKEN":
        return {"status": "PATTERN_BROKEN", "broken_idx": pattern["broken_idx"], **common}

    confirm_idx = pattern["confirm_idx"]
    common["confirm_idx"] = confirm_idx
    common["pattern_count"] = pattern["count"]
    confirm_candle = candles5.iloc[confirm_idx]
    confirm_close_ts = confirm_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, confirm_close_ts)
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", **common}

    fill_ts = pd.Timestamp(fill_bar["ts"])
    if not (ENTRY_WINDOW_START <= fill_ts.time() <= ENTRY_WINDOW_END):
        return {"status": "FILL_OUTSIDE_WINDOW", "fill_ts": fill_ts, **common}

    entry_price = float(fill_bar["open"])
    stop_price = sweep_high + STOP_BUFFER_ATR * atr_raw
    common2 = {"fill_ts": fill_ts, "entry_price": entry_price, "stop_price": stop_price, **common}

    if entry_price >= stop_price:
        return {"status": "ENTRY_ABOVE_STOP", **common2}
    risk_pct = (stop_price - entry_price) / entry_price
    if risk_pct > MAX_RISK_PCT:
        return {"status": "STOP_TOO_WIDE", **common2}
    if risk_pct < MIN_RISK_PCT:
        return {"status": "STOP_TOO_TIGHT", **common2}

    r = stop_price - entry_price
    half_target_price = entry_price - HALF_TARGET_R * r
    full_target_price = entry_price - FULL_TARGET_R * r
    qty = int(CAPITAL_RS // entry_price)
    if qty < 1:
        return {
            "status": "ZERO_QTY", "half_target_price": half_target_price,
            "full_target_price": full_target_price, **common2,
        }

    return {
        "status": "ENTERED", "qty": qty, "half_qty": qty // 2,
        "half_target_price": half_target_price, "full_target_price": full_target_price, **common2,
    }


# ---------------------------------------------------------------------
# Counterfactual: what A's (long) / B's (short) own IMMEDIATE entry at
# the first reclaim reachable from the SAME sweep would have produced --
# for Section 9's own "were the filtered-out trades actually worse"
# comparison. Reuses liquidity.c's own already-validated counterfactual
# fill/resolve functions directly (Study D has no reclaim step of its
# own, so `poc.v4.find_reclaim`/`liquidity.b.find_reclaim_short` are
# called here, fresh, on the same sweep, exactly as A/B themselves would).
# ---------------------------------------------------------------------

def _original_ab_entry_long(candles5, bars1, sweep_idx, sweep_low, zone_price, atr_raw):
    reclaim = find_reclaim(candles5, sweep_idx, sweep_low, zone_price)
    if reclaim["status"] != "RECLAIMED":
        return None
    return _c_original_entry_long(candles5, bars1, reclaim["idx"], reclaim["sweep_low"], atr_raw)


def _original_ab_entry_short(candles5, bars1, sweep_idx, sweep_high, zone_price, atr_raw):
    reclaim = find_reclaim_short(candles5, sweep_idx, sweep_high, zone_price)
    if reclaim["status"] != "RECLAIMED":
        return None
    return _c_original_entry_short(candles5, bars1, reclaim["idx"], reclaim["sweep_high"], atr_raw)


# ---------------------------------------------------------------------
# Backtest orchestration (Section 6/9) -- one pair of functions per
# side, parameterized by n_required so both CONFIG 2LOW and CONFIG 3LOW
# share the same code, mirroring liquidity.c.evaluate_entity_c_long/short
# with the retest step replaced by the ascending-lows scan.
# ---------------------------------------------------------------------

def evaluate_entity_d_long(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict, n_required: int,
) -> dict:
    trades: list[dict] = []
    skips = {r: 0 for r in SKIP_REASONS_LONG}
    filtered_out: list[dict] = []
    sweep_depths_atr: list[float] = []
    errors: list[dict] = []

    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache: dict = {}
    level_lookup = _build_level_lookup_for_entity(warehouse_con, entity_id)
    atr_adjusted_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)

    for year in years:
        year_start = max(dt.date(year, 1, 1), start)
        year_end = min(dt.date(year, 12, 31), end)
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
                skips[dctx["skip"]] += 1
                continue

            lv = level_lookup.get(day)
            factor_today = factor_lookup.get(day)
            if lv is None or pd.isna(lv["lo_3m"]) or factor_today is None:
                skips["level_insufficient_history"] += 1
                continue

            prev_day = previous_nse_trading_day(day)
            atr_adjusted = atr_adjusted_lookup.get(prev_day)
            if atr_adjusted is None or pd.isna(atr_adjusted):
                skips["atr_unavailable"] += 1
                continue
            atr_raw = to_raw_scale(atr_adjusted, factor_today)

            lo_3m_raw = to_raw_scale(lv["lo_3m"], factor_today)
            lo_1w_raw = to_raw_scale(lv["lo_1w"], factor_today)
            lo_1d_raw = to_raw_scale(lv["lo_1d"], factor_today)
            prev_close_raw = (
                to_raw_scale(lv["prev_close"], factor_today) if not pd.isna(lv["prev_close"]) else float("nan")
            )

            zone = find_confluence_zone(lo_3m_raw, lo_1w_raw, lo_1d_raw, atr_raw, prev_close_raw)
            if zone["status"] == "NO_CONFLUENCE":
                skips["no_confluence"] += 1
                continue

            today_day_raw, today_candles5 = dctx["day_raw"], dctx["candles5"]
            band, rank, year_of_day = dctx["band"], dctx["rank"], dctx["year"]

            entry = find_entry_d_long(today_candles5, today_day_raw, zone["zone_price"], atr_raw, n_required)
            status = entry["status"]
            if "sweep_depth_atr" in entry:
                sweep_depths_atr.append(entry["sweep_depth_atr"])

            if status == "NO_SWEEP":
                skips["no_sweep"] += 1
                continue
            if status != "ENTERED" and status not in ("PATTERN_BROKEN", "PATTERN_INCOMPLETE"):
                skips[_ENTRY_STATUS_TO_SKIP_LONG[status]] += 1
                continue

            if status in ("PATTERN_BROKEN", "PATTERN_INCOMPLETE", "ENTERED"):
                orig = _original_ab_entry_long(
                    today_candles5, today_day_raw, entry["sweep_idx"], entry["sweep_low"], zone["zone_price"],
                    atr_raw,
                )
                orig_net = (
                    _c_resolve_counterfactual_long(today_day_raw, today_candles5, orig, band)
                    if orig is not None else None
                )
            else:
                orig = orig_net = None

            if status in ("PATTERN_BROKEN", "PATTERN_INCOMPLETE"):
                skips[_ENTRY_STATUS_TO_SKIP_LONG[status]] += 1
                if orig is not None and orig_net is not None:
                    filtered_out.append({
                        "entity_id": entity_id, "trade_date": day, "skip_reason": status.lower(),
                        "original_entry_price": orig["entry_price"], "original_net_return_pct": orig_net,
                    })
                continue

            try:
                exit_res = resolve_scaled_exit_a(
                    today_day_raw, today_candles5, entry["fill_ts"], entry["entry_price"],
                    entry["stop_price"], entry["half_target_price"], entry["full_target_price"], entry["qty"],
                )
            except Exception as e:
                errors.append({"entity_id": entity_id, "trade_date": day, "error": f"{type(e).__name__}: {e}"})
                continue

            qty = entry["qty"]
            entry_price = entry["entry_price"]
            stop_price = entry["stop_price"]
            legs = exit_res["legs"]
            pnl_rs = sum(leg["qty"] * (leg["price"] - entry_price) for leg in legs)
            position_size_rs = qty * entry_price
            total_cost_rs = three_order_cost_rs(entry_price, qty, legs, band)
            hypothetical_cost_rs = hypothetical_single_exit_cost_rs(entry_price, qty, band)
            net_return_pct = (pnl_rs - total_cost_rs) / position_size_rs
            gross_return_pct = pnl_rs / position_size_rs

            half_leg = legs[0] if exit_res["half_exit_happened"] else None
            final_leg = legs[-1]

            sweep_candle = today_candles5.iloc[entry["sweep_idx"]]
            sweep_close_ts = sweep_candle["ts"] + pd.Timedelta(minutes=5)
            delay_minutes = (entry["fill_ts"] - sweep_close_ts).total_seconds() / 60.0
            pct_given_up = (
                (entry_price - orig["entry_price"]) / orig["entry_price"] if orig is not None else None
            )

            trades.append({
                "entity_id": entity_id, "trade_date": day, "year": year_of_day,
                "band": band, "rank": rank,
                "confluence_members": zone["members"], "zone_price": zone["zone_price"],
                "multi_cluster": zone["multi_cluster"],
                "sweep_idx": entry["sweep_idx"], "confirm_idx": entry["confirm_idx"],
                "pattern_count": entry["pattern_count"], "sweep_depth_atr": entry["sweep_depth_atr"],
                "fill_ts": entry["fill_ts"], "entry_price": entry_price, "stop_price": stop_price,
                "half_target_price": entry["half_target_price"], "full_target_price": entry["full_target_price"],
                "qty": qty, "half_qty": entry["half_qty"],
                "outcome": exit_res["outcome"], "qty1_path": exit_res["qty1_path"],
                "half_exit_happened": exit_res["half_exit_happened"],
                "half_exit_ts": half_leg["ts"] if half_leg else None,
                "half_exit_price": half_leg["price"] if half_leg else None,
                "final_exit_ts": final_leg["ts"], "final_exit_price": final_leg["price"],
                "final_exit_kind": final_leg["kind"],
                "time_exit_fallback": exit_res["time_exit_fallback"],
                "position_size_rs": position_size_rs,
                "total_cost_rs": total_cost_rs, "hypothetical_cost_rs": hypothetical_cost_rs,
                "extra_cost_rs": total_cost_rs - hypothetical_cost_rs,
                "pnl_rs": pnl_rs, "gross_return_pct": gross_return_pct, "net_return_pct": net_return_pct,
                "stop_distance_pct": (entry_price - stop_price) / entry_price,
                "delay_minutes": delay_minutes,
                "original_entry_price": orig["entry_price"] if orig is not None else None,
                "original_net_return_pct": orig_net,
                "pct_given_up": pct_given_up,
            })

    return {
        "trades": trades, "skips": skips, "errors": errors, "filtered_out": filtered_out,
        "sweep_depths_atr": sweep_depths_atr,
    }


def evaluate_entity_d_short(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict, n_required: int,
) -> dict:
    trades: list[dict] = []
    skips = {r: 0 for r in SKIP_REASONS_SHORT}
    filtered_out: list[dict] = []
    sweep_depths_atr: list[float] = []
    errors: list[dict] = []

    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache: dict = {}
    level_lookup = _build_level_lookup_for_entity(warehouse_con, entity_id)
    atr_adjusted_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)

    for year in years:
        year_start = max(dt.date(year, 1, 1), start)
        year_end = min(dt.date(year, 12, 31), end)
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
                skips[dctx["skip"]] += 1
                continue

            lv = level_lookup.get(day)
            factor_today = factor_lookup.get(day)
            if lv is None or pd.isna(lv["hi_3m"]) or factor_today is None:
                skips["level_insufficient_history"] += 1
                continue

            prev_day = previous_nse_trading_day(day)
            atr_adjusted = atr_adjusted_lookup.get(prev_day)
            if atr_adjusted is None or pd.isna(atr_adjusted):
                skips["atr_unavailable"] += 1
                continue
            atr_raw = to_raw_scale(atr_adjusted, factor_today)

            hi_3m_raw = to_raw_scale(lv["hi_3m"], factor_today)
            hi_1w_raw = to_raw_scale(lv["hi_1w"], factor_today)
            hi_1d_raw = to_raw_scale(lv["hi_1d"], factor_today)
            prev_close_raw = (
                to_raw_scale(lv["prev_close"], factor_today) if not pd.isna(lv["prev_close"]) else float("nan")
            )

            zone = find_confluence_zone_b(hi_3m_raw, hi_1w_raw, hi_1d_raw, atr_raw, prev_close_raw)
            if zone["status"] == "NO_CONFLUENCE":
                skips["no_confluence"] += 1
                continue

            today_day_raw, today_candles5 = dctx["day_raw"], dctx["candles5"]
            band, rank, year_of_day = dctx["band"], dctx["rank"], dctx["year"]

            entry = find_entry_d_short(today_candles5, today_day_raw, zone["zone_price"], atr_raw, n_required)
            status = entry["status"]
            if "sweep_depth_atr" in entry:
                sweep_depths_atr.append(entry["sweep_depth_atr"])

            if status == "NO_SWEEP":
                skips["no_sweep"] += 1
                continue
            if status != "ENTERED" and status not in ("PATTERN_BROKEN", "PATTERN_INCOMPLETE"):
                skips[_ENTRY_STATUS_TO_SKIP_SHORT[status]] += 1
                continue

            if status in ("PATTERN_BROKEN", "PATTERN_INCOMPLETE", "ENTERED"):
                orig = _original_ab_entry_short(
                    today_candles5, today_day_raw, entry["sweep_idx"], entry["sweep_high"], zone["zone_price"],
                    atr_raw,
                )
                orig_net = (
                    _c_resolve_counterfactual_short(today_day_raw, today_candles5, orig, band)
                    if orig is not None else None
                )
            else:
                orig = orig_net = None

            if status in ("PATTERN_BROKEN", "PATTERN_INCOMPLETE"):
                skips[_ENTRY_STATUS_TO_SKIP_SHORT[status]] += 1
                if orig is not None and orig_net is not None:
                    filtered_out.append({
                        "entity_id": entity_id, "trade_date": day, "skip_reason": status.lower(),
                        "original_entry_price": orig["entry_price"], "original_net_return_pct": orig_net,
                    })
                continue

            try:
                exit_res = resolve_scaled_exit_b(
                    today_day_raw, today_candles5, entry["fill_ts"], entry["entry_price"],
                    entry["stop_price"], entry["half_target_price"], entry["full_target_price"], entry["qty"],
                )
            except Exception as e:
                errors.append({"entity_id": entity_id, "trade_date": day, "error": f"{type(e).__name__}: {e}"})
                continue

            qty = entry["qty"]
            entry_price = entry["entry_price"]
            stop_price = entry["stop_price"]
            legs = exit_res["legs"]
            pnl_rs = sum(leg["qty"] * (entry_price - leg["price"]) for leg in legs)
            position_size_rs = qty * entry_price
            total_cost_rs = three_order_cost_rs_b(entry_price, qty, legs, band)
            hypothetical_cost_rs = hypothetical_single_exit_cost_rs_b(entry_price, qty, band)
            net_return_pct = (pnl_rs - total_cost_rs) / position_size_rs
            gross_return_pct = pnl_rs / position_size_rs

            half_leg = legs[0] if exit_res["half_exit_happened"] else None
            final_leg = legs[-1]

            sweep_candle = today_candles5.iloc[entry["sweep_idx"]]
            sweep_close_ts = sweep_candle["ts"] + pd.Timedelta(minutes=5)
            delay_minutes = (entry["fill_ts"] - sweep_close_ts).total_seconds() / 60.0
            pct_given_up = (
                (orig["entry_price"] - entry_price) / orig["entry_price"] if orig is not None else None
            )

            trades.append({
                "entity_id": entity_id, "trade_date": day, "year": year_of_day,
                "band": band, "rank": rank,
                "confluence_members": zone["members"], "zone_price": zone["zone_price"],
                "multi_cluster": zone["multi_cluster"],
                "sweep_idx": entry["sweep_idx"], "confirm_idx": entry["confirm_idx"],
                "pattern_count": entry["pattern_count"], "sweep_depth_atr": entry["sweep_depth_atr"],
                "fill_ts": entry["fill_ts"], "entry_price": entry_price, "stop_price": stop_price,
                "half_target_price": entry["half_target_price"], "full_target_price": entry["full_target_price"],
                "qty": qty, "half_qty": entry["half_qty"],
                "outcome": exit_res["outcome"], "qty1_path": exit_res["qty1_path"],
                "half_exit_happened": exit_res["half_exit_happened"],
                "half_exit_ts": half_leg["ts"] if half_leg else None,
                "half_exit_price": half_leg["price"] if half_leg else None,
                "final_exit_ts": final_leg["ts"], "final_exit_price": final_leg["price"],
                "final_exit_kind": final_leg["kind"],
                "time_exit_fallback": exit_res["time_exit_fallback"],
                "position_size_rs": position_size_rs,
                "total_cost_rs": total_cost_rs, "hypothetical_cost_rs": hypothetical_cost_rs,
                "extra_cost_rs": total_cost_rs - hypothetical_cost_rs,
                "pnl_rs": pnl_rs, "gross_return_pct": gross_return_pct, "net_return_pct": net_return_pct,
                "stop_distance_pct": (stop_price - entry_price) / entry_price,
                "delay_minutes": delay_minutes,
                "original_entry_price": orig["entry_price"] if orig is not None else None,
                "original_net_return_pct": orig_net,
                "pct_given_up": pct_given_up,
            })

    return {
        "trades": trades, "skips": skips, "errors": errors, "filtered_out": filtered_out,
        "sweep_depths_atr": sweep_depths_atr,
    }


def _run_backtest_d(evaluate_fn, skip_reasons, intraday_con, warehouse_con, start, end, n_required, entity_ids=None):
    """Shared driver, identical structure to liquidity.c._run_backtest_c,
    parameterized by which per-entity evaluator AND which n_required to use."""
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
        return {
            "trades": pd.DataFrame(), "skips": {r: 0 for r in skip_reasons}, "errors": [],
            "filtered_out": pd.DataFrame(), "sweep_depths_atr": [], "universe": universe,
        }
    from fibo.universe import assert_universe_membership, restrict_to_universe
    candidates = restrict_to_universe(candidates, universe)
    entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    all_trades: list[dict] = []
    all_filtered_out: list[dict] = []
    total_skips = {r: 0 for r in skip_reasons}
    all_sweep_depths: list[float] = []
    all_errors: list[dict] = []

    for entity_id, years in entity_years.items():
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_fn(
            intraday_con, warehouse_con, entity_id, years, start, end, jump_dates, rank_lookup, n_required)
        all_trades.extend(result["trades"])
        all_filtered_out.extend(result["filtered_out"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        all_sweep_depths.extend(result["sweep_depths_atr"])
        all_errors.extend(result["errors"])

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label="liquidity study D trade list")

    return {
        "trades": trades_df, "skips": total_skips, "errors": all_errors,
        "filtered_out": pd.DataFrame(all_filtered_out), "sweep_depths_atr": all_sweep_depths, "universe": universe,
    }


def run_backtest_d_long(intraday_con, warehouse_con, start: dt.date, end: dt.date, config: str,
                         entity_ids=None) -> dict:
    return _run_backtest_d(evaluate_entity_d_long, SKIP_REASONS_LONG, intraday_con, warehouse_con,
                            start, end, CONFIG_N_REQUIRED[config], entity_ids)


def run_backtest_d_short(intraday_con, warehouse_con, start: dt.date, end: dt.date, config: str,
                          entity_ids=None) -> dict:
    return _run_backtest_d(evaluate_entity_d_short, SKIP_REASONS_SHORT, intraday_con, warehouse_con,
                            start, end, CONFIG_N_REQUIRED[config], entity_ids)


# ---------------------------------------------------------------------
# Nulls (Section 7) -- identical population/structure to liquidity.c,
# built from each configuration's own trades and pool.
# ---------------------------------------------------------------------

def build_timing_pool_d(intraday_con, warehouse_con, trades: pd.DataFrame, rank_lookup: dict,
                         jump_dates_by_entity: dict) -> list[dict]:
    pool = []
    for entity_id, grp in trades.groupby("entity_id"):
        days = sorted(grp["trade_date"].unique())
        years = sorted({d.year for d in days})
        start, end = min(days), max(days)
        bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
        ex_dates = fetch_ex_dates(warehouse_con, entity_id)
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        single_day_cache: dict = {}
        block = fetch_bars_range(intraday_con, entity_id, start, end)
        day_groups = group_by_day(block)

        for _, row in grp.iterrows():
            day = row["trade_date"]
            dctx = eligible_day_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup,
            )
            if dctx["skip"] is not None:
                continue
            stop_distance_rs = abs(float(row["entry_price"]) - float(row["stop_price"]))
            pool.append({
                "candles5": dctx["candles5"], "day_raw": dctx["day_raw"],
                "valid_idx": _valid_entry_idx(dctx["candles5"]),
                "stop_distance_rs": stop_distance_rs, "band": row["band"],
            })
    return pool


def _timing_draw_d_long(ctx: dict, rng: np.random.Generator) -> float | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = entry_price - ctx["stop_distance_rs"]
    if stop_price <= 0:
        return None
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT or risk_pct < MIN_RISK_PCT:
        return None
    r = entry_price - stop_price
    half_target_price = entry_price + HALF_TARGET_R * r
    full_target_price = entry_price + FULL_TARGET_R * r
    qty = int(CAPITAL_RS // entry_price)
    if qty < 1:
        return None
    exit_res = resolve_scaled_exit_a(
        ctx["day_raw"], ctx["candles5"], fill_ts, entry_price, stop_price,
        half_target_price, full_target_price, qty,
    )
    legs = exit_res["legs"]
    pnl_rs = sum(leg["qty"] * (leg["price"] - entry_price) for leg in legs)
    position_size_rs = qty * entry_price
    total_cost_rs = three_order_cost_rs(entry_price, qty, legs, ctx["band"])
    return (pnl_rs - total_cost_rs) / position_size_rs


def _timing_draw_d_short(ctx: dict, rng: np.random.Generator) -> float | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = entry_price + ctx["stop_distance_rs"]
    risk_pct = (stop_price - entry_price) / entry_price
    if risk_pct > MAX_RISK_PCT or risk_pct < MIN_RISK_PCT:
        return None
    r = stop_price - entry_price
    half_target_price = entry_price - HALF_TARGET_R * r
    full_target_price = entry_price - FULL_TARGET_R * r
    qty = int(CAPITAL_RS // entry_price)
    if qty < 1:
        return None
    exit_res = resolve_scaled_exit_b(
        ctx["day_raw"], ctx["candles5"], fill_ts, entry_price, stop_price,
        half_target_price, full_target_price, qty,
    )
    legs = exit_res["legs"]
    pnl_rs = sum(leg["qty"] * (entry_price - leg["price"]) for leg in legs)
    position_size_rs = qty * entry_price
    total_cost_rs = three_order_cost_rs_b(entry_price, qty, legs, ctx["band"])
    return (pnl_rs - total_cost_rs) / position_size_rs


def timing_null_seed_mean_d(pool: list[dict], draw_fn, rng: np.random.Generator) -> float:
    draws = [r for ctx in pool if (r := draw_fn(ctx, rng)) is not None]
    return float(np.mean(draws)) if draws else float("nan")


def _get_or_build_entity_setup_d(warehouse_con, entity_id: str, jump_dates: set,
                                  full_start: dt.date, full_end: dt.date, setup_cache: dict) -> dict:
    if entity_id in setup_cache:
        return setup_cache[entity_id]
    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(full_start.year - 1, 1, 1), full_end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    level_lookup = _build_level_lookup_for_entity(warehouse_con, entity_id)
    atr_adjusted_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)
    entry = {
        "bhav": bhav, "ex_dates": ex_dates, "level_lookup": level_lookup,
        "atr_adjusted_lookup": atr_adjusted_lookup, "factor_lookup": factor_lookup,
    }
    setup_cache[entity_id] = entry
    return entry


def build_month_pool_d(intraday_con, warehouse_con, universe: pd.DataFrame, year: int, month: int,
                        rank_lookup: dict, jump_dates_by_entity: dict, entity_setup_cache: dict,
                        full_start: dt.date, full_end: dt.date, level_key: str) -> list[dict]:
    month_start = dt.date(year, month, 1)
    month_end = (dt.date(year, month, 1) + pd.offsets.MonthEnd(0)).date()
    members = universe.loc[universe["year"] == year, "entity_id"].tolist()

    pool = []
    for entity_id in members:
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        setup = _get_or_build_entity_setup_d(warehouse_con, entity_id, jump_dates, full_start, full_end,
                                              entity_setup_cache)
        single_day_cache: dict = {}
        block = fetch_bars_range(intraday_con, entity_id, month_start, month_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        for day in sorted(day_groups.keys()):
            dctx = eligible_day_context(
                intraday_con, entity_id, day, day_groups, setup["bhav"], setup["ex_dates"], jump_dates,
                single_day_cache, rank_lookup,
            )
            if dctx["skip"] is not None:
                continue
            lv = setup["level_lookup"].get(day)
            factor_today = setup["factor_lookup"].get(day)
            if lv is None or pd.isna(lv[level_key]) or factor_today is None:
                continue
            prev_day = previous_nse_trading_day(day)
            atr_adjusted = setup["atr_adjusted_lookup"].get(prev_day)
            if atr_adjusted is None or pd.isna(atr_adjusted):
                continue
            pool.append({
                "candles5": dctx["candles5"], "day_raw": dctx["day_raw"],
                "valid_idx": _valid_entry_idx(dctx["candles5"]), "band": dctx["band"],
            })
    return pool


def _selection_draw_d_long(ctx: dict, sampled_pct: float, rng: np.random.Generator) -> float | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = entry_price * (1 - sampled_pct)
    if stop_price <= 0:
        return None
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT or risk_pct < MIN_RISK_PCT:
        return None
    r = entry_price - stop_price
    half_target_price = entry_price + HALF_TARGET_R * r
    full_target_price = entry_price + FULL_TARGET_R * r
    qty = int(CAPITAL_RS // entry_price)
    if qty < 1:
        return None
    exit_res = resolve_scaled_exit_a(
        ctx["day_raw"], ctx["candles5"], fill_ts, entry_price, stop_price,
        half_target_price, full_target_price, qty,
    )
    legs = exit_res["legs"]
    pnl_rs = sum(leg["qty"] * (leg["price"] - entry_price) for leg in legs)
    position_size_rs = qty * entry_price
    total_cost_rs = three_order_cost_rs(entry_price, qty, legs, ctx["band"])
    return (pnl_rs - total_cost_rs) / position_size_rs


def _selection_draw_d_short(ctx: dict, sampled_pct: float, rng: np.random.Generator) -> float | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = entry_price * (1 + sampled_pct)
    risk_pct = (stop_price - entry_price) / entry_price
    if risk_pct > MAX_RISK_PCT or risk_pct < MIN_RISK_PCT:
        return None
    r = stop_price - entry_price
    half_target_price = entry_price - HALF_TARGET_R * r
    full_target_price = entry_price - FULL_TARGET_R * r
    qty = int(CAPITAL_RS // entry_price)
    if qty < 1:
        return None
    exit_res = resolve_scaled_exit_b(
        ctx["day_raw"], ctx["candles5"], fill_ts, entry_price, stop_price,
        half_target_price, full_target_price, qty,
    )
    legs = exit_res["legs"]
    pnl_rs = sum(leg["qty"] * (entry_price - leg["price"]) for leg in legs)
    position_size_rs = qty * entry_price
    total_cost_rs = three_order_cost_rs_b(entry_price, qty, legs, ctx["band"])
    return (pnl_rs - total_cost_rs) / position_size_rs


def selection_null_seed_mean_d(month_pool: list[dict], count: int, rng: np.random.Generator,
                                rho_pool: np.ndarray, draw_fn) -> list[float]:
    if not month_pool:
        return []
    draws = []
    n = len(month_pool)
    for _ in range(count):
        ctx = month_pool[int(rng.integers(0, n))]
        sampled_pct = float(rho_pool[int(rng.integers(0, len(rho_pool)))])
        r = draw_fn(ctx, sampled_pct, rng)
        if r is not None:
            draws.append(r)
    return draws


# ---------------------------------------------------------------------
# Study D's own sealed TEST window -- own object, own log, shares
# nothing with A's, B's, C's, or any other guard
# ---------------------------------------------------------------------

SEALED_AT = dt.date(2026, 11, 1)

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 18)

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "liquidity" / "d" / "test_window_access_log.txt"


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside Study D's own sealed test window."""


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
            f"requested range end {end} intersects Study D's own sealed test window "
            f"(>= {TEST_START}). This is disallowed by default. If this really is the "
            f"one authorized end-of-study test evaluation, pass authorize_test=True "
            f"explicitly -- and only there."
        )
