"""Integration proof that the dead-man's-switch ping is wired where it
must be: reachable ONLY after a fully successful run, never when the job
fails the way it actually failed live (git divergence, 2026-11-06 through
2026-11-13 -- OPERATIONS.md's "Evening job dead-man's switch" section).

This does not re-test ping_evening_heartbeat's own behavior (see
test_fibo_evening_heartbeat.py) -- it tests PLACEMENT: that
scripts/fibo_evening.py's main(), run exactly the way Task Scheduler runs
it (through run_unattended, so the exception is caught and swallowed the
same way it was live), never reaches the ping call when an earlier step
raises. requests.get is monkeypatched to RAISE if called at all, so this
fails loudly rather than silently passing if the wiring ever regresses.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fibo_evening  # noqa: E402
import fibo_live.heartbeat as heartbeat  # noqa: E402
from fibo_live.scheduler_support import run_unattended  # noqa: E402


def _get_must_not_be_called(*a, **k):
    raise AssertionError(
        "requests.get was called -- the heartbeat ping fired despite main() "
        "raising before reaching it. The ping must only be reachable after "
        "a fully successful run."
    )


def test_git_sync_failure_never_reaches_the_heartbeat(monkeypatch):
    """Reproduces the actual live failure shape (GitPullError from
    pull_before_appending, the first line of main()) and proves the
    heartbeat is never pinged when it happens."""
    monkeypatch.setenv("FIBO_EVENING_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")
    monkeypatch.setattr(heartbeat, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(heartbeat.requests, "get", _get_must_not_be_called)
    monkeypatch.setattr(sys, "argv", ["fibo_evening.py", "--date", "2026-11-06"])

    class FakeGitPullError(Exception):
        pass

    def raise_git_pull_error(log):
        raise FakeGitPullError("git pull --ff-only failed (128): simulated diverging branches")

    monkeypatch.setattr(fibo_evening, "pull_before_appending", raise_git_pull_error)

    logged = []
    # run_unattended is the REAL wrapper Task Scheduler invokes main()
    # through -- it must swallow the exception (exit 0) without the
    # heartbeat ever firing.
    run_unattended("FIBO EVENING JOB", fibo_evening.main, logged.append)

    assert any("UNHANDLED EXCEPTION" in m for m in logged)
    assert any("FakeGitPullError" in m or "simulated diverging branches" in m for m in logged)


def test_duckdb_lock_failure_never_reaches_the_heartbeat(monkeypatch):
    """Same proof, for the other failure shape actually observed live
    (warehouse.duckdb locked by another process, 2026-10-27/2026-11-03)."""
    monkeypatch.setenv("FIBO_EVENING_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")
    monkeypatch.setattr(heartbeat, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(heartbeat.requests, "get", _get_must_not_be_called)
    monkeypatch.setattr(sys, "argv", ["fibo_evening.py", "--date", "2026-11-06"])

    monkeypatch.setattr(fibo_evening, "pull_before_appending", lambda log: None)

    def raise_lock_error(path):
        raise OSError('IO Error: Cannot open file "warehouse.duckdb": '
                      "The process cannot access the file because it is being used by another process.")

    monkeypatch.setattr(fibo_evening, "get_connection", raise_lock_error)

    logged = []
    run_unattended("FIBO EVENING JOB", fibo_evening.main, logged.append)

    assert any("UNHANDLED EXCEPTION" in m for m in logged)
