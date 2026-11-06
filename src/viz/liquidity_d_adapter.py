"""Liquidity confluence Study D (ascending lows)-specific overlay
construction -- the Liquidity analogue of `viz.liquidity_a_adapter`/
`viz.liquidity_b_adapter`/`viz.liquidity_c_adapter`. Recomputes live via
`box_theory.context.eligible_day_context` + `liquidity.d`'s own pure
functions (`find_entry_d_long`/`find_entry_d_short`), the exact same
functions `src/liquidity/d.py`'s real DEV run used. `liquidity.a`,
`liquidity.b`, and `liquidity.d` are all CLOSED studies and are imported
read-only here, never modified.

**Only CONFIG 2LOW is wired here, hardcoded (`_N_REQUIRED = 2`).** CONFIG
3LOW's own DEV run was interrupted before any configuration finished and
was deliberately NOT resumed (LIQUIDITY_D_FINDINGS.md's own "Why 3LOW
was not run" section) -- there is no completed 3LOW result anywhere in
this project, so this module never offers it, and the browser must not
either.

Two entry points, one per side: `build_liquidity_d_long_overlay` and
`build_liquidity_d_short_overlay`. Shows all six levels, the confluence
zone, the sweep extreme (Study D has no reclaim step -- the sweep's own
detected extreme is both where the risk is defended AND where the
ascending-lows scan starts), EACH ascending low/high the pattern counted
on the way to confirmation (or to PATTERN_BROKEN/PATTERN_INCOMPLETE),
and entry/half/full/stop."""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from box_theory.context import eligible_day_context, group_by_day
from box_theory.holiday import previous_nse_trading_day
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.price_scale import to_raw_scale

from liquidity.a import _build_level_lookup_for_entity, find_confluence_zone, resolve_scaled_exit_a
from liquidity.b import find_confluence_zone_b, resolve_scaled_exit_b
from liquidity.d import find_entry_d_long, find_entry_d_short
from poc.v4 import _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity

from viz.overlay import Band, Level, Overlay, PriceMarker, VMarker

LOOKBACK_FETCH_BUFFER_DAYS = 25

_N_REQUIRED = 2  # CONFIG 2LOW only -- see module docstring; 3LOW was never run and is never offered

_LEVEL_STYLE_LONG = {
    "lo_3m": ("3M_LOW", "tab:purple", "dash"), "lo_1w": ("1W_LOW", "tab:pink", "dash"),
    "lo_1d": ("1D_LOW", "tab:gray", "dash"),
    "hi_3m": ("3M_HIGH", "tab:red", "dot"), "hi_1w": ("1W_HIGH", "tab:orange", "dot"),
    "hi_1d": ("1D_HIGH", "tab:brown", "dot"),
}
_LEVEL_STYLE_SHORT = {
    "hi_3m": ("3M_HIGH", "tab:red", "dash"), "hi_1w": ("1W_HIGH", "tab:orange", "dash"),
    "hi_1d": ("1D_HIGH", "tab:brown", "dash"),
    "lo_3m": ("3M_LOW", "tab:purple", "dot"), "lo_1w": ("1W_LOW", "tab:pink", "dot"),
    "lo_1d": ("1D_LOW", "tab:gray", "dot"),
}


