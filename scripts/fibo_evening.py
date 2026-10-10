"""EVENING JOB -- run after market close. PAPER ONLY, data-only: this
script never places, modifies, or cancels an order, and imports no Angel
One order endpoint (it never even imports Angel One at all -- the daily
bar comes from the NSE bhavcopy archive, the same source every other
hypothesis in this warehouse uses).

    python scripts/fibo_evening.py [--date YYYY-MM-DD]

Steps (PREREGISTRATION_FIBO.md Section 3a-3c, frozen rules; Section 1's
top-200 universe amendment):
  1. Incrementally fetch today's (or --date's) daily bar for the whole
     market from NSE bhavcopy and append it to prices_eod (idempotent --
     a day already loaded is skipped, no re-download).
  2. Re-materialize adjustment_factors (needed so today's adjusted close
     exists before any swing/zone computation reads it).
  3. For every top-200 universe member: Alligator uptrend, most recent
     confirmed swing + 2xATR filter, golden zone, and tomorrow's scale
     factor (src/fibo_live/watchlist.py).
  4. Log the full universe, one event per stock plus one run-summary
     event, append-only, tagged with a fresh run_id -- this is what the
     morning job reads. The log's own timestamp (now, well before
     tomorrow's 09:15 open) is what makes the forward test honest: the
     watchlist is fixed before any price for that date is known.

Prints how many stocks qualify (PREREGISTRATION_FIBO.md's uptrend AND
valid-swing-passing-2xATR AND known-scale-factor definition, src/fibo_live/
watchlist.py's module docstring).

UNATTENDED (Windows Task Scheduler): every log() line also goes to
data/fibo_live/scheduler.log (src/fibo_live/scheduler_support.py) since a
scheduled run has no terminal. main() is wrapped so an unhandled exception
-- dead network on the bhavcopy fetch, anything -- is caught, logged with
its traceback, and swallowed: the process always exits 0. Idempotent
against an accidental double-fire for the same trade_date (checks for an
existing watchlist_run event first) on top of the staleness guard below
and load_bhavcopy_to_duckdb's own existing-row skip.
"""
import argparse
import datetime as dt
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.adjustment import materialize_adjustment_factors
from data_layer.db import get_connection
from data_layer.prices_nse import load_bhavcopy_to_duckdb
from data_layer.staleness import assert_data_current, StaleDataError

from fibo_live.clock import detect_run_mode
from fibo_live.config import RAW_PRICES_DIR, TOP_N, WAREHOUSE_DB
from fibo_live.eventlog import append_event, read_events
from fibo_live.notify import already_notified, record_notification, send_email
from fibo_live.scheduler_support import make_logger, run_unattended
from fibo_live.watchlist import build_watchlist

SERIES_INCLUDE = ["EQ", "BE", "BZ"]  # same set config.yaml's nse_bhavcopy.series_include uses

log = make_logger()


def already_has_watchlist_run(trade_date: dt.date) -> bool:
    return any(e.get("as_of_date") == str(trade_date) for e in read_events(kind="watchlist_run"))


