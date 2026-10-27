"""POC-specific overlay construction -- the ONLY place in this project's
visualization tooling that knows about POC_PRICE, PREV_HIGH, the touch/
confirmation mechanic, or the stop/target rule. `src/viz/` itself (data.py,
overlay.py, chart.py) has no idea any of this exists.

Recomputes live via `poc.context.build_poc_context` + `poc.resolution.
find_entry`/`resolve_exit` for the given (entity, trade_date) -- the
exact same functions `src/poc/backtest.py`'s real DEV run uses, so a
chart can never show something the backtest itself would not have
produced. This works IDENTICALLY for a real trade and a skipped setup --
only how far `find_entry` gets (NO_TOUCH, POC_FAILED, ..., ENTERED)
differs; every intermediate stage still gets its own markers so a skip
is as explorable as a trade, per instruction ("the chart should show the
POC, the touch, and why no entry happened").
"""
from __future__ import annotations

import datetime as dt

import duckdb

from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import effective_universe, reconstitute_annually

from box_theory.context import group_by_day
from box_theory.costs import round_trip_cost_rs
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily, fetch_ex_dates

from poc.backtest import STUB_YEAR, TOP_N, _build_trend_lookup_for_entity
from poc.context import build_poc_context
from poc.resolution import FIXED_RISK_RS, find_entry, resolve_exit

from viz.overlay import Band, Level, Overlay, PriceMarker, VMarker

LOOKBACK_FETCH_BUFFER_DAYS = 25  # calendar days of 1-min archive fetched before trade_date --
                                  # enough slack for Section 3's 6-day trading-day chain across holidays/weekends