def _scan_ascending_lows_events_long(candles5: pd.DataFrame, sweep_idx: int, sweep_low: float,
                                      zone_price: float, n_required: int) -> list[dict]:
    """Viz-only mirror of `liquidity.d.find_ascending_lows_long`'s own
    scan loop -- identical control flow, so it terminates at the exact
    same PATTERN_BROKEN/PATTERN_CONFIRMED/PATTERN_INCOMPLETE point the
    real (closed) function does. The only difference: this version also
    records each COUNTED local low along the way (its candle index,
    value, and whether it EXTENDED the running count or RESET it) so the
    overlay can mark each ascending low individually -- state the real
    function correctly never needed to return. Never used to decide
    anything; `find_entry_d_long`'s own PATTERN_* status is what the
    adapter trusts for the real verdict, this is display-only."""
    n = len(candles5)
    last_counted_low = None
    count = 0
    events: list[dict] = []
    for j in range(sweep_idx + 1, n):
        low_j = float(candles5.iloc[j]["low"])
        if low_j < sweep_low:
            return events
        candidate_idx = j - 1
        if candidate_idx >= sweep_idx + 1:
            low_before = float(candles5.iloc[candidate_idx - 1]["low"])
            low_candidate = float(candles5.iloc[candidate_idx]["low"])
            if low_candidate < low_before and low_candidate < low_j and low_candidate <= zone_price:
                if last_counted_low is not None and low_candidate > last_counted_low:
                    count += 1
                    action = "EXTEND"
                else:
                    count = 1
                    action = "RESET"
                last_counted_low = low_candidate
                events.append({
                    "confirm_idx": j, "candidate_idx": candidate_idx, "value": low_candidate,
                    "action": action, "count": count,
                })
                if count >= n_required:
                    return events
    return events


def _scan_ascending_highs_events_short(candles5: pd.DataFrame, sweep_idx: int, sweep_high: float,
                                        zone_price: float, n_required: int) -> list[dict]:
    """Mirror of `_scan_ascending_lows_events_long`: local highs, each
    qualifying high at/above the zone, each successive counted high
    STRICTLY LOWER than the last to EXTEND the count."""
    n = len(candles5)
    last_counted_high = None
    count = 0
    events: list[dict] = []
    for j in range(sweep_idx + 1, n):
        high_j = float(candles5.iloc[j]["high"])
        if high_j > sweep_high:
            return events
        candidate_idx = j - 1
        if candidate_idx >= sweep_idx + 1:
            high_before = float(candles5.iloc[candidate_idx - 1]["high"])
            high_candidate = float(candles5.iloc[candidate_idx]["high"])
            if high_candidate > high_before and high_candidate > high_j and high_candidate >= zone_price:
                if last_counted_high is not None and high_candidate < last_counted_high:
                    count += 1
                    action = "EXTEND"
                else:
                    count = 1
                    action = "RESET"
                last_counted_high = high_candidate
                events.append({
                    "confirm_idx": j, "candidate_idx": candidate_idx, "value": high_candidate,
                    "action": action, "count": count,
                })
                if count >= n_required:
                    return events
    return events


