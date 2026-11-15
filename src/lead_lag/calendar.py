"""Governing exchange-session calendar (Decisions 10, 21, 24).

**Correction, this revision**: the prior implementation derived session
membership from `bars_1min` row presence (`compute_n_min_table` /
`classify_archive`). This violated Decision 24: the governing calendar
must be determined by the exchange-session source (NSE holiday master
plus explicit special-session verification), never by which rows a data
vendor happens to have archived. This revision removes all dependency
on `bars_1min`, `prices_eod`, or any database connection from the
calendar-truth functions below -- they are pure functions of a date and
`data_layer.nse_holidays`.

Session membership rule (no data-presence input anywhere):

    is_exchange_session(d) ==
        d in GOVERNING_SPECIAL_SESSIONS                    (the 4 verified
                                                             weekend specials)
        OR (d.weekday() < 5 AND NOT is_nse_holiday(d))      (ordinary weekday,
                                                             not a holiday)

The governing calendar is every `d` for which this is true. The
primary-sample calendar (Decision 21) is the governing calendar less
`PRIMARY_SAMPLE_EXCLUSIONS` (`2021-02-24`, conservatively excluded --
session identity unresolved, and `REGULAR_SESSION_FINAL_BAR_AUDIT.md`
itself contains mutually inconsistent statements about this date's own
in-window coverage).

**Unknown holiday-calendar years are never silently treated as normal
trading days.** `data_layer.nse_holidays.is_nse_holiday` raises
`HolidayCalendarMissing` for years its source does not cover; this
module never catches that exception -- it propagates to the caller, who
must treat it as a blocker, not default it to `True` or `False`.

**Archive-coverage diagnostics are a separate concern, implemented in
`archive_coverage_diagnostics` below, clearly separated from session-
truth.** A date can be a genuine exchange session with zero, partial, or
full `bars_1min` coverage -- that is a downstream Stage A/B eligibility
fact (handled in `eligibility.py`), never a reason to reclassify the
date's own session status here.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_layer.nse_holidays import is_nse_holiday, HolidayCalendarMissing  # noqa: E402,F401 (re-exported)

REGULAR_SESSION_START = dt.time(9, 15, 0)
REGULAR_SESSION_END = dt.time(15, 29, 59)

# Decision 21 (AMENDMENT 9 LOG, Section 4): the four verified genuine
# weekend special-trading-session dates. These are NOT derivable from
# `nse_holidays.py` (a holiday-exclusion source, not a special-session
# inclusion source) -- they are reused, approved constants, exactly as
# every prior amendment in this family has treated them.
GOVERNING_SPECIAL_SESSIONS: frozenset[dt.date] = frozenset({
    dt.date(2020, 2, 1),
    dt.date(2024, 1, 20),
    dt.date(2025, 2, 1),
    dt.date(2026, 2, 1),
})

# Decision 21 (AMENDMENT 9 LOG, Section 4): excluded from the primary
# sample -- session identity unresolved, and the final-bar audit's own
# in-window-coverage statements for this date are mutually inconsistent.
PRIMARY_SAMPLE_EXCLUSIONS: frozenset[dt.date] = frozenset({
    dt.date(2021, 2, 24),
})

# Decision 23/24: the approved data cutoff for this study. This is a
# DATA boundary, not a calendar-truth boundary -- `is_exchange_session`
# does not reference it, and a caller must not infer that the exchange
# was closed on or after this date. It exists only so orchestration code
# (e.g. a future caller enumerating ranking dates for the study) has one
# documented, non-magic constant for "where this study's data stops."
DATA_CUTOFF_END = dt.date(2026, 9, 18)


def is_exchange_session(d: dt.date) -> bool:
    """Decision 10/21/24: is `d` a genuine NSE exchange trading session?
    Pure function of the date and the NSE holiday master -- no database
    connection, no archive-presence input of any kind.

    Raises `HolidayCalendarMissing` (propagated, never caught here) if
    `d`'s year is not covered by `data_layer.nse_holidays`'s source."""
    if d in GOVERNING_SPECIAL_SESSIONS:
        return True
    if d.weekday() >= 5:
        return False
    return not is_nse_holiday(d)  # may raise HolidayCalendarMissing -- propagated


def is_primary_sample_date(d: dt.date) -> bool:
    """Decision 21/24: is `d` part of the primary-sample calendar (the
    governing calendar, less the conservative exclusions)? Pure
    function; propagates `HolidayCalendarMissing` exactly like
    `is_exchange_session`."""
    if d in PRIMARY_SAMPLE_EXCLUSIONS:
        return False
    return is_exchange_session(d)


def exchange_session_dates(start: dt.date, end: dt.date) -> list[dt.date]:
    """Decision 10: every governing exchange-session date in
    `[start, end]`, inclusive. Pure calendar enumeration -- no database
    connection. Raises `HolidayCalendarMissing` immediately if any
    covered year is unresolvable (not silently skipped)."""
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    out = []
    d = start
    one_day = dt.timedelta(days=1)
    while d <= end:
        if is_exchange_session(d):
            out.append(d)
        d += one_day
    return out


def primary_sample_dates(start: dt.date, end: dt.date) -> list[dt.date]:
    """Decision 21/24: every primary-sample date in `[start, end]`."""
    return [d for d in exchange_session_dates(start, end) if d not in PRIMARY_SAMPLE_EXCLUSIONS]


def first_session_of_month(dates: list[dt.date]) -> dict[tuple[int, int], dt.date]:
    """Decision 24: for a list of governing/primary-sample calendar
    dates, the earliest date in each (year, month) -- the ranking date
    for that month's roster construction. Pure function, no DB access."""
    out: dict[tuple[int, int], dt.date] = {}
    for d in sorted(dates):
        key = (d.year, d.month)
        if key not in out:
            out[key] = d
    return out


