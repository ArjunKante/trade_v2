"""Per-factor rank IC on forward 63-day returns, purged walk-forward CV,
FOLD-LEVEL standard error (not date-level -- overlapping 63-day targets mean
adjacent dates are not independent observations; treating them as such is
exactly the mistake that gave the prior project a meaningless date-level
t-stat of -6.10 against an honest period-level t of -1.24).

No composite, no model here -- this module answers one question per call:
does this one factor, alone, have a measurable rank relationship with
forward 63-day returns, and how confident can we be in that given only a
handful of genuinely-independent-ish time blocks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from purgedcv import PurgedKFold
from scipy.stats import spearmanr

HORIZON_DAYS = 63
PURGE = "63D"
EMBARGO = "5D"


def daily_rank_ic(df: pd.DataFrame, factor_col: str = "value", target_col: str = "fwd_return") -> pd.DataFrame:
    """Spearman rank IC per trade_date (cross-sectional, across entities)."""
    def _ic(g):
        if len(g) < 5 or g[factor_col].nunique() < 2:
            return np.nan
        rho, _ = spearmanr(g[factor_col], g[target_col])
        return rho

    out = df.groupby("trade_date").apply(_ic, include_groups=False)
    return out.rename("ic").reset_index()


def purged_fold_assignments(df: pd.DataFrame, n_splits: int) -> np.ndarray:
    """Returns a fold-id array (same length/order as df) using PurgedKFold's
    test-fold membership. purge_horizon/embargo are applied to TRAIN, not to
    which rows belong to which test fold, so this just recovers each row's
    test-fold id for later grouping by fold.

    CALLER MUST pass df already sorted by trade_date (monotonic
    non-decreasing) with a fresh RangeIndex -- PurgedKFold requires this of
    prediction_times and this function does not re-sort, so the returned
    array stays aligned to df's given row order."""
    pred_times = pd.to_datetime(df["trade_date"])
    eval_times = pd.to_datetime(df["eval_date"])
    cv = PurgedKFold(n_splits=n_splits, prediction_times=pred_times, evaluation_times=eval_times,
                      purge_horizon=PURGE, embargo=EMBARGO)
    fold_id = np.full(len(df), -1)
    for k, (_, test_idx) in enumerate(cv.split(df)):
        fold_id[test_idx] = k
    return fold_id


def fold_level_ic_report(df: pd.DataFrame, n_splits: int, factor_col: str = "value",
                          target_col: str = "fwd_return") -> dict:
    """df: one row per (entity_id, trade_date) with factor_col, target_col,
    eval_date populated (already dropna'd). Returns a dict with fold ICs,
    mean, SE (across folds), t-stat, and n_folds actually used (folds with
    too few dates to compute a stable IC are dropped and reported as such,
    not silently zero-filled)."""
    df = df.dropna(subset=[factor_col, target_col, "eval_date"]).sort_values("trade_date").reset_index(drop=True)
    fold_id = purged_fold_assignments(df, n_splits)
    df = df.assign(_fold=fold_id)

    fold_ics = []
    fold_n_dates = []
    for k in sorted(df["_fold"].unique()):
        if k < 0:
            continue
        fold_df = df[df["_fold"] == k]
        daily = daily_rank_ic(fold_df, factor_col, target_col).dropna(subset=["ic"])
        if len(daily) < 10:  # too few independent-ish dates in this fold to trust a mean
            continue
        fold_ics.append(daily["ic"].mean())
        fold_n_dates.append(len(daily))

    fold_ics = np.array(fold_ics)
    n_folds = len(fold_ics)
    mean_ic = fold_ics.mean() if n_folds > 0 else np.nan
    se_ic = fold_ics.std(ddof=1) / np.sqrt(n_folds) if n_folds > 1 else np.nan
    t_stat = mean_ic / se_ic if se_ic and not np.isnan(se_ic) and se_ic > 0 else np.nan

    return {
        "n_folds_used": n_folds,
        "n_folds_requested": n_splits,
        "fold_ics": fold_ics.tolist(),
        "fold_n_dates": fold_n_dates,
        "mean_ic": mean_ic,
        "se_ic": se_ic,
        "t_stat": t_stat,
    }


def rebalance_spacing_trading_days(used_dates, reference_calendar) -> dict:
    """Gap, in TRADING-DAY ROWS on reference_calendar (the same row-based unit
    compute_forward_return's horizon is defined in -- never calendar days),
    between consecutive entries of used_dates once sorted and deduped.

    used_dates is whatever a caller is about to treat as "independent
    observations" -- typically a factor's own surviving rebalance dates
    AFTER dropping NaNs, not the full rebalance grid, since dropped dates
    could in principle change the effective spacing between what's left.
    Computed and reported explicitly rather than assumed from how the grid
    was constructed, per the same discipline as every other point-in-time
    check in this project: verify the mechanism, don't infer it."""
    ref_sorted = sorted(pd.to_datetime(pd.Series(reference_calendar)).unique())
    pos = {d: i for i, d in enumerate(ref_sorted)}
    used_sorted = sorted(pd.to_datetime(pd.Series(used_dates)).unique())
    positions = [pos[d] for d in used_sorted if d in pos]
    if len(positions) < 2:
        return {"min": None, "median": None, "max": None, "n_dates": len(positions)}
    gaps = np.diff(positions)
    return {"min": int(gaps.min()), "median": float(np.median(gaps)), "max": int(gaps.max()), "n_dates": len(positions)}


