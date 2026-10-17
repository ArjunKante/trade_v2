"""Regression tests for src/box_theory/resolution.py and bars.py: touch
detection, FAST/SLOW confirmation (including SLOW's extra close-above
condition), the entry fill/room filter, the 3% stop walk (including a
gap-below-stop fill), arming + FAST/SLOW armed red-candle exit, the
same-bar STOP-wins tie, and the 15:15 time exit."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from box_theory.bars import aggregate_to_5min
from box_theory.resolution import (
    find_touch_idx, find_fast_confirmation, find_slow_confirmation,
    find_entry, resolve_exit, resolve_exit_arrays, position_size_shares, FIXED_RISK_RS,
)

DAY = "2024-01-02"


def _expand_candle(ts_start: str, o: float, h: float, l: float, c: float) -> list[dict]:
    """One 5-minute candle (open o, high h, low l, close c) expanded into
    5 one-minute bars whose own aggregate reproduces exactly (o, h, l, c)."""
    base = pd.Timestamp(f"{DAY} {ts_start}")
    return [
        {"ts": base, "open": o, "high": o, "low": o, "close": o, "volume": 100},
        {"ts": base + pd.Timedelta(minutes=1), "open": o, "high": h, "low": l, "close": o, "volume": 100},
        {"ts": base + pd.Timedelta(minutes=2), "open": o, "high": o, "low": o, "close": o, "volume": 100},
        {"ts": base + pd.Timedelta(minutes=3), "open": o, "high": o, "low": o, "close": o, "volume": 100},
        {"ts": base + pd.Timedelta(minutes=4), "open": o, "high": max(o, c), "low": min(o, c), "close": c, "volume": 100},
    ]


def _session(candle_specs: list[tuple]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """candle_specs: list of (ts_start_str, o, h, l, c), one per 5-minute
    bucket, in session order. Returns (bars1, candles5)."""
    rows = []
    for spec in candle_specs:
        rows.extend(_expand_candle(*spec))
    bars1 = pd.DataFrame(rows)
    candles5 = aggregate_to_5min(bars1)
    return bars1, candles5


# ---------------------------------------------------------------------
# touch / confirmation
# ---------------------------------------------------------------------

def test_find_touch_idx_first_candle_with_low_breaching_prev_low():
    _, candles5 = _session([
        ("09:15", 100, 101, 99, 100),
        ("09:20", 100, 101, 95, 96),   # PREV_LOW=96 touched here (low=95<=96)
        ("09:25", 96, 98, 95, 97),     # also breaches, but not the FIRST
    ])
    idx = find_touch_idx(candles5, prev_low=96.0)
    assert idx == 1


def test_find_touch_idx_none_when_never_touched():
    _, candles5 = _session([("09:15", 100, 101, 99, 100)])
    assert find_touch_idx(candles5, prev_low=50.0) is None


def test_fast_confirmation_first_green_after_touch_not_adjacent():
    # touch at idx0; idx1 is red; idx2 is the first green -> FAST confirms at idx2
    _, candles5 = _session([
        ("09:15", 100, 100, 90, 95),   # touch candle (red, low=90)
        ("09:20", 95, 96, 94, 94),     # red -- does not confirm
        ("09:25", 94, 97, 94, 96),     # green -- confirms
    ])
    assert find_fast_confirmation(candles5, after_idx=0) == 2


def test_slow_confirmation_requires_second_close_above_first():
    _, candles5 = _session([
        ("09:15", 100, 100, 90, 95),     # touch
        ("09:20", 95, 97, 94, 96),       # green, close=96
        ("09:25", 96, 97, 95, 95.5),     # green but closes BELOW 96 -- pair fails
        ("09:30", 95.5, 98, 95, 97),     # green, close=97
        ("09:35", 97, 99, 96.5, 98),     # green, close=98 > 97 -- pair confirms at (3,4)
    ])
    assert find_slow_confirmation(candles5, after_idx=0) == (3, 4)


# ---------------------------------------------------------------------
# entry fill, room filter, sizing
# ---------------------------------------------------------------------

def test_find_entry_fast_fills_at_open_of_bar_after_confirm_closes():
    bars1, candles5 = _session([
        ("09:15", 100, 100, 85, 95),   # touch, PREV_LOW=90 breached (low=85)
        ("09:20", 95, 96, 94, 94.5),   # red -- does not confirm
        ("09:25", 94.5, 97, 94, 96),   # confirms FAST -- closes at 09:30
        ("09:30", 96, 97, 95.5, 96.5), # fill bar: open=96
    ])
    result = find_entry(candles5, bars1, prev_high=150.0, prev_low=90.0, config="FAST")
    assert result["status"] == "ENTERED"
    assert result["fill_ts"] == pd.Timestamp(f"{DAY} 09:30")
    assert result["entry_price"] == pytest.approx(96.0)  # 09:30 candle's own open


def test_find_entry_no_room_when_prev_high_too_close():
    bars1, candles5 = _session([
        ("09:15", 100, 100, 85, 95),
        ("09:20", 95, 96, 94, 94.5),
        ("09:25", 94.5, 97, 94, 96),
        ("09:30", 96, 97, 95.5, 96.5), # fill at 96
    ])
    # entry fills at 96; prev_high=96.5 -> room = 0.5/96 = 0.52% < 1%
    result = find_entry(candles5, bars1, prev_high=96.5, prev_low=90.0, config="FAST")
    assert result["status"] == "NO_ROOM"


def test_find_entry_fill_outside_window_skipped():
    bars1, candles5 = _session([
        ("14:20", 100, 100, 85, 95),   # touch
        ("14:25", 95, 96, 94, 94.5),   # red -- does not confirm
        ("14:30", 94.5, 97, 94, 96),   # confirms -- closes at 14:35
        ("14:35", 96, 96.5, 95.5, 96.2),  # fill bar exists, but 14:35 > 14:30 (latest fill)
    ])
    result = find_entry(candles5, bars1, prev_high=150.0, prev_low=90.0, config="FAST")
    assert result["status"] == "FILL_OUTSIDE_WINDOW"


def test_position_size_floors_and_caps_risk():
    qty = position_size_shares(entry_price=100.0)  # 3% of 100 = Rs3/share risk
    assert qty == 166  # floor(500/3) = 166
    assert qty * 3.0 <= FIXED_RISK_RS


# ---------------------------------------------------------------------
# stop / arming / exit
# ---------------------------------------------------------------------

def test_resolve_exit_stop_hit_on_1min_bar():
    # entry at 100 (stop=97). Entry candle 09:30-09:35 is flat; inside it,
    # minute 09:32 dips to 96 (below stop) via manual bars.
    entry_ts = pd.Timestamp(f"{DAY} 09:30")
    bars1 = pd.DataFrame([
        {"ts": entry_ts, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 100},
        {"ts": entry_ts + pd.Timedelta(minutes=1), "open": 100.0, "high": 100.0, "low": 99.0, "close": 99.0, "volume": 100},
        {"ts": entry_ts + pd.Timedelta(minutes=2), "open": 99.0, "high": 99.0, "low": 96.0, "close": 96.5, "volume": 100},  # stop(97) breached
        {"ts": entry_ts + pd.Timedelta(minutes=3), "open": 96.5, "high": 97.0, "low": 96.0, "close": 96.8, "volume": 100},
        {"ts": entry_ts + pd.Timedelta(minutes=4), "open": 96.8, "high": 97.5, "low": 96.5, "close": 97.0, "volume": 100},
    ])
    candles5 = aggregate_to_5min(bars1)
    result = resolve_exit(candles5, bars1, entry_candle_idx=0, fill_ts=entry_ts,
                           entry_price=100.0, prev_high=200.0, config="FAST")
    assert result["outcome"] == "STOP"
    assert result["exit_price"] == pytest.approx(97.0)  # bar opened (99.0) above stop -> fill at stop


def test_resolve_exit_stop_gapped_below_fills_at_open():
    entry_ts = pd.Timestamp(f"{DAY} 09:30")
    bars1 = pd.DataFrame([
        {"ts": entry_ts, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 100},
        {"ts": entry_ts + pd.Timedelta(minutes=1), "open": 95.0, "high": 95.0, "low": 94.0, "close": 94.5, "volume": 100},  # opened BELOW stop(97)
    ])
    candles5 = aggregate_to_5min(bars1)
    result = resolve_exit(candles5, bars1, entry_candle_idx=0, fill_ts=entry_ts,
                           entry_price=100.0, prev_high=200.0, config="FAST")
    assert result["outcome"] == "STOP"
    assert result["exit_price"] == pytest.approx(95.0)  # fills at the gapped-down open, not the stop level


def test_resolve_exit_fast_armed_red_candle_exit():
    entry_ts = pd.Timestamp(f"{DAY} 09:30")
    # entry candle (idx0) arms immediately (high >= 0.995*prev_high=99.5);
    # idx1 green; idx2 red -> FAST exit confirms at idx2, fills at idx3's bar
    bars1, _ = _session([
        ("09:30", 90, 100, 89, 95),    # entry candle, high=100 arms (prev_high=100)
        ("09:35", 95, 97, 94, 96),     # green
        ("09:40", 96, 97, 93, 94),     # red -- confirms FAST exit
        ("09:45", 94, 95, 93, 94),
    ])
    candles5 = aggregate_to_5min(bars1)
    result = resolve_exit(candles5, bars1, entry_candle_idx=0, fill_ts=entry_ts,
                           entry_price=90.0, prev_high=100.0, config="FAST")
    assert result["outcome"] == "ARMED_EXIT"
    assert result["armed"] is True
    assert result["exit_ts"] == pd.Timestamp(f"{DAY} 09:45")
    assert result["exit_price"] == pytest.approx(94.0)  # 09:45 candle's own open


def test_resolve_exit_slow_requires_two_consecutive_red_candles():
    entry_ts = pd.Timestamp(f"{DAY} 09:30")
    bars1, _ = _session([
        ("09:30", 90, 100, 89, 95),    # entry candle, arms
        ("09:35", 95, 97, 94, 96),     # green
        ("09:40", 96, 97, 93, 94),     # red (1 of 2)
        ("09:45", 94, 95, 90, 91),     # red (2 of 2) -- SLOW confirms
        ("09:50", 91, 92, 90, 91),
    ])
    candles5 = aggregate_to_5min(bars1)
    result = resolve_exit(candles5, bars1, entry_candle_idx=0, fill_ts=entry_ts,
                           entry_price=90.0, prev_high=100.0, config="SLOW")
    assert result["outcome"] == "ARMED_EXIT"
    assert result["exit_ts"] == pd.Timestamp(f"{DAY} 09:50")


def test_resolve_exit_time_exit_when_nothing_triggers():
    entry_ts = pd.Timestamp(f"{DAY} 09:30")
    bars1, _ = _session([
        ("09:30", 90, 91, 89, 90.5),   # never arms (prev_high=200)
        ("15:15", 90, 91, 89.5, 90.8),
    ])
    candles5 = aggregate_to_5min(bars1)
    result = resolve_exit(candles5, bars1, entry_candle_idx=0, fill_ts=entry_ts,
                           entry_price=90.0, prev_high=200.0, config="FAST")
    assert result["outcome"] == "TIME_EXIT"
    assert result["exit_price"] == pytest.approx(90.8)
    assert result["armed"] is False
    assert result["time_exit_fallback"] is False  # the real 15:15 candle existed -- no fallback needed


def test_resolve_exit_same_bar_tie_stop_wins_over_armed_exit():
    # entry candle arms immediately; the very next 1-minute bar both
    # breaches the stop AND is the fill bar for an armed exit that would
    # otherwise trigger here -- STOP must win.
    entry_ts = pd.Timestamp(f"{DAY} 09:30")
    bars1, _ = _session([
        ("09:30", 90, 100, 89, 95),    # entry candle, arms (prev_high=100)
        ("09:35", 95, 96, 93, 94),     # red -- confirms FAST armed exit, fill bar = 09:40's first minute
        ("09:40", 94, 94.5, 93.5, 94),
    ])
    candles5 = aggregate_to_5min(bars1)
    # override the 09:40 fill bar's low to also breach the stop (90*0.97=87.3)
    bars1.loc[bars1["ts"] == pd.Timestamp(f"{DAY} 09:40"), ["low", "open"]] = [80.0, 85.0]
    result = resolve_exit(candles5, bars1, entry_candle_idx=0, fill_ts=entry_ts,
                           entry_price=90.0, prev_high=100.0, config="FAST")
    assert result["outcome"] == "STOP"


# ---------------------------------------------------------------------
# resolve_exit_arrays (box_theory.nulls' fast path) must agree exactly
# with resolve_exit (the DataFrame-based, reference implementation) on
# every scenario above.
# ---------------------------------------------------------------------

def _cross_check(candles5, bars1, entry_candle_idx, fill_ts, entry_price, prev_high, config):
    reference = resolve_exit(candles5, bars1, entry_candle_idx, fill_ts, entry_price, prev_high, config)
    fast = resolve_exit_arrays(
        candles5["ts"].to_numpy(), candles5["open"].to_numpy(), candles5["high"].to_numpy(),
        candles5["close"].to_numpy(), candles5["is_red"].to_numpy(),
        bars1["ts"].to_numpy(), bars1["open"].to_numpy(), bars1["low"].to_numpy(),
        entry_candle_idx, pd.Timestamp(fill_ts).to_numpy(), entry_price, prev_high, config,
    )
    assert fast["outcome"] == reference["outcome"]
    assert fast["exit_price"] == pytest.approx(reference["exit_price"])
    assert pd.Timestamp(fast["exit_ts"]) == reference["exit_ts"]
    assert fast["armed"] == reference["armed"]
    assert fast["time_exit_fallback"] == reference["time_exit_fallback"]


def test_resolve_exit_arrays_matches_reference_on_every_prior_scenario():
    entry_ts = pd.Timestamp(f"{DAY} 09:30")

    bars1, _ = _session([
        ("09:30", 100, 100.5, 99.5, 100), ("09:31", 100, 100, 99, 99),
        ("09:32", 99, 99, 96, 96.5), ("09:33", 96.5, 97, 96, 96.8), ("09:34", 96.8, 97.5, 96.5, 97),
    ])
    candles5 = aggregate_to_5min(bars1)
    _cross_check(candles5, bars1, 0, entry_ts, 100.0, 200.0, "FAST")  # STOP

    bars1, _ = _session([
        ("09:30", 90, 100, 89, 95), ("09:35", 95, 97, 94, 96), ("09:40", 96, 97, 93, 94), ("09:45", 94, 95, 93, 94),
    ])
    candles5 = aggregate_to_5min(bars1)
    _cross_check(candles5, bars1, 0, entry_ts, 90.0, 100.0, "FAST")  # ARMED_EXIT

    bars1, _ = _session([
        ("09:30", 90, 100, 89, 95), ("09:35", 95, 97, 94, 96), ("09:40", 96, 97, 93, 94),
        ("09:45", 94, 95, 90, 91), ("09:50", 91, 92, 90, 91),
    ])
    candles5 = aggregate_to_5min(bars1)
    _cross_check(candles5, bars1, 0, entry_ts, 90.0, 100.0, "SLOW")  # ARMED_EXIT (consecutive reds)

    bars1, _ = _session([("09:30", 90, 91, 89, 90.5), ("15:15", 90, 91, 89.5, 90.8)])
    candles5 = aggregate_to_5min(bars1)
    _cross_check(candles5, bars1, 0, entry_ts, 90.0, 200.0, "FAST")  # TIME_EXIT

    bars1, _ = _session([
        ("09:30", 90, 100, 89, 95), ("09:35", 95, 96, 93, 94), ("09:40", 94, 94.5, 93.5, 94),
    ])
    bars1.loc[bars1["ts"] == pd.Timestamp(f"{DAY} 09:40"), ["low", "open"]] = [80.0, 85.0]
    candles5 = aggregate_to_5min(bars1)
    _cross_check(candles5, bars1, 0, entry_ts, 90.0, 100.0, "FAST")  # same-bar tie -> STOP


# ---------------------------------------------------------------------
# Short-day fallback: an entity-day whose own archive doesn't reach
# 15:15 (an afternoon trading halt, or a data gap) -- found live during
# the real DEV run (one stock-day crashed the entire multi-hour backtest
# with an unhandled ValueError before this fallback existed). Section 2b's
# eligibility checks only validate the PREVIOUS session's completeness,
# never today's, so this is not caught earlier -- resolve_exit must
# degrade gracefully, the same way fibo.resolution.resolve_trade already
# falls back to the latest available bar when its own exit_ts bar is
# missing, rather than raising.
# ---------------------------------------------------------------------

def test_resolve_exit_time_exit_falls_back_when_day_has_no_1515_candle():
    entry_ts = pd.Timestamp(f"{DAY} 09:30")
    # the archive stops at 13:45 -- no candle anywhere near 15:15
    bars1, _ = _session([
        ("09:30", 90, 91, 89, 90.5),   # never arms (prev_high=200)
        ("13:45", 90.5, 91, 90, 90.9),  # last available candle of the (short) day
    ])
    candles5 = aggregate_to_5min(bars1)
    result = resolve_exit(candles5, bars1, entry_candle_idx=0, fill_ts=entry_ts,
                           entry_price=90.0, prev_high=200.0, config="FAST")
    assert result["outcome"] == "TIME_EXIT"
    assert result["exit_price"] == pytest.approx(90.9)  # the 13:45 candle's own close
    assert result["exit_ts"] == pd.Timestamp(f"{DAY} 13:50")  # that candle's own close time
    assert result["armed"] is False
    assert result["time_exit_fallback"] is True


def test_resolve_exit_arrays_matches_reference_on_short_day_fallback():
    entry_ts = pd.Timestamp(f"{DAY} 09:30")
    bars1, _ = _session([
        ("09:30", 90, 91, 89, 90.5),
        ("13:45", 90.5, 91, 90, 90.9),
    ])
    candles5 = aggregate_to_5min(bars1)
    _cross_check(candles5, bars1, 0, entry_ts, 90.0, 200.0, "FAST")
