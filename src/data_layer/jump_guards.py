"""Single entry point for the merged jump-guard dict that
`compute_momentum`/`compute_forward_return` now require explicitly
(BUGS.md Bug #26's structural resolution, 2026-11-16) -- combines
`lineage_jump_guard` (Bug #1, transition-boundary jumps) and the FULL,
unfiltered `same_isin_jump_guard` output (Bug #11, same-ISIN jumps of
any `gap_days`, not just the tight 78/82-entity canonical pin, which
Bug #26 follow-up 3 showed catches almost none of the lineage exposure
and was never designed to protect an arbitrary forward-return window).

One function, so every caller that wants "the real guard" gets the
same, complete answer, rather than each re-deriving its own partial
version."""
from __future__ import annotations

import datetime as dt

import duckdb

from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from data_layer.same_isin_jump_guard import find_unexplained_same_isin_jumps


def all_unexplained_jump_dates(con: duckdb.DuckDBPyConnection, before: dt.date | None = None) -> dict[str, set]:
    """entity_id -> set of dates to treat as a hard boundary for any
    momentum/forward-return window that spans them. Merges both guards;
    pass `before` to restrict to jumps known as of a given date (same
    point-in-time convention both underlying guards already use)."""
    merged: dict[str, set] = {}
    for eid, dates in unexplained_jump_boundaries(con, before=before).items():
        merged.setdefault(eid, set()).update(dates)

    same_isin = find_unexplained_same_isin_jumps(con, before=before)
    same_isin = same_isin[~same_isin["has_nearby_ca_record"]]
    if not same_isin.empty:
        lineage = con.execute("SELECT DISTINCT isin, entity_id FROM isin_lineage").fetchdf()
        iso_to_entity = lineage.set_index("isin")["entity_id"].to_dict()
        for _, row in same_isin.iterrows():
            eid = iso_to_entity.get(row["isin"])
            if eid:
                merged.setdefault(eid, set()).add(row["jump_date"])

    return merged
