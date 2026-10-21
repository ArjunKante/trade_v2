"""`PREREGISTRATION_IPO.md` Section 6: structurally identical to
`box_theory.costs.round_trip_cost_rs` (same statutory + Groww fixed-cost
call into `swing.costs`, unchanged), but parameterized by an explicit
spread bps value rather than box theory's fixed 3-band dict, because
this study evaluates ONE population at three different bps levels
(7/14/28 -- the widest existing band used as a floor, and 2x/4x), not
three different populations each at their own band.
"""
from __future__ import annotations

from swing.costs import buy_leg_cost_rs, sell_leg_cost_rs

ORDER_TYPE = "INTRADAY"

FLOOR_BPS = 7.0
COST_SCENARIOS_BPS = (7.0, 14.0, 28.0)  # floor (widest existing band), 2x, 4x


def round_trip_cost_rs(position_size_rs: float, spread_bps: float) -> float:
    """Statutory + Groww fixed costs (both legs, INTRADAY) plus a spread/
    impact component at the given flat bps."""
    fixed = buy_leg_cost_rs(position_size_rs, ORDER_TYPE) + sell_leg_cost_rs(position_size_rs, ORDER_TYPE)
    spread = position_size_rs * spread_bps / 10_000
    return fixed + spread


def net_r(pnl_rs: float, position_size_rs: float, spread_bps: float, fixed_risk_rs: float = 500.0) -> float:
    cost = round_trip_cost_rs(position_size_rs, spread_bps)
    return (pnl_rs - cost) / fixed_risk_rs
