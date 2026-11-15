"""Dead-man's-switch heartbeat for the options-depth collector
(`scripts/snapshot_options_depth.py`), same shape as `src/fibo_live/
heartbeat.py` -- DUPLICATED, not imported, per this package's own
`__init__.py` ("Separate from Fibo... nothing in those packages is
imported or modified here") and `scheduler_support.py`'s own precedent
("same shape as the Fibo jobs' own scheduler_support.py, duplicated to
stay decoupled"). Same fix, same tests, two independent copies on
purpose -- not a cross-package import.

WHY THIS EXISTS: `OPERATIONS.md`'s "Evening job dead-man's switch"
section (2026-11-15) flagged this collector as having no independent
heartbeat either -- its only failure signal was `fibo_evening.py`'s own
`snapshot_health` log line, a check FROM a different job, not a check ON
this one's own launch. Fixed here in the same pass per `PROJECT_CONTEXT.md`
Section 7 findings #4 ("fixed where noticed, not everywhere the pattern
recurs") and #9 ("blast radius must be measured in both directions") --
not left recorded as a future candidate, which would just repeat finding
#15's mistake (a flag that never gets carried out of the document it was
written in).

SHAPE: this collector runs 3x/trading day on a fixed schedule
(10:30/12:30/14:30 IST) via three separate Windows Task Scheduler
triggers of the same script. `check_market_hours()` correctly refusing to
run (weekend, holiday, outside session) is NOT a failure -- Task
Scheduler's own triggers fire on every weekday regardless of NSE's
holiday calendar, so treating that refusal as a failure would alert on
every single market holiday (the exact "crying wolf" mistake the evening
job's 18:30->20:00 move was made to avoid, OPERATIONS.md). The ping
therefore fires on BOTH outcomes that represent correct, intended
behavior: a successful snapshot (rows recorded) and a correctly-recognized
non-trading window -- never on a login failure, a spot-fetch failure, a
stale-session detection, zero resolved contracts, or zero rows fetched
across every chunk, all of which are genuine problems that must surface.

FAIL-SOFT, same rule as fibo_live.heartbeat and notify.send_email: never
raises, never logs the ping URL itself (bearer-token-shaped secret)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
PING_TIMEOUT_S = 10


def ping_options_depth_heartbeat(log: Callable[[str], None] = print) -> bool:
    """Best-effort GET to OPTIONS_DEPTH_HEALTHCHECK_URL. Returns True only
    on a confirmed 2xx; False on a missing env var or any request
    failure. Never raises."""
    load_dotenv(ENV_PATH, override=False)
    url = os.environ.get("OPTIONS_DEPTH_HEALTHCHECK_URL")
    if not url:
        log("HEARTBEAT NOT SENT: OPTIONS_DEPTH_HEALTHCHECK_URL is empty or not set in .env.")
        return False
    try:
        resp = requests.get(url, timeout=PING_TIMEOUT_S)
        resp.raise_for_status()
        log("Heartbeat ping sent (options-depth run OK).")
        return True
    except Exception as e:
        # Exception TYPE only, never str(e) or the URL -- see module docstring.
        log(f"HEARTBEAT NOT SENT: {type(e).__name__} pinging healthchecks.io.")
        return False
