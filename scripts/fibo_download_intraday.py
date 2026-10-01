"""Step 3: download 1-minute bars for the full Fibo universe (src/fibo/
universe.py's point-in-time top-50-by-turnover, annually reconstituted)
across the full range 2016-10-04 (Step 1's measured floor) to 2026-09-18,
into data/fibo_intraday.duckdb -- a SEPARATE DuckDB file, never
data/warehouse.duckdb. Resumable, chunked (<=25 days/request, well under
Angel's documented 30-day ONE_MINUTE cap), truncation-safe
(src/fibo/download.fetch_chunk_with_retry -- see Step 1's silent-
truncation finding), flush+heartbeat logged, incrementally committed,
throttled at 0.4s/request.

DOCUMENTED LIMITS, confirmed live 2026-09-28 against
https://smartapi.angelone.in/docs/RateLimit and
.../docs/Historical: getCandleData = 3 req/sec, 150 req/min, 5000 req/hour.
No documented DAILY cap exists for this endpoint (only per-second/minute/
hour). ONE_MINUTE max 30 days/request (this script uses 25, with margin).
This script self-throttles against the 150/min and 5000/hour ceilings with
a rolling-window check (HourlyBudget below), independent of the flat 0.4s
sleep, as insurance against the flat throttle alone being too close to the
minute-level cap in practice.

RATE-LIMIT SAFETY, per instruction: on the FIRST rate-limit or
access-denied-shaped error, this script STOPS IMMEDIATELY -- no retry
loop, no continuing to the next chunk. Hammering an API key after a limit
is hit risks it being blocked. The download is resumable by design
(re-running skips every chunk already logged 'ok' in fetch_log_intraday,
via src/fibo/intraday_db.py's schema), so stopping costs nothing -- a
later run picks up exactly where this one stopped.

SESSION EXPIRY, found live during this run (not anticipated in the first
version of this script): Angel One's JWT session expired after ~2 hours
of continuous use, and every subsequent request failed identically with
"Invalid Token" -- a DIFFERENT failure shape from a rate limit (the
account/API key is fine; the session token is simply stale), so it is
handled differently: this script detects a token-expiry-shaped error and
calls fibo.auth.login() again for a fresh session (a normal, safe action,
unlike hammering a rate limit), then retries the SAME chunk once. Capped
at MAX_RELOGINS per run so a genuinely broken session (e.g. revoked API
key) still surfaces as a stop rather than looping forever. The first
version of this script treated "Invalid Token" as an ordinary skip-and-
continue error, which wasted several minutes re-attempting an already-dead
session on every remaining chunk before this was caught and fixed.

Reuses fibo.auth.login()'s single authenticated (and logger-neutralized)
client for every call -- never constructs a second SmartConnect except via
the explicit re-login path above, which itself goes through the same
neutralized login().
"""
import datetime as dt
import sys
import time
from collections import deque
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.auth import login, _redact
from fibo.download import (
    build_download_plan, chunk_date_ranges, fetch_chunk_with_retry, resolve_entity_tokens, CHUNK_DAYS,
    looks_rate_limited, looks_token_expired,
)
from fibo.universe import reconstitute_annually
from fibo.intraday_db import get_connection as get_intraday_connection, SOURCE_NAME
from data_layer.db import get_read_connection

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
LOG_DIR = ROOT / "data" / "fibo_logs"

DEV_START = dt.date(2016, 10, 4)
FULL_END = dt.date(2026, 9, 18)
THROTTLE_SECONDS = 0.4
HEARTBEAT_SECONDS = 45
MAX_RELOGINS = 5  # cap so a genuinely broken session surfaces as a stop, not an infinite retry loop

MINUTE_BUDGET = 140    # stay under the documented 150/min cap
HOUR_BUDGET = 4500     # stay under the documented 5000/hour cap


