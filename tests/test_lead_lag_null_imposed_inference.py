"""Vectorized null-imposed, anchor-matched residual block bootstrap
(the S_L=0 hypothesis-test p-value procedure). SYNTHETIC DATA ONLY --
no test here reads a real database or CSV, or fits against real data.
Exercises the actual production `null_imposed_block_bootstrap` /
`primary_null_imposed_bootstrap` / `sensitivity_null_imposed_bootstrap`
functions in `src/lead_lag/inference.py`."""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag import inference as inf
from lead_lag.regression import ObservationRow, build_regression_dataset
from lead_lag.schedule import non_overlapping_schedule, tod_bucket

D0 = dt.date(2026, 1, 5)
ANCHORS_H60 = non_overlapping_schedule(60)  # the real, approved 5 fixed anchors


def make_dataset(n_days, true_beta, seed, drop_prob=0.0, day_ar_phi=0.0,
                   day_sd=0.002, idio_sd=0.0015, gamma=0.5, delta2=0.3):
    """Full h=60 schedule (5 fixed anchors/day); each (day, anchor) is
    independently dropped with probability `drop_prob` to mimic Stage
    A/B discards and exercise the anchor-matching exclusion path."""
    rng = np.random.default_rng(seed)
    day_effect = np.zeros(n_days)
    if day_ar_phi > 0:
        day_effect[0] = rng.normal(0, day_sd)
        for i in range(1, n_days):
            day_effect[i] = day_ar_phi * day_effect[i - 1] + rng.normal(0, day_sd * np.sqrt(1 - day_ar_phi ** 2))
    rows = []
    for i in range(n_days):
        d = D0 + dt.timedelta(days=i)
        for t in ANCHORS_H60:
            if drop_prob > 0 and rng.random() < drop_prob:
                continue
            S_L = rng.normal(0, 0.01)
            R_F = rng.normal(0, 0.01)
            Momentum_F = rng.normal(0, 0.01)
            Y = true_beta * S_L + gamma * R_F + delta2 * Momentum_F + day_effect[i] + rng.normal(0, idio_sd)
            rows.append(ObservationRow(d, t, 60, S_L, R_F, tod_bucket(t), Momentum_F, Y))
    df = build_regression_dataset(rows, horizon=60)
    all_dates = [D0 + dt.timedelta(days=i) for i in range(n_days)]
    return df, all_dates


# ---- planted-coefficient recovery ----

def test_positive_planted_beta_gives_small_p_value():
    df, dates = make_dataset(120, true_beta=8.0, seed=1, idio_sd=0.0003)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=2000, seed=1)
    assert result.p_value < 0.01
    assert np.median(result.beta_star) == pytest.approx(0.0, abs=5.0)  # null-imposed: centered near 0, NOT near beta_hat


def test_zero_planted_beta_gives_large_p_value_typically():
    df, dates = make_dataset(120, true_beta=0.0, seed=2, idio_sd=0.002)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=2000, seed=2)
    assert result.p_value > 0.05  # not guaranteed every seed, but a reasonable sanity check


def test_negative_planted_beta_gives_small_p_value_two_sided():
    df, dates = make_dataset(120, true_beta=-8.0, seed=3, idio_sd=0.0003)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=2000, seed=3)
    assert result.p_value < 0.01  # two-sided test: large |beta_hat| rejects regardless of sign


# ---- block construction ----

def test_l6_uses_primary_block_length():
    df, dates = make_dataset(60, true_beta=1.0, seed=4)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=500, seed=4)
    assert result.block_length == 6


def test_l1_uses_sensitivity_block_length():
    df, dates = make_dataset(60, true_beta=1.0, seed=5)
    result = inf.sensitivity_null_imposed_bootstrap(df, dates, n_resamples=500, seed=5)
    assert result.block_length == 1
    assert result.n_blocks_available == len(dates)


# ---- anchor-keyed matching ----

def test_full_coverage_dataset_has_perfect_match_rate():
    """With no dropped observations, every donor day has every anchor
    -- match rate must be exactly 1.0 for every resample."""
    df, dates = make_dataset(60, true_beta=1.0, seed=6, drop_prob=0.0)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=300, seed=6)
    assert result.match_rate_min == pytest.approx(1.0)
    assert result.match_rate_mean == pytest.approx(1.0)


