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
After every run, the events log is committed and pushed (src/fibo_live/
git_sync.py), best-effort, never blocking the job on a failed push
(OPERATIONS.md).
"""
import argparse
import datetime as dt
import sys
import uuid
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.adjustment import materialize_adjustment_factors
from data_layer.db import get_connection
from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday
from data_layer.prices_nse import load_bhavcopy_to_duckdb
from data_layer.staleness import assert_data_current, latest_trade_date, StaleDataError

from fibo_live.clock import detect_run_mode
from fibo_live.config import EVENTS_LOG, RAW_PRICES_DIR, TOP_N, WAREHOUSE_DB
from fibo_live.eventlog import append_event, read_events
from fibo_live.git_sync import pull_before_appending, sync_events_log_to_git
from fibo_live.notify import already_notified, record_notification, send_email
from fibo_live.scheduler_support import make_logger, run_unattended
from fibo_live.watchlist import build_watchlist

from spread_monitor.market_hours import IST

SERIES_INCLUDE = ["EQ", "BE", "BZ"]  # same set config.yaml's nse_bhavcopy.series_include uses
MAX_LOOKBACK_DAYS = 10  # bound for the backward walk only when the warehouse has no prior data at all (see main())

log = make_logger()


def next_trading_day(con, d: dt.date, known_through: dt.date) -> dt.date:
    """Next trading day after `d`: skips Saturday/Sunday, and skips a
    weekday CONFIRMED an NSE holiday by data_layer.nse_holidays.
    is_nse_holiday (the full local pkl if present, else the committed
    fallback JSON) -- holiday-aware UP FRONT, not just reactively.

    Previously this only learned about a holiday from an EXISTING
    fetch_log 'no_data' row (confirmed by some prior fetch attempt
    against that exact date) -- which meant a day's own holiday status
    was invisible until something had already tried and failed to fetch
    it. Found live: Monday 2026-10-19's evening run targeted Tuesday
    2026-10-20 (a real NSE holiday) directly, because nothing had tried
    fetching Tuesday yet -- leaving a stale watchlist_run and a
    misleading digest email for a day nobody would trade. Consulting
    is_nse_holiday up front is what lets Monday's own run see Tuesday's
    holiday in advance and target Wednesday directly instead.

    DEGRADES to the OLD reactive-only check, one candidate day at a
    time, when is_nse_holiday raises HolidayCalendarMissing for that
    candidate's year (e.g. 2027, absent from the committed fallback as
    of this writing, see data/raw/nse_cm_holidays_fallback.json) --
    logged as a visible WARNING every time, never a silent degradation.
    In that fallback mode this function is exactly as holiday-blind as
    it always was: it can only skip a day up to `known_through` that
    this run's own backward walk (or an earlier run's) already confirmed
    has no published bhavcopy; a day beyond `known_through` with no
    calendar coverage is simply assumed an ordinary trading day, the
    same known, flagged gap this project has always carried for an
    uncovered year.

    Only used for the idempotency guard below and the report line; the
    watchlist itself is always computed from `data_date`, the actual
    latest day with published bhavcopy, never from this."""
    nxt = d + dt.timedelta(days=1)
    while True:
        if nxt.weekday() >= 5:  # Saturday=5, Sunday=6
            nxt += dt.timedelta(days=1)
            continue
        try:
            if is_nse_holiday(nxt):
                nxt += dt.timedelta(days=1)
                continue
        except HolidayCalendarMissing:
            log(f"WARNING: next_trading_day cannot confirm whether {nxt} is an NSE holiday -- "
                f"no calendar entry for {nxt.year} (neither the local pkl nor the committed "
                f"fallback covers it). Falling back to the reactive, fetch_log-only check for "
                f"this date -- a real holiday that year will only be caught AFTER a fetch "
                f"attempt against it confirms no bhavcopy was published, not in advance.")
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


def _zone_distance(close: float, zone_low: float, zone_high: float) -> str:
    """'<pct>% / Rs<rupees> above/below zone', measured from the nearer
    zone boundary, or 'inside zone' if close already sits within
    [zone_low, zone_high]."""
    if close > zone_high:
        diff = close - zone_high
        return f"{diff / zone_high * 100:.2f}% / Rs{diff:.2f} above zone"
    if close < zone_low:
        diff = zone_low - close
        return f"{diff / zone_low * 100:.2f}% / Rs{diff:.2f} below zone"
    return "inside zone"


def notify_watchlist_digest(target_trade_date: dt.date, watchlist: pd.DataFrame) -> None:
    """One summary email per NEW watchlist run (never for an idempotent
    skip or a refusal -- those paths never reach this call, and a refusal
    already sends its own notify_evening_skipped email). Separate from,
    and does not replace, the morning job's own per-stock SETUP/trigger
    alerts (notify.py) -- those depend on tomorrow's opening range, which
    does not exist yet at evening-job time; this digest only reports
    where today's close already sits relative to each zone.

    Deduped per target_trade_date the same way every other alert here is
    (already_notified/record_notification) -- a second run that resolves
    to the SAME target (e.g. a weekend re-run with no new bhavcopy) will
    not resend. A genuine correction producing a materially different
    watchlist for a target that already got a digest (rare -- see
    BUGS.md's 2026-10-09 fetch-failure-cached-as-holiday entry) will also
    not resend automatically; that case is intentionally left to be
    noticed and handled by hand, same as the watchlist_run_correction
    bookkeeping itself is."""
    if already_notified("watchlist_digest", target_trade_date):
        return

    qualifying = watchlist[watchlist["qualifies"]].sort_values("rank")
    n_qualify = len(qualifying)
    subject = f"FIBO WATCHLIST for {target_trade_date} - {n_qualify} stocks"

    lines = [
        "Entry, stop and target depend on tomorrow's 09:15-09:30 opening range "
        "and are not known yet. You will get a separate SETUP email at ~09:30 "
        "if any stock's opening range lands in its zone.",
        "",
    ]
    if n_qualify == 0:
        lines.append("No stocks qualify tonight.")
    for _, r in qualifying.iterrows():
        zone_low, zone_high, close = r["golden_zone_low"], r["golden_zone_high"], r["close"]
        distance = _zone_distance(close, zone_low, zone_high) if close is not None else "close unavailable"
        close_str = f"{close:.2f}" if close is not None else "n/a"
        lines.append(
            f"{r['symbol']} (rank {int(r['rank'])}): zone {zone_low:.2f}-{zone_high:.2f}, "
            f"close {close_str} -- {distance}"
        )
    body = "\n".join(lines)

    if send_email(subject, body, log=log):
        record_notification("watchlist_digest", target_trade_date, n_qualify=n_qualify)
    else:
        log("  watchlist-digest email NOT sent -- will retry next run")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD, default: today")
    args = parser.parse_args()
    # Explicit IST, not dt.date.today() (host-local) -- parity with
    # scripts/fibo_morning.py's same fix, even though this job stays on
    # the IST laptop for now.
    requested_date = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(IST).date()

    # FIRST thing this job does, before any append_event call -- see
    # fibo_live/git_sync.py's pull_before_appending docstring. Raises
    # (abort, logged loudly via run_unattended) rather than proceeding
    # against a possibly-stale local events.jsonl.
    pull_before_appending(log)

    log(f"=== FIBO EVENING JOB -- requested {requested_date} ===")

    con = get_connection(WAREHOUSE_DB)

    # BUGS.md: the staleness guard must protect the COMPUTATION, not block
    # the fetch that would cure it. Checking staleness BEFORE fetching (the
    # original order) meant a single missed evening run, hit again after a
    # weekend, made the gap between real "today" and whatever the warehouse
    # already had look like a multi-day outage -- and refused before ever
    # trying to fetch the one day (last Friday, say) that would have closed
    # it. The fetch below is unconditional; staleness is checked further
    # down, against the warehouse's state AFTER fetching, right before the
    # computation that check actually exists to protect.
    #
    # `floor` bounds the backward walk below -- normally the warehouse's
    # own prior latest date (already known to have data, so walking past it
    # finds nothing new). On a genuinely empty warehouse (prior_latest is
    # None) there is no such floor, so MAX_LOOKBACK_DAYS stands in instead,
    # bounding the walk so it cannot loop indefinitely.
    prior_latest = latest_trade_date(con)
    floor = prior_latest if prior_latest is not None else (requested_date - dt.timedelta(days=MAX_LOOKBACK_DAYS))
    log(f"Warehouse's latest trading day before this run: "
        f"{prior_latest if prior_latest is not None else 'none (empty warehouse)'}.")

    # Find the latest trading day that actually HAS published bhavcopy data,
    # starting at requested_date (today, or --date) and walking backward one
    # calendar day at a time. On an ordinary weekday evening run this exits
    # on its first iteration, exactly like the old single-fetch code. On a
    # weekend, holiday, or missed-run catch-up, requested_date (and possibly
    # several days before it) has nothing published, so this keeps trying
    # the prior day until it finds one -- bounded by `floor`.
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
        if candidate <= floor:
            data_date = prior_latest  # may still be None if the warehouse was empty and nothing new was found
            break
        log(f"  No bhavcopy for {candidate} (holiday or weekend) -- trying the prior calendar day.")
        candidate -= dt.timedelta(days=1)

    if data_date is None:
        # Only reachable when the warehouse had no prior data at all AND
        # nothing was found within MAX_LOOKBACK_DAYS -- a genuinely empty
        # warehouse, not a missed-run catch-up. assert_data_current below
        # would raise on this too (prices_eod is empty), but data_date is
        # about to be used unchecked (next_trading_day, detect_run_mode) --
        # fail clearly here rather than on a None a few lines down.
        log(f"No bhavcopy found for {requested_date} or any of the {MAX_LOOKBACK_DAYS} days before it, "
            f"and the warehouse has no prior data either. Nothing to compute from.")
        notify_evening_skipped(requested_date, "no data available",
                                f"warehouse is empty and no bhavcopy could be fetched within "
                                f"{MAX_LOOKBACK_DAYS} days of {requested_date}.")
        con.close()
        return

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

    # Checked AFTER fetching, not before: this is what protects the
    # COMPUTATION from a genuinely stalled feed (BUGS.md Bug #13), now that
    # the fetch above has already had its chance to cure an ordinary missed-
    # run gap. If the warehouse is STILL stale at this point -- the fetch
    # found nothing new, or what it found isn't recent enough -- refuse to
    # compute rather than build a watchlist from a stale panel.
    try:
        confirmed_latest = assert_data_current(con)
        log(f"Freshness check OK: warehouse's latest trading day is {confirmed_latest} after fetching.")
    except StaleDataError as e:
        log(f"REFUSING TO COMPUTE: {e}")
        notify_evening_skipped(requested_date, "stale data", str(e))
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

    notify_watchlist_digest(target_trade_date, watchlist)


if __name__ == "__main__":
    run_unattended("FIBO EVENING JOB", main, log)
    # Runs after run_unattended returns -- which it always does, success,
    # idempotent skip, stale-data refusal, or a swallowed crash -- so
    # whatever this run appended (even a partial run cut short by an
    # exception) still gets backed up off this one laptop. Never raises;
    # see fibo_live/git_sync.py and OPERATIONS.md.
    sync_events_log_to_git(EVENTS_LOG, log, job_label="Fibo evening events")
