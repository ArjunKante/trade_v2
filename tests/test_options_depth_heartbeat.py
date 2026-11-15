"""src/options_depth/heartbeat.py's ping_options_depth_heartbeat -- the
options-depth collector's dead-man's-switch ping (OPERATIONS.md's
"Evening job dead-man's switch" section names this collector as the next
candidate; this is that fix). Deliberately the same shape as
test_fibo_evening_heartbeat.py -- same module, duplicated not imported,
same test coverage duplicated to match.

No real network call is ever made -- requests.get is monkeypatched in
every test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import options_depth.heartbeat as heartbeat  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


@pytest.fixture(autouse=True)
def _no_real_dotenv(monkeypatch):
    monkeypatch.setattr(heartbeat, "load_dotenv", lambda *a, **k: None)


def test_missing_url_returns_false_and_does_not_raise(monkeypatch):
    monkeypatch.delenv("OPTIONS_DEPTH_HEALTHCHECK_URL", raising=False)
    logged = []
    assert heartbeat.ping_options_depth_heartbeat(log=logged.append) is False
    assert any("not set" in m.lower() or "empty" in m.lower() for m in logged)


def test_successful_ping_returns_true(monkeypatch):
    monkeypatch.setenv("OPTIONS_DEPTH_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return _FakeResponse(200)

    monkeypatch.setattr(heartbeat.requests, "get", fake_get)
    logged = []
    assert heartbeat.ping_options_depth_heartbeat(log=logged.append) is True
    assert calls == [("https://hc-ping.com/fake-uuid", heartbeat.PING_TIMEOUT_S)]
    assert not any("fake-uuid" in m for m in logged)


def test_non_2xx_response_returns_false_not_raise(monkeypatch):
    monkeypatch.setenv("OPTIONS_DEPTH_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")
    monkeypatch.setattr(heartbeat.requests, "get", lambda url, timeout: _FakeResponse(500))
    logged = []
    assert heartbeat.ping_options_depth_heartbeat(log=logged.append) is False
    assert any("HEARTBEAT NOT SENT" in m for m in logged)


def test_network_exception_returns_false_not_raise(monkeypatch):
    monkeypatch.setenv("OPTIONS_DEPTH_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")

    def raise_connection_error(url, timeout):
        raise requests.ConnectionError("simulated network-down failure")

    monkeypatch.setattr(heartbeat.requests, "get", raise_connection_error)
    logged = []
    assert heartbeat.ping_options_depth_heartbeat(log=logged.append) is False
    assert any("ConnectionError" in m for m in logged)
    assert not any("simulated network-down" in m for m in logged)
