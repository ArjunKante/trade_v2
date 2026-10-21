"""Listing-day bhavcopy cross-check (`PREREGISTRATION_IPO.md` Section 3,
"VALIDATE"): aggregate each listing's fetched 1-minute bars to a single
daily OHLC and compare against that day's own `prices_eod` bhavcopy row
for the same ISIN, using the SAME two functions `fibo.validation`
already built for this exact purpose (`fibo.bars.aggregate_to_daily`,
`fibo.validation.compare_daily_to_bhavcopy`) -- unchanged, read-only
reuse per Section 0. Both are generic over their `entity_id` column
name; `listing_id` is passed in that column here, since this study has
no pre-IPO entity identity of its own (`ipo_listing.listings`).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from fibo.validation import compare_daily_to_bhavcopy
from ipo_listing.rescale import LATEST_BARS_SQL

DEFAULT_TOLERANCE_PCT = 0.1  # same default fibo.validation uses; not re-derived


def validate_against_bhavcopy(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection,
    listings: pd.DataFrame, tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> pd.DataFrame:
    """`listings`: must include [listing_id, isin, listing_date] (the
    `isin` column from `listings.attach_listing_day_isin`). Returns
    `compare_daily_to_bhavcopy`'s own per-(listing_id, trade_date)
    comparison frame, for every listing with at least one fetched bar AND
    a matching bhavcopy row for that ISIN/date."""
    bars = intraday_con.execute(
        f"SELECT listing_id AS entity_id, listing_date AS trade_date, ts, open, high, low, close, volume "
        f"FROM ({LATEST_BARS_SQL})"
    ).fetchdf()
    if bars.empty:
        return pd.DataFrame()

    isin_by_listing = dict(zip(listings["listing_id"], listings["isin"]))
    bhav_rows = []
    for listing_id, isin in isin_by_listing.items():
        if pd.isna(isin):
            continue
        day = listings.loc[listings["listing_id"] == listing_id, "listing_date"].iloc[0]
        row = warehouse_con.execute(
            "SELECT open, high, low, close FROM prices_eod WHERE isin = ? AND trade_date = ?", [isin, day]
        ).fetchone()
        if row:
            bhav_rows.append((listing_id, day, *row))
    bhavcopy_daily = pd.DataFrame(
        bhav_rows, columns=["entity_id", "trade_date", "open", "high", "low", "close"]
    )
    if bhavcopy_daily.empty:
        return pd.DataFrame()

    # bars['trade_date'] comes back from duckdb's fetchdf() as datetime64;
    # bhavcopy_daily['trade_date'] is built from plain python `date` objects
    # (listings.listing_date) -- pandas' merge refuses to join mismatched
    # key dtypes outright (raises) rather than silently coercing, so both
    # sides are normalized to datetime64 here before compare_daily_to_bhavcopy's
    # own merge.
    bars = bars.copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])
    bhavcopy_daily["trade_date"] = pd.to_datetime(bhavcopy_daily["trade_date"])

    return compare_daily_to_bhavcopy(bars, bhavcopy_daily, tolerance_pct=tolerance_pct)
