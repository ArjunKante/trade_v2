"""Step 3's chunking, truncation-detection-with-retry, and download-plan
logic -- pure functions (dependency-injected API calls), testable without a
live connection. Orchestration (login, DB writes, logging, throttling,
stop-on-rate-limit) lives in scripts/fibo_download_intraday.py, which
imports these.

THE TRUNCATION PITFALL (Step 1's finding, restated here because this module
exists specifically to never accept it silently): Angel One's getCandleData
does not error on an oversized request -- it silently returns only the most
recent slice ending at `todate`. CHUNK_DAYS=25 is comfortably under the
documented 30-day ONE_MINUTE cap (confirmed live against
https://smartapi.angelone.in/docs/Historical), so truncation is not
EXPECTED to occur in normal operation -- but `fetch_chunk_with_retry` checks
for it on every single chunk and splits smaller rather than ever assuming
the requested range came back intact.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd
import requests

ANGEL_SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"

CHUNK_DAYS = 25
MIN_CHUNK_DAYS = 3
TRUNCATION_SLACK_DAYS = 2  # absorbs the ordinary case of a requested start on a weekend/holiday

# Two DIFFERENT failure shapes the live download needs to tell apart (found
# live, the second one the hard way -- see scripts/fibo_download_intraday.py's
# module docstring): a rate-limit/access-denied error means STOP (the account
# is fine, we are hammering it too fast); a token-expiry error means the
# session died of old age on a multi-hour run and a fresh login() fixes it --
# treating the two the same either stops a perfectly healthy run early, or
# (the bug actually hit) retries a dead session on every remaining chunk.
RATE_LIMIT_KEYWORDS = ("rate", "too many", "exceed", "access denied", "403", "throttl")
TOKEN_EXPIRY_KEYWORDS = ("invalid token", "token expired", "session expired", "jwt", "unauthorized", "invalid session")


def looks_rate_limited(msg: str) -> bool:
    low = (msg or "").lower()
    return any(k in low for k in RATE_LIMIT_KEYWORDS)


def looks_token_expired(msg: str) -> bool:
    low = (msg or "").lower()
    return any(k in low for k in TOKEN_EXPIRY_KEYWORDS)


def chunk_date_ranges(start: dt.date, end: dt.date, chunk_days: int = CHUNK_DAYS) -> list[tuple[dt.date, dt.date]]:
    """[start, end] split into <=chunk_days pieces, inclusive, non-overlapping, in order."""
    ranges = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + dt.timedelta(days=chunk_days - 1), end)
        ranges.append((cur, chunk_end))
        cur = chunk_end + dt.timedelta(days=1)
    return ranges


def is_truncated(requested_start: dt.date, first_candle_date: dt.date, slack_days: int = TRUNCATION_SLACK_DAYS) -> bool:
    """True if the first returned candle is suspiciously later than the
    requested start -- the silent-truncation signature found in Step 1.
    `slack_days` absorbs an ordinary weekend/holiday gap at the start of
    the requested window (not itself a truncation)."""
    return (first_candle_date - requested_start).days > slack_days


def fetch_chunk_with_retry(call_fn, start: dt.date, end: dt.date,
                            min_chunk_days: int = MIN_CHUNK_DAYS) -> tuple[list | None, str | None]:
    """call_fn(start, end) -> (candles, err), candles is Angel's raw
    [[iso_ts, o, h, l, c, v], ...] list. Detects truncation
    (module docstring) and recursively splits the range smaller, reassembling
    sub-results, rather than ever accepting a truncated response. Returns
    (candles, note) on success (note is non-None only if a split happened,
    for logging) or (None, error_message) on a real API error.

    Raises RuntimeError if truncation persists even at min_chunk_days --
    an unexpected condition (would mean Angel's real per-request limit is
    smaller than assumed), stop-worthy, never silently accepted."""
    data, err = call_fn(start, end)
    if err is not None:
        return None, err
    if not data:
        return [], None

    first_date = dt.date.fromisoformat(data[0][0][:10])
    if not is_truncated(start, first_date):
        return data, None

    span_days = (end - start).days + 1
    if span_days <= min_chunk_days:
        raise RuntimeError(
            f"chunk [{start},{end}] (span={span_days}d) still truncated (first candle "
            f"{first_date}, requested start {start}) even at min_chunk_days={min_chunk_days} -- "
            f"unexpected; Angel's real limit may be smaller than assumed. Stopping rather than "
            f"silently accepting a short chunk."
        )
    half = max(min_chunk_days, span_days // 2)
    mid = start + dt.timedelta(days=half - 1)

    # NOTE: failure is signaled by the DATA being None, never by the second
    # return value alone -- a successful recursive call that ITSELF had to
    # split further also returns a non-None "note" as its second value, so
    # checking `if lerr is not None` here (an earlier version of this
    # function did exactly that) would wrongly treat a successful nested
    # split as an error and discard perfectly good candles.
    left, lnote = fetch_chunk_with_retry(call_fn, start, mid, min_chunk_days)
    if left is None:
        return None, lnote
    right, rnote = fetch_chunk_with_retry(call_fn, mid + dt.timedelta(days=1), end, min_chunk_days)
    if right is None:
        return None, rnote
    return (left or []) + (right or []), f"split [{start},{end}] into halves due to truncation at full size"


def build_download_plan(universe: pd.DataFrame, entity_to_token: dict, dev_start: dt.date, full_end: dt.date,
                         chunk_days: int = CHUNK_DAYS) -> pd.DataFrame:
    """[entity_id, year, start, end, n_chunks] -- one row per (entity, year)
    that has a resolved token, covering that year's membership window
    clipped to [dev_start, full_end]. The Oct-Dec dev_start.year stub (no
    reconstituted universe exists for a partial first year, per
    src/fibo/universe.py's own documented gap) reuses the NEXT
    reconstituted year's membership list -- the nearest defined one,
    flagged here rather than silently assumed."""
    rows = []
    years = sorted(universe["year"].unique())
    stub_year = dev_start.year
    if stub_year not in years and years and years[0] > stub_year:
        stub_members = set(universe.loc[universe["year"] == years[0], "entity_id"])
        stub_end = min(dt.date(stub_year, 12, 31), full_end)
        for eid in stub_members:
            if eid in entity_to_token:
                rows.append((eid, stub_year, dev_start, stub_end))

    for y in years:
        y_start = max(dt.date(y, 1, 1), dev_start)
        y_end = min(dt.date(y, 12, 31), full_end)
        if y_start > y_end:
            continue
        members = set(universe.loc[universe["year"] == y, "entity_id"])
        for eid in members:
            if eid in entity_to_token:
                rows.append((eid, y, y_start, y_end))

    plan = pd.DataFrame(rows, columns=["entity_id", "year", "start", "end"])
    plan["n_chunks"] = plan.apply(lambda r: len(chunk_date_ranges(r["start"], r["end"], chunk_days)), axis=1)
    return plan.sort_values(["entity_id", "year"]).reset_index(drop=True)


def resolve_entity_tokens(con: duckdb.DuckDBPyConnection, entity_ids: list[str]) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """[entity_id, isin, symbol, token] for every entity resolvable against
    Angel One's current NSE-EQ instrument master, using each entity's MOST
    RECENTLY OBSERVED symbol in prices_eod (handles a symbol rename over
    the entity's lifetime the same way corporate_actions/isin_lineage
    already do -- use the latest known identity, not the first).

    Returns (resolved_df, missing) where `missing` is [(entity_id, symbol)]
    for every entity NOT found in Angel's master -- typically a name since
    delisted, merged, or renamed (Angel's master is a snapshot of what's
    CURRENTLY listed, not a historical registry). Every entity gets a
    verdict; none is silently dropped."""
    placeholders = ", ".join(["?"] * len(entity_ids))
    sym_df = con.execute(
        f"""
        SELECT l.entity_id, p.isin, p.symbol, MAX(p.trade_date) AS last_seen
        FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
        WHERE l.entity_id IN ({placeholders})
        GROUP BY l.entity_id, p.isin, p.symbol
        """,
        entity_ids,
    ).fetchdf()
    sym_df = sym_df.sort_values("last_seen").drop_duplicates("entity_id", keep="last")

    master = requests.get(ANGEL_SCRIP_MASTER_URL, timeout=60).json()
    token_map = {row["symbol"]: row["token"] for row in master
                 if row.get("exch_seg") == "NSE" and row.get("symbol", "").endswith("-EQ")}

    resolved_rows, missing = [], []
    for _, r in sym_df.iterrows():
        key = f"{r['symbol']}-EQ"
        if key in token_map:
            resolved_rows.append({"entity_id": r["entity_id"], "isin": r["isin"], "symbol": r["symbol"], "token": token_map[key]})
        else:
            missing.append((r["entity_id"], r["symbol"]))

    resolved = pd.DataFrame(resolved_rows, columns=["entity_id", "isin", "symbol", "token"])
    return resolved, missing
