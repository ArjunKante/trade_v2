"""Regression tests for src/fibo/resolution.py: target/position sizing
arithmetic and the stop/target resolution walk over 1-minute bars,
including the same-bar-tie -> STOP conservative rule."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.resolution import (
    compute_r, compute_target, position_size_shares, resolve_trade, FIXED_RISK_RS,
)


def _bars(rows):
    """rows: list of (ts_str, o, h, l, c)."""
    return pd.DataFrame([
        {"ts": pd.Timestamp(f"2024-01-02 {t}"), "open": o, "high": h, "low": l, "close": c}
        for t, o, h, l, c in rows
    ])


def test_compute_r_and_target_capped_at_swing_high():
    entry, stop = 110.0, 100.0  # R = 10
    # 2R target = 130, but swing high is only 125 -> target must be capped at 125
    assert compute_r(entry, stop) == pytest.approx(10.0)
    assert compute_target(entry, stop, swing_high_price=125.0) == pytest.approx(125.0)
    # when the swing high is ABOVE 2R, the plain 2R target applies
    assert compute_target(entry, stop, swing_high_price=200.0) == pytest.approx(130.0)


def test_position_size_floors_shares_and_never_exceeds_fixed_risk():
    # R = 37, Rs 500 / 37 = 13.51... -> must floor to 13, not round to 14
    # (rounding up would risk more than Rs 500 if stopped out)
    shares = position_size_shares(entry_price=137.0, stop_price=100.0)
    assert shares == 13
    assert shares * 37.0 <= FIXED_RISK_RS


def test_position_size_raises_on_nonpositive_r():
    with pytest.raises(ValueError):
        position_size_shares(entry_price=100.0, stop_price=105.0)  # stop above entry: invalid for a long


def test_resolve_trade_hits_target_cleanly():
    bars = _bars([
        ("09:31", 110, 111, 109, 110),
        ("09:32", 110, 116, 110, 115),   # target=115 touched here
        ("09:33", 115, 117, 114, 116),
    ])
    result = resolve_trade(bars, entry_ts="2024-01-02 09:30", stop_price=100.0, target_price=115.0, exit_ts="2024-01-02 15:15")
    assert result["outcome"] == "TARGET"
    assert result["exit_price"] == pytest.approx(115.0)
    assert result["exit_ts"] == pd.Timestamp("2024-01-02 09:32")


def test_resolve_trade_hits_stop_cleanly():
    bars = _bars([
        ("09:31", 110, 111, 109, 110),
        ("09:32", 110, 111, 99, 100),    # stop=100 touched here
        ("09:33", 100, 102, 99, 101),
    ])
    result = resolve_trade(bars, entry_ts="2024-01-02 09:30", stop_price=100.0, target_price=130.0, exit_ts="2024-01-02 15:15")
    assert result["outcome"] == "STOP"
    assert result["exit_price"] == pytest.approx(100.0)
    assert result["exit_ts"] == pd.Timestamp("2024-01-02 09:32")


def test_resolve_trade_same_bar_tie_counts_as_stop():
    # a single bar's range covers BOTH stop (100) and target (120) -- must resolve STOP, not TARGET
    bars = _bars([
        ("09:31", 110, 111, 109, 110),
        ("09:32", 110, 125, 95, 105),    # high=125 >= target(120) AND low=95 <= stop(100)
    ])
    result = resolve_trade(bars, entry_ts="2024-01-02 09:30", stop_price=100.0, target_price=120.0, exit_ts="2024-01-02 15:15")
    assert result["outcome"] == "STOP"
    assert result["exit_price"] == pytest.approx(100.0)


def test_resolve_trade_neither_hit_exits_at_1515_close():
    bars = _bars([
        ("09:31", 110, 112, 108, 110),
        ("15:14", 110, 112, 108, 111),
        ("15:15", 111, 113, 110, 112),   # neither stop(90) nor target(200) touched -> TIME_EXIT at this bar's close
    ])
    result = resolve_trade(bars, entry_ts="2024-01-02 09:30", stop_price=90.0, target_price=200.0, exit_ts="2024-01-02 15:15")
    assert result["outcome"] == "TIME_EXIT"
    assert result["exit_price"] == pytest.approx(112.0)
    assert result["exit_ts"] == pd.Timestamp("2024-01-02 15:15")


def test_resolve_trade_excludes_the_entry_bar_itself():
    # the entry bar's own range would touch the target, but it must be
    # excluded from monitoring (entry_ts itself is not scanned)
    bars = _bars([
        ("09:30", 110, 200, 109, 110),   # entry bar -- must be ignored even though high=200 >= target
        ("09:31", 110, 111, 109, 110),
    ])
    result = resolve_trade(bars, entry_ts="2024-01-02 09:30", stop_price=100.0, target_price=120.0, exit_ts="2024-01-02 15:15")
    assert result["outcome"] == "TIME_EXIT"  # neither the (excluded) entry bar nor 09:31 hits anything
