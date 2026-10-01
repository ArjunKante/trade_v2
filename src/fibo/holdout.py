"""The Fibo module's own sealed TEST window -- guarded in code, not by
convention, the same discipline data_layer.holdout established for the
main project's historical holdout (a function every date-bounded backtest
must call, which raises rather than silently returning data).

Frozen 2026-09-28 (PREREGISTRATION_FIBO.md Section 5), decided once Step
1's data-depth report existed, not before:
    DEVELOPMENT : 2016-10-04 (the earliest date Angel One's SmartAPI
                  actually has 1-minute/15-minute history for this study's
                  universe, measured in Step 1 -- not this project's daily
                  warehouse's own 2016-01-01 start, which predates Angel
                  One's intraday archive by ~9 months) through 2022-12-31.
    TEST (SEALED): 2023-01-01 through 2026-09-18. Read once, at the single
                  end-of-project evaluation, never before, never twice.

THIS IS A DIFFERENT, UNRELATED SEALED WINDOW from data_layer.holdout's
SEALED_HOLDOUT_START (2025-03-19), which FINDINGS.md Section 7 RETIRED for
every hypothesis sharing the main daily warehouse. That retirement does not
touch this window: this is a fresh seal, created now, for this hypothesis
only, using its own separate intraday data store
(data/fibo_intraday.duckdb) that the retired window's own ledger never
covered. The two windows happen to overlap in calendar time
(2025-03-19 onward), which is recorded, not hidden, but they are governed
independently -- the Fibo test window is not "reopened" by the daily
window's retirement, and the daily window's retirement is not affected by
this new seal.
"""
from __future__ import annotations

import datetime as dt

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)
SEALED_TEST_START = dt.date(2023, 1, 1)
SEALED_AT = dt.date(2026, 9, 28)  # the date this seal was created


class FiboHoldoutViolationError(Exception):
    """Raised when an operation would touch data inside the Fibo module's sealed test window."""


def guard_date_range(start: dt.date, end: dt.date, authorize_holdout: bool = False) -> None:
    """Raise if [start, end] intersects the sealed test window (>=
    SEALED_TEST_START), unless explicitly authorized. Call this at the top
    of any function that bounds a Fibo backtest query, a signal-generation
    walk, or a report by a date range."""
    if authorize_holdout:
        return
    if end >= SEALED_TEST_START:
        raise FiboHoldoutViolationError(
            f"requested range end {end} intersects the Fibo module's sealed test "
            f"window (>= {SEALED_TEST_START}). This is disallowed by default. "
            f"If this really is the one authorized end-of-project test evaluation, "
            f"pass authorize_holdout=True explicitly -- and only there."
        )


def clip_to_development(dates) -> "object":
    """Convenience: filter an iterable/Series of dates to strictly before
    the sealed test window. Does not need authorization since it can only
    ever narrow a range away from the test window, never expand into it."""
    import pandas as pd
    s = pd.Series(list(dates))
    return s[pd.to_datetime(s) < pd.Timestamp(SEALED_TEST_START)]
