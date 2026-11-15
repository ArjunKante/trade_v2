"""Computes the Fibo forward test's VALID-OBSERVATION-DAY counter --
read-only, no trade/rule/event touched.

WHY THIS EXISTS (2026-11-15 health check, OPERATIONS.md, FIBO_FINDINGS.md):
"0 trades in N calendar days" is not a usable denominator for this
forward test, because most calendar days since inception were not days
the pipeline was actually capable of producing a trade -- the evening job
has been down for entire weeks at a stretch (BUGS.md Bug #19), and the
morning job's own GitHub-Actions-schedule bug (OPERATIONS.md, "GitHub
Actions schedule fires hours late") meant the live-monitoring half of
this system had never once run successfully before 2026-10-23. Reading
"0 trades in 38 days" against the backtest's own trade rate would already
look like decay by the time there are 100 calendar days behind this test;
the denominator that actually matters is how many of those days the
system was CAPABLE of producing a trade, not how many days have passed.

DEFINITION (frozen here, not re-derived informally each time this is
quoted): a trading day D is a VALID OBSERVATION DAY if and only if:
  1. a `watchlist_run` event exists with target_trade_date == D (the
     evening job produced a fresh watchlist for D, satisfying the
     morning job's own freshness guard, fibo_morning.assert_watchlist_
     current), AND
  2. at least one `setup` event exists for D with run_mode == "LIVE" and
     a timestamp between 09:30 and 11:30 IST -- the entry window the
     breakout rule actually uses (PREREGISTRATION_FIBO.md Section (f)),
     i.e. the morning job reached the per-entity setup/trigger-checking
     stage while a trigger could still have fired, not merely logged a
     session_status refusal or a setup event discovered after the window
     had already closed (the AXISBANK 2026-10-19 case: SETUP_ON logged
     14:59, 3.5 hours after the window closed -- does NOT count).

A day that is a confirmed NSE holiday or a weekend is not a trading day
at all and is excluded from both the numerator and the denominator, not
counted as invalid.

Usage:
    python scripts/fibo_valid_observation_days.py [--since YYYY-MM-DD]

Prints the running total and the day-by-day classification. Intended to
be re-run periodically and its headline number copied into
FIBO_FINDINGS.md as a dated, append-only entry (never silently updated in
place) -- see that file's "Valid-observation-day counter" section.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVENTS_LOG = ROOT / "data" / "fibo_live" / "v1" / "events.jsonl"
FORWARD_TEST_START = dt.date(2026, 10, 8)  # first watchlist_run event ever logged

ENTRY_WINDOW_START = dt.time(9, 30)
ENTRY_WINDOW_END = dt.time(11, 30)


def _load_events() -> list[dict]:
    events = []
    with open(EVENTS_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _parse_ts(ts: str) -> dt.datetime:
    # Events carry either a naive IST string ("...T18:30:00") or an
    # explicit-offset one ("...+05:30") -- normalize to naive IST for the
    # time-of-day comparison this script needs; never mix with UTC.
    parsed = dt.datetime.fromisoformat(ts)
    return parsed.replace(tzinfo=None)


def _is_trading_day(d: dt.date) -> bool:
    if d.weekday() >= 5:
        return False
    try:
        if is_nse_holiday(d):
            return False
    except HolidayCalendarMissing:
        pass  # treated as an ordinary trading day, same degraded-mode fallback as fibo_evening.py
    return True


def compute(since: dt.date, through: dt.date) -> dict:
    events = _load_events()

    watchlist_targets = {e["target_trade_date"] for e in events
                         if e.get("kind") == "watchlist_run" and e.get("target_trade_date")}

    live_setup_in_window_days = set()
    for e in events:
        if e.get("kind") != "setup" or e.get("run_mode") != "LIVE":
            continue
        trade_date = e.get("trade_date")
        if not trade_date:
            continue
        try:
            ts = _parse_ts(e["ts"])
        except (KeyError, ValueError):
            continue
        if ENTRY_WINDOW_START <= ts.time() <= ENTRY_WINDOW_END:
            live_setup_in_window_days.add(trade_date)

    rows = []
    d = since
    while d <= through:
        if _is_trading_day(d):
            ds = d.isoformat()
            has_watchlist = ds in watchlist_targets
            has_in_window_morning = ds in live_setup_in_window_days
            rows.append({
                "date": ds, "weekday": d.strftime("%a"),
                "evening_watchlist": has_watchlist,
                "morning_in_window": has_in_window_morning,
                "valid_observation_day": has_watchlist and has_in_window_morning,
            })
        d += dt.timedelta(days=1)

    n_trading_days = len(rows)
    n_valid = sum(1 for r in rows if r["valid_observation_day"])
    return {"rows": rows, "n_trading_days": n_trading_days, "n_valid": n_valid}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=str, default=FORWARD_TEST_START.isoformat())
    parser.add_argument("--through", type=str, default=None, help="default: today")
    args = parser.parse_args()
    since = dt.date.fromisoformat(args.since)
    through = dt.date.fromisoformat(args.through) if args.through else dt.date.today()

    result = compute(since, through)
    for r in result["rows"]:
        flag = "VALID" if r["valid_observation_day"] else "---"
        print(f"{r['date']} ({r['weekday']})  evening={r['evening_watchlist']!s:5}  "
              f"morning_in_window={r['morning_in_window']!s:5}  {flag}")
    print()
    print(f"Trading days {since} .. {through}: {result['n_trading_days']}")
    print(f"Valid observation days: {result['n_valid']}")


if __name__ == "__main__":
    main()
