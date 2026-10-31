"""Section 7 power calculation (PREREGISTRATION_PORTFOLIO.md) -- run
BEFORE any non-baseline configuration is evaluated. Also exposes the
Bonferroni/Benjamini-Hochberg machinery Section 6 uses at the grid stage
(implemented directly rather than via `statsmodels`, listed in
`requirements.txt` but not installed in this environment -- confirmed
before writing PREREGISTRATION_PORTFOLIO.md).
"""
from __future__ import annotations

import numpy as np
from scipy import stats

N_TRIALS = 24
ALPHA_UNCORRECTED = 0.05
ALPHA_BONFERRONI = ALPHA_UNCORRECTED / N_TRIALS  # 0.05/24 = 0.0020833...
POWER_TARGET = 0.80


def false_positive_probability(n_trials: int, alpha: float) -> float:
    """P(at least one false positive) across n_trials independent tests
    each run at `alpha` -- the arithmetic PREREGISTRATION_PORTFOLIO.md
    Section 6 states explicitly."""
    return 1.0 - (1.0 - alpha) ** n_trials


def minimum_detectable_difference(n: int, sigma_period: float, rebalance_days: int,
                                   alpha: float = ALPHA_BONFERRONI, power: float = POWER_TARGET) -> dict:
    """Both a bare detection threshold (critical value only, no power
    term) and the standard minimum-detectable-EFFECT at `power`
    (default 80%), using the t-distribution (df = n-1) rather than the
    normal approximation given the small sample sizes here. Annualized
    via proper compounding, `(1 + x)^(252/rebalance_days) - 1`, not a
    linear approximation.

    `sigma_period`: observed standard deviation of the PERIOD (not
    annualized) net return series this is being computed against."""
    df = n - 1
    t_alpha = stats.t.ppf(1 - alpha / 2, df)
    t_beta = stats.t.ppf(power, df)
    se = sigma_period / np.sqrt(n)

    detection_threshold_period = t_alpha * se
    mde_period = (t_alpha + t_beta) * se

    periods_per_year = 252 / rebalance_days
    detection_threshold_annual = (1 + detection_threshold_period) ** periods_per_year - 1
    mde_annual = (1 + mde_period) ** periods_per_year - 1

    return {
        "n": n, "df": df, "alpha": alpha, "power": power,
        "t_alpha": float(t_alpha), "t_beta": float(t_beta), "se_period": float(se),
        "detection_threshold_period": float(detection_threshold_period),
        "mde_period": float(mde_period),
        "detection_threshold_annual": float(detection_threshold_annual),
        "mde_annual": float(mde_annual),
    }


def benjamini_hochberg(p_values: list[float], labels: list[str], q: float = 0.05) -> list[dict]:
    """Returns one dict per (label, p_value), each carrying `bh_reject`
    (bool) -- sort ascending, find the largest k with p_(k) <= (k/m)*q,
    reject all p_(1..k). Implemented directly (statsmodels not
    installed, see module docstring)."""
    m = len(p_values)
    order = np.argsort(p_values)
    sorted_p = np.array(p_values)[order]
    thresholds = (np.arange(1, m + 1) / m) * q
    passing = np.flatnonzero(sorted_p <= thresholds)
    k = int(passing.max()) + 1 if len(passing) else 0

    out = [None] * m
    for rank, idx in enumerate(order):
        out[idx] = {
            "label": labels[idx], "p_value": float(p_values[idx]),
            "bh_rank": rank + 1, "bh_threshold": float(thresholds[rank]),
            "bh_reject": bool(rank < k),
        }
    return out
