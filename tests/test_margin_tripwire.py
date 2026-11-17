"""Regression test for FINDINGS.md Section 2's tripwire: the 3.50
holdout margin is recorded as reproducible only because corporate_
actions/isin_lineage are frozen and prices_eod has never been revised
inside the sealed holdout window. data_layer.margin_tripwire is the
mechanized version of that tripwire -- these tests fix its two failure
conditions as data, not placeholders, so a resumed feed or a backfill
is caught here before someone has to notice the margin moved.
"""
import datetime as dt
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import SCHEMA_SQL
from data_layer.margin_tripwire import (
    CORPORATE_ACTIONS_FROZEN_AT,
    CORPORATE_ACTIONS_FROZEN_ROWS,
    HOLDOUT_WINDOW_END,
    HOLDOUT_WINDOW_START,
    ISIN_LINEAGE_FROZEN_AT,
    ISIN_LINEAGE_FROZEN_ROWS,
    FrozenTableResumedError,
    HoldoutWindowPriceRevisionError,
    assert_corporate_actions_and_lineage_still_frozen,
    assert_no_in_window_price_revision,
)

CA_ROW = (
    "('ISIN1', 'SYM', '{ex_date}', 'bonus', 1.0, 'raw', 'ISIN1', "
    "'{ex_date}', '{fetched_at}', 'test', 1)"
)
LINEAGE_ROW = (
    "('ISIN2', 'ENT1', 'ISIN1', 'nsdl_structural', '2025-01-01', "
    "'{fetched_at}', 'test', 1)"
)
PRICE_ROW = (
    "('ISIN1', '{trade_date}', 'SYM', 'EQ', 1,1,1,1,1,1,1,1,1, "
    "'{trade_date}', '{fetched_at}', 'test', 1)"
)


def _con_with_frozen_tables(n_ca: int, n_lineage: int) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA_SQL)
    for i in range(n_ca):
        con.execute(
            f"INSERT INTO corporate_actions VALUES "
            + CA_ROW.format(ex_date="2020-01-01", fetched_at=CORPORATE_ACTIONS_FROZEN_AT)
        )
    for i in range(n_lineage):
        con.execute(f"INSERT INTO isin_lineage VALUES " + LINEAGE_ROW.format(fetched_at=ISIN_LINEAGE_FROZEN_AT))
    return con


def test_matching_frozen_snapshot_passes():
    con = _con_with_frozen_tables(CORPORATE_ACTIONS_FROZEN_ROWS, ISIN_LINEAGE_FROZEN_ROWS)
    assert_corporate_actions_and_lineage_still_frozen(con)  # no raise


def test_corporate_actions_new_fetched_at_is_refused():
    con = _con_with_frozen_tables(CORPORATE_ACTIONS_FROZEN_ROWS - 1, ISIN_LINEAGE_FROZEN_ROWS)
    con.execute(
        "INSERT INTO corporate_actions VALUES "
        + CA_ROW.format(ex_date="2026-11-18", fetched_at="2026-11-18 00:00:00")
    )
    with pytest.raises(FrozenTableResumedError):
        assert_corporate_actions_and_lineage_still_frozen(con)


def test_isin_lineage_new_row_is_refused():
    con = _con_with_frozen_tables(CORPORATE_ACTIONS_FROZEN_ROWS, ISIN_LINEAGE_FROZEN_ROWS)
    con.execute("INSERT INTO isin_lineage VALUES " + LINEAGE_ROW.format(fetched_at="2026-11-18 00:00:00"))
    with pytest.raises(FrozenTableResumedError):
        assert_corporate_actions_and_lineage_still_frozen(con)


def test_no_in_window_revision_passes():
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA_SQL)
    baseline = dt.datetime(2026, 11, 17, 3, 43, 12)
    con.execute(
        "INSERT INTO prices_eod VALUES "
        + PRICE_ROW.format(trade_date="2025-06-15", fetched_at="2025-06-16 00:00:00")
    )
    assert_no_in_window_price_revision(con, baseline_fetched_at=baseline)  # no raise


def test_in_window_row_touched_after_baseline_is_refused():
    """The exact failure mode the tripwire exists for: a trade_date already
    inside the sealed holdout window gets a fetched_at AFTER the margin
    was last verified -- condition (a), FINDINGS.md Section 2."""
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA_SQL)
    baseline = dt.datetime(2026, 11, 17, 3, 43, 12)
    con.execute(
        "INSERT INTO prices_eod VALUES "
        + PRICE_ROW.format(trade_date="2025-06-15", fetched_at="2026-11-18 00:00:00")
    )
    with pytest.raises(HoldoutWindowPriceRevisionError):
        assert_no_in_window_price_revision(con, baseline_fetched_at=baseline)


def test_revision_outside_window_does_not_trip():
    """A row revised after the baseline is fine as long as its trade_date
    falls outside [HOLDOUT_WINDOW_START, HOLDOUT_WINDOW_END] -- forward
    growth on current trading days is the expected, harmless case."""
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA_SQL)
    baseline = dt.datetime(2026, 11, 17, 3, 43, 12)
    assert HOLDOUT_WINDOW_END < dt.date(2026, 11, 1)
    con.execute(
        "INSERT INTO prices_eod VALUES "
        + PRICE_ROW.format(trade_date="2026-11-18", fetched_at="2026-11-18 00:00:00")
    )
    assert_no_in_window_price_revision(con, baseline_fetched_at=baseline)  # no raise
