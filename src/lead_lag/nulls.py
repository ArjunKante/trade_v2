"""Section 16: null-generation machinery -- (a) timing null (per-day
circular shift), (b) selection null (B1 per-month independent redraw,
B2 fixed rank-position rule, both against a candidate pool disjoint
from the true leader tier), (e) placebo diagnostic (one shared random
placebo day per real response day, >=20 trading days away, same
intraday minute).

Every function here is pure and deterministic given a seed (Section 22:
`20261107`) and operates on an already-built regression dataset (the
`build_regression_dataset` DataFrame shape: `trade_date`, `t`, `horizon`,
`S_L`, `R_F`, `Momentum_F`, `Y`, `TOD_opening_30`, `TOD_closing_30`) plus,
for the selection null, caller-supplied real leader-return data (this
module has no database access of its own).

**This module never runs against real study data and never computes a
real beta, p-value, or significance result** -- every test in
`tests/test_lead_lag_nulls.py` uses synthetic fixtures with known,
constructed structure. Running this machinery against the real Phase 4
dataset is primary-gate (Phase 6) territory, not performed here or by
anything that calls this module in this codebase.

**(c) market-factor null and (d) reverse-direction diagnostic are not
implemented here** -- both are nested/alternative regression
specifications using machinery `regression.py` already provides
(`fit_ols` with a reduced or swapped regressor set), not new sampling
machinery; they do not belong in a null-GENERATION module.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .regression import fit_primary_regression

SEED = 20261107  # Section 22
N_DRAWS = 1000  # Section 14, 16 -- timing and selection nulls
PLACEBO_MIN_DAY_SEPARATION = 20  # Section 16e (original)


@dataclass(frozen=True)
class NullDrawResult:
    variant: str
    real_beta: float
    null_betas: np.ndarray
    two_sided_95th_abs: float
    passes: bool  # |real_beta| > 95th percentile of |null_betas|, two-sided
    n_draws_used: int  # may be < requested if some draws had no usable rows


def _two_sided_result(variant: str, real_beta: float, null_betas: np.ndarray) -> NullDrawResult:
    if len(null_betas) == 0:
        raise ValueError(f"{variant}: no usable null draws were produced")
    threshold = float(np.percentile(np.abs(null_betas), 95))
    return NullDrawResult(
        variant=variant, real_beta=real_beta, null_betas=null_betas,
        two_sided_95th_abs=threshold, passes=bool(abs(real_beta) > threshold),
        n_draws_used=len(null_betas),
    )


# ---------------------------------------------------------------------------
# (a) Timing null: per-day circular shift of Y; S_L keeps its real timestamps.
# ---------------------------------------------------------------------------

def timing_null_circular_shift(df: pd.DataFrame, n_draws: int = N_DRAWS,
                                 seed: int = SEED) -> NullDrawResult:
    """Section 16(a). Within each `trade_date`, cyclically rotate the `Y`
    values among that day's own rows (chronological order by `t`) by a
    random nonzero amount, leaving `S_L`/`R_F`/`Momentum_F`/`TOD_*` at
    their real values. A day with only one row is left unshifted (a
    1-element rotation is always the identity -- not an error, not
    skipped silently, just a no-op for that day)."""
    real_fit = fit_primary_regression(df)
    real_beta = real_fit.coefficients["S_L"]

    day_order: dict = {}
    for day, g in df.groupby("trade_date"):
        day_order[day] = g.sort_values("t").index.to_numpy()

    rng = np.random.default_rng(seed)
    null_betas = np.empty(n_draws)
    for i in range(n_draws):
        y = df["Y"].to_numpy(dtype=float).copy()
        for day, idx in day_order.items():
            n = len(idx)
            if n <= 1:
                continue
            shift = int(rng.integers(1, n))
            y[idx] = np.roll(y[idx], shift)
        shifted = df.copy()
        shifted["Y"] = y
        fit = fit_primary_regression(shifted)
        null_betas[i] = fit.coefficients["S_L"]

    return _two_sided_result("timing_null_a", real_beta, null_betas)


# ---------------------------------------------------------------------------
# (b) Selection null: B1 (per-month independent redraw) and B2 (fixed
# rank-position rule), against a candidate pool disjoint from the true
# leader tier (ranks n_leaders+1..3*n_leaders).
# ---------------------------------------------------------------------------

def _month_key(d: dt.date) -> tuple[int, int]:
    return (d.year, d.month)


def _refit_with_random_leader_signal(df: pd.DataFrame, s_l_random: np.ndarray) -> float:
    shifted = df.copy()
    shifted["S_L"] = s_l_random
    return fit_primary_regression(shifted).coefficients["S_L"]


def _b1_single_repetition(df: pd.DataFrame, candidate_pool_by_month: dict,
                            leader_portfolio_return_fn, n_leaders: int,
                            rng: np.random.Generator) -> np.ndarray:
    """One B1 repetition's `S_leader_random(t)` series: a fresh,
    independent draw for every calendar month present. Exposed
    separately so the per-month-independence property is directly
    testable without needing to run a full regression refit."""
    drawn_by_month: dict = {}
    s_l_random = np.empty(len(df))
    for pos, row in enumerate(df.itertuples(index=False)):
        month = _month_key(row.trade_date)
        if month not in drawn_by_month:
            pool = candidate_pool_by_month[month]
            if len(pool) < n_leaders:
                raise ValueError(f"candidate pool for {month} has fewer than n_leaders={n_leaders} entities")
            drawn_by_month[month] = rng.choice(pool, size=n_leaders, replace=False)
        s_l_random[pos] = leader_portfolio_return_fn(
            list(drawn_by_month[month]), row.trade_date, row.t
        )
    return s_l_random


def selection_null_b1(
    df: pd.DataFrame,
    candidate_pool_by_month: dict[tuple[int, int], list[str]],
    leader_portfolio_return_fn,
    n_leaders: int,
    n_repetitions: int = N_DRAWS,
    seed: int = SEED,
) -> NullDrawResult:
    """Section 16(b), Null B1: for each repetition, draw `n_leaders`
    entities uniformly without replacement from that month's disjoint
    candidate pool, INDEPENDENTLY for every calendar month.

    `leader_portfolio_return_fn(entity_ids, trade_date, t) -> float` is
    caller-supplied (this module has no database access): it must
    return the equal-weight `S_leader_random(t)` value for the given
    drawn portfolio at that real observation's `(trade_date, t)`, using
    the exact Section 8 signal-construction procedure on the real
    follower-side-fixed data. The real follower-side rows (`R_F`,
    `Momentum_F`, `TOD_*`, `Y`) are held fixed across every repetition,
    per Section 16(b) step 1."""
    real_fit = fit_primary_regression(df)
    real_beta = real_fit.coefficients["S_L"]
    rng = np.random.default_rng(seed)
    null_betas = np.empty(n_repetitions)

    for r in range(n_repetitions):
        s_l_random = _b1_single_repetition(df, candidate_pool_by_month, leader_portfolio_return_fn, n_leaders, rng)
        null_betas[r] = _refit_with_random_leader_signal(df, s_l_random)

    return _two_sided_result("selection_null_b1", real_beta, null_betas)


def _b2_single_repetition(df: pd.DataFrame, candidate_pool_by_month: dict,
                            leader_portfolio_return_fn, rank_positions: np.ndarray) -> np.ndarray:
    """One B2 repetition's `S_leader_random(t)` series, given one
    already-drawn set of rank-positions applied identically to every
    month. Exposed separately so the "same rank positions shared across
    months" property is directly testable."""
    s_l_random = np.empty(len(df))
    for pos, row in enumerate(df.itertuples(index=False)):
        month = _month_key(row.trade_date)
        pool = candidate_pool_by_month[month]
        drawn = [pool[k] for k in rank_positions]
        s_l_random[pos] = leader_portfolio_return_fn(drawn, row.trade_date, row.t)
    return s_l_random


