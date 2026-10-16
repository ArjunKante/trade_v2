"""End-to-end simulation of the real Oct 2026 holiday week -- Monday
2026-10-19, the NSE holiday Tuesday 2026-10-20, Wednesday 2026-10-21 --
run entirely against tmp fixtures. NO live runs: no real network, no
real Angel One session, no real git push. Exercises the REAL
next_trading_day / previous_trading_day / is_nse_holiday /
load_bhavcopy_to_duckdb holiday-classification code, chained across
both scheduled jobs sharing one tmp events.jsonl -- the same file the
laptop (evening job) and GitHub Actions (morning job) share for real.

next_trading_day is now holiday-aware UP FRONT (consults is_nse_holiday
directly, not just a reactive fetch_log check) -- Monday evening's run
sees Tuesday's holiday in advance and targets Wednesday directly, no
stale Tuesday-targeting watchlist_run and no misleading digest email for
the holiday itself. See test_next_trading_day_degrades_... below for the
explicit, logged degradation when a candidate year isn't covered by any
calendar at all.

Only three things are faked: the network fetch (fetch_raw_zip, so no
real NSE request is made -- but it still raises the exact exception
load_bhavcopy_to_duckdb's real holiday-classification logic branches
on), build_watchlist/materialize_adjustment_factors (pure compute
stubs, not what this file is testing), and the morning job's Angel
login/live-feed check (no real broker session). Everything else --
the backward-walk, next_trading_day, is_nse_holiday,
assert_watchlist_current, previous_trading_day, log_refusal, and the
REAL already_notified/record_notification dedup for the digest email --
runs for real.
"""
import datetime as dt
import functools
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import data_layer.prices_nse as prices_nse  # noqa: E402
import fibo_live.notify as notify_module  # noqa: E402
from data_layer.db import get_connection  # noqa: E402
from data_layer.nse_holidays import HolidayCalendarMissing  # noqa: E402
from data_layer.nse_holidays import _load as holidays_load  # noqa: E402
from data_layer.prices_nse import SOURCE_UDIFF, NoDataForDate  # noqa: E402
from data_layer.staleness import assert_data_current as real_assert_data_current  # noqa: E402

import fibo_evening  # noqa: E402
import fibo_morning  # noqa: E402
from fibo_live.eventlog import append_event as real_append_event, read_events as real_read_events  # noqa: E402
from fibo_live.session_status import NON_TRADING_DAY  # noqa: E402
from fibo_live.session_status import record_session_status as real_record_session_status  # noqa: E402

MONDAY = dt.date(2026, 10, 19)
HOLIDAY_TUESDAY = dt.date(2026, 10, 20)  # confirmed (live, against this laptop's own pkl) an NSE holiday
WEDNESDAY = dt.date(2026, 10, 21)

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


class _StubLoginResult:
    ok = True
    client = object()


@pytest.fixture(autouse=True)
def _clear_holiday_cache():
    """is_nse_holiday's own lru_cache is module-global and shared across
    the whole test session -- clear it so this file always reads
    whatever real calendar file(s) actually exist on disk right now,
    never a result cached by an unrelated earlier test."""
    holidays_load.cache_clear()
    yield
    holidays_load.cache_clear()