def _shared_day_setup(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date, jump_dates_by_entity: dict | None, rank_lookup: dict | None,
    level_key_for_nan_check: str,
) -> dict:
    """Identical shared setup to `viz.liquidity_c_adapter`'s own helper
    of the same name -- duplicated rather than imported, since each
    adapter module is meant to stand alone (the project's own existing
    convention: `viz.liquidity_a_adapter`/`viz.liquidity_b_adapter` never
    imported from each other either)."""
    fetch_start = trade_date - dt.timedelta(days=LOOKBACK_FETCH_BUFFER_DAYS)
    block = fetch_bars_range(intraday_con, entity_id, fetch_start, trade_date)
    if block.empty:
        return {"early_exit": {
            "bars": None, "overlay": None, "status": "NO_ARCHIVE_DATA",
            "detail": {"reason": f"no bars_1min rows for {entity_id} in [{fetch_start}, {trade_date}]"},
        }}
    day_groups = group_by_day(block)
    if trade_date not in day_groups:
        return {"early_exit": {
            "bars": None, "overlay": None, "status": "NO_ARCHIVE_DATA",
            "detail": {"reason": f"{entity_id} has no bars_1min rows on {trade_date} itself"},
        }}

    bhav = fetch_bhav_daily(warehouse_con, entity_id, dt.date(fetch_start.year - 1, 1, 1), trade_date)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    if jump_dates_by_entity is None:
        jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)
    jump_dates = jump_dates_by_entity.get(entity_id, set())

    if rank_lookup is None:
        from fibo.universe import effective_universe, reconstitute_annually
        from poc.backtest import STUB_YEAR, TOP_N
        universe = effective_universe(reconstitute_annually(warehouse_con, top_n=TOP_N), stub_year=STUB_YEAR)
        rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}

    single_day_cache: dict = {}
    dctx = eligible_day_context(
        intraday_con, entity_id, trade_date, day_groups, bhav, ex_dates, jump_dates,
        single_day_cache, rank_lookup,
    )
    if dctx["skip"] is not None:
        return {"early_exit": {
            "bars": day_groups.get(trade_date), "overlay": None, "status": dctx["skip"].upper(),
            "detail": {"reason": f"single-day eligibility failed: {dctx['skip']}"},
        }}

    level_lookup = _build_level_lookup_for_entity(warehouse_con, entity_id)
    atr_adjusted_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)

    lv = level_lookup.get(trade_date)
    factor_today = factor_lookup.get(trade_date)
    if lv is None or pd.isna(lv[level_key_for_nan_check]) or factor_today is None:
        return {"early_exit": {
            "bars": dctx["day_raw"], "overlay": None, "status": "LEVEL_INSUFFICIENT_HISTORY",
            "detail": {"reason": "fewer than 63 prior trading days of panel history for this entity-day"},
        }}

    prev_day = previous_nse_trading_day(trade_date)
    atr_adjusted = atr_adjusted_lookup.get(prev_day)
    if atr_adjusted is None or pd.isna(atr_adjusted):
        return {"early_exit": {
            "bars": dctx["day_raw"], "overlay": None, "status": "ATR_UNAVAILABLE",
            "detail": {"reason": f"ATR(14) unavailable for {prev_day}"},
        }}
    atr_raw = to_raw_scale(atr_adjusted, factor_today)

    return {"ctx": {"dctx": dctx, "lv": lv, "factor_today": factor_today, "atr_raw": atr_raw}}


