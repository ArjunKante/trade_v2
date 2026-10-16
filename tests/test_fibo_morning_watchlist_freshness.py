"""scripts/fibo_morning.py's assert_watchlist_current -- the
events.jsonl-only replacement for the old data_layer.staleness.
assert_data_current(warehouse) check, now that the morning job never
opens the warehouse (GitHub Actions migration).

Freshness is judged by the target_trade_date/as_of_date RELATIONSHIP
(does a watchlist_run exist targeting today, built from today's own
previous trading day), never by how many wall-clock hours ago it was
logged. An hours-based cutoff was the original rule here, and it was
wrong: the evening job runs once per trading night by design, so a
Friday-evening run targeting the following Monday is, correctly, ~63
hours old by the time Monday morning's job checks it -- any cutoff tight
enough to catch a real multi-day gap (BUGS.md Bug #13's meta-pattern)
also falsely refuses every single Monday. See
test_friday_evening_watchlist_is_valid_on_monday_morning below for the
regression this file now guards against.

Every test writes to its own tmp_path log file via the log_path override
-- never the real data/fibo_live/v1/events.jsonl.
"""
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fibo_morning  # noqa: E402

TRADE_DATE = dt.date(2026, 10, 14)  # a Wednesday -- previous trading day is an ordinary Tuesday, no weekend/holiday involved
FRIDAY_BEFORE_MONDAY = dt.date(2026, 10, 16)
MONDAY = dt.date(2026, 10, 19)  # confirmed (live, 2026-10-16) not an NSE holiday itself
THURSDAY_BEFORE_HOLIDAY_FRIDAY = dt.date(2026, 10, 15)


def _log_watchlist_run(log_path, target_trade_date, as_of_date, ts: dt.datetime | None = None, run_id="run-1"):
    ts = ts or dt.datetime.combine(as_of_date, dt.time(20, 0))
    event = {
        "event_id": f"evt-{run_id}", "ts": ts.isoformat(timespec="seconds"), "kind": "watchlist_run",
        "run_id": run_id, "as_of_date": str(as_of_date),
        "target_trade_date": str(target_trade_date), "run_mode": "REPLAY",
        "n_universe": 200, "n_qualify": 5,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def test_no_watchlist_run_at_all_is_refused(tmp_path):
    log_path = tmp_path / "events.jsonl"
    with pytest.raises(fibo_morning.StaleWatchlistError):
        fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)


def test_run_targeting_a_different_day_does_not_count(tmp_path):
    log_path = tmp_path / "events.jsonl"
    _log_watchlist_run(log_path, TRADE_DATE - dt.timedelta(days=1), TRADE_DATE - dt.timedelta(days=2))
    with pytest.raises(fibo_morning.StaleWatchlistError):
        fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)


def test_run_with_the_correct_as_of_date_passes(tmp_path):
    """Ordinary weekday case: Wednesday's watchlist built from Tuesday's
    close -- no weekend or holiday in the gap at all."""
    log_path = tmp_path / "events.jsonl"
    _log_watchlist_run(log_path, TRADE_DATE, TRADE_DATE - dt.timedelta(days=1), run_id="run-fresh")
    latest_run = fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)
    assert latest_run["run_id"] == "run-fresh"


def test_run_with_the_wrong_as_of_date_is_refused(tmp_path):
    """The actual BUGS.md Bug #13 shape this check must still catch: a
    watchlist_run DOES target today, but its data is from a week ago (a
    multi-day gap in the evening job), not from today's real previous
    trading day -- refused on the data relationship, not on elapsed
    time."""
    log_path = tmp_path / "events.jsonl"
    stale_as_of = TRADE_DATE - dt.timedelta(days=8)
    _log_watchlist_run(log_path, TRADE_DATE, stale_as_of)
    with pytest.raises(fibo_morning.StaleWatchlistError):
        fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)


def test_picks_the_latest_of_several_valid_runs_targeting_the_same_day(tmp_path):
    log_path = tmp_path / "events.jsonl"
    correct_as_of = TRADE_DATE - dt.timedelta(days=1)
    _log_watchlist_run(log_path, TRADE_DATE, correct_as_of,
                        ts=dt.datetime.combine(correct_as_of, dt.time(19, 0)), run_id="run-older")
    _log_watchlist_run(log_path, TRADE_DATE, correct_as_of,
                        ts=dt.datetime.combine(correct_as_of, dt.time(23, 0)), run_id="run-newer")
    latest_run = fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)
    assert latest_run["run_id"] == "run-newer"


