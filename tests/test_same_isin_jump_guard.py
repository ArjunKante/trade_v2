"""Regression test for the same-isin jump detector (BUGS.md's new bug,
found via the swing project's Phase 3 backtest -- MAJESCO's uncorrected
December 2020 demerger). Mirrors test_lineage_jump_guard.py's style:
a small in-memory duckdb with a fabricated collapse and no corresponding
corporate_actions row."""
import datetime as dt
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.same_isin_jump_guard import find_unexplained_same_isin_jumps, unexplained_same_isin_jump_entities


@pytest.fixture
def con(tmp_path):
    c = get_connection(tmp_path / "test.duckdb")
    c.execute("INSERT INTO isin_lineage VALUES ('INE_CLEAN', 'E_CLEAN', NULL, 'chain_start', '2020-01-01', NOW(), 'test', 1)")
    c.execute("INSERT INTO isin_lineage VALUES ('INE_BAD', 'E_BAD', NULL, 'chain_start', '2020-01-01', NOW(), 'test', 1)")

    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    for i, d in enumerate(dates):
        close = 100.0
        c.execute(
            "INSERT INTO prices_eod VALUES ('INE_CLEAN', ?, 'CLEAN', 'EQ', ?, ?, ?, ?, ?, ?, 1000, 100000, 10, ?, NOW(), 'test', 1)",
            [d.date(), close, close, close, close, close, close, d.date()],
        )
        c.execute(
            "INSERT INTO adjustment_factors VALUES ('E_CLEAN', ?, 1.0, ?, NOW(), 'test', 1)",
            [d.date(), d.date()],
        )
        # BAD entity: flat at 100 until a collapse to 5 on day index 5, no corporate action
        close_bad = 100.0 if i < 5 else 5.0
        c.execute(
            "INSERT INTO prices_eod VALUES ('INE_BAD', ?, 'BAD', 'EQ', ?, ?, ?, ?, ?, ?, 1000, 100000, 10, ?, NOW(), 'test', 1)",
            [d.date(), close_bad, close_bad, close_bad, close_bad, close_bad, close_bad, d.date()],
        )
        c.execute(
            "INSERT INTO adjustment_factors VALUES ('E_BAD', ?, 1.0, ?, NOW(), 'test', 1)",
            [d.date(), d.date()],
        )
    yield c
    c.close()


def test_no_jump_flagged_for_clean_entity(con):
    jumps = find_unexplained_same_isin_jumps(con)
    assert "INE_CLEAN" not in jumps["isin"].values


def test_unexplained_collapse_is_flagged(con):
    jumps = find_unexplained_same_isin_jumps(con)
    bad = jumps[jumps["isin"] == "INE_BAD"]
    assert len(bad) == 1
    assert bad["ratio"].iloc[0] == pytest.approx(0.05)
    assert bad["has_nearby_ca_record"].iloc[0] == False
    assert bad["gap_days"].iloc[0] <= 5  # consecutive business days, no calendar gap


def test_entity_resolution_for_exclusion(con):
    entities = unexplained_same_isin_jump_entities(con)
    assert "E_BAD" in entities["entity_id"].values
    assert "E_CLEAN" not in entities["entity_id"].values


def test_corporate_action_nearby_suppresses_the_flag(con):
    con.execute(
        "INSERT INTO corporate_actions VALUES ('INE_BAD', 'BAD', ?, 'split', 20.0, 'test note', NULL, ?, NOW(), 'test', 1)",
        [dt.date(2020, 1, 8), dt.date(2020, 1, 8)],
    )
    jumps = find_unexplained_same_isin_jumps(con)
    bad = jumps[jumps["isin"] == "INE_BAD"]
    assert len(bad) == 1
    assert bad["has_nearby_ca_record"].iloc[0] == True
    entities = unexplained_same_isin_jump_entities(con)
    assert "E_BAD" not in entities["entity_id"].values
