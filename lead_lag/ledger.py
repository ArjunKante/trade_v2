"""Machine-readable trial-ledger enforcement for the lead-lag family.

Governance tooling only -- no strategy/signal/measurement logic lives
here. Built in response to an independent methodology review finding
that this project's existing trial-count discipline (PROJECT_CONTEXT.md
Section 3) is purely a prose convention, and that the POC family's own
Bonferroni denominator stayed pinned at 2 across three preregistrations
while its real trial count reached 5 (PROJECT_CONTEXT.md Section 3,
finding #15) -- a demonstrated, in-project failure of "update the
markdown by hand." This module makes the lead-lag family's denominator
a single computed fact (len(trials) in trial_ledger.json), and makes
"was this configuration pre-registered before it reached a gate" a
function call Phase 4 code is required to make, not a thing a reviewer
has to manually cross-check against prose.

Any future Phase 4 implementation MUST call `assert_registered(...)`
before running a statistical gate for a given configuration, and MUST
call `record_gate_run(...)` immediately after, so the ledger file
itself -- not a markdown document -- is the append-only record of what
actually ran. Adding a brand-new configuration requires hand-editing
trial_ledger.json and committing that edit; there is no runtime API to
silently grow the trial list.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_PATH = Path(__file__).resolve().parent / "trial_ledger.json"


class UnregisteredConfigurationError(RuntimeError):
    """Raised when code attempts to reach a statistical gate for a
    configuration that does not already have an entry in
    trial_ledger.json. The fix is never to catch and ignore this -- it
    is to stop, add the configuration to the ledger by hand, commit
    that change, and only then proceed."""


class LedgerIntegrityError(RuntimeError):
    """Raised when trial_ledger.json itself is malformed (duplicate
    config_key, missing required field) -- a defect in the ledger, not
    in the caller."""


@dataclass(frozen=True)
class Trial:
    id: int
    config_key: str
    configuration: str
    stage_registered: str
    date_registered: str
    status: str
    source_doc: str


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _validate_integrity(data)
    return data


def _validate_integrity(data: dict[str, Any]) -> None:
    trials = data.get("trials", [])
    seen_ids: set[int] = set()
    seen_keys: set[str] = set()
    required_fields = {
        "id", "config_key", "configuration", "stage_registered",
        "date_registered", "status", "source_doc", "gate_runs",
    }
    for t in trials:
        missing = required_fields - set(t.keys())
        if missing:
            raise LedgerIntegrityError(
                f"trial {t.get('config_key', '<unknown>')} missing fields: {missing}"
            )
        if t["id"] in seen_ids:
            raise LedgerIntegrityError(f"duplicate trial id: {t['id']}")
        if t["config_key"] in seen_keys:
            raise LedgerIntegrityError(f"duplicate config_key: {t['config_key']}")
        seen_ids.add(t["id"])
        seen_keys.add(t["config_key"])


def denominator(data: dict[str, Any] | None = None) -> int:
    """The family's multiple-testing correction denominator.

    Always len(trials) -- never a hand-typed number. Any document
    citing a trial count for this family must call this function (or
    report the number it returns, with a note that it is computed from
    trial_ledger.json) rather than restate a number independently.
    """
    data = data if data is not None else load_ledger()
    return len(data["trials"])


def registered_keys(data: dict[str, Any] | None = None) -> set[str]:
    data = data if data is not None else load_ledger()
    return {t["config_key"] for t in data["trials"]}


def assert_registered(config_key: str, data: dict[str, Any] | None = None) -> Trial:
    """Raise UnregisteredConfigurationError unless config_key already
    has a trial_ledger.json entry. Returns the matching Trial on
    success. Call this before running ANY statistical gate (a
    regression fit that will be interpreted against Section 20's
    verdict rules, a null draw, a horizon's actual DEV result) for a
    given configuration.
    """
    data = data if data is not None else load_ledger()
    for t in data["trials"]:
        if t["config_key"] == config_key:
            return Trial(
                id=t["id"], config_key=t["config_key"],
                configuration=t["configuration"],
                stage_registered=t["stage_registered"],
                date_registered=t["date_registered"],
                status=t["status"], source_doc=t["source_doc"],
            )
    raise UnregisteredConfigurationError(
        f"config_key={config_key!r} is not in {LEDGER_PATH.name}. "
        f"Registered keys: {sorted(registered_keys(data))}. "
        f"Add this configuration to the ledger and commit that change "
        f"before running any gate against it -- do not proceed."
    )


def record_gate_run(
    config_key: str,
    run_metadata: dict[str, Any],
    path: Path = LEDGER_PATH,
) -> None:
    """Append an automatic, timestamped record that `config_key`
    actually reached a statistical gate. Raises UnregisteredConfigurationError
    if the configuration was never registered -- this is the
    enforcement point: you cannot record a gate run for a configuration
    that isn't already in the ledger, which means an unregistered
    configuration cannot produce a recorded result at all.

    This is the "every configuration reaching a gate must be recorded
    automatically" requirement: callers are not expected to remember to
    update a markdown findings doc -- this function is the record.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _validate_integrity(data)

    match = None
    for t in data["trials"]:
        if t["config_key"] == config_key:
            match = t
            break
    if match is None:
        raise UnregisteredConfigurationError(
            f"config_key={config_key!r} is not in {path.name} -- cannot "
            f"record a gate run for an unregistered configuration."
        )

    entry = dict(run_metadata)
    entry["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    match.setdefault("gate_runs", []).append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def reconciliation_report(data: dict[str, Any] | None = None) -> str:
    """Human-readable summary: denominator, which trials have actually
    been run vs. only registered, for stage-reconciliation checks
    (OPERATIONS.md standing rule, line ~1481)."""
    data = data if data is not None else load_ledger()
    lines = [
        f"Family: {data['family']}",
        f"Denominator (len(trials), computed): {denominator(data)}",
        f"Frozen as of commit: {data.get('frozen_as_of_commit', '<unset>')}",
        "",
    ]
    for t in data["trials"]:
        n_runs = len(t.get("gate_runs", []))
        lines.append(
            f"  [{t['id']}] {t['config_key']:<28} status={t['status']:<22} "
            f"gate_runs={n_runs}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(reconciliation_report())
