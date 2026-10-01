"""Regression tests for src/fibo/backtest.py -- the per-(entity, day)
evaluation engine. Synthetic full trading days (09:15-15:29, one bar per
minute) built to exercise every category and every exit reason, since
this module is explicitly for CODE VERIFICATION (PREREGISTRATION_FIBO.md
Section 5a) and must be trustworthy before any real trade is reported."""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.backtest import compute_orb, zones_overlap, find_entry, evaluate_entity_day
from fibo.scale_probe import ScaleDecision
from fibo.bars import aggregate_to_15min

DAY = "2020-06-15"


def _day_bars(default_price=100.0, overrides=None):
    """375 1-min bars for one full session, flat at default_price unless a
    specific 'HH:MM' key is overridden with an {open,high,low,close} dict."""
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
    return evaluate_entity_day("E1", dt.date.fromisoformat(DAY), signal_row, decision, scale, factor_d, bars)


# ---- helper-function unit tests ----

def test_compute_orb_from_09_15_window():
    # minutes 09:15..09:29 (15 bars) are the ORB window; the max high/min low
    # occur at the LAST minute in range, m=29
    overrides = {f"09:{m:02d}": {"high": 100.0 + m, "low": 95.0 - m} for m in range(15, 30)}
    overrides["09:30"] = {"high": 999.0, "low": -999.0}  # outside the ORB window -- must NOT be included
    bars = _day_bars(overrides=overrides)
    orb_high, orb_low = compute_orb(bars)
    assert orb_high == pytest.approx(129.0)  # m=29 -> 100+29
    assert orb_low == pytest.approx(66.0)    # m=29 -> 95-29


def test_zones_overlap_true_and_false():
    assert zones_overlap(orb_low=99.0, orb_high=101.0, zone_low=100.0, zone_high=102.0)
    assert not zones_overlap(orb_low=99.0, orb_high=101.0, zone_low=150.0, zone_high=160.0)


def test_find_entry_picks_first_qualifying_candle_not_a_later_one():
    overrides = {
        "09:30": {"close": 100.0},   # below orb_high, no trigger
        "09:44": {"close": 100.0},   # 09:30 candle's close (last minute) -- still below
        "09:45": {"close": 102.0},   # this candle starts here
        "09:59": {"close": 102.0},   # 09:45 candle's close -- ABOVE orb_high=101 -> should trigger HERE
        "10:00": {"close": 200.0},   # a later, even-more-qualifying candle -- must NOT be picked
    }
    bars = _day_bars(default_price=100.0, overrides=overrides)
    bars_15min = aggregate_to_15min(bars)
    entry = find_entry(bars_15min, orb_high=101.0)
    assert entry is not None
    entry_ts, entry_price = entry
    assert entry_price == pytest.approx(102.0)
    assert entry_ts == pd.Timestamp(f"{DAY} 09:59")  # last 1-min bar inside the 09:45 candle


# ---- evaluate_entity_day: non-trade categories ----

def test_excluded_scale_short_circuits_before_touching_bars():
    result = _evaluate(bars=None, signal_row=_signal(), decision=ScaleDecision.UNRESOLVED, scale=None)
    assert result["category"] == "EXCLUDED_SCALE"


def test_no_signal_when_not_uptrend():
    bars = _day_bars()
    result = _evaluate(bars, _signal(uptrend=False))
    assert result["category"] == "NO_SIGNAL"


def test_no_signal_when_no_swing():
    bars = _day_bars()
    result = _evaluate(bars, _signal(has_swing=False))
    assert result["category"] == "NO_SIGNAL"


def test_setup_off_when_orb_does_not_overlap_zone():
    bars = _day_bars(default_price=100.0)  # ORB ~= [100,100]
    result = _evaluate(bars, _signal(zone_low=500.0, zone_high=600.0))
    assert result["category"] == "SETUP_OFF"


def test_setup_on_no_trigger_when_price_never_closes_above_orb_high():
    overrides = {f"09:{m:02d}": {"high": 101.0, "low": 99.0} for m in range(15, 30)}
    bars = _day_bars(default_price=100.0, overrides=overrides)  # never exceeds 101 all day
    result = _evaluate(bars, _signal(zone_low=99.0, zone_high=101.0))
    assert result["category"] == "SETUP_ON_NO_TRIGGER"


