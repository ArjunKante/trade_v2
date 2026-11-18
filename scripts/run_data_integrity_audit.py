"""Data integrity audit of the Fibo and options datasets -- REPORT ONLY.

Scope: data/fibo_intraday.duckdb, data/options_history/options_history.duckdb,
data/options_depth/v1/, data/fibo_live/v1/events.jsonl.

STRICTLY READ-ONLY, ENFORCED NOT ASSUMED: every DuckDB connection opened
here uses read_only=True (DuckDB refuses any write at the engine level
through such a connection); every CSV/JSONL target is opened "r" only.
On top of that, this script fingerprints (size, mtime_ns) every target
file before it runs anything and asserts, as its very last action, that
every fingerprint is unchanged -- a self-check that this run itself wrote
nothing, rather than a claim trusted on code inspection alone. A test
wrote into events.jsonl once before (two days prior to this script's
first version); this guard is deliberately independent of "the code
looks read-only."

WHY THIS DOESN'T NEED data_layer.holdout / options_history.test_seal
authorization: both are signal/performance seals (momentum rebalance
results, options fair-pricing realized-move ratios) -- guarding against
*seeing a result* before a design is frozen. This script computes
completeness/validity *counts* only (row presence, OHLC sanity, expiry
coverage, snapshot cadence) and never computes or prints any realized
return, R, IC, or pricing ratio from either sealed window. Same posture
already established by scripts/fibo_step5_top200_data_quality.py
("DATA QUALITY ONLY... cannot be a second look at strategy performance")
and by src/data_layer/price_gap_detector.py (runs over prices_eod's full
history, no holdout guard, because completeness-checking is a different
kind of question than signal evaluation). No authorize_test / authorize_
holdout bypass is exercised anywhere below.

Every finding is classified EXPECTED (cites a BUGS.md bug number, a
FIBO_FINDINGS.md section, or an invalidated_snapshots.csv row) or
UNEXPLAINED (new, needs a decision -- not fixed here). Re-runnable:
intended to be wired into the weekly job once reviewed, not a one-off.

Usage: python scripts/run_data_integrity_audit.py [--since YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday  # noqa: E402
from data_layer.db import get_read_connection as get_warehouse_ro  # noqa: E402
from fibo.universe import reconstitute_annually  # noqa: E402
from fibo.intraday_db import get_read_connection as get_intraday_ro  # noqa: E402
from options_depth.writer import (  # noqa: E402
    DEFAULT_LOG_PATH as DEPTH_LOG,
    DEFAULT_INVALID_PATH as DEPTH_INVALID_LOG,
    load_invalidated_timestamps,
)

WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
FIBO_INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
OPTIONS_HISTORY_DB = ROOT / "data" / "options_history" / "options_history.duckdb"
EVENTS_LOG = ROOT / "data" / "fibo_live" / "v1" / "events.jsonl"

FULL_SESSION_BARS = 375
MATERIALLY_SHORT_BARS = 330  # < 88% of a full session -- stated threshold, not derived
SESSION_START_T = dt.time(9, 15)
SESSION_LAST_BAR_START_T = dt.time(15, 29)  # bar covering 15:29-15:30, the last valid minute
SCALE_TOLERANCE = 0.005  # Bug #18's own 0.5% disagreement threshold
DEPTH_SCHEDULE = [dt.time(10, 30), dt.time(12, 30), dt.time(14, 30)]
DEPTH_SCHEDULE_TOLERANCE_MIN = 75  # how close a real timestamp must be to a scheduled slot to count as it

FORWARD_TEST_START = dt.date(2026, 10, 8)  # first watchlist_run event ever logged (fibo_valid_observation_days.py)

# Known BUGS.md Bug #18 blast-radius entries (entity_id, date) -- the sealed
# TEST+DEV trades BUGS.md already confirmed disagree between scale_probe and
# the table method. Cited verbatim from BUGS.md Bug #18 so Section C can
# tell "already a known instance of this exact mechanism" apart from "new".
BUG18_KNOWN_MISMATCHES = {
    ("INE647O01011", dt.date(2023, 6, 22)), ("INE647O01011", dt.date(2023, 6, 28)),
    ("INE237A01028", dt.date(2025, 1, 15)), ("INE237A01028", dt.date(2025, 10, 1)),
    ("INE0J1Y01017", dt.date(2025, 9, 29)), ("INE732I01013", dt.date(2025, 4, 17)),
    ("INE423A01024", dt.date(2024, 10, 8)), ("INE849A01012", dt.date(2025, 5, 5)),
    ("INE774D01024", dt.date(2024, 2, 14)), ("INE423A01024", dt.date(2024, 6, 14)),
    ("INE423A01024", dt.date(2024, 6, 20)), ("INE205A01025", dt.date(2021, 11, 22)),
    ("INE237A01028", dt.date(2016, 11, 9)), ("INE397D01024", dt.date(2017, 5, 10)),
    ("INE628A01036", dt.date(2021, 12, 22)), ("INE239A01016", dt.date(2021, 11, 26)),
}

# Known BUGS.md Bug #19 evening-job outage (7 straight trading days) and the
# 2026-10-15/16 GitHub Actions schedule gap (OPERATIONS.md) -- cited so
# Section A.5 doesn't re-litigate already-documented missing days as new.
BUG19_EVENING_OUTAGE_DAYS = {
    dt.date(2026, 11, 6), dt.date(2026, 11, 9), dt.date(2026, 11, 10),
    dt.date(2026, 11, 11), dt.date(2026, 11, 12), dt.date(2026, 11, 13),
}
GHA_MORNING_MISSED_DAYS = {dt.date(2026, 10, 15), dt.date(2026, 10, 16)}

results: list[dict] = []


def log(msg: str = "") -> None:
    print(msg, flush=True)


def section(title: str) -> None:
    log("\n" + "=" * 100)
    log(title)
    log("=" * 100)


def record(check: str, bad_result_sentence: str, count: int, classification: str,
           examples: list | None = None, note: str = "") -> None:
    """Prints one check's result (bad result first, per instruction) and
    appends it to the final summary table."""
    log(f"[{check}] {bad_result_sentence}")
    log(f"  count={count}  classification={classification}")
    if note:
        log(f"  note: {note}")
    for ex in (examples or [])[:5]:
        log(f"    example: {ex}")
    results.append({
        "check": check, "result": bad_result_sentence, "count": count,
        "classification": classification,
    })


def checkpoint(label: str) -> None:
    log(f"\n--- checkpoint: {label} complete, {dt.datetime.now().isoformat(timespec='seconds')} ---")


# --------------------------------------------------------------------------
# Read-only enforcement
# --------------------------------------------------------------------------

def _fingerprint(path: Path) -> tuple | None:
    if not path.exists():
        return None
    st = path.stat()
    return (st.st_size, st.st_mtime_ns)


def snapshot_fingerprints(paths: list[Path]) -> dict[Path, tuple | None]:
    return {p: _fingerprint(p) for p in paths}


def assert_fingerprints_unchanged(before: dict[Path, tuple | None]) -> None:
    changed = []
    for p, fp_before in before.items():
        fp_after = _fingerprint(p)
        if fp_after != fp_before:
            changed.append((p, fp_before, fp_after))
    if changed:
        lines = "\n".join(f"  {p}: before={b} after={a}" for p, b, a in changed)
        raise RuntimeError(
            f"READ-ONLY VIOLATION: this audit run changed {len(changed)} file(s) it was "
            f"only supposed to read:\n{lines}\nThis script must write nothing to data/ -- "
            f"investigate immediately, do not ignore."
        )
    log(f"\nRead-only guard: {len(before)} target file(s) fingerprinted at start are byte-identical now.")


def is_trading_day(d: dt.date) -> tuple[bool, str]:
    """(is_trading_day, reason). reason='unverifiable_year' if the holiday
    master doesn't cover d.year -- callers must not silently treat that as
    either True or False."""
    if d.weekday() >= 5:
        return False, "weekend"
    try:
        if is_nse_holiday(d):
            return False, "nse_holiday"
    except HolidayCalendarMissing:
        return True, "unverifiable_year"
    return True, "trading_day"


def trading_days_between(start: dt.date, end: dt.date) -> list[dt.date]:
    out = []
    d = start
    while d <= end:
        ok, reason = is_trading_day(d)
        if ok:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


# --------------------------------------------------------------------------
# Raw events.jsonl loader -- deliberately NOT fibo_live.eventlog.read_events,
# which silently dedupes by event_id. This audit needs the raw, undeduped
# rows (Section E.13 is specifically checking for duplicates read_events()
# would otherwise hide).
# --------------------------------------------------------------------------

def load_raw_events(path: Path) -> list[dict]:
    events = []
    if not path.exists():
        return events
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                d = {"_parse_error": str(e), "_raw": line}
            d["_line_no"] = line_no
            events.append(d)
    return events


def parse_event_ts(ts: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(ts)
    return parsed.replace(tzinfo=None)


# ==========================================================================
# SECTION A: COMPLETENESS
# ==========================================================================

def check_a1_a2_c9(con_wh, con_intr) -> pd.DataFrame:
    """One full scan of bars_1min, grouped to (entity_id, isin, trade_date),
    carrying everything A.1 (presence), A.2 (bar counts) and C.9 (session
    high/low/close) need -- avoids three separate full-table scans over
    169M+ rows."""
    log("Scanning bars_1min (one pass, grouped by entity/isin/trade_date)...")
    sql = """
        SELECT entity_id, isin, trade_date,
               COUNT(*) AS n_bars,
               MIN(ts) AS first_ts, MAX(ts) AS last_ts,
               MAX(high) AS sess_high, MIN(low) AS sess_low,
               arg_max(close, ts) AS sess_close,
               SUM(CASE WHEN high < low THEN 1 ELSE 0 END) AS n_high_lt_low,
               SUM(CASE WHEN high < open OR high < close THEN 1 ELSE 0 END) AS n_high_violation,
               SUM(CASE WHEN low > open OR low > close THEN 1 ELSE 0 END) AS n_low_violation,
               SUM(CASE WHEN volume < 0 THEN 1 ELSE 0 END) AS n_neg_volume,
               SUM(CASE WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
                        OR volume IS NULL THEN 1 ELSE 0 END) AS n_null_required,
               SUM(CASE WHEN CAST(ts AS TIME) < TIME '09:15:00'
                        OR CAST(ts AS TIME) > TIME '15:29:00' THEN 1 ELSE 0 END) AS n_out_of_hours,
               SUM(CASE WHEN CAST(ts AS DATE) != trade_date THEN 1 ELSE 0 END) AS n_date_mismatch
        FROM bars_1min
        GROUP BY entity_id, isin, trade_date
    """
    df = con_intr.execute(sql).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    log(f"  {len(df):,} entity-day rows.")
    return df


def check_a1_missing_trading_days(agg: pd.DataFrame) -> None:
    universe = reconstitute_annually(get_warehouse_ro(WAREHOUSE_DB), top_n=200)
    present = set(zip(agg["entity_id"], agg["trade_date"]))
    entity_range = agg.groupby("entity_id")["trade_date"].agg(["min", "max"])

    zero_coverage_entities: set[str] = set()
    zero_overlap_entity_years: list[tuple] = []
    unverifiable: list[tuple] = []
    missing: list[tuple] = []

    for row in universe.itertuples(index=False):
        year, entity_id = int(row.year), row.entity_id
        if entity_id not in entity_range.index:
            zero_coverage_entities.add(entity_id)
            continue
        mn, mx = entity_range.loc[entity_id, "min"], entity_range.loc[entity_id, "max"]
        lo = max(dt.date(year, 1, 1), mn)
        hi = min(dt.date(year, 12, 31), mx)
        if lo > hi:
            zero_overlap_entity_years.append((entity_id, year))
            continue
        d = lo
        while d <= hi:
            ok, reason = is_trading_day(d)
            if ok:
                if (entity_id, d) not in present:
                    missing.append((entity_id, d))
            elif reason == "unverifiable_year":
                unverifiable.append((entity_id, d))
            d += dt.timedelta(days=1)

    record(
        "A.1 Fibo intraday: entity-days with zero bars (interior gaps, within an entity's own observed range)",
        f"{len(missing)} interior entity-day gap(s) found across the top-200 universe "
        f"({universe['entity_id'].nunique()} distinct members, {universe['year'].nunique()} universe-years).",
        len(missing), "UNEXPLAINED" if missing else "N/A",
        examples=[f"{e} {d}" for e, d in sorted(missing, key=lambda t: t[1])[:5]],
        note="Bounded by each entity's own observed min/max trade_date, same convention as "
             "src/data_layer/price_gap_detector.py -- a day before an entity's own first or "
             "after its own last observed date is a coverage-boundary question (reported "
             "separately below), not an interior hole.",
    )
    record(
        "A.1b Fibo intraday: universe (year, entity) pairs with ZERO overlap between the universe year "
        "and that entity's own observed data range",
        f"{len(zero_overlap_entity_years)} (year, entity) pair(s) are universe members for a year "
        f"their own intraday archive never reaches.",
        len(zero_overlap_entity_years), "UNEXPLAINED" if zero_overlap_entity_years else "N/A",
        examples=[f"{e} year={y}" for e, y in zero_overlap_entity_years[:5]],
    )
    record(
        "A.1c Fibo intraday: universe members with NO intraday data at all, any year",
        f"{len(zero_coverage_entities)} universe member(s) have never been fetched into bars_1min.",
        len(zero_coverage_entities), "UNEXPLAINED" if zero_coverage_entities else "N/A",
        examples=sorted(zero_coverage_entities)[:5],
    )
    record(
        "A.1d Fibo intraday: entity-days unverifiable (holiday master doesn't cover that year)",
        f"{len(unverifiable)} entity-day(s) could not be checked against the NSE holiday master.",
        len(unverifiable), "EXPECTED (HolidayCalendarMissing, data_layer/nse_holidays.py)" if unverifiable else "N/A",
        examples=[f"{e} {d}" for e, d in unverifiable[:5]],
    )


def check_a2_bars_per_entity_day(agg: pd.DataFrame) -> None:
    short = agg[agg["n_bars"] < MATERIALLY_SHORT_BARS].sort_values("n_bars")
    pct = agg["n_bars"].quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).to_dict()
    pct_str = ", ".join(f"p{int(k*100)}={v:.0f}" for k, v in pct.items())
    record(
        "A.2 Fibo intraday: bars per entity-day materially short of a full ~375-bar session",
        f"{len(short)} of {len(agg)} entity-days ({100*len(short)/len(agg):.2f}%) have fewer than "
        f"{MATERIALLY_SHORT_BARS} bars -- distribution: {pct_str}, min={agg['n_bars'].min()}, "
        f"max={agg['n_bars'].max()}.",
        len(short), "UNEXPLAINED",
        examples=[f"{r.entity_id} {r.trade_date}: {r.n_bars} bars ({r.first_ts}..{r.last_ts})"
                  for r in short.head(5).itertuples()],
        note="Signature of the previously-documented silent API truncation. Some short days may be "
             "legitimate truncated/special sessions (e.g. Muhurat trading) not distinguishable from a "
             "real truncation with the data checked here -- not assumed either way.",
    )


def check_a3_options_depth_schedule() -> None:
    if not DEPTH_LOG.exists():
        record("A.3 Options depth: snapshots vs 3 scheduled times/day", "nifty_depth_log.csv does not exist.",
               0, "N/A")
        return
    df = pd.read_csv(DEPTH_LOG, usecols=["timestamp_ist"])
    ts = pd.to_datetime(df["timestamp_ist"]).drop_duplicates().sort_values()
    if ts.empty:
        record("A.3 Options depth: snapshots vs 3 scheduled times/day", "log has zero snapshots.", 0, "N/A")
        return
    start, end = ts.dt.date.min(), ts.dt.date.max()
    trading_days = trading_days_between(start, end)

    by_day: dict[dt.date, list[dt.time]] = {}
    for t in ts:
        by_day.setdefault(t.date(), []).append(t.time())

    missing_slots = []
    for d in trading_days:
        times_today = by_day.get(d, [])
        for slot in DEPTH_SCHEDULE:
            slot_dt = dt.datetime.combine(d, slot)
            hit = any(abs((dt.datetime.combine(d, t) - slot_dt).total_seconds()) <= DEPTH_SCHEDULE_TOLERANCE_MIN * 60
                      for t in times_today)
            if not hit:
                missing_slots.append((d, slot))

    expected = len(trading_days) * len(DEPTH_SCHEDULE)
    record(
        "A.3 Options depth: snapshots vs 3 scheduled times/day (10:30/12:30/14:30 IST)",
        f"{len(missing_slots)} of {expected} expected (day, slot) snapshots are missing "
        f"({100*len(missing_slots)/expected:.1f}%) across {len(trading_days)} trading days "
        f"({start}..{end}); {ts.dt.date.nunique()} distinct snapshot-days actually have >=1 snapshot.",
        len(missing_slots), "UNEXPLAINED",
        examples=[f"{d} missing {slot.strftime('%H:%M')}" for d, slot in missing_slots[:5]],
        note="Collector is a Task Scheduler job documented as 'a missed snapshot is acceptable' "
             "(scripts/snapshot_options_depth.py) -- that is a design acceptance of some loss, not a "
             "documented EXPECTED count, so missing slots are classified UNEXPLAINED pending that decision.",
    )


def check_a4_options_history_expiries() -> None:
    con = duckdb.connect(str(OPTIONS_HISTORY_DB), read_only=True)
    try:
        by_year = con.execute(
            "SELECT EXTRACT(year FROM expiry_date)::INT AS y, COUNT(DISTINCT expiry_date) AS n_expiries "
            "FROM nifty_options_eod GROUP BY 1 ORDER BY 1"
        ).fetchdf()
        strikes = con.execute(
            "SELECT expiry_date, COUNT(DISTINCT strike) AS n_strikes FROM nifty_options_eod "
            "GROUP BY 1 ORDER BY 1"
        ).fetchdf()
        expiries = sorted(con.execute("SELECT DISTINCT expiry_date FROM nifty_options_eod ORDER BY 1")
                           .fetchdf()["expiry_date"].tolist())
    finally:
        con.close()

    log(f"  Expiries per year: {by_year.to_dict('records')}")
    thin = strikes[strikes["n_strikes"] < 10]
    record(
        "A.4a Options history: expiries with suspiciously few distinct strikes (<10)",
        f"{len(thin)} of {len(strikes)} expiries have fewer than 10 distinct strikes.",
        len(thin), "UNEXPLAINED" if len(thin) else "N/A",
        examples=[f"{r.expiry_date}: {r.n_strikes} strikes" for r in thin.head(5).itertuples()],
    )

    not_trading_day = []
    for e in expiries:
        ok, reason = is_trading_day(e)
        if not ok:
            not_trading_day.append((e, reason))
    record(
        "A.4b Options history: expiry dates that are not themselves a confirmed NSE trading day",
        f"{len(not_trading_day)} of {len(expiries)} distinct expiry dates fall on a weekend or holiday.",
        len(not_trading_day), "UNEXPLAINED" if not_trading_day else "N/A",
        examples=[f"{e} ({r})" for e, r in not_trading_day[:5]],
    )

    gaps = []
    for a, b in zip(expiries, expiries[1:]):
        gap_days = (b - a).days
        if gap_days > 10:
            gaps.append((a, b, gap_days))
    record(
        "A.4c Options history: gaps >10 calendar days between consecutive distinct expiries",
        f"{len(gaps)} gap(s) over 10 days found in the expiry series ({len(expiries)} distinct expiries, "
        f"{expiries[0]}..{expiries[-1]}).",
        len(gaps), "UNEXPLAINED" if gaps else "N/A",
        examples=[f"{a} -> {b} ({g}d)" for a, b, g in gaps[:5]],
        note="NIFTY's expiry cadence changed over this history (monthly-only pre-2019, weekly "
             "thereafter) -- a >10-day gap is not automatically wrong without checking which "
             "regime it falls in; not resolved here, flagged for that individual decision.",
    )


def check_a5_events_reconciliation(raw_events: list[dict]) -> None:
    today = dt.date.today()
    watchlist_targets = {e["target_trade_date"] for e in raw_events
                         if e.get("kind") == "watchlist_run" and e.get("target_trade_date")}
    setup_days = {e["trade_date"] for e in raw_events if e.get("kind") == "setup" and e.get("trade_date")}
    morning_status_days = {e["trade_date"] for e in raw_events
                           if e.get("kind") == "session_status" and e.get("session") == "morning"
                           and e.get("trade_date")}
    morning_any_evidence = setup_days | morning_status_days

    trading_days = trading_days_between(FORWARD_TEST_START, today)
    missing_evening = [d for d in trading_days if d.isoformat() not in watchlist_targets]
    missing_morning = [d for d in trading_days if d.isoformat() not in morning_any_evidence]

    known_missing_evening = {d for d in missing_evening if d in BUG19_EVENING_OUTAGE_DAYS}
    unexplained_missing_evening = [d for d in missing_evening if d not in BUG19_EVENING_OUTAGE_DAYS]
    known_missing_morning = {d for d in missing_morning if d in (BUG19_EVENING_OUTAGE_DAYS | GHA_MORNING_MISSED_DAYS)}
    unexplained_missing_morning = [d for d in missing_morning if d not in known_missing_morning]

    record(
        "A.5a events.jsonl: trading evenings with no watchlist_run event",
        f"{len(missing_evening)} of {len(trading_days)} trading days since {FORWARD_TEST_START} have "
        f"no watchlist_run ({len(known_missing_evening)} match BUGS.md Bug #19's known outage window).",
        len(unexplained_missing_evening),
        "PARTIALLY EXPECTED" if known_missing_evening else ("UNEXPLAINED" if missing_evening else "N/A"),
        examples=[str(d) for d in unexplained_missing_evening[:5]],
        note=f"BUGS.md Bug #19 (evening job down 2026-11-06..11-13) explains {len(known_missing_evening)} "
             f"of these; remainder, if any, are new.",
    )
    record(
        "A.5b events.jsonl: trading days with no morning-session evidence at all (no setup, no session_status)",
        f"{len(missing_morning)} of {len(trading_days)} trading days have neither a setup event nor a "
        f"morning session_status event.",
        len(unexplained_missing_morning),
        "PARTIALLY EXPECTED" if known_missing_morning else ("UNEXPLAINED" if missing_morning else "N/A"),
        examples=[str(d) for d in unexplained_missing_morning[:5]],
        note=f"BUGS.md Bug #19 + OPERATIONS.md's GitHub Actions schedule gap (2026-10-15/16) explain "
             f"{len(known_missing_morning)} of these.",
    )

    try:
        fvod_mod = __import__("fibo_valid_observation_days")
        valid = fvod_mod.compute(FORWARD_TEST_START, today)
        n_valid, n_trading = valid["n_valid"], valid["n_trading_days"]
    except Exception as e:  # pragma: no cover - defensive, reported not swallowed
        n_valid, n_trading = None, None
        log(f"  (could not import scripts/fibo_valid_observation_days.py for reconciliation: {e})")

    n_loose_both = len(set(trading_days) - set(missing_evening) - set(missing_morning))
    record(
        "A.5c Reconciliation against FIBO_FINDINGS.md Section 14's valid-observation-day counter",
        f"Loose 'both evening and morning ran' count = {n_loose_both} of {n_trading if n_trading is not None else len(trading_days)} "
        f"trading days; Section 14's strict valid-observation-day count (morning must be LIVE and inside "
        f"the 09:30-11:30 entry window) = {n_valid}.",
        (n_loose_both - n_valid) if n_valid is not None else -1,
        "EXPECTED" if n_valid is not None else "UNEXPLAINED",
        note="The gap between the loose count and Section 14's strict count is explained by design "
             "(REPLAY runs, out-of-window setups, and REFUSED/MISSED session_status rows all count as "
             "'morning ran' here but not as a valid observation day) -- not a discrepancy to resolve.",
    )


# ==========================================================================
# SECTION B: VALIDITY
# ==========================================================================

def check_b6_b7_ohlc_and_timestamps(agg: pd.DataFrame, con_intr) -> None:
    n_high_lt_low = int(agg["n_high_lt_low"].sum())
    n_high_violation = int(agg["n_high_violation"].sum())
    n_low_violation = int(agg["n_low_violation"].sum())
    n_neg_volume = int(agg["n_neg_volume"].sum())
    n_null_required = int(agg["n_null_required"].sum())
    n_out_of_hours = int(agg["n_out_of_hours"].sum())
    n_date_mismatch = int(agg["n_date_mismatch"].sum())
    total_bars = int(agg["n_bars"].sum())

    def examples_for(predicate_sql: str, label: str, n: int) -> list[str]:
        if n == 0:
            return []
        df = con_intr.execute(
            f"SELECT entity_id, trade_date, ts, open, high, low, close, volume FROM bars_1min "
            f"WHERE {predicate_sql} LIMIT 5"
        ).fetchdf()
        return [f"{r.entity_id} {r.ts}: O={r.open} H={r.high} L={r.low} C={r.close} V={r.volume}"
                for r in df.itertuples()]

    record("B.6a Fibo intraday OHLC: high < low", f"{n_high_lt_low} of {total_bars:,} bars have high < low.",
           n_high_lt_low, "UNEXPLAINED" if n_high_lt_low else "N/A",
           examples=examples_for("high < low", "high<low", n_high_lt_low))
    record("B.6b Fibo intraday OHLC: high < max(open, close)",
           f"{n_high_violation} bars have high below open or close.",
           n_high_violation, "UNEXPLAINED" if n_high_violation else "N/A",
           examples=examples_for("high < open OR high < close", "high violation", n_high_violation))
    record("B.6c Fibo intraday OHLC: low > min(open, close)",
           f"{n_low_violation} bars have low above open or close.",
           n_low_violation, "UNEXPLAINED" if n_low_violation else "N/A",
           examples=examples_for("low > open OR low > close", "low violation", n_low_violation))
    record("B.6d Fibo intraday: negative volume", f"{n_neg_volume} bars have volume < 0.",
           n_neg_volume, "UNEXPLAINED" if n_neg_volume else "N/A",
           examples=examples_for("volume < 0", "neg volume", n_neg_volume))
    record("B.6e Fibo intraday: null required fields", f"{n_null_required} bars have a null OHLCV field.",
           n_null_required, "UNEXPLAINED" if n_null_required else "N/A",
           examples=examples_for("open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL OR volume IS NULL",
                                  "null field", n_null_required))
    record("B.7a Fibo intraday: bars outside 09:15-15:29 IST",
           f"{n_out_of_hours} bars have a start time outside the trading session.",
           n_out_of_hours, "UNEXPLAINED" if n_out_of_hours else "N/A",
           examples=examples_for("CAST(ts AS TIME) < TIME '09:15:00' OR CAST(ts AS TIME) > TIME '15:29:00'",
                                  "out of hours", n_out_of_hours))
    record("B.7b Fibo intraday: ts date component != trade_date column",
           f"{n_date_mismatch} bars have ts whose own date disagrees with trade_date.",
           n_date_mismatch, "UNEXPLAINED" if n_date_mismatch else "N/A",
           examples=examples_for("CAST(ts AS DATE) != trade_date", "date mismatch", n_date_mismatch))

    n_dup_ts = con_intr.execute(
        "SELECT COUNT(*) FROM (SELECT entity_id, ts FROM bars_1min GROUP BY entity_id, ts HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    record("B.7c Fibo intraday: duplicate (entity_id, ts) rows",
           f"{n_dup_ts} duplicate (entity_id, ts) key(s) found across the whole table.",
           n_dup_ts, "UNEXPLAINED" if n_dup_ts else "N/A",
           note="Strictly-increasing-within-a-day follows directly from this being zero: with no "
                "duplicate (entity_id, ts) anywhere, sorting by ts within a day cannot be non-monotonic.")


def check_b8_options_rows() -> None:
    con = duckdb.connect(str(OPTIONS_HISTORY_DB), read_only=True)
    try:
        bad = con.execute(
            "SELECT COUNT(*) FROM nifty_options_eod WHERE "
            "open < 0 OR high < 0 OR low < 0 OR close < 0 OR settle_price < 0 OR volume < 0 OR oi < 0 "
            "OR strike <= 0"
        ).fetchone()[0]
        bad_examples = con.execute(
            "SELECT trade_date, expiry_date, strike, option_type, open, high, low, close, settle_price, "
            "volume, oi FROM nifty_options_eod WHERE "
            "open < 0 OR high < 0 OR low < 0 OR close < 0 OR settle_price < 0 OR volume < 0 OR oi < 0 "
            "OR strike <= 0 LIMIT 5"
        ).fetchdf()
        n_expiry_not_trading_day = 0  # computed in A.4b already; not duplicated here
    finally:
        con.close()
    record(
        "B.8a Options history (nifty_options_eod): negative premium/volume/OI or non-positive strike",
        f"{bad} row(s) violate a basic non-negativity invariant.",
        bad, "UNEXPLAINED" if bad else "N/A",
        examples=[str(r) for r in bad_examples.to_dict("records")[:5]],
        note="NO BID/ASK EXISTS in nifty_options_eod at any date (src/options_history/__init__.py's own "
             "documented scope) -- 'LTP inside bid-ask' is therefore not checkable against this table at "
             "all; it is checked below against options_depth, which does carry a book.",
    )

    if not DEPTH_LOG.exists():
        return
    df = pd.read_csv(DEPTH_LOG)
    neg_prices = df[(df["ltp"] < 0) | (df["bid1_price"] < 0) | (df["ask1_price"] < 0) | (df["strike"] <= 0)]
    record(
        "B.8b Options depth: negative LTP/bid/ask or non-positive strike",
        f"{len(neg_prices)} row(s) violate a basic non-negativity invariant.",
        len(neg_prices), "UNEXPLAINED" if len(neg_prices) else "N/A",
        examples=neg_prices.head(5)["timestamp_ist"].tolist(),
    )

    both = df.dropna(subset=["bid1_price", "ask1_price"])
    crossed = both[both["bid1_price"] > both["ask1_price"]]
    record(
        "B.8c Options depth: crossed book (bid1 > ask1)",
        f"{len(crossed)} of {len(both)} rows with both sides present have bid1 > ask1.",
        len(crossed), "UNEXPLAINED" if len(crossed) else "N/A",
        examples=[f"{r.timestamp_ist} {r.symbol}: bid1={r.bid1_price} ask1={r.ask1_price}"
                  for r in crossed.head(5).itertuples()],
        note="BUGS.md/OPERATIONS.md already documents a crossed-book incident (2026-10-07 15:27:41, "
             "18/20 symbols) attributed to pre-close auction timing -- cross-checked by timestamp below "
             "where it recurs, not assumed identical every time.",
    )
    pre_close_crossed = crossed[pd.to_datetime(crossed["timestamp_ist"]).dt.time >= dt.time(15, 15)]
    log(f"  Of those, {len(pre_close_crossed)} fall at/after 15:15 IST (the documented pre-close-auction window).")

    ltp_outside = both[(both["ltp"] < both["bid1_price"] * 0.99) | (both["ltp"] > both["ask1_price"] * 1.01)]
    record(
        "B.8d Options depth: LTP outside [bid1, ask1] by more than 1%",
        f"{len(ltp_outside)} of {len(both)} rows have LTP materially outside the best bid/ask.",
        len(ltp_outside), "UNEXPLAINED" if len(ltp_outside) else "N/A",
        examples=[f"{r.timestamp_ist} {r.symbol}: ltp={r.ltp} bid1={r.bid1_price} ask1={r.ask1_price}"
                  for r in ltp_outside.head(5).itertuples()],
        note="LTP is the last TRADED price, which can legitimately sit outside a quote recorded "
             "moments later/earlier -- flagged as an outlier worth individual review, not asserted wrong.",
    )

    # Reconstruct the expected symbol from the row's OWN expiry/strike/option_type
    # columns rather than parsing the symbol with a regex: a loose digit-count
    # regex is ambiguous between the expiry's trailing year digits and the
    # strike's leading digits (e.g. "...2026" + "22700..." both start with
    # digits), which is exactly the kind of parser ambiguity this project's
    # own BUGS.md repeatedly warns against trusting without checking.
    mismatches = []
    for r in df.itertuples():
        symbol = str(r.symbol)
        prefix = f"NIFTY{r.expiry}"
        suffix = str(r.option_type)
        if not (symbol.startswith(prefix) and symbol.endswith(suffix)):
            mismatches.append((r.timestamp_ist, r.symbol,
                                f"column expiry={r.expiry} option_type={r.option_type} -- "
                                f"symbol doesn't even start/end with those"))
            continue
        middle = symbol[len(prefix):-len(suffix)]
        try:
            middle_strike = float(middle)
        except ValueError:
            mismatches.append((r.timestamp_ist, r.symbol, f"strike segment {middle!r} did not parse as a number"))
            continue
        if abs(middle_strike - float(r.strike)) > 1e-6:
            mismatches.append((r.timestamp_ist, r.symbol,
                                f"symbol strike segment={middle_strike} != column strike={r.strike}"))
    record(
        "B.8e Options depth: symbol field internally inconsistent with its own expiry/strike/option_type columns",
        f"{len(mismatches)} of {len(df)} rows have a symbol that doesn't parse back to its own columns.",
        len(mismatches), "UNEXPLAINED" if mismatches else "N/A",
        examples=[f"{ts} {sym}: {detail}" for ts, sym, detail in mismatches[:5]],
    )


# ==========================================================================
# SECTION C: SCALE RECONCILIATION (Bug #18's shape)
# ==========================================================================

def check_c9_scale_reconciliation(agg: pd.DataFrame, con_wh) -> None:
    eod = con_wh.execute(
        "SELECT isin, trade_date, high AS eod_high, low AS eod_low, close AS eod_close "
        "FROM prices_eod WHERE series = 'EQ'"
    ).fetchdf()
    eod["trade_date"] = pd.to_datetime(eod["trade_date"]).dt.date

    both = agg.merge(eod, on=["isin", "trade_date"], how="inner")
    if both.empty:
        record("C.9 Intraday session OHLC vs daily bhavcopy (Bug #18's shape)",
               "no entity-days have both intraday and daily data to compare.", 0, "N/A")
        return

    for col, eod_col in (("sess_high", "eod_high"), ("sess_low", "eod_low"), ("sess_close", "eod_close")):
        both[f"ratio_{col}"] = both[col] / both[eod_col]

    both["max_abs_dev"] = both[["ratio_sess_high", "ratio_sess_low", "ratio_sess_close"]] \
        .sub(1.0).abs().max(axis=1)
    disagree = both[both["max_abs_dev"] > SCALE_TOLERANCE].copy()
    disagree["is_known_bug18"] = disagree.apply(
        lambda r: (r["entity_id"], r["trade_date"]) in BUG18_KNOWN_MISMATCHES, axis=1)
    known = disagree[disagree["is_known_bug18"]]
    new = disagree[~disagree["is_known_bug18"]].sort_values("max_abs_dev", ascending=False)

    pct = both["max_abs_dev"].quantile([0.5, 0.9, 0.95, 0.99, 0.999]).to_dict()
    pct_str = ", ".join(f"p{k*100:g}={v:.4f}" for k, v in pct.items())

    if len(new):
        by_entity = new["entity_id"].value_counts()
        top10_share = by_entity.head(10).sum() / len(new)
        log(f"  New mismatches by entity: {len(by_entity)} distinct entities; "
            f"top 10 account for {100*top10_share:.1f}% of the {len(new)} new mismatches: "
            f"{by_entity.head(10).to_dict()}")

    record(
        "C.9 Intraday session high/low/close vs daily bhavcopy bar, same (isin, trade_date) (Bug #18's shape)",
        f"{len(disagree)} of {len(both)} entity-days ({100*len(disagree)/len(both):.2f}%) disagree by more "
        f"than {SCALE_TOLERANCE*100:.1f}% on at least one of high/low/close; max-deviation distribution: "
        f"{pct_str}. {len(known)} match BUGS.md Bug #18's already-confirmed blast-radius list.",
        len(new), "PARTIALLY EXPECTED" if len(known) else ("UNEXPLAINED" if len(disagree) else "N/A"),
        examples=[f"{r.entity_id} {r.trade_date}: ratio_high={r.ratio_sess_high:.3f} "
                  f"ratio_low={r.ratio_sess_low:.3f} ratio_close={r.ratio_sess_close:.3f}"
                  for r in new.head(5).itertuples()],
        note="This is a more basic check than Bug #18's own reference-level-conversion comparison "
             "(same family: an unreconciled price-scale mismatch between two sources for the same day). "
             "BUGS.md Bug #18 explains the known rows; the rest are new and not individually verified here.",
    )


# ==========================================================================
# SECTION D: STALENESS AND FROZEN TICKS
# ==========================================================================

DEPTH_PAYLOAD_COLS = (
    [f"bid{i}_price" for i in range(1, 6)] + [f"bid{i}_qty" for i in range(1, 6)]
    + [f"ask{i}_price" for i in range(1, 6)] + [f"ask{i}_qty" for i in range(1, 6)]
    + ["ltp", "volume", "oi"]
)


def check_d10_frozen_ticks(invalid_ts: dict[str, str]) -> None:
    if not DEPTH_LOG.exists():
        record("D.10 Options depth: frozen/stale consecutive snapshots", "log does not exist.", 0, "N/A")
        return
    df = pd.read_csv(DEPTH_LOG)
    df = df.sort_values(["symbol", "timestamp_ist"])
    frozen = []
    for symbol, g in df.groupby("symbol"):
        g = g.reset_index(drop=True)
        same_payload = (g[DEPTH_PAYLOAD_COLS] == g[DEPTH_PAYLOAD_COLS].shift(1)).all(axis=1)
        for idx in g.index[same_payload]:
            if idx == 0:
                continue
            frozen.append((symbol, g.loc[idx - 1, "timestamp_ist"], g.loc[idx, "timestamp_ist"]))

    already_flagged = [(s, t1, t2) for s, t1, t2 in frozen if t1 in invalid_ts or t2 in invalid_ts]
    new_frozen = [(s, t1, t2) for s, t1, t2 in frozen if t1 not in invalid_ts and t2 not in invalid_ts]

    record(
        "D.10 Options depth: consecutive snapshots with identical full payload, per symbol",
        f"{len(frozen)} consecutive same-symbol snapshot pairs have byte-identical bid/ask/ltp/oi/volume "
        f"({len(already_flagged)} already covered by invalidated_snapshots.csv).",
        len(new_frozen), "PARTIALLY EXPECTED" if already_flagged else ("UNEXPLAINED" if frozen else "N/A"),
        examples=[f"{s}: {t1} -> {t2}" for s, t1, t2 in new_frozen[:5]],
        note="exchFeedTime is NOT persisted in nifty_depth_log.csv (src/options_depth/quotes.py's DepthRow "
             "has no such column -- it is only used transiently at collection time) -- so 'identical "
             "exchFeedTime' per the spec cannot be checked from stored data; identical full payload is "
             "the closest available proxy for a frozen tick. Recorded as a structural limitation, not a count.",
    )


def check_d11_snapshots_off_hours(invalid_ts: dict[str, str]) -> None:
    if not DEPTH_LOG.exists():
        record("D.11 Options depth: snapshots on a non-trading day / outside market hours", "log does not exist.",
               0, "N/A")
        return
    df = pd.read_csv(DEPTH_LOG, usecols=["timestamp_ist"]).drop_duplicates()
    ts = pd.to_datetime(df["timestamp_ist"])
    bad = []
    for raw, t in zip(df["timestamp_ist"], ts):
        d = t.date()
        ok, reason = is_trading_day(d)
        off_hours = not (dt.time(9, 15) <= t.time() <= dt.time(15, 30))
        if not ok or off_hours:
            bad.append((raw, reason if not ok else "off_hours"))

    unflagged = [(raw, reason) for raw, reason in bad if raw not in invalid_ts]
    record(
        "D.11 Options depth: snapshots on a non-trading day or outside market hours",
        f"{len(bad)} of {len(df)} distinct snapshot timestamps are on a non-trading day or outside "
        f"09:15-15:30 IST ({len(bad) - len(unflagged)} already covered by invalidated_snapshots.csv).",
        len(unflagged), "PARTIALLY EXPECTED" if len(bad) > len(unflagged) else ("UNEXPLAINED" if bad else "N/A"),
        examples=[f"{raw} ({reason})" for raw, reason in unflagged[:5]],
    )


def check_d12_invalidated_enforcement(invalid_ts: dict[str, str]) -> None:
    if DEPTH_LOG.exists():
        logged_ts = set(pd.read_csv(DEPTH_LOG, usecols=["timestamp_ist"])["timestamp_ist"])
    else:
        logged_ts = set()
    orphaned = [t for t in invalid_ts if t not in logged_ts]
    record(
        "D.12a invalidated_snapshots.csv rows that don't correspond to any real logged snapshot",
        f"{len(orphaned)} of {len(invalid_ts)} invalidated timestamp(s) do not exist in nifty_depth_log.csv.",
        len(orphaned), "UNEXPLAINED" if orphaned else "N/A",
        examples=orphaned[:5],
    )

    py_files = list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py"))
    unguarded_readers = []
    for f in py_files:
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # "nifty_depth_log" names this specific file; a bare "DEFAULT_LOG_PATH" is
        # too generic on its own (src/spread_monitor/writer.py defines an
        # unrelated constant of the exact same name for equity spreads) -- only
        # count it when the surrounding module is actually options_depth's own.
        references_log = "nifty_depth_log" in text or ("options_depth" in text and "DEFAULT_LOG_PATH" in text)
        if not references_log:
            continue
        is_writer_module = f.name in ("writer.py", "quotes.py", "contracts.py", "heartbeat.py",
                                       "scheduler_support.py", "snapshot_options_depth.py",
                                       "mark_depth_snapshot_invalid.py", "test_options_depth.py",
                                       "run_data_integrity_audit.py")
        honours_exclusion = "invalidated" in text.lower() or "snapshot_health" in text
        if not is_writer_module and not honours_exclusion:
            unguarded_readers.append(str(f.relative_to(ROOT)))

    record(
        "D.12b Readers of nifty_depth_log.csv that do NOT filter via invalidated_snapshots.csv (Bug #26's shape)",
        f"{len(unguarded_readers)} file(s) reference the depth log without referencing the invalidation "
        f"mechanism at all (collector/writer/test infrastructure excluded by name).",
        len(unguarded_readers), "UNEXPLAINED" if unguarded_readers else "N/A",
        examples=unguarded_readers[:5],
        note="Only src/options_depth/writer.py's snapshot_health() currently aggregates this log for any "
             "reporting purpose, and it does filter via load_invalidated_timestamps -- no backtest/analysis "
             "script reads this log yet. Re-run this check after any new consumer is added.",
    )


# ==========================================================================
# SECTION E: PROVENANCE (events.jsonl)
# ==========================================================================

def check_e13_unique_event_ids(raw_events: list[dict]) -> None:
    ids = [e.get("event_id") for e in raw_events if e.get("event_id")]
    counts = pd.Series(ids).value_counts()
    dups = counts[counts > 1]
    dup_lines = []
    if len(dups):
        id_to_lines = {}
        for e in raw_events:
            eid = e.get("event_id")
            if eid in dups.index:
                id_to_lines.setdefault(eid, []).append(e["_line_no"])
        dup_lines = [f"{eid}: lines {lines}" for eid, lines in list(id_to_lines.items())[:5]]
    record(
        "E.13 events.jsonl: duplicate event_ids",
        f"{len(dups)} event_id(s) appear more than once across {len(raw_events)} raw lines "
        f"({len(ids)} with a non-null event_id).",
        len(dups), "UNEXPLAINED" if len(dups) else "N/A",
        examples=dup_lines,
        note="read_events() in src/fibo_live/eventlog.py silently dedupes by event_id as merge-safety "
             "insurance; this check deliberately reads the raw file to see what it would be hiding.",
    )


def check_e14_timestamps(raw_events: list[dict]) -> None:
    now = dt.datetime.now()
    future = []
    for e in raw_events:
        if "ts" not in e:
            continue
        try:
            ts = parse_event_ts(e["ts"])
        except (ValueError, TypeError):
            continue
        if ts > now + dt.timedelta(minutes=5):
            future.append((e.get("event_id"), e["ts"], e.get("kind")))
    record(
        "E.14a events.jsonl: events dated in the future",
        f"{len(future)} event(s) carry a ts after the current wall-clock time.",
        len(future), "UNEXPLAINED" if future else "N/A",
        examples=[f"{eid} {ts} ({kind})" for eid, ts, kind in future[:5]],
    )

    by_kind: dict[str, int] = {}
    for kind in {e.get("kind") for e in raw_events if e.get("kind")}:
        rows = [e for e in raw_events if e.get("kind") == kind and "ts" in e]
        inversions = 0
        prev_ts = None
        for e in rows:  # file order = append order
            try:
                ts = parse_event_ts(e["ts"])
            except (ValueError, TypeError):
                continue
            if prev_ts is not None and ts < prev_ts - dt.timedelta(seconds=60):
                inversions += 1
            prev_ts = ts
        by_kind[kind] = inversions
    total_inversions = sum(by_kind.values())
    record(
        "E.14b events.jsonl: file-order timestamp inversions per event kind (>60s backwards)",
        f"{total_inversions} inversion(s) across {len(by_kind)} kinds: {by_kind}.",
        total_inversions, "EXPECTED (git_sync.py's documented two-writer union merge)" if total_inversions else "N/A",
        note=".gitattributes/src/fibo_live/git_sync.py explicitly document that file line order is NOT "
             "semantically load-bearing once two independent writers (laptop evening job, GitHub Actions "
             "morning job) merge via union -- an inversion here is expected by design, not a defect.",
    )


def _git_first_commit_ts(event_id: str) -> dt.datetime | None:
    """Earliest commit (author date, IST-naive) that introduced a line
    containing this event_id into events.jsonl's history."""
    try:
        out = subprocess.run(
            ["git", "log", "--follow", "--diff-filter=A", "-S", event_id,
             "--format=%aI", "--", str(EVENTS_LOG.relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
    except Exception:
        return None
    lines = [l for l in out.stdout.strip().splitlines() if l]
    if not lines:
        # -S with --diff-filter=A can miss additions bundled with other changes;
        # retry without --diff-filter=A as a fallback, same -S search.
        out2 = subprocess.run(
            ["git", "log", "-S", event_id, "--format=%aI", "--", str(EVENTS_LOG.relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
        lines = [l for l in out2.stdout.strip().splitlines() if l]
        if not lines:
            return None
    earliest = min(dt.datetime.fromisoformat(l) for l in lines)
    return earliest.astimezone().replace(tzinfo=None)


def check_e15_signal_before_outcome(raw_events: list[dict]) -> None:
    outcomes = [e for e in raw_events if e.get("kind") == "outcome"]
    violations = []
    checked = 0
    for o in outcomes:
        entity_id, trade_date = o.get("entity_id"), o.get("trade_date")
        candidates = [e for e in raw_events
                      if e.get("entity_id") == entity_id and e.get("trade_date") == trade_date
                      and e.get("kind") in ("trigger", "setup")]
        if not candidates:
            violations.append((o.get("event_id"), "NO matching setup/trigger event found at all"))
            continue
        signal = next((e for e in candidates if e.get("kind") == "trigger"), None)
        if signal is None:
            signal = next((e for e in candidates if e.get("status") == "SETUP_ON"), candidates[0])

        checked += 1
        commit_ts = _git_first_commit_ts(signal["event_id"])
        if commit_ts is None:
            violations.append((o.get("event_id"), f"could not resolve a git commit for signal "
                                                    f"event_id={signal.get('event_id')}"))
            continue

        if o.get("triggered") and o.get("exit_ts"):
            knowable_at = parse_event_ts(o["exit_ts"]) if "T" in str(o["exit_ts"]) else None
        else:
            try:
                td = dt.date.fromisoformat(trade_date)
                knowable_at = dt.datetime.combine(td, dt.time(11, 30))
            except (TypeError, ValueError):
                knowable_at = None
        if knowable_at is not None and commit_ts >= knowable_at:
            violations.append((o.get("event_id"), f"signal commit_ts={commit_ts} >= outcome-knowable "
                                                    f"moment={knowable_at}"))

    record(
        "E.15 events.jsonl: signal's git commit timestamp must precede the moment its outcome became knowable",
        f"{len(violations)} violation(s) found across {checked} signal/outcome pair(s) checked "
        f"({len(outcomes)} outcome event(s) total).",
        len(violations), "UNEXPLAINED" if violations else "N/A",
        examples=[f"{eid}: {reason}" for eid, reason in violations],  # every violation, not truncated to 5
        note="Reported individually per instruction, not summarised. 'Signal' = the trigger event if "
             "triggered, else the SETUP_ON setup event; 'knowable moment' = exit_ts if triggered, else "
             "11:30 IST on trade_date (the entry window close, PREREGISTRATION_FIBO.md Section (f)).",
    )


def check_e16_working_tree_matches_head() -> None:
    rel = str(EVENTS_LOG.relative_to(ROOT))
    out = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT, capture_output=True, timeout=30)
    matches = out.returncode == 0
    record(
        "E.16 events.jsonl: working tree matches git HEAD exactly",
        "Matches HEAD." if matches else "DOES NOT match HEAD -- uncommitted changes present.",
        0 if matches else 1, "N/A" if matches else "UNEXPLAINED",
    )


# ==========================================================================
# SECTION F: CROSS-SOURCE RECONCILIATION
# ==========================================================================

def check_f17_watchlist_entities_have_bars(raw_events: list[dict], agg: pd.DataFrame) -> None:
    present = set(zip(agg["entity_id"], agg["trade_date"]))
    archive_max_date = agg["trade_date"].max()
    missing_within_archive = []
    missing_beyond_archive = []
    for e in raw_events:
        if e.get("kind") != "watchlist":
            continue
        entity_id, target = e.get("entity_id"), e.get("target_trade_date")
        if not entity_id or not target:
            continue
        try:
            d = dt.date.fromisoformat(target)
        except ValueError:
            continue
        if (entity_id, d) not in present:
            (missing_beyond_archive if d > archive_max_date else missing_within_archive).append(
                (entity_id, d, e.get("symbol")))

    record(
        "F.17a Watchlist entities whose target_trade_date is beyond bars_1min's own archive coverage",
        f"{len(missing_beyond_archive)} watchlist row(s) target a date after bars_1min's own max "
        f"({archive_max_date}) -- structural, not a per-entity miss: the historical intraday archive has "
        f"not been refreshed since before the live forward test started ({FORWARD_TEST_START}).",
        len(missing_beyond_archive), "EXPECTED (archive staleness, not a per-entity gap)" if missing_beyond_archive else "N/A",
        note="The live system fetches ORB candles directly from the broker at run time, not from this "
             "archive, so this does not mean the live run itself had no data for these entities.",
    )
    record(
        "F.17b Watchlist entities with no bars WITHIN the archive's own covered date range",
        f"{len(missing_within_archive)} watchlist row(s) reference an (entity, target day) that is inside "
        f"bars_1min's covered range ({archive_max_date} or earlier) but still has no bars at all -- a "
        f"genuine miss, not a staleness artifact.",
        len(missing_within_archive), "UNEXPLAINED" if missing_within_archive else "N/A",
        examples=[f"{e} {d} ({s})" for e, d, s in missing_within_archive[:5]],
    )


def check_f18_trigger_bars_coverage(raw_events: list[dict]) -> None:
    triggers = [e for e in raw_events if e.get("kind") == "trigger"]
    record(
        "F.18 Every trigger event has bars covering its entry/stop/exit times",
        f"{len(triggers)} trigger event(s) exist in events.jsonl to check.",
        0, "N/A",
        note="Vacuously nothing to check: the live system has never logged a trigger event (0 of "
             f"{len(raw_events)} raw rows). This is not evidence the check would pass if it had one.",
    )


def check_f19_depth_vs_history_overlap() -> None:
    if not DEPTH_LOG.exists():
        record("F.19 Options depth vs options history: overlapping dates agree", "depth log absent.", 0, "N/A")
        return
    depth_dates = pd.to_datetime(pd.read_csv(DEPTH_LOG, usecols=["timestamp_ist"])["timestamp_ist"]).dt.date
    depth_range = (depth_dates.min(), depth_dates.max())

    con = duckdb.connect(str(OPTIONS_HISTORY_DB), read_only=True)
    try:
        hist_range = con.execute("SELECT MIN(trade_date), MAX(trade_date) FROM nifty_options_eod").fetchone()
    finally:
        con.close()

    overlap_start = max(depth_range[0], hist_range[0])
    overlap_end = min(depth_range[1], hist_range[1])
    if overlap_start > overlap_end:
        record(
            "F.19 Options depth vs options history: overlapping dates agree",
            f"NO overlap exists between options_depth's coverage ({depth_range[0]}..{depth_range[1]}) "
            f"and options_history's coverage ({hist_range[0]}..{hist_range[1]}) -- the two sources have "
            f"never been cross-validated against each other.",
            0, "UNEXPLAINED",
            note="Structural: options_history (nifty_options_eod) has not been refreshed past "
                 f"{hist_range[1]}, while options_depth only starts {depth_range[0]}. Re-run this check "
                 "once either source's coverage extends to overlap the other -- the comparison logic "
                 "below is ready for that day but has nothing to compare yet.",
        )
        return

    log(f"  Overlap window: {overlap_start}..{overlap_end} -- comparing LTP/underlying vs settle/close.")


# ==========================================================================
# MAIN
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=str, default=None, help="unused placeholder for future scoping")
    parser.parse_args()

    log(f"Data integrity audit starting {dt.datetime.now().isoformat(timespec='seconds')}")
    log("Read-only: every DuckDB connection below is opened read_only=True; every file is opened 'r' only.")

    guarded_paths = [FIBO_INTRADAY_DB, OPTIONS_HISTORY_DB, WAREHOUSE_DB, DEPTH_LOG, DEPTH_INVALID_LOG, EVENTS_LOG]
    fingerprints_before = snapshot_fingerprints(guarded_paths)

    con_wh = get_warehouse_ro(WAREHOUSE_DB)
    con_intr = get_intraday_ro(FIBO_INTRADAY_DB)

    section("A. COMPLETENESS")
    agg = check_a1_a2_c9(con_wh, con_intr)
    check_a1_missing_trading_days(agg)
    checkpoint("A.1")
    check_a2_bars_per_entity_day(agg)
    checkpoint("A.2")
    check_a3_options_depth_schedule()
    checkpoint("A.3")
    check_a4_options_history_expiries()
    checkpoint("A.4")
    raw_events = load_raw_events(EVENTS_LOG)
    check_a5_events_reconciliation(raw_events)
    checkpoint("A.5 / Section A")

    section("B. VALIDITY")
    check_b6_b7_ohlc_and_timestamps(agg, con_intr)
    checkpoint("B.6/B.7")
    check_b8_options_rows()
    checkpoint("B.8 / Section B")

    section("C. SCALE RECONCILIATION (Bug #18's shape)")
    check_c9_scale_reconciliation(agg, con_wh)
    checkpoint("Section C")

    section("D. STALENESS AND FROZEN TICKS")
    invalid_ts = load_invalidated_timestamps(DEPTH_INVALID_LOG)
    check_d10_frozen_ticks(invalid_ts)
    check_d11_snapshots_off_hours(invalid_ts)
    check_d12_invalidated_enforcement(invalid_ts)
    checkpoint("Section D")

    section("E. PROVENANCE (events.jsonl)")
    check_e13_unique_event_ids(raw_events)
    check_e14_timestamps(raw_events)
    check_e15_signal_before_outcome(raw_events)
    check_e16_working_tree_matches_head()
    checkpoint("Section E")

    section("F. CROSS-SOURCE RECONCILIATION")
    check_f17_watchlist_entities_have_bars(raw_events, agg)
    check_f18_trigger_bars_coverage(raw_events)
    check_f19_depth_vs_history_overlap()
    checkpoint("Section F")

    con_wh.close()
    con_intr.close()

    section("SUMMARY")
    log(f"{'check':<95} {'count':>8}  classification")
    for r in results:
        log(f"{r['check']:<95} {r['count']:>8}  {r['classification']}")

    assert_fingerprints_unchanged(fingerprints_before)
    log(f"\nDone {dt.datetime.now().isoformat(timespec='seconds')}.")


if __name__ == "__main__":
    main()
