"""Bar-validity rules (Decision 17): PRESENT-VALID, FUNCTIONALLY ABSENT,
structural invalidity, and the exact-duration gap-classification rule.

Categories (as named in `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 10
LOG and `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md`):

    A1: zero-volume, OHLC-flat, all four values finite and strictly
        positive -- PRESENT-VALID.
    B1: zero-volume, OHLC-non-flat -- FUNCTIONALLY ABSENT; own values
        never used; own timestamp never imputed.
    C:  genuine missing-timestamp gap -- exact elapsed duration;
        `<180`s forward-fillable (Stage A only), `>=180`s excluded.
    D:  positive-volume, structurally valid (including numerically
        extreme values, no invented cutoff) -- PRESENT-VALID.
    E:  structurally invalid -- FUNCTIONALLY ABSENT; own values never
        used; own timestamp never repaired/forward-filled, regardless of
        gap length. Takes precedence over A1: a structurally invalid bar
        is never PRESENT-VALID even if its OHLC values are equal.

No new rule is invented here; this module implements exactly the policy
recorded in AMENDMENT 10 LOG, Sections 1-4, and its precision correction.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

GAP_THRESHOLD_SECONDS = 180.0  # Decision 17, sub-decision C. 180s itself excluded.


def _finite_positive(x: float | None) -> bool:
    return x is not None and math.isfinite(x) and x > 0


def is_structurally_invalid(open_: float | None, high: float | None,
                             low: float | None, close: float | None,
                             volume: float | None) -> bool:
    """Category E, exact rule (AMENDMENT 10 LOG, Section 3). True if the
    bar must be excluded outright, regardless of volume.

    **Correction, this revision**: the approved rule's fifth criterion is
    literally "`volume < 0`", which a null or non-finite `volume` does
    not satisfy under plain Python comparison (`None < 0` short-circuits
    to False via the `is not None` guard; `float('nan') < 0` is `False`;
    `float('inf') > 0` is `True`, which would previously have let an
    infinite-volume bar through as category D). A null or non-finite
    `volume` is not a valid representation of "zero or more shares
    traded" under any reading of the schema -- this is classified as
    structurally invalid too, as the narrowest, most conservative
    extension of the existing "volume < 0" criterion to cover a
    representation the original five-criterion list did not anticipate.
    This is a restriction, not a new permissive interpretation: it can
    only ever move a bar from "present-valid" to "excluded," never the
    reverse."""
    vals = (open_, high, low, close)
    if any(v is None or not math.isfinite(v) or v <= 0 for v in vals):
        return True
    if volume is None or not math.isfinite(volume):
        return True
    if high < low:
        return True
    if not (low <= open_ <= high):
        return True
    if not (low <= close <= high):
        return True
    if volume < 0:
        return True
    return False


def is_present_valid(open_: float | None, high: float | None, low: float | None,
                      close: float | None, volume: float | None) -> bool:
    """PRESENT-VALID (AMENDMENT 10 LOG, Section 4, precision-corrected).
    Category E takes precedence: never PRESENT-VALID if structurally
    invalid, even if flat."""
    if is_structurally_invalid(open_, high, low, close, volume):
        return False
    if volume is not None and volume > 0:
        # category D: positive-volume, structurally valid (already
        # confirmed above) -- accepted, including extreme values, no cutoff.
        return True
    # category A1: zero-volume, OHLC-flat, all four finite and positive.
    if volume == 0 and open_ == high == low == close and _finite_positive(open_):
        return True
    return False


def is_functionally_absent(open_: float | None, high: float | None, low: float | None,
                            close: float | None, volume: float | None,
                            present: bool = True) -> bool:
    """FUNCTIONALLY ABSENT, for gap-length classification only
    (AMENDMENT 10 LOG, Section 4). `present=False` means a true absent
    expected timestamp (no row at all) -- always functionally absent.
    `present=True` means a row exists; functionally absent iff it is
    category B1 (zero-volume, non-flat) or category E (structurally
    invalid)."""
    if not present:
        return True
    if is_structurally_invalid(open_, high, low, close, volume):
        return True  # category E
    if volume == 0 and not (open_ == high == low == close):
        return True  # category B1
    return False


def bar_category(open_: float | None, high: float | None, low: float | None,
                  close: float | None, volume: float | None, present: bool = True) -> str:
    """Returns one of "A1", "B1", "D", "E", or "absent" -- the exact
    category a present row (or true absence) falls into."""
    if not present:
        return "absent"
    if is_structurally_invalid(open_, high, low, close, volume):
        return "E"
    if volume is not None and volume > 0:
        return "D"
    if volume == 0 and open_ == high == low == close:
        return "A1"
    return "B1"


def imputable_at_own_timestamp(open_: float | None, high: float | None, low: float | None,
                                close: float | None, volume: float | None,
                                present: bool) -> bool:
    """Only a true absent expected timestamp is ever eligible to receive
    an imputed value. A category-B1 or category-E bar's own timestamp is
    never imputable, regardless of surrounding gap length."""
    return not present


@dataclass(frozen=True)
class GapClassification:
    elapsed_seconds: float
    forward_fillable: bool  # Stage A only; never applies to Stage B


def classify_gap(prev_present_ts_epoch: float, next_present_ts_epoch: float) -> GapClassification:
    """Decision 17, sub-decision C: exact elapsed duration between the
    two bounding present-valid rows. `<180`s forward-fillable (Stage A
    pre-signal endpoints only); `>=180`s excluded -- 180 itself is on
    the excluded side."""
    elapsed = next_present_ts_epoch - prev_present_ts_epoch
    return GapClassification(elapsed_seconds=elapsed, forward_fillable=elapsed < GAP_THRESHOLD_SECONDS)
