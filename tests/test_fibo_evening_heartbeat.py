"""src/fibo_live/heartbeat.py's ping_evening_heartbeat -- the evening
job's dead-man's-switch ping (OPERATIONS.md's "Evening job dead-man's
switch" section, PROJECT_CONTEXT.md Section 7 findings #4/#15).

Three things this must prove: (1) a missing env var is a soft no-op, not
a crash, (2) a successful HTTP call returns True, (3) ANY request
failure (network down, non-2xx, timeout) is caught and returns False,
never raised -- the whole point of this function is that it must never
be the thing that breaks a job it only exists to monitor.

No real network call is ever made -- requests.get is monkeypatched in
every test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fibo_live.heartbeat as heartbeat  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


@pytest.fixture(autouse=True)
def _no_real_dotenv(monkeypatch):
    # Prevent the real .env (with the real ping URL) from ever being read
    # by a test -- each test sets FIBO_EVENING_HEALTHCHECK_URL explicitly.
    monkeypatch.setattr(heartbeat, "load_dotenv", lambda *a, **k: None)


def test_missing_url_returns_false_and_does_not_raise(monkeypatch):
    monkeypatch.delenv("FIBO_EVENING_HEALTHCHECK_URL", raising=False)
    logged = []
    assert heartbeat.ping_evening_heartbeat(log=logged.append) is False
    assert any("not set" in m.lower() or "empty" in m.lower() for m in logged)


def test_successful_ping_returns_true(monkeypatch):
    monkeypatch.setenv("FIBO_EVENING_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return _FakeResponse(200)

    monkeypatch.setattr(heartbeat.requests, "get", fake_get)
    logged = []
    assert heartbeat.ping_evening_heartbeat(log=logged.append) is True
    assert calls == [("https://hc-ping.com/fake-uuid", heartbeat.PING_TIMEOUT_S)]
    # The URL itself must never be logged (it's a bearer-token-shaped secret).
    assert not any("fake-uuid" in m for m in logged)


def test_non_2xx_response_returns_false_not_raise(monkeypatch):
    monkeypatch.setenv("FIBO_EVENING_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")
    monkeypatch.setattr(heartbeat.requests, "get", lambda url, timeout: _FakeResponse(500))
    logged = []
    assert heartbeat.ping_evening_heartbeat(log=logged.append) is False
    assert any("HEARTBEAT NOT SENT" in m for m in logged)


def test_network_exception_returns_false_not_raise(monkeypatch):
    monkeypatch.setenv("FIBO_EVENING_HEALTHCHECK_URL", "https://hc-ping.com/fake-uuid")

    def raise_connection_error(url, timeout):
        raise requests.ConnectionError("simulated network-down failure")

    monkeypatch.setattr(heartbeat.requests, "get", raise_connection_error)
    logged = []
    assert heartbeat.ping_evening_heartbeat(log=logged.append) is False
    assert any("ConnectionError" in m for m in logged)
    # Exception message text must never be logged -- type name only.
    assert not any("simulated network-down" in m for m in logged)
