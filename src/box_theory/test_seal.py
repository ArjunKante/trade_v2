"""The sealed TEST window for the Box Theory study, guarded in code, not by
convention -- same mechanism as `src/options_history/test_seal.py`
(itself modeled on `src/data_layer/holdout.py::HoldoutViolationError`),
given its OWN copy here per PREREGISTRATION_BOX.md Section 0: this study's
DEV/TEST boundary is its own, unrelated to Fibo's sealed holdout or
options' sealed test window -- no state, no log file, and no
authorization flag is shared with either.

Sealed NOW (2026-10-16, before any box-theory trade, R value, or null has
been computed, per PREREGISTRATION_BOX.md):
    DEV:  2016-10-04 to 2022-12-31
    TEST (sealed): 2023-01-01 to 2026-09-18

Exactly one authorized bypass path (`authorize_test=True`), intended for
exactly one future script that performs the single, real, end-of-study
test-window evaluation -- never a default, never set in exploratory code,
never set twice.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

SEALED_AT = dt.date(2026, 10, 16)

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 18)

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "box_theory" / "test_window_access_log.txt"


class TestWindowViolationError(Exception):
    """Raised when an operation would touch data inside the sealed test window."""


def _log_test_window_access(start: dt.date, end: dt.date, caller: str, reason: str) -> None:
    """Append-only audit trail of every authorized bypass, called from
    guard_date_range itself so it can never be skipped while the bypass
    is exercised -- same convention as options_history's own log."""
    ACCESS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ACCESS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            f"{dt.datetime.now().isoformat()} | range=[{start},{end}] | caller={caller} | "
            f"authorize_test=True | {reason}\n"
        )


def guard_date_range(start: dt.date, end: dt.date, authorize_test: bool = False,
                      caller: str = "", reason: str = "") -> None:
    """Raise if [start, end] intersects the sealed TEST window, unless
    explicitly authorized. Call this at the top of any function that
    bounds a query or a backtest/report by a date range in this study.
    When `authorize_test=True` is actually exercised (the range really
    does intersect the sealed window), the access is appended to
    ACCESS_LOG_PATH -- `caller`/`reason` should describe what is being
    computed and why."""
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
    the development window. Never needs authorization -- can only narrow
    a range away from the sealed test window, never expand into it."""
    import pandas as pd
    s = pd.Series(list(dates))
    ts = pd.to_datetime(s)
    return s[(ts >= pd.Timestamp(DEV_START)) & (ts <= pd.Timestamp(DEV_END))]
