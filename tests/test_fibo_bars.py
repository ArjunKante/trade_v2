"""Regression tests for src/fibo/bars.py's 1-min -> 15-min and
1-min -> daily aggregation, on hand-computable synthetic bars."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.bars import aggregate_to_15min, aggregate_to_daily


def _minute_bars(entity_id, trade_date, start, n_minutes, o, h, l, c, v):
    """Build n_minutes of 1-min bars, one row per minute starting at `start`
    (e.g. '09:15'), with per-bar OHLCV lists of length n_minutes."""
    ts = pd.date_range(f"{trade_date} {start}", periods=n_minutes, freq="1min")
    return pd.DataFrame({
        "entity_id": entity_id, "trade_date": trade_date, "ts": ts,
        "open": o, "high": h, "low": l, "close": c, "volume": v,
    })


def test_15min_aggregation_matches_hand_calc_on_orb_window():
    # 09:15-09:29 (15 bars) -> exactly ONE ORB bucket
    n = 15
    o = [100 + i * 0.1 for i in range(n)]
    h = [101 + i * 0.1 for i in range(n)]
    l = [99 - i * 0.05 for i in range(n)]
    c = [100.5 + i * 0.1 for i in range(n)]
    v = [1000] * n
    bars = _minute_bars("E1", "2024-01-02", "09:15", n, o, h, l, c, v)

    result = aggregate_to_15min(bars)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["ts"] == pd.Timestamp("2024-01-02 09:15:00")
    assert row["open"] == pytest.approx(o[0])     # first bar's open
    assert row["high"] == pytest.approx(max(h))   # max high across the 15 minutes
    assert row["low"] == pytest.approx(min(l))    # min low across the 15 minutes
    assert row["close"] == pytest.approx(c[-1])   # last bar's close
    assert row["volume"] == sum(v)


def test_15min_aggregation_splits_across_bucket_boundary():
    # 09:15-09:44 (30 minutes) -> two buckets: 09:15 and 09:30
    n = 30
    bars = _minute_bars("E1", "2024-01-02", "09:15", n, [100.0] * n, [101.0] * n, [99.0] * n, [100.0] * n, [10] * n)
    # give the second bucket a distinguishable high so bucket separation is provable
    bars.loc[bars["ts"] == "2024-01-02 09:35:00", "high"] = 150.0
    result = aggregate_to_15min(bars).sort_values("ts").reset_index(drop=True)
    assert len(result) == 2
    assert result.loc[0, "ts"] == pd.Timestamp("2024-01-02 09:15:00")
    assert result.loc[1, "ts"] == pd.Timestamp("2024-01-02 09:30:00")
    assert result.loc[0, "high"] == pytest.approx(101.0)   # spike is NOT in the first bucket
    assert result.loc[1, "high"] == pytest.approx(150.0)   # spike IS in the second bucket


def test_daily_aggregation_collapses_full_session_to_one_ohlcv_bar():
    n = 60
    o = [100.0] * n
    h = [100.0] * n
    l = [100.0] * n
    c = [100.0] * n
    o[0] = 95.0    # day's open = first bar's open
    h[30] = 120.0  # day's high
    l[45] = 80.0   # day's low
    c[-1] = 110.0  # day's close = last bar's close
    v = [5] * n
    bars = _minute_bars("E1", "2024-01-02", "09:15", n, o, h, l, c, v)

    daily = aggregate_to_daily(bars)
    assert len(daily) == 1
    row = daily.iloc[0]
    assert row["open"] == pytest.approx(95.0)
    assert row["high"] == pytest.approx(120.0)
    assert row["low"] == pytest.approx(80.0)
    assert row["close"] == pytest.approx(110.0)
    assert row["volume"] == 5 * n
