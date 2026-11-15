"""Regression-ready dataset construction and the approved primary
regression formula (Decisions 7, 8, 9, 11, 13, 22).

```
Y(t,h) = alpha + beta*S_L(t) + gamma*R_F(t) + delta_1*TOD(t) + delta_2*Momentum_F(t) + epsilon(t,h)
```

Primary controls, exactly: `R_F(t)`, `TOD(t)` (opening_30/midday/closing_30,
`midday` as the omitted baseline category), `Momentum_F(t)`. No other
variable is added to the primary specification -- trailing realized
volatility, coarse trading activity, prior-day NIFTY50, and year/quarter
fixed effects remain sensitivity/diagnostic-only (Decisions 7, 8, 9) and
are deliberately NOT parameters of `fit_primary_regression` below.

**Three distinct things, kept separate, per this module's own design**:

1. **Regression-ready dataset construction** (`build_regression_dataset`) --
   pure data assembly from already-computed per-observation quantities
   (`S_L`, `R_F`, `TOD`, `Momentum_F`, `Y`) into one row per `(trade_date,
   t, h)`, one dataset per horizon (Decision 7/Section 10: horizons are
   never pooled across each other in the primary specification).
2. **Regression implementation** (`fit_ols`, `fit_primary_regression`) --
   ordinary-least-squares coefficient estimation via `numpy.linalg.lstsq`
   (statsmodels is listed in `requirements.txt` but is not installed in
   this environment -- confirmed by direct import attempt -- so this
   module does not depend on it, to avoid an unverifiable dependency).
   **No standard errors, day-clustering, or significance testing is
   implemented here** -- that is Phase 6/Decision-12 territory
   (`box_theory.inference.day_clustered_bootstrap`, explicitly deferred),
   out of scope for this implementation-only pass.
3. **Running the primary empirical gate** -- NOT implemented, NOT
   invoked anywhere in this module or its tests. `fit_primary_regression`
   is exercised only against synthetic fixtures with known, planted
   coefficients (see `tests/test_lead_lag_regression.py`) to verify the
   formula and recovery mechanics are correct -- never against real
   study data, and no beta/p-value/significance from real data is ever
   computed or inspected by this module or anything that calls it in
   this codebase.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

HORIZONS = (5, 15, 30, 60)  # Decision 7/Section 10 -- never pooled across horizons
TOD_CATEGORIES = ("opening_30", "midday", "closing_30")
TOD_BASELINE = "midday"  # omitted category


@dataclass(frozen=True)
class ObservationRow:
    """One fully-resolved observation: a single `(trade_date, t, h)`
    slot that passed Stage A (both tiers) and Stage B (follower side,
    this horizon) -- i.e. exactly what Decisions 17/19/20 already
    computed. This module does not itself decide eligibility; it only
    assembles already-eligible rows into a dataset."""
    trade_date: dt.date
    t: dt.time
    horizon: int
    S_L: float
    R_F: float
    tod: str
    Momentum_F: float
    Y: float


def build_regression_dataset(rows: list[ObservationRow], horizon: int) -> pd.DataFrame:
    """Assemble one horizon's regression-ready dataset. Raises if any
    row's `horizon` does not match, or if `tod` is not one of the three
    approved categories -- this function does not silently drop or
    coerce malformed rows."""
    if horizon not in HORIZONS:
        raise ValueError(f"horizon {horizon} is not one of the approved horizons {HORIZONS}")
    filtered = [r for r in rows if r.horizon == horizon]
    mismatched = [r for r in rows if r.horizon != horizon]
    if mismatched:
        raise ValueError(
            f"{len(mismatched)} row(s) have a horizon other than {horizon}; "
            f"horizons must never be pooled in one dataset"
        )
    for r in filtered:
        if r.tod not in TOD_CATEGORIES:
            raise ValueError(f"unknown TOD category: {r.tod!r}")

    df = pd.DataFrame([{
        "trade_date": r.trade_date, "t": r.t, "horizon": r.horizon,
        "S_L": r.S_L, "R_F": r.R_F, "Momentum_F": r.Momentum_F, "Y": r.Y,
        "TOD_opening_30": 1.0 if r.tod == "opening_30" else 0.0,
        "TOD_closing_30": 1.0 if r.tod == "closing_30" else 0.0,
    } for r in filtered])
    return df


PRIMARY_REGRESSORS = ("S_L", "R_F", "TOD_opening_30", "TOD_closing_30", "Momentum_F")


@dataclass(frozen=True)
class OLSResult:
    coefficients: dict[str, float]  # includes "alpha" (intercept)
    n_obs: int
    residuals: np.ndarray
    design_columns: tuple[str, ...]


def fit_ols(df: pd.DataFrame, y_col: str, x_cols: tuple[str, ...]) -> OLSResult:
    """Plain OLS via `numpy.linalg.lstsq` -- `y = alpha + X @ coef + eps`.
    No inference (SE/p-values/significance) is computed -- deliberately
    out of scope for this implementation-only pass."""
    if df.empty:
        raise ValueError("fit_ols called on an empty dataset")
    y = df[y_col].to_numpy(dtype=float)
    X = df[list(x_cols)].to_numpy(dtype=float)
    X_design = np.column_stack([np.ones(len(df)), X])
    coef, *_ = np.linalg.lstsq(X_design, y, rcond=None)
    fitted = X_design @ coef
    residuals = y - fitted
    coefficients = {"alpha": float(coef[0])}
    for name, c in zip(x_cols, coef[1:]):
        coefficients[name] = float(c)
    return OLSResult(coefficients=coefficients, n_obs=len(df), residuals=residuals,
                      design_columns=("alpha", *x_cols))


def fit_primary_regression(df: pd.DataFrame) -> OLSResult:
    """`Y(t,h) = alpha + beta*S_L(t) + gamma*R_F(t) + delta_1*TOD(t) + delta_2*Momentum_F(t) + epsilon`,
    using exactly the approved primary controls
    (`PRIMARY_REGRESSORS`) -- no other regressor is added. `df` must
    already be one horizon's dataset from `build_regression_dataset`;
    this function does not itself fetch, filter, or pool data across
    horizons."""
    missing = [c for c in PRIMARY_REGRESSORS if c not in df.columns]
    if missing:
        raise ValueError(f"dataset missing required primary-regressor columns: {missing}")
    if "Y" not in df.columns:
        raise ValueError("dataset missing the dependent variable column 'Y'")
    return fit_ols(df, "Y", PRIMARY_REGRESSORS)
