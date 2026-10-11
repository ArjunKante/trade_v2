"""R_REVERSAL / R_CONTINUATION weekly rule mechanics -- entry/exit/stop
simulation shared by both named rules (they differ only in which sign of
the PRIOR week's return triggers entry) and by the random-entry null
(per_stock.stats), which reuses the exact same exit/stop mechanics with a
randomly chosen entry week instead of a signal-triggered one.

FROZEN, per PREREGISTRATION_PER_STOCK.md -- SIGMA_MULTIPLE is not a knob:
    R_REVERSAL:     prior week's return < -SIGMA_MULTIPLE * sigma
    R_CONTINUATION: prior week's return > +SIGMA_MULTIPLE * sigma
    stop:           exit if a day's close <= entry * (1 - SIGMA_MULTIPLE * sigma)
    exit otherwise: that week's own week_close (Friday, or the week's last
                     traded day if Friday itself did not trade)
Long only. One position per stock at a time is automatic, not separately
enforced: every trade both enters and fully resolves (stop or week close)
within the SAME calendar week, so no two trades for the same entity can
ever overlap.
"""
from __future__ import annotations

import pandas as pd

from per_stock.costs import net_cost_fraction

SIGMA_MULTIPLE = 1.0

REVERSAL = "R_REVERSAL"
CONTINUATION = "R_CONTINUATION"
RULES = (REVERSAL, CONTINUATION)


def entry_candidates(weekly: pd.DataFrame, entity_id: str) -> pd.DataFrame:
    """One row per week that COULD be entered (signal week i's own
    return/sigma paired with entry week i+1's own open/close) -- the
    shared pool both `generate_trades` (filtered to a return-sign
    condition) and the random-entry null (sampled unconditionally) draw
    from. Only rows with a defined, positive `sig_sigma` are included --
    the first SIGMA_WINDOW_WEEKS (52) weeks of any entity's history can
    never produce a trade or a random entry, by construction."""
    w = weekly[weekly["entity_id"] == entity_id].sort_values("week_start").reset_index(drop=True)
    cols = ["entity_id", "sig_week_start", "sig_return", "sig_sigma",
            "entry_week_start", "entry_week_open", "entry_week_close"]
    if len(w) < 2:
        return pd.DataFrame(columns=cols)
    sig = w.iloc[:-1].reset_index(drop=True)
    entry = w.iloc[1:].reset_index(drop=True)
    out = pd.DataFrame({
        "entity_id": entity_id,
        "sig_week_start": sig["week_start"], "sig_return": sig["week_return"], "sig_sigma": sig["sigma"],
        "entry_week_start": entry["week_start"], "entry_week_open": entry["week_open"],
        "entry_week_close": entry["week_close"],
    })
    return out[out["sig_sigma"].notna() & (out["sig_sigma"] > 0)].reset_index(drop=True)


def precompute_week_days(daily: pd.DataFrame, entity_id: str) -> dict:
    """{week_start: [(trade_date, adjusted_close), ... sorted ...]} for
    every week `entity_id` has at least one traded day. Built ONCE per
    entity and reused across every trial/rule/null-draw for that entity --
    the random null alone needs up to NULL_SEEDS x dozens of trades x
    every (stock, rule) of these lookups, so the stop-check inner loop
    must never re-filter the full daily panel per trade."""
    sub = daily[daily["entity_id"] == entity_id].sort_values("trade_date")
    week_start = sub["trade_date"] - pd.to_timedelta(sub["trade_date"].dt.weekday, unit="D")
    cache: dict = {}
    for ws, date, close in zip(week_start, sub["trade_date"], sub["adjusted_close"]):
        cache.setdefault(ws, []).append((date, float(close)))
    return cache


def simulate_trade(week_days: dict, entity_id: str, entry_week_start: pd.Timestamp,
                    entry_week_open: float, entry_week_close: float, sigma: float) -> dict:
    """One trade: enter at `entry_week_open`, stop at
    entry*(1 - SIGMA_MULTIPLE*sigma) checked on each trading day's close
    within the week (first breach wins, same-day as the breach), else
    exit at `entry_week_close`. `sigma` is the FROZEN value that produced
    the signal (or, for a random-null draw, the preceding week's own
    sigma) -- never re-estimated intra-week. `week_days`: see
    precompute_week_days."""
    entry_price = float(entry_week_open)
    stop_price = entry_price * (1 - SIGMA_MULTIPLE * sigma)
    days = week_days.get(pd.Timestamp(entry_week_start), [])

    exit_price, exit_date, stopped_out = None, None, False
    for date, close in days:
        if close <= stop_price:
            exit_price, exit_date, stopped_out = close, date, True
            break
    if exit_price is None:
        exit_price = float(entry_week_close)
        exit_date = days[-1][0] if days else entry_week_start

    raw_return = exit_price / entry_price - 1.0
    cost_frac = net_cost_fraction(entry_price, stop_price)
    net_return = raw_return - cost_frac

    return {
        "entity_id": entity_id, "entry_week_start": entry_week_start, "entry_price": entry_price,
        "stop_price": stop_price, "sigma": sigma, "exit_price": exit_price, "exit_date": exit_date,
        "stopped_out": stopped_out, "raw_return": raw_return, "cost_frac": cost_frac, "net_return": net_return,
    }


def generate_trades(weekly: pd.DataFrame, week_days: dict, entity_id: str, rule: str) -> pd.DataFrame:
    """Every trade `rule` would have triggered over `entity_id`'s full
    available weekly history."""
    if rule not in RULES:
        raise ValueError(f"rule must be one of {RULES}, got {rule!r}")
    cands = entry_candidates(weekly, entity_id)
    if rule == REVERSAL:
        cands = cands[cands["sig_return"] < -SIGMA_MULTIPLE * cands["sig_sigma"]]
    else:
        cands = cands[cands["sig_return"] > SIGMA_MULTIPLE * cands["sig_sigma"]]

    trades = [
        simulate_trade(week_days, entity_id, row["entry_week_start"], row["entry_week_open"],
                        row["entry_week_close"], row["sig_sigma"])
        for _, row in cands.iterrows()
    ]
    cols = ["entity_id", "entry_week_start", "entry_price", "stop_price", "sigma", "exit_price",
            "exit_date", "stopped_out", "raw_return", "cost_frac", "net_return"]
    return pd.DataFrame(trades, columns=cols) if trades else pd.DataFrame(columns=cols)
