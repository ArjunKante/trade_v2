"""PREREGISTRATION_POC.md Section 3: the multi-day lookback eligibility
wrapper. Chains `box_theory.context.eligible_day_context` -- reused
unchanged -- across six days (L1..L5, T) instead of calling it once, the
first study in this project that needs more than one day's worth of
resolved RAW-scale bars for a single decision.

Also folds in Section 4 (PROXY POC / PREV_HIGH, `poc.poc`) and Section 5
(the 50-day trend filter, `poc.trend`) so a caller gets one assembled
per-(entity, T) context or a single, specific skip reason.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from box_theory.context import eligible_day_context
from box_theory.holiday import previous_nse_trading_day

from poc.poc import bucket_width, compute_poc, compute_prev_high
from poc.trend import trend_filter_passes

N_LOOKBACK_DAYS = 5

# relative-day labels, oldest to newest: L1 (5 trading days before T) .. L5
# (yesterday), then T itself
RELATIVE_LABELS = ("L1", "L2", "L3", "L4", "L5", "T")


def lookback_dates(today: dt.date) -> dict:
    """{"L1": date, ..., "L5": date, "T": date} -- L5 = previous_nse_
    trading_day(T), L4 = previous_nse_trading_day(L5), etc., per
    PREREGISTRATION_POC.md Section 3's exact definition ("the previous 5
    TRADING DAYS, not including today")."""
    days = [today]
    cur = today
    for _ in range(N_LOOKBACK_DAYS):
        cur = previous_nse_trading_day(cur)
        days.append(cur)
    # days = [T, L5, L4, L3, L2, L1] -- reverse to L1..L5, T
    ordered = list(reversed(days))
    return dict(zip(RELATIVE_LABELS, ordered))


def _cached_eligible_day_context(
    intraday_con: duckdb.DuckDBPyConnection, entity_id: str, day: dt.date,
    day_groups: dict, bhav: pd.DataFrame, ex_dates: set, jump_dates: set,
    single_day_cache: dict, rank_lookup: dict, eligible_ctx_cache: dict | None,
) -> dict:
    """Memoized `eligible_day_context` call, keyed by `day` alone --
    correct ONLY because `eligible_ctx_cache` is fresh per entity (the
    caller resets it once per entity, same lifetime as `single_day_cache`
    itself). Added because Section 3's six-day sliding window otherwise
    recomputes the SAME day's eligibility up to 6 times (day T's own "L5"
    is the same physical day as T+1's own "L4", etc.) -- a pure function
    of (entity_id, day) given these fixed per-entity inputs, so caching
    changes no result, only how many times it is computed."""
    if eligible_ctx_cache is not None and day in eligible_ctx_cache:
        return eligible_ctx_cache[day]
    ctx = eligible_day_context(
        intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
        single_day_cache, rank_lookup,
    )
    if eligible_ctx_cache is not None:
        eligible_ctx_cache[day] = ctx
    return ctx


def build_poc_context(
    intraday_con: duckdb.DuckDBPyConnection, entity_id: str, today: dt.date,
    day_groups: dict, bhav: pd.DataFrame, ex_dates: set, jump_dates: set,
    single_day_cache: dict, rank_lookup: dict, trend_lookup: dict,
    eligible_ctx_cache: dict | None = None,
) -> dict:
    """Runs Section 3's six-day chain, then Section 4/5, for one (entity,
    today). Returns either {"skip": "LOOKBACK_INCOMPLETE", "detail": {...}}
    or {"skip": "TREND_FILTER_FAILED", "poc_price": ..., "prev_high": ...,
    "band": ..., "rank": ..., "year": ...} (POC/PREV_HIGH ARE still
    computed on a trend-filter failure, per Section 5 -- needed for the
    SELECTION null's own pool) or {"skip": None, "today_day_raw": ...,
    "today_candles5": ..., "poc_price": ..., "prev_high": ..., "band": ...,
    "rank": ..., "year": ...}.

    `day_groups`/`bhav`/`ex_dates`/`jump_dates`/`single_day_cache`/
    `rank_lookup` are the SAME per-entity precomputed structures
    `box_theory.backtest.evaluate_entity` already builds once per entity
    -- passed in unchanged (Section 0: `eligible_day_context` is reused,
    not rewritten, so its own fallback for a day outside the currently
    streamed block, e.g. L1 landing in December when T is early January,
    already works with no new code here)."""
    dates = lookback_dates(today)

    ctxs: dict[str, dict] = {}
    for label in RELATIVE_LABELS:
        day = dates[label]
        ctx = _cached_eligible_day_context(
            intraday_con, entity_id, day, day_groups, bhav, ex_dates, jump_dates,
            single_day_cache, rank_lookup, eligible_ctx_cache,
        )
        if ctx["skip"] is not None:
            return {
                "skip": "LOOKBACK_INCOMPLETE",
                "detail": {"failed_at": label, "date": day, "reason": ctx["skip"]},
            }
        ctxs[label] = ctx

    lookback_bars = [ctxs[label]["day_raw"] for label in ("L1", "L2", "L3", "L4", "L5")]
    today_ctx = ctxs["T"]
    today_day_raw = today_ctx["day_raw"]

    width = bucket_width(float(today_day_raw.iloc[0]["open"]))
    poc_result = compute_poc(lookback_bars, width)
    prev_high = compute_prev_high(lookback_bars)

    base = {
        "poc_price": poc_result["poc_price"],
        "poc_bucket_index": poc_result["poc_bucket_index"],
        "poc_bucket_volume": poc_result["poc_bucket_volume"],
        "prev_high": prev_high,
        "band": today_ctx["band"], "rank": today_ctx["rank"], "year": today_ctx["year"],
        "today_day_raw": today_day_raw, "today_candles5": today_ctx["candles5"],
    }

    if not trend_filter_passes(trend_lookup, dates["L5"]):
        out = dict(base)
        out["skip"] = "TREND_FILTER_FAILED"
        return out

    base["skip"] = None
    return base
