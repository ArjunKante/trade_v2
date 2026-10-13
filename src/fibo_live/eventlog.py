"""Append-only JSONL event log -- the single evidence trail for the live
paper-trading system. One file per PAPER_VERSION (config.EVENTS_LOG);
every evening watchlist row, every morning setup, every trigger, and every
trade outcome is one JSON line in this same file, tagged by `kind`.

IMMUTABILITY BY OMISSION, deliberately: this module exposes append_event
and read_events ONLY. There is no update_event, no delete_event, and
append always opens the file in "a" mode (never "w", never seek-and-
rewrite) -- the same append-only discipline src/monitor/web.py's
_log_holdout_access and this project's warehouse tables (known_date/
fetched_at/source/revision_seq, never UPDATE/DELETE) already use
elsewhere. A correction to an already-logged event is a NEW event row
with a `corrects` field pointing at the original event's `event_id` --
never a rewrite of the original line. Any future caller that wants to
"fix" a row belongs in a new row, not a new function in this module.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

from fibo_live.config import EVENTS_LOG
from spread_monitor.market_hours import IST


def _jsonable(obj):
    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    return obj


def append_event(kind: str, payload: dict, log_path: Path = EVENTS_LOG) -> dict:
    """Appends one event line {event_id, ts, kind, **payload} and returns
    it. `ts` is wall-clock now() IN IST -- explicit, never the host
    machine's own local clock, so entries logged from the laptop
    (evening job) and a GitHub Actions runner (morning job, OS clock
    UTC) stay on the same clock in the SAME file. For the evening
    watchlist this is what makes the forward test honest (logged before
    any price for that date is known); for every other kind it is simply
    when the event happened."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": str(uuid.uuid4()),
        "ts": dt.datetime.now(IST).isoformat(timespec="seconds"),
        "kind": kind,
        **{k: _jsonable(v) for k, v in payload.items()},
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=_jsonable) + "\n")
    return event


def read_events(kind: str | None = None, log_path: Path = EVENTS_LOG) -> list[dict]:
    """All events, optionally filtered to one `kind`, in file (= chronological
    append) order. Returns [] if the log does not exist yet -- a fresh
    version with nothing logged is not an error."""
    if not log_path.exists():
        return []
    events = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    if kind is not None:
        events = [e for e in events if e.get("kind") == kind]
    return events
