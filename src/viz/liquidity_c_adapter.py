"""Liquidity confluence Study C (retest confirmation)-specific overlay
construction -- the Liquidity analogue of `viz.liquidity_a_adapter`/
`viz.liquidity_b_adapter`, extended with the retest step `liquidity.c`
adds on top of A's/B's own sweep-and-reclaim. Recomputes live via
`box_theory.context.eligible_day_context` + `liquidity.c`'s own pure
functions (`find_entry_c_long`/`find_entry_c_short`), the exact same
functions `src/liquidity/c.py`'s real DEV run used. `liquidity.a`,
`liquidity.b`, and `liquidity.c` are all CLOSED studies and are imported
read-only here, never modified.

Two entry points, one per side (mirroring the project's own A/B
convention of a dedicated function per direction, kept in one file here
because `liquidity.c` itself already bundles both directions in one
module): `build_liquidity_c_long_overlay` and
`build_liquidity_c_short_overlay`. Shows ALL SIX levels (as A's/B's own
adapters do), the confluence zone, the sweep extreme, the reclaim, and
-- new to this study -- the RETEST candle: price returning to within
0.2xATR of the zone and reclosing through it, the second confirmation
Study C requires before A's/B's own immediate reclaim-entry fires.
"""
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
from liquidity.c import find_entry_c_long, find_entry_c_short
from poc.v4 import (
    RECLAIM_WINDOW_CANDLES, _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity,
)

from viz.overlay import Band, Level, Overlay, PriceMarker, VMarker

LOOKBACK_FETCH_BUFFER_DAYS = 25

# Same six-color palette as viz.liquidity_a_adapter/viz.liquidity_b_adapter
# -- same window -> same color, so a level's identity stays visually
# stable across every study in this family.
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


def _shared_day_setup(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date, jump_dates_by_entity: dict | None, rank_lookup: dict | None,
    level_key_for_nan_check: str,
) -> dict:
    """Shared single-day eligibility + level/ATR resolution, identical
    between the long and short entry points except which level column
    is checked for the insufficient-history NaN guard (`lo_3m` for long,
    `hi_3m` for short, exactly as `liquidity.c`'s own backtest loops
    check). Returns either an early-exit adapter result dict (key
    "early_exit") or the resolved context (key "ctx")."""
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

    return {"ctx": {
        "dctx": dctx, "lv": lv, "factor_today": factor_today, "atr_raw": atr_raw,
    }}


def build_liquidity_c_long_overlay(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date,
    jump_dates_by_entity: dict | None = None, rank_lookup: dict | None = None,
) -> dict:
    """Same 4-key return shape as every other `src/viz/*_adapter.py`.
    LONG side, mirroring `viz.liquidity_a_adapter.build_liquidity_a_
    overlay` with the retest step inserted between reclaim and fill."""
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
        f"{entity_id}  {trade_date}  [Liquidity Study C: LONG, retest confirmation]",
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

    entry = find_entry_c_long(today_candles5, today_day_raw, zone_price, atr_raw)
    status = entry["status"]

    if "sweep_idx" in entry:
        sweep_idx = entry["sweep_idx"]
        window_end = entry["reclaim_idx"] if "reclaim_idx" in entry else min(
            sweep_idx + RECLAIM_WINDOW_CANDLES, len(today_candles5) - 1)
        sweep_window = today_candles5.iloc[sweep_idx:window_end + 1]
        extreme_idx = sweep_window["low"].idxmin()
        sweep_ts = today_candles5.loc[extreme_idx, "ts"]
        sweep_price = float(today_candles5.loc[extreme_idx, "low"])
        overlay.vmarkers.append(VMarker(sweep_ts, "SWEEP_LOW", color="saddlebrown"))
        overlay.price_markers.append(PriceMarker(sweep_ts, sweep_price, "sweep", f"SWEEP_LOW {sweep_price:.2f}"))
        text_panel.append(f"SWEEP_LOW = {sweep_price:.4f} @ {sweep_ts.time()}  "
                           f"(depth={entry['sweep_depth_atr']:.4f}xATR)")

    if "reclaim_idx" in entry:
        reclaim_candle = today_candles5.iloc[entry["reclaim_idx"]]
        overlay.vmarkers.append(VMarker(reclaim_candle["ts"], "RECLAIM", color="purple"))
        overlay.price_markers.append(
            PriceMarker(reclaim_candle["ts"], float(reclaim_candle["close"]), "reclaim",
                        f"RECLAIM {reclaim_candle['close']:.2f}"))
        text_panel.append(f"RECLAIM close = {reclaim_candle['close']:.4f} @ {reclaim_candle['ts'].time()}")

    if "retest_idx" in entry:
        retest_candle = today_candles5.iloc[entry["retest_idx"]]
        overlay.vmarkers.append(VMarker(retest_candle["ts"], "RETEST", color="darkcyan"))
        overlay.price_markers.append(
            PriceMarker(retest_candle["ts"], float(retest_candle["close"]), "retest",
                        f"RETEST {retest_candle['close']:.2f}"))
        text_panel.append(f"RETEST close = {retest_candle['close']:.4f} @ {retest_candle['ts'].time()}  "
                          f"(Study C's own second confirmation, required before entry)")
    elif status == "RETEST_FAILED" and "retest_breach_idx" in entry:
        breach_candle = today_candles5.iloc[entry["retest_breach_idx"]]
        overlay.vmarkers.append(VMarker(breach_candle["ts"], "RETEST_FAILED (breach)", color="firebrick"))
        text_panel.append(f"RETEST_FAILED: breached the original sweep extreme @ {breach_candle['ts'].time()}")
    elif status == "NO_RETEST":
        text_panel.append("NO_RETEST: price never returned to the zone before the window/day ended")

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


