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
from pathlib import Path

from .quotes import CSV_HEADER, DepthRow

DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "options_depth" / "v1" / "nifty_depth_log.csv"


def append_rows(rows: list[DepthRow], path: Path = DEFAULT_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(row.as_csv_row())
