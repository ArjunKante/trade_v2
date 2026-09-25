"""Adds the 166 Bug #7-affected companies' documents to data/quarterly_xbrl_
to_fetch_v2.csv and data/annual_xbrl_to_fetch.csv -- BUGS.md Bug #7's second
face. The original CSVs (generator script never committed; only its output
survived) were built by joining the fundamentals feed's raw isin directly
against prices_eod for a "price coverage only" scope cut -- the same
unreliable-isin join corporate_actions.py had already shown cannot be
trusted, applied here to decide what to even DOWNLOAD, not just how to
store it.

DELIBERATELY NARROW, not a full rebuild: a first attempt reconstructed the
entire fetch-scope universe from scratch and was abandoned after it
produced ~27,000 "brand-new" documents spread across ~1,980 distinct
isins -- checked against TCS, a company with NO isin issue at all, which
still gained 2 "new" periods under the reconstruction. The original
scoping script's exact tie-breaking/boundary logic cannot be perfectly
reproduced from its output alone, and wholesale-replacing the CSVs risked
silently changing behavior for ~2,300 unaffected companies with no way to
verify the result against the lost original. The disciplined alternative:
touch ONLY the 166 confirmed-affected isins, whose rows are ENTIRELY
absent from the existing CSVs (verified), so there is no existing behavior
to diverge from -- this is a pure addition, not a rebuild. Read directly
from fundamentals_filings, which already carries the CORRECTED isin for
these companies (Bug #7's main fix already applied it in place) -- no
re-resolution needed here, only correct scoping and the same consolidated-
preferred dedup this project already uses elsewhere.

Read-only against the warehouse; only appends to the two CSV files
(originals preserved for every other company, byte-for-byte). Does not
fetch anything.
"""
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from factors.fundamentals_factors import _pick_pit_series

ROOT = Path(__file__).resolve().parents[1]
con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

# The 166 recovered isins: entity_ids whose current (corrected) isin was, in
# the pre-fix backup, orphaned from prices_eod despite the symbol trading.
# Re-derive directly rather than hard-coding, so this script stays correct
# if re-run after any future correction.
backup_path = ROOT / "data" / "warehouse.duckdb.bak_before_isin_fix_20260924"
con_bak = get_read_connection(backup_path)
price_isins_bak = set(con_bak.execute("SELECT DISTINCT isin FROM prices_eod").fetchdf()["isin"])
symbols_in_prices_bak = set(con_bak.execute("SELECT DISTINCT symbol FROM prices_eod").fetchdf()["symbol"])
filings_bak = con_bak.execute("SELECT isin, symbol FROM fundamentals_filings").fetchdf()
con_bak.close()
recovered_old_isins = set(
    filings_bak[(~filings_bak["isin"].isin(price_isins_bak)) & (filings_bak["symbol"].isin(symbols_in_prices_bak))]["isin"]
)
recovered_symbols = set(filings_bak[filings_bak["isin"].isin(recovered_old_isins)]["symbol"])
print(f"{len(recovered_old_isins)} old (stale) isins -> resolving to their current, corrected isins...")

# Their CURRENT (corrected) isins, straight from the already-fixed table
current_isins = set(con.execute(
    f"SELECT DISTINCT isin FROM fundamentals_filings WHERE symbol IN ({','.join('?' for _ in recovered_symbols)})",
    list(recovered_symbols),
).fetchdf()["isin"])
print(f"{len(current_isins)} distinct current isins for these {len(recovered_symbols)} symbols")

filings = con.execute(
    f"SELECT isin, symbol, period_end, consolidated, seq_number, xbrl_url, known_date, reporting_quarter "
    f"FROM fundamentals_filings WHERE isin IN ({','.join('?' for _ in current_isins)})",
    list(current_isins),
).fetchdf()
filings["period_end"] = pd.to_datetime(filings["period_end"])
filings["known_date"] = pd.to_datetime(filings["known_date"])
already_extracted = set(con.execute("SELECT DISTINCT seq_number FROM fundamentals_xbrl_facts").fetchdf()["seq_number"])
con.close()
print(f"{len(filings)} filing rows for the recovered companies")

