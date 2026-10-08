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
     condition. Logs one "setup" event per qualifying stock.

  2. For every SETUP ON stock, watches each 15-minute candle close in
     [09:30, 11:30) in real time (sleeping until each boundary + a short
     buffer) for the first close above the ORB high
     (PREREGISTRATION_FIBO.md Section 3f) -- the actual entry trigger,
     price, and time are logged as a "trigger" event the moment it fires.
     One trade per stock per day: a stock stops being watched the instant
     it triggers.

  3. Once the entry window has closed (11:30) AND the trading day itself
     has closed (15:15) -- or immediately, if this script is instead run
     well after both, catching up on a day it missed live -- resolves
     every triggered stock's stop/target against that day's full 1-minute
     bars using the SAME fibo.resolution.resolve_trade function the sealed
     backtest itself uses (not a separate live-resolution algorithm), and
     logs a final "outcome" event (src/fibo_live/outcomes.py) for every
     SETUP ON stock, triggered or not.

IDEMPOTENT / RESUMABLE: before acting on any stock, checks whether today's
event of that kind already exists for it and skips -- safe to stop and
re-run this script at any point in the day (e.g. if it crashes at 10:15,
re-running it will not re-fetch an ORB it already has, and will not
double-log a trigger or outcome).

NOT YET LIVE-VERIFIED: written and reviewed against the exact mechanism
scripts/fibo_test_backtest.py already uses on historical data, but not run
against a live market session -- the market is closed at the time this
script was written. Flagged per this project's own convention of stating
an unverified assumption rather than silently presenting it as checked.
"""
import argparse
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from data_layer.db import get_read_connection

from fibo.auth import login, _redact
from fibo.backtest import zones_overlap
from fibo.download import resolve_entity_tokens
from fibo.price_scale import to_raw_scale
from fibo.resolution import compute_r, compute_target, position_size_shares, resolve_trade

from fibo_live.config import WAREHOUSE_DB
from fibo_live.eventlog import append_event, read_events
from fibo_live.outcomes import record_outcome

ORB_START, ORB_END = dt.time(9, 15), dt.time(9, 30)
ENTRY_STARTS = [dt.time(h, m) for h, m in
                [(9, 30), (9, 45), (10, 0), (10, 15), (10, 30), (10, 45), (11, 0), (11, 15)]]
ENTRY_WINDOW_CLOSE = dt.time(11, 30)
EXIT_TIME = dt.time(15, 15)
POLL_BUFFER_SECONDS = 20  # wait this long past a candle's close before trusting it's final
THROTTLE_SECONDS = 0.4


def log(msg: str) -> None:
    print(msg, flush=True)


def latest_watchlist(trade_date: dt.date) -> pd.DataFrame:
    runs = [e for e in read_events(kind="watchlist_run") if e["as_of_date"] < str(trade_date)]
    if not runs:
        return pd.DataFrame()
    latest_run_id = max(runs, key=lambda e: e["ts"])["run_id"]
    rows = [e for e in read_events(kind="watchlist") if e["run_id"] == latest_run_id and e["qualifies"]]
    return pd.DataFrame(rows)


def already_logged(kind: str, entity_id: str, trade_date: dt.date) -> bool:
    for e in read_events(kind=kind):
        if e.get("entity_id") == entity_id and e.get("trade_date") == str(trade_date):
            return True
    return False


def fetch_candle(client, token: str, start: dt.datetime, end: dt.datetime, interval: str):
    params = {
        "exchange": "NSE", "symboltoken": str(token), "interval": interval,
        "fromdate": start.strftime("%Y-%m-%d %H:%M"), "todate": end.strftime("%Y-%m-%d %H:%M"),
    }
    try:
        resp = client.getCandleData(params)
    except Exception as e:
        return None, _redact(f"{type(e).__name__}: {e}")
    finally:
        time.sleep(THROTTLE_SECONDS)
    if isinstance(resp, dict) and resp.get("status") is True:
        return resp.get("data") or [], None
    return None, _redact(str(resp.get("message") if isinstance(resp, dict) else resp))


def candle_to_bar(c) -> dict:
    ts = pd.Timestamp(c[0]).tz_localize(None)
    return {"ts": ts, "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "volume": c[5]}


def phase1_setups(client, con, watchlist: pd.DataFrame, trade_date: dt.date) -> pd.DataFrame:
    if watchlist.empty:
        log("No qualifying watchlist rows for today -- nothing to do.")
        return watchlist

    entity_ids = watchlist["entity_id"].tolist()
    resolved, missing = resolve_entity_tokens(con, entity_ids)
    if missing:
        log(f"  {len(missing)} entities have no resolvable Angel token (delisted/renamed?): {missing}")
    token_lookup = dict(zip(resolved["entity_id"], resolved["token"]))

    setups = []
    for _, r in watchlist.iterrows():
        entity_id = r["entity_id"]
        if already_logged("setup", entity_id, trade_date):
            log(f"  {r['symbol']}: setup already logged today, skipping re-fetch")
            prior = [e for e in read_events(kind="setup")
                     if e["entity_id"] == entity_id and e["trade_date"] == str(trade_date)][0]
            setups.append(prior)
            continue

        token = token_lookup.get(entity_id)
        if token is None:
            continue
        start = dt.datetime.combine(trade_date, ORB_START)
        end = dt.datetime.combine(trade_date, ORB_END)
        candles, err = fetch_candle(client, token, start, end, "FIFTEEN_MINUTE")
        if err or not candles:
            log(f"  {r['symbol']}: ORB fetch failed ({err or 'no candle'})")
            continue
        orb = candle_to_bar(candles[0])
        orb_high, orb_low = orb["high"], orb["low"]

        zone_low_raw = to_raw_scale(r["golden_zone_low"], r["scale_factor"])
        zone_high_raw = to_raw_scale(r["golden_zone_high"], r["scale_factor"])
        swing_high_raw = to_raw_scale(r["swing_high"], r["scale_factor"])
        setup_on = zones_overlap(orb_low, orb_high, zone_low_raw, zone_high_raw)

        payload = {
            "entity_id": entity_id, "symbol": r["symbol"], "trade_date": trade_date, "rank": r["rank"],
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


def watch_for_triggers(client, con, setups: pd.DataFrame, trade_date: dt.date) -> None:
    active = setups[setups.get("setup_on") == True].copy() if not setups.empty else setups  # noqa: E712
    if active.empty:
        log("No SETUP ON stocks -- nothing to watch.")
        return
    entity_ids = active["entity_id"].tolist()
    resolved, _ = resolve_entity_tokens(con, entity_ids)
    token_lookup = dict(zip(resolved["entity_id"], resolved["token"]))

    pending = {r["entity_id"]: r for _, r in active.iterrows() if not already_logged("trigger", r["entity_id"], trade_date)}
    log(f"Watching {len(pending)} SETUP ON stock(s) for an entry trigger, 09:30-11:30...")

    for candle_start in ENTRY_STARTS:
        if not pending:
            break
        candle_close_wall = dt.datetime.combine(trade_date, candle_start) + dt.timedelta(minutes=15, seconds=POLL_BUFFER_SECONDS)
        wait = (candle_close_wall - dt.datetime.now()).total_seconds()
        if wait > 0:
            log(f"  waiting {wait:.0f}s for the {candle_start} candle to close...")
            time.sleep(wait)

        start = dt.datetime.combine(trade_date, candle_start)
        end = start + dt.timedelta(minutes=15)
        for entity_id in list(pending.keys()):
            r = pending[entity_id]
            token = token_lookup.get(entity_id)
            if token is None:
                continue
            candles, err = fetch_candle(client, token, start, end, "FIFTEEN_MINUTE")
            if err or not candles:
                continue
            bar = candle_to_bar(candles[0])
            if bar["close"] > r["orb_high"]:
                entry_ts, entry_price = start + dt.timedelta(minutes=14), bar["close"]
                stop = r["orb_low"]
                target = compute_target(entry_price, stop, r["swing_high_raw"])
                qty = position_size_shares(entry_price, stop)
                append_event("trigger", {
                    "entity_id": entity_id, "symbol": r["symbol"], "trade_date": trade_date,
                    "entry_ts": entry_ts, "entry_price": entry_price, "stop": stop, "target": target, "qty": qty,
                })
                log(f"  TRIGGER {r['symbol']} @ {entry_price:.2f} ({entry_ts})")
                del pending[entity_id]

    for entity_id in pending:
        log(f"  no trigger by 11:30: {pending[entity_id]['symbol']}")


def resolve_outcomes(client, con, setups: pd.DataFrame, trade_date: dt.date) -> None:
    if setups.empty:
        return
    now = dt.datetime.now()
    exit_deadline = dt.datetime.combine(trade_date, EXIT_TIME)
    if now < exit_deadline:
        wait = (exit_deadline - now).total_seconds()
        log(f"Waiting {wait/60:.0f} min for the trading day to reach 15:15 before resolving outcomes...")
        time.sleep(wait)

    triggers = {e["entity_id"]: e for e in read_events(kind="trigger") if e["trade_date"] == str(trade_date)}
    entity_ids = setups[setups.get("setup_on") == True]["entity_id"].tolist() if not setups.empty else []  # noqa: E712
    resolved, _ = resolve_entity_tokens(con, entity_ids)
    token_lookup = dict(zip(resolved["entity_id"], resolved["token"]))

    for _, s in setups.iterrows():
        if not s.get("setup_on"):
            continue
        entity_id = s["entity_id"]
        if already_logged("outcome", entity_id, trade_date):
            continue

        trig = triggers.get(entity_id)
        if trig is None:
            record_outcome(entity_id=entity_id, symbol=s["symbol"], trade_date=trade_date,
                            rank=s["rank"], triggered=False)
            log(f"  {s['symbol']}: outcome logged -- no trigger")
            continue

        token = token_lookup.get(entity_id)
        if token is None:
            continue
        day_start = dt.datetime.combine(trade_date, dt.time(9, 15))
        day_end = dt.datetime.combine(trade_date, dt.time(15, 30))
        candles, err = fetch_candle(client, token, day_start, day_end, "ONE_MINUTE")
        if err or not candles:
            log(f"  {s['symbol']}: 1-min bars fetch failed ({err}) -- cannot resolve outcome yet")
            continue
        bars = pd.DataFrame([candle_to_bar(c) for c in candles])
        entry_ts = pd.Timestamp(trig["entry_ts"])
        exit_ts = pd.Timestamp.combine(pd.Timestamp(trade_date), EXIT_TIME)
        resolution = resolve_trade(bars, entry_ts, trig["stop"], trig["target"], exit_ts)

        record_outcome(
            entity_id=entity_id, symbol=s["symbol"], trade_date=trade_date, rank=s["rank"], triggered=True,
            entry_ts=trig["entry_ts"], entry_price=trig["entry_price"], stop=trig["stop"], target=trig["target"],
            qty=trig["qty"], exit_ts=resolution["exit_ts"], exit_price=resolution["exit_price"],
            exit_reason=resolution["outcome"],
        )
        log(f"  {s['symbol']}: outcome logged -- {resolution['outcome']} @ {resolution['exit_price']:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD, default: today")
    args = parser.parse_args()
    trade_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()

    log(f"=== FIBO MORNING JOB -- {trade_date} ===")
    con = get_read_connection(WAREHOUSE_DB)

    watchlist = latest_watchlist(trade_date)
    log(f"{len(watchlist)} qualifying stock(s) from last night's watchlist.")

    result = login()
    if not result.ok:
        log(f"Angel One login FAILED: {result.status}")
        return
    log("Angel One login OK (data-only session).")

    setups = phase1_setups(result.client, con, watchlist, trade_date)
    watch_for_triggers(result.client, con, setups, trade_date)
    resolve_outcomes(result.client, con, setups, trade_date)
    con.close()
    log("=== Morning job complete. ===")


if __name__ == "__main__":
    main()
