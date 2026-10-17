"""The shared per-(entity, day) eligibility pipeline: jump guard, ex-date,
previous-session validity (calendar + >=350-bar archive check), and scale
resolution (PREREGISTRATION_BOX.md Section 2b) -- factored out of
`backtest.py` so `nulls.py`'s SELECTION null (which needs the exact same
"is this a valid box-day" population, including days that never touched
PREV_LOW) does not re-derive or drift from the real backtest's own
eligibility logic. One definition, two callers.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fibo.scale_probe import probe_scale, passes_gap_guard, ScaleDecision, to_raw_scale

from box_theory.bars import aggregate_to_5min
from box_theory.costs import band_for_rank
from box_theory.holiday import previous_nse_trading_day
from box_theory.universe_data import fetch_bars_single_day

STUB_YEAR = 2016


def group_by_day(block: pd.DataFrame) -> dict:
    """{date -> sub-DataFrame}, grouped ONCE per entity-year block --
    avoids repeated boolean-mask scans (see universe_data.fetch_bars_range's
    docstring)."""
    return {
        pd.Timestamp(ts).date(): grp.sort_values("ts").reset_index(drop=True)
        for ts, grp in block.groupby("trade_date", sort=True)
    }


def eligible_day_context(
    intraday_con: duckdb.DuckDBPyConnection, entity_id: str, day: dt.date,
    day_groups: dict, bhav: pd.DataFrame, ex_dates: set, jump_dates: set,
    single_day_cache: dict, rank_lookup: dict,
) -> dict:
    """Runs every Section 2b eligibility check for one (entity, day) in
    order. Returns either {"skip": reason} (reason in SKIP_REASONS) or
    {"skip": None, "day_raw": DataFrame, "candles5": DataFrame,
    "prev_high": float, "prev_low": float, "band": str, "rank": int|None,
    "year": int}. `day_groups`/`bhav`/`ex_dates`/`single_day_cache` are
    the same per-entity precomputed structures `backtest.evaluate_entity`
    builds once -- passed in rather than rebuilt here so a caller
    iterating many days for one entity pays the entity-level fetch cost
    once."""
    prev_day = previous_nse_trading_day(day)

    if day in jump_dates or prev_day in jump_dates:
        return {"skip": "jump_guard"}

    if day in ex_dates:
        return {"skip": "ex_date"}

    if prev_day in day_groups:
        prev_bars = day_groups[prev_day]
    else:
        if prev_day not in single_day_cache:
            single_day_cache[prev_day] = fetch_bars_single_day(intraday_con, entity_id, prev_day)
        prev_bars = single_day_cache[prev_day]

    if len(prev_bars) < 350:
        return {"skip": "bad_previous_session"}

    if prev_day not in bhav.index or day not in bhav.index:
        return {"skip": "bad_previous_session"}
    bhav_prev = bhav.loc[prev_day]

    angel_high_prev = float(prev_bars["high"].max())
    angel_low_prev = float(prev_bars["low"].min())
    decision, scale = probe_scale(
        float(bhav_prev["high"]), angel_high_prev, float(bhav_prev["low"]), angel_low_prev,
    )
    if decision == ScaleDecision.UNRESOLVED:
        return {"skip": "bad_previous_session"}

    day_bars = day_groups.get(day)
    if day_bars is None or day_bars.empty:
        return {"skip": "bad_previous_session"}
    angel_open_d = float(day_bars.iloc[0]["open"])
    converted_open_d = to_raw_scale(angel_open_d, scale)
    if not passes_gap_guard(converted_open_d, float(bhav_prev["close"])):
        return {"skip": "bad_previous_session"}

    prev_high = to_raw_scale(angel_high_prev, scale)
    prev_low = to_raw_scale(angel_low_prev, scale)

    day_raw = day_bars.copy()
    for c in ("open", "high", "low", "close"):
        day_raw[c] = day_raw[c] * scale
    candles5 = aggregate_to_5min(day_raw[["ts", "open", "high", "low", "close", "volume"]])

    year_of_day = STUB_YEAR if day.year == STUB_YEAR else day.year
    rank = rank_lookup.get((year_of_day, entity_id))
    band = band_for_rank(rank)

    return {
        "skip": None, "day_raw": day_raw, "candles5": candles5,
        "prev_high": prev_high, "prev_low": prev_low, "band": band, "rank": rank,
        "year": year_of_day,
    }
