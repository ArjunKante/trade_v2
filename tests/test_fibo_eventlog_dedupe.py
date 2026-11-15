"""src/fibo_live/eventlog.py's read_events dedupe-by-event_id -- cheap
insurance against a line appearing on both sides of a git merge
(.gitattributes's merge=union driver, src/fibo_live/git_sync.py's
pull_before_appending). See tests/test_fibo_git_union_merge.py for the
real-git proof that such a duplicate can actually occur; this file tests
the dedupe logic itself, directly, without needing git at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live.eventlog import append_event, read_events  # noqa: E402


def _write_raw(log_path: Path, *events: dict) -> None:
    with open(log_path, "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def test_duplicate_event_id_collapses_to_first_occurrence(tmp_path):
    log_path = tmp_path / "events.jsonl"
    _write_raw(
        log_path,
        {"event_id": "a", "kind": "setup", "n": 1},
        {"event_id": "b", "kind": "setup", "n": 2},
        {"event_id": "a", "kind": "setup", "n": 1},  # exact duplicate, as a union merge can produce
    )
    events = read_events(log_path=log_path)
    assert [e["event_id"] for e in events] == ["a", "b"]


def test_no_event_id_field_is_never_deduped_against_anything(tmp_path):
    """Defensive: every real append_event call mints an event_id, but the
    dedupe must not crash or silently drop a line that lacks one."""
    log_path = tmp_path / "events.jsonl"
    _write_raw(
        log_path,
        {"kind": "legacy_no_id", "n": 1},
        {"kind": "legacy_no_id", "n": 2},
    )
    events = read_events(log_path=log_path)
    assert len(events) == 2


def test_normal_append_and_read_round_trip_unaffected_by_dedupe(tmp_path):
    log_path = tmp_path / "events.jsonl"
    e1 = append_event("setup", {"symbol": "RELIANCE"}, log_path=log_path)
    e2 = append_event("setup", {"symbol": "TCS"}, log_path=log_path)
    events = read_events(log_path=log_path)
    assert [e["event_id"] for e in events] == [e1["event_id"], e2["event_id"]]
    assert read_events(kind="setup", log_path=log_path) == events


def test_returns_empty_list_for_missing_file(tmp_path):
    assert read_events(log_path=tmp_path / "does_not_exist.jsonl") == []
