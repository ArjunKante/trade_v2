"""Decision 10 (Revision 5, point 8): missingness-emulation diagnostic.
SYNTHETIC DATA ONLY for the mechanics -- these tests construct
artificial eligible-id lists and missingness probabilities; none of
this module or its tests reads a real database, computes a partial
forward return, or uses a real t+h outcome value."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag import missingness as miss
from lead_lag.eligibility import freeze_subset


def make_ids(n, prefix="E"):
    return [f"{prefix}{i}" for i in range(n)]


# ---- (A) pre-signal eligibility-mask emulation ----

def test_mask_emulation_rejects_unknown_endpoint():
    with pytest.raises(ValueError):
        miss.emulate_pre_signal_eligibility_mask("follower", make_ids(160), 160, 0.1, "t_minus_99")


def test_mask_emulation_rejects_out_of_range_fraction():
    with pytest.raises(ValueError):
        miss.emulate_pre_signal_eligibility_mask("follower", make_ids(160), 160, 1.5, "t")


def test_mask_emulation_zero_fraction_reproduces_the_real_outcome_exactly():
    ids = make_ids(160)
    result = miss.emulate_pre_signal_eligibility_mask("follower", ids, 160, 0.0, "t", seed=1)
    assert result.n_masked_out == 0
    assert result.n_surviving == result.n_real_eligible == 160
    assert result.masked_breadth == pytest.approx(result.real_breadth)
    assert result.masked_threshold_met == result.real_threshold_met


def test_mask_emulation_removes_the_correct_fraction():
    ids = make_ids(200)
    result = miss.emulate_pre_signal_eligibility_mask("follower", ids, 160, 0.10, "t_minus_35", seed=3)
    assert result.n_masked_out == 20  # 10% of 200
    assert result.n_surviving == 180
    assert result.mask_endpoint == "t_minus_35"


def test_mask_emulation_can_flip_threshold_from_met_to_not_met():
    """112/160 = 0.70 exactly meets the floor; masking out 2 of them
    drops to 110/160 = 0.6875, below 0.70."""
    ids = make_ids(112)
    result = miss.emulate_pre_signal_eligibility_mask(
        "follower", ids, 160, mask_fraction=2 / 112, mask_endpoint="t_minus_5", seed=5
    )
    assert result.real_threshold_met is True
    assert result.n_masked_out == 2
    assert result.masked_threshold_met is False


def test_mask_emulation_never_exceeds_available_ids():
    ids = make_ids(5)
    result = miss.emulate_pre_signal_eligibility_mask("follower", ids, 160, 1.0, "t", seed=7)
    assert result.n_masked_out == 5
    assert result.n_surviving == 0


def test_mask_emulation_is_deterministic_given_seed():
    ids = make_ids(160)
    r1 = miss.emulate_pre_signal_eligibility_mask("follower", ids, 160, 0.3, "t", seed=42)
    r2 = miss.emulate_pre_signal_eligibility_mask("follower", ids, 160, 0.3, "t", seed=42)
    assert r1.surviving_members == r2.surviving_members


def test_mask_emulation_never_uses_a_tplush_or_outcome_parameter():
    import inspect
    params = inspect.signature(miss.emulate_pre_signal_eligibility_mask).parameters
    for forbidden in ("y", "Y", "t_plus_h", "outcome", "price_tplush"):
        assert forbidden not in params


# ---- (B) forward-endpoint diagnostic ----

def test_discard_frequency_zero_when_nothing_is_missing():
    frozen = freeze_subset("follower", make_ids(50))
    result = miss.forward_endpoint_discard_frequency(frozen, {}, n_draws=200, seed=1)
    assert result.n_discarded == 0
    assert result.discard_rate == 0.0


def test_discard_frequency_is_near_one_when_every_member_has_high_missing_prob():
    ids = make_ids(50)
    frozen = freeze_subset("follower", ids)
    probs = {e: 0.9 for e in ids}
    result = miss.forward_endpoint_discard_frequency(frozen, probs, n_draws=500, seed=2)
    assert result.discard_rate > 0.95  # near-certain at least one of 50 members misses


def test_discard_frequency_matches_expected_rate_for_a_single_member_subset():
    ids = make_ids(1)
    frozen = freeze_subset("follower", ids)
    result = miss.forward_endpoint_discard_frequency(frozen, {ids[0]: 0.3}, n_draws=5000, seed=3)
    assert result.discard_rate == pytest.approx(0.3, abs=0.03)


def test_discard_frequency_rejects_empty_frozen_subset():
    frozen = freeze_subset("follower", [])
    with pytest.raises(ValueError):
        miss.forward_endpoint_discard_frequency(frozen, {}, n_draws=10, seed=1)


def test_discard_frequency_rejects_invalid_probabilities():
    frozen = freeze_subset("follower", make_ids(5))
    with pytest.raises(ValueError):
        miss.forward_endpoint_discard_frequency(frozen, {"E0": 1.5}, n_draws=10, seed=1)


def test_discard_frequency_is_deterministic_given_seed():
    ids = make_ids(20)
    frozen = freeze_subset("follower", ids)
    probs = {e: 0.1 for e in ids}
    r1 = miss.forward_endpoint_discard_frequency(frozen, probs, n_draws=300, seed=9)
    r2 = miss.forward_endpoint_discard_frequency(frozen, probs, n_draws=300, seed=9)
    assert r1.n_discarded == r2.n_discarded


def test_discard_frequency_never_computes_a_return_or_reads_a_price():
    """Structural guarantee: no return-related name appears anywhere in
    this function's source."""
    import inspect
    src = inspect.getsource(miss.forward_endpoint_discard_frequency)
    for forbidden in ("portfolio_return", "endpoint_return", "DatedPrice", "compute_Y", ".close", ".price"):
        assert forbidden not in src
