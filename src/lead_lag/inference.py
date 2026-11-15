"""Section 7C (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`) /
Decision 12 (AMENDMENT 14 LOG): the primary consecutive multi-day
block-bootstrap inference procedure for the primary regression
coefficient `beta` on `S_L`, with the single-day-cluster bootstrap as
the prescribed sensitivity check -- both implemented by the SAME
function at different block lengths (`L=6` primary, `L=1` sensitivity),
since Section 7C describes them as the same mechanism, not two
separate procedures.

**Primary-outcome firewall**: every function here is exercised only
against synthetic fixtures (`tests/test_lead_lag_inference.py`).
Nothing in this module or its tests reads `full_pipeline_observations.csv`
or any other real data. Running this machinery against the real
primary dataset requires separate, explicit authorization.

**Resampling unit**: a "block" is `L` CONSECUTIVE TRADING-SESSION
POSITIONS in the governing calendar's own ordered date sequence (the
same position convention Decision 12's own ACF diagnostic used,
`block_length.py`) -- not `L` consecutive rows of the observation
dataset. All of a day's own observations travel together as a unit
when that day is selected (never split across resample positions). A
block whose every day happens to have zero retained observations
contributes nothing to that resample -- it is not a failure, and
nothing is substituted for it.

**Two specific implementation choices this module makes, flagged
explicitly because the governing documents do not pin either one down
(Section 7C states the block length and the primary/sensitivity
hierarchy, but not these two mechanics)**:

1. **Blocks per resample**: `ceil(n_session_positions / L)` blocks are
   drawn (with replacement) per resample -- the standard moving-block-
   bootstrap convention of resampling enough blocks to cover
   approximately the original sample's own time span. A shorter or
   longer convention is not ruled out by the governing text, but this
   is the standard one.
2. **p-value / CI construction**: the governing documents prescribe
   WHICH resampling unit and WHICH alpha to use, but not an explicit
   formula for turning a bootstrap distribution of `beta` into a
   two-sided p-value. This module uses the standard percentile/test-
   inversion convention: CI = the `[alpha/2, 1-alpha/2]` percentiles of
   the raw bootstrap `beta` distribution; two-sided p-value =
   `2 * min(mean(beta_boot <= 0), mean(beta_boot >= 0))` (the standard
   percentile-bootstrap test statistic for `H0: beta=0`, equivalent by
   test-inversion to "0 lies outside the `(1-alpha)` percentile CI iff
   `p < alpha`"). This is a well-established, pre-existing convention,
   not invented for this family -- but it IS a choice among valid
   alternatives (e.g. a studentized/pivotal bootstrap, or a Wald test
   using the bootstrap SE against a normal critical value) that the
   governing text does not itself specify. Flagged here for
   confirmation before any real-data use.

**Not implemented here**: the Section 7C "supplementary: continuous/
overlapping sample" check. The governing documents give no further
construction detail (sampling grid, spacing, whether Stage A/B still
apply, aggregation) beyond that one phrase -- see the Phase 5
inference-implementation report for the exact ambiguity.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .diagnostics import REDUCED_CONTROLS
from .regression import PRIMARY_REGRESSORS, fit_ols, fit_primary_regression
from .schedule import non_overlapping_schedule

SEED = 20261107  # Section 22
PRIMARY_BLOCK_LENGTH = 6  # Decision 12, AMENDMENT 14 LOG
SENSITIVITY_BLOCK_LENGTH = 1  # Section 7C -- single-day-cluster bootstrap
ALPHA = 0.00625  # Decision 16, operative multiplicity-adjusted alpha
N_RESAMPLES = 1000  # Section 14/16's existing draw-count convention


def _build_overlapping_blocks(all_session_dates: list[dt.date], block_length: int) -> list[list[dt.date]]:
    """Every contiguous window of `block_length` consecutive positions
    in `all_session_dates` (already ordered) -- the standard moving-
    block-bootstrap block set. `len(all_session_dates) - block_length + 1`
    blocks in total."""
    if block_length < 1:
        raise ValueError("block_length must be >= 1")
    n = len(all_session_dates)
    if block_length > n:
        raise ValueError(f"block_length ({block_length}) exceeds the number of available session positions ({n})")
    return [all_session_dates[i:i + block_length] for i in range(n - block_length + 1)]


@dataclass(frozen=True)
class BlockBootstrapResult:
    block_length: int
    n_session_positions: int
    n_blocks_available: int  # distinct contiguous windows to draw from
    n_blocks_per_resample: int
    n_resamples_requested: int
    n_valid: int
    n_failed: int
    point_estimate: float  # beta from a single fit on the full, un-resampled df
    beta_boot: np.ndarray  # length n_valid
    se: float
    ci_low: float
    ci_high: float
    alpha: float
    p_value: float
    significant: bool
    seed: int


def block_bootstrap_beta(
    df: pd.DataFrame,
    all_session_dates: list[dt.date],
    block_length: int,
    n_resamples: int = N_RESAMPLES,
    alpha: float = ALPHA,
    seed: int = SEED,
) -> BlockBootstrapResult:
    """Section 7C: resample contiguous `block_length`-day blocks (with
    replacement) from `all_session_dates`, refit the full primary
    regression (`fit_primary_regression`, unchanged -- `S_L` included)
    on each resample, and derive `beta`'s bootstrap SE/CI/two-sided
    p-value. `block_length=6` is the APPROVED primary procedure
    (Decision 12); `block_length=1` is the prescribed single-day-
    cluster sensitivity check -- the SAME function, not a different
    implementation, per Section 7C's own framing.

    `df` must have a `trade_date` column and the primary model's
    columns (`S_L`, `R_F`, `TOD_opening_30`, `TOD_closing_30`,
    `Momentum_F`, `Y`) -- validated up front via a single real fit,
    which also supplies `point_estimate` (the actual, un-resampled
    `beta`). A resample that ends up with zero rows (every day in
    every drawn block happened to have no observations) or that fails
    to fit (e.g. a singular design from too little variation) is
    counted in `n_failed` and excluded from `beta_boot` -- never
    silently treated as a zero or dropped without being counted."""
    if "trade_date" not in df.columns:
        raise ValueError("df must have a 'trade_date' column")
    point_fit = fit_primary_regression(df)  # validates columns; also the real point estimate
    point_estimate = point_fit.coefficients["S_L"]

    blocks = _build_overlapping_blocks(all_session_dates, block_length)
    n_blocks_per_resample = math.ceil(len(all_session_dates) / block_length)

    by_date = {d: g for d, g in df.groupby("trade_date")}
    rng = np.random.default_rng(seed)

    betas = []
    n_failed = 0
    for _ in range(n_resamples):
        chosen = rng.integers(0, len(blocks), size=n_blocks_per_resample)
        parts = [by_date[d] for bi in chosen for d in blocks[bi] if d in by_date and not by_date[d].empty]
        if not parts:
            n_failed += 1
            continue
        resampled_df = pd.concat(parts, ignore_index=True)
        try:
            fit = fit_primary_regression(resampled_df)
        except ValueError:
            n_failed += 1
            continue
        betas.append(fit.coefficients["S_L"])

    betas = np.array(betas, dtype=float)
    n_valid = len(betas)
    if n_valid == 0:
        raise ValueError("block_bootstrap_beta: every resample failed or was empty -- cannot derive inference")

    se = float(betas.std(ddof=1)) if n_valid > 1 else float("nan")
    ci_low, ci_high = (float(v) for v in np.percentile(betas, [100 * alpha / 2, 100 * (1 - alpha / 2)]))
    frac_le0 = float(np.mean(betas <= 0))
    frac_ge0 = float(np.mean(betas >= 0))
    p_value = min(1.0, 2 * min(frac_le0, frac_ge0))

    return BlockBootstrapResult(
        block_length=block_length, n_session_positions=len(all_session_dates),
        n_blocks_available=len(blocks), n_blocks_per_resample=n_blocks_per_resample,
        n_resamples_requested=n_resamples, n_valid=n_valid, n_failed=n_failed,
        point_estimate=point_estimate, beta_boot=betas, se=se,
        ci_low=ci_low, ci_high=ci_high, alpha=alpha, p_value=p_value,
        significant=p_value < alpha, seed=seed,
    )


def primary_block_bootstrap(df: pd.DataFrame, all_session_dates: list[dt.date],
                              n_resamples: int = N_RESAMPLES, alpha: float = ALPHA,
                              seed: int = SEED) -> BlockBootstrapResult:
    """Decision 12's approved primary procedure: `block_length=6`."""
    return block_bootstrap_beta(df, all_session_dates, PRIMARY_BLOCK_LENGTH, n_resamples, alpha, seed)


