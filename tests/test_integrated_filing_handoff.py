"""Real-data regression test for the Integrated Filing transition boundary,
following this project's established pattern (test_announcement_lag_vsttillers.py,
test_catchup_filing_visibility.py) of testing a specific real case against
the live warehouse rather than only a synthetic fixture -- the whole point
is confirming the transition is clean on an actual company, not merely that
the mechanism is theoretically sound.

Case: INE133A01011 (JSWDULUX under the old format's own symbol). Chosen
because it has continuous quarterly filings on both sides of the April 2025
Integrated Filing mandate with no ambiguity.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"
TEST_ISIN = "INE133A01011"


@pytest.fixture(scope="module")
def con():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    c = get_read_connection(WAREHOUSE)
    yield c
    c.close()


def test_2025_03_31_quarter_is_retrievable_via_new_fetcher(con):
    rows = con.execute(
        "SELECT COUNT(*) FROM fundamentals_xbrl_facts "
        "WHERE source = 'NSE_INTEGRATED_FILING_FINANCIALS' AND isin = ? AND period_end = ?",
        [TEST_ISIN, dt.date(2025, 3, 31)],
    ).fetchone()[0]
    assert rows > 0, f"{TEST_ISIN}'s 2025-03-31 quarter should be present via the Integrated Filing source"


def test_2025_03_31_quarter_is_absent_from_old_format(con):
    rows = con.execute(
        "SELECT COUNT(*) FROM fundamentals_filings WHERE isin = ? AND period_end = ?",
        [TEST_ISIN, dt.date(2025, 3, 31)],
    ).fetchone()[0]
    assert rows == 0, f"{TEST_ISIN}'s 2025-03-31 quarter should NOT exist under the old format -- if it does, both formats double-cover this quarter"


def test_no_gap_old_formats_last_quarter_immediately_precedes_new_formats_first(con):
    last_old = con.execute(
        "SELECT MAX(period_end) FROM fundamentals_filings WHERE isin = ?", [TEST_ISIN]
    ).fetchone()[0]
    first_new = con.execute(
        "SELECT MIN(period_end) FROM fundamentals_xbrl_facts "
        "WHERE source = 'NSE_INTEGRATED_FILING_FINANCIALS' AND isin = ?", [TEST_ISIN]
    ).fetchone()[0]
    assert last_old == dt.date(2024, 12, 31)
    assert first_new == dt.date(2025, 3, 31)
    # one quarter apart, not two -- a skipped quarter would silently break TTM continuity
    assert (first_new.year - last_old.year) * 12 + (first_new.month - last_old.month) == 3


def test_no_overlap_between_the_two_sources_for_this_isin(con):
    """Neither source has a row inside the other's covered window -- the
    real check that a company was never double-counted across the
    transition, not just that individual endpoints reported clean ranges."""
    overlap_new_before_transition = con.execute(
        "SELECT COUNT(*) FROM fundamentals_xbrl_facts "
        "WHERE source = 'NSE_INTEGRATED_FILING_FINANCIALS' AND isin = ? AND period_end <= ?",
        [TEST_ISIN, dt.date(2024, 12, 31)],
    ).fetchone()[0]
    overlap_old_after_transition = con.execute(
        "SELECT COUNT(*) FROM fundamentals_filings WHERE isin = ? AND period_end >= ?",
        [TEST_ISIN, dt.date(2025, 3, 31)],
    ).fetchone()[0]
    assert overlap_new_before_transition == 0
    assert overlap_old_after_transition == 0
