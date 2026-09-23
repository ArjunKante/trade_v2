"""Two diagnostics on a completed fundamental-screener run: a per-metric
FAIL breakdown (is the screen balanced or does one metric dominate?) and a
cause-split of the INSUFFICIENT DATA group (too-new listing vs mature-but-
unfiled vs a specific missing field). Descriptive only -- changes no
threshold and reclassifies no verdict.

    python scripts/run_screener_diagnostics.py --source-run fundamental_screener_20260923T193821

Re-runs the screener against the current warehouse (confirmed identical to
the referenced run: same funnel 147/119/81/43/38/66, same warehouse state,
nothing ingested in between) rather than re-parsing the log file, so the
diagnostics are computed from the same typed result the original run used,
not a text re-parse of it.
"""
import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from reports.fundamental_screener import (
    run_screener, fail_breakdown, insufficient_breakdown, render_diagnostics, write_diagnostics_log,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-run", required=True, help="label of the screener run these diagnostics describe")
    args = ap.parse_args()

    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
    print("Re-running screener to compute diagnostics against the same result...", file=sys.stderr)
    result = run_screener(con)
    print(f"Funnel: {result['funnel']}  (confirm this matches the referenced run before trusting the diagnostics below)", file=sys.stderr)

    fb = fail_breakdown(result)
    ib = insufficient_breakdown(con, result)
    con.close()

    text = render_diagnostics(fb, ib, args.source_run)
    print(text)

    path = write_diagnostics_log(text, ROOT)
    print(f"\nDiagnostics log written to {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
