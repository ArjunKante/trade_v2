"""BUGS.md Bug #30's structural fix: data_layer.price_gap_detector finds
holes INSIDE prices_eod's own history that staleness.py's tail-only
check cannot see. Fixes the real incident's exact shape as data, same
convention as test_staleness.py: the 10 real missing days
(2026-10-27..30, 2026-11-03/06/09/11/12/13) that sat undetected for up
to three weeks before Bug #30 traced the zero-candidate screener back
to them.

is_nse_holiday is monkeypatched directly on the module (price_gap_
detector.is_nse_holiday is a name bound at import time, same shape
test_holiday_week_oct2026.py already works around) so this suite never
depends on which holiday calendar file happens to be present on a given
machine.
"""
import datetime as dt
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer import price_gap_detector as gap_module  # noqa: E402
from data_layer.db import SCHEMA_SQL  # noqa: E402
from data_layer.nse_holidays import HolidayCalendarMissing  # noqa: E402
from data_layer.price_gap_detector import (  # noqa: E402
    REASON_MISSING,
    REASON_UNVERIFIABLE_YEAR,
    find_missing_trading_days,
)

ROW = "('{isin}', '{trade_date}', 'SYM', 'EQ', 1,1,1,1,1,1,1,1,1, '{trade_date}', now(), 'T', 1)"


def _warehouse_with_dates(dates: list[dt.date]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA_SQL)
    for i, d in enumerate(dates):
        con.execute(f"INSERT INTO prices_eod VALUES {ROW.format(isin=f'ISIN{i}', trade_date=d.isoformat())}")
    return con


def test_no_gaps_when_every_weekday_present(monkeypatch):
    monkeypatch.setattr(gap_module, "is_nse_holiday", lambda d: False)
    dates = [dt.date(2026, 11, 2), dt.date(2026, 11, 3), dt.date(2026, 11, 4),
             dt.date(2026, 11, 5), dt.date(2026, 11, 6)]  # Mon-Fri, no holidays
    con = _warehouse_with_dates(dates)
    assert find_missing_trading_days(con) == []


def test_the_actual_10_day_bug_30_incident_is_found(monkeypatch):
    """Reproduces the real shape: prices_eod has 2026-10-26 and 2026-11-17
    (and nothing is a holiday in between), with the 10 real gap dates
    absent. All 10 must be reported, nothing else."""
    monkeypatch.setattr(gap_module, "is_nse_holiday", lambda d: False)
    present = [dt.date(2026, 10, 26), dt.date(2026, 10, 31), dt.date(2026, 11, 2),
               dt.date(2026, 11, 4), dt.date(2026, 11, 5), dt.date(2026, 11, 10),
               dt.date(2026, 11, 16), dt.date(2026, 11, 17)]
    con = _warehouse_with_dates(present)
    found = {m.trade_date for m in find_missing_trading_days(con)}
    expected = {
        dt.date(2026, 10, 27), dt.date(2026, 10, 28), dt.date(2026, 10, 29), dt.date(2026, 10, 30),
        dt.date(2026, 11, 3), dt.date(2026, 11, 6), dt.date(2026, 11, 9),
        dt.date(2026, 11, 11), dt.date(2026, 11, 12), dt.date(2026, 11, 13),
    }
    assert found == expected
    assert all(m.reason == REASON_MISSING for m in find_missing_trading_days(con))


def test_a_confirmed_holiday_is_not_reported_as_missing(monkeypatch):
    holiday = dt.date(2026, 11, 4)
    monkeypatch.setattr(gap_module, "is_nse_holiday", lambda d: d == holiday)
    dates = [dt.date(2026, 11, 2), dt.date(2026, 11, 3), dt.date(2026, 11, 5), dt.date(2026, 11, 6)]
    con = _warehouse_with_dates(dates)
    assert find_missing_trading_days(con) == []


def test_weekend_gaps_are_never_reported(monkeypatch):
    """Sat/Sun have no bhavcopy and are not in the holiday master -- this
    must never flag them; only Mon-Fri absences count."""
    monkeypatch.setattr(gap_module, "is_nse_holiday", lambda d: False)
    dates = [dt.date(2026, 11, 6), dt.date(2026, 11, 9)]  # Fri, then the following Mon
    con = _warehouse_with_dates(dates)
    assert find_missing_trading_days(con) == []


def test_unverifiable_year_is_reported_distinctly_not_silently_skipped(monkeypatch):
    def _raise(d):
        raise HolidayCalendarMissing(f"no entry for {d.year}")
    monkeypatch.setattr(gap_module, "is_nse_holiday", _raise)
    dates = [dt.date(2026, 11, 2), dt.date(2026, 11, 6)]
    con = _warehouse_with_dates(dates)
    found = find_missing_trading_days(con)
    found_dates = {m.trade_date for m in found}
    assert found_dates == {dt.date(2026, 11, 3), dt.date(2026, 11, 4), dt.date(2026, 11, 5)}
    assert all(m.reason == REASON_UNVERIFIABLE_YEAR for m in found)


def test_empty_prices_eod_reports_nothing():
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA_SQL)
    assert find_missing_trading_days(con) == []
