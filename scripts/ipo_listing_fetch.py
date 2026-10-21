"""PREREGISTRATION_IPO.md Section 3: fetch 1-minute bars for the LISTING
DAY ONLY of each of the 552 identified IPOs, into data/ipo_listing/
ipo_intraday.duckdb -- never fibo_intraday.duckdb or warehouse.duckdb.

Mirrors scripts/fibo_download_intraday.py's throttle/budget/relogin/
stop-on-rate-limit/resumable/incremental-commit/heartbeat conventions
exactly (see that script's own module docstring for the hard-won reasons
behind each one -- not re-derived here). The only structural difference:
each "chunk" here is a single listing day, not a multi-year span, so
fetch_chunk_with_retry's truncation-split logic is reused for safety but
is not expected to ever actually trigger.

MEASURE-BEFORE-COMMITTING, per the box theory retrospective (see
PREREGISTRATION_FVG.md Section 8's own restatement of that contingency,
and the user's explicit instruction for this run): after PROBE_N real
API calls, this script logs the OBSERVED pace (not an a-priori guess)
and the resulting ETA for the remaining calls, prominently, before the
bulk of the run proceeds -- not retrofitted after the fact.
"""
import datetime as dt
import json
import sys
import time
from collections import deque
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.auth import login, _redact
from fibo.download import fetch_chunk_with_retry, looks_rate_limited, looks_token_expired
from fibo.bars import aggregate_to_daily
from data_layer.db import get_read_connection
from ipo_listing.listings import load_master_listings, attach_listing_day_isin
from ipo_listing.token_resolution import resolve_listing_tokens
from ipo_listing.intraday_db import get_connection as get_intraday_connection, SOURCE_NAME
from ipo_listing.validation import validate_against_bhavcopy
from ipo_listing.rescale import compute_and_apply_scale_corrections, SCALE_TOLERANCE
from ipo_listing.exclusions import KNOWN_DATA_DEFECTS

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "ipo_listing" / "ipo_intraday.duckdb"
LOG_DIR = ROOT / "data" / "ipo_logs"
SUMMARY_PATH = ROOT / "data" / "ipo_listing" / "phase1_fetch_summary.json"

THROTTLE_SECONDS = 0.4          # same flat throttle as fibo's own download script
HEARTBEAT_SECONDS = 45
MAX_RELOGINS = 5
MINUTE_BUDGET = 140
HOUR_BUDGET = 4500
PROBE_N = 15                    # real calls measured before the observed-pace ETA is logged

USABLE_FRACTION_DEV = 0.60


class HourlyBudget:
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
    def __init__(self, client):
        self.client = client


