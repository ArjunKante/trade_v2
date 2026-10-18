"""Per-(entity, day) eligibility (jump guard, ex-date, previous-session
validity, scale resolution) -- structurally identical to `box_theory.
context.eligible_day_context`, reimplemented here ONLY because it must
aggregate to 1-hour candles (`fvg.bars.aggregate_to_1hour`) instead of
5-minute ones; every underlying check and primitive is the same one box
theory already uses (`box_theory.holiday.previous_nse_trading_day`,
`box_theory.universe_data.fetch_bars_single_day`, `box_theory.costs.
band_for_rank`, `fibo.scale_probe`). `box_theory/context.py` itself is
imported read-only for `group_by_day` (no coupling to bar width -- reused
unchanged) but not for `eligible_day_context` (bar width IS coupled
there).

Also new here, because box theory never needs it (its pattern and exit
both resolve within one session): `build_entity_timeline`, which strings
a sequence of eligible days into ONE continuous, globally-indexed 1-hour
candle series and ONE continuous 1-minute bar series per entity --
`PREREGISTRATION_FVG.md` Section 3's "ineligible days are excised, not a
pause" rule, and Section 4's cross-day pattern/live-window scanning,
both depend on this single continuous structure existing.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from fibo.scale_probe import probe_scale, passes_gap_guard, ScaleDecision, to_raw_scale

from box_theory.context import group_by_day  # unchanged, no bar-width coupling
from box_theory.costs import band_for_rank
from box_theory.holiday import previous_nse_trading_day
from box_theory.universe_data import fetch_bars_single_day

from fvg.bars import aggregate_to_1hour

STUB_YEAR = 2016
SKIP_REASONS = ("bad_previous_session", "ex_date", "jump_guard")


def eligible_day_context(
    intraday_con: duckdb.DuckDBPyConnection, entity_id: str, day: dt.date,
    day_groups: dict, bhav: pd.DataFrame, ex_dates: set, jump_dates: set,
    single_day_cache: dict, rank_lookup: dict,
) -> dict:
    """Same four checks, same order, as `box_theory.context.
    eligible_day_context`. Returns {"skip": reason} or {"skip": None,
    "day_raw": DataFrame, "candles1h": DataFrame, "band": str,
    "rank": int|None, "year": int}."""
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

    day_raw = day_bars.copy()
    price_cols = ["open", "high", "low", "close"]
    day_raw[price_cols] = day_raw[price_cols].to_numpy() * scale
    candles1h = aggregate_to_1hour(day_raw[["ts", "open", "high", "low", "close", "volume"]])

    year_of_day = STUB_YEAR if day.year == STUB_YEAR else day.year
    rank = rank_lookup.get((year_of_day, entity_id))
    band = band_for_rank(rank)

    return {
        "skip": None, "day_raw": day_raw, "candles1h": candles1h,
        "band": band, "rank": rank, "year": year_of_day,
    }


def build_entity_timeline(
    intraday_con: duckdb.DuckDBPyConnection, entity_id: str, day_groups: dict,
    bhav: pd.DataFrame, ex_dates: set, jump_dates: set, single_day_cache: dict,
    rank_lookup: dict,
) -> dict:
    """Runs `eligible_day_context` over every day in `day_groups` (sorted),
    then concatenates the ELIGIBLE days' `day_raw`/`candles1h` into ONE
    continuous, globally-indexed series -- ineligible days are excised
    entirely (PREREGISTRATION_FVG.md Section 3), not a placeholder.

    Returns {"candles": DataFrame [global_idx, ts, bucket_end, open, high,
    low, close, volume, is_green, is_red, trade_date, band, rank, year]
    (index = global_idx, 0-based, chronological across all eligible days),
    "bars1": DataFrame [ts, open, high, low, close, volume, trade_date]
    (continuous 1-minute series, same eligible days only), "skips":
    {reason: count}, "eligible_days": sorted list of dates included}."""
    skips = {r: 0 for r in SKIP_REASONS}
    candle_frames = []
    bar1_frames = []
    eligible_days = []
    # per-day scalars (trade_date/band/rank/year) are NOT assigned column-
    # by-column inside this loop -- doing so forces a fresh pandas
    # DataFrame.__setitem__ (block-manager rebuild, index-engine rebuild)
    # per day, which profiled as the dominant cost of this whole function
    # at full-universe scale (dwarfing the actual DB fetch time). Instead,
    # each day's own metadata is recorded once here and broadcast with
    # `np.repeat` AFTER concatenation -- O(1) setitem calls total instead
    # of O(days).
    day_meta: list[tuple] = []  # (trade_date, band, rank, year, n_rows)

    for day in sorted(day_groups.keys()):
        ctx = eligible_day_context(
            intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
            single_day_cache, rank_lookup,
        )
        if ctx["skip"] is not None:
            skips[ctx["skip"]] += 1
            continue
        c1h = ctx["candles1h"]
        if c1h.empty:
            continue
        candle_frames.append(c1h)
        day_meta.append((day, ctx["band"], ctx["rank"], ctx["year"], len(c1h)))

        b1 = ctx["day_raw"][["ts", "open", "high", "low", "close", "volume"]]
        bar1_frames.append(b1)
        eligible_days.append(day)

    if candle_frames:
        candles = pd.concat(candle_frames, ignore_index=True)
        n_candle_rows = np.array([m[4] for m in day_meta])
        candles["trade_date"] = np.repeat([m[0] for m in day_meta], n_candle_rows)
        candles["band"] = np.repeat([m[1] for m in day_meta], n_candle_rows)
        candles["rank"] = np.repeat([m[2] for m in day_meta], n_candle_rows)
        candles["year"] = np.repeat([m[3] for m in day_meta], n_candle_rows)
        candles.index.name = "global_idx"

        bars1 = pd.concat(bar1_frames, ignore_index=True)
        n_bar_rows = np.array([len(b1) for b1 in bar1_frames])
        bars1["trade_date"] = np.repeat([m[0] for m in day_meta], n_bar_rows)
    else:
        candles = pd.DataFrame(columns=[
            "ts", "bucket_end", "open", "high", "low", "close", "volume",
            "is_green", "is_red", "trade_date", "band", "rank", "year",
        ])
        bars1 = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume", "trade_date"])

    return {"candles": candles, "bars1": bars1, "skips": skips, "eligible_days": eligible_days}
