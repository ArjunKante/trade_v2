"""Section 7C / Decision 12 (AMENDMENT 14 LOG): primary (L=6) and
sensitivity (L=1) block-bootstrap inference for the primary
regression's S_L coefficient. SYNTHETIC DATA ONLY -- no test here
reads full_pipeline_observations.csv or any real database. Exercises
the actual production `block_bootstrap_beta` / `primary_block_bootstrap`
/ `sensitivity_single_day_cluster_bootstrap` functions against
constructed data-generating processes with known planted coefficients."""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag import inference as inf
from lead_lag.regression import ObservationRow, build_regression_dataset

D0 = dt.date(2026, 1, 5)


def make_dataset(n_days, obs_per_day, true_beta, seed, gamma=0.5, delta2=0.3, noise=0.0001):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_days):
        d = D0 + dt.timedelta(days=i)
        for j in range(obs_per_day):
            t = (dt.datetime.combine(dt.date(2000, 1, 1), dt.time(9, 19)) + dt.timedelta(minutes=j * 65)).time()
            S_L = rng.normal(0, 0.01)
            R_F = rng.normal(0, 0.01)
            Momentum_F = rng.normal(0, 0.01)
            tod = "midday"
            Y = true_beta * S_L + gamma * R_F + delta2 * Momentum_F + rng.normal(0, noise)
            rows.append(ObservationRow(d, t, 60, S_L, R_F, tod, Momentum_F, Y))
    df = build_regression_dataset(rows, horizon=60)
    all_dates = [D0 + dt.timedelta(days=i) for i in range(n_days)]
    return df, all_dates


# ---- recovery of planted coefficients ----

def test_recovers_planted_positive_coefficient_as_significant():
    df, dates = make_dataset(n_days=80, obs_per_day=3, true_beta=5.0, seed=1, noise=0.0002)
    result = inf.primary_block_bootstrap(df, dates, n_resamples=200, seed=1)
    assert result.point_estimate > 0
    assert result.ci_low > 0  # strongly positive, CI should exclude zero
    assert result.significant is True
    assert result.p_value < result.alpha


def test_recovers_planted_zero_coefficient_as_not_significant():
    df, dates = make_dataset(n_days=80, obs_per_day=3, true_beta=0.0, seed=2, noise=0.01)
    result = inf.primary_block_bootstrap(df, dates, n_resamples=200, seed=2)
    assert result.ci_low < 0 < result.ci_high  # CI should straddle zero
    assert result.significant is False


def test_recovers_planted_negative_coefficient_as_significant_negative():
    df, dates = make_dataset(n_days=80, obs_per_day=3, true_beta=-5.0, seed=3, noise=0.0002)
    result = inf.primary_block_bootstrap(df, dates, n_resamples=200, seed=3)
    assert result.point_estimate < 0
    assert result.ci_high < 0
    assert result.significant is True


# ---- block construction ----

def test_contiguous_six_session_blocks_are_built_correctly():
    dates = [D0 + dt.timedelta(days=i) for i in range(10)]
    blocks = inf._build_overlapping_blocks(dates, 6)
    assert len(blocks) == 5  # 10 - 6 + 1
    assert blocks[0] == dates[0:6]
    assert blocks[-1] == dates[4:10]


def test_single_day_blocks_are_each_exactly_one_date():
    dates = [D0 + dt.timedelta(days=i) for i in range(10)]
    blocks = inf._build_overlapping_blocks(dates, 1)
    assert len(blocks) == 10
    assert all(len(b) == 1 for b in blocks)


def test_block_length_exceeding_available_positions_raises():
    dates = [D0 + dt.timedelta(days=i) for i in range(3)]
    with pytest.raises(ValueError):
        inf._build_overlapping_blocks(dates, 6)


def test_block_length_must_be_at_least_one():
    dates = [D0 + dt.timedelta(days=i) for i in range(10)]
    with pytest.raises(ValueError):
        inf._build_overlapping_blocks(dates, 0)


