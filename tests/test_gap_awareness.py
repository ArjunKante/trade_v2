"""Regression tests for the gap-awareness bug: a stale multi-month trading
halt followed by resumption gets silently treated as one ordinary trading
day's return by any row-based shift(). Found live: 47 of the panel's 50 most
extreme "daily" returns had a >100-calendar-day gap to the prior row and no
corporate action anywhere nearby -- not a missing-adjustment issue, a
missing-gap-awareness issue, affecting momentum, trailing_vol, and the
forward-return target (all built on row-based shift()).
"""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factors.lowvol import compute_trailing_vol, _log_returns, STALE_GAP_DAYS as VOL_GAP
from factors.momentum import compute_momentum, _max_gap_in_window
from factors.target import compute_forward_return, _max_gap_in_forward_window


def _panel_with_gap(gap_days: int, n_before: int = 10, n_after: int = 10):
    before = pd.date_range("2020-01-01", periods=n_before, freq="B")
    after = pd.date_range(before[-1] + pd.Timedelta(days=gap_days), periods=n_after, freq="B")
    dates = list(before) + list(after)
    close = list(range(100, 100 + n_before)) + list(range(200, 200 + n_after))
    return pd.DataFrame({"entity_id": ["E"] * len(dates), "trade_date": dates, "adjusted_close": close})


def test_log_return_is_nan_across_a_stale_gap():
    panel = _panel_with_gap(gap_days=200)
    p = _log_returns(panel)
    boundary_idx = 10  # first row after the gap
    assert pd.isna(p["_logret"].iloc[boundary_idx])
    assert not pd.isna(p["_logret"].iloc[boundary_idx + 1])  # rows after the boundary are normal again


def test_log_return_not_nan_across_a_short_gap():
    panel = _panel_with_gap(gap_days=3)  # within STALE_GAP_DAYS
    p = _log_returns(panel)
    boundary_idx = 10
    assert not pd.isna(p["_logret"].iloc[boundary_idx])


def test_momentum_nan_when_gap_falls_inside_lookback_window():
    panel = _panel_with_gap(gap_days=200, n_before=300, n_after=300)
    mom = compute_momentum(panel, window=252, skip=21)
    # a date shortly after the gap should have the gap inside its 273-row lookback
    row = mom.iloc[310]
    assert pd.isna(row["value"])
    # a date far enough past the gap that the lookback window is entirely post-gap should be clean
    row_far = mom.iloc[580]
    assert not pd.isna(row_far["value"])


def test_forward_return_nan_when_gap_falls_inside_forward_window():
    panel = _panel_with_gap(gap_days=200, n_before=100, n_after=100)
    fwd = compute_forward_return(panel, horizon=63)
    # a prediction date whose forward 63-row window crosses the gap
    contaminated = fwd[(fwd["trade_date"] >= panel["trade_date"].iloc[40]) &
                        (fwd["trade_date"] <= panel["trade_date"].iloc[98])]
    # these should have been dropped entirely (NaN'd then dropna'd) rather than silently kept
    boundary_date = panel["trade_date"].iloc[95]
    assert not (fwd["trade_date"] == boundary_date).any()


def test_gap_fix_does_not_flag_a_fully_clean_series():
    panel = _panel_with_gap(gap_days=1, n_before=300, n_after=300)  # effectively continuous
    mom = compute_momentum(panel, window=252, skip=21)
    assert mom["value"].notna().sum() > 0
