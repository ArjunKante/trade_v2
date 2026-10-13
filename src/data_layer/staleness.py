"""Shared freshness guard for every computation built on prices_eod.

Found live (BUGS.md Bug #13): daily ingestion silently stopped for 13
trading days -- zero trace in fetch_log, not attempted, not failed,
simply never run. Nothing alerted. The gap only surfaced days later when
factors.momentum's own internal gap guard correctly NaN'd every momentum
value, which crashed a UI route far downstream of the actual problem. Had
only the Fibo evening job been run that night, it would have produced a
plausible-looking watchlist on incomplete data with no error anywhere --
the code behaved correctly throughout; nothing was watching whether the
data was current.

A scheduled ingestion job can fail silently too -- this project has no
scheduled runner at all (ingestion has always been a manual step, per
RUNBOOK.md), so there was never anything watching in the first place. This
guard is not a substitute for scheduling or monitoring ingestion; it is
the last line, checked at the one place a silent ingestion gap would
otherwise turn directly into a wrong computed result: immediately before
that computation runs. Every entry point that computes from the price
panel calls THIS function -- the Fibo evening watchlist
(src/fibo_live/watchlist.py), the momentum universe
(src/reports/fundamental_snapshot.py), the screener
(src/reports/fundamental_screener.py), and the persistence monitor
(src/monitor/web.py) -- none of them re-implements the date arithmetic
itself.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import duckdb

IST = ZoneInfo("Asia/Kolkata")  # same tz as spread_monitor.market_hours.IST; defined
                                 # locally rather than imported to avoid data_layer
                                 # depending on a higher-level live-trading module.
DEFAULT_MAX_STALENESS_DAYS = 3  # 1 trading day plus a long weekend's worth of margin


class StaleDataError(Exception):
    """Raised instead of silently computing from a price panel older than
    max_staleness_days. Callers must let this propagate -- never catch and
    continue with a stale panel."""


def latest_trade_date(con: duckdb.DuckDBPyConnection) -> dt.date | None:
    row = con.execute("SELECT MAX(trade_date) FROM prices_eod").fetchone()
    return row[0] if row and row[0] is not None else None


def assert_data_current(
    con: duckdb.DuckDBPyConnection,
    as_of: dt.date | None = None,
    max_staleness_days: int = DEFAULT_MAX_STALENESS_DAYS,
) -> dt.date:
    """Returns the warehouse's latest trade_date if it is within
    max_staleness_days of `as_of` (real wall-clock today IN IST by
    default -- never the host machine's own local clock, so this stays
    correct whether it runs on an IST laptop or a UTC GitHub Actions
    runner -- override only for tests that need to pin "today" to
    reproduce a specific historical gap deterministically). Raises
    StaleDataError otherwise."""
    as_of = as_of or dt.datetime.now(IST).date()
    latest = latest_trade_date(con)
    if latest is None:
        raise StaleDataError("prices_eod is empty -- nothing to compute from.")
    gap_days = (as_of - latest).days
    if gap_days > max_staleness_days:
        raise StaleDataError(
            f"warehouse's latest trading day is {latest}, {gap_days} days before {as_of} "
            f"(max allowed: {max_staleness_days}). Daily ingestion looks stalled -- refusing to "
            f"compute anything from this price panel until it is current. See BUGS.md Bug #13."
        )
    return latest
