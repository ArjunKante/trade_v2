"""NSE-hosted Integrated Filing-Financials fetcher -- the format that
replaced quarterly/annual "Financial Results" filings from April 2025
onward (SEBI's Integrated Filing mandate). Same `nseindia.com` /
`nsearchives.nseindia.com` hosts and terms already assessed for the old
format (`fundamentals_nse.py`, `LICENSE_ASSESSMENT.md` section D) -- this is
a different SEBI-issued taxonomy (`in-capmkt`, not `in-bse-fin`) served from
the same regulatory-filings archive, not a different data source.

Two things this format does differently from the old one, both handled
here rather than assumed away:

1. ISIN is not on the list-metadata API (unlike the old `isin` field on
   `corporates-financial-results`) -- it is tagged inside each document
   body instead (`xbrl_parser.extract_isin`). Never resolved by joining the
   list API's `symbol` to this project's own most-recent-known ISIN for
   that symbol: 11.1% of symbols in this project's own price history (440
   of 3,971) have mapped to more than one ISIN over time, so a symbol join
   would risk silently attaching one company's fundamentals to another's
   prices. The correct identity for every fact loaded from this source
   comes only from parsing that fact's own document.

2. `known_date` is split across two mutually-exclusive fields instead of
   one: `broadcast_Date` (populated only when `type_Sub == "Original"`) and
   `revised_Date` (populated only when `type_Sub == "Revision"`). Verified
   on the full 26,829-record dataset available at investigation time: this
   split is total and exact (zero rows with both null, zero with both
   populated) -- not a fallback for an edge case, the actual rule.
"""
from __future__ import annotations

import datetime as dt
import time

import duckdb
import pandas as pd
import requests

from data_layer.fundamentals_nse import _session  # noqa: F401 -- re-exported for callers

API_URL = "https://www.nseindia.com/api/integrated-filing-results"
SOURCE_NAME = "NSE_INTEGRATED_FILING_FINANCIALS"
FILING_TYPE = "Integrated Filing- Financials"


def fetch_integrated_filing_page(
    session: requests.Session, page: int, size: int = 1000, type_: str = FILING_TYPE
) -> dict:
    resp = session.get(
        API_URL,
        params={"type": type_, "page": page, "size": size},
        headers={"Accept": "application/json", "Referer": "https://www.nseindia.com/companies-listing/corporate-integrated-filing"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_all_integrated_filing_metadata(
    session: requests.Session, size: int = 1000, type_: str = FILING_TYPE, sleep_seconds: float = 0.33
) -> list[dict]:
    """Paginates through the full list -- the endpoint itself does not
    return everything in one call (unlike the old `corporates-financial-
    results`, which does).

    `totalCount` is NOT a trustworthy stopping bound -- confirmed directly,
    not assumed: four consecutive calls a few seconds apart returned
    26765, 26765, 26765, then 26829, because this list is live and mutating
    (new filings and revisions arrive continuously) and offset-based
    pagination against it can also skip or duplicate rows at page
    boundaries as records shift underneath it. Using `totalCount` from a
    single page as an exact cutoff caused an early, silent stop at 3,000 of
    ~26,800 records on the first real run -- caught before it fed a partial
    metadata set into the fetcher, not after.

    The robust signal is a page returning fewer rows than requested (the
    dataset is actually exhausted), not any particular `totalCount` value.
    A generous multiple of the largest `totalCount` ever observed is kept
    only as a runaway-loop safety net, not as the primary stop condition."""
    page = 1
    all_rows: list[dict] = []
    max_total_seen = 0
    while True:
        j = fetch_integrated_filing_page(session, page=page, size=size, type_=type_)
        max_total_seen = max(max_total_seen, j.get("totalCount", 0))
        rows = j.get("data", [])
        all_rows.extend(rows)
        if len(rows) < size:
            break
        if max_total_seen and len(all_rows) >= max_total_seen * 2:
            raise RuntimeError(
                f"fetch_all_integrated_filing_metadata: collected {len(all_rows)} rows, more than "
                f"double the largest totalCount seen ({max_total_seen}) -- pagination is not "
                f"terminating normally, stopping rather than looping indefinitely."
            )
        page += 1
        time.sleep(sleep_seconds)
    return all_rows


def _parse_nse_datetime(raw: str | None) -> dt.datetime | None:
    """NSE's own API is inconsistent about month-abbreviation case between
    fields (`broadcast_Date` uses "Sep", `revised_Date` uses "SEP" in the
    same response) -- confirmed directly, not assumed. Python's strptime
    matches `%b` case-insensitively, so one format string covers both."""
    if not raw:
        return None
    return dt.datetime.strptime(raw, "%d-%b-%Y %H:%M:%S")


def _parse_qe_date(raw: str) -> dt.date:
    return dt.datetime.strptime(raw, "%d-%b-%Y").date()


def to_metadata_df(records: list[dict]) -> pd.DataFrame:
    """One row per filing metadata record, with known_date derived per the
    Original/Revision split documented in the module docstring. isin is
    NOT populated here -- it is only known after the document body is
    parsed; see extract_isin in xbrl_parser.py."""
    rows = []
    now = dt.datetime.now()
    for r in records:
        type_sub = r.get("type_Sub")
        broadcast_dt = _parse_nse_datetime(r.get("broadcast_Date"))
        revised_dt = _parse_nse_datetime(r.get("revised_Date"))
        known_dt = broadcast_dt if type_sub == "Original" else revised_dt
        if known_dt is None:
            # neither field populated for this row's type_Sub -- do not guess
            known_dt = revised_dt or broadcast_dt
        qe_date = r.get("qe_Date")
        rows.append(
            {
                "symbol": r.get("symbol"),
                "company_name": r.get("cmName"),
                "period_end": _parse_qe_date(qe_date) if qe_date else None,
                "consolidated": r.get("consolidated"),
                "audited": r.get("audited"),
                "type_sub": type_sub,
                "revision_remark": r.get("revision_Remark"),
                "seq_number": str(r.get("seq_Id")),
                "xbrl_url": r.get("xbrl"),
                "broadcast_ts": broadcast_dt,
                "revised_ts": revised_dt,
                "known_date": known_dt.date() if known_dt is not None else None,
                "fetched_at": now,
                "source": SOURCE_NAME,
            }
        )
    columns = [
        "symbol", "company_name", "period_end", "consolidated", "audited", "type_sub",
        "revision_remark", "seq_number", "xbrl_url", "broadcast_ts", "revised_ts",
        "known_date", "fetched_at", "source",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    return df.dropna(subset=["symbol", "period_end", "known_date", "xbrl_url"])


def scope_to_price_covered_symbols(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> pd.DataFrame:
    """Same cut as Phase C's quarterly XBRL extraction: an entity with no
    price coverage at all can never contribute to any IC calculation, so
    fetching its filings is pure waste. Scoped by SYMBOL here only as a
    coarse pre-fetch filter to decide what to download -- never as a
    substitute for the real per-document ISIN identity (see module
    docstring). A symbol appearing in this project's price history under a
    different ISIN at a different time is still fetched; the document's own
    parsed ISIN is what ultimately gets attached to it, not this symbol."""
    price_symbols = set(con.execute("SELECT DISTINCT symbol FROM prices_eod").fetchdf()["symbol"])
    return df[df["symbol"].isin(price_symbols)].copy()