def build_liquidity_c_short_overlay(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date,
    jump_dates_by_entity: dict | None = None, rank_lookup: dict | None = None,
) -> dict:
    """SHORT side, mirroring `viz.liquidity_b_adapter.build_liquidity_b_
    overlay` with the retest step inserted -- direction-aware exactly as
    that module is (`PriceMarker(direction="short")`, `[SHORT]`-prefixed
    labels/title) so the short direction reads as structurally different
    at a glance, not as an upside-down long."""
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
        f"{entity_id}  {trade_date}  [SHORT] Liquidity Study C: SHORT, retest confirmation",
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

    entry = find_entry_c_short(today_candles5, today_day_raw, zone_price, atr_raw)
    status = entry["status"]

    if "sweep_idx" in entry:
        sweep_idx = entry["sweep_idx"]
        window_end = entry["reclaim_idx"] if "reclaim_idx" in entry else min(
            sweep_idx + RECLAIM_WINDOW_CANDLES, len(today_candles5) - 1)
        sweep_window = today_candles5.iloc[sweep_idx:window_end + 1]
        extreme_idx = sweep_window["high"].idxmax()
        sweep_ts = today_candles5.loc[extreme_idx, "ts"]
        sweep_price = float(today_candles5.loc[extreme_idx, "high"])
        overlay.vmarkers.append(VMarker(sweep_ts, "SWEEP_HIGH", color="saddlebrown"))
        overlay.price_markers.append(PriceMarker(sweep_ts, sweep_price, "sweep", f"SWEEP_HIGH {sweep_price:.2f}"))
        text_panel.append(f"SWEEP_HIGH = {sweep_price:.4f} @ {sweep_ts.time()}  "
                           f"(depth={entry['sweep_depth_atr']:.4f}xATR)")

    if "reclaim_idx" in entry:
        reclaim_candle = today_candles5.iloc[entry["reclaim_idx"]]
        overlay.vmarkers.append(VMarker(reclaim_candle["ts"], "RECLAIM", color="purple"))
        overlay.price_markers.append(
            PriceMarker(reclaim_candle["ts"], float(reclaim_candle["close"]), "reclaim",
                        f"RECLAIM {reclaim_candle['close']:.2f}"))
        text_panel.append(f"RECLAIM close = {reclaim_candle['close']:.4f} @ {reclaim_candle['ts'].time()}")

    if "retest_idx" in entry:
        retest_candle = today_candles5.iloc[entry["retest_idx"]]
        overlay.vmarkers.append(VMarker(retest_candle["ts"], "RETEST", color="darkcyan"))
        overlay.price_markers.append(
            PriceMarker(retest_candle["ts"], float(retest_candle["close"]), "retest",
                        f"RETEST {retest_candle['close']:.2f}", direction="short"))
        text_panel.append(f"RETEST close = {retest_candle['close']:.4f} @ {retest_candle['ts'].time()}  "
                          f"(Study C's own second confirmation, required before entry)")
    elif status == "RETEST_FAILED" and "retest_breach_idx" in entry:
        breach_candle = today_candles5.iloc[entry["retest_breach_idx"]]
        overlay.vmarkers.append(VMarker(breach_candle["ts"], "RETEST_FAILED (breach)", color="firebrick"))
        text_panel.append(f"RETEST_FAILED: breached the original sweep extreme @ {breach_candle['ts'].time()}")
    elif status == "NO_RETEST":
        text_panel.append("NO_RETEST: price never returned to the zone before the window/day ended")

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
