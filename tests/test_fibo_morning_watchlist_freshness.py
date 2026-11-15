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
import functools
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fibo_morning  # noqa: E402
from fibo_live.eventlog import read_events as real_read_events  # noqa: E402

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


def test_two_valid_runs_for_the_same_target_select_the_latest_by_timestamp_not_the_first(tmp_path, monkeypatch):
    """Reproduces the real shape found 2026-11-15 (FIBO_FINDINGS.md
    Section 15): the forward test's first evening (2026-10-08) logged two
    watchlist_run events targeting 2026-10-09, both with the same
    as_of_date -- the first computed against a panel still mid-ingestion
    (stale swing values for one entity), the second (56 minutes later,
    same evening) against the completed one (corrected values). Both
    assert_watchlist_current and latest_watchlist select by
    max(..., key=ts) -- "latest run wins", not "first match" -- so the
    corrected run is what the morning job actually uses. This is the
    answer to "which one does the morning job select": latest by
    timestamp, confirmed here, not assumed from reading the code."""
    log_path = tmp_path / "events.jsonl"
    as_of = dt.date(2026, 10, 8)
    target = dt.date(2026, 10, 9)

    _log_watchlist_run(log_path, target, as_of, ts=dt.datetime(2026, 10, 8, 22, 46, 5), run_id="stale-run")
    _log_watchlist_run(log_path, target, as_of, ts=dt.datetime(2026, 10, 8, 23, 42, 16), run_id="corrected-run")

    def _watchlist_row(run_id, swing_high):
        return {
            "event_id": f"w-{run_id}", "ts": dt.datetime(2026, 10, 8, 22, 0).isoformat(), "kind": "watchlist",
            "run_id": run_id, "entity_id": "E1", "symbol": "VMM", "qualifies": True, "swing_high": swing_high,
        }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(_watchlist_row("stale-run", 115.4)) + "\n")
        f.write(json.dumps(_watchlist_row("corrected-run", 108.23)) + "\n")

    latest_run = fibo_morning.assert_watchlist_current(target, log_path=log_path)
    assert latest_run["run_id"] == "corrected-run", (
        "assert_watchlist_current must select the LATEST valid run by timestamp, not the first logged"
    )

    # latest_watchlist (unlike assert_watchlist_current) takes no log_path
    # parameter -- it always reads via the module-level `read_events`
    # name, so pointing it at this test's tmp_path means monkeypatching
    # that name directly, same pattern used throughout this test suite.
    monkeypatch.setattr(fibo_morning, "read_events", functools.partial(real_read_events, log_path=log_path))
    watchlist = fibo_morning.latest_watchlist(target)

    assert len(watchlist) == 1
    assert watchlist.iloc[0]["run_id"] == "corrected-run"
    assert watchlist.iloc[0]["swing_high"] == 108.23, (
        "the morning job must use the corrected run's rows, not the stale first run's"
    )


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


def test_friday_holiday_run_raises_holiday_calendar_missing_rather_than_degrading(tmp_path, monkeypatch):
    """The flip side, and a gap this project used to carry rather than
    fix: if the holiday calendar is NOT available (HolidayCalendarMissing
    -- the real situation on a GitHub Actions runner for an uncovered
    year, since data/raw/nse_cm_holidays.pkl is not committed and the
    fallback JSON covers fewer years), previous_trading_day USED TO fall
    back to weekend-only and silently compute the wrong expected as_of_date
    -- a Thursday-sourced watchlist would be wrongly refused, or worse,
    a wrong one could be wrongly accepted, with no visible signal either
    way. 2026-11-15 (OPERATIONS.md, PROJECT_CONTEXT.md Section 7 finding
    #15): this now REFUSES LOUDLY instead -- HolidayCalendarMissing
    propagates out of assert_watchlist_current uncaught, and main() (see
    test_holiday_week_oct2026.py's own coverage) turns that into a durable
    REFUSED session_status event, not a silent wrong guess."""
    log_path = tmp_path / "events.jsonl"

    def raise_missing(d):
        raise fibo_morning.HolidayCalendarMissing("no calendar on this runner")

    monkeypatch.setattr(fibo_morning, "is_nse_holiday", raise_missing)

    _log_watchlist_run(log_path, MONDAY, THURSDAY_BEFORE_HOLIDAY_FRIDAY,
                        ts=dt.datetime.combine(THURSDAY_BEFORE_HOLIDAY_FRIDAY, dt.time(18, 30)), run_id="run-thursday")
    with pytest.raises(fibo_morning.HolidayCalendarMissing):
        fibo_morning.assert_watchlist_current(MONDAY, log_path=log_path)


def test_previous_trading_day_skips_weekend_only_when_no_holiday(monkeypatch):
    monkeypatch.setattr(fibo_morning, "is_nse_holiday", lambda d: False)
    assert fibo_morning.previous_trading_day(MONDAY) == FRIDAY_BEFORE_MONDAY


def test_previous_trading_day_skips_a_confirmed_weekday_holiday_too(monkeypatch):
    friday = FRIDAY_BEFORE_MONDAY
    monkeypatch.setattr(fibo_morning, "is_nse_holiday", lambda d: d == friday)
    assert fibo_morning.previous_trading_day(MONDAY) == THURSDAY_BEFORE_HOLIDAY_FRIDAY
