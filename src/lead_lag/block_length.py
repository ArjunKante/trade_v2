"""Decision 12: the bootstrap block-length `L` selection procedure
(`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 7B, final
form, reproduced in `PREREGISTRATION_LEAD_LAG_V1.md` Section 23's
Revision-5 summary).

Fully deterministic given three externally-supplied parameters that
this module deliberately does NOT choose for itself -- they remain
Decision 12's own open sub-parameters, to be set "by reference to
standard time-series-diagnostic/block-bootstrap practice once the
real, post-exclusion day counts are known," never invented here and
never chosen by looking at how favorable the resulting inference is:

  - `min_n_k`: the minimum number of valid pairwise-complete day-pairs
    for a lag to be evaluable at all.
  - `min_run_length` (`R`): the minimum consecutive qualifying run
    length (`R >= 2` by construction -- enforced here).
  - `min_usable_blocks`: the minimum number of usable blocks
    (`n_usable_days // L`) for the resulting `L` to support reliable
    block-bootstrap inference.

This module never fits the primary (`S_L`-including) regression, never
computes or inspects a real beta/p-value/effect size, and never reads
a real database -- it operates purely on an already-computed,
day-level-aggregated, hypothesis-predictor-free series (the controls-
only baseline-model residuals, signed or squared, Section 7B.1),
supplied by the caller as `{trading_session_position: value}`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

ACF_BAND_Z = 2.0  # the standard +/- 2/sqrt(n) large-sample white-noise band
INITIAL_MAX_LAG = 10
EXTENDED_MAX_LAG = 20
MIN_RUN_LENGTH_FLOOR = 2  # R >= 2 by construction (closes the isolated-terminal-lag loophole)


@dataclass(frozen=True)
class LagResult:
    lag: int
    acf: float | None  # None iff indeterminate (n_k < min_n_k)
    n_k: int
    qualifies: bool | None  # None = indeterminate; never silently True/False


def compute_acf_by_lag(values_by_position: dict[int, float], max_lag: int,
                        min_n_k: int) -> list[LagResult]:
    """Section 7B.3: exact pairwise-complete-case sample ACF, lag
    measured in true trading-session positions (gaps in
    `values_by_position`'s keys are real excluded days, never
    compressed out of the sequence). Mean and the normalizing sum of
    squared deviations are estimated once from every available
    position (the standard sample-ACF convention); the lag-`k`
    numerator uses only the pairs where both `i` and `i+k` have a
    valid value ("pairwise-complete"), which is the one deliberate,
    documented implementation choice this module makes beyond what
    Section 7B pins down verbatim -- the alternative (re-deriving a
    fresh local mean/variance from each lag's own pair subset) is
    non-standard and was not adopted."""
    if max_lag < 1:
        raise ValueError("max_lag must be >= 1")
    positions = sorted(values_by_position)
    all_vals = np.array([values_by_position[p] for p in positions], dtype=float)
    mean = float(all_vals.mean())
    denom = float(np.sum((all_vals - mean) ** 2))
    results: list[LagResult] = []
    for k in range(1, max_lag + 1):
        pairs = [(values_by_position[i], values_by_position[i + k])
                 for i in positions if (i + k) in values_by_position]
        n_k = len(pairs)
        if n_k < min_n_k:
            results.append(LagResult(lag=k, acf=None, n_k=n_k, qualifies=None))
            continue
        numerator = sum((x - mean) * (y - mean) for x, y in pairs)
        acf = numerator / denom if denom > 0 else 0.0
        band = ACF_BAND_Z / math.sqrt(n_k)
        results.append(LagResult(lag=k, acf=acf, n_k=n_k, qualifies=abs(acf) <= band))
    return results


def find_qualifying_block_length(lag_results: list[LagResult], min_run_length: int) -> int | None:
    """Section 7B.4: the smallest `L` such that every lag from `L`
    through the current maximum qualifies AND that run has length
    `>= min_run_length`. Equivalent to: walk backward from the maximum
    examined lag, counting a contiguous run of `qualifies is True`
    lags; an indeterminate (`None`) OR failing (`False`) lag BREAKS the
    run immediately -- never treated as qualifying, never skipped. If
    the resulting reach is `>= min_run_length`, the smallest valid `L`
    is `max_lag - reach + 1` (using the full reach); otherwise no
    qualifying run reaching the maximum exists in this range."""
    if min_run_length < MIN_RUN_LENGTH_FLOOR:
        raise ValueError(f"min_run_length must be >= {MIN_RUN_LENGTH_FLOOR} by construction (Section 7B.4)")
    if not lag_results:
        return None
    max_lag = lag_results[-1].lag
    by_lag = {r.lag: r for r in lag_results}
    reach = 0
    for k in range(max_lag, 0, -1):
        if by_lag[k].qualifies is True:
            reach += 1
        else:
            break
    return max_lag - reach + 1 if reach >= min_run_length else None


@dataclass(frozen=True)
class BlockLengthSeriesOutcome:
    L: int | None
    lag_results: list[LagResult]
    max_lag_examined: int  # 10 if found within the initial range, else 20


def freeze_block_length_one_series(values_by_position: dict[int, float],
                                    min_n_k: int, min_run_length: int) -> BlockLengthSeriesOutcome:
    """Section 7B.4's deterministic extension rule for ONE series:
    try range 1-10 first; if no qualifying run of length `>= min_run_length`
    reaching the current maximum is found, extend to 1-20 and reapply
    the identical criterion. Never extends past 20."""
    results = compute_acf_by_lag(values_by_position, INITIAL_MAX_LAG, min_n_k)
    L = find_qualifying_block_length(results, min_run_length)
    if L is not None:
        return BlockLengthSeriesOutcome(L=L, lag_results=results, max_lag_examined=INITIAL_MAX_LAG)
    results = compute_acf_by_lag(values_by_position, EXTENDED_MAX_LAG, min_n_k)
    L = find_qualifying_block_length(results, min_run_length)
    return BlockLengthSeriesOutcome(L=L, lag_results=results, max_lag_examined=EXTENDED_MAX_LAG)


@dataclass(frozen=True)
class BlockLengthDecision:
    status: str  # "OK" | "INCONCLUSIVE_NO_QUALIFYING_RUN" | "INCONCLUSIVE_TOO_FEW_USABLE_BLOCKS"
    L: int | None  # max(L_a, L_b) if both series found a run, else None
    series_a: BlockLengthSeriesOutcome
    series_b: BlockLengthSeriesOutcome
    n_usable_days: int
    min_usable_blocks: int
    usable_block_count: int | None  # n_usable_days // L, once L is known


def freeze_block_length(
    signed_residual_by_position: dict[int, float],
    squared_residual_by_position: dict[int, float],
    n_usable_days: int,
    min_n_k: int,
    min_run_length: int,
    min_usable_blocks: int,
) -> BlockLengthDecision:
    """Section 7B, end to end: apply the identical procedure to series
    (a) (signed controls-only baseline residuals) and (b) (the same
    residuals, squared); take the LARGER of the two resulting `L`
    values as the single predeclared block length; then check the
    implied usable-block count. `INCONCLUSIVE` in either failure mode
    is reported honestly, never resolved by shrinking `L`, `R`, or
    `min_n_k` to manufacture a usable result."""
    outcome_a = freeze_block_length_one_series(signed_residual_by_position, min_n_k, min_run_length)
    outcome_b = freeze_block_length_one_series(squared_residual_by_position, min_n_k, min_run_length)

    if outcome_a.L is None or outcome_b.L is None:
        return BlockLengthDecision(
            status="INCONCLUSIVE_NO_QUALIFYING_RUN", L=None,
            series_a=outcome_a, series_b=outcome_b,
            n_usable_days=n_usable_days, min_usable_blocks=min_usable_blocks,
            usable_block_count=None,
        )

    L = max(outcome_a.L, outcome_b.L)
    usable_blocks = n_usable_days // L
    status = "OK" if usable_blocks >= min_usable_blocks else "INCONCLUSIVE_TOO_FEW_USABLE_BLOCKS"
    return BlockLengthDecision(
        status=status, L=L, series_a=outcome_a, series_b=outcome_b,
        n_usable_days=n_usable_days, min_usable_blocks=min_usable_blocks,
        usable_block_count=usable_blocks,
    )
