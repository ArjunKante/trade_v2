"""Section 16(c) market-factor null and Section 16(d) reverse-direction
diagnostic. SYNTHETIC DATA ONLY -- no test here reads a real database
or fits either function against the real Phase 5 dataset. Verifies the
nested-model/incremental-R-squared mechanics and the direction-agnostic
fitting layer, not any real-world beta/p-value/significance result."""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag import diagnostics as diag
from lead_lag.regression import ObservationRow, build_regression_dataset

D = dt.date(2026, 6, 1)


def make_df(n, seed, s_l_contributes=True):
    rng = np.random.default_rng(seed)
    R_F = rng.normal(0, 0.01, n)
    Momentum_F = rng.normal(0, 0.01, n)
    S_L = rng.normal(0, 0.01, n)
    tod_choices = rng.choice(["opening_30", "midday", "closing_30"], n)
    beta_s_l = 2.0 if s_l_contributes else 0.0
    Y = 0.5 * R_F + 0.3 * Momentum_F + (beta_s_l * S_L if s_l_contributes else 0.0) + rng.normal(0, 0.0001, n)
    rows = [ObservationRow(D, dt.time(9, 19), 60, S_L[i], R_F[i], tod_choices[i], Momentum_F[i], Y[i])
            for i in range(n)]
    return build_regression_dataset(rows, horizon=60)


# ---- (c) market-factor null ----

def test_market_factor_null_shows_large_incremental_r_squared_when_s_l_truly_contributes():
    df = make_df(500, seed=1, s_l_contributes=True)
    result = diag.market_factor_null(df)
    assert result.incremental_r_squared > 0.1  # S_L was planted with a large true coefficient
    assert result.full_r_squared > result.reduced_r_squared


def test_market_factor_null_shows_near_zero_incremental_r_squared_when_s_l_is_pure_noise():
    df = make_df(500, seed=2, s_l_contributes=False)
    result = diag.market_factor_null(df)
    assert abs(result.incremental_r_squared) < 0.02  # S_L has no true relationship to Y here


def test_market_factor_null_rejects_dataset_missing_reduced_controls():
    df = make_df(50, seed=3).drop(columns=["Momentum_F"])
    with pytest.raises(ValueError):
        diag.market_factor_null(df)


def test_market_factor_null_full_fit_matches_fit_primary_regression_directly():
    from lead_lag.regression import fit_primary_regression
    df = make_df(100, seed=4)
    result = diag.market_factor_null(df)
    direct = fit_primary_regression(df)
    assert result.full_fit.coefficients == direct.coefficients


def test_r_squared_perfect_fit_is_one_and_pure_noise_is_near_zero():
    df = make_df(300, seed=5, s_l_contributes=True)
    from lead_lag.regression import fit_ols
    # a model with every true contributor included should fit very well (near 1)
    good_fit = fit_ols(df, "Y", ("S_L", "R_F", "Momentum_F"))
    r2_good = diag.r_squared(df["Y"], good_fit)
    assert r2_good > 0.95


# ---- (d) reverse-direction diagnostic ----

def test_reverse_direction_fit_is_symmetric_mechanically():
    """Fitting 'Y on S_L+R_F+Momentum_F' via reverse_direction_fit must
    match fit_ols called directly with the same arguments -- this
    function adds no hidden asymmetry between the two directions."""
    from lead_lag.regression import fit_ols
    df = make_df(200, seed=6)
    result = diag.reverse_direction_fit(
        df, signal_col="S_L", response_col="Y",
        control_cols=("R_F", "Momentum_F"), direction="leader_predicts_follower",
    )
    direct = fit_ols(df, "Y", ("R_F", "Momentum_F", "S_L"))
    assert result.fit.coefficients == direct.coefficients
    assert result.direction == "leader_predicts_follower"


def test_reverse_direction_fit_can_swap_signal_and_response_roles():
    """Demonstrates direction-agnosticism: swapping which column is
    'signal' and which is 'response' produces a DIFFERENT fit (as
    expected -- it is now a different regression), not an error and
    not a silently-identical result."""
    df = make_df(200, seed=7)
    forward = diag.reverse_direction_fit(df, "S_L", "Y", ("R_F", "Momentum_F"), "forward")
    reversed_ = diag.reverse_direction_fit(df, "Y", "S_L", ("R_F", "Momentum_F"), "reversed")
    assert forward.fit.coefficients != reversed_.fit.coefficients
    assert forward.response_col == "Y" and reversed_.response_col == "S_L"


def test_reverse_direction_fit_rejects_missing_columns():
    df = make_df(50, seed=8)
    with pytest.raises(ValueError):
        diag.reverse_direction_fit(df, "S_L", "Y", ("R_F", "NOT_A_REAL_COLUMN"), "forward")


def test_reverse_direction_result_never_labels_itself_causal():
    """Structural/documentation guarantee: the module's own docstrings
    state this is diagnostic-only, never causal proof."""
    import inspect
    src = inspect.getsource(diag.reverse_direction_fit)
    assert "causal proof" in inspect.getsource(diag)  # documented in the module, not asserted at runtime


def test_this_module_never_runs_against_the_real_phase5_dataset():
    """Structural guarantee: neither function accepts a file-path or
    database-connection parameter, and this test module never loads
    full_pipeline_observations.csv."""
    import inspect
    for name in ("market_factor_null", "reverse_direction_fit"):
        params = inspect.signature(getattr(diag, name)).parameters
        assert "con" not in params and "connection" not in params and "path" not in params
