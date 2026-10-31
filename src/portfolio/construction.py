"""Portfolio construction for the momentum portfolio-construction study
(PREREGISTRATION_PORTFOLIO.md Section 4). New code -- no prior script in
this project has needed a concentration-controlled or weighted momentum
portfolio; `scripts/run_holdout_study1.py`'s own construction is a single
fixed point (full decile, equal weight) this module generalizes.
"""
from __future__ import annotations

import pandas as pd

DECILE_FRAC = 0.10  # unchanged from scripts/run_holdout_study1.py


def select_portfolio(pool: pd.DataFrame, concentration, weighting: str) -> pd.DataFrame:
    """`pool`: one rebalance date's eligible cross-section, columns
    [entity_id, value] (value = momentum_12_1). `concentration`: int
    (10/25/50, a fixed count) or the literal string "decile" (the
    `1 - DECILE_FRAC` quantile cutoff, the same variable-count
    construction `run_holdout_study1.py` uses). `weighting`: "equal" or
    "rank" (PREREGISTRATION_PORTFOLIO.md Section 4's own linear rank
    tilt, this study's own new construction).

    Returns [entity_id, weight, rank], weight summing to 1.0 (or an
    empty frame if `pool` itself is empty -- never pads a short
    cross-section to a target count)."""
    if pool.empty:
        return pd.DataFrame(columns=["entity_id", "weight", "rank"])

    ranked = pool.sort_values("value", ascending=False).reset_index(drop=True)
    if concentration == "decile":
        cutoff = pool["value"].quantile(1 - DECILE_FRAC)
        sel = ranked[ranked["value"] >= cutoff].copy()
    else:
        sel = ranked.head(int(concentration)).copy()
    if sel.empty:
        return pd.DataFrame(columns=["entity_id", "weight", "rank"])

    sel["rank"] = range(1, len(sel) + 1)
    n_sel = len(sel)
    if weighting == "equal":
        sel["weight"] = 1.0 / n_sel
    elif weighting == "rank":
        # Linear rank tilt: rank 1 (strongest momentum) gets n_sel
        # "shares" out of n_sel*(n_sel+1)/2 total; the weakest name in
        # the selection gets 1 share. PREREGISTRATION_PORTFOLIO.md
        # Section 4's own exact formula, stated there as this study's
        # own new construction, not a prior convention.
        shares = (n_sel - sel["rank"] + 1).astype(float)
        sel["weight"] = shares / shares.sum()
    else:
        raise ValueError(f"unknown weighting {weighting!r}")

    return sel[["entity_id", "weight", "rank"]].reset_index(drop=True)
