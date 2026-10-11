"""EVENING JOB -- run after market close. PAPER ONLY, data-only: this
script never places, modifies, or cancels an order, and imports no Angel
One order endpoint (it never even imports Angel One at all -- the daily
bar comes from the NSE bhavcopy archive, the same source every other
hypothesis in this warehouse uses).

    python scripts/fibo_evening.py [--date YYYY-MM-DD]

Steps (PREREGISTRATION_FIBO.md Section 3a-3c, frozen rules; Section 1's
top-200 universe amendment):
  1. Incrementally fetch the daily bar for the whole market from NSE
     bhavcopy, starting at today's (or --date's) calendar date and
     walking backward one day at a time until one is actually published
     (idempotent -- a day already loaded is skipped, no re-download).
     This is what makes a manual run on a weekend or a holiday -- when
     "today" has no bhavcopy at all -- still find the latest real trading
     day's close instead of exiting with nothing to do (the scheduled
     Monday 18:30 run was never affected: it always finds data for its
     own calendar day on the first try). The watchlist is then computed
     for the NEXT trading day after whatever day that data turns out to
     be, not for "today" or "--date" literally.
  2. Re-materialize adjustment_factors (needed so that day's adjusted
     close exists before any swing/zone computation reads it).
  3. For every top-200 universe member: Alligator uptrend, most recent
     confirmed swing + 2xATR filter, golden zone, and the next trading
     day's scale factor (src/fibo_live/watchlist.py).
  4. Log the full universe, one event per stock plus one run-summary
     event, append-only, tagged with a fresh run_id -- this is what the
     morning job reads. The log's own timestamp (now, well before the
     next trading day's 09:15 open) is what makes the forward test
     honest: the watchlist is fixed before any price for that date is
     known.

Prints how many stocks qualify (PREREGISTRATION_FIBO.md's uptrend AND
valid-swing-passing-2xATR AND known-scale-factor definition, src/fibo_live/
watchlist.py's module docstring).

UNATTENDED (Windows Task Scheduler): every log() line also goes to
data/fibo_live/scheduler.log (src/fibo_live/scheduler_support.py) since a
scheduled run has no terminal. main() is wrapped so an unhandled exception
-- dead network on the bhavcopy fetch, anything -- is caught, logged with
its traceback, and swallowed: the process always exits 0. Idempotent
against an accidental double-fire targeting the same next trading day
(checks for an existing watchlist_run event first) on top of the
staleness guard below and load_bhavcopy_to_duckdb's own existing-row skip.
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


def next_trading_day(con, d: dt.date, known_through: dt.date) -> dt.date:
    """Next trading day after `d`: skips Saturday/Sunday, and also skips any
    day up to `known_through` that this run's own backward walk (or an
    earlier run's) already confirmed has no published bhavcopy -- a real
    NSE weekday holiday, like 2026-10-09 (a Friday) with nothing published.
    No NSE holiday calendar exists anywhere in this project (fibo_live/
    clock.py's docstring; config.py's EX_DATE_LOOKAHEAD_DAYS take the same
    stance), so beyond `known_through` -- a day that hasn't happened yet --
    there is no way to know about a holiday in advance; the weekend-only
    heuristic is all that's left there, consistent with that same known,
    flagged gap. Only used for the idempotency guard below and the report
    line; the watchlist itself is always computed from `data_date`, the
    actual latest day with published bhavcopy, never from this."""
    nxt = d + dt.timedelta(days=1)
    while True:
        if nxt.weekday() >= 5:  # Saturday=5, Sunday=6
            nxt += dt.timedelta(days=1)
            continue
        if nxt <= known_through:
            no_data = con.execute(
                "SELECT 1 FROM fetch_log WHERE trade_date = ? AND status = 'no_data' LIMIT 1", [nxt]
            ).fetchone()
            if no_data is not None:
                nxt += dt.timedelta(days=1)
                continue
        return nxt


def already_has_watchlist_run(target_trade_date: dt.date) -> bool:
    """Keyed on the NEXT trading day the watchlist is FOR (target_trade_date),
    not on the data date it was computed from (as_of_date) -- a weekend
    re-run with no new bhavcopy published resolves to the same data_date and
    hence the same target_trade_date as the original run, and must be
    recognized as the same idempotent unit of work rather than minting a
    second watchlist_run for what is, from the next trading day's point of
    view, an identical result.

    A run that has since been marked superseded (a "watchlist_run_correction"
    event naming its run_id -- e.g. BUGS.md's 2026-10-09 fetch-failure-
    cached-as-holiday bug, which made an earlier run compute this exact
    target from a stale, Friday-less data panel) does NOT count here: a
    genuine correction must be allowed to produce a fresh run for the same
    target_trade_date, not get refused as a false "idempotent" duplicate of
    the very run it is replacing."""
    runs = [e for e in read_events(kind="watchlist_run") if e.get("target_trade_date") == str(target_trade_date)]
    if not runs:
        return False
    superseded_run_ids = {e["supersedes_run_id"] for e in read_events(kind="watchlist_run_correction")}
    return any(r["run_id"] not in superseded_run_ids for r in runs)


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
    requested_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()

    log(f"=== FIBO EVENING JOB -- requested {requested_date} ===")

    con = get_connection(WAREHOUSE_DB)

    # Checked BEFORE any fetch below, against whatever the warehouse's
    # latest trade_date already was -- this is what catches a multi-day
    # ingestion gap (BUGS.md Bug #13): walking back from requested_date and
    # computing from whatever we eventually find would otherwise mask a
    # genuinely stalled feed behind a plausible-looking but wrong watchlist.
    # It also hands us `prior_latest`, which the walk-back loop below uses
    # as its floor -- that date is already known to have data.
    try:
        prior_latest = assert_data_current(con)
        log(f"Freshness check OK: warehouse's latest trading day was {prior_latest} before this run.")
    except StaleDataError as e:
        log(f"REFUSING TO RUN: {e}")
        notify_evening_skipped(requested_date, "stale data", str(e))
        con.close()
        return

    # Find the latest trading day that actually HAS published bhavcopy data,
    # starting at requested_date (today, or --date) and walking backward one
    # calendar day at a time. On an ordinary weekday evening run this exits
    # on its first iteration, exactly like the old single-fetch code. On a
    # weekend or holiday manual run, requested_date has nothing published,
    # so this keeps trying the prior day until it finds one -- bounded by
    # prior_latest, which the freshness check above already guarantees has
    # data, so the loop always terminates with a real data_date.
    data_date = None
    candidate = requested_date
    while True:
        log(f"Fetching bhavcopy for {candidate} (incremental -- skipped if already loaded)...")
        n_rows = load_bhavcopy_to_duckdb(con, candidate, RAW_PRICES_DIR, series_include=SERIES_INCLUDE)
        status = con.execute(
            "SELECT status FROM fetch_log WHERE trade_date = ? ORDER BY attempted_at DESC LIMIT 1", [candidate]
        ).fetchone()
        status = status[0] if status else None
        log(f"  fetch_log status: {status}, new rows this call: {n_rows}")

        existing = con.execute("SELECT COUNT(*) FROM prices_eod WHERE trade_date = ?", [candidate]).fetchone()[0]
        if existing > 0:
            data_date = candidate
            break
        if candidate <= prior_latest:
            data_date = prior_latest
            break
        log(f"  No bhavcopy for {candidate} (holiday or weekend) -- trying the prior calendar day.")
        candidate -= dt.timedelta(days=1)

    target_trade_date = next_trading_day(con, data_date, known_through=requested_date)
    # Detected once, from the clock (src/fibo_live/clock.py), against the
    # actual data date rather than requested_date -- this job runs after
    # close by design, so it is expected to read REPLAY almost always;
    # stamped for consistency with the morning job's events.
    run_mode = detect_run_mode(data_date)
    log(f"Latest completed trading day with data: {data_date} -- "
        f"computing the watchlist for the next trading day, {target_trade_date} (run_mode={run_mode}).")

    # Idempotency: a once-daily scheduled trigger should never fire twice in
    # a row for the same target trading day, but "Run task as soon as
    # possible after a scheduled start is missed" or a manual re-run (e.g.
    # once on Saturday, again on Sunday, both resolving to the same Friday
    # data_date) both can. A second run recomputing the same watchlist
    # wastes work rather than causing wrong data (build_watchlist is pure,
    # re-fetch is separately idempotent), but it would still mint a
    # redundant watchlist_run + 200 watchlist events every time -- refuse
    # instead.
    if already_has_watchlist_run(target_trade_date):
        log(f"watchlist_run already logged targeting {target_trade_date} -- skipping (idempotent). "
            f"Nothing else to do.")
        con.close()
        return

    log("Re-materializing adjustment_factors...")
    n_factors = materialize_adjustment_factors(con)
    log(f"  {n_factors} rows")

    log(f"Computing top-{TOP_N} watchlist as of {data_date} close...")
    watchlist = build_watchlist(con, data_date, top_n=TOP_N)
    con.close()

    run_id = str(uuid.uuid4())
    for _, r in watchlist.iterrows():
        append_event("watchlist", {
            "run_id": run_id, "as_of_date": data_date, "target_trade_date": target_trade_date,
            "run_mode": run_mode, **r.to_dict(),
        })

    n_universe = len(watchlist)
    n_qualify = int(watchlist["qualifies"].sum()) if n_universe else 0
    append_event("watchlist_run", {
        "run_id": run_id, "as_of_date": data_date, "target_trade_date": target_trade_date, "run_mode": run_mode,
        "n_universe": n_universe, "n_qualify": n_qualify,
    })

    log(f"\n=== {n_universe} universe members logged, run_id={run_id} ===")
    log(f"=== {n_qualify} stocks QUALIFY for {target_trade_date}'s watchlist "
        f"(uptrend AND valid 2xATR swing AND known scale factor) ===")
    if n_qualify:
        qualifying = watchlist[watchlist["qualifies"]][["symbol", "rank", "golden_zone_low", "golden_zone_high"]]
        log(qualifying.to_string(index=False))


if __name__ == "__main__":
    run_unattended("FIBO EVENING JOB", main, log)
