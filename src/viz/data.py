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


def fetch_raw_multi_day_bars(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date, n_lookback_days: int,
) -> dict:
    """Study-agnostic multi-day view: `n_lookback_days` trading days
    BEFORE `trade_date`, plus `trade_date` itself, each independently
    RAW-scale-resolved via `fetch_raw_day_bars` (same per-day mechanism,
    just called once per day instead of once). Each day keeps its OWN
    scale resolution -- a stock whose scale changed partway through the
    window is not silently forced onto one day's factor.

    Returns {"days": [{"date": date, "bars": DataFrame, "scale_label":
    str}, ...] in ascending order (oldest lookback day first, `trade_date`
    last), "combined": one concatenated DataFrame with an added
    `trade_date` column so a renderer can find day boundaries without
    re-deriving them, "missing_days": [date, ...] for any day with no
    bars_1min rows at all (skipped, not padded)}."""
    dates = []
    cur = trade_date
    for _ in range(n_lookback_days):
        cur = previous_nse_trading_day(cur)
        dates.append(cur)
    dates = list(reversed(dates)) + [trade_date]

    days = []
    missing_days = []
    combined_frames = []
    for day in dates:
        res = fetch_raw_day_bars(warehouse_con, intraday_con, entity_id, day)
        if res["bars"].empty:
            missing_days.append(day)
            continue
        days.append({"date": day, "bars": res["bars"], "scale_label": res["scale_label"]})
        tagged = res["bars"].copy()
        tagged["trade_date"] = day
        combined_frames.append(tagged)

    combined = pd.concat(combined_frames, ignore_index=True) if combined_frames else pd.DataFrame()
    return {"days": days, "combined": combined, "missing_days": missing_days}


def fetch_raw_hourly_bars(
    warehouse_con: duckdb.DuckDBPyConnection, intraday_con: duckdb.DuckDBPyConnection,
    entity_id: str, trade_date: dt.date, n_lookback_days: int,
) -> dict:
    """Hourly-candle view of the SAME window `fetch_raw_multi_day_bars`
    fetches (`n_lookback_days` before `trade_date`, plus `trade_date`
    itself) -- built ON TOP of it (same RAW-scale resolution, same
    missing-day handling), then each day's own 1-minute bars aggregated
    to 1-hour buckets via `fvg.bars.aggregate_to_1hour`: buckets anchored
    at the 09:15 session open (not midnight), so a day's LAST bucket is
    the PARTIAL 15:15-15:30 one (15 minutes, not 60) -- carried through
    on every row as `bucket_end`, the bucket's own actual close
    timestamp, rather than assuming a fixed 60-minute width. A caller
    placing a marker inside a bucket (an entry/exit fill, which lands
    partway through an hour, not on its boundary) needs this exact value
    to find the right point inside a partial bucket too, not just full
    ones.

    Returns the same shape as `fetch_raw_multi_day_bars`: {"days":
    [{"date": date, "bars": DataFrame[ts, bucket_end, open, high, low,
    close, volume], "scale_label": str}, ...], "combined": one
    concatenated DataFrame with the same columns plus `trade_date`,
    "missing_days": [date, ...]} -- a day with no bars_1min rows at all
    is skipped here exactly as it is upstream, never padded with an
    empty hourly bucket."""
    from fvg.bars import aggregate_to_1hour

    multi = fetch_raw_multi_day_bars(warehouse_con, intraday_con, entity_id, trade_date, n_lookback_days)

    hourly_days = []
    combined_frames = []
    for day in multi["days"]:
        hourly = aggregate_to_1hour(day["bars"])
        if hourly.empty:
            continue
        hourly = hourly.drop(columns=["is_green", "is_red"])
        hourly["trade_date"] = day["date"]
        hourly_days.append({"date": day["date"], "bars": hourly, "scale_label": day["scale_label"]})
        combined_frames.append(hourly)

    combined = pd.concat(combined_frames, ignore_index=True) if combined_frames else pd.DataFrame()
    return {"days": hourly_days, "combined": combined, "missing_days": multi["missing_days"]}


