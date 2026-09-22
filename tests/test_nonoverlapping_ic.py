"""Synthetic checks for ic_eval.nonoverlapping_ic_report and its spacing
guard, written before trusting either on the real Phase E panel -- same
discipline as tests/test_fundamentals_factors_ttm.py, which caught Bug #3
on a two-row fixture before real data could hide it."""
import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factors.ic_eval import nonoverlapping_ic_report, rebalance_spacing_trading_days


def test_spacing_guard_raises_when_windows_overlap():
    # horizon 63, spacing only 30 trading days apart -- must refuse, not
    # silently understate the SE.
    dates = pd.date_range("2020-01-01", periods=5, freq="B")
    df = pd.DataFrame({
        "trade_date": np.repeat(dates, 5),
        "value": np.tile([1, 2, 3, 4, 5], 5),
        "fwd_return": np.tile([0.01, 0.02, 0.03, 0.04, 0.05], 5),
    })
    with pytest.raises(AssertionError):
        nonoverlapping_ic_report(df, min_spacing_trading_days=30, horizon_days=63)


def test_nonoverlapping_ic_matches_hand_computed_se():
    # 4 independent rebalance dates, perfect rank correlation (ic=1.0) on
    # two of them and perfect anti-correlation (ic=-1.0) on the other two --
    # mean 0; sample std (ddof=1) of [1,-1,1,-1] is sqrt(4/3)=1.1547, so
    # se = 1.1547/sqrt(4) = 0.5774.
    rng = pd.date_range("2020-01-01", periods=4, freq="B")
    rows = []
    for i, d in enumerate(rng):
        vals = [1, 2, 3, 4, 5]
        fwd = [0.01, 0.02, 0.03, 0.04, 0.05] if i % 2 == 0 else [0.05, 0.04, 0.03, 0.02, 0.01]
        for v, f in zip(vals, fwd):
            rows.append({"trade_date": d, "value": v, "fwd_return": f})
    df = pd.DataFrame(rows)
    rep = nonoverlapping_ic_report(df, min_spacing_trading_days=63, horizon_days=63)
    assert rep["n_dates"] == 4
    assert rep["mean_ic"] == pytest.approx(0.0, abs=1e-9)
    assert rep["std_ic"] == pytest.approx(np.sqrt(4 / 3), abs=1e-9)
    assert rep["se_ic"] == pytest.approx(np.sqrt(4 / 3) / 2, abs=1e-9)
    assert rep["t_stat"] == pytest.approx(0.0, abs=1e-9)


def test_rebalance_spacing_measures_trading_day_rows_not_calendar_days():
    calendar = pd.date_range("2020-01-01", periods=200, freq="B")
    used = [calendar[0], calendar[63], calendar[126]]  # exactly 63 rows apart
    spacing = rebalance_spacing_trading_days(used, calendar)
    assert spacing["min"] == 63
    assert spacing["max"] == 63
    assert spacing["n_dates"] == 3


def test_rebalance_spacing_flags_a_narrower_gap_when_dates_are_dropped_unevenly():
    calendar = pd.date_range("2020-01-01", periods=200, freq="B")
    used = [calendar[0], calendar[40], calendar[103]]  # first gap only 40 rows
    spacing = rebalance_spacing_trading_days(used, calendar)
    assert spacing["min"] == 40
    assert spacing["max"] == 63