class HourlyBudget:
    """Rolling-window self-throttle against Angel's documented per-minute
    and per-hour caps for getCandleData, independent of the flat
    THROTTLE_SECONDS sleep -- insurance in case real latency ever makes the
    flat throttle alone too close to the minute-level cap."""
    def __init__(self):
        self.timestamps = deque()

    def wait_if_needed(self, log):
        now = time.time()
        while self.timestamps and now - self.timestamps[0] > 3600:
            self.timestamps.popleft()
        last_minute = sum(1 for t in self.timestamps if now - t <= 60)
        last_hour = len(self.timestamps)
        if last_minute >= MINUTE_BUDGET:
            log(f"  [budget] {last_minute} requests in the last 60s (cap {MINUTE_BUDGET}) -- pausing 15s")
            time.sleep(15)
        if last_hour >= HOUR_BUDGET:
            log(f"  [budget] {last_hour} requests in the last hour (cap {HOUR_BUDGET}) -- pausing 300s")
            time.sleep(300)

    def record(self):
        self.timestamps.append(time.time())


class ClientHolder:
    """Mutable indirection so call_fn's closure always uses the CURRENT
    client -- re-login on token expiry replaces .client in place, and
    every already-created call_fn closure picks up the fresh session on
    its next call without needing to be rebuilt."""
    def __init__(self, client):
        self.client = client


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"download_{dt.datetime.now():%Y%m%dT%H%M%S}.log"
    log_file = open(log_path, "a", encoding="utf-8")

    def log(msg: str):
        line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")
        log_file.flush()

    log(f"=== Fibo Step 3 intraday download starting. Log: {log_path} ===")

    result = login()
    if not result.ok:
        log(f"LOGIN FAILED: {result.status}")
        return
    holder = ClientHolder(result.client)
    log("login OK")
    n_relogins = 0

    warehouse_con = get_read_connection(WAREHOUSE)
    universe = reconstitute_annually(warehouse_con, top_n=50)
    entity_ids = universe["entity_id"].unique().tolist()
    resolved, missing = resolve_entity_tokens(warehouse_con, entity_ids)
    entity_to_token = dict(zip(resolved.entity_id, resolved.token))
    entity_meta = resolved.set_index("entity_id")[["isin", "symbol"]].to_dict("index")

    if missing:
        log(f"{len(missing)} entities have NO Angel One NSE-EQ token (delisted/merged/renamed) -- excluded, not silently skipped:")
        for eid, sym in missing:
            log(f"  SKIPPED (no token): {eid} {sym}")

    plan = build_download_plan(universe, entity_to_token, DEV_START, FULL_END, chunk_days=CHUNK_DAYS)
    total_requests = int(plan["n_chunks"].sum())
    log(f"Download plan: {len(plan)} (entity, year) units, {total_requests} chunk requests "
        f"(<= {CHUNK_DAYS} days each), range {DEV_START} .. {FULL_END}")
    eta_seconds = total_requests * 0.8  # observed Step-1 pace incl. throttle + API latency
    log(f"ETA at ~0.8s/request (observed pace): ~{eta_seconds/60:.0f} minutes (~{eta_seconds/3600:.2f} hours)")

    intraday_con = get_intraday_connection(INTRADAY_DB)
    done = set(
        tuple(r) for r in intraday_con.execute(
            "SELECT entity_id, trade_date FROM fetch_log_intraday WHERE status = 'ok'"
        ).fetchall()
    )
    log(f"Resuming: {len(done)} chunks already marked 'ok' from a prior run will be skipped.")

    budget = HourlyBudget()
    n_success = 0
    n_skipped_resume = 0
    n_errors_logged = 0
    last_heartbeat = time.time()
    stop_reason = None

    def call_fn(token):
        def _call(start, end):
            budget.wait_if_needed(log)
            params = {
                "exchange": "NSE", "symboltoken": str(token), "interval": "ONE_MINUTE",
                "fromdate": start.strftime("%Y-%m-%d 09:00"), "todate": end.strftime("%Y-%m-%d 15:30"),
            }
            try:
                resp = holder.client.getCandleData(params)
            except Exception as e:
                return None, _redact(f"{type(e).__name__}: {e}")
            finally:
                budget.record()
                time.sleep(THROTTLE_SECONDS)
            if isinstance(resp, dict) and resp.get("status") is True:
                return resp.get("data") or [], None
            msg = _redact(str(resp.get("message") if isinstance(resp, dict) else resp))
            return None, msg
        return _call

    def try_relogin() -> bool:
        nonlocal n_relogins
        if n_relogins >= MAX_RELOGINS:
            log(f"  already re-logged in {n_relogins} times this run -- not attempting another (MAX_RELOGINS={MAX_RELOGINS})")
            return False
        n_relogins += 1
        log(f"  session appears expired -- attempting re-login ({n_relogins}/{MAX_RELOGINS})")
        fresh = login()
        if not fresh.ok:
            log(f"  re-login FAILED: {fresh.status}")
            return False
        holder.client = fresh.client
        log("  re-login OK -- resuming with the fresh session")
        return True

    for _, row in plan.iterrows():
        if stop_reason:
            break
        eid, year, start, end = row["entity_id"], row["year"], row["start"], row["end"]
        meta = entity_meta[eid]
        for c_start, c_end in chunk_date_ranges(start, end, CHUNK_DAYS):
            if (eid, c_start) in done:
                n_skipped_resume += 1
                continue

            try:
                data, note_or_err = fetch_chunk_with_retry(call_fn(entity_to_token[eid]), c_start, c_end)
            except RuntimeError as e:
                log(f"  STOP-WORTHY: persistent truncation for {eid} [{c_start},{c_end}]: {e}")
                stop_reason = f"persistent truncation: {e}"
                break

            if data is None and looks_token_expired(note_or_err):
                if try_relogin():
                    try:
                        data, note_or_err = fetch_chunk_with_retry(call_fn(entity_to_token[eid]), c_start, c_end)
                    except RuntimeError as e:
                        log(f"  STOP-WORTHY: persistent truncation for {eid} [{c_start},{c_end}]: {e}")
                        stop_reason = f"persistent truncation: {e}"
                        break
                else:
                    log(f"STOPPING: session expired and re-login failed. Successful requests so far: {n_success}.")
                    stop_reason = f"re-login failed after token expiry: {note_or_err}"
                    break

            if data is None:
                if looks_rate_limited(note_or_err):
                    log(f"RATE-LIMIT-SHAPED ERROR on {eid} [{c_start},{c_end}]: {note_or_err}")
                    log(f"STOPPING IMMEDIATELY per instruction. Successful requests so far: {n_success}.")
                    stop_reason = note_or_err
                    break
                log(f"  error for {eid} [{c_start},{c_end}]: {note_or_err} -- not logged as done, will retry on next run")
                n_errors_logged += 1
                continue

            if note_or_err:
                log(f"  note for {eid} [{c_start},{c_end}]: {note_or_err}")

            if data:
                rows = []
                now = dt.datetime.now()
                for ts, o, h, l, c, v in data:
                    trade_date = dt.date.fromisoformat(ts[:10])
                    rows.append((eid, meta["isin"], meta["symbol"], str(entity_to_token[eid]), trade_date,
                                 dt.datetime.fromisoformat(ts), o, h, l, c, v,
                                 trade_date, now, SOURCE_NAME, 1))
                df = pd.DataFrame(rows, columns=[
                    "entity_id", "isin", "symbol", "angel_token", "trade_date", "ts", "open", "high", "low",
                    "close", "volume", "known_date", "fetched_at", "source", "revision_seq"])
                intraday_con.register("chunk_new", df)
                intraday_con.execute("INSERT INTO bars_1min SELECT * FROM chunk_new")
                intraday_con.unregister("chunk_new")

            intraday_con.execute(
                "INSERT INTO fetch_log_intraday VALUES (?, ?, 'ok', ?, ?)",
                [eid, c_start, len(data), dt.datetime.now()],
            )
            intraday_con.commit()  # incremental commit -- never batch the whole run into one transaction
            n_success += 1

            if time.time() - last_heartbeat > HEARTBEAT_SECONDS:
                log(f"  heartbeat: {n_success} chunks done, {n_skipped_resume} resumed-skip, "
                    f"{n_errors_logged} errors, entity={eid} year={year}")
                last_heartbeat = time.time()

    log(f"=== Done. success={n_success} skipped(resume)={n_skipped_resume} errors={n_errors_logged} "
        f"stop_reason={stop_reason or 'completed'} ===")
    intraday_con.close()
    warehouse_con.close()
    log_file.close()


if __name__ == "__main__":
    main()
