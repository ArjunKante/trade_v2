"""Decisions 11, 22: non-overlapping signal schedule and TOD buckets."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag.schedule import (
    tod_bucket,
    non_overlapping_schedule,
    all_schedules,
    SIGNAL_END_MINUTE_ANCHOR,
    SESSION_END,
)


def test_signal_end_anchor_is_0919():
    assert SIGNAL_END_MINUTE_ANCHOR == dt.time(9, 19)


def test_tod_bucket_opening_30():
    assert tod_bucket(dt.time(9, 15)) == "opening_30"
    assert tod_bucket(dt.time(9, 44)) == "opening_30"


def test_tod_bucket_closing_30():
    assert tod_bucket(dt.time(15, 0)) == "closing_30"
    assert tod_bucket(dt.time(15, 29)) == "closing_30"


def test_tod_bucket_midday():
    assert tod_bucket(dt.time(12, 0)) == "midday"
    assert tod_bucket(dt.time(9, 45)) == "midday"
    assert tod_bucket(dt.time(14, 59)) == "midday"


def test_schedule_h5_spacing_is_10_minutes():
    sched = non_overlapping_schedule(5)
    assert sched[0] == dt.time(9, 19)
    assert sched[1] == dt.time(9, 29)
    assert sched[2] == dt.time(9, 39)


def test_schedule_h60_spacing_is_65_minutes():
    sched = non_overlapping_schedule(60)
    assert sched[0] == dt.time(9, 19)
    assert sched[1] == dt.time(10, 24)


def test_schedule_last_eligible_t_satisfies_t_plus_h_within_session():
    for h in (5, 15, 30, 60):
        sched = non_overlapping_schedule(h)
        last_t = sched[-1]
        last_t_plus_h = (dt.datetime.combine(dt.date(2000, 1, 1), last_t)
                          + dt.timedelta(minutes=h)).time()
        assert last_t_plus_h <= SESSION_END, f"h={h}: {last_t_plus_h} > {SESSION_END}"
        # the NEXT slot (one spacing further) would have violated it
        next_t = (dt.datetime.combine(dt.date(2000, 1, 1), last_t)
                  + dt.timedelta(minutes=h + 5)).time()
        next_t_plus_h = (dt.datetime.combine(dt.date(2000, 1, 1), next_t)
                         + dt.timedelta(minutes=h)).time()
        assert next_t_plus_h > SESSION_END


def test_no_duplicate_or_overlapping_slots_within_a_horizon():
    for h, sched in all_schedules().items():
        assert len(sched) == len(set(sched)), f"duplicate slot in horizon {h}"
        assert sched == sorted(sched)


def test_all_four_horizons_present():
    schedules = all_schedules()
    assert set(schedules.keys()) == {5, 15, 30, 60}
    for h, sched in schedules.items():
        assert len(sched) > 0
