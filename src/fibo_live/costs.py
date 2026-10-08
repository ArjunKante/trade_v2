"""Section 8c frozen cost model, copied verbatim from
scripts/fibo_test_amended_cost.py -- the SAME band-based spread/impact
figures used for the amended re-test, so a live trade's net R is computed
on the identical cost assumption the +0.3673 baseline (config.
SEALED_AMENDED_MEAN_NET_R) was itself computed under. This is a frozen rule
for the purposes of the DO-NOT list: it does not change before 100 trades,
and a change to it is a new PAPER_VERSION, not an edit here.
"""
from __future__ import annotations

from swing.costs import buy_leg_cost_rs, sell_leg_cost_rs

BAND_EDGES = [(1, 50, "1-50"), (51, 100, "51-100"), (101, 200, "101-200")]

# PREREGISTRATION_FIBO.md Section 8c, frozen 2026-10-08.
FROZEN_SPREAD_BPS = {"1-50": 2.0, "51-100": 4.0, "101-200": 7.0, "unranked": 7.0}


def band_for_rank(rank: int | None) -> str:
    if rank is None:
        return "unranked"
    for lo, hi, label in BAND_EDGES:
        if lo <= rank <= hi:
            return label
    return "unranked"


def amended_cost_rs(position_size_rs: float, band: str) -> float:
    fixed = buy_leg_cost_rs(position_size_rs, "INTRADAY") + sell_leg_cost_rs(position_size_rs, "INTRADAY")
    spread = position_size_rs * FROZEN_SPREAD_BPS.get(band, 7.0) / 10_000
    return fixed + spread


def net_r_amended(gross_r: float, entry_price: float, qty: int, r_rupees: float, band: str) -> float:
    position_size_rs = qty * entry_price
    cost = amended_cost_rs(position_size_rs, band)
    return gross_r - cost / (r_rupees * qty)
