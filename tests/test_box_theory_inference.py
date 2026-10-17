"""Regression tests for src/box_theory/inference.py's day-clustered
bootstrap: whole trading days are resampled, not individual trades, and
the reported CI is the 97.5% two-sided (Bonferroni-for-2-configs)
interval -- [1.25th, 98.75th] percentile of the resample means."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from box_theory.inference import day_clustered_bootstrap, excludes_zero, percentile_vs_null


def test_empty_trades_returns_nan_fields():
    out = day_clustered_bootstrap(pd.DataFrame(columns=["trade_date", "net_r"]))
    assert out["n_trades"] == 0
    assert out["n_days"] == 0
    assert np.isnan(out["mean_net_r"])


def test_point_estimate_matches_plain_mean():
    trades = pd.DataFrame({
        "trade_date": [pd.Timestamp("2024-01-01")] * 3 + [pd.Timestamp("2024-01-02")] * 2,
        "net_r": [1.0, 2.0, 3.0, -1.0, 0.0],
    })
    out = day_clustered_bootstrap(trades, n_resamples=2000, seed=1)
    assert out["mean_net_r"] == pytest.approx(trades["net_r"].mean())
    assert out["n_trades"] == 5
    assert out["n_days"] == 2


def test_single_day_pool_has_degenerate_ci_at_that_days_own_mean():
    # every resample draws the SAME single day every time -> CI collapses
    # to a point at that day's own mean
    trades = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-01")] * 4, "net_r": [1.0, -1.0, 2.0, -2.0]})
    out = day_clustered_bootstrap(trades, n_resamples=1000, seed=0)
    assert out["ci_low"] == pytest.approx(0.0, abs=1e-9)
    assert out["ci_high"] == pytest.approx(0.0, abs=1e-9)
    assert out["se"] == pytest.approx(0.0, abs=1e-9)


def test_more_days_shrinks_ci_width_for_same_per_trade_variance():
    rng = np.random.default_rng(0)
    few_days = pd.DataFrame({
        "trade_date": np.repeat(pd.date_range("2024-01-01", periods=5), 4),
        "net_r": rng.normal(0.1, 1.0, size=20),
    })
    many_days = pd.DataFrame({
        "trade_date": np.repeat(pd.date_range("2024-01-01", periods=200), 4),
        "net_r": rng.normal(0.1, 1.0, size=800),
    })
    few = day_clustered_bootstrap(few_days, n_resamples=5000, seed=2)
    many = day_clustered_bootstrap(many_days, n_resamples=5000, seed=2)
    assert (many["ci_high"] - many["ci_low"]) < (few["ci_high"] - few["ci_low"])
    assert many["mde"] < few["mde"]


def test_excludes_zero():
    assert excludes_zero(0.1, 0.5) is True
    assert excludes_zero(-0.5, -0.1) is True
    assert excludes_zero(-0.1, 0.1) is False


def test_percentile_vs_null():
    null_means = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    # observed mean beats 9 of 10 null draws -> 90th percentile
    assert percentile_vs_null(0.85, null_means) == pytest.approx(90.0)
