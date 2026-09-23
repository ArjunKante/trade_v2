"""Regression tests for the Bug #1 follow-up: an ISIN lineage transition
with a fabricated price jump and NO calendar gap at all (unlike Bug #2's
stale-gap contamination) must still get NaN'd across the boundary, in
momentum, trailing_vol, and the forward-return target -- via the
unexplained_jump_dates parameter, not by excluding the whole entity.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factors.lowvol import _log_returns
from factors.momentum import compute_momentum
from factors.target import compute_forward_return


def _panel_with_fabricated_jump(n_before: int = 300, n_after: int = 300, jump_multiple: float = 90.0):
    """No calendar gap (freq='B', back-to-back business days) -- the
    boundary is purely a price discontinuity, the class of case Bug #2's
    calendar-gap fix cannot catch."""
    dates = pd.date_range("2020-01-01", periods=n_before + n_after, freq="B")
    before_close = list(range(100, 100 + n_before))
    after_close = [before_close[-1] * jump_multiple + i for i in range(n_after)]
    close = before_close + after_close
    return pd.DataFrame({"entity_id": ["E"] * len(dates), "trade_date": dates, "adjusted_close": close}), dates[n_before]


def test_no_calendar_gap_means_bug2_alone_does_not_catch_it():
    panel, boundary_date = _panel_with_fabricated_jump()
    p = _log_returns(panel)  # no unexplained_jump_dates passed -- old behavior
    boundary_row = p[p["trade_date"] == boundary_date].iloc[0]
    assert not pd.isna(boundary_row["_logret"])  # confirms this case needs its own guard


def test_log_return_nan_at_unexplained_jump_boundary():
    panel, boundary_date = _panel_with_fabricated_jump()
    jump_dates = {"E": {boundary_date}}
    p = _log_returns(panel, unexplained_jump_dates=jump_dates)
    boundary_row = p[p["trade_date"] == boundary_date].iloc[0]
    assert pd.isna(boundary_row["_logret"])
    # a row well before the boundary is unaffected
    clean_row = p[p["trade_date"] == panel["trade_date"].iloc[10]].iloc[0]
    assert not pd.isna(clean_row["_logret"])


def test_momentum_nan_when_unexplained_jump_falls_inside_lookback_window():
    panel, boundary_date = _panel_with_fabricated_jump()
    jump_dates = {"E": {boundary_date}}
    mom_guarded = compute_momentum(panel, window=252, skip=21, unexplained_jump_dates=jump_dates)
    mom_unguarded = compute_momentum(panel, window=252, skip=21)

    row_near_guarded = mom_guarded[mom_guarded["trade_date"] == panel["trade_date"].iloc[310]].iloc[0]
    row_near_unguarded = mom_unguarded[mom_unguarded["trade_date"] == panel["trade_date"].iloc[310]].iloc[0]
    assert pd.isna(row_near_guarded["value"])
    assert not pd.isna(row_near_unguarded["value"])  # the fabricated ~90x return, uncaught without the guard

    # far enough past the boundary that the lookback window is entirely post-jump: clean again
    row_far = mom_guarded[mom_guarded["trade_date"] == panel["trade_date"].iloc[580]].iloc[0]
    assert not pd.isna(row_far["value"])


def test_forward_return_nan_when_unexplained_jump_falls_inside_forward_window():
    panel, boundary_date = _panel_with_fabricated_jump(n_before=100, n_after=100)
    jump_dates = {"E": {boundary_date}}
    fwd = compute_forward_return(panel, horizon=63, unexplained_jump_dates=jump_dates)
    # a prediction date shortly before the boundary has the fabricated jump inside its forward 63-row window
    pre_boundary_date = panel["trade_date"].iloc[95]
    assert not (fwd["trade_date"] == pre_boundary_date).any()
    # a prediction date far enough past the boundary (but still within the
    # panel's valid forward-window range) is clean again
    post_boundary_date = panel["trade_date"].iloc[105]
    assert (fwd["trade_date"] == post_boundary_date).any()


def test_unrelated_entity_is_not_affected():
    panel, boundary_date = _panel_with_fabricated_jump()
    other = panel.copy()
    other["entity_id"] = "F"
    combined = pd.concat([panel, other], ignore_index=True)
    jump_dates = {"E": {boundary_date}}  # only entity E is flagged
    mom = compute_momentum(combined, window=252, skip=21, unexplained_jump_dates=jump_dates)
    row_f = mom[(mom["entity_id"] == "F") & (mom["trade_date"] == panel["trade_date"].iloc[310])].iloc[0]
    assert not pd.isna(row_f["value"])  # entity F's fabricated jump is NOT flagged, so still uncaught -- by design
