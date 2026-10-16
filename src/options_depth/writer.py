"""Append-only CSV writer for the NIFTY options depth log. Never
overwrites: each run adds rows to the same file, creating it with a
header only if it does not already exist -- same convention as
src/spread_monitor/writer.py, duplicated rather than imported to keep
this package decoupled (see src/options_depth/__init__.py).

THE FILE THIS WRITES IS IRREPLACEABLE AND NOT IN GIT (see this package's
__init__.py) -- it lives only on this laptop until manually copied
elsewhere."""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from .quotes import CSV_HEADER, DepthRow

DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "options_depth" / "v1" / "nifty_depth_log.csv"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"  # matches DepthRow.timestamp_ist, see quotes.py


def append_rows(rows: list[DepthRow], path: Path = DEFAULT_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(row.as_csv_row())


def snapshot_health(today: dt.date, path: Path = DEFAULT_LOG_PATH) -> dict:
    """Read-only health summary, for the evening job's daily log line
    (OPERATIONS.md): the number of DISTINCT snapshot timestamps recorded
    on `today`, and the most recent snapshot timestamp in the whole log
    (which may be from an earlier day, or None if the file does not
    exist yet) -- so a day with zero snapshots shows up as "0 today,
    last one was 2026-09-01" rather than silently.

    One snapshot writes one row per contract (~150-200 rows), so "number
    of snapshots" is the count of DISTINCT timestamp_ist values, not the
    row count."""
    if not path.exists():
        return {"snapshots_today": 0, "most_recent_ts": None}

    timestamps_today: set[str] = set()
    most_recent: dt.datetime | None = None
    with path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row.get("timestamp_ist")
            if not raw:
                continue
            try:
                parsed = dt.datetime.strptime(raw, TIMESTAMP_FORMAT)
            except ValueError:
                continue
            if parsed.date() == today:
                timestamps_today.add(raw)
            if most_recent is None or parsed > most_recent:
                most_recent = parsed

    return {
        "snapshots_today": len(timestamps_today),
        "most_recent_ts": most_recent.strftime(TIMESTAMP_FORMAT) if most_recent else None,
    }
