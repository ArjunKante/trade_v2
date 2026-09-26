"""NSE equity transaction cost model for short-horizon (1-5 day) swing
trading, on a retail Groww account. Two distinct execution structures --
they differ materially and must never be blended into one number:

  INTRADAY  (buy at open, sell at close, SAME day -- no depository transfer)
  DELIVERY  (buy, hold 1-5 trading days, sell -- shares actually move via
             the depository)

STATUTORY (exact, publicly documented -- not this project's own
assumption, but also not independently re-verified against a primary
source in this session; flagged per component below):
  - STT (Securities Transaction Tax): DELIVERY 0.1% on BOTH the buy and
    sell side; INTRADAY 0.025% on the SELL side ONLY. (Given directly by
    the user for this project; matches the well-known post-2023 STT
    schedule.)
  - Stamp duty: DELIVERY 0.015%, INTRADAY 0.003%, BUY side only, uniform
    pan-India since July 2020. The intraday rate specifically is filled in
    from general knowledge of the published schedule, not independently
    re-verified against NSE/SEBI circulars this session -- flag before
    relying on it for anything beyond an order-of-magnitude gate check.
  - NSE exchange transaction charges: ~0.00297% per side, same both
    structures (a cash-market-turnover charge, not settlement-type
    dependent). Ported from the sibling trade-info project's
    src/nsepit/costs.py, not independently re-verified for currency here.
  - SEBI turnover fee: 0.0001% per side, same both structures. Same
    ported-not-reverified status as the exchange charge above.
  - GST: 18% on (exchange charge + SEBI fee + brokerage), per side.

GROWW FIXED FEES (given directly by the user for this project; not in
trade-info's cost model, which assumed zero brokerage -- these are new
inputs specifically because short-horizon trading fires far more orders
per unit of capital than the quarterly-rebalance strategies this project's
other cost models were built for, so a fixed per-order cost that was
negligible there can dominate here):
  - Brokerage: min(Rs 20, 0.1% of trade value) per executed order (i.e.
    per leg), floored at Rs 5. Same formula both structures, per
    instruction.
  - DP (depository participant) charge: ~Rs 23.60 per company per SELL
    day, DELIVERY ONLY -- charged by the depository (CDSL/NSDL) only when
    shares actually move, which never happens on an intraday square-off.
    Rs 23.60 = Rs 20 + 18% GST (20 x 1.18 = 23.60 exactly) -- treated here
    as already GST-inclusive; GST is not separately re-applied to it.

SPREAD + MARKET IMPACT -- the least certain input, stated plainly:
Ported and back-solved from the sibling trade-info project's ground-truth
capacity study (ops/report_capacity_slippage_groundtruth.py), which
measured live Groww market-depth quoted spreads on 5 names (2026-09-15,
two readings each) at turnover rank 300-600 in ITS OWN whole-market
universe, and reported a headline all-in DELIVERY round-trip cost range of
26.0-39.0bps (ops/report_baselines_capacity.py's ROUND_TRIP_BPS_LO/HI)
built from a ~20bps statutory-floor assumption plus 2x the measured
per-side slippage. Back-solving out that ~20bps floor to isolate the
spread+impact component alone: (26-20, 39-20) = 6.0-19.0bps round-trip,
recombined here with this module's own precise statutory calculation
instead of the crude floor.

THIS PORT IS NOT VALIDATED FOR THIS PROJECT'S UNIVERSE, for three stated
reasons, not glossed over:
  1. Rank 300-600 by turnover in trade-info's whole-market universe is a
     DIFFERENT liquidity population from this project's planned swing
     universe (top two turnover terciles of the momentum top decile, which
     this project's own FINDINGS.md shows skews toward more liquid names
     already -- 58.3% high_liq / 31.2% mid_liq / 10.5% low_liq in momentum's
     top decile). A more liquid universe should have TIGHTER true spreads
     than this figure, so using it directly is probably conservative
     (overstates cost) -- the safe direction for a viability gate, but an
     assumption, not a measurement, for the population this project will
     actually use.
  2. The source measurement is DELIVERY-context (quoted spreads don't
     structurally depend on settlement type, but this was never measured
     for intraday specifically) -- reused here for intraday too, flagged.
  3. It is 5 names, 2 readings, one afternoon (2026-09-15) -- the source
     script itself states this should not be trusted to the second
     significant figure, and that status carries over unchanged here.

Deliberately a flat-bps-range model (not size/liquidity dependent beyond
the range itself) -- appropriate for a Phase 1 viability gate, not a claim
of execution-quality precision.
"""
from __future__ import annotations

# ---- statutory (exact, but flagged per-component above) ----
STT_DELIVERY_BPS_PER_SIDE = 10.0     # 0.1%, both sides
STT_INTRADAY_SELL_BPS = 2.5          # 0.025%, sell side only
STAMP_DUTY_DELIVERY_BUY_BPS = 1.5    # 0.015%, buy side only
STAMP_DUTY_INTRADAY_BUY_BPS = 0.3    # 0.003%, buy side only -- not re-verified this session
EXCHANGE_CHARGE_BPS_PER_SIDE = 0.297 # ~0.00297%, both structures, ported from trade-info
SEBI_FEE_BPS_PER_SIDE = 0.01         # 0.0001%, both structures, ported from trade-info
GST_RATE = 0.18                      # on exchange charge + SEBI fee + brokerage, per side

