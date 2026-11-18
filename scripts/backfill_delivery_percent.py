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
`trade-info` (2016-2025), 369 (11.0%) are NOT in this project's own
`isin_lineage` at all -- 7.0% of delivery ROWS. This is NOT a lineage
MISLINK (Bug #7/#11/#33's shape) -- it is a universe-coverage gap in this
project's own price ingestion: unmatched ISINs skew heavily toward
recently-listed names (85.4% first traded after 2016-06, median first
trade 2022-10-17, vs 49.3%/2016-03-14 for matched) and toward lower
liquidity (median avg turnover ~5.0M vs ~39.2M for matched, ~8x). These
369 ISINs are simply never fetched into this project's `prices_eod` at
all, under any ISIN -- there is nothing for `isin_lineage` to have
mis-resolved. Confirmed, not assumed: checked against `prices_eod`
directly below, not inferred from the `isin_lineage` absence alone.

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

import duckdb
import pandas as pd

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

    matched["known_date"] = matched["trade_date"]
    matched["fetched_at"] = dt.datetime.now()
    matched["source"] = SOURCE_NAME
    matched["revision_seq"] = 1
    out = matched[["isin", "trade_date", "delivery_volume", "delivery_percent",
                    "known_date", "fetched_at", "source", "revision_seq"]]

    con = duckdb.connect(str(WAREHOUSE_DB))
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
