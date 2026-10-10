"""Regression tests for src/fibo/indicators.py -- Alligator, fractals, ATR,
the 2xATR swing filter, and the golden zone. Hand-computable synthetic
fixtures throughout, so every assertion can be checked against a
by-hand arithmetic result, not just "did it run."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.indicators import (
    _smma, true_range, atr, alligator, alligator_uptrend, fractals,
    most_recent_confirmed_swing, golden_zone, ATR_PERIOD, SWING_LOOKBACK_DAYS,
)


def _ohlc(entity_id, highs, lows, closes, opens=None):
    n = len(highs)
    dates = pd.date_range("2022-01-03", periods=n, freq="B")
    opens = opens if opens is not None else closes
    return pd.DataFrame({
        "entity_id": entity_id, "trade_date": dates,
        "adjusted_open": opens, "adjusted_high": highs, "adjusted_low": lows, "adjusted_close": closes,
        "volume": [1000] * n, "turnover": [c * 1000 for c in closes],
    })


def test_smma_seeds_with_plain_sma_then_recurses_by_hand():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    out = _smma(s, period=3)
    assert np.isnan(out.iloc[0]) and np.isnan(out.iloc[1])
    # seed = mean(1,2,3) = 2.0
    assert out.iloc[2] == pytest.approx(2.0)
    # smma[3] = (2.0*2 + 4.0)/3 = 8/3
    assert out.iloc[3] == pytest.approx(8.0 / 3.0)
    # smma[4] = (8/3*2 + 5.0)/3
    expected4 = (8.0 / 3.0 * 2 + 5.0) / 3.0
    assert out.iloc[4] == pytest.approx(expected4)


def test_true_range_covers_gap_up_and_gap_down():
    # day0: H=10 L=9 C=9.5 ; day1 gaps UP: H=13 L=12 (prev close 9.5) -> TR = max(1, |13-9.5|=3.5, |12-9.5|=2.5) = 3.5
    # day2 gaps DOWN: H=8 L=6 (prev close ~12ish) -> TR dominated by |low - prev_close|
    df = _ohlc("E1", highs=[10, 13, 8], lows=[9, 12, 6], closes=[9.5, 12.5, 7.0])
    tr = true_range(df)
    assert tr.iloc[1] == pytest.approx(3.5)
    assert tr.iloc[2] == pytest.approx(abs(6 - 12.5))  # 6.5, the largest of the three TR components


def test_atr_wilder_matches_hand_recursion():
    n = ATR_PERIOD + 3
    highs = [100 + i for i in range(n)]
    lows = [98 + i for i in range(n)]
    closes = [99 + i for i in range(n)]
    df = _ohlc("E1", highs, lows, closes)
    result = atr(df, period=ATR_PERIOD)
    tr = true_range(df)
    hand = _smma(tr, ATR_PERIOD)
    pd.testing.assert_series_equal(
        result["atr"].reset_index(drop=True), hand.reset_index(drop=True), check_names=False)


def _ohlc_with_dates(entity_id, dates, highs, lows, closes):
    """Same shape as `_ohlc` above, but with explicit (possibly
    non-consecutive) dates -- needed to construct a deliberate stale gap,
    which `_ohlc`'s freq='B' date_range cannot represent."""
    return pd.DataFrame({
        "entity_id": entity_id, "trade_date": pd.to_datetime(dates),
        "adjusted_open": closes, "adjusted_high": highs, "adjusted_low": lows, "adjusted_close": closes,
        "volume": [1000] * len(dates), "turnover": [c * 1000 for c in closes],
    })


