"""Option 2 frozen-subset construction: Stage A pre-signal eligibility
and Stage B forward-endpoint completeness (Decisions 17, 19, 20).

Stage A (steps 1-6 of the proposal's 9-step construction):
  1. Start with the fixed monthly roster (one tier at a time).
  2. A name is eligible iff PRESENT-VALID at `t-35`, `t-5`, AND `t`
     (joint, all-or-nothing) AND not inside its own corporate-action
     exclusion window at any of those three endpoints (Decision 20,
     folded into this same check, not a separate filter).
  3. Freeze the eligible subset and equal weights (`1/n_eligible`).
  4. Apply the minimum-breadth threshold to the frozen subset:
     `n_frozen / n_roster_tier >= 0.70` (Decision 19) -- the denominator
     is the ORIGINAL monthly roster-tier size, not the frozen subset's
     own size.
  5. If not met, the observation is ineligible for that tier -- no
     substitution.
  6. If met, the same frozen subset/weights are used for every control
     that needs them (`R_F`, `Y`, `Momentum_F`).

Stage B (steps 7-9), per horizon `h`, strictly after freezing:
  7. Check `t+h` PRESENT-VALID for every frozen-subset member.
  8. If ANY member fails, discard the ENTIRE observation for that
     horizon -- never reweight, substitute, or partially return.
  9. (Stated, not enforced in code: this still leaves
     observation-selection/informative-censoring dependence on `t+h`,
     even though constituent-selection dependence is eliminated by the
     freeze in steps 2-3.)
"""
from __future__ import annotations

import bisect
import datetime as dt
from dataclasses import dataclass

import duckdb
import pandas as pd

from .validity import is_present_valid, classify_gap

STAGE_A_THRESHOLD = 0.70  # Decision 19


@dataclass(frozen=True)
class Bar:
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None

    def present_valid(self) -> bool:
        return is_present_valid(self.open, self.high, self.low, self.close, self.volume)


@dataclass(frozen=True)
class EndpointObservation:
    """Everything needed to resolve one Stage A endpoint (`t-35`, `t-5`,
    or `t`) under Decision 17's short-gap rule.

    `present=True`: a row exists at this exact nominal timestamp; its
    own OHLCV is `bar`. If that row is category A1/D (`bar.present_valid()`
    is True), it is used directly. If it is category B1 or E
    (`present_valid()` False), it is REJECTED outright -- never imputed,
    never substituted, regardless of surrounding gap length.

    `present=False`: a true absent expected timestamp, belonging to one
    contiguous absence run, within a specific trading `session`. The run
    is bounded by two ACTUAL PRESENT-VALID rows:

    - `prev_present_valid_epoch` / `prev_present_valid_price` /
      `prev_present_valid_session`: the nearest PRECEDING present-valid
      row (skipping over any number of intervening true absences or
      B1/E rows).
    - `next_present_valid_epoch` / `next_present_valid_session`: the
      nearest FOLLOWING present-valid row (skipping over the same).
      **This is the run's real upper bound -- never the specific missing
      endpoint's own nominal timestamp.** Decision 17's duration is
      `next_present_valid_epoch - prev_present_valid_epoch`, the same
      pair for every missing timestamp inside one run, regardless of
      which one is being resolved.

    **Explicit same-session enforcement**: `session` is this endpoint's
    own trading session; `prev_present_valid_session` /
    `next_present_valid_session` are the sessions the two bounds were
    actually found in. The resolver checks these directly -- it no
    longer relies on elapsed duration alone (a `>=180`s gap) to reject a
    cross-session bound; a bound from a different session, or a session
    that cannot be established at all, is rejected outright regardless
    of how small its elapsed-second value happens to be. The caller
    still finds the bounds (never treating a B1/E row as one), but must
    now also report which session each bound came from; it must never
    default a missing bound session to this endpoint's own session --
    an unknown bound session is a rejection, not a pass-through.
    `this_epoch` (this slot's own nominal timestamp) is retained for
    diagnostics only -- it is NOT an input to the duration calculation
    below."""
    present: bool
    session: dt.date | None = None
    bar: Bar | None = None
    this_epoch: float | None = None
    prev_present_valid_epoch: float | None = None
    prev_present_valid_price: float | None = None
    prev_present_valid_session: dt.date | None = None
    next_present_valid_epoch: float | None = None
    next_present_valid_session: dt.date | None = None


@dataclass(frozen=True)
class ResolvedEndpoint:
    """The outcome of resolving one Stage A endpoint: whether it is
    usable at all, and if so, which price to use and why."""
    valid: bool
    price: float | None
    source: str  # "present" | "forward_filled" | "rejected_present_invalid" | "rejected_no_prior_bar" | "rejected_no_next_bar" | "rejected_gap_too_long" | "rejected_session_unknown" | "rejected_prev_cross_session" | "rejected_next_cross_session"
    elapsed_seconds: float | None = None
    bounding_prev_epoch: float | None = None
    bounding_next_epoch: float | None = None


