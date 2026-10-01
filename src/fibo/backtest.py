"""Step 5's development-backtest engine: the per-(entity, day) evaluation
that turns a daily signal (src/fibo/signals.py) plus that day's intraday
bars into a category -- EXCLUDED_SCALE, NO_SIGNAL, SETUP_OFF,
SETUP_ON_NO_TRIGGER, DEGENERATE_QTY, or TRADE -- and, for TRADE, a fully
resolved trade record.

TWO SCALE LAYERS, applied in order, per PREREGISTRATION_FIBO.md's Section
2 and the price-scale REVISION note:
  1. The golden zone and swing high are computed on THIS PROJECT'S OWN
     adjusted daily prices -- converted to day D's raw scale via
     src/fibo/price_scale.py, using data_layer.adjustment's deterministic
     factor(D).
  2. Angel's own 1-minute bars for day D are converted to raw scale via
     src/fibo/scale_probe.py's empirically-measured scale(D) (the
     HIGH/LOW method).
Both conversions land in the SAME raw scale -- the actual rupee prices D
traded at -- only then are they compared.

ONE TRADE PER STOCK PER DAY, by construction: one daily signal (one swing,
one golden zone) per entity per day, and the entry scan stops at the FIRST
qualifying 15-minute candle.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from fibo.bars import aggregate_to_15min
from fibo.resolution import compute_r, compute_target, position_size_shares, resolve_trade
from fibo.scale_probe import ScaleDecision, to_raw_scale as scale_probe_to_raw
from fibo.price_scale import to_raw_scale as factor_to_raw
from swing.costs import round_trip_cost_rs

ORB_START = dt.time(9, 15)
ORB_END = dt.time(9, 30)          # exclusive
ENTRY_WINDOW_START = dt.time(9, 30)
ENTRY_WINDOW_LAST_START = dt.time(11, 15)  # last candle START that can trigger (closes 11:30)
EXIT_TIME = dt.time(15, 15)


def compute_orb(bars_1min_raw: pd.DataFrame) -> tuple[float, float] | None:
    """(orb_high, orb_low) from the 09:15-09:30 1-minute bars, RAW scale.
    None if no bars fall in that window."""
    window = bars_1min_raw[(bars_1min_raw["ts"].dt.time >= ORB_START) & (bars_1min_raw["ts"].dt.time < ORB_END)]
    if window.empty:
        return None
    return window["high"].max(), window["low"].min()


def zones_overlap(orb_low: float, orb_high: float, zone_low: float, zone_high: float) -> bool:
    return orb_low <= zone_high and orb_high >= zone_low


def find_entry(bars_15min_raw: pd.DataFrame, orb_high: float) -> tuple[pd.Timestamp, float] | None:
    """Scans 15-min candles (RAW scale) with start in
    [ENTRY_WINDOW_START, ENTRY_WINDOW_LAST_START] for the FIRST whose close
    > orb_high. Returns (entry_ts, entry_price); entry_ts is the LAST
    1-minute bar's own timestamp inside that candle (start + 14min),
    matching resolve_trade's "exclude the entry bar itself" convention."""
    window = bars_15min_raw[
        (bars_15min_raw["ts"].dt.time >= ENTRY_WINDOW_START) & (bars_15min_raw["ts"].dt.time <= ENTRY_WINDOW_LAST_START)
    ].sort_values("ts")
    for _, bar in window.iterrows():
        if bar["close"] > orb_high:
            return bar["ts"] + pd.Timedelta(minutes=14), float(bar["close"])
    return None


