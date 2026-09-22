"""NSE corporate actions (bonus/split) ingestion.

Scope, deliberately narrow: only bonus and face-value-split events are
parsed into a price-adjustment ratio. These are the two event types that
fabricate a raw-price discontinuity if left unadjusted (a split literally
divides the traded price). Dividends, buybacks, AGMs, rights issues, and
"Capital Reduction" are real corporate actions but do not corrupt a naive
return calculation the same way and are not reliably machine-parseable from
this feed's free-text `subject` field -- out of scope here, matching the
prior project's own documented choice.

Two traps found by the prior project and confirmed live against this same
endpoint before writing this module:

1. The feed's own `isin` field is the SYMBOL'S ORIGINAL ISIN, every time,
   not the ISIN active on the action's ex_date. Confirmed directly: every
   BAJFINANCE record from this API -- including the 2025-06-16 event -- is
   tagged INE296A01016 (BAJFINANCE's 2016 ISIN, retired that same year).
   Trusting it would misfile the 2025 action against a nine-year-dead ISIN.
   Fixed by resolving (symbol, ex_date) against our own prices_eod
   symbol/ISIN observations instead.

2. Combined subjects exist and are easy to half-parse: BAJFINANCE's
   2016-09-08 event is one string, "Bonus 1:1/Face Value Split
   (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share", containing
   BOTH a bonus and a split. A parser that returns on first match silently
   drops the second component. Fixed by extracting every pattern present,
   never just the first.

Do NOT derive splits from PREVCLOSE. Tested by the prior project: 991 of 994
same-ISIN PREVCLOSE-ratio candidates returned exactly 1.0, because NSE
carries the OLD ISIN's raw close forward as the NEW ISIN's PREVCLOSE on its
first trading day -- PREVCLOSE cannot see a cross-ISIN event at all, by
construction of how NSE populates that field.
"""
from __future__ import annotations

import datetime as dt
import re
import time
from pathlib import Path

import duckdb
import pandas as pd
import requests

API_URL = "https://www.nseindia.com/api/corporates-corporateActions"
HOME_URL = "https://www.nseindia.com/"
SOURCE_NAME = "NSE_CORPORATE_ACTIONS_API"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

BONUS_RE = re.compile(r"Bonus\s+(\d+)\s*:\s*(\d+)", re.IGNORECASE)
SPLIT_RE = re.compile(
    r"From\s+(?:Rs|Re)\.?\s*([\d.]+)\s*/?-?\s*Per\s+Share\s+To\s+(?:Rs|Re)\.?\s*([\d.]+)\s*/?-?\s*Per\s+Share",
    re.IGNORECASE,
)