@pytest.fixture
def holiday_week(tmp_path, monkeypatch):
    warehouse_path = tmp_path / "warehouse.duckdb"
    events_path = tmp_path / "events.jsonl"

    con = get_connection(warehouse_path)
    # Monday is already fetched and present -- an ordinary, already-
    # ingested trading day, exactly like every other weekday evening.
    con.execute(f"INSERT INTO prices_eod VALUES {ROW.format(isin='ISIN1', trade_date=MONDAY.isoformat())}")
    con.execute("INSERT INTO fetch_log VALUES (?, ?, 'ok', 1, now())", [SOURCE_UDIFF, MONDAY])
    con.close()

    monkeypatch.setattr(fibo_evening, "WAREHOUSE_DB", warehouse_path)
    monkeypatch.setattr(fibo_evening, "RAW_PRICES_DIR", tmp_path / "raw")
    monkeypatch.setattr(fibo_evening, "pull_before_appending", lambda log: None)
    monkeypatch.setattr(fibo_evening, "materialize_adjustment_factors", lambda con: 0)
    monkeypatch.setattr(fibo_evening, "build_watchlist", _fake_build_watchlist)

    # already_notified/record_notification are left as the REAL functions
    # imported into fibo_evening -- their own dedup logic (kind=
    # "notification" events) is exactly what ITEM 4's "no duplicate
    # digest email" requirement needs to be tested for real, not stubbed
    # away. Redirecting notify.py's OWN append_event/read_events to the
    # shared tmp log is what makes that dedup operate against it instead
    # of the real data/fibo_live/v1/events.jsonl.
    monkeypatch.setattr(notify_module, "append_event", functools.partial(real_append_event, log_path=events_path))
    monkeypatch.setattr(notify_module, "read_events", functools.partial(real_read_events, log_path=events_path))

    sent_emails = []

    def fake_send_email(subject, body, log=print):
        sent_emails.append({"subject": subject, "body": body})
        return True

    monkeypatch.setattr(fibo_evening, "send_email", fake_send_email)

    # Pins assert_data_current's "today" to whichever date is driving the
    # CURRENT step of the simulation (set via state["as_of"] right before
    # each fibo_evening.main() call below) -- never real wall-clock
    # "today", which would make this test's pass/fail depend on which
    # actual calendar date it happens to run on.
    state = {"as_of": None}

    def fixed_as_of_assert_data_current(con, as_of=None, max_staleness_days=3):
        return real_assert_data_current(con, as_of=state["as_of"], max_staleness_days=max_staleness_days)

    monkeypatch.setattr(fibo_evening, "assert_data_current", fixed_as_of_assert_data_current)

    # The only network call in this whole simulation, and it never
    # actually reaches the network: real NSE 404s on a day nothing is
    # published, which is what load_bhavcopy_to_duckdb's REAL (not
    # faked) is_nse_holiday-based classification branches on. Any other
    # date reaching this means the pre-seeded fetch_log 'ok' row for
    # Monday didn't short-circuit as expected -- fail loudly, don't
    # silently let a real network call happen.
    def fake_fetch_raw_zip(trade_date, raw_dir, source=None, sleep_seconds=0.8):
        if trade_date == HOLIDAY_TUESDAY:
            raise NoDataForDate(f"simulated NSE 404 for {trade_date} -- no bhavcopy published")
        raise AssertionError(f"fetch_raw_zip must not be called for {trade_date} in this simulation")

    monkeypatch.setattr(prices_nse, "fetch_raw_zip", fake_fetch_raw_zip)

    # One shared events.jsonl, exactly like the real laptop (evening job)
    # and GitHub Actions (morning job) share via git.
    monkeypatch.setattr(fibo_evening, "append_event", functools.partial(real_append_event, log_path=events_path))
    monkeypatch.setattr(fibo_evening, "read_events", functools.partial(real_read_events, log_path=events_path))
    monkeypatch.setattr(fibo_morning, "append_event", functools.partial(real_append_event, log_path=events_path))
    monkeypatch.setattr(fibo_morning, "read_events", functools.partial(real_read_events, log_path=events_path))
    monkeypatch.setattr(fibo_morning, "record_session_status",
                         functools.partial(real_record_session_status, log_path=events_path))
    real_awc = fibo_morning.assert_watchlist_current
    monkeypatch.setattr(fibo_morning, "assert_watchlist_current",
                         functools.partial(real_awc, log_path=events_path))

    return {"events_path": events_path, "warehouse_path": warehouse_path, "state": state, "sent_emails": sent_emails}


def _run_evening(holiday_week, monkeypatch, requested_date, as_of):
    holiday_week["state"]["as_of"] = as_of
    monkeypatch.setattr(sys, "argv", ["fibo_evening.py", "--date", requested_date.isoformat()])
    fibo_evening.main()


def _boom_login():
    raise AssertionError("must not attempt to log in -- the freshness check should already have refused")


# --- ITEM 1 (now fixed) ------------------------------------------------

def test_monday_evening_watchlist_targets_wednesday_directly(holiday_week, monkeypatch):
    """ITEM 1, FIXED: next_trading_day is now holiday-aware up front, so
    Monday evening's run sees Tuesday's holiday in advance (via
    is_nse_holiday, not a reactive fetch_log check) and targets
    Wednesday directly. No stale Tuesday-targeting watchlist_run, and
    exactly one digest email -- for 2026-10-21, never for the holiday
    Tuesday itself."""
    _run_evening(holiday_week, monkeypatch, MONDAY, as_of=MONDAY)

    runs = fibo_morning.read_events(kind="watchlist_run")
    assert len(runs) == 1
    run = runs[0]
    assert run["as_of_date"] == str(MONDAY)
    assert run["target_trade_date"] == str(WEDNESDAY), (
        "next_trading_day must now be holiday-aware up front -- Monday evening's run should "
        "target Wednesday directly, not the holiday Tuesday."
    )

    sent = holiday_week["sent_emails"]
    assert len(sent) == 1, f"expected exactly one digest email, got {len(sent)}: {sent}"
    assert str(WEDNESDAY) in sent[0]["subject"]
    assert str(HOLIDAY_TUESDAY) not in sent[0]["subject"]


# --- ITEM 4 (now idempotent-skip, not a second watchlist) ---------------