def build_liquidity_d_long_overlay(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date,
    jump_dates_by_entity: dict | None = None, rank_lookup: dict | None = None,
) -> dict:
    """Same 4-key return shape as every other `src/viz/*_adapter.py`.
    LONG side, CONFIG 2LOW only (see module docstring)."""
    setup = _shared_day_setup(warehouse_con, intraday_con, entity_id, trade_date,
                               jump_dates_by_entity, rank_lookup, "lo_3m")
    if "early_exit" in setup:
        return setup["early_exit"]
    dctx, lv, factor_today, atr_raw = (setup["ctx"][k] for k in ("dctx", "lv", "factor_today", "atr_raw"))

    raw_levels = {k: to_raw_scale(lv[k], factor_today) for k in _LEVEL_STYLE_LONG}
    prev_close_raw = to_raw_scale(lv["prev_close"], factor_today) if not pd.isna(lv["prev_close"]) else float("nan")

    today_day_raw, today_candles5 = dctx["day_raw"], dctx["candles5"]
    band, rank = dctx["band"], dctx["rank"]

    overlay = Overlay()
    for key, (label, color, style) in _LEVEL_STYLE_LONG.items():
        overlay.levels.append(Level(raw_levels[key], label, color=color, linestyle=style))

    text_panel = [
        f"{entity_id}  {trade_date}  [Liquidity Study D: LONG, ascending lows, CONFIG 2LOW]",
        f"band={band} rank={rank}  ATR(14)_raw={atr_raw:.4f}",
    ]
    for key, (label, _c, _s) in _LEVEL_STYLE_LONG.items():
        text_panel.append(f"{label} = {raw_levels[key]:.4f}")

    detail: dict = {_LEVEL_STYLE_LONG[k][0]: raw_levels[k] for k in _LEVEL_STYLE_LONG}
    detail.update({"band": band, "rank": rank, "atr_raw": atr_raw})
    detail["daily_levels"] = [(lbl, raw_levels[k], color) for k, (lbl, color, _s) in _LEVEL_STYLE_LONG.items()]

    zone = find_confluence_zone(raw_levels["lo_3m"], raw_levels["lo_1w"], raw_levels["lo_1d"], atr_raw, prev_close_raw)
    if zone["status"] == "NO_CONFLUENCE":
        text_panel.append("status = NO_CONFLUENCE -- no two LOW levels within 0.5xATR of each other")
        overlay.text_panel = text_panel
        overlay.title_suffix = "SKIPPED (NO_CONFLUENCE)"
        return {"bars": today_day_raw, "overlay": overlay, "status": "NO_CONFLUENCE", "detail": detail}

    tol = 0.5 * atr_raw
    zone_members, zone_price = zone["members"], zone["zone_price"]
    zone_label = "+".join(zone_members)
    overlay.bands.append(Band(zone_price - tol, zone_price + tol, f"CONFLUENCE: {zone_label}",
                               color="gold", alpha=0.18))
    overlay.levels.append(Level(zone_price, f"ZONE({zone_label})", color="goldenrod", linestyle="dash"))
    text_panel.append(f"CONFLUENCE zone = {zone_label} -> {zone_price:.4f}  "
                       f"(tol=0.5xATR={tol:.4f}, multi_cluster={zone['multi_cluster']})")
    detail["confluence_zone_price"] = zone_price
    detail["confluence_members"] = zone_label
    detail["daily_zone"] = (zone_price - tol, zone_price + tol, f"ZONE({zone_label})")

    entry = find_entry_d_long(today_candles5, today_day_raw, zone_price, atr_raw, _N_REQUIRED)
    status = entry["status"]

    if "sweep_idx" in entry:
        sweep_idx, sweep_low = entry["sweep_idx"], entry["sweep_low"]
        sweep_candle = today_candles5.iloc[sweep_idx]
        overlay.vmarkers.append(VMarker(sweep_candle["ts"], "SWEEP_LOW", color="saddlebrown"))
        overlay.price_markers.append(
            PriceMarker(sweep_candle["ts"], sweep_low, "sweep", f"SWEEP_LOW {sweep_low:.2f}"))
        text_panel.append(f"SWEEP_LOW = {sweep_low:.4f} @ {sweep_candle['ts'].time()}  "
                           f"(depth={entry['sweep_depth_atr']:.4f}xATR)  -- no reclaim step in Study D, the "
                           f"ascending-lows scan starts on the very next candle")

        events = _scan_ascending_lows_events_long(today_candles5, sweep_idx, sweep_low, zone_price, _N_REQUIRED)
        for ev in events:
            candle = today_candles5.iloc[ev["candidate_idx"]]
            tag = f"ASC_LOW count={ev['count']} ({ev['action']})"
            color = "seagreen" if ev["action"] == "EXTEND" else "slategray"
            overlay.vmarkers.append(VMarker(candle["ts"], tag, color=color))
            overlay.price_markers.append(PriceMarker(candle["ts"], ev["value"], "sweep", tag))
            text_panel.append(f"{tag}: low={ev['value']:.4f} @ {candle['ts'].time()}")

    if status == "PATTERN_BROKEN":
        broken_candle = today_candles5.iloc[entry["broken_idx"]]
        overlay.vmarkers.append(VMarker(broken_candle["ts"], "PATTERN_BROKEN (new low beyond sweep)",
                                         color="firebrick"))
        text_panel.append(f"PATTERN_BROKEN @ {broken_candle['ts'].time()}: a new low broke below SWEEP_LOW")
    elif status == "PATTERN_INCOMPLETE":
        text_panel.append(f"PATTERN_INCOMPLETE: count never reached {_N_REQUIRED} "
                           f"(reached {entry.get('pattern_count', 0)}) before the window/day ended")

    is_real_entry = (status == "ENTERED")

    if "stop_price" in entry:
        overlay.levels.append(Level(entry["stop_price"], "STOP", color="crimson"))
        lo, hi = sorted((entry["stop_price"], zone_price))
        overlay.bands.append(Band(lo, hi, "risk zone", color="crimson", alpha=0.06))
    if "half_target_price" in entry:
        overlay.levels.append(Level(entry["half_target_price"], "HALF_TARGET (1.5R)", color="seagreen"))
    if "full_target_price" in entry:
        overlay.levels.append(Level(entry["full_target_price"], "FULL_TARGET (3.0R)", color="darkgreen"))

    if "fill_ts" in entry and "entry_price" in entry:
        kind_label = "ENTRY FILL" if is_real_entry else f"WOULD-BE FILL ({status})"
        marker_color = "blue" if is_real_entry else "gray"
        overlay.vmarkers.append(VMarker(entry["fill_ts"], kind_label, color=marker_color))
        pm_label = f"ENTRY {entry['entry_price']:.2f}" if is_real_entry else f"(rejected) {entry['entry_price']:.2f}"
        overlay.price_markers.append(PriceMarker(entry["fill_ts"], entry["entry_price"], "entry", pm_label))

    text_panel.append(f"status = {status}")

    if is_real_entry:
        qty = entry["qty"]
        exit_res = resolve_scaled_exit_a(
            today_day_raw, today_candles5, entry["fill_ts"], entry["entry_price"], entry["stop_price"],
            entry["half_target_price"], entry["full_target_price"], qty,
        )
        legs = exit_res["legs"]
        for i, leg in enumerate(legs):
            is_half = exit_res["half_exit_happened"] and i == 0 and len(legs) == 2
            if is_half:
                tag = "HALF_EXIT"
            elif exit_res["half_exit_happened"]:
                tag = "FULL_EXIT (remainder)"
            else:
                tag = "EXIT (full position)"
            vm_label = f"{tag} ({leg['kind']})"
            pm_label = f"{tag} ({leg['kind']}) {leg['price']:.2f}"
            overlay.vmarkers.append(VMarker(leg["ts"], vm_label, color="black"))
            overlay.price_markers.append(PriceMarker(leg["ts"], leg["price"], "exit", pm_label))

        entry_price = entry["entry_price"]
        pnl_rs = sum(leg["qty"] * (leg["price"] - entry_price) for leg in legs)
        position_size_rs = qty * entry_price
        text_panel += [
            f"entry = {entry_price:.4f} @ {entry['fill_ts'].time()}", f"stop  = {entry['stop_price']:.4f}",
            f"qty   = {qty}  half_qty={entry['half_qty']}", f"outcome = {exit_res['outcome']}",
            f"pnl_rs (gross) = {pnl_rs:.2f}  position_size_rs = {position_size_rs:,.2f}",
        ]
        overlay.title_suffix = f"ENTERED -> {exit_res['outcome']}"
    else:
        overlay.title_suffix = f"SKIPPED ({status})"

    overlay.text_panel = text_panel
    return {"bars": today_day_raw, "overlay": overlay, "status": status, "detail": detail}


