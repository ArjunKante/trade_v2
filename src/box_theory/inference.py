"""Day-clustered bootstrap inference, PREREGISTRATION_BOX.md Section 5:
trades on the same day are correlated, so resampling draws whole trading
days (with replacement), not individual trades. 10,000 resamples, a
97.5% two-sided CI (Bonferroni-corrected for the 2 pre-registered
configurations: family-wise alpha 0.05 / 2 tests = 0.025 per test, i.e.
the [1.25th, 98.75th] percentile of the resampled means). No trade-level
t-statistic is used anywhere. The minimum detectable effect is computed
from the bootstrap standard error ALONE, never from the observed mean.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

N_RESAMPLES = 10_000
# two-sided critical value for alpha=0.025 (97.5% CI, Bonferroni for 2 configs)
Z_CRITICAL = 2.2414


def day_clustered_bootstrap(trades: pd.DataFrame, net_r_col: str = "net_r",
                             n_resamples: int = N_RESAMPLES, seed: int = 0) -> dict:
    """`trades` must have `trade_date` and `net_r_col` columns, already
    restricted to ONE configuration and ONE window. Returns a dict with
    the pooled point estimate, the 97.5% CI, the resample count, the
    distinct-day count, the bootstrap SE, and the MDE (= Z_CRITICAL x SE,
    computed from variance only)."""
    if trades.empty:
        return {
            "n_trades": 0, "n_days": 0, "mean_net_r": float("nan"), "median_net_r": float("nan"),
            "ci_low": float("nan"), "ci_high": float("nan"), "se": float("nan"), "mde": float("nan"),
        }

    by_day = trades.groupby("trade_date")[net_r_col]
    day_sums = by_day.sum().to_numpy()
    day_counts = by_day.count().to_numpy()
    n_days = len(day_sums)

    rng = np.random.default_rng(seed)
    draw_idx = rng.integers(0, n_days, size=(n_resamples, n_days))
    resample_sums = day_sums[draw_idx].sum(axis=1)
    resample_counts = day_counts[draw_idx].sum(axis=1)
    resample_means = resample_sums / resample_counts

    ci_low, ci_high = np.percentile(resample_means, [1.25, 98.75])
    se = float(resample_means.std(ddof=1))

    return {
        "n_trades": int(len(trades)), "n_days": int(n_days),
        "mean_net_r": float(trades[net_r_col].mean()),
        "median_net_r": float(trades[net_r_col].median()),
        "ci_low": float(ci_low), "ci_high": float(ci_high),
        "se": se, "mde": Z_CRITICAL * se,
        "resample_means": resample_means,
    }


def excludes_zero(ci_low: float, ci_high: float) -> bool:
    return ci_low > 0 or ci_high < 0


def percentile_vs_null(observed_mean: float, null_means: np.ndarray) -> float:
    """What percentile `observed_mean` sits at within the null
    distribution's own mean draws -- used for both the TIMING and
    SELECTION null comparisons (Section 6: ">= 95th percentile vs both
    nulls")."""
    return float((null_means < observed_mean).mean() * 100.0)
