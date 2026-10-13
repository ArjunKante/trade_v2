"""scripts/fibo_morning.py's assert_watchlist_current -- the
events.jsonl-only replacement for the old data_layer.staleness.
assert_data_current(warehouse) check, now that the morning job never
opens the warehouse (GitHub Actions migration). Every test writes to its
own tmp_path log file via the log_path override -- never the real
data/fibo_live/v1/events.jsonl.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fibo_live.eventlog import append_event  # noqa: E402
from spread_monitor.market_hours import IST  # noqa: E402

import fibo_morning  # noqa: E402

TRADE_DATE = dt.date(2026, 10, 14)


def _log_watchlist_run(log_path, target_trade_date, ts: dt.datetime, run_id="run-1"):
    # append_event always stamps its OWN real ts; to control the ts this
    # test actually checks against, write the line directly rather than
    # through append_event.
    import json
    event = {
        "event_id": "evt-1", "ts": ts.isoformat(timespec="seconds"), "kind": "watchlist_run",
        "run_id": run_id, "as_of_date": str(target_trade_date - dt.timedelta(days=1)),
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
    _log_watchlist_run(log_path, TRADE_DATE - dt.timedelta(days=1), dt.datetime.now(IST))
    with pytest.raises(fibo_morning.StaleWatchlistError):
        fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)


def test_fresh_run_targeting_today_passes(tmp_path):
    log_path = tmp_path / "events.jsonl"
    recent = dt.datetime.now(IST) - dt.timedelta(hours=10)  # last night's evening job
    _log_watchlist_run(log_path, TRADE_DATE, recent, run_id="run-fresh")
    latest_run = fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)
    assert latest_run["run_id"] == "run-fresh"


def test_run_older_than_max_staleness_is_refused(tmp_path):
    log_path = tmp_path / "events.jsonl"
    stale = dt.datetime.now(IST) - dt.timedelta(hours=40)  # evening job missed a night
    _log_watchlist_run(log_path, TRADE_DATE, stale)
    with pytest.raises(fibo_morning.StaleWatchlistError):
        fibo_morning.assert_watchlist_current(TRADE_DATE, max_staleness_hours=36.0, log_path=log_path)


def test_naive_pre_fix_ts_is_still_treated_as_ist(tmp_path):
    """Events logged before eventlog.py's own IST fix have a naive ts --
    must still be read as IST wall time, not misinterpreted as UTC or
    the test-runner's local clock."""
    log_path = tmp_path / "events.jsonl"
    naive_recent = (dt.datetime.now(IST) - dt.timedelta(hours=5)).replace(tzinfo=None)
    _log_watchlist_run(log_path, TRADE_DATE, naive_recent)
    latest_run = fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)
    assert latest_run["target_trade_date"] == str(TRADE_DATE)


def test_picks_the_latest_of_several_runs_targeting_the_same_day(tmp_path):
    log_path = tmp_path / "events.jsonl"
    now = dt.datetime.now(IST)
    _log_watchlist_run(log_path, TRADE_DATE, now - dt.timedelta(hours=20), run_id="run-older")
    _log_watchlist_run(log_path, TRADE_DATE, now - dt.timedelta(hours=5), run_id="run-newer")
    latest_run = fibo_morning.assert_watchlist_current(TRADE_DATE, log_path=log_path)
    assert latest_run["run_id"] == "run-newer"
