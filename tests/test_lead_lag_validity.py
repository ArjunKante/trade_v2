"""Decision 17: PRESENT-VALID, structural invalidity, A1/E precedence,
and the exact-duration gap threshold."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag.validity import (
    is_present_valid,
    is_structurally_invalid,
    is_functionally_absent,
    bar_category,
    imputable_at_own_timestamp,
    classify_gap,
    GAP_THRESHOLD_SECONDS,
)


def test_category_d_positive_volume_structurally_valid_accepted():
    assert is_present_valid(open_=100, high=101, low=99, close=100.5, volume=500) is True
    assert bar_category(100, 101, 99, 100.5, 500) == "D"


def test_category_d_numerically_extreme_volume_still_accepted_no_cutoff():
    assert is_present_valid(open_=100, high=101, low=99, close=100.5, volume=10_000_000) is True


def test_category_a1_zero_volume_flat_positive_finite_accepted():
    assert is_present_valid(open_=50, high=50, low=50, close=50, volume=0) is True
    assert bar_category(50, 50, 50, 50, 0) == "A1"


def test_category_a1_requires_strictly_positive_not_zero_or_negative():
    # open=high=low=close=0, volume=0 -- flat but NOT finite-and-positive;
    # also satisfies category E's own "<=0" criterion, which takes precedence.
    assert is_present_valid(open_=0, high=0, low=0, close=0, volume=0) is False
    assert is_structurally_invalid(0, 0, 0, 0, 0) is True
    assert bar_category(0, 0, 0, 0, 0) == "E"


def test_category_e_precedence_over_a1_even_when_flat():
    """A structurally invalid bar is never PRESENT-VALID, even if its
    OHLC values happen to be equal to each other (AMENDMENT 10 LOG,
    Section 4, precision correction)."""
    assert is_present_valid(open_=-5, high=-5, low=-5, close=-5, volume=0) is False
    assert bar_category(-5, -5, -5, -5, 0) == "E"


def test_category_b1_zero_volume_non_flat_functionally_absent_never_present_valid():
    assert is_present_valid(open_=100, high=101, low=99, close=100.5, volume=0) is False
    assert bar_category(100, 101, 99, 100.5, 0) == "B1"
    assert is_functionally_absent(100, 101, 99, 100.5, 0, present=True) is True


def test_category_e_structural_invalidity_each_criterion():
    assert is_structurally_invalid(high=9, low=10, open_=9.5, close=9.5, volume=100) is True  # high<low
    assert is_structurally_invalid(open_=20, high=15, low=10, close=12, volume=100) is True  # open outside [low,high]
    assert is_structurally_invalid(open_=12, high=15, low=10, close=20, volume=100) is True  # close outside [low,high]
    assert is_structurally_invalid(open_=None, high=15, low=10, close=12, volume=100) is True  # null
    assert is_structurally_invalid(open_=float("nan"), high=15, low=10, close=12, volume=100) is True  # non-finite
    assert is_structurally_invalid(open_=12, high=15, low=10, close=12, volume=-5) is True  # negative volume


def test_category_e_extreme_positive_volume_alone_is_not_structural_invalidity():
    assert is_structurally_invalid(open_=100, high=101, low=99, close=100.5, volume=99_999_999) is False


def test_b1_and_e_never_imputable_at_own_timestamp():
    assert imputable_at_own_timestamp(100, 101, 99, 100.5, 0, present=True) is False  # B1
    assert imputable_at_own_timestamp(-5, -5, -5, -5, 0, present=True) is False  # E
    assert imputable_at_own_timestamp(None, None, None, None, None, present=False) is True  # true absence


def test_null_volume_is_structurally_invalid_never_present_valid():
    assert is_structurally_invalid(100, 101, 99, 100.5, None) is True
    assert is_present_valid(100, 101, 99, 100.5, None) is False
    assert bar_category(100, 101, 99, 100.5, None) == "E"


def test_nan_volume_is_structurally_invalid_never_present_valid():
    nan = float("nan")
    assert is_structurally_invalid(100, 101, 99, 100.5, nan) is True
    assert is_present_valid(100, 101, 99, 100.5, nan) is False
    assert bar_category(100, 101, 99, 100.5, nan) == "E"


def test_positive_infinite_volume_is_structurally_invalid_not_accepted_as_category_d():
    """Regression test for the specific bug found in review: `inf > 0`
    is True in Python, so the prior implementation accepted an infinite
    volume as a normal category-D positive-volume bar."""
    inf = float("inf")
    assert is_structurally_invalid(100, 101, 99, 100.5, inf) is True
    assert is_present_valid(100, 101, 99, 100.5, inf) is False
    assert bar_category(100, 101, 99, 100.5, inf) == "E"


def test_negative_infinite_volume_is_structurally_invalid():
    neg_inf = float("-inf")
    assert is_structurally_invalid(100, 101, 99, 100.5, neg_inf) is True
    assert is_present_valid(100, 101, 99, 100.5, neg_inf) is False


def test_null_and_nonfinite_volume_never_misclassified_as_b1():
    """A null/NaN/inf volume is not literally `== 0`, so it is not
    genuine category B1 (zero-volume, non-flat) either -- it must be
    labeled E, not silently folded into B1's label."""
    for bad_volume in (None, float("nan"), float("inf"), float("-inf")):
        assert bar_category(100, 101, 99, 100.5, bad_volume) == "E"


def test_gap_threshold_exact_180_seconds_is_excluded_not_forward_filled():
    g_179 = classify_gap(0.0, 179.0)
    g_180 = classify_gap(0.0, 180.0)
    g_181 = classify_gap(0.0, 181.0)
    assert g_179.forward_fillable is True
    assert g_180.forward_fillable is False  # 180 itself is on the excluded side
    assert g_181.forward_fillable is False
    assert GAP_THRESHOLD_SECONDS == 180.0
