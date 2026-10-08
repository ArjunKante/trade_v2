"""Market-hours guard: refuses to let a quote be recorded when the
market cannot plausibly be open, so a meaningless reading (stale depth
against a shut market) never enters the log.

KNOWN GAP, stated plainly rather than silently assumed away: this checks
weekday + the 09:15-15:30 IST window only. It does NOT check an NSE
trading-holiday calendar -- no such calendar exists anywhere in this
project (the Fibo/swing download code detects holidays reactively, from
a 404 on the bhavcopy archive, not from a precomputed list; see
src/data_layer/prices_nse.py's NoDataForDate). A quote attempted on an
NSE holiday that falls on a weekday will pass this guard and hit the
live API; whether that returns stale FULL-mode depth or an error is
untested here. Treat any reading taken on a suspected holiday as
suspect until checked against the day's actual bhavcopy.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = dt.time(9, 15)
MARKET_CLOSE = dt.time(15, 30)

# Opening volatility and the pre-close auction are exactly where feed
# oddities cluster (e.g. the 2026-10-07 15:27:41 snapshot: 18/20 symbols
# came back with a crossed book -- best_bid > best_ask -- a reading taken
# 3 minutes before close). Refuse the first/last 15 minutes of the
# session outright rather than relying on the caller to remember to avoid
# them.
OPEN_GUARD_END = dt.time(9, 30)
CLOSE_GUARD_START = dt.time(15, 15)


def check_market_hours(now: dt.datetime | None = None) -> tuple[bool, str]:
    """(True, "") if `now` (IST, defaults to the current moment) falls
    inside a plausible trading session, excluding the first/last 15
    minutes (opening volatility / pre-close auction); otherwise
    (False, reason)."""
    if now is None:
        now = dt.datetime.now(IST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)

    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False, f"not a trading day (weekend): {now:%Y-%m-%d %A}"

    if not (MARKET_OPEN <= now.time() <= MARKET_CLOSE):
        return False, (
            f"outside market hours: {now:%Y-%m-%d %H:%M:%S} IST is not within "
            f"{MARKET_OPEN:%H:%M}-{MARKET_CLOSE:%H:%M} IST"
        )

    if now.time() < OPEN_GUARD_END:
        return False, (
            f"too close to open: {now:%Y-%m-%d %H:%M:%S} IST is within the first 15 "
            f"minutes of the session ({MARKET_OPEN:%H:%M}-{OPEN_GUARD_END:%H:%M} IST) -- "
            f"opening volatility makes depth readings unreliable"
        )

    if now.time() >= CLOSE_GUARD_START:
        return False, (
            f"too close to close: {now:%Y-%m-%d %H:%M:%S} IST is within the last 15 "
            f"minutes of the session ({CLOSE_GUARD_START:%H:%M}-{MARKET_CLOSE:%H:%M} IST) -- "
            f"pre-close auction effects make depth readings unreliable"
        )

    return True, ""
