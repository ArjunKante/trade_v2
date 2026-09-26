"""Unit tests for src/swing/costs.py -- the swing-trading cost model.
Pure arithmetic, no database, no market data."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swing.costs import (
    BROKERAGE_CAP_RS, BROKERAGE_FLOOR_RS, DP_CHARGE_RS,
    brokerage_rs, buy_leg_cost_rs, sell_leg_cost_rs,
    round_trip_cost_rs, round_trip_cost_bps,
)


def test_brokerage_floors_at_rs5_for_tiny_trades():
    assert brokerage_rs(100) == BROKERAGE_FLOOR_RS


def test_brokerage_caps_at_rs20_for_large_trades():
    assert brokerage_rs(1_000_000) == BROKERAGE_CAP_RS


def test_brokerage_is_pct_in_the_middle_band():
    # 0.1% of 10,000 = Rs 10 -- strictly between the Rs5 floor and Rs20 cap
    assert brokerage_rs(10_000) == pytest.approx(10.0)


def test_dp_charge_is_gst_inclusive_20_times_1_18():
    assert DP_CHARGE_RS == pytest.approx(20.0 * 1.18)


def test_delivery_sell_leg_costs_more_than_intraday_sell_leg():
    # delivery STT is 2x the (both-sides) rate vs intraday's sell-only rate,
    # plus the DP charge -- delivery must always cost more per sell leg.
    intraday = sell_leg_cost_rs(50_000, "INTRADAY")
    delivery = sell_leg_cost_rs(50_000, "DELIVERY")
    assert delivery > intraday
    assert delivery - intraday >= DP_CHARGE_RS


def test_buy_leg_has_no_stt_either_order_type():
    # this model charges all STT on the sell leg (see costs.py's note in
    # buy_leg_cost_rs) -- confirm the buy leg is statutory-light by
    # comparison: strictly less than the matching sell leg at the same size.
    for order_type in ("INTRADAY", "DELIVERY"):
        assert buy_leg_cost_rs(50_000, order_type) < sell_leg_cost_rs(50_000, order_type)


def test_round_trip_cost_scales_with_position_size():
    lo_10k, hi_10k = round_trip_cost_rs(10_000, "DELIVERY")
    lo_100k, hi_100k = round_trip_cost_rs(100_000, "DELIVERY")
    assert lo_100k > lo_10k
    assert hi_100k > hi_10k


def test_round_trip_bps_lo_le_hi():
    for order_type in ("INTRADAY", "DELIVERY"):
        for size in (10_000, 50_000, 100_000, 500_000):
            lo, hi = round_trip_cost_bps(size, order_type)
            assert lo <= hi
            assert lo > 0


def test_fixed_costs_dominate_small_delivery_trades():
    # at Rs 10k, Rs 5 floor brokerage x2 legs + ~Rs23.60 DP charge is a much
    # bigger fraction of trade value than at Rs 5L -- confirms the user's
    # stated concern that fixed costs matter far more at small size.
    lo_10k, _ = round_trip_cost_bps(10_000, "DELIVERY")
    lo_500k, _ = round_trip_cost_bps(500_000, "DELIVERY")
    assert lo_10k > lo_500k


def test_invalid_order_type_raises():
    with pytest.raises(ValueError):
        buy_leg_cost_rs(10_000, "SWING")
