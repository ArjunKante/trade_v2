"""Materialized entity-adjusted daily price panel. Derived, fully
recomputed each run (like adjustment_factors) -- not append-only facts.

Physically excludes the sealed holdout at materialization time (not just at
analysis time) as a second, independent layer of protection: even a bug in
a downstream analysis script that forgets to call the holdout guard cannot
see sealed dates, because they were never materialized into this table in
the first place.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from data_layer.holdout import SEALED_HOLDOUT_START, guard_date_range


def materialize_entity_panel(con: duckdb.DuckDBPyConnection) -> int:
    end = SEALED_HOLDOUT_START - dt.timedelta(days=1)
    guard_date_range(dt.date(2016, 1, 1), end)  # must not raise; documents the bound explicitly

    sql = """
        SELECT l.entity_id, p.trade_date, p.isin, p.close AS raw_close,
               p.close * af.factor AS adjusted_close, p.volume, p.turnover
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        JOIN adjustment_factors af ON af.entity_id = l.entity_id AND af.trade_date = p.trade_date
        WHERE p.series = 'EQ' AND p.trade_date < ?
    """
    df = con.execute(sql, [SEALED_HOLDOUT_START]).fetchdf()
    df["known_date"] = df["trade_date"]
    df["fetched_at"] = dt.datetime.now()
    df["source"] = "ENTITY_PANEL_MATERIALIZED"
    df["revision_seq"] = 1

    con.execute("DELETE FROM entity_prices_daily")
    con.register("panel_new", df)
    con.execute(
        "INSERT INTO entity_prices_daily SELECT entity_id, trade_date, isin, raw_close, adjusted_close, "
        "volume, turnover, known_date, fetched_at, source, revision_seq FROM panel_new"
    )
    con.unregister("panel_new")
    return len(df)


def read_full_entity_panel_authorized(con: duckdb.DuckDBPyConnection, authorize_holdout: bool) -> pd.DataFrame:
    """The one sanctioned way to read entity-adjusted prices INCLUDING the
    sealed holdout window. Bypasses entity_prices_daily (which is physically
    truncated at SEALED_HOLDOUT_START) with a fresh, unrestricted query --
    requires authorize_holdout=True explicitly, no default. For factor
    computation, historical lookback naturally spans the pre-holdout period
    regardless (that is not a leak; it's how a live strategy would work).
    What actually matters is which DATES get evaluated as decisions, which
    is the caller's responsibility, not this function's."""
    guard_date_range(dt.date(2016, 1, 1), dt.date.today(), authorize_holdout=authorize_holdout)
    sql = """
        SELECT l.entity_id, p.trade_date, p.isin, p.close AS raw_close,
               p.close * af.factor AS adjusted_close, p.volume, p.turnover
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        JOIN adjustment_factors af ON af.entity_id = l.entity_id AND af.trade_date = p.trade_date
        WHERE p.series = 'EQ'
    """
    df = con.execute(sql).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.sort_values(["entity_id", "trade_date"]).reset_index(drop=True)


def read_entity_panel(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("SELECT * FROM entity_prices_daily ORDER BY entity_id, trade_date").fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df
