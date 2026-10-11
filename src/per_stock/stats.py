"""FIT/CHECK evaluation, Bonferroni correction, and the random-entry null
for the per-stock weekly study. Every threshold here is pre-registered in
PREREGISTRATION_PER_STOCK.md, fixed before this module ever saw a trade
result.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from per_stock.rules import entry_candidates, simulate_trade

FIT_START, FIT_END = pd.Timestamp("2016-10-01"), pd.Timestamp("2022-12-31")
CHECK_START, CHECK_END = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-09-30")

MIN_CHECK_TRADES = 15
FIT_T_MIN = 2.0
ALPHA = 0.05

NULL_SEEDS = 1000
# Not given verbatim by the user ("beat random weeks" is qualitative) --
# fixed here, before any trial ran, at the same one-sided 95% convention
# this study's other gates already use (FIT_T_MIN=2 is itself close to a
# two-sided 95% bar at moderate df). Stated explicitly as a filled-in gap,
# not hidden as if the user had specified a number.
NULL_BEAT_PERCENTILE = 95.0


def split_fit_check(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        return trades, trades
    fit = trades[(trades["entry_week_start"] >= FIT_START) & (trades["entry_week_start"] <= FIT_END)]
    check = trades[(trades["entry_week_start"] >= CHECK_START) & (trades["entry_week_start"] <= CHECK_END)]
    return fit, check


def t_test_mean_gt_zero(returns: pd.Series) -> dict:
    """mean/t_stat/p_value for H0: mean == 0 (two-sided). t_stat/p_value
    are NaN with fewer than 2 observations or zero variance (cannot be
    computed, never silently treated as passing or failing)."""
    n = len(returns)
    mean = float(returns.mean()) if n else float("nan")
    std = float(returns.std(ddof=1)) if n > 1 else float("nan")
    if n < 2 or std == 0 or pd.isna(std):
        return {"n": n, "mean": mean, "std": std, "t_stat": float("nan"), "p_value": float("nan")}
    t_stat, p_value = scipy_stats.ttest_1samp(returns, 0.0)
    return {"n": n, "mean": mean, "std": std, "t_stat": float(t_stat), "p_value": float(p_value)}


def bonferroni_alpha(n_trials: int, alpha: float = ALPHA) -> float:
    return alpha / n_trials


def chance_expectation(n_trials: int, alpha: float = ALPHA) -> dict:
    """Two different "by chance alone" baselines, reported together
    because they answer different questions and are easy to conflate:
      - naive_uncorrected: expected false positives at an UNCORRECTED
        alpha, i.e. what you'd see if each of the n_trials trials were
        tested independently at the 5% level with no multiple-testing
        adjustment (alpha * n_trials).
      - bonferroni_corrected: expected false positives under THIS study's
        actual gate (each trial tested at alpha/n_trials) -- which is
        alpha by construction, independent of n_trials. This is the
        whole point of Bonferroni: the family-wise expected false-positive
        count stays pinned near alpha (here, 0.05) no matter how many
        trials are run, in exchange for each individual trial needing a
        much smaller p-value to pass."""
    return {"naive_uncorrected": n_trials * alpha, "bonferroni_corrected": n_trials * (alpha / n_trials)}


def random_entry_null(weekly: pd.DataFrame, week_days: dict, entity_id: str, n_trades: int,
                       window_start: pd.Timestamp = CHECK_START, window_end: pd.Timestamp = CHECK_END,
                       seed_count: int = NULL_SEEDS) -> np.ndarray:
    """1000 draws of `n_trades` DISTINCT random entry weeks from
    `entity_id`'s own CHECK-window entry-candidate pool (same mechanics as
    a real signal trade -- the only difference is which weeks are
    entered), each draw's mean net return. Empty array if the pool has
    fewer than `n_trades` eligible weeks (cannot be compared; the caller
    must treat that as "cannot be evaluated against a null," not as a
    pass or a fail). `week_days`: per_stock.rules.precompute_week_days's
    cache, built once per entity and reused across every seed here."""
    pool = entry_candidates(weekly, entity_id)
    pool = pool[(pool["entry_week_start"] >= window_start) & (pool["entry_week_start"] <= window_end)]
    pool = pool.reset_index(drop=True)
    if len(pool) < n_trades or n_trades == 0:
        return np.array([])

    means = np.empty(seed_count)
    for seed in range(seed_count):
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(pool), size=n_trades, replace=False)
        sub = pool.iloc[idx]
        rets = [
            simulate_trade(week_days, entity_id, r["entry_week_start"], r["entry_week_open"],
                            r["entry_week_close"], r["sig_sigma"])["net_return"]
            for _, r in sub.iterrows()
        ]
        means[seed] = float(np.mean(rets))
    return means


def null_percentile(actual_mean: float, null_means: np.ndarray) -> float:
    """% of the null distribution strictly below the actual mean -- NaN
    if the null could not be built (see random_entry_null)."""
    if null_means.size == 0:
        return float("nan")
    return float((null_means < actual_mean).mean() * 100)


def forward_trades_needed(mean_return: float, std_return: float, target_t: float = FIT_T_MIN) -> float | None:
    """Sample size N such that a per-trade mean/std matching the observed
    values would reach t=target_t: N = (target_t * std / mean)^2. None if
    mean <= 0 or std <= 0 (cannot be confirmed by more trades at a
    non-positive mean, or undefined with zero variance)."""
    if mean_return is None or std_return is None:
        return None
    if mean_return <= 0 or std_return <= 0 or pd.isna(mean_return) or pd.isna(std_return):
        return None
    return float((target_t * std_return / mean_return) ** 2)
