"""Sizing and cost model, PREREGISTRATION_DARVAS.md Section 3: DELIVERY
(`swing.costs`, unchanged -- STT 0.1% both sides, stamp duty, exchange/
SEBI fees, GST, Groww brokerage, the DELIVERY-only DP charge, and the
ported 6.0-19.0bps round-trip spread/impact range), fixed Rs 500 risk,
`floor(500 / (entry - stop))` sizing with NO minimum-1-share override --
unlike `per_stock.costs.position_size_shares`'s own stated choice for a
different study, this document's instruction gives the bare formula with
no floor-at-1 carve-out, so a zero-quantity result is a skip
(`ZERO_QTY_SKIP`, tracked by the caller), never silently forced to 1
share.
"""
from __future__ import annotations

import math

from swing.costs import round_trip_cost_rs

FIXED_RISK_RS = 500.0


def position_size_shares(entry_price: float, stop_price: float, fixed_risk_rs: float = FIXED_RISK_RS) -> int:
    """floor(fixed_risk_rs / (entry_price - stop_price)). Can legitimately
    be 0 (Section 3) -- callers must check for that themselves rather than
    treat it as an error; only entry_price <= stop_price (a malformed
    box) raises."""
    r = entry_price - stop_price
    if r <= 0:
        raise ValueError(f"stop {stop_price} must be below entry {entry_price} (got R={r})")
    return math.floor(fixed_risk_rs / r)


def round_trip_cost_rs_midpoint(position_size_rs: float) -> float:
    """Midpoint of swing.costs' DELIVERY lo/hi spread+impact range --
    the identical convention `per_stock.costs.net_cost_fraction` already
    uses, Section 3's own note on why ONE point estimate is needed per
    trade. The range itself is carried as a stated sensitivity note in
    the report, never silently collapsed to this point value alone."""
    lo, hi = round_trip_cost_rs(position_size_rs, "DELIVERY")
    return (lo + hi) / 2


def net_r(pnl_rs: float, position_size_rs: float, fixed_risk_rs: float = FIXED_RISK_RS) -> float:
    """Net R = (pnl - cost) / FIXED_RISK_RS -- the NOMINAL Rs 500 target
    is the denominator throughout (Section 3), not each trade's own
    realized qty*(entry-stop), which is <= 500 by construction of the
    floor. Same convention PREREGISTRATION_BOX.md Section 4 already
    states for its own fixed-risk sizing."""
    cost = round_trip_cost_rs_midpoint(position_size_rs)
    return (pnl_rs - cost) / fixed_risk_rs
