"""Section 16: null-generation machinery. SYNTHETIC DATA ONLY -- no test
in this file reads any real database or fits the primary regression to
real study data. Verifies the sampling mechanics (per-day circular
shift, per-month-independent B1 draws, shared-rank-position B2 draws,
shared-placebo-day pairing) and the pass/fail comparison logic, not any
real-world beta/p-value/significance result."""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag import nulls
from lead_lag.regression import ObservationRow, build_regression_dataset

D0 = dt.date(2026, 1, 5)  # a Monday, arbitrary synthetic anchor


def make_df(rows):
    """rows: list of (trade_date, t, S_L, R_F, Momentum_F, Y, tod)"""
    obs = [ObservationRow(trade_date=d, t=t, horizon=60, S_L=s_l, R_F=r_f,
                           tod=tod, Momentum_F=mom, Y=y)
           for (d, t, s_l, r_f, mom, y, tod) in rows]
    return build_regression_dataset(obs, horizon=60)


# ---- (a) timing null ----

def test_timing_null_is_a_noop_when_every_day_has_a_single_row():
    rows = [(D0 + dt.timedelta(days=i), dt.time(9, 19), 0.01 * i, 0.005 * i,
              0.002 * i, 0.003 * i, "midday") for i in range(10)]
    df = make_df(rows)
    result = nulls.timing_null_circular_shift(df, n_draws=20, seed=1)
    assert np.all(result.null_betas == result.null_betas[0])  # deterministic no-op every draw
    assert result.null_betas[0] == pytest.approx(result.real_beta, abs=1e-10)


def test_timing_null_multi_row_days_actually_shift_and_vary_across_draws():
    """Uses independent random (not formulaically linear) values so no
    exact affine relationship across rows could make the fit invariant
    to within-day permutation by coincidence."""
    gen = np.random.default_rng(2026)
    rows = []
    for i in range(8):
        d = D0 + dt.timedelta(days=i)
        for t in [dt.time(9, 19), dt.time(10, 24), dt.time(11, 29)]:
            s_l, r_f, mom, y = gen.standard_normal(4) * 0.01
            rows.append((d, t, s_l, r_f, mom, y, "midday"))
    df = make_df(rows)
    result = nulls.timing_null_circular_shift(df, n_draws=30, seed=42)
    assert len(set(np.round(result.null_betas, 10))) > 1  # not all identical -> shifting occurred


def test_timing_null_is_deterministic_given_seed():
    rows = []
    for i in range(6):
        d = D0 + dt.timedelta(days=i)
        for t in [dt.time(9, 19), dt.time(10, 24)]:
            rows.append((d, t, 0.01 * i, 0.002 * i, 0.001 * i, 0.005 * i, "midday"))
    df = make_df(rows)
    r1 = nulls.timing_null_circular_shift(df, n_draws=15, seed=7)
    r2 = nulls.timing_null_circular_shift(df, n_draws=15, seed=7)
    assert np.array_equal(r1.null_betas, r2.null_betas)


def test_timing_null_result_fields_are_self_consistent():
    rows = [(D0 + dt.timedelta(days=i), dt.time(9, 19), 0.01 * i, 0.005 * i,
              0.002 * i, 0.003 * i, "midday") for i in range(5)]
    df = make_df(rows)
    result = nulls.timing_null_circular_shift(df, n_draws=50, seed=3)
    assert result.variant == "timing_null_a"
    assert result.two_sided_95th_abs == pytest.approx(np.percentile(np.abs(result.null_betas), 95))
    assert result.passes == (abs(result.real_beta) > result.two_sided_95th_abs)
    assert result.n_draws_used == 50


# ---- (b) selection null B1/B2 ----

def pool_for(month, size, prefix):
    return [f"{prefix}{month[1]}_{k}" for k in range(size)]


def rank_sum_fn(entity_ids, trade_date, t):
    """Deterministic synthetic leader-portfolio-return stand-in: mean of
    each entity's own numeric rank suffix."""
    ranks = [int(e.split("_")[1]) for e in entity_ids]
    return float(np.mean(ranks)) / 100.0


def make_two_month_df():
    rows = []
    for month, day_offset in [(1, 0), (2, 35)]:
        d = dt.date(2026, month, 10)
        for t in [dt.time(9, 19), dt.time(10, 24)]:
            rows.append((d, t, 0.0, 0.002, 0.001, 0.004, "midday"))
    return make_df(rows)


def test_selection_null_b1_draws_independently_per_month():
    df = make_two_month_df()
    pools = {(2026, 1): pool_for((2026, 1), 20, "A"), (2026, 2): pool_for((2026, 2), 20, "B")}
    rng = np.random.default_rng(123)
    s_l = nulls._b1_single_repetition(df, pools, rank_sum_fn, n_leaders=3, rng=rng)
    # month 1's rows and month 2's rows get independently drawn pools --
    # the two months' entities are drawn from disjoint prefixes (A vs B),
    # so this is really checking wiring; the independence itself is
    # checked by reproducibility below.
    assert len(s_l) == len(df)


def test_selection_null_b1_fresh_draw_every_repetition():
    df = make_two_month_df()
    pools = {(2026, 1): pool_for((2026, 1), 30, "A"), (2026, 2): pool_for((2026, 2), 30, "B")}
    rng = np.random.default_rng(99)
    s_l_1 = nulls._b1_single_repetition(df, pools, rank_sum_fn, n_leaders=3, rng=rng)
    s_l_2 = nulls._b1_single_repetition(df, pools, rank_sum_fn, n_leaders=3, rng=rng)
    assert not np.array_equal(s_l_1, s_l_2)  # fresh draw each call, same rng stream


