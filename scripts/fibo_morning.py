"""MORNING JOB -- run any time from 09:15. PAPER ONLY, data-only: this
script only ever calls Angel One's getCandleData (historical/intraday
candles, read-only market data) via src/fibo/auth.py's login() session.
It never imports or calls placeOrder, modifyOrder, cancelOrder, or any
other order endpoint -- grep this file and src/fibo/auth.py yourself if in
doubt; there is no such import anywhere in this tree.

    python scripts/fibo_morning.py [--date YYYY-MM-DD]

Reads the MOST RECENT watchlist_run logged by scripts/fibo_evening.py
(src/fibo_live/eventlog.py), restricted to qualifies=True rows, and:

  1. Fetches the 09:15-09:30 opening range for each (one FIFTEEN_MINUTE
     candle). Converts the stored golden zone (adjusted scale) to today's
     raw scale via the watchlist's own stored scale_factor
     (src/fibo/price_scale.to_raw_scale) and flags SETUP ON where the ORB
     overlaps it (PREREGISTRATION_FIBO.md Section 3e) -- uptrend is
     already true for every qualifying row, so this is the only remaining
     condition. Logs one "setup" event per qualifying stock, with
     status SETUP_ON / SETUP_OFF / FETCH_FAILED -- a symbol whose ORB fetch
     never actually succeeded is FETCH_FAILED, never SETUP_OFF, and FETCH_FAILED
     is NOT treated as resolved: it does not block a retry on the next run.

  2. For every SETUP ON stock, checks each 15-minute candle close in
     [09:30, 11:30) that has ALREADY happened as of right now for the
     first close above the ORB high (PREREGISTRATION_FIBO.md Section 3f) --
     the actual entry trigger, price, and time are logged as a "trigger"
     event the moment it's found. One trade per stock per day: a stock
     stops being watched the instant it triggers. This does NOT sleep
     waiting for a future candle -- it is meant to be re-run periodically
     (e.g. every few minutes between 09:30 and 11:30); each run picks up
     whatever newly-closed candles exist and reports what's still pending.

  3. Once the trading day itself has closed (15:15), resolves every
     triggered stock's stop/target against that day's full 1-minute bars
     using the SAME fibo.resolution.resolve_trade function the sealed
     backtest itself uses (not a separate live-resolution algorithm), and
     logs a final "outcome" event (src/fibo_live/outcomes.py) for every
     SETUP ON stock, triggered or not. If 15:15 hasn't arrived yet, or
     there are no SETUP ON stocks at all, this returns immediately with a
     message instead of blocking -- re-run after 15:15 to resolve.

RATE LIMITS: every Angel One candle fetch is throttled to THROTTLE_SECONDS
(0.4s) apart. A rate-limit error specifically (fibo.download.looks_rate_limited)
triggers exponential backoff and retry (MAX_FETCH_RETRIES, RETRY_BASE_DELAY_SECONDS)
rather than being treated as a final answer -- a symbol that still fails after
retries is logged distinctly (FETCH_FAILED / "... fetch FAILED") and simply
retried again on the next run, never silently recorded as SETUP_OFF or as a
checked candle.

RUN MODE: detected once per invocation from the wall clock
(src/fibo_live/clock.detect_run_mode) and stamped on every event this run
logs -- LIVE if this run started on `trade_date` itself before 15:15 (the
day's outcome was genuinely not yet known), REPLAY otherwise (a catch-up
run after close, or on a later day, against data that already fully
existed). Not a flag passed on the command line; nothing here sets it.

IDEMPOTENT / RESUMABLE: before acting on any stock, checks whether today's
event of that kind already exists for it and skips -- safe to stop and
re-run this script at any point in the day (e.g. if it crashes at 10:15,
re-running it will not re-fetch an ORB it already has, and will not
double-log a trigger or outcome).

NO WAREHOUSE DEPENDENCY (GitHub Actions migration): this script never
opens data/warehouse.duckdb. Everything it needs comes from events.jsonl
(the watchlist, already carrying each row's `symbol`) and Angel One
itself: an Angel instrument token is resolved straight from that
`symbol` (spread_monitor.tokens.resolve_tokens -- the instrument master,
disk-cached per IST date, never the warehouse's isin_lineage/prices_eod
join fibo.download.resolve_entity_tokens used to do this through). This
keeps NSE price data, and the warehouse file itself, off of any machine
this script runs on that isn't the laptop.

UNATTENDED (Windows Task Scheduler, or GitHub Actions): every log() line
also goes to data/fibo_live/scheduler.log (src/fibo_live/
scheduler_support.py), since a scheduled run has no terminal for stdout
to land in. main() is wrapped so ANY unhandled exception -- dead
network, Angel down, anything -- is caught, logged with its traceback,
and swallowed: the process always exits 0 and a bad run never blocks a
later one. Two refusal checks run before any per-stock work:
assert_watchlist_current (below -- catches the evening job never having
logged tonight's watchlist at all, the events.jsonl-only replacement for
the old data_layer.staleness.assert_data_current warehouse check; see
BUGS.md Bug #13 for the silent-gap failure mode both guard against) and
a LIVE trading-day check (catches a single isolated NSE holiday landing
on a weekday, which the freshness check alone does NOT). The live check
reuses the exact mechanism scripts/snapshot_spreads.py already uses and
has run live (src/spread_monitor/trading_day.py's verify_trading_day
against Angel's getMarketData exchFeedTime), rather than inventing a
second one: without it, a scheduler firing every 15 minutes on a holiday
would log a FETCH_FAILED-shaped "no candle" event for every watchlist
stock, every run, all morning, for no reason.

After every run, the events log is committed and pushed (src/fibo_live/
git_sync.py), best-effort, never blocking the job on a failed push. This
is the run that matters most for a credible git timestamp on setup/
trigger events specifically: they are written here, during market hours,
and syncing only from the evening job (hours later, after that trade's
outcome is already known) would mean git could never independently show
a setup was recorded before its outcome (OPERATIONS.md).

NOT YET LIVE-VERIFIED: written and reviewed against the exact mechanism
scripts/fibo_test_backtest.py already uses on historical data, but not run
against a live market session -- the market is closed at the time this
script was written. Flagged per this project's own convention of stating
an unverified assumption rather than silently presenting it as checked.

EMAIL ALERTS (src/fibo_live/notify.py): one email the first time a stock
is found SETUP ON for the day, one email per entry trigger fired. NOT sent
for a zero-setup morning or for an outcome resolution (that's what
events.jsonl is for) -- see notify.py's own docstring for the idempotency
and fail-soft guarantees.
"""
import argparse
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from fibo.auth import login, _redact
from fibo.backtest import zones_overlap
from fibo.download import looks_rate_limited
from fibo.price_scale import to_raw_scale
from fibo.resolution import compute_r, compute_target, position_size_shares, resolve_trade

