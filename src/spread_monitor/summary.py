"""Reads the append-only spread log and summarizes it per symbol."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .trading_day import OK as TRADING_DAY_OK
from .writer import DEFAULT_LOG_PATH

# A split point for "calm" vs "volatile" has no single correct value --
# this is a stated judgment call, not a measured constant. 1.0% absolute
# Nifty move (open-to-now) is roughly an above-average-but-not-extreme
# day; adjust if the collected readings cluster in a way that makes this
# cutoff uninformative.
VOLATILE_NIFTY_MOVE_PCT_THRESHOLD = 1.0


def load_log(path: Path = DEFAULT_LOG_PATH) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["timestamp_ist"])


def _usable(df: pd.DataFrame) -> pd.DataFrame:
    """Rows whose trading day was live-verified. A row whose day could
    not be confirmed (market.trading_day.UNVERIFIED) is excluded from
    every stat here, never averaged in as if it were a normal reading --
    per instruction, a bad row is worse than a missing one."""
    return df[df["trading_day_status"] == TRADING_DAY_OK]


def summarize_by_symbol(df: pd.DataFrame) -> pd.DataFrame:
    """n readings, median/min/max spread_bps per symbol, among
    trading-day-verified rows with a valid (uncrossed, non-empty) quote."""
    usable = _usable(df)
    valid = usable.dropna(subset=["spread_bps"])
    out = valid.groupby("symbol")["spread_bps"].agg(n="count", median_bps="median",
                                                      min_bps="min", max_bps="max")
    invalid_n = usable.groupby("symbol")["spread_bps"].apply(lambda s: s.isna().sum())
    out["invalid_readings"] = invalid_n.reindex(out.index).fillna(0).astype(int)
    unverified_n = df.groupby("symbol")["trading_day_status"].apply(lambda s: (s != TRADING_DAY_OK).sum())
    out["unverified_trading_day"] = unverified_n.reindex(out.index).fillna(0).astype(int)
    return out.reset_index().sort_values("symbol")


def summarize_by_time_of_day(df: pd.DataFrame) -> pd.DataFrame:
    """Median spread_bps per symbol per hour-of-day bucket (IST)."""
    valid = _usable(df).dropna(subset=["spread_bps"]).copy()
    valid["hour_ist"] = valid["timestamp_ist"].dt.hour
    out = valid.groupby(["symbol", "hour_ist"])["spread_bps"].agg(n="count", median_bps="median")
    return out.reset_index().sort_values(["symbol", "hour_ist"])


def classify_session(nifty_move_pct: float | None, threshold: float = VOLATILE_NIFTY_MOVE_PCT_THRESHOLD) -> str | None:
    if nifty_move_pct is None or pd.isna(nifty_move_pct):
        return None
    return "volatile" if abs(nifty_move_pct) >= threshold else "calm"


def summarize_by_session(df: pd.DataFrame, threshold: float = VOLATILE_NIFTY_MOVE_PCT_THRESHOLD) -> pd.DataFrame:
    """Median/min/max spread_bps per symbol, split by whether that
    snapshot's own Nifty move (open-to-now) was calm or volatile -- the
    whole point of this flag: showing whether the collected readings are
    biased toward quiet markets relative to the 2023-2024 window they
    stand in for."""
    valid = _usable(df).dropna(subset=["spread_bps", "nifty_move_pct"]).copy()
    valid["session"] = valid["nifty_move_pct"].apply(lambda x: classify_session(x, threshold))
    out = valid.groupby(["symbol", "session"])["spread_bps"].agg(n="count", median_bps="median",
                                                                    min_bps="min", max_bps="max")
    return out.reset_index().sort_values(["symbol", "session"])
