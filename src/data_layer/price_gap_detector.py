"""Full-history gap detector: prices_eod's own trading days vs NSE's
holiday master, over the WHOLE interior of the history -- not just the
tail.

BUGS.md Bug #30: the evening job's bhavcopy fetch (prices_nse.py's
per-run walk-backward-until-found loop) only ever guarantees the LATEST
trading day gets fetched. A day it fails to fetch on its own scheduled
evening is never revisited once a later evening succeeds on ITS OWN
day directly -- the backward walk only looks further back when the
current day's own fetch also fails. That silently left 10 trading days
(2026-10-27..30, 2026-11-03/06/09/11/12/13) missing from prices_eod for
up to three weeks. assert_data_current (staleness.py) could not see
this: it only compares "today" against the warehouse's latest date, and
the warehouse's latest date kept advancing normally every day the
missing days' neighbors fetched fine. factors.momentum's own gap guard
(STALE_GAP_DAYS) correctly NaN'd every momentum window spanning the
gap -- which, because the lookback is a RELATIVE 273-trading-day
window, meant roughly a year of future dates, not just the gap itself.
Nothing surfaced "there is a hole in the middle of the history" as its
own, nameable condition until Bug #30 was traced back to it by hand.

This module is that condition, checked directly and cheaply: for every
weekday between prices_eod's own min and max trade_date, is there a row
for it, and if not, is that confirmed by NSE's own holiday calendar?
Read-only. Does not fetch, fix, or write anything -- see
scripts/run_price_gap_check.py for the standalone report, and BUGS.md
for whether/how this gets wired into fibo_evening.py as an automatic
check (deliberately not done in this module, so the report can be read
before that decision is made)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import duckdb

from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday

REASON_MISSING = "MISSING"  # confirmed not a holiday -- a genuine, unexplained gap
REASON_UNVERIFIABLE_YEAR = "UNVERIFIABLE_YEAR"  # holiday master doesn't cover this year; cannot rule out a holiday


@dataclass(frozen=True)
class MissingTradingDay:
    trade_date: dt.date
    reason: str


def find_missing_trading_days(con: duckdb.DuckDBPyConnection) -> list[MissingTradingDay]:
    """Every weekday strictly within [MIN(trade_date), MAX(trade_date)] of
    prices_eod that has no row there and is not a confirmed NSE holiday.
    Bounded by prices_eod's own history on purpose: a day before its
    earliest or after its latest date is an ingestion-start or staleness
    question (staleness.py's job), not a hole inside otherwise-present
    history, which is what this function exists to find."""
    start, end = con.execute("SELECT MIN(trade_date), MAX(trade_date) FROM prices_eod").fetchone()
    if start is None:
        return []
    existing = {row[0] for row in con.execute("SELECT DISTINCT trade_date FROM prices_eod").fetchall()}

    missing: list[MissingTradingDay] = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in existing:
            try:
                confirmed_holiday = is_nse_holiday(d)
            except HolidayCalendarMissing:
                missing.append(MissingTradingDay(d, REASON_UNVERIFIABLE_YEAR))
                d += dt.timedelta(days=1)
                continue
            if not confirmed_holiday:
                missing.append(MissingTradingDay(d, REASON_MISSING))
        d += dt.timedelta(days=1)
    return missing
