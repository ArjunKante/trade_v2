"""Regression tests for src/options_depth/quotes.py's exch_feed_date --
the stale-session guard scripts/snapshot_options_depth.py uses to refuse
a tick served while the market is shut (e.g. an NSE holiday
check_market_hours() cannot detect on its own)."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from options_depth.quotes import exch_feed_date


def test_parses_angels_format():
    assert exch_feed_date("19-Oct-2026 16:08:11") == dt.date(2026, 10, 19)


def test_none_input_returns_none():
    assert exch_feed_date(None) is None


def test_empty_string_returns_none():
    assert exch_feed_date("") is None


def test_unparseable_string_returns_none():
    assert exch_feed_date("not a timestamp") is None
