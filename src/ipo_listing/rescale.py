"""Corrects a listing-day scale mismatch found live during Phase 1
validation, NOT anticipated in `PREREGISTRATION_IPO.md`: Angel One's
`getCandleData` returns prices adjusted for every corporate action
between the historical date and today, while `prices_eod` (bhavcopy) is
always RAW for that specific historical date -- the same RAW-vs-adjusted
distinction `fibo.scale_probe` exists elsewhere in this project to
resolve (`box_theory.resolution`'s own docstring: "All price arguments
are assumed already converted to day D's RAW rupee scale"). Confirmed
live: Varun Beverages' 2016-11-08 bhavcopy close is 459.50; Angel's
fetched close for the same day is 122.53 -- ratio ~3.75, and BOTH open
and close diverge from bhavcopy by the IDENTICAL percentage (73.33%),
the signature of one constant per-day multiplicative factor (a since-
applied split/bonus), not timing noise or microstructure.

`fibo.scale_probe`'s own day-to-day jump-detection method is not reused
here -- it resolves a scale by comparing consecutive days across a
multi-year continuous timeline, which a single isolated listing day
does not have. This instead computes the scale DIRECTLY from the one
piece of ground truth already in hand: that day's own real bhavcopy
close (`prices_eod`), divided into the fetched close for the same day.
This is simpler and more exact than a jump-probe would be here, not a
weaker substitute for it.

Corrections are appended as revision_seq=2 rows (never UPDATE/DELETE,
same append-only convention as every table in this project) -- the
original as-fetched rows are never destroyed, and `latest_bars_1min_sql`
is the one place that knows to read only the latest revision per
listing, so no caller has to re-derive that query.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

SCALE_TOLERANCE = 0.02  # 2% -- below this, treated as ordinary rounding/microstructure noise, not a real adjustment
CORRECTION_SOURCE = "ANGEL_ONE_SMARTAPI_HISTORICAL_RAW_SCALE_CORRECTED"

# Every downstream reader of bars_1min must use ONLY the latest revision
# per listing -- centralized here once rather than re-derived per caller.
LATEST_BARS_SQL = """
SELECT listing_id, company_name, symbol_used, angel_token, listing_date, ts, open, high, low, close, volume
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY listing_id, ts ORDER BY revision_seq DESC
    ) AS rn
    FROM bars_1min
)
WHERE rn = 1
"""


def compute_and_apply_scale_corrections(
    intraday_con: duckdb.DuckDBPyConnection, warehouse_con: duckdb.DuckDBPyConnection, listings: pd.DataFrame,
) -> pd.DataFrame:
    """For every listing with an 'OK' fetch, derive scale = bhavcopy_close
    / fetched_close (latest revision). If |scale - 1| exceeds
    SCALE_TOLERANCE, append rescaled (open,high,low,close) * scale rows
    at revision_seq=2 for that listing (volume is a share count, never
    rescaled). Returns [listing_id, company_name, scale, corrected,
    reason] for every OK listing -- 'reason' explains why no correction
    was applied when corrected=False (already within tolerance, or no
    bhavcopy row found for that ISIN/date)."""
    ok = intraday_con.execute(
        "SELECT DISTINCT listing_id, listing_date FROM fetch_log WHERE status = 'OK'"
    ).fetchdf()
    isin_by_listing = dict(zip(listings["listing_id"], listings["isin"]))
    company_by_listing = dict(zip(listings["listing_id"], listings["company_name"]))

    rows_report = []
    for _, r in ok.iterrows():
        listing_id, day = int(r["listing_id"]), r["listing_date"]
        isin = isin_by_listing.get(listing_id)
        company = company_by_listing.get(listing_id)
        if pd.isna(isin):
            rows_report.append((listing_id, company, None, False, "no isin resolved for this listing"))
            continue

        bhav = warehouse_con.execute(
            "SELECT close FROM prices_eod WHERE isin = ? AND trade_date = ?", [isin, day]
        ).fetchone()
        if not bhav:
            rows_report.append((listing_id, company, None, False, "no bhavcopy row for this isin/date"))
            continue
        bhav_close = bhav[0]

        latest = intraday_con.execute(
            f"SELECT close, ts FROM ({LATEST_BARS_SQL}) WHERE listing_id = ? ORDER BY ts DESC LIMIT 1",
            [listing_id],
        ).fetchone()
        if not latest:
            rows_report.append((listing_id, company, None, False, "no bars found (unexpected for an OK fetch)"))
            continue
        fetched_close = latest[0]
        if fetched_close == 0:
            rows_report.append((listing_id, company, None, False, "fetched close is zero, cannot compute a scale"))
            continue

        scale = bhav_close / fetched_close
        if abs(scale - 1.0) <= SCALE_TOLERANCE:
            rows_report.append((listing_id, company, scale, False, "within tolerance, no correction needed"))
            continue

        bars = intraday_con.execute(
            f"SELECT * FROM ({LATEST_BARS_SQL}) WHERE listing_id = ?", [listing_id]
        ).fetchdf()
        now = dt.datetime.now()
        corrected = pd.DataFrame({
            "listing_id": bars["listing_id"], "company_name": bars["company_name"],
            "symbol_used": bars["symbol_used"], "angel_token": bars["angel_token"],
            "listing_date": bars["listing_date"], "ts": bars["ts"],
            "open": bars["open"] * scale, "high": bars["high"] * scale,
            "low": bars["low"] * scale, "close": bars["close"] * scale,
            "volume": bars["volume"], "fetched_at": now, "source": CORRECTION_SOURCE, "revision_seq": 2,
        })
        intraday_con.register("corrected_new", corrected)
        intraday_con.execute("INSERT INTO bars_1min SELECT * FROM corrected_new")
        intraday_con.unregister("corrected_new")
        intraday_con.commit()
        rows_report.append((listing_id, company, scale, True, f"corrected by factor {scale:.6f}"))

    return pd.DataFrame(rows_report, columns=["listing_id", "company_name", "scale", "corrected", "reason"])
