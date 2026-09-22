"""Phase B step 1: Annual financial-results metadata backfill, 2016-present.
Same monthly-chunk approach as the quarterly backfill (Phase A), same
resumability via fetch_log, distinct source tag so it never collides with
the quarterly rows in fetch_log's (source, trade_date) key.
"""
import datetime as dt
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.fundamentals_nse import _session, to_filings_df, load_filings_to_duckdb

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TAG = "NSE_XBRL_FINANCIAL_RESULTS_ANNUAL_BACKFILL"
START = dt.date(2016, 1, 1)
END = dt.date(2026, 9, 20)


def month_ranges(start, end):
    d = dt.date(start.year, start.month, 1)
    while d <= end:
        nxt = dt.date(d.year + 1, 1, 1) if d.month == 12 else dt.date(d.year, d.month + 1, 1)
        last_day = min(nxt - dt.timedelta(days=1), end)
        yield d, last_day
        d = nxt


con = get_connection(ROOT / "data" / "warehouse.duckdb")
s = _session()

total_inserted = 0
total_fetched = 0
month_counts = []

for m_start, m_end in month_ranges(START, END):
    already = con.execute(
        "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [SOURCE_TAG, m_start]
    ).fetchone()
    if already and already[0] == "ok":
        month_counts.append((m_start, None, "skipped_already_logged"))
        continue

    resp = s.get(
        "https://www.nseindia.com/api/corporates-financial-results",
        params={"index": "equities", "period": "Annual",
                "from_date": m_start.strftime("%d-%m-%Y"), "to_date": m_end.strftime("%d-%m-%Y")},
        headers={"Accept": "application/json",
                 "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"},
        timeout=30,
    )
    time.sleep(0.8)
    records = resp.json() if resp.status_code == 200 else []
    df = to_filings_df(records)
    n_inserted = load_filings_to_duckdb(con, df)
    total_fetched += len(records)
    total_inserted += n_inserted
    month_counts.append((m_start, len(records), "ok"))

    con.execute("DELETE FROM fetch_log WHERE source=? AND trade_date=?", [SOURCE_TAG, m_start])
    con.execute("INSERT INTO fetch_log VALUES (?, ?, 'ok', ?, ?)", [SOURCE_TAG, m_start, len(records), dt.datetime.now()])

    if m_start.month == 1:
        print(f"  ... {m_start.year} in progress", flush=True)

print(f"\nDONE. Total Annual records fetched: {total_fetched}, new rows inserted: {total_inserted}")
counts_df = pd.DataFrame(month_counts, columns=["month", "n_records", "status"])
counts_df.to_csv(ROOT / "data" / "fundamentals_annual_backfill_month_counts.csv", index=False)
con.close()
