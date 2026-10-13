"""ONE-OFF PROBE -- manually triggered only (see
.github/workflows/probe_github_actions.yml, workflow_dispatch, no
schedule). Answers four factual questions about running the Fibo morning
job on a GitHub Actions runner, before any schedule is built:

  1. Does Angel One accept a login from this runner's IP? (status only --
     "OK" or a short redacted error code, never the raw response)
  2. Does the code's own IST computation (src/spread_monitor/market_hours.
     IST) give the correct current IST time on a runner whose OS clock is
     UTC? (prints the computed IST wall-clock time -- not a secret)
  3. Does a test email actually send from this runner? (boolean only)
  4. How long does the Angel scrip-master download take on this runner?
     (informs whether scripts/fibo_morning.py's resolve_entity_tokens
     needs actions/cache)

CREDENTIAL SAFETY: every credential is read from an environment variable
(set from a GitHub Secret in the workflow's `env:`) and handed directly
to the existing, already-audited login()/send_email() functions -- this
script itself never reads, prints, or constructs a string containing any
credential value. It prints only: a redacted status string, a wall-clock
timestamp, a boolean, and a float duration.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import datetime as dt

import requests

from fibo.auth import login
from fibo_live.notify import send_email
from spread_monitor.market_hours import IST

# Same URL as fibo.download.ANGEL_SCRIP_MASTER_URL -- duplicated here
# rather than imported, so this probe doesn't need duckdb/pandas
# installed just to read a constant string.
ANGEL_SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"


def probe_login() -> None:
    print("--- 1. Angel One login ---")
    result = login()
    print(f"status: {result.status}")


def probe_ist_clock() -> None:
    print("--- 2. IST clock ---")
    now_ist = dt.datetime.now(IST)
    print(f"computed IST now: {now_ist.isoformat()}")
    print(f"(compare by eye against the real current IST time to confirm correctness)")


def probe_email() -> None:
    print("--- 3. Test email ---")
    sent = send_email(
        "FIBO PROBE: test email from GitHub Actions",
        "This is a one-off test email sent by scripts/probe_github_actions.py "
        "to confirm outbound SMTP works from a GitHub Actions runner.",
        log=print,
    )
    print(f"send_email returned: {sent}")


def probe_scrip_master() -> None:
    print("--- 4. Scrip master download timing ---")
    start = time.monotonic()
    resp = requests.get(ANGEL_SCRIP_MASTER_URL, timeout=60)
    n_bytes = len(resp.content)
    master = resp.json()
    elapsed = time.monotonic() - start
    print(f"downloaded + parsed {len(master)} instruments ({n_bytes / 1_000_000:.1f} MB) in {elapsed:.2f}s")


def main() -> None:
    probe_login()
    probe_ist_clock()
    probe_email()
    probe_scrip_master()


if __name__ == "__main__":
    main()
