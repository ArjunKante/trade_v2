"""The sealed holdout guard, exercised directly -- including the exact
failure mode that compromised the prior project's holdout: a date range
that unintentionally reaches into the sealed window."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.holdout import guard_date_range, clip_to_pre_holdout, HoldoutViolationError, SEALED_HOLDOUT_START


def test_range_entirely_before_seal_is_allowed():
    guard_date_range(dt.date(2020, 1, 1), dt.date(2024, 12, 31))  # must not raise


def test_range_touching_seal_boundary_is_rejected():
    with pytest.raises(HoldoutViolationError):
        guard_date_range(dt.date(2024, 1, 1), SEALED_HOLDOUT_START)


def test_range_entirely_inside_seal_is_rejected():
    with pytest.raises(HoldoutViolationError):
        guard_date_range(dt.date(2025, 6, 1), dt.date(2025, 12, 31))


def test_authorize_flag_bypasses_explicitly():
    guard_date_range(dt.date(2020, 1, 1), dt.date(2026, 9, 19), authorize_holdout=True)  # must not raise


def test_clip_to_pre_holdout_drops_sealed_dates():
    dates = [dt.date(2024, 12, 31), dt.date(2025, 3, 18), dt.date(2025, 3, 19), dt.date(2025, 6, 1)]
    clipped = clip_to_pre_holdout(dates)
    assert len(clipped) == 2  # only 2024-12-31 and 2025-03-18 survive
