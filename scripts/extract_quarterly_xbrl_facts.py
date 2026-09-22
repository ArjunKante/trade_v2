"""Phase E prep, scoped down per instruction: 2018+ only (2016-2017 already
has 0% real XBRL per Phase A, confirmed a no-op cut here), entities with
price coverage only (a company with no clean forward-return window can't
contribute to any IC calculation), 0.33s throttle (still under NSE's 3
req/sec limit, matching the price backfill's own proven rate).

Logging per OPERATIONS.md: every line flushes immediately, plus a 45s
time-based heartbeat regardless of document count. Resumable via checking
fundamentals_xbrl_facts for existing seq_number (scoped to this source)
before each fetch -- confirmed directly against the DB that this correctly
preserves prior partial-run progress before restarting this script.
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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
SOURCE_NAME = "NSE_XBRL_QUARTERLY_FACTS"
HEARTBEAT_SECONDS = 45
SLEEP_SECONDS = 0.33
BACKOFF_SLEEP_SECONDS = 0.5

todo = pd.read_csv(ROOT / "data" / "quarterly_xbrl_to_fetch_v2.csv", parse_dates=["period_end", "known_date"])
todo["seq_number"] = todo["seq_number"].astype(str)

# Persistent Session, not bare requests.get() per call -- measured live: bare
# get() averages 0.484s/request (fresh TCP+TLS handshake every time) vs
# 0.075s/request with a reused Session, a 6.4x difference. Found and fixed
# alongside the missing seq_number index (both were silently inflating this
# run's real per-document cost well past the throttle-only estimate).
http = requests.Session()
http.headers.update({"User-Agent": USER_AGENT})

con = get_connection(ROOT / "data" / "warehouse.duckdb")
already_done = set(con.execute(
    "SELECT DISTINCT seq_number FROM fundamentals_xbrl_facts WHERE source = ?", [SOURCE_NAME]
).fetchdf()["seq_number"])
print(f"{len(todo)} total documents (2018+, price-covered entities only), "
      f"{len(already_done)} already extracted, "
      f"{len(todo) - todo['seq_number'].isin(already_done).sum()} remaining", flush=True)

n_ok, n_empty, n_err, n_429 = 0, 0, 0, 0
sleep_seconds = SLEEP_SECONDS
last_heartbeat = time.time()

for i, row in todo.iterrows():
    if row["seq_number"] in already_done:
        continue
    try:
        resp = http.get(row["xbrl_url"], timeout=20)
        time.sleep(sleep_seconds)
        if resp.status_code == 429:
            n_429 += 1
            if sleep_seconds < BACKOFF_SLEEP_SECONDS:
                sleep_seconds = BACKOFF_SLEEP_SECONDS
                print(f"  *** 429 at row {i} -- backing off to {BACKOFF_SLEEP_SECONDS}s ***", flush=True)
            n_err += 1
            continue
        if resp.status_code != 200 or not resp.text.strip():
            n_err += 1
            continue
        facts = parse_xbrl_facts(resp.text)
        if not facts:
            n_empty += 1
            continue
        fdf = facts_to_df(
            facts, isin=row["isin"], seq_number=row["seq_number"], period_end=row["period_end"].date(),
            consolidated=row["consolidated"], known_date=row["known_date"].date(), source=SOURCE_NAME,
        )
        load_facts_to_duckdb(con, fdf)
        n_ok += 1
    except requests.exceptions.ConnectionError as e:
        n_err += 1
        if sleep_seconds < BACKOFF_SLEEP_SECONDS:
            sleep_seconds = BACKOFF_SLEEP_SECONDS
            print(f"  *** connection error at row {i} ({e}) -- backing off to {BACKOFF_SLEEP_SECONDS}s ***", flush=True)
    except Exception:
        n_err += 1

    now = time.time()
    if now - last_heartbeat >= HEARTBEAT_SECONDS:
        print(f"  heartbeat: {n_ok} ok, {n_empty} empty, {n_err} errors ({n_429} were 429s), "
              f"sleep={sleep_seconds}s, at row {i}/{len(todo)}", flush=True)
        last_heartbeat = now

print(f"\nDONE. {n_ok} ok, {n_empty} empty, {n_err} errors ({n_429} were 429s), final sleep={sleep_seconds}s", flush=True)
con.close()
