"""Shared unattended-run support for the options-depth collector --
same shape as `src/fibo_live/scheduler_support.py` (log-to-file +
never-crash-the-schedule wrapper), duplicated rather than imported to
keep this package decoupled from Fibo (see `src/options_depth/
__init__.py`). Task Scheduler runs this with no terminal attached, on
battery, without waking the machine -- the same operational posture the
Fibo evening/morning jobs already run under, for the same reasons:

WHY A FILE LOG: anything only print()'d vanishes the instant a
Task-Scheduler-launched process exits with no terminal attached. Every
log() call here also appends a timestamped, flushed line to
data/options_depth/scheduler.log, so a human can check afterwards that a
run actually happened and what it did.

WHY run_unattended: a scheduled task has no one watching to re-run it by
hand after a crash, and a missed snapshot here is explicitly ACCEPTABLE
(per instruction: this task must not wake the machine, so a laptop that
is asleep at 12:30 simply skips that snapshot -- that is normal, not a
failure to recover from). What must never happen is an unhandled
exception -- a holiday, a dead network, Angel down, anything -- making
Task Scheduler record this run as failed and, worse, propagating past
this process in a way that could affect anything else scheduled nearby.
Caught, logged with its full traceback, swallowed -- the process always
exits 0.
"""
from __future__ import annotations

import datetime as dt
import traceback
from pathlib import Path

SCHEDULER_LOG = Path(__file__).resolve().parents[2] / "data" / "options_depth" / "scheduler.log"


def make_logger(log_path: Path = SCHEDULER_LOG):
    """Returns a log(msg) that prints to stdout (so an interactive run
    still shows output) AND appends every line of msg to log_path, each
    stamped with its own timestamp and flushed immediately -- never
    buffered, since a killed/crashed process must not lose lines it
    already "logged"."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: object = "") -> None:
        text = str(msg)
        print(text, flush=True)
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            for line in text.splitlines() or [""]:
                f.write(f"[{ts}] {line}\n")
            f.flush()

    return log


def run_unattended(job_name: str, main_fn, log) -> None:
    """Calls main_fn() with no arguments. ALWAYS returns normally (so the
    process exits 0) even if main_fn raises -- the exception is logged
    with its full traceback via `log` first. Never retries: one failed
    scheduled run just waits for the next trigger, it does not loop
    here."""
    try:
        main_fn()
    except Exception:
        log(f"=== {job_name}: UNHANDLED EXCEPTION -- run aborted but not re-raised "
            f"(a crashed run must never block the next scheduled one) ===")
        log(traceback.format_exc())
