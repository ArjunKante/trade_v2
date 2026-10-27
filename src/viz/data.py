"""Study-agnostic single-day RAW-scale data fetch for src/viz/'s plotting
tools. Reuses the same scale-resolution primitives every intraday study
in this project already uses (`fibo.scale_probe`, `box_theory.holiday`)
-- a trimmed, single-day version, since a plotting tool looks at one
entity-day at a time, not a batched multi-year backtest.

Unlike every backtest's own eligibility pipeline (`box_theory.context.
eligible_day_context` and its per-study derivatives), a day that FAILS
scale resolution here is never silently excluded -- it is still plotted,
with the chart saying so loudly, because a visualization tool's job is
to show what is actually in the archive, not to decide whether a day is
backtest-eligible. "Prices must be in the day's RAW scale ... and the
chart must say which scale it is showing" (per instruction) is the
reason `scale_label` exists and is never optional.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fibo.scale_probe import ScaleDecision, passes_gap_guard, probe_scale, to_raw_scale

from box_theory.holiday import previous_nse_trading_day
from box_theory.universe_data import fetch_bars_range, fetch_bhav_daily


def fetch_raw_day_bars(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date,
) -> dict:
    """Returns {"bars": DataFrame[ts, open, high, low, close, volume],
    "decision": ScaleDecision, "scale": float, "scale_label": str}.

    `bars` is in RAW rupee scale when `decision` is RAW_EQUIVALENT or
    SCALED; when scale resolution fails for any reason, `bars` is
    returned UNCONVERTED (Angel-native units) and `scale_label` says so
    explicitly -- never silently presented as RAW."""
    bars = fetch_bars_range(intraday_con, entity_id, trade_date, trade_date)
    if bars.empty:
        return {
            "bars": bars, "decision": ScaleDecision.UNRESOLVED, "scale": 1.0,
            "scale_label": f"NO DATA -- {entity_id} has no bars_1min rows on {trade_date}",
        }
    bars = bars.sort_values("ts").reset_index(drop=True)

    prev_day = previous_nse_trading_day(trade_date)
    prev_bars = fetch_bars_range(intraday_con, entity_id, prev_day, prev_day)
    bhav = fetch_bhav_daily(warehouse_con, entity_id, prev_day, trade_date)

    decision, scale, reason = ScaleDecision.UNRESOLVED, None, "no previous-day Angel bars"
    if not prev_bars.empty and prev_day in bhav.index:
        angel_high_prev = float(prev_bars["high"].max())
        angel_low_prev = float(prev_bars["low"].min())
        bhav_prev = bhav.loc[prev_day]
        decision, scale = probe_scale(
            float(bhav_prev["high"]), angel_high_prev, float(bhav_prev["low"]), angel_low_prev,
        )
        if decision == ScaleDecision.UNRESOLVED:
            reason = "previous-day HIGH/LOW disagreement beyond 0.1% tolerance"
        else:
            angel_open_d = float(bars.iloc[0]["open"])
            converted_open_d = to_raw_scale(angel_open_d, scale)
            if not passes_gap_guard(converted_open_d, float(bhav_prev["close"])):
                decision, scale, reason = ScaleDecision.UNRESOLVED, None, "gap guard failed (>20% overnight move)"

    if decision == ScaleDecision.UNRESOLVED or scale is None:
        label = (f"SCALE UNRESOLVED ({reason}) -- showing Angel-native prices AS-IS, "
                 f"NOT a verified RAW rupee scale")
        return {"bars": bars, "decision": ScaleDecision.UNRESOLVED, "scale": 1.0, "scale_label": label}

    out = bars.copy()
    for c in ("open", "high", "low", "close"):
        out[c] = out[c] * scale
    label = f"RAW rupee scale (factor {scale:.6f} resolved from {prev_day}, decision={decision.value})"
    return {"bars": out, "decision": decision, "scale": scale, "scale_label": label}
