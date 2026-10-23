"""Parses Angel One's getMarketData(mode="FULL", ...) response into one
row per option contract, carrying the full 5-level bid/ask book (not
just best bid/ask, unlike src/spread_monitor/quotes.py's equity row --
depth shape itself, not just the top-of-book spread, is exactly what a
retroactive audit could never recover, so this collector keeps all 5
levels this call already provides for free). Pure functions only -- no
network call, no login -- testable against synthetic response dicts.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

N_LEVELS = 5
EXCH_FEED_TIME_FORMAT = "%d-%b-%Y %H:%M:%S"  # Angel's own format, e.g. "19-Oct-2026 16:08:11"


def exch_feed_date(exch_feed_time: str | None) -> dt.date | None:
    """Parses Angel's exchFeedTime into its calendar date, or None if
    missing/unparseable. Used to catch a stale tick served when the
    market is shut on a weekday check_market_hours() cannot detect on its
    own (an NSE holiday -- no holiday calendar exists in this package,
    see spread_monitor.market_hours's own documented gap): on a shut
    market Angel's FULL-mode quote keeps returning the last real tick, so
    the response succeeds and check_market_hours() passes, but the feed's
    own exchFeedTime still carries the date of that last real session,
    not today."""
    if not exch_feed_time:
        return None
    try:
        return dt.datetime.strptime(exch_feed_time, EXCH_FEED_TIME_FORMAT).date()
    except ValueError:
        return None


@dataclass
class DepthRow:
    timestamp_ist: str
    symbol: str
    token: str
    expiry: str
    strike: float
    option_type: str
    bid_prices: list       # length N_LEVELS, None for a missing level
    bid_qtys: list
    ask_prices: list
    ask_qtys: list
    ltp: float | None
    volume: int | None
    oi: float | None
    nifty_spot: float | None
    nifty_spot_ts: str | None

    def as_csv_row(self) -> list:
        row = [self.timestamp_ist, self.symbol, self.token, self.expiry, self.strike, self.option_type]
        for i in range(N_LEVELS):
            row += [self.bid_prices[i], self.bid_qtys[i]]
        for i in range(N_LEVELS):
            row += [self.ask_prices[i], self.ask_qtys[i]]
        row += [self.ltp, self.volume, self.oi, self.nifty_spot, self.nifty_spot_ts]
        return row


def _level_cols(side: str) -> list[str]:
    cols = []
    for i in range(1, N_LEVELS + 1):
        cols += [f"{side}{i}_price", f"{side}{i}_qty"]
    return cols


CSV_HEADER = (
    ["timestamp_ist", "symbol", "token", "expiry", "strike", "option_type"]
    + _level_cols("bid") + _level_cols("ask")
    + ["ltp", "volume", "oi", "nifty_spot", "nifty_spot_ts"]
)


def _pad_levels(levels: list[dict]) -> tuple[list, list]:
    """(prices, qtys), each exactly N_LEVELS long, padded with None for
    any missing level -- a thin book (fewer than 5 real levels) is
    recorded as such, not silently reinterpreted."""
    prices = [lvl.get("price") for lvl in levels[:N_LEVELS]]
    qtys = [lvl.get("quantity") for lvl in levels[:N_LEVELS]]
    while len(prices) < N_LEVELS:
        prices.append(None)
        qtys.append(None)
    return prices, qtys


def parse_full_depth_row(contract, fetched_row: dict, timestamp_ist: str,
                          nifty_spot: float | None, nifty_spot_ts: str | None) -> DepthRow:
    """`contract`: an options_depth.contracts.OptionContract. `fetched_row`:
    one element of getMarketData's response['data']['fetched'] list in
    FULL mode. Missing/empty depth (a halted or no-quote contract) is
    recorded as all-None levels, never skipped -- every attempted read
    is auditable, the same convention spread_monitor.quotes already
    uses for equities."""
    depth = fetched_row.get("depth") or {}
    bid_prices, bid_qtys = _pad_levels(depth.get("buy") or [])
    ask_prices, ask_qtys = _pad_levels(depth.get("sell") or [])

    return DepthRow(
        timestamp_ist=timestamp_ist, symbol=contract.symbol, token=contract.token,
        expiry=contract.expiry, strike=contract.strike, option_type=contract.option_type,
        bid_prices=bid_prices, bid_qtys=bid_qtys, ask_prices=ask_prices, ask_qtys=ask_qtys,
        ltp=fetched_row.get("ltp"), volume=fetched_row.get("tradeVolume"), oi=fetched_row.get("opnInterest"),
        nifty_spot=nifty_spot, nifty_spot_ts=nifty_spot_ts,
    )