from fibo_live.clock import detect_run_mode
from fibo_live.config import EVENTS_LOG
from fibo_live.eventlog import append_event, read_events
from fibo_live.git_sync import sync_events_log_to_git
from fibo_live.notify import already_notified, record_notification, send_email
from fibo_live.outcomes import record_outcome
from fibo_live.scheduler_support import make_logger, run_unattended

from spread_monitor.market_hours import IST
from spread_monitor.tokens import resolve_tokens
from spread_monitor.trading_day import verify_trading_day

NIFTY_50_INDEX_TOKEN = "99926000"  # Angel's NSE instrument-master token for the Nifty 50 index

ORB_START, ORB_END = dt.time(9, 15), dt.time(9, 30)
ENTRY_STARTS = [dt.time(h, m) for h, m in
                [(9, 30), (9, 45), (10, 0), (10, 15), (10, 30), (10, 45), (11, 0), (11, 15)]]
ENTRY_WINDOW_CLOSE = dt.time(11, 30)
EXIT_TIME = dt.time(15, 15)
POLL_BUFFER_SECONDS = 20  # wait this long past a candle's close before trusting it's final
THROTTLE_SECONDS = 0.4
# The opening-range pass hit rate limits hardest of the three fetch passes
# (2026-10-14 manual run: most of 16 stocks retried, LAURUSLABS exhausted
# all 5 retries) -- every ORB fetch happens back-to-back in one burst at
# the start of the run, unlike the trigger/outcome passes which are
# naturally spread across re-runs. Slower pace here specifically rather
# than raising THROTTLE_SECONDS everywhere.
ORB_THROTTLE_SECONDS = 0.8
MAX_FETCH_RETRIES = 5  # retries on a RATE-LIMIT error specifically, not on any other error
RETRY_BASE_DELAY_SECONDS = 2.0


