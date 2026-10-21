"""The sealed TEST window for the IPO listing-day study -- same mechanism
as `box_theory.test_seal` / `options_history.test_seal`
(`guard_date_range`, an `authorize_test` bypass exercised at most once,
its own append-only access log), given its own copy per
`PREREGISTRATION_IPO.md` Section 7: no state shared with any other
study's seal.

UNLIKE every other seal in this project (see `PREREGISTRATION_IPO.md`'s
own "Provenance" section): this dataset has never been touched by any
prior study, so this TEST window is a genuine, first-exposure holdout,
not a forward-only discipline device. Enforced accordingly: no slack.

Sealed NOW (2026-10-22, the moment Phase 1's fetch AND the post-
validation exclusions completed, before any IPO trade, R value, or null
has been computed), on the 498 listings that fetched 'OK' AND were not
excluded for a known data defect (`ipo_listing.exclusions.
KNOWN_DATA_DEFECTS` -- 3 listings dropped for a single-tick low-price
artifact; `data/ipo_listing/phase1_fetch_summary.json`), split
chronologically by listing date, earlier 60% / most recent 40%:
    DEV:  listings through 2024-11-29 (299 listings)
    TEST (sealed): listings from 2024-12-06 onward (199 listings)
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

SEALED_AT = dt.date(2026, 10, 22)

DEV_END = dt.date(2024, 11, 29)
TEST_START = dt.date(2024, 12, 6)

N_DEV = 299
N_TEST = 199

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "ipo_listing" / "test_window_access_log.txt"


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside the sealed test window."""


def _log_test_window_access(start: dt.date, end: dt.date, caller: str, reason: str) -> None:
    ACCESS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ACCESS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            f"{dt.datetime.now().isoformat()} | range=[{start},{end}] | caller={caller} | "
            f"authorize_test=True | {reason}\n"
        )


def guard_date_range(start: dt.date, end: dt.date, authorize_test: bool = False,
                      caller: str = "", reason: str = "") -> None:
    """Raise if [start, end] intersects the sealed TEST window, unless
    explicitly authorized."""
    if authorize_test:
        if end >= TEST_START:
            _log_test_window_access(start, end, caller or "(caller not specified)",
                                     reason or "(reason not specified)")
        return
    if end >= TEST_START:
        raise TestWindowViolationError(
            f"requested range end {end} intersects the sealed test window "
            f"(>= {TEST_START}). This is disallowed by default. If this "
            f"really is the one authorized end-of-study test evaluation, "
            f"pass authorize_test=True explicitly -- and only there."
        )


def clip_to_development(dates) -> "object":
    """Convenience: filter an iterable/Series of dates to strictly inside
    the development window. Never needs authorization."""
    import pandas as pd
    s = pd.Series(list(dates))
    ts = pd.to_datetime(s)
    return s[ts <= pd.Timestamp(DEV_END)]
