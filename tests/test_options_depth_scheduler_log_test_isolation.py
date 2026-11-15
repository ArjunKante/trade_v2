"""src/options_depth/scheduler_support.py's make_logger() -- same test
isolation fix as src/fibo_live/scheduler_support.py (duplicated, not
imported, per this package's own decoupling convention), same proof.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from options_depth import scheduler_support  # noqa: E402


def test_default_log_path_under_pytest_is_never_the_real_scheduler_log():
    assert "pytest" in sys.modules
    logger = scheduler_support.make_logger()
    logger("a line that must never reach the real production log")

    assert scheduler_support.TEST_SCHEDULER_LOG.exists()
    content = scheduler_support.TEST_SCHEDULER_LOG.read_text(encoding="utf-8")
    assert "a line that must never reach the real production log" in content

    if scheduler_support.SCHEDULER_LOG.exists():
        real_content = scheduler_support.SCHEDULER_LOG.read_text(encoding="utf-8")
        assert "a line that must never reach the real production log" not in real_content


def test_explicit_log_path_is_never_overridden(tmp_path):
    custom_path = tmp_path / "custom.log"
    logger = scheduler_support.make_logger(log_path=custom_path)
    logger("explicit path line, unique marker XYZZY-43")
    assert "XYZZY-43" in custom_path.read_text(encoding="utf-8")
