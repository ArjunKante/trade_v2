"""Regression test for FINDINGS.md Section 2's tripwire: the 3.50
holdout margin is recorded as reproducible only because corporate_
actions/isin_lineage are frozen and prices_eod has never been revised
inside the sealed holdout window. data_layer.margin_tripwire is the
mechanized version of that tripwire -- these tests fix its two failure
conditions as data, not placeholders, so a resumed feed or a backfill
is caught here before someone has to notice the margin moved.

The first group below is hermetic (synthetic in-memory warehouse) and
runs everywhere, including CI. The LIVE group at the bottom
(`test_live_*`) is data-gated on `real_con`, same skip-guard convention
as `test_isin_lineage.py`'s own `real_con` fixture and ~44 other tests
in this suite: skips with "real warehouse not present" wherever
data/warehouse.duckdb doesn't exist (every GitHub Actions push), and
runs for real only in the weekly full-suite job against this project's
actual data (`scripts/weekly_full_test_run.py` -- see that script's own
docstring for the Task Scheduler/healthchecks.io wiring; task #19,
registering it in OPERATIONS.md, is separately still open). A failure
here makes that job exit nonzero, which withholds its healthchecks.io
heartbeat ping, which produces healthchecks.io's own DOWN email once
the grace window lapses -- the existing dead-man's-switch alerting
path, not a new one.
"""
import datetime as dt
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import SCHEMA_SQL, get_read_connection
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


WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"

_MEANING = (
    "the momentum margin's stability conditions are violated; 3.50 must be "
    "recomputed and PROJECT_CONTEXT.md Section 4 / FINDINGS.md Section 2 "
    "revisited before that figure is cited again."
)


@pytest.fixture(scope="module")
def real_con():
    """Same skip-guard convention as test_isin_lineage.py's real_con and
    ~44 other data-gated tests in this suite: skips cleanly wherever
    data/warehouse.duckdb doesn't exist (every GitHub Actions push),
    runs for real only against this project's actual local warehouse
    (the Saturday weekly full-suite job)."""
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    return get_read_connection(WAREHOUSE)


def test_live_corporate_actions_and_lineage_still_frozen(real_con):
    """Condition (b): corporate_actions/isin_lineage resuming updates.
    Runs only against real data -- see module docstring for why a
    failure here reaches a human via the existing weekly-heartbeat
    dead-man's-switch, not a new alerting path."""
    try:
        assert_corporate_actions_and_lineage_still_frozen(real_con)
    except FrozenTableResumedError as e:
        pytest.fail(
            "MOMENTUM MARGIN TRIPWIRE TRIPPED (condition b, corporate_actions/"
            f"isin_lineage resumed updating): {_MEANING}\nDetail: {e}"
        )


def test_live_no_in_window_price_revision(real_con):
    """Condition (a): a price row inside the sealed holdout window
    [2025-04-11, 2026-04-22] touched after the margin was last verified.
    Runs only against real data -- see module docstring."""
    try:
        assert_no_in_window_price_revision(real_con)
    except HoldoutWindowPriceRevisionError as e:
        pytest.fail(
            "MOMENTUM MARGIN TRIPWIRE TRIPPED (condition a, in-window price "
            f"revision): {_MEANING}\nDetail: {e}"
        )
