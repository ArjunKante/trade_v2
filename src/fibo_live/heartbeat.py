"""Dead-man's-switch heartbeat for the EVENING job (healthchecks.io), the
laptop-side counterpart to fibo_morning.yml's own heartbeat step.

WHY THIS EXISTS, AND WHY IT IS SHAPED DIFFERENTLY FROM THE MORNING ONE:
PROJECT_CONTEXT.md Section 7 finding #4 ("fixed where noticed, not
everywhere the pattern recurs") -- the morning job got a heartbeat after
its own late-firing failure mode was found (OPERATIONS.md's "External
pinger" sections), but the identical defect SHAPE -- a scheduled job
whose only failure signal was a local log or a caught exception -- was
never checked for one layer up, on the evening job, until the 2026-11-15
health check found it. Three of ten failure-days in that check had ZERO
scheduler.log entries at all: Windows Task Scheduler never launched
python.exe. No exception handler, log line, or email-on-error inside
fibo_evening.py could ever see that, because the process never started.
Only an external service independently noticing an EXPECTED ping did not
arrive can catch it -- the same "can't block the job is not the same as
the failure is visible" lesson, recurring in a place the original fix
never reached. Escalated to OPERATIONS.md too, not left only here, per
finding #15 ("a flag recorded in a per-study document is not a
correction" -- it needs an escalation path or it dies where it was
written).

SHAPE DIFFERENCE FROM THE MORNING HEARTBEAT, DELIBERATE: fibo_morning.yml
pings FIRST, before anything else, purely to answer "did a run happen at
all" -- it is expected to fire 4x/trading day regardless of outcome. This
job runs once/weekday evening and is expected to SUCCEED every time; its
ping fires LAST, only after a fully successful run (the normal
watchlist-computed path, or the recognized idempotent-skip path), from
INSIDE main() -- never from the run_unattended wrapper, and never at the
start. A git-sync failure, a DuckDB lock, a stale-data refusal, or any
unhandled exception all mean main() never reaches the ping call, so the
check goes overdue and healthchecks.io alerts -- exactly the cases this
was built to catch, on top of whatever this run's own exception handling
already logged.

FAIL-SOFT, same rule as notify.send_email: a broken network or an empty
secret must never fail or even slow down the job this exists to monitor.
Catches every exception itself, never raises, and never logs the ping
URL (it's a bearer-token-shaped secret -- anyone with it can mark the
check up) -- only whether the env var was present and whether the HTTP
call succeeded."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
PING_TIMEOUT_S = 10


def ping_evening_heartbeat(log: Callable[[str], None] = print) -> bool:
    """Best-effort GET to FIBO_EVENING_HEALTHCHECK_URL. Returns True only
    on a confirmed 2xx; False on a missing env var or any request
    failure. Never raises."""
    load_dotenv(ENV_PATH, override=False)
    url = os.environ.get("FIBO_EVENING_HEALTHCHECK_URL")
    if not url:
        log("HEARTBEAT NOT SENT: FIBO_EVENING_HEALTHCHECK_URL is empty or not set in .env.")
        return False
    try:
        resp = requests.get(url, timeout=PING_TIMEOUT_S)
        resp.raise_for_status()
        log("Heartbeat ping sent (evening job success).")
        return True
    except Exception as e:
        # Exception TYPE only, never str(e) or the URL -- see module docstring.
        log(f"HEARTBEAT NOT SENT: {type(e).__name__} pinging healthchecks.io.")
        return False
