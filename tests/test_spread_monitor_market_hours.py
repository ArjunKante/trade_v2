"""Asserts the market-hours guard blocks an out-of-hours run and allows
an in-hours one."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spread_monitor.market_hours import IST, check_market_hours


def test_blocks_before_market_open():
    before_open = dt.datetime(2026, 10, 5, 9, 0, 0, tzinfo=IST)  # Monday, 09:00
    ok, reason = check_market_hours(before_open)
    assert ok is False
    assert "outside market hours" in reason


def test_blocks_after_market_close():
    after_close = dt.datetime(2026, 10, 5, 16, 0, 0, tzinfo=IST)  # Monday, 16:00
    ok, reason = check_market_hours(after_close)
    assert ok is False
    assert "outside market hours" in reason


def test_blocks_on_weekend():
    saturday = dt.datetime(2026, 10, 3, 11, 0, 0, tzinfo=IST)
    ok, reason = check_market_hours(saturday)
    assert ok is False
    assert "weekend" in reason


def test_allows_during_market_hours():
    during = dt.datetime(2026, 10, 5, 11, 31, 0, tzinfo=IST)  # Monday, 11:31
    ok, reason = check_market_hours(during)
    assert ok is True
    assert reason == ""


def test_session_boundaries_fall_inside_the_open_close_guards():
    # 09:15 and 15:30 are the session's literal open/close, but both now
    # fall inside the 15-minute guard windows and should be refused.
    at_open = dt.datetime(2026, 10, 5, 9, 15, 0, tzinfo=IST)
    at_close = dt.datetime(2026, 10, 5, 15, 30, 0, tzinfo=IST)
    assert check_market_hours(at_open)[0] is False
    assert check_market_hours(at_close)[0] is False


def test_naive_datetime_is_treated_as_ist():
    naive_during = dt.datetime(2026, 10, 5, 11, 31, 0)
    ok, _ = check_market_hours(naive_during)
    assert ok is True


def test_blocks_within_15_minutes_of_open():
    just_after_open = dt.datetime(2026, 10, 5, 9, 29, 59, tzinfo=IST)
    ok, reason = check_market_hours(just_after_open)
    assert ok is False
    assert "too close to open" in reason


def test_allows_right_after_open_guard_ends():
    at_guard_end = dt.datetime(2026, 10, 5, 9, 30, 0, tzinfo=IST)
    ok, reason = check_market_hours(at_guard_end)
    assert ok is True
    assert reason == ""


def test_blocks_within_15_minutes_of_close():
    just_before_close = dt.datetime(2026, 10, 5, 15, 15, 0, tzinfo=IST)
    ok, reason = check_market_hours(just_before_close)
    assert ok is False
    assert "too close to close" in reason


def test_allows_right_before_close_guard_starts():
    at_guard_start = dt.datetime(2026, 10, 5, 15, 14, 59, tzinfo=IST)
    ok, reason = check_market_hours(at_guard_start)
    assert ok is True
    assert reason == ""
