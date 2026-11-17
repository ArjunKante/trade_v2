"""Standalone report for BUGS.md Bug #30's structural fix: every trading
day prices_eod is missing against NSE's own holiday master, across the
whole history currently in the warehouse.

Read-only -- reports, does not fetch or fix anything. Run this by hand
(or, once a decision is made per BUGS.md, as part of the evening job)
to see the full list before deciding how a missing day should be
handled automatically.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection  # noqa: E402
from data_layer.price_gap_detector import find_missing_trading_days  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
    missing = find_missing_trading_days(con)
    if not missing:
        print("No missing trading days found in prices_eod's full history.")
        return
    print(f"{len(missing)} missing trading day(s) found:")
    for m in missing:
        print(f"  {m.trade_date}  {m.reason}")


if __name__ == "__main__":
    main()
