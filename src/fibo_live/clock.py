"""Detects whether a Fibo live run is LIVE (started during market hours
on the trading day itself -- the day's outcome is genuinely not yet
knowable) or REPLAY (started after that day's close, or on any later day
-- the day's bars already fully exist, so resolving a trade is a replay
of known history, not a wait for something to actually happen, even
though it runs the exact same frozen code). Computed ONCE per script
invocation from the wall clock -- never passed in as a flag, and never
set by a human -- see src/fibo_live/outcomes.py's evaluate() for why the
two must be reported separately rather than blended into one number.

DELIBERATELY NOT per-event: an outcome event is always logged at or after
15:15 by construction (scripts/fibo_morning.py's resolve_outcomes waits
for market close before resolving a trade). Detecting run_mode from an
individual event's OWN append timestamp would misclassify every single
outcome as REPLAY, even one from a genuinely live run that watched the
entry trigger fire in real time that morning. What distinguishes LIVE
from REPLAY is whether the RUN started before that trading day's data
fully existed -- not when any one event inside it happened to get
appended. Each orchestration script (fibo_evening.py, fibo_morning.py)
calls this exactly once per invocation and stamps the same value on every
event it logs that run.
"""
from __future__ import annotations

import datetime as dt

from spread_monitor.market_hours import IST

MARKET_OPEN = dt.time(9, 15)
MARKET_CLOSE = dt.time(15, 15)  # matches fibo.backtest.EXIT_TIME -- the day's outcome is settled by this time

LIVE = "LIVE"
REPLAY = "REPLAY"


def detect_run_mode(trade_date: dt.date, now: dt.datetime | None = None) -> str:
    """LIVE iff `now` falls on `trade_date` itself, strictly before that
    day's market close. REPLAY otherwise -- any later day, or the same day
    at/after 15:15.

    When `now` is omitted, it defaults to the REAL current instant
    converted to IST explicitly (dt.datetime.now(IST)), never the host's
    local clock -- this must give the same answer regardless of whether
    the machine running it has its OS clock set to IST (a laptop) or UTC
    (a GitHub Actions runner). A `now` passed in naive (as every existing
    caller/test does) is taken to already BE an IST wall-clock reading;
    a tz-aware `now` is converted to IST before comparison.

    NSE holidays are not checked here: a run started on a trading holiday
    would be misclassified as LIVE if it happened to fall within these
    clock hours. Not handled, flagged -- in practice,
    src/data_layer/staleness.py's guard is what prevents anything from
    being computed on a non-trading day to begin with."""
    now = now or dt.datetime.now(IST)
    if now.tzinfo is not None:
        now = now.astimezone(IST)
    if now.date() != trade_date:
        return REPLAY
    return LIVE if now.time() < MARKET_CLOSE else REPLAY
