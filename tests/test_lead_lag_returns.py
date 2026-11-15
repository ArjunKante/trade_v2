"""Decision 13: exact-endpoint-price return convention; R_L/R_F/S_L/Y/
Momentum_F portfolio-level construction; MANDATORY same-session
enforcement via `DatedPrice` (Decision 14) -- no path exists to compute
a return without supplying both endpoints' trading dates."""
import datetime as dt
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag.eligibility import freeze_subset
from lead_lag.returns import (
    DatedPrice,
    endpoint_return,
    portfolio_return,
    compute_R_L,
    compute_R_F,
    compute_S_L,
    compute_Y,
    compute_Momentum_F,
    assert_same_session,
    CrossSessionReturnError,
)

D = dt.date(2026, 6, 1)
D2 = dt.date(2026, 6, 2)


def test_endpoint_return_exact_formula():
    assert endpoint_return(DatedPrice(100, D), DatedPrice(110, D)) == pytest.approx(0.10)


def test_endpoint_return_raises_on_cross_session_pair():
    with pytest.raises(CrossSessionReturnError):
        endpoint_return(DatedPrice(100, D), DatedPrice(110, D2))


def test_dated_price_cannot_be_constructed_without_a_trade_date():
    """Structural guarantee: `DatedPrice` requires a `trade_date` at
    construction -- there is no way to produce a usable price value
    without one, so no caller can accidentally omit the information the
    same-session assertion needs."""
    params = inspect.signature(DatedPrice).parameters
    assert "trade_date" in params
    assert params["trade_date"].default is inspect.Parameter.empty  # mandatory, no default


def test_portfolio_return_is_arithmetic_mean_of_constituent_returns():
    frozen = freeze_subset("leader", ["E1", "E2"])
    prices_a = {"E1": DatedPrice(100, D), "E2": DatedPrice(200, D)}
    prices_b = {"E1": DatedPrice(110, D), "E2": DatedPrice(220, D)}
    assert portfolio_return(frozen, prices_a, prices_b) == pytest.approx(0.10)


def test_portfolio_return_arithmetic_mean_not_price_weighted():
    frozen = freeze_subset("leader", ["E1", "E2"])
    prices_a = {"E1": DatedPrice(10, D), "E2": DatedPrice(1000, D)}
    prices_b = {"E1": DatedPrice(11, D), "E2": DatedPrice(1000, D)}
    assert portfolio_return(frozen, prices_a, prices_b) == pytest.approx(0.05)


def test_portfolio_return_empty_subset_raises():
    frozen = freeze_subset("leader", [])
    with pytest.raises(ValueError):
        portfolio_return(frozen, {}, {})


def test_portfolio_return_raises_if_any_constituent_crosses_sessions():
    """A caller cannot bypass the assertion for just one constituent --
    every constituent's own pair is checked."""
    frozen = freeze_subset("leader", ["E1", "E2"])
    prices_a = {"E1": DatedPrice(100, D), "E2": DatedPrice(200, D)}
    prices_b = {"E1": DatedPrice(110, D), "E2": DatedPrice(220, D2)}  # E2 crosses sessions
    with pytest.raises(CrossSessionReturnError):
        portfolio_return(frozen, prices_a, prices_b)


def test_S_L_is_leader_minus_follower():
    assert compute_S_L(0.02, 0.01) == pytest.approx(0.01)


def test_R_L_R_F_Y_momentum_full_chain_and_same_session_enforced_throughout():
    leaders = freeze_subset("leader", ["L1", "L2"])
    followers = freeze_subset("follower", ["F1", "F2"])

    price_t_minus_35 = {"F1": DatedPrice(90, D), "F2": DatedPrice(190, D)}
    price_t_minus_5 = {"L1": DatedPrice(100, D), "L2": DatedPrice(200, D),
                        "F1": DatedPrice(95, D), "F2": DatedPrice(195, D)}
    price_t = {"L1": DatedPrice(105, D), "L2": DatedPrice(210, D),
               "F1": DatedPrice(96, D), "F2": DatedPrice(196, D)}
    price_t_plus_h = {"F1": DatedPrice(100, D), "F2": DatedPrice(200, D)}

    r_l = compute_R_L(leaders, price_t_minus_5, price_t)
    r_f = compute_R_F(followers, price_t_minus_5, price_t)
    s_l = compute_S_L(r_l, r_f)
    y = compute_Y(followers, price_t, price_t_plus_h)
    mom_f = compute_Momentum_F(followers, price_t_minus_35, price_t_minus_5)

    assert r_l == pytest.approx(0.05)
    assert s_l == pytest.approx(r_l - r_f)
    assert y == pytest.approx((endpoint_return(DatedPrice(96, D), DatedPrice(100, D)) +
                                endpoint_return(DatedPrice(196, D), DatedPrice(200, D))) / 2)
    assert mom_f == pytest.approx((endpoint_return(DatedPrice(90, D), DatedPrice(95, D)) +
                                    endpoint_return(DatedPrice(190, D), DatedPrice(195, D))) / 2)


@pytest.mark.parametrize("compute_fn,name", [
    (compute_R_L, "R_L"), (compute_R_F, "R_F"), (compute_Y, "Y"), (compute_Momentum_F, "Momentum_F"),
])
def test_every_higher_level_function_enforces_same_session(compute_fn, name):
    """Each of R_L, R_F, Y, Momentum_F must reject a cross-session pair
    -- not just the low-level portfolio_return primitive."""
    frozen = freeze_subset("x", ["E1"])
    prices_a = {"E1": DatedPrice(100, D)}
    prices_b = {"E1": DatedPrice(110, D2)}
    with pytest.raises(CrossSessionReturnError):
        compute_fn(frozen, prices_a, prices_b)


def test_assert_same_session_passes_when_equal():
    assert_same_session(DatedPrice(100, D), DatedPrice(110, D))  # no raise


def test_assert_same_session_raises_on_cross_session_pair():
    with pytest.raises(CrossSessionReturnError):
        assert_same_session(DatedPrice(100, D), DatedPrice(110, D2))
