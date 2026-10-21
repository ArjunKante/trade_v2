"""Orchestrates `ipo_listing.resolution`'s pure entry/exit mechanics
against real archived bars (`ipo_listing.rescale.LATEST_BARS_SQL`, the
scale-corrected, latest-revision view) for the final usable sample --
`fetch_log.status = 'OK'` (the 498-listing sample, Section 3a's 21
unresolved and Section 3's 3 excluded-data-defect listings already
carry a different status and are never selected here).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from ipo_listing.costs import round_trip_cost_rs, net_r, COST_SCENARIOS_BPS
from ipo_listing.resolution import find_entry, resolve_exit

TRADE_COLUMNS = [
    "listing_id", "company_name", "symbol_used", "listing_date", "status",
    "first_open", "first_high", "first_low", "first_close", "is_green",
    "fill_ts", "entry_price", "qty", "stop", "target",
    "exit_outcome", "exit_price", "exit_ts", "time_exit_fallback",
    "pnl_rs", "position_size_rs",
    "net_r_7bps", "net_r_14bps", "net_r_28bps",
]


def load_usable_listings(intraday_con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """[listing_id, company_name, symbol_used, listing_date] for every
    listing with fetch_log.status = 'OK' -- the final 498-listing usable
    sample (21 NO_TOKEN, 3 EXCLUDED_DATA_DEFECT, 30 FETCH_FAILED already
    excluded by this status filter)."""
    return intraday_con.execute(
        """
        SELECT f.listing_id, b.company_name, f.symbol_used, f.listing_date
        FROM fetch_log f
        JOIN (SELECT DISTINCT listing_id, company_name FROM bars_1min) b ON b.listing_id = f.listing_id
        WHERE f.status = 'OK'
        ORDER BY f.listing_date
        """
    ).fetchdf()


def load_day_bars(intraday_con: duckdb.DuckDBPyConnection, listing_id: int) -> pd.DataFrame:
    """One listing's own 1-minute bars (latest revision only -- scale-
    corrected where `ipo_listing.rescale` found a correction needed),
    ts-sorted."""
    from ipo_listing.rescale import LATEST_BARS_SQL
    df = intraday_con.execute(
        f"SELECT ts, open, high, low, close FROM ({LATEST_BARS_SQL}) WHERE listing_id = ? ORDER BY ts",
        [listing_id],
    ).fetchdf()
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def run_one(bars1_day: pd.DataFrame, listing_row: pd.Series, ignore_color: bool = False) -> dict:
    """One listing's full trade-or-skip record, at all three cost
    scenarios. `ignore_color=True` is the SELECTION null's alternate
    rule (`ipo_listing.resolution.find_entry`'s own docstring)."""
    rec = {col: None for col in TRADE_COLUMNS}
    rec.update({
        "listing_id": int(listing_row["listing_id"]), "company_name": listing_row["company_name"],
        "symbol_used": listing_row["symbol_used"], "listing_date": listing_row["listing_date"],
    })

    entry = find_entry(bars1_day, ignore_color=ignore_color)
    rec["status"] = entry["status"]
    if "first_candle" in entry:
        fc = entry["first_candle"]
        rec.update({"first_open": fc["open"], "first_high": fc["high"], "first_low": fc["low"],
                    "first_close": fc["close"], "is_green": entry["is_green"]})

    if entry["status"] != "ENTERED":
        return rec

    rec.update({
        "fill_ts": entry["fill_ts"], "entry_price": entry["entry_price"], "qty": entry["qty"],
        "stop": entry["stop"], "target": entry["target"],
    })

    exit_ = resolve_exit(bars1_day, entry["fill_ts"], entry["entry_price"], entry["stop"], entry["target"])
    rec.update({
        "exit_outcome": exit_["outcome"], "exit_price": exit_["exit_price"], "exit_ts": exit_["exit_ts"],
        "time_exit_fallback": exit_["time_exit_fallback"],
    })

    qty = entry["qty"]
    entry_price = entry["entry_price"]
    pnl_rs = qty * (exit_["exit_price"] - entry_price)
    position_size_rs = qty * entry_price
    rec["pnl_rs"] = pnl_rs
    rec["position_size_rs"] = position_size_rs
    for bps in COST_SCENARIOS_BPS:
        rec[f"net_r_{int(bps)}bps"] = net_r(pnl_rs, position_size_rs, bps)
    return rec


def run_backtest(intraday_con: duckdb.DuckDBPyConnection, listings: pd.DataFrame,
                  ignore_color: bool = False) -> pd.DataFrame:
    """`listings`: [listing_id, company_name, symbol_used, listing_date]
    (typically `load_usable_listings`'s own output, pre-filtered to a
    DEV/TEST window by the caller). One row per listing, trade-or-skip,
    at all three cost scenarios (`TRADE_COLUMNS`)."""
    rows = []
    for _, r in listings.iterrows():
        bars = load_day_bars(intraday_con, int(r["listing_id"]))
        rows.append(run_one(bars, r, ignore_color=ignore_color))
    return pd.DataFrame(rows, columns=TRADE_COLUMNS)
