"""PREREGISTRATION_LIQUIDITY_A.md: liquidity confluence, Study A (long
only).

ALL new logic for Study A lives in this one file. Shared infrastructure
from `poc.*`, `box_theory.*`, `fibo.*`, and `swing.costs` is imported and
reused READ-ONLY -- never modified, so no closed study's own result can
be touched by anything here. See the prereg's own Section 0 for exactly
which pieces are reused and why.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from box_theory.context import eligible_day_context, group_by_day
from box_theory.costs import BAND_SPREAD_BPS, round_trip_cost_rs as hypothetical_round_trip_cost_rs
from box_theory.holiday import previous_nse_trading_day
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from fibo.daily_ohlc import build_daily_ohlc_panel
from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.price_scale import to_raw_scale
from fibo.universe import assert_universe_membership, restrict_to_universe

from poc.backtest import build_universe, _entity_years
from poc.nulls import _random_fill, _valid_entry_idx
from poc.resolution import (
    ENTRY_WINDOW_END, ENTRY_WINDOW_START, MAX_RISK_PCT, fill_bar_after_candle_close,
    resolve_exit, _stop_target_event,
)
from poc.v2 import CAPITAL_RS, MIN_RISK_PCT
from poc.v4 import (
    STOP_BUFFER_ATR, find_reclaim, find_sweep,
    _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity,
)

from swing.costs import buy_leg_cost_rs, sell_leg_cost_rs

# ---------------------------------------------------------------------
# Study A's own frozen parameters
# ---------------------------------------------------------------------

LEVEL_WINDOW_1W_DAYS = 5
LEVEL_WINDOW_3M_DAYS = 63
CONFLUENCE_TOL_ATR = 0.5
HALF_TARGET_R = 1.5
FULL_TARGET_R = 3.0

SKIP_REASONS = (
    "jump_guard", "ex_date", "bad_previous_session",
    "level_insufficient_history", "atr_unavailable",
    "no_confluence", "no_sweep", "touch_too_shallow", "breakdown_not_sweep", "not_reclaimed",
    "no_fill_bar", "fill_outside_window", "entry_below_stop", "stop_too_wide", "stop_too_tight", "zero_qty",
)

_ENTRY_STATUS_TO_SKIP = {
    "TOUCH_TOO_SHALLOW": "touch_too_shallow", "BREAKDOWN_NOT_SWEEP": "breakdown_not_sweep",
    "NOT_RECLAIMED": "not_reclaimed", "NO_FILL_BAR": "no_fill_bar",
    "FILL_OUTSIDE_WINDOW": "fill_outside_window", "ENTRY_BELOW_STOP": "entry_below_stop",
    "STOP_TOO_WIDE": "stop_too_wide", "STOP_TOO_TIGHT": "stop_too_tight", "ZERO_QTY": "zero_qty",
}


# ---------------------------------------------------------------------
# Level construction (Section 1) -- entity-adjusted daily panel, shifted
# by 1 row before any rolling window, converted to TODAY's raw scale at
# evaluation time via the same mechanism poc.v4 already uses for ATR.
# ---------------------------------------------------------------------

def _build_level_lookup_for_entity(warehouse_con: duckdb.DuckDBPyConnection, entity_id: str) -> dict[dt.date, dict]:
    """{trade_date: {"lo_1d","hi_1d","lo_1w","hi_1w","lo_3m","hi_3m",
    "prev_close"}} -- all still on `fibo.daily_ohlc`'s entity-ADJUSTED
    scale, NOT yet converted to any particular day's raw scale (the
    caller does that per trade date, same two-step shape as poc.v4's own
    ATR lookup)."""
    panel = build_daily_ohlc_panel(warehouse_con, entity_ids=[entity_id])
    if panel.empty:
        return {}
    panel = panel.sort_values("trade_date").reset_index(drop=True)
    shifted_low = panel["adjusted_low"].shift(1)
    shifted_high = panel["adjusted_high"].shift(1)
    shifted_close = panel["adjusted_close"].shift(1)

    lo_1w = shifted_low.rolling(LEVEL_WINDOW_1W_DAYS).min()
    hi_1w = shifted_high.rolling(LEVEL_WINDOW_1W_DAYS).max()
    lo_3m = shifted_low.rolling(LEVEL_WINDOW_3M_DAYS).min()
    hi_3m = shifted_high.rolling(LEVEL_WINDOW_3M_DAYS).max()

    dates = panel["trade_date"].dt.date.to_numpy()
    out: dict[dt.date, dict] = {}
    for i, d in enumerate(dates):
        out[d] = {
            "lo_1d": shifted_low.iat[i], "hi_1d": shifted_high.iat[i],
            "lo_1w": lo_1w.iat[i], "hi_1w": hi_1w.iat[i],
            "lo_3m": lo_3m.iat[i], "hi_3m": hi_3m.iat[i],
            "prev_close": shifted_close.iat[i],
        }
    return out


# ---------------------------------------------------------------------
# Confluence zone (Section 2)
# ---------------------------------------------------------------------

def find_confluence_zone(
    lo_3m_raw: float, lo_1w_raw: float, lo_1d_raw: float, atr_raw: float, prev_close_raw: float,
) -> dict:
    """Connected components over the "within 0.5xATR" adjacency graph on
    the three LOW levels. Returns {"status": "NO_CONFLUENCE"} or
    {"status": "CONFLUENCE", "members": tuple, "zone_price": float,
    "multi_cluster": bool}. See PREREGISTRATION_LIQUIDITY_A.md Section 2
    for the proof that `multi_cluster` can never be True with exactly
    three candidate levels -- the branch below is kept for defensive
    correctness and Study B's own reuse, not because it is expected to
    execute here."""
    levels = {"3m": lo_3m_raw, "1w": lo_1w_raw, "1d": lo_1d_raw}
    tol = CONFLUENCE_TOL_ATR * atr_raw
    pairs = (("3m", "1w"), ("3m", "1d"), ("1w", "1d"))
    edges = [(a, b) for a, b in pairs if abs(levels[a] - levels[b]) <= tol]
    if not edges:
        return {"status": "NO_CONFLUENCE"}

    adj: dict[str, set] = {n: set() for n in levels}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)

    visited: set = set()
    components: list[set] = []
    for n in levels:
        if n in visited or not adj[n]:
            continue
        stack, comp = [n], set()
        while stack:
            cur = stack.pop()
            if cur in comp:
                continue
            comp.add(cur)
            visited.add(cur)
            stack.extend(adj[cur] - comp)
        components.append(comp)

    if len(components) > 1:
        best = None
        for comp in components:
            members = sorted(comp)
            price = float(np.mean([levels[m] for m in members]))
            if not pd.isna(prev_close_raw) and price <= prev_close_raw and (best is None or price > best[0]):
                best = (price, members)
        if best is None:
            zone_price, members = max(
                ((float(np.mean([levels[m] for m in sorted(c)])), sorted(c)) for c in components),
                key=lambda t: t[0],
            )
        else:
            zone_price, members = best
        return {"status": "CONFLUENCE", "members": tuple(members), "zone_price": zone_price, "multi_cluster": True}

    members = sorted(components[0])
    zone_price = float(np.mean([levels[m] for m in members]))
    return {"status": "CONFLUENCE", "members": tuple(members), "zone_price": zone_price, "multi_cluster": False}


# ---------------------------------------------------------------------
# Entry (Section 3) -- sweep/reclaim are poc.v4's own, unchanged, called
# against the confluence zone's own price instead of V4's lookback_low
# ---------------------------------------------------------------------

def find_entry_a(candles5: pd.DataFrame, bars1: pd.DataFrame, zone_price: float, atr_raw: float) -> dict:
    sweep = find_sweep(candles5, zone_price, atr_raw)
    if sweep["status"] != "SWEEP":
        return {"status": sweep["status"]}

    sweep_idx, sweep_low_at_detection = sweep["idx"], sweep["sweep_low"]
    sweep_depth_atr = (zone_price - sweep_low_at_detection) / atr_raw

    reclaim = find_reclaim(candles5, sweep_idx, sweep_low_at_detection, zone_price)
    if reclaim["status"] == "NOT_RECLAIMED":
        return {
            "status": "NOT_RECLAIMED", "sweep_idx": sweep_idx, "sweep_depth_atr": sweep_depth_atr,
            "new_low_during_reclaim": reclaim["new_low_seen"],
        }

    reclaim_idx, final_sweep_low = reclaim["idx"], reclaim["sweep_low"]
    new_low_during_reclaim = final_sweep_low < sweep_low_at_detection
    common = {
        "sweep_idx": sweep_idx, "reclaim_idx": reclaim_idx, "sweep_depth_atr": sweep_depth_atr,
        "new_low_during_reclaim": new_low_during_reclaim,
    }

    reclaim_candle = candles5.iloc[reclaim_idx]
    reclaim_close_ts = reclaim_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, reclaim_close_ts)
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", **common}

    fill_ts = pd.Timestamp(fill_bar["ts"])
    fill_time = fill_ts.time()
    if not (ENTRY_WINDOW_START <= fill_time <= ENTRY_WINDOW_END):
        return {"status": "FILL_OUTSIDE_WINDOW", "fill_ts": fill_ts, **common}

    entry_price = float(fill_bar["open"])
    stop_price = final_sweep_low - STOP_BUFFER_ATR * atr_raw
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


# ---------------------------------------------------------------------
# Scaled exit resolution (Section 4) -- composed from two calls to the
# reused poc.resolution._stop_target_event, never a new tie-break
# ---------------------------------------------------------------------

def _time_exit_candle(candles5: pd.DataFrame, fill_ts: pd.Timestamp) -> tuple[float, pd.Timestamp, bool]:
    """Mirrors poc.resolution.resolve_exit's own TIME_EXIT branch
    exactly (duplicated, not imported, since that function always also
    runs the 2-level stop/target scan first -- this helper is called
    standalone from two different places in resolve_scaled_exit_a)."""
    day_start = candles5["ts"].iloc[0].normalize()
    time_exit_ts = np.datetime64(day_start + pd.Timedelta(hours=15, minutes=15))
    ts_arr = candles5["ts"].to_numpy()
    rows = np.flatnonzero(ts_arr == time_exit_ts)
    if len(rows) > 0:
        row_idx = int(rows[0])
        used_fallback = False
    else:
        before = np.flatnonzero(ts_arr <= time_exit_ts)
        if len(before) == 0:
            raise ValueError("no candle at or before 15:15 for this day -- cannot resolve a time exit")
        row_idx = int(before[-1])
        used_fallback = True
    row = candles5.iloc[row_idx]
    return float(row["close"]), row["ts"] + pd.Timedelta(minutes=5), used_fallback


def resolve_scaled_exit_a(
    bars1: pd.DataFrame, candles5: pd.DataFrame, fill_ts: pd.Timestamp, entry_price: float,
    stop_price: float, half_target_price: float, full_target_price: float, qty: int,
) -> dict:
    """Returns {"outcome": str, "qty1_path": bool, "half_exit_happened":
    bool, "legs": [{"qty","price","ts","kind"}, ...], "time_exit_
    fallback": bool}. `legs` has 1 entry for the qty==1 path or a full
    STOP/no-half resolution, 2 entries once a half exit has happened."""
    if qty == 1:
        res = resolve_exit(bars1, candles5, fill_ts, entry_price, stop_price, full_target_price)
        outcome_map = {"STOP": "STOP_QTY1", "TARGET": "TARGET_QTY1", "TIME_EXIT": "TIME_EXIT_QTY1"}
        return {
            "outcome": outcome_map[res["outcome"]], "qty1_path": True, "half_exit_happened": False,
            "legs": [{"qty": qty, "price": res["exit_price"], "ts": res["exit_ts"], "kind": res["outcome"]}],
            "time_exit_fallback": res["time_exit_fallback"],
        }

    half_qty = qty // 2
    remainder_qty = qty - half_qty

    outcome1, bar1 = _stop_target_event(bars1, fill_ts, stop_price, half_target_price)
    if outcome1 is None:
        price, ts, fallback = _time_exit_candle(candles5, fill_ts)
        return {
            "outcome": "TIME_EXIT_FULL", "qty1_path": False, "half_exit_happened": False,
            "legs": [{"qty": qty, "price": price, "ts": ts, "kind": "TIME_EXIT"}],
            "time_exit_fallback": fallback,
        }
    if outcome1 == "STOP":
        exit_price = float(bar1["open"]) if bar1["open"] <= stop_price else stop_price
        return {
            "outcome": "STOP_NO_HALF", "qty1_path": False, "half_exit_happened": False,
            "legs": [{"qty": qty, "price": exit_price, "ts": pd.Timestamp(bar1["ts"]), "kind": "STOP"}],
            "time_exit_fallback": False,
        }

    # outcome1 == "TARGET" -- half-target hit, half exit executes here
    half_leg = {
        "qty": half_qty, "price": half_target_price, "ts": pd.Timestamp(bar1["ts"]), "kind": "HALF_TARGET",
    }
    outcome2, bar2 = _stop_target_event(bars1, pd.Timestamp(bar1["ts"]), stop_price, full_target_price)
    if outcome2 is None:
        price, ts, fallback = _time_exit_candle(candles5, fill_ts)
        return {
            "outcome": "HALF_THEN_TIME_EXIT", "qty1_path": False, "half_exit_happened": True,
            "legs": [half_leg, {"qty": remainder_qty, "price": price, "ts": ts, "kind": "TIME_EXIT"}],
            "time_exit_fallback": fallback,
        }
    if outcome2 == "STOP":
        exit_price = float(bar2["open"]) if bar2["open"] <= stop_price else stop_price
        return {
            "outcome": "HALF_THEN_STOP", "qty1_path": False, "half_exit_happened": True,
            "legs": [
                half_leg,
                {"qty": remainder_qty, "price": exit_price, "ts": pd.Timestamp(bar2["ts"]), "kind": "STOP"},
            ],
            "time_exit_fallback": False,
        }

    same_bar = bool(pd.Timestamp(bar2["ts"]) == pd.Timestamp(bar1["ts"]))
    return {
        "outcome": "FULL_EXIT_SAME_BAR" if same_bar else "FULL_EXIT", "qty1_path": False,
        "half_exit_happened": True,
        "legs": [
            half_leg,
            {"qty": remainder_qty, "price": full_target_price, "ts": pd.Timestamp(bar2["ts"]), "kind": "FULL_TARGET"},
        ],
        "time_exit_fallback": False,
    }


# ---------------------------------------------------------------------
# Costs (Section 6) -- per-leg three-order model, plus the hypothetical
# single-exit-at-3R comparison figure
# ---------------------------------------------------------------------

def _leg_cost_rs(trade_value_rs: float, band: str, is_buy: bool) -> float:
    half_spread_bps = BAND_SPREAD_BPS.get(band, 7.0) / 2.0
    fixed = buy_leg_cost_rs(trade_value_rs, "INTRADAY") if is_buy else sell_leg_cost_rs(trade_value_rs, "INTRADAY")
    spread = trade_value_rs * half_spread_bps / 10_000
    return fixed + spread


def three_order_cost_rs(entry_price: float, qty: int, legs: list[dict], band: str) -> float:
    entry_value_rs = qty * entry_price
    total = _leg_cost_rs(entry_value_rs, band, is_buy=True)
    for leg in legs:
        total += _leg_cost_rs(leg["qty"] * leg["price"], band, is_buy=False)
    return total


def hypothetical_single_exit_cost_rs(entry_price: float, qty: int, band: str) -> float:
    """What this exact trade would have cost under the POC family's own
    existing two-order round-trip convention (box_theory.costs.round_
    trip_cost_rs, unchanged) -- the Section 11 comparison figure."""
    return hypothetical_round_trip_cost_rs(qty * entry_price, band)


# ---------------------------------------------------------------------
# Backtest orchestration (Section 7)
# ---------------------------------------------------------------------

def evaluate_entity_a(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict,
) -> dict:
    trades: list[dict] = []
    skips = {r: 0 for r in SKIP_REASONS}
    sweep_depths_atr: list[float] = []
    new_low_during_reclaim_count = 0
    reached_reclaim_count = 0
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

            entry = find_entry_a(today_candles5, today_day_raw, zone["zone_price"], atr_raw)
            status = entry["status"]
            if "sweep_depth_atr" in entry:
                sweep_depths_atr.append(entry["sweep_depth_atr"])
            if status not in ("NO_SWEEP", "TOUCH_TOO_SHALLOW", "BREAKDOWN_NOT_SWEEP"):
                reached_reclaim_count += 1
                if entry.get("new_low_during_reclaim"):
                    new_low_during_reclaim_count += 1

            if status == "NO_SWEEP":
                skips["no_sweep"] += 1
                continue
            if status != "ENTERED":
                skips[_ENTRY_STATUS_TO_SKIP[status]] += 1
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

            trades.append({
                "entity_id": entity_id, "trade_date": day, "year": year_of_day,
                "band": band, "rank": rank,
                "confluence_members": zone["members"], "zone_price": zone["zone_price"],
                "multi_cluster": zone["multi_cluster"],
                "sweep_idx": entry["sweep_idx"], "reclaim_idx": entry["reclaim_idx"],
                "sweep_depth_atr": entry["sweep_depth_atr"],
                "new_low_during_reclaim": entry["new_low_during_reclaim"],
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
            })

    return {
        "trades": trades, "skips": skips, "errors": errors,
        "sweep_depths_atr": sweep_depths_atr, "new_low_during_reclaim_count": new_low_during_reclaim_count,
        "reached_reclaim_count": reached_reclaim_count,
    }


def run_backtest_a(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    start: dt.date, end: dt.date, entity_ids: list[str] | None = None,
) -> dict:
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
            "trades": pd.DataFrame(), "skips": {r: 0 for r in SKIP_REASONS}, "errors": [],
            "sweep_depths_atr": [], "new_low_during_reclaim_count": 0, "reached_reclaim_count": 0,
            "universe": universe,
        }
    candidates = restrict_to_universe(candidates, universe)
    entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    all_trades: list[dict] = []
    total_skips = {r: 0 for r in SKIP_REASONS}
    all_sweep_depths: list[float] = []
    total_new_low = 0
    total_reached_reclaim = 0
    all_errors: list[dict] = []

    for entity_id, years in entity_years.items():
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_entity_a(intraday_con, warehouse_con, entity_id, years, start, end, jump_dates, rank_lookup)
        all_trades.extend(result["trades"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        all_sweep_depths.extend(result["sweep_depths_atr"])
        total_new_low += result["new_low_during_reclaim_count"]
        total_reached_reclaim += result["reached_reclaim_count"]
        all_errors.extend(result["errors"])

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label="liquidity study A trade list")

    return {
        "trades": trades_df, "skips": total_skips, "errors": all_errors,
        "sweep_depths_atr": all_sweep_depths, "new_low_during_reclaim_count": total_new_low,
        "reached_reclaim_count": total_reached_reclaim, "universe": universe,
    }


# ---------------------------------------------------------------------
# TIMING null (Section 9)
# ---------------------------------------------------------------------

def build_timing_pool_a(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    trades: pd.DataFrame, rank_lookup: dict, jump_dates_by_entity: dict,
) -> list[dict]:
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
                continue  # should not happen (day was tradeable for real); defensive only
            stop_distance_rs = float(row["entry_price"]) - float(row["stop_price"])
            pool.append({
                "candles5": dctx["candles5"], "day_raw": dctx["day_raw"],
                "valid_idx": _valid_entry_idx(dctx["candles5"]),
                "stop_distance_rs": stop_distance_rs, "band": row["band"],
            })
    return pool


def _timing_draw_a(ctx: dict, rng: np.random.Generator) -> float | None:
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


def timing_null_seed_mean_a(pool: list[dict], rng: np.random.Generator) -> float:
    draws = [r for ctx in pool if (r := _timing_draw_a(ctx, rng)) is not None]
    return float(np.mean(draws)) if draws else float("nan")


# ---------------------------------------------------------------------
# SELECTION null (Section 9)
# ---------------------------------------------------------------------

def _get_or_build_entity_setup_a(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, jump_dates: set,
    full_start: dt.date, full_end: dt.date, setup_cache: dict,
) -> dict:
    """Memoized {"bhav","ex_dates","level_lookup","atr_adjusted_lookup",
    "factor_lookup"} for one entity across the WHOLE SELECTION-null run,
    not per month -- same performance lesson poc.nulls.get_or_build_
    entity_setup's own docstring already documents (OPERATIONS.md): these
    five artifacts are all O(entity's daily history), cheap to hold for
    every universe entity at once; rebuilding them per (entity, month)
    was measured there at 45-100s/month for just 15 entities."""
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


def build_month_pool_a(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    universe: pd.DataFrame, year: int, month: int, rank_lookup: dict, jump_dates_by_entity: dict,
    entity_setup_cache: dict, full_start: dt.date, full_end: dt.date,
) -> list[dict]:
    """Every (entity, day) for every universe member of `year`, restricted
    to calendar `month`, that passes single-day eligibility AND has
    sufficient level history AND has ATR available -- matching the real
    backtest's own gates BEFORE the confluence/sweep/reclaim checks, per
    this lineage's own SELECTION-null population principle."""
    month_start = dt.date(year, month, 1)
    month_end = (dt.date(year, month, 1) + pd.offsets.MonthEnd(0)).date()
    members = universe.loc[universe["year"] == year, "entity_id"].tolist()

    pool = []
    for entity_id in members:
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        setup = _get_or_build_entity_setup_a(
            warehouse_con, entity_id, jump_dates, full_start, full_end, entity_setup_cache,
        )
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
            if lv is None or pd.isna(lv["lo_3m"]) or factor_today is None:
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


def _selection_draw_a(ctx: dict, sampled_pct: float, rng: np.random.Generator) -> float | None:
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


def selection_null_seed_mean_a(
    month_pool: list[dict], count: int, rng: np.random.Generator, rho_pool: np.ndarray,
) -> list[float]:
    """`rho_pool` = the real strategy's own pooled `stop_distance_pct`
    values -- the original V1 convention (a sampled PERCENTAGE, not a
    deterministic per-day level), since Study A's stop is not anchored
    to a single deterministic day-level the way V2-V5's lookback-low
    stop is."""
    if not month_pool:
        return []
    draws = []
    n = len(month_pool)
    for _ in range(count):
        ctx = month_pool[int(rng.integers(0, n))]
        sampled_pct = float(rho_pool[int(rng.integers(0, len(rho_pool)))])
        r = _selection_draw_a(ctx, sampled_pct, rng)
        if r is not None:
            draws.append(r)
    return draws


# ---------------------------------------------------------------------
# Study A's own sealed TEST window -- own object, own log, shares
# nothing with any POC-family or box-theory guard
# ---------------------------------------------------------------------

SEALED_AT = dt.date(2026, 10, 30)

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 18)

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "liquidity" / "a" / "test_window_access_log.txt"


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside Study A's own sealed test window."""


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
            f"requested range end {end} intersects Study A's own sealed test window "
            f"(>= {TEST_START}). This is disallowed by default. If this really is the "
            f"one authorized end-of-study test evaluation, pass authorize_test=True "
            f"explicitly -- and only there."
        )
