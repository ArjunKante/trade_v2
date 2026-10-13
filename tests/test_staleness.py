"""Regression test for BUGS.md Bug #13: daily ingestion silently stopped
for 13 trading days (2026-09-19 to 2026-10-07) with zero trace in
fetch_log, and nothing computed from the price panel noticed until a
downstream gap guard happened to crash on it. data_layer.staleness.
assert_data_current is the shared guard every entry point (Fibo watchlist,
momentum, screener, monitor) now calls instead of each re-implementing
this check -- this test fixes the exact gap from that incident as data,
not a synthetic placeholder, so the regression is tied to what actually
happened.
"""
import datetime as dt
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer import staleness as staleness_module
from data_layer.db import SCHEMA_SQL
from data_layer.staleness import assert_data_current, latest_trade_date, StaleDataError

ROW = "('{isin}', '{trade_date}', 'SYM', 'EQ', 1,1,1,1,1,1,1,1,1, '{trade_date}', now(), 'T', 1)"


def _warehouse_with_latest(latest: dt.date) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA_SQL)
    con.execute(f"INSERT INTO prices_eod VALUES {ROW.format(isin='ISIN1', trade_date=latest.isoformat())}")
    return con


def test_the_actual_13_day_gap_incident_is_refused():
    """2026-09-18 was the warehouse's latest day; 2026-10-08 is when the
    Fibo evening job ran and would otherwise have silently computed a
    watchlist across the 13-trading-day hole in between."""
    con = _warehouse_with_latest(dt.date(2026, 9, 18))
    with pytest.raises(StaleDataError):
        assert_data_current(con, as_of=dt.date(2026, 10, 8), max_staleness_days=3)


def test_one_day_lag_within_default_threshold_passes():
    """The ordinary case: today's bar hasn't been fetched yet, yesterday's
    is the latest -- this must NOT be treated as stale."""
    con = _warehouse_with_latest(dt.date(2026, 10, 7))
    latest = assert_data_current(con, as_of=dt.date(2026, 10, 8), max_staleness_days=3)
    assert latest == dt.date(2026, 10, 7)


def test_long_weekend_within_default_threshold_passes():
    """Friday's bar, checked the following Monday (3 calendar days) --
    exactly the margin max_staleness_days=3 exists to allow."""
    con = _warehouse_with_latest(dt.date(2026, 10, 2))  # a Friday
    latest = assert_data_current(con, as_of=dt.date(2026, 10, 5), max_staleness_days=3)  # the following Monday
    assert latest == dt.date(2026, 10, 2)


def test_exactly_one_day_past_threshold_is_refused():
    con = _warehouse_with_latest(dt.date(2026, 10, 1))
    with pytest.raises(StaleDataError):
        assert_data_current(con, as_of=dt.date(2026, 10, 5), max_staleness_days=3)


def test_empty_prices_eod_is_refused_not_treated_as_fresh():
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA_SQL)
    assert latest_trade_date(con) is None
    with pytest.raises(StaleDataError):
        assert_data_current(con, as_of=dt.date(2026, 10, 8))


class _FakeDateTimeOnUTCHost(dt.datetime):
    """See tests/test_fibo_live_clock.py's identical fake -- simulates a
    host OS clock set to UTC. now() with no tz returns the naive UTC
    wall-clock reading; now(tz) still converts the same real instant
    correctly."""

    # 2026-10-08 19:00 UTC == 2026-10-09 00:30 IST -- a naive (UTC-as-
    # local) reading says "2026-10-08" while the true IST calendar date
    # is already 2026-10-09, one day later.
    _real_instant = dt.datetime(2026, 10, 8, 19, 0, 0, tzinfo=dt.timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls._real_instant.replace(tzinfo=None)
        return cls._real_instant.astimezone(tz)


def test_default_as_of_is_ist_correct_even_if_host_clock_is_utc(monkeypatch):
    """Regression for the GitHub Actions migration: assert_data_current's
    default `as_of` (every real caller omits it) must be today's date IN
    IST, not the host machine's own local "today". Warehouse's latest
    trading day is 2026-10-07; the true IST "as_of" is 2026-10-09 (a
    1-day gap, within the 3-day default tolerance). A regression to a
    bare dt.date.today() on a UTC-clock host would instead compute
    as_of=2026-10-08, still within tolerance here too by coincidence of
    the gap size -- so this test picks a gap that is ONLY within
    tolerance under the correct IST date, to actually discriminate the
    two."""
    con = _warehouse_with_latest(dt.date(2026, 10, 5))
    monkeypatch.setattr(staleness_module.dt, "datetime", _FakeDateTimeOnUTCHost)
    # Correct (IST) as_of=2026-10-09 -> gap=4 days -> OUTSIDE max_staleness_days=3,
    # so this must raise. A bug that used the naive UTC date (2026-10-08,
    # gap=3) would wrongly let this pass instead.
    with pytest.raises(StaleDataError):
        assert_data_current(con, max_staleness_days=3)
