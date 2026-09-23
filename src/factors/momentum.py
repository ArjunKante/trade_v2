"""Momentum factors, Jegadeesh-Titman construction: a lookback return that
SKIPS the most recent month. The skip is not cosmetic -- short-term reversal
(the most recent ~1 month) is a distinct, opposite-signed effect, and
including it contaminates a momentum factor with reversal's opposite sign.

All computation on entity-adjusted close (entity_panel), never raw close --
a raw-price momentum factor across an unadjusted split would show a
~-90%-return "momentum crash" for reasons that have nothing to do with
momentum, exactly the failure mode the lineage+adjustment layers exist to
prevent.

Trading-day approximation: 21 trading days ~= 1 month, 126 ~= 6 months,
252 ~= 12 months. Standard convention, not a project-specific choice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SKIP_DAYS = 21
WINDOW_12M = 252
WINDOW_6M = 126

# Same threshold as factors.lowvol.STALE_GAP_DAYS. A row-based shift() picks
# the price *skip+window rows back*, whatever calendar span that actually
# covers -- for a name with a multi-month trading halt inside that window,
# the "12-month" return might really span 2+ years, or compare against a
# stale pre-halt price with little economic relevance to the current
# 12-month formation period. Measured live: 16.8% of momentum_12_1
# observations have a >5-calendar-day gap somewhere in their 273-row lookback;
# excluding them RAISES IC (0.0714 -> 0.0867) and cleans up the decile
# gradient -- the contaminated 16.8% were diluting the signal with noise,
# the opposite direction from the same bug's effect on trailing_vol (which
# it inflated with a wrong-signed spurious relationship). Same root cause,
# different symptom, because vol chains returns multiplicatively across the
# gap while momentum only compares the two endpoint prices.
STALE_GAP_DAYS = 5


def _is_unexplained_jump_row(p: pd.DataFrame, unexplained_jump_dates: dict | None) -> pd.Series:
    """True on the first row of an entity's series after an unexplained
    lineage-jump boundary (Bug #1 / lineage_jump_guard) -- a hard boundary
    regardless of calendar gap size, since these transitions often have no
    real trading halt at all (the fabricated jump is in the PRICE, not in
    time)."""
    if not unexplained_jump_dates:
        return pd.Series(False, index=p.index)
    flag = pd.Series(False, index=p.index)
    for eid, dates in unexplained_jump_dates.items():
        mask = (p["entity_id"] == eid) & (p["trade_date"].isin(dates))
        flag |= mask
    return flag


def _max_gap_in_window(panel: pd.DataFrame, window: int, unexplained_jump_dates: dict | None = None) -> pd.Series:
    p = panel.sort_values(["entity_id", "trade_date"])
    prev_date = p.groupby("entity_id")["trade_date"].shift(1)
    gap_days = (p["trade_date"] - prev_date).dt.days
    is_gap = (gap_days > STALE_GAP_DAYS) | _is_unexplained_jump_row(p, unexplained_jump_dates)
    is_gap = is_gap.astype(int)
    return is_gap.groupby(p["entity_id"]).rolling(window, min_periods=1).max().reset_index(level=0, drop=True)


def compute_momentum(panel: pd.DataFrame, window: int, skip: int = SKIP_DAYS,
                      unexplained_jump_dates: dict | None = None) -> pd.DataFrame:
    """panel: columns [entity_id, trade_date, adjusted_close], one row per
    entity per trading day it traded. Returns [entity_id, trade_date, value]
    where value = adjusted_close[t-skip] / adjusted_close[t-skip-window] - 1,
    computed per entity via its own trading-day index (not calendar days --
    an entity's t-1 is its own most recent prior trading day, so a name with
    a trading gap doesn't get penalized for missing calendar days it was
    never expected to trade on).

    NaN'd out (not silently computed) whenever a >STALE_GAP_DAYS trading gap
    falls anywhere inside the lookback window -- the return is real, but its
    formation period isn't the intended ~skip+window trading days, and
    measured live it's pure noise relative to the clean-window observations."""
    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    grp = p.groupby("entity_id", group_keys=False)
    p["_far"] = grp["adjusted_close"].shift(skip + window)
    p["_near"] = grp["adjusted_close"].shift(skip)
    p["value"] = p["_near"] / p["_far"] - 1
    p["_gap_in_window"] = _max_gap_in_window(p, skip + window, unexplained_jump_dates)
    p.loc[p["_gap_in_window"] == 1, "value"] = np.nan
    return p[["entity_id", "trade_date", "value"]]


def compute_momentum_12_1(panel: pd.DataFrame, unexplained_jump_dates: dict | None = None) -> pd.DataFrame:
    return compute_momentum(panel, window=WINDOW_12M, skip=SKIP_DAYS, unexplained_jump_dates=unexplained_jump_dates)


def compute_momentum_6_1(panel: pd.DataFrame, unexplained_jump_dates: dict | None = None) -> pd.DataFrame:
    return compute_momentum(panel, window=WINDOW_6M, skip=SKIP_DAYS, unexplained_jump_dates=unexplained_jump_dates)
