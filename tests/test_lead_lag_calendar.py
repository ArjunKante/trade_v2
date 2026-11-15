"""Decisions 10, 21, 24: governing exchange-session calendar --
corrected to be a pure function of the NSE holiday master and the
approved special-session list, with NO dependency on `bars_1min` or
`prices_eod` row presence."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag.calendar import (
    is_exchange_session,
    is_primary_sample_date,
    exchange_session_dates,
    primary_sample_dates,
    first_session_of_month,
    ranking_date_for_month,
    GOVERNING_SPECIAL_SESSIONS,
    PRIMARY_SAMPLE_EXCLUSIONS,
    HolidayCalendarMissing,
)
from data_layer.nse_holidays import is_nse_holiday


def test_ordinary_weekday_session():
    d = dt.date(2024, 6, 10)  # Monday, not a holiday
    assert not is_nse_holiday(d)
    assert is_exchange_session(d) is True


def test_nse_holiday_is_not_a_session():
    # Republic Day is a fixed NSE holiday every year
    d = dt.date(2024, 1, 26)
    assert is_nse_holiday(d) is True
    assert is_exchange_session(d) is False


def test_ordinary_weekend_is_not_a_session():
    d = dt.date(2024, 6, 8)  # Saturday, not a special session
    assert d.weekday() >= 5
    assert d not in GOVERNING_SPECIAL_SESSIONS
    assert is_exchange_session(d) is False


def test_all_four_weekend_special_sessions_are_governing_sessions():
    for d in GOVERNING_SPECIAL_SESSIONS:
        assert d.weekday() >= 5
        assert is_exchange_session(d) is True
        assert is_primary_sample_date(d) is True


def test_2021_02_24_excluded_from_primary_sample_but_present_in_governing():
    d = dt.date(2021, 2, 24)
    assert d in PRIMARY_SAMPLE_EXCLUSIONS
    assert d.weekday() == 2  # ordinary Wednesday
    assert not is_nse_holiday(d)
    assert is_exchange_session(d) is True       # governing: yes
    assert is_primary_sample_date(d) is False   # primary-sample: no


def test_calendar_session_with_zero_bars_1min_rows_remains_a_governing_session():
    """A valid exchange session must not depend on whether any vendor's
    archive happens to have rows for it -- `is_exchange_session` takes
    no database connection at all, so this is true by construction, not
    by a lucky coincidence of real data."""
    import inspect
    assert "con" not in inspect.signature(is_exchange_session).parameters
    assert "con" not in inspect.signature(exchange_session_dates).parameters
    # an ordinary weekday with (hypothetically) zero archive coverage is
    # still a session:
    d = dt.date(2024, 6, 10)
    assert is_exchange_session(d) is True


def test_2016_10_03_is_a_genuine_session_despite_archive_starting_2016_10_04():
    """Decision 24: the intraday archive's own coverage gap must never
    be mistaken for the exchange being closed."""
    d = dt.date(2016, 10, 3)  # Monday
    assert d.weekday() == 0
    assert not is_nse_holiday(d)
    assert is_exchange_session(d) is True


def test_unknown_holiday_year_raises_not_silently_resolved():
    """An unresolvable year must block, not default to True or False."""
    far_future = dt.date(2099, 6, 10)  # Monday, year uncovered by the holiday master
    with pytest.raises(HolidayCalendarMissing):
        is_exchange_session(far_future)
    with pytest.raises(HolidayCalendarMissing):
        exchange_session_dates(dt.date(2099, 1, 1), dt.date(2099, 1, 31))


def test_exchange_session_dates_enumeration_matches_is_exchange_session():
    start, end = dt.date(2024, 1, 1), dt.date(2024, 1, 31)
    dates = exchange_session_dates(start, end)
    d = start
    expected = []
    while d <= end:
        if is_exchange_session(d):
            expected.append(d)
        d += dt.timedelta(days=1)
    assert dates == expected
    assert len(dates) > 0


def test_primary_sample_dates_excludes_2021_02_24_only():
    dates_gov = exchange_session_dates(dt.date(2021, 2, 1), dt.date(2021, 2, 28))
    dates_prim = primary_sample_dates(dt.date(2021, 2, 1), dt.date(2021, 2, 28))
    assert dt.date(2021, 2, 24) in dates_gov
    assert dt.date(2021, 2, 24) not in dates_prim
    assert set(dates_gov) - set(dates_prim) == {dt.date(2021, 2, 24)}


def test_first_session_of_month_weekend_special_wins():
    dates = exchange_session_dates(dt.date(2025, 2, 1), dt.date(2025, 2, 28))
    out = first_session_of_month(dates)
    assert out[(2025, 2)] == dt.date(2025, 2, 1)  # the Saturday special, not Feb 3


@pytest.mark.parametrize("year,month,expected", [
    (2020, 2, dt.date(2020, 2, 1)),   # Saturday special wins
    (2024, 1, dt.date(2024, 1, 1)),   # ordinary Jan 1, 2024 is a Monday
    (2025, 2, dt.date(2025, 2, 1)),   # Saturday special wins
    (2026, 2, dt.date(2026, 2, 1)),   # Sunday special wins
])
def test_ranking_date_for_month_february_special_session_consequence(year, month, expected):
    assert ranking_date_for_month(year, month) == expected


def test_ranking_date_for_month_2016_10_uses_true_calendar_not_archive_start():
    """Decision 24's concrete consequence: the TRUE governing ranking
    date for October 2016 is 2016-10-03 (the first genuine Monday
    session), not 2016-10-04 (where the intraday archive happens to
    start) -- this module has no way to even see the archive, so it
    cannot default to the archive's own boundary."""
    assert ranking_date_for_month(2016, 10) == dt.date(2016, 10, 3)
