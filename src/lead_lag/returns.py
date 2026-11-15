"""Exact-endpoint-price return convention (Decision 13) and the
portfolio-level estimand (`R_L(t)`, `R_F(t)`, `S_L(t)`, `Y(t,h)`,
`Momentum_F(t)`).

`r_i(a,b) = P_i(b)/P_i(a) - 1` per frozen-eligible constituent; arithmetic
mean across constituents for the portfolio-level quantity. Price return,
dividends excluded. Applied identically to all four quantities -- no
quantity uses a different endpoint convention.

**Correction, this revision**: the prior implementation accepted plain
`dict[str, float]` prices with an OPTIONAL pair of `trade_dates_a`/
`trade_dates_b` dictionaries -- a caller could omit them and the
same-session assertion simply never ran. This revision removes that
path entirely: every price is now represented by `DatedPrice(price,
trade_date)`, so a caller cannot provide a price without also providing
the trading date it came from, and `portfolio_return` (and therefore
every one of `R_L`, `R_F`, `Y`, `Momentum_F`) unconditionally asserts
same-session membership for every constituent, every time -- there is
no parameter to omit that would skip it.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .eligibility import FrozenSubset


class CrossSessionReturnError(ValueError):
    """Raised when a same-session return's two endpoints do not share a
    `trade_date` -- a same-session guarantee violation (Decision 14's
    conditional dependency)."""


@dataclass(frozen=True)
class DatedPrice:
    """A price that always carries the trading date it was observed on.
    This is the ONLY accepted price representation in this module --
    there is no code path that accepts a bare float, so the same-session
    assertion below can never be bypassed by omission."""
    price: float
    trade_date: dt.date


def assert_same_session(a: DatedPrice, b: DatedPrice) -> None:
    if a.trade_date != b.trade_date:
        raise CrossSessionReturnError(
            f"endpoints on different trade_dates: {a.trade_date} vs {b.trade_date}"
        )


def endpoint_return(price_a: DatedPrice, price_b: DatedPrice) -> float:
    """Decision 13: `r(a,b) = P(b)/P(a) - 1`. Mandatorily asserts both
    endpoints share a `trade_date` before computing anything."""
    assert_same_session(price_a, price_b)
    return price_b.price / price_a.price - 1.0


def portfolio_return(frozen: FrozenSubset,
                      prices_a: dict[str, DatedPrice],
                      prices_b: dict[str, DatedPrice]) -> float:
    """Arithmetic equal-weight mean of each frozen constituent's own
    `r_i(a,b)`. Requires every member of `frozen` to have both
    `DatedPrice` endpoints; `endpoint_return` asserts same-session
    membership for each one -- unconditionally, with no way to opt out.
    Callers must not call this on a subset that failed Stage A/Stage B --
    those checks happen before this function, not inside it."""
    if frozen.n == 0:
        raise ValueError("portfolio_return called on an empty frozen subset")
    rets = [endpoint_return(prices_a[e], prices_b[e]) for e in frozen.members]
    return sum(rets) / len(rets)


def compute_R_L(frozen_leaders: FrozenSubset,
                 price_t_minus_5: dict[str, DatedPrice],
                 price_t: dict[str, DatedPrice]) -> float:
    """Leader portfolio return over the signal window `[t-5, t]`."""
    return portfolio_return(frozen_leaders, price_t_minus_5, price_t)


def compute_R_F(frozen_followers: FrozenSubset,
                 price_t_minus_5: dict[str, DatedPrice],
                 price_t: dict[str, DatedPrice]) -> float:
    """Follower portfolio return over the same signal window `[t-5, t]`."""
    return portfolio_return(frozen_followers, price_t_minus_5, price_t)


def compute_S_L(r_l: float, r_f: float) -> float:
    """`S_L(t) = R_L(t) - R_F(t)`."""
    return r_l - r_f


def compute_Y(frozen_followers: FrozenSubset,
              price_t: dict[str, DatedPrice],
              price_t_plus_h: dict[str, DatedPrice]) -> float:
    """Follower portfolio forward return over horizon `h`, using the
    SAME frozen follower subset as `R_F`/`Momentum_F` (step 6: one
    shared portfolio identity per observation)."""
    return portfolio_return(frozen_followers, price_t, price_t_plus_h)


def compute_Momentum_F(frozen_followers: FrozenSubset,
                        price_t_minus_35: dict[str, DatedPrice],
                        price_t_minus_5: dict[str, DatedPrice]) -> float:
    """Follower portfolio return over the disjoint earlier window
    `[t-35, t-5]`, same frozen follower subset."""
    return portfolio_return(frozen_followers, price_t_minus_35, price_t_minus_5)
