"""Box theory's cost model -- PREREGISTRATION_BOX.md Section 4 and Section
0's reuse note: `swing.costs`'s INTRADAY statutory + Groww fixed-fee
formulas, plus the PREREGISTRATION_FIBO.md Section 8c frozen banded
spread/impact model (2.0 / 4.0 / 7.0 bps round trip for bands 1-50 /
51-100 / 101-200). This is the identical combination `scripts/
fibo_test_amended_cost.py` already applies for Fibo's own amended
re-test -- reused here as a frozen cost model, not re-derived.
"""
from __future__ import annotations

from swing.costs import buy_leg_cost_rs, sell_leg_cost_rs

# PREREGISTRATION_FIBO.md Section 8c, frozen 2026-10-08. Unranked
# (stub-year) entities fall back to the worst (101-200) figure, the same
# conservative convention scripts/fibo_test_amended_cost.py uses.
BAND_SPREAD_BPS = {"1-50": 2.0, "51-100": 4.0, "101-200": 7.0, "unranked": 7.0}

ORDER_TYPE = "INTRADAY"


def band_for_rank(rank: int | None) -> str:
    if rank is None:
        return "unranked"
    if 1 <= rank <= 50:
        return "1-50"
    if 51 <= rank <= 100:
        return "51-100"
    if 101 <= rank <= 200:
        return "101-200"
    return "unranked"


def round_trip_cost_rs(position_size_rs: float, band: str) -> float:
    """Statutory + Groww fixed costs (both legs, INTRADAY) plus the
    frozen Section 8c banded spread/impact component."""
    fixed = buy_leg_cost_rs(position_size_rs, ORDER_TYPE) + sell_leg_cost_rs(position_size_rs, ORDER_TYPE)
    spread = position_size_rs * BAND_SPREAD_BPS.get(band, 7.0) / 10_000
    return fixed + spread


def net_r(pnl_rs: float, position_size_rs: float, band: str, fixed_risk_rs: float = 500.0) -> float:
    """Net R = (pnl - cost) / fixed_risk_rs, per PREREGISTRATION_BOX.md
    Section 4."""
    cost = round_trip_cost_rs(position_size_rs, band)
    return (pnl_rs - cost) / fixed_risk_rs
