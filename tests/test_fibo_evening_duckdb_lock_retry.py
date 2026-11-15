"""scripts/fibo_evening.py's _open_warehouse_with_retry -- bounded retry
with backoff around opening warehouse.duckdb, added after a DuckDB
file-lock conflict (another process already had the file open) cost 2
forward-test days (2026-10-27, 2026-11-03, BUGS.md/OPERATIONS.md).

Confirmed live (not assumed) before writing this: duckdb.connect()
raises duckdb.IOException IMMEDIATELY when another process already holds
the file open on Windows -- it does not block-and-wait on its own -- so a
bounded sleep-and-retry genuinely helps for a transient hold.

time.sleep is monkeypatched in every test that exercises a retry, so this
suite runs in well under a second despite exercising exponential backoff
logic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fibo_evening  # noqa: E402


def test_succeeds_immediately_when_the_file_is_not_locked(monkeypatch):
    sentinel = object()
    calls = []
    monkeypatch.setattr(fibo_evening, "get_connection", lambda path: (calls.append(path) or sentinel))

    result = fibo_evening._open_warehouse_with_retry("warehouse.duckdb", log=print)

    assert result is sentinel
    assert calls == ["warehouse.duckdb"]


def test_succeeds_after_transient_locks_clear_before_exhaustion(monkeypatch):
    sentinel = object()
    attempts = {"n": 0}

    def flaky_get_connection(path):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise duckdb.IOException("simulated: file in use")
        return sentinel

    monkeypatch.setattr(fibo_evening, "get_connection", flaky_get_connection)
    sleeps = []
    monkeypatch.setattr(fibo_evening.time, "sleep", lambda s: sleeps.append(s))

    logged = []
    result = fibo_evening._open_warehouse_with_retry("warehouse.duckdb", log=logged.append)

    assert result is sentinel
    assert attempts["n"] == 3
    # Exponential backoff: 3s then 6s between the first two failed attempts.
    assert sleeps == [3, 6]
    assert any("attempt 1/5" in m for m in logged)
    assert any("attempt 2/5" in m for m in logged)


def test_exits_nonzero_after_exhausting_all_attempts(monkeypatch):
    def always_locked(path):
        raise duckdb.IOException("simulated: file in use")

    monkeypatch.setattr(fibo_evening, "get_connection", always_locked)
    sleeps = []
    monkeypatch.setattr(fibo_evening.time, "sleep", lambda s: sleeps.append(s))

    logged = []
    with pytest.raises(SystemExit) as exc_info:
        fibo_evening._open_warehouse_with_retry("warehouse.duckdb", log=logged.append)

    assert exc_info.value.code == 1
    # 5 attempts total -> 4 sleeps (no sleep after the final, exhausted attempt).
    assert sleeps == [3, 6, 12, 24]
    assert any("FATAL" in m for m in logged)
    assert any("research_app.py" in m for m in logged)  # names the prime suspect, not just "something"


def test_sys_exit_is_not_a_plain_exception_run_unattended_would_swallow():
    """The whole point of using sys.exit(1) here rather than letting the
    final duckdb.IOException propagate as an ordinary exception: it must
    survive run_unattended's `except Exception` and actually terminate
    the process non-zero."""
    from fibo_live.scheduler_support import run_unattended

    def main_that_locks_out():
        raise SystemExit(1)

    with pytest.raises(SystemExit) as exc_info:
        run_unattended("FIBO EVENING JOB", main_that_locks_out, log=print)
    assert exc_info.value.code == 1