def test_true_range_nan_across_a_stale_calendar_gap():
    """Bug #2 shape (BUGS.md), unguarded in src/fibo/ until 2026-10-11: a
    row-based prev_close = shift(1) treats a multi-month halt as one
    ordinary trading day. before/after prices are deliberately far apart
    (100ish -> 300) so an un-guarded true_range would be enormous -- the
    fix must NaN it out, not shrink it."""
    before_dates = pd.bdate_range("2022-01-03", periods=20)
    after_dates = pd.bdate_range(before_dates[-1] + pd.Timedelta(days=200), periods=10)
    dates = list(before_dates) + list(after_dates)
    highs = [101 + i for i in range(20)] + [301 + i for i in range(10)]
    lows = [99 + i for i in range(20)] + [299 + i for i in range(10)]
    closes = [100 + i for i in range(20)] + [300 + i for i in range(10)]
    df = _ohlc_with_dates("E1", dates, highs, lows, closes)

    tr = true_range(df)
    boundary_idx = 20  # first row after the 200-day gap
    assert pd.isna(tr.iloc[boundary_idx])
    assert not pd.isna(tr.iloc[boundary_idx - 1])  # the row before the gap is unaffected
    assert not pd.isna(tr.iloc[boundary_idx + 1])  # rows after the boundary are normal again


def test_true_range_not_nan_across_a_short_gap():
    """A 3-day gap (ordinary weekend/holiday shape) must NOT be flagged --
    only matches test_true_range_nan_across_a_stale_calendar_gap's >5-day
    case, same STALE_GAP_DAYS=5 threshold as factors/lowvol.py."""
    before_dates = pd.bdate_range("2022-01-03", periods=10)
    after_dates = pd.bdate_range(before_dates[-1] + pd.Timedelta(days=3), periods=10)
    dates = list(before_dates) + list(after_dates)
    highs = [101 + i for i in range(20)]
    lows = [99 + i for i in range(20)]
    closes = [100 + i for i in range(20)]
    df = _ohlc_with_dates("E1", dates, highs, lows, closes)
    tr = true_range(df)
    assert not pd.isna(tr.iloc[10])


def test_true_range_nan_for_unexplained_jump_row_with_no_calendar_gap():
    """Bug #11 shape: a same-isin jump with gap_days=1 (an otherwise
    ordinary consecutive trading day) -- the calendar-gap check alone
    (STALE_GAP_DAYS) cannot see this; only the explicit
    unexplained_jump_dates flag can."""
    dates = pd.bdate_range("2022-01-03", periods=5)
    highs = [101, 102, 13, 104, 105]
    lows = [99, 100, 11, 102, 103]
    closes = [100, 101, 12, 103, 104]  # row 2 (index 2) is the MAJESCO-shape collapse
    df = _ohlc_with_dates("E1", dates, highs, lows, closes)

    tr_unguarded = true_range(df)
    assert not pd.isna(tr_unguarded.iloc[2])  # no gap, so un-guarded true_range sees nothing wrong

    jump_dates = {"E1": {dates[2]}}
    tr_guarded = true_range(df, unexplained_jump_dates=jump_dates)
    assert pd.isna(tr_guarded.iloc[2])
    assert not pd.isna(tr_guarded.iloc[1])
    assert not pd.isna(tr_guarded.iloc[3])  # the row AFTER the flagged date is a real true_range again


def test_atr_carries_forward_across_a_stale_gap_and_does_not_propagate_nan_forever():
    """The regression this fix exists to prevent: naively NaN-ing
    true_range at the gap would otherwise corrupt every later ATR value
    too, since Wilder's SMMA is recursive (out[i] depends on out[i-1]).
    Asserts both halves: ATR right after the gap equals ATR right before
    it (carried forward, not computed from a fabricated true_range), AND
    ATR resumes real recursive updates afterward rather than staying NaN."""
    before_dates = pd.bdate_range("2022-01-03", periods=20)
    after_dates = pd.bdate_range(before_dates[-1] + pd.Timedelta(days=200), periods=10)
    dates = list(before_dates) + list(after_dates)
    # before: H-L spread of 2 every day -> true_range (and hence ATR) converges to a constant 2.0.
    # after: a deliberately WIDER spread of 10 every day, so a resumed, real ATR update is numerically
    # distinguishable from "stuck at the carried-forward pre-gap value" -- not just non-NaN.
    highs = [101 + i for i in range(20)] + [305 + i for i in range(10)]
    lows = [99 + i for i in range(20)] + [295 + i for i in range(10)]
    closes = [100 + i for i in range(20)] + [300 + i for i in range(10)]
    df = _ohlc_with_dates("E1", dates, highs, lows, closes)

    result = atr(df, period=ATR_PERIOD)
    atrs = result["atr"].to_numpy()
    boundary_idx = 20

    assert not np.isnan(atrs[boundary_idx - 1])
    assert atrs[boundary_idx] == pytest.approx(atrs[boundary_idx - 1])  # carried forward, not NaN, not fabricated
    assert not np.isnan(atrs[boundary_idx + 1])  # real recursive updates resume -- no permanent NaN propagation
    assert atrs[boundary_idx + 1] != pytest.approx(atrs[boundary_idx])  # and it actually DID update, not stuck


