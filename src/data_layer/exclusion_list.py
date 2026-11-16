"""Persisted, materialized exclusion lists.

This is the cheap fix for the reproducibility hole `BUGS.md` Bug #27 and
Bug #28 found: `lineage_jump_guard`/`same_isin_jump_guard` recompute
`has_nearby_ca_record` against the CURRENT `corporate_actions` state on
every call, so re-deriving "the same" exclusion list later can silently
produce a different one. The as-of predicate that would fix the
detectors themselves is separate, larger work (BUGS.md's resolution-path
entry, "item B") and is NOT what this module does.

Instead: a script that PRODUCES a recorded result calls
`save_exclusion_list()` once, persisting the actual entity IDs (and/or
jump dates) it used -- not the code that derives them. A script that
REPRODUCES that result calls `load_exclusion_list()` instead of calling
the detectors again. The loader never falls back to recomputation, under
any flag -- a missing file is an error. Silent recomputation is the
entire cause of Bug #27/#28; a fallback would reintroduce it with extra
steps.

Stored under `results/exclusions/`, not `data/` -- these are entity IDs
and dates, not redistributed NSE price/market data, so the `/data/*`
gitignore carve-out (committed only for a short, deliberate allow-list)
does not apply and should not be extended to cover them. Filenames are
keyed to the RESULT they belong to, not a date, so the link from a
number in `FINDINGS.md`/`PROJECT_CONTEXT.md` to the list that produced
it is unambiguous.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results" / "exclusions"


class ExclusionListMissingError(Exception):
    """Raised when `load_exclusion_list` cannot find the requested file.
    There is no fallback to recomputation -- see this module's own
    docstring for why that path is permanently closed here."""


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _content_hash(components: list) -> str:
    canonical = json.dumps(components, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_exclusion_list(result_id: str, *, produced_by: str, components: list,
                         detector_paths: list, notes: str = "",
                         results_dir: Path = RESULTS_DIR) -> Path:
    """Persist the materialized exclusion state behind one recorded
    result. `components` is a list of dicts, each one of:

      {"guard": "same_isin" | "lineage", "mode": "entity_exclusion",
       "entity_ids": [<entity_id>, ...]}

      {"guard": "same_isin" | "lineage", "mode": "window_mask",
       "jump_dates": {<entity_id>: [<iso date>, ...], ...}}

    `detector_paths`: the detector module file(s) that produced these
    components (e.g. `src/data_layer/same_isin_jump_guard.py`) -- hashed
    and stored so a later reader can at least tell if the CODE changed,
    even though the real instability this fixes is the warehouse STATE,
    which this file freezes by storing the actual IDs/dates directly.

    Writes `<results_dir>/<result_id>.json`. Overwrites if the file
    already exists -- callers that want to protect an existing file
    should check `(results_dir / f"{result_id}.json").exists()` first."""
    results_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "result_id": result_id,
        "produced_by": produced_by,
        "generated_at": dt.datetime.now().isoformat(),
        "notes": notes,
        "detector_source_hashes": {str(p): _file_hash(Path(p)) for p in detector_paths},
        "components": components,
        "content_hash": _content_hash(components),
    }
    path = results_dir / f"{result_id}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=False))
    return path


def load_exclusion_list(result_id: str, results_dir: Path = RESULTS_DIR) -> dict:
    """Load a previously saved exclusion record. Raises
    `ExclusionListMissingError` if the file does not exist -- no
    fallback to recomputation, ever, under any flag. Raises `ValueError`
    if the file's own content hash does not match its components (hand-
    edited or corrupted; not trusted either way)."""
    path = results_dir / f"{result_id}.json"
    if not path.exists():
        raise ExclusionListMissingError(
            f"No saved exclusion list for result_id={result_id!r} at {path}. "
            f"This loader does not fall back to recomputation -- that silent "
            f"recompute path is Bug #27/#28's own mechanism, and reintroducing "
            f"it here would defeat the entire point of this module. Either "
            f"save one (if this script PRODUCES the result) or find/restore "
            f"the file (if this script REPRODUCES a result that should "
            f"already have one)."
        )
    record = json.loads(path.read_text())
    expected = _content_hash(record["components"])
    if record.get("content_hash") != expected:
        raise ValueError(
            f"Content hash mismatch for {path}: expected {expected}, "
            f"recorded {record.get('content_hash')}. The file may have been "
            f"hand-edited or corrupted after being written; not trusting it."
        )
    return record


def entity_ids_from(record: dict, guard: str) -> set:
    """Flat entity-id set from `guard`'s entity_exclusion component, if
    present in this record; empty set otherwise."""
    out = set()
    for c in record["components"]:
        if c["guard"] == guard and c["mode"] == "entity_exclusion":
            out |= set(c["entity_ids"])
    return out


def all_entity_ids(record: dict) -> set:
    """Flat entity-id set across EVERY entity_exclusion component in
    this record, regardless of which guard produced it."""
    out = set()
    for c in record["components"]:
        if c["mode"] == "entity_exclusion":
            out |= set(c["entity_ids"])
    return out


def jump_dates_from(record: dict, guard: str) -> dict:
    """{entity_id: {pd.Timestamp, ...}} from `guard`'s window_mask
    component, if present in this record; empty dict otherwise."""
    import pandas as pd
    out = {}
    for c in record["components"]:
        if c["guard"] == guard and c["mode"] == "window_mask":
            for eid, dates in c["jump_dates"].items():
                out.setdefault(eid, set()).update(pd.Timestamp(d) for d in dates)
    return out


def all_jump_dates(record: dict) -> dict:
    """{entity_id: {pd.Timestamp, ...}} across EVERY window_mask
    component in this record, regardless of which guard produced it."""
    import pandas as pd
    out = {}
    for c in record["components"]:
        if c["mode"] == "window_mask":
            for eid, dates in c["jump_dates"].items():
                out.setdefault(eid, set()).update(pd.Timestamp(d) for d in dates)
    return out
