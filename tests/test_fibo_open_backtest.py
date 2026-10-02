"""Regression tests for src/fibo_open/backtest_open.py -- the open-entry
evaluation engine. Mirrors tests/test_fibo_backtest.py's synthetic-day
construction (one bar per minute, 09:15-15:29)."""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_open.backtest_open import find_open_entry, evaluate_entity_day_open
from fibo.scale_probe import ScaleDecision

DAY = "2020-06-15"


def _day_bars(default_price=100.0, overrides=None):
    times = pd.date_range(f"{DAY} 09:15", f"{DAY} 15:29", freq="1min")
    rows = []
    for t in times:
        ov = (overrides or {}).get(t.strftime("%H:%M"), {})
        rows.append({
            "entity_id": "E1", "trade_date": dt.date.fromisoformat(DAY), "ts": t,
            "open": ov.get("open", default_price), "high": ov.get("high", default_price),
            "low": ov.get("low", default_price), "close": ov.get("close", default_price),
            "volume": 100,
        })
    return pd.DataFrame(rows)


def _signal(uptrend=True, has_swing=True, zone_low=99.0, zone_high=101.0, swing_high_price=200.0):
    return {"uptrend": uptrend, "has_swing": has_swing, "zone_low": zone_low, "zone_high": zone_high,
            "swing_high_price": swing_high_price}


def _evaluate(bars, signal_row, factor_d=1.0, scale=1.0, decision=ScaleDecision.RAW_EQUIVALENT):
    return evaluate_entity_day_open("E1", dt.date.fromisoformat(DAY), signal_row, decision, scale, factor_d, bars)


# ---- find_open_entry ----

def test_find_open_entry_is_the_0930_bars_own_open_not_its_close():
    overrides = {"09:30": {"open": 150.0, "close": 160.0}}
    bars = _day_bars(overrides=overrides)
    entry = find_open_entry(bars, dt.date.fromisoformat(DAY))
    assert entry is not None
    entry_ts, entry_price = entry
    assert entry_price == pytest.approx(150.0)
    assert entry_ts == pd.Timestamp(f"{DAY} 09:30")


def test_find_open_entry_none_when_0930_bar_missing():
    bars = _day_bars()
    bars = bars[bars["ts"].dt.time != dt.time(9, 30)]
    assert find_open_entry(bars, dt.date.fromisoformat(DAY)) is None


# ---- evaluate_entity_day_open: category gating, unchanged from breakout rule ----

def test_excluded_scale_short_circuits():
    bars = _day_bars()
    result = _evaluate(bars, _signal(), decision=ScaleDecision.UNRESOLVED)
    assert result["category"] == "EXCLUDED_SCALE"


def test_no_intraday_data():
    result = _evaluate(None, _signal())
    assert result["category"] == "NO_INTRADAY_DATA"


def test_no_signal_when_not_uptrend_or_no_swing():
    bars = _day_bars()
    assert _evaluate(bars, _signal(uptrend=False))["category"] == "NO_SIGNAL"
    assert _evaluate(bars, _signal(has_swing=False))["category"] == "NO_SIGNAL"


def test_setup_off_when_orb_does_not_overlap_zone():
    bars = _day_bars()  # ORB flat at 100 both sides -> orb_high=orb_low=100
    result = _evaluate(bars, _signal(zone_low=150.0, zone_high=160.0))
    assert result["category"] == "SETUP_OFF"


# ---- entry is UNCONDITIONAL on every setup-ON day: no SETUP_ON_NO_TRIGGER ----

def test_every_setup_on_day_becomes_a_trade_no_breakout_wait():
    # ORB flat at 100 (orb_high=orb_low=100), zone overlaps trivially;
    # 09:30 open priced just above the ORB so R > 0. The point: a TRADE is
    # produced immediately from the fixed 09:30 price -- no breakout trigger
    # condition is evaluated at all (contrast fibo.backtest.find_entry,
    # which would scan forward for a close > orb_high).
    overrides = {"09:30": {"open": 105.0, "high": 105.0, "low": 105.0, "close": 105.0}}
    bars = _day_bars(default_price=100.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=95.0, zone_high=110.0))
    assert result["category"] == "TRADE"
    assert result["trade"]["entry_price"] == pytest.approx(105.0)
    assert result["trade"]["entry_ts"] == pd.Timestamp(f"{DAY} 09:30")


# ---- the re-derived assumption: the entry bar's OWN high/low must be monitored ----

def test_stop_hit_within_the_entry_bar_itself_is_caught():
    # entry at 09:30 open=105 (stop = orb_low = 100); the SAME 09:30 bar's
    # low dips to 99 before its own close -- must resolve as STOP, not be
    # skipped the way the breakout rule's "exclude the entry bar" convention
    # would skip it if blindly reused here.
    overrides = {"09:30": {"open": 105.0, "low": 99.0, "high": 105.0, "close": 104.0}}
    bars = _day_bars(default_price=100.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=95.0, zone_high=110.0))
    assert result["category"] == "TRADE"
    trade = result["trade"]
    assert trade["exit_reason"] == "STOP"
    assert trade["exit_ts"] == pd.Timestamp(f"{DAY} 09:30")


def test_target_hit_within_the_entry_bar_itself_is_caught():
    overrides = {"09:30": {"open": 105.0, "low": 105.0, "high": 115.0, "close": 110.0}}
    bars = _day_bars(default_price=100.0, overrides=overrides)
    # stop=100, entry=105 -> R=5, target=min(105+10, swing_high=200)=115
    result = _evaluate(bars, _signal(zone_low=95.0, zone_high=110.0, swing_high_price=200.0))
    assert result["category"] == "TRADE"
    trade = result["trade"]
    assert trade["exit_reason"] == "TARGET"
    assert trade["exit_ts"] == pd.Timestamp(f"{DAY} 09:30")


def test_degenerate_qty_when_r_too_large_for_fixed_risk():
    overrides = {"09:30": {"open": 100000.0}}
    bars = _day_bars(default_price=0.01, overrides=overrides)
    # ORB low ~0.01, entry 100000 -> R huge -> qty = floor(500/R) = 0
    result = _evaluate(bars, _signal(zone_low=0.0, zone_high=200000.0))
    assert result["category"] == "DEGENERATE_QTY"
