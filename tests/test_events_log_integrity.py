"""Integrity checks on the REAL data/fibo_live/v1/events.jsonl -- this
project's entire evidence trail for the Fibo forward test. Deliberately
a VERIFICATION, not vigilance (BUGS.md Bug #24): these run every time
the suite runs, with no human needing to remember to look.

Reads the file directly, by path, NEVER through conftest.py's
`_redirect_events_log` fixture (that fixture only redirects
`fibo_live.config.EVENTS_LOG` for code that resolves it fresh -- it
cannot and must not redirect a test that deliberately wants the real
path to check it)."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fibo_live.config as fibo_config  # noqa: E402

REAL_EVENTS_LOG = fibo_config.ROOT / "data" / "fibo_live" / "v1" / "events.jsonl"

# Kinds logged by exactly ONE job, so file-order ts must be monotonic
# within each: watchlist/watchlist_run/data_correction/
# watchlist_run_correction are evening-job only; setup/trigger/outcome
# are morning-job only. notification and session_status are logged by
# EITHER job (src/fibo_live/notify.py, session_status.py are called from
# both scripts/fibo_evening.py and scripts/fibo_morning.py) -- excluded
# from the monotonic check for that reason, not an oversight: a morning
# run's notification can legitimately carry an earlier or later ts than
# an evening run's, interleaved in file order after a git merge of two
# genuinely independent writers.
SINGLE_WRITER_KINDS = {
    "watchlist", "watchlist_run", "data_correction", "watchlist_run_correction",
    "setup", "trigger", "outcome",
}


def _read_raw_lines() -> list[str]:
    if not REAL_EVENTS_LOG.exists():
        pytest.skip("real events.jsonl does not exist in this checkout")
    return [l for l in REAL_EVENTS_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def _parsed_events() -> list[dict]:
    events = []
    for i, line in enumerate(_read_raw_lines()):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as e:
            pytest.fail(f"events.jsonl line {i + 1} is not valid JSON: {e}")
    return events


def test_every_line_is_well_formed_json_with_required_fields():
    events = _parsed_events()
    assert events, "events.jsonl exists but has no parseable lines"
    for i, e in enumerate(events):
        assert "event_id" in e, f"line {i + 1} missing event_id: {e}"
        assert "ts" in e, f"line {i + 1} missing ts: {e}"
        assert "kind" in e, f"line {i + 1} missing kind: {e}"
        # must parse as a real timestamp, not just be present
        dt.datetime.fromisoformat(e["ts"])


def test_all_event_ids_are_unique():
    events = _parsed_events()
    ids = [e["event_id"] for e in events if e.get("event_id") is not None]
    duplicates = {x for x in ids if ids.count(x) > 1}
    assert not duplicates, (
        f"duplicate event_id(s) in events.jsonl: {duplicates} -- read_events() "
        f"dedupes these at read time (eventlog.py), but the file itself should "
        f"never have grown a true duplicate append in the first place."
    )


def _parse_ts_as_naive_wall_clock(ts: str) -> dt.datetime:
    """events.jsonl has a real, explained mix (checked 2026-11-15, BUGS.md
    Bug #24): lines from 2026-10-08 through 2026-10-13 have NAIVE `ts`
    (append_event predated IST-aware timestamping); 2026-10-13 onward have
    `ts` with an explicit +05:30 offset (ZoneInfo("Asia/Kolkata"), added
    that day -- the one day of overlap is where the fix landed mid-day).
    Both represent the same thing, IST wall-clock time, so comparing them
    for ordering purposes means dropping the offset rather than treating
    aware and naive as genuinely different instants."""
    parsed = dt.datetime.fromisoformat(ts)
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def test_timestamps_are_monotonic_within_each_single_writer_kind():
    events = _parsed_events()
    by_kind: dict[str, list[tuple[int, str]]] = {}
    for i, e in enumerate(events):
        kind = e.get("kind")
        if kind in SINGLE_WRITER_KINDS:
            by_kind.setdefault(kind, []).append((i, e["ts"]))

    violations = []
    for kind, rows in by_kind.items():
        prev_ts = None
        prev_line = None
        for line_no, ts in rows:
            parsed = _parse_ts_as_naive_wall_clock(ts)
            if prev_ts is not None and parsed < prev_ts:
                violations.append(
                    f"kind={kind!r}: line {line_no + 1} (ts={ts}) is earlier than "
                    f"line {prev_line + 1} (ts={prev_ts.isoformat()})"
                )
            prev_ts = parsed
            prev_line = line_no
    assert not violations, "events.jsonl has out-of-order timestamps:\n" + "\n".join(violations)


def test_file_matches_the_last_committed_version():
    """A sanity check at whatever point in the run this test happens to
    execute: right now, this file has no uncommitted changes. This is
    NOT the authoritative "did this test RUN corrupt the file" check --
    pytest collects and can run test files in any order, so a test file
    alphabetically before this one could corrupt events.jsonl AFTER this
    assertion already passed. The authoritative, order-independent check
    is conftest.py's `pytest_sessionfinish` hook, which hashes the file
    at session start and compares again after every single test has
    finished, no matter which one (if any) touched it. Kept here too
    because a named, individually-diagnosable pytest failure is more
    useful during normal development than only a session-exit-code flip."""
    rel = str(REAL_EVENTS_LOG.relative_to(fibo_config.ROOT))
    result = subprocess.run(
        ["git", "diff", "--exit-code", "--", rel],
        cwd=fibo_config.ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"data/fibo_live/v1/events.jsonl has uncommitted changes:\n{result.stdout}\n"
        f"This file is this project's entire evidence trail for the Fibo forward "
        f"test (git_sync.py's module docstring) -- an uncommitted change here, "
        f"from a test run or anything else, must be investigated before it is "
        f"either committed or reverted, never left dirty."
    )
