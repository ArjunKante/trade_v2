"""src/fibo_live/session_status.py: record_session_status/
already_logged_session_status -- the durable (events.jsonl) evidence
trail for whether a scheduled run itself refused to do anything, and
why. Every test writes to its own tmp_path log file via the log_path
override -- never the real data/fibo_live/v1/events.jsonl.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live.session_status import (  # noqa: E402
    NON_TRADING_DAY,
    REFUSED,
    already_logged_session_status,
    record_session_status,
)

TRADE_DATE = dt.date(2026, 10, 20)


def test_records_a_new_refusal(tmp_path):
    log_path = tmp_path / "events.jsonl"
    event = record_session_status(TRADE_DATE, "morning", REFUSED, "no watchlist", run_mode="LIVE",
                                    log_path=log_path)
    assert event is not None
    assert event["status"] == REFUSED
    assert event["trade_date"] == str(TRADE_DATE)
    assert event["reason"] == "no watchlist"
    assert event["run_mode"] == "LIVE"
    assert event["kind"] == "session_status"


def test_identical_reason_is_not_logged_twice(tmp_path):
    """The actual point of this module: a 15-minute schedule hitting the
    SAME refusal all morning must write the event once, not nine times."""
    log_path = tmp_path / "events.jsonl"
    first = record_session_status(TRADE_DATE, "morning", REFUSED, "no watchlist", log_path=log_path)
    second = record_session_status(TRADE_DATE, "morning", REFUSED, "no watchlist", log_path=log_path)

    assert first is not None
    assert second is None  # deduped -- nothing new appended
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_a_different_reason_the_same_day_is_logged_separately(tmp_path):
    """Not deduped against a DIFFERENT reason -- e.g. a watchlist refusal
    earlier in the morning, then a login failure on a later re-run, are
    two distinct, both worth-recording facts."""
    log_path = tmp_path / "events.jsonl"
    record_session_status(TRADE_DATE, "morning", REFUSED, "no watchlist", log_path=log_path)
    second = record_session_status(TRADE_DATE, "morning", REFUSED, "login failed", log_path=log_path)

    assert second is not None
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_the_same_reason_on_a_different_day_is_logged_separately(tmp_path):
    log_path = tmp_path / "events.jsonl"
    record_session_status(TRADE_DATE, "morning", REFUSED, "no watchlist", log_path=log_path)
    second = record_session_status(TRADE_DATE + dt.timedelta(days=1), "morning", REFUSED, "no watchlist",
                                     log_path=log_path)

    assert second is not None


def test_already_logged_session_status_matches_on_date_session_and_reason(tmp_path):
    log_path = tmp_path / "events.jsonl"
    assert already_logged_session_status(TRADE_DATE, "morning", "no watchlist", log_path=log_path) is False
    record_session_status(TRADE_DATE, "morning", NON_TRADING_DAY, "weekend", log_path=log_path)
    assert already_logged_session_status(TRADE_DATE, "morning", "weekend", log_path=log_path) is True
    assert already_logged_session_status(TRADE_DATE, "morning", "no watchlist", log_path=log_path) is False
    assert already_logged_session_status(TRADE_DATE, "evening", "weekend", log_path=log_path) is False