def test_tuesday_evening_handles_holiday_cleanly_without_duplicating_the_watchlist(holiday_week, monkeypatch):
    """ITEM 4, UPDATED: Tuesday evening's run still confirms the holiday
    for REAL (fetch_log 'no_data' via the real is_nse_holiday path --
    the Bug #15 regression this guards against). But since Monday
    evening already produced the correct Wednesday-targeting watchlist,
    already_has_watchlist_run(Wednesday) now catches this run as
    idempotent and refuses to write a duplicate -- and since
    notify_watchlist_digest is only ever reached after a NEW
    watchlist_run is logged, no second digest email is sent either."""
    _run_evening(holiday_week, monkeypatch, MONDAY, as_of=MONDAY)
    assert len(fibo_morning.read_events(kind="watchlist_run")) == 1
    assert len(holiday_week["sent_emails"]) == 1  # Monday's own digest

    _run_evening(holiday_week, monkeypatch, HOLIDAY_TUESDAY, as_of=HOLIDAY_TUESDAY)

    con = get_connection(holiday_week["warehouse_path"])
    row = con.execute(
        "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [SOURCE_UDIFF, HOLIDAY_TUESDAY]
    ).fetchone()
    con.close()
    assert row is not None, "Tuesday's fetch attempt was never logged at all"
    assert row[0] == "no_data", (
        f"Tuesday's 404 must still be classified as a CONFIRMED holiday ('no_data'), not {row[0]!r}"
    )

    runs = fibo_morning.read_events(kind="watchlist_run")
    assert len(runs) == 1, f"Tuesday evening must NOT write a duplicate watchlist_run, got {len(runs)}: {runs}"
    assert runs[0]["target_trade_date"] == str(WEDNESDAY)

    assert len(holiday_week["sent_emails"]) == 1, (
        "the idempotent Tuesday-evening skip must not send a second digest email"
    )


# --- ITEM 3 (re-confirmed under the fix) ---------------------------------

def test_tuesday_morning_logs_non_trading_day_once_no_setup_rows(holiday_week, monkeypatch):
    """ITEM 3, re-confirmed under the fixed next_trading_day: since no
    watchlist_run ever targets the holiday Tuesday now (Monday's run
    already skips straight to Wednesday), assert_watchlist_current
    itself refuses first -- "no watchlist_run targets this date" --
    and login() is never even reached. log_refusal still classifies
    this correctly as NON_TRADING_DAY, not a plain REFUSED, because that
    classification depends only on is_non_trading_day(trade_date), not
    on which check happened to trigger the refusal. Deduped across the
    */15 cron firing repeatedly all morning; zero setup events."""
    _run_evening(holiday_week, monkeypatch, MONDAY, as_of=MONDAY)  # produces Wednesday's watchlist, not Tuesday's

    monkeypatch.setattr(fibo_morning, "login", _boom_login)

    for _ in range(3):  # simulates the */15 cron firing repeatedly all morning
        monkeypatch.setattr(sys, "argv", ["fibo_morning.py", "--date", HOLIDAY_TUESDAY.isoformat()])
        fibo_morning.main()

    session_events = fibo_morning.read_events(kind="session_status")
    assert len(session_events) == 1, f"expected exactly one deduped session_status event, got {session_events}"
    assert session_events[0]["status"] == NON_TRADING_DAY
    assert session_events[0]["trade_date"] == str(HOLIDAY_TUESDAY)
    assert "No watchlist_run event targets" in session_events[0]["reason"]

    assert fibo_morning.read_events(kind="setup") == []


# --- ITEM 2 (unaffected by the fix) --------------------------------------

def test_wednesday_morning_freshness_accepts_mondays_as_of_date(holiday_week, monkeypatch):
    """ITEM 2, isolated: a watchlist_run with as_of_date=Monday,
    target=Wednesday must pass Wednesday morning's freshness check, via
    previous_trading_day(Wednesday) correctly resolving to Monday
    because Tuesday is a confirmed NSE holiday -- using the REAL,
    unmocked is_nse_holiday (whichever calendar file is actually present
    on this machine), not a monkeypatched stand-in."""
    real_append_event("watchlist_run", {
        "run_id": "run-wed", "as_of_date": MONDAY, "target_trade_date": WEDNESDAY, "run_mode": "REPLAY",
        "n_universe": 1, "n_qualify": 1,
    }, log_path=holiday_week["events_path"])

    assert fibo_morning.previous_trading_day(WEDNESDAY) == MONDAY

    latest = fibo_morning.assert_watchlist_current(WEDNESDAY)
    assert latest["run_id"] == "run-wed"


# --- Full week, chained end to end ------------------------------------------

