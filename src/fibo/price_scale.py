"""Converts an entity-adjusted daily price level (golden zone, swing high/
low, ATR distance -- anything computed from src/fibo/daily_ohlc.py's
adjusted columns) into the RAW price scale a specific historical date D
actually traded at.

THE PITFALL THIS MODULE EXISTS FOR: daily prices in this warehouse are
split-adjusted to TODAY's scale (data_layer.adjustment: adjusted(d) =
raw(d) * factor(d), factor(d) folding in every corporate action with
ex_date > d, so factor is smallest for the oldest pre-split dates and 1.0
for the most recent regime). Angel One's INTRADAY bars, by contrast, are
raw prints in whatever scale the exchange was actually quoting on that
specific day -- NOT retroactively re-scaled for a split that happened
later. A golden zone computed from adjusted daily closes is therefore in
"today's scale"; comparing it directly against date D's raw 1-minute bars
is only correct if D postdates every split this entity has ever had. For
any D before a later split, the comparison is silently wrong by exactly
that split's ratio -- the zone would be misplaced by ~2x, ~5x, ~10x,
whatever the ratio was, with no error raised anywhere, because both
numbers "look like a price" and nothing about the shapes mismatches.

THE FIX: raw(D) = adjusted_level / factor(D) -- the same relationship
data_layer.adjustment defines, inverted, read off the ALREADY-MATERIALIZED
adjustment_factors table for D specifically (never recomputed here; this
module is a read-only consumer of that layer, same convention as
data_layer.adjustment.read_adjusted_prices).
"""
from __future__ import annotations

import datetime as dt

import duckdb


def get_adjustment_factor(con: duckdb.DuckDBPyConnection, entity_id: str, trade_date: dt.date) -> float:
    """The materialized factor(D) for this entity, or raise -- there is no
    sane fallback for a missing factor (it would mean either D wasn't a
    real trading day for this entity, or adjustment_factors hasn't been
    materialized for it yet; silently defaulting to 1.0 is exactly the
    prior project's factor=1.0-everywhere bug this project's own test
    suite (test_adjustment_factors.py) exists to catch)."""
    row = con.execute(
        "SELECT factor FROM adjustment_factors WHERE entity_id = ? AND trade_date = ?",
        [entity_id, trade_date],
    ).fetchone()
    if row is None:
        raise ValueError(
            f"no materialized adjustment factor for entity_id={entity_id!r} on {trade_date} -- "
            "either not a real trading day for this entity, or adjustment_factors is stale/unmaterialized"
        )
    return row[0]


def to_raw_scale(adjusted_price: float, factor: float) -> float:
    """adjusted_price = raw_price * factor  =>  raw_price = adjusted_price / factor."""
    return adjusted_price / factor


def zone_to_raw_scale(
    con: duckdb.DuckDBPyConnection, entity_id: str, trade_date: dt.date,
    zone_low_adjusted: float, zone_high_adjusted: float,
) -> tuple[float, float]:
    """Convert a golden-zone (or any adjusted-scale price pair) to trade
    date D's raw scale, in one factor lookup. This is the one function a
    Step-4/5 signal-generation script should call before comparing a
    golden zone against a day's intraday bars -- never compare an adjusted
    zone to raw intraday prices directly."""
    factor = get_adjustment_factor(con, entity_id, trade_date)
    return to_raw_scale(zone_low_adjusted, factor), to_raw_scale(zone_high_adjusted, factor)
