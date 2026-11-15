"""Decision 10 (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Revision 5, point 8): the revised, endpoint-specific missingness-
emulation diagnostic.

Two components, kept separate as the governing document requires:

  (A) **Pre-signal eligibility-mask emulation**: apply a synthetic mask
      that preserves WHICH Stage-A endpoint (`t-35`, `t-5`, or `t`)
      would have failed, re-run the exact Option 2 eligibility
      determination (`freeze_subset`, `stage_a_threshold_met`), and
      compare the masked outcome against the known, real ground truth.
      The caller supplies the real eligible-id list and real prices --
      this module never reads a database.
  (B) **Forward-endpoint diagnostic**: measures only how often, and
      under what synthetic missingness rate, Stage B's existing
      zero-tolerance whole-observation discard rule
      (`stage_b_observation_valid`) would trigger. **Never computes a
      partial forward return** -- the function below only ever asks
      the boolean question "does this frozen subset still pass Stage
      B," exactly the real rule, never a reweighted or substituted
      return.

Neither component uses a real `t+h` outcome VALUE to choose or tune a
mask/rate, and neither proves missing-at-random -- both are explicitly
disclosed limitations in the governing document, repeated here rather
than silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .eligibility import Bar, FrozenSubset, freeze_subset, stage_a_threshold_met, stage_b_observation_valid

SEED = 20261107


# ---------------------------------------------------------------------------
# (A) Pre-signal eligibility-mask emulation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MaskEmulationResult:
    mask_endpoint: str  # "t_minus_35" | "t_minus_5" | "t" -- diagnostic label only
    mask_fraction: float
    n_real_eligible: int
    n_masked_out: int
    n_surviving: int
    roster_tier_size: int
    real_breadth: float
    masked_breadth: float
    real_threshold_met: bool
    masked_threshold_met: bool
    surviving_members: tuple[str, ...]


def emulate_pre_signal_eligibility_mask(
    tier: str,
    real_eligible_ids: list[str],
    roster_tier_size: int,
    mask_fraction: float,
    mask_endpoint: str,
    seed: int = SEED,
) -> MaskEmulationResult:
    """Component A. Starting from the REAL, already-determined eligible
    set for one tier (`tier in {"leader","follower"}`), synthetically
    remove `mask_fraction` of them (uniformly, without replacement) to
    simulate additional missingness that would have been attributed to
    `mask_endpoint` specifically -- `mask_endpoint` is carried only as a
    diagnostic label (which endpoint this round of masking represents),
    it does not change the mechanics (removal from the eligible set is
    the correct emulation of ANY endpoint's failure, since Option 2's
    Stage A eligibility is already all-or-nothing across the three
    endpoints). Never uses `t+h` outcomes."""
    if mask_endpoint not in ("t_minus_35", "t_minus_5", "t"):
        raise ValueError(f"unknown mask_endpoint: {mask_endpoint!r}")
    if not (0.0 <= mask_fraction <= 1.0):
        raise ValueError("mask_fraction must be in [0, 1]")

    real_frozen = freeze_subset(tier, real_eligible_ids)
    real_threshold_met = stage_a_threshold_met(real_frozen, roster_tier_size)
    real_breadth = real_frozen.n / roster_tier_size if roster_tier_size > 0 else float("nan")

    rng = np.random.default_rng(seed)
    n_mask = round(mask_fraction * len(real_eligible_ids))
    n_mask = min(n_mask, len(real_eligible_ids))
    masked_out = set(rng.choice(real_eligible_ids, size=n_mask, replace=False)) if n_mask > 0 else set()
    surviving = [e for e in real_eligible_ids if e not in masked_out]

    masked_frozen = freeze_subset(tier, surviving)
    masked_threshold_met = stage_a_threshold_met(masked_frozen, roster_tier_size)
    masked_breadth = masked_frozen.n / roster_tier_size if roster_tier_size > 0 else float("nan")

    return MaskEmulationResult(
        mask_endpoint=mask_endpoint, mask_fraction=mask_fraction,
        n_real_eligible=len(real_eligible_ids), n_masked_out=len(masked_out),
        n_surviving=masked_frozen.n, roster_tier_size=roster_tier_size,
        real_breadth=real_breadth, masked_breadth=masked_breadth,
        real_threshold_met=real_threshold_met, masked_threshold_met=masked_threshold_met,
        surviving_members=masked_frozen.members,
    )


# ---------------------------------------------------------------------------
# (B) Forward-endpoint diagnostic: discard-frequency only, never a
# partial return.
# ---------------------------------------------------------------------------

_ALWAYS_PRESENT_VALID_BAR = Bar(open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0)


@dataclass(frozen=True)
class DiscardFrequencyResult:
    n_draws: int
    n_discarded: int
    discard_rate: float


def forward_endpoint_discard_frequency(
    frozen: FrozenSubset,
    per_entity_missing_prob: dict[str, float],
    n_draws: int = 1000,
    seed: int = SEED,
) -> DiscardFrequencyResult:
    """Component B. For each of `n_draws` Monte Carlo repetitions,
    independently mark each frozen member "missing at `t+h`" with its
    own supplied probability (`per_entity_missing_prob`, defaulting to
    0.0 for any member not present in that dict -- never silently
    assumed missing), and ask the REAL Stage B rule
    (`stage_b_observation_valid`) whether the observation would be
    discarded. Reports only the fraction of repetitions that would
    discard -- **no return value, partial or otherwise, is ever
    computed here.** A "present" draw uses a placeholder present-valid
    bar (its specific OHLCV values are never used by
    `stage_b_observation_valid`, which only calls `.present_valid()`),
    not a real price -- this function has no access to real `t+h`
    prices and does not need them to answer a yes/no discard question."""
    if frozen.n == 0:
        raise ValueError("forward_endpoint_discard_frequency called on an empty frozen subset")
    rng = np.random.default_rng(seed)
    probs = np.array([per_entity_missing_prob.get(e, 0.0) for e in frozen.members])
    if np.any((probs < 0) | (probs > 1)):
        raise ValueError("per_entity_missing_prob values must be in [0, 1]")

    n_discarded = 0
    for _ in range(n_draws):
        draws = rng.random(len(frozen.members))
        bars = {
            e: (None if draws[i] < probs[i] else _ALWAYS_PRESENT_VALID_BAR)
            for i, e in enumerate(frozen.members)
        }
        if not stage_b_observation_valid(frozen, bars):
            n_discarded += 1

    return DiscardFrequencyResult(n_draws=n_draws, n_discarded=n_discarded, discard_rate=n_discarded / n_draws)
