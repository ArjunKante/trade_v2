"""Per-entity-PER-DAY scale detection for Angel One's historical intraday
archive -- REVISED 2026-09-29, replacing the first version of this module
(which derived the scale from this project's own `adjustment_factors`
table) with a DIRECT empirical measurement that does not depend on that
table, or on knowing WHY a mismatch exists, at all.

WHY THE FIRST VERSION WAS REPLACED, per explicit decision (a data-quality
finding, not a strategy result -- made before any development backtest):
the first version's dev-window report found 14.90% UNRESOLVED, 85%+ of it
concentrated in 7 of 81 entities, and traced to CAUSES outside this
project's control -- most notably, `corporate_actions` only covers
`ex_date >= 2016-01-05`, so KOTAKBANK's real 2015 ING Vysya Bank merger
(a confirmed, clean 5x price factor) is invisible to this project's own
adjustment computation. Stated for the record: this is NOT a warehouse
bug -- the daily warehouse itself starts 2016-01, after that merger, so
every daily-side return in this project is unaffected. It only mattered
here because the FIRST scale-probe version compared Angel's archive
against OUR OWN factor table, which has no way to know about a
pre-warehouse event. Backfilling pre-2016 corporate actions was considered
and rejected in favor of a method that sidesteps the question entirely.

THE NEW MECHANISM: for entity E on trading day D, using ONLY day D-1 (E's
own previous trading day, known before D opens):

    r_high = bhavcopy's raw HIGH(D-1) / Angel's HIGH(D-1)
    r_low  = bhavcopy's raw LOW(D-1)  / Angel's LOW(D-1)
    if r_high and r_low agree within 0.1% (relative to their mean):
        scale(D) = mean(r_high, r_low)
        D's raw bars = Angel's D bars x scale(D)
    else:
        UNRESOLVED -- skip E on D

HIGH and LOW, not CLOSE: bhavcopy's CLOSE is NSE's own volume-weighted
average of the last 30 minutes of trading, which never exactly equals
Angel's last 1-minute print -- confirmed empirically on the development
window (RELIANCE alone showed a persistent ~1.27% close-vs-close drift
this way, plausibly a dividend-adjustment artifact, unrelated to any
genuine scale question). HIGH and LOW are the extreme prints of the SAME
underlying trades in both sources and should match to the rupee once the
correct scale is applied -- confirmed empirically: on a 500-pair
development-window sample, r_high and r_low agreed within 0.1% for 99.8%
of pairs (median relative disagreement exactly 0.0%).

This single mechanism resolves every case the first version struggled
with, without needing to know which case is which: a genuinely raw
archive (scale ~= 1), a back-adjusted archive (scale = the true
adjustment ratio, whatever it is), KOTAKBANK's invisible pre-2016 merger,
the TATAMOTORS/IBULHSGFIN restructurings, and RELIANCE's dividend drift --
none of these need to be individually diagnosed, because the scale is
measured directly from the same two numbers (a real HIGH, a real LOW)
every single time.

GAP GUARD, new: even a day that passes the HIGH/LOW check can still be
wrong if something happened OVERNIGHT between D-1's close and D's open
that D-1's own bars cannot see (an unflagged restructuring, a halt, a
listing event) -- if D's converted 09:15 open differs from D-1's raw
close by more than 20%, E is skipped on D regardless of how clean the
HIGH/LOW match was.

Ex-dates are still skipped outright, unchanged from the first version: the
scale can change overnight across an entity's own ex-date, and D-1 cannot
describe it.

ALL SIMULATION -- zones, entry, stop, target, quantity, costs -- happens
in D's RAW scale, because quantity = floor(500 / (entry - stop)) and
brokerage depend on real rupee prices. src/fibo/price_scale.py remains a
SEPARATE layer: it converts THIS PROJECT'S OWN adjusted daily golden-zone
levels down to raw(D) using the deterministic, well-understood
data_layer.adjustment factor. A live signal on day D needs both layers --
price_scale.py for the golden zone, this module for Angel's own bars.
"""
from __future__ import annotations

import datetime as dt
from enum import Enum

import duckdb

RATIO_AGREEMENT_TOLERANCE = 0.001   # 0.1%, r_high vs r_low agreement, per instruction
GAP_GUARD_THRESHOLD = 0.20          # 20%, converted D open vs D-1 raw close
RAW_EQUIVALENT_BAND = 0.01          # reporting-only split of "resolved" into RAW_EQUIVALENT vs SCALED


class ScaleDecision(Enum):
    RAW_EQUIVALENT = "RAW_EQUIVALENT"  # resolved, scale ~= 1.0 (reporting label only)
    SCALED = "SCALED"                  # resolved, scale meaningfully != 1.0
    UNRESOLVED = "UNRESOLVED"          # r_high/r_low disagreed beyond tolerance, or data missing
    EX_DATE_SKIP = "EX_DATE_SKIP"      # D is itself an ex-date for E
    GAP_GUARD_SKIP = "GAP_GUARD_SKIP"  # resolved, but D's converted open gapped >20% from D-1's raw close


