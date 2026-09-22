"""DuckDB connection and append-only schema for the point-in-time warehouse.

Every table carries known_date (when the fact became knowable to a market
participant), fetched_at (when we actually retrieved it), source, and
revision_seq. Tables are append-only: corrections are new rows with a higher
revision_seq for the same natural key, never UPDATE/DELETE.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import pandas as pd

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prices_eod (
    isin            VARCHAR NOT NULL,
    trade_date      DATE NOT NULL,
    symbol          VARCHAR NOT NULL,
    series          VARCHAR NOT NULL,
    open            DOUBLE,
    high            DOUBLE,
    low             DOUBLE,
    close           DOUBLE,
    last            DOUBLE,
    prev_close      DOUBLE,
    volume          BIGINT,
    turnover        DOUBLE,
    n_trades        BIGINT,
    known_date      DATE NOT NULL,
    fetched_at      TIMESTAMP NOT NULL,
    source          VARCHAR NOT NULL,
    revision_seq    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fundamentals_filings (
    isin             VARCHAR NOT NULL,
    symbol           VARCHAR NOT NULL,
    company_name     VARCHAR,
    period_start     DATE,
    period_end       DATE NOT NULL,
    financial_year   VARCHAR,
    reporting_quarter VARCHAR,
    consolidated     VARCHAR,
    audited          VARCHAR,
    seq_number       VARCHAR NOT NULL,
    xbrl_url         VARCHAR,
    broadcast_ts     TIMESTAMP,
    known_date       DATE NOT NULL,
    data_quality     VARCHAR,
    fetched_at       TIMESTAMP NOT NULL,
    source           VARCHAR NOT NULL,
    revision_seq     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS corporate_actions (
    isin          VARCHAR NOT NULL,   -- resolved via (symbol, ex_date) against our own price observations
    symbol        VARCHAR NOT NULL,
    ex_date       DATE NOT NULL,
    action_type   VARCHAR NOT NULL,   -- 'bonus' | 'split'
    ratio         DOUBLE NOT NULL,    -- multiplicative factor for this one component
    subject_raw   VARCHAR,
    feed_isin     VARCHAR,            -- the feed's own (unreliable -- original-ISIN) isin field, kept for audit
    known_date    DATE NOT NULL,
    fetched_at    TIMESTAMP NOT NULL,
    source        VARCHAR NOT NULL,
    revision_seq  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS index_eod (
    index_name    VARCHAR NOT NULL,
    trade_date    DATE NOT NULL,
    open          DOUBLE,
    high          DOUBLE,
    low           DOUBLE,
    close         DOUBLE,
    known_date    DATE NOT NULL,
    fetched_at    TIMESTAMP NOT NULL,
    source        VARCHAR NOT NULL,
    revision_seq  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_prices_daily (
    entity_id     VARCHAR NOT NULL,
    trade_date    DATE NOT NULL,
    isin          VARCHAR NOT NULL,
    raw_close     DOUBLE,
    adjusted_close DOUBLE,
    volume        BIGINT,
    turnover      DOUBLE,
    known_date    DATE NOT NULL,
    fetched_at    TIMESTAMP NOT NULL,
    source        VARCHAR NOT NULL,
    revision_seq  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fetch_log (
    source        VARCHAR NOT NULL,
    trade_date    DATE NOT NULL,
    status        VARCHAR NOT NULL,   -- 'ok' | 'no_data' | 'error'
    rows_loaded   INTEGER NOT NULL,
    attempted_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (source, trade_date)
);

CREATE TABLE IF NOT EXISTS isin_lineage (
    isin              VARCHAR NOT NULL,
    entity_id         VARCHAR NOT NULL,   -- earliest ISIN in the linked chain
    predecessor_isin  VARCHAR,            -- NULL if this ISIN is its chain's first
    link_method       VARCHAR NOT NULL,   -- 'nsdl_structural' | 'chain_start'
    known_date        DATE NOT NULL,      -- the historical transition date, NEVER "now"
    fetched_at        TIMESTAMP NOT NULL,
    source            VARCHAR NOT NULL,
    revision_seq      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS isin_lineage_ambiguous (
    symbol       VARCHAR NOT NULL,
    isin_a       VARCHAR NOT NULL,
    isin_b       VARCHAR NOT NULL,
    reason       VARCHAR NOT NULL,
    detected_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS adjustment_factors (
    entity_id     VARCHAR NOT NULL,   -- spans the full lineage chain, not a bare ISIN
    trade_date    DATE NOT NULL,
    factor        DOUBLE NOT NULL,
    known_date    DATE NOT NULL,      -- = trade_date: a factor for date d is only knowable once d's own known_date arrives
    fetched_at    TIMESTAMP NOT NULL,
    source        VARCHAR NOT NULL,
    revision_seq  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fundamentals_xbrl_facts (
    isin             VARCHAR NOT NULL,
    seq_number       VARCHAR NOT NULL,
    period_end       DATE NOT NULL,
    consolidated     VARCHAR,
    context_ref      VARCHAR,
    tag              VARCHAR NOT NULL,
    value            VARCHAR,
    unit             VARCHAR,
    known_date       DATE NOT NULL,
    fetched_at       TIMESTAMP NOT NULL,
    source           VARCHAR NOT NULL,
    revision_seq     INTEGER NOT NULL
);

-- Without this, load_facts_to_duckdb's existence check (WHERE seq_number = ?)
-- is a full table scan repeated on every one of tens of thousands of calls in
-- a bulk extraction -- found live during the Phase E quarterly XBRL
-- extraction: observed throughput was ~6s/document against a 0.33s throttle,
-- traced to exactly this scan against a table already at 2.5M+ rows from the
-- annual extraction. The caller-side in-memory dedup set makes the check
-- itself redundant for that workflow, but removing it would risk silent
-- duplicate rows from any future caller that doesn't pre-check -- indexing
-- instead of removing keeps the safety and fixes the cost.
CREATE INDEX IF NOT EXISTS idx_fundamentals_xbrl_facts_seq ON fundamentals_xbrl_facts(seq_number);

-- Added when a second source (Integrated Filing, in-capmkt taxonomy) started
-- sharing this table with the original quarterly/annual sources: seq_number
-- is only unique WITHIN one source's own ID space, and the two sources'
-- numeric ranges were found to overlap (Integrated Filing's seq_Id ~190k-545k
-- falls inside the older sources' ~11-1.2M range). load_facts_to_duckdb's
-- existence check is now scoped by (source, seq_number) together; this index
-- backs that scoped lookup the same way the seq_number-only index backs the
-- original single-source check.
CREATE INDEX IF NOT EXISTS idx_fundamentals_xbrl_facts_source_seq ON fundamentals_xbrl_facts(source, seq_number);
"""


