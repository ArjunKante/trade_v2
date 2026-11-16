"""Regression tests for src/data_layer/exclusion_list.py -- the
persisted-exclusion-list mechanism (BUGS.md Bug #27/#28's cheap fix).
The one property that matters most: the loader never falls back to
recomputation when a file is missing."""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.exclusion_list import (
    save_exclusion_list, load_exclusion_list, entity_ids_from, all_entity_ids,
    jump_dates_from, all_jump_dates, ExclusionListMissingError,
)

THIS_FILE = Path(__file__)


def test_missing_file_raises_not_falls_back():
    with tempfile.TemporaryDirectory() as td:
        with pytest.raises(ExclusionListMissingError):
            load_exclusion_list("no_such_result", results_dir=Path(td))


def test_save_then_load_round_trips_entity_exclusion():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        save_exclusion_list(
            "my_result", produced_by="tests/test_exclusion_list.py",
            components=[{"guard": "same_isin", "mode": "entity_exclusion",
                         "entity_ids": ["E1", "E2"]}],
            detector_paths=[THIS_FILE], results_dir=d,
        )
        record = load_exclusion_list("my_result", results_dir=d)
        assert entity_ids_from(record, "same_isin") == {"E1", "E2"}
        assert entity_ids_from(record, "lineage") == set()
        assert all_entity_ids(record) == {"E1", "E2"}


def test_save_then_load_round_trips_window_mask():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        save_exclusion_list(
            "my_result", produced_by="tests/test_exclusion_list.py",
            components=[{"guard": "lineage", "mode": "window_mask",
                         "jump_dates": {"E1": ["2024-01-01", "2024-02-02"]}}],
            detector_paths=[THIS_FILE], results_dir=d,
        )
        record = load_exclusion_list("my_result", results_dir=d)
        dates = jump_dates_from(record, "lineage")
        assert set(str(x.date()) for x in dates["E1"]) == {"2024-01-01", "2024-02-02"}
        assert all_jump_dates(record) == dates


def test_combined_components_both_guards():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        save_exclusion_list(
            "combined", produced_by="tests/test_exclusion_list.py",
            components=[
                {"guard": "same_isin", "mode": "entity_exclusion", "entity_ids": ["A"]},
                {"guard": "lineage", "mode": "entity_exclusion", "entity_ids": ["B"]},
            ],
            detector_paths=[THIS_FILE], results_dir=d,
        )
        record = load_exclusion_list("combined", results_dir=d)
        assert entity_ids_from(record, "same_isin") == {"A"}
        assert entity_ids_from(record, "lineage") == {"B"}
        assert all_entity_ids(record) == {"A", "B"}


def test_filename_keyed_to_result_id_not_date():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        path = save_exclusion_list(
            "unambiguous_result_name", produced_by="x",
            components=[{"guard": "same_isin", "mode": "entity_exclusion", "entity_ids": []}],
            detector_paths=[THIS_FILE], results_dir=d,
        )
        assert path.name == "unambiguous_result_name.json"


def test_hand_edited_content_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        path = save_exclusion_list(
            "tamper_test", produced_by="x",
            components=[{"guard": "same_isin", "mode": "entity_exclusion", "entity_ids": ["A"]}],
            detector_paths=[THIS_FILE], results_dir=d,
        )
        text = path.read_text().replace('"A"', '"A_TAMPERED"')
        path.write_text(text)
        with pytest.raises(ValueError):
            load_exclusion_list("tamper_test", results_dir=d)