def selection_null_b2(
    df: pd.DataFrame,
    candidate_pool_by_month: dict[tuple[int, int], list[str]],
    leader_portfolio_return_fn,
    n_leaders: int,
    n_repetitions: int = N_DRAWS,
    seed: int = SEED,
) -> NullDrawResult:
    """Section 16(b), Null B2: for each repetition, draw ONE random
    subset of `n_leaders` RANK-POSITIONS (not entity identities) within
    the disjoint band once, and apply that same rank-position rule to
    every month's own candidate pool for the rest of that repetition --
    entity identities vary month to month as the pool's membership
    shifts, but which rank-positions are selected does not.

    Each `candidate_pool_by_month[month]` list must already be ordered
    by rank (ascending), so index `k` means the same relative liquidity
    position in every month."""
    real_fit = fit_primary_regression(df)
    real_beta = real_fit.coefficients["S_L"]
    rng = np.random.default_rng(seed)
    null_betas = np.empty(n_repetitions)

    pool_size = len(next(iter(candidate_pool_by_month.values())))
    for month, pool in candidate_pool_by_month.items():
        if len(pool) != pool_size:
            raise ValueError("all months' candidate pools must have the same size for B2's rank-position rule")

    for r in range(n_repetitions):
        rank_positions = rng.choice(pool_size, size=n_leaders, replace=False)
        s_l_random = _b2_single_repetition(df, candidate_pool_by_month, leader_portfolio_return_fn, rank_positions)
        null_betas[r] = _refit_with_random_leader_signal(df, s_l_random)

    return _two_sided_result("selection_null_b2", real_beta, null_betas)