def fetch_raw_actions(from_date: dt.date, to_date: dt.date) -> list[dict]:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    s.get(HOME_URL, timeout=30)
    time.sleep(0.8)
    resp = s.get(
        API_URL,
        params={
            "index": "equities",
            "from_date": from_date.strftime("%d-%m-%Y"),
            "to_date": to_date.strftime("%d-%m-%Y"),
        },
        headers={"Accept": "application/json", "Referer": "https://www.nseindia.com/"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def parse_subject_ratios(subject: str) -> list[tuple[str, float]]:
    """Extract every (component_type, ratio) pair present in a subject string.
    A combined subject yields more than one component; multiplying them gives
    the total adjustment ratio for that single ex_date event."""
    components = []
    for num, den in BONUS_RE.findall(subject):
        components.append(("bonus", (int(num) + int(den)) / int(den)))
    for old, new in SPLIT_RE.findall(subject):
        old_f, new_f = float(old), float(new)
        if new_f > 0:
            components.append(("split", old_f / new_f))
    return components


def build_symbol_isin_observations(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Every (symbol, trade_date, isin) triple ever observed in prices_eod --
    the ground truth used to resolve which ISIN a symbol actually traded
    under on any given date, since the corporate-actions feed's own isin
    field cannot be trusted for this."""
    df = con.execute(
        "SELECT DISTINCT symbol, trade_date, isin FROM prices_eod ORDER BY symbol, trade_date"
    ).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def resolve_isin_for_actions(actions_df: pd.DataFrame, symbol_obs: pd.DataFrame) -> pd.DataFrame:
    """Resolve each action's true ISIN via (symbol, ex_date) against our own
    price observations, forward-preferred (the new ISIN's first trading day
    typically coincides with ex_date for a split/bonus), falling back to the
    nearest observation in either direction when no exact/forward match
    exists (e.g. an ex_date that isn't itself a trading day)."""
    actions_df = actions_df.copy()
    symbol_obs = symbol_obs.copy()
    actions_df["ex_date"] = pd.to_datetime(actions_df["ex_date"]).astype("datetime64[ns]")
    symbol_obs["trade_date"] = pd.to_datetime(symbol_obs["trade_date"]).astype("datetime64[ns]")
    actions_df = actions_df.sort_values("ex_date").reset_index(drop=True)
    symbol_obs = symbol_obs.sort_values("trade_date").reset_index(drop=True)

    resolved_parts = []
    for direction in ["forward", "backward"]:
        merged = pd.merge_asof(
            actions_df, symbol_obs, left_on="ex_date", right_on="trade_date",
            by="symbol", direction=direction, suffixes=("", "_obs"),
        )
        resolved_parts.append(merged["isin"])

    forward_isin, backward_isin = resolved_parts
    resolved = forward_isin.combine_first(backward_isin)
    actions_df = actions_df.copy()
    actions_df["resolved_isin"] = resolved
    return actions_df


def to_corporate_actions_df(raw_records: list[dict], symbol_obs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in raw_records:
        subject = r.get("subject") or ""
        components = parse_subject_ratios(subject)
        if not components:
            continue  # not a bonus/split event (dividend, AGM, buyback, rights, capital reduction, ...)
        ex_date = pd.to_datetime(r["exDate"], format="%d-%b-%Y").date()
        for action_type, ratio in components:
            rows.append(
                {
                    "symbol": r["symbol"],
                    "ex_date": ex_date,
                    "action_type": action_type,
                    "ratio": ratio,
                    "subject_raw": subject.strip(),
                    "feed_isin": r.get("isin"),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=["isin", "symbol", "ex_date", "action_type", "ratio", "subject_raw",
                     "feed_isin", "known_date", "fetched_at", "source", "revision_seq"]
        )

    df = pd.DataFrame(rows)
    df["ex_date"] = pd.to_datetime(df["ex_date"])
    df = resolve_isin_for_actions(df, symbol_obs)
    df = df.dropna(subset=["resolved_isin"])
    df["isin"] = df["resolved_isin"]
    df["ex_date"] = df["ex_date"].dt.date
    df["known_date"] = df["ex_date"]  # caBroadcastDate is always null on this feed; ex_date is unambiguously public
    df["fetched_at"] = dt.datetime.now()
    df["source"] = SOURCE_NAME
    df["revision_seq"] = 1
    return df[["isin", "symbol", "ex_date", "action_type", "ratio", "subject_raw",
               "feed_isin", "known_date", "fetched_at", "source", "revision_seq"]]


def load_corporate_actions_to_duckdb(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    existing = con.execute("SELECT isin, ex_date, action_type, subject_raw FROM corporate_actions").fetchdf()
    if not existing.empty:
        key = lambda d: set(zip(d["isin"], d["ex_date"].astype(str), d["action_type"], d["subject_raw"]))
        existing_keys = key(existing)
        df = df[~df.apply(lambda r: (r["isin"], str(r["ex_date"]), r["action_type"], r["subject_raw"]) in existing_keys, axis=1)]
    if df.empty:
        return 0
    con.register("ca_new", df)
    con.execute("INSERT INTO corporate_actions SELECT * FROM ca_new")
    con.unregister("ca_new")
    return len(df)