def test_friday_evening_watchlist_is_valid_on_monday_morning(tmp_path):
    """THE regression this file exists to guard against: a Friday-
    evening run targeting the following Monday is, correctly, about 63
    wall-clock hours old by Monday 09:30 -- the old hours-based check
    would have refused this every single week. The target/as_of_date
    relationship must accept it."""
    log_path = tmp_path / "events.jsonl"
    _log_watchlist_run(log_path, MONDAY, FRIDAY_BEFORE_MONDAY,
                        ts=dt.datetime.combine(FRIDAY_BEFORE_MONDAY, dt.time(18, 30)), run_id="run-friday")
    latest_run = fibo_morning.assert_watchlist_current(MONDAY, log_path=log_path)
    assert latest_run["run_id"] == "run-friday"


def test_thursday_evening_watchlist_is_valid_on_monday_after_a_friday_holiday(tmp_path, monkeypatch):
    """A genuine NSE holiday falling on the Friday before a Monday: the
    evening job's own warehouse-based fetch_log check (outside this
    script) correctly skipped the holiday Friday and built Monday's
    watchlist from Thursday's close instead -- as_of_date=Thursday,
    target_trade_date=Monday. previous_trading_day must recognize
    Thursday as valid here, not demand Friday.

    is_nse_holiday is monkeypatched (not relying on the real
    data/raw/nse_cm_holidays.pkl) so this test is identical on a machine
    that has that file and on a GitHub Actions runner that doesn't."""
    log_path = tmp_path / "events.jsonl"
    friday = FRIDAY_BEFORE_MONDAY

    def fake_is_holiday(d):
        return d == friday

    monkeypatch.setattr(fibo_morning, "is_nse_holiday", fake_is_holiday)

    _log_watchlist_run(log_path, MONDAY, THURSDAY_BEFORE_HOLIDAY_FRIDAY,
                        ts=dt.datetime.combine(THURSDAY_BEFORE_HOLIDAY_FRIDAY, dt.time(18, 30)), run_id="run-thursday")
    latest_run = fibo_morning.assert_watchlist_current(MONDAY, log_path=log_path)
    assert latest_run["run_id"] == "run-thursday"


def test_friday_holiday_run_is_rejected_without_the_holiday_confirmed(tmp_path, monkeypatch):
    """The flip side, and the known residual gap this change carries
    over rather than introduces: if the holiday calendar is NOT
    available (HolidayCalendarMissing -- the real situation on a GitHub
    Actions runner today, since data/raw/nse_cm_holidays.pkl is not
    committed), previous_trading_day falls back to weekend-only and
    computes Friday, not Thursday, as the expected as_of_date -- so a
    Thursday-sourced watchlist is (incorrectly, but knowingly) refused
    in that degraded mode. Documents the gap; does not pretend it's
    fixed."""
    log_path = tmp_path / "events.jsonl"

    def raise_missing(d):
        raise fibo_morning.HolidayCalendarMissing("no calendar on this runner")

    monkeypatch.setattr(fibo_morning, "is_nse_holiday", raise_missing)

    _log_watchlist_run(log_path, MONDAY, THURSDAY_BEFORE_HOLIDAY_FRIDAY,
                        ts=dt.datetime.combine(THURSDAY_BEFORE_HOLIDAY_FRIDAY, dt.time(18, 30)), run_id="run-thursday")
    with pytest.raises(fibo_morning.StaleWatchlistError):
        fibo_morning.assert_watchlist_current(MONDAY, log_path=log_path)


def test_previous_trading_day_skips_weekend_only_when_no_holiday(monkeypatch):
    monkeypatch.setattr(fibo_morning, "is_nse_holiday", lambda d: False)
    assert fibo_morning.previous_trading_day(MONDAY) == FRIDAY_BEFORE_MONDAY


def test_previous_trading_day_skips_a_confirmed_weekday_holiday_too(monkeypatch):
    friday = FRIDAY_BEFORE_MONDAY
    monkeypatch.setattr(fibo_morning, "is_nse_holiday", lambda d: d == friday)
    assert fibo_morning.previous_trading_day(MONDAY) == THURSDAY_BEFORE_HOLIDAY_FRIDAY