def _log_fetch(con, listing_id, listing_date, symbol_used, token_used, status, reason, n_candles):
    """DELETE-then-INSERT, same idempotent-retry convention
    data_layer.prices_nse._log_fetch uses -- listing_id is a PRIMARY KEY,
    and a listing previously logged NO_TOKEN or FETCH_FAILED is deliberately
    re-attempted on a later run (see `to_fetch`'s own selection), so a bare
    INSERT would violate the primary key the second time any such listing
    is touched."""
    con.execute("DELETE FROM fetch_log WHERE listing_id = ?", [listing_id])
    con.execute(
        "INSERT INTO fetch_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [listing_id, listing_date, symbol_used, token_used, status, reason, n_candles, dt.datetime.now()],
    )


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"fetch_{dt.datetime.now():%Y%m%dT%H%M%S}.log"
    log_file = open(log_path, "a", encoding="utf-8")

    def log(msg: str):
        line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")
        log_file.flush()

    log(f"=== IPO listing-day intraday fetch starting. Log: {log_path} ===")

    result = login()
    if not result.ok:
        log(f"LOGIN FAILED: {result.status}")
        return
    holder = ClientHolder(result.client)
    log("login OK")
    n_relogins = 0

    warehouse_con = get_read_connection(WAREHOUSE)
    listings = load_master_listings()
    listings = attach_listing_day_isin(warehouse_con, listings)
    n_no_isin = int(listings["isin"].isna().sum())
    if n_no_isin:
        log(f"WARNING: {n_no_isin} listings found NO prices_eod row at (symbol_at_listing, listing_date) -- "
            f"unexpected, since Section 2's cross-check already confirmed 552/552 resolve. Listed below, "
            f"will be NO_TOKEN'd downstream rather than silently dropped:")
        for _, r in listings[listings["isin"].isna()].iterrows():
            log(f"    {r['company_name']} ({r['symbol_at_listing']}, {r['listing_date']})")
    log(f"Loaded {len(listings)} identified listings from the committed master CSV.")

    resolved = resolve_listing_tokens(warehouse_con, listings)
    direct = resolved[resolved["resolution"] == "direct"]
    recovered = resolved[resolved["resolution"] == "recovered"]
    unresolved = resolved[resolved["resolution"] == "unresolved"]
    log(f"Token resolution: {len(direct)} direct, {len(recovered)} recovered via current-symbol lookup, "
        f"{len(unresolved)} unresolved (NO_TOKEN) out of {len(resolved)}.")
    if len(recovered):
        log("  Recovered via current-symbol lookup:")
        for _, r in recovered.iterrows():
            log(f"    {r['company_name']} ({r['symbol_at_listing']} -> {r['symbol_used']})")
    if len(unresolved):
        log("  UNRESOLVED (no Angel token even after recovery attempt):")
        for _, r in unresolved.iterrows():
            log(f"    {r['company_name']} ({r['symbol_at_listing']}, listed {r['listing_date']})")

    intraday_con = get_intraday_connection(INTRADAY_DB)

    # NO_TOKEN listings are logged immediately -- never a silent skip.
    already_logged = set(
        r[0] for r in intraday_con.execute("SELECT listing_id FROM fetch_log").fetchall()
    )
    for _, r in unresolved.iterrows():
        if r["listing_id"] in already_logged:
            continue
        _log_fetch(intraday_con, int(r["listing_id"]), r["listing_date"], r["symbol_at_listing"], None,
                   "NO_TOKEN", "no Angel token even after current-symbol recovery attempt", 0)
    intraday_con.commit()

    done_ok = set(
        r[0] for r in intraday_con.execute("SELECT listing_id FROM fetch_log WHERE status = 'OK'").fetchall()
    )
    to_fetch = resolved[(resolved["resolution"] != "unresolved") & (~resolved["listing_id"].isin(done_ok))]
    log(f"Resuming: {len(done_ok)} listings already 'OK' from a prior run will be skipped. "
        f"{len(to_fetch)} remain to attempt this run.")

    budget = HourlyBudget()
    n_success = 0
    n_failed = 0
    n_zero_candles = 0
    last_heartbeat = time.time()
    stop_reason = None
    call_times = []

    def call_fn(token):
        def _call(start, end):
            t0 = time.time()
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
                call_times.append(time.time() - t0)
            if isinstance(resp, dict) and resp.get("status") is True:
                return resp.get("data") or [], None
            msg = _redact(str(resp.get("message") if isinstance(resp, dict) else resp))
            return None, msg
        return _call

    def try_relogin() -> bool:
        nonlocal n_relogins
        if n_relogins >= MAX_RELOGINS:
            log(f"  already re-logged in {n_relogins} times this run -- not attempting another")
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

    n_attempted = 0
    probe_logged = False

    def _maybe_log_probe():
        nonlocal probe_logged
        if probe_logged or len(call_times) < PROBE_N:
            return
        probe_logged = True
        observed_pace = sum(call_times) / len(call_times)
        remaining = len(to_fetch) - n_attempted
        eta_seconds = remaining * observed_pace
        log(f"  >>> MEASURED PACE after {len(call_times)} real calls: {observed_pace:.2f}s/call "
            f"(incl. throttle+budget waits). Projected ETA for remaining {remaining} calls: "
            f"~{eta_seconds/60:.1f} minutes. <<<")

    for _, row in to_fetch.iterrows():
        if stop_reason:
            break
        listing_id = int(row["listing_id"])
        token = row["token"]
        day = row["listing_date"]
        n_attempted += 1

        try:
            data, note_or_err = fetch_chunk_with_retry(call_fn(token), day, day)
        except RuntimeError as e:
            log(f"  STOP-WORTHY: persistent truncation for listing {listing_id} ({day}): {e}")
            stop_reason = f"persistent truncation: {e}"
            break

        if data is None and looks_token_expired(note_or_err):
            if try_relogin():
                try:
                    data, note_or_err = fetch_chunk_with_retry(call_fn(token), day, day)
                except RuntimeError as e:
                    log(f"  STOP-WORTHY: persistent truncation for listing {listing_id} ({day}): {e}")
                    stop_reason = f"persistent truncation: {e}"
                    break
            else:
                log(f"STOPPING: session expired and re-login failed. Successful so far: {n_success}.")
                stop_reason = f"re-login failed after token expiry: {note_or_err}"
                break

        if data is None:
            if looks_rate_limited(note_or_err):
                log(f"RATE-LIMIT-SHAPED ERROR on listing {listing_id}: {note_or_err}")
                log(f"STOPPING IMMEDIATELY per instruction. Successful so far: {n_success}.")
                stop_reason = note_or_err
                break
            _log_fetch(intraday_con, listing_id, day, row["symbol_used"], str(token),
                       "FETCH_FAILED", note_or_err, 0)
            intraday_con.commit()
            n_failed += 1
            log(f"  FETCH_FAILED (API error) listing {listing_id} {row['company_name']}: {note_or_err}")
            _maybe_log_probe()
            continue

        if not data:
            _log_fetch(intraday_con, listing_id, day, row["symbol_used"], str(token),
                       "FETCH_FAILED", "zero_candles", 0)
            intraday_con.commit()
            n_failed += 1
            n_zero_candles += 1
            log(f"  FETCH_FAILED (zero candles) listing {listing_id} {row['company_name']} ({day})")
            _maybe_log_probe()
            continue

        rows = []
        now = dt.datetime.now()
        for ts, o, h, l, c, v in data:
            rows.append((listing_id, row["company_name"], row["symbol_used"], str(token), day,
                         dt.datetime.fromisoformat(ts), o, h, l, c, v, now, SOURCE_NAME, 1))
        df = pd.DataFrame(rows, columns=[
            "listing_id", "company_name", "symbol_used", "angel_token", "listing_date", "ts",
            "open", "high", "low", "close", "volume", "fetched_at", "source", "revision_seq"])
        intraday_con.register("chunk_new", df)
        intraday_con.execute("INSERT INTO bars_1min SELECT * FROM chunk_new")
        intraday_con.unregister("chunk_new")
        _log_fetch(intraday_con, listing_id, day, row["symbol_used"], str(token), "OK", None, len(data))
        intraday_con.commit()  # incremental commit -- never batch the whole run into one transaction
        n_success += 1
        _maybe_log_probe()

        if time.time() - last_heartbeat > HEARTBEAT_SECONDS:
            log(f"  heartbeat: {n_success} ok, {n_failed} failed ({n_zero_candles} zero-candle), "
                f"listing={listing_id} {row['company_name']}")
            last_heartbeat = time.time()

    log(f"=== Fetch loop done. ok={n_success} failed={n_failed} (zero_candles={n_zero_candles}) "
        f"stop_reason={stop_reason or 'completed'} ===")

    # ---- Validation against bhavcopy, BEFORE scale correction ----
    log("Running bhavcopy cross-check on everything fetched so far (pre-correction, raw-as-fetched)...")
    cmp_before = validate_against_bhavcopy(intraday_con, warehouse_con, listings)
    if cmp_before.empty:
        log("Validation produced no comparable rows (no OK fetches yet?).")
        mismatch_rate_before = None
        n_compared = 0
    else:
        n_compared = len(cmp_before)
        mismatch_rate_before = float(cmp_before["mismatch"].mean()) * 100.0
        log(f"Bhavcopy validation (BEFORE scale correction): {n_compared} listing-days compared, "
            f"mismatch rate = {mismatch_rate_before:.2f}%")

    # ---- Scale correction: Angel returns split/bonus-ADJUSTED historical
    # prices; bhavcopy is always RAW for that historical date (found live
    # during this validation pass -- see ipo_listing.rescale's own module
    # docstring). Corrected rows are appended at revision_seq=2, never
    # overwriting the as-fetched rows. ----
    log("Computing and applying per-listing scale corrections (ipo_listing.rescale)...")
    scale_report = compute_and_apply_scale_corrections(intraday_con, warehouse_con, listings)
    n_corrected = int(scale_report["corrected"].sum())
    log(f"Scale correction: {n_corrected}/{len(scale_report)} OK listings needed a correction "
        f"(|scale-1| > {int(SCALE_TOLERANCE*100)}%).")
    big_scale = scale_report[scale_report["corrected"]].copy()
    if len(big_scale):
        log(f"  Largest 10 scale factors applied:")
        for _, r in big_scale.reindex(big_scale["scale"].sub(1).abs().sort_values(ascending=False).index).head(10).iterrows():
            log(f"    {r['company_name']} (listing_id={r['listing_id']}): scale={r['scale']:.4f}")

    log("Re-running bhavcopy cross-check AFTER scale correction...")
    cmp_after = validate_against_bhavcopy(intraday_con, warehouse_con, listings)
    if cmp_after.empty:
        mismatch_rate_after = None
    else:
        mismatch_rate_after = float(cmp_after["mismatch"].mean()) * 100.0
        log(f"Bhavcopy validation (AFTER scale correction): {len(cmp_after)} listing-days compared, "
            f"mismatch rate = {mismatch_rate_after:.2f}%")
        mism = cmp_after[cmp_after["mismatch"]]
        if len(mism):
            log(f"  {len(mism)} STILL-mismatching listing-days after correction (showing up to 15):")
            for _, r in mism.head(15).iterrows():
                log(f"    listing_id={r['entity_id']} trade_date={r['trade_date']} "
                    f"open_diff={r['open_pct_diff']:.2f}% close_diff={r['close_pct_diff']:.2f}%")

    # Context-only figure, NOT a tolerance change (user instruction): what
    # fraction match closely even though the project-standard 0.1%
    # tolerance -- never loosened -- still calls them a mismatch.
    pct_within_half_pct = None
    if not cmp_after.empty:
        within = (cmp_after["open_pct_diff"] <= 0.5) & (cmp_after["close_pct_diff"] <= 0.5)
        pct_within_half_pct = float(within.mean()) * 100.0
        log(f"  Context only, NOT a tolerance change: {within.sum()}/{len(cmp_after)} "
            f"({pct_within_half_pct:.1f}%) match bhavcopy within 0.5% on BOTH open and close.")

    # ---- Exclude known data-defect listings (ipo_listing.exclusions) --
    # found during THIS validation pass, applied as code so a fresh run
    # reproduces the same final sample, never a one-off manual DB edit. ----
    if KNOWN_DATA_DEFECTS:
        log(f"Excluding {len(KNOWN_DATA_DEFECTS)} listing(s) for a known single-tick data defect "
            f"(ipo_listing.exclusions.KNOWN_DATA_DEFECTS):")
        for listing_id, reason in KNOWN_DATA_DEFECTS.items():
            row = intraday_con.execute(
                "SELECT listing_date, symbol_used, token_used, n_candles FROM fetch_log WHERE listing_id = ?",
                [listing_id],
            ).fetchone()
            if row is None:
                log(f"    listing_id={listing_id}: not found in fetch_log -- skipping exclusion (nothing to exclude)")
                continue
            day, symbol_used, token_used, n_candles = row
            _log_fetch(intraday_con, listing_id, day, symbol_used, token_used,
                       "EXCLUDED_DATA_DEFECT", reason, n_candles)
            intraday_con.commit()
            log(f"    listing_id={listing_id}: {reason}")

    # ---- Final status breakdown and DEV/TEST boundary (Section 7) ----
    status_counts = intraday_con.execute(
        "SELECT status, COUNT(*) FROM fetch_log GROUP BY status"
    ).fetchdf()
    log(f"Final fetch_log status breakdown:\n{status_counts.to_string(index=False)}")

    usable = intraday_con.execute(
        "SELECT listing_id, listing_date FROM fetch_log WHERE status = 'OK' ORDER BY listing_date"
    ).fetchdf()
    n_usable = len(usable)
    boundary = None
    dev_count = test_count = None
    if n_usable:
        dev_count = int(round(n_usable * USABLE_FRACTION_DEV))
        test_count = n_usable - dev_count
        boundary_date = usable.iloc[dev_count - 1]["listing_date"] if dev_count else None
        test_start_date = usable.iloc[dev_count]["listing_date"] if dev_count < n_usable else None
        boundary = {
            "n_usable": n_usable, "dev_count": dev_count, "test_count": test_count,
            "dev_end_date": str(boundary_date) if boundary_date is not None else None,
            "test_start_date": str(test_start_date) if test_start_date is not None else None,
        }
        log(f"DEV/TEST boundary (60/40 by listing date, on {n_usable} usable listings): "
            f"DEV={dev_count} (through {boundary_date}), TEST={test_count} (from {test_start_date})")

    # Survivorship accounting (Section 3a) -- recovered vs still-unresolved, named.
    n_direct, n_recovered, n_unresolved = len(direct), len(recovered), len(unresolved)
    pct_unresolved_of_usable = (n_unresolved / n_usable * 100.0) if n_usable else None
    survivorship = {
        "n_angel_unresolvable_at_phase1_report": 33,  # the original report's figure, different symbol basis -- see completion report
        "n_recovered_via_current_symbol_or_lineage": n_recovered,
        "n_still_unresolved": n_unresolved,
        "pct_unresolved_of_final_usable_sample": pct_unresolved_of_usable,
        "unresolved_companies": unresolved[["company_name", "symbol_at_listing", "listing_date"]]
            .astype({"listing_date": str}).to_dict("records"),
    }

    summary = {
        "generated_at": dt.datetime.now().isoformat(),
        "n_listings_total": len(listings),
        "token_resolution": {"direct": n_direct, "recovered": n_recovered, "unresolved": n_unresolved},
        "fetch_status_counts": status_counts.to_dict("records"),
        "n_zero_candles": n_zero_candles,
        "bhavcopy_validation": {
            "n_compared": n_compared,
            "mismatch_rate_pct_before_scale_correction": mismatch_rate_before,
            "mismatch_rate_pct_after_scale_correction": mismatch_rate_after,
            "n_listings_scale_corrected": n_corrected,
            "pct_within_0.5pct_context_only_not_a_tolerance_change": pct_within_half_pct,
        },
        "known_data_defect_exclusions": KNOWN_DATA_DEFECTS,
        "dev_test_boundary": boundary,
        "survivorship": survivorship,
        "stop_reason": stop_reason,
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    log(f"Summary written to {SUMMARY_PATH}")

    intraday_con.close()
    warehouse_con.close()
    log_file.close()


if __name__ == "__main__":
    main()
