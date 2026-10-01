"""Daily-side rules for the Fibonacci/ORB intraday study: Alligator uptrend
filter, fractal swings, ATR(14), the 2xATR minimum-move filter, and
the 50-61.8% golden retracement zone. All computed on entity-adjusted daily
OHLC (src/fibo/daily_ohlc.py) -- never raw, for the same reason every other
price-level computation in this project uses adjusted prices: an unadjusted
split would fabricate a fake gap/range on the ex-date with nothing to do
with the actual price action.

FROZEN, per PREREGISTRATION_FIBO.md (the user's own exact spec, not this
module's interpretation):

- Alligator source price: median price (high+low)/2, the original Williams
  convention, not close.
- Alligator lines: SMMA(13) shifted forward 8 bars (jaw), SMMA(8) shifted
  forward 5 bars (teeth), SMMA(5) shifted forward 3 bars (lips).
- "Uptrend" = lips > teeth > jaw (fanned bullish) AND close above ALL
  THREE lines. Implemented as `close > lips` alone: since the fanned
  condition already forces lips to be the highest of the three, close >
  lips is mathematically identical to close being above all three -- not
  a looser stand-in for the spec's wording, the same condition.
- ATR: Wilder's original smoothing (the same recursive form the RSI/ADX
  papers use), period 14 -- not a simple rolling mean of true range.
- Swing construction (`most_recent_confirmed_swing`): the swing HIGH is
  the most recent confirmed up-fractal; the swing LOW is the lowest
  confirmed down-fractal in the 60 trading days strictly before it. This
  is NOT a generic alternating zigzag pairing -- a lower high or an
  intervening down-fractal that isn't the lowest one in the window is
  simply not used. 2xATR(14), evaluated at the swing high's own date, is
  the pass/fail gate on that one pair.
- Fractal window: 5 BARS EACH SIDE (an 11-bar window, `FRACTAL_WING = 5`),
  not the standard 2-each-side Williams fractal -- CORRECTED 2026-09-28,
  before any intraday data was fetched, per the user's own clarification
  that "5-bar fractal each side" meant five bars on each side (a wider
  window meant to capture only significant reversals), not a 5-bar-total
  window. This is a spec clarification of ambiguous wording, not a
  post-hoc tuning change -- recorded here and in PREREGISTRATION_FIBO.md's
  amendment note for exactly that reason.
- Fractal confirmation lag: a fractal at index i is only knowable once its
  5th bar after i (i.e. bar i+FRACTAL_WING) exists -- 5 bars, matching the
  wider window above. `fractals()` itself returns the raw, un-lagged flag
  (needed for retrospective hand-verification); every point-in-time
  CONSUMER of a fractal (`most_recent_confirmed_swing`) enforces the
  5-bar confirmation lag explicitly via its own `as_of_date` argument, so
  a fractal cannot be used as a live signal before its confirming bar has
  actually happened.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ALLIGATOR_JAW_PERIOD, ALLIGATOR_JAW_SHIFT = 13, 8
ALLIGATOR_TEETH_PERIOD, ALLIGATOR_TEETH_SHIFT = 8, 5
ALLIGATOR_LIPS_PERIOD, ALLIGATOR_LIPS_SHIFT = 5, 3
ATR_PERIOD = 14
FRACTAL_WING = 5  # 5 bars EACH side of the center bar -> an 11-bar window (corrected 2026-09-28, see module docstring)
ATR_MULTIPLE_MIN_MOVE = 2.0
GOLDEN_ZONE_LO, GOLDEN_ZONE_HI = 0.5, 0.618


def _smma(series: pd.Series, period: int) -> pd.Series:
    """Wilder/Alligator smoothed moving average: seeded with a plain SMA of
    the first `period` values, then recursively
    smma[i] = (smma[i-1]*(period-1) + x[i]) / period. NaN before the seed
    point (not backfilled)."""
    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) < period:
        return pd.Series(out, index=series.index)
    seed = np.nanmean(values[:period])
    out[period - 1] = seed
    for i in range(period, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return pd.Series(out, index=series.index)


def _per_entity(df: pd.DataFrame, fn) -> pd.DataFrame:
    """Apply a single-entity function independently per entity_id, sorted by
    trade_date, then reassemble -- every indicator here is entity-local
    (must never smooth across a boundary between two different companies)."""
    parts = []
    for entity_id, g in df.sort_values(["entity_id", "trade_date"]).groupby("entity_id", sort=False):
        parts.append(fn(g.reset_index(drop=True)))
    return pd.concat(parts, ignore_index=True) if parts else fn(df.iloc[0:0])


def true_range(g: pd.DataFrame) -> pd.Series:
    prev_close = g["adjusted_close"].shift(1)
    return pd.concat([
        g["adjusted_high"] - g["adjusted_low"],
        (g["adjusted_high"] - prev_close).abs(),
        (g["adjusted_low"] - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(panel: pd.DataFrame, period: int = ATR_PERIOD) -> pd.DataFrame:
    """[entity_id, trade_date, atr] -- Wilder's ATR, one series per entity."""
    def _one(g: pd.DataFrame) -> pd.DataFrame:
        tr = true_range(g)
        g = g.copy()
        g["atr"] = _smma(tr, period)
        return g[["entity_id", "trade_date", "atr"]]
    return _per_entity(panel, _one)


