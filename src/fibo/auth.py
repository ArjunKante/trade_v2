"""Angel One SmartAPI authentication -- the ONLY place in src/fibo/ that
touches login credentials. Data-only: authenticates a session for reading
market data; nothing in src/fibo/ imports or calls an order endpoint (see
FIBO.md / PREREGISTRATION_FIBO.md Section 0).

CREDENTIAL SAFETY, no exceptions, per instruction:
  - never print, log, echo, or display any credential, TOTP code, JWT, or
    session token -- not in output, logs, errors, or test failures
  - never run commands whose output would show them
  - redact tokens in any exception message before it is shown

THE THING THIS MODULE SPECIFICALLY EXISTS TO PREVENT: the `smartapi-python`
SDK's own logger (`logzero`) attaches a FILE handler
(`logs/<date>/app.log`, relative to CWD) inside `SmartConnect.__init__`,
and on ANY failed API call it logs at ERROR level with
`f"... Request: {params}, Response: {data}"` -- for `generateSession`,
`params` is `{"clientcode": ..., "password": <MPIN>, "totp": <TOTP>}`,
i.e. the SDK writes the raw MPIN and TOTP to a local file in cleartext on
a failed login. This is a defect in the third-party library, confirmed by
reading its source (`SmartApi/smartConnect.py`), not something this
project's own code does. `_neutralize_sdk_logger` strips every handler
from that logger immediately after `SmartConnect()` is constructed and
before `generateSession()` is ever called, so nothing the SDK tries to
log is written or printed, regardless of what it contains.

On any failure, only a short, regex-redacted status string is ever
returned -- never the SDK's raw response dict, never a raw exception
message. On success, the authenticated client is returned for reuse (it
holds tokens as instance attributes, same as the SDK's own design); this
module never itself prints or logs that client or its attributes.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
REQUIRED_KEYS = ["ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_MPIN", "ANGEL_TOTP_SECRET"]

# Defensive redaction for anything that ends up in a status string: long
# token-like strings (JWTs etc, 20+ url-safe chars) and bare 4-8 digit runs
# (MPIN/TOTP shape) -- applied even though the intended code path never
# constructs a status string FROM a credential, as a second layer.
_TOKEN_LIKE = re.compile(r"[A-Za-z0-9_\-\.]{20,}")
_DIGIT_CODE = re.compile(r"(?<!\w)\d{4,8}(?!\w)")


def _redact(text: str) -> str:
    text = _TOKEN_LIKE.sub("[REDACTED]", text)
    text = _DIGIT_CODE.sub("[REDACTED]", text)
    return text[:200]


def _neutralize_sdk_logger() -> None:
    """Strip every handler the smartapi-python SDK's logzero logger has
    attached (see module docstring). Must be called AFTER SmartConnect()
    is constructed and BEFORE generateSession() is ever called."""
    import logzero
    for handler in list(logzero.logger.handlers):
        logzero.logger.removeHandler(handler)
    logzero.logger.addHandler(logging.NullHandler())
    logzero.logger.propagate = False


class LoginResult:
    def __init__(self, ok: bool, status: str, client=None):
        self.ok = ok
        self.status = status  # "OK", or a short redacted failure code -- never a token
        self.client = client  # authenticated SmartConnect instance, or None on failure


def login() -> LoginResult:
    """Load .env, authenticate once against Angel One SmartAPI, return a
    LoginResult. Everything that could conceivably touch a credential
    value lives inside this one try/except so nothing escapes unredacted."""
    try:
        load_dotenv(ENV_PATH, override=False)
        missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
        if missing:
            return LoginResult(False, f"MISSING_ENV:{','.join(missing)}")

        from SmartApi import SmartConnect
        import pyotp

        client = SmartConnect(api_key=os.environ["ANGEL_API_KEY"])
        _neutralize_sdk_logger()  # MUST happen before generateSession -- see module docstring

        totp_code = pyotp.TOTP(os.environ["ANGEL_TOTP_SECRET"]).now()
        result = client.generateSession(os.environ["ANGEL_CLIENT_CODE"], os.environ["ANGEL_MPIN"], totp_code)
        totp_code = None  # discard; never referenced again

        if isinstance(result, dict) and result.get("status") is True:
            return LoginResult(True, "OK", client)

        error_code = result.get("errorcode", "UNKNOWN") if isinstance(result, dict) else "UNKNOWN"
        return LoginResult(False, _redact(str(error_code)))
    except Exception as e:
        return LoginResult(False, _redact(f"{type(e).__name__}: {e}"))
