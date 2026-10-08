"""Parsing and bps-calculation tests against synthetic getMarketData(FULL)
responses -- no network call, no login."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spread_monitor.quotes import compute_move_pct, compute_spread, parse_full_quote_row


def test_compute_spread_normal_book():
    rupees, bps = compute_spread(1050.90, 1051.50)
    assert rupees == 1051.50 - 1050.90
    assert abs(bps - (0.60 / 1051.20 * 10000)) < 1e-9


def test_compute_spread_none_when_bid_missing():
    assert compute_spread(None, 1051.50) == (None, None)


def test_compute_spread_none_when_ask_missing():
    assert compute_spread(1050.90, None) == (None, None)


def test_compute_spread_none_when_crossed_book():
    # ask <= bid should never be treated as a real spread
    assert compute_spread(1051.50, 1050.90) == (None, None)


def test_compute_spread_none_when_non_positive():
    assert compute_spread(0, 10) == (None, None)
    assert compute_spread(-5, 10) == (None, None)


def test_compute_move_pct_normal():
    assert abs(compute_move_pct(100.0, 101.5) - 1.5) < 1e-9
    assert abs(compute_move_pct(100.0, 98.0) - (-2.0)) < 1e-9


def test_compute_move_pct_none_when_open_missing_or_non_positive():
    assert compute_move_pct(None, 101.5) is None
    assert compute_move_pct(0, 101.5) is None
    assert compute_move_pct(-5, 101.5) is None


def test_compute_move_pct_none_when_ltp_missing():
    assert compute_move_pct(100.0, None) is None


def test_parse_full_quote_row_normal():
    fetched_row = {
        "symbolToken": "9819",
        "open": 1050.0,
        "ltp": 1045.8,
        "depth": {
            "buy": [{"price": 1045.8, "quantity": 3, "orders": 1}],
            "sell": [{"price": 1046.2, "quantity": 107, "orders": 10}],
        },
    }
    row = parse_full_quote_row("HAVELLS", fetched_row, "2026-10-05 11:31:00",
                                nifty_move_pct=0.23, trading_day_status="OK")
    assert row.symbol == "HAVELLS"
    assert row.best_bid == 1045.8
    assert row.best_ask == 1046.2
    assert row.bid_qty == 3
    assert row.ask_qty == 107
    assert row.ltp == 1045.8
    assert abs(row.spread_rupees - 0.4) < 1e-6
    assert row.spread_bps is not None and row.spread_bps > 0
    assert abs(row.stock_move_pct - ((1045.8 - 1050.0) / 1050.0 * 100)) < 1e-9
    assert row.nifty_move_pct == 0.23
    assert row.trading_day_status == "OK"


def test_parse_full_quote_row_empty_depth_is_recorded_not_skipped():
    fetched_row = {"symbolToken": "123", "open": 500.0, "ltp": 500.0, "depth": {"buy": [], "sell": []}}
    row = parse_full_quote_row("THIN", fetched_row, "2026-10-05 11:31:00",
                                nifty_move_pct=None, trading_day_status="OK")
    assert row.symbol == "THIN"
    assert row.best_bid is None
    assert row.best_ask is None
    assert row.spread_bps is None
    assert row.ltp == 500.0  # still recorded even though depth was empty
    assert row.nifty_move_pct is None


def test_parse_full_quote_row_missing_depth_key_entirely():
    fetched_row = {"symbolToken": "123", "open": 500.0, "ltp": 500.0}
    row = parse_full_quote_row("NODEPTH", fetched_row, "2026-10-05 11:31:00",
                                nifty_move_pct=None, trading_day_status="OK")
    assert row.best_bid is None and row.best_ask is None and row.spread_bps is None


def test_parse_full_quote_row_carries_unverified_trading_day_status_through():
    fetched_row = {
        "symbolToken": "9819", "open": 1050.0, "ltp": 1045.8,
        "depth": {"buy": [{"price": 1045.8, "quantity": 3}], "sell": [{"price": 1046.2, "quantity": 107}]},
    }
    row = parse_full_quote_row("HAVELLS", fetched_row, "2026-10-05 11:31:00",
                                nifty_move_pct=0.1, trading_day_status="UNVERIFIED_TRADING_DAY")
    assert row.trading_day_status == "UNVERIFIED_TRADING_DAY"


def test_csv_row_shape_matches_header():
    from spread_monitor.quotes import CSV_HEADER
    fetched_row = {
        "symbolToken": "9819", "open": 1050.0, "ltp": 1045.8,
        "depth": {"buy": [{"price": 1045.8, "quantity": 3}], "sell": [{"price": 1046.2, "quantity": 107}]},
    }
    row = parse_full_quote_row("HAVELLS", fetched_row, "2026-10-05 11:31:00",
                                nifty_move_pct=0.1, trading_day_status="OK")
    assert len(row.as_csv_row()) == len(CSV_HEADER)
