"""CLI: reads data/spread_logs/spread_log.csv and reports, per symbol,
n readings, median/min/max spread in bps, and spread by hour of day.

Usage: python scripts/spread_summary.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from spread_monitor.summary import (
    VOLATILE_NIFTY_MOVE_PCT_THRESHOLD, load_log, summarize_by_session,
    summarize_by_symbol, summarize_by_time_of_day,
)
from spread_monitor.writer import DEFAULT_LOG_PATH


def main() -> int:
    if not DEFAULT_LOG_PATH.exists():
        print(f"No log yet at {DEFAULT_LOG_PATH}. Run scripts/snapshot_spreads.py first.")
        return 1

    df = load_log()
    pd.set_option("display.width", 120)

    print(f"=== Per-symbol summary ({len(df)} total readings) ===")
    print(summarize_by_symbol(df).to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\n=== Median spread_bps by hour of day (IST) ===")
    print(summarize_by_time_of_day(df).to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    n_unverified = (df["trading_day_status"] != "OK").sum()
    if n_unverified:
        print(f"\n{n_unverified} row(s) excluded from all stats above: trading day could not be "
              f"live-verified. Check them manually against the day's bhavcopy before trusting them.")

    print("\n=== Spread by session (calm vs volatile, split on |Nifty move| at "
          f"{VOLATILE_NIFTY_MOVE_PCT_THRESHOLD}%) ===")
    print(summarize_by_session(df).to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
