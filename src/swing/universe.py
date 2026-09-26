"""Point-in-time candidate universe and the frozen rule's three conditions,
computed at EVERY historical trading date (not just "today") -- this is
what a 5-day-horizon rule needs, unlike the main project's 63-day-rebalance
convention. Every per-date cross-sectional computation here mirrors an
already-tested convention elsewhere in this project (momentum ranking:
factors.momentum + fundamental_snapshot.compute_momentum_universe;
liquidity tercile: fundamental_screener.compute_liquidity_tercile) --
duplicated rather than imported, per this project's own established
convention for factor modules (each self-contained, tested independently).

MECHANISM CORRECTION (recorded per instruction, attributed): the 5-day
return bottom-tercile condition is ranked across the FULL EQ universe, NOT
within the momentum-top-decile-filtered candidate set. Ranking within the
candidate set would select "the least-strong momentum winners," not
"stocks that fell relative to the market" -- a different population, and
one the short-term-reversal mechanism this rule is testing does not
obviously apply to. The correct order is: rank bottom-tercile-by-5-day-
return across the full universe FIRST, then intersect with the momentum/
liquidity candidate set -- implemented that way below.

INTERPRETATION, stated because the instruction did not fully disambiguate
it: "full liquid EQ universe" is read here as every EQ-series entity with
a valid (gap-guarded) 5-day return on that date -- no additional liquidity-
tercile restriction on the RANKING population itself (that restriction is
applied separately, only to the final candidate set, per the frozen rule).
If a narrower ranking population (e.g. high+mid tercile only) was intended,
this is a one-line change to make.

KNOWN GAP, flagged rather than silently worked around: the fundamentals
screener (fundamental_screener.py) currently only computes a CURRENT
snapshot verdict, not a historical point-in-time series across 9 years of
quarterly-lagged fundamentals. It is OMITTED from this candidate-count
diagnostic and from the counts below for that reason -- not dropped from
the rule, just not yet historically computable. Building a point-in-time
historical screener is a separate undertaking, not attempted here.

KNOWN SIMPLIFICATION: the volume-ratio's 20-day trailing average does not
apply the STALE_GAP_DAYS guard the way every return computation elsewhere
in this project does. Left as a simplification for this diagnostic;
revisit before the actual Phase 3 backtest treats it as final.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factors.momentum import compute_momentum, WINDOW_12M, SKIP_DAYS

LIQUIDITY_WINDOW_DAYS = 20
VOLUME_RATIO_WINDOW_DAYS = 20
VOLUME_RATIO_THRESHOLD = 1.5
BOTTOM_TERCILE = 1 / 3
TOP_DECILE_CUTOFF = 0.90
NIFTY_SMA_DAYS = 50


def historical_momentum_top_decile(panel: pd.DataFrame, unexplained_jump_dates: dict | None = None) -> pd.DataFrame:
    """[entity_id, trade_date, momentum_12_1, rank, n_that_date, in_top_decile],
    one row per (entity_id, trade_date) with a computable momentum_12_1 --
    ranked independently within each trade_date's own cross-section, same
    convention as fundamental_snapshot.compute_momentum_universe applied to
    every historical date instead of only the current one."""
    mom = compute_momentum(panel, window=WINDOW_12M, skip=SKIP_DAYS, unexplained_jump_dates=unexplained_jump_dates)
    m = mom.dropna(subset=["value"]).rename(columns={"value": "momentum_12_1"}).copy()
    m["rank"] = m.groupby("trade_date")["momentum_12_1"].rank(ascending=False, method="min")
    m["n_that_date"] = m.groupby("trade_date")["momentum_12_1"].transform("count")
    cutoff = m.groupby("trade_date")["momentum_12_1"].transform(lambda s: s.quantile(TOP_DECILE_CUTOFF))
    m["in_top_decile"] = m["momentum_12_1"] >= cutoff
    return m[["entity_id", "trade_date", "momentum_12_1", "rank", "n_that_date", "in_top_decile"]]


def historical_liquidity_tercile(panel: pd.DataFrame) -> pd.DataFrame:
    """[entity_id, trade_date, tercile] -- tercile computed across the FULL
    panel (whole market) at each date, same as
    fundamental_screener.compute_liquidity_tercile, just retained for every
    date instead of collapsed to each entity's latest row."""
    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    p["_liq"] = p.groupby("entity_id")["turnover"].transform(
        lambda s: s.rolling(LIQUIDITY_WINDOW_DAYS, min_periods=LIQUIDITY_WINDOW_DAYS).median())
    p["tercile"] = p.groupby("trade_date")["_liq"].transform(
        lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
        if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index)
    )
    return p[["entity_id", "trade_date", "tercile"]]


def historical_bottom_tercile_5d_return(panel: pd.DataFrame, unexplained_jump_dates: dict | None = None) -> pd.DataFrame:
    """[entity_id, trade_date, ret_5d, bottom_tercile] -- 5-trading-day
    trailing return (compute_momentum with window=5, skip=0 -- gap-guarded
    the same way as every other return in this project), bottom-tercile
    flag computed ACROSS THE FULL EQ UNIVERSE per date (see module
    docstring's mechanism-correction note)."""
    ret5 = compute_momentum(panel, window=5, skip=0, unexplained_jump_dates=unexplained_jump_dates)
    r = ret5.dropna(subset=["value"]).rename(columns={"value": "ret_5d"}).copy()
    cutoff = r.groupby("trade_date")["ret_5d"].transform(lambda s: s.quantile(BOTTOM_TERCILE))
    r["bottom_tercile"] = r["ret_5d"] <= cutoff
    return r[["entity_id", "trade_date", "ret_5d", "bottom_tercile"]]


def historical_volume_ratio(panel: pd.DataFrame) -> pd.DataFrame:
    """[entity_id, trade_date, vol_ratio, high_volume] --
    volume[t] / mean(volume[t-20..t-1]), the signal date excluded from its
    own trailing average."""
    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    grp = p.groupby("entity_id", group_keys=False)
    p["_avg20"] = grp["volume"].transform(
        lambda s: s.shift(1).rolling(VOLUME_RATIO_WINDOW_DAYS, min_periods=VOLUME_RATIO_WINDOW_DAYS).mean())
    p["vol_ratio"] = p["volume"] / p["_avg20"]
    p["high_volume"] = p["vol_ratio"] > VOLUME_RATIO_THRESHOLD
    return p[["entity_id", "trade_date", "vol_ratio", "high_volume"]]


def nifty_regime(con, before) -> pd.DataFrame:
    """[trade_date, nifty_close, nifty_sma50, regime_on] -- NIFTY50 close
    above its own trailing 50-trading-day simple moving average, evaluated
    as of that date's close (no lookahead: the SMA at date t uses only
    closes up to and including t)."""
    df = con.execute(
        "SELECT trade_date, close FROM index_eod WHERE index_name = 'NIFTY50' AND trade_date < ? ORDER BY trade_date",
        [before],
    ).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["nifty_sma50"] = df["close"].rolling(NIFTY_SMA_DAYS, min_periods=NIFTY_SMA_DAYS).mean()
    df["regime_on"] = df["close"] > df["nifty_sma50"]
    return df.rename(columns={"close": "nifty_close"})[["trade_date", "nifty_close", "nifty_sma50", "regime_on"]]
