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
"""
from __future__ import annotations

import datetime as dt
import traceback
from pathlib import Path

from fibo_live.config import LIVE_DIR
from spread_monitor.market_hours import IST

SCHEDULER_LOG = LIVE_DIR.parent / "scheduler.log"  # data/fibo_live/scheduler.log


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
