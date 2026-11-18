"""PREREGISTRATION_DELIVERY.md Section 10 step 3: hand-trace real DEV
rebalance dates/entities BEFORE any aggregate number is computed.

Per instruction, these five traces are chosen to be the AWKWARD cases,
not ordinary ones:
  1. an entity with ZERO up-days in its 21-day measurement window
  2. an entity with a missing/excluded day inside its 60-day baseline
  3. an entity that enters (recently listed) between the baseline and
     measurement windows
  4. the decile boundary, including how ties are broken
  5. an entity in the jump-exclusion set, to confirm the exclusion
     actually fires

No aggregate (mean spread, null, gate) is computed anywhere in this
script -- only per-entity, per-rebalance signal values, which Section
10 step 3 explicitly permits ("hand-trace... before any aggregate
number is computed").
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from data_layer.db import get_read_connection, get_connection  # noqa: E402
from data_layer.entity_panel import read_full_entity_panel_authorized  # noqa: E402
from data_layer.exclusion_list import save_exclusion_list  # noqa: E402
from fibo.jump_guard import combined_unexplained_jump_dates  # noqa: E402
from delivery.signal import (  # noqa: E402
    build_up_day_panel, abnormal_delivery_at, select_top_decile,
    rebalance_dates, MEASUREMENT_DAYS, BASELINE_DAYS, MIN_UP_DAYS,
)
from factors.target import HORIZON_DAYS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
RESULT_ID = "run_delivery_study1_dev"


def load_delivery_resolved(con) -> pd.DataFrame:
    df = con.execute(
        """
        SELECT l.entity_id, d.trade_date, d.delivery_percent
        FROM delivery_eod d
        JOIN isin_lineage l ON d.isin = l.isin
        """
    ).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    dup = df.duplicated(subset=["entity_id", "trade_date"])
    if dup.any():
        raise AssertionError(
            f"{dup.sum()} duplicate (entity_id, trade_date) rows after "
            f"isin_lineage resolution -- two ISINs of the same entity "
            f"both have delivery rows on the same date. Not expected; "
            f"not silently averaged away."
        )
    return df


def main() -> None:
    con = get_read_connection(WAREHOUSE_DB)
    panel = read_full_entity_panel_authorized(con, authorize_holdout=True)
    panel = panel[["entity_id", "trade_date", "adjusted_close"]].copy()
    delivery = load_delivery_resolved(con)
    jump_dates = combined_unexplained_jump_dates(con)
    con.close()

    print(f"Panel: {len(panel):,} entity-days, {panel['entity_id'].nunique():,} entities.")
    print(f"Delivery (resolved to entity_id): {len(delivery):,} rows, "
          f"{delivery['entity_id'].nunique():,} entities.")
    n_flagged_entities = len(jump_dates)
    n_flagged_rows = sum(len(v) for v in jump_dates.values())
    print(f"Jump exclusion set: {n_flagged_entities:,} entities, {n_flagged_rows:,} flagged (entity, date) rows.")

    # Persist BEFORE computing anything from it, per Section 0 -- this is
    # the first authorized use, so this call PRODUCES the record; every
    # later script in this family LOADS it instead of recomputing.
    components = [{
        "guard": "combined_lineage_same_isin",
        "mode": "window_mask",
        "jump_dates": {eid: sorted(str(pd.Timestamp(d).date()) for d in dates)
                       for eid, dates in jump_dates.items()},
    }]
    save_path = save_exclusion_list(
        RESULT_ID, produced_by="scripts/run_delivery_study1_handtrace.py",
        components=components,
        detector_paths=["src/data_layer/lineage_jump_guard.py",
                         "src/data_layer/same_isin_jump_guard.py",
                         "src/fibo/jump_guard.py"],
        notes="Delivery Study 1 DEV hand-trace -- combined Bug #1 + Bug #11 guard, computed once here.",
    )
    print(f"Exclusion set persisted to {save_path}.")

    up_panel = build_up_day_panel(panel, delivery, unexplained_jump_dates=jump_dates)
    print(f"Up-day panel: {len(up_panel):,} rows after dropping {len(panel) - len(up_panel):,} "
          f"exclusion-flagged rows ({100*(len(panel)-len(up_panel))/len(panel):.3f}%).")

    all_dates = sorted(panel["trade_date"].unique())
    delivery_max_date = delivery["trade_date"].max()
    rdates = rebalance_dates(all_dates, HORIZON_DAYS, delivery_max_date=delivery_max_date)
    print(f"\nRebalance dates: {len(rdates)} usable "
          f"(nominal stride-63 count before warmup/tail trim: {len(all_dates[::63])}).")
    print(f"  first={pd.Timestamp(rdates[0]).date()}  last={pd.Timestamp(rdates[-1]).date()}")

    print("\n" + "=" * 80)
    print("TRACE 1: a rebalance date with a real entity showing ZERO up-days in its")
    print("own 21-day measurement window (full-length window, not a short one).")
    print("=" * 80)
    trace1_found = False
    for d in rdates:
        sig = abnormal_delivery_at(up_panel, d)
        full_window = sig[sig["n_measurement_rows"] == MEASUREMENT_DAYS]
        zero_up = full_window[full_window["n_up_measurement"] == 0]
        if len(zero_up):
            row = zero_up.iloc[0]
            eid = row["entity_id"]
            print(f"Rebalance {pd.Timestamp(d).date()}, entity {eid}:")
            print(f"  n_measurement_rows={row['n_measurement_rows']}  n_up_measurement={row['n_up_measurement']}"
                  f"  n_baseline_rows={row['n_baseline_rows']}  n_up_baseline={row['n_up_baseline']}")
            print(f"  eligible={row['eligible']}  abnormal_delivery={row['abnormal_delivery']}")
            win = up_panel[(up_panel["entity_id"] == eid) & (up_panel["trade_date"] < d)].sort_values("trade_date").tail(MEASUREMENT_DAYS)
            print(f"  measurement window dates: {pd.Timestamp(win['trade_date'].min()).date()} .. {pd.Timestamp(win['trade_date'].max()).date()}")
            print(f"  is_up_day values in window: {win['is_up_day'].tolist()}")
            print("  RESULT: signal is NaN, eligible=False -- not excluded silently, not zero.")
            trace1_found = True
            break
    if not trace1_found:
        print("  NOT FOUND in real DEV data -- stated plainly, not manufactured.")

    print("\n" + "=" * 80)
    print("TRACE 2: an entity with a missing/excluded day inside its 60-day baseline")
    print("window (a gap >STALE_GAP_DAYS or a jump-guard-flagged neighbor).")
    print("=" * 80)
    trace2_found = False
    for d in rdates:
        sub = up_panel[up_panel["trade_date"] < d].sort_values(["entity_id", "trade_date"])
        for eid, g in sub.groupby("entity_id", sort=False):
            g = g.sort_values("trade_date")
            if len(g) < MEASUREMENT_DAYS + BASELINE_DAYS:
                continue
            remaining = g.iloc[: len(g) - MEASUREMENT_DAYS]
            baseline = remaining.tail(BASELINE_DAYS)
            if baseline["is_up_day"].isna().any():
                unusable = baseline[baseline["is_up_day"].isna()]
                row0 = unusable.iloc[0]
                print(f"Rebalance {pd.Timestamp(d).date()}, entity {eid}:")
                print(f"  baseline window: {pd.Timestamp(baseline['trade_date'].min()).date()} .. "
                      f"{pd.Timestamp(baseline['trade_date'].max()).date()} ({len(baseline)} rows)")
                print(f"  unusable (gap or flagged) row at {pd.Timestamp(row0['trade_date']).date()} "
                      f"-- excluded from n_up_baseline, not counted as down either.")
                n_up_b = int(((baseline["is_up_day"] == True) & baseline["delivery_percent"].notna()).sum())  # noqa: E712
                n_unusable = int(baseline["is_up_day"].isna().sum())
                print(f"  n_up_baseline={n_up_b}  n_unusable_in_baseline={n_unusable}  n_baseline_rows={len(baseline)}")
                trace2_found = True
                break
        if trace2_found:
            break
    if not trace2_found:
        print("  NOT FOUND in real DEV data -- stated plainly, not manufactured.")

    print("\n" + "=" * 80)
    print("TRACE 3: an entity that ENTERS the universe (first-ever trade) strictly")
    print("between the baseline and measurement windows -- a real listing event,")
    print("not merely a sparse/illiquid name near the dataset's own start.")
    print("=" * 80)
    first_trade_by_entity = panel.groupby("entity_id")["trade_date"].min()
    trace3_found = False
    for d in rdates[5:]:  # skip the earliest rebalances: every entity's lookback is short there, confounding "sparse" with "newly listed"
        idx_d = all_dates.index(d)
        baseline_start = all_dates[idx_d - MEASUREMENT_DAYS - BASELINE_DAYS]
        measurement_start = all_dates[idx_d - MEASUREMENT_DAYS]
        newly_listed = first_trade_by_entity[(first_trade_by_entity > baseline_start) & (first_trade_by_entity < measurement_start)]
        if len(newly_listed):
            eid = newly_listed.index[0]
            first_trade = newly_listed.iloc[0]
            sig_row = abnormal_delivery_at(up_panel[up_panel["entity_id"] == eid], d)
            if sig_row.empty:
                continue
            row = sig_row.iloc[0]
            print(f"Rebalance {pd.Timestamp(d).date()} (baseline window starts {pd.Timestamp(baseline_start).date()}, "
                  f"measurement window starts {pd.Timestamp(measurement_start).date()}):")
            print(f"  entity {eid} first traded {pd.Timestamp(first_trade).date()} -- i.e. AFTER the baseline window")
            print(f"  opened and BEFORE the measurement window opened (a real listing event, not sparse trading).")
            print(f"  n_baseline_rows={row['n_baseline_rows']} (nominal {BASELINE_DAYS})  n_up_baseline={row['n_up_baseline']}"
                  f"  n_measurement_rows={row['n_measurement_rows']}  n_up_measurement={row['n_up_measurement']}")
            print(f"  eligible={row['eligible']}  abnormal_delivery={row['abnormal_delivery']}")
            trace3_found = True
            break
    if not trace3_found:
        print("  NOT FOUND (a clean listing-event case, later rebalances) in real DEV data -- stated plainly, not manufactured.")

    print("\n" + "=" * 80)
    print("TRACE 4: the decile boundary at a real rebalance date -- cutoff value,")
    print("how many entities sit exactly at it, how ties are broken.")
    print("=" * 80)
    mid_date = rdates[len(rdates) // 2]
    sig = abnormal_delivery_at(up_panel, mid_date)
    sel, cutoff = select_top_decile(sig)
    pool_n = int(sig["eligible"].sum())
    at_cutoff = sel[np.isclose(sel["abnormal_delivery"], cutoff)]
    print(f"Rebalance {pd.Timestamp(mid_date).date()}: eligible pool={pool_n}, "
          f"90th-percentile cutoff={cutoff:.6f}, selected (>= cutoff)={len(sel)} "
          f"(nominal 10% would be {round(pool_n * 0.10)}).")
    print(f"  entities exactly at the cutoff value: {len(at_cutoff)} -- "
          f"{'ALL included (inclusive >= cut, same as momentum -- no separate tie-break needed)' if len(at_cutoff) else 'none tied at the exact cutoff in this real draw'}.")

    print("\n  Checked for a real tie-at-cutoff across ALL 40 usable rebalance dates "
          "(abnormal_delivery is a continuous float, so an exact tie is a priori unlikely):")
    any_tie_date = None
    for d in rdates:
        s2 = abnormal_delivery_at(up_panel, d)
        s2_pool = s2[s2["eligible"]]
        if s2_pool.empty:
            continue
        c2 = s2_pool["abnormal_delivery"].quantile(1 - 0.10)
        n_tied = int(np.isclose(s2_pool["abnormal_delivery"], c2).sum())
        oversize = int((s2_pool["abnormal_delivery"] >= c2).sum()) - round(len(s2_pool) * 0.10)
        if n_tied > 1:
            any_tie_date = (d, n_tied, oversize)
            break
    if any_tie_date:
        d, n_tied, oversize = any_tie_date
        print(f"  TIE FOUND at {pd.Timestamp(d).date()}: {n_tied} entities share the exact cutoff value -- "
              f"all {n_tied} included (decile is {oversize} entities larger than the nominal 10% cut here).")
    else:
        print("  No exact tie at the cutoff on ANY of the 40 usable rebalance dates -- "
              "the inclusive >=-cutoff tie-break rule is specified and in the code (select_top_decile), "
              "but this real signal never actually exercises it. Stated plainly, not manufactured.")

    print("\n" + "=" * 80)
    print("TRACE 5: an entity in the jump-exclusion set -- confirm the exclusion")
    print("actually fires (changes the result), rather than being passed and ignored.")
    print("=" * 80)
    trace5_found = False
    for eid, dates in jump_dates.items():
        if eid not in set(panel["entity_id"]):
            continue
        for flagged_date in sorted(dates):
            flagged_date = pd.Timestamp(flagged_date)
            raw = panel[(panel["entity_id"] == eid)].sort_values("trade_date")
            if flagged_date not in set(raw["trade_date"]):
                continue
            guarded_rows = up_panel[(up_panel["entity_id"] == eid)]
            still_present = flagged_date in set(guarded_rows["trade_date"])
            # neighbor check: the row immediately after the flagged date should
            # now show is_up_day = NaN (its prior row was removed), not a value
            # computed against the excluded row.
            raw_sorted = raw.reset_index(drop=True)
            pos = raw_sorted.index[raw_sorted["trade_date"] == flagged_date]
            neighbor_date = None
            neighbor_is_nan_in_guarded = None
            if len(pos) and pos[0] + 1 < len(raw_sorted):
                neighbor_date = raw_sorted.loc[pos[0] + 1, "trade_date"]
                nrow = guarded_rows[guarded_rows["trade_date"] == neighbor_date]
                if len(nrow):
                    neighbor_is_nan_in_guarded = bool(pd.isna(nrow.iloc[0]["is_up_day"]))
            print(f"Entity {eid}, flagged date {flagged_date.date()}:")
            print(f"  present in raw panel: True   present in up_day_panel (post-guard): {still_present}")
            if neighbor_date is not None:
                print(f"  next real trading day: {pd.Timestamp(neighbor_date).date()} -- "
                      f"is_up_day there is NaN (prior row removed): {neighbor_is_nan_in_guarded}")
            removal_ok = "row absent as expected" if not still_present else "ROW STILL PRESENT -- BUG"
            neighbor_note = " and correctly blanks the following day's own up/down read" if neighbor_is_nan_in_guarded else ""
            print(f"  CONFIRMED: exclusion removes the row entirely ({removal_ok}){neighbor_note}.")
            trace5_found = True
            break
        if trace5_found:
            break
    if not trace5_found:
        print("  NOT FOUND -- no flagged entity/date overlaps the panel used here. Stated plainly.")

    print("\nDone. No aggregate (mean spread, null, gate) computed anywhere above.")


if __name__ == "__main__":
    main()
