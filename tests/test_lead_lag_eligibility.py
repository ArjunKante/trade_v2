"""Decisions 17, 19, 20: Stage A pre-signal eligibility (exact-duration
short-gap resolution, freeze, 70% threshold, CA exclusion) and Stage B
zero-tolerance forward check."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag.eligibility import (
    Bar,
    EndpointObservation,
    ResolvedEndpoint,
    resolve_stage_a_endpoint,
    stage_a_name_eligible,
    freeze_subset,
    stage_a_threshold_met,
    stage_b_observation_valid,
    ca_exclusion_window,
)

VALID = Bar(open=100, high=101, low=99, close=100.5, volume=500)
STRUCT_INVALID = Bar(open=-5, high=-5, low=-5, close=-5, volume=0)
ZERO_VOL_NONFLAT = Bar(open=100, high=101, low=99, close=100.5, volume=0)

T0 = 1_000_000.0  # arbitrary epoch anchor

SESSION = dt.date(2026, 6, 15)
OTHER_SESSION = dt.date(2026, 6, 16)  # a different trading session


def present_obs(bar, session=SESSION):
    return EndpointObservation(present=True, session=session, bar=bar)


def absent_obs(prev_epoch, prev_price, next_epoch, this_epoch=None,
                session=SESSION, prev_session=SESSION, next_session=SESSION):
    """`prev_epoch`/`next_epoch` are the run's two ACTUAL bounding
    PRESENT-VALID timestamps. `this_epoch` (the specific missing
    endpoint's own nominal timestamp) is optional and, per the
    correction, must have NO effect on the resolver's decision --
    several tests below deliberately vary it while holding
    prev/next fixed to prove this. `session`/`prev_session`/
    `next_session` default to the SAME session (matching every prior
    test's implicit same-session assumption); the explicit
    session-enforcement tests below override one or more of them to
    prove cross-session bounds are rejected regardless of elapsed
    seconds."""
    return EndpointObservation(present=False, session=session, this_epoch=this_epoch,
                                prev_present_valid_epoch=prev_epoch,
                                prev_present_valid_price=prev_price,
                                prev_present_valid_session=prev_session,
                                next_present_valid_epoch=next_epoch,
                                next_present_valid_session=next_session)


# ---- Stage A: exact-duration short-gap resolution (corrected: uses the
# run's actual prev/next PRESENT-VALID bounds, never the missing
# endpoint's own nominal timestamp) ----

def test_bounding_observations_120_seconds_apart_fill_permitted():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is True
    assert r.source == "forward_filled"
    assert r.price == 100.0
    assert r.elapsed_seconds == 120


def test_bounding_observations_exactly_180_seconds_apart_rejected():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 180)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_gap_too_long"
    assert r.elapsed_seconds == 180


def test_bounding_observations_more_than_180_seconds_apart_rejected():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 181)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_gap_too_long"
    assert r.elapsed_seconds == 181


def test_multiple_consecutive_missing_timestamps_use_the_same_run_bounds_not_own_position():
    """Decision 17: every missing timestamp inside ONE absence run must
    be classified using the SAME (prev, next) bounding pair -- the
    classification must not become more permissive merely because an
    earlier (or later) missing timestamp within the run is being
    resolved. Here the run spans [T0+60, T0+120] (two missing minutes),
    bounded by a present-valid bar at T0 and the next at T0+180 (total
    180s -- rejected). Resolving EITHER missing minute, with the SAME
    prev/next bounds, must give the identical (rejected) answer,
    regardless of each one's own nominal position (`this_epoch`)."""
    prev_epoch, next_epoch = T0, T0 + 180
    obs_first_missing_minute = absent_obs(prev_epoch=prev_epoch, prev_price=100.0,
                                           next_epoch=next_epoch, this_epoch=T0 + 60)
    obs_second_missing_minute = absent_obs(prev_epoch=prev_epoch, prev_price=100.0,
                                            next_epoch=next_epoch, this_epoch=T0 + 120)
    r1 = resolve_stage_a_endpoint(obs_first_missing_minute)
    r2 = resolve_stage_a_endpoint(obs_second_missing_minute)
    assert r1.valid is False and r1.source == "rejected_gap_too_long" and r1.elapsed_seconds == 180
    assert r2.valid is False and r2.source == "rejected_gap_too_long" and r2.elapsed_seconds == 180
    assert r1.elapsed_seconds == r2.elapsed_seconds  # position-independent


def test_multiple_consecutive_missing_timestamps_fillable_run_both_resolve_identically():
    """Same structural test as above, but for a genuinely fillable run
    (120s total), confirming position-independence in the fillable
    direction too, not only the rejected direction."""
    prev_epoch, next_epoch = T0, T0 + 120
    obs_a = absent_obs(prev_epoch=prev_epoch, prev_price=55.5, next_epoch=next_epoch, this_epoch=T0 + 60)
    obs_b = absent_obs(prev_epoch=prev_epoch, prev_price=55.5, next_epoch=next_epoch, this_epoch=T0 + 90)
    r_a, r_b = resolve_stage_a_endpoint(obs_a), resolve_stage_a_endpoint(obs_b)
    assert r_a.valid is True and r_a.source == "forward_filled" and r_a.price == 55.5
    assert r_b.valid is True and r_b.source == "forward_filled" and r_b.price == 55.5
    assert r_a.elapsed_seconds == r_b.elapsed_seconds == 120


def test_missing_next_present_valid_bound_permits_no_fill():
    """If the run never closes (no next PRESENT-VALID bar could be
    established -- e.g. it would run past session end), no bound is
    invented and no fill is permitted."""
    obs = EndpointObservation(present=False, session=SESSION, this_epoch=T0 + 60,
                               prev_present_valid_epoch=T0, prev_present_valid_price=100.0,
                               prev_present_valid_session=SESSION,
                               next_present_valid_epoch=None)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_no_next_bar"


def test_cross_session_bound_is_never_fillable_even_if_supplied():
    """Belt-and-suspenders: even with explicit session fields correctly
    set to the SAME session throughout (so the explicit check below
    would not catch a mislabeling), a real cross-session gap is still
    orders of magnitude larger than 180 seconds, so the exact-duration
    rule independently rejects it too. This test exercises the
    magnitude-based layer specifically; `test_prev_bound_from_another_
    session_is_rejected` and `test_next_bound_from_another_session_is_
    rejected` below exercise the EXPLICIT session-field check, which
    fires even when elapsed seconds would otherwise be small."""
    same_session_close_epoch = dt.datetime(2026, 6, 15, 15, 29).timestamp()
    next_session_open_epoch = dt.datetime(2026, 6, 16, 9, 15).timestamp()
    obs = absent_obs(prev_epoch=same_session_close_epoch, prev_price=100.0,
                      next_epoch=next_session_open_epoch)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_gap_too_long"
    assert r.elapsed_seconds > 180


# ---- Explicit same-session enforcement: the resolver checks
# `session`/`prev_present_valid_session`/`next_present_valid_session`
# directly. These tests use a SMALL elapsed-second value throughout
# (well under 180s) specifically to prove the session check fires on
# its own -- NOT because the gap happens to be large. ----

def test_same_session_bounds_normal_fill_behavior_preserved():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120,
                      session=SESSION, prev_session=SESSION, next_session=SESSION)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is True
    assert r.source == "forward_filled"
    assert r.price == 100.0


def test_prev_bound_from_another_session_is_rejected():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120,
                      session=SESSION, prev_session=OTHER_SESSION, next_session=SESSION)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_prev_cross_session"
    assert r.elapsed_seconds is None  # rejected before any duration arithmetic


