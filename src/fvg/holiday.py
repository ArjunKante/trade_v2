"""Forward-stepping mirror of `box_theory.holiday.previous_nse_trading_day`
-- box theory never needs to step FORWARD across days (its pattern and
exit all resolve within one session), but `PREREGISTRATION_FVG.md`
Section 6's 5-trading-day time exit does. Same market-wide (not
per-entity) weekend+holiday stepping logic, same fail-safe stance on an
unverifiable weekday (treated as an ordinary trading day rather than
assumed to be a holiday) -- reimplemented here, not imported, because
`box_theory.holiday` is reused read-only (Section 0) and this direction
of stepping does not exist there.
"""
from __future__ import annotations

import datetime as dt

from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday


def next_nse_trading_day(d: dt.date) -> dt.date:
    """The NSE trading day immediately after `d`: steps forward one
    calendar day at a time, skipping Saturday/Sunday and any weekday the
    holiday master confirms was a holiday. An unverifiable weekday
    (`HolidayCalendarMissing`) is treated as an ordinary trading day --
    same fail-safe stance as `box_theory.holiday.previous_nse_trading_day`."""
    candidate = d + dt.timedelta(days=1)
    while True:
        if candidate.weekday() >= 5:
            candidate += dt.timedelta(days=1)
            continue
        try:
            if is_nse_holiday(candidate):
                candidate += dt.timedelta(days=1)
                continue
        except HolidayCalendarMissing:
            pass
        return candidate


def nth_next_nse_trading_day(d: dt.date, n: int) -> dt.date:
    """`next_nse_trading_day` applied `n` times -- the 5th NSE trading day
    strictly after `d`, per `PREREGISTRATION_FVG.md` Section 6's time exit."""
    out = d
    for _ in range(n):
        out = next_nse_trading_day(out)
    return out