# ---- Groww fixed fees (this project's own new input, not in trade-info) ----
BROKERAGE_CAP_RS = 20.0
BROKERAGE_PCT = 0.001                # 0.1% of trade value
BROKERAGE_FLOOR_RS = 5.0
DP_CHARGE_RS = 23.60                 # per company per sell day, DELIVERY only, GST-inclusive already

# ---- spread + impact, ground-truth-anchored but NOT validated for this universe (see module docstring) ----
SPREAD_IMPACT_ROUND_TRIP_BPS_LO = 6.0
SPREAD_IMPACT_ROUND_TRIP_BPS_HI = 19.0

ORDER_TYPES = ("INTRADAY", "DELIVERY")


def brokerage_rs(trade_value_rs: float) -> float:
    """Groww discount-broker formula: the smaller of a flat Rs 20 or 0.1%
    of trade value, floored at Rs 5. Same formula both order types, per
    instruction."""
    return max(BROKERAGE_FLOOR_RS, min(BROKERAGE_CAP_RS, trade_value_rs * BROKERAGE_PCT))


def _gst_on(*components_rs: float) -> float:
    return sum(components_rs) * GST_RATE


def buy_leg_cost_rs(trade_value_rs: float, order_type: str) -> float:
    """Statutory + Groww fixed cost to BUY one leg (excludes spread/impact,
    added separately at the round-trip level -- see round_trip_cost_rs)."""
    if order_type not in ORDER_TYPES:
        raise ValueError(f"order_type must be one of {ORDER_TYPES}, got {order_type!r}")
    stamp_bps = STAMP_DUTY_INTRADAY_BUY_BPS if order_type == "INTRADAY" else STAMP_DUTY_DELIVERY_BUY_BPS
    exchange = trade_value_rs * EXCHANGE_CHARGE_BPS_PER_SIDE / 10_000
    sebi = trade_value_rs * SEBI_FEE_BPS_PER_SIDE / 10_000
    stamp = trade_value_rs * stamp_bps / 10_000
    brokerage = brokerage_rs(trade_value_rs)
    gst = _gst_on(exchange, sebi, brokerage)
    # No STT on the buy leg under either order type: delivery STT is charged
    # both sides but this project models it entirely on the sell leg's own
    # STT_DELIVERY_BPS_PER_SIDE call in sell_leg_cost_rs for symmetry with
    # the intraday case (sell-only) -- see sell_leg_cost_rs's own STT line;
    # avoided splitting delivery STT across both functions to keep each
    # leg's STT line traceable to a single formula.
    return exchange + sebi + stamp + brokerage + gst


def sell_leg_cost_rs(trade_value_rs: float, order_type: str) -> float:
    """Statutory + Groww fixed cost to SELL one leg (excludes spread/impact).
    DELIVERY STT (both sides, per the model's convention -- see
    buy_leg_cost_rs's note) is charged in full here, twice the intraday
    sell-only rate, which is itself sell-only STT."""
    if order_type not in ORDER_TYPES:
        raise ValueError(f"order_type must be one of {ORDER_TYPES}, got {order_type!r}")
    stt_bps = STT_INTRADAY_SELL_BPS if order_type == "INTRADAY" else STT_DELIVERY_BPS_PER_SIDE * 2
    stt = trade_value_rs * stt_bps / 10_000
    exchange = trade_value_rs * EXCHANGE_CHARGE_BPS_PER_SIDE / 10_000
    sebi = trade_value_rs * SEBI_FEE_BPS_PER_SIDE / 10_000
    brokerage = brokerage_rs(trade_value_rs)
    gst = _gst_on(exchange, sebi, brokerage)
    dp = DP_CHARGE_RS if order_type == "DELIVERY" else 0.0
    return stt + exchange + sebi + brokerage + gst + dp


def round_trip_cost_rs(position_size_rs: float, order_type: str) -> tuple[float, float]:
    """(lo, hi) total Rs cost for one buy-then-sell round trip at this
    position size, spanning the ground-truth-anchored spread/impact range
    (see module docstring for its ported, not-yet-validated-for-this-
    universe status). Statutory + Groww fixed costs are exact given the
    stated assumptions and identical at both ends of the range; only the
    spread/impact component varies."""
    fixed = buy_leg_cost_rs(position_size_rs, order_type) + sell_leg_cost_rs(position_size_rs, order_type)
    spread_lo = position_size_rs * SPREAD_IMPACT_ROUND_TRIP_BPS_LO / 10_000
    spread_hi = position_size_rs * SPREAD_IMPACT_ROUND_TRIP_BPS_HI / 10_000
    return fixed + spread_lo, fixed + spread_hi


def round_trip_cost_bps(position_size_rs: float, order_type: str) -> tuple[float, float]:
    lo, hi = round_trip_cost_rs(position_size_rs, order_type)
    return lo / position_size_rs * 10_000, hi / position_size_rs * 10_000
