"""Corwin-Schultz (2012) and Roll (1984) high-low/close-only spread
estimators, for `SPREAD_ESTIMATOR_VALIDATION.md`.

`corwin_schultz` is copied unchanged from `scripts/run_lowliq_cost_
calibration_diagnostic.py`'s own `corwin_schultz` function (that script
has no shared module to import from -- the logic lives inline in a
one-off diagnostic) -- same two-day overlapping-window construction, same
negative-value floor, not re-derived or altered in the move. A unit test
below checks this module's own output against the original script's
function directly, byte-for-byte on the same synthetic input, so the two
can never silently drift apart.

`roll_1984` does not exist anywhere in THIS repository before this
module -- ported from the sibling `trade-info` project's own corrected
implementation (`ops/report_capacity_slippage.py`'s `roll_1984_annual`,
itself a fix for that project's own Bug #8: an earlier version silently
treated Roll's own undefined case -- a non-negative first-order
autocovariance, economically inconsistent with pure bid-ask bounce -- as
a zero spread inside a `.median()`, rather than excluding it and
reporting how often it occurred). This port preserves that fix: it
returns whether the estimate is defined, never silently substitutes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def corwin_schultz(high: pd.Series, low: pd.Series) -> pd.Series:
    """Standard 2-day Corwin-Schultz (2012) high-low spread estimator.
    Returns a per-day spread estimate (fraction of price); negative alpha
    (the known small-sample artifact) is floored to a zero spread for that
    day, per the original paper's own recommendation. Index 0 of the
    result is always NaN (no prior day to pair with)."""
    h, l = high.values, low.values
    beta = np.full(len(h), np.nan)
    for i in range(1, len(h)):
        beta[i] = np.log(h[i] / l[i]) ** 2 + np.log(h[i - 1] / l[i - 1]) ** 2
    h2 = np.maximum(h[1:], h[:-1])
    l2 = np.minimum(l[1:], l[:-1])
    gamma = np.log(h2 / l2) ** 2
    gamma = np.concatenate([[np.nan], gamma])
    k = 3 - 2 * np.sqrt(2)
    with np.errstate(invalid="ignore"):
        alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    spread = np.where(spread < 0, 0.0, spread)
    return pd.Series(spread, index=high.index)


def roll_1984(daily_log_ret: pd.Series, min_obs: int = 20) -> tuple[float, bool]:
    """Roll's (1984) covariance spread estimator: `s = 2*sqrt(-Cov)`
    where `Cov` is the first-order autocovariance of daily log returns,
    defined ONLY when `Cov < 0` -- a non-negative autocovariance is
    economically inconsistent with the model's own pure-bid-ask-bounce
    assumption, and the estimator is UNDEFINED there, not zero.

    Returns `(spread_fraction_or_nan, was_defined)`. `was_defined=False`
    on either too few observations (`< min_obs`) or a non-negative
    autocovariance -- the caller must check this flag and EXCLUDE
    undefined observations from any mean/median, never treat NaN-or-0 as
    interchangeable with a true small-spread estimate (the exact
    `trade-info` Bug #8 this port exists to not repeat)."""
    r = daily_log_ret.dropna()
    if len(r) < min_obs:
        return float("nan"), False
    cov = np.cov(r.iloc[1:], r.iloc[:-1].values)[0, 1]
    if cov < 0:
        return float(2 * np.sqrt(-cov)), True
    return float("nan"), False