log = make_logger()


def confirm_trading_day(client) -> tuple[bool, str]:
    """(True, "") if Angel's live feed confirms today as an actual trading
    day (src/spread_monitor/trading_day.py); (False, reason) otherwise --
    e.g. an NSE holiday that falls on a weekday, which a scheduler has no
    calendar to exclude on its own. One extra lightweight quote call
    (reusing the NIFTY 50 index token scripts/snapshot_spreads.py already
    uses), done once per run before any per-stock work."""
    try:
        resp = client.getMarketData("FULL", {"NSE": [NIFTY_50_INDEX_TOKEN]})
    except Exception as e:
        return False, f"quote request raised ({_redact(f'{type(e).__name__}: {e}')})"
    if not isinstance(resp, dict) or not resp.get("status"):
        return False, f"quote request failed ({_redact(str(resp.get('message') if isinstance(resp, dict) else resp))})"
    fetched = (resp.get("data") or {}).get("fetched") or []
    status = verify_trading_day(fetched, dt.datetime.now(IST))
    if status != "OK":
        return False, f"live feed does not confirm today as a trading day (status={status})"
    return True, ""


class StaleWatchlistError(Exception):
    """Raised instead of silently running against a missing or stale
    watchlist. Callers must let this propagate -- never catch and
    continue."""


def assert_watchlist_current(trade_date: dt.date, max_staleness_hours: float = 36.0,
                              log_path: Path = EVENTS_LOG) -> dict:
    """The events.jsonl-only replacement for the old
    data_layer.staleness.assert_data_current(warehouse) check, now that
    this script never opens the warehouse. Checks the one fact the
    morning job actually depends on, directly: a watchlist_run event
    targeting `trade_date` exists, logged within max_staleness_hours of
    right now (IST). Raises StaleWatchlistError otherwise -- no evening
    run has computed tonight's watchlist at all, or the only one that
    did is too old to trust (e.g. a multi-day gap in the evening job
    itself -- see BUGS.md Bug #13's meta-pattern: a silent gap must
    refuse loudly, not compute on faith).

    36 hours, not the warehouse check's 3 days: the evening job runs
    once nightly and this is checked the very next morning, so the
    normal gap between "watchlist logged" and "morning job runs" is a
    few hours, never days -- a wider tolerance here would hide exactly
    the staleness this exists to catch. Returns the matching
    watchlist_run event (for logging) on success.

    `log_path` defaults to the real events.jsonl; overridable for tests
    the same way outcomes.py's record_outcome/evaluate already are."""
    runs = [e for e in read_events(kind="watchlist_run", log_path=log_path)
            if e.get("target_trade_date") == str(trade_date)]
    if not runs:
        raise StaleWatchlistError(
            f"No watchlist_run event targets {trade_date} -- the evening job has not "
            f"logged tonight's watchlist (or hasn't run at all)."
        )
    latest_run = max(runs, key=lambda e: e["ts"])
    run_ts = dt.datetime.fromisoformat(latest_run["ts"])
    if run_ts.tzinfo is None:
        run_ts = run_ts.replace(tzinfo=IST)  # pre-fix events: naive ts already meant IST wall time
    age_hours = (dt.datetime.now(IST) - run_ts.astimezone(IST)).total_seconds() / 3600
    if age_hours > max_staleness_hours:
        raise StaleWatchlistError(
            f"watchlist_run {latest_run['run_id']} targeting {trade_date} was logged "
            f"{age_hours:.1f}h ago (max allowed: {max_staleness_hours}h) -- too old to trust."
        )
    return latest_run


