"""Per-company fundamental snapshot -- a research tool, not a study.

    python scripts/run_fundamental_snapshot.py TCS
    python scripts/run_fundamental_snapshot.py INE467B01029
    python scripts/run_fundamental_snapshot.py --batch-top-decile

No pre-registration, no study slot, no holdout at stake. See
src/reports/fundamental_snapshot.py's module docstring for the two
deliberate design choices this tool makes: it reads current (not
pre-holdout-truncated) price data, and it does NOT read the SEBI Integrated
Filing fundamentals source (unverified context convention) -- both stated
there in full, not repeated here.
"""
import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from reports.fundamental_snapshot import (
    build_company_report, compute_momentum_universe, compute_sector_valuation_snapshot,
    render_report, render_batch_row, render_batch_table,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("identifier", nargs="?", help="symbol or ISIN")
    ap.add_argument("--batch-top-decile", action="store_true",
                     help="run across the current momentum top decile, one row per company")
    args = ap.parse_args()

    if not args.identifier and not args.batch_top_decile:
        ap.error("provide a symbol/ISIN, or pass --batch-top-decile")

    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    print("Computing current momentum universe...", file=sys.stderr)
    universe = compute_momentum_universe(con)
    as_of = universe["as_of_date"].max()
    print("Computing sector valuation snapshot (Nifty Total Market list)...", file=sys.stderr)
    sector_snapshot = compute_sector_valuation_snapshot(con, as_of)

    if args.batch_top_decile:
        top = universe[universe["in_top_decile"]]
        print(f"{len(top)} names in the current momentum top decile "
              f"(of {universe['n_universe'].iloc[0]} active entities, as of {as_of.date()})", file=sys.stderr)
        rows = []
        for _, u in top.iterrows():
            try:
                report = build_company_report(con, u["symbol"], momentum_universe=universe, sector_snapshot=sector_snapshot)
                rows.append(render_batch_row(report))
            except Exception as e:
                print(f"  skipped {u['symbol']}: {e}", file=sys.stderr)
        print(render_batch_table(rows))
    else:
        report = build_company_report(con, args.identifier, momentum_universe=universe, sector_snapshot=sector_snapshot)
        print(render_report(report))

    con.close()


if __name__ == "__main__":
    main()
