"""src/fibo_live/clock.py: run_mode must be detected from the wall clock
relative to the trade date, never passed in as a flag."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live import clock as clock_module
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


class _FakeDateTimeOnUTCHost(dt.datetime):
    """Stands in for a host whose OS clock is set to UTC (a GitHub
    Actions runner) rather than IST (the laptop). `now()` with no tz
    argument returns the naive UTC wall-clock reading, exactly as such a
    host's local clock would -- `now(tz)` still correctly converts the
    SAME real instant into whatever tz is asked for. This is the one
    distinction that matters: code that calls bare dt.datetime.now() gets
    fooled by this fake; code that calls dt.datetime.now(IST) does not,
    regardless of what the host's own clock thinks "now" is."""

    # 2026-10-13 20:00 UTC == 2026-10-14 01:30 IST -- deliberately chosen
    # to straddle midnight IST, so a naive (UTC-read-as-local) now() lands
    # on the WRONG CALENDAR DAY entirely, not just the wrong hour. This is
    # exactly the failure mode a same-day-only time check would miss.
    _real_instant = dt.datetime(2026, 10, 13, 20, 0, 0, tzinfo=dt.timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls._real_instant.replace(tzinfo=None)
        return cls._real_instant.astimezone(tz)


def test_default_now_is_ist_correct_even_if_host_clock_is_utc(monkeypatch):
    """Regression for the GitHub Actions migration: detect_run_mode's
    default (no `now` passed, as every real caller does) must compute
    "now" as an explicit IST conversion, never the host's own local
    clock. Simulates a UTC-clock host at an instant that is already
    2026-10-14 in IST but still 2026-10-13 in a naive/UTC reading -- if
    the code under test ever regresses to a bare dt.datetime.now(), this
    fails by classifying trade_date=2026-10-14 as REPLAY (wrong day)
    instead of LIVE."""
    monkeypatch.setattr(clock_module.dt, "datetime", _FakeDateTimeOnUTCHost)
    assert detect_run_mode(dt.date(2026, 10, 14)) == LIVE