def test_alligator_uptrend_true_in_sustained_rally_false_in_downtrend():
    n = 60
    up_prices = 100 + np.arange(n) * 1.0
    df_up = _ohlc("UP", highs=up_prices + 1, lows=up_prices - 1, closes=up_prices)
    alli_up = alligator(df_up)
    trend_up = alligator_uptrend(df_up, alli_up)
    tail = trend_up.dropna().tail(5)
    assert tail["uptrend"].all(), "sustained rally should be flagged as an Alligator uptrend by the end"

    down_prices = 200 - np.arange(n) * 1.0
    df_down = _ohlc("DOWN", highs=down_prices + 1, lows=down_prices - 1, closes=down_prices)
    alli_down = alligator(df_down)
    trend_down = alligator_uptrend(df_down, alli_down)
    tail_down = trend_down.dropna().tail(5)
    assert not tail_down["uptrend"].any(), "sustained decline must never be flagged as an uptrend"


def test_fractal_detects_isolated_peak_and_trough():
    # 5 bars EACH SIDE (11-bar window): index 10 is a clean local max in
    # highs (needs indices 5-15 clear on both sides), index 25 a clean
    # local min in lows (needs indices 20-30 clear), spaced far enough
    # apart that their ±5 windows never overlap.
    n = 35
    highs = [10] * n
    lows = [5] * n
    highs[10] = 20
    lows[25] = 1
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    df = _ohlc("E1", highs, lows, closes)
    frac = fractals(df)
    assert frac.loc[10, "up_fractal"]
    assert not frac["up_fractal"].drop(index=10).any()
    assert frac.loc[25, "down_fractal"]
    assert not frac["down_fractal"].drop(index=25).any()


def test_fractal_tie_against_neighbor_does_not_fire():
    # indices 8 and 9 tie for the highest high, both within each other's
    # ±5 window -> neither should fire (strict inequality required)
    n = 20
    highs = [10] * n
    lows = [5] * n
    highs[8] = 20
    highs[9] = 20
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    df = _ohlc("E1", highs, lows, closes)
    frac = fractals(df)
    assert not frac.loc[8, "up_fractal"]
    assert not frac.loc[9, "up_fractal"]


def test_swing_picks_most_recent_high_not_the_highest_and_lowest_low_in_window():
    # Flat baseline (H=100, L=98). An EARLIER, HIGHER peak (idx10, high=110)
    # must be ignored in favor of a LATER, LOWER peak (idx20, high=105) --
    # "most recent", not "most extreme" (unlike a generic zigzag). Two
    # candidate troughs precede the chosen high: idx5 (low=95) and idx15
    # (low=90, DEEPER) -- the deeper one must win regardless of proximity.
    n = 30
    highs = [100.0] * n
    lows = [98.0] * n
    lows[5] = 95.0
    highs[10] = 110.0
    lows[15] = 90.0
    highs[20] = 105.0
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    df = _ohlc("E1", highs, lows, closes)

    result = most_recent_confirmed_swing(df, as_of_date=df["trade_date"].iloc[-1])
    assert len(result) == 1
    row = result.iloc[0]
    assert row["swing_high_price"] == pytest.approx(105.0)   # the MORE RECENT peak, not the higher one
    assert row["swing_low_price"] == pytest.approx(90.0)     # the LOWEST trough in the window, not the nearest one


