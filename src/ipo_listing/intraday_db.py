"""Separate DuckDB file for IPO listing-day 1-minute bars
(`data/ipo_listing/ipo_intraday.duckdb`) -- never `data/fibo_intraday.duckdb`
or `data/warehouse.duckdb` (`PREREGISTRATION_IPO.md` Section 0/3). Same
schema shape and append-only discipline as `fibo.intraday_db`, keyed by
`listing_id` (this study's own natural key, `ipo_listing.listings`)
instead of `entity_id`, since a listing has no pre-IPO entity identity in
this project's existing entity/ISIN-lineage system.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bars_1min (
    listing_id      INTEGER NOT NULL,
    company_name    VARCHAR NOT NULL,
    symbol_used     VARCHAR NOT NULL,   -- the symbol actually sent to Angel (listing-day or recovered current)
    angel_token     VARCHAR,
    listing_date    DATE NOT NULL,
    ts              TIMESTAMP NOT NULL, -- bar START time, Asia/Kolkata, naive
    open            DOUBLE,
    high            DOUBLE,
    low             DOUBLE,
    close           DOUBLE,
    volume          BIGINT,
    fetched_at      TIMESTAMP NOT NULL,
    source          VARCHAR NOT NULL,
    revision_seq    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bars_1min_listing ON bars_1min(listing_id);

CREATE TABLE IF NOT EXISTS fetch_log (
    listing_id    INTEGER NOT NULL,
    listing_date  DATE NOT NULL,
    symbol_used   VARCHAR,
    token_used    VARCHAR,
    status        VARCHAR NOT NULL,   -- 'OK' | 'FETCH_FAILED' | 'NO_TOKEN'
    reason        VARCHAR,
    n_candles     INTEGER NOT NULL,
    attempted_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (listing_id)
);
"""

SOURCE_NAME = "ANGEL_ONE_SMARTAPI_HISTORICAL"


def get_connection(duckdb_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Read-write connection. Runs schema DDL. Ingestion scripts only."""
    duckdb_path = Path(duckdb_path)
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(duckdb_path))
    con.execute(SCHEMA_SQL)
    return con


def get_read_connection(duckdb_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Read-only connection for validation/backtest code."""
    return duckdb.connect(str(duckdb_path), read_only=True)
