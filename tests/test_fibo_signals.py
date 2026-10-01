"""Regression tests for src/fibo/signals.py: cross-checks the batch,
one-pass-per-entity computation against src/fibo/indicators.most_recent_confirmed_swing
(the already-tested, one-date-at-a-time reference implementation) on the
same synthetic fixtures used in tests/test_fibo_indicators.py, plus a
confirmation-lag check specific to computing every day at once."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.signals import compute_daily_signals
from fibo.indicators import most_recent_confirmed_swing, alligator, alligator_uptrend


def _ohlc(entity_id, highs, lows, closes):
    n = len(highs)
    dates = pd.date_range("2022-01-03", periods=n, freq="B")
    return pd.DataFrame({
        "entity_id": entity_id, "trade_date": dates,
        "adjusted_open": closes, "adjusted_high": highs, "adjusted_low": lows, "adjusted_close": closes,
        "volume": [1000] * n, "turnover": [c * 1000 for c in closes],
    })


def test_matches_most_recent_confirmed_swing_on_the_known_fixture():
    """Same fixture as test_fibo_indicators.py's
    test_swing_picks_most_recent_high_not_the_highest_and_lowest_low_in_window --
    the batch computation for the LAST date must agree exactly with the
    reference per-call function."""
    n = 30
    highs = [100.0] * n
    lows = [98.0] * n
    lows[5] = 95.0
    highs[10] = 110.0
    lows[15] = 90.0
    highs[20] = 105.0
    df = _ohlc("E1", highs, lows, [(h + l) / 2 for h, l in zip(highs, lows)])

    signals = compute_daily_signals(df)
    last_row = signals.iloc[-1]
    reference = most_recent_confirmed_swing(df, as_of_date=df["trade_date"].iloc[-1])
    ref_row = reference.iloc[0]

    assert last_row["has_swing"] == bool(ref_row["passes_filter"])
    assert last_row["swing_high_price"] == pytest.approx(ref_row["swing_high_price"])
    assert last_row["swing_low_price"] == pytest.approx(ref_row["swing_low_price"])
    assert last_row["swing_high_date"] == ref_row["swing_high_date"]
    assert last_row["swing_low_date"] == ref_row["swing_low_date"]


def test_matches_reference_at_an_earlier_as_of_date_too():
    """Not just the last row -- pick a MIDDLE date and confirm the batch
    row for that date matches a fresh per-call computation with that same
    as_of_date. This is the real point of this module: getting every day
    right, not just the final one."""
    n = 40
    highs = [100.0] * n
    lows = [98.0] * n
    lows[5] = 95.0
    highs[10] = 110.0
    lows[15] = 90.0
    highs[30] = 120.0
    df = _ohlc("E1", highs, lows, [(h + l) / 2 for h, l in zip(highs, lows)])

    signals = compute_daily_signals(df)
    as_of_idx = 25  # after the idx-10 high is confirmed, before the idx-30 high even exists
    as_of_date = df["trade_date"].iloc[as_of_idx]
    row = signals[signals["trade_date"] == as_of_date].iloc[0]

    reference = most_recent_confirmed_swing(df, as_of_date=as_of_date)
    ref_row = reference.iloc[0]
    assert row["swing_high_price"] == pytest.approx(ref_row["swing_high_price"])
    assert row["swing_low_price"] == pytest.approx(ref_row["swing_low_price"])
    assert row["has_swing"] == bool(ref_row["passes_filter"])


def test_no_swing_before_any_fractal_is_confirmed():
    n = 15
    highs = [100.0] * n
    lows = [98.0] * n
    df = _ohlc("E1", highs, lows, [(h + l) / 2 for h, l in zip(highs, lows)])
    signals = compute_daily_signals(df)
    assert not signals["has_swing"].any()
    assert signals["swing_high_date"].isna().all()


def test_uptrend_column_matches_alligator_uptrend_directly():
    n = 60
    prices = 100 + pd.Series(range(n)) * 1.0
    df = _ohlc("UP", (prices + 1).tolist(), (prices - 1).tolist(), prices.tolist())
    signals = compute_daily_signals(df)
    alli = alligator(df)
    trend = alligator_uptrend(df, alli)
    trend_map = dict(zip(trend["trade_date"], trend["uptrend"]))
    for _, row in signals.iterrows():
        assert row["uptrend"] == bool(trend_map[row["trade_date"]])


def test_swing_not_confirmed_early_becomes_available_later_at_the_right_row():
    """A fractal at index h needs row h+wing to exist before it is usable.
    Confirm the batch computation withholds it (has_swing False via
    swing_high_date None) until exactly that row, matching FRACTAL_WING."""
    from fibo.indicators import FRACTAL_WING
    n = 30
    highs = [100.0] * n
    lows = [98.0] * n
    lows[5] = 90.0
    highs[10] = 110.0
    df = _ohlc("E1", highs, lows, [(h + l) / 2 for h, l in zip(highs, lows)])
    signals = compute_daily_signals(df)

    confirm_row = 10 + FRACTAL_WING
    row_before = signals.iloc[confirm_row - 1]
    row_at = signals.iloc[confirm_row]
    assert row_before["swing_high_date"] is None or pd.isna(row_before["swing_high_date"])
    assert row_at["swing_high_price"] == pytest.approx(110.0)
