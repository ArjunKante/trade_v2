"""The invariant every reader depends on: ONE ROW PER LOGICAL KEY. The prior
project's shared loader had no revision_seq dedup at all -- correct for
eighteen months purely because no (isin, date) key had ever received a
second revision, until a backfill created one and every downstream reader
silently doubled its row count with no error anywhere.

This test manufactures exactly that: inserts a synthetic second revision for
an existing key and asserts read_latest still returns exactly one row for
it, with the higher-revision values winning -- and that a bare SELECT *
(the thing read_latest replaces) would have doubled, proving the dedup is
load-bearing and not a no-op.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection, read_latest


@pytest.fixture
def con(tmp_path):
    c = get_connection(tmp_path / "canary.duckdb")
    c.execute(
        """
        INSERT INTO prices_eod VALUES
        ('ISIN1', '2026-01-05', 'AAA', 'EQ', 100,101,99,100,100,99, 1000, 100000, 50, '2026-01-05', now(), 'TEST', 1),
        ('ISIN1', '2026-01-06', 'AAA', 'EQ', 100,101,99,101,101,100, 1000, 101000, 50, '2026-01-06', now(), 'TEST', 1)
        """
    )
    return c


def test_bare_select_star_doubles_after_a_second_revision(con):
    """Demonstrate the failure mode itself: without dedup, a second revision
    of an existing key doubles the row count for that key."""
    before = con.execute("SELECT COUNT(*) FROM prices_eod WHERE isin='ISIN1' AND trade_date='2026-01-05'").fetchone()[0]
    assert before == 1

    # a correction arrives: same logical key (isin, trade_date), revision_seq=2
    con.execute(
        """
        INSERT INTO prices_eod VALUES
        ('ISIN1', '2026-01-05', 'AAA', 'EQ', 100,101,99,105,105,99, 1000, 100000, 50, '2026-01-05', now(), 'TEST', 2)
        """
    )
    after_bare = con.execute("SELECT COUNT(*) FROM prices_eod WHERE isin='ISIN1' AND trade_date='2026-01-05'").fetchone()[0]
    assert after_bare == 2  # the bare-SELECT failure mode: silently doubled


def test_read_latest_dedups_to_one_row_with_highest_revision(con):
    con.execute(
        """
        INSERT INTO prices_eod VALUES
        ('ISIN1', '2026-01-05', 'AAA', 'EQ', 100,101,99,105,105,99, 1000, 100000, 50, '2026-01-05', now(), 'TEST', 2)
        """
    )
    df = read_latest(con, "prices_eod", key_cols=["isin", "trade_date"])
    key_rows = df[(df["isin"] == "ISIN1") & (df["trade_date"].astype(str) == "2026-01-05")]
    assert len(key_rows) == 1
    assert key_rows.iloc[0]["close"] == 105  # revision 2's value won, not revision 1's

    # the OTHER key (2026-01-06), never revised, must still appear exactly once
    other = df[(df["isin"] == "ISIN1") & (df["trade_date"].astype(str) == "2026-01-06")]
    assert len(other) == 1


def test_read_latest_row_count_unchanged_by_a_synthetic_second_revision():
    """The canary in its cleanest form: total distinct-key row count via
    read_latest must be invariant to how many revisions exist per key."""
    import duckdb
    con = duckdb.connect(":memory:")
    from data_layer.db import SCHEMA_SQL
    con.execute(SCHEMA_SQL)
    con.execute(
        """
        INSERT INTO prices_eod VALUES
        ('A', '2026-01-01', 'X', 'EQ', 1,1,1,1,1,1,1,1,1, '2026-01-01', now(), 'T', 1),
        ('B', '2026-01-01', 'Y', 'EQ', 1,1,1,1,1,1,1,1,1, '2026-01-01', now(), 'T', 1)
        """
    )
    n_before = len(read_latest(con, "prices_eod", key_cols=["isin", "trade_date"]))
    assert n_before == 2

    con.execute(
        "INSERT INTO prices_eod VALUES ('A', '2026-01-01', 'X', 'EQ', 1,1,1,2,2,1,1,1,1, '2026-01-01', now(), 'T', 2)"
    )
    n_after = len(read_latest(con, "prices_eod", key_cols=["isin", "trade_date"]))
    assert n_after == 2  # unchanged -- this is the canary
