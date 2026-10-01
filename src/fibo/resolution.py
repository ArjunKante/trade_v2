"""Target computation, fixed-risk position sizing, and stop/target
resolution against 1-minute bars -- the mechanical trade-management core
of the frozen rule (PREREGISTRATION_FIBO.md): stop = ORB low, target =
min(2R, swing high), exit 15:15, Rs 500 fixed risk, same-bar tie = STOP.
"""
from __future__ import annotations

import math

import pandas as pd

FIXED_RISK_RS = 500.0
TARGET_R_MULTIPLE = 2.0


def compute_r(entry_price: float, stop_price: float) -> float:
    """R = entry - stop (a long-only system per the frozen rule: entry
    above the ORB high, stop at the ORB low, so R > 0 by construction for
    any setup that reaches entry)."""
    return entry_price - stop_price


def compute_target(entry_price: float, stop_price: float, swing_high_price: float) -> float:
    """target = min(entry + 2R, swing_high) -- capped at the swing high so
    the target never extrapolates past the level the golden-zone setup was
    itself measured from."""
    r = compute_r(entry_price, stop_price)
    return min(entry_price + TARGET_R_MULTIPLE * r, swing_high_price)


def position_size_shares(entry_price: float, stop_price: float, fixed_risk_rs: float = FIXED_RISK_RS) -> int:
    """Whole shares only (NSE EQ cash-market trades in single-share
    lots -- no lot-size rounding needed, unlike F&O). Floored, never
    rounded up: rounding up would risk more than fixed_risk_rs if stopped
    out, which the fixed-risk design is specifically meant to prevent."""
    r = compute_r(entry_price, stop_price)
    if r <= 0:
        raise ValueError(f"R must be positive (entry {entry_price} must exceed stop {stop_price}), got R={r}")
    return math.floor(fixed_risk_rs / r)


def resolve_trade(bars_1min: pd.DataFrame, entry_ts, stop_price: float, target_price: float, exit_ts) -> dict:
    """bars_1min: ONE entity's ONE day of 1-minute bars, columns
    [ts, open, high, low, close], any order (sorted here). Scans bars with
    entry_ts < ts <= exit_ts (the entry bar itself is excluded -- its
    price action is already priced into the entry fill; monitoring starts
    from the next 1-minute bar).

    Returns {'outcome': 'STOP'|'TARGET'|'TIME_EXIT', 'exit_price': float,
    'exit_ts': Timestamp}.

    SAME-BAR TIE, per instruction: if a single 1-minute bar's range
    touches BOTH the stop and the target (low <= stop_price AND
    high >= target_price), it is resolved as STOP -- conservative,
    since a 1-minute bar cannot tell us which level was actually touched
    first intra-minute.

    If neither level is touched by exit_ts, the trade is closed at the
    exit bar's own close (the bar whose ts == exit_ts, i.e. the 15:15
    candle's close for this rule's exit_ts=15:15) -- a TIME_EXIT.
    """
    bars = bars_1min.copy()
    bars["ts"] = pd.to_datetime(bars["ts"])
    entry_ts = pd.Timestamp(entry_ts)
    exit_ts = pd.Timestamp(exit_ts)

    window = bars[(bars["ts"] > entry_ts) & (bars["ts"] <= exit_ts)].sort_values("ts")
    for _, bar in window.iterrows():
        hit_stop = bar["low"] <= stop_price
        hit_target = bar["high"] >= target_price
        if hit_stop:  # covers both the same-bar tie (hit_stop and hit_target) and a clean stop
            return {"outcome": "STOP", "exit_price": stop_price, "exit_ts": bar["ts"]}
        if hit_target:
            return {"outcome": "TARGET", "exit_price": target_price, "exit_ts": bar["ts"]}

    exit_bar = bars[bars["ts"] == exit_ts]
    if not exit_bar.empty:
        exit_price = float(exit_bar.iloc[0]["close"])
    else:
        before = bars[bars["ts"] <= exit_ts].sort_values("ts")
        if before.empty:
            raise ValueError(f"no bars at or before exit_ts={exit_ts} to resolve a TIME_EXIT against")
        exit_price = float(before.iloc[-1]["close"])
    return {"outcome": "TIME_EXIT", "exit_price": exit_price, "exit_ts": exit_ts}
