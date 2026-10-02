"""Open-entry variant of the Fibo day-selection rule. ORIGIN (stated plainly,
per FIBO_OPEN.md): this idea came from observing src/fibo's own TIMING-null
result on the sealed test -- the ORB-breakout entry trigger scored at the
2.3rd percentile against a random-entry-time null on the SAME good days the
Fibonacci+ORB confluence picked (FIBO.md, "THE SEALED TEST" section). That
observation was NOT pre-specified before the sealed test was read, so this
module's rules were decided AFTER seeing that result -- the historical data
has therefore already been seen, and Phase 1 here is explicitly a
DIAGNOSTIC, not a test (see FIBO_OPEN.md).

EVERY rule is identical to src/fibo except the entry mechanism:
  - same daily Alligator uptrend, 5-each-side fractals, 2xATR minimum move,
    50-61.8% golden zone, same ORB-overlap condition for SETUP ON -- all
    reused directly from src/fibo (fibo.indicators, fibo.signals), never
    reimplemented here.
  - same ORB (09:15-09:30), same stop (ORB low), same target
    (min(entry+2R, swing high)), same Rs 500 fixed risk, same 15:15 exit --
    reused directly from fibo.backtest.compute_orb/zones_overlap and
    fibo.resolution.compute_r/compute_target/position_size_shares/
    resolve_trade.
  - ENTRY (the one rule that changes): buy at the 09:30 price on EVERY
    setup-ON day -- no breakout trigger, no waiting, no 11:30 cutoff. "The
    09:30 price" is read as the OPEN of the first 1-minute bar immediately
    after the opening range closes (fibo.backtest.ORB_END = 09:30,
    exclusive of the ORB window itself) -- the literal first print available
    at 09:30, not that bar's close (which is what the breakout rule uses,
    for a different reason: the breakout rule needs a CLOSE to evaluate its
    trigger condition against). This is a stated interpretation of "the
    09:30 price," not an invented detail.

RE-DERIVED, NOT COPIED, ASSUMPTION -- resolve_trade's "exclude the entry bar
from monitoring" convention (fibo.resolution.py's docstring: "the entry bar
itself is excluded -- its price action is already priced into the entry
fill"). That convention is correct for the breakout rule because its entry
price IS that bar's CLOSE -- by the time the signal fires, the bar is over
and there is nothing left in it to monitor. It does NOT travel unexamined to
an open-price entry: here the entry fill happens at the INSTANT the 09:30 bar
opens, so that same bar's own subsequent high/low (whatever happens for the
rest of that minute) is still live risk, not yet "priced into the fill."
Accordingly, `evaluate_entity_day_open` passes resolve_trade an entry_ts one
minute before the entry bar (the ORB window's own last bar, 09:29) so the
monitoring window (ts > entry_ts) correctly INCLUDES the 09:30 bar itself,
rather than skipping it the way the breakout rule's convention would if
blindly reused.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from fibo.backtest import compute_orb, zones_overlap, ORB_END
from fibo.resolution import compute_r, compute_target, position_size_shares, resolve_trade
from fibo.scale_probe import ScaleDecision, to_raw_scale as scale_probe_to_raw
from fibo.price_scale import to_raw_scale as factor_to_raw
from swing.costs import round_trip_cost_rs

ENTRY_TIME = ORB_END  # 09:30 -- the first 1-minute bar immediately after the opening range closes
EXIT_TIME = dt.time(15, 15)


def find_open_entry(bars_1min_raw: pd.DataFrame, day: dt.date) -> tuple[pd.Timestamp, float] | None:
    """The 09:30 1-minute bar's own OPEN price -- "the 09:30 price," per the
    frozen rule. None if that exact bar is missing from the day's downloaded
    bars (a data gap; should be rare since the ORB bars immediately
    preceding it exist by construction of reaching this point)."""
    bar = bars_1min_raw[bars_1min_raw["ts"].dt.time == ENTRY_TIME]
    if bar.empty:
        return None
    row = bar.sort_values("ts").iloc[0]
    return row["ts"], float(row["open"])


def evaluate_entity_day_open(
    entity_id: str, day: dt.date, signal_row: dict, scale_decision: ScaleDecision, scale: float | None,
    factor_d: float, bars_1min_angel: pd.DataFrame | None,
) -> dict:
    """The open-entry counterpart of fibo.backtest.evaluate_entity_day.
    Same arguments, same category vocabulary where the concept still
    applies (EXCLUDED_SCALE, NO_INTRADAY_DATA, NO_SIGNAL, SETUP_OFF,
    DEGENERATE_QTY, INVALID_R, TRADE) -- SETUP_ON_NO_TRIGGER does not exist
    here, by rule: every setup-ON day enters, unconditionally."""
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

    entry = find_open_entry(bars, day)
    if entry is None:
        return {"category": "NO_OPEN_BAR", "orb_high": orb_high, "orb_low": orb_low}
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
    # monitor from one minute before the entry bar so the entry bar's OWN
    # high/low (still live risk after an open-price fill) is included --
    # see the module docstring's RE-DERIVED note.
    monitor_from_ts = entry_ts - pd.Timedelta(minutes=1)
    resolution = resolve_trade(bars, monitor_from_ts, stop, target, exit_ts)

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