def test_swing_excludes_lows_outside_the_lookback_window():
    # Spaced for the 11-bar (±5) fractal window: trough1 (deep, index10) is
    # far enough from trough2 (shallow, index25) and the swing high
    # (index28) that no two fractal windows overlap; a short lookback_days=3
    # window then only reaches back to index25, excluding trough1 entirely.
    n = 40
    highs = [100.0] * n
    lows = [98.0] * n
    lows[10] = 80.0    # deep trough, will fall OUTSIDE the short lookback window
    lows[25] = 95.0    # shallower trough, INSIDE the window
    highs[28] = 110.0  # swing high
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    df = _ohlc("E1", highs, lows, closes)

    result = most_recent_confirmed_swing(df, as_of_date=df["trade_date"].iloc[-1], lookback_days=3)
    assert len(result) == 1
    # window is idx[25,26,27] only -- idx10's deeper low must be excluded
    assert result.iloc[0]["swing_low_price"] == pytest.approx(95.0)


def test_swing_respects_fractal_confirmation_lag_via_as_of_date():
    # wing=5 -> confirming bar for a fractal at idx15 is idx20
    n = 30
    highs = [100.0] * n
    lows = [98.0] * n
    lows[5] = 90.0
    highs[15] = 110.0  # confirming bar is idx20 (wing=5)
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    df = _ohlc("E1", highs, lows, closes)

    # as_of idx19's date: idx15's confirming bar (idx20) hasn't happened yet -> no usable swing high
    not_yet = most_recent_confirmed_swing(df, as_of_date=df["trade_date"].iloc[19])
    assert not_yet.empty

    # as_of the last date: idx20 has happened -> the swing is now usable
    now_confirmed = most_recent_confirmed_swing(df, as_of_date=df["trade_date"].iloc[-1])
    assert len(now_confirmed) == 1
    assert now_confirmed.iloc[0]["swing_high_price"] == pytest.approx(110.0)


def test_swing_2xatr_filter_fails_on_small_move_passes_on_large_move():
    # peaks placed at idx20 (well past ATR(14)'s seed point at idx13) so
    # atr_at_swing_high is a real, non-NaN number in both cases -- a peak
    # too close to the start would leave ATR undefined and make
    # passes_filter False for the wrong reason (no ATR, not a small move).
    n = 30
    highs = [91.0] * n
    lows = [89.0] * n
    lows[5] = 88.5      # shallow trough
    highs[20] = 91.1    # shallow peak -> move = 2.6, small
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    small_df = _ohlc("E1", highs, lows, closes)
    small_result = most_recent_confirmed_swing(small_df, as_of_date=small_df["trade_date"].iloc[-1], atr_multiple=2.0)
    assert len(small_result) == 1
    assert pd.notna(small_result.iloc[0]["atr_at_swing_high"])
    assert not bool(small_result.iloc[0]["passes_filter"])

    highs2 = [91.0] * n
    lows2 = [89.0] * n
    lows2[5] = 88.5
    highs2[20] = 150.0  # deep peak -> move = 61.5, unambiguously large
    closes2 = [(h + l) / 2 for h, l in zip(highs2, lows2)]
    large_df = _ohlc("E1", highs2, lows2, closes2)
    large_result = most_recent_confirmed_swing(large_df, as_of_date=large_df["trade_date"].iloc[-1], atr_multiple=2.0)
    assert len(large_result) == 1 and bool(large_result.iloc[0]["passes_filter"])


def test_swing_empty_when_no_down_fractal_precedes_the_high():
    # n=25 so index15 actually falls within range(wing, n-wing)=range(5,20)
    # and is genuinely evaluated as a fractal (a smaller n would leave it
    # outside the valid window entirely, making this test pass for the
    # wrong reason -- the peak never being recognized at all, not "no
    # down-fractal precedes it").
    n = 25
    highs = [100.0] * n
    lows = [98.0] * n
    highs[15] = 110.0  # a swing high with no preceding down-fractal at all
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    df = _ohlc("E1", highs, lows, closes)
    frac = fractals(df)
    assert frac.loc[15, "up_fractal"]  # confirm the peak IS recognized, so the empty result below is meaningful
    result = most_recent_confirmed_swing(df, as_of_date=df["trade_date"].iloc[-1])
    assert result.empty


def test_golden_zone_arithmetic():
    zone_low, zone_high = golden_zone(swing_low_price=100.0, swing_high_price=200.0)
    # range = 100; 61.8% retracement = 200 - 61.8 = 138.2; 50% retracement = 150.0
    assert zone_low == pytest.approx(138.2)
    assert zone_high == pytest.approx(150.0)
    assert zone_low < zone_high
