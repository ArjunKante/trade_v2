"""CLI: records one bid-ask spread reading for every symbol in
config/spread_monitor_symbols.txt, in one pass, appended to
data/spread_logs/spread_log.csv.

Infrastructure only: this script authenticates (data-only, via
src/fibo/auth.login -- the project's one existing, credential-safety-
hardened login path; reused rather than reimplemented so the
_neutralize_sdk_logger fix in that module is not duplicated or
accidentally dropped) and calls getMarketData(mode="FULL", ...), the
quote/depth endpoint. It places no order, computes no signal, and does
not touch any Fibo result.

Usage: python scripts/snapshot_spreads.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fibo.auth import login
from spread_monitor.config import load_symbols
from spread_monitor.market_hours import IST, check_market_hours
from spread_monitor.quotes import compute_move_pct, parse_full_quote_row
from spread_monitor.tokens import resolve_tokens
from spread_monitor.trading_day import verify_trading_day
from spread_monitor.writer import append_rows

NIFTY_50_INDEX_TOKEN = "99926000"  # Angel's NSE instrument-master token for the Nifty 50 index


def main() -> int:
    ok, reason = check_market_hours()
    if not ok:
        print(f"REFUSING TO RUN: {reason}. A quote captured when the market "
              f"is shut is meaningless and will not be logged.")
        return 1

    symbols = load_symbols()
    token_map, missing = resolve_tokens(symbols)
    if missing:
        print(f"WARNING: no Angel instrument-master match for: {', '.join(missing)} "
              f"-- skipping these, recording the rest.")
    if not token_map:
        print("No symbols resolved to a token. Nothing to record.")
        return 1

    result = login()
    if not result.ok:
        print(f"LOGIN FAILED: {result.status}")
        return 1

    all_tokens = list(token_map.values()) + [NIFTY_50_INDEX_TOKEN]
    resp = result.client.getMarketData("FULL", {"NSE": all_tokens})
    if not isinstance(resp, dict) or not resp.get("status"):
        print(f"QUOTE REQUEST FAILED: {resp.get('message') if isinstance(resp, dict) else resp}")
        return 1

    data = resp.get("data") or {}
    fetched = data.get("fetched") or []
    unfetched = data.get("unfetched") or []
    if unfetched:
        print(f"WARNING: {len(unfetched)} token(s) returned unfetched by the API: {unfetched}")

    now_ist = dt.datetime.now(IST)
    timestamp_ist = now_ist.strftime("%Y-%m-%d %H:%M:%S")

    trading_day_status = verify_trading_day(fetched, now_ist)
    if trading_day_status != "OK":
        print(f"WARNING: trading day could not be live-verified ({trading_day_status}) -- "
              f"rows will be recorded with this status rather than dropped silently; "
              f"treat their spreads as suspect until checked against the day's bhavcopy.")

    nifty_row = next((r for r in fetched if str(r.get("symbolToken")) == NIFTY_50_INDEX_TOKEN), None)
    nifty_move_pct = compute_move_pct(nifty_row.get("open"), nifty_row.get("ltp")) if nifty_row else None
    if nifty_move_pct is None:
        print("WARNING: could not compute Nifty's move today (index row missing or incomplete) -- "
              "recording None for nifty_move_pct on every row.")

    token_to_symbol = {str(token): symbol for symbol, token in token_map.items()}

    rows = []
    for item in fetched:
        token_str = str(item.get("symbolToken"))
        if token_str == NIFTY_50_INDEX_TOKEN:
            continue  # the index is an input signal here, not one of the measured symbols
        symbol = token_to_symbol.get(token_str)
        if symbol is None:
            print(f"WARNING: fetched row with unrecognized symbolToken {item.get('symbolToken')!r}, skipping.")
            continue
        rows.append(parse_full_quote_row(symbol, item, timestamp_ist, nifty_move_pct, trading_day_status))

    append_rows(rows)

    print(f"Recorded {len(rows)} reading(s) at {timestamp_ist} IST "
          f"(nifty_move_pct={nifty_move_pct}, trading_day_status={trading_day_status}):")
    for row in rows:
        bps = f"{row.spread_bps:.2f}bps" if row.spread_bps is not None else "N/A"
        move = f"{row.stock_move_pct:+.2f}%" if row.stock_move_pct is not None else "N/A"
        print(f"  {row.symbol:12s} bid={row.best_bid} ask={row.best_ask} ltp={row.ltp} spread={bps} move={move}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
