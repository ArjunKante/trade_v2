"""Non-overlapping signal schedule and time-of-day buckets (Decisions
11, 22).

Decision 11: `09:15` is the first regular-session bar; the earliest
non-overlapping signal-end minute is `t=09:19` (the `09:15..09:19`
signal window), becoming known at wall-clock `09:20`.

Non-overlapping spacing: for prediction horizon `h`, consecutive signal
slots are spaced `h+5` minutes apart (the signal window itself is 5
minutes wide), so the forward window `[t-4,t+h]` of one slot never
overlaps the next slot's own signal window.

Momentum_F(t)'s own minimum anchor (Decision 22) is `t >= 09:50`
(`t-35 >= 09:15`) -- NOT separately enforced by this module. Momentum_F
is a required primary control (Decision 7), so any scheduled slot before
`09:50` will systematically fail Stage A eligibility for lack of a valid
`t-35` endpoint (eligibility.py), not because this module silently drops
it. This module generates the full schedule starting at the Decision-11
anchor; Stage A is where the Momentum_F constraint actually bites.
"""
from __future__ import annotations

import datetime as dt

SIGNAL_END_MINUTE_ANCHOR = dt.time(9, 19)  # Decision 11
SESSION_END = dt.time(15, 29)  # Section 12, Decision 17
OPENING_30_END = dt.time(9, 44)
CLOSING_30_START = dt.time(15, 0)

HORIZONS = (5, 15, 30, 60)  # Section 10


def tod_bucket(t: dt.time) -> str:
    """Section 6/11: categorical time-of-day control, opening-30 /
    midday / closing-30."""
    if dt.time(9, 15) <= t <= OPENING_30_END:
        return "opening_30"
    if CLOSING_30_START <= t <= SESSION_END:
        return "closing_30"
    return "midday"


def _add_minutes(t: dt.time, minutes: int) -> dt.time:
    base = dt.datetime.combine(dt.date(2000, 1, 1), t)
    return (base + dt.timedelta(minutes=minutes)).time()


def non_overlapping_schedule(horizon: int,
                              anchor: dt.time = SIGNAL_END_MINUTE_ANCHOR,
                              session_end: dt.time = SESSION_END) -> list[dt.time]:
    """Candidate signal-end minutes `t` for one horizon `h`, spaced
    `h+5` apart starting at `anchor`, stopping once `t+h` would exceed
    `session_end` (last eligible `t` satisfies `t+h <= session_end`)."""
    spacing = horizon + 5
    out = []
    t = anchor
    last_eligible = _add_minutes(session_end, -horizon)
    while t <= last_eligible:
        out.append(t)
        t = _add_minutes(t, spacing)
    return out


def all_schedules(horizons: tuple[int, ...] = HORIZONS,
                   anchor: dt.time = SIGNAL_END_MINUTE_ANCHOR,
                   session_end: dt.time = SESSION_END) -> dict[int, list[dt.time]]:
    return {h: non_overlapping_schedule(h, anchor, session_end) for h in horizons}
