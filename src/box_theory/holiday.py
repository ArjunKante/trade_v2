"""Market-wide "what date is the immediately preceding NSE trading day"
stepper -- deliberately NOT `fibo.scale_probe.previous_trading_day` (that
function answers a different question: entity E's own most recent
`prices_eod` row before D, which silently skips past any day E happened
not to trade and would mask exactly the Muhurat/gap case
PREREGISTRATION_BOX.md Section 2b needs caught). This one answers "what
date was the market open before D," independent of any one entity's own
archive, using the same shared NSE holiday master every other live/
backtest script in this project already reads (`data_layer.nse_holidays`).

Same weekend+holiday stepping logic `scripts/fibo_morning.py`'s own
`previous_trading_day` already uses, reimplemented here (not imported --
that function lives in a script, not an importable module, and box_theory
does not reach into Fibo's live-trading script for a research backtest).
"""
from __future__ import annotations

import datetime as dt

from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday


def previous_nse_trading_day(d: dt.date) -> dt.date:
    """The NSE trading day immediately before `d`: steps back one calendar
    day at a time, skipping Saturday/Sunday and any weekday the holiday
    master confirms was a holiday. If the holiday master cannot confirm a
    given weekday either way (`HolidayCalendarMissing`), that weekday is
    treated as an ordinary trading day -- same fail-safe stance `data_
    layer.nse_holidays` itself documents (an unverifiable day is never
    assumed to be a holiday); for this backtest, the archive-side 350-bar
    floor (Section 2b) is the real backstop against a wrongly-assumed
    trading day, not this function."""
    candidate = d - dt.timedelta(days=1)
    while True:
        if candidate.weekday() >= 5:  # Saturday=5, Sunday=6
            candidate -= dt.timedelta(days=1)
            continue
        try:
            if is_nse_holiday(candidate):
                candidate -= dt.timedelta(days=1)
                continue
        except HolidayCalendarMissing:
            pass
        return candidate