def test_degenerate_qty_when_r_exceeds_fixed_risk():
    overrides = {f"09:{m:02d}": {"high": 1101.0, "low": 100.0} for m in range(15, 30)}  # ORB low=100, high=1101 -> R=1001 if entry~1102
    overrides["09:45"] = {"close": 1102.0}
    bars = _day_bars(default_price=1102.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=100.0, zone_high=1101.0, swing_high_price=5000.0))
    assert result["category"] == "DEGENERATE_QTY"


# ---- evaluate_entity_day: the four required trade scenarios, plus same-bar tie ----

def _orb_and_entry_overrides(orb_high=101.0, orb_low=99.0, entry_close=102.0):
    overrides = {f"09:{m:02d}": {"high": orb_high, "low": orb_low} for m in range(15, 30)}
    overrides["09:45"] = {"close": entry_close}
    return overrides


def test_trade_hits_target_flat_2r():
    overrides = _orb_and_entry_overrides()
    overrides["10:00"] = {"high": 110.0, "low": 101.0, "close": 105.0}  # R=102-99=3, 2R target=108 -- exceeds 108
    bars = _day_bars(default_price=102.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=99.0, zone_high=101.0, swing_high_price=200.0))
    assert result["category"] == "TRADE"
    t = result["trade"]
    assert t["exit_reason"] == "TARGET"
    assert t["target"] == pytest.approx(108.0)
    assert t["stop"] == pytest.approx(99.0)
    assert t["entry_price"] == pytest.approx(102.0)
    assert t["gross_r"] == pytest.approx(2.0)


def test_trade_hits_stop():
    overrides = _orb_and_entry_overrides()
    overrides["10:00"] = {"high": 103.0, "low": 95.0, "close": 96.0}  # dips through stop=99
    bars = _day_bars(default_price=102.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=99.0, zone_high=101.0, swing_high_price=200.0))
    assert result["category"] == "TRADE"
    t = result["trade"]
    assert t["exit_reason"] == "STOP"
    assert t["exit_price"] == pytest.approx(99.0)
    assert t["gross_r"] == pytest.approx(-1.0)


def test_trade_exits_at_1515_when_neither_hit():
    overrides = _orb_and_entry_overrides()
    overrides["15:14"] = {"close": 103.5}  # between stop(99) and target(108), never touched either
    bars = _day_bars(default_price=102.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=99.0, zone_high=101.0, swing_high_price=200.0))
    assert result["category"] == "TRADE"
    t = result["trade"]
    assert t["exit_reason"] == "TIME_EXIT"
    assert t["exit_ts"] == pd.Timestamp(f"{DAY} 15:15")


def test_trade_target_capped_at_swing_high():
    overrides = _orb_and_entry_overrides()
    # R = 102-99 = 3, flat 2R would be 108, but swing_high (raw, factor=1) = 104 caps it lower
    overrides["10:00"] = {"high": 105.0, "low": 101.0, "close": 104.5}
    bars = _day_bars(default_price=102.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=99.0, zone_high=101.0, swing_high_price=104.0))
    assert result["category"] == "TRADE"
    t = result["trade"]
    assert t["target"] == pytest.approx(104.0)  # capped, not 108
    assert t["exit_reason"] == "TARGET"
    assert t["exit_price"] == pytest.approx(104.0)


def test_trade_same_bar_tie_resolves_as_stop():
    overrides = _orb_and_entry_overrides()
    overrides["10:00"] = {"high": 110.0, "low": 90.0, "close": 100.0}  # touches both stop(99) and target(108) in one bar
    bars = _day_bars(default_price=102.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=99.0, zone_high=101.0, swing_high_price=200.0))
    assert result["category"] == "TRADE"
    t = result["trade"]
    assert t["exit_reason"] == "STOP"
    assert t["exit_price"] == pytest.approx(99.0)


def test_trade_cost_fields_present_and_qty_correct():
    overrides = _orb_and_entry_overrides()
    overrides["10:00"] = {"high": 110.0, "low": 101.0, "close": 105.0}
    bars = _day_bars(default_price=102.0, overrides=overrides)
    result = _evaluate(bars, _signal(zone_low=99.0, zone_high=101.0, swing_high_price=200.0))
    t = result["trade"]
    # R=3, qty=floor(500/3)=166
    assert t["qty"] == 166
    assert t["cost_lo_rs"] > 0 and t["cost_hi_rs"] >= t["cost_lo_rs"]
    assert t["net_r_hi_cost"] <= t["net_r_lo_cost"]
    assert t["net_r_lo_cost"] == pytest.approx(t["gross_r"] - t["cost_lo_r"])