def resolve_stage_a_endpoint(obs: EndpointObservation) -> ResolvedEndpoint:
    """Decision 17, Stage A: resolve one endpoint, applying the
    exact-duration short-gap rule (`<180`s forward-fillable, `>=180`s
    excluded -- 180 itself excluded). Only a true absence is ever
    eligible for forward-fill; a present B1/E row's own timestamp is
    never imputed and its own value is never used.

    The gap duration is computed from the run's two actual bounding
    PRESENT-VALID rows (`prev_present_valid_epoch`,
    `next_present_valid_epoch`) -- NOT from the specific missing
    endpoint's own nominal timestamp (`obs.this_epoch`). If
    `next_present_valid_epoch` is not available (the run never closes
    within the session, or the caller could not establish it), no bound
    is invented and no fill is permitted.

    **Explicit same-session enforcement**: before any duration
    arithmetic, each bound's session is checked directly against
    `obs.session` -- a bound from a different session, or a bound whose
    session could not be established, is rejected outright. This is a
    real check on `session`/`prev_present_valid_session`/
    `next_present_valid_session`, not an inference from elapsed seconds;
    a bound is never accepted merely because its elapsed-second value
    happens to be small."""
    if obs.present:
        if obs.bar is not None and obs.bar.present_valid():
            return ResolvedEndpoint(valid=True, price=obs.bar.close, source="present")
        return ResolvedEndpoint(valid=False, price=None, source="rejected_present_invalid")
    if obs.session is None:
        return ResolvedEndpoint(valid=False, price=None, source="rejected_session_unknown")
    if obs.prev_present_valid_epoch is None:
        return ResolvedEndpoint(valid=False, price=None, source="rejected_no_prior_bar")
    if obs.prev_present_valid_session is None or obs.prev_present_valid_session != obs.session:
        return ResolvedEndpoint(valid=False, price=None, source="rejected_prev_cross_session",
                                 bounding_prev_epoch=obs.prev_present_valid_epoch)
    if obs.next_present_valid_epoch is None:
        return ResolvedEndpoint(valid=False, price=None, source="rejected_no_next_bar",
                                 bounding_prev_epoch=obs.prev_present_valid_epoch)
    if obs.next_present_valid_session is None or obs.next_present_valid_session != obs.session:
        return ResolvedEndpoint(valid=False, price=None, source="rejected_next_cross_session",
                                 bounding_prev_epoch=obs.prev_present_valid_epoch,
                                 bounding_next_epoch=obs.next_present_valid_epoch)
    gap = classify_gap(obs.prev_present_valid_epoch, obs.next_present_valid_epoch)
    if gap.forward_fillable:
        return ResolvedEndpoint(
            valid=True, price=obs.prev_present_valid_price, source="forward_filled",
            elapsed_seconds=gap.elapsed_seconds,
            bounding_prev_epoch=obs.prev_present_valid_epoch, bounding_next_epoch=obs.next_present_valid_epoch,
        )
    return ResolvedEndpoint(
        valid=False, price=None, source="rejected_gap_too_long",
        elapsed_seconds=gap.elapsed_seconds,
        bounding_prev_epoch=obs.prev_present_valid_epoch, bounding_next_epoch=obs.next_present_valid_epoch,
    )


def ca_exclusion_window(ex_date: dt.date, governing_dates: list[dt.date]) -> frozenset[dt.date]:
    """Decision 20: the existing `+/-1`-trading-day corporate-action
    window, resolved against the governing exchange-session calendar
    (not raw calendar days). Returns {prev_session, ex_date, next_session}.
    `governing_dates` must be sorted ascending."""
    idx = bisect.bisect_left(governing_dates, ex_date)
    window = {ex_date}
    if idx < len(governing_dates) and governing_dates[idx] == ex_date:
        if idx > 0:
            window.add(governing_dates[idx - 1])
        if idx + 1 < len(governing_dates):
            window.add(governing_dates[idx + 1])
    else:
        # ex_date itself is not a governing session (should not normally
        # happen for a real corporate action, but handled defensively,
        # not silently): bracket with the nearest governing sessions.
        if idx > 0:
            window.add(governing_dates[idx - 1])
        if idx < len(governing_dates):
            window.add(governing_dates[idx])
    return frozenset(window)


def load_ca_exclusion_windows(
    con: duckdb.DuckDBPyConnection,
    entity_ids: tuple[str, ...],
    governing_dates: list[dt.date],
) -> dict[str, frozenset[dt.date]]:
    """[entity_id -> set of excluded trade_dates], from `corporate_actions`
    joined through `isin_lineage` (Decision 20). Read-only."""
    if not entity_ids:
        return {}
    placeholders = ",".join(["?"] * len(entity_ids))
    q = f"""
        SELECT l.entity_id, ca.ex_date
        FROM corporate_actions ca
        JOIN isin_lineage l ON ca.isin = l.isin
        WHERE l.entity_id IN ({placeholders})
    """
    df = con.execute(q, list(entity_ids)).fetchdf()
    out: dict[str, set[dt.date]] = {}
    for entity_id, ex_date in zip(df["entity_id"], df["ex_date"]):
        ex_date = pd.Timestamp(ex_date).date()
        out.setdefault(entity_id, set()).update(ca_exclusion_window(ex_date, governing_dates))
    return {k: frozenset(v) for k, v in out.items()}


