"""Email alerts for the Fibo live jobs -- Gmail SMTP with an app password
(free, no new account: smtp.gmail.com:587 + STARTTLS, logging in with an
app-specific password instead of the real Gmail password). Credentials
load from .env the same way src/fibo/auth.py's Angel credentials do, and
are held to the exact same rule: never printed, logged, or echoed, by
anyone, anywhere, including in a send failure.

FAIL SOFT, always: send_email() catches every exception itself and
returns False rather than raising -- a broken SMTP connection (no
network, a wrong app password, Gmail rate-limiting) must never stop a
job from recording its own events. On failure only the exception TYPE
name is logged, never its message -- an SMTP auth error can echo back
part of the server conversation, and there is no reason to risk any of
that reaching a log file.

IDEMPOTENCY: already_notified()/record_notification() store a durable
"notification" event in the SAME append-only events.jsonl every other
live event lives in (src/fibo_live/eventlog.py) -- a notification is
"sent" only once send_email() returns True, so a run that crashes or a
send that fails leaves nothing recorded and the next run naturally
retries it. Dedup key is (notif_type, trade_date, entity_id); entity_id
is None for jobs not about one specific stock (e.g. evening-skipped).

DISCLAIMER: every email body carries the same paper-trading disclaimer
this project puts on anything performance- or action-shaped
(PREREGISTRATION_FIBO.md Section 0 / FIBO_FINDINGS.md) -- a reader
skimming only the email must never come away thinking a real order was
placed or that this strategy is proven.
"""
from __future__ import annotations

import datetime as dt
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from fibo_live.eventlog import append_event, read_events

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

DISCLAIMER = (
    "PAPER TRADING ONLY. No order is placed. The Fibo strategy passed a "
    "corrected re-test of an already-read window, not a clean sealed test."
)


def send_email(subject: str, body: str, log: Callable[[str], None] = print) -> bool:
    """Best-effort send -- returns True on success, False on ANY failure.
    Never raises. The disclaimer is appended here, once, so no caller can
    forget it."""
    load_dotenv(ENV_PATH, override=False)
    sender = os.environ.get("FIBO_EMAIL_FROM")
    app_password = os.environ.get("FIBO_EMAIL_APP_PASSWORD")
    to = os.environ.get("FIBO_EMAIL_TO")
    missing = [k for k, v in [("FIBO_EMAIL_FROM", sender), ("FIBO_EMAIL_APP_PASSWORD", app_password),
                               ("FIBO_EMAIL_TO", to)] if not v]
    if missing:
        log(f"EMAIL NOT SENT: missing .env key(s): {', '.join(missing)}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(f"{body}\n\n{DISCLAIMER}\n")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls(context=context)
            server.login(sender, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        # Exception TYPE only -- never str(e) -- see module docstring.
        log(f"EMAIL NOT SENT: {type(e).__name__} talking to {SMTP_HOST}:{SMTP_PORT}")
        return False


def already_notified(notif_type: str, trade_date: dt.date, entity_id: str | None = None) -> bool:
    for e in read_events(kind="notification"):
        if e.get("notif_type") != notif_type or e.get("trade_date") != str(trade_date):
            continue
        if e.get("entity_id") == entity_id:
            return True
    return False


def record_notification(notif_type: str, trade_date: dt.date, entity_id: str | None = None, **extra) -> dict:
    return append_event("notification", {
        "notif_type": notif_type, "trade_date": trade_date, "entity_id": entity_id, **extra,
    })
