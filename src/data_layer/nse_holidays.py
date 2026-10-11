"""NSE's official CM-segment trading-holiday calendar -- the ground truth
for whether a weekday with no published bhavcopy is a genuine holiday or
something else.

BUGS.md Bug #13-adjacent: fibo_evening.py's backward-looking search for the
latest trading day hit 2026-10-09 (a Friday) marked 'no_data' in fetch_log,
and treated it as a confirmed holiday. It wasn't -- a backfill run had
fetched it at 00:23 local time that day, hours before the bhavcopy could
possibly be published, gotten a 404 for that reason alone, and
prices_nse.py cached that as a PERMANENT 'no_data' with no way to tell a
confirmed holiday apart from a premature/failed fetch attempt. Re-fetched
live: HTTP 200, a complete valid bhavcopy, 3687 real rows. This module is
the fix's other half -- `load_bhavcopy_to_duckdb` (prices_nse.py) only
writes a permanent 'no_data' when THIS calendar confirms the date really
is a holiday; every other 404 is logged as a retryable failure instead.

Source: data/raw/nse_cm_holidays.pkl, a dict of {year: set(dates)} fetched
directly from NSE in an earlier phase of this project, covering 2016-2026.
Not committed to git (data/ is gitignored) -- each environment that needs
this keeps its own copy; a missing file or an uncovered year is NEVER
silently treated as "not a holiday" (see HolidayCalendarMissing below) --
an unverifiable gap must fail safe, the same stance src/spread_monitor/
trading_day.py already takes for the live equivalent check.
"""
from __future__ import annotations

import datetime as dt
import pickle
from functools import lru_cache
from pathlib import Path

HOLIDAYS_PKL = Path(__file__).resolve().parents[2] / "data" / "raw" / "nse_cm_holidays.pkl"


class HolidayCalendarMissing(Exception):
    """Raised when the holiday master file is absent, or doesn't cover the
    requested year. Callers must treat this the same as "cannot confirm
    this is a holiday" -- never catch it and assume True or False."""


@lru_cache(maxsize=1)
def _load() -> dict[int, set[dt.date]]:
    if not HOLIDAYS_PKL.exists():
        raise HolidayCalendarMissing(f"{HOLIDAYS_PKL} not found -- cannot verify NSE holidays")
    with open(HOLIDAYS_PKL, "rb") as f:
        return pickle.load(f)


def is_nse_holiday(d: dt.date) -> bool:
    """True iff `d` is in NSE's official CM-segment holiday master for its
    year. Raises HolidayCalendarMissing if that year isn't covered by the
    master at all -- deliberately never falls back to False in that case,
    since an unverifiable year waved through as "confirmed not a holiday"
    is exactly the bug this module exists to prevent."""
    calendar = _load()
    if d.year not in calendar:
        raise HolidayCalendarMissing(f"NSE holiday master has no entry for year {d.year} (needed for {d})")
    return d in calendar[d.year]
