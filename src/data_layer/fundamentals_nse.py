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


def resolve_isin_for_filings(filings_df: pd.DataFrame, symbol_obs: pd.DataFrame) -> pd.DataFrame:
    """Resolve each filing's true ISIN via (symbol, known_date) against our
    own price observations -- the exact mechanism corporate_actions.py's
    resolve_isin_for_actions already established, ported here because this
    feed has the identical defect. Confirmed live (2026-09-24) against NSE's
    corporates-financial-results API: BHEL's FY2024 annual filing (broadcast
    2024-05-21) is tagged isin=INE257A01018 -- one NSDL serial behind the
    ISIN this warehouse's own price feed uses for BHEL (INE257A01026), which
    never appears in prices_eod at all. Same for NATIONALUM, GRANULES,
    AUROPHARMA, and (scoped directly) 166 of 2,487 distinct ISINs project-
    wide (83% of the 200 that never matched prices_eod) -- systemic, not a
    handful of edge cases.

    THIS IS THE FOURTH OCCURRENCE, PER THIS PROJECT'S OWN RECORD, OF THE
    SAME META-PATTERN: a fix applied where the bug was first noticed, not
    everywhere the same feed-ISIN-unreliability pattern occurs. Bug #2
    (BUGS.md) already needed its own gap-awareness fix applied independently
    to momentum.py, lowvol.py, AND target.py rather than shared once; this
    is the same lesson at the module level -- corporate_actions.py solved
    "the feed's isin field cannot be trusted" for corporate actions, and
    that fix was never checked against the OTHER NSE feed (financial
    results) using the identical isin field for the identical reason.

    Point-in-time by (symbol, known_date) -- NEVER "symbol's current ISIN".
    11.1% of symbols in this project's own isin_lineage have mapped to more
    than one ISIN over time; a naive current-ISIN join would misattribute
    an older filing to a company's NEWER ISIN, exactly the cross-company/
    cross-period contamination this document-body ISIN-parsing discipline
    exists to prevent elsewhere in this project.

    Unlike corporate_actions.py, does NOT persist a feed_isin audit column
    -- fundamentals_filings/fundamentals_xbrl_facts already exist in the
    live warehouse with a fixed schema, and adding a column is a deliberate
    migration this fix does not make. The original (wrong) feed isin is not
    retained; it is recoverable from a fresh NSE pull if ever needed. Stated
    as a scope decision, not a silent omission.

    BACKWARD-PREFERRED, forward only as a fallback -- fixed 2026-09-26 after
    shipping the opposite preference by mistake. The first version of this
    function copied resolve_isin_for_actions' FORWARD-preferred direction
    wholesale, without re-deriving whether the reason it was correct there
    still held here. It did not: an action's ex_date structurally anchors
    at the ISIN transition (the action CAUSES the change), so searching
    forward from ex_date naturally lands on the post-action ISIN -- that is
    what makes forward-preference correct for corporate_actions.py. A
    filing's known_date has no such relationship to any ISIN change; it is
    just "when this became public." Confirmed live: BURNPUR's 2025-02-10
    and 2025-03-11 filings, and four of SUMEETINDS', have known_dates
    falling inside the calendar gap between an old ISIN's last trade and a
    new ISIN's first (BURNPUR: 2025-01-29 -> 2026-08-11, 559 days). The
    forward-preferred version resolved both to the ISIN that would not
    start trading for another 17 months -- attributing a filing to an
    identity that did not exist yet at the time it was made public.

    Backward-first is what belongs here, and matches every other point-in-
    time convention in this codebase (`known_date <= as_of`,
    build_entity_resolver, guard_date_range): resolve to whichever ISIN was
    ACTUALLY trading as of known_date; only fall forward to a later
    observation when no prior one exists at all (a company's very first
    filing, disclosed before this warehouse's price history for it begins).

    The general lesson, not just this instance: when porting logic between
    contexts, re-derive the ASSUMPTIONS the logic depends on, not just the
    code that implements it. An assumption that holds in the source context
    (here: "the anchoring event causes the identity change") does not
    automatically travel with the function into a context where the
    anchoring event has no such causal relationship. This is a different
    failure shape from the five fix-not-propagated instances already on
    record in this project (BUGS.md) -- not "the fix wasn't applied
    everywhere the bug occurs," but "the fix was applied everywhere, and
    carried an unexamined assumption into a place it didn't hold."

    Also worth recording plainly: the error direction this shipped with was
    CONSERVATIVE, not a lookahead -- a misattributed filing vanished from
    every as-of query for the gap window and reappeared late, rather than
    becoming visible before it should have. That was luck, not design. The
    same directional mismatch the other way -- a context where the wrong
    preference resolves a document EARLY instead of late -- would have been
    a genuine leak, not a delay, and nothing about how this bug was written
    would have prevented that version of it.
    """
    filings_df = filings_df.rename(columns={"isin": "feed_isin"}).copy()
    symbol_obs = symbol_obs.copy()
    filings_df["known_date"] = pd.to_datetime(filings_df["known_date"]).astype("datetime64[ns]")
    symbol_obs["trade_date"] = pd.to_datetime(symbol_obs["trade_date"]).astype("datetime64[ns]")
    filings_df = filings_df.sort_values("known_date").reset_index(drop=True)
    symbol_obs = symbol_obs.sort_values("trade_date").reset_index(drop=True)

    resolved_parts = []
    for direction in ["backward", "forward"]:
        merged = pd.merge_asof(
            filings_df, symbol_obs, left_on="known_date", right_on="trade_date",
            by="symbol", direction=direction,
        )
        resolved_parts.append(merged["isin"])

    backward_isin, forward_isin = resolved_parts
    resolved = backward_isin.combine_first(forward_isin)
    filings_df["isin"] = resolved
    filings_df = filings_df.drop(columns=["feed_isin"])
    return filings_df


def to_filings_df(records: list[dict], symbol_obs: pd.DataFrame | None = None) -> pd.DataFrame:
    """symbol_obs: pass data_layer.corporate_actions.build_symbol_isin_
    observations(con) to resolve each filing's ISIN point-in-time against
    this warehouse's own price observations (see resolve_isin_for_filings).
    Optional and defaults to None (the feed's raw, unreliable isin passed
    through unchanged) so existing callers/tests that predate this fix keep
    their exact prior behavior -- every real ingestion path should pass it."""
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
    df = df.dropna(subset=["isin", "period_end", "known_date"])
    if symbol_obs is not None:
        df = resolve_isin_for_filings(df, symbol_obs)
        df = df.dropna(subset=["isin"])  # symbol never observed in prices_eod at all -- genuinely unresolvable, not guessed
    return df


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