def build_poc_overlay(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date,
) -> dict:
    """Returns {"bars": today's RAW-scale 1-minute DataFrame (or None if
    nothing could be computed at all), "overlay": Overlay | None,
    "status": str, "detail": dict}.

    Deliberately NOT the batched-for-performance path `src/poc/
    backtest.py` uses across a whole DEV run (per-entity-year fetch,
    shared caches across thousands of days) -- this is a one-chart tool,
    so a fresh, minimal per-entity setup scoped to just this one call is
    the right tradeoff (seconds, not part of a multi-hour run)."""
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

    bhav = fetch_bhav_daily(warehouse_con, entity_id, fetch_start - dt.timedelta(days=5), trade_date)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)
    jump_dates = combined_unexplained_jump_dates(warehouse_con).get(entity_id, set())
    trend_lookup = _build_trend_lookup_for_entity(warehouse_con, entity_id, jump_dates)

    universe = effective_universe(reconstitute_annually(warehouse_con, top_n=TOP_N), stub_year=STUB_YEAR)
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}

    ctx = build_poc_context(
        intraday_con, entity_id, trade_date, day_groups, bhav, ex_dates, jump_dates,
        {}, rank_lookup, trend_lookup,
    )

    if ctx["skip"] == "LOOKBACK_INCOMPLETE":
        d = ctx["detail"]
        return {
            "bars": day_groups.get(trade_date), "overlay": None, "status": "LOOKBACK_INCOMPLETE",
            "detail": {"reason": f"{d['failed_at']} ({d['date']}) failed its own eligibility check: {d['reason']}"},
        }

    today_day_raw, today_candles5 = ctx["today_day_raw"], ctx["today_candles5"]
    poc_price, prev_high, band, rank = ctx["poc_price"], ctx["prev_high"], ctx["band"], ctx["rank"]
    trend_blocked = ctx["skip"] == "TREND_FILTER_FAILED"

    overlay = Overlay()
    overlay.levels.append(Level(poc_price, "POC", color="tab:blue"))
    overlay.levels.append(Level(prev_high, "PREV_HIGH", color="tab:purple"))

    text_panel = [f"{entity_id}  {trade_date}", f"band={band} rank={rank}",
                  f"POC_PRICE = {poc_price:.4f}", f"PREV_HIGH = {prev_high:.4f}"]
    if trend_blocked:
        text_panel.append("TREND_FILTER_FAILED -- no entry sought by the real backtest")
        text_panel.append("(touch/confirm below are informational only)")

    entry = find_entry(today_candles5, today_day_raw, poc_price, prev_high)
    raw_status = entry["status"]
    final_status = "TREND_FILTER_FAILED" if trend_blocked else raw_status

    if "touch_idx" in entry:
        touch_candle = today_candles5.iloc[entry["touch_idx"]]
        overlay.vmarkers.append(VMarker(touch_candle["ts"], "TOUCH", color="darkorange"))
    if "confirm_idx" in entry:
        confirm_candle = today_candles5.iloc[entry["confirm_idx"]]
        kind = entry.get("confirm_kind", "")
        label = "CONFIRM" + (f" ({kind})" if kind else "")
        overlay.vmarkers.append(VMarker(confirm_candle["ts"], label, color="purple"))

    is_real_entry = (raw_status == "ENTERED" and not trend_blocked)

    if "stop_price" in entry:
        overlay.levels.append(Level(entry["stop_price"], "STOP", color="crimson"))
        overlay.bands.append(Band(entry["stop_price"], poc_price, "risk zone", color="crimson", alpha=0.08))
    if "target_price" in entry:
        overlay.levels.append(Level(entry["target_price"], "TARGET", color="seagreen"))

    if "fill_ts" in entry and "entry_price" in entry:
        kind_label = "ENTRY FILL" if is_real_entry else f"WOULD-BE FILL ({raw_status})"
        marker_color = "blue" if is_real_entry else "gray"
        overlay.vmarkers.append(VMarker(entry["fill_ts"], kind_label, color=marker_color))
        if is_real_entry:
            overlay.price_markers.append(
                PriceMarker(entry["fill_ts"], entry["entry_price"], "entry", f"ENTRY {entry['entry_price']:.2f}"))
        else:
            overlay.price_markers.append(
                PriceMarker(entry["fill_ts"], entry["entry_price"], "entry",
                            f"(rejected) {entry['entry_price']:.2f}"))

    text_panel.append(f"status = {final_status}")

    if is_real_entry:
        stop_price, target_price = entry["stop_price"], entry["target_price"]
        fill_ts, entry_price, qty = entry["fill_ts"], entry["entry_price"], entry["qty"]

        exit_res = resolve_exit(today_day_raw, today_candles5, fill_ts, entry_price, stop_price, target_price)
        exit_ts, exit_price, outcome = exit_res["exit_ts"], exit_res["exit_price"], exit_res["outcome"]
        overlay.vmarkers.append(VMarker(exit_ts, f"EXIT ({outcome})", color="black"))
        overlay.price_markers.append(PriceMarker(exit_ts, exit_price, "exit", f"EXIT {exit_price:.2f}"))

        pnl_rs = qty * (exit_price - entry_price)
        position_size_rs = qty * entry_price
        cost_rs = round_trip_cost_rs(position_size_rs, band)
        net_r = (pnl_rs - cost_rs) / FIXED_RISK_RS

        text_panel += [
            f"entry  = {entry_price:.4f} @ {fill_ts.time()}",
            f"stop   = {stop_price:.4f}", f"target = {target_price:.4f}", f"qty    = {qty}",
            f"exit   = {exit_price:.4f} @ {exit_ts.time()}  ({outcome})",
            f"position_rs = {position_size_rs:,.0f}", f"cost_rs     = {cost_rs:,.2f}",
            f"net_r       = {net_r:+.4f}",
        ]
        overlay.title_suffix = f"ENTERED -> {outcome}, net_r={net_r:+.3f}"
    else:
        overlay.title_suffix = f"SKIPPED ({final_status})"

    overlay.text_panel = text_panel
    return {
        "bars": today_day_raw, "overlay": overlay, "status": final_status,
        "detail": {"poc_price": poc_price, "prev_high": prev_high, "band": band, "rank": rank,
                   "raw_entry_status": raw_status},
    }