def evaluate_entity_day(
    entity_id: str, day: dt.date, signal_row: dict, scale_decision: ScaleDecision, scale: float | None,
    factor_d: float, bars_1min_angel: pd.DataFrame | None,
) -> dict:
    """The full per-(entity, day) decision. `bars_1min_angel` is that day's
    RAW-Angel-units 1-minute bars (columns ts/open/high/low/close/volume,
    NOT yet scale-corrected) or None/empty if nothing was downloaded for
    this day. `signal_row` carries uptrend/has_swing/zone_low/zone_high/
    swing_high_price -- all in THIS PROJECT'S adjusted scale.

    Returns {"category": str, ...}; category == "TRADE" additionally
    carries a "trade" dict with every field needed for the aggregate
    report and hand-tracing.
    """
    if scale_decision not in (ScaleDecision.RAW_EQUIVALENT, ScaleDecision.SCALED):
        return {"category": "EXCLUDED_SCALE", "reason": scale_decision.value}

    if bars_1min_angel is None or bars_1min_angel.empty:
        return {"category": "NO_INTRADAY_DATA"}

    if not signal_row["uptrend"] or not signal_row["has_swing"]:
        return {"category": "NO_SIGNAL"}

    bars = bars_1min_angel.copy()
    for col in ("open", "high", "low", "close"):
        bars[col] = scale_probe_to_raw(bars[col], scale)

    orb = compute_orb(bars)
    if orb is None:
        return {"category": "NO_ORB_DATA"}
    orb_high, orb_low = orb

    zone_low_raw = factor_to_raw(signal_row["zone_low"], factor_d)
    zone_high_raw = factor_to_raw(signal_row["zone_high"], factor_d)
    swing_high_raw = factor_to_raw(signal_row["swing_high_price"], factor_d)

    if not zones_overlap(orb_low, orb_high, zone_low_raw, zone_high_raw):
        return {"category": "SETUP_OFF", "orb_high": orb_high, "orb_low": orb_low,
                "zone_low": zone_low_raw, "zone_high": zone_high_raw}

    bars_15min = aggregate_to_15min(bars)
    entry = find_entry(bars_15min, orb_high)
    if entry is None:
        return {"category": "SETUP_ON_NO_TRIGGER", "orb_high": orb_high, "orb_low": orb_low,
                "zone_low": zone_low_raw, "zone_high": zone_high_raw}
    entry_ts, entry_price = entry

    stop = orb_low
    r = compute_r(entry_price, stop)
    if r <= 0:
        return {"category": "INVALID_R", "entry_price": entry_price, "stop": stop}

    qty = position_size_shares(entry_price, stop)
    if qty < 1:
        return {"category": "DEGENERATE_QTY", "r": r, "entry_price": entry_price, "stop": stop}

    target = compute_target(entry_price, stop, swing_high_raw)
    exit_ts = pd.Timestamp.combine(pd.Timestamp(day), EXIT_TIME)
    resolution = resolve_trade(bars, entry_ts, stop, target, exit_ts)

    gross_r = (resolution["exit_price"] - entry_price) / r
    position_size_rs = qty * entry_price
    cost_lo_rs, cost_hi_rs = round_trip_cost_rs(position_size_rs, "INTRADAY")
    cost_lo_r = cost_lo_rs / (r * qty)
    cost_hi_r = cost_hi_rs / (r * qty)

    trade = {
        "entity_id": entity_id, "trade_date": day,
        "orb_high": orb_high, "orb_low": orb_low, "zone_low": zone_low_raw, "zone_high": zone_high_raw,
        "swing_high_raw": swing_high_raw,
        "entry_ts": entry_ts, "entry_price": entry_price, "stop": stop, "target": target, "r_rupees": r,
        "qty": qty, "position_size_rs": position_size_rs,
        "exit_ts": resolution["exit_ts"], "exit_price": resolution["exit_price"], "exit_reason": resolution["outcome"],
        "gross_r": gross_r,
        "cost_lo_rs": cost_lo_rs, "cost_hi_rs": cost_hi_rs, "cost_lo_r": cost_lo_r, "cost_hi_r": cost_hi_r,
        "net_r_lo_cost": gross_r - cost_lo_r, "net_r_hi_cost": gross_r - cost_hi_r,
    }
    return {"category": "TRADE", "trade": trade}
