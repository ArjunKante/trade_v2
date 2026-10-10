"""Single source of truth for combining Bug #1 (lineage-jump) and Bug #11
(same-isin-jump) exclusions into the one `unexplained_jump_dates` shape
src/fibo/indicators.py's true_range/atr already expect (entity_id -> set of
flagged dates) -- imports both detectors, reimplements neither. Every
caller that builds a Fibo daily panel for real (non-synthetic-test) use
should call this once and thread the result through, rather than each
re-deriving its own exclusion set (the exact "fixed where noticed, not
everywhere the pattern recurs" failure this project has hit five times
before -- BUGS.md).
"""
from __future__ import annotations

import datetime as dt

import duckdb

from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from data_layer.same_isin_jump_guard import unexplained_same_isin_jump_entities


def combined_unexplained_jump_dates(con: duckdb.DuckDBPyConnection, before: dt.date | None = None) -> dict[str, set]:
    """entity_id -> set of dates to treat as untrustworthy for a
    true_range/ATR computation (Bug #1 lineage-transition jumps union Bug
    #11 same-isin jumps, both already restricted by each detector to the
    has_nearby_ca_record == False case -- a jump WITH a corporate-action
    record nearby is a parser gap, not something to blind the ATR to).
    `before`: optional cutoff passed through to both detectors unchanged;
    omit for a full-history read (the right default for a live/current
    computation -- a caller doing historical-window-only work should pass
    its own cutoff explicitly, same convention as both detectors already
    document)."""
    out: dict[str, set] = {}
    for eid, dates in unexplained_jump_boundaries(con, before=before).items():
        out.setdefault(eid, set()).update(dates)

    same_isin = unexplained_same_isin_jump_entities(con, before=before)
    for _, r in same_isin.iterrows():
        out.setdefault(r["entity_id"], set()).add(r["jump_date"])

    return out
