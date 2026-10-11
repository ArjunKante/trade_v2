"""Cost model for the per-stock weekly study: reuses src/swing/costs.py's
DELIVERY round-trip model UNCHANGED and read-only -- this project's single
source of truth for NSE equity transaction costs, never duplicated or
re-derived here. Positions in this study are held Monday-to-Friday
(overnight, multi-day), so DELIVERY (not INTRADAY) is the correct
structure -- same reasoning src/fibo/backtest.py applies for its own
overnight-vs-same-day choice, just landing on the other side of it.

POSITION SIZING, a declared assumption, fixed before any trial ran, never
tuned: FIXED_RISK_RS below. Matches the fixed-risk-per-trade convention
src/fibo/resolution.py already uses for the (unrelated) Fibo study
(entry/stop both well-defined here too: stop = entry * (1 - sigma)), with
its own independent value -- not reused from Fibo, not meant to match it,
just the same style of round, stated number. This matters because
swing.costs' fixed-fee components (brokerage floor/cap, the flat DELIVERY
DP charge) make cost-as-a-fraction-of-position-size shrink as position
size grows -- the position size is NOT a free knob tuned after seeing
results; it is fixed once, here, in this file's one constant.
"""
from __future__ import annotations

import math

from swing.costs import round_trip_cost_rs

FIXED_RISK_RS = 2000.0


def position_size_shares(entry_price: float, stop_price: float, fixed_risk_rs: float = FIXED_RISK_RS) -> int:
    """Whole shares, floored (never rounded up -- rounding up would risk
    more than fixed_risk_rs if stopped out). Floored at a MINIMUM of 1
    share, not 0: a high-priced, high-sigma week can make the fixed-risk
    budget alone imply fewer than 1 share (e.g. a Rs10,000 stock with a
    6% weekly sigma needs R=Rs600/share -- fine at fixed_risk_rs=2000, but
    a wide enough sigma week can still push R past the budget). Buying 1
    share anyway (risking more than fixed_risk_rs in that one case) is
    the stated tie-breaker, chosen over silently dropping the trade or
    raising, so a volatile week doesn't just vanish from the trade count."""
    r = entry_price - stop_price
    if r <= 0:
        raise ValueError(f"stop {stop_price} must be below entry {entry_price} (got R={r})")
    return max(1, math.floor(fixed_risk_rs / r))


def net_cost_fraction(entry_price: float, stop_price: float, fixed_risk_rs: float = FIXED_RISK_RS) -> float:
    """Round-trip DELIVERY cost as a fraction of this trade's own position
    value, at the fixed-risk share count entry_price/stop_price implies.
    Uses the MIDPOINT of swing.costs' lo/hi spread+impact range (see that
    module's docstring for why a range exists instead of a point value) --
    a single point estimate is needed here to produce one net return per
    trade; the range itself is carried into the report as a stated
    sensitivity note, not silently collapsed."""
    qty = position_size_shares(entry_price, stop_price, fixed_risk_rs)
    position_size_rs = qty * entry_price
    lo, hi = round_trip_cost_rs(position_size_rs, "DELIVERY")
    return (lo + hi) / 2 / position_size_rs
