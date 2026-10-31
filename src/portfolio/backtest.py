"""Parameterized backtest loop for the portfolio-construction study
(PREREGISTRATION_PORTFOLIO.md), generalizing `scripts/run_holdout_
study1.py`'s own single-frequency, equal-weight-only loop to arbitrary
concentration/weighting/rebalance-frequency. Reuses `factors.momentum.
compute_momentum_12_1`, `factors.target.compute_forward_return`, and the
rolling-20-day-median-turnover tercile construction unchanged -- see
PREREGISTRATION_PORTFOLIO.md Section 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from portfolio.construction import select_portfolio
from portfolio.costs import COST_BY_TERCILE, turnover_and_cost


def build_tercile_lookup(panel: pd.DataFrame) -> pd.DataFrame:
    """Same rolling-20-day-median-turnover tercile construction as
    `scripts/run_holdout_study1.py`, unchanged. Returns [entity_id,
    trade_date, _tercile]."""
    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
    p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
        lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
        if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index)
    )
    return p[["entity_id", "trade_date", "_tercile"]]


def rebalance_dates_for(all_dates: list, rebalance_days: int) -> list:
    """Every `rebalance_days`-th trading day, trimmed at the tail
    wherever the forward-return window (horizon == rebalance_days, this
    study's own convention -- the holding period always matches the
    rebalance cadence) would run past the end of available data. Same
    trimming rule as `run_holdout_study1.py`'s own
    `all_dates.index(d) + HORIZON_DAYS < len(all_dates)`."""
    dates = all_dates[::rebalance_days]
    return [d for d in dates if all_dates.index(d) + rebalance_days < len(all_dates)]


def run_config(mom: pd.DataFrame, fwd: pd.DataFrame, tercile: pd.DataFrame, all_dates: list,
               concentration, weighting: str, rebalance_days: int) -> dict:
    """`mom`: [entity_id, trade_date, value] from compute_momentum_12_1.
    `fwd`: [entity_id, trade_date, eval_date, fwd_return] from
    compute_forward_return(panel, horizon=rebalance_days) -- the horizon
    MUST already match rebalance_days; this function does not check it.
    `tercile`: build_tercile_lookup's own output. `all_dates`: sorted
    list of every distinct trade_date in the panel.

    Returns {"records": DataFrame[date, n_held, gross, turnover, cost,
    net], "nav": list[float] (nav[0]=1.0, one entry per realized
    rebalance), "dates": list[Timestamp] (len(dates) == len(nav)-1)}."""
    full = mom.merge(tercile, on=["entity_id", "trade_date"]).dropna(subset=["value", "_tercile"])
    clean = mom.merge(fwd, on=["entity_id", "trade_date"]).merge(
        tercile, on=["entity_id", "trade_date"]
    ).dropna(subset=["value", "fwd_return", "_tercile"])

    rb_dates = rebalance_dates_for(all_dates, rebalance_days)

    nav = [1.0]
    nav_dates: list = []
    prev_weights: dict = {}
    records = []

    for d in rb_dates:
        day_full = full[full["trade_date"] == d]
        if len(day_full) < 20:
            continue
        pool = clean[clean["trade_date"] == d].rename(columns={"fwd_return": "realized_return"})
        if pool.empty:
            continue

        sel = select_portfolio(pool[["entity_id", "value"]], concentration, weighting)
        if sel.empty:
            continue
        new_weights = dict(zip(sel["entity_id"], sel["weight"]))

        ret_lookup = dict(zip(pool["entity_id"], pool["realized_return"]))
        gross_ret = sum(w * ret_lookup[eid] for eid, w in new_weights.items() if eid in ret_lookup)

        tercile_lookup = dict(zip(pool["entity_id"], pool["_tercile"]))
        turnover, cost = turnover_and_cost(prev_weights, new_weights, tercile_lookup)

        net_ret = gross_ret - cost
        nav.append(nav[-1] * (1 + net_ret))
        nav_dates.append(d)
        records.append({
            "date": d, "n_held": len(sel), "gross": gross_ret,
            "turnover": turnover, "cost": cost, "net": net_ret,
        })
        prev_weights = new_weights

    return {"records": pd.DataFrame(records), "nav": nav, "dates": nav_dates}


def max_drawdown(nav: list) -> dict:
    """Returns {"mdd": float (negative), "peak_idx": int, "trough_idx":
    int, "duration_periods": int} -- duration in REBALANCE PERIODS
    (indices into `nav`), not trading days; converted to trading days by
    the caller (duration_periods * rebalance_days) where that unit is
    needed."""
    arr = np.array(nav)
    peak = np.maximum.accumulate(arr)
    dd = (arr - peak) / peak
    trough_idx = int(np.argmin(dd))
    peak_idx = int(np.argmax(arr[: trough_idx + 1])) if trough_idx > 0 else 0
    return {"mdd": float(dd[trough_idx]), "peak_idx": peak_idx, "trough_idx": trough_idx,
            "duration_periods": trough_idx - peak_idx}