def notify_evening_skipped(trade_date: dt.date, short_reason: str, detail: str) -> None:
    """Silence from a scheduled job is indistinguishable from success --
    this is the one alert that exists purely to say "nothing happened,
    and here is why" rather than to report a result. Deduped per
    trade_date so a second same-day run (manual re-run, a Task Scheduler
    catch-up fire) hitting the same refusal doesn't resend."""
    if already_notified("evening_skipped", trade_date):
        return
    subject = f"FIBO EVENING SKIPPED - {short_reason}"
    body = f"The evening job for {trade_date} did not produce a watchlist.\n\nReason: {detail}"
    if send_email(subject, body, log=log):
        record_notification("evening_skipped", trade_date, reason=short_reason)
    else:
        log("  evening-skipped email NOT sent -- will retry next run")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD, default: today")
    args = parser.parse_args()
    trade_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()

    # Detected once, from the clock (src/fibo_live/clock.py) -- this job
    # runs after close by design, so it is expected to read REPLAY almost
    # always; stamped for consistency with the morning job's events, and
    # because "almost always" is not "always" (e.g. a late --date catch-up).
    run_mode = detect_run_mode(trade_date)

    log(f"=== FIBO EVENING JOB -- {trade_date} (run_mode={run_mode}) ===")

    # Idempotency: a once-daily scheduled trigger should never fire twice
    # in a row for the same trade_date, but "Run task as soon as possible
    # after a scheduled start is missed" or a manual re-run both can. A
    # second run recomputing the same day's watchlist wastes work rather
    # than causing wrong data (build_watchlist is pure, re-fetch is
    # separately idempotent), but it would still mint a redundant
    # watchlist_run + 200 watchlist events every time -- refuse instead.
    if already_has_watchlist_run(trade_date):
        log(f"watchlist_run already logged for {trade_date} -- skipping (idempotent). "
            f"Nothing else to do.")
        return

    con = get_connection(WAREHOUSE_DB)

    # Checked BEFORE today's own fetch, against whatever the warehouse's
    # latest trade_date already was -- this is what catches a multi-day
    # ingestion gap (BUGS.md Bug #13): fetching just today's bar and
    # computing across the hole would otherwise produce a plausible-looking
    # but wrong watchlist with no error anywhere.
    try:
        prior_latest = assert_data_current(con)
        log(f"Freshness check OK: warehouse's latest trading day was {prior_latest} before this run.")
    except StaleDataError as e:
        log(f"REFUSING TO RUN: {e}")
        notify_evening_skipped(trade_date, "stale data", str(e))
        con.close()
        return

    log(f"Fetching bhavcopy for {trade_date} (incremental -- skipped if already loaded)...")
    n_rows = load_bhavcopy_to_duckdb(con, trade_date, RAW_PRICES_DIR, series_include=SERIES_INCLUDE)
    status = con.execute(
        "SELECT status FROM fetch_log WHERE trade_date = ? ORDER BY attempted_at DESC LIMIT 1", [trade_date]
    ).fetchone()
    status = status[0] if status else None
    log(f"  fetch_log status: {status}, new rows this call: {n_rows}")

    existing = con.execute("SELECT COUNT(*) FROM prices_eod WHERE trade_date = ?", [trade_date]).fetchone()[0]
    if existing == 0:
        reason = f"No bhavcopy data for {trade_date} (holiday, weekend, or not yet published)"
        log(f"{reason} -- no watchlist written. Nothing else to do.")
        notify_evening_skipped(trade_date, "missing bhavcopy", reason)
        con.close()
        return

    log("Re-materializing adjustment_factors...")
    n_factors = materialize_adjustment_factors(con)
    log(f"  {n_factors} rows")

    log(f"Computing top-{TOP_N} watchlist as of {trade_date} close...")
    watchlist = build_watchlist(con, trade_date, top_n=TOP_N)
    con.close()

    run_id = str(uuid.uuid4())
    for _, r in watchlist.iterrows():
        append_event("watchlist", {"run_id": run_id, "as_of_date": trade_date, "run_mode": run_mode, **r.to_dict()})

    n_universe = len(watchlist)
    n_qualify = int(watchlist["qualifies"].sum()) if n_universe else 0
    append_event("watchlist_run", {
        "run_id": run_id, "as_of_date": trade_date, "run_mode": run_mode,
        "n_universe": n_universe, "n_qualify": n_qualify,
    })

    log(f"\n=== {n_universe} universe members logged, run_id={run_id} ===")
    log(f"=== {n_qualify} stocks QUALIFY for tomorrow's watchlist "
        f"(uptrend AND valid 2xATR swing AND known scale factor) ===")
    if n_qualify:
        qualifying = watchlist[watchlist["qualifies"]][["symbol", "rank", "golden_zone_low", "golden_zone_high"]]
        log(qualifying.to_string(index=False))


if __name__ == "__main__":
    run_unattended("FIBO EVENING JOB", main, log)
