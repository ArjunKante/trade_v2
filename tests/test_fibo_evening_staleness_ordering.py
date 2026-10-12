"""Regression test for the staleness-guard-ordering bug: the evening job
used to check staleness BEFORE fetching, so a single missed evening run
(discovered live, 2026-10-12: nobody ran it at 18:30, nothing was
scheduled to) made the gap between real wall-clock "today" and the
warehouse's last-ingested date look like a multi-day outage -- and
refused before ever trying to fetch the one day that would have cured
it. The fix moved the fetch to run unconditionally, with staleness
checked AFTER, against the refreshed warehouse, right before the
computation that guard exists to protect.

This fixture reproduces the exact live scenario: a warehouse whose
latest data is a Friday, the job run the following Tuesday (after
midnight -- real "today" is Tuesday, 4 calendar days past Friday,
already past data_layer.staleness's default 3-day tolerance), with
Monday's bhavcopy available to be fetched. It must fetch Monday and
produce Tuesday's watchlist, not refuse.

Everything that would touch the real filesystem, network, or email is
monkeypatched: WAREHOUSE_DB (a tmp_path file, never data/warehouse.duckdb),
load_bhavcopy_to_duckdb (a stub that inserts a synthetic Monday row
instead of hitting NSE's real archive), assert_data_current (wrapped to
a fixed `as_of` so the test is not at the mercy of whatever day it
actually runs on), build_watchlist/materialize_adjustment_factors
(stubs -- this test is about the ORDERING of the staleness guard around
the fetch, not a re-test of the watchlist computation itself, which has
its own coverage), and already_notified/record_notification/send_email
(stubs -- no real email, no real event-log write).
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fibo_evening  # noqa: E402

from data_layer.staleness import assert_data_current as real_assert_data_current  # noqa: E402

FRIDAY = dt.date(2026, 10, 9)
MONDAY = dt.date(2026, 10, 12)
TUESDAY = dt.date(2026, 10, 13)  # real "today" for this test -- 4 calendar days past FRIDAY

ROW = ("('{isin}', '{trade_date}', 'SYM', 'EQ', 1,1,1,1,1,1,1,1,1, "
       "'{trade_date}', now(), 'T', 1)")


def _fake_build_watchlist(con, as_of_date, top_n=200):
    return pd.DataFrame([{
        "entity_id": "E1", "symbol": "TESTSTOCK", "year": as_of_date.year, "rank": 1,
        "uptrend": True, "has_swing": True, "passes_atr_filter": True,
        "swing_high": 110.0, "swing_low": 90.0, "atr": 2.0,
        "golden_zone_low": 95.0, "golden_zone_high": 100.0,
        "scale_factor": 1.0, "ex_date_flag": False, "qualifies": True,
        "close": 97.0,
    }])


@pytest.fixture
def isolated_evening_job(tmp_path, monkeypatch):
    """Points fibo_evening at a throwaway warehouse (seeded with only a
    Friday row), a throwaway events log, and stubs every fetch/compute/
    notify side effect -- see module docstring for why each one."""
    warehouse_path = tmp_path / "test_warehouse.duckdb"
    events_path = tmp_path / "events.jsonl"

    from data_layer.db import get_connection
    seed_con = get_connection(warehouse_path)
    seed_con.execute(f"INSERT INTO prices_eod VALUES {ROW.format(isin='ISIN1', trade_date=FRIDAY.isoformat())}")
    seed_con.close()

    monkeypatch.setattr(fibo_evening, "WAREHOUSE_DB", warehouse_path)
    monkeypatch.setattr(fibo_evening, "RAW_PRICES_DIR", tmp_path / "raw")

    fetched_dates = []

    def fake_load_bhavcopy(con, trade_date, raw_dir, series_include=None):
        fetched_dates.append(trade_date)
        if trade_date == MONDAY:
            con.execute(f"INSERT INTO prices_eod VALUES {ROW.format(isin='ISIN2', trade_date=MONDAY.isoformat())}")
            return 1
        return 0  # Tuesday (requested_date, not yet published this early) and anything else

    monkeypatch.setattr(fibo_evening, "load_bhavcopy_to_duckdb", fake_load_bhavcopy)

    def fixed_as_of_assert_data_current(con, as_of=None, max_staleness_days=3):
        return real_assert_data_current(con, as_of=TUESDAY, max_staleness_days=max_staleness_days)

    monkeypatch.setattr(fibo_evening, "assert_data_current", fixed_as_of_assert_data_current)
    monkeypatch.setattr(fibo_evening, "materialize_adjustment_factors", lambda con: 0)
    monkeypatch.setattr(fibo_evening, "build_watchlist", _fake_build_watchlist)

    logged_events = []

    def fake_append_event(kind, payload):
        event = {"kind": kind, **payload}
        logged_events.append(event)
        return event

    def fake_read_events(kind=None):
        return [e for e in logged_events if kind is None or e.get("kind") == kind]

    monkeypatch.setattr(fibo_evening, "append_event", fake_append_event)
    monkeypatch.setattr(fibo_evening, "read_events", fake_read_events)
    monkeypatch.setattr(fibo_evening, "already_notified", lambda *a, **k: False)
    monkeypatch.setattr(fibo_evening, "record_notification", lambda *a, **k: None)
    monkeypatch.setattr(fibo_evening, "send_email", lambda *a, **k: True)

    monkeypatch.setattr(sys, "argv", ["fibo_evening.py", "--date", TUESDAY.isoformat()])

    return {"fetched_dates": fetched_dates, "logged_events": logged_events, "warehouse_path": warehouse_path}


def test_missed_monday_evening_run_still_produces_tuesdays_watchlist(isolated_evening_job):
    """The exact live scenario: warehouse ends on Friday, job runs the
    following Tuesday (real 'today'), Monday's bhavcopy is available.
    Must fetch Monday and produce Tuesday's watchlist -- must NOT refuse
    on staleness before ever trying to fetch."""
    fibo_evening.main()

    fetched = isolated_evening_job["fetched_dates"]
    assert MONDAY in fetched, (
        f"Monday {MONDAY} was never fetched -- the staleness guard blocked the fetch "
        f"that would have cured the gap. Fetched: {fetched}"
    )

    runs = [e for e in isolated_evening_job["logged_events"] if e["kind"] == "watchlist_run"]
    assert len(runs) == 1, f"expected exactly one watchlist_run event, got {len(runs)}: {runs}"
    run = runs[0]
    assert run["as_of_date"] == MONDAY, f"watchlist computed from the wrong data date: {run['as_of_date']}"
    assert run["target_trade_date"] == TUESDAY, f"watchlist targeted the wrong trading day: {run['target_trade_date']}"

    watchlist_rows = [e for e in isolated_evening_job["logged_events"] if e["kind"] == "watchlist"]
    assert len(watchlist_rows) == 1
    assert watchlist_rows[0]["qualifies"] is True


def test_still_refuses_when_no_fetch_can_cure_the_gap(tmp_path, monkeypatch):
    """Companion case: if the fetch genuinely finds nothing (a real
    multi-day outage, not just one missed evening), the guard must still
    refuse -- this fix must not have turned the guard into a no-op."""
    warehouse_path = tmp_path / "test_warehouse_2.duckdb"
    from data_layer.db import get_connection
    seed_con = get_connection(warehouse_path)
    seed_con.execute(f"INSERT INTO prices_eod VALUES {ROW.format(isin='ISIN1', trade_date=FRIDAY.isoformat())}")
    seed_con.close()

    monkeypatch.setattr(fibo_evening, "WAREHOUSE_DB", warehouse_path)
    monkeypatch.setattr(fibo_evening, "RAW_PRICES_DIR", tmp_path / "raw")
    # Nothing is ever found -- simulates a genuine multi-day feed outage,
    # not a single missed evening with real data waiting to be fetched.
    monkeypatch.setattr(fibo_evening, "load_bhavcopy_to_duckdb", lambda con, trade_date, raw_dir, series_include=None: 0)

    def fixed_as_of_assert_data_current(con, as_of=None, max_staleness_days=3):
        return real_assert_data_current(con, as_of=TUESDAY, max_staleness_days=max_staleness_days)

    monkeypatch.setattr(fibo_evening, "assert_data_current", fixed_as_of_assert_data_current)
    monkeypatch.setattr(fibo_evening, "materialize_adjustment_factors", lambda con: 0)
    monkeypatch.setattr(fibo_evening, "build_watchlist", _fake_build_watchlist)

    logged_events = []
    monkeypatch.setattr(fibo_evening, "append_event", lambda kind, payload: logged_events.append({"kind": kind, **payload}))
    monkeypatch.setattr(fibo_evening, "read_events", lambda kind=None: [e for e in logged_events if kind is None or e.get("kind") == kind])
    monkeypatch.setattr(fibo_evening, "already_notified", lambda *a, **k: False)
    monkeypatch.setattr(fibo_evening, "record_notification", lambda *a, **k: None)
    monkeypatch.setattr(fibo_evening, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(sys, "argv", ["fibo_evening.py", "--date", TUESDAY.isoformat()])

    fibo_evening.main()

    runs = [e for e in logged_events if e["kind"] == "watchlist_run"]
    assert runs == [], f"should have refused (no cure found), but logged a watchlist_run anyway: {runs}"
