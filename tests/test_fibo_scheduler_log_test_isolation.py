"""src/fibo_live/scheduler_support.py's make_logger() must never write to
the real data/fibo_live/scheduler.log when running under pytest.

This is a regression test for a real incident: `tests/
test_fibo_morning_idempotency.py` (fake SYM1..SYM16 fixtures) only ever
monkeypatched `append_event`/`read_events`, never `fibo_morning.log` --
so every `log()` call inside `phase1_setups`/`watch_for_triggers` wrote
straight into the REAL scheduler.log, because `log = make_logger()` at
`fibo_morning.py`'s own module level bound the real path at import time.
This polluted the production log with test fixture noise and a
simulated-failure line, which briefly cost audit time during the
2026-11-15 health check that found it.

The first fix attempt (keying off `PYTEST_CURRENT_TEST`) was PROVEN WRONG
live before being replaced: that env var is only set once pytest starts
RUNNING a test, which is after every test module -- including the one
whose import binds `log = make_logger()` -- is already imported during
collection. This test asserts against the real mechanism
(`"pytest" in sys.modules`), not just the intent.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live import scheduler_support  # noqa: E402


def test_default_log_path_under_pytest_is_never_the_real_scheduler_log():
    # This test itself runs under pytest, so "pytest" in sys.modules is
    # unconditionally true here -- exactly the condition make_logger()
    # checks. No monkeypatching needed to prove the real, current behavior.
    assert "pytest" in sys.modules
    logger = scheduler_support.make_logger()  # the exact call fibo_morning.py/fibo_evening.py make
    logger("a line that must never reach the real production log")

    assert scheduler_support.TEST_SCHEDULER_LOG.exists()
    content = scheduler_support.TEST_SCHEDULER_LOG.read_text(encoding="utf-8")
    assert "a line that must never reach the real production log" in content

    # The real log is untouched by this call -- don't assert it's absent
    # (it legitimately exists from real production runs), just that this
    # test's own line never landed there.
    if scheduler_support.SCHEDULER_LOG.exists():
        real_content = scheduler_support.SCHEDULER_LOG.read_text(encoding="utf-8")
        assert "a line that must never reach the real production log" not in real_content


def test_explicit_log_path_is_never_overridden(tmp_path):
    """A test that already does the right thing (passes its own tmp_path)
    must be completely unaffected by the pytest-detection default."""
    custom_path = tmp_path / "custom.log"
    logger = scheduler_support.make_logger(log_path=custom_path)
    logger("explicit path line, unique marker XYZZY-42")
    assert "XYZZY-42" in custom_path.read_text(encoding="utf-8")