def alligator(panel: pd.DataFrame) -> pd.DataFrame:
    """[entity_id, trade_date, jaw, teeth, lips] -- each SMMA computed on
    median price (H+L)/2, then shifted forward by its own display offset."""
    def _one(g: pd.DataFrame) -> pd.DataFrame:
        median_price = (g["adjusted_high"] + g["adjusted_low"]) / 2.0
        g = g.copy()
        g["jaw"] = _smma(median_price, ALLIGATOR_JAW_PERIOD).shift(ALLIGATOR_JAW_SHIFT)
        g["teeth"] = _smma(median_price, ALLIGATOR_TEETH_PERIOD).shift(ALLIGATOR_TEETH_SHIFT)
        g["lips"] = _smma(median_price, ALLIGATOR_LIPS_PERIOD).shift(ALLIGATOR_LIPS_SHIFT)
        return g[["entity_id", "trade_date", "jaw", "teeth", "lips"]]
    return _per_entity(panel, _one)


def alligator_uptrend(panel: pd.DataFrame, alligator_df: pd.DataFrame) -> pd.DataFrame:
    """[entity_id, trade_date, uptrend] -- lips > teeth > jaw (fanned
    bullish) AND close > lips (price trading above the whole fan)."""
    merged = panel[["entity_id", "trade_date", "adjusted_close"]].merge(
        alligator_df, on=["entity_id", "trade_date"], how="inner")
    fanned = (merged["lips"] > merged["teeth"]) & (merged["teeth"] > merged["jaw"])
    above = merged["adjusted_close"] > merged["lips"]
    merged["uptrend"] = fanned & above
    return merged[["entity_id", "trade_date", "uptrend"]]


def fractals(panel: pd.DataFrame, wing: int = FRACTAL_WING) -> pd.DataFrame:
    """[entity_id, trade_date, up_fractal, down_fractal] -- an 11-bar
    (wing=5, i.e. 5 bars EACH side) fractal: bar i's high (low) is
    STRICTLY the max (min) of the `wing` bars on each side. A tie against
    any neighbor means no fractal at i (simplification, stated rather than
    silently broken by an arbitrary tie-break). NOT confirmation-lag-
    adjusted -- see module docstring."""
    def _one(g: pd.DataFrame) -> pd.DataFrame:
        n = len(g)
        up = np.zeros(n, dtype=bool)
        down = np.zeros(n, dtype=bool)
        highs = g["adjusted_high"].to_numpy()
        lows = g["adjusted_low"].to_numpy()
        for i in range(wing, n - wing):
            window_h = highs[i - wing:i + wing + 1]
            window_l = lows[i - wing:i + wing + 1]
            if highs[i] == window_h.max() and (highs[i] > np.delete(window_h, wing)).all():
                up[i] = True
            if lows[i] == window_l.min() and (lows[i] < np.delete(window_l, wing)).all():
                down[i] = True
        g = g.copy()
        g["up_fractal"] = up
        g["down_fractal"] = down
        return g[["entity_id", "trade_date", "up_fractal", "down_fractal"]]
    return _per_entity(panel, _one)


SWING_LOOKBACK_DAYS = 60  # trading days, per the frozen rule (PREREGISTRATION_FIBO.md)


