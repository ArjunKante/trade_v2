"""Point-in-time fundamentals selection, tested against a REAL restatement
found in the full backfill: VSTTILLERS filed Q3 FY25 (period_end
2024-12-31) on time on 2025-02-11 (42-day lag), then refiled the SAME
period on 2026-07-30 (576-day lag from period_end, 536 days after the
original). This corrects an earlier characterization of this case as
simply "one 19-month-late filing" -- it is an on-time original plus a
genuine later restatement, and is a better fixture for exactly this reason:
it exercises both the announcement-lag invariant AND the
restatement-visibility invariant in one real example.

A point-in-time query as_of any date between the two announcements must
return the ORIGINAL version. Returning the restated version early is
exactly the mechanism of bug #9 in the prior project (a shared reader with
no correct revision selection silently doubling/misselecting rows).
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.fundamentals_pit import point_in_time_fundamentals

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"


@pytest.fixture(scope="module")
def con():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    return get_read_connection(WAREHOUSE)


def _vsttillers_row(con, as_of):
    df = point_in_time_fundamentals(con, as_of)
    row = df[(df["symbol"] == "VSTTILLERS") & (df["period_end"] == pd.Timestamp(2024, 12, 31))]
    return row.iloc[0] if len(row) else None


def test_not_visible_before_original_announcement(con):
    assert _vsttillers_row(con, dt.date(2025, 2, 10)) is None


def test_original_version_visible_immediately_after_announcement(con):
    row = _vsttillers_row(con, dt.date(2025, 2, 12))
    assert row is not None
    assert row["known_date"].date() == dt.date(2025, 2, 11)


def test_original_version_still_visible_the_day_before_restatement(con):
    """The exact boundary the prior project's bug #10 got wrong for a
    different table: one day before a known transition must NOT see it."""
    row = _vsttillers_row(con, dt.date(2026, 7, 29))
    assert row is not None
    assert row["known_date"].date() == dt.date(2025, 2, 11)  # still the ORIGINAL, not the restatement


def test_restated_version_visible_the_day_after(con):
    row = _vsttillers_row(con, dt.date(2026, 7, 31))
    assert row is not None
    assert row["known_date"].date() == dt.date(2026, 7, 30)


def test_consolidated_preferred_over_standalone_when_both_exist(con):
    row = _vsttillers_row(con, dt.date(2026, 9, 1))
    assert row is not None
    assert row["consolidated"] == "Consolidated"
