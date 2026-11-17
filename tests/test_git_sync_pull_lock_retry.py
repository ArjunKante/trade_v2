"""src/fibo_live/git_sync.py's pull_before_appending index.lock retry --
mirrors tests/test_fibo_evening_duckdb_lock_retry.py exactly, same shape
of fix (BUGS.md Bug #31, 2026-11-18): the evening job now runs at 20:00
IST, inside the window active development work happens in this same
repo, and a concurrent git commit/add can hold .git/index.lock for the
brief moment this job's own git pull tries to run.

time.sleep is monkeypatched in every test that exercises a retry, so
this suite runs in well under a second despite exercising exponential
backoff logic. _run_git itself is monkeypatched (not real git
subprocesses, unlike test_git_sync_pull.py) since the point here is the
retry/backoff/exit-code logic, not git's own pull semantics.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live import git_sync  # noqa: E402
from fibo_live.git_sync import GitPullError, pull_before_appending  # noqa: E402

LOCK_STDERR = "fatal: Unable to create '/repo/.git/index.lock': File exists."


def _result(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["git", "pull"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_succeeds_immediately_when_not_locked(monkeypatch):
    calls = []
    monkeypatch.setattr(git_sync, "_run_git", lambda *a: calls.append(a) or _result(0, stdout="Already up to date."))
    pull_before_appending(log=print)
    assert len(calls) == 1


def test_succeeds_after_transient_lock_clears_before_exhaustion(monkeypatch):
    attempts = {"n": 0}

    def flaky(*a):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return _result(128, stderr=LOCK_STDERR)
        return _result(0, stdout="Already up to date.")

    monkeypatch.setattr(git_sync, "_run_git", flaky)
    sleeps = []
    monkeypatch.setattr(git_sync.time, "sleep", lambda s: sleeps.append(s))

    logged = []
    pull_before_appending(log=logged.append)  # must not raise

    assert attempts["n"] == 3
    assert sleeps == [3, 6]  # exponential backoff: 3s then 6s between the two failed attempts
    assert any("attempt 1/5" in m for m in logged)
    assert any("attempt 2/5" in m for m in logged)


def test_exits_nonzero_after_exhausting_all_attempts_against_persistent_lock(monkeypatch):
    monkeypatch.setattr(git_sync, "_run_git", lambda *a: _result(128, stderr=LOCK_STDERR))
    sleeps = []
    monkeypatch.setattr(git_sync.time, "sleep", lambda s: sleeps.append(s))

    logged = []
    with pytest.raises(SystemExit) as exc_info:
        pull_before_appending(log=logged.append)

    assert exc_info.value.code == 1
    # 5 attempts total -> 4 sleeps (no sleep after the final, exhausted attempt).
    assert sleeps == [3, 6, 12, 24]
    assert any("FATAL" in m for m in logged)
    assert any("20:00 IST" in m for m in logged)  # names the actual recurring cause, not just "something"


def test_non_lock_failure_is_not_retried_and_raises_gitpullerror_immediately(monkeypatch):
    """A genuine conflict or missing remote will not resolve itself by
    waiting -- same philosophy as before this fix: raise immediately,
    don't burn 4 sleeps on a failure retrying cannot cure."""
    calls = []
    monkeypatch.setattr(git_sync, "_run_git",
                         lambda *a: calls.append(a) or _result(1, stderr="fatal: No configured push destination."))
    sleeps = []
    monkeypatch.setattr(git_sync.time, "sleep", lambda s: sleeps.append(s))

    with pytest.raises(GitPullError):
        pull_before_appending(log=print)

    assert len(calls) == 1  # no retries attempted
    assert sleeps == []


def test_sys_exit_is_not_a_plain_exception_run_unattended_would_swallow():
    """The whole point of sys.exit(1) here rather than raising
    GitPullError on lock exhaustion: it must survive run_unattended's
    `except Exception` and actually terminate the process non-zero."""
    from fibo_live.scheduler_support import run_unattended

    def main_that_locks_out():
        raise SystemExit(1)

    with pytest.raises(SystemExit) as exc_info:
        run_unattended("FIBO EVENING JOB", main_that_locks_out, log=print)
    assert exc_info.value.code == 1
