"""One-time retroactive correction for the fundamentals-feed stale-ISIN bug
(see data_layer.fundamentals_nse.resolve_isin_for_filings's docstring for
the full mechanism and the BHEL/NATIONALUM/GRANULES/AUROPHARMA evidence).

WHY AN UPDATE, NOT A NEW APPEND-ONLY ROW: db.py's own docstring states
"corrections are new rows with a higher revision_seq, never UPDATE/DELETE"
-- that protects a REAL-WORLD restatement's point-in-time history (a
company genuinely refiling a number). This is different: it is OUR OWN
ingestion pipeline's join key that was wrong, not a number the company
disclosed. The underlying XBRL facts were already fetched and parsed
correctly by extract_quarterly_xbrl_facts.py/extract_annual_xbrl_facts.py
-- they are just keyed by the isin fundamentals_filings told them to use.
A full re-fetch (2016-2026, tens of thousands of requests, hours per
BUGS.md's own throughput lessons) would reach the identical corrected
values; this reaches them from data already sitting in the warehouse.

Only the two LEGACY sources (NSE_XBRL_QUARTERLY_FACTS,
NSE_XBRL_ANNUAL_BALANCE_SHEET) are touched in fundamentals_xbrl_facts --
NSE_INTEGRATED_FILING_FINANCIALS is left alone (out of scope, and per
Bug #5/BUGS.md its seq_number range can overlap the legacy sources', so
touching it without that same care would risk exactly the collision Bug #5
already fixed for the read path).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.corporate_actions import build_symbol_isin_observations
from data_layer.fundamentals_nse import resolve_isin_for_filings

ROOT = Path(__file__).resolve().parents[1]
LEGACY_FACT_SOURCES = ("NSE_XBRL_QUARTERLY_FACTS", "NSE_XBRL_ANNUAL_BALANCE_SHEET")

con = get_connection(ROOT / "data" / "warehouse.duckdb")

symbol_obs = build_symbol_isin_observations(con)
price_isins = set(con.execute("SELECT DISTINCT isin FROM prices_eod").fetchdf()["isin"])

filings = con.execute("SELECT isin, symbol, known_date, seq_number FROM fundamentals_filings").fetchdf()
filings["known_date"] = pd.to_datetime(filings["known_date"])

orphan_mask = ~filings["isin"].isin(price_isins)
orphans = filings[orphan_mask].copy().reset_index(drop=True)
n_orphan_isins = orphans["isin"].nunique()
print(f"{len(orphans)} fundamentals_filings rows ({n_orphan_isins} distinct isins) use an isin never observed in prices_eod")

# IMPORTANT: pass the FULL frame (seq_number and a copy of the original isin
# riding along as passenger columns) into resolve_isin_for_filings in ONE
# call, and read seq_number/old_isin back from its RETURNED frame -- the
# function internally re-sorts by known_date, so reattaching seq_number
# from the pre-sort `orphans` by positional .values afterward silently
# misaligns rows (caught by a dry run before this touched the database:
# it produced nonsense like CLCIND's filings "resolving" to BHEL's isin).
orphans["old_isin"] = orphans["isin"]
resolved = resolve_isin_for_filings(orphans, symbol_obs)

recovered = resolved.dropna(subset=["isin"])
unresolvable = resolved[resolved["isin"].isna()]

n_recovered_isins = recovered["old_isin"].nunique()
n_unresolvable_isins = unresolvable["old_isin"].nunique()
print(f"RECOVERED: {n_recovered_isins} of {n_orphan_isins} orphaned isins resolve to a real trading isin "
      f"({len(recovered)} filing rows)")
print(f"UNRESOLVABLE: {n_unresolvable_isins} of {n_orphan_isins} orphaned isins -- symbol never observed in "
      f"prices_eod at all ({len(unresolvable)} filing rows)")

unresolvable_symbols = orphans.set_index("isin").loc[unresolvable["old_isin"].unique(), "symbol"].unique()
print(f"Unresolvable symbols (first 20 of {len(unresolvable_symbols)}): {sorted(unresolvable_symbols)[:20]}")

# --- Apply: fundamentals_filings (unique per seq_number, single source) ---
mapping = recovered[["seq_number", "isin"]].drop_duplicates(subset=["seq_number"])
con.register("isin_fix", mapping)
before = con.execute(
    "SELECT COUNT(*) FROM fundamentals_filings f JOIN isin_fix ON f.seq_number = isin_fix.seq_number "
    "WHERE f.isin != isin_fix.isin"
).fetchone()[0]
con.execute(
    "UPDATE fundamentals_filings SET isin = isin_fix.isin FROM isin_fix "
    "WHERE fundamentals_filings.seq_number = isin_fix.seq_number AND fundamentals_filings.isin != isin_fix.isin"
)
print(f"\nfundamentals_filings: corrected {before} rows")

# --- Apply: fundamentals_xbrl_facts, legacy sources only, matched on (source-scoped) seq_number + old isin ---
fact_map = recovered[["seq_number", "old_isin", "isin"]].drop_duplicates(subset=["seq_number"]).rename(
    columns={"isin": "new_isin"})
con.register("fact_isin_fix", fact_map)
sources_clause = "(" + ",".join(f"'{s}'" for s in LEGACY_FACT_SOURCES) + ")"
before_facts = con.execute(
    f"SELECT COUNT(*) FROM fundamentals_xbrl_facts x JOIN fact_isin_fix ON x.seq_number = fact_isin_fix.seq_number "
    f"WHERE x.isin = fact_isin_fix.old_isin AND x.source IN {sources_clause}"
).fetchone()[0]
con.execute(
    f"UPDATE fundamentals_xbrl_facts SET isin = fact_isin_fix.new_isin FROM fact_isin_fix "
    f"WHERE fundamentals_xbrl_facts.seq_number = fact_isin_fix.seq_number "
    f"AND fundamentals_xbrl_facts.isin = fact_isin_fix.old_isin "
    f"AND fundamentals_xbrl_facts.source IN {sources_clause}"
)
print(f"fundamentals_xbrl_facts: corrected {before_facts} rows (legacy sources only)")

con.unregister("isin_fix")
con.unregister("fact_isin_fix")

# --- Verify: how many orphaned isins remain after the fix ---
remaining_orphans = con.execute(
    "SELECT COUNT(DISTINCT isin) FROM fundamentals_filings WHERE isin NOT IN (SELECT DISTINCT isin FROM prices_eod)"
).fetchone()[0]
print(f"\nVerification: {remaining_orphans} distinct isins in fundamentals_filings still never seen in prices_eod "
      f"(expected: {n_unresolvable_isins}, the genuinely-unresolvable ones)")

con.close()
