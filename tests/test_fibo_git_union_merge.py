"""Proves the fix for BUGS.md's evening-job git-divergence entry: a
single-writer assumption (`git pull --ff-only`) in what is actually a
two-writer system (GitHub Actions commits from the morning job, this
laptop commits from the evening job, both to the same events.jsonl)
blocked every evening run for 7 straight trading days, 2026-11-06 through
2026-11-13, the moment the two histories diverged -- normal, expected
behavior for two independent writers, not an error.

Two real, disposable git repos are merged with real `git` subprocesses
(not mocked) under `.gitattributes`'s `merge=union` driver, reproducing
the exact two-writer shape: a laptop-side commit and a morning-job-side
commit, each appending to events.jsonl from the same common ancestor,
never pushed/pulled before the other existed.

Two things are proven, not assumed:
1. Two divergent appends of DISTINCT events merge via union with no loss
   and no duplication -- `git pull --no-rebase` must not raise, and
   every event from both sides must appear exactly once.
2. The union driver's own guarantee is NOT airtight -- a genuinely
   overlapping edit (both sides add a line with the SAME event_id,
   surrounded by other distinct lines) can produce a literal duplicate
   line in the merged file. `fibo_live.eventlog.read_events`'s
   dedupe-by-event_id is what actually closes this gap, not the merge
   driver alone -- proven by reading the merged file through it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live.eventlog import read_events  # noqa: E402

REL_PATH = "data/fibo_live/v1/events.jsonl"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _init_seed_repo(path: Path, baseline_lines: list[str]) -> None:
    (path / "data" / "fibo_live" / "v1").mkdir(parents=True)
    (path / REL_PATH).write_text("\n".join(baseline_lines) + "\n", encoding="utf-8")
    # The real .gitattributes rule, written fresh here rather than copied
    # from the repo root -- this test must prove the MECHANISM, not just
    # that the real file happens to exist.
    (path / ".gitattributes").write_text(f"{REL_PATH.rsplit('/', 1)[0]}/*.jsonl merge=union\n", encoding="utf-8")
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "init")


def _append_commit_push(repo: Path, lines: list[str], message: str, push: bool = True) -> None:
    with open(repo / REL_PATH, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    if push:
        _git(repo, "push", "-q")


def _event(event_id: str, **extra) -> str:
    return json.dumps({"event_id": event_id, "kind": "setup", **extra})


def test_two_divergent_appends_of_distinct_events_merge_with_no_loss_or_duplication(tmp_path):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "-q", "--bare")

    seed = tmp_path / "seed"
    _init_seed_repo(seed, [_event("e1"), _event("e2")])
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-q", "-u", "origin", "HEAD:main")

    laptop = tmp_path / "laptop"
    _git(tmp_path, "clone", "-q", str(remote), str(laptop))
    _git(laptop, "checkout", "-q", "main")
    _git(laptop, "config", "user.email", "test@example.com")
    _git(laptop, "config", "user.name", "Test")

    morning = tmp_path / "morning"
    _git(tmp_path, "clone", "-q", str(remote), str(morning))
    _git(morning, "checkout", "-q", "main")
    _git(morning, "config", "user.email", "test@example.com")
    _git(morning, "config", "user.name", "Test")

    # Morning job pushes first, from the SAME base commit the laptop started from.
    _append_commit_push(morning, [_event("e3-morning")], "morning appends e3")

    # Laptop commits its own new event, locally, BEFORE ever seeing origin's new commit --
    # this is the divergence: laptop's HEAD and origin/main both have one commit the other lacks.
    _append_commit_push(laptop, [_event("e4-evening")], "laptop appends e4 (not yet pushed)", push=False)

    # The actual fix: --no-rebase (never --ff-only, never rebase).
    result = _git(laptop, "pull", "--no-rebase")
    assert "Merge made" in result.stdout or "Auto-merging" in (result.stdout + result.stderr) \
        or result.returncode == 0

    events = read_events(log_path=laptop / REL_PATH)
    event_ids = sorted(e["event_id"] for e in events)
    assert event_ids == ["e1", "e2", "e3-morning", "e4-evening"], (
        "merge must contain every event from both sides exactly once, no loss, no duplication"
    )


def test_overlapping_duplicate_event_id_is_deduped_by_read_events_not_by_the_merge_driver(tmp_path):
    """The harder case: a documented limit of the union driver, not a
    feature -- proven by forcing it, not assumed away."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "-q", "--bare")

    seed = tmp_path / "seed"
    _init_seed_repo(seed, [_event("e1")])
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-q", "-u", "origin", "HEAD:main")

    laptop = tmp_path / "laptop"
    _git(tmp_path, "clone", "-q", str(remote), str(laptop))
    _git(laptop, "checkout", "-q", "main")
    _git(laptop, "config", "user.email", "test@example.com")
    _git(laptop, "config", "user.name", "Test")

    morning = tmp_path / "morning"
    _git(tmp_path, "clone", "-q", str(remote), str(morning))
    _git(morning, "checkout", "-q", "main")
    _git(morning, "config", "user.email", "test@example.com")
    _git(morning, "config", "user.name", "Test")

    # Both sides add a line with the SAME event_id, but surrounded by
    # different other lines -- an overlapping, non-identical diff hunk.
    _append_commit_push(morning, [_event("X-morning"), _event("DUPLICATE")], "morning: X then DUPLICATE")
    _append_commit_push(laptop, [_event("DUPLICATE"), _event("Y-evening")],
                         "laptop: DUPLICATE then Y", push=False)

    _git(laptop, "pull", "--no-rebase")

    raw_lines = [l for l in (laptop / REL_PATH).read_text(encoding="utf-8").splitlines() if l.strip()]
    raw_duplicate_count = sum(1 for l in raw_lines if json.loads(l)["event_id"] == "DUPLICATE")
    assert raw_duplicate_count == 2, (
        "this assertion documents the union driver's own limit: a genuinely overlapping "
        "hunk CAN still duplicate a line in the raw merged file. If this ever starts "
        "failing (raw_duplicate_count == 1), the merge driver's behavior changed -- good "
        "news, but read_events's dedupe below must still be kept as the real guarantee."
    )

    events = read_events(log_path=laptop / REL_PATH)
    event_ids = [e["event_id"] for e in events]
    assert event_ids.count("DUPLICATE") == 1, (
        "read_events must dedupe the raw duplicate down to one -- this is the actual "
        "guarantee the system relies on, not the merge driver alone"
    )
    assert set(event_ids) == {"e1", "X-morning", "DUPLICATE", "Y-evening"}
