"""The sealed TEST window for the Fair Value Gap study, guarded in code --
its OWN instance per `PREREGISTRATION_FVG.md` Section 0/9, not shared with
`box_theory.test_seal` or any Fibo seal (same reasoning box theory's own
module gives for not sharing with Fibo's: this study's DEV/TEST boundary
is its own, even though the dates happen to be numerically identical to
box theory's).

Sealed NOW (2026-10-19, before any FVG gap, trade, or R value has been
computed, per PREREGISTRATION_FVG.md):
    DEV:  2016-10-04 to 2022-12-31
    TEST (sealed): 2023-01-01 to 2026-09-18
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

SEALED_AT = dt.date(2026, 10, 19)

DEV_START = dt.date(2016, 10, 4)
DEV_END = dt.date(2022, 12, 31)

TEST_START = dt.date(2023, 1, 1)
TEST_END = dt.date(2026, 9, 18)

ACCESS_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "fvg" / "test_window_access_log.txt"


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
    return s[(ts >= pd.Timestamp(DEV_START)) & (ts <= pd.Timestamp(DEV_END))]