def build_liquidity_d_short_overlay(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date,
    jump_dates_by_entity: dict | None = None, rank_lookup: dict | None = None,
) -> dict:
    """SHORT side, CONFIG 2LOW only -- direction-aware exactly like
    `viz.liquidity_b_adapter`/`viz.liquidity_c_adapter`'s own short
    entry points."""
    setup = _shared_day_setup(warehouse_con, intraday_con, entity_id, trade_date,
                               jump_dates_by_entity, rank_lookup, "hi_3m")
    if "early_exit" in setup:
        return setup["early_exit"]
    dctx, lv, factor_today, atr_raw = (setup["ctx"][k] for k in ("dctx", "lv", "factor_today", "atr_raw"))

    raw_levels = {k: to_raw_scale(lv[k], factor_today) for k in _LEVEL_STYLE_SHORT}
    prev_close_raw = to_raw_scale(lv["prev_close"], factor_today) if not pd.isna(lv["prev_close"]) else float("nan")

    today_day_raw, today_candles5 = dctx["day_raw"], dctx["candles5"]
    band, rank = dctx["band"], dctx["rank"]

    overlay = Overlay()
    for key, (label, color, style) in _LEVEL_STYLE_SHORT.items():
        overlay.levels.append(Level(raw_levels[key], label, color=color, linestyle=style))

    text_panel = [
        f"{entity_id}  {trade_date}  [SHORT] Liquidity Study D: SHORT, ascending highs, CONFIG 2LOW",
        f"band={band} rank={rank}  ATR(14)_raw={atr_raw:.4f}",
    ]
    for key, (label, _c, _s) in _LEVEL_STYLE_SHORT.items():
        text_panel.append(f"{label} = {raw_levels[key]:.4f}")

    detail: dict = {_LEVEL_STYLE_SHORT[k][0]: raw_levels[k] for k in _LEVEL_STYLE_SHORT}
    detail.update({"band": band, "rank": rank, "atr_raw": atr_raw, "direction": "SHORT"})
    detail["daily_levels"] = [(lbl, raw_levels[k], color) for k, (lbl, color, _s) in _LEVEL_STYLE_SHORT.items()]

    zone = find_confluence_zone_b(
        raw_levels["hi_3m"], raw_levels["hi_1w"], raw_levels["hi_1d"], atr_raw, prev_close_raw)
    if zone["status"] == "NO_CONFLUENCE":
        text_panel.append("status = NO_CONFLUENCE -- no two HIGH levels within 0.5xATR of each other")
        overlay.text_panel = text_panel
        overlay.title_suffix = "[SHORT] SKIPPED (NO_CONFLUENCE)"
        return {"bars": today_day_raw, "overlay": overlay, "status": "NO_CONFLUENCE", "detail": detail}

    tol = 0.5 * atr_raw
    zone_members, zone_price = zone["members"], zone["zone_price"]
    zone_label = "+".join(zone_members)
    overlay.bands.append(Band(zone_price - tol, zone_price + tol, f"CONFLUENCE: {zone_label}",
                               color="gold", alpha=0.18))
    overlay.levels.append(Level(zone_price, f"ZONE({zone_label})", color="goldenrod", linestyle="dash"))
    text_panel.append(f"CONFLUENCE zone = {zone_label} -> {zone_price:.4f}  "
                       f"(tol=0.5xATR={tol:.4f}, multi_cluster={zone['multi_cluster']})")
    detail["confluence_zone_price"] = zone_price
    detail["confluence_members"] = zone_label
    detail["daily_zone"] = (zone_price - tol, zone_price + tol, f"ZONE({zone_label})")

    entry = find_entry_d_short(today_candles5, today_day_raw, zone_price, atr_raw, _N_REQUIRED)
    status = entry["status"]

    if "sweep_idx" in entry:
        sweep_idx, sweep_high = entry["sweep_idx"], entry["sweep_high"]
        sweep_candle = today_candles5.iloc[sweep_idx]
        overlay.vmarkers.append(VMarker(sweep_candle["ts"], "SWEEP_HIGH", color="saddlebrown"))
        overlay.price_markers.append(
            PriceMarker(sweep_candle["ts"], sweep_high, "sweep", f"SWEEP_HIGH {sweep_high:.2f}"))
        text_panel.append(f"SWEEP_HIGH = {sweep_high:.4f} @ {sweep_candle['ts'].time()}  "
                           f"(depth={entry['sweep_depth_atr']:.4f}xATR)  -- no reclaim step in Study D, the "
                           f"ascending-highs scan starts on the very next candle")

        events = _scan_ascending_highs_events_short(today_candles5, sweep_idx, sweep_high, zone_price, _N_REQUIRED)
        for ev in events:
            candle = today_candles5.iloc[ev["candidate_idx"]]
            tag = f"ASC_HIGH count={ev['count']} ({ev['action']})"
            color = "seagreen" if ev["action"] == "EXTEND" else "slategray"
            overlay.vmarkers.append(VMarker(candle["ts"], tag, color=color))
            overlay.price_markers.append(
                PriceMarker(candle["ts"], ev["value"], "sweep", tag, direction="short"))
            text_panel.append(f"{tag}: high={ev['value']:.4f} @ {candle['ts'].time()}")

    if status == "PATTERN_BROKEN":
        broken_candle = today_candles5.iloc[entry["broken_idx"]]
        overlay.vmarkers.append(VMarker(broken_candle["ts"], "PATTERN_BROKEN (new high beyond sweep)",
                                         color="firebrick"))
        text_panel.append(f"PATTERN_BROKEN @ {broken_candle['ts'].time()}: a new high broke above SWEEP_HIGH")
    elif status == "PATTERN_INCOMPLETE":
        text_panel.append(f"PATTERN_INCOMPLETE: count never reached {_N_REQUIRED} "
                           f"(reached {entry.get('pattern_count', 0)}) before the window/day ended")

    is_real_entry = (status == "ENTERED")

    if "stop_price" in entry:
        overlay.levels.append(Level(entry["stop_price"], "STOP (above entry)", color="crimson"))
        lo, hi = sorted((entry["stop_price"], zone_price))
        overlay.bands.append(Band(lo, hi, "risk zone", color="crimson", alpha=0.06))
    if "half_target_price" in entry:
        overlay.levels.append(Level(entry["half_target_price"], "HALF_TARGET (1.5R, below entry)",
                                     color="seagreen"))
    if "full_target_price" in entry:
        overlay.levels.append(Level(entry["full_target_price"], "FULL_TARGET (3.0R, below entry)",
                                     color="darkgreen"))

    if "fill_ts" in entry and "entry_price" in entry:
        kind_label = "SHORT ENTRY (sell-to-open)" if is_real_entry else f"WOULD-BE FILL ({status})"
        marker_color = "darkorange" if is_real_entry else "gray"
        overlay.vmarkers.append(VMarker(entry["fill_ts"], kind_label, color=marker_color))
        pm_label = (f"SHORT ENTRY {entry['entry_price']:.2f}" if is_real_entry
                    else f"(rejected) {entry['entry_price']:.2f}")
        overlay.price_markers.append(
            PriceMarker(entry["fill_ts"], entry["entry_price"], "entry", pm_label,
                        direction="short" if is_real_entry else "long"))

    text_panel.append(f"status = {status}")

    if is_real_entry:
        qty = entry["qty"]
        exit_res = resolve_scaled_exit_b(
            today_day_raw, today_candles5, entry["fill_ts"], entry["entry_price"], entry["stop_price"],
            entry["half_target_price"], entry["full_target_price"], qty,
        )
        legs = exit_res["legs"]
        for i, leg in enumerate(legs):
            is_half = exit_res["half_exit_happened"] and i == 0 and len(legs) == 2
            if is_half:
                tag = "HALF_COVER"
            elif exit_res["half_exit_happened"]:
                tag = "FULL_COVER (remainder)"
            else:
                tag = "COVER (full position)"
            vm_label = f"{tag} ({leg['kind']})"
            pm_label = f"{tag} ({leg['kind']}) {leg['price']:.2f}"
            overlay.vmarkers.append(VMarker(leg["ts"], vm_label, color="teal"))
            overlay.price_markers.append(PriceMarker(leg["ts"], leg["price"], "exit", pm_label, direction="short"))

        entry_price = entry["entry_price"]
        pnl_rs = sum(leg["qty"] * (entry_price - leg["price"]) for leg in legs)
        position_size_rs = qty * entry_price
        text_panel += [
            f"SHORT entry = {entry_price:.4f} @ {entry['fill_ts'].time()}",
            f"stop (above) = {entry['stop_price']:.4f}", f"qty   = {qty}  half_qty={entry['half_qty']}",
            f"outcome = {exit_res['outcome']}",
            f"pnl_rs (gross, short convention: entry-exit) = {pnl_rs:.2f}  "
            f"position_size_rs = {position_size_rs:,.2f}",
        ]
        overlay.title_suffix = f"[SHORT] ENTERED -> {exit_res['outcome']}"
    else:
        overlay.title_suffix = f"[SHORT] SKIPPED ({status})"

    overlay.text_panel = text_panel
    return {"bars": today_day_raw, "overlay": overlay, "status": status, "detail": detail}
