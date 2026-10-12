"""Orchestrates one full 2016-2026 NIFTY-options backfill: disk-space
guard, per-day fetch/extract/verify/delete, resumable (checks fetch_log
before re-fetching a day already resolved either way), flush+heartbeat
logging.
"""
from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import duckdb

from options_history.db import clear_date, fetch_status, insert_rows, log_fetch, row_count_for_date
from options_history.fetch import NoDataForDate, classify_404, fetch_raw_zip, format_for_date, parse_nifty_options

MIN_FREE_GB = 10.0


def disk_free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1024 ** 3


def daterange_weekdays(start: dt.date, end: dt.date):
    d = start
    while d <= end:
        if d.weekday() < 5:  # Monday=0 ... Friday=4
            yield d
        d += dt.timedelta(days=1)


def ingest_one_day(con: duckdb.DuckDBPyConnection, trade_date: dt.date, log) -> str:
    """Returns the final status for `trade_date`: 'ok', 'no_data',
    'error', or 'skipped' (already resolved by an earlier run)."""
    source = format_for_date(trade_date)
    existing = fetch_status(con, source, trade_date)
    if existing in ("ok", "no_data"):
        return "skipped"

    try:
        zip_path, used_source = fetch_raw_zip(trade_date, source=source)
    except NoDataForDate:
        status = classify_404(trade_date)
        log_fetch(con, source, trade_date, status, 0)
        return status

    try:
        rows = parse_nifty_options(zip_path, used_source, trade_date)
        clear_date(con, trade_date)  # idempotent against a prior killed run's orphaned partial insert
        inserted = insert_rows(con, rows)
        verified = row_count_for_date(con, trade_date)
        if verified != len(rows):
            log(f"  VERIFICATION MISMATCH for {trade_date}: parsed {len(rows)}, "
                f"db shows {verified} -- raw file KEPT at {zip_path} for inspection, not deleted.")
            log_fetch(con, source, trade_date, "error", inserted)
            return "error"
        zip_path.unlink()
        log_fetch(con, source, trade_date, "ok", inserted)
        return "ok"
    except Exception as e:
        log(f"  PARSE/INSERT FAILED for {trade_date} ({type(e).__name__}: {e}) -- "
            f"raw file KEPT at {zip_path} for inspection, not deleted.")
        log_fetch(con, source, trade_date, "error", 0)
        return "error"


def run_backfill(con: duckdb.DuckDBPyConnection, start: dt.date, end: dt.date, log,
                  min_free_gb: float = MIN_FREE_GB, heartbeat_every: int = 50) -> dict:
    free_gb = disk_free_gb(Path("C:/"))
    log(f"Disk check: {free_gb:.2f} GB free on C:.")
    if free_gb < min_free_gb:
        log(f"REFUSING TO RUN: only {free_gb:.2f} GB free, below the {min_free_gb} GB floor. Stopping, nothing fetched.")
        return {"aborted_disk": True}

    counts = {"ok": 0, "no_data": 0, "error": 0, "skipped": 0}
    days = list(daterange_weekdays(start, end))
    log(f"Backfilling {len(days)} weekdays from {start} to {end}...")
    for i, d in enumerate(days, start=1):
        status = ingest_one_day(con, d, log)
        counts[status] += 1
        if i % heartbeat_every == 0 or i == len(days):
            free_gb_now = disk_free_gb(Path("C:/"))
            log(f"  [{i}/{len(days)}] {d} -> {status}  (running totals: {counts}, disk free: {free_gb_now:.2f} GB)")
            if free_gb_now < min_free_gb:
                log(f"REFUSING TO CONTINUE: disk dropped below {min_free_gb} GB free mid-run. Stopping.")
                counts["aborted_disk"] = True
                break
    return counts
