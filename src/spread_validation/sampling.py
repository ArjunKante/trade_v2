"""Stratified sample selection for `SPREAD_ESTIMATOR_VALIDATION.md`.
Read-only against the warehouse -- queries real historical price/
turnover data to choose WHICH names to monitor live later; never calls
Angel One or collects a live quote itself.

Deliberately does NOT go through `data_layer.entity_panel`/
`entity_prices_daily` (the pre-holdout-truncated, stale-since-2025-03-18
table most factor/backtest code in this project uses) -- there is no
holdout concern here at all. `FINDINGS.md` Section 7's retirement is
about the MOMENTUM FACTOR's own sealed-test evaluation window; it has
nothing to do with choosing which stocks to point a live spread monitor
at. Using a table frozen 19 months in the past to select TODAY's sample
would be actively wrong for this purpose, not merely over-cautious -- so
this module reads `prices_eod` directly, through the warehouse's own
latest available date, for both the turnover ranking and the volatility
measure.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from factors.lowvol import compute_trailing_vol
from fibo.universe import reconstitute_annually

VOL_LOOKBACK_TRADING_DAYS = 320  # >252 (factors.lowvol.VOL_WINDOW) + buffer for the rolling window's own warmup
BE_MIN_ACTIVE_DAYS = 20  # same threshold confirmed during research: 308 BE symbols clear this in the trailing 3 months
BE_LOOKBACK_DAYS = 95  # ~3 trading months, calendar days (generous, trimmed by actual trading-day count below)


def current_turnover_bands(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """[entity_id, rank, band] for the CURRENT point-in-time universe --
    `fibo.universe.reconstitute_annually`'s own year=latest-available row,
    unchanged, the same canonical turnover-rank source every other
    point-in-time study in this project uses."""
    uni = reconstitute_annually(con, top_n=200)
    year = int(uni["year"].max())
    cur = uni[uni["year"] == year].copy()
    cur["band"] = np.select(
        [cur["rank"] <= 50, cur["rank"] <= 100], ["1-50", "51-100"], default="101-200")
    return cur[["entity_id", "rank", "band"]], year


def latest_price_and_symbol(con: duckdb.DuckDBPyConnection, entity_ids: list[str]) -> pd.DataFrame:
    """[entity_id, symbol, close, trade_date] -- each entity's own most
    recent `prices_eod` row (EQ or BE, whichever series that entity_id's
    own ISIN is actually under), via `isin_lineage`. Raw bhavcopy close,
    unadjusted -- a live monitor compares against TODAY's own raw quote,
    never an entity-adjusted figure."""
    placeholders = ",".join("?" for _ in entity_ids)
    sql = f"""
        WITH ranked AS (
            SELECT l.entity_id, p.symbol, p.close, p.series, p.trade_date,
                   ROW_NUMBER() OVER (PARTITION BY l.entity_id ORDER BY p.trade_date DESC) AS rn
            FROM prices_eod p
            JOIN isin_lineage l ON p.isin = l.isin
            WHERE l.entity_id IN ({placeholders})
        )
        SELECT entity_id, symbol, close, series, trade_date FROM ranked WHERE rn = 1
    """
    df = con.execute(sql, entity_ids).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def current_volatility(con: duckdb.DuckDBPyConnection, entity_ids: list[str]) -> pd.DataFrame:
    """[entity_id, vol] -- each entity's own MOST RECENT trailing-252-day
    annualized volatility (`factors.lowvol.compute_trailing_vol`, reused
    unchanged), computed on a FRESH panel read directly from `prices_eod`
    through the warehouse's own latest date -- not the stale pre-holdout
    `entity_prices_daily` table (see module docstring)."""
    placeholders = ",".join("?" for _ in entity_ids)
    max_date = con.execute("SELECT MAX(trade_date) FROM prices_eod").fetchone()[0]
    start = (pd.Timestamp(max_date) - pd.tseries.offsets.BDay(VOL_LOOKBACK_TRADING_DAYS * 1.6)).date()
    sql = f"""
        SELECT l.entity_id, p.trade_date, p.close * af.factor AS adjusted_close
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        JOIN adjustment_factors af ON af.entity_id = l.entity_id AND af.trade_date = p.trade_date
        WHERE p.series = 'EQ' AND l.entity_id IN ({placeholders}) AND p.trade_date >= ?
    """
    panel = con.execute(sql, entity_ids + [start]).fetchdf()
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])
    vol = compute_trailing_vol(panel)
    latest = vol.sort_values("trade_date").groupby("entity_id").tail(1)
    return latest[["entity_id", "value"]].rename(columns={"value": "vol"})


def select_eq_band_sample(con: duckdb.DuckDBPyConnection, n_per_band: int = 6) -> pd.DataFrame:
    """Within each of the three turnover bands (1-50/51-100/101-200):
    rank eligible band members by trailing volatility; take the 2
    highest-vol and 2 lowest-vol names, then (from the remainder) the
    highest-price and lowest-price name not already selected --
    `n_per_band` total (default 6: 2 high-vol, 2 low-vol, 1 high-price,
    1 low-price), a deterministic rule that guarantees BOTH volatility
    AND price-level extremes are represented in every band, not merely
    incidental to a vol-only or price-only sort."""
    bands, universe_year = current_turnover_bands(con)
    prices = latest_price_and_symbol(con, bands["entity_id"].tolist())
    vols = current_volatility(con, bands["entity_id"].tolist())

    merged = bands.merge(prices, on="entity_id", how="inner").merge(vols, on="entity_id", how="inner")
    merged = merged.dropna(subset=["vol", "close"])

    rows = []
    for band_name, grp in merged.groupby("band"):
        grp = grp.sort_values("vol", ascending=False).reset_index(drop=True)
        n_half = n_per_band // 3  # 2 of 6 go to vol-high, 2 to vol-low, remainder split across price
        high_vol = grp.head(2)
        low_vol = grp.tail(2)
        chosen_ids = set(high_vol["entity_id"]) | set(low_vol["entity_id"])
        remaining = grp[~grp["entity_id"].isin(chosen_ids)]
        n_price_slots = n_per_band - len(chosen_ids)
        price_sorted = remaining.sort_values("close", ascending=False)
        price_picks = pd.concat([price_sorted.head(1), price_sorted.tail(1)]).drop_duplicates("entity_id")
        price_picks = price_picks.head(n_price_slots)

        for _, r in pd.concat([high_vol, low_vol, price_picks]).drop_duplicates("entity_id").iterrows():
            tag = ("high_vol" if r["entity_id"] in set(high_vol["entity_id"])
                   else "low_vol" if r["entity_id"] in set(low_vol["entity_id"])
                   else "price_extreme")
            rows.append({**r.to_dict(), "selection_reason": tag, "universe_year": universe_year})

    return pd.DataFrame(rows)


def select_be_sample(con: duckdb.DuckDBPyConnection, n: int = 6, lookback_days: int = BE_LOOKBACK_DAYS,
                      min_active_days: int = BE_MIN_ACTIVE_DAYS) -> pd.DataFrame:
    """[entity_id, symbol, close, median_turnover, active_days,
    selection_reason] -- `n` BE-series (trade-to-trade) names, spread
    across the ACTIVE BE population's OWN turnover distribution
    (percentile-spaced, not top-N), so the sample is not just the `n`
    most-liquid T2T names. "Active" = at least `min_active_days`
    distinct BE-series trading days in the trailing `lookback_days`
    calendar days."""
    max_date = con.execute("SELECT MAX(trade_date) FROM prices_eod").fetchone()[0]
    start = max_date - dt.timedelta(days=lookback_days)
    sql = """
        SELECT l.entity_id, p.symbol, p.trade_date, p.close, p.turnover
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        WHERE p.series = 'BE' AND p.trade_date >= ? AND p.turnover IS NOT NULL AND p.turnover > 0
    """
    df = con.execute(sql, [start]).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    agg = df.groupby("entity_id").agg(
        active_days=("trade_date", "nunique"),
        median_turnover=("turnover", "median"),
    ).reset_index()
    agg = agg[agg["active_days"] >= min_active_days]

    latest = df.sort_values("trade_date").groupby("entity_id").tail(1)[["entity_id", "symbol", "close"]]
    agg = agg.merge(latest, on="entity_id")

    agg = agg.sort_values("median_turnover").reset_index(drop=True)
    pool_n = len(agg)
    if pool_n == 0:
        return pd.DataFrame(columns=["entity_id", "symbol", "close", "median_turnover", "active_days"])
    # Percentile-spaced indices across the active BE population's own
    # turnover-sorted order -- spans the distribution rather than taking
    # only the most (or least) liquid T2T names.
    percentiles = np.linspace(0.05, 0.95, n)
    idx = sorted(set(min(pool_n - 1, int(round(p * (pool_n - 1)))) for p in percentiles))
    while len(idx) < n and len(idx) < pool_n:
        for i in range(pool_n):
            if i not in idx:
                idx.append(i)
                break
    sel = agg.iloc[sorted(idx)[:n]].copy()
    sel["selection_reason"] = "be_turnover_percentile_spread"
    sel["band"] = "T2T"
    return sel[["entity_id", "symbol", "close", "median_turnover", "active_days", "band", "selection_reason"]]
