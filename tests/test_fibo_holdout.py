"""The Fibo module's sealed test-window guard, exercised directly -- same
discipline as tests/test_holdout_guard.py for the main project's guard."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.holdout import guard_date_range, clip_to_development, FiboHoldoutViolationError, SEALED_TEST_START


def test_range_entirely_before_seal_is_allowed():
    guard_date_range(dt.date(2016, 10, 4), dt.date(2022, 12, 31))  # must not raise


def test_range_touching_seal_boundary_is_rejected():
    with pytest.raises(FiboHoldoutViolationError):
        guard_date_range(dt.date(2022, 1, 1), SEALED_TEST_START)


def test_range_entirely_inside_seal_is_rejected():
    with pytest.raises(FiboHoldoutViolationError):
        guard_date_range(dt.date(2024, 1, 1), dt.date(2024, 12, 31))


def test_authorize_flag_bypasses_explicitly():
    guard_date_range(dt.date(2016, 10, 4), dt.date(2026, 9, 18), authorize_holdout=True)  # must not raise


def test_clip_to_development_drops_sealed_dates():
    dates = [dt.date(2022, 12, 30), dt.date(2022, 12, 31), dt.date(2023, 1, 1), dt.date(2023, 6, 1)]
    clipped = clip_to_development(dates)
    assert len(clipped) == 2  # only 2022-12-30 and 2022-12-31 survive
