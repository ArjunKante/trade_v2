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


# ---------------------------------------------------------------------------
# Second momentum holdout window.
#
# Declared 2026-11-16, RE-DECLARED 2026-11-17 (FINDINGS.md Section 7) after
# finding the first declaration had already been partially read: one
# uncorrected script run printed the 2026-07-23 rebalance's own composition
# and realized return before the seal existed, and four unpinned
# "bug11_check" scripts independently leaked the same rebalance a second
# time by reproducing an inflated margin (7.31 against the recorded 3.64)
# that is only explainable by that rebalance's own strongly-positive
# relative return. 2026-07-23 is therefore EXCLUDED, permanently, from this
# seal -- sealing it now would be sealing data already seen twice, and it
# carries no evidential weight going forward (see FINDINGS.md Section 7 for
# the actual figures, recorded as contaminated observations, not as a
# result).
#
# The new seal starts at the first rebalance AFTER the contaminated one:
# 2026-10-23 (63-trading-day cadence from 2026-07-23, confirmed against the
# live panel, not assumed). A function, not a comment, enforces this --
# the same discipline SEALED_HOLDOUT_START above already uses.
# ---------------------------------------------------------------------------

MOMENTUM_WINDOW_2_DECLARED = dt.date(2026, 11, 17)
MOMENTUM_WINDOW_2_CONTAMINATED_REBALANCE = dt.date(2026, 7, 23)
MOMENTUM_WINDOW_2_START = dt.date(2026, 10, 23)
MOMENTUM_WINDOW_2_MIN_REBALANCES = 5


class MomentumWindow2ViolationError(Exception):
    """Raised when an operation would touch a rebalance date inside the
    second sealed momentum window."""


def guard_momentum_rebalance_dates(dates, authorize_momentum_window_2: bool = False) -> None:
    """Raise if any rebalance date in `dates` falls on or after
    MOMENTUM_WINDOW_2_START, unless explicitly authorized. Call this on
    the candidate rebalance-date list of any momentum evaluation, the
    same way `guard_date_range` is called on a bare date range. The
    contaminated 2026-07-23 rebalance is not inside this window (it is
    earlier) and this guard does not catch it -- use
    `clip_momentum_rebalance_dates` to drop that one too."""
    if authorize_momentum_window_2:
        return
    bad = sorted(d for d in dates if _as_ts(d) >= _as_ts(MOMENTUM_WINDOW_2_START))
    if bad:
        raise MomentumWindow2ViolationError(
            f"{len(bad)} rebalance date(s) >= {MOMENTUM_WINDOW_2_START} requested "
            f"(first: {bad[0]}) -- inside the second sealed momentum window "
            f"(FINDINGS.md Section 7). Disallowed by default. If this is really "
            f"the one authorized evaluation (>={MOMENTUM_WINDOW_2_MIN_REBALANCES} "
            f"rebalances accumulated, preregistration written first), pass "
            f"authorize_momentum_window_2=True explicitly -- and only there."
        )


def clip_momentum_rebalance_dates(dates) -> list:
    """Convenience: filter an iterable of rebalance dates to exclude BOTH
    the contaminated 2026-07-23 rebalance AND anything on or after the
    second sealed window's start. Never needs authorization -- it only
    ever narrows, the same convention as `clip_to_pre_holdout`."""
    contaminated = _as_ts(MOMENTUM_WINDOW_2_CONTAMINATED_REBALANCE)
    start = _as_ts(MOMENTUM_WINDOW_2_START)
    return [d for d in dates if _as_ts(d) != contaminated and _as_ts(d) < start]


def _as_ts(d):
    import pandas as pd
    return pd.Timestamp(d)