def latest_watchlist(trade_date: dt.date) -> pd.DataFrame:
    runs = [e for e in read_events(kind="watchlist_run") if e["as_of_date"] < str(trade_date)]
    if not runs:
        return pd.DataFrame()
    latest_run_id = max(runs, key=lambda e: e["ts"])["run_id"]
    rows = [e for e in read_events(kind="watchlist") if e["run_id"] == latest_run_id and e["qualifies"]]
    return pd.DataFrame(rows)


def resolve_tokens_for_rows(rows) -> dict[str, str]:
    """{entity_id: token} resolved purely from the `symbol` each row
    already carries (from events.jsonl -- fibo_evening.py's watchlist.py
    computed it the same way, hours earlier), against Angel's current
    instrument master (spread_monitor.tokens.resolve_tokens, disk-cached
    per IST date) -- never the warehouse. `rows` may be a DataFrame or a
    list of Series, as used at each of this script's three call sites.
    A symbol with no resolvable token (delisted/renamed since last
    night) is logged, never silently dropped."""
    if hasattr(rows, "iterrows"):
        rows = [r for _, r in rows.iterrows()]
    symbols = {r["entity_id"]: r["symbol"] for r in rows}
    token_map, missing_symbols = resolve_tokens(list(symbols.values()))
    if missing_symbols:
        log(f"  {len(missing_symbols)} symbol(s) have no resolvable Angel token "
            f"(delisted/renamed?): {missing_symbols}")
    return {entity_id: token_map[sym] for entity_id, sym in symbols.items() if sym in token_map}


def already_logged(kind: str, entity_id: str, trade_date: dt.date) -> bool:
    for e in read_events(kind=kind):
        if e.get("entity_id") == entity_id and e.get("trade_date") == str(trade_date):
            return True
    return False


def fetch_candle(client, token: str, start: dt.datetime, end: dt.datetime, interval: str,
                  throttle_seconds: float = THROTTLE_SECONDS):
    params = {
        "exchange": "NSE", "symboltoken": str(token), "interval": interval,
        "fromdate": start.strftime("%Y-%m-%d %H:%M"), "todate": end.strftime("%Y-%m-%d %H:%M"),
    }
    try:
        resp = client.getCandleData(params)
    except Exception as e:
        return None, _redact(f"{type(e).__name__}: {e}")
    finally:
        time.sleep(throttle_seconds)
    if isinstance(resp, dict) and resp.get("status") is True:
        return resp.get("data") or [], None
    return None, _redact(str(resp.get("message") if isinstance(resp, dict) else resp))


def fetch_candle_with_retry(client, token: str, start: dt.datetime, end: dt.datetime, interval: str,
                             throttle_seconds: float = THROTTLE_SECONDS):
    """Same contract as fetch_candle, but a RATE-LIMIT error (specifically --
    not any other error) triggers exponential backoff and retry rather than
    an immediate give-up, since a rate-limit means the account is fine and
    just needs to wait, not that the request itself is bad."""
    delay = RETRY_BASE_DELAY_SECONDS
    candles, err = None, None
    for attempt in range(MAX_FETCH_RETRIES + 1):
        candles, err = fetch_candle(client, token, start, end, interval, throttle_seconds=throttle_seconds)
        if err is None:
            return candles, None
        if not looks_rate_limited(err) or attempt == MAX_FETCH_RETRIES:
            return None, err
        log(f"    rate-limited, backing off {delay:.1f}s (retry {attempt + 1}/{MAX_FETCH_RETRIES})...")
        time.sleep(delay)
        delay = min(delay * 2, 30.0)
    return None, err


def latest_setup_event(entity_id: str, trade_date: dt.date) -> dict | None:
    matches = [e for e in read_events(kind="setup")
               if e.get("entity_id") == entity_id and e.get("trade_date") == str(trade_date)]
    return max(matches, key=lambda e: e["ts"]) if matches else None


