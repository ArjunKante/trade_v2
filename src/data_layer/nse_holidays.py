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
this keeps its own copy.

FALLBACK, for environments that don't: data/raw/nse_cm_holidays_fallback.json
is a trimmed copy of the SAME source (dates only -- the pkl carries no
holiday names either, so none are lost by trimming), covering only the
year(s) it was generated for (2026, as of this fallback's creation --
see scripts/fibo_morning.py's GitHub Actions migration). It IS committed
(.gitignore carves out this one path the same way it does for
data/fibo_live/v1/events.jsonl) specifically so a GitHub Actions
runner's fresh checkout -- which never has the full pkl -- still has
something to confirm a holiday against. `_load` prefers the full pkl
when present (it covers more years and is the laptop's own source of
truth) and uses the fallback only when the pkl is absent.

A missing file (both absent) or an uncovered year is NEVER silently
treated as "not a holiday" (see HolidayCalendarMissing below) -- an
unverifiable gap must fail safe, the same stance src/spread_monitor/
trading_day.py already takes for the live equivalent check. Callers
that want "assume ordinary trading day when unverifiable" instead (e.g.
scripts/fibo_morning.py's previous_trading_day) must choose that
explicitly at the call site, by catching HolidayCalendarMissing
themselves -- this module never makes that choice for them.
"""
from __future__ import annotations

import datetime as dt
import json
import pickle
from functools import lru_cache
from pathlib import Path

HOLIDAYS_PKL = Path(__file__).resolve().parents[2] / "data" / "raw" / "nse_cm_holidays.pkl"
HOLIDAYS_FALLBACK_JSON = Path(__file__).resolve().parents[2] / "data" / "raw" / "nse_cm_holidays_fallback.json"


class HolidayCalendarMissing(Exception):
    """Raised when the holiday master file is absent, or doesn't cover the
    requested year. Callers must treat this the same as "cannot confirm
    this is a holiday" -- never catch it and assume True or False."""


@lru_cache(maxsize=1)
def _load() -> dict[int, set[dt.date]]:
    if HOLIDAYS_PKL.exists():
        with open(HOLIDAYS_PKL, "rb") as f:
            return pickle.load(f)
    if HOLIDAYS_FALLBACK_JSON.exists():
        raw = json.loads(HOLIDAYS_FALLBACK_JSON.read_text(encoding="utf-8"))
        return {int(year): {dt.date.fromisoformat(s) for s in dates} for year, dates in raw.items()}
    raise HolidayCalendarMissing(
        f"neither {HOLIDAYS_PKL} nor {HOLIDAYS_FALLBACK_JSON} exists -- cannot verify NSE holidays"
    )


def is_nse_holiday(d: dt.date) -> bool:
    """True iff `d` is in NSE's official CM-segment holiday master for its
    year (full pkl if present, else the committed fallback JSON). Raises
    HolidayCalendarMissing if that year isn't covered by whichever
    source was loaded -- deliberately never falls back to False in that
    case, since an unverifiable year waved through as "confirmed not a
    holiday" is exactly the bug this module exists to prevent."""
    calendar = _load()
    if d.year not in calendar:
        raise HolidayCalendarMissing(f"NSE holiday master has no entry for year {d.year} (needed for {d})")
    return d in calendar[d.year]
