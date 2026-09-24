"""Phase A: full quarterly financial-results (P&L) backfill, 2016-01 to
present. Monthly chunks -- a single full-year request was found live to
silently return far less data than the sum of its months for 2025 (3,960
for the full year vs 3,759 from just Jan+Feb alone), so monthly chunking is
the safer, more auditable unit regardless of whether that's an NSE backend
quirk or a genuine reporting-seasonality effect for very recent months.
Resumable via fetch_log, same pattern as the price/index backfills.
"""
import datetime as dt
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.corporate_actions import build_symbol_isin_observations
from data_layer.fundamentals_nse import _session, to_filings_df, load_filings_to_duckdb

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TAG = "NSE_XBRL_FINANCIAL_RESULTS_QUARTERLY_BACKFILL"
START = dt.date(2016, 1, 1)
END = dt.date(2026, 9, 20)


def month_ranges(start, end):
    d = dt.date(start.year, start.month, 1)
    while d <= end:
        if d.month == 12:
            nxt = dt.date(d.year + 1, 1, 1)
        else:
            nxt = dt.date(d.year, d.month + 1, 1)
        last_day = min(nxt - dt.timedelta(days=1), end)
        yield d, last_day
        d = nxt


con = get_connection(ROOT / "data" / "warehouse.duckdb")
s = _session()
symbol_obs = build_symbol_isin_observations(con)  # loaded once, reused every month -- see fundamentals_nse.resolve_isin_for_filings

total_inserted = 0
total_fetched = 0
month_counts = []

for m_start, m_end in month_ranges(START, END):
    key = f"{SOURCE_TAG}:{m_start.isoformat()}"
    already = con.execute(
        "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [SOURCE_TAG, m_start]
    ).fetchone()
    if already and already[0] == "ok":
        month_counts.append((m_start, None, "skipped_already_logged"))
        continue

    resp = s.get(
        "https://www.nseindia.com/api/corporates-financial-results",
        params={
            "index": "equities", "period": "Quarterly",
            "from_date": m_start.strftime("%d-%m-%Y"), "to_date": m_end.strftime("%d-%m-%Y"),
        },
        headers={"Accept": "application/json",
                 "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"},
        timeout=30,
    )
    time.sleep(0.8)
    records = resp.json() if resp.status_code == 200 else []
    df = to_filings_df(records, symbol_obs=symbol_obs)
    n_inserted = load_filings_to_duckdb(con, df)
    total_fetched += len(records)
    total_inserted += n_inserted
    month_counts.append((m_start, len(records), "ok"))

    con.execute("DELETE FROM fetch_log WHERE source=? AND trade_date=?", [SOURCE_TAG, m_start])
    con.execute("INSERT INTO fetch_log VALUES (?, ?, 'ok', ?, ?)", [SOURCE_TAG, m_start, len(records), dt.datetime.now()])

    if m_start.month == 1:
        print(f"  ... {m_start.year} in progress ({len(records)} records for Jan)", flush=True)

print(f"\nDONE. Total records fetched: {total_fetched}, total new rows inserted: {total_inserted}")

counts_df = pd.DataFrame(month_counts, columns=["month", "n_records", "status"])
counts_df.to_csv(ROOT / "data" / "fundamentals_backfill_month_counts.csv", index=False)
print(counts_df.to_string(index=False))

con.close()
