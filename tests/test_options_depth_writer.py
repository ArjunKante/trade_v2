"""Regression tests for src/options_depth/writer.py's snapshot_health --
the evening job's daily health line (OPERATIONS.md): count of distinct
snapshot timestamps recorded today, and the most recent timestamp ever
recorded, read straight from the append-only CSV log."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from options_depth.writer import mark_invalid, snapshot_health

HEADER = "timestamp_ist,symbol,token,expiry,strike,option_type,ltp\n"


def _write_log(path: Path, rows: list[tuple]) -> None:
    lines = [HEADER]
    for ts, symbol in rows:
        lines.append(f"{ts},{symbol},1,13OCT2026,22000.0,CE,100.0\n")
    path.write_text("".join(lines), encoding="utf-8")


def test_missing_file_returns_zero_and_none(tmp_path):
    result = snapshot_health(dt.date(2026, 10, 16), path=tmp_path / "nope.csv")
    assert result == {"snapshots_today": 0, "invalid_today": 0, "most_recent_ts": None}


def test_counts_distinct_timestamps_not_rows(tmp_path):
    log = tmp_path / "log.csv"
    # one snapshot (same timestamp) writes multiple contract rows -- must
    # count as ONE snapshot, not three
    _write_log(log, [
        ("2026-10-16 10:30:05", "NIFTY1"),
        ("2026-10-16 10:30:05", "NIFTY2"),
        ("2026-10-16 10:30:05", "NIFTY3"),
        ("2026-10-16 12:30:07", "NIFTY1"),
    ])
    result = snapshot_health(dt.date(2026, 10, 16), path=log)
    assert result["snapshots_today"] == 2
    assert result["most_recent_ts"] == "2026-10-16 12:30:07"


def test_zero_snapshots_today_still_reports_most_recent_from_an_earlier_day(tmp_path):
    log = tmp_path / "log.csv"
    _write_log(log, [("2026-10-12 09:50:26", "NIFTY1"), ("2026-10-12 10:00:27", "NIFTY1")])
    result = snapshot_health(dt.date(2026, 10, 16), path=log)
    assert result["snapshots_today"] == 0
    assert result["most_recent_ts"] == "2026-10-12 10:00:27"  # not silently None -- the whole point


def test_only_counts_rows_matching_the_requested_date(tmp_path):
    log = tmp_path / "log.csv"
    _write_log(log, [
        ("2026-10-15 14:30:01", "NIFTY1"),
        ("2026-10-16 10:30:02", "NIFTY1"),
        ("2026-10-16 12:30:03", "NIFTY1"),
    ])
    result = snapshot_health(dt.date(2026, 10, 16), path=log)
    assert result["snapshots_today"] == 2
    assert result["most_recent_ts"] == "2026-10-16 12:30:03"


def test_invalidated_timestamp_is_excluded_from_count_and_most_recent(tmp_path):
    log = tmp_path / "log.csv"
    invalid = tmp_path / "invalid.csv"
    _write_log(log, [
        ("2026-10-16 10:30:05", "NIFTY1"),
        ("2026-10-16 12:30:07", "NIFTY1"),
        ("2026-10-16 14:30:09", "NIFTY1"),
    ])
    # the LATEST of the three is the stale one -- must not win most_recent_ts either
    mark_invalid("2026-10-16 14:30:09", "stale tick, market shut", path=invalid)
    result = snapshot_health(dt.date(2026, 10, 16), path=log, invalid_path=invalid)
    assert result["snapshots_today"] == 2
    assert result["invalid_today"] == 1
    assert result["most_recent_ts"] == "2026-10-16 12:30:07"