def sensitivity_single_day_cluster_bootstrap(df: pd.DataFrame, all_session_dates: list[dt.date],
                                               n_resamples: int = N_RESAMPLES, alpha: float = ALPHA,
                                               seed: int = SEED) -> BlockBootstrapResult:
    """Section 7C's prescribed sensitivity check: `block_length=1`
    (independent single-day clusters). Must never replace or be
    presented as the primary result -- callers should report both,
    labeled, side by side."""
    return block_bootstrap_beta(df, all_session_dates, SENSITIVITY_BLOCK_LENGTH, n_resamples, alpha, seed)


# ===========================================================================
# NULL-IMPOSED, ANCHOR-MATCHED RESIDUAL BLOCK BOOTSTRAP (p-value only)
#
# This is a SEPARATE procedure from the two functions above. It is used
# ONLY to compute the two-sided hypothesis-test p-value for H0: beta=0;
# it must NEVER be used to construct a confidence interval -- its own
# `beta_star` distribution is centered at/near zero BY CONSTRUCTION
# (the null is imposed), so it says nothing about where the true beta
# actually sits. CI/SE for beta remain the unrestricted
# `block_bootstrap_beta`/`primary_block_bootstrap`/
# `sensitivity_single_day_cluster_bootstrap` above, UNCHANGED.
#
# Algorithm (fully vectorized, no per-resample Python-level refit):
#   1. Fit the null (controls-only, no S_L) model once via `fit_ols`.
#   2. Index every real observation by (day position, anchor index),
#      using the APPROVED schedule (`non_overlapping_schedule`) to
#      derive the anchor set -- never hardcoded, never inferred from
#      row order.
#   3. Draw `ceil(n_days/L)` blocks of L consecutive day positions,
#      with replacement, exactly as `_build_overlapping_blocks` already
#      does; concatenate and truncate to `n_days` donor-day positions,
#      one per target-day position (unchanged mechanism).
#   4. For every real target observation, look up its assigned donor
#      day's null-model residual AT THE SAME ANCHOR. If the donor
#      lacks that anchor, the observation is excluded from this
#      resample -- never recycled, interpolated, or substituted.
#   5. Construct pseudo-Y = null_fitted(target) + matched donor
#      residual, for every surviving matched row; real covariates
#      (including S_L) are untouched.
#   6. Refit the complete, unmodified primary regression via weighted
#      normal equations (weight=1 for matched rows, 0 for excluded
#      ones) -- mathematically identical to dropping the excluded rows
#      and fitting OLS on the remainder, just computed via a single
#      batched matmul across all resamples at once instead of a
#      per-resample pandas refit.
#   7. A resample is RANK-DEFICIENT only if its weighted X'X rank falls
#      STRICTLY BELOW the real, full design's own baseline rank
#      (`k_eff`, computed once from the unresampled data) -- never
#      merely for matching that baseline. This matters because, for
#      the approved primary horizon h=60, every schedule anchor except
#      the first falls in the "midday" TOD bucket (verified from
#      `schedule.non_overlapping_schedule(60)`), so `TOD_closing_30` is
#      IDENTICALLY ZERO for every possible h=60 observation -- a
#      permanent, pre-existing rank deficiency of exactly one
#      dimension that `fit_ols`'s own `lstsq` already silently
#      resolves (via its minimum-norm solution) every time it is
#      called on real h=60 data. Every resample necessarily matches,
#      never falls below, this baseline on that account alone; a
#      resample is only flagged RANK-DEFICIENT for a genuine,
#      bootstrap-specific additional loss of identification (e.g. its
#      matched rows happen to also lose all TOD_opening_30 variation).
#      This is a numerical-solvability check tied to the data's own
#      achievable rank, not an arbitrary coverage-fraction or
#      condition-number threshold.
# ===========================================================================


