"""src/fibo_live/git_sync.py's pull_before_appending: the FIRST thing
fibo_evening.py's main() does, before any append_event call, once the
Fibo morning job moves to GitHub Actions and may have pushed commits the
laptop hasn't seen yet. Unlike the module's push (best-effort, every
failure swallowed), this must RAISE on failure -- proceeding against a
possibly-stale local events.jsonl is exactly what it exists to prevent.

CHANGED 2026-11-15: `--ff-only` -> `--no-rebase`, after the former blocked
every evening run for 7 straight trading days (2026-11-06 through
2026-11-13) the moment the laptop's local HEAD and origin diverged --
the NORMAL state in a two-writer system (GitHub Actions + this laptop),
not an error. See `test_merges_cleanly_when_laptop_and_origin_have_both_
diverged` below (the literal historical failure, now proven fixed) and
`tests/test_fibo_git_union_merge.py` (the events.jsonl-specific union
merge driver this relies on to make that merge conflict-free).

Uses real git subprocesses against disposable tmp_path repos (matching
git_sync.py's own subprocess-based design) rather than mocking git
itself.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live import git_sync  # noqa: E402
from fibo_live.git_sync import GitPullError, pull_before_appending  # noqa: E402


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _init_repo_with_commit(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("initial\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-q", "-m", "initial")


def test_raises_loudly_when_no_remote_is_configured(tmp_path, monkeypatch):
    """No remote tracking info at all -- git pull --ff-only has nothing
    sane to do and must fail; this must surface as GitPullError, not be
    swallowed."""
    repo = tmp_path / "repo"
    _init_repo_with_commit(repo)
    monkeypatch.setattr(git_sync, "ROOT", repo)

    with pytest.raises(GitPullError):
        pull_before_appending(log=print)


def test_succeeds_silently_when_already_up_to_date(tmp_path, monkeypatch):
    """A clone with nothing new on the remote -- the normal case for
    every evening run except the day the morning job has pushed
    something new -- must not raise."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "-q", "--bare")

    seed = tmp_path / "seed"
    _init_repo_with_commit(seed)
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-q", "-u", "origin", "HEAD:main")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(remote), str(clone))
    _git(clone, "checkout", "-q", "main")
    _git(clone, "branch", "-q", "--set-upstream-to=origin/main", "main")

    monkeypatch.setattr(git_sync, "ROOT", clone)
    pull_before_appending(log=print)  # must not raise


def test_fast_forwards_cleanly_when_remote_has_a_new_commit(tmp_path, monkeypatch):
    """The actual scenario this exists for: another clone (standing in
    for a GitHub Actions run) pushed a new commit to origin; pulling
    must fast-forward cleanly rather than requiring a merge."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "-q", "--bare")

    seed = tmp_path / "seed"
    _init_repo_with_commit(seed)
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-q", "-u", "origin", "HEAD:main")

    laptop = tmp_path / "laptop"
    _git(tmp_path, "clone", "-q", str(remote), str(laptop))
    _git(laptop, "checkout", "-q", "main")
    _git(laptop, "branch", "-q", "--set-upstream-to=origin/main", "main")

    # Simulate the morning job (a different clone) pushing a new commit
    # to origin before the laptop's evening run. Checked out onto "main"
    # explicitly -- a fresh clone's default checkout name depends on
    # this machine's init.defaultBranch, not necessarily "main".
    morning_runner = tmp_path / "morning_runner"
    _git(tmp_path, "clone", "-q", str(remote), str(morning_runner))
    _git(morning_runner, "checkout", "-q", "main")
    (morning_runner / "events.jsonl").write_text('{"kind": "setup"}\n', encoding="utf-8")
    _git(morning_runner, "add", "events.jsonl")
    _git(morning_runner, "config", "user.email", "test@example.com")
    _git(morning_runner, "config", "user.name", "Test")
    _git(morning_runner, "commit", "-q", "-m", "morning job commit")
    _git(morning_runner, "push", "-q")

    monkeypatch.setattr(git_sync, "ROOT", laptop)
    pull_before_appending(log=print)  # must not raise

    assert (laptop / "events.jsonl").exists()


def test_merges_cleanly_when_laptop_and_origin_have_both_diverged(tmp_path, monkeypatch):
    """THE LITERAL HISTORICAL FAILURE (BUGS.md, OPERATIONS.md's "Evening
    job dead-man's switch" section): the laptop has a local commit origin
    doesn't have, AND origin has a commit the laptop doesn't have --
    genuine two-way divergence, the normal state for two independent
    writers to the same file. Under the old `--ff-only` this raised
    GitPullError every time (2026-11-06 through 2026-11-13, 7 straight
    trading days). Under `--no-rebase` plus `.gitattributes`'s
    `merge=union` driver on events.jsonl, this must merge cleanly with
    both sides' events present."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "-q", "--bare")

    seed = tmp_path / "seed"
    _init_repo_with_commit(seed)
    (seed / ".gitattributes").write_text("events.jsonl merge=union\n", encoding="utf-8")
    (seed / "events.jsonl").write_text('{"event_id": "e1", "kind": "watchlist_run"}\n', encoding="utf-8")
    _git(seed, "add", ".")
    _git(seed, "commit", "-q", "-m", "add events.jsonl + union attribute")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-q", "-u", "origin", "HEAD:main")

    laptop = tmp_path / "laptop"
    _git(tmp_path, "clone", "-q", str(remote), str(laptop))
    _git(laptop, "checkout", "-q", "main")
    _git(laptop, "branch", "-q", "--set-upstream-to=origin/main", "main")
    _git(laptop, "config", "user.email", "test@example.com")
    _git(laptop, "config", "user.name", "Test")

    morning_runner = tmp_path / "morning_runner"
    _git(tmp_path, "clone", "-q", str(remote), str(morning_runner))
    _git(morning_runner, "checkout", "-q", "main")
    _git(morning_runner, "config", "user.email", "test@example.com")
    _git(morning_runner, "config", "user.name", "Test")
    with open(morning_runner / "events.jsonl", "a", encoding="utf-8") as f:
        f.write('{"event_id": "e2-morning", "kind": "setup"}\n')
    _git(morning_runner, "add", "events.jsonl")
    _git(morning_runner, "commit", "-q", "-m", "morning job commit")
    _git(morning_runner, "push", "-q")

    # The laptop commits its own new event BEFORE pulling -- e.g. a
    # previous evening run's commit that was made but never pushed (a
    # failed push, swallowed by sync_events_log_to_git's own best-effort
    # discipline). This is what makes it a genuine two-way divergence,
    # not just "laptop is behind."
    with open(laptop / "events.jsonl", "a", encoding="utf-8") as f:
        f.write('{"event_id": "e3-evening", "kind": "watchlist_run"}\n')
    _git(laptop, "add", "events.jsonl")
    _git(laptop, "commit", "-q", "-m", "laptop's own unpushed commit")

    monkeypatch.setattr(git_sync, "ROOT", laptop)
    pull_before_appending(log=print)  # must NOT raise GitPullError

    content = (laptop / "events.jsonl").read_text(encoding="utf-8")
    assert "e1" in content and "e2-morning" in content and "e3-evening" in content