def get_connection(duckdb_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Read-write connection. Runs schema DDL. For ingestion/materialization
    scripts ONLY -- never import this into a report."""
    duckdb_path = Path(duckdb_path)
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(duckdb_path))
    con.execute(SCHEMA_SQL)
    return con


def get_read_connection(duckdb_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Read-only connection for reports and analysis. Cannot run DDL or
    INSERT/UPDATE/DELETE -- DuckDB enforces this at the connection level, so
    a report that accidentally imports a write function fails loudly instead
    of quietly materializing on every invocation. The prior project had a
    report call materialize_factors() as a side effect of computing adjusted
    prices, which meant reading data held a write lock and one report run
    took 33 minutes. Materialization is a distinctly-named, separately-run
    script (scripts/materialize_*.py, scripts/ingest_*.py); reports import
    only read functions."""
    return duckdb.connect(str(duckdb_path), read_only=True)


def read_latest(con: duckdb.DuckDBPyConnection, table: str, key_cols: list[str], where: str = "1=1") -> pd.DataFrame:
    """Read a fact table deduped to exactly one row per logical key (highest
    revision_seq wins). Every reader must go through this rather than a bare
    SELECT * -- the invariant this project depends on is ONE ROW PER LOGICAL
    KEY, and the prior project's shared loader had no revision dedup at all.
    It was correct for eighteen months purely because no key had ever
    received a second revision; the first time a backfill created one, every
    downstream reader silently doubled its row count with no error anywhere.
    See tests/test_revision_dedup_canary.py for the regression test."""
    key_list = ", ".join(key_cols)
    sql = f"""
        SELECT * EXCLUDE (_rn) FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY {key_list} ORDER BY revision_seq DESC) AS _rn
            FROM {table} WHERE {where}
        ) WHERE _rn = 1
    """
    return con.execute(sql).fetchdf()


class HoldoutViolationError(Exception):
    """Raised when a query would return data from beyond the allowed as_of date."""


def query_as_of(
    con: duckdb.DuckDBPyConnection,
    table: str,
    as_of: dt.date,
    where_extra: str = "1=1",
    known_date_col: str = "known_date",
):
    """Query a table restricted to known_date <= as_of, then verify in code.

    The WHERE clause does the filtering; the assertion afterwards is defense
    in depth so a future refactor that drops the WHERE clause fails loudly
    instead of silently leaking future information, per the prior project's
    lesson about an unchecked date boundary.
    """
    sql = f"SELECT * FROM {table} WHERE {known_date_col} <= ? AND ({where_extra})"
    df = con.execute(sql, [as_of]).fetchdf()
    as_of_ts = pd.Timestamp(as_of)
    if not df.empty and (pd.to_datetime(df[known_date_col]) > as_of_ts).any():
        raise HoldoutViolationError(
            f"query_as_of on {table} returned {known_date_col} > {as_of}; "
            "this must never happen — investigate immediately."
        )
    return df