def most_recent_confirmed_swing(
    panel: pd.DataFrame, as_of_date, lookback_days: int = SWING_LOOKBACK_DAYS,
    atr_multiple: float = ATR_MULTIPLE_MIN_MOVE, wing: int = FRACTAL_WING,
) -> pd.DataFrame:
    """The frozen rule's EXACT swing construction (PREREGISTRATION_FIBO.md
    Section 3b), one row per entity that has one: the swing HIGH is the
    MOST RECENT confirmed up-fractal at/before `as_of_date`; the swing LOW
    is the LOWEST confirmed down-fractal strictly BEFORE the swing high's
    own date, within `lookback_days` TRADING DAYS preceding it (a row-count
    lookback over that entity's own trading calendar, not a calendar-day
    window). No swing high, or no down-fractal at all in that window, means
    no swing for this entity as of this date -- returned as no row, not a
    NaN row.

    CONFIRMED, point-in-time: a fractal centered at row i is only usable
    once its confirming bar (i + wing) actually exists AND that confirming
    bar's own trade_date is <= as_of_date -- a fractal whose second
    confirming bar hasn't happened yet by as_of_date cannot be used as a
    live signal input. This makes the function safe to call with
    as_of_date strictly less than the panel's last date (e.g. during a
    backtest that walks forward day by day over a panel computed once).

    2xATR FILTER: applied to this specific (low, high) pair using ATR(14)
    AS OF THE SWING HIGH (the signal date) -- an explicit choice, stated
    because "ATR(14)" alone doesn't say which date's ATR when the leg spans
    many days; using the swing high's own ATR (rather than the swing low's,
    or an average) keeps the filter anchored to the same date the setup
    itself is evaluated on.

    [entity_id, swing_high_date, swing_high_price, swing_low_date,
    swing_low_price, move, atr_at_swing_high, passes_filter]."""
    frac = fractals(panel)
    atr_df = atr(panel)
    as_of_ts = pd.Timestamp(as_of_date)

    rows = []
    for entity_id, g in panel.sort_values(["entity_id", "trade_date"]).groupby("entity_id", sort=False):
        g = g.reset_index(drop=True)
        f = frac[frac["entity_id"] == entity_id].reset_index(drop=True)
        a = atr_df[atr_df["entity_id"] == entity_id].reset_index(drop=True)
        n = len(g)
        dates = g["trade_date"]
        highs = g["adjusted_high"].to_numpy()
        lows = g["adjusted_low"].to_numpy()
        atrs = a["atr"].to_numpy()
        up = f["up_fractal"].to_numpy()
        down = f["down_fractal"].to_numpy()

        def confirmed(i: int) -> bool:
            confirm_idx = i + wing
            return confirm_idx < n and dates.iloc[confirm_idx] <= as_of_ts

        swing_high_idx = None
        for i in range(n - 1, -1, -1):
            if dates.iloc[i] > as_of_ts:
                continue
            if up[i] and confirmed(i):
                swing_high_idx = i
                break
        if swing_high_idx is None:
            continue

        window_start = max(0, swing_high_idx - lookback_days)
        swing_low_idx = None
        for j in range(window_start, swing_high_idx):
            if down[j] and confirmed(j) and (swing_low_idx is None or lows[j] < lows[swing_low_idx]):
                swing_low_idx = j
        if swing_low_idx is None:
            continue

        move = highs[swing_high_idx] - lows[swing_low_idx]
        atr_at_swing_high = atrs[swing_high_idx]
        passes = bool(pd.notna(atr_at_swing_high) and move >= atr_multiple * atr_at_swing_high)
        rows.append({
            "entity_id": entity_id,
            "swing_high_date": dates.iloc[swing_high_idx], "swing_high_price": highs[swing_high_idx],
            "swing_low_date": dates.iloc[swing_low_idx], "swing_low_price": lows[swing_low_idx],
            "move": move, "atr_at_swing_high": atr_at_swing_high, "passes_filter": passes,
        })
    return pd.DataFrame(rows, columns=[
        "entity_id", "swing_high_date", "swing_high_price", "swing_low_date", "swing_low_price",
        "move", "atr_at_swing_high", "passes_filter",
    ])


def golden_zone(swing_low_price: float, swing_high_price: float) -> tuple[float, float]:
    """(zone_low, zone_high): the 50%-61.8% retracement band measured back
    from the swing high toward the swing low. zone_low is the DEEPER
    (61.8%) retracement, zone_high the SHALLOWER (50%) one -- i.e. the zone
    is [high - 0.618*range, high - 0.5*range]."""
    rng = swing_high_price - swing_low_price
    zone_low = swing_high_price - GOLDEN_ZONE_HI * rng
    zone_high = swing_high_price - GOLDEN_ZONE_LO * rng
    return zone_low, zone_high