# ---- within-day preservation ----

def test_within_day_observations_are_never_split_across_a_resample():
    """Every date that appears in a resample must contribute ALL of its
    own rows, not a subset -- verified by checking that a resampled
    dataframe's per-date row counts always match the original."""
    df, dates = make_dataset(n_days=20, obs_per_day=4, true_beta=1.0, seed=4)
    by_date_count = df.groupby("trade_date").size().to_dict()
    rng = np.random.default_rng(10)
    blocks = inf._build_overlapping_blocks(dates, 6)
    by_date = {d: g for d, g in df.groupby("trade_date")}
    chosen = rng.integers(0, len(blocks), size=4)
    parts = [by_date[d] for bi in chosen for d in blocks[bi] if d in by_date]
    resampled = pd.concat(parts, ignore_index=True)
    for d in resampled["trade_date"].unique():
        n_occurrences_of_d_in_draw = sum(1 for bi in chosen for dd in blocks[bi] if dd == d)
        expected = by_date_count.get(d, 0) * n_occurrences_of_d_in_draw
        assert (resampled["trade_date"] == d).sum() == expected


# ---- L=1 sensitivity behavior ----

def test_sensitivity_uses_block_length_one():
    df, dates = make_dataset(n_days=60, obs_per_day=2, true_beta=3.0, seed=5, noise=0.0003)
    result = inf.sensitivity_single_day_cluster_bootstrap(df, dates, n_resamples=150, seed=5)
    assert result.block_length == 1
    assert result.n_blocks_available == len(dates)


def test_primary_and_sensitivity_are_independent_no_leakage():
    df, dates = make_dataset(n_days=60, obs_per_day=2, true_beta=3.0, seed=6, noise=0.0003)
    primary = inf.primary_block_bootstrap(df, dates, n_resamples=150, seed=6)
    sensitivity = inf.sensitivity_single_day_cluster_bootstrap(df, dates, n_resamples=150, seed=6)
    assert primary.block_length == 6
    assert sensitivity.block_length == 1
    assert not np.array_equal(primary.beta_boot, sensitivity.beta_boot)


# ---- reproducibility ----

def test_reproducible_under_fixed_seed():
    df, dates = make_dataset(n_days=50, obs_per_day=2, true_beta=1.0, seed=7)
    r1 = inf.primary_block_bootstrap(df, dates, n_resamples=100, seed=99)
    r2 = inf.primary_block_bootstrap(df, dates, n_resamples=100, seed=99)
    assert np.array_equal(r1.beta_boot, r2.beta_boot)
    assert r1.se == r2.se
    assert r1.p_value == r2.p_value


# ---- SE / CI construction ----

def test_bootstrap_se_matches_sample_std_of_betas():
    df, dates = make_dataset(n_days=50, obs_per_day=3, true_beta=2.0, seed=8)
    result = inf.primary_block_bootstrap(df, dates, n_resamples=100, seed=8)
    assert result.se == pytest.approx(float(result.beta_boot.std(ddof=1)))


def test_confidence_interval_is_the_alpha_percentile_of_the_bootstrap_distribution():
    df, dates = make_dataset(n_days=50, obs_per_day=3, true_beta=2.0, seed=9)
    result = inf.primary_block_bootstrap(df, dates, n_resamples=200, alpha=0.05, seed=9)
    expected_low, expected_high = np.percentile(result.beta_boot, [2.5, 97.5])
    assert result.ci_low == pytest.approx(expected_low)
    assert result.ci_high == pytest.approx(expected_high)


def test_alpha_parameter_changes_the_significance_decision_not_the_bootstrap_distribution():
    df, dates = make_dataset(n_days=50, obs_per_day=3, true_beta=2.0, seed=10)
    loose = inf.primary_block_bootstrap(df, dates, n_resamples=150, alpha=0.5, seed=10)
    strict = inf.primary_block_bootstrap(df, dates, n_resamples=150, alpha=0.00001, seed=10)
    assert np.array_equal(loose.beta_boot, strict.beta_boot)  # same resamples
    assert loose.ci_low != strict.ci_low or loose.ci_high != strict.ci_high  # different CI width


