"""Recovers annual filings whose picked seq_number's URL is dead by falling
back to a live sibling for the same (isin, period_end) -- BUGS.md: the
consolidated-preferred dedup picked a registration without ever checking it
resolves, the same class of defect as Bug #7's ISIN join (a selection made
on metadata that was never validated against reality).

Scope, deliberately bounded to the 175 already-identified real-URL annual
failures (experiments.csv, 2026-09-25 diagnostic) -- NOT a blanket
revalidation of all ~13,600 annual documents:
  - 318 placeholder-URL failures ("/xbrl/-") are untouched: no document
    ever existed for them, there is nothing to fall back to.
  - For the rest, try a live SAME-consolidated-type sibling first (fixes
    the "_WEB_2 duplicate registration" pattern -- confirmed live for
    TEXINFRA/JMFINANCIL: the "_WEB_2" seq_number 404s, the sibling without
    the suffix returns 200). No basis change, no flag needed.
  - If no same-type sibling resolves, try a live DIFFERENT-type sibling
    (the IFCI pattern: Consolidated dead, Non-Consolidated live). Using
    this is a basis switch and is FLAGGED explicitly in
    data/annual_basis_switch_log.csv -- never silent, per instruction.
  - If nothing resolves, the row is left as a permanent failure (genuine
    NSE-side gap, e.g. confirmed for INDUSINDBK/KTKBANK/CANBK/CENTRALBK,
    all BANKING_ taxonomy, both variants dead).

Live HTTP checks only for candidates not already extracted (an already-
extracted sibling needs no re-fetch, just use its existing facts).
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.xbrl_parser import parse_xbrl_facts, facts_to_df, load_facts_to_duckdb

ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "NSE_XBRL_ANNUAL_BALANCE_SHEET"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
SLEEP_SECONDS = 0.33
LOG_PATH = ROOT / "data" / "annual_basis_switch_log.csv"

con = get_connection(ROOT / "data" / "warehouse.duckdb")
http = requests.Session()
http.headers.update({"User-Agent": USER_AGENT})

todo = pd.read_csv(ROOT / "data" / "annual_xbrl_to_fetch.csv", parse_dates=["period_end", "known_date"])
todo["seq_number"] = todo["seq_number"].astype(str)
extracted = set(con.execute(f"SELECT DISTINCT seq_number FROM fundamentals_xbrl_facts WHERE source = '{SOURCE_NAME}'").fetchdf()["seq_number"])
failed = todo[~todo["seq_number"].isin(extracted)].copy()

placeholder_mask = failed["xbrl_url"].str.endswith("/-")
placeholder = failed[placeholder_mask]
real_url_failed = failed[~placeholder_mask]
print(f"{len(failed)} total failed rows: {len(placeholder)} placeholder (untouched), "
      f"{len(real_url_failed)} real-URL (candidates for sibling recovery)")

# All filing rows for the affected isins, to search for siblings.
affected_isins = real_url_failed["isin"].unique().tolist()
all_filings = con.execute(
    f"SELECT isin, symbol, period_end, consolidated, seq_number, xbrl_url, known_date "
    f"FROM fundamentals_filings WHERE isin IN ({','.join('?' for _ in affected_isins)})",
    affected_isins,
).fetchdf()
all_filings["period_end"] = pd.to_datetime(all_filings["period_end"])
all_filings["known_date"] = pd.to_datetime(all_filings["known_date"])
all_filings["seq_number"] = all_filings["seq_number"].astype(str)

checked_cache: dict[str, bool] = {}


def url_is_live(url: str) -> bool:
    if url in checked_cache:
        return checked_cache[url]
    try:
        resp = http.get(url, timeout=20)
        time.sleep(SLEEP_SECONDS)
        ok = resp.status_code == 200 and bool(resp.text.strip())
        checked_cache[url] = ok
        return ok
    except requests.exceptions.RequestException:
        checked_cache[url] = False
        return False


n_same_type_recovered = 0
n_basis_switched = 0
n_still_dead = 0
basis_switch_rows = []

for i, row in real_url_failed.reset_index(drop=True).iterrows():
    siblings = all_filings[
        (all_filings["isin"] == row["isin"]) & (all_filings["period_end"] == row["period_end"])
        & (all_filings["seq_number"] != row["seq_number"])
    ]
    same_type = siblings[siblings["consolidated"] == row["consolidated"]].sort_values("known_date", ascending=False)
    other_type = siblings[siblings["consolidated"] != row["consolidated"]].sort_values("known_date", ascending=False)

    resolved = None
    is_basis_switch = False
    for _, cand in same_type.iterrows():
        if cand["seq_number"] in extracted or url_is_live(cand["xbrl_url"]):
            resolved = cand
            break
    if resolved is None:
        for _, cand in other_type.iterrows():
            if cand["seq_number"] in extracted or url_is_live(cand["xbrl_url"]):
                resolved = cand
                is_basis_switch = True
                break

    if resolved is None:
        n_still_dead += 1
        continue

    if resolved["seq_number"] not in extracted:
        resp = http.get(resolved["xbrl_url"], timeout=20)
        time.sleep(SLEEP_SECONDS)
        facts = parse_xbrl_facts(resp.text)
        if facts:
            fdf = facts_to_df(
                facts, isin=row["isin"], seq_number=resolved["seq_number"], period_end=row["period_end"].date(),
                consolidated=resolved["consolidated"], known_date=resolved["known_date"].date(), source=SOURCE_NAME,
            )
            load_facts_to_duckdb(con, fdf)
            extracted.add(resolved["seq_number"])

    if is_basis_switch:
        n_basis_switched += 1
        basis_switch_rows.append({
            "isin": row["isin"], "symbol": row["symbol"], "period_end": row["period_end"].date(),
            "failed_seq_number": row["seq_number"], "failed_consolidated": row["consolidated"],
            "used_seq_number": resolved["seq_number"], "used_consolidated": resolved["consolidated"],
            "reason": f"{row['consolidated']} variant confirmed dead; {resolved['consolidated']} variant live",
        })
    else:
        n_same_type_recovered += 1

    if (i + 1) % 20 == 0:
        print(f"  ... {i+1}/{len(real_url_failed)} processed", flush=True)

print(f"\nRecovered via live same-type sibling: {n_same_type_recovered}")
print(f"Recovered via basis switch (flagged): {n_basis_switched}")
print(f"Still dead (no live sibling of any type): {n_still_dead}")
print(f"Placeholder (untouched, no document ever existed): {len(placeholder)}")

if basis_switch_rows:
    pd.DataFrame(basis_switch_rows).to_csv(LOG_PATH, index=False)
    print(f"\nBasis-switch log written to {LOG_PATH} ({len(basis_switch_rows)} rows)")

con.close()
