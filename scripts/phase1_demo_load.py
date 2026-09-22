"""One-off driver for the Phase 1 gate: load a few real trading days of
bhavcopy and one real batch of XBRL financial-results filings, then print
sample rows. Not the production ingestion loop (that will iterate a date
range with the throttle honored day-by-day) — this just proves the schema
and known_date handling against real data.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.prices_nse import load_bhavcopy_to_duckdb
from data_layer.fundamentals_nse import _session, fetch_financial_results, to_filings_df, load_filings_to_duckdb
from data_layer.xbrl_parser import parse_xbrl_facts, facts_to_df, load_facts_to_duckdb
import requests

ROOT = Path(__file__).resolve().parents[1]
con = get_connection(ROOT / "data" / "warehouse.duckdb")

for d in [dt.date(2026, 9, 16), dt.date(2026, 9, 17), dt.date(2026, 9, 18)]:
    n = load_bhavcopy_to_duckdb(con, d, ROOT / "data" / "raw" / "prices", series_include=["EQ", "BE", "BZ"])
    print(f"prices {d}: inserted {n} rows")

print("\n--- prices_eod sample (5 rows) ---")
print(con.execute("SELECT * FROM prices_eod WHERE symbol = 'RELIANCE' ORDER BY trade_date").fetchdf().to_string())

s = _session()
records = fetch_financial_results(s, index="equities", period="Quarterly")
filings_df = to_filings_df(records)
n = load_filings_to_duckdb(con, filings_df)
print(f"\nfundamentals_filings: inserted {n} rows (of {len(filings_df)} fetched)")

print("\n--- fundamentals_filings sample (5 rows) ---")
print(con.execute("SELECT * FROM fundamentals_filings ORDER BY broadcast_ts DESC LIMIT 5").fetchdf().to_string())

# Pull XBRL facts for one filing to prove the numbers-from-XBRL path end to end.
one = con.execute(
    "SELECT isin, seq_number, period_end, consolidated, known_date, xbrl_url FROM fundamentals_filings "
    "WHERE xbrl_url IS NOT NULL ORDER BY broadcast_ts DESC LIMIT 1"
).fetchdf().iloc[0]
xml_text = requests.get(one["xbrl_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
facts = parse_xbrl_facts(xml_text)
facts_df = facts_to_df(
    facts, isin=one["isin"], seq_number=one["seq_number"], period_end=one["period_end"],
    consolidated=one["consolidated"], known_date=one["known_date"], source="NSE_XBRL_FINANCIAL_RESULTS",
)
n = load_facts_to_duckdb(con, facts_df)
print(f"\nfundamentals_xbrl_facts: inserted {n} rows for {one['isin']} seq {one['seq_number']}")

print("\n--- fundamentals_xbrl_facts sample (5 rows) ---")
print(con.execute(
    "SELECT * FROM fundamentals_xbrl_facts WHERE tag LIKE '%EarningsPerShare%' OR tag = 'RevenueFromOperations' LIMIT 5"
).fetchdf().to_string())

con.close()
