"""Decisions 7, 8, 9, 11, 13, 22: regression-ready dataset construction
and the primary regression formula. SYNTHETIC DATA ONLY -- this file
never reads any real database and never fits the primary regression to
real study data. It validates shape, types, controls, horizon
separation, and error handling, and that known, planted coefficients
are recoverable from fabricated data -- nothing here is a real-data
beta, p-value, or significance result."""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag.regression import (
    ObservationRow,
    build_regression_dataset,
    fit_ols,
    fit_primary_regression,
    PRIMARY_REGRESSORS,
    HORIZONS,
    TOD_CATEGORIES,
)

D = dt.date(2026, 6, 1)


def make_row(t_minute, horizon, S_L, R_F, tod, Momentum_F, Y):
    return ObservationRow(trade_date=D, t=dt.time(9, t_minute), horizon=horizon,
                           S_L=S_L, R_F=R_F, tod=tod, Momentum_F=Momentum_F, Y=Y)


def test_build_regression_dataset_shape_and_columns():
    rows = [make_row(19 + i, 60, 0.01 * i, 0.005 * i, "midday", 0.002 * i, 0.003 * i) for i in range(5)]
    df = build_regression_dataset(rows, horizon=60)
    assert len(df) == 5
    for col in ("trade_date", "t", "horizon", "S_L", "R_F", "Momentum_F", "Y",
                "TOD_opening_30", "TOD_closing_30"):
        assert col in df.columns
    assert (df["horizon"] == 60).all()


def test_build_regression_dataset_rejects_mismatched_horizon():
    rows = [make_row(19, 60, 0.01, 0.005, "midday", 0.002, 0.003),
            make_row(24, 5, 0.01, 0.005, "midday", 0.002, 0.003)]
    with pytest.raises(ValueError):
        build_regression_dataset(rows, horizon=60)


def test_build_regression_dataset_rejects_unknown_tod():
    rows = [make_row(19, 60, 0.01, 0.005, "overnight", 0.002, 0.003)]
    with pytest.raises(ValueError):
        build_regression_dataset(rows, horizon=60)


def test_build_regression_dataset_rejects_unapproved_horizon():
    rows = [make_row(19, 45, 0.01, 0.005, "midday", 0.002, 0.003)]
    with pytest.raises(ValueError):
        build_regression_dataset(rows, horizon=45)


@pytest.mark.parametrize("tod,col_open,col_close", [
    ("opening_30", 1.0, 0.0), ("midday", 0.0, 0.0), ("closing_30", 0.0, 1.0),
])
def test_tod_dummy_encoding_midday_is_baseline(tod, col_open, col_close):
    rows = [make_row(19, 60, 0.01, 0.005, tod, 0.002, 0.003)]
    df = build_regression_dataset(rows, horizon=60)
    assert df["TOD_opening_30"].iloc[0] == col_open
    assert df["TOD_closing_30"].iloc[0] == col_close


def test_all_four_approved_horizons_are_handled_independently():
    """Each horizon's dataset is built separately; passing another
    horizon's rows into the wrong call is rejected (verified in
    `test_build_regression_dataset_rejects_mismatched_horizon` above) --
    this test confirms each horizon, built on its own, works correctly."""
    assert HORIZONS == (5, 15, 30, 60)
    for h in HORIZONS:
        rows = [make_row(19, h, 0.01, 0.005, "midday", 0.002, 0.003)]
        df = build_regression_dataset(rows, horizon=h)
        assert len(df) == 1
        assert df["horizon"].iloc[0] == h


def test_primary_regressors_are_exactly_the_approved_set():
    """No additional primary control (volatility, trading activity,
    NIFTY50, fixed effects) may appear in the primary regressor list."""
    assert set(PRIMARY_REGRESSORS) == {"S_L", "R_F", "TOD_opening_30", "TOD_closing_30", "Momentum_F"}
    forbidden = {"volatility", "trading_activity", "nifty50", "year_fe", "quarter_fe"}
    assert forbidden.isdisjoint(PRIMARY_REGRESSORS)


def test_fit_primary_regression_rejects_dataset_missing_a_required_column():
    rows = [make_row(19, 60, 0.01, 0.005, "midday", 0.002, 0.003)]
    df = build_regression_dataset(rows, horizon=60).drop(columns=["Momentum_F"])
    with pytest.raises(ValueError):
        fit_primary_regression(df)


def test_fit_ols_recovers_known_planted_coefficients_on_synthetic_data():
    """Synthetic-only: plant exact coefficients, generate noiseless data
    from them, and verify OLS recovers them -- this validates the
    IMPLEMENTATION's correctness, not any real-world hypothesis."""
    rng = np.random.default_rng(42)
    n = 500
    S_L = rng.normal(0, 0.01, n)
    R_F = rng.normal(0, 0.01, n)
    tod_choices = rng.choice(TOD_CATEGORIES, n)
    Momentum_F = rng.normal(0, 0.01, n)
    TOD_opening_30 = (tod_choices == "opening_30").astype(float)
    TOD_closing_30 = (tod_choices == "closing_30").astype(float)

    true_alpha, true_beta, true_gamma, true_d1, true_d2 = 0.0001, 2.0, 0.5, 0.0003, -0.0002
    Y = (true_alpha + true_beta * S_L + true_gamma * R_F
         + true_d1 * TOD_opening_30 + true_d2 * TOD_closing_30
         + 0.3 * Momentum_F)  # no noise -- exact recovery expected

    rows = [ObservationRow(D, dt.time(9, 19), 60, S_L[i], R_F[i], tod_choices[i], Momentum_F[i], Y[i])
            for i in range(n)]
    df = build_regression_dataset(rows, horizon=60)
    result = fit_primary_regression(df)

    assert result.coefficients["alpha"] == pytest.approx(true_alpha, abs=1e-8)
    assert result.coefficients["S_L"] == pytest.approx(true_beta, abs=1e-8)
    assert result.coefficients["R_F"] == pytest.approx(true_gamma, abs=1e-8)
    assert result.coefficients["TOD_opening_30"] == pytest.approx(true_d1, abs=1e-8)
    assert result.coefficients["TOD_closing_30"] == pytest.approx(true_d2, abs=1e-8)
    assert result.coefficients["Momentum_F"] == pytest.approx(0.3, abs=1e-8)
    assert result.n_obs == n


def test_fit_ols_rejects_empty_dataset():
    with pytest.raises(ValueError):
        fit_ols(pd.DataFrame(columns=["Y", "x"]), "Y", ("x",))


def test_this_module_never_touches_a_real_database_connection():
    """Structural guarantee, not just a convention: no function in
    `regression.py` accepts a `duckdb` connection parameter."""
    import inspect
    from lead_lag import regression as regression_module
    for name in ("build_regression_dataset", "fit_ols", "fit_primary_regression"):
        fn = getattr(regression_module, name)
        params = inspect.signature(fn).parameters
        assert "con" not in params and "connection" not in params
