"""The sealed test window for the options fair-pricing study, guarded in
code, not by convention -- same mechanism as src/data_layer/holdout.py's
HoldoutViolationError, applied to this study's own development/test
split instead of Fibo/momentum's sealed holdout (a different boundary,
a different study, the same discipline: "don't query dates after X" must
be enforced by something that raises, not just written down).

Sealed NOW (2026-10-12, before any straddle-vs-realized-move ratio has
been computed, per PREREGISTRATION_OPTIONS.md):
    DEVELOPMENT: 2016-01 to 2022-12 (84 months -- includes the 2020-03
                 COVID crash, this study's one large-tail observation)
    TEST (sealed): 2023-01 to 2026-09 (45 months -- contains NO crash of
                 2020's scale; see PREREGISTRATION_OPTIONS.md's stated
                 limitation -- the test window cannot evaluate crash
                 behaviour, only development can)

This module has exactly one authorized bypass path
(`authorize_test=True`), intended for exactly one future script that
performs the single, real, end-of-study test-window evaluation -- never
a default, never set in exploratory/development code, never set twice.
"""
from __future__ import annotations

import datetime as dt

SEALED_AT = dt.date(2026, 10, 12)  # the date this seal was created

DEV_START = dt.date(2016, 1, 1)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 30)


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside the sealed test window."""


def guard_date_range(start: dt.date, end: dt.date, authorize_test: bool = False) -> None:
    """Raise if [start, end] intersects the sealed TEST window, unless
    explicitly authorized. Call this at the top of any function that
    bounds a query, a straddle/realized-move computation, or a report by
    a date range in this study."""
    if authorize_test:
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
    the development window. Does not need authorization since it can
    only ever narrow a range away from the sealed test window, never
    expand into it."""
    import pandas as pd
    s = pd.Series(list(dates))
    ts = pd.to_datetime(s)
    return s[(ts >= pd.Timestamp(DEV_START)) & (ts <= pd.Timestamp(DEV_END))]