def candle_to_bar(c) -> dict:
    ts = pd.Timestamp(c[0]).tz_localize(None)
    return {"ts": ts, "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "volume": c[5]}


def phase1_setups(client, watchlist: pd.DataFrame, trade_date: dt.date, run_mode: str) -> pd.DataFrame:
    if watchlist.empty:
        log("No qualifying watchlist rows for today -- nothing to do.")
        return watchlist

    # Resolved rows (a terminal SETUP_ON/SETUP_OFF already logged today)
    # need no token at all -- splitting this BEFORE resolving tokens means
    # a run where every stock is already resolved makes no Angel One call
    # whatsoever here (not even the scrip-master lookup), not just skips
    # the ORB candle fetch. A run with nothing left to do should exit in
    # seconds, not pay for a lookup it will throw away.
    setups: list[dict] = []
    to_fetch = []
    for _, r in watchlist.iterrows():
        prior = latest_setup_event(r["entity_id"], trade_date)
        if prior is not None and prior.get("status") != "FETCH_FAILED":
            log(f"  {r['symbol']}: setup already logged today, skipping re-fetch")
            setups.append(prior)
            continue
        to_fetch.append(r)

    if not to_fetch:
        return pd.DataFrame(setups)

    token_lookup = resolve_tokens_for_rows(to_fetch)

    for r in to_fetch:
        entity_id = r["entity_id"]
        token = token_lookup.get(entity_id)
        if token is None:
            continue
        start = dt.datetime.combine(trade_date, ORB_START)
        end = dt.datetime.combine(trade_date, ORB_END)
        candles, err = fetch_candle_with_retry(client, token, start, end, "FIFTEEN_MINUTE",
                                                throttle_seconds=ORB_THROTTLE_SECONDS)
        if err or not candles:
            # A symbol whose ORB we never actually fetched must never be
            # recorded as SETUP OFF -- that would silently claim we checked
            # and it didn't qualify, when in truth we never checked at all.
            # FETCH_FAILED is a distinct, non-terminal status: it does NOT
            # satisfy the already-logged skip above, so the next run retries it.
            payload = {
                "entity_id": entity_id, "symbol": r["symbol"], "trade_date": trade_date, "rank": r["rank"],
                "run_mode": run_mode, "status": "FETCH_FAILED", "error": err or "no candle", "setup_on": None,
            }
            event = append_event("setup", payload)
            setups.append(event)
            log(f"  {r['symbol']}: FETCH_FAILED ({err or 'no candle'}) -- will retry on next run")
            continue
        orb = candle_to_bar(candles[0])
        orb_high, orb_low = orb["high"], orb["low"]

        zone_low_raw = to_raw_scale(r["golden_zone_low"], r["scale_factor"])
        zone_high_raw = to_raw_scale(r["golden_zone_high"], r["scale_factor"])
        swing_high_raw = to_raw_scale(r["swing_high"], r["scale_factor"])
        setup_on = zones_overlap(orb_low, orb_high, zone_low_raw, zone_high_raw)

        payload = {
            "entity_id": entity_id, "symbol": r["symbol"], "trade_date": trade_date, "rank": r["rank"],
            "run_mode": run_mode, "status": "SETUP_ON" if setup_on else "SETUP_OFF",
            "orb_high": orb_high, "orb_low": orb_low, "zone_low_raw": zone_low_raw, "zone_high_raw": zone_high_raw,
            "swing_high_raw": swing_high_raw, "setup_on": setup_on,
        }
        if setup_on:
            # provisional only -- the real entry price is unknown until a 15-min
            # close actually clears orb_high; stand in with orb_high itself (the
            # boundary any real entry must exceed) so a number can be shown now.
            prov_target = compute_target(orb_high, orb_low, swing_high_raw)
            prov_qty = position_size_shares(orb_high, orb_low)
            payload.update({"provisional_entry": orb_high, "stop": orb_low,
                             "provisional_target": prov_target, "provisional_qty": prov_qty})
        event = append_event("setup", payload)
        setups.append(event)
        log(f"  {r['symbol']}: ORB=[{orb_low:.2f},{orb_high:.2f}] zone=[{zone_low_raw:.2f},{zone_high_raw:.2f}] "
            f"SETUP {'ON' if setup_on else 'OFF'}")

    return pd.DataFrame(setups)


def notify_setup_on(setups: pd.DataFrame, trade_date: dt.date) -> None:
    """Emails once per stock the FIRST time it's found SETUP ON for
    trade_date -- never again after that, even across many 15-min runs
    (already_notified checks the durable "notification" event, not
    anything in-memory). Batches every not-yet-notified stock from THIS
    call into one email rather than one email per stock."""
    if setups.empty:
        return
    active = setups[setups.get("setup_on") == True]  # noqa: E712
    new_rows = [r for _, r in active.iterrows() if not already_notified("setup_on", trade_date, r["entity_id"])]
    if not new_rows:
        return

    blocks = []
    for r in new_rows:
        blocks.append(
            f"{r['symbol']}\n"
            f"  ORB high/low: {r['orb_high']:.2f} / {r['orb_low']:.2f}\n"
            f"  Golden zone: {r['zone_low_raw']:.2f} - {r['zone_high_raw']:.2f}\n"
            f"  Entry trigger (15-min close above): {r['provisional_entry']:.2f}\n"
            f"  Stop: {r['stop']:.2f}\n"
            f"  Target: {r['provisional_target']:.2f}\n"
            f"  Qty: {r['provisional_qty']}"
        )
    subject = f"FIBO SETUP: {len(new_rows)} stock(s) - {trade_date}"
    body = (
        f"{len(new_rows)} stock(s) SETUP ON for {trade_date}:\n\n" + "\n\n".join(blocks) +
        f"\n\nRe-run the morning job before 11:30 IST to check for entry triggers on these."
    )
    if send_email(subject, body, log=log):
        for r in new_rows:
            record_notification("setup_on", trade_date, r["entity_id"], symbol=r["symbol"])
    else:
        log(f"  setup-on email NOT sent for {[r['symbol'] for r in new_rows]} -- will retry next run")


def notify_pending_triggers(trade_date: dt.date) -> None:
    """Emails every "trigger" event for trade_date not yet notified --
    reads from the durable event log rather than in-memory state, so a
    crash between append_event("trigger", ...) and a successful send
    still gets retried on the next run (watch_for_triggers's own pending
    filter would otherwise never revisit an entity once its trigger event
    exists, since that event means "don't re-evaluate this stock", not
    "notification sent")."""
    triggers = [e for e in read_events(kind="trigger") if e.get("trade_date") == str(trade_date)]
    for t in triggers:
        entity_id = t["entity_id"]
        if already_notified("trigger", trade_date, entity_id):
            continue
        subject = f"FIBO TRIGGER: {t['symbol']} @ {t['entry_price']:.2f}"
        body = (
            f"{t['symbol']} entry trigger fired.\n\n"
            f"Entry: {t['entry_price']:.2f}\n"
            f"Stop: {t['stop']:.2f}\n"
            f"Target: {t['target']:.2f}\n"
            f"Qty: {t['qty']}\n"
            f"Time: {t['entry_ts']}"
        )
        if send_email(subject, body, log=log):
            record_notification("trigger", trade_date, entity_id, symbol=t["symbol"])
        else:
            log(f"  trigger email NOT sent for {t['symbol']} -- will retry next run")


def watch_for_triggers(client, setups: pd.DataFrame, trade_date: dt.date, run_mode: str) -> None:
    active = setups[setups.get("setup_on") == True].copy() if not setups.empty else setups  # noqa: E712
    if active.empty:
        log("No SETUP ON stocks -- nothing to watch.")
        return
    token_lookup = resolve_tokens_for_rows(active)

    pending = {r["entity_id"]: r for _, r in active.iterrows() if not already_logged("trigger", r["entity_id"], trade_date)}
    if not pending:
        log("All SETUP ON stocks already have a trigger recorded today.")
        return
    log(f"Checking {len(pending)} SETUP ON stock(s) for an entry trigger "
        f"(only candles already closed as of now) -- re-run this script periodically "
        f"between 09:30 and 11:30 to catch later ones.")

    # NOT a blocking watch loop: this checks whatever 15-min candles have
    # ALREADY closed as of right now and returns -- it never sleeps waiting
    # for a future candle. Catching a trigger on a candle that hasn't closed
    # yet means running this script again after that candle closes.
    #
    # now is explicit IST, never the host's local clock (dt.datetime.now())
    # -- this must stay correct on a GitHub Actions runner (OS clock UTC)
    # exactly as it is on the laptop (OS clock already IST), so every
    # candle_close_wall it's compared against is built with tzinfo=IST too.
    now = dt.datetime.now(IST)
    for candle_start in ENTRY_STARTS:
        if not pending:
            break
        candle_close_wall = dt.datetime.combine(trade_date, candle_start, tzinfo=IST) + dt.timedelta(minutes=15, seconds=POLL_BUFFER_SECONDS)
        if now < candle_close_wall:
            log(f"  {candle_start.strftime('%H:%M')} candle not closed yet "
                f"(closes {candle_close_wall.strftime('%H:%M:%S')}) -- run again after then.")
            break

        start = dt.datetime.combine(trade_date, candle_start)
        end = start + dt.timedelta(minutes=15)
        for entity_id in list(pending.keys()):
            r = pending[entity_id]
            token = token_lookup.get(entity_id)
            if token is None:
                continue
            candles, err = fetch_candle_with_retry(client, token, start, end, "FIFTEEN_MINUTE")
            if err or not candles:
                log(f"  {r['symbol']}: {candle_start.strftime('%H:%M')} candle fetch FAILED "
                    f"({err or 'no candle'}) -- will retry on next run")
                continue
            bar = candle_to_bar(candles[0])
            if bar["close"] > r["orb_high"]:
                entry_ts, entry_price = start + dt.timedelta(minutes=14), bar["close"]
                stop = r["orb_low"]
                target = compute_target(entry_price, stop, r["swing_high_raw"])
                qty = position_size_shares(entry_price, stop)
                append_event("trigger", {
                    "entity_id": entity_id, "symbol": r["symbol"], "trade_date": trade_date, "run_mode": run_mode,
                    "entry_ts": entry_ts, "entry_price": entry_price, "stop": stop, "target": target, "qty": qty,
                })
                log(f"  TRIGGER {r['symbol']} @ {entry_price:.2f} ({entry_ts})")
                del pending[entity_id]

    if not pending:
        return
    if dt.datetime.now(IST) >= dt.datetime.combine(trade_date, ENTRY_WINDOW_CLOSE, tzinfo=IST):
        for entity_id in pending:
            log(f"  no trigger by 11:30: {pending[entity_id]['symbol']}")
    else:
        names = [pending[e]["symbol"] for e in pending]
        log(f"  still pending (no trigger yet): {names} -- run again before 11:30")


def resolve_outcomes(client, setups: pd.DataFrame, trade_date: dt.date, run_mode: str) -> None:
    if setups.empty:
        return
    active = setups[setups.get("setup_on") == True] if not setups.empty else setups  # noqa: E712
    if active.empty:
        log("No SETUP ON stocks -- nothing to resolve.")
        return
    pending = [s for _, s in active.iterrows() if not already_logged("outcome", s["entity_id"], trade_date)]
    if not pending:
        log("All outcomes already resolved for today.")
        return

    # NOT a blocking wait: if the market hasn't reached 15:15 yet, there is
    # nothing this run can resolve -- say so and return rather than holding
    # the terminal open for hours. Re-run this script after 15:15 instead.
    # Explicit IST, not the host clock -- see watch_for_triggers above.
    now = dt.datetime.now(IST)
    exit_deadline = dt.datetime.combine(trade_date, EXIT_TIME, tzinfo=IST)
    if now < exit_deadline:
        log(f"Market hasn't reached {EXIT_TIME.strftime('%H:%M')} yet -- outcomes not resolvable. "
            f"Run again after {EXIT_TIME.strftime('%H:%M')}.")
        return

    triggers = {e["entity_id"]: e for e in read_events(kind="trigger") if e["trade_date"] == str(trade_date)}
    token_lookup = resolve_tokens_for_rows(pending)

    for s in pending:
        entity_id = s["entity_id"]
        trig = triggers.get(entity_id)
        if trig is None:
            record_outcome(entity_id=entity_id, symbol=s["symbol"], trade_date=trade_date,
                            rank=s["rank"], triggered=False, run_mode=run_mode)
            log(f"  {s['symbol']}: outcome logged -- no trigger")
            continue

        token = token_lookup.get(entity_id)
        if token is None:
            continue
        day_start = dt.datetime.combine(trade_date, dt.time(9, 15))
        day_end = dt.datetime.combine(trade_date, dt.time(15, 30))
        candles, err = fetch_candle_with_retry(client, token, day_start, day_end, "ONE_MINUTE")
        if err or not candles:
            log(f"  {s['symbol']}: 1-min bars fetch FAILED ({err}) -- will retry on next run")
            continue
        bars = pd.DataFrame([candle_to_bar(c) for c in candles])
        entry_ts = pd.Timestamp(trig["entry_ts"])
        exit_ts = pd.Timestamp.combine(pd.Timestamp(trade_date), EXIT_TIME)
        resolution = resolve_trade(bars, entry_ts, trig["stop"], trig["target"], exit_ts)

        record_outcome(
            entity_id=entity_id, symbol=s["symbol"], trade_date=trade_date, rank=s["rank"], triggered=True,
            run_mode=run_mode,
            entry_ts=trig["entry_ts"], entry_price=trig["entry_price"], stop=trig["stop"], target=trig["target"],
            qty=trig["qty"], exit_ts=resolution["exit_ts"], exit_price=resolution["exit_price"],
            exit_reason=resolution["outcome"],
        )
        log(f"  {s['symbol']}: outcome logged -- {resolution['outcome']} @ {resolution['exit_price']:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD, default: today")
    args = parser.parse_args()
    # Explicit IST, not dt.date.today() (host-local) -- "today" for this
    # script always means today in India, regardless of what timezone the
    # machine running it (laptop or a GitHub Actions runner) is set to.
    trade_date = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(IST).date()

    # Detected ONCE, from the clock, for this whole run -- never re-detected
    # per event (see src/fibo_live/clock.py for why that would be wrong).
    run_mode = detect_run_mode(trade_date)

    log(f"=== FIBO MORNING JOB -- {trade_date} (run_mode={run_mode}) ===")

    try:
        latest_run = assert_watchlist_current(trade_date)
        log(f"Watchlist freshness check OK: watchlist_run {latest_run['run_id']} "
            f"targeting {trade_date}, logged {latest_run['ts']}.")
    except StaleWatchlistError as e:
        log(f"REFUSING TO RUN: {e}")
        return

    watchlist = latest_watchlist(trade_date)
    log(f"{len(watchlist)} qualifying stock(s) from last night's watchlist.")

    result = login()
    if not result.ok:
        log(f"Angel One login FAILED: {result.status} -- offline, Angel down, or bad credentials. "
            f"Not retrying; the next scheduled run will try again.")
        return
    log("Angel One login OK (data-only session).")

    is_trading, reason = confirm_trading_day(result.client)
    if not is_trading:
        log(f"REFUSING TO RUN: {reason} -- likely a weekend/NSE holiday the scheduler fired on anyway. "
            f"No per-stock events logged this run.")
        return
    log("Live trading-day check OK.")

    setups = phase1_setups(result.client, watchlist, trade_date, run_mode)
    notify_setup_on(setups, trade_date)
    watch_for_triggers(result.client, setups, trade_date, run_mode)
    notify_pending_triggers(trade_date)
    resolve_outcomes(result.client, setups, trade_date, run_mode)
    log("=== Morning job complete. ===")


if __name__ == "__main__":
    run_unattended("FIBO MORNING JOB", main, log)
    # Runs after run_unattended returns -- success, an early refusal
    # (stale data, login failure, non-trading day), or a swallowed crash --
    # so a setup/trigger/outcome logged this run gets a commit timestamp
    # from during market hours, not held back until the evening job runs
    # hours later and after that trade's outcome is already known. Never
    # raises; see fibo_live/git_sync.py and OPERATIONS.md.
    sync_events_log_to_git(EVENTS_LOG, log, job_label="Fibo morning events")
