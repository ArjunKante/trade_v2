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
DEFAULT_INVALID_PATH = Path(__file__).resolve().parents[2] / "data" / "options_depth" / "v1" / "invalidated_snapshots.csv"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"  # matches DepthRow.timestamp_ist, see quotes.py
INVALID_CSV_HEADER = ["timestamp_ist", "reason", "marked_at_ist"]


def append_rows(rows: list[DepthRow], path: Path = DEFAULT_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(row.as_csv_row())


def mark_invalid(timestamp_ist: str, reason: str, path: Path = DEFAULT_INVALID_PATH) -> None:
    """Append-only correction for a snapshot ALREADY WRITTEN to
    nifty_depth_log.csv (e.g. a stale tick recorded while the market was
    shut on an NSE holiday) -- never rewrites or deletes the original
    rows, same convention as ipo_listing.rescale's revision_seq rows.
    snapshot_health() reads this file to exclude invalidated timestamps
    from its count, so marking something invalid here is what actually
    makes it stop counting as an observation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(INVALID_CSV_HEADER)
        writer.writerow([timestamp_ist, reason, dt.datetime.now().strftime(TIMESTAMP_FORMAT)])


def load_invalidated_timestamps(path: Path = DEFAULT_INVALID_PATH) -> dict[str, str]:
    """{timestamp_ist: reason} for every snapshot marked invalid via
    mark_invalid(). Empty dict if the file doesn't exist yet."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = row.get("timestamp_ist")
            if ts:
                out[ts] = row.get("reason", "")
    return out


def snapshot_health(today: dt.date, path: Path = DEFAULT_LOG_PATH, invalid_path: Path = DEFAULT_INVALID_PATH) -> dict:
    """Read-only health summary, for the evening job's daily log line
    (OPERATIONS.md): the number of VALID DISTINCT snapshot timestamps
    recorded on `today` (excluding anything mark_invalid() has flagged --
    a stale tick captured on a shut market must never count as an
    observation), and the most recent VALID snapshot timestamp in the
    whole log (which may be from an earlier day, or None if the file does
    not exist yet) -- so a day with zero snapshots shows up as "0 today,
    last one was 2026-09-01" rather than silently.

    One snapshot writes one row per contract (~150-200 rows), so "number
    of snapshots" is the count of DISTINCT timestamp_ist values, not the
    row count."""
    if not path.exists():
        return {"snapshots_today": 0, "invalid_today": 0, "most_recent_ts": None}

    invalidated = load_invalidated_timestamps(invalid_path)

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
            if raw not in invalidated and (most_recent is None or parsed > most_recent):
                most_recent = parsed

    valid_today = {t for t in timestamps_today if t not in invalidated}

    return {
        "snapshots_today": len(valid_today),
        "invalid_today": len(timestamps_today) - len(valid_today),
        "most_recent_ts": most_recent.strftime(TIMESTAMP_FORMAT) if most_recent else None,
    }
