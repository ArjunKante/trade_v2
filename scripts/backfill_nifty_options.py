"""CLI: backfills NIFTY index-option EOD data (open/high/low/close,
settlement price, volume, OI -- NO bid/ask, see
OPTIONS_HISTORICAL_FEASIBILITY.md) from NSE's free daily F&O bhavcopy
archive, 2016-01-01 through 2026-09-30, into this module's own
data/options_history/options_history.duckdb.

DISK FIRST: checks free space on C: before fetching anything, and again
every 50 days during the run; refuses to continue below 10 GB free.

RESUMABLE: a day already resolved ('ok' or confirmed 'no_data') in the
fetch_log is skipped -- re-running this script after an interruption
only fetches what is still missing.

HOLIDAY-AWARE (Bug #15's fix, reused not re-derived): a 404 is recorded
'no_data' ONLY when data_layer.nse_holidays confirms the date is a real
NSE holiday. Every other 404 is 'error' -- retried on the next run, never
cached as a wrongly-assumed holiday.

DOES NOT KEEP RAW FILES: each day's whole-market zip is downloaded,
NIFTY-option rows extracted, the insert verified against the parsed row
count, then the raw zip is deleted. Kept only on a verification failure
or a parse/insert exception, for inspection.

Usage: python scripts/backfill_nifty_options.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from options_history.backfill import run_backfill
from options_history.db import get_connection

LOG_PATH = ROOT / "data" / "options_history" / "backfill.log"

DEFAULT_START = dt.date(2016, 1, 1)
DEFAULT_END = dt.date(2026, 9, 30)


def make_logger(log_path: Path = LOG_PATH):
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: object = "") -> None:
        text = str(msg)
        print(text, flush=True)
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            for line in text.splitlines() or [""]:
                f.write(f"[{ts}] {line}\n")
            f.flush()

    return log


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    args = parser.parse_args()
    start = dt.date.fromisoformat(args.start) if args.start else DEFAULT_START
    end = dt.date.fromisoformat(args.end) if args.end else DEFAULT_END

    log = make_logger()
    log(f"=== NIFTY OPTIONS BACKFILL -- {start} to {end} ===")

    con = get_connection()
    counts = run_backfill(con, start, end, log)
    con.close()

    log(f"=== DONE: {counts} ===")


if __name__ == "__main__":
    main()