def ranking_date_for_month(year: int, month: int) -> dt.date:
    """Decision 24: the governing ranking date for one specific calendar
    month -- the earliest exchange-session date in that month, per the
    governing calendar (not the primary-sample calendar: a ranking date
    is never `2021-02-24` in practice since that date is never the 1st
    of a month, but this function deliberately uses the governing
    calendar, exactly as AMENDMENT 11 LOG specifies, not the narrower
    primary-sample one)."""
    import calendar as _stdlib_calendar
    start = dt.date(year, month, 1)
    end = dt.date(year, month, _stdlib_calendar.monthrange(year, month)[1])
    sessions = exchange_session_dates(start, end)
    if not sessions:
        raise ValueError(f"no governing exchange session found in {year}-{month:02d}")
    return sessions[0]


# ---------------------------------------------------------------------
# Archive-coverage diagnostics -- explicitly separate from session truth.
# Nothing in this section may be used to decide whether a date is a
# governing or primary-sample session; it exists only to report how
# much `bars_1min` data exists for an already-determined session date,
# for monitoring/diagnostic purposes.
# ---------------------------------------------------------------------

def archive_coverage_diagnostics(con: duckdb.DuckDBPyConnection, d: dt.date) -> dict:
    """Diagnostic only: `bars_1min` row/entity/minute counts for date
    `d`, regardless of whether `d` is a governing session. A governing
    session with zero rows here is still a governing session -- this
    function never feeds back into `is_exchange_session` or any
    calendar-truth function above."""
    row = con.execute(
        """
        SELECT
            COUNT(*) AS n_rows,
            COUNT(DISTINCT entity_id) AS n_entities,
            COUNT(DISTINCT CASE
                WHEN CAST(ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:59'
                THEN CAST(ts AS TIME) END) AS n_min_in_window
        FROM bars_1min WHERE trade_date = ?
        """,
        [d],
    ).fetchone()
    return {
        "trade_date": d,
        "n_rows": row[0],
        "n_entities": row[1],
        "n_min_in_window": row[2],
        "is_exchange_session": is_exchange_session(d),
    }