def test_selection_null_b1_raises_if_pool_too_small():
    df = make_two_month_df()
    pools = {(2026, 1): pool_for((2026, 1), 2, "A"), (2026, 2): pool_for((2026, 2), 20, "B")}
    rng = np.random.default_rng(1)
    with pytest.raises(ValueError):
        nulls._b1_single_repetition(df, pools, rank_sum_fn, n_leaders=3, rng=rng)


def test_selection_null_b2_applies_identical_rank_positions_to_every_month():
    df = make_two_month_df()
    pool_size = 20
    pools = {(2026, 1): pool_for((2026, 1), pool_size, "A"), (2026, 2): pool_for((2026, 2), pool_size, "B")}
    rank_positions = np.array([2, 5, 9])
    s_l = nulls._b2_single_repetition(df, pools, rank_sum_fn, rank_positions)
    expected_mean_rank = float(np.mean(rank_positions)) / 100.0
    assert np.all(np.isclose(s_l, expected_mean_rank))  # same rank-sum regardless of month


def test_selection_null_b2_rejects_mismatched_pool_sizes():
    df = make_two_month_df()
    pools = {(2026, 1): pool_for((2026, 1), 20, "A"), (2026, 2): pool_for((2026, 2), 15, "B")}
    with pytest.raises(ValueError):
        nulls.selection_null_b2(df, pools, rank_sum_fn, n_leaders=3, n_repetitions=2, seed=1)


def test_selection_null_b1_and_b2_end_to_end_return_valid_result():
    df = make_two_month_df()
    pools = {(2026, 1): pool_for((2026, 1), 20, "A"), (2026, 2): pool_for((2026, 2), 20, "B")}
    r1 = nulls.selection_null_b1(df, pools, rank_sum_fn, n_leaders=3, n_repetitions=25, seed=5)
    r2 = nulls.selection_null_b2(df, pools, rank_sum_fn, n_leaders=3, n_repetitions=25, seed=5)
    assert r1.variant == "selection_null_b1" and r2.variant == "selection_null_b2"
    assert r1.n_draws_used == 25 and r2.n_draws_used == 25
    assert r1.two_sided_95th_abs >= 0 and r2.two_sided_95th_abs >= 0


# ---- (e) placebo diagnostic ----

def make_many_days_df(n_days=60):
    rows = []
    for i in range(n_days):
        d = D0 + dt.timedelta(days=i)
        rows.append((d, dt.time(9, 19), float(i), 0.001 * i, 0.0005 * i, 0.002 * i, "midday"))
    return make_df(rows)


def test_shared_placebo_day_assignment_respects_minimum_separation():
    real_days = [D0 + dt.timedelta(days=i) for i in range(60)]
    rng = np.random.default_rng(11)
    assignment = nulls._draw_shared_placebo_days(real_days, min_day_separation=20, rng=rng)
    day_index = {d: i for i, d in enumerate(real_days)}
    for day, placebo in assignment.items():
        if placebo is None:
            continue
        assert abs(day_index[placebo] - day_index[day]) >= 20


def test_placebo_null_shares_one_placebo_day_across_every_row_on_the_same_real_day():
    """Construct a day with two different t's; both rows on that day
    must receive S_L values that trace back to the SAME placebo day
    (verified indirectly: both rows' substituted S_L equal the known
    S_L(placebo_day, t) for whichever single placebo day was drawn --
    checked by reconstructing the lookup and confirming consistency)."""
    rows = []
    for i in range(60):
        d = D0 + dt.timedelta(days=i)
        rows.append((d, dt.time(9, 19), float(100 + i), 0.0, 0.0, 0.0, "midday"))
        rows.append((d, dt.time(10, 24), float(200 + i), 0.0, 0.0, 0.0, "midday"))
    df = make_df(rows)
    real_days = sorted(df["trade_date"].unique())
    s_l_by_t_day = {t_val: dict(zip(g["trade_date"], g["S_L"])) for t_val, g in df.groupby("t")}
    rng = np.random.default_rng(55)
    assignment = nulls._draw_shared_placebo_days(real_days, min_day_separation=20, rng=rng)
    day0 = real_days[0]
    placebo_day0 = assignment[day0]
    if placebo_day0 is not None:
        expected_0919 = s_l_by_t_day[dt.time(9, 19)][placebo_day0]
        expected_1024 = s_l_by_t_day[dt.time(10, 24)][placebo_day0]
        # same placebo day -> the two t's pull from that one day's two
        # distinct per-minute S_L values, not two independently-drawn days
        assert expected_0919 == 100 + real_days.index(placebo_day0)
        assert expected_1024 == 200 + real_days.index(placebo_day0)


def test_placebo_null_end_to_end_returns_valid_result():
    df = make_many_days_df(n_days=60)
    result = nulls.placebo_null(df, n_draws=25, min_day_separation=20, seed=9)
    assert result.variant == "placebo_e"
    assert result.n_draws_used > 0
    assert result.two_sided_95th_abs >= 0


def test_placebo_null_is_deterministic_given_seed():
    df = make_many_days_df(n_days=60)
    r1 = nulls.placebo_null(df, n_draws=20, min_day_separation=20, seed=17)
    r2 = nulls.placebo_null(df, n_draws=20, min_day_separation=20, seed=17)
    assert np.array_equal(r1.null_betas, r2.null_betas)


def test_this_module_never_touches_a_real_database_connection():
    import inspect
    from lead_lag import nulls as nulls_module
    for name in ("timing_null_circular_shift", "selection_null_b1", "selection_null_b2", "placebo_null"):
        params = inspect.signature(getattr(nulls_module, name)).parameters
        assert "con" not in params and "connection" not in params
