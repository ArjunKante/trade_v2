"""src/fibo_live/clock.py: run_mode must be detected from the wall clock
relative to the trade date, never passed in as a flag."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live.clock import detect_run_mode, LIVE, REPLAY


def test_same_day_before_close_is_live():
    assert detect_run_mode(dt.date(2026, 10, 9), now=dt.datetime(2026, 10, 9, 10, 30)) == LIVE


def test_same_day_right_before_close_boundary_is_live():
    assert detect_run_mode(dt.date(2026, 10, 9), now=dt.datetime(2026, 10, 9, 15, 14, 59)) == LIVE


def test_same_day_at_close_is_replay():
    assert detect_run_mode(dt.date(2026, 10, 9), now=dt.datetime(2026, 10, 9, 15, 15, 0)) == REPLAY


def test_same_day_after_close_is_replay():
    assert detect_run_mode(dt.date(2026, 10, 9), now=dt.datetime(2026, 10, 9, 20, 0)) == REPLAY


def test_same_day_before_market_open_is_still_live():
    """Outcome is genuinely unknown even before the open -- nothing has
    happened yet on the trade date."""
    assert detect_run_mode(dt.date(2026, 10, 9), now=dt.datetime(2026, 10, 9, 7, 0)) == LIVE


def test_a_later_day_is_replay():
    assert detect_run_mode(dt.date(2026, 10, 8), now=dt.datetime(2026, 10, 9, 10, 0)) == REPLAY


def test_defaults_to_real_now_when_not_given():
    # Not asserting a specific value (depends on when the test runs) --
    # only that it returns one of the two valid modes without error.
    assert detect_run_mode(dt.date.today()) in (LIVE, REPLAY)