# Split by type before dedup -- see module docstring / BUGS.md for why
# (a March-FY company's Q4 and Annual share a period_end).
quarterly_raw = filings[(filings["period_end"] >= "2018-01-01") & (filings["reporting_quarter"] != "Annual")]
annual_raw = filings[filings["reporting_quarter"] == "Annual"]
quarterly_new = _pick_pit_series(quarterly_raw)
annual_new = _pick_pit_series(annual_raw)

q_cols = ["isin", "period_end", "consolidated", "seq_number", "xbrl_url", "known_date"]
a_cols = ["isin", "symbol", "period_end", "consolidated", "seq_number", "xbrl_url", "known_date"]

q_path = ROOT / "data" / "quarterly_xbrl_to_fetch_v2.csv"
a_path = ROOT / "data" / "annual_xbrl_to_fetch.csv"
old_q = pd.read_csv(q_path, dtype={"seq_number": str})
old_a = pd.read_csv(a_path, dtype={"seq_number": str})

# Sanity: confirm these isins really are entirely absent from the existing
# CSVs (a pure addition, not an overlap/overwrite) before appending.
overlap_q = set(quarterly_new["isin"]) & set(old_q["isin"])
overlap_a = set(annual_new["isin"]) & set(old_a["isin"])
assert not overlap_q, f"expected zero isin overlap in quarterly scope, found {overlap_q}"
assert not overlap_a, f"expected zero isin overlap in annual scope, found {overlap_a}"

# Write date columns as plain "YYYY-MM-DD" strings, matching the existing
# CSVs' own format EXACTLY -- caught live: writing the new rows' datetime64
# columns straight to CSV produced "2020-09-30 00:00:00" (a time component)
# against the existing rows' "2020-09-30" (none). That mixed format made
# pandas' parse_dates silently fall back to leaving the WHOLE column as
# strings on read, which then failed deep in facts_to_df with a bare
# AttributeError ('str' object has no attribute 'date') -- swallowed with
# no message by extract_quarterly_xbrl_facts.py's blanket except Exception.
# Confirmed live: this produced 171 consecutive failures, 0 successes,
# before being caught and stopped.
quarterly_new = quarterly_new.copy()
annual_new = annual_new.copy()
quarterly_new["period_end"] = quarterly_new["period_end"].dt.strftime("%Y-%m-%d")
quarterly_new["known_date"] = quarterly_new["known_date"].dt.strftime("%Y-%m-%d")
annual_new["period_end"] = annual_new["period_end"].dt.strftime("%Y-%m-%d")
annual_new["known_date"] = annual_new["known_date"].dt.strftime("%Y-%m-%d")

combined_q = pd.concat([old_q, quarterly_new[q_cols].assign(seq_number=quarterly_new["seq_number"].astype(str))], ignore_index=True)
combined_a = pd.concat([old_a, annual_new[a_cols].assign(seq_number=annual_new["seq_number"].astype(str), has_xbrl=annual_new["xbrl_url"].notna())], ignore_index=True)

combined_q.to_csv(q_path, index=False)
combined_a.to_csv(a_path, index=False)

# Verify the fix: re-read both CSVs the same way the extraction scripts do
# and confirm period_end/known_date parse as real dates, not strings.
verify_q = pd.read_csv(q_path, parse_dates=["period_end", "known_date"])
verify_a = pd.read_csv(a_path, parse_dates=["period_end", "known_date"])
assert str(verify_q["period_end"].dtype).startswith("datetime64"), f"quarterly period_end still not parsed as dates: {verify_q['period_end'].dtype}"
assert str(verify_a["period_end"].dtype).startswith("datetime64"), f"annual period_end still not parsed as dates: {verify_a['period_end'].dtype}"
print("Verified: both CSVs parse as real dates on read (dtype check passed).")

print(f"\nQUARTERLY: {len(old_q)} existing + {len(quarterly_new)} added = {len(combined_q)}")
print(f"ANNUAL: {len(old_a)} existing + {len(annual_new)} added = {len(combined_a)}")

new_remaining = (~pd.concat([quarterly_new, annual_new])["seq_number"].astype(str).isin(already_extracted)).sum()
print(f"\nOf the {len(quarterly_new) + len(annual_new)} newly-added documents, "
      f"{new_remaining} are not yet extracted (this is the refetch workload).")
