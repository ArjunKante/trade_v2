"""Box Theory V2 (PREREGISTRATION_BOX_V2.md): strength-filtered
confirmation over V1's touch population. Only the entry signal changes
(Changes 1-3); the box, universe, stop, arming, exit, time-exit, and
cost logic are all reused READ-ONLY from this package's existing,
closed-V1 modules (`context.py`, `resolution.py`, `costs.py`,
`backtest.py`, `inference.py`, `nulls.py`, `test_seal.py`) -- nothing
in this file modifies them, and nothing they do changes by V2 existing.

`find_entry_v2` is the only new SIGNAL logic. `evaluate_entity_v2`/
`run_backtest_v2` are a thin orchestration layer, structurally identical
to `backtest.py`'s own `evaluate_entity`/`run_backtest` (same
eligibility loop via `context.eligible_day_context`, same cost
attribution, same bounded per-trade exception handling V1 added after
its own DEV run), just calling `find_entry_v2` instead of V1's
`find_entry` and always resolving the exit with `config="FAST"` --
V2 tests exactly one configuration, equivalent to V1's FAST exit style,
not a label of convenience: that string selects the single-red-candle
exit branch `resolve_exit` already implements.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import restrict_to_universe, assert_universe_membership

from box_theory.context import eligible_day_context, group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.resolution import (
    find_touch_idx, fill_bar_after_candle_close, position_size_shares,
    resolve_exit, ENTRY_WINDOW_START, ENTRY_WINDOW_END, FIXED_RISK_RS,
)
from box_theory.backtest import build_universe, _entity_years
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

EXIT_STYLE = "FAST"  # V2 tests exactly one configuration, equivalent to V1's FAST exit

ROOM_PCT_V2 = 0.05          # Change 3: replaces V1's 0.01 outright
RANGE_VOLUME_MULTIPLIER = 1.5  # Change 1: FIXED, not tuned (PREREGISTRATION_BOX_V2.md Section 3)
TRAILING_WINDOW_MAX = 8        # 8 candles ending at touch inclusive = trailing 40 minutes
TRAILING_WINDOW_MIN = 4        # below this, skip the day (insufficient_candles)
MAX_CANDIDATE_OFFSET = 2        # Change 2: only the 1st or 2nd candle after touch is ever checked

SKIP_REASONS = ("no_room", "bad_previous_session", "ex_date", "jump_guard", "insufficient_candles")
DIAGNOSTIC_REASONS = ("no_touch", "no_strong_candle", "no_fill_bar", "fill_outside_window", "zero_qty")


def _trailing_window(candles5: pd.DataFrame, touch_idx: int) -> pd.DataFrame | None:
    """The up-to-8 candles ending at touch_idx inclusive. None if fewer
    than TRAILING_WINDOW_MIN are available (PREREGISTRATION_BOX_V2.md
    Section 3, Change 1's "fewer than 8 prior candles" clause, read
    literally as a window that always ENDS at touch, never shrinking
    from the wrong end)."""
    available = touch_idx + 1
    if available < TRAILING_WINDOW_MIN:
        return None
    window_len = min(available, TRAILING_WINDOW_MAX)
    return candles5.iloc[touch_idx + 1 - window_len: touch_idx + 1]


def _is_strong_candle(candles5: pd.DataFrame, idx: int, mean_range: float, mean_volume: float) -> bool:
    """Change 1's three conditions, all required: green, range >=
    1.5x the trailing window's mean range, volume >= 1.5x the trailing
    window's mean volume. False (not an error) if idx runs past the
    end of the day's candles -- the caller just has no 2nd candidate
    that day."""
    if idx >= len(candles5):
        return False
    row = candles5.iloc[idx]
    if not bool(row["is_green"]):
        return False
    candle_range = float(row["high"] - row["low"])
    if candle_range < RANGE_VOLUME_MULTIPLIER * mean_range:
        return False
    if float(row["volume"]) < RANGE_VOLUME_MULTIPLIER * mean_volume:
        return False
    return True


def find_entry_v2(candles5: pd.DataFrame, bars1: pd.DataFrame, prev_high: float, prev_low: float) -> dict:
    """Touch (reused `find_touch_idx`) -> strength-filtered, two-candle-
    patience confirmation (Changes 1-2) -> fill (reused) -> 5% room
    (Change 3) -> sizing (reused). Returns a dict with at least
    {"status": ...}; status is one of "NO_TOUCH", "INSUFFICIENT_
    CANDLES", "NO_STRONG_CANDLE", "NO_FILL_BAR", "FILL_OUTSIDE_WINDOW",
    "NO_ROOM", "ZERO_QTY", "ENTERED". On "ENTERED": touch_idx,
    confirm_idx, which_candle (1 or 2), entry_candle_idx, fill_ts,
    entry_price, qty, room_at_entry (fraction, e.g. 0.052 for 5.2%)."""
    touch_idx = find_touch_idx(candles5, prev_low)
    if touch_idx is None:
        return {"status": "NO_TOUCH"}

    window = _trailing_window(candles5, touch_idx)
    if window is None:
        return {"status": "INSUFFICIENT_CANDLES", "touch_idx": touch_idx}

    mean_range = float((window["high"] - window["low"]).mean())
    mean_volume = float(window["volume"].mean())

    confirm_idx = None
    which_candle = None
    for offset in range(1, MAX_CANDIDATE_OFFSET + 1):
        candidate_idx = touch_idx + offset
        if _is_strong_candle(candles5, candidate_idx, mean_range, mean_volume):
            confirm_idx = candidate_idx
            which_candle = offset
            break

    if confirm_idx is None:
        return {"status": "NO_STRONG_CANDLE", "touch_idx": touch_idx}

    confirm_candle = candles5.iloc[confirm_idx]
    confirm_close_ts = confirm_candle["ts"] + pd.Timedelta(minutes=5)
    fill_bar = fill_bar_after_candle_close(bars1, confirm_close_ts)
    if fill_bar is None:
        return {"status": "NO_FILL_BAR", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
                "which_candle": which_candle}

    fill_ts = pd.Timestamp(fill_bar["ts"])
    fill_time = fill_ts.time()
    if not (ENTRY_WINDOW_START <= fill_time <= ENTRY_WINDOW_END):
        return {"status": "FILL_OUTSIDE_WINDOW", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
                "which_candle": which_candle, "fill_ts": fill_ts}

    entry_price = float(fill_bar["open"])
    room_at_entry = (prev_high - entry_price) / entry_price
    if room_at_entry < ROOM_PCT_V2:
        return {"status": "NO_ROOM", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
                "which_candle": which_candle, "fill_ts": fill_ts, "entry_price": entry_price,
                "room_at_entry": room_at_entry}

    qty = position_size_shares(entry_price)
    if qty < 1:
        return {"status": "ZERO_QTY", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
                "which_candle": which_candle, "fill_ts": fill_ts, "entry_price": entry_price,
                "room_at_entry": room_at_entry}

    return {
        "status": "ENTERED", "touch_idx": touch_idx, "confirm_idx": confirm_idx,
        "which_candle": which_candle, "entry_candle_idx": confirm_idx + 1, "fill_ts": fill_ts,
        "entry_price": entry_price, "qty": qty, "room_at_entry": room_at_entry,
    }


def evaluate_entity_v2(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, years: list[int], start: dt.date, end: dt.date,
    jump_dates: set, rank_lookup: dict,
) -> dict:
    """Runs every eligible day for one entity across `years`, V2's
    single configuration only. Returns {"trades": [...], "skips":
    {reason: count}, "diagnostics": {reason: count}, "errors": [...]}."""
    trades: list[dict] = []
    skips = {r: 0 for r in SKIP_REASONS}
    diagnostics = {r: 0 for r in DIAGNOSTIC_REASONS}
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

            entry = find_entry_v2(candles5, day_raw, prev_high, prev_low)
            status = entry["status"]
            if status == "NO_TOUCH":
                diagnostics["no_touch"] += 1
                continue
            if status == "INSUFFICIENT_CANDLES":
                skips["insufficient_candles"] += 1
                continue
            if status == "NO_STRONG_CANDLE":
                diagnostics["no_strong_candle"] += 1
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

            try:
                exit_res = resolve_exit(
                    candles5, day_raw, entry["entry_candle_idx"], entry["fill_ts"],
                    entry["entry_price"], prev_high, EXIT_STYLE,
                )
            except Exception as e:
                errors.append({
                    "entity_id": entity_id, "trade_date": day,
                    "error": f"{type(e).__name__}: {e}",
                })
                continue

            qty = entry["qty"]
            entry_price = entry["entry_price"]
            pnl_rs = qty * (exit_res["exit_price"] - entry_price)
            position_size_rs = qty * entry_price
            cost_rs = round_trip_cost_rs(position_size_rs, band)
            net_r = (pnl_rs - cost_rs) / FIXED_RISK_RS
            gross_r = pnl_rs / FIXED_RISK_RS

            trades.append({
                "entity_id": entity_id, "trade_date": day, "year": year_of_day,
                "band": band, "rank": rank, "prev_high": prev_high, "prev_low": prev_low,
                "touch_idx": entry["touch_idx"], "confirm_idx": entry["confirm_idx"],
                "which_candle": entry["which_candle"], "fill_ts": entry["fill_ts"],
                "entry_price": entry_price, "room_at_entry": entry["room_at_entry"], "qty": qty,
                "stop_price": entry_price * 0.97,
                "outcome": exit_res["outcome"], "armed": exit_res["armed"],
                "time_exit_fallback": exit_res["time_exit_fallback"],
                "exit_ts": exit_res["exit_ts"], "exit_price": exit_res["exit_price"],
                "position_size_rs": position_size_rs, "cost_rs": cost_rs,
                "pnl_rs": pnl_rs, "gross_r": gross_r, "net_r": net_r,
            })

    return {"trades": trades, "skips": skips, "diagnostics": diagnostics, "errors": errors}


def run_backtest_v2(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    start: dt.date, end: dt.date, entity_ids: list[str] | None = None,
) -> dict:
    """Top-level entry point, structurally identical to `backtest.
    run_backtest` -- does NOT itself call `test_seal.guard_date_range`;
    the caller script is responsible for that."""
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
        return {"trades": pd.DataFrame(), "skips": {r: 0 for r in SKIP_REASONS},
                "diagnostics": {r: 0 for r in DIAGNOSTIC_REASONS}, "errors": [], "universe": universe}
    candidates = restrict_to_universe(candidates, universe)
    entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    all_trades: list[dict] = []
    total_skips = {r: 0 for r in SKIP_REASONS}
    total_diag = {r: 0 for r in DIAGNOSTIC_REASONS}
    all_errors: list[dict] = []

    for entity_id, years in entity_years.items():
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_entity_v2(
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
        assert_universe_membership(check, universe, label="box_theory_v2 trade list")

    return {
        "trades": trades_df, "skips": total_skips, "diagnostics": total_diag,
        "errors": all_errors, "universe": universe,
    }
