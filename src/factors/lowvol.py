"""Low-volatility factors: trailing realized volatility and beta vs Nifty 50.
Both computed on entity-adjusted daily log returns.

Sign convention, stated explicitly: the low-vol anomaly predicts LOWER
volatility -> HIGHER forward return, i.e. a NEGATIVE rank IC of raw
trailing_vol against forward return is what "the anomaly holds" looks like.
This module reports the raw vol/beta values; sign interpretation happens at
the IC-reporting stage, not baked in here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VOL_WINDOW = 252
BETA_WINDOW = 252

# Same threshold the prior project's gap-aware outlier detector used
# (nsepit.quality.classify_discontinuity, STALE_GAP_DAYS). A pandas
# row-to-row shift() spans however many CALENDAR days actually elapsed
# between two trading rows -- for a name that stopped trading for months
# (suspension, illiquidity, awaiting a corporate restructuring) and then
# resumed, that gap gets silently computed as if it were one ordinary
# trading day's return. Found live: 47 of the panel's 50 most extreme
# "daily" returns had zero corporate action anywhere near them and a
# median 195-day (up to 2,127-day) gap to the prior trading row -- not a
# missing-adjustment bug, a missing-gap-awareness bug, structurally
# different from the corporate-actions/lineage issue and much more
# pervasive (only 3 of those 50 even involved a lineage transition).
STALE_GAP_DAYS = 5


def _log_returns(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    p["_logret"] = np.log(p["adjusted_close"] / p.groupby("entity_id")["adjusted_close"].shift(1))
    prev_date = p.groupby("entity_id")["trade_date"].shift(1)
    gap_days = (p["trade_date"] - prev_date).dt.days
    p.loc[gap_days > STALE_GAP_DAYS, "_logret"] = np.nan  # the return spanning a stale gap is not a real 1-day return
    return p


def compute_trailing_vol(panel: pd.DataFrame, window: int = VOL_WINDOW) -> pd.DataFrame:
    """Annualized trailing realized volatility of daily log returns, per entity."""
    p = _log_returns(panel)
    p["value"] = (
        p.groupby("entity_id")["_logret"]
        .rolling(window, min_periods=window)
        .std()
        .reset_index(level=0, drop=True)
        * np.sqrt(252)
    )
    return p[["entity_id", "trade_date", "value"]]


def compute_beta(panel: pd.DataFrame, index_returns: pd.DataFrame, window: int = BETA_WINDOW) -> pd.DataFrame:
    """Rolling OLS beta of each entity's daily log return against the Nifty
    50 daily log return. index_returns: columns [trade_date, mkt_logret]."""
    p = _log_returns(panel)
    p = p.merge(index_returns, on="trade_date", how="left")

    def _rolling_beta(g: pd.DataFrame) -> pd.Series:
        cov = g["_logret"].rolling(window, min_periods=window).cov(g["mkt_logret"])
        var = g["mkt_logret"].rolling(window, min_periods=window).var()
        return cov / var

    p["value"] = p.groupby("entity_id", group_keys=False).apply(_rolling_beta, include_groups=False)
    return p[["entity_id", "trade_date", "value"]]
