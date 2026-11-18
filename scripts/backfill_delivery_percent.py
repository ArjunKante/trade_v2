"""One-time (re-runnable) import of NSE delivery position (MTO report) data
from the sibling `trade-info` project's `prices_raw` table into this
project's own `delivery_eod` table (src/data_layer/db.py).

WHY A SEPARATE PROJECT IS THE SOURCE: `delivery_volume`/`delivery_percent`
do not exist anywhere in this project's own ingestion (`prices_eod` has no
such columns and never has) -- confirmed by Phase 0 feasibility check,
2026-11-19. `trade-info` already ingests and backfills this data
(`backfill_trades_delivery_log`), with 100% coverage 2016-2025 and a hard
cutoff at 2026-01 (that project's own backfill has not caught up past
2025-12-31). This import's scope matches that cutoff exactly -- 2016-2025,
not later -- since nothing past it exists to import.

ENTITY RESOLUTION, the hard part, reported here rather than silently
resolved: `trade-info` keys delivery rows on bare ISIN; this project's own
factor/universe code resolves ISINs to `entity_id` via `isin_lineage`
(lineage has already produced Bugs #7, #11, #33 -- a history of silent
misresolution in this exact join). Checked directly before writing
anything (2026-11-19): of 3,344 distinct ISINs with delivery data in
`trade-info` (2016-2025), 369 (11.0%, 7.0% of rows) are NOT in this
project's own `isin_lineage` at all.

**CORRECTED, same day, before this script's first real run finished
being reviewed**: the first pass characterized this as a universe-
coverage gap (unmatched ISINs skewing toward recent listings and lower
liquidity). Checked the actual unmatched ISIN list directly and that
framing was wrong -- **all 369 of them, 100%, are `INF`-prefixed**
(fund/ETF units), which `isin_lineage.build_isin_date_ranges`
(`EQUITY_ISIN_PREFIXES = ("INE", "IN9")`) excludes BY DESIGN -- INF uses
a different NSDL allocation scheme entirely and was never equity in
scope for that module's structural rule to begin with. There is no real
entity-resolution gap at all: every genuine equity ISIN in `trade-info`'s
delivery data resolves cleanly. The listing-age/liquidity skew observed
is just a property of fund/ETF products as a category (many newly
launched, more thinly traded) and has nothing to do with lineage
coverage -- coincidental correlation, not the cause.

UNMATCHED ISINS ARE SKIPPED, NEVER SILENTLY DROPPED: this script writes a
full report (`results/delivery_import_unmatched_isins.csv`) listing every
skipped ISIN with its own first/last trade date and average turnover, so
the skew above is independently checkable, not just asserted here.

Idempotent: deletes and re-inserts its own `source` tag's rows for the
scoped date range before inserting, so re-running does not duplicate.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import sys

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from data_layer.db import get_connection  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TRADE_INFO_DB = Path(r"C:\projects\trade-info\data\nsepit.duckdb")
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
UNMATCHED_REPORT = ROOT / "results" / "delivery_import_unmatched_isins.csv"

SOURCE_NAME = "TRADE_INFO_PRICES_RAW_IMPORT"
SCOPE_START = dt.date(2016, 1, 1)
SCOPE_END = dt.date(2025, 12, 31)  # trade-info's own delivery backfill has not caught up past this


def main() -> None:
    if not TRADE_INFO_DB.exists():
        raise FileNotFoundError(
            f"{TRADE_INFO_DB} not found -- this import only runs on a machine with the "
            f"sibling trade-info checkout present. Not a remote/CI-portable step."
        )

    src = duckdb.connect(str(TRADE_INFO_DB), read_only=True)
    dst_known_isins = set(
        duckdb.connect(str(WAREHOUSE_DB), read_only=True)
        .execute("SELECT DISTINCT isin FROM isin_lineage")
        .fetchdf()["isin"]
    )

    print(f"Reading trade-info prices_raw, deduped to latest revision, {SCOPE_START}..{SCOPE_END}...")
    df = src.execute(
        f"""
        WITH latest AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY isin, date ORDER BY revision_seq DESC) AS rn
            FROM prices_raw
            WHERE date BETWEEN '{SCOPE_START}' AND '{SCOPE_END}' AND delivery_percent IS NOT NULL
        )
        SELECT isin, date AS trade_date, delivery_volume, delivery_percent, turnover
        FROM latest WHERE rn = 1
        """
    ).fetchdf()
    src.close()
    print(f"  {len(df):,} source rows, {df['isin'].nunique():,} distinct ISINs.")

    matched_mask = df["isin"].isin(dst_known_isins)
    matched = df[matched_mask].copy()
    unmatched = df[~matched_mask].copy()

    print(f"Matched to isin_lineage: {len(matched):,} rows, {matched['isin'].nunique():,} ISINs.")
    print(f"UNMATCHED (skipped, not dropped silently): {len(unmatched):,} rows "
          f"({100 * len(unmatched) / len(df):.1f}%), {unmatched['isin'].nunique():,} ISINs "
          f"({100 * unmatched['isin'].nunique() / df['isin'].nunique():.1f}%).")

    unmatched_profile = unmatched.groupby("isin").agg(
        first_date=("trade_date", "min"), last_date=("trade_date", "max"),
        avg_turnover=("turnover", "mean"), n_rows=("trade_date", "count"),
    ).reset_index().sort_values("isin")
    UNMATCHED_REPORT.parent.mkdir(parents=True, exist_ok=True)
    unmatched_profile.to_csv(UNMATCHED_REPORT, index=False)
    print(f"  Unmatched-ISIN profile written to {UNMATCHED_REPORT}.")

    # Verified property, not just documented prose: as of 2026-11-19, every
    # unmatched ISIN is INF-prefixed (fund/ETF units, out of scope for
    # isin_lineage's equity-only structural rule by design -- see module
    # docstring's correction). A non-INF ISIN showing up unmatched on a
    # future re-run would mean an actual equity coverage gap has appeared
    # and this printed warning is what would surface it.
    non_inf_unmatched = sorted(set(unmatched_profile.loc[~unmatched_profile["isin"].str.startswith("INF"), "isin"]))
    if non_inf_unmatched:
        print(f"  WARNING: {len(non_inf_unmatched)} unmatched ISIN(s) are NOT fund/ETF (INF-prefixed) -- "
              f"a real equity coverage gap, not the fund-exclusion explained in this script's docstring: "
              f"{non_inf_unmatched[:10]}")
    else:
        print("  Confirmed: all unmatched ISINs are INF-prefixed (fund/ETF units) -- "
              "no real equity entity-resolution gap.")

    matched["known_date"] = matched["trade_date"]
    matched["fetched_at"] = dt.datetime.now()
    matched["source"] = SOURCE_NAME
    matched["revision_seq"] = 1
    out = matched[["isin", "trade_date", "delivery_volume", "delivery_percent",
                    "known_date", "fetched_at", "source", "revision_seq"]]

    con = get_connection(WAREHOUSE_DB)
    con.execute(
        "DELETE FROM delivery_eod WHERE source = ? AND trade_date BETWEEN ? AND ?",
        [SOURCE_NAME, SCOPE_START, SCOPE_END],
    )
    con.register("delivery_new", out)
    con.execute("INSERT INTO delivery_eod SELECT * FROM delivery_new")
    con.unregister("delivery_new")
    n_written = con.execute(
        "SELECT COUNT(*) FROM delivery_eod WHERE source = ?", [SOURCE_NAME]
    ).fetchone()[0]
    con.close()
    print(f"\nWrote {len(out):,} rows to delivery_eod (table now has {n_written:,} rows from this source).")


if __name__ == "__main__":
    main()
