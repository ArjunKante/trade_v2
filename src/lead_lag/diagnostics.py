"""Section 16(c) market-factor null and Section 16(d) reverse-direction
diagnostic -- both alternative/nested regression specifications, not
randomized-sampling null machinery (that is `nulls.py`).

**Primary-outcome firewall, both functions**: `market_factor_null`
literally fits the full, `S_L`-including primary model (that is the
whole point of a nested-model comparison -- there is no way to ask
"does adding S_L improve on the controls-only model" without fitting
the model that includes `S_L`). `reverse_direction_fit` is direction-
agnostic and can be used for either the primary or the reversed
direction. **Neither function is called against the real Phase 5
dataset anywhere in this codebase** -- both are exercised only against
synthetic fixtures in `tests/test_lead_lag_diagnostics.py`. Running
either against the real dataset requires the separate, explicit
real-data authorization the governing documents and the task
instructions both require, which has not been given.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .regression import PRIMARY_REGRESSORS, OLSResult, fit_ols, fit_primary_regression


def r_squared(y: pd.Series, fit: OLSResult) -> float:
    y_arr = y.to_numpy(dtype=float)
    ss_res = float(np.sum(fit.residuals ** 2))
    ss_tot = float(np.sum((y_arr - y_arr.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


# ---------------------------------------------------------------------------
# (c) Market-factor null: nested-model comparison, X(j,t)-only vs. the
# full (S_L-including) primary model.
# ---------------------------------------------------------------------------

REDUCED_CONTROLS = ("R_F", "TOD_opening_30", "TOD_closing_30", "Momentum_F")


@dataclass(frozen=True)
class MarketFactorNullResult:
    reduced_fit: OLSResult  # X(j,t) only -- no S_L
    full_fit: OLSResult  # the full primary model, including S_L
    reduced_r_squared: float
    full_r_squared: float
    incremental_r_squared: float  # full - reduced; the "beyond the controls" contribution


def market_factor_null(df: pd.DataFrame) -> MarketFactorNullResult:
    """Section 16(c): "Can the same prediction be explained by market
    and sector returns alone? Test whether the leader signal provides
    incremental information after controlling for [...] relevant
    volatility and liquidity conditions." Implemented here, per
    Section 16(c)'s own text ("nested-model comparison, X(j,t) only vs.
    full model"), as the incremental R-squared `S_L` contributes beyond
    `REDUCED_CONTROLS` (`R_F`, `TOD`, `Momentum_F` -- this family's
    existing, approved `X(j,t)` control set, Decisions 7/8/9).

    **This function fits the full model, which includes `S_L` --** it
    is NOT safe to run against the real dataset without separate,
    explicit authorization; see module docstring. It is a diagnostic
    only: Section 9 ("What this construction can and cannot rule out")
    already discloses that this family has no independent intraday
    market/sector index, so this nested comparison can rule out "fully
    redundant with the existing controls" but cannot establish that
    `S_L` is not itself a proxy for an unmeasured market/sector factor.
    """
    missing = [c for c in REDUCED_CONTROLS if c not in df.columns]
    if missing:
        raise ValueError(f"dataset missing required reduced-model columns: {missing}")
    reduced_fit = fit_ols(df, "Y", REDUCED_CONTROLS)
    full_fit = fit_primary_regression(df)
    r2_reduced = r_squared(df["Y"], reduced_fit)
    r2_full = r_squared(df["Y"], full_fit)
    return MarketFactorNullResult(
        reduced_fit=reduced_fit, full_fit=full_fit,
        reduced_r_squared=r2_reduced, full_r_squared=r2_full,
        incremental_r_squared=r2_full - r2_reduced,
    )


# ---------------------------------------------------------------------------
# (d) Reverse-direction diagnostic: direction-agnostic fitting layer.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReverseDirectionResult:
    direction: str  # free-form label, e.g. "leader_predicts_follower" | "follower_predicts_leader"
    fit: OLSResult
    r_squared: float
    signal_col: str
    response_col: str


def reverse_direction_fit(df: pd.DataFrame, signal_col: str, response_col: str,
                            control_cols: tuple[str, ...], direction: str) -> ReverseDirectionResult:
    """Section 16(d): "Investigate whether the apparent relationship is
    directional. Test whether leaders predict laggards [or] laggards
    predict leaders [...] both directions reported regardless of
    result." This is a DIAGNOSTIC, never causal proof either way
    (Section 16(d)'s own framing: "not permission to select whichever
    direction performs best").

    This function is deliberately DIRECTION-AGNOSTIC: it is the exact
    same OLS machinery (`fit_ols`) as the primary model, just
    parameterized so the caller supplies which column is the signal,
    which is the response, and which columns are controls. It does
    **not** construct a reversed dataset itself.

    **Known, reported ambiguity (per task instruction, not silently
    resolved)**: the governing documents (Section 16(d), master spec
    Part 8) state the REQUIREMENT ("test both directions") but do not
    specify the reversed direction's exact control-variable
    construction -- i.e. whether a genuine "laggards predict leaders"
    regression should control for the leader's own analogous momentum
    (`Momentum_L`, mirroring `Momentum_F`'s role) and the leader
    portfolio's own signal-window return (mirroring `R_F`'s role), both
    of which would need to be newly computed by the Phase 5 pipeline (
    neither exists today -- the pipeline only computes follower-side
    `Y`/`Momentum_F`). Building that reversed dataset is a genuine,
    not-yet-made methodology decision, not resolved by this function,
    which only provides the fitting/reporting layer once such a dataset
    exists."""
    missing = [c for c in (*control_cols, signal_col, response_col) if c not in df.columns]
    if missing:
        raise ValueError(f"dataset missing required columns for this direction: {missing}")
    fit = fit_ols(df, response_col, (*control_cols, signal_col))
    r2 = r_squared(df[response_col], fit)
    return ReverseDirectionResult(
        direction=direction, fit=fit, r_squared=r2,
        signal_col=signal_col, response_col=response_col,
    )
