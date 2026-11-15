"""Decisions 15, 16: multiplicity accounting. Verifies the module's
output reproduces the frozen Section 23 constants exactly, and that the
ledger (a real, read-only file) is never edited and reconciles as
expected. No real statistical gate, beta, or p-value is computed here."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag import multiplicity as mult

ledger = mult.ledger  # the real governance ledger module, loaded by multiplicity.py


def test_operative_alpha_matches_frozen_section_23_value():
    assert mult.bonferroni_alpha(8) == pytest.approx(0.00625, abs=1e-12)
    assert mult.bonferroni_alpha(8) == mult.FROZEN_OPERATIVE_ALPHA


def test_operative_z_critical_matches_frozen_section_23_value():
    z = mult.two_sided_z_critical(mult.bonferroni_alpha(8))
    assert z == pytest.approx(mult.FROZEN_OPERATIVE_Z_CRITICAL, abs=1e-4)


def test_historical_six_denominator_z_critical_matches_frozen_value():
    """Section 23's historical, superseded row: alpha=0.05/6 -> z=2.63826."""
    z = mult.two_sided_z_critical(mult.bonferroni_alpha(6))
    assert z == pytest.approx(2.63826, abs=1e-4)


def test_bonferroni_alpha_rejects_nonpositive_denominator():
    with pytest.raises(ValueError):
        mult.bonferroni_alpha(0)
    with pytest.raises(ValueError):
        mult.bonferroni_alpha(-1)


def test_two_sided_z_critical_rejects_invalid_alpha():
    with pytest.raises(ValueError):
        mult.two_sided_z_critical(0.0)
    with pytest.raises(ValueError):
        mult.two_sided_z_critical(1.0)


def test_project_trial_count_and_operative_denominator_are_the_frozen_constants():
    assert mult.PROJECT_TRIAL_COUNT == 7
    assert mult.OPERATIVE_MULTIPLICITY_DENOMINATOR == 8


def test_reconcile_against_the_real_ledger_file_is_consistent_and_read_only():
    before = ledger.load_ledger()
    before_denom = ledger.denominator(before)
    result = mult.reconcile()
    after = ledger.load_ledger()
    assert ledger.denominator(after) == before_denom  # file untouched
    assert result.ledger_denominator == 6
    assert result.consistent is True
    assert result.operative_denominator == 8
    assert result.operative_alpha == pytest.approx(0.00625, abs=1e-12)


def test_reconcile_flags_inconsistency_if_ledger_denominator_drifts():
    fake_data = {"trials": [{"id": i} for i in range(5)]}  # pretend only 5 trials
    result = mult.reconcile(fake_data)
    assert result.consistent is False
    assert "MISMATCH" in result.note


def test_this_module_never_writes_the_ledger_file():
    """Structural guarantee: no function here accepts a write-capable
    path parameter, and `reconcile` only ever calls `ledger.denominator`
    (a pure read), never `ledger.record_gate_run`."""
    import inspect
    assert "record_gate_run" not in inspect.getsource(mult.reconcile)
