"""Hand-verified check for ic_eval.benjamini_hochberg before trusting it on
Phase E's real p-values -- same discipline as every other statistical
helper in this project: verify on a case small enough to compute by hand.

p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205], alpha=0.05, m=8.
BH thresholds (i/m)*alpha = [0.00625, 0.0125, 0.01875, 0.025, 0.03125,
0.0375, 0.04375, 0.05]. p_(1)=0.001<=0.00625 and p_(2)=0.008<=0.0125 both
hold; p_(3)=0.039 already exceeds 0.01875 and nothing further down qualifies
(the m=8 slot is a deliberate echo of the actual Phase E test count -- EY
and PE collapsed into one signal). So exactly the two smallest p-values are
rejected. q-values hand-computed via q_(i)=min_{j>=i}(m/j * p_(j)),
monotone from the top: q = [0.008, 0.032, 0.0672, 0.0672, 0.0672, 0.08,
0.0846, 0.205] for ranks 1..8 in sorted order.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factors.ic_eval import benjamini_hochberg

PVALUES = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205]
EXPECTED_Q_SORTED = [0.008, 0.032, 0.0672, 0.0672, 0.0672, 0.08, 0.0846, 0.205]


def test_bh_rejects_exactly_the_two_smallest_pvalues():
    out = benjamini_hochberg(PVALUES, alpha=0.05)
    reject_by_rank = out.sort_values("rank")["reject"].tolist()
    assert reject_by_rank == [True, True, False, False, False, False, False, False]


def test_bh_qvalues_match_hand_computation():
    out = benjamini_hochberg(PVALUES, alpha=0.05)
    q_sorted = out.sort_values("rank")["q_value"].tolist()
    for got, expected in zip(q_sorted, EXPECTED_Q_SORTED):
        assert got == pytest.approx(expected, abs=1e-4)


def test_bh_preserves_original_order_and_pvalues():
    out = benjamini_hochberg(PVALUES, alpha=0.05)
    assert out["pvalue"].tolist() == pytest.approx(PVALUES)


def test_bh_all_reject_when_every_pvalue_tiny():
    out = benjamini_hochberg([1e-6] * 5, alpha=0.05)
    assert out["reject"].all()


def test_bh_none_reject_when_every_pvalue_large():
    out = benjamini_hochberg([0.9, 0.8, 0.7, 0.6, 0.5], alpha=0.05)
    assert not out["reject"].any()
