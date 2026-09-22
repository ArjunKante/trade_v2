"""NSE-hosted XBRL financial-results fetcher.

Why this instead of scraping bseindia.com/corporates/ann.html: bseindia.com's
website disclaimer prohibits reproduction/redistribution/retransmission of
site content, with no carve-out for regulatory filings (see
LICENSE_ASSESSMENT.md). NSE separately hosts the same SEBI-mandated XBRL
taxonomy (the documents are literally in the `in-bse-fin` namespace even when
served from nseindia.com — it is the common national taxonomy, not a
BSE-exclusive one) for its own listed universe, via
nseindia.com/api/corporates-financial-results and the nsearchives.nseindia.com
XBRL archive. This is covered by NSE's own data usage terms, already assessed
for the price data. Since this project's universe is NSE equities, this
source has full coverage and BSE scraping is unnecessary.

CRITICAL: known_date is broadCastDate (the exchange dissemination timestamp),
never financial_year or period_end. A Q1 result filed Aug 12 must be invisible
to any as_of query dated before Aug 12, regardless of which quarter it reports.
"""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import duckdb
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HOME_URL = "https://www.nseindia.com/"
API_URL = "https://www.nseindia.com/api/corporates-financial-results"
SOURCE_NAME = "NSE_XBRL_FINANCIAL_RESULTS"
FALLBACK_LAG_DAYS = 45
FALLBACK_FLAG = "ANNOUNCEMENT_DATE_MISSING_45D_LAG_APPLIED"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _session() -> requests.Session:
    """NSE's API requires a browser-like session: hit the homepage first to
    pick up cookies the WAF expects, then reuse that session for API calls.

    Mounts a retry adapter so a stale pooled connection doesn't silently
    stall every subsequent request. Found live during the Integrated Filing
    backfill: after ~574 successful requests through one reused Session,
    every following request timed out (read timeout=20) with zero
    successes for 59 consecutive attempts -- yet a brand-new, session-less
    request to the same URL immediately after succeeded in 0.4s. That
    points at one dead connection stuck in the session's pool, not a
    server-side block: urllib3's Retry, on a connect/read failure, drops
    the bad connection and grabs a fresh one for the retry rather than
    hammering the same socket, which a bare reused Session does not do on
    its own.

    Kept deliberately to ONE retry, not several: measured live, retrying 3x
    against an already-wedged pool (the initial fix) cost ~45s per failed
    attempt (up to 3 x the ~20s per-request timeout) before the caller's own
    session-rebuild safety net ever got a chance to run -- multiplied across
    ~10 consecutive failures per episode, that was ~7.5 minutes of dead time
    per episode, recurring every ~1,200 requests. A single retry fails fast
    and hands off to the caller's own recovery (a full session rebuild,
    which is what actually fixes a wedged pool) sooner rather than spending
    that time retrying within the same possibly-still-bad pool."""
    retry = Retry(total=1, connect=1, read=1, status=1, backoff_factor=0.3,
                   status_forcelist=[502, 503, 504], allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retry)
    s = requests.Session()
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    s.get(HOME_URL, timeout=30)  # 403 on this response body is normal; cookies still get set
    time.sleep(0.8)
    return s


def fetch_financial_results(
    session: requests.Session, index: str = "equities", period: str = "Quarterly"
) -> list[dict]:
    resp = session.get(
        API_URL,
        params={"index": index, "period": period},
        headers={"Accept": "application/json", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_broadcast_ts(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    return dt.datetime.strptime(raw, "%d-%b-%Y %H:%M:%S")


def to_filings_df(records: list[dict]) -> pd.DataFrame:
    rows = []
    now = dt.datetime.now()
    for r in records:
        broadcast_ts = _parse_broadcast_ts(r.get("broadCastDate"))
        data_quality = None
        if broadcast_ts is None:
            period_end = pd.to_datetime(r.get("toDate"), format="%d-%b-%Y", errors="coerce")
            broadcast_ts = (period_end + pd.Timedelta(days=FALLBACK_LAG_DAYS)) if pd.notna(period_end) else None
            data_quality = FALLBACK_FLAG
        rows.append(
            {
                "isin": r.get("isin"),
                "symbol": r.get("symbol"),
                "company_name": r.get("companyName"),
                "period_start": pd.to_datetime(r.get("fromDate"), format="%d-%b-%Y", errors="coerce").date()
                if r.get("fromDate") else None,
                "period_end": pd.to_datetime(r.get("toDate"), format="%d-%b-%Y", errors="coerce").date(),
                "financial_year": r.get("financialYear"),
                "reporting_quarter": r.get("relatingTo"),
                "consolidated": r.get("consolidated"),
                "audited": r.get("audited"),
                "seq_number": str(r.get("seqNumber")),
                "xbrl_url": r.get("xbrl"),
                "broadcast_ts": broadcast_ts,
                "known_date": broadcast_ts.date() if broadcast_ts is not None else None,
                "data_quality": data_quality,
                "fetched_at": now,
                "source": SOURCE_NAME,
                "revision_seq": 1,
            }
        )
    columns = ["isin", "symbol", "company_name", "period_start", "period_end", "financial_year",
               "reporting_quarter", "consolidated", "audited", "seq_number", "xbrl_url",
               "broadcast_ts", "known_date", "data_quality", "fetched_at", "source", "revision_seq"]
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    return df.dropna(subset=["isin", "period_end", "known_date"])


def load_filings_to_duckdb(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    existing_seqs = set(con.execute("SELECT seq_number FROM fundamentals_filings").fetchdf()["seq_number"])
    new_df = df[~df["seq_number"].isin(existing_seqs)]
    if new_df.empty:
        return 0
    table_column_order = [
        "isin", "symbol", "company_name", "period_start", "period_end", "financial_year",
        "reporting_quarter", "consolidated", "audited", "seq_number", "xbrl_url",
        "broadcast_ts", "known_date", "data_quality", "fetched_at", "source", "revision_seq",
    ]
    con.register("df_new", new_df[table_column_order])
    con.execute("INSERT INTO fundamentals_filings SELECT * FROM df_new")
    con.unregister("df_new")
    return len(new_df)
