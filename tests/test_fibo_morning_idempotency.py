"""scripts/fibo_morning.py's idempotency across phase1_setups/
watch_for_triggers/resolve_outcomes: once a stock has a terminal setup
(SETUP_ON or SETUP_OFF) logged for the day, a later run must never
re-fetch its opening range, and only SETUP_ON stocks are ever considered
for a trigger-watch or outcome-resolution fetch. A run where every
watchlist stock is already resolved for the day must make NO Angel One
candle-fetch call at all -- that is what "exits within seconds" actually
means here, not a timing assertion (which would be flaky); a BoomClient
that raises if getCandleData is ever called is the faithful way to prove
it.

Every test monkeypatches fibo_morning's own `append_event`/`read_events`
names (the ones phase1_setups/watch_for_triggers/etc. actually call) to a
tmp_path log -- never the real data/fibo_live/v1/events.jsonl.
"""
import functools
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fibo_live.eventlog import append_event as real_append_event, read_events as real_read_events  # noqa: E402

import fibo_morning  # noqa: E402

TRADE_DATE = date(2026, 10, 14)


class BoomClient:
    """Standing in for the Angel One client: raises if a candle fetch is
    ever attempted. Any test using this must never see that exception --
    it proves the already-resolved/already-terminal stock was never
    re-fetched."""

    def getCandleData(self, params):
        raise AssertionError(f"must not fetch candle data: {params}")


@pytest.fixture
def events_log(tmp_path, monkeypatch):
    log_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(fibo_morning, "append_event",
                         functools.partial(real_append_event, log_path=log_path))
    monkeypatch.setattr(fibo_morning, "read_events",
                         functools.partial(real_read_events, log_path=log_path))
    return log_path


def _watchlist_row(entity_id, symbol, rank):
    return {
        "entity_id": entity_id, "symbol": symbol, "rank": rank,
        "golden_zone_low": 100.0, "golden_zone_high": 110.0,
        "swing_high": 120.0, "scale_factor": 1.0,
    }


def test_setup_off_stock_is_not_refetched(events_log):
    """A stock already logged SETUP_OFF today must be skipped entirely --
    no token resolution, no candle fetch."""
    fibo_morning.append_event("setup", {
        "entity_id": "E1", "symbol": "SYM1", "trade_date": TRADE_DATE, "rank": 1,
        "run_mode": "LIVE", "status": "SETUP_OFF", "orb_high": 105.0, "orb_low": 101.0,
        "zone_low_raw": 100.0, "zone_high_raw": 110.0, "swing_high_raw": 120.0, "setup_on": False,
    })
    watchlist = pd.DataFrame([_watchlist_row("E1", "SYM1", 1)])

    result = fibo_morning.phase1_setups(BoomClient(), watchlist, TRADE_DATE, "LIVE")

    assert len(result) == 1
    assert result.iloc[0]["status"] == "SETUP_OFF"


def test_setup_on_stock_is_not_refetched_either(events_log):
    """Same as above for a terminal SETUP_ON -- the ORB result is cached
    and re-used, never re-fetched, even though this stock IS still being
    watched for a trigger."""
    fibo_morning.append_event("setup", {
        "entity_id": "E1", "symbol": "SYM1", "trade_date": TRADE_DATE, "rank": 1,
        "run_mode": "LIVE", "status": "SETUP_ON", "orb_high": 105.0, "orb_low": 101.0,
        "zone_low_raw": 100.0, "zone_high_raw": 110.0, "swing_high_raw": 120.0, "setup_on": True,
        "provisional_entry": 105.0, "stop": 101.0, "provisional_target": 115.0, "provisional_qty": 10,
    })
    watchlist = pd.DataFrame([_watchlist_row("E1", "SYM1", 1)])

    result = fibo_morning.phase1_setups(BoomClient(), watchlist, TRADE_DATE, "LIVE")

    assert len(result) == 1
    assert result.iloc[0]["status"] == "SETUP_ON"


def test_fetch_failed_is_not_terminal_and_is_retried(events_log, monkeypatch):
    """FETCH_FAILED must NOT satisfy the already-logged skip -- it is the
    one status that is retried on the next run (unlike SETUP_ON/OFF)."""
    fibo_morning.append_event("setup", {
        "entity_id": "E1", "symbol": "SYM1", "trade_date": TRADE_DATE, "rank": 1,
        "run_mode": "LIVE", "status": "FETCH_FAILED", "error": "rate limited", "setup_on": None,
    })
    watchlist = pd.DataFrame([_watchlist_row("E1", "SYM1", 1)])
    monkeypatch.setattr(fibo_morning, "resolve_tokens_for_rows", lambda rows: {"E1": "tok-1"})

    retried = {"called": False}

    def fake_fetch_with_retry(client, token, start, end, interval, throttle_seconds=None):
        retried["called"] = True
        return [[TRADE_DATE.isoformat(), 101.0, 105.0, 100.0, 103.0, 1000]], None

    monkeypatch.setattr(fibo_morning, "fetch_candle_with_retry", fake_fetch_with_retry)

    fibo_morning.phase1_setups(BoomClient(), watchlist, TRADE_DATE, "LIVE")

    assert retried["called"] is True


