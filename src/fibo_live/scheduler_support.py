"""Shared unattended-run support for the Fibo evening/morning scheduled
jobs (Windows Task Scheduler): a log() that writes to a shared file, not
just stdout, and a run_unattended() wrapper that guarantees a scheduled
run never crashes the schedule.

WHY A FILE LOG: Task Scheduler runs these with no terminal attached --
anything only print()'d vanishes the instant the process exits. Every
log() call here also appends a timestamped, flushed line to
data/fibo_live/scheduler.log, shared by both jobs, so a human (or this
assistant) can check afterwards that a run actually happened and what it
did, the same way the append-only events.jsonl is the evidence trail for
WHAT was decided (src/fibo_live/eventlog.py's docstring) -- this is the
evidence trail for WHETHER AND WHEN a run itself happened.

WHY run_unattended: a scheduled task has no one watching to re-run it by
hand after a crash. An unhandled exception here -- a dead network, Angel
returning something unexpected, anything -- must never propagate past
main(), because that would both (a) leave nothing in the log explaining
why (a bare traceback on stderr, which Task Scheduler does not surface
anywhere readable) and (b) needlessly worry anyone checking the process
exit code, even though a single bad run should never block the next
scheduled one. Caught, logged with its full traceback, and swallowed --
the process always exits 0.

TEST ISOLATION (added 2026-11-15, OPERATIONS.md): `make_logger()`'s
default path used to be bound to the real `SCHEDULER_LOG` at this
module's own import time, so any test that imported `fibo_morning`/
`fibo_evening` and exercised a code path calling the module-level `log`
without explicitly monkeypatching it over (most tests correctly do; a few
historical ones didn't) wrote straight into the real production log --
confirmed as the source of `data/fibo_live/scheduler.log`'s SYM1..SYM16
fixture noise and a simulated-failure line that briefly made a 2026-11-15
health check second-guess a real incident. Fixed by resolving the default
lazily, at CALL time, keyed on `"pytest" in sys.modules` -- NOT
`PYTEST_CURRENT_TEST` (tried first, and wrong: that env var is only set
once pytest starts RUNNING a test, which is after every test MODULE is
already imported during collection, i.e. after `log = make_logger()`'s
own module-level call site has already executed and bound the real path
-- confirmed live, the first version of this fix still leaked 29 lines
into the real log on its own test run). `"pytest" in sys.modules` is true
from the moment pytest itself starts up, before collection, so it is
already true at every module's import time too. An explicit `log_path`
argument (every test that already does the right thing) is untouched.
"""
from __future__ import annotations

import datetime as dt
import sys
import tempfile
import traceback
from pathlib import Path

from fibo_live.config import LIVE_DIR
from spread_monitor.market_hours import IST

SCHEDULER_LOG = LIVE_DIR.parent / "scheduler.log"  # data/fibo_live/scheduler.log
TEST_SCHEDULER_LOG = Path(tempfile.gettempdir()) / "fibo_test_scheduler.log"


def make_logger(log_path: Path | None = None):
    """Returns a log(msg) that prints to stdout (so an interactive run
    still shows output) AND appends every line of msg to log_path, each
    stamped with its own timestamp and flushed immediately -- never
    buffered, since a killed/crashed process must not lose lines it
    already "logged".

    `log_path=None` (the default, and what every module-level `log =
    make_logger()` call in this codebase uses) resolves to
    TEST_SCHEDULER_LOG under pytest, SCHEDULER_LOG otherwise -- see this
    module's docstring."""
    if log_path is None:
        log_path = TEST_SCHEDULER_LOG if "pytest" in sys.modules else SCHEDULER_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: object = "") -> None:
        text = str(msg)
        print(text, flush=True)
        # Explicit IST, not the host clock -- so scheduler.log reads
        # consistently whether a line came from the laptop or a GitHub
        # Actions runner.
        ts = dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            for line in text.splitlines() or [""]:
                f.write(f"[{ts}] {line}\n")
            f.flush()

    return log


def run_unattended(job_name: str, main_fn, log) -> None:
    """Calls main_fn() with no arguments. ALWAYS returns normally (so the
    process exits 0) even if main_fn raises -- the exception is logged
    with its full traceback via `log` first. Never retries: one failed
    scheduled run just waits for the next trigger, it does not loop here."""
    try:
        main_fn()
    except Exception:
        log(f"=== {job_name}: UNHANDLED EXCEPTION -- run aborted but not re-raised "
            f"(a crashed run must never block the next scheduled one) ===")
        log(traceback.format_exc())
