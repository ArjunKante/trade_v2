"""Regression tests for src/fibo/auth.py's credential-safety guarantees.

The finding this file exists to guard against, confirmed by reading
SmartApi/smartConnect.py directly: on ANY API response with status=False,
the SDK's own code logs, at ERROR level,
`f"... Request: {params}, Response: {data}"` -- for generateSession,
`params` is the raw clientcode/password(MPIN)/totp -- via a `logzero`
logger that, by default, writes to a file (`logs/<date>/app.log`, relative
to CWD). `_neutralize_sdk_logger` must strip that logger's handlers before
any credential-bearing call, so nothing is ever written or printed
regardless of what the SDK tries to log.
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.auth import _neutralize_sdk_logger


def test_neutralize_strips_every_handler_and_disables_propagation(tmp_path):
    import logzero
    logzero.logfile(str(tmp_path / "some_path_that_would_normally_get_attached.log"))
    assert len(logzero.logger.handlers) > 0  # sanity: something WAS attached

    _neutralize_sdk_logger()

    assert all(isinstance(h, __import__("logging").NullHandler) for h in logzero.logger.handlers)
    assert logzero.logger.propagate is False


def test_neutralized_sdk_never_writes_credential_marker_on_a_real_failed_call(tmp_path, monkeypatch):
    """Forces a REAL failed request through the actual, unmodified
    SmartConnect._request code path (not a mocked-out logger) -- only the
    underlying `requests.request` HTTP call is faked, so the SDK's own
    error-handling and logging logic runs for real. A marker value stands
    in for a credential in the request params; asserts it never appears in
    any file anywhere under the test's isolated working directory."""
    marker = "MARKER_SECRET_9f8e7d6c5b4a3210_NOT_A_REAL_CREDENTIAL"

    monkeypatch.chdir(tmp_path)  # so the SDK's relative 'logs/' dir lands here, never the real repo

    from SmartApi import SmartConnect
    client = SmartConnect(api_key="dummy_key_for_test")
    _neutralize_sdk_logger()  # the exact call order production code uses (fibo.auth.login)

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.content = b'{"status": false, "message": "Invalid credentials", "errorcode": "AB1010", "data": null}'

    with patch("SmartApi.smartConnect.requests.request", return_value=fake_response):
        result = client.generateSession("DUMMY_CLIENT_CODE", marker, "123456")

    assert isinstance(result, dict)
    assert result.get("status") is False  # confirms the failure path (the leaky branch) actually ran

    leaked_files = []
    for dirpath, _dirnames, filenames in os.walk(tmp_path):
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                content = fpath.read_bytes()
            except OSError:
                continue
            if marker.encode() in content:
                leaked_files.append(str(fpath))
    assert leaked_files == [], f"credential marker leaked into: {leaked_files}"
