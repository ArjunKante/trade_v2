"""Tests for summary.py: unverified-trading-day rows are excluded from
every stat (never averaged in), and the calm/volatile session split."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spread_monitor.summary import classify_session, summarize_by_session, summarize_by_symbol

COLUMNS = ["timestamp_ist", "symbol", "best_bid", "best_ask", "bid_qty", "ask_qty",
           "ltp", "spread_rupees", "spread_bps", "stock_move_pct", "nifty_move_pct",
           "trading_day_status"]


def _row(symbol, spread_bps, nifty_move_pct=0.1, trading_day_status="OK", ts="2026-10-05 11:00:00"):
    return [ts, symbol, 100.0, 100.1, 10, 10, 100.05, 0.1, spread_bps, 0.0, nifty_move_pct, trading_day_status]


def test_classify_session_boundaries():
    assert classify_session(0.5) == "calm"
    assert classify_session(1.0) == "volatile"  # >= threshold is volatile
    assert classify_session(-1.5) == "volatile"
    assert classify_session(None) is None


def test_summarize_by_symbol_excludes_unverified_trading_day_rows():
    df = pd.DataFrame([
        _row("HAVELLS", 5.0, trading_day_status="OK"),
        _row("HAVELLS", 999.0, trading_day_status="UNVERIFIED_TRADING_DAY"),
    ], columns=COLUMNS)
    out = summarize_by_symbol(df)
    row = out[out["symbol"] == "HAVELLS"].iloc[0]
    assert row["n"] == 1
    assert row["median_bps"] == 5.0  # the 999.0 unverified row must not pollute this
    assert row["unverified_trading_day"] == 1


def test_summarize_by_session_splits_calm_vs_volatile():
    df = pd.DataFrame([
        _row("HAVELLS", 4.0, nifty_move_pct=0.2),   # calm
        _row("HAVELLS", 6.0, nifty_move_pct=0.3),   # calm
        _row("HAVELLS", 9.0, nifty_move_pct=1.8),   # volatile
    ], columns=COLUMNS)
    out = summarize_by_session(df)
    calm = out[(out["symbol"] == "HAVELLS") & (out["session"] == "calm")].iloc[0]
    volatile = out[(out["symbol"] == "HAVELLS") & (out["session"] == "volatile")].iloc[0]
    assert calm["n"] == 2
    assert calm["median_bps"] == 5.0
    assert volatile["n"] == 1
    assert volatile["median_bps"] == 9.0


def test_summarize_by_session_excludes_unverified_rows_too():
    df = pd.DataFrame([
        _row("HAVELLS", 4.0, nifty_move_pct=0.2, trading_day_status="OK"),
        _row("HAVELLS", 999.0, nifty_move_pct=0.2, trading_day_status="UNVERIFIED_TRADING_DAY"),
    ], columns=COLUMNS)
    out = summarize_by_session(df)
    calm = out[(out["symbol"] == "HAVELLS") & (out["session"] == "calm")].iloc[0]
    assert calm["n"] == 1
    assert calm["median_bps"] == 4.0
