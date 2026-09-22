"""Regression test for a real bug hit during the 2016-2026 backfill: NSE's
legacy bhavcopy archive is inconsistent about the TIMESTAMP column's year
width across its own history. 2024-07-05's file reads "05-JUL-2024" (4-digit
year); 2020-07-13's reads "13-Jul-20" (2-digit year) -- same source, same
column, different format, ten years apart. A parser that trusts this column
as the source of truth for trade_date needs to guess the right format per
file. The fix instead takes trade_date from the request itself (a bhavcopy
file is always for exactly one known day) and only loosely cross-checks the
embedded field's day/month against it.

Network test: fetches the real file. Skipped if that fails.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.prices_nse import fetch_raw_zip, parse_bhavcopy_zip, SOURCE_LEGACY, TradeDateMismatch

TWO_DIGIT_YEAR_DAY = dt.date(2020, 7, 13)  # confirmed live: TIMESTAMP column reads "13-Jul-20"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "prices"


@pytest.fixture(scope="module")
def parsed():
    try:
        path, source = fetch_raw_zip(TWO_DIGIT_YEAR_DAY, RAW_DIR, source=SOURCE_LEGACY)
    except Exception as e:
        pytest.skip(f"network fetch failed: {e}")
    return parse_bhavcopy_zip(path, source, TWO_DIGIT_YEAR_DAY, series_include=["EQ"])


def test_two_digit_year_file_parses_to_correct_trade_date(parsed):
    assert (parsed["trade_date"] == TWO_DIGIT_YEAR_DAY).all()
    assert len(parsed) > 1000


def test_mismatched_expected_date_is_caught_not_silently_accepted():
    """If the file we got back doesn't actually match the day we asked for
    (wrong file served, off-by-one in a date loop, etc.), this must raise,
    not silently stamp the wrong file's rows with the requested date."""
    try:
        path, source = fetch_raw_zip(TWO_DIGIT_YEAR_DAY, RAW_DIR, source=SOURCE_LEGACY)
    except Exception as e:
        pytest.skip(f"network fetch failed: {e}")
    wrong_date = dt.date(2020, 7, 14)  # one day off from the file's real content
    with pytest.raises(TradeDateMismatch):
        parse_bhavcopy_zip(path, source, wrong_date, series_include=["EQ"])
