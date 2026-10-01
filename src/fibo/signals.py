"""Daily-side signal precomputation for the Step 5 development backtest.

src/fibo/indicators.most_recent_confirmed_swing answers "what is the
swing, as of THIS ONE date" per call -- correct and already tested, but a
full backtest needs the answer for every trading day at once (thousands of
calls otherwise, each redoing the same fractal/ATR computation). This
module computes the identical point-in-time answer for every day in one
pass per entity: the Alligator uptrend flag and the most-recent-CONFIRMED
swing (same 5-bars-each-side fractal, 60-day lookback, 2xATR filter,
confirmation-lag discipline as indicators.py) as of each day's own close --
never using information from later rows.

CONFIRMATION-LAG CORRECTNESS, the one subtlety worth stating explicitly: a
fractal at row i is only usable once its confirming row (i + wing) exists.
Because we're computing this once per entity for the WHOLE panel (which
extends into the future relative to any given day being evaluated), the
raw `fractals()` output includes fractals flagged using future rows the
strategy could not have seen at the time -- respected here the same way
indicators.most_recent_confirmed_swing respects it per call: a fractal is
only considered "available as of day j" once its own confirming row's
index is <= j. A swing LOW candidate strictly before an already-confirmed
swing HIGH is automatically confirmed too (its own confirming row is
strictly earlier), so it needs no separate as-of check -- the same
reasoning indicators.py's own docstring already states.
"""
from __future__ import annotations

import pandas as pd

from fibo.indicators import (
    fractals, atr as compute_atr, alligator, alligator_uptrend, golden_zone,
    FRACTAL_WING, ATR_MULTIPLE_MIN_MOVE, SWING_LOOKBACK_DAYS,
)

SIGNAL_COLUMNS = [
    "entity_id", "trade_date", "uptrend", "has_swing",
    "swing_high_date", "swing_high_price", "swing_low_date", "swing_low_price",
    "move", "atr_at_swing_high", "zone_low", "zone_high",
]


def compute_daily_signals(
    panel: pd.DataFrame, lookback_days: int = SWING_LOOKBACK_DAYS,
    atr_multiple: float = ATR_MULTIPLE_MIN_MOVE, wing: int = FRACTAL_WING,
) -> pd.DataFrame:
    """panel: ONE entity's daily OHLC (src/fibo/daily_ohlc.py columns),
    sorted by trade_date, covering at least the full range to be signaled
    over (plus whatever history the swing lookback needs before it).

    Returns one row per day: SIGNAL_COLUMNS. `has_swing` is True only when
    a confirmed swing high AND a confirmed swing low before it exist AND
    the pair clears the 2xATR filter -- exactly indicators.py's
    `passes_filter`, renamed here since it is now the single gate for
    whether a golden zone exists at all that day. `zone_low`/`zone_high`
    are populated (in ADJUSTED scale, same as swing_high_price/
    swing_low_price) only when has_swing is True.
    """
    g = panel.sort_values("trade_date").reset_index(drop=True)
    entity_id = g["entity_id"].iloc[0]
    n = len(g)

    frac = fractals(g, wing=wing)
    atr_df = compute_atr(g)
    alli = alligator(g)
    trend_df = alligator_uptrend(g, alli)
    trend_map = dict(zip(trend_df["trade_date"], trend_df["uptrend"]))

    dates = g["trade_date"]
    highs = g["adjusted_high"].to_numpy()
    lows = g["adjusted_low"].to_numpy()
    atrs = atr_df["atr"].to_numpy()
    up = frac["up_fractal"].to_numpy()
    down = frac["down_fractal"].to_numpy()

    # most recent CONFIRMED up-fractal index available as of each row (forward-filled)
    confirmed_at: dict[int, int] = {}
    for i in range(n):
        c = i + wing
        if up[i] and c < n:
            confirmed_at[c] = i
    swing_high_idx_asof = [-1] * n
    last = -1
    for j in range(n):
        if j in confirmed_at:
            last = confirmed_at[j]
        swing_high_idx_asof[j] = last

    # swing low for each DISTINCT swing-high index, computed once
    swing_low_cache: dict[int, int] = {}

    def swing_low_for(h: int) -> int:
        if h in swing_low_cache:
            return swing_low_cache[h]
        window_start = max(0, h - lookback_days)
        best = -1
        for k in range(window_start, h):
            if down[k] and (best == -1 or lows[k] < lows[best]):
                best = k
        swing_low_cache[h] = best
        return best

    rows = []
    for j in range(n):
        trade_date = dates.iloc[j]
        uptrend = bool(trend_map.get(trade_date, False))
        h = swing_high_idx_asof[j]
        if h == -1:
            rows.append(dict(entity_id=entity_id, trade_date=trade_date, uptrend=uptrend, has_swing=False,
                              swing_high_date=None, swing_high_price=None, swing_low_date=None,
                              swing_low_price=None, move=None, atr_at_swing_high=None, zone_low=None, zone_high=None))
            continue
        low_idx = swing_low_for(h)
        if low_idx == -1:
            rows.append(dict(entity_id=entity_id, trade_date=trade_date, uptrend=uptrend, has_swing=False,
                              swing_high_date=dates.iloc[h], swing_high_price=highs[h], swing_low_date=None,
                              swing_low_price=None, move=None, atr_at_swing_high=None, zone_low=None, zone_high=None))
            continue
        move = highs[h] - lows[low_idx]
        atr_h = atrs[h]
        passes = bool(pd.notna(atr_h) and move >= atr_multiple * atr_h)
        zl, zh = golden_zone(lows[low_idx], highs[h]) if passes else (None, None)
        rows.append(dict(
            entity_id=entity_id, trade_date=trade_date, uptrend=uptrend, has_swing=passes,
            swing_high_date=dates.iloc[h], swing_high_price=highs[h],
            swing_low_date=dates.iloc[low_idx], swing_low_price=lows[low_idx],
            move=move, atr_at_swing_high=atr_h, zone_low=zl, zone_high=zh,
        ))

    return pd.DataFrame(rows, columns=SIGNAL_COLUMNS)