def test_full_holiday_week_end_to_end(holiday_week, monkeypatch):
    """All four steps in sequence, against the ONE shared events.jsonl,
    reproducing the actual week in order: Monday evening (now targets
    Wednesday directly) -> Tuesday morning (holiday, scheduled anyway,
    refuses as NON_TRADING_DAY with no watchlist at all) -> Tuesday
    evening (confirms the holiday for real, idempotent-skips rather
    than duplicating) -> Wednesday morning freshness check."""
    # Monday evening.
    _run_evening(holiday_week, monkeypatch, MONDAY, as_of=MONDAY)
    runs = fibo_morning.read_events(kind="watchlist_run")
    assert len(runs) == 1
    assert runs[0]["target_trade_date"] == str(WEDNESDAY)
    assert len(holiday_week["sent_emails"]) == 1

    # Tuesday morning -- the schedule fires anyway; no watchlist exists
    # for Tuesday at all now, so the freshness check itself refuses,
    # correctly classified as NON_TRADING_DAY.
    monkeypatch.setattr(fibo_morning, "login", _boom_login)
    monkeypatch.setattr(sys, "argv", ["fibo_morning.py", "--date", HOLIDAY_TUESDAY.isoformat()])
    fibo_morning.main()
    session_events = fibo_morning.read_events(kind="session_status")
    assert len(session_events) == 1
    assert session_events[0]["status"] == NON_TRADING_DAY
    assert fibo_morning.read_events(kind="setup") == []

    # Tuesday evening -- confirms the holiday for real (fetch_log
    # no_data), but the idempotency guard on target_trade_date=Wednesday
    # skips writing a duplicate watchlist and no second digest email.
    _run_evening(holiday_week, monkeypatch, HOLIDAY_TUESDAY, as_of=HOLIDAY_TUESDAY)
    runs = fibo_morning.read_events(kind="watchlist_run")
    assert len(runs) == 1, "Tuesday evening must not duplicate Monday's watchlist_run"
    assert len(holiday_week["sent_emails"]) == 1, "no second digest email on the idempotent Tuesday-evening skip"

    con = get_connection(holiday_week["warehouse_path"])
    row = con.execute(
        "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [SOURCE_UDIFF, HOLIDAY_TUESDAY]
    ).fetchone()
    con.close()
    assert row[0] == "no_data"

    # Wednesday morning -- freshness check against the SAME shared log.
    latest = fibo_morning.assert_watchlist_current(WEDNESDAY)
    assert latest["run_id"] == runs[0]["run_id"]


# --- next_trading_day's degraded fallback, explicitly tested -------------

def test_next_trading_day_degrades_to_reactive_check_and_warns_when_calendar_missing(tmp_path, monkeypatch):
    """A candidate day in a year no calendar covers (e.g. 2027 -- absent
    from the committed fallback as of this writing) must fall back to
    the OLD reactive fetch_log-only check, AND log a clear, visible
    warning every time it does -- a silent degradation would defeat the
    whole point of flagging this gap."""
    con = get_connection(tmp_path / "w.duckdb")
    friday_uncovered = dt.date(2027, 1, 1)
    con.execute("INSERT INTO fetch_log VALUES (?, ?, 'no_data', 0, now())", [SOURCE_UDIFF, friday_uncovered])

    def raise_for_2027(d):
        if d.year == 2027:
            raise HolidayCalendarMissing(f"no entry for {d.year}")
        return False

    monkeypatch.setattr(fibo_evening, "is_nse_holiday", raise_for_2027)
    warnings = []
    monkeypatch.setattr(fibo_evening, "log", lambda msg="": warnings.append(str(msg)))

    result = fibo_evening.next_trading_day(
        con, friday_uncovered - dt.timedelta(days=1), known_through=friday_uncovered
    )
    con.close()

    assert result == friday_uncovered + dt.timedelta(days=3), (
        "must still skip the confirmed-via-fetch_log holiday (Friday) and the weekend after it, "
        "landing on the following Monday"
    )
    assert any("cannot confirm" in w and str(friday_uncovered) in w for w in warnings), (
        f"expected a clear warning naming the uncovered date, got: {warnings}"
    )


def test_next_trading_day_treats_uncovered_year_as_ordinary_without_a_fetch_log_signal(tmp_path, monkeypatch):
    """Same degraded (calendar-missing) mode, but with nothing in
    fetch_log either -- must default to treating the day as an ordinary
    trading day (never silently skip it), the same stance this gap has
    always had."""
    con = get_connection(tmp_path / "w2.duckdb")
    monday_uncovered = dt.date(2027, 1, 4)  # not pre-seeded in fetch_log at all

    def raise_for_2027(d):
        if d.year == 2027:
            raise HolidayCalendarMissing(f"no entry for {d.year}")
        return False

    monkeypatch.setattr(fibo_evening, "is_nse_holiday", raise_for_2027)
    monkeypatch.setattr(fibo_evening, "log", lambda msg="": None)

    result = fibo_evening.next_trading_day(
        con, monday_uncovered - dt.timedelta(days=1), known_through=monday_uncovered
    )
    con.close()

    assert result == monday_uncovered
