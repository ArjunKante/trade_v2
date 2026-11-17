"""scripts/fibo_morning.py's durable refusal logging: is_non_trading_day,
log_refusal, and main() itself when it refuses to run. Every test
monkeypatches fibo_morning's own append_event/read_events/
record_session_status names to a tmp_path log -- never the real
data/fibo_live/v1/events.jsonl.
"""
import functools
import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fibo_live.eventlog import append_event as real_append_event, read_events as real_read_events  # noqa: E402
from fibo_live.session_status import NON_TRADING_DAY, REFUSED  # noqa: E402
from fibo_live.session_status import record_session_status as real_record_session_status  # noqa: E402

import fibo_morning  # noqa: E402

real_assert_watchlist_current = fibo_morning.assert_watchlist_current

MONDAY = date(2026, 10, 19)  # confirmed (live) not an NSE holiday -- the real, upcoming first automatic run
SATURDAY = date(2026, 10, 17)
ORDINARY_WEEKDAY = date(2026, 10, 13)  # Tuesday, confirmed (live) not an NSE holiday


@pytest.fixture
def events_log(tmp_path, monkeypatch):
    log_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(fibo_morning, "append_event",
                         functools.partial(real_append_event, log_path=log_path))
    monkeypatch.setattr(fibo_morning, "read_events",
                         functools.partial(real_read_events, log_path=log_path))
    monkeypatch.setattr(fibo_morning, "record_session_status",
                         functools.partial(real_record_session_status, log_path=log_path))
    # UPDATE 2026-11-15: assert_watchlist_current's `log_path=None` now
    # resolves fibo_live.config.EVENTS_LOG fresh at call time rather than
    # binding it once at import (BUGS.md Bug #24) -- conftest.py's
    # autouse _redirect_events_log fixture would catch this on its own
    # now. Kept as an explicit rebind anyway, so this fixture's tmp_path
    # is shared consistently across append_event/read_events/
    # record_session_status/assert_watchlist_current within THIS test,
    # independent of whatever conftest.py does.
    monkeypatch.setattr(fibo_morning, "assert_watchlist_current",
                         functools.partial(real_assert_watchlist_current, log_path=log_path))
    # UPDATE 2026-11-18: log_refusal now calls notify_morning_refused,
    # which calls the REAL send_email -- and this laptop's own .env has
    # real, working Gmail credentials. Without this, every test below
    # that exercises a REFUSED refusal would attempt a real SMTP send on
    # every pytest run. Never real network in a test (conftest.py's own
    # rule) -- mocked here, once, for every test in this file, the same
    # way test_fibo_evening_heartbeat_wiring.py mocks the evening job's
    # equivalent call.
    monkeypatch.setattr(fibo_morning, "send_email", lambda *a, **k: False)
    return log_path


def _session_status_events(log_path):
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [e for e in events if e.get("kind") == "session_status"]


# --- is_non_trading_day -------------------------------------------------

def test_is_non_trading_day_true_for_a_weekend():
    assert fibo_morning.is_non_trading_day(SATURDAY) is True


def test_is_non_trading_day_false_for_an_ordinary_weekday():
    assert fibo_morning.is_non_trading_day(ORDINARY_WEEKDAY) is False


def test_is_non_trading_day_true_for_a_monkeypatched_weekday_holiday(monkeypatch):
    monkeypatch.setattr(fibo_morning, "is_nse_holiday", lambda d: d == ORDINARY_WEEKDAY)
    assert fibo_morning.is_non_trading_day(ORDINARY_WEEKDAY) is True


def test_is_non_trading_day_false_when_calendar_missing_on_a_weekday(monkeypatch):
    """An unverifiable day is never assumed to be a holiday -- it just
    means the eventual refusal logs as REFUSED, not NON_TRADING_DAY."""
    def raise_missing(d):
        raise fibo_morning.HolidayCalendarMissing("no calendar here")
    monkeypatch.setattr(fibo_morning, "is_nse_holiday", raise_missing)
    assert fibo_morning.is_non_trading_day(ORDINARY_WEEKDAY) is False


# --- log_refusal ---------------------------------------------------------

def test_log_refusal_records_refused_on_an_ordinary_weekday(events_log):
    fibo_morning.log_refusal(ORDINARY_WEEKDAY, "LIVE", "no watchlist_run targets this date")
    events = _session_status_events(events_log)
    assert len(events) == 1
    assert events[0]["status"] == REFUSED
    assert events[0]["trade_date"] == str(ORDINARY_WEEKDAY)
    assert events[0]["session"] == "morning"
    assert events[0]["run_mode"] == "LIVE"


def test_log_refusal_records_non_trading_day_on_a_weekend(events_log):
    fibo_morning.log_refusal(SATURDAY, "REPLAY", "no watchlist_run targets this date")
    events = _session_status_events(events_log)
    assert len(events) == 1
    assert events[0]["status"] == NON_TRADING_DAY


def test_log_refusal_dedupes_the_same_reason_across_repeated_calls(events_log):
    """The actual point: a 15-minute schedule hitting the same refusal
    all morning must log it once, not nine times."""
    for _ in range(9):
        fibo_morning.log_refusal(ORDINARY_WEEKDAY, "LIVE", "no watchlist_run targets this date")
    events = _session_status_events(events_log)
    assert len(events) == 1


