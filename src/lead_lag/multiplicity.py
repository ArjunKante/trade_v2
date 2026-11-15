"""Decisions 15, 16: multiple-testing accounting for the lead-lag family's
future primary gate.

Three distinct concepts, deliberately kept separate (`PREREGISTRATION_LEAD_LAG_V1.md`
Section 23, Decision 16 amendment; `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Revision 5, point 6):

  (A) Ledger-registered configurations: `lead_lag.ledger.denominator()`,
      always `len(trials)` in `trial_ledger.json` -- currently 6. The
      ledger file itself is never edited by this module.
  (B) Project trial count: 7 (6 ledger-registered + Option 1, an
      unregistered Phase 1 feasibility kill that was never added to the
      ledger as its own trial).
  (C) Operative multiplicity-family denominator for the future primary
      gate: 8 (the 7-trial project count + Option 2, included for
      multiplicity-control purposes despite not being a formal trial).

None of these numbers are computed from data -- they are frozen,
human-approved constants (Decision 16). This module's only job is to
expose them as a single source of truth so no future primary-gate
report hand-types a different number, and to compute the resulting
Bonferroni alpha and two-sided z-critical deterministically from
whichever denominator is operative.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from scipy.stats import norm

# `lead_lag/ledger.py` lives in the top-level `lead_lag/` governance-doc
# directory, NOT inside this `src/lead_lag/` package -- the two share a
# name but are different directories, so a normal `from . import ledger`
# or `import lead_lag.ledger` would incorrectly resolve against whichever
# `lead_lag` package is first on `sys.path`. Loaded explicitly by file
# path instead, so this module always reaches the real, single
# governance ledger regardless of import order.
_LEDGER_PATH = Path(__file__).resolve().parents[2] / "lead_lag" / "ledger.py"
_spec = importlib.util.spec_from_file_location("lead_lag_governance_ledger", _LEDGER_PATH)
ledger = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ledger  # dataclass() needs the module registered before exec
_spec.loader.exec_module(ledger)

UNADJUSTED_ALPHA = 0.05  # Section 15 -- the unadjusted, two-sided level.

PROJECT_TRIAL_COUNT = 7  # Section 15, Decision 16 amendment; Section 23.
OPERATIVE_MULTIPLICITY_DENOMINATOR = 8  # Section 23, Decision 16 amendment.

# The frozen Section 23 value this module's output must reproduce exactly,
# for the operative denominator -- used only as a regression-test anchor,
# never as an input to any computation below.
FROZEN_OPERATIVE_ALPHA = 0.05 / 8  # == 0.00625
FROZEN_OPERATIVE_Z_CRITICAL = 2.73437


def bonferroni_alpha(denominator: int = OPERATIVE_MULTIPLICITY_DENOMINATOR,
                      unadjusted_alpha: float = UNADJUSTED_ALPHA) -> float:
    """Decision 16: `unadjusted_alpha / denominator`. Never silently
    changes which denominator is "operative" -- the caller must say so
    explicitly; the default is the current operative one (8)."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return unadjusted_alpha / denominator


def two_sided_z_critical(alpha: float) -> float:
    """`z_{1-alpha/2}`, the standard two-sided critical value for a
    Bonferroni-adjusted alpha. A pre-existing statistical convention
    (Section 17), not a new invention."""
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0, 1)")
    return float(norm.ppf(1 - alpha / 2))


@dataclass(frozen=True)
class MultiplicityReconciliation:
    ledger_denominator: int
    project_trial_count: int
    operative_denominator: int
    operative_alpha: float
    operative_z_critical: float
    consistent: bool
    note: str


def reconcile(ledger_data: dict | None = None) -> MultiplicityReconciliation:
    """Cross-check the ledger's own count against the frozen, approved
    project-trial-count and operative-denominator constants. This is a
    RECONCILIATION, not an edit -- `trial_ledger.json` is deliberately
    never written by this function (Section 23: "the ledger is
    deliberately not edited"). A mismatch between the ledger's raw count
    (6) and the operative denominator (8) is EXPECTED and documented
    (Option 1 and Option 2 are accounted for outside the ledger) -- this
    function reports that as `consistent=True` with an explanatory note,
    not as an error; it only flags `consistent=False` if the ledger's
    own count unexpectedly drifts away from 6, which would mean a trial
    was added or removed without this module being updated to match."""
    ledger_denom = ledger.denominator(ledger_data)
    expected_ledger_denom = 6
    consistent = (ledger_denom == expected_ledger_denom)
    note = (
        f"ledger={ledger_denom} (registered configurations); "
        f"project_trial_count={PROJECT_TRIAL_COUNT} (adds Option 1, unregistered "
        f"Phase 1 feasibility kill); operative_denominator={OPERATIVE_MULTIPLICITY_DENOMINATOR} "
        f"(adds Option 2, basket-construction methodology choice, for multiplicity "
        f"control despite not being a formal trial). The gap between ledger and "
        f"operative denominator (6 -> 8) is expected and documented, not a defect."
    )
    if not consistent:
        note = (
            f"MISMATCH: ledger denominator is {ledger_denom}, expected {expected_ledger_denom}. "
            f"A trial was added to or removed from trial_ledger.json since this module's "
            f"constants were last reconciled with Decision 16 -- PROJECT_TRIAL_COUNT and "
            f"OPERATIVE_MULTIPLICITY_DENOMINATOR must be re-reviewed against the ledger and "
            f"the governing documents before any primary-gate alpha is used. " + note
        )
    return MultiplicityReconciliation(
        ledger_denominator=ledger_denom,
        project_trial_count=PROJECT_TRIAL_COUNT,
        operative_denominator=OPERATIVE_MULTIPLICITY_DENOMINATOR,
        operative_alpha=bonferroni_alpha(OPERATIVE_MULTIPLICITY_DENOMINATOR),
        operative_z_critical=two_sided_z_critical(bonferroni_alpha(OPERATIVE_MULTIPLICITY_DENOMINATOR)),
        consistent=consistent,
        note=note,
    )