def probe_scale(
    bhav_high_prev: float, angel_high_prev: float, bhav_low_prev: float, angel_low_prev: float,
    tolerance: float = RATIO_AGREEMENT_TOLERANCE,
) -> tuple[ScaleDecision, float | None]:
    """The pure decision from D-1's day-HIGH and day-LOW in both sources
    (day-level extremes, i.e. MAX(high)/MIN(low) across that day's 1-minute
    bars on the Angel side -- not any single bar). Returns (decision,
    scale): scale is the empirical raw-per-Angel-unit multiplier (apply as
    raw = Angel x scale), None when UNRESOLVED."""
    if not angel_high_prev or not angel_low_prev or not bhav_high_prev or not bhav_low_prev:
        return ScaleDecision.UNRESOLVED, None
    r_high = bhav_high_prev / angel_high_prev
    r_low = bhav_low_prev / angel_low_prev
    mean_r = (r_high + r_low) / 2.0
    if mean_r <= 0:
        return ScaleDecision.UNRESOLVED, None
    rel_diff = abs(r_high - r_low) / mean_r
    if rel_diff > tolerance:
        return ScaleDecision.UNRESOLVED, None
    decision = ScaleDecision.RAW_EQUIVALENT if abs(mean_r - 1.0) <= RAW_EQUIVALENT_BAND else ScaleDecision.SCALED
    return decision, mean_r


def passes_gap_guard(converted_open_d: float, bhav_close_prev: float, threshold: float = GAP_GUARD_THRESHOLD) -> bool:
    """False (fails the guard, E must be skipped on D) if D's converted
    09:15 open differs from D-1's raw close by more than `threshold` --
    an unflagged overnight event D-1's own bars cannot see."""
    if not bhav_close_prev:
        return False
    return abs(converted_open_d - bhav_close_prev) / bhav_close_prev <= threshold


def to_raw_scale(angel_price: float, scale: float) -> float:
    """Angel's D-day price, corrected to D's true raw scale: raw = Angel x scale."""
    return angel_price * scale


def is_ex_date(warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, day: dt.date) -> bool:
    """True if `day` is itself a corporate-action ex_date for entity_id's
    full ISIN lineage chain -- the scale can change overnight on this date,
    so D-1 cannot describe it and the entity must not be traded on it."""
    row = warehouse_con.execute(
        """SELECT 1 FROM corporate_actions ca JOIN isin_lineage l ON ca.isin = l.isin
           WHERE l.entity_id = ? AND ca.ex_date = ? LIMIT 1""",
        [entity_id, day],
    ).fetchone()
    return row is not None


def previous_trading_day(warehouse_con: duckdb.DuckDBPyConnection, entity_id: str, day: dt.date) -> dt.date | None:
    """entity_id's own most recent trading day strictly before `day`, per
    prices_eod -- the entity's own trading-day index, not a calendar-day
    lookback. None if no earlier trading day exists."""
    row = warehouse_con.execute(
        """SELECT MAX(p.trade_date) FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
           WHERE l.entity_id = ? AND p.series = 'EQ' AND p.trade_date < ?""",
        [entity_id, day],
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def decide_scale_for_day(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    entity_id: str, day: dt.date, tolerance: float = RATIO_AGREEMENT_TOLERANCE,
    gap_threshold: float = GAP_GUARD_THRESHOLD,
) -> dict:
    """The full, live decision for entity_id on trading day `day`. Returns
    {"decision": ScaleDecision, "scale": float|None, "prev_day": date|None}.
    Never reads `day`'s own bhavcopy -- only D-1's, plus D's own Angel OPEN
    (needed for the gap guard, which is about D's price action, not a peek
    at D's outcome)."""
    if is_ex_date(warehouse_con, entity_id, day):
        return {"decision": ScaleDecision.EX_DATE_SKIP, "scale": None, "prev_day": None}

    prev_day = previous_trading_day(warehouse_con, entity_id, day)
    if prev_day is None:
        return {"decision": ScaleDecision.UNRESOLVED, "scale": None, "prev_day": None}

    angel_prev = intraday_con.execute(
        "SELECT MAX(high), MIN(low) FROM bars_1min WHERE entity_id = ? AND trade_date = ?",
        [entity_id, prev_day],
    ).fetchone()
    if angel_prev is None or angel_prev[0] is None:
        return {"decision": ScaleDecision.UNRESOLVED, "scale": None, "prev_day": prev_day}
    angel_high_prev, angel_low_prev = angel_prev

    bhav_prev = warehouse_con.execute(
        "SELECT p.high, p.low, p.close FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin "
        "WHERE l.entity_id = ? AND p.trade_date = ? AND p.series = 'EQ'",
        [entity_id, prev_day],
    ).fetchone()
    if bhav_prev is None:
        return {"decision": ScaleDecision.UNRESOLVED, "scale": None, "prev_day": prev_day}
    bhav_high_prev, bhav_low_prev, bhav_close_prev = bhav_prev

    decision, scale = probe_scale(bhav_high_prev, angel_high_prev, bhav_low_prev, angel_low_prev, tolerance)
    if decision == ScaleDecision.UNRESOLVED:
        return {"decision": decision, "scale": None, "prev_day": prev_day}

    angel_open_d = intraday_con.execute(
        "SELECT open FROM bars_1min WHERE entity_id = ? AND trade_date = ? ORDER BY ts ASC LIMIT 1",
        [entity_id, day],
    ).fetchone()
    if angel_open_d is None:
        return {"decision": ScaleDecision.UNRESOLVED, "scale": None, "prev_day": prev_day}

    converted_open_d = to_raw_scale(angel_open_d[0], scale)
    if not passes_gap_guard(converted_open_d, bhav_close_prev, gap_threshold):
        return {"decision": ScaleDecision.GAP_GUARD_SKIP, "scale": scale, "prev_day": prev_day}

    return {"decision": decision, "scale": scale, "prev_day": prev_day}
