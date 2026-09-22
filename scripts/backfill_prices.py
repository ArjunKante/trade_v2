"""Full resumable price backfill, 2016-01-01 through today. Safe to kill and
re-run: fetch_log means every already-resolved trading day is skipped without
a network call. Respects the 3 req/sec convention via the fetcher's built-in
sleep between requests.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.prices_nse import backfill_range

ROOT = Path(__file__).resolve().parents[1]
START = dt.date(2016, 1, 1)
END = dt.date.today()

con = get_connection(ROOT / "data" / "warehouse.duckdb")
print(f"Backfilling {START} to {END} ...", flush=True)
stats = backfill_range(
    con, START, END, ROOT / "data" / "raw" / "prices", series_include=["EQ", "BE", "BZ"], progress_every=100
)
print("DONE:", stats, flush=True)
con.close()