def test_next_bound_from_another_session_is_rejected():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120,
                      session=SESSION, prev_session=SESSION, next_session=OTHER_SESSION)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_next_cross_session"
    assert r.elapsed_seconds is None


def test_target_session_differs_from_both_bounds_is_rejected():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120,
                      session=OTHER_SESSION, prev_session=SESSION, next_session=SESSION)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_prev_cross_session"


def test_missing_target_session_is_rejected():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120, session=None)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_session_unknown"


def test_missing_prev_bound_session_is_rejected():
    """The prev bound's epoch/price are present but its session is
    unknown -- must not be silently defaulted to the target's own
    session; a missing bound session is a rejection, not a pass."""
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120,
                      prev_session=None)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_prev_cross_session"


def test_missing_next_bound_session_is_rejected():
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120,
                      next_session=None)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_next_cross_session"


def test_absent_with_no_prior_bar_is_rejected():
    obs = EndpointObservation(present=False, session=SESSION, this_epoch=T0,
                               prev_present_valid_epoch=None,
                               next_present_valid_epoch=T0 + 60)
    r = resolve_stage_a_endpoint(obs)
    assert r.valid is False
    assert r.source == "rejected_no_prior_bar"


def test_structurally_invalid_bar_in_the_run_is_never_used_as_a_bound_or_price():
    """A present-but-structurally-invalid (E) bar sitting inside an
    absence run must never be treated as a bound (present-valid) or as
    the fill price -- it must be skipped over by whoever constructs the
    bounding pair (verified here at the EndpointObservation/resolver
    contract level: an E bar's own close is never what gets used)."""
    e_bar = STRUCT_INVALID
    assert e_bar.present_valid() is False  # confirms it would never qualify as a bound
    # the caller must skip past it; simulate the correctly-skipped result:
    obs = absent_obs(prev_epoch=T0, prev_price=100.0, next_epoch=T0 + 120)
    r = resolve_stage_a_endpoint(obs)
    assert r.price == 100.0  # the real present-valid price, never the E bar's own value
    assert r.price != e_bar.close


def test_present_valid_bar_used_directly_no_gap_logic():
    r = resolve_stage_a_endpoint(present_obs(VALID))
    assert r.valid is True
    assert r.source == "present"
    assert r.price == VALID.close
    assert r.elapsed_seconds is None


def test_b1_own_timestamp_never_imputed_rejected_regardless_of_gap():
    """A present B1 (zero-volume, non-flat) row is rejected outright --
    it is never treated as if absent, so no forward-fill logic is even
    consulted for it."""
    r = resolve_stage_a_endpoint(present_obs(ZERO_VOL_NONFLAT))
    assert r.valid is False
    assert r.source == "rejected_present_invalid"


