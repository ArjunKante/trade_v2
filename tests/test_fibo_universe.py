"""Regression tests for src/fibo/universe.py's point-in-time,
annually-reconstituted top-N-by-turnover universe."""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.universe import reconstitute_annually, membership_report, is_member


def _make_con(rows):
    """rows: list of (isin, entity_id, trade_date, turnover). Builds a
    minimal in-memory DuckDB with just the two tables universe.py reads."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE prices_eod (isin VARCHAR, trade_date DATE, series VARCHAR, turnover DOUBLE)")
    con.execute("CREATE TABLE isin_lineage (isin VARCHAR, entity_id VARCHAR)")
    isins = sorted({r[0] for r in rows})
    con.executemany("INSERT INTO isin_lineage VALUES (?, ?)", [(i, i) for i in isins])
    con.executemany(
        "INSERT INTO prices_eod VALUES (?, ?, 'EQ', ?)",
        [(isin, td, turnover) for isin, _entity, td, turnover in rows],
    )
    return con


def test_2016_dropped_no_preceding_year():
    """Only 2016 data exists (a full year, through December) -> 2016 itself
    can't be reconstituted (no 2015 to rank against), but 2017 CAN be,
    ranked off 2016's own (complete) turnover."""
    rows = [("E1", "E1", d, 1000.0) for d in pd.date_range("2016-01-01", "2016-12-31", freq="D")]
    con = _make_con(rows)
    universe = reconstitute_annually(con, top_n=50)
    assert 2016 not in set(universe["year"])  # 2016 itself never gets ranked (no 2015 data)
    assert 2017 in set(universe["year"])      # but 2017 IS ranked off 2016's turnover


def test_top_n_selects_highest_median_turnover():
    rows = []
    # 3 entities in 2020, distinct turnover levels -> top_n=2 keeps the top 2
    for entity, level in [("HIGH", 3000.0), ("MID", 2000.0), ("LOW", 1000.0)]:
        for d in pd.date_range("2020-01-01", "2020-12-31", freq="D"):
            rows.append((entity, entity, d, level))
    con = _make_con(rows)
    universe = reconstitute_annually(con, top_n=2)
    members_2021 = set(universe.loc[universe["year"] == 2021, "entity_id"])
    assert members_2021 == {"HIGH", "MID"}
    assert "LOW" not in members_2021


def test_membership_fixed_for_full_year_not_recomputed_mid_year():
    """A name with a turnover spike in only the LAST MONTH of 2020 should
    not enter the universe until 2021 based on its full-year 2020 MEDIAN
    (still dominated by its 11 quiet months), even though a continuously-
    rolling short window would have picked the spike up immediately."""
    rows = []
    for d in pd.date_range("2020-01-01", "2020-11-30", freq="D"):
        rows.append(("STEADY", "STEADY", d, 5000.0))
        rows.append(("LATE_SPIKE", "LATE_SPIKE", d, 10.0))
    for d in pd.date_range("2020-12-01", "2020-12-31", freq="D"):
        rows.append(("STEADY", "STEADY", d, 5000.0))
        rows.append(("LATE_SPIKE", "LATE_SPIKE", d, 999999.0))
    con = _make_con(rows)
    universe = reconstitute_annually(con, top_n=1)
    # 2020's full-year MEDIAN for LATE_SPIKE is still 10.0 (11 of 12 months
    # quiet), so STEADY wins the single top_n=1 slot for 2021
    assert set(universe.loc[universe["year"] == 2021, "entity_id"]) == {"STEADY"}


def test_in_progress_year_not_used_as_ranking_base():
    """A year whose data stops in September (still in progress, like the
    warehouse's current year) must not be treated as a complete prior year
    -- it should not produce a membership list for the following year."""
    rows = []
    for d in pd.date_range("2020-01-01", "2020-12-31", freq="D"):
        rows.append(("A", "A", d, 100.0))
    for d in pd.date_range("2021-01-01", "2021-09-15", freq="D"):  # stops in September
        rows.append(("A", "A", d, 100.0))
    con = _make_con(rows)
    universe = reconstitute_annually(con, top_n=50)
    assert 2021 in set(universe["year"])       # 2020 was complete -> ranks 2021
    assert 2022 not in set(universe["year"])   # 2021 is in-progress -> must not rank 2022


def test_membership_report_counts_added_dropped():
    universe = pd.DataFrame({
        "year": [2020, 2020, 2021, 2021, 2021],
        "entity_id": ["A", "B", "A", "C", "D"],
        "median_turnover_prior_year": [1.0] * 5,
        "rank": [1, 2, 1, 2, 3],
    })
    report = membership_report(universe)
    row_2021 = report[report["year"] == 2021].iloc[0]
    assert row_2021["n_members"] == 3
    assert row_2021["n_added"] == 2   # C, D
    assert row_2021["n_dropped"] == 1  # B


def test_is_member_point_in_time():
    universe = pd.DataFrame({
        "year": [2021], "entity_id": ["A"], "median_turnover_prior_year": [1.0], "rank": [1],
    })
    assert is_member(universe, "A", pd.Timestamp("2021-06-01"))
    assert not is_member(universe, "A", pd.Timestamp("2022-06-01"))
    assert not is_member(universe, "B", pd.Timestamp("2021-06-01"))
