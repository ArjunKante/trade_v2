"""Proves the trial-ledger enforcement mechanism actually enforces
something, rather than being documentation that happens to be valid
JSON. Specifically: an unregistered configuration cannot produce a
recorded gate result, and the denominator is always derived from the
ledger's own trial count, never a separate hand-typed number.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ledger


def test_denominator_is_six_and_computed_not_hardcoded():
    data = ledger.load_ledger()
    assert ledger.denominator(data) == len(data["trials"])
    assert ledger.denominator(data) == 6


def test_all_six_known_trials_are_registered():
    data = ledger.load_ledger()
    keys = ledger.registered_keys(data)
    expected = {
        "grouping:liquidity_tier",
        "grouping:statistical_cluster",
        "horizon:5min",
        "horizon:15min",
        "horizon:30min",
        "horizon:60min",
    }
    assert keys == expected


def test_assert_registered_succeeds_for_known_configuration():
    t = ledger.assert_registered("horizon:60min")
    assert t.status == "primary_gate"
    assert t.id == 6


def test_assert_registered_rejects_unknown_configuration():
    with pytest.raises(ledger.UnregisteredConfigurationError):
        ledger.assert_registered("horizon:90min")


def test_record_gate_run_rejects_unregistered_configuration(tmp_path):
    ledger_copy = tmp_path / "trial_ledger.json"
    ledger_copy.write_text(ledger.LEDGER_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ledger.UnregisteredConfigurationError):
        ledger.record_gate_run(
            "horizon:90min", {"note": "should never be recorded"}, path=ledger_copy
        )
    # file on disk must be unchanged -- no partial write on rejection
    after = json.loads(ledger_copy.read_text(encoding="utf-8"))
    assert after == json.loads(ledger.LEDGER_PATH.read_text(encoding="utf-8"))


def test_record_gate_run_appends_for_registered_configuration(tmp_path):
    ledger_copy = tmp_path / "trial_ledger.json"
    ledger_copy.write_text(ledger.LEDGER_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    before = json.loads(ledger_copy.read_text(encoding="utf-8"))
    before_runs = next(t for t in before["trials"] if t["config_key"] == "horizon:60min")["gate_runs"]
    assert before_runs == []

    ledger.record_gate_run(
        "horizon:60min",
        {"beta": None, "note": "test-only placeholder run, not a real DEV result"},
        path=ledger_copy,
    )

    after = json.loads(ledger_copy.read_text(encoding="utf-8"))
    after_runs = next(t for t in after["trials"] if t["config_key"] == "horizon:60min")["gate_runs"]
    assert len(after_runs) == 1
    assert "recorded_at_utc" in after_runs[0]

    # the original committed ledger file itself must never be touched by a test
    original = json.loads(ledger.LEDGER_PATH.read_text(encoding="utf-8"))
    original_runs = next(t for t in original["trials"] if t["config_key"] == "horizon:60min")["gate_runs"]
    assert original_runs == []


def test_duplicate_config_key_is_an_integrity_error():
    data = ledger.load_ledger()
    corrupted = json.loads(json.dumps(data))  # deep copy
    corrupted["trials"].append(dict(corrupted["trials"][0]))
    corrupted["trials"][-1]["id"] = 999  # distinct id, same config_key -> still a duplicate key
    with pytest.raises(ledger.LedgerIntegrityError):
        ledger._validate_integrity(corrupted)