SMA_WINDOW = 50  # same as poc.trend.SMA_WINDOW -- the trend filter's own window


def fetch_daily_bars(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, trade_date: dt.date, n_days: int = 80,
) -> dict:
    """Study-agnostic daily-candle view: up to `n_days` trading days
    ending on (and including) `trade_date`, ENTITY-ADJUSTED scale --
    deliberately NOT RAW scale, because the 50-day moving average shown
    alongside it is the exact line a daily-timeframe trend filter (e.g.
    `poc.trend.build_trend_lookup`) computes, and that filter compares
    against `fibo.daily_ohlc`'s own adjusted close, never RAW intraday
    prices. Jump-guard-flagged days are dropped before the rolling mean
    is computed, the identical convention `poc.backtest._build_trend_
    lookup_for_entity` already uses, so this IS the real trend filter's
    own line, not a visually-similar recomputation.

    Returns {"bars": DataFrame[trade_date, adjusted_open/high/low/close,
    sma] trimmed to the last `n_days` rows, "scale_note": str}. The
    `sma` column is computed over the ENTITY'S FULL fetched history
    (not just the displayed window) so the line is correct from the
    first displayed candle, not NaN-truncated at the left edge.
    `fetch_adjustment_factor_for_overlay` (below) is what a caller uses
    to bring a RAW-scale level (POC_PRICE, PREV_HIGH) onto this same
    adjusted scale for overlay -- never compare a RAW level to these
    candles directly."""
    from fibo.daily_ohlc import build_daily_ohlc_panel
    from fibo.jump_guard import combined_unexplained_jump_dates

    panel = build_daily_ohlc_panel(warehouse_con, entity_ids=[entity_id])
    if panel.empty:
        return {"bars": pd.DataFrame(), "scale_note": f"NO DATA -- {entity_id} has no daily history"}

    jump_dates = combined_unexplained_jump_dates(warehouse_con).get(entity_id, set())
    if jump_dates:
        flagged = pd.to_datetime(pd.Series(sorted(jump_dates)))
        panel = panel[~panel["trade_date"].isin(flagged)]

    panel = panel.sort_values("trade_date").reset_index(drop=True)
    panel["sma"] = panel["adjusted_close"].rolling(window=SMA_WINDOW, min_periods=SMA_WINDOW).mean()

    panel = panel[panel["trade_date"] <= pd.Timestamp(trade_date)]
    if panel.empty:
        return {"bars": pd.DataFrame(), "scale_note": f"NO DATA -- {entity_id} has no daily history on or before {trade_date}"}

    display = panel.tail(n_days).reset_index(drop=True)
    scale_note = (
        f"Entity-adjusted daily scale (fibo.daily_ohlc) -- NOT the same scale as the 1-minute RAW view. "
        f"50-day MA is the trend filter's own line (jump-guard-flagged days already excluded)."
    )
    return {"bars": display, "scale_note": scale_note}


def adjust_raw_level_for_daily_chart(
    warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, trade_date: dt.date, raw_price: float,
) -> float:
    """Converts a RAW-scale price level (e.g. POC_PRICE/PREV_HIGH,
    resolved for `trade_date`'s own intraday scale) onto the SAME
    entity-adjusted scale `fetch_daily_bars` plots -- using `fibo.
    price_scale`'s own factor lookup, inverted (that module converts
    adjusted -> raw; `adjusted = raw * factor(trade_date)` is the same
    relationship run the other way). Comparing a RAW level directly
    against adjusted daily candles would be silently wrong by whatever
    split/bonus ratio occurred between `trade_date` and today -- the
    exact pitfall `fibo.price_scale`'s own docstring names."""
    from fibo.price_scale import get_adjustment_factor

    factor = get_adjustment_factor(warehouse_con, entity_id, trade_date)
    return raw_price * factor
