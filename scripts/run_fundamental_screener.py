"""Fundamental screener: filters the momentum top decile down to a
shortlist. Research tool, not a study -- see
src/reports/fundamental_screener.py's module docstring for the untested-
modification disclaimer, the accepted turnaround-story trade-off, and the
verdict precedence rule.

    python scripts/run_fundamental_screener.py

Writes a full timestamped log (every company, every check, survivors,
insufficient-data, and failed with reasons) to data/screener_logs/.
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from reports.fundamental_screener import run_screener, render_full_report, write_log

ROOT = Path(__file__).resolve().parents[1]


def main():
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
    print("Running fundamental screener over the current momentum top decile...", file=sys.stderr)
    result = run_screener(con)
    con.close()

    report = render_full_report(result)
    print(report)

    log_path = write_log(report, ROOT)
    print(f"\nFull log written to {log_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
