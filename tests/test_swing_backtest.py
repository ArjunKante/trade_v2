"""Regression tests for src/swing/backtest.py's trade construction --
the entry/exit alignment and the concurrent-positions sweep are the two
easiest places to get an off-by-one wrong, so both are tested directly
against a hand-computable synthetic panel."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swing.backtest import (
    entry_exit_returns, attach_trades_to_signals, concurrent_positions, trade_stats,
    random_entry_benchmark, coin_flip_benchmark, equity_curve_drawdown,
)


def _panel(entity_id, opens, closes, start="2020-01-01"):
    dates = pd.date_range(start, periods=len(opens), freq="B")
    return pd.DataFrame({"entity_id": entity_id, "trade_date": dates,
                          "adjusted_open": opens, "adjusted_close": closes})


def test_entry_exit_alignment_open_to_open_5_days_forward():
    # signal at row 0 (date d0) -> entry at row 1 (d1's open) -> exit at row 6 (d6's open)
    opens = [100, 110, 111, 112, 113, 114, 121, 130]  # row1=110 (entry), row6=121 (exit)
    closes = opens  # irrelevant to this function
    panel = _panel("E1", opens, closes)
    ee = entry_exit_returns(panel)
    entry_row = panel.iloc[1]
    row = ee[(ee["entity_id"] == "E1") & (ee["trade_date"] == entry_row["trade_date"])]
    assert not row.empty
    expected = 121 / 110 - 1
    assert row["fwd_return"].iloc[0] == pytest.approx(expected)


def test_attach_trades_drops_signal_with_no_next_row():
    opens = [100, 110]
    panel = _panel("E1", opens, opens)
    ee = entry_exit_returns(panel)
    signals = pd.DataFrame({"entity_id": ["E1"], "trade_date": [panel["trade_date"].iloc[-1]]})
    trades = attach_trades_to_signals(signals, panel, ee)
    assert trades.empty  # last row has no next row to enter on


def test_attach_trades_end_to_end_matches_manual_calc():
    opens = [100, 110, 111, 112, 113, 114, 121, 130, 131, 132, 133, 134]
    panel = _panel("E1", opens, opens)
    ee = entry_exit_returns(panel)
    signal_date = panel["trade_date"].iloc[0]
    signals = pd.DataFrame({"entity_id": ["E1"], "trade_date": [signal_date]})
    trades = attach_trades_to_signals(signals, panel, ee)
    assert len(trades) == 1
    assert trades["entry_date"].iloc[0] == panel["trade_date"].iloc[1]
    assert trades["exit_date"].iloc[0] == panel["trade_date"].iloc[6]
    assert trades["gross_return"].iloc[0] == pytest.approx(121 / 110 - 1)


def test_concurrent_positions_sweep():
    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    # two trades: [entry=d0, exit=d5] and [entry=d2, exit=d7] -- overlap on d2..d4
    trades = pd.DataFrame({
        "entity_id": ["A", "B"],
        "entry_date": [dates[0], dates[2]],
        "exit_date": [dates[5], dates[7]],
        "gross_return": [0.01, -0.02],
    })
    conc = concurrent_positions(trades, dates)
    assert conc[dates[0]] == 1   # A opens
    assert conc[dates[1]] == 1   # A still open, B not yet
    assert conc[dates[2]] == 2   # B opens, A still open -- both concurrent
    assert conc[dates[4]] == 2   # both still open (exit is exclusive)
    assert conc[dates[5]] == 1   # A closes at d5's open, B still open
    assert conc[dates[7]] == 0   # B closes at d7's open
    assert conc.max() == 2


def test_trade_stats_win_rate_and_expectancy():
    trades = pd.DataFrame({"gross_return": [0.05, 0.03, -0.02, -0.10],
                            "exit_date": pd.date_range("2020-01-01", periods=4, freq="B")})
    stats = trade_stats(trades, cost_bps=0.0, trades_per_year=252)
    assert stats["n_trades"] == 4
    assert stats["win_rate"] == pytest.approx(0.5)
    assert stats["avg_win"] == pytest.approx((0.05 + 0.03) / 2)
    assert stats["avg_loss"] == pytest.approx((-0.02 - 0.10) / 2)
    assert stats["expectancy"] == pytest.approx((0.05 + 0.03 - 0.02 - 0.10) / 4)


def test_trade_stats_cost_reduces_every_trade_equally():
    trades = pd.DataFrame({"gross_return": [0.05, -0.02], "exit_date": pd.date_range("2020-01-01", periods=2, freq="B")})
    no_cost = trade_stats(trades, cost_bps=0.0, trades_per_year=252)
    with_cost = trade_stats(trades, cost_bps=40.0, trades_per_year=252)  # 40bps = 0.004
    assert with_cost["expectancy"] == pytest.approx(no_cost["expectancy"] - 0.004)


def test_random_entry_benchmark_matches_trade_count_and_stays_within_pool():
    dates = pd.date_range("2020-01-01", periods=3, freq="B")
    strategy_trades = pd.DataFrame({"signal_date": [dates[0], dates[0], dates[1]],
                                     "gross_return": [0.01, 0.02, 0.03]})
    eligible_trades = pd.DataFrame({
        "entity_id": ["A", "B", "C", "D", "A", "B"],
        "signal_date": [dates[0], dates[0], dates[0], dates[0], dates[1], dates[1]],
        "gross_return": [0.10, 0.20, 0.30, 0.40, -0.50, -0.60],
    })
    result = random_entry_benchmark(strategy_trades, eligible_trades, n_seeds=20)
    assert len(result) == 20
    # day0 needs 2 of {0.10,0.20,0.30,0.40}, day1 needs 1 of {-0.50,-0.60} -> n_trades always 3
    assert (result["n_trades"] == 3).all()
    assert result["mean_gross_return"].between(-0.60, 0.40).all()


def test_random_entry_benchmark_is_fast_with_many_seeds():
    import time
    dates = pd.date_range("2020-01-01", periods=200, freq="B")
    strategy_trades = pd.DataFrame({"signal_date": dates[:100], "gross_return": np.random.rand(100)})
    eligible_trades = pd.DataFrame({
        "entity_id": [f"E{i}" for _ in range(200) for i in range(100)],
        "signal_date": [d for d in dates for _ in range(100)],
        "gross_return": np.random.randn(200 * 100) * 0.01,
    })
    start = time.time()
    result = random_entry_benchmark(strategy_trades, eligible_trades, n_seeds=1000)
    elapsed = time.time() - start
    assert len(result) == 1000
    assert elapsed < 15  # regression guard: an earlier version took >8 minutes via a per-seed merge


def test_equity_curve_drawdown_is_interpretable_percentage():
    dates = pd.date_range("2020-01-01", periods=4, freq="B")
    # capital 300,000; trades: +10%, +10%, -50%, +5% (rupee P&L: +30k,+30k,-150k,+15k)
    trades = pd.DataFrame({"gross_return": [0.10, 0.10, -0.50, 0.05], "exit_date": dates})
    result = equity_curve_drawdown(trades, cost_bps=0.0, position_size=300_000, starting_capital=300_000)
    # equity path: 300k -> 330k -> 360k -> 210k -> 225k. Peak before trough = 360k, trough = 210k.
    assert result["max_drawdown_rs"] == pytest.approx(210_000 - 360_000)
    assert result["max_drawdown_pct_of_peak"] == pytest.approx((210_000 - 360_000) / 360_000)
    assert result["ending_equity"] == pytest.approx(225_000)


def test_coin_flip_benchmark_sign_randomization():
    trades = pd.DataFrame({"gross_return": [0.05, 0.05, 0.05, 0.05]})
    result = coin_flip_benchmark(trades, n_seeds=200)
    assert len(result) == 200
    # with enough seeds, both +0.05-dominant and -0.05-dominant means should appear
    assert result["mean_gross_return"].max() > 0
    assert result["mean_gross_return"].min() < 0
