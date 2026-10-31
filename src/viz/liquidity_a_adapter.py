"""Liquidity confluence Study A (long, LOW-side)-specific overlay
construction -- the Liquidity analogue of `viz.poc_v3_adapter`. Recomputes
live via `box_theory.context.eligible_day_context` + `liquidity.a`'s own
pure functions (`_build_level_lookup_for_entity`, `find_confluence_zone`,
`find_entry_a`, `resolve_scaled_exit_a`), the exact same functions
`src/liquidity/a.py`'s real DEV run used. `liquidity.a` is a CLOSED study
and is imported read-only here, never modified.

Shows ALL SIX levels the study computes (3-month/1-week/1-day high AND
low), not just the three LOW levels the study actually reads -- the
three HIGH levels are drawn too, muted, so the overlap problem Study A's
own findings doc describes (1-day/1-week clustering "by construction")
can be judged visually against the unused side as well.
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

from liquidity.a import (
    _build_level_lookup_for_entity, find_confluence_zone, find_entry_a, resolve_scaled_exit_a,
)
from poc.v4 import (
    RECLAIM_WINDOW_CANDLES, _build_adjustment_factor_lookup_for_entity, _build_atr_adjusted_lookup_for_entity,
)

from viz.overlay import Band, Level, Overlay, PriceMarker, VMarker

LOOKBACK_FETCH_BUFFER_DAYS = 25

# Six-level palette: dash = the three LOW levels Study A's own confluence
# filter actually reads; dot = the three HIGH levels `liquidity.a` already
# computes (built for Study B's own reuse) but never uses here. Colors are
# shared with `viz.liquidity_b_adapter`'s own palette (same window -> same
# color, HIGH vs LOW is the only difference), so switching between the two
# studies in the browser keeps each level's own identity visually stable.
_LEVEL_STYLE = {
    "lo_3m": ("3M_LOW", "tab:purple", "dash"), "lo_1w": ("1W_LOW", "tab:pink", "dash"),
    "lo_1d": ("1D_LOW", "tab:gray", "dash"),
    "hi_3m": ("3M_HIGH", "tab:red", "dot"), "hi_1w": ("1W_HIGH", "tab:orange", "dot"),
    "hi_1d": ("1D_HIGH", "tab:brown", "dot"),
}


def build_liquidity_a_overlay(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date,
    jump_dates_by_entity: dict | None = None, rank_lookup: dict | None = None,
) -> dict:
    """Same 4-key return shape as every other `src/viz/*_adapter.py`.
    `detail` additionally carries all six raw-scale level values (keyed
    by their own display label, e.g. `"3M_LOW"`), the confluence zone's
    own price/members when one formed, and `daily_levels`/`daily_zone` --
    a generic hook `scripts/research_app.py`'s Daily-chart branch reads
    to overlay these same six levels (and the zone) on the daily view,
    since the 3-month level in particular is invisible on an intraday
    chart."""
    fetch_start = trade_date - dt.timedelta(days=LOOKBACK_FETCH_BUFFER_DAYS)
    block = fetch_bars_range(intraday_con, entity_id, fetch_start, trade_date)
    if block.empty:
        return {
            "bars": None, "overlay": None, "status": "NO_ARCHIVE_DATA",
            "detail": {"reason": f"no bars_1min rows for {entity_id} in [{fetch_start}, {trade_date}]"},
        }
    day_groups = group_by_day(block)
    if trade_date not in day_groups:
        return {
            "bars": None, "overlay": None, "status": "NO_ARCHIVE_DATA",
            "detail": {"reason": f"{entity_id} has no bars_1min rows on {trade_date} itself"},
        }

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
        return {
            "bars": day_groups.get(trade_date), "overlay": None, "status": dctx["skip"].upper(),
            "detail": {"reason": f"single-day eligibility failed: {dctx['skip']}"},
        }

    level_lookup = _build_level_lookup_for_entity(warehouse_con, entity_id)
    atr_adjusted_lookup = _build_atr_adjusted_lookup_for_entity(warehouse_con, entity_id, jump_dates)
    factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)

    lv = level_lookup.get(trade_date)
    factor_today = factor_lookup.get(trade_date)
    if lv is None or pd.isna(lv["lo_3m"]) or factor_today is None:
        return {
            "bars": dctx["day_raw"], "overlay": None, "status": "LEVEL_INSUFFICIENT_HISTORY",
            "detail": {"reason": "fewer than 63 prior trading days of panel history for this entity-day"},
        }

    prev_day = previous_nse_trading_day(trade_date)
    atr_adjusted = atr_adjusted_lookup.get(prev_day)
    if atr_adjusted is None or pd.isna(atr_adjusted):
        return {
            "bars": dctx["day_raw"], "overlay": None, "status": "ATR_UNAVAILABLE",
            "detail": {"reason": f"ATR(14) unavailable for {prev_day}"},
        }
    atr_raw = to_raw_scale(atr_adjusted, factor_today)

    raw_levels = {k: to_raw_scale(lv[k], factor_today) for k in _LEVEL_STYLE}
    prev_close_raw = to_raw_scale(lv["prev_close"], factor_today) if not pd.isna(lv["prev_close"]) else float("nan")

    today_day_raw, today_candles5 = dctx["day_raw"], dctx["candles5"]
    band, rank = dctx["band"], dctx["rank"]

    overlay = Overlay()
    for key, (label, color, style) in _LEVEL_STYLE.items():
        overlay.levels.append(Level(raw_levels[key], label, color=color, linestyle=style))

    text_panel = [
        f"{entity_id}  {trade_date}  [Liquidity Study A: LONG, LOW-side confluence]",
        f"band={band} rank={rank}  ATR(14)_raw={atr_raw:.4f}",
    ]
    for key, (label, _c, _s) in _LEVEL_STYLE.items():
        text_panel.append(f"{label} = {raw_levels[key]:.4f}")

    detail: dict = {_LEVEL_STYLE[k][0]: raw_levels[k] for k in _LEVEL_STYLE}
    detail.update({"band": band, "rank": rank, "atr_raw": atr_raw})
    detail["daily_levels"] = [(lbl, raw_levels[k], color) for k, (lbl, color, _s) in _LEVEL_STYLE.items()]

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

    entry = find_entry_a(today_candles5, today_day_raw, zone_price, atr_raw)
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
