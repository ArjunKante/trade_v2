"""Freeze today's top-decile momentum_12_1 basket -- a single, dated,
append-only, NEVER-recomputed record, written before any outcome is
known, so that a later check-in can measure a real forward return
instead of a retrospective one.

THIS IS NOT A STRATEGY, A SIGNAL, OR A VALIDATED RESULT. It is one
dated snapshot. One basket, one window, is a single descriptive data
point when it resolves at check-in -- see OPERATIONS.md's own note on
this script for the full statement of what this is and is not (recorded
there per instruction, not just here, so it cannot drift).

THIS SCRIPT, LIKE `scripts/run_momentum_persistence_monitor.py` before
it, PASSES `authorize_holdout=True` to read today's price. Per
`FINDINGS.md` Section 7 and `MOMENTUM_PERSISTENCE_MONITOR.md`: the
historical holdout is RETIRED, not merely "not charged" -- there is no
slot left to spend. Logged to `data/holdout_access_log.txt` as an audit
trail, same convention as the persistence monitor.

Universe, exclusions, and top-decile selection are the EXACT methodology
`scripts/run_momentum_backtest.py` already used and already reported
(same universe via `read_full_entity_panel_authorized`, same rolling-
20-day-median-turnover liquidity terciles, same `quantile(1-0.10)`
top-decile cut, same `REBALANCE_DAYS=63` horizon) -- with ONE deliberate
refinement, stated explicitly rather than silently applied: this script
ALSO applies the lineage-jump NaN-guard (`unexplained_jump_boundaries`)
to the momentum computation itself and the same-ISIN full-entity
exclusion (BUGS.md Bug #11), the same two guards
`run_momentum_persistence_monitor.py` already applies and the original
backtest script (written before Bug #11) does not. The backtest's own
already-published CAGR/Sharpe numbers are untouched by this -- this is
a new, separate snapshot, not a recomputation of that result.

Appends exactly ONE row to `monitor_logs/momentum_basket_log.jsonl` per
run, refusing to run if a row for today's snapshot date already exists
(never overwrites, never edits a past row). Committed with the code
(not under `data/`, which is gitignored), same convention as the
persistence monitor's own CSV log.

Usage:
    python scripts/run_momentum_basket_snapshot.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_full_entity_panel_authorized
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday
from factors.momentum import compute_momentum_12_1
from monitor.persistence import same_isin_jump_excluded_entities

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT_LOG_PATH = ROOT / "data" / "holdout_access_log.txt"
BASKET_LOG_PATH = ROOT / "monitor_logs" / "momentum_basket_log.jsonl"

REBALANCE_DAYS = 63  # momentum's own tested holding/rebalance horizon (scripts/run_momentum_backtest.py)
DECILE_FRAC = 0.10
MIN_CROSS_SECTION_N = 20
COST_BY_TERCILE_BPS = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}  # unchanged from the backtest


def _append_holdout_access_log(reason: str) -> None:
    HOLDOUT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HOLDOUT_LOG_PATH, "a") as f:
        f.write(
            f"{dt.datetime.now().isoformat()} | scripts/run_momentum_basket_snapshot.py | "
            f"authorize_holdout=True | {reason}\n"
        )


def _next_nse_trading_day(d: dt.date) -> dt.date:
    """Steps forward one calendar day at a time, skipping weekends and any
    weekday the holiday master CAN confirm was a holiday -- same fail-safe
    stance `box_theory.holiday.previous_nse_trading_day` takes (an
    unverifiable day, e.g. one in a year the holiday master doesn't cover,
    is treated as an ordinary trading day, never silently assumed to be a
    holiday). Reimplemented here, stepping FORWARD, since no forward
    stepper exists anywhere in this project yet."""
    candidate = d + dt.timedelta(days=1)
    while True:
        if candidate.weekday() >= 5:
            candidate += dt.timedelta(days=1)
            continue
        try:
            if is_nse_holiday(candidate):
                candidate += dt.timedelta(days=1)
                continue
        except HolidayCalendarMissing:
            pass
        return candidate


def add_nse_trading_days(start: dt.date, n: int) -> tuple[dt.date, bool]:
    """(check_in_date, calendar_uncertain). `calendar_uncertain` is True
    if any stepped-through day fell in a year the holiday master doesn't
    cover (the master covers 2016-2026 as of this script's writing) --
    stated explicitly in the recorded basket rather than presented as
    exact, since an unconfirmed NSE holiday in that stretch (e.g. a
    January 2027 holiday) would shift the true 63rd trading day by a day
    or two from this calculation."""
    d = start
    uncertain = False
    for _ in range(n):
        d = _next_nse_trading_day(d)
        try:
            is_nse_holiday(d)  # probe only, to detect calendar coverage; result already applied above
        except HolidayCalendarMissing:
            uncertain = True
    return d, uncertain


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    excluded = same_isin_jump_excluded_entities(con)  # BUGS.md Bug #11
    panel_all = read_full_entity_panel_authorized(con, authorize_holdout=True)
    panel = panel_all[~panel_all["entity_id"].isin(excluded)].reset_index(drop=True)
    jump_dates = unexplained_jump_boundaries(con, before=None)

    _append_holdout_access_log(
        f"ONE-TIME DATED SNAPSHOT (momentum basket record, scripts/run_momentum_basket_snapshot.py) -- "
        f"NOT a backtest evaluation or pass/fail verdict; a forward-looking record frozen today to be "
        f"checked in {REBALANCE_DAYS} NSE trading days from now. Reads against the HISTORICAL HOLDOUT, "
        f"RETIRED per FINDINGS.md Section 7 (same justification already used by "
        f"scripts/run_momentum_persistence_monitor.py). {len(excluded)} same-ISIN-jump entities excluded "
        f"(BUGS.md Bug #11)."
    )
    print(f"Holdout access logged to {HOLDOUT_LOG_PATH}", file=sys.stderr, flush=True)

    mom = compute_momentum_12_1(panel, unexplained_jump_dates=jump_dates)

    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
    p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
        lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
        if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index)
    )
    liq = p[["entity_id", "trade_date", "_tercile"]]

    m = mom.merge(liq, on=["entity_id", "trade_date"]).merge(
        panel[["entity_id", "trade_date", "raw_close"]], on=["entity_id", "trade_date"]
    )
    m = m.dropna(subset=["value", "_tercile"])

    # latest date with a large enough cross-section to cut a decile from --
    # NOT necessarily literally "today": EOD ingestion lags the calendar
    # date by a few days, stated explicitly in the recorded basket rather
    # than silently treating a stale date as today's.
    candidate_dates = sorted(m["trade_date"].unique(), reverse=True)
    snapshot_date = None
    for d in candidate_dates:
        if len(m[m["trade_date"] == d]) >= MIN_CROSS_SECTION_N:
            snapshot_date = d
            break
    if snapshot_date is None:
        print("No date in the panel has a large enough momentum cross-section. Nothing recorded.",
              file=sys.stderr)
        return 1
    snapshot_date = pd.Timestamp(snapshot_date).date()
    today = dt.date.today()
    if snapshot_date != today:
        print(f"NOTE: latest usable price/momentum date is {snapshot_date}, not today ({today}) -- "
              f"EOD data ingestion lag. Recording against {snapshot_date}, stated explicitly in the log.",
              file=sys.stderr)

    day = m[m["trade_date"] == pd.Timestamp(snapshot_date)].copy()
    cutoff = day["value"].quantile(1 - DECILE_FRAC)
    top = day[day["value"] >= cutoff].sort_values("value", ascending=False).reset_index(drop=True)
    top["rank"] = top.index + 1

    # symbol lookup: prices_eod has its own `symbol` column, joined via isin_lineage at the snapshot date
    entity_ids = top["entity_id"].tolist()
    placeholders = ",".join("?" * len(entity_ids))
    sym_df = con.execute(
        f"""
        SELECT l.entity_id, p.symbol, p.isin
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        WHERE l.entity_id IN ({placeholders}) AND p.trade_date = ?
        """,
        entity_ids + [snapshot_date],
    ).fetchdf()
    con.close()

    top = top.merge(sym_df, on="entity_id", how="left")

    check_in_date, calendar_uncertain = add_nse_trading_days(snapshot_date, REBALANCE_DAYS)

    holdings = [
        {
            "entity_id": row["entity_id"], "symbol": row["symbol"], "isin": row["isin"],
            "rank": int(row["rank"]), "momentum_12_1": float(row["value"]),
            "raw_close": float(row["raw_close"]), "liquidity_tercile": str(row["_tercile"]),
        }
        for _, row in top.iterrows()
    ]

    record = {
        "schema": "momentum_basket_v1",
        "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
        "snapshot_date": str(snapshot_date),
        "check_in_date": str(check_in_date),
        "check_in_date_calendar_uncertain": calendar_uncertain,
        "rebalance_horizon_trading_days": REBALANCE_DAYS,
        "universe": "all INE/IN9 EQ entities (read_full_entity_panel_authorized), "
                    "same-ISIN-jump entities excluded (BUGS.md Bug #11), "
                    "lineage-jump NaN-guard applied to momentum_12_1 (unexplained_jump_boundaries)",
        "selection": f"top decile by momentum_12_1 (value >= {DECILE_FRAC:.0%} quantile cutoff), "
                     f"min {MIN_CROSS_SECTION_N} names in cross-section",
        "n_eligible_cross_section": int(len(day)),
        "n_holdings": len(holdings),
        "price_scale": "RAW -- prices_eod.close as published (NOT entity-adjusted)",
        "weighting": "equal-weighted, not yet computed (no return exists until check-in)",
        "cost_model_to_apply_at_checkin": "tercile model, see OPERATIONS.md: "
                                           "high_liq=23bps, mid_liq=32.5bps, low_liq=118bps round-trip",
        "status": "recorded, not yet checked in -- no return has been computed",
        "holdout_access_log_entry": "data/holdout_access_log.txt (see entry at recorded_at timestamp above)",
        "holdings": holdings,
    }

    BASKET_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if BASKET_LOG_PATH.exists():
        with open(BASKET_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                existing = json.loads(line)
                if existing.get("snapshot_date") == str(snapshot_date):
                    print(f"A basket for snapshot_date={snapshot_date} is already recorded in "
                          f"{BASKET_LOG_PATH}. Refusing to record a duplicate -- this log is append-only "
                          f"and never edited.", file=sys.stderr)
                    return 1

    with open(BASKET_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    uncertain_note = (
        " -- calendar uncertain beyond the holiday master's known coverage for part of this stretch"
        if calendar_uncertain else ""
    )
    print(f"\n=== MOMENTUM BASKET RECORDED -- {snapshot_date} ===")
    print(f"Check-in date: {check_in_date} ({REBALANCE_DAYS} NSE trading days forward{uncertain_note})")
    print(f"{len(holdings)} holdings, cross-section n={len(day)}")
    print(f"{'rank':>4s} {'symbol':>12s} {'entity_id':>14s} {'momentum_12_1':>14s} {'raw_close':>12s} {'tercile':>10s}")
    for h in holdings:
        print(f"{h['rank']:>4d} {str(h['symbol']):>12s} {h['entity_id']:>14s} "
              f"{h['momentum_12_1']*100:>13.2f}% {h['raw_close']:>12.2f} {h['liquidity_tercile']:>10s}")
    print(f"\nAppended one row to {BASKET_LOG_PATH}. No return computed -- nothing to compute yet.")
    print("This is NOT a validated result. See OPERATIONS.md for what this is and is not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
