"""PREREGISTRATION_POC_V5.md: POC family V5, multi-day hold.

ALL new logic for V5 lives in this one file, per instruction. V1-V4's
own files are imported and reused READ-ONLY -- never modified, so none
of their closed results can be touched by anything in this module.

V5 is V4 with the holding period changed, nothing else: entry (sweep +
reclaim) and stop (sweep_low - 0.1x ATR) are byte-unchanged from V4,
reused via `poc.v4.find_sweep`/`find_reclaim`. Target changes (forced,
not tuned) to 3x initial risk from entry, since V4's intraday
2%-below-PREV_HIGH target would resolve almost immediately over a
10-day hold. Resolution is new: 1-minute bars on the entry day (reusing
`poc.resolution._stop_target_event` unchanged), daily bars with
gap-aware stop/target checks for up to 10 further trading days, time
limit at the 10th day's own close. Costs are DELIVERY (`src.swing.
costs`), not intraday.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from box_theory.context import group_by_day
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.backtest import _build_trend_lookup_for_entity, _entity_years, build_universe
from poc.context import build_poc_context, lookback_dates
from poc.resolution import (
    ENTRY_WINDOW_END, ENTRY_WINDOW_START, MAX_RISK_PCT, _stop_target_event, fill_bar_after_candle_close,
)
from poc.v2 import CAPITAL_RS, MIN_RISK_PCT, compute_lookback_low, position_size_shares_v2
from poc.v4 import (
    STOP_BUFFER_ATR, _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity,
    find_reclaim, find_sweep,
)

from swing.costs import round_trip_cost_rs as delivery_round_trip_cost_rs

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.price_scale import to_raw_scale
from fibo.universe import assert_universe_membership, restrict_to_universe

# ---------------------------------------------------------------------
# V5's own frozen parameters (prereg's own stated reasoning)
# ---------------------------------------------------------------------

TARGET_RISK_MULTIPLE = 3.0  # entry + 3 x (entry - stop) -- FORCED change, not tuned, see prereg
HOLD_MAX_TRADING_DAYS_AFTER_ENTRY = 10
SUBSEQUENT_FETCH_CALENDAR_BUFFER_DAYS = 30  # comfortably covers 10 trading days incl. weekends/holidays

SKIP_REASONS = (
    "lookback_incomplete", "trend_filter_failed", "atr_unavailable",
    "no_sweep", "touch_too_shallow", "breakdown_not_sweep", "not_reclaimed",
    "no_fill_bar", "fill_outside_window", "entry_below_stop", "stop_too_wide", "stop_too_tight", "no_room",
)
# DEV_BOUNDARY_TRUNCATED is a real outcome, not a skip -- a trade DID enter; it is
# EXCLUDED from the gate's own population and reported separately (prereg Section 9).


# ---------------------------------------------------------------------
# Entry (prereg Section 5) -- identical to poc.v4.find_entry_v4 except
# the target formula (and NO_ROOM, which the new formula makes
# structurally unreachable, kept for symmetry/documentation only)
# ---------------------------------------------------------------------

def find_entry_v5(candles5: pd.DataFrame, bars1: pd.DataFrame, lookback_low: float, atr_raw: float) -> dict:
    """Same shape as `poc.v4.find_entry_v4`. No `prev_high` argument --
    V5's target no longer depends on it at all (see prereg's own Target
    section)."""
    sweep = find_sweep(candles5, lookback_low, atr_raw)
    if sweep["status"] != "SWEEP":
        return {"status": sweep["status"]}

    sweep_idx, sweep_low_at_detection = sweep["idx"], sweep["sweep_low"]
    sweep_depth_atr = (lookback_low - sweep_low_at_detection) / atr_raw

    reclaim = find_reclaim(candles5, sweep_idx, sweep_low_at_detection, lookback_low)
    if reclaim["status"] == "NOT_RECLAIMED":
        return {
            "status": "NOT_RECLAIMED", "sweep_idx": sweep_idx, "sweep_depth_atr": sweep_depth_atr,
            "new_low_during_reclaim": reclaim["new_low_seen"],
        }

    reclaim_idx, final_sweep_low = reclaim["idx"], reclaim["sweep_low"]
    new_low_during_reclaim = final_sweep_low < sweep_low_at_detection

    reclaim_candle = candles5.iloc[reclaim_idx]
    reclaim_close_ts = reclaim_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, reclaim_close_ts)
    if fill_bar is None:
        return {
            "status": "NO_FILL_BAR", "sweep_idx": sweep_idx, "reclaim_idx": reclaim_idx,
            "sweep_depth_atr": sweep_depth_atr, "new_low_during_reclaim": new_low_during_reclaim,
        }

    fill_ts = pd.Timestamp(fill_bar["ts"])
    fill_time = fill_ts.time()
    if not (ENTRY_WINDOW_START <= fill_time <= ENTRY_WINDOW_END):
        return {
            "status": "FILL_OUTSIDE_WINDOW", "sweep_idx": sweep_idx, "reclaim_idx": reclaim_idx,
            "fill_ts": fill_ts, "sweep_depth_atr": sweep_depth_atr,
            "new_low_during_reclaim": new_low_during_reclaim,
        }

    entry_price = float(fill_bar["open"])
    stop_price = final_sweep_low - STOP_BUFFER_ATR * atr_raw  # unchanged from V4

    common = {
        "sweep_idx": sweep_idx, "reclaim_idx": reclaim_idx, "fill_ts": fill_ts,
        "entry_price": entry_price, "stop_price": stop_price,
        "sweep_depth_atr": sweep_depth_atr, "new_low_during_reclaim": new_low_during_reclaim,
    }

    if entry_price <= stop_price:
        return {"status": "ENTRY_BELOW_STOP", **common}
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT:
        return {"status": "STOP_TOO_WIDE", **common}
    if risk_pct < MIN_RISK_PCT:
        return {"status": "STOP_TOO_TIGHT", **common}

    target_price = entry_price + TARGET_RISK_MULTIPLE * (entry_price - stop_price)  # CHANGED, forced
    if target_price <= entry_price:  # structurally unreachable -- kept for symmetry, see prereg
        return {"status": "NO_ROOM", "target_price": target_price, **common}

    qty = position_size_shares_v2(entry_price)

    return {"status": "ENTERED", "confirm_kind": "RECLAIM", "target_price": target_price, "qty": qty, **common}


# ---------------------------------------------------------------------
# Resolution (prereg Section 6) -- the overnight mechanics
# ---------------------------------------------------------------------

def _fetch_daily_ohlc_with_open(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, start: dt.date, end: dt.date,
) -> pd.DataFrame:
    """[trade_date (index), open, high, low, close] -- RAW scale, this
    entity's full EQ-series daily history in [start, end]. A new,
    V5-local query (not an edit to `box_theory.universe_data.
    fetch_bhav_daily`, which returns high/low/close only, no open --
    see prereg's own Overnight Mechanics section for why a new function,
    not a shared-module change, was the right call here)."""
    df = warehouse_con.execute(
        """SELECT p.trade_date, p.open, p.high, p.low, p.close
           FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
           WHERE l.entity_id = ? AND p.series = 'EQ' AND p.trade_date BETWEEN ? AND ?
           ORDER BY p.trade_date""",
        [entity_id, start, end],
    ).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df.set_index("trade_date")


def fetch_subsequent_daily_bars(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, entry_date: dt.date, dev_end: dt.date,
) -> pd.DataFrame:
    """This entity's own next trading days strictly after `entry_date`,
    up through `dev_end` -- NEVER past it, enforced at the SQL level
    (the `end` bound passed to `_fetch_daily_ohlc_with_open` is
    `min(entry_date + buffer, dev_end)`, so a sealed-TEST-window row is
    never fetched at all, regardless of what the resolution does with
    the result). Trimmed to at most `HOLD_MAX_TRADING_DAYS_AFTER_ENTRY`
    rows -- more than enough is fetched, never used."""
    fetch_end = min(entry_date + dt.timedelta(days=SUBSEQUENT_FETCH_CALENDAR_BUFFER_DAYS), dev_end)
    start = entry_date + dt.timedelta(days=1)
    if start > fetch_end:
        return pd.DataFrame(columns=["open", "high", "low", "close"])
    df = _fetch_daily_ohlc_with_open(warehouse_con, entity_id, start, fetch_end)
    return df.head(HOLD_MAX_TRADING_DAYS_AFTER_ENTRY)


def resolve_multiday_exit_from_bars(
    bars1_entry: pd.DataFrame, fill_ts: pd.Timestamp, entry_price: float, stop_price: float,
    target_price: float, subsequent_daily_bars: pd.DataFrame,
) -> dict:
    """Pure (no DB access). `bars1_entry`: entry day's own 1-minute RAW
    bars. `subsequent_daily_bars`: this entity's own next trading days
    strictly after entry, ALREADY scoped to <= DEV_END by the caller
    (`fetch_subsequent_daily_bars`) -- at most `HOLD_MAX_TRADING_DAYS_
    AFTER_ENTRY` rows, fewer if the entity's own archive or the DEV
    window itself ends first (both produce `DEV_BOUNDARY_TRUNCATED`
    here, undistinguished -- see prereg's own amendment note for why).

    Returns {"outcome": "STOP"|"TARGET"|"TIME_LIMIT"|"DEV_BOUNDARY_
    TRUNCATED", "exit_price": float, "exit_date": date, "trading_days_
    held": int (entry day = 1), "gap_through": bool, "held_overnight":
    bool}."""
    outcome, bar = _stop_target_event(bars1_entry, fill_ts, stop_price, target_price)
    if outcome == "STOP":
        gap = bool(bar["open"] <= stop_price)
        exit_price = float(bar["open"]) if gap else stop_price
        return {
            "outcome": "STOP", "exit_price": exit_price, "exit_date": pd.Timestamp(bar["ts"]).date(),
            "trading_days_held": 1, "gap_through": gap, "held_overnight": False,
        }
    if outcome == "TARGET":
        return {
            "outcome": "TARGET", "exit_price": target_price, "exit_date": pd.Timestamp(bar["ts"]).date(),
            "trading_days_held": 1, "gap_through": False, "held_overnight": False,
        }

    days_checked = 0
    last_close_in_bounds = None
    last_date_in_bounds = None
    for day_date, row in subsequent_daily_bars.iterrows():
        days_checked += 1
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        last_close_in_bounds, last_date_in_bounds = c, day_date

        if l <= stop_price:  # STOP checked first -- wins a same-day hit, per instruction
            gap = o <= stop_price
            return {
                "outcome": "STOP", "exit_price": o if gap else stop_price, "exit_date": day_date,
                "trading_days_held": 1 + days_checked, "gap_through": gap, "held_overnight": True,
            }
        if h >= target_price:
            gap = o >= target_price
            return {
                "outcome": "TARGET", "exit_price": o if gap else target_price, "exit_date": day_date,
                "trading_days_held": 1 + days_checked, "gap_through": False, "held_overnight": True,
            }
        if days_checked >= HOLD_MAX_TRADING_DAYS_AFTER_ENTRY:
            return {
                "outcome": "TIME_LIMIT", "exit_price": c, "exit_date": day_date,
                "trading_days_held": 1 + days_checked, "gap_through": False, "held_overnight": True,
            }

    # fewer than HOLD_MAX_TRADING_DAYS_AFTER_ENTRY in-bounds rows existed at all
    if last_date_in_bounds is None:
        return {
            "outcome": "DEV_BOUNDARY_TRUNCATED", "exit_price": entry_price,
            "exit_date": pd.Timestamp(fill_ts).date(), "trading_days_held": 1,
            "gap_through": False, "held_overnight": False,
        }
    return {
        "outcome": "DEV_BOUNDARY_TRUNCATED", "exit_price": last_close_in_bounds,
        "exit_date": last_date_in_bounds, "trading_days_held": 1 + days_checked,
        "gap_through": False, "held_overnight": True,
    }


def resolve_multiday_exit(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, entry_date: dt.date, dev_end: dt.date,
    bars1_entry: pd.DataFrame, fill_ts: pd.Timestamp, entry_price: float, stop_price: float,
    target_price: float,
) -> dict:
    """Fetch-then-resolve convenience for the real backtest's own
    per-trade (non-repeated) resolution -- nulls use `fetch_subsequent_
    daily_bars` once per pooled entity-day and call `resolve_multiday_
    exit_from_bars` directly against the cached result instead (prereg's
    own stated performance reasoning)."""
    bars = fetch_subsequent_daily_bars(warehouse_con, entity_id, entry_date, dev_end)
    return resolve_multiday_exit_from_bars(bars1_entry, fill_ts, entry_price, stop_price, target_price, bars)


# ---------------------------------------------------------------------
# Costs (prereg Section 8) -- DELIVERY, a range; midpoint drives the gate
# ---------------------------------------------------------------------

def net_return_pct_range(pnl_rs: float, position_size_rs: float) -> dict:
    cost_lo, cost_hi = delivery_round_trip_cost_rs(position_size_rs, "DELIVERY")
    cost_mid = (cost_lo + cost_hi) / 2.0
    return {
        "cost_rs_lo": cost_lo, "cost_rs_hi": cost_hi, "cost_rs_mid": cost_mid,
        "net_return_pct": (pnl_rs - cost_mid) / position_size_rs,
        "net_return_pct_lo_cost": (pnl_rs - cost_hi) / position_size_rs,  # higher cost -> lower return
        "net_return_pct_hi_cost": (pnl_rs - cost_lo) / position_size_rs,  # lower cost -> higher return
    }


# ---------------------------------------------------------------------
# Backtest orchestration
# ---------------------------------------------------------------------

_ENTRY_STATUS_TO_SKIP = {
    "NO_SWEEP": "no_sweep", "TOUCH_TOO_SHALLOW": "touch_too_shallow",
    "BREAKDOWN_NOT_SWEEP": "breakdown_not_sweep", "NOT_RECLAIMED": "not_reclaimed",
    "NO_FILL_BAR": "no_fill_bar", "FILL_OUTSIDE_WINDOW": "fill_outside_window",
    "ENTRY_BELOW_STOP": "entry_below_stop", "STOP_TOO_WIDE": "stop_too_wide",
    "STOP_TOO_TIGHT": "stop_too_tight", "NO_ROOM": "no_room",
}


def evaluate_entity_v5(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict,
) -> dict:
    trades: list[dict] = []
    boundary_trades: list[dict] = []
    skips = {r: 0 for r in SKIP_REASONS}
    lookback_incomplete_detail: dict[tuple, int] = {}
    errors: list[dict] = []

    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(min(years) - 1, 1, 1), end)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    single_day_cache: dict[dt.date, pd.DataFrame] = {}
    eligible_ctx_cache: dict[dt.date, dict] = {}
    trend_lookup = _build_trend_lookup_for_entity(warehouse_con, entity_id, jump_dates)
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
        trade_dates = sorted(day_groups.keys())

        for day in trade_dates:
            ctx = build_poc_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup, trend_lookup, eligible_ctx_cache,
            )
            if ctx["skip"] == "LOOKBACK_INCOMPLETE":
                skips["lookback_incomplete"] += 1
                detail = ctx["detail"]
                key = (detail["failed_at"], detail["reason"])
                lookback_incomplete_detail[key] = lookback_incomplete_detail.get(key, 0) + 1
                continue

            lookback_low = compute_lookback_low(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup, eligible_ctx_cache,
            )

            if ctx["skip"] == "TREND_FILTER_FAILED":
                skips["trend_filter_failed"] += 1
                continue

            l5 = lookback_dates(day)["L5"]
            atr_adjusted = atr_adjusted_lookup.get(l5)
            factor_today = factor_lookup.get(day)
            if atr_adjusted is None or pd.isna(atr_adjusted) or factor_today is None:
                skips["atr_unavailable"] += 1
                continue
            atr_raw = to_raw_scale(atr_adjusted, factor_today)

            today_day_raw, today_candles5 = ctx["today_day_raw"], ctx["today_candles5"]
            band, rank, year_of_day = ctx["band"], ctx["rank"], ctx["year"]

            entry = find_entry_v5(today_candles5, today_day_raw, lookback_low, atr_raw)
            status = entry["status"]
            if status != "ENTERED":
                skips[_ENTRY_STATUS_TO_SKIP[status]] += 1
                continue

            try:
                exit_res = resolve_multiday_exit(
                    warehouse_con, entity_id, day, end, today_day_raw, entry["fill_ts"],
                    entry["entry_price"], entry["stop_price"], entry["target_price"],
                )
            except Exception as e:
                errors.append({"entity_id": entity_id, "trade_date": day, "error": f"{type(e).__name__}: {e}"})
                continue

            qty = entry["qty"]
            entry_price = entry["entry_price"]
            stop_price = entry["stop_price"]
            exit_price = exit_res["exit_price"]
            pnl_rs = qty * (exit_price - entry_price)
            position_size_rs = qty * entry_price
            cost_info = net_return_pct_range(pnl_rs, position_size_rs)

            record = {
                "entity_id": entity_id, "trade_date": day, "year": year_of_day,
                "band": band, "rank": rank,
                "lookback_low": lookback_low, "atr_raw": atr_raw,
                "sweep_idx": entry["sweep_idx"], "reclaim_idx": entry["reclaim_idx"],
                "sweep_depth_atr": entry["sweep_depth_atr"],
                "new_low_during_reclaim": entry["new_low_during_reclaim"],
                "fill_ts": entry["fill_ts"],
                "entry_price": entry_price, "stop_price": stop_price,
                "target_price": entry["target_price"], "qty": qty,
                "outcome": exit_res["outcome"], "exit_date": exit_res["exit_date"],
                "exit_price": exit_price, "trading_days_held": exit_res["trading_days_held"],
                "gap_through": exit_res["gap_through"], "held_overnight": exit_res["held_overnight"],
                "position_size_rs": position_size_rs, "pnl_rs": pnl_rs,
                "gross_return_pct": pnl_rs / position_size_rs,
                "stop_distance_pct": (entry_price - stop_price) / entry_price,
                "entry_above_lookback_low_frac": (entry_price - lookback_low) / entry_price,
                **cost_info,
            }

            if exit_res["outcome"] == "DEV_BOUNDARY_TRUNCATED":
                boundary_trades.append(record)
            else:
                trades.append(record)

    return {
        "trades": trades, "boundary_trades": boundary_trades, "skips": skips,
        "lookback_incomplete_detail": lookback_incomplete_detail, "errors": errors,
    }


def run_backtest_v5(
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
        return {"trades": pd.DataFrame(), "boundary_trades": pd.DataFrame(), "skips": {r: 0 for r in SKIP_REASONS},
                "lookback_incomplete_detail": {}, "errors": [], "universe": universe}
    candidates = restrict_to_universe(candidates, universe)
    entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    all_trades: list[dict] = []
    all_boundary_trades: list[dict] = []
    total_skips = {r: 0 for r in SKIP_REASONS}
    total_lookback_detail: dict[tuple, int] = {}
    all_errors: list[dict] = []

    for entity_id, years in entity_years.items():
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_entity_v5(
            intraday_con, warehouse_con, entity_id, years, start, end, jump_dates, rank_lookup,
        )
        all_trades.extend(result["trades"])
        all_boundary_trades.extend(result["boundary_trades"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        for key, v in result["lookback_incomplete_detail"].items():
            total_lookback_detail[key] = total_lookback_detail.get(key, 0) + v
        all_errors.extend(result["errors"])

    trades_df = pd.DataFrame(all_trades)
    boundary_df = pd.DataFrame(all_boundary_trades)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label="poc v5 trade list")

    return {
        "trades": trades_df, "boundary_trades": boundary_df, "skips": total_skips,
        "lookback_incomplete_detail": total_lookback_detail, "errors": all_errors, "universe": universe,
    }


# ---------------------------------------------------------------------
# TIMING null -- same population as V2-V4's own (the real trades' own
# entry days), resolved via resolve_multiday_exit_from_bars with V5's
# own 3x-risk target. Subsequent-day bars fetched ONCE per pool entry.
# ---------------------------------------------------------------------

def _valid_entry_idx(candles5: pd.DataFrame) -> np.ndarray:
    times = candles5["ts"].dt.time
    return candles5.index[(times >= ENTRY_WINDOW_START) & (times <= ENTRY_WINDOW_END)].to_numpy()


def _random_fill(candles5: pd.DataFrame, day_raw: pd.DataFrame, rng: np.random.Generator,
                  valid_idx: np.ndarray) -> tuple[float | None, pd.Timestamp | None]:
    if len(valid_idx) == 0:
        return None, None
    idx = int(rng.choice(valid_idx))
    candle_close_ts = candles5.loc[idx, "ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(day_raw, candle_close_ts)
    if fill_bar is None:
        return None, None
    return float(fill_bar["open"]), pd.Timestamp(fill_bar["ts"])


def build_timing_pool_v5(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    trades: pd.DataFrame, rank_lookup: dict, jump_dates_by_entity: dict, dev_end: dt.date,
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
            from box_theory.context import eligible_day_context
            dctx = eligible_day_context(
                intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
                single_day_cache, rank_lookup,
            )
            if dctx["skip"] is not None:
                continue
            subsequent_bars = fetch_subsequent_daily_bars(warehouse_con, entity_id, day, dev_end)
            stop_distance = float(row["entry_price"]) - float(row["stop_price"])
            pool.append({
                "candles5": dctx["candles5"], "day_raw": dctx["day_raw"],
                "valid_idx": _valid_entry_idx(dctx["candles5"]),
                "stop_distance": stop_distance, "subsequent_bars": subsequent_bars,
            })
    return pool


def _timing_draw_v5(ctx: dict, rng: np.random.Generator) -> dict | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = entry_price - ctx["stop_distance"]
    if stop_price <= 0 or entry_price <= stop_price:
        return None
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT or risk_pct < MIN_RISK_PCT:
        return None
    target_price = entry_price + TARGET_RISK_MULTIPLE * (entry_price - stop_price)  # V5's own formula
    qty = position_size_shares_v2(entry_price)
    exit_res = resolve_multiday_exit_from_bars(
        ctx["day_raw"], fill_ts, entry_price, stop_price, target_price, ctx["subsequent_bars"],
    )
    if exit_res["outcome"] == "DEV_BOUNDARY_TRUNCATED":
        return None  # excluded from the gate, same as the real backtest's own trades
    pnl_rs = qty * (exit_res["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    return net_return_pct_range(pnl_rs, position_size_rs)


def timing_null_seed_mean_v5(pool: list[dict], rng: np.random.Generator) -> float:
    draws = [r["net_return_pct"] for ctx in pool if (r := _timing_draw_v5(ctx, rng)) is not None]
    return float(np.mean(draws)) if draws else float("nan")


# ---------------------------------------------------------------------
# SELECTION null -- same population as V2-V4's own (every eligible day,
# matched count per month), stop = that day's own LOOKBACK_LOW (V2's
# own established simplification for an arbitrary pooled day -- no real
# sweep occurred on it), target = V5's own 3x-risk formula.
# ---------------------------------------------------------------------

def build_month_pool_v5(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    universe: pd.DataFrame, year: int, month: int, rank_lookup: dict, jump_dates_by_entity: dict,
    entity_setup_cache: dict, full_start: dt.date, full_end: dt.date, dev_end: dt.date,
) -> list[dict]:
    from poc.nulls import get_or_build_entity_setup

    month_start = dt.date(year, month, 1)
    month_end = (dt.date(year, month, 1) + pd.offsets.MonthEnd(0)).date()
    members = universe.loc[universe["year"] == year, "entity_id"].tolist()

    pool = []
    for entity_id in members:
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        setup = get_or_build_entity_setup(warehouse_con, entity_id, jump_dates, full_start, full_end,
                                           entity_setup_cache)
        single_day_cache: dict = {}
        eligible_ctx_cache: dict = {}
        block = fetch_bars_range(intraday_con, entity_id, month_start, month_end)
        if block.empty:
            continue
        day_groups = group_by_day(block)
        for day in sorted(day_groups.keys()):
            ctx = build_poc_context(
                intraday_con, entity_id, day, day_groups, setup["bhav"], setup["ex_dates"], jump_dates,
                single_day_cache, rank_lookup, setup["trend_lookup"], eligible_ctx_cache,
            )
            if ctx["skip"] == "LOOKBACK_INCOMPLETE":
                continue
            lookback_low = compute_lookback_low(
                intraday_con, entity_id, day, day_groups, setup["bhav"], setup["ex_dates"], jump_dates,
                single_day_cache, rank_lookup, eligible_ctx_cache,
            )
            subsequent_bars = fetch_subsequent_daily_bars(warehouse_con, entity_id, day, dev_end)
            pool.append({
                "candles5": ctx["today_candles5"], "day_raw": ctx["today_day_raw"],
                "valid_idx": _valid_entry_idx(ctx["today_candles5"]),
                "lookback_low": lookback_low, "subsequent_bars": subsequent_bars,
            })
    return pool


def _selection_draw_v5(ctx: dict, rng: np.random.Generator) -> dict | None:
    entry_price, fill_ts = _random_fill(ctx["candles5"], ctx["day_raw"], rng, ctx["valid_idx"])
    if entry_price is None or entry_price <= 0:
        return None
    stop_price = ctx["lookback_low"]  # deterministic, the drawn day's own real lookback low (V2's convention)
    if entry_price <= stop_price:
        return None
    risk_pct = (entry_price - stop_price) / entry_price
    if risk_pct > MAX_RISK_PCT or risk_pct < MIN_RISK_PCT:
        return None
    target_price = entry_price + TARGET_RISK_MULTIPLE * (entry_price - stop_price)  # V5's own formula
    qty = position_size_shares_v2(entry_price)
    exit_res = resolve_multiday_exit_from_bars(
        ctx["day_raw"], fill_ts, entry_price, stop_price, target_price, ctx["subsequent_bars"],
    )
    if exit_res["outcome"] == "DEV_BOUNDARY_TRUNCATED":
        return None
    pnl_rs = qty * (exit_res["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    return net_return_pct_range(pnl_rs, position_size_rs)


def selection_null_seed_mean_v5(month_pool: list[dict], count: int, rng: np.random.Generator) -> list[float]:
    if not month_pool:
        return []
    draws = []
    n = len(month_pool)
    for _ in range(count):
        ctx = month_pool[int(rng.integers(0, n))]
        r = _selection_draw_v5(ctx, rng)
        if r is not None:
            draws.append(r["net_return_pct"])
    return draws


# ---------------------------------------------------------------------
# V5's own sealed TEST window -- own object, own log, shares nothing
# with any prior POC seal
# ---------------------------------------------------------------------

SEALED_AT = dt.date(2026, 10, 30)

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 18)

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "poc" / "v5" / "test_window_access_log.txt"


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside V5's own sealed test window."""


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
            f"requested range end {end} intersects POC V5's own sealed test window "
            f"(>= {TEST_START}). This is disallowed by default. If this really is the "
            f"one authorized end-of-study test evaluation, pass authorize_test=True "
            f"explicitly -- and only there."
        )
