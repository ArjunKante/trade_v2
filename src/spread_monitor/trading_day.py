"""Live trading-day verification.

The project's existing mechanism (src/data_layer/prices_nse.py's
NoDataForDate) detects a holiday from a 404 on the END-OF-DAY bhavcopy --
which does not exist until after that day's bhavcopy is published. A
live intraday snapshot cannot wait for that; it needs a signal available
DURING the session. The same underlying fact -- presence vs. absence of
real trading activity for today -- is available live from the quote feed
itself: Angel's getMarketData response carries `exchFeedTime`, the
exchange's own feed clock, on every row including an index (confirmed
live, 2026-10-05: a stock's row and the Nifty 50 index row both carried
the current wall-clock minute during live market hours). On a day NSE is
not trading, that feed does not advance to today's date, so comparing
its date against today's IST calendar date is the live equivalent of the
bhavcopy-404 check: absence of a live, current feed means the day is not
confirmed as a trading day.

Fails safe: any missing or unparseable exchFeedTime is treated as
UNVERIFIED, never as OK. A bad row in an append-only measurement log is
worse than a missing one (user instruction, 2026-10-05).
"""
from __future__ import annotations

import datetime as dt

from .market_hours import IST

OK = "OK"
UNVERIFIED = "UNVERIFIED_TRADING_DAY"

_EXCH_FEED_TIME_FORMAT = "%d-%b-%Y %H:%M:%S"


def _parse_feed_date(exch_feed_time: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(exch_feed_time, _EXCH_FEED_TIME_FORMAT).date()
    except (TypeError, ValueError):
        return None


def verify_trading_day(fetched_rows: list[dict], now_ist: dt.datetime) -> str:
    """OK if at least one fetched row's exchFeedTime carries today's IST
    date; UNVERIFIED_TRADING_DAY otherwise (no rows, no exchFeedTime
    field, unparseable value, or a stale date -- e.g. a holiday serving
    the last trading day's cached quote)."""
    today = now_ist.astimezone(IST).date()
    for row in fetched_rows:
        feed_date = _parse_feed_date(row.get("exchFeedTime"))
        if feed_date == today:
            return OK
    return UNVERIFIED