@dataclass(frozen=True)
class NullImposedBootstrapResult:
    """Produces ONLY a hypothesis-test p-value for H0: beta=0. Deliberately
    carries NO `ci_low`/`ci_high`/`se` fields -- it is structurally
    impossible to misread this result as a confidence interval."""
    block_length: int
    n_session_positions: int
    n_blocks_available: int
    n_blocks_per_resample: int
    n_resamples_requested: int
    n_valid: int
    n_failed_empty_or_unmatched: int  # fewer matched rows than parameters
    n_failed_rank_deficient: int  # matched rows exist, but weighted X'X is ill-conditioned
    n_failed_total: int
    beta_hat: float  # the unrestricted point estimate -- for reference only, NOT a CI center here
    beta_star: np.ndarray  # length n_valid; the null-imposed bootstrap distribution, centered near 0
    p_value: float
    n_target_total: int
    retained_row_counts: np.ndarray  # length n_resamples_requested, for EVERY attempted resample (valid + failed)
    match_rate_mean: float
    match_rate_median: float
    match_rate_min: float
    match_rate_p05: float
    null_model_coefficients: dict
    k_eff: int  # the real, unresampled design's own achievable rank (<= number of parameters)
    zero_variance_regressors: tuple[str, ...]  # e.g. ("TOD_closing_30",) for h=60 -- permanent audit record
    seed: int