def test_missing_donor_and_target_anchors_reduce_match_rate_below_one():
    df, dates = make_dataset(80, true_beta=1.0, seed=7, drop_prob=0.2)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=500, seed=7)
    assert result.match_rate_mean < 1.0
    assert result.match_rate_mean > 0.0


def test_match_rate_roughly_tracks_the_drop_probability():
    """At independent per-anchor drop rate p, expected match rate
    (donor present AND target present, conditioned on target present)
    is approximately (1-p) -- loose sanity bound, not an exact claim."""
    df, dates = make_dataset(150, true_beta=0.0, seed=8, drop_prob=0.25)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=1000, seed=8)
    assert 0.55 < result.match_rate_mean < 0.95


def test_zero_drop_prob_never_excludes_any_observation_via_anchor_mismatch():
    df, dates = make_dataset(40, true_beta=2.0, seed=9, drop_prob=0.0)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=200, seed=9)
    assert np.all(result.retained_row_counts == result.n_target_total)


# ---- unequal daily observation counts / rank deficiency ----

def test_very_high_drop_probability_runs_without_crashing_and_counts_are_consistent():
    """At 85% drop, even the REAL (unresampled) design may itself lose
    extra rank (e.g. too few opening_30 rows survive) on top of the
    permanent h=60 TOD_closing_30 baseline -- whether that produces
    additional per-resample failures depends on the random draw, so
    this test only asserts the mechanism stays self-consistent and
    never crashes, not that failures must occur."""
    df, dates = make_dataset(100, true_beta=1.0, seed=10, drop_prob=0.85)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=500, seed=10)
    assert result.n_valid + result.n_failed_total == 500
    assert result.n_failed_total == result.n_failed_empty_or_unmatched + result.n_failed_rank_deficient


def test_failed_resamples_are_counted_not_silently_dropped_from_the_total():
    df, dates = make_dataset(60, true_beta=1.0, seed=11, drop_prob=0.3)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=400, seed=11)
    assert result.n_resamples_requested == 400
    assert result.n_valid + result.n_failed_empty_or_unmatched + result.n_failed_rank_deficient == 400


# ---- reproducibility ----

def test_reproducible_under_fixed_seed():
    df, dates = make_dataset(80, true_beta=1.0, seed=12)
    r1 = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=1000, seed=77)
    r2 = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=1000, seed=77)
    assert np.array_equal(r1.beta_star, r2.beta_star)
    assert r1.p_value == r2.p_value
    assert np.array_equal(r1.retained_row_counts, r2.retained_row_counts)


# ---- finite-sample p-value formula ----

def test_p_value_formula_matches_direct_computation():
    df, dates = make_dataset(80, true_beta=3.0, seed=13, idio_sd=0.0005)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=1500, seed=13)
    expected = (1 + np.sum(np.abs(result.beta_star) >= abs(result.beta_hat))) / (1 + result.n_valid)
    assert result.p_value == pytest.approx(expected)


def test_p_value_is_never_zero_due_to_finite_sample_correction():
    df, dates = make_dataset(100, true_beta=20.0, seed=14, idio_sd=0.0001)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=500, seed=14)
    assert result.p_value >= 1.0 / (1 + result.n_valid)
    assert result.p_value > 0.0


# ---- separation of unrestricted CI/SE and null-imposed p-value ----

def test_null_imposed_result_has_no_ci_or_se_fields():
    fields = inf.NullImposedBootstrapResult.__dataclass_fields__
    for forbidden in ("ci_low", "ci_high", "se", "significant"):
        assert forbidden not in fields


def test_unrestricted_and_null_imposed_are_independent_procedures_different_distributions():
    df, dates = make_dataset(80, true_beta=5.0, seed=15, idio_sd=0.0008)
    unrestricted = inf.primary_block_bootstrap(df, dates, n_resamples=500, seed=15)
    null_imposed = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=500, seed=15)
    # unrestricted beta_boot should cluster near the real (large, positive) beta_hat;
    # null-imposed beta_star should cluster near zero -- a real structural difference.
    assert np.median(unrestricted.beta_boot) > 2.0
    assert abs(np.median(null_imposed.beta_star)) < 2.0


# ---- no recycling / no arbitrary row-order matching ----