def nonoverlapping_ic_report(df: pd.DataFrame, min_spacing_trading_days: int, horizon_days: int = HORIZON_DAYS,
                              factor_col: str = "value", target_col: str = "fwd_return") -> dict:
    """Direct (non-CV) significance test for a single, PARAMETER-FREE factor
    whose rebalance spacing is >= the target horizon, so consecutive
    observations' forward-return windows do NOT overlap and are therefore
    independent draws already -- no purged-fold structure is needed to get a
    valid SE, and imposing one just starves every fold of dates it doesn't
    need to be dropped for (this is what produced 0-folds-used across every
    Phase E factor when fold_level_ic_report was applied to a ~25-date
    quarterly-rebalance panel built for daily overlapping data).

    This is NOT a general replacement for fold_level_ic_report. It is valid
    only when BOTH hold:
      (1) no overlap -- rebalance spacing (in trading days) >= horizon_days.
          The caller must compute this itself (see
          rebalance_spacing_trading_days) and pass the MINIMUM observed
          spacing, not assume it from how the grid was designed -- a design
          intent and a verified fact are not the same thing here.
      (2) no fitting -- df's factor_col is one single parameter-free value
          per observation (a ratio, not a fitted model's output). Fitting
          introduces in-sample leakage risk that only cross-validation
          guards against; this function does not guard against that at all.
          Point-in-time correctness (known_date discipline) is a separate,
          already-handled concern and does not depend on which report is used.

    Raises AssertionError if the spacing precondition is violated -- the
    entire basis for skipping fold structure is the non-overlap guarantee,
    so a caller passing a spacing that violates it must be stopped loudly,
    not given a silently understated SE.
    """
    assert min_spacing_trading_days >= horizon_days, (
        f"rebalance spacing ({min_spacing_trading_days} trading days) is less than the "
        f"target horizon ({horizon_days} trading days) -- forward-return windows overlap, "
        "so consecutive dates' ICs are NOT independent and this direct SE would understate "
        "the true uncertainty. Use fold_level_ic_report instead."
    )
    daily = daily_rank_ic(df, factor_col, target_col).dropna(subset=["ic"])
    n = len(daily)
    mean_ic = daily["ic"].mean() if n > 0 else np.nan
    std_ic = daily["ic"].std(ddof=1) if n > 1 else np.nan
    se_ic = std_ic / np.sqrt(n) if n > 1 and std_ic > 0 else np.nan
    t_stat = mean_ic / se_ic if se_ic and not np.isnan(se_ic) else np.nan
    return {"n_dates": n, "mean_ic": mean_ic, "std_ic": std_ic, "se_ic": se_ic, "t_stat": t_stat}


def benjamini_hochberg(pvalues, alpha: float = 0.05) -> pd.DataFrame:
    """Standard BH step-up procedure, implemented directly (no statsmodels
    dependency in this environment). Given m p-values, sorts ascending,
    finds the largest rank k where p_(k) <= (k/m)*alpha, and rejects all
    hypotheses at or below that rank. Also returns the monotone BH-adjusted
    p-value (q-value) per hypothesis: q_(i) = min_{j>=i} (m/j * p_(j)),
    enforced non-decreasing from the largest p down to the smallest, which
    is what makes q comparable directly against alpha for any hypothesis
    without re-deriving the step-up threshold by hand.

    Returns a dataframe indexed like the input (original order preserved),
    columns [pvalue, rank, q_value, reject]."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p)
    ranked = p[order]
    raw_q = ranked * m / (np.arange(m) + 1)
    q = np.minimum.accumulate(raw_q[::-1])[::-1]
    q = np.minimum(q, 1.0)
    thresholds = (np.arange(m) + 1) / m * alpha
    below = ranked <= thresholds
    k = np.max(np.where(below)[0]) + 1 if below.any() else 0
    reject_sorted = np.zeros(m, dtype=bool)
    reject_sorted[:k] = True

    out = pd.DataFrame(index=np.arange(m))
    out.loc[order, "pvalue"] = ranked
    out.loc[order, "rank"] = np.arange(1, m + 1)
    out.loc[order, "q_value"] = q
    out.loc[order, "reject"] = reject_sorted
    return out


def ic_by_year(df: pd.DataFrame, factor_col: str = "value", target_col: str = "fwd_return") -> pd.DataFrame:
    """Descriptive only (not CV-based): mean daily rank IC per calendar year,
    so a regime-dependent factor shows up as such rather than being averaged
    away into one number."""
    daily = daily_rank_ic(df, factor_col, target_col).dropna(subset=["ic"])
    daily["year"] = pd.to_datetime(daily["trade_date"]).dt.year
    return daily.groupby("year")["ic"].agg(["mean", "std", "count"]).reset_index()