def name_in_ca_window(entity_id: str, d: dt.date, ca_windows: dict[str, frozenset[dt.date]]) -> bool:
    return d in ca_windows.get(entity_id, frozenset())


@dataclass(frozen=True)
class NameEligibilityResult:
    entity_id: str
    eligible: bool
    reason: str  # "eligible" | "ca_window" | "t_minus_35_rejected" | "t_minus_5_rejected" | "t_rejected"
    resolved_t_minus_35: ResolvedEndpoint | None = None
    resolved_t_minus_5: ResolvedEndpoint | None = None
    resolved_t: ResolvedEndpoint | None = None


def stage_a_name_eligible(
    entity_id: str,
    obs_t_minus_35: EndpointObservation,
    obs_t_minus_5: EndpointObservation,
    obs_t: EndpointObservation,
    trade_date: dt.date,
    ca_windows: dict[str, frozenset[dt.date]],
) -> NameEligibilityResult:
    """One name's Stage A eligibility: each of the three endpoints is
    resolved under Decision 17's short-gap rule (`resolve_stage_a_endpoint`),
    jointly, all-or-nothing, AND the name must not be inside its own CA
    window on `trade_date` (Decision 20 -- the CA window is date-level,
    applying identically to all three same-day endpoints, since `t-35`,
    `t-5`, `t` all fall on `trade_date` by the existing same-session
    construction). The short-gap forward-fill rule is applied here, at
    Stage A, and nowhere else -- Stage B (`stage_b_observation_valid`)
    never calls this function or `resolve_stage_a_endpoint`."""
    if name_in_ca_window(entity_id, trade_date, ca_windows):
        return NameEligibilityResult(entity_id, False, "ca_window")

    r35 = resolve_stage_a_endpoint(obs_t_minus_35)
    if not r35.valid:
        return NameEligibilityResult(entity_id, False, "t_minus_35_rejected", resolved_t_minus_35=r35)
    r5 = resolve_stage_a_endpoint(obs_t_minus_5)
    if not r5.valid:
        return NameEligibilityResult(entity_id, False, "t_minus_5_rejected", resolved_t_minus_35=r35, resolved_t_minus_5=r5)
    rt = resolve_stage_a_endpoint(obs_t)
    if not rt.valid:
        return NameEligibilityResult(entity_id, False, "t_rejected", resolved_t_minus_35=r35, resolved_t_minus_5=r5, resolved_t=rt)

    return NameEligibilityResult(entity_id, True, "eligible", r35, r5, rt)


@dataclass(frozen=True)
class FrozenSubset:
    tier: str
    members: tuple[str, ...]
    weights: dict[str, float]  # equal-weight, 1/n

    @property
    def n(self) -> int:
        return len(self.members)


def freeze_subset(tier: str, eligible_entity_ids: list[str]) -> FrozenSubset:
    """Step 3: freeze membership and equal weights. No further
    addition/removal/substitution for this observation."""
    members = tuple(sorted(eligible_entity_ids))
    n = len(members)
    weights = {e: 1.0 / n for e in members} if n else {}
    return FrozenSubset(tier=tier, members=members, weights=weights)


def stage_a_threshold_met(frozen: FrozenSubset, roster_tier_size: int,
                           threshold: float = STAGE_A_THRESHOLD) -> bool:
    """Step 4: Decision 19's own Stage-A threshold, evaluated on the
    already-frozen subset, against the ORIGINAL roster-tier size."""
    if roster_tier_size <= 0:
        return False
    return (frozen.n / roster_tier_size) >= threshold


def stage_b_observation_valid(frozen: FrozenSubset, bars_t_plus_h: dict[str, Bar | None]) -> bool:
    """Steps 7-8: zero-tolerance forward check. True iff `frozen` is
    non-empty AND EVERY frozen-subset member has a PRESENT-VALID bar at
    `t+h`. A single failure discards the entire observation -- never
    reweight, substitute, or return a partial portfolio return.

    **Correction, this revision**: an empty frozen subset must never
    pass this check. The prior implementation's `for` loop over zero
    members vacuously completed without ever finding a failure, so an
    empty subset was incorrectly treated as "valid" -- there is nothing
    to compute a portfolio return over, and this is never a legitimate
    observation. (In practice `freeze_subset` combined with
    `stage_a_threshold_met` already prevents an empty subset from
    reaching this function, since `0/n_roster_tier` can never meet the
    70% threshold for a non-empty roster -- but this function no longer
    relies on that upstream guarantee holding.)"""
    if frozen.n == 0:
        return False
    for entity_id in frozen.members:
        bar = bars_t_plus_h.get(entity_id)
        if bar is None or not bar.present_valid():
            return False
    return True
