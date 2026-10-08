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

Every outcome also carries `run_mode` (src/fibo_live/clock.py): LIVE if
the run that produced it started during market hours on the trade date
itself, before that day's outcome was knowable; REPLAY otherwise (a
catch-up run after close, or on a later day, against data that already
fully existed). The caller detects and passes this -- it is not computed
here from the outcome event's own append timestamp, which would be wrong
(see clock.py's docstring for why).

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
from pathlib import Path

from fibo_live.config import EVAL_MIN_TRADES, EVENTS_LOG, SEALED_AMENDED_MEAN_NET_R
from fibo_live.costs import amended_cost_rs, band_for_rank
from fibo_live.eventlog import append_event, read_events

# how far apart the LIVE and REPLAY means must be, relative to the sealed
# amended baseline's own scale, before evaluate() flags it as a material
# difference worth looking at -- not an arbitrary epsilon, a fraction of
# the one external number this project already treats as meaningful.
MATERIAL_DIFF_FRACTION_OF_BASELINE = 0.5


def record_outcome(
    *, entity_id: str, symbol: str, trade_date: dt.date, rank: int | None, triggered: bool, run_mode: str,
    entry_ts=None, entry_price: float | None = None, stop: float | None = None, target: float | None = None,
    qty: int | None = None, exit_ts=None, exit_price: float | None = None, exit_reason: str | None = None,
    corrects: str | None = None, log_path: Path = EVENTS_LOG,
) -> dict:
    """Logs one completed-or-not setup outcome. When triggered=True, computes
    gross_r and net_r (Section 8c amended cost model, src/fibo_live/costs.py)
    from entry/exit/qty -- the caller never computes R itself, so every
    logged trade's R is computed by exactly one code path. `run_mode` is
    required, not defaulted -- the caller must have already detected it
    once per run (src/fibo_live/clock.detect_run_mode), not leave it to
    silently fall back to something here."""
    payload = {
        "entity_id": entity_id, "symbol": symbol, "trade_date": trade_date, "rank": rank,
        "triggered": triggered, "run_mode": run_mode,
        "entry_ts": entry_ts, "entry_price": entry_price, "stop": stop,
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

    return append_event("outcome", payload, log_path=log_path)


def _stats(net_rs: list[float]) -> dict:
    n = len(net_rs)
    if n == 0:
        return {"n": 0, "mean_net_r": None, "t_stat": None}
    mean = sum(net_rs) / n
    if n > 1:
        variance = sum((x - mean) ** 2 for x in net_rs) / (n - 1)
        se = math.sqrt(variance / n)
        t_stat = mean / se if se > 0 else float("nan")
    else:
        t_stat = None  # a single observation has no estimate of its own spread
    return {"n": n, "mean_net_r": mean, "t_stat": t_stat}


def evaluate(log_path: Path = EVENTS_LOG) -> dict:
    """The gate itself. Returns {"n_completed": int, "evaluated": False} if
    fewer than EVAL_MIN_TRADES triggered outcomes exist in total -- the UI
    must show COUNT ONLY in that case, nothing else.

    Once the gate opens: reports LIVE-only, REPLAY-only, and combined mean
    net R / t-stat side by side, never blended into a single number without
    also showing the split. REPLAY runs compute the exact same frozen rule
    against data that already fully existed when the run started -- closer
    in evidentiary strength to a backtest than to a genuine forward test
    (the same caveat Section 9i raised about the amended re-test). If the
    two sets differ by more than MATERIAL_DIFF_FRACTION_OF_BASELINE of the
    sealed amended baseline's own mean, `material_difference` is flagged
    True -- that divergence is itself a finding, not noise to average away."""
    outcomes = [o for o in read_events(kind="outcome", log_path=log_path) if o.get("triggered")]
    n = len(outcomes)
    if n < EVAL_MIN_TRADES:
        return {"n_completed": n, "evaluated": False, "min_trades": EVAL_MIN_TRADES}

    all_net_rs = [o["net_r"] for o in outcomes]
    live_net_rs = [o["net_r"] for o in outcomes if o.get("run_mode") == "LIVE"]
    replay_net_rs = [o["net_r"] for o in outcomes if o.get("run_mode") == "REPLAY"]

    combined = _stats(all_net_rs)
    live = _stats(live_net_rs)
    replay = _stats(replay_net_rs)

    live_vs_replay_diff = None
    material_difference = None
    if live["mean_net_r"] is not None and replay["mean_net_r"] is not None:
        live_vs_replay_diff = live["mean_net_r"] - replay["mean_net_r"]
        material_difference = (
            abs(live_vs_replay_diff) > MATERIAL_DIFF_FRACTION_OF_BASELINE * abs(SEALED_AMENDED_MEAN_NET_R)
        )

    return {
        "n_completed": n, "evaluated": True,
        # top-level fields are the COMBINED figures, kept for backward compatibility
        # with anything that only reads one number.
        "mean_net_r": combined["mean_net_r"], "t_stat": combined["t_stat"],
        "sealed_amended_mean_net_r": SEALED_AMENDED_MEAN_NET_R,
        "diff_vs_sealed": combined["mean_net_r"] - SEALED_AMENDED_MEAN_NET_R,
        "combined": combined, "live": live, "replay": replay,
        "live_vs_replay_diff": live_vs_replay_diff, "material_difference": material_difference,
    }
