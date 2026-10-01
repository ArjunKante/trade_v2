"""Regression tests for src/fibo/validation.py's daily-vs-bhavcopy
cross-check, on synthetic data -- proving the mismatch detector actually
detects a mismatch BEFORE it is ever pointed at a real Angel One download
(Step 1/3 of this module's build has not run yet)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.validation import compare_daily_to_bhavcopy, mismatch_rate


def _minute_bars(entity_id, trade_date, o, h, l, c, v=1000):
    ts = pd.date_range(f"{trade_date} 09:15", periods=1, freq="1min")
    return pd.DataFrame({
        "entity_id": [entity_id], "trade_date": [trade_date], "ts": ts,
        "open": [o], "high": [h], "low": [l], "close": [c], "volume": [v],
    })


def test_matching_data_produces_no_mismatch():
    bars = pd.concat([
        _minute_bars("E1", "2024-01-02", 100.0, 105.0, 99.0, 103.0),
        _minute_bars("E2", "2024-01-02", 50.0, 52.0, 49.0, 51.0),
    ], ignore_index=True)
    bhavcopy = pd.DataFrame({
        "entity_id": ["E1", "E2"], "trade_date": ["2024-01-02", "2024-01-02"],
        "open": [100.0, 50.0], "high": [105.0, 52.0], "low": [99.0, 49.0], "close": [103.0, 51.0],
    })
    result = compare_daily_to_bhavcopy(bars, bhavcopy, tolerance_pct=0.1)
    assert not result["mismatch"].any()
    assert mismatch_rate(result) == 0.0


def test_large_close_discrepancy_is_flagged_as_a_mismatch():
    bars = _minute_bars("E1", "2024-01-02", 100.0, 105.0, 99.0, 103.0)
    bhavcopy = pd.DataFrame({
        "entity_id": ["E1"], "trade_date": ["2024-01-02"],
        "open": [100.0], "high": [105.0], "low": [99.0], "close": [90.0],  # 103 vs 90: way beyond tolerance
    })
    result = compare_daily_to_bhavcopy(bars, bhavcopy, tolerance_pct=0.1)
    assert result["mismatch"].iloc[0]
    assert result["close_pct_diff"].iloc[0] == pytest.approx(abs(103.0 - 90.0) / 90.0 * 100.0)
    assert mismatch_rate(result) == 1.0


def test_within_tolerance_discrepancy_is_not_flagged():
    bars = _minute_bars("E1", "2024-01-02", 100.0, 105.0, 99.0, 100.05)  # 0.05% off close
    bhavcopy = pd.DataFrame({
        "entity_id": ["E1"], "trade_date": ["2024-01-02"],
        "open": [100.0], "high": [105.0], "low": [99.0], "close": [100.0],
    })
    result = compare_daily_to_bhavcopy(bars, bhavcopy, tolerance_pct=0.1)
    assert not result["mismatch"].iloc[0]


def test_days_missing_from_one_side_are_excluded_not_treated_as_mismatch():
    bars = pd.concat([
        _minute_bars("E1", "2024-01-02", 100.0, 105.0, 99.0, 103.0),
        _minute_bars("E1", "2024-01-03", 103.0, 106.0, 102.0, 104.0),  # no bhavcopy row for this date
    ], ignore_index=True)
    bhavcopy = pd.DataFrame({
        "entity_id": ["E1"], "trade_date": ["2024-01-02"],
        "open": [100.0], "high": [105.0], "low": [99.0], "close": [103.0],
    })
    result = compare_daily_to_bhavcopy(bars, bhavcopy, tolerance_pct=0.1)
    assert len(result) == 1  # only the day present on both sides is compared