def test_log_refusal_logs_a_different_reason_separately(events_log):
    fibo_morning.log_refusal(ORDINARY_WEEKDAY, "LIVE", "no watchlist_run targets this date")
    fibo_morning.log_refusal(ORDINARY_WEEKDAY, "LIVE", "Angel One login FAILED")
    events = _session_status_events(events_log)
    assert len(events) == 2


# --- main(): the actual Monday-with-no-watchlist case -------------------

def test_main_refuses_and_logs_durably_when_monday_has_no_watchlist(events_log, monkeypatch):
    """The exact shape that motivated this change: an ordinary Monday,
    no watchlist_run logged for it at all (the evening job never ran, or
    hasn't yet). main() must refuse WITHOUT ever calling login(), and
    the refusal must be durably recorded (not just printed) so it
    survives the run."""
    monkeypatch.setattr(sys, "argv", ["fibo_morning.py", "--date", str(MONDAY)])

    def boom_login():
        raise AssertionError("must not attempt to log in when the watchlist check already refused")
    monkeypatch.setattr(fibo_morning, "login", boom_login)

    fibo_morning.main()  # must not raise

    events = _session_status_events(events_log)
    assert len(events) == 1
    assert events[0]["status"] == REFUSED  # Monday 2026-10-19 is not a holiday
    assert events[0]["trade_date"] == str(MONDAY)
    assert "No watchlist_run event targets" in events[0]["reason"]


def test_main_classifies_a_weekend_no_watchlist_refusal_as_non_trading_day(events_log, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["fibo_morning.py", "--date", str(SATURDAY)])

    def boom_login():
        raise AssertionError("must not attempt to log in on a confirmed non-trading day")
    monkeypatch.setattr(fibo_morning, "login", boom_login)

    fibo_morning.main()

    events = _session_status_events(events_log)
    assert len(events) == 1
    assert events[0]["status"] == NON_TRADING_DAY


def test_main_run_twice_on_the_same_missing_watchlist_logs_once(events_log, monkeypatch):
    """Simulates the real schedule: the */15 cron re-fires every 15
    minutes all morning, hitting the identical missing-watchlist refusal
    each time."""
    monkeypatch.setattr(sys, "argv", ["fibo_morning.py", "--date", str(MONDAY)])
    monkeypatch.setattr(fibo_morning, "login", lambda: (_ for _ in ()).throw(
        AssertionError("must not attempt to log in")))

    fibo_morning.main()
    fibo_morning.main()

    events = _session_status_events(events_log)
    assert len(events) == 1


# --- notify_morning_refused -----------------------------------------------
# A REFUSED morning must email -- an independent signal from healthchecks.io,
# which a dashboard click can silence without the underlying problem being
# fixed (found 2026-11-17/18, the evening-job collision incident).

def test_log_refusal_emails_on_refused(events_log, monkeypatch):
    sent = []
    monkeypatch.setattr(fibo_morning, "send_email",
                         lambda subject, body, log=print: sent.append((subject, body)) or True)
    fibo_morning.log_refusal(ORDINARY_WEEKDAY, "LIVE", "No watchlist_run event targets this date")
    assert len(sent) == 1
    subject, body = sent[0]
    assert str(ORDINARY_WEEKDAY) in subject
    assert "No watchlist_run event targets this date" in body


def test_log_refusal_does_not_email_on_non_trading_day(events_log, monkeypatch):
    sent = []
    monkeypatch.setattr(fibo_morning, "send_email",
                         lambda subject, body, log=print: sent.append((subject, body)) or True)
    fibo_morning.log_refusal(SATURDAY, "REPLAY", "no watchlist_run targets this date")
    assert sent == []  # a holiday/weekend is expected, not alarming -- no email


def test_log_refusal_email_dedupes_across_repeated_calls(events_log, monkeypatch):
    """The same point as the session_status dedup test, for the email
    path specifically: a 15-minute schedule hitting the same refusal all
    morning must send one email, not nine."""
    sent = []
    monkeypatch.setattr(fibo_morning, "send_email",
                         lambda subject, body, log=print: sent.append((subject, body)) or True)
    for _ in range(9):
        fibo_morning.log_refusal(ORDINARY_WEEKDAY, "LIVE", "no watchlist_run targets this date")
    assert len(sent) == 1


def test_log_refusal_email_retries_next_call_if_send_failed(events_log, monkeypatch):
    """send_email failing (no network, bad credentials) must not be
    treated as "notified" -- the next refusal should try again, same
    fail-soft/retry contract notify_evening_skipped already has."""
    monkeypatch.setattr(fibo_morning, "send_email", lambda *a, **k: False)
    fibo_morning.log_refusal(ORDINARY_WEEKDAY, "LIVE", "no watchlist_run targets this date")
    sent = []
    monkeypatch.setattr(fibo_morning, "send_email",
                         lambda subject, body, log=print: sent.append((subject, body)) or True)
    fibo_morning.log_refusal(ORDINARY_WEEKDAY, "LIVE", "no watchlist_run targets this date")
    assert len(sent) == 1  # the first (failed) attempt was not recorded as sent
