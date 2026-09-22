"""Phase B step 2: fetch and extract XBRL facts for every picked (consolidated-
preferred, deduped) Annual filing. Long-running (12,308 documents) --
resumable via checking fundamentals_xbrl_facts for existing seq_number
before each fetch, same pattern as every other backfill in this project.
"""
import datetime as dt
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
SOURCE_NAME = "NSE_XBRL_ANNUAL_BALANCE_SHEET"

todo = pd.read_csv(ROOT / "data" / "annual_xbrl_to_fetch.csv", parse_dates=["period_end", "known_date"])
todo["seq_number"] = todo["seq_number"].astype(str)

con = get_connection(ROOT / "data" / "warehouse.duckdb")
already_done = set(con.execute("SELECT DISTINCT seq_number FROM fundamentals_xbrl_facts").fetchdf()["seq_number"])
print(f"{len(todo)} total documents, {len(already_done)} already extracted, "
      f"{len(todo) - todo['seq_number'].isin(already_done).sum()} remaining")

n_ok, n_empty, n_err = 0, 0, 0
for i, row in todo.iterrows():
    if row["seq_number"] in already_done:
        continue
    try:
        resp = requests.get(row["xbrl_url"], headers={"User-Agent": USER_AGENT}, timeout=20)
        time.sleep(0.6)
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
    except Exception as e:
        n_err += 1

    if (n_ok + n_empty + n_err) % 500 == 0:
        print(f"  progress: {n_ok} ok, {n_empty} empty, {n_err} errors, at row {i}", flush=True)

print(f"\nDONE. {n_ok} ok, {n_empty} empty, {n_err} errors")
con.close()
