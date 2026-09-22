"""Corporate-actions parsing and ISIN resolution, validated against
BAJFINANCE's two real events -- exactly the fixtures specified for this
build, both already located in this project's own backfilled data.
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.corporate_actions import parse_subject_ratios, resolve_isin_for_actions


def test_combined_subject_extracts_both_components_2016_event():
    """BAJFINANCE 2016-09-08: one string containing both a bonus and a split.
    A parser that returns on first match silently drops the second -- this
    is the exact bug the prior project hit and fixed."""
    subject = " Bonus 1:1/Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"
    components = parse_subject_ratios(subject)
    types = {c[0] for c in components}
    assert types == {"bonus", "split"}
    ratios = {c[0]: c[1] for c in components}
    assert ratios["bonus"] == pytest.approx(2.0)
    assert ratios["split"] == pytest.approx(5.0)
    combined = ratios["bonus"] * ratios["split"]
    assert combined == pytest.approx(10.0)


def test_separate_rows_2025_event_combine_to_same_ratio():
    """BAJFINANCE 2025-06-16: same combined 10x ratio, but split across two
    separate feed records instead of one string -- both shapes must produce
    the same total adjustment."""
    bonus_subject = "Bonus 4:1"
    split_subject = "Face Value Split (Sub-Division) - From Rs 2/- Per Share To Re 1/- Per Share"
    bonus = parse_subject_ratios(bonus_subject)
    split = parse_subject_ratios(split_subject)
    assert bonus == [("bonus", pytest.approx(5.0))]
    assert split == [("split", pytest.approx(2.0))]
    assert bonus[0][1] * split[0][1] == pytest.approx(10.0)


def test_re_and_rs_currency_prefix_both_parse():
    """'Re 1/-' (singular rupee) must parse the same as 'Rs 1/-'."""
    assert parse_subject_ratios("From Rs 5/- Per Share To Re 1/- Per Share") == [("split", pytest.approx(5.0))]


def test_non_split_bonus_subjects_produce_no_components():
    for subject in ["Dividend - Rs 20 Per Share", "Buyback Of Shares", "Annual General Meeting/Dividend - Rs 3.60/- Per Share"]:
        assert parse_subject_ratios(subject) == []


def test_isin_resolution_uses_own_observations_not_feed_isin():
    """The feed's isin field is BAJFINANCE's original 2016 ISIN even for the
    2025 event -- trusting it would misfile a 2025 action against a
    nine-year-retired ISIN. Resolution must use our own (symbol, ex_date)
    price observations instead."""
    actions = pd.DataFrame([
        {"symbol": "BAJFINANCE", "ex_date": pd.Timestamp("2025-06-16"), "action_type": "bonus",
         "ratio": 5.0, "subject_raw": "Bonus 4:1", "feed_isin": "INE296A01016"},  # feed lies: says 2016 ISIN
    ])
    symbol_obs = pd.DataFrame([
        {"symbol": "BAJFINANCE", "trade_date": pd.Timestamp("2025-06-13"), "isin": "INE296A01024"},
        {"symbol": "BAJFINANCE", "trade_date": pd.Timestamp("2025-06-16"), "isin": "INE296A01032"},
        {"symbol": "BAJFINANCE", "trade_date": pd.Timestamp("2025-06-17"), "isin": "INE296A01032"},
    ])
    resolved = resolve_isin_for_actions(actions, symbol_obs)
    assert resolved.iloc[0]["resolved_isin"] == "INE296A01032"  # NOT the feed's INE296A01016
