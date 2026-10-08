"""JSON payload for the screener web app's "Fibo Live (Paper)" tab.

Unlike reports.screener_web.build_cache (computed ONCE at server startup),
this is read FRESH on every request -- the evening/morning jobs
(scripts/fibo_evening.py, scripts/fibo_morning.py) are separate processes
that keep appending to the same append-only event log all day, and the UI
is meant to show whatever is true right now, not a snapshot from whenever
the web server happened to start. The read itself is cheap (a single
JSONL file, at most a few hundred stocks/day) so there is no need to cache
it across requests.

Shows no price, no R, no win rate for anything beyond the watchlist/setup
mechanics themselves until EVAL_MIN_TRADES completed trades exist
(src/fibo_live/outcomes.evaluate) -- the UI must enforce the same gate the
DO-NOT list states, not just this backend.
"""
from __future__ import annotations

import datetime as dt

from fibo_live.config import PAPER_VERSION
from fibo_live.eventlog import read_events
from fibo_live.outcomes import evaluate


def _latest_watchlist_run():
    runs = read_events(kind="watchlist_run")
    return max(runs, key=lambda e: e["ts"]) if runs else None


def build_fibo_live_payload() -> dict:
    run = _latest_watchlist_run()
    if run is None:
        return {"available": False, "paper_version": PAPER_VERSION}

    watchlist_rows = [e for e in read_events(kind="watchlist") if e["run_id"] == run["run_id"] and e["qualifies"]]
    trade_date = run["as_of_date"]

    setups = {e["entity_id"]: e for e in read_events(kind="setup") if e["trade_date"] == trade_date}
    triggers = {e["entity_id"]: e for e in read_events(kind="trigger") if e["trade_date"] == trade_date}
    outcomes_by_entity = {}
    for e in read_events(kind="outcome"):
        if e["trade_date"] == trade_date:
            outcomes_by_entity[e["entity_id"]] = e  # last one wins -- a correction row sorts later in the file

    rows = []
    for w in watchlist_rows:
        entity_id = w["entity_id"]
        setup = setups.get(entity_id)
        trigger = triggers.get(entity_id)
        outcome = outcomes_by_entity.get(entity_id)

        current_price, current_price_ts, current_price_label = None, None, None
        if outcome and outcome.get("exit_price") is not None:
            current_price, current_price_ts, current_price_label = outcome["exit_price"], outcome["ts"], "exit price"
        elif trigger:
            current_price, current_price_ts, current_price_label = trigger["entry_price"], trigger["ts"], "entry price"
        elif setup and setup.get("orb_high") is not None:
            current_price, current_price_ts, current_price_label = setup["orb_high"], setup["ts"], "ORB high"

        inside_zone = None
        if setup and setup.get("zone_low_raw") is not None:
            inside_zone = setup["zone_low_raw"] <= setup["orb_high"] and setup["orb_low"] <= setup["zone_high_raw"]

        rows.append({
            "entity_id": entity_id, "symbol": w["symbol"], "rank": w["rank"],
            "golden_zone_low": w["golden_zone_low"], "golden_zone_high": w["golden_zone_high"],
            "golden_zone_computed_ts": w["ts"],
            "orb_high": setup.get("orb_high") if setup else None,
            "orb_low": setup.get("orb_low") if setup else None,
            "setup_on": setup.get("setup_on") if setup else None,
            "setup_computed_ts": setup["ts"] if setup else None,
            "inside_zone": inside_zone,
            "entry_trigger_price": setup.get("provisional_entry") if setup else None,
            "stop": setup.get("stop") if setup else None,
            "target": setup.get("provisional_target") if setup else None,
            "qty": setup.get("provisional_qty") if setup else None,
            "triggered": trigger is not None,
            "trigger_entry_ts": trigger.get("entry_ts") if trigger else None,
            "trigger_entry_price": trigger.get("entry_price") if trigger else None,
            "trigger_logged_ts": trigger.get("ts") if trigger else None,
            "outcome_exit_reason": outcome.get("exit_reason") if outcome else None,
            "outcome_logged_ts": outcome.get("ts") if outcome else None,
            "current_price": current_price, "current_price_ts": current_price_ts,
            "current_price_label": current_price_label,
        })

    return {
        "available": True,
        "paper_version": PAPER_VERSION,
        "trade_date": trade_date,
        "watchlist_run_ts": run["ts"],
        "n_universe": run["n_universe"],
        "n_qualify": run["n_qualify"],
        "rows": rows,
        "evaluation": evaluate(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
