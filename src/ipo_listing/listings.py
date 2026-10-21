"""Loads the pre-identified, bhavcopy-cross-validated master list of NSE
mainboard IPO listings (`PREREGISTRATION_IPO.md` Section 2) from
`data/ipo_listing/ipo_master_listings.csv` -- a static, committed input,
not re-derived here. That CSV's `final_symbol_at_listing` column is
already corrected for the two symbol-rename cases (Infibeam/Karda) found
during Phase 1 identification.

Deliberately NOT using that CSV's own `isin_claimed` / `found_isin`
columns as this study's authoritative ISIN: `isin_claimed` is null for
all 451 rows sourced from the 2020-2026 GitHub cohort (that source has
no ISIN column at all, only an NSE symbol), and `found_isin` is stale
for the same 15 rows `PREREGISTRATION_IPO.md` Section 2 found needed
listing-day-era symbol resolution -- it holds whatever ISIN the FIRST
(pre-fix) cross-validation pass matched, which for those 15 is the
company's CURRENT isin, not its listing-day one. Both problems disappear
by deriving the listing-day ISIN FRESH, directly from this project's own
`prices_eod`, via `(symbol_at_listing, listing_date)` -- exactly the same
lookup that already confirmed 552/552 of these listings resolve cleanly
(Section 2), so it is guaranteed to find a match for every row that
already passed that check.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

MASTER_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "ipo_listing" / "ipo_master_listings.csv"


def load_master_listings(csv_path: Path | str = MASTER_CSV_PATH) -> pd.DataFrame:
    """[listing_id, company_name, listing_date, symbol_at_listing] -- one
    row per identified IPO, `listing_id` a stable 0-based row index into
    the committed CSV (this study's own natural key, since no entity_id/
    isin_lineage system in this project was built to cover a company
    before its own IPO). Call `attach_listing_day_isin` next to get each
    row's authoritative ISIN."""
    df = pd.read_csv(csv_path, parse_dates=["listing_date"])
    df["listing_date"] = df["listing_date"].dt.date
    out = df[["company_name", "listing_date", "final_symbol_at_listing"]].copy()
    out = out.rename(columns={"final_symbol_at_listing": "symbol_at_listing"})
    out.insert(0, "listing_id", range(len(out)))
    return out


def attach_listing_day_isin(warehouse_con: duckdb.DuckDBPyConnection, listings: pd.DataFrame) -> pd.DataFrame:
    """Adds an `isin` column: the ISIN actually trading under each row's
    `symbol_at_listing` on its own `listing_date`, read from `prices_eod`
    (any series -- a brand-new listing commonly trades briefly outside EQ
    before migrating, same finding Section 2 already made). NaN for any
    row with no such row (none expected; logged, not silently dropped, by
    the caller)."""
    isins = []
    for _, r in listings.iterrows():
        row = warehouse_con.execute(
            "SELECT isin FROM prices_eod WHERE symbol = ? AND trade_date = ? LIMIT 1",
            [r["symbol_at_listing"], r["listing_date"]],
        ).fetchone()
        isins.append(row[0] if row else None)
    out = listings.copy()
    out["isin"] = isins
    return out
