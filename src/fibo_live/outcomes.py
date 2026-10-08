"""Outcome logging and the evaluation gate (DO-NOT list: never show
performance before 100 completed trades).

An "outcome" event is the final word on one (entity, trade_date) setup
that was SETUP ON that morning: either it triggered (an entry actually
happened, with a full entry/exit/R record) or it did not (11:30 passed
with no qualifying 15-minute close). Both are logged -- a day that never
triggered is not silently dropped, it is evidence too (per Section 6b's
own TIMING-null finding: how often a qualifying setup fails to trigger is
itself informative). Only `triggered=True` rows count as a COMPLETED
TRADE for the 100-trade gate below; a no-trigger day has no R to average
into anything.

Append-only, same as eventlog.py generally: this module has no edit
function. A correction to an already-logged outcome (e.g. a hand-checked
exit price turns out wrong) is logged as a NEW outcome event carrying
`corrects=<original event_id>` -- never a rewrite of the original line.
record_outcome() always appends a new row; nothing here ever locates and
mutates an existing one.
"""
from __future__ import annotations

import datetime as dt
import math

from fibo_live.config import EVAL_MIN_TRADES, SEALED_AMENDED_MEAN_NET_R
from fibo_live.costs import amended_cost_rs, band_for_rank
from fibo_live.eventlog import append_event, read_events


def record_outcome(
    *, entity_id: str, symbol: str, trade_date: dt.date, rank: int | None, triggered: bool,
    entry_ts=None, entry_price: float | None = None, stop: float | None = None, target: float | None = None,
    qty: int | None = None, exit_ts=None, exit_price: float | None = None, exit_reason: str | None = None,
    corrects: str | None = None,
) -> dict:
    """Logs one completed-or-not setup outcome. When triggered=True, computes
    gross_r and net_r (Section 8c amended cost model, src/fibo_live/costs.py)
    from entry/exit/qty -- the caller never computes R itself, so every
    logged trade's R is computed by exactly one code path."""
    payload = {
        "entity_id": entity_id, "symbol": symbol, "trade_date": trade_date, "rank": rank,
        "triggered": triggered, "entry_ts": entry_ts, "entry_price": entry_price, "stop": stop,
        "target": target, "qty": qty, "exit_ts": exit_ts, "exit_price": exit_price, "exit_reason": exit_reason,
    }
    if corrects:
        payload["corrects"] = corrects

    if triggered:
        if None in (entry_price, stop, qty, exit_price):
            raise ValueError("triggered=True requires entry_price, stop, qty, exit_price")
        r_rupees = entry_price - stop
        gross_r = (exit_price - entry_price) / r_rupees
        band = band_for_rank(rank)
        position_size_rs = qty * entry_price
        cost_rs = amended_cost_rs(position_size_rs, band)
        net_r = gross_r - cost_rs / (r_rupees * qty)
        payload.update({"band": band, "r_rupees": r_rupees, "gross_r": gross_r,
                         "cost_rs": cost_rs, "net_r": net_r})

    return append_event("outcome", payload)


def evaluate() -> dict:
    """The gate itself. Returns {"n_completed": int, "evaluated": False} if
    fewer than EVAL_MIN_TRADES triggered outcomes exist -- the UI must show
    COUNT ONLY in that case, nothing else. Once the gate opens, returns
    mean net R, its t-stat against zero, and the comparison against the
    sealed amended re-test's own +0.3673 (config.SEALED_AMENDED_MEAN_NET_R)."""
    outcomes = [o for o in read_events(kind="outcome") if o.get("triggered")]
    n = len(outcomes)
    if n < EVAL_MIN_TRADES:
        return {"n_completed": n, "evaluated": False, "min_trades": EVAL_MIN_TRADES}

    net_rs = [o["net_r"] for o in outcomes]
    mean = sum(net_rs) / n
    variance = sum((x - mean) ** 2 for x in net_rs) / (n - 1) if n > 1 else 0.0
    se = math.sqrt(variance / n) if n > 1 else 0.0
    t_stat = mean / se if se > 0 else float("nan")

    return {
        "n_completed": n, "evaluated": True, "mean_net_r": mean, "t_stat": t_stat,
        "sealed_amended_mean_net_r": SEALED_AMENDED_MEAN_NET_R,
        "diff_vs_sealed": mean - SEALED_AMENDED_MEAN_NET_R,
    }
