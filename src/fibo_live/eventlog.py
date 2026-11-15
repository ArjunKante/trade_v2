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

import fibo_live.config as config
from spread_monitor.market_hours import IST


def _jsonable(obj):
    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    return obj


def append_event(kind: str, payload: dict, log_path: Path | None = None) -> dict:
    """Appends one event line {event_id, ts, kind, **payload} and returns
    it. `ts` is wall-clock now() IN IST -- explicit, never the host
    machine's own local clock, so entries logged from the laptop
    (evening job) and a GitHub Actions runner (morning job, OS clock
    UTC) stay on the same clock in the SAME file. For the evening
    watchlist this is what makes the forward test honest (logged before
    any price for that date is known); for every other kind it is simply
    when the event happened.

    `log_path=None` (the default) resolves `config.EVENTS_LOG` FRESH, at
    call time -- never bound once at this function's own definition time
    (2026-11-15, BUGS.md: a bare `log_path: Path = EVENTS_LOG` default
    would capture the real path permanently, immune to a test-session
    monkeypatch of `fibo_live.config.EVENTS_LOG`, the exact stale-default
    shape `scheduler_support.make_logger` already had). This is what lets
    `tests/conftest.py`'s autouse fixture redirect every caller that
    doesn't pass its own explicit `log_path` -- including a test written
    carelessly with no monkeypatching of this function at all -- without
    this module needing to know pytest exists."""
    log_path = log_path if log_path is not None else config.EVENTS_LOG
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


def read_events(kind: str | None = None, log_path: Path | None = None) -> list[dict]:
    """All events, optionally filtered to one `kind`, in file (= chronological
    append) order. Returns [] if the log does not exist yet -- a fresh
    version with nothing logged is not an error.

    DEDUPES BY event_id, keeping the first occurrence: cheap insurance
    against the same line appearing on both sides of a git merge
    (.gitattributes's `merge=union` driver on this file, git_sync.py's
    pull_before_appending) -- a union merge is expected to already avoid
    this, but this is a one-line guarantee against relying on that alone.
    An event with no `event_id` (should not happen; every append_event
    call mints one) is never deduped against anything, including itself,
    since there's no key to dedupe on.

    `log_path=None` resolves `config.EVENTS_LOG` fresh at call time -- see
    `append_event`'s docstring for why (same stale-default fix, 2026-11-15)."""
    log_path = log_path if log_path is not None else config.EVENTS_LOG
    if not log_path.exists():
        return []
    events = []
    seen_event_ids = set()
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            event_id = event.get("event_id")
            if event_id is not None:
                if event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event_id)
            events.append(event)
    if kind is not None:
        events = [e for e in events if e.get("kind") == kind]
    return events