# ---------------------------------------------------------------------------
# (e) Placebo diagnostic: one shared random placebo day per real response
# day, >=20 trading days away, same intraday minute-of-day.
# ---------------------------------------------------------------------------

def _draw_shared_placebo_days(real_days: list, min_day_separation: int,
                                rng: np.random.Generator) -> dict:
    """One random placebo day per real day, shared by every row on that
    day (Section 16e's resolved, per-real-day-shared reading -- never
    an independent draw per follower-row)."""
    day_index = {d: i for i, d in enumerate(real_days)}
    assignment = {}
    for day in real_days:
        candidates = [d for d in real_days if abs(day_index[d] - day_index[day]) >= min_day_separation]
        assignment[day] = candidates[int(rng.integers(len(candidates)))] if candidates else None
    return assignment


def placebo_null(df: pd.DataFrame, n_draws: int = N_DRAWS,
                   min_day_separation: int = PLACEBO_MIN_DAY_SEPARATION,
                   seed: int = SEED) -> NullDrawResult:
    """Section 16(e). Never fits a contemporaneous, real signal-to-
    response relationship: substitutes, for every row on a given real
    day, the REAL `S_L` value realized on one shared placebo day (at the
    same `t`) in place of that day's own `S_L`. A row is dropped from a
    given draw only if no valid placebo day/minute pairing exists for
    it (e.g. the chosen placebo day has no observation at that `t`)."""
    real_fit = fit_primary_regression(df)
    real_beta = real_fit.coefficients["S_L"]

    real_days = sorted(df["trade_date"].unique())
    s_l_by_t_day = {t_val: dict(zip(g["trade_date"], g["S_L"])) for t_val, g in df.groupby("t")}

    rng = np.random.default_rng(seed)
    null_betas = []
    for _ in range(n_draws):
        placebo_day_for = _draw_shared_placebo_days(real_days, min_day_separation, rng)
        rows = []
        for row in df.itertuples(index=False):
            placebo_day = placebo_day_for.get(row.trade_date)
            if placebo_day is None:
                continue
            lut = s_l_by_t_day.get(row.t, {})
            if placebo_day not in lut:
                continue
            new_row = row._asdict()
            new_row["S_L"] = lut[placebo_day]
            rows.append(new_row)
        if not rows:
            continue
        shifted = pd.DataFrame(rows)
        null_betas.append(fit_primary_regression(shifted).coefficients["S_L"])

    return _two_sided_result("placebo_e", real_beta, np.array(null_betas))
