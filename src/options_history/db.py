"""This module's own DuckDB file -- data/options_history/options_history.duckdb,
never data/warehouse.duckdb. Two tables, same shape/intent as
src/data_layer's fetch_log + prices_eod, duplicated rather than shared:
`fetch_log` (one row per (source, trade_date) attempt, 'ok'/'no_data'/
'error' -- see fetch.py's module docstring for the no_data-vs-error
distinction) and `nifty_options_eod` (the extracted rows themselves).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "options_history" / "options_history.duckdb"

SCHEMA = """
CREATE TABLE IF NOT EXISTS fetch_log (
    source        VARCHAR NOT NULL,
    trade_date    DATE NOT NULL,
    status        VARCHAR NOT NULL,   -- 'ok' | 'no_data' | 'error'
    rows_loaded   INTEGER NOT NULL,
    attempted_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (source, trade_date)
);

CREATE TABLE IF NOT EXISTS nifty_options_eod (
    trade_date        DATE NOT NULL,
    expiry_date       DATE NOT NULL,
    strike            DOUBLE NOT NULL,
    option_type       VARCHAR NOT NULL,
    open              DOUBLE,
    high              DOUBLE,
    low               DOUBLE,
    close             DOUBLE,
    settle_price      DOUBLE,
    volume            BIGINT,
    oi                BIGINT,
    underlying_price  DOUBLE,
    contract_name     VARCHAR,
    source            VARCHAR NOT NULL,
    fetched_at        TIMESTAMP NOT NULL
);
"""


def get_connection(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA)
    return con


def fetch_status(con: duckdb.DuckDBPyConnection, source: str, trade_date: dt.date) -> str | None:
    row = con.execute(
        "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [source, trade_date]
    ).fetchone()
    return row[0] if row else None


def log_fetch(con: duckdb.DuckDBPyConnection, source: str, trade_date: dt.date, status: str, rows: int) -> None:
    con.execute("DELETE FROM fetch_log WHERE source = ? AND trade_date = ?", [source, trade_date])
    con.execute(
        "INSERT INTO fetch_log VALUES (?, ?, ?, ?, ?)", [source, trade_date, status, rows, dt.datetime.now()],
    )


def clear_date(con: duckdb.DuckDBPyConnection, trade_date: dt.date) -> None:
    """Deletes any existing nifty_options_eod rows for `trade_date`
    before a fresh insert. Needed because a run killed between
    insert_rows() succeeding and log_fetch('ok') being written (BUGS.md-
    adjacent: found live, 2026-10-12, a resumed run re-fetched and
    re-inserted on top of a killed run's partial insert for 2020-06-18,
    doubling that date's row count) leaves orphaned rows behind that
    fetch_log's own status check cannot see, since fetch_log's row for
    that date was never written as 'ok' in the first place. Call this
    unconditionally before every insert, not just on a detected retry --
    cheap (one indexed-free delete, this table is not large enough to
    matter) and correct regardless of why a date is being (re)inserted."""
    con.execute("DELETE FROM nifty_options_eod WHERE trade_date = ?", [trade_date])


def insert_rows(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = ["trade_date", "expiry_date", "strike", "option_type", "open", "high", "low", "close",
            "settle_price", "volume", "oi", "underlying_price", "contract_name", "source", "fetched_at"]
    values = [[r[c] for c in cols] for r in rows]
    placeholders = ", ".join(["?"] * len(cols))
    con.executemany(f"INSERT INTO nifty_options_eod ({', '.join(cols)}) VALUES ({placeholders})", values)
    return len(rows)


def row_count_for_date(con: duckdb.DuckDBPyConnection, trade_date: dt.date) -> int:
    return con.execute("SELECT COUNT(*) FROM nifty_options_eod WHERE trade_date = ?", [trade_date]).fetchone()[0]
