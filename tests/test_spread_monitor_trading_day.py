"""Tests for the live trading-day verification signal (exchFeedTime vs.
today's IST date) -- no network call."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spread_monitor.market_hours import IST
from spread_monitor.trading_day import OK, UNVERIFIED, verify_trading_day


def test_ok_when_a_row_carries_todays_feed_date():
    now = dt.datetime(2026, 10, 5, 12, 48, 54, tzinfo=IST)
    fetched = [
        {"symbolToken": "99926000", "exchFeedTime": "05-Oct-2026 12:48:54"},
        {"symbolToken": "9819", "exchFeedTime": "05-Oct-2026 12:48:54"},
    ]
    assert verify_trading_day(fetched, now) == OK


def test_unverified_when_feed_date_is_stale():
    # e.g. a holiday serving the last trading day's cached quote
    now = dt.datetime(2026, 10, 6, 11, 0, 0, tzinfo=IST)
    fetched = [{"symbolToken": "9819", "exchFeedTime": "05-Oct-2026 15:29:58"}]
    assert verify_trading_day(fetched, now) == UNVERIFIED


def test_unverified_when_no_rows():
    now = dt.datetime(2026, 10, 5, 12, 0, 0, tzinfo=IST)
    assert verify_trading_day([], now) == UNVERIFIED


def test_unverified_when_feed_time_missing():
    now = dt.datetime(2026, 10, 5, 12, 0, 0, tzinfo=IST)
    fetched = [{"symbolToken": "9819"}]
    assert verify_trading_day(fetched, now) == UNVERIFIED


def test_unverified_when_feed_time_unparseable():
    now = dt.datetime(2026, 10, 5, 12, 0, 0, tzinfo=IST)
    fetched = [{"symbolToken": "9819", "exchFeedTime": "garbage"}]
    assert verify_trading_day(fetched, now) == UNVERIFIED


def test_ok_if_any_single_row_matches_even_if_others_dont():
    now = dt.datetime(2026, 10, 5, 12, 0, 0, tzinfo=IST)
    fetched = [
        {"symbolToken": "1", "exchFeedTime": "garbage"},
        {"symbolToken": "2", "exchFeedTime": "05-Oct-2026 12:00:00"},
    ]
    assert verify_trading_day(fetched, now) == OK
