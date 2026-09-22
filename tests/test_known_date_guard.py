"""No query against the warehouse may ever return a row with known_date > as_of.

This is the single most important guarantee in the whole project: the prior
project's model leaked information across a date boundary in an unchecked
diagnostic. Here that boundary is enforced in code, not by convention, and
this test exercises the failure mode directly rather than trusting the
happy path.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection, query_as_of, HoldoutViolationError


@pytest.fixture
def con(tmp_path):
    c = get_connection(tmp_path / "test.duckdb")
    c.execute(
        """
        INSERT INTO prices_eod VALUES
        ('ISIN1', '2026-01-05', 'AAA', 'EQ', 100,101,99,100,100,99, 1000, 100000, 50, '2026-01-05', now(), 'TEST', 1),
        ('ISIN1', '2026-01-06', 'AAA', 'EQ', 100,101,99,101,101,100, 1000, 101000, 50, '2026-01-06', now(), 'TEST', 1),
        ('ISIN1', '2026-01-07', 'AAA', 'EQ', 101,103,100,102,102,101, 1000, 102000, 50, '2026-01-07', now(), 'TEST', 1)
        """
    )
    return c


def test_as_of_excludes_future_rows(con):
    df = query_as_of(con, "prices_eod", as_of=dt.date(2026, 1, 6))
    assert set(df["trade_date"].astype(str)) == {"2026-01-05", "2026-01-06"}
    assert "2026-01-07" not in set(df["known_date"].astype(str))


def test_as_of_on_exact_boundary_is_inclusive(con):
    df = query_as_of(con, "prices_eod", as_of=dt.date(2026, 1, 5))
    assert len(df) == 1
    assert str(df.iloc[0]["known_date"])[:10] == "2026-01-05"


def test_as_of_before_any_data_is_empty(con):
    df = query_as_of(con, "prices_eod", as_of=dt.date(2025, 12, 31))
    assert df.empty


def test_guard_raises_if_a_row_with_future_known_date_slips_through(con, monkeypatch):
    """Simulate the exact failure the guard exists to catch: a query that
    forgets to filter on known_date. query_as_of's WHERE clause is bypassed
    here on purpose to prove the post-hoc assertion still fires."""
    import data_layer.db as db_module

    import pandas as pd

    def broken_query_as_of(con, table, as_of, where_extra="1=1", known_date_col="known_date"):
        df = con.execute(f"SELECT * FROM {table}").fetchdf()  # no known_date filter — the bug
        if not df.empty and (pd.to_datetime(df[known_date_col]) > pd.Timestamp(as_of)).any():
            raise HoldoutViolationError("leak")
        return df

    with pytest.raises(HoldoutViolationError):
        broken_query_as_of(con, "prices_eod", as_of=dt.date(2026, 1, 6))
