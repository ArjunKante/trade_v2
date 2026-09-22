"""Backfill the Integrated Filing-Financials format (SEBI's in-capmkt
taxonomy, replacing quarterly/annual "Financial Results" from April 2025).

Two steps: (1) fetch and cache the full list-metadata (paginated, one shot,
small and cheap relative to the documents themselves); (2) fetch each
document's XBRL body, parse it, extract its own ISIN, and load its facts
into the same `fundamentals_xbrl_facts` table the old sources use, under a
new source label (`NSE_INTEGRATED_FILING_FINANCIALS`) -- point-in-time
selection (`fundamentals_factors._pick_pit_series`, `load_quarterly_tag`,
`load_annual_tag`) is source-agnostic and needs no changes to read this data
once it is loaded correctly.

Scoped to entities with price coverage (symbol pre-filter only -- identity
always comes from the document's own parsed ISIN, never the symbol; see
integrated_filing_nse.py's docstring). Resumable: skips seq_numbers already
loaded under this source. Logging per OPERATIONS.md: every print flushes
immediately, plus a 45s time-based heartbeat regardless of document count.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.xbrl_parser import parse_xbrl_facts, facts_to_df, load_facts_to_duckdb, extract_isin
from data_layer.integrated_filing_nse import (
    _session, fetch_all_integrated_filing_metadata, to_metadata_df,
    scope_to_price_covered_symbols, SOURCE_NAME,
)

ROOT = Path(__file__).resolve().parents[1]
HEARTBEAT_SECONDS = 45
SLEEP_SECONDS = 0.33
BACKOFF_SLEEP_SECONDS = 0.5

print("Fetching Integrated Filing-Financials metadata (paginated)...", flush=True)
http = _session()
records = fetch_all_integrated_filing_metadata(http, size=1000, sleep_seconds=SLEEP_SECONDS)
print(f"{len(records)} metadata records fetched.", flush=True)

meta = to_metadata_df(records)
print(f"{len(meta)} usable after dropping rows with no symbol/period_end/known_date/xbrl_url.", flush=True)

con = get_connection(ROOT / "data" / "warehouse.duckdb")
meta = scope_to_price_covered_symbols(con, meta)
print(f"{len(meta)} remain after scoping to entities with price coverage "
      f"({meta['symbol'].nunique()} distinct symbols).", flush=True)

meta["seq_number"] = meta["seq_number"].astype(str)
already_done = set(con.execute(
    "SELECT DISTINCT seq_number FROM fundamentals_xbrl_facts WHERE source = ?", [SOURCE_NAME]
).fetchdf()["seq_number"])
n_remaining = (~meta["seq_number"].isin(already_done)).sum()
print(f"{len(already_done)} already extracted, {n_remaining} remaining.", flush=True)

n_ok, n_empty, n_no_isin, n_err, n_429 = 0, 0, 0, 0, 0
sleep_seconds = SLEEP_SECONDS
last_heartbeat = time.time()
consecutive_failures = 0
consecutive_successes = 0
# Safety net beyond _session()'s own retry adapter: found live that a
# reused Session can still wedge after enough requests. Tuned down from an
# initial 10-failure threshold with a 20s per-request timeout after
# measuring the actual cost live: each failed attempt against a wedged pool
# took ~45s (the adapter's own internal retries compounding the timeout),
# so 10 failures before rebuilding cost ~7.5 minutes of dead time PER
# EPISODE, recurring roughly every 1,200 requests -- on this run's ~26,700
# documents that projected to ~2.75 hours of pure dead time, blowing the
# estimated completion window. Shorter timeout + fewer failures-before-
# rebuild + adapter retries cut to 1 (see fundamentals_nse._session)
# together cut the per-episode cost from ~450s to an estimated ~60s.
REQUEST_TIMEOUT_SECONDS = 10
CONSECUTIVE_FAILURE_SESSION_RESET = 3
# Throttle backoff (0.33s -> 0.5s) never had a way back down, so a single
# early error would permanently cost ~1.5 extra hours over a ~26,700-row
# run for no ongoing reason. Reset to normal once the connection has
# clearly recovered (sustained successes), not on a fixed timer.
THROTTLE_RESET_AFTER_SUCCESSES = 200

for i, row in meta.reset_index(drop=True).iterrows():
    if row["seq_number"] in already_done:
        continue
    try:
        resp = http.get(row["xbrl_url"], timeout=REQUEST_TIMEOUT_SECONDS)
        time.sleep(sleep_seconds)
        if resp.status_code == 429:
            n_429 += 1
            consecutive_failures += 1
            consecutive_successes = 0
            if sleep_seconds < BACKOFF_SLEEP_SECONDS:
                sleep_seconds = BACKOFF_SLEEP_SECONDS
                print(f"  *** 429 at row {i} -- backing off to {BACKOFF_SLEEP_SECONDS}s ***", flush=True)
            n_err += 1
            continue
        if resp.status_code != 200 or not resp.text.strip():
            n_err += 1
            consecutive_failures += 1
            consecutive_successes = 0
            continue
        facts = parse_xbrl_facts(resp.text)
        if not facts:
            n_empty += 1
            consecutive_failures = 0
            continue
        isin = extract_isin(facts)
        if not isin:
            n_no_isin += 1
            consecutive_failures = 0
            continue
        fdf = facts_to_df(
            facts, isin=isin, seq_number=row["seq_number"], period_end=row["period_end"],
            consolidated=row["consolidated"], known_date=row["known_date"], source=SOURCE_NAME,
        )
        load_facts_to_duckdb(con, fdf)
        n_ok += 1
        consecutive_failures = 0
        consecutive_successes += 1
        if sleep_seconds > SLEEP_SECONDS and consecutive_successes >= THROTTLE_RESET_AFTER_SUCCESSES:
            print(f"  {consecutive_successes} consecutive successes -- resetting throttle to {SLEEP_SECONDS}s at row {i}", flush=True)
            sleep_seconds = SLEEP_SECONDS
    except requests.exceptions.RequestException as e:
        n_err += 1
        consecutive_failures += 1
        consecutive_successes = 0
        if sleep_seconds < BACKOFF_SLEEP_SECONDS:
            sleep_seconds = BACKOFF_SLEEP_SECONDS
            print(f"  *** request error at row {i} ({type(e).__name__}: {e}) -- backing off to {BACKOFF_SLEEP_SECONDS}s ***", flush=True)
        if consecutive_failures >= CONSECUTIVE_FAILURE_SESSION_RESET:
            print(f"  *** {consecutive_failures} consecutive failures -- rebuilding session at row {i} ***", flush=True)
            http = _session()
            consecutive_failures = 0
    except Exception as e:
        n_err += 1
        print(f"  *** unexpected error at row {i} ({e}) ***", flush=True)

    now = time.time()
    if now - last_heartbeat >= HEARTBEAT_SECONDS:
        print(f"  heartbeat: {n_ok} ok, {n_empty} empty, {n_no_isin} no-isin, {n_err} errors "
              f"({n_429} were 429s), sleep={sleep_seconds}s, at row {i}/{len(meta)}", flush=True)
        last_heartbeat = now

print(f"\nDONE. {n_ok} ok, {n_empty} empty, {n_no_isin} no-isin, {n_err} errors "
      f"({n_429} were 429s), final sleep={sleep_seconds}s", flush=True)

print("\nCoverage by quarter (period_end) for this source:", flush=True)
cov = con.execute(f"""
    SELECT period_end, COUNT(DISTINCT seq_number) AS n_docs, COUNT(DISTINCT isin) AS n_entities
    FROM fundamentals_xbrl_facts WHERE source = '{SOURCE_NAME}'
    GROUP BY period_end ORDER BY period_end
""").fetchdf()
print(cov.to_string(index=False), flush=True)

con.close()
