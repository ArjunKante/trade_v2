"""Minimal XBRL fact extractor for NSE/BSE-hosted SEBI financial-disclosure
taxonomies.

Deliberately dumb: pulls every tagged numeric/text fact into a long
(isin, tag, value, context) table rather than hand-mapping a wide schema.
Each taxonomy has hundreds of tags and varies by filing (segment reporting,
exceptional items, etc.) — factor code picks the handful of tags it needs
(RevenueFromOperations, ProfitLossForPeriod, EPS variants, ...) at the point
of use. Balance-sheet tags (assets, equity, debt) only appear in
annual/half-yearly filings, not every quarter — this is a real limitation on
value/quality factor refresh frequency in India, not a parsing bug.

Two taxonomies are read through this one parser: `in-bse-fin` (pre-April-2025
quarterly/annual "Financial Results" filings) and `in-capmkt` (the Integrated
Filing format that replaced it). Investigated directly against real documents
before writing this, not assumed: the tag VOCABULARY carried over almost
completely between the two (RevenueFromOperations, Assets, Equity, etc. are
the identical local tag name under both namespaces) — only the namespace
prefix differs, so the regex matches any `in-<suffix>` prefix rather than
hardcoding one, and the same downstream factor code that names tags by their
local name works unmodified against either taxonomy's facts. Context IDs
also gained underscore-containing forms in the new taxonomy (`I_Audited`,
`PY_I`) not present in the old (`OneD`, `FourD`) — the context pattern
allows underscores so both taxonomies parse under the same regex.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import duckdb
import pandas as pd

_FACT_RE = re.compile(
    r'<(?P<ns>in-[A-Za-z0-9-]+):(?P<tag>[A-Za-z0-9]+)\s+contextRef="(?P<ctx>[A-Za-z0-9_]+)"'
    r'(?:\s+unitRef="(?P<unit>[A-Za-z]+)")?[^>]*>(?P<value>[^<]*)</(?P=ns):(?P=tag)>'
)


def parse_xbrl_facts(xml_text: str) -> list[dict]:
    facts = []
    for m in _FACT_RE.finditer(xml_text):
        facts.append(
            {
                "context_ref": m.group("ctx"),
                "tag": m.group("tag"),
                "unit": m.group("unit"),
                "value": m.group("value"),
            }
        )
    return facts


def extract_isin(facts: list[dict]) -> str | None:
    """The Integrated Filing taxonomy tags ISIN directly inside the document
    body (tag "ISIN", context "OneD") rather than exposing it on the list
    API the way the old `corporates-financial-results` endpoint did. Parsed
    from each document's own facts, never joined in via symbol -- 11.1% of
    symbols in this project's own price history (440 of 3,971) have mapped
    to more than one ISIN over time, so a symbol-keyed join would risk
    silently attaching one company's fundamentals to another's prices.
    Returns None (never a guess) if no ISIN fact is present, so the caller
    can skip and count the document rather than insert an unverified isin."""
    for f in facts:
        if f["tag"] == "ISIN" and f["value"]:
            return f["value"].strip()
    return None


def facts_to_df(
    facts: list[dict], isin: str, seq_number: str, period_end: dt.date,
    consolidated: str, known_date: dt.date, source: str,
) -> pd.DataFrame:
    now = dt.datetime.now()
    df = pd.DataFrame(facts)
    df["isin"] = isin
    df["seq_number"] = seq_number
    df["period_end"] = period_end
    df["consolidated"] = consolidated
    df["known_date"] = known_date
    df["fetched_at"] = now
    df["source"] = source
    df["revision_seq"] = 1
    table_column_order = [
        "isin", "seq_number", "period_end", "consolidated", "context_ref", "tag",
        "value", "unit", "known_date", "fetched_at", "source", "revision_seq",
    ]
    return df[table_column_order]


def load_facts_to_duckdb(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    """Existence check is scoped by (source, seq_number), never seq_number
    alone. seq_number is only unique WITHIN one source's own ID space --
    confirmed a real risk, not theoretical, before this was scoped: the
    Integrated Filing taxonomy's seq_Id values (observed ~190k-545k) overlap
    the numeric range already used by the older quarterly/annual sources
    (11 to ~1.2M) in this same table. A bare seq_number check would silently
    skip a genuine new fact from one source because an unrelated fact from a
    different source happened to reuse the same number, or -- worse -- treat
    the two as the same filing on read. No live collision was found in a
    spot sample, but the ranges overlap enough that this needed fixing
    before ingesting a second source into the same table, not after finding
    a corrupted row."""
    if df.empty:
        return 0
    existing = con.execute(
        "SELECT DISTINCT seq_number FROM fundamentals_xbrl_facts WHERE seq_number = ? AND source = ?",
        [df["seq_number"].iloc[0], df["source"].iloc[0]],
    ).fetchdf()
    if not existing.empty:
        return 0
    con.register("facts_new", df)
    con.execute("INSERT INTO fundamentals_xbrl_facts SELECT * FROM facts_new")
    con.unregister("facts_new")
    return len(df)