def test_shuffled_row_order_gives_identical_result_proving_no_order_dependence():
    df, dates = make_dataset(60, true_beta=2.0, seed=16, drop_prob=0.2)
    shuffled = df.sample(frac=1.0, random_state=0).reset_index(drop=True)
    r1 = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=300, seed=20)
    r2 = inf.primary_null_imposed_bootstrap(shuffled, dates, n_resamples=300, seed=20)
    assert r1.p_value == pytest.approx(r2.p_value)
    assert np.array_equal(np.sort(r1.retained_row_counts), np.sort(r2.retained_row_counts))


def test_unknown_anchor_outside_approved_schedule_is_rejected():
    df, dates = make_dataset(10, true_beta=1.0, seed=17)
    bad = df.copy()
    bad.loc[0, "t"] = dt.time(11, 0)  # not one of the 5 approved anchors
    with pytest.raises(ValueError):
        inf.null_imposed_block_bootstrap(bad, dates, block_length=6, n_resamples=50, seed=17)


def test_trade_date_not_in_calendar_is_rejected():
    df, dates = make_dataset(10, true_beta=1.0, seed=18)
    short_dates = dates[:5]  # df references dates beyond this truncated calendar
    with pytest.raises(ValueError):
        inf.null_imposed_block_bootstrap(df, short_dates, block_length=6, n_resamples=50, seed=18)


def test_missing_required_column_is_rejected():
    df, dates = make_dataset(10, true_beta=1.0, seed=19)
    df = df.drop(columns=["Momentum_F"])
    with pytest.raises(ValueError):
        inf.null_imposed_block_bootstrap(df, dates, block_length=6, n_resamples=50, seed=19)


def test_mixed_horizon_dataset_is_rejected():
    df, dates = make_dataset(10, true_beta=1.0, seed=20)
    df.loc[0, "horizon"] = 30
    with pytest.raises(ValueError):
        inf.null_imposed_block_bootstrap(df, dates, block_length=6, n_resamples=50, seed=20)


def test_h60_structural_tod_closing_30_degeneracy_is_not_treated_as_resample_failure():
    """For the approved primary horizon h=60, every schedule anchor
    except the first is 'midday' -- TOD_closing_30 is identically zero
    for the ENTIRE dataset, making the real design matrix permanently
    rank-deficient by one dimension. This must not cause every (or
    even most) resamples to be marked rank-deficient -- only a
    genuine, additional loss of identification beyond that baseline
    should be flagged."""
    df, dates = make_dataset(100, true_beta=1.0, seed=21, drop_prob=0.0)
    assert (df["TOD_closing_30"] == 0).all()  # confirms the structural fact this test exercises
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=500, seed=21)
    assert result.n_failed_rank_deficient == 0  # full coverage -> no additional rank loss beyond baseline
    assert result.n_valid == 500


def test_audit_fields_identify_the_zero_variance_regressor_by_name():
    df, dates = make_dataset(100, true_beta=1.0, seed=22, drop_prob=0.0)
    result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=200, seed=22)
    assert result.zero_variance_regressors == ("TOD_closing_30",)
    assert result.k_eff == 5


def test_genuinely_rank_deficient_resamples_are_detected_at_least_once_across_seeds():
    """At very high drop probability, SOME seed must eventually trigger
    a genuine rank-deficiency beyond the permanent h=60 baseline (e.g.
    losing all TOD_opening_30 variation too) -- demonstrating the
    detection path is reachable, without hardcoding one brittle seed's
    exact count (which was the earlier test's fragility)."""
    found_rank_deficient = False
    for seed in range(30, 50):
        df, dates = make_dataset(100, true_beta=1.0, seed=seed, drop_prob=0.9)
        result = inf.primary_null_imposed_bootstrap(df, dates, n_resamples=300, seed=seed)
        if result.n_failed_rank_deficient > 0:
            found_rank_deficient = True
            break
    assert found_rank_deficient, "rank-deficiency detection path was never exercised across 20 seeds at 90% drop"


def test_this_module_never_touches_a_real_database_or_real_csv():
    import inspect
    from lead_lag import inference as inference_module
    src = inspect.getsource(inference_module)
    for forbidden in ("duckdb", "read_csv(", "connect("):
        assert forbidden not in src
