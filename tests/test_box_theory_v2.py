"""Regression tests for src/box_theory/v2.py's find_entry_v2: the
trailing 8-candle (down to 4) window, the strong-candle check (green +
1.5x range + 1.5x volume), two-candle patience (1st vs 2nd candidate,
no further scan), the insufficient-candles skip, and the 5% room floor.
Exit/stop/arming is reused, untested-again here (covered by
tests/test_box_theory_resolution.py already)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from box_theory.bars import aggregate_to_5min
from box_theory.v2 import find_entry_v2, _trailing_window, _is_strong_candle, ROOM_PCT_V2

DAY = "2024-01-02"


def _expand_candle(ts_start: str, o: float, h: float, l: float, c: float, vol: float = 1000) -> list[dict]:
    base = pd.Timestamp(f"{DAY} {ts_start}")
    return [
        {"ts": base, "open": o, "high": o, "low": o, "close": o, "volume": vol * 0.2},
        {"ts": base + pd.Timedelta(minutes=1), "open": o, "high": h, "low": l, "close": o, "volume": vol * 0.2},
        {"ts": base + pd.Timedelta(minutes=2), "open": o, "high": o, "low": o, "close": o, "volume": vol * 0.2},
        {"ts": base + pd.Timedelta(minutes=3), "open": o, "high": o, "low": o, "close": o, "volume": vol * 0.2},
        {"ts": base + pd.Timedelta(minutes=4), "open": o, "high": max(o, c), "low": min(o, c), "close": c,
         "volume": vol * 0.2},
    ]


def _session(candle_specs: list[tuple]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for spec in candle_specs:
        rows.extend(_expand_candle(*spec))
    bars1 = pd.DataFrame(rows)
    candles5 = aggregate_to_5min(bars1)
    return bars1, candles5


def _flat_candles(n: int, start="09:15", o=100.0, h=101.0, l=99.0, c=100.0, vol=1000.0):
    """n ordinary, identically-shaped candles starting at `start`, 5 min apart."""
    base = pd.Timestamp(f"{DAY} {start}")
    specs = []
    for i in range(n):
        ts = (base + pd.Timedelta(minutes=5 * i)).strftime("%H:%M")
        specs.append((ts, o, h, l, c, vol))
    return specs


# ---------------------------------------------------------------------
# trailing window
# ---------------------------------------------------------------------

def test_trailing_window_uses_full_8_when_available():
    specs = _flat_candles(10)  # touch will be idx 9 (last), 10 candles total, 9 prior + itself = window of 8
    _, candles5 = _session(specs)
    window = _trailing_window(candles5, touch_idx=9)
    assert len(window) == 8
    assert window.iloc[-1]["ts"] == candles5.iloc[9]["ts"]  # ends at touch inclusive


def test_trailing_window_shrinks_but_floors_at_4():
    specs = _flat_candles(5)
    _, candles5 = _session(specs)
    window = _trailing_window(candles5, touch_idx=4)  # 5 available (idx 0..4) -> window of 5
    assert len(window) == 5


def test_trailing_window_none_below_4():
    specs = _flat_candles(3)
    _, candles5 = _session(specs)
    window = _trailing_window(candles5, touch_idx=2)  # only 3 candles available -> below floor
    assert window is None


# ---------------------------------------------------------------------
# strong-candle check
# ---------------------------------------------------------------------

def test_is_strong_candle_requires_green_and_range_and_volume():
    # trailing window: 4 flat candles, range=2 (101-99), volume=1000 each
    specs = _flat_candles(4, h=101.0, l=99.0, vol=1000.0)
    _, candles5 = _session(specs)
    mean_range, mean_volume = 2.0, 1000.0

    # candidate idx 4 doesn't exist yet in this 4-candle frame -- add one strong green candle
    strong_specs = specs + [("09:35", 100, 104, 99, 103, 2000)]  # range=5>=3, vol=2000>=1500, green
    _, candles5_strong = _session(strong_specs)
    assert _is_strong_candle(candles5_strong, 4, mean_range, mean_volume) is True

    weak_range_specs = specs + [("09:35", 100, 101.5, 99.5, 101, 2000)]  # range=2 < 1.5*2=3
    _, candles5_weak_range = _session(weak_range_specs)
    assert _is_strong_candle(candles5_weak_range, 4, mean_range, mean_volume) is False

    weak_vol_specs = specs + [("09:35", 100, 104, 99, 103, 1200)]  # vol=1200 < 1500
    _, candles5_weak_vol = _session(weak_vol_specs)
    assert _is_strong_candle(candles5_weak_vol, 4, mean_range, mean_volume) is False

    red_specs = specs + [("09:35", 103, 104, 99, 100, 2000)]  # red (close<open), otherwise strong
    _, candles5_red = _session(red_specs)
    assert _is_strong_candle(candles5_red, 4, mean_range, mean_volume) is False


def test_is_strong_candle_false_past_end_of_day():
    specs = _flat_candles(4)
    _, candles5 = _session(specs)
    assert _is_strong_candle(candles5, 10, 2.0, 1000.0) is False


# ---------------------------------------------------------------------
# find_entry_v2: end-to-end
# ---------------------------------------------------------------------

def test_find_entry_v2_confirms_on_1st_candidate():
    # 3 ordinary trailing candles (range=2, vol=1000 each) + touch candle
    # (range=6, vol=1000) -> trailing-window mean_range=3.0, mean_volume=1000.
    # Threshold for a strong candidate: range>=4.5, volume>=1500.
    specs = [
        ("09:15", 100, 101, 99, 100, 1000),
        ("09:20", 100, 101, 99, 100, 1000),
        ("09:25", 100, 101, 99, 100, 1000),
        ("09:30", 95, 96, 90, 94, 1000),         # touch: low=90 breaches prev_low=92, range=6
        ("09:35", 94, 99.5, 93.5, 99, 2000),      # 1st candidate: range=6>=4.5, vol=2000>=1500, green -- confirms
        ("09:40", 99, 100, 98, 99.5, 1000),       # fill-bar source candle
    ]
    bars1, candles5 = _session(specs)
    result = find_entry_v2(candles5, bars1, prev_high=200.0, prev_low=92.0)
    assert result["status"] == "ENTERED"
    assert result["touch_idx"] == 3
    assert result["which_candle"] == 1
    assert result["confirm_idx"] == 4
    assert result["fill_ts"] == pd.Timestamp(f"{DAY} 09:40")
    assert result["entry_price"] == pytest.approx(99.0)  # 09:40 candle's own open


def test_find_entry_v2_confirms_on_2nd_candidate_when_1st_is_weak():
    # Same trailing window as above (mean_range=3.0, mean_volume=1000,
    # threshold range>=4.5/volume>=1500). 1st candidate deliberately weak
    # (range=2), 2nd candidate strong.
    specs = [
        ("09:15", 100, 101, 99, 100, 1000),
        ("09:20", 100, 101, 99, 100, 1000),
        ("09:25", 100, 101, 99, 100, 1000),
        ("09:30", 95, 96, 90, 94, 1000),         # touch, range=6
        ("09:35", 94, 95.5, 93.5, 95, 1000),      # 1st candidate: range=2 < 4.5 -- weak, fails
        ("09:40", 95, 101.5, 94.5, 100, 2200),    # 2nd candidate: range=7>=4.5, vol=2200>=1500, green -- confirms
        ("09:45", 100, 101, 99, 100.5, 1000),     # fill-bar source candle
    ]
    bars1, candles5 = _session(specs)
    result = find_entry_v2(candles5, bars1, prev_high=200.0, prev_low=92.0)
    assert result["status"] == "ENTERED"
    assert result["which_candle"] == 2
    assert result["confirm_idx"] == 5
    assert result["fill_ts"] == pd.Timestamp(f"{DAY} 09:45")
    assert result["entry_price"] == pytest.approx(100.0)


def test_find_entry_v2_no_strong_candle_when_neither_candidate_qualifies():
    specs = [
        ("09:15", 100, 101, 99, 100, 1000),
        ("09:20", 100, 101, 99, 100, 1000),
        ("09:25", 100, 101, 99, 100, 1000),
        ("09:30", 95, 96, 90, 94, 1000),         # touch, range=6, mean_range=3.0
        ("09:35", 94, 95.5, 93.5, 95, 1000),      # 1st candidate: range=2 < 4.5 -- weak
        ("09:40", 95, 96.5, 94.5, 96, 1000),      # 2nd candidate: range=2 < 4.5 -- also weak
    ]
    _, candles5 = _session(specs)
    bars1 = pd.DataFrame()  # never reached
    result = find_entry_v2(candles5, bars1, prev_high=200.0, prev_low=92.0)
    assert result["status"] == "NO_STRONG_CANDLE"
    assert result["touch_idx"] == 3


def test_find_entry_v2_insufficient_candles_when_touch_too_early():
    # touch at idx 1 -> only 2 candles available (below the floor of 4)
    specs = [
        ("09:15", 100, 101, 99, 100, 1000),
        ("09:20", 100, 101, 90, 95, 1000),    # touch (prev_low=92)
        ("09:25", 95, 102, 94, 101, 2600),      # would otherwise confirm strongly
    ]
    _, candles5 = _session(specs)
    bars1 = pd.DataFrame()
    result = find_entry_v2(candles5, bars1, prev_high=200.0, prev_low=92.0)
    assert result["status"] == "INSUFFICIENT_CANDLES"
    assert result["touch_idx"] == 1


def test_find_entry_v2_no_room_at_5_percent_floor():
    specs = [
        ("09:15", 100, 101, 99, 100, 1000),
        ("09:20", 100, 101, 99, 100, 1000),
        ("09:25", 100, 101, 99, 100, 1000),
        ("09:30", 95, 96, 90, 94, 1000),         # touch, range=6
        ("09:35", 94, 99.5, 93.5, 99, 2000),      # confirms (1st candidate)
        ("09:40", 99, 100, 98, 99.5, 1000),       # fill bar: open=99
    ]
    bars1, candles5 = _session(specs)
    # prev_high=103 -> room = (103-99)/99 = 4.04% < 5%
    result = find_entry_v2(candles5, bars1, prev_high=103.0, prev_low=92.0)
    assert result["status"] == "NO_ROOM"
    assert result["room_at_entry"] == pytest.approx((103.0 - 99.0) / 99.0)


def test_find_entry_v2_room_exactly_at_5_percent_enters():
    specs = [
        ("09:15", 100, 101, 99, 100, 1000),
        ("09:20", 100, 101, 99, 100, 1000),
        ("09:25", 100, 101, 99, 100, 1000),
        ("09:30", 95, 96, 90, 94, 1000),
        ("09:35", 94, 99.5, 93.5, 99, 2000),
        ("09:40", 99, 100, 98, 99.5, 1000),
    ]
    bars1, candles5 = _session(specs)
    prev_high = 99.0 * 1.05  # exactly 5% room
    result = find_entry_v2(candles5, bars1, prev_high=prev_high, prev_low=92.0)
    assert result["status"] == "ENTERED"
    assert result["room_at_entry"] == pytest.approx(ROOM_PCT_V2)
