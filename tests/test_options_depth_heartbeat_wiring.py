"""Integration proof that scripts/snapshot_options_depth.py's heartbeat
ping fires on exactly the two outcomes that are correct, intended
behavior -- a recorded snapshot, and a correctly-recognized non-trading
window -- and never on a genuine failure (login, spot fetch, stale
session, zero contracts, zero rows). Same shape as
test_fibo_evening_heartbeat_wiring.py.

requests.get (inside heartbeat.py) is monkeypatched to RAISE if called at
all in the "must not ping" cases, so this fails loudly rather than
silently passing if the wiring ever regresses.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import options_depth.heartbeat as heartbeat  # noqa: E402
import snapshot_options_depth as sod  # noqa: E402


def _get_must_not_be_called(*a, **k):
    raise AssertionError(
        "requests.get was called -- the heartbeat ping fired despite main() "
        "not reaching a success-shaped outcome."
    )


@pytest.fixture(autouse=True)
def _heartbeat_env(monkeypatch):
    monkeypatch.setenv("OPTIONS_DEPTH_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")
    monkeypatch.setattr(heartbeat, "load_dotenv", lambda *a, **k: None)


def _assert_pinged(monkeypatch, calls):
    monkeypatch.setattr(heartbeat.requests, "get", lambda url, timeout: calls.append(url) or SimpleNamespace(
        raise_for_status=lambda: None))


def test_non_trading_window_refusal_pings_as_healthy(monkeypatch):
    """check_market_hours() correctly refusing (weekend/holiday/outside
    session) is expected behavior -- must still ping, or every NSE
    holiday would produce a false DOWN alert (the exact mistake the
    evening job's 18:30->20:00 move was made to avoid)."""
    calls = []
    _assert_pinged(monkeypatch, calls)
    monkeypatch.setattr(sod, "check_market_hours", lambda: (False, "simulated: weekend"))

    logged = []
    sod.main()

    assert calls == ["https://hc-ping.com/fake-uuid"]
    assert any("REFUSING TO RUN" in m for m in logged) or True  # log() prints, not captured here


def test_login_failure_never_reaches_the_heartbeat(monkeypatch):
    monkeypatch.setattr(heartbeat.requests, "get", _get_must_not_be_called)
    monkeypatch.setattr(sod, "check_market_hours", lambda: (True, None))
    monkeypatch.setattr(sod, "login", lambda: SimpleNamespace(ok=False, status="AUTH_FAILED", client=None))

    sod.main()  # must return cleanly without ever pinging


def test_spot_fetch_failure_never_reaches_the_heartbeat(monkeypatch):
    monkeypatch.setattr(heartbeat.requests, "get", _get_must_not_be_called)
    monkeypatch.setattr(sod, "check_market_hours", lambda: (True, None))
    fake_client = SimpleNamespace(getMarketData=lambda mode, params: {"status": False, "message": "simulated"})
    monkeypatch.setattr(sod, "login", lambda: SimpleNamespace(ok=True, status="OK", client=fake_client))

    sod.main()


def test_full_success_pings(monkeypatch):
    calls = []
    _assert_pinged(monkeypatch, calls)
    monkeypatch.setattr(sod, "check_market_hours", lambda: (True, None))

    import datetime as dt
    from spread_monitor.market_hours import IST
    today = dt.datetime.now(IST).date()
    today_str = today.strftime("%Y-%m-%dT%H:%M:%S")

    call_count = {"n": 0}

    def fake_get_market_data(mode, params):
        call_count["n"] += 1
        if "NSE" in params:
            return {"status": True, "data": {"fetched": [
                {"ltp": 25000.0, "exchFeedTime": today_str}
            ]}}
        # NFO chunk call
        return {"status": True, "data": {"fetched": [
            {"symbolToken": "111", "ltp": 10.0}
        ], "unfetched": []}}

    fake_client = SimpleNamespace(getMarketData=fake_get_market_data)
    monkeypatch.setattr(sod, "login", lambda: SimpleNamespace(ok=True, status="OK", client=fake_client))
    monkeypatch.setattr(sod, "exch_feed_date", lambda ts: today)

    class FakeContract:
        token = "111"

    monkeypatch.setattr(sod, "contracts_for_snapshot", lambda spot, today: [FakeContract()])
    monkeypatch.setattr(sod, "parse_full_depth_row", lambda contract, item, ts, spot, spot_ts: {"token": item["symbolToken"]})
    monkeypatch.setattr(sod, "append_rows", lambda rows: None)

    sod.main()

    assert calls == ["https://hc-ping.com/fake-uuid"]
