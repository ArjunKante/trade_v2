"""Read-only inspection tool for OPERATIONS_UNATTENDED.md's gap_backfill
LineageWouldChangeError recovery procedure (BUGS.md Bug #33).

Answers: "if I ran scripts/build_isin_lineage.py right now, which isins
would change, and how?" -- the exact question a human needs answered
before deciding whether to accept a pending lineage change. Safe to run
at any time, any number of times, including long after the triggering
evening-job failure: it diffs a FRESH build_lineage() against whatever
is CURRENTLY PERSISTED in isin_lineage, which is unaffected by this
script and does not change just because time has passed.

Prints each changed isin's old vs new (entity_id, predecessor_isin,
link_method, known_date) side by side. Changes nothing -- get_read_
connection only, same read-only discipline as every other audit script
in this project.

Usage: python scripts/inspect_lineage_drift.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection  # noqa: E402
from data_layer.gap_backfill import _LINEAGE_CONTENT_COLS, _lineage_content_diff  # noqa: E402
from data_layer.isin_lineage import build_lineage  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
    persisted = con.execute(f"SELECT isin, {', '.join(_LINEAGE_CONTENT_COLS)} FROM isin_lineage").fetchdf()
    fresh, ambiguous = build_lineage(con)

    changed = _lineage_content_diff(persisted, fresh)
    print(f"Currently persisted isin_lineage: {len(persisted)} isins.")
    print(f"Fresh build_lineage() right now: {len(fresh)} isins, {len(ambiguous)} ambiguous pairs.")
    print(f"\n{len(changed)} isin(s) would change if scripts/build_isin_lineage.py were run now:\n")

    if not changed:
        print("  (none -- the frozen table already matches what a fresh rebuild would produce. "
              "Safe to leave as-is; no action needed.)")
        return

    persisted_idx = persisted.set_index("isin")
    fresh_idx = fresh.set_index("isin")
    for isin in changed:
        old = persisted_idx.loc[isin] if isin in persisted_idx.index else None
        new = fresh_idx.loc[isin] if isin in fresh_idx.index else None
        print(f"  {isin}:")
        if old is None:
            print(f"    OLD: (not in currently persisted isin_lineage at all)")
        else:
            print(f"    OLD: entity_id={old['entity_id']} predecessor_isin={old['predecessor_isin']} "
                  f"link_method={old['link_method']} known_date={old['known_date']}")
        if new is None:
            print(f"    NEW: (would be removed -- no longer resolves to any isin in prices_eod)")
        else:
            print(f"    NEW: entity_id={new['entity_id']} predecessor_isin={new['predecessor_isin']} "
                  f"link_method={new['link_method']} known_date={new['known_date']}")
    print(f"\nReview each one by hand (is the NEW resolution actually correct?) before deciding "
          f"whether to run scripts/build_isin_lineage.py -- see OPERATIONS_UNATTENDED.md's "
          f"LineageWouldChangeError recovery procedure for the full decision and the required "
          f"margin_tripwire.py follow-up.")


if __name__ == "__main__":
    main()