def test_a_fully_resolved_run_makes_no_angel_one_call_at_all(events_log):
    """The actual "nothing left to do" scenario: every watchlist stock
    already has a terminal setup for today (e.g. the 2026-10-14 run --
    all 16 stocks ended SETUP_OFF). phase1_setups must not even resolve
    tokens, let alone fetch a candle -- resolve_tokens_for_rows is left
    unpatched here deliberately, so a regression that calls it anyway
    would hit the network and fail the test for the right reason."""
    for i in range(1, 4):
        fibo_morning.append_event("setup", {
            "entity_id": f"E{i}", "symbol": f"SYM{i}", "trade_date": TRADE_DATE, "rank": i,
            "run_mode": "LIVE", "status": "SETUP_OFF", "orb_high": 105.0, "orb_low": 101.0,
            "zone_low_raw": 100.0, "zone_high_raw": 110.0, "swing_high_raw": 120.0, "setup_on": False,
        })
    watchlist = pd.DataFrame([_watchlist_row(f"E{i}", f"SYM{i}", i) for i in range(1, 4)])

    result = fibo_morning.phase1_setups(BoomClient(), watchlist, TRADE_DATE, "LIVE")

    assert len(result) == 3
    assert (result["status"] == "SETUP_OFF").all()


def test_watch_for_triggers_ignores_setup_off_stocks(events_log):
    """Only SETUP_ON stocks are ever considered for a trigger-watch
    fetch -- a SETUP_OFF stock must never reach fetch_candle_with_retry."""
    setups = pd.DataFrame([{
        "entity_id": "E1", "symbol": "SYM1", "rank": 1, "trade_date": TRADE_DATE,
        "status": "SETUP_OFF", "setup_on": False,
    }])

    fibo_morning.watch_for_triggers(BoomClient(), setups, TRADE_DATE, "LIVE")  # must not raise


def test_watch_for_triggers_skips_a_stock_already_triggered(events_log):
    """A SETUP_ON stock that already has today's trigger event logged
    must not be re-checked -- no candle fetch for it either."""
    fibo_morning.append_event("trigger", {
        "entity_id": "E1", "symbol": "SYM1", "trade_date": TRADE_DATE, "run_mode": "LIVE",
        "entry_ts": "2026-10-14T09:44:00", "entry_price": 106.0, "stop": 101.0, "target": 115.0, "qty": 10,
    })
    setups = pd.DataFrame([{
        "entity_id": "E1", "symbol": "SYM1", "rank": 1, "trade_date": TRADE_DATE,
        "status": "SETUP_ON", "setup_on": True, "orb_high": 105.0, "orb_low": 101.0,
        "swing_high_raw": 120.0,
    }])

    fibo_morning.watch_for_triggers(BoomClient(), setups, TRADE_DATE, "LIVE")  # must not raise


def test_resolve_outcomes_ignores_setup_off_stocks(events_log):
    """SETUP_OFF stocks are never resolved against 1-minute bars --
    resolve_outcomes must return immediately without a candle fetch."""
    setups = pd.DataFrame([{
        "entity_id": "E1", "symbol": "SYM1", "rank": 1, "trade_date": TRADE_DATE,
        "status": "SETUP_OFF", "setup_on": False,
    }])

    fibo_morning.resolve_outcomes(BoomClient(), setups, TRADE_DATE, "LIVE")  # must not raise


def test_resolve_outcomes_skips_a_stock_already_resolved(events_log):
    """A SETUP_ON stock that already has today's outcome event logged
    must not be re-resolved -- no 1-minute-bar fetch for it."""
    fibo_morning.append_event("outcome", {
        "entity_id": "E1", "symbol": "SYM1", "trade_date": TRADE_DATE, "rank": 1,
        "triggered": False, "run_mode": "LIVE",
    })
    setups = pd.DataFrame([{
        "entity_id": "E1", "symbol": "SYM1", "rank": 1, "trade_date": TRADE_DATE,
        "status": "SETUP_ON", "setup_on": True,
    }])

    fibo_morning.resolve_outcomes(BoomClient(), setups, TRADE_DATE, "LIVE")  # must not raise


def test_end_to_end_nothing_left_to_do_run_never_touches_the_client(events_log):
    """The full 2026-10-14-after-it-already-ran shape: every stock
    terminal SETUP_OFF, no triggers, nothing pending. Chaining all three
    phases against a BoomClient proves the whole "nothing left to do"
    path -- not just one function in isolation -- never calls
    getCandleData, which is what makes such a run finish in seconds."""
    for i in range(1, 17):
        fibo_morning.append_event("setup", {
            "entity_id": f"E{i}", "symbol": f"SYM{i}", "trade_date": TRADE_DATE, "rank": i,
            "run_mode": "LIVE", "status": "SETUP_OFF", "orb_high": 105.0, "orb_low": 101.0,
            "zone_low_raw": 100.0, "zone_high_raw": 110.0, "swing_high_raw": 120.0, "setup_on": False,
        })
    watchlist = pd.DataFrame([_watchlist_row(f"E{i}", f"SYM{i}", i) for i in range(1, 17)])

    client = BoomClient()
    setups = fibo_morning.phase1_setups(client, watchlist, TRADE_DATE, "LIVE")
    fibo_morning.watch_for_triggers(client, setups, TRADE_DATE, "LIVE")
    fibo_morning.resolve_outcomes(client, setups, TRADE_DATE, "LIVE")

    assert len(setups) == 16
    assert (setups["status"] == "SETUP_OFF").all()