def test_e_own_timestamp_never_imputed_rejected_regardless_of_gap():
    r = resolve_stage_a_endpoint(present_obs(STRUCT_INVALID))
    assert r.valid is False
    assert r.source == "rejected_present_invalid"


def test_stage_a_name_eligible_uses_forward_fill_for_genuine_absence():
    d = dt.date(2026, 6, 1)
    obs35 = present_obs(VALID)
    obs5 = present_obs(VALID)
    obs_t = absent_obs(prev_epoch=T0, prev_price=99.0, next_epoch=T0 + 100)  # <180s -> fillable
    result = stage_a_name_eligible("E1", obs35, obs5, obs_t, d, {})
    assert result.eligible is True
    assert result.resolved_t.source == "forward_filled"
    assert result.resolved_t.price == 99.0


def test_stage_a_name_eligible_rejects_when_gap_too_long():
    d = dt.date(2026, 6, 1)
    obs35 = present_obs(VALID)
    obs5 = present_obs(VALID)
    obs_t = absent_obs(prev_epoch=T0, prev_price=99.0, next_epoch=T0 + 200)  # >=180s
    result = stage_a_name_eligible("E1", obs35, obs5, obs_t, d, {})
    assert result.eligible is False
    assert result.reason == "t_rejected"


def test_stage_a_name_eligible_excludes_name_inside_its_own_ca_window():
    d = dt.date(2026, 6, 1)
    ca_windows = {"E1": frozenset({d})}
    result = stage_a_name_eligible("E1", present_obs(VALID), present_obs(VALID), present_obs(VALID), d, ca_windows)
    assert result.eligible is False
    assert result.reason == "ca_window"
    # a different entity on the same date is unaffected
    result2 = stage_a_name_eligible("E2", present_obs(VALID), present_obs(VALID), present_obs(VALID), d, ca_windows)
    assert result2.eligible is True


def test_ca_exclusion_window_brackets_ex_date_with_adjacent_governing_sessions():
    governing = [dt.date(2026, 6, 1), dt.date(2026, 6, 2), dt.date(2026, 6, 3), dt.date(2026, 6, 4)]
    window = ca_exclusion_window(dt.date(2026, 6, 2), governing)
    assert window == frozenset({dt.date(2026, 6, 1), dt.date(2026, 6, 2), dt.date(2026, 6, 3)})


# ---- Freeze + Stage A threshold ----

def test_freeze_subset_equal_weights_sum_to_one():
    frozen = freeze_subset("follower", ["E3", "E1", "E2"])
    assert frozen.members == ("E1", "E2", "E3")
    assert frozen.n == 3
    assert abs(sum(frozen.weights.values()) - 1.0) < 1e-12


def test_stage_a_threshold_exact_boundary():
    frozen70 = freeze_subset("follower", [f"E{i}" for i in range(112)])
    assert stage_a_threshold_met(frozen70, roster_tier_size=160) is True  # 112/160 = 0.70
    frozen69 = freeze_subset("follower", [f"E{i}" for i in range(111)])
    assert stage_a_threshold_met(frozen69, roster_tier_size=160) is False


def test_stage_a_threshold_denominator_is_original_roster_size():
    frozen = freeze_subset("follower", ["E1", "E2"])
    assert stage_a_threshold_met(frozen, roster_tier_size=2) is True
    assert stage_a_threshold_met(frozen, roster_tier_size=160) is False


# ---- Stage B: zero-tolerance, never uses short-gap fill, rejects empty ----

def test_stage_b_rejects_observation_if_even_one_member_lacks_valid_forward_endpoint():
    frozen = freeze_subset("follower", ["E1", "E2", "E3"])
    all_valid = {"E1": VALID, "E2": VALID, "E3": VALID}
    assert stage_b_observation_valid(frozen, all_valid) is True
    one_missing = {"E1": VALID, "E2": VALID, "E3": None}
    assert stage_b_observation_valid(frozen, one_missing) is False
    one_invalid = {"E1": VALID, "E2": VALID, "E3": STRUCT_INVALID}
    assert stage_b_observation_valid(frozen, one_invalid) is False


def test_stage_b_empty_frozen_subset_is_always_rejected():
    frozen = freeze_subset("follower", [])
    assert frozen.n == 0
    assert stage_b_observation_valid(frozen, {}) is False


def test_stage_b_has_no_short_gap_fill_path_at_all():
    """Stage B's signature takes only `dict[str, Bar | None]` -- there is
    no elapsed-duration or forward-fill parameter anywhere it could use;
    a missing bar is simply `None`, always a hard failure."""
    import inspect
    params = inspect.signature(stage_b_observation_valid).parameters
    assert set(params) == {"frozen", "bars_t_plus_h"}
    frozen = freeze_subset("follower", ["E1"])
    # even a 1-second-old missing bar at t+h must fail -- there is no
    # mechanism in this function to forward-fill it.
    assert stage_b_observation_valid(frozen, {"E1": None}) is False
