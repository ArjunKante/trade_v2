"""Separate DuckDB warehouse for 1-minute intraday bars -- deliberately its
own file (data/fibo_intraday.duckdb), never sharing data/warehouse.duckdb.
Two independent reasons: (1) this project's daily warehouse is append-only
FACTS at daily granularity; a year of 1-minute bars across 50 names is
~2 orders of magnitude more rows and has no reason to share a file with
(or risk corrupting) the daily-factor research the rest of this project
depends on; (2) src/fibo/ is DATA-ONLY against a live broker API (Angel One
SmartAPI) -- keeping its storage physically separate makes it trivial to
confirm by inspection that nothing in this module's write path touches the
main warehouse.

Same append-only, known_date/fetched_at/source/revision_seq discipline as
data_layer.db.SCHEMA_SQL, for the same reason: corrections are new rows
with a higher revision_seq, never UPDATE/DELETE.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bars_1min (
    entity_id       VARCHAR NOT NULL,
    isin            VARCHAR NOT NULL,
    symbol          VARCHAR NOT NULL,
    angel_token     VARCHAR,            -- Angel One's own instrument token, kept for audit/re-fetch
    trade_date      DATE NOT NULL,
    ts              TIMESTAMP NOT NULL, -- bar START time, Asia/Kolkata, naive (exchange-local, no tz math needed)
    open            DOUBLE,
    high            DOUBLE,
    low             DOUBLE,
    close           DOUBLE,
    volume          BIGINT,
    known_date      DATE NOT NULL,
    fetched_at      TIMESTAMP NOT NULL,
    source          VARCHAR NOT NULL,
    revision_seq    INTEGER NOT NULL
);

-- every read path filters/joins by (entity_id, trade_date) or scans a
-- (entity_id, ts) range for one day's bars -- both backed by this index
CREATE INDEX IF NOT EXISTS idx_bars_1min_entity_date ON bars_1min(entity_id, trade_date);

CREATE TABLE IF NOT EXISTS fetch_log_intraday (
    entity_id     VARCHAR NOT NULL,
    trade_date    DATE NOT NULL,
    status        VARCHAR NOT NULL,   -- 'ok' | 'no_data' | 'error'
    rows_loaded   INTEGER NOT NULL,
    attempted_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (entity_id, trade_date)
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
    """Read-only connection for backtest/report code -- same reasoning as
    data_layer.db.get_read_connection: a read path that accidentally
    imports a write function fails loudly instead of quietly holding a
    write lock during a long backtest run."""
    return duckdb.connect(str(duckdb_path), read_only=True)
