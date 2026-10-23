"""CLI: records one NIFTY index-option depth snapshot -- nearest 2
expiries, strikes within +/-5% of the live NIFTY spot -- appended to
data/options_depth/v1/nifty_depth_log.csv.

RESEARCH/COLLECTION ONLY (src/options_depth/__init__.py): no strategy,
no analysis, no signal. Intended to run three times a trading day
(~10:30, ~12:30, ~14:30 IST) via Windows Task Scheduler -- see
OPERATIONS.md for the exact setup (battery-tolerant, never wakes the
machine, a missed snapshot is acceptable). This data is irreplaceable
once a contract expires and is NOT backed up by git (see
src/options_depth/__init__.py) -- back it up off this laptop manually.

Infrastructure only: authenticates via src/fibo/auth.login (data-only,
the one credential-safety-hardened login path, reused rather than
reimplemented) and calls getMarketData(mode="FULL", ...). Places no
order, computes no signal, touches no Fibo/swing/momentum/per_stock
result.

Angel's getMarketData has a HARD LIMIT of 50 tokens per call (confirmed
live, 2026-10-12: 51 tokens -> error AB4029 "Tokens max limit exceeded",
50 -> success, OPERATIONS.md) -- option tokens are chunked accordingly.
Same rate-limit posture as scripts/snapshot_spreads.py: a flat pace
between calls (this project's standard 0.4s, OPERATIONS.md), and NO
retry-with-backoff on a rate-limit-shaped error -- a failed chunk is
logged and skipped for this snapshot, never recorded as if it had
succeeded, the same as the spread monitor's own documented behavior.

UNATTENDED (Windows Task Scheduler, src/options_depth/scheduler_support.py
-- same shape as the Fibo jobs' own scheduler_support.py, duplicated to
stay decoupled, see this package's __init__.py): every log() line also
goes to data/options_depth/scheduler.log, since a scheduled run has no
terminal. main() is wrapped so ANY unhandled exception is caught, logged
with its traceback, and swallowed -- the process always exits 0. A
holiday, a weekend, or a market-closed run hits check_market_hours()'s
own clean early return (logged, not raised) -- never an error, never a
non-zero exit, never a reason Task Scheduler would flag this run as
failed.

Usage: python scripts/snapshot_options_depth.py
"""
from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fibo.auth import login
from options_depth.contracts import NIFTY_50_INDEX_TOKEN, contracts_for_snapshot
from options_depth.quotes import exch_feed_date, parse_full_depth_row
from options_depth.scheduler_support import make_logger, run_unattended
from options_depth.writer import append_rows
from spread_monitor.market_hours import IST, check_market_hours

CHUNK_SIZE = 50  # Angel's hard per-call token limit, confirmed live -- see module docstring
INTER_CALL_PACE_SECONDS = 0.4  # this project's standard flat throttle, OPERATIONS.md

log = make_logger()


def _chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def main() -> None:
    ok, reason = check_market_hours()
    if not ok:
        log(f"REFUSING TO RUN: {reason}. A snapshot taken when the market "
            f"is shut (or in the first/last 15 minutes) is not recorded. "
            f"Nothing else to do.")
        return

    result = login()
    if not result.ok:
        log(f"LOGIN FAILED: {result.status} -- offline, Angel down, or bad credentials. "
            f"Not retrying; the next scheduled run will try again.")
        return
    client = result.client

    spot_resp = client.getMarketData("FULL", {"NSE": [NIFTY_50_INDEX_TOKEN]})
    if not isinstance(spot_resp, dict) or not spot_resp.get("status"):
        log(f"SPOT REQUEST FAILED: {spot_resp.get('message') if isinstance(spot_resp, dict) else spot_resp} "
            f"-- cannot select strikes without a live spot. Nothing recorded.")
        return
    spot_fetched = (spot_resp.get("data") or {}).get("fetched") or []
    if not spot_fetched:
        log("SPOT REQUEST returned no row for the Nifty 50 index. Nothing recorded.")
        return
    spot_row = spot_fetched[0]
    nifty_spot = spot_row.get("ltp")
    nifty_spot_ts = spot_row.get("exchFeedTime")
    if nifty_spot is None:
        log("Spot row carried no ltp. Nothing recorded.")
        return
    log(f"Nifty spot: {nifty_spot} (exchFeedTime={nifty_spot_ts})")

    today = dt.datetime.now(IST).date()

    feed_date = exch_feed_date(nifty_spot_ts)
    if feed_date != today:
        log(f"WARNING: STALE SESSION -- exchFeedTime={nifty_spot_ts!r} resolves to "
            f"{feed_date}, not today ({today}). check_market_hours() passed (weekday, "
            f"within session hours) but the feed itself is not live -- most likely an "
            f"NSE holiday check_market_hours() cannot detect (spread_monitor.market_hours's "
            f"documented gap). A stale tick must never be recorded as a snapshot. "
            f"Nothing recorded.")
        return

    contracts = contracts_for_snapshot(nifty_spot, today=today)
    if not contracts:
        log("No NIFTY option contracts resolved for today's nearest 2 expiries / +-5% band. Nothing recorded.")
        return
    log(f"{len(contracts)} contracts selected (nearest 2 expiries, strikes within +-5% of spot).")
    by_token = {c.token: c for c in contracts}

    timestamp_ist = dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    chunks = _chunk(list(by_token.keys()), CHUNK_SIZE)
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(INTER_CALL_PACE_SECONDS)
        resp = client.getMarketData("FULL", {"NFO": chunk})
        if not isinstance(resp, dict) or not resp.get("status"):
            log(f"  chunk {i + 1}/{len(chunks)} ({len(chunk)} tokens) FAILED: "
                f"{resp.get('message') if isinstance(resp, dict) else resp} -- skipped, not retried.")
            continue
        data = resp.get("data") or {}
        fetched = data.get("fetched") or []
        unfetched = data.get("unfetched") or []
        if unfetched:
            log(f"  chunk {i + 1}/{len(chunks)}: {len(unfetched)} token(s) unfetched: {unfetched}")
        for item in fetched:
            token_str = str(item.get("symbolToken"))
            contract = by_token.get(token_str)
            if contract is None:
                log(f"  WARNING: fetched row with unrecognized symbolToken {item.get('symbolToken')!r}, skipping.")
                continue
            rows.append(parse_full_depth_row(contract, item, timestamp_ist, nifty_spot, nifty_spot_ts))

    if not rows:
        log("No rows fetched across any chunk. Nothing recorded.")
        return

    append_rows(rows)
    log(f"Recorded {len(rows)} of {len(contracts)} contract(s) at {timestamp_ist} IST.")


if __name__ == "__main__":
    run_unattended("OPTIONS DEPTH SNAPSHOT", main, log)
