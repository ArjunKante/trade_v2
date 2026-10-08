"""Parses Angel One's getMarketData(mode="FULL", ...) response into one
row per symbol, and computes the quoted spread. Pure functions only --
no network call, no login -- so they're testable against synthetic
response dicts.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QuoteRow:
    timestamp_ist: str
    symbol: str
    best_bid: float | None
    best_ask: float | None
    bid_qty: int | None
    ask_qty: int | None
    ltp: float | None
    spread_rupees: float | None
    spread_bps: float | None
    stock_move_pct: float | None
    nifty_move_pct: float | None
    trading_day_status: str

    def as_csv_row(self) -> list:
        return [self.timestamp_ist, self.symbol, self.best_bid, self.best_ask,
                self.bid_qty, self.ask_qty, self.ltp, self.spread_rupees, self.spread_bps,
                self.stock_move_pct, self.nifty_move_pct, self.trading_day_status]


CSV_HEADER = ["timestamp_ist", "symbol", "best_bid", "best_ask", "bid_qty",
              "ask_qty", "ltp", "spread_rupees", "spread_bps",
              "stock_move_pct", "nifty_move_pct", "trading_day_status"]


def compute_spread(best_bid: float | None, best_ask: float | None) -> tuple[float | None, float | None]:
    """(spread_rupees, spread_bps), bps against the bid/ask midpoint --
    the same convention used for every manual reading already recorded
    in FIBO_FINDINGS.md Section 5(d) (e.g. HAVELLS 1050.90/1051.50 ->
    0.60 / 1051.20 * 10000 = 5.7bps). None if either side is missing or
    non-positive, or the book is crossed (ask <= bid) -- a quote that
    thin or broken is not a spread worth logging as a number."""
    if best_bid is None or best_ask is None:
        return None, None
    if best_bid <= 0 or best_ask <= 0 or best_ask <= best_bid:
        return None, None
    spread_rupees = best_ask - best_bid
    mid = (best_bid + best_ask) / 2
    spread_bps = spread_rupees / mid * 10000
    return spread_rupees, spread_bps


def compute_move_pct(open_price: float | None, ltp: float | None) -> float | None:
    """Percent move from today's open to the current price. None if
    open is missing or non-positive -- a move computed against a zero
    or absent open is not a number worth logging."""
    if open_price is None or ltp is None or open_price <= 0:
        return None
    return (ltp - open_price) / open_price * 100


def parse_full_quote_row(symbol: str, fetched_row: dict, timestamp_ist: str,
                          nifty_move_pct: float | None, trading_day_status: str) -> QuoteRow:
    """`fetched_row` is one element of getMarketData's
    response['data']['fetched'] list in FULL mode: has 'depth':
    {'buy': [{'price','quantity','orders'}, ...], 'sell': [...]},
    'ltp', and 'open'. Missing/empty depth (e.g. a halted or no-quote
    name) is recorded as None fields, not skipped -- every attempted
    read is auditable. `nifty_move_pct` and `trading_day_status` are
    computed once per snapshot (from the batch's own Nifty-50 row and
    feed timestamps) and stamped onto every symbol's row, so each row is
    self-contained for the calm-vs-volatile summary split."""
    depth = fetched_row.get("depth") or {}
    buy = depth.get("buy") or []
    sell = depth.get("sell") or []

    best_bid = buy[0]["price"] if buy else None
    bid_qty = buy[0]["quantity"] if buy else None
    best_ask = sell[0]["price"] if sell else None
    ask_qty = sell[0]["quantity"] if sell else None
    ltp = fetched_row.get("ltp")

    spread_rupees, spread_bps = compute_spread(best_bid, best_ask)
    stock_move_pct = compute_move_pct(fetched_row.get("open"), ltp)

    return QuoteRow(
        timestamp_ist=timestamp_ist, symbol=symbol,
        best_bid=best_bid, best_ask=best_ask, bid_qty=bid_qty, ask_qty=ask_qty,
        ltp=ltp, spread_rupees=spread_rupees, spread_bps=spread_bps,
        stock_move_pct=stock_move_pct, nifty_move_pct=nifty_move_pct,
        trading_day_status=trading_day_status,
    )
