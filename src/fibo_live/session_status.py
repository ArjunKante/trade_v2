"""Durable session_status events: the evidence trail for WHETHER a
scheduled run itself did anything, independent of whatever log happens
to survive the machine it ran on.

data/fibo_live/scheduler.log (scheduler_support.py) answers "did the
process run and what did it print" -- but on a GitHub Actions runner
that file lives only on the ephemeral runner and is thrown away the
instant the job finishes; the only thing committed and pushed anywhere
durable is events.jsonl. Without a record THERE, a refused run (a stale
watchlist, a non-trading day, a login failure) is visible only in that
one run's own Actions log, gone once GitHub's retention window closes,
and indistinguishable after the fact from the evening job never having
run at all -- the exact ambiguity that made the 2026-10-15/16 gap need a
manual backfill (see OPERATIONS.md).

kind="session_status" events carry trade_date, session, status, reason,
run_mode. `status` is one of the constants below:
  MISSED           -- no run happened at all (only ever backfilled by
                      hand, after the fact discovering a gap -- nothing
                      in this codebase logs this one automatically,
                      since a run that never happened can't log anything).
  REFUSED          -- a run happened and explicitly declined to do any
                      per-stock work, for a reason that is NOT "today
                      isn't a trading day" (e.g. a stale/missing
                      watchlist, a login failure).
  NON_TRADING_DAY  -- a run happened and confirmed today is not a
                      trading day (weekend, or an NSE holiday confirmed
                      by data_layer.nse_holidays.is_nse_holiday) -- kept
                      distinct from REFUSED so a holiday reads
                      differently from a genuinely missed/broken evening
                      run (see scripts/fibo_morning.py's
                      is_non_trading_day, which decides which applies).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from fibo_live.config import EVENTS_LOG
from fibo_live.eventlog import append_event, read_events

MISSED = "MISSED"
REFUSED = "REFUSED"
NON_TRADING_DAY = "NON_TRADING_DAY"


def already_logged_session_status(trade_date: dt.date, session: str, reason: str,
                                   log_path: Path = EVENTS_LOG) -> bool:
    """True iff an identical (trade_date, session, reason) session_status
    event is already logged -- the dedup key a schedule re-hitting the
    SAME refusal every 15 minutes all morning must match on, so it
    writes the event once, not nine times."""
    key = str(trade_date)
    for e in read_events(kind="session_status", log_path=log_path):
        if e.get("trade_date") == key and e.get("session") == session and e.get("reason") == reason:
            return True
    return False


def record_session_status(trade_date: dt.date, session: str, status: str, reason: str,
                           run_mode: str | None = None, log_path: Path = EVENTS_LOG) -> dict | None:
    """Appends one session_status event unless an identical one (same
    trade_date/session/reason) is already logged -- returns None in that
    case rather than writing a duplicate row. `reason` should be the
    same human-readable text already being logged to scheduler.log/
    stdout at the call site, reused verbatim so the two records agree.

    `log_path` defaults to the real events.jsonl; overridable for tests
    the same way outcomes.py's record_outcome/evaluate already are."""
    if already_logged_session_status(trade_date, session, reason, log_path=log_path):
        return None
    return append_event("session_status", {
        "trade_date": trade_date, "session": session, "status": status,
        "reason": reason, "run_mode": run_mode,
    }, log_path=log_path)
