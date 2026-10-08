"""Append-only CSV writer for spread readings. Never overwrites: each
run adds rows to the same file, creating it with a header only if it
does not already exist."""
from __future__ import annotations

import csv
from pathlib import Path

from .quotes import CSV_HEADER, QuoteRow

DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "spread_logs" / "spread_log.csv"


def append_rows(rows: list[QuoteRow], path: Path = DEFAULT_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(row.as_csv_row())
