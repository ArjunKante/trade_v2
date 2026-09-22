"""Point-in-time selection over fundamentals_filings.

Two independent things must both be handled correctly, and conflating them
is the trap: (1) consolidated-vs-standalone -- pick consolidated where a
company files both, standalone otherwise, never mix within one company's
time series; (2) restatements -- a company can refile the SAME period_end
later (a genuine, real event here: VSTTILLERS' Q3 FY25 result was filed on
time 2025-02-11, lag 42 days, then REFILED 2026-07-30, lag 576 days -- the
same period, two real announcements 536 days apart). A point-in-time query
as_of a date between those two announcements must return the ORIGINAL
version; the restated version did not exist yet.

revision_seq as ingested is not reliable for this: every row is written
with revision_seq=1 (this is DIFFERENT from a re-fetch of the same fact --
each restatement here is a genuinely distinct NSE announcement, its own
seq_number, its own known_date). The correct ordering key is known_date
itself, not a separately-maintained counter, and is computed at read time.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd


def point_in_time_fundamentals(con: duckdb.DuckDBPyConnection, as_of: dt.date) -> pd.DataFrame:
    """One row per (isin, period_end), as knowable at as_of:
    - only rows with known_date <= as_of are visible at all
    - consolidated preferred over standalone, per company-period, independently
    - among visible rows for the winning (isin, period_end, consolidated) key,
      the one with the LATEST known_date wins (the most recent restatement
      the market actually knew about by as_of -- never a later one)
    """
    sql = """
    WITH visible AS (
        SELECT * FROM fundamentals_filings WHERE known_date <= ?
    ),
    ranked_within_type AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY isin, period_end, consolidated
                   ORDER BY known_date DESC, seq_number DESC
               ) AS _rn
        FROM visible
    ),
    latest_per_type AS (
        SELECT * FROM ranked_within_type WHERE _rn = 1
    ),
    type_priority AS (
        SELECT *,
               CASE WHEN consolidated = 'Consolidated' THEN 0 ELSE 1 END AS _pref,
               ROW_NUMBER() OVER (
                   PARTITION BY isin, period_end
                   ORDER BY (CASE WHEN consolidated = 'Consolidated' THEN 0 ELSE 1 END)
               ) AS _type_rn
        FROM latest_per_type
    )
    SELECT * EXCLUDE (_rn, _pref, _type_rn) FROM type_priority WHERE _type_rn = 1
    """
    df = con.execute(sql, [as_of]).fetchdf()
    return df
