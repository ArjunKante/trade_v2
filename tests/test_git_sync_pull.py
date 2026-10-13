"""src/fibo_live/git_sync.py's pull_before_appending: the FIRST thing
fibo_evening.py's main() does, before any append_event call, once the
Fibo morning job moves to GitHub Actions and may have pushed commits the
laptop hasn't seen yet. Unlike the module's push (best-effort, every
failure swallowed), this must RAISE on failure -- proceeding against a
possibly-stale local events.jsonl is exactly what it exists to prevent.

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
