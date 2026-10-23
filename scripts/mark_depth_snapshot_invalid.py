"""One-off, reproducible correction tool: marks a snapshot timestamp
ALREADY WRITTEN to data/options_depth/v1/nifty_depth_log.csv as invalid,
without rewriting or deleting the original rows (src/options_depth/
writer.py's mark_invalid -- append-only, same convention as
ipo_listing.rescale's revision_seq correction rows).

Usage:
    python scripts/mark_depth_snapshot_invalid.py "2026-10-20 10:30:57" "reason text"
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from options_depth.writer import mark_invalid


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <timestamp_ist> <reason>")
        sys.exit(1)
    timestamp_ist, reason = sys.argv[1], sys.argv[2]
    mark_invalid(timestamp_ist, reason)
    print(f"Marked invalid: {timestamp_ist!r} -- {reason}")


if __name__ == "__main__":
    main()
