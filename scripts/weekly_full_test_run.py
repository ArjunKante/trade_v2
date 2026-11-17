"""Weekly scheduled run of the FULL pytest suite against this laptop's
real local data (Windows Task Scheduler, weekly, see OPERATIONS.md's
"Weekly full-suite run against real data" section) -- the thing
.github/workflows/test_suite.yml structurally cannot do, since a
GitHub-hosted runner never has data/warehouse.duckdb,
data/fibo_intraday.duckdb, or the real multi-year NSE holiday calendar
(~45 tests skip there for exactly that reason). This is the one place
all ~693 tests actually run against real data on a schedule, not just
when a human happens to run `pytest` by hand.

HEARTBEAT DISCIPLINE, deliberately asymmetric, same shape as
fibo_live/heartbeat.py's evening-job ping: pings healthchecks.io ONLY
when pytest's own exit code is 0 (every test either passed or was
cleanly skipped -- never on a failure, never on an error). A failing
run, or this task never running at all (Task Scheduler itself not
firing, the laptop being off, python.exe missing), both end up as the
SAME signal from healthchecks.io's side: the expected ping didn't
arrive, and its own "Period"/grace-window alert fires. This script never
sends its own email -- the dead-man's-switch pattern already proven for
the evening job (FAIL SOFT: a broken network or empty secret must never
raise, see heartbeat.py's docstring) is the only notification layer
here, deliberately not duplicated.

NEVER pings on a nonzero exit code -- that is the whole point. Never
logs the ping URL itself (a bearer-token-shaped secret) -- only whether
the env var was present and whether the HTTP call succeeded, matching
heartbeat.py's own rule.
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
LOG_PATH = ROOT / "data" / "weekly_test_run.log"
PING_TIMEOUT_S = 10


def log(msg: str) -> None:
    text = str(msg)
    print(text, flush=True)
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for line in text.splitlines() or [""]:
            f.write(f"[{ts}] {line}\n")
        f.flush()


def ping_weekly_test_heartbeat() -> bool:
    """Same fail-soft contract as heartbeat.ping_evening_heartbeat:
    returns True only on a confirmed 2xx; never raises."""
    load_dotenv(ENV_PATH, override=False)
    url = os.environ.get("WEEKLY_TEST_SUITE_HEALTHCHECK_URL")
    if not url:
        log("HEARTBEAT NOT SENT: WEEKLY_TEST_SUITE_HEALTHCHECK_URL is empty or not set in .env.")
        return False
    try:
        resp = requests.get(url, timeout=PING_TIMEOUT_S)
        resp.raise_for_status()
        log("Heartbeat ping sent (weekly full test suite passed/skipped cleanly).")
        return True
    except Exception as e:
        log(f"HEARTBEAT NOT SENT: {type(e).__name__} pinging healthchecks.io.")
        return False


def main() -> int:
    log("=== WEEKLY FULL TEST SUITE RUN ===")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT, capture_output=True, text=True,
    )
    log(result.stdout)
    if result.stderr:
        log("--- stderr ---")
        log(result.stderr)
    log(f"pytest exit code: {result.returncode}")

    if result.returncode == 0:
        ping_weekly_test_heartbeat()
    else:
        log("NOT pinging heartbeat -- pytest exited nonzero (a real failure or "
            "collection error, not a clean pass/skip). The missed ping is the "
            "signal; healthchecks.io's own overdue alert will fire.")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
