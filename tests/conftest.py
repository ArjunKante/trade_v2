"""Session-wide guards against a test ever touching real production data.

PROMPTED BY A REAL INCIDENT (2026-11-13/14, BUGS.md Bug #24): a draft
test for fibo_morning.py's holiday-calendar-missing refusal appended a
fabricated session_status event to the REAL data/fibo_live/v1/events.jsonl
-- caught only because this project habitually diffs that file against
git after every test run, not because anything structural stopped it.
The root cause was `assert_watchlist_current`'s own `log_path: Path =
EVENTS_LOG` default, bound ONCE at import time to the real path, which a
test's `functools.partial(read_events, log_path=events_path)` patch
could not override (an explicit call-site keyword always wins over a
partial's preset keyword). That stale-default shape existed in 7
functions across eventlog.py/fibo_morning.py/outcomes.py/
session_status.py -- all fixed the same day to resolve
`fibo_live.config.EVENTS_LOG` FRESH, at call time, instead (see
eventlog.append_event's docstring).

That fix alone still relies on every future function doing the fresh
lookup correctly -- a convention, not a guarantee. This file adds two
independent, deliberately overlapping layers so a mistake in either one
alone still cannot reach the real file:

  1. `_redirect_events_log` (below): gives EVERY test, automatically, a
     working substitute events.jsonl under that test's own tmp_path, by
     patching the one canonical source (`fibo_live.config.EVENTS_LOG`)
     that every fixed function now reads fresh. Normal tests that
     exercise real append_event/read_events code paths keep passing --
     they just write somewhere harmless.

  2. `_protect_production_files` (below): makes the REAL files
     read-only at the OS level for the whole pytest session, restored
     after. This does not depend on layer 1, on any monkeypatching, or
     on any function being written correctly -- confirmed empirically
     (2026-11-15) that a chmod-read-only file makes both a plain
     `open(path, "a")` and a write-mode `duckdb.connect(path)` raise
     (PermissionError / duckdb.IOException respectively) on this
     project's Windows dev machine, while a read_only=True duckdb
     connection is unaffected. A test that skips layer 1 entirely, or
     touches a real path this project hasn't thought to redirect yet,
     gets a loud OS-level failure instead of a silent write.

NOT covered by layer 2, and why: `data/raw/prices` and `data/raw/index`
(fibo_live.config.RAW_PRICES_DIR / RAW_INDEX_DIR) are DIRECTORIES new
files get created inside, not files opened in place -- chmod's read-only
attribute on a directory is not reliably enforced by Windows/NTFS the
way it is on a file (confirmed empirically the same day: a chmod'd
read-only directory did not block file creation inside it). Making that
directory level genuinely tamper-proof needs an ACL change (icacls), not
attempted here since the only two tests that reach that code path
(test_holiday_week_oct2026.py, test_fibo_evening_staleness_ordering.py)
already monkeypatch `fibo_evening.RAW_PRICES_DIR` to a tmp_path
explicitly -- a real but narrower, vigilance-based protection, flagged
as a residual gap in BUGS.md Bug #24 rather than silently assumed fixed.

options_depth/scheduler.log is NOT included here on purpose: that
package already has its own identical "pytest in sys.modules" lazy
resolution (src/options_depth/scheduler_support.py), and is deliberately
decoupled from fibo_live (see that package's own __init__.py) -- this
file should not import it, nor should fibo_live import this one.
"""
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import fibo_live.config as fibo_config  # noqa: E402

_REAL_EVENTS_LOG = fibo_config.ROOT / "data" / "fibo_live" / "v1" / "events.jsonl"
_events_log_hash_at_session_start: str | None = None


def _hash_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pytest_sessionstart(session):
    """Hashes the REAL events.jsonl before any test (not test file order
    dependent, not a fixture, not something a test can skip by running
    early) -- the baseline pytest_sessionfinish, below, compares against.
    See tests/test_events_log_integrity.py for the same project's
    content-shape checks (duplicate ids, monotonic ts, valid JSON),
    which run as ordinary named tests instead, since those don't need
    session-start/session-end framing to be meaningful."""
    global _events_log_hash_at_session_start
    _events_log_hash_at_session_start = _hash_file(_REAL_EVENTS_LOG)


def pytest_sessionfinish(session, exitstatus):
    """The authoritative, order-independent half of the events.jsonl
    integrity check (BUGS.md Bug #24): compares this file's hash now
    against the hash taken in pytest_sessionstart, above, regardless of
    which test file ran when, or whether anything else in this session
    already asserted the file was clean. A test suite that corrupts this
    file must fail LOUDLY -- forcing session.exitstatus nonzero here
    does that even though this hook runs after pytest's own reporting,
    so look for this line directly in the output, not just the pass/fail
    counts above it."""
    current_hash = _hash_file(_REAL_EVENTS_LOG)
    if _events_log_hash_at_session_start is not None and current_hash != _events_log_hash_at_session_start:
        print(
            "\n\n!!! INTEGRITY FAILURE: data/fibo_live/v1/events.jsonl changed "
            "during this pytest session (hash differs from session start) !!!\n"
            "This file must never be written by a test, under any circumstance -- "
            "see conftest.py's module docstring and BUGS.md Bug #24. Run "
            "`git diff -- data/fibo_live/v1/events.jsonl` to inspect, then "
            "`git checkout -- data/fibo_live/v1/events.jsonl` to revert before doing "
            "anything else.\n",
            file=sys.stderr,
        )
        session.exitstatus = 1

# Real, on-disk production paths this project cannot afford to lose or
# corrupt. Only FILES belong here -- see the module docstring for why
# directories (RAW_PRICES_DIR, RAW_INDEX_DIR) are deliberately excluded.
_PRODUCTION_FILES = [
    fibo_config.EVENTS_LOG,                               # data/fibo_live/v1/events.jsonl
    fibo_config.LIVE_DIR.parent / "scheduler.log",         # data/fibo_live/scheduler.log
    fibo_config.WAREHOUSE_DB,                              # data/warehouse.duckdb
    fibo_config.INTRADAY_DB,                               # data/fibo_intraday.duckdb
]


@pytest.fixture(autouse=True)
def _redirect_events_log(tmp_path, monkeypatch):
    """Every test gets its own fresh, writable events.jsonl substitute.
    Patches the one canonical module attribute every fixed consumer
    (append_event, read_events, and everything in outcomes.py/
    session_status.py/fibo_morning.py that forwards to them) resolves
    FRESH at call time -- see eventlog.append_event's docstring. A test
    that needs the real path for a specific, deliberate reason (there is
    currently no such test) should request it explicitly rather than
    relying on this fixture not running."""
    fake_events_log = tmp_path / "events.jsonl"
    monkeypatch.setattr(fibo_config, "EVENTS_LOG", fake_events_log)
    yield fake_events_log


@pytest.fixture(scope="session", autouse=True)
def _protect_production_files():
    """OS-level backstop, independent of every other fixture in this
    file: makes each path in _PRODUCTION_FILES read-only for the
    duration of the whole pytest session, restoring its original mode
    afterward even if the session is interrupted. See module docstring
    for the empirical verification that this actually blocks both a
    plain file append and a write-mode DuckDB connection on this
    project's Windows dev machine, while leaving read_only=True
    connections (used throughout this test suite) unaffected."""
    existing = [p for p in _PRODUCTION_FILES if p.exists()]
    original_modes = {p: stat.S_IMODE(os.stat(p).st_mode) for p in existing}
    for p in existing:
        os.chmod(p, stat.S_IREAD)
    try:
        yield
    finally:
        for p, mode in original_modes.items():
            os.chmod(p, mode)