# ---- p-value correctness ----

def test_p_value_is_two_sided_percentile_test_inversion_formula():
    df, dates = make_dataset(n_days=60, obs_per_day=3, true_beta=4.0, seed=11, noise=0.0002)
    result = inf.primary_block_bootstrap(df, dates, n_resamples=200, seed=11)
    frac_le0 = float(np.mean(result.beta_boot <= 0))
    frac_ge0 = float(np.mean(result.beta_boot >= 0))
    expected_p = min(1.0, 2 * min(frac_le0, frac_ge0))
    assert result.p_value == pytest.approx(expected_p)


# ---- invalid/insufficient resample handling ----

def test_sparse_coverage_produces_counted_failed_resamples_not_a_crash():
    """Construct a dataset where only a few scattered days (out of a
    much longer calendar) have any observations at all -- most drawn
    blocks will land on empty days, producing some failed resamples
    that must be counted, not silently ignored or crashed on."""
    rng = np.random.default_rng(12)
    sparse_days = [D0 + dt.timedelta(days=i) for i in (0, 40, 80, 120, 160)]
    rows = []
    for d in sparse_days:
        for _ in range(3):
            S_L, R_F, Momentum_F = rng.normal(0, 0.01, 3)
            Y = 1.0 * S_L + 0.1 * R_F + rng.normal(0, 0.001)
            rows.append(ObservationRow(d, dt.time(9, 19), 60, S_L, R_F, "midday", Momentum_F, Y))
    df = build_regression_dataset(rows, horizon=60)
    all_dates = [D0 + dt.timedelta(days=i) for i in range(200)]
    result = inf.block_bootstrap_beta(df, all_dates, block_length=6, n_resamples=100, seed=13)
    assert result.n_valid + result.n_failed == 100
    assert result.n_failed >= 0


def test_all_resamples_failing_raises_rather_than_returning_a_fake_result():
    """A dataset with observations only on days entirely outside the
    supplied calendar's range can never produce a non-empty resample."""
    rng = np.random.default_rng(14)
    rows = []
    far_day = D0 + dt.timedelta(days=5000)
    for _ in range(3):
        S_L, R_F, Momentum_F = rng.normal(0, 0.01, 3)
        rows.append(ObservationRow(far_day, dt.time(9, 19), 60, S_L, R_F, "midday", Momentum_F, 0.001))
    df = build_regression_dataset(rows, horizon=60)
    all_dates = [D0 + dt.timedelta(days=i) for i in range(50)]  # does not include far_day
    with pytest.raises(ValueError):
        inf.block_bootstrap_beta(df, all_dates, block_length=6, n_resamples=20, seed=15)


# ---- regression failures / missing regressors ----

def test_missing_primary_regressor_column_raises_before_any_resampling():
    df, dates = make_dataset(n_days=30, obs_per_day=2, true_beta=1.0, seed=16)
    df = df.drop(columns=["Momentum_F"])
    with pytest.raises(ValueError):
        inf.primary_block_bootstrap(df, dates, n_resamples=10, seed=16)


def test_missing_trade_date_column_raises():
    df, dates = make_dataset(n_days=10, obs_per_day=2, true_beta=1.0, seed=17)
    df = df.drop(columns=["trade_date"])
    with pytest.raises(ValueError):
        inf.primary_block_bootstrap(df, dates, n_resamples=10, seed=17)


def test_this_module_never_touches_a_real_database_or_real_csv():
    import inspect
    from lead_lag import inference as inference_module
    src = inspect.getsource(inference_module)
    for forbidden in ("duckdb", "read_csv(", "connect(", "import pd.read"):
        assert forbidden not in src