def null_imposed_block_bootstrap(
    df: pd.DataFrame,
    all_session_dates: list[dt.date],
    block_length: int,
    n_resamples: int = 10_000,
    alpha: float = ALPHA,
    seed: int = SEED,
    batch_size: int = 2000,
) -> NullImposedBootstrapResult:
    """See the module-level algorithm description above. `alpha` is
    carried through for interface symmetry with `block_bootstrap_beta`
    but only affects the caller's own significance decision
    (`p_value < alpha`); it does not change anything computed here."""
    required_cols = {"trade_date", "t", "horizon", "Y", *PRIMARY_REGRESSORS}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {missing}")
    horizons_present = df["horizon"].unique()
    if len(horizons_present) != 1:
        raise ValueError("df must contain exactly one horizon")
    horizon = int(horizons_present[0])

    # Point estimate and null-model fit: both via the EXISTING,
    # unmodified fitting code (fit_primary_regression, fit_ols) --
    # no new estimator introduced.
    beta_hat = fit_primary_regression(df).coefficients["S_L"]
    null_fit = fit_ols(df, "Y", REDUCED_CONTROLS)

    # --- anchor + day-position indexing, derived from the APPROVED
    # schedule function -- never hardcoded, never row-order-based. ---
    anchors = non_overlapping_schedule(horizon)
    anchor_index = {a: i for i, a in enumerate(anchors)}
    unknown_anchors = sorted(set(df["t"]) - set(anchors))
    if unknown_anchors:
        raise ValueError(
            f"df contains t values outside the approved schedule for horizon={horizon}: {unknown_anchors}"
        )

    day_index = {d: i for i, d in enumerate(all_session_dates)}
    missing_days = sorted(set(df["trade_date"]) - set(day_index))
    if missing_days:
        raise ValueError(f"df contains trade_dates not present in all_session_dates: {missing_days[:5]}")

    n_days = len(all_session_dates)
    n_anchors = len(anchors)
    df2 = df.reset_index(drop=True)
    day_pos_of_row = df2["trade_date"].map(day_index).to_numpy()
    anchor_idx_of_row = df2["t"].map(anchor_index).to_numpy()
    n_target_total = len(df2)
    if n_target_total == 0:
        raise ValueError("df has no rows")

    # X in the EXACT column order fit_ols uses: alpha(intercept), then PRIMARY_REGRESSORS.
    X = np.column_stack(
        [np.ones(n_target_total)] + [df2[c].to_numpy(dtype=float) for c in PRIMARY_REGRESSORS]
    )
    k = X.shape[1]
    s_l_col = 1 + PRIMARY_REGRESSORS.index("S_L")  # column 0 is the intercept
    null_fitted_target = df2["Y"].to_numpy(dtype=float) - null_fit.residuals

    # Donor residual grid, NaN where that (day, anchor) is not a real
    # retained observation at all.
    null_resid_grid = np.full((n_days, n_anchors), np.nan, dtype=float)
    null_resid_grid[day_pos_of_row, anchor_idx_of_row] = null_fit.residuals

    # Precomputed per-row outer products, flattened -- used once per
    # batch via a single (mask @ XXouter) matmul instead of looping.
    XXouter = np.einsum("ik,il->ikl", X, X).reshape(n_target_total, k * k)

    # **Structural-rank baseline, computed ONCE from the real, full,
    # unmasked design** -- NOT from any resample. For the approved
    # primary horizon (h=60), every schedule anchor except the first
    # falls in the "midday" TOD bucket (verified directly from
    # `schedule.non_overlapping_schedule(60)`), so `TOD_closing_30` is
    # IDENTICALLY ZERO across the entire universe of h=60 observations
    # -- a genuine, permanent rank deficiency of exactly one dimension
    # that `fit_ols`'s own `lstsq` already silently absorbs (via its
    # minimum-norm resolution, assigning that coefficient exactly 0)
    # every time it is called on real h=60 data, without ever flagging
    # it. This bootstrap's explicit per-resample solve must behave
    # consistently with that existing, already-approved method -- a
    # resample is only RANK-DEFICIENT (a bootstrap-specific failure) if
    # its rank falls BELOW this baseline, never merely for matching it.
    k_eff = int(np.linalg.matrix_rank(X.T @ X))
    # Explicit, named audit record of which regressor(s) have exactly
    # zero variance in the real data (the specific, common cause of a
    # baseline rank shortfall; a permanent STRUCTURED result field, not
    # merely a transient warning that could be missed in a real run).
    zero_variance_regressors = tuple(
        c for c in PRIMARY_REGRESSORS if np.var(df2[c].to_numpy(dtype=float)) == 0.0
    )
    if k_eff < k:
        import warnings
        zero_variance_desc = zero_variance_regressors or (
            "(none -- deficiency is a collinearity among otherwise-varying "
            "columns, not a single dead column)"
        )
        warnings.warn(
            f"null_imposed_block_bootstrap: the real design matrix has rank {k_eff} < {k} "
            f"parameters. Zero-variance regressor(s) identified: {zero_variance_desc}. "
            f"For h=60 specifically, TOD_closing_30 is identically zero because no approved h=60 anchor "
            f"falls in the closing-30 window -- a permanent property of the approved specification, not "
            f"introduced by this bootstrap; `fit_ols`'s own lstsq already resolves it silently via its "
            f"minimum-norm solution. The bootstrap treats k_eff as the baseline and only flags resamples "
            f"that fall BELOW it as rank-deficient failures -- see the result's own `k_eff` and "
            f"`zero_variance_regressors` fields for a permanent audit record of this run.",
            stacklevel=2,
        )

    blocks = _build_overlapping_blocks(all_session_dates, block_length)
    n_blocks_per_resample = math.ceil(n_days / block_length)
    offsets = np.arange(block_length)

    rng = np.random.default_rng(seed)

    beta_star_parts: list[np.ndarray] = []
    retained_counts_all = np.empty(n_resamples, dtype=np.int64)
    n_failed_empty = 0
    n_failed_rank = 0

    done = 0
    while done < n_resamples:
        this_batch = min(batch_size, n_resamples - done)

        chosen_block_starts = rng.integers(0, len(blocks), size=(this_batch, n_blocks_per_resample))
        donor_seq = (chosen_block_starts[:, :, None] + offsets[None, None, :]).reshape(this_batch, -1)[:, :n_days]

        donor_day_for_target = donor_seq[:, day_pos_of_row]  # (this_batch, n_target_total)
        gathered_resid = null_resid_grid[donor_day_for_target, anchor_idx_of_row]  # (this_batch, n_target_total)
        mask = ~np.isnan(gathered_resid)
        n_matched = mask.sum(axis=1)
        retained_counts_all[done:done + this_batch] = n_matched

        # NaN-safe: gathered_resid has NaN exactly where mask is False;
        # np.where replaces those positions with 0 before use, so no
        # NaN ever reaches the matmuls below (0 * NaN == NaN in IEEE
        # arithmetic, which is why this guard is necessary, not optional).
        y_star_safe = np.where(mask, null_fitted_target[None, :] + np.nan_to_num(gathered_resid, nan=0.0), 0.0)
        Z = y_star_safe  # already zero at excluded positions

        M = mask.astype(np.float64)
        XtWX = (M @ XXouter).reshape(this_batch, k, k)
        Xty = Z @ X  # (this_batch, k)

        empty = n_matched < k_eff  # can't possibly reach the baseline rank with this few rows
        considerable = ~empty

        ranks = np.zeros(this_batch, dtype=int)
        if considerable.any():
            ranks[considerable] = np.linalg.matrix_rank(XtWX[considerable])
        # Rank-deficient iff STRICTLY below the real design's own baseline
        # rank (k_eff) -- matching it (as every h=60 resample structurally
        # will, because of the permanent TOD_closing_30 zero column) is
        # normal, expected, and not a failure.
        rank_deficient = considerable & (ranks < k_eff)
        solvable = considerable & ~rank_deficient

        n_failed_empty += int(empty.sum())
        n_failed_rank += int(rank_deficient.sum())

        if solvable.any():
            # Minimum-norm (pseudo-inverse) solve -- consistent with
            # `fit_ols`'s own `lstsq` convention, so a resample whose
            # rank exactly matches the real design's baseline (the
            # normal h=60 case) resolves its own permanently-zero
            # column to coefficient 0, exactly as the existing,
            # unmodified point-estimation method already does.
            betas = np.einsum("rij,rj->ri", np.linalg.pinv(XtWX[solvable]), Xty[solvable])
            beta_star_parts.append(betas[:, s_l_col])

        done += this_batch

    beta_star = np.concatenate(beta_star_parts) if beta_star_parts else np.array([], dtype=float)
    n_valid = len(beta_star)
    if n_valid == 0:
        raise ValueError("null_imposed_block_bootstrap: every resample failed -- cannot derive a p-value")

    p_value = float((1 + np.sum(np.abs(beta_star) >= abs(beta_hat))) / (1 + n_valid))

    match_rates_all = retained_counts_all / n_target_total
    return NullImposedBootstrapResult(
        block_length=block_length, n_session_positions=n_days,
        n_blocks_available=len(blocks), n_blocks_per_resample=n_blocks_per_resample,
        n_resamples_requested=n_resamples, n_valid=n_valid,
        n_failed_empty_or_unmatched=n_failed_empty, n_failed_rank_deficient=n_failed_rank,
        n_failed_total=n_failed_empty + n_failed_rank,
        beta_hat=beta_hat, beta_star=beta_star, p_value=p_value,
        n_target_total=n_target_total, retained_row_counts=retained_counts_all,
        match_rate_mean=float(match_rates_all.mean()), match_rate_median=float(np.median(match_rates_all)),
        match_rate_min=float(match_rates_all.min()), match_rate_p05=float(np.percentile(match_rates_all, 5)),
        null_model_coefficients=dict(null_fit.coefficients),
        k_eff=k_eff, zero_variance_regressors=zero_variance_regressors, seed=seed,
    )


def primary_null_imposed_bootstrap(df: pd.DataFrame, all_session_dates: list[dt.date],
                                     n_resamples: int = 10_000, alpha: float = ALPHA,
                                     seed: int = SEED, batch_size: int = 2000) -> NullImposedBootstrapResult:
    """Decision 12's approved primary block length (`L=6`), null-imposed
    p-value procedure."""
    return null_imposed_block_bootstrap(df, all_session_dates, PRIMARY_BLOCK_LENGTH,
                                         n_resamples, alpha, seed, batch_size)


def sensitivity_null_imposed_bootstrap(df: pd.DataFrame, all_session_dates: list[dt.date],
                                         n_resamples: int = 10_000, alpha: float = ALPHA,
                                         seed: int = SEED, batch_size: int = 2000) -> NullImposedBootstrapResult:
    """Section 7C's single-day-cluster sensitivity check (`L=1`),
    null-imposed p-value procedure. Same function, different block
    length -- not a separate implementation."""
    return null_imposed_block_bootstrap(df, all_session_dates, SENSITIVITY_BLOCK_LENGTH,
                                         n_resamples, alpha, seed, batch_size)
