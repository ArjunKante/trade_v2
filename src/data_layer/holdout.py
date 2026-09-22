"""The sealed holdout, guarded in code, not by convention.

Sealed NOW (2026-09-19, before any Phase 2 factor is computed), 18 months
back. The prior project's holdout was compromised by an unchecked date
boundary in a throwaway diagnostic script that happened to swallow the
sealed window whole -- the mechanism existed only as a convention ("don't
query dates after X"), and nothing enforced it. Here it's a function every
date-bounded analysis must call, which raises rather than silently returning
data.

This module has exactly one authorized bypass path (`authorize_holdout=True`),
intended for exactly one future script that performs the single, real,
end-of-project holdout evaluation -- never a default, never set in a
diagnostic, never set twice.
"""
from __future__ import annotations

import datetime as dt

SEALED_AT = dt.date(2026, 9, 19)  # the date this seal was created
HOLDOUT_MONTHS = 18
SEALED_HOLDOUT_START = dt.date(2025, 3, 19)  # SEALED_AT minus 18 months, fixed permanently from here


class HoldoutViolationError(Exception):
    """Raised when an operation would touch data inside the sealed holdout window."""


def guard_date_range(start: dt.date, end: dt.date, authorize_holdout: bool = False) -> None:
    """Raise if [start, end] intersects the sealed window, unless explicitly
    authorized. Call this at the top of any function that bounds a query,
    a CV split, a factor computation, or a report by a date range."""
    if authorize_holdout:
        return
    if end >= SEALED_HOLDOUT_START:
        raise HoldoutViolationError(
            f"requested range end {end} intersects the sealed holdout "
            f"(>= {SEALED_HOLDOUT_START}). This is disallowed by default. "
            f"If this really is the one authorized end-of-project holdout "
            f"evaluation, pass authorize_holdout=True explicitly -- and only there."
        )


def clip_to_pre_holdout(dates) -> "object":
    """Convenience: filter an iterable/Series of dates to strictly before the
    sealed window. Does not need authorization since it can only ever narrow
    a range away from the holdout, never expand into it."""
    import pandas as pd
    s = pd.Series(list(dates))
    return s[pd.to_datetime(s) < pd.Timestamp(SEALED_HOLDOUT_START)]
