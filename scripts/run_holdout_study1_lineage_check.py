"""BUG #26 FOLLOW-UP 3 MATERIALITY CHECK on Study 1's holdout evaluation.

Identical to scripts/run_holdout_study1_bug11_check.py in every respect
EXCEPT it additionally corrects for the 40 entities with an unexplained,
zero-gap lineage-transition jump (BUGS.md Bug #26 follow-up 3), on top
of the already-applied 78 same-ISIN-jump exclusion. Two corrections,
both reported (FINDINGS.md's pre-commitment, 2026-11-16):

  (a) WINDOW-LEVEL: pass unexplained_jump_dates (the 40 entities' own
      transition dates) into compute_momentum_12_1/compute_forward_return
      -- NaNs only the specific momentum/forward-return observations
      whose lookback/lookahead window spans the transition, keeping the
      entity's other, clean windows.
  (b) ENTITY-LEVEL: drop all 40 entities from the panel outright, same
      mechanism as the existing 78-entity same-ISIN pin.

Nothing about the strategy varies -- same rules, same windows, same
universe construction as run_holdout_study1.py. Only the data excluded
changes. The holdout is RETIRED (FINDINGS.md Section 7) -- rereading it
is a materiality check, not a new spend, logged to
data/holdout_access_log.txt accordingly.
"""
import datetime as dt
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.holdout import SEALED_HOLDOUT_START
from data_layer.entity_panel import read_full_entity_panel_authorized
from data_layer.lineage_jump_guard import find_unexplained_jumps
from data_layer.same_isin_jump_guard import find_unexplained_same_isin_jumps
from data_layer.exclusion_list import save_exclusion_list
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return, HORIZON_DAYS

DETECTOR_PATHS = [
    Path(__file__).resolve().parents[1] / "src" / "data_layer" / "same_isin_jump_guard.py",
    Path(__file__).resolve().parents[1] / "src" / "data_layer" / "lineage_jump_guard.py",
]

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10
COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5
MARGIN_REQUIRED_PP = 3.0
MAXDD_SLACK_PP = 10.0

# Original 5-rebalance holdout window, FIXED -- matches
# data/holdout_study1_records.csv exactly (last date 2026-04-22), same
# convention as run_holdout_study1_bug11_check_versioned.py. Without this,
# "today's" live panel has grown a 6th rebalance (2026-07-23) that did not
# exist when 3.87/3.64 were recorded -- comparing against that would not
# be the same window.
ORIGINAL_HOLDOUT_LAST_DATE = pd.Timestamp("2026-04-22")

RECORDED = {"margin_78_excluded": 3.64, "margin_original": 3.87}

LOG_PATH = ROOT / "data" / "holdout_access_log.txt"
with open(LOG_PATH, "a") as f:
    f.write(f"{dt.datetime.now().isoformat()} | scripts/run_holdout_study1_lineage_check.py | "
            f"authorize_holdout=True | MATERIALITY CHECK on the ALREADY-RETIRED historical "
            f"holdout (FINDINGS.md Section 7) -- reruns Study 1 (78 same-ISIN entities already "
            f"excluded) with the 40 Bug #26-follow-up-3 lineage-jump entities ALSO corrected, "
            f"window-level and entity-level, to check whether the recorded pass rests on this "
            f"second contamination. Rereading a retired window, not a new spend.\n")
print(f"Holdout access logged to {LOG_PATH}", file=sys.stderr, flush=True)

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
# Pinned to the 2026-09-27 read date, same reconstruction convention as
# run_holdout_study1_bug11_check_versioned.py -- NOT the live set, which
# has grown to 82 entities by ordinary backfill since then and would not
# reproduce the recorded 3.64 margin.
same_isin_tight = find_unexplained_same_isin_jumps(con, before=dt.date(2026, 9, 28))
same_isin_tight = same_isin_tight[(~same_isin_tight["has_nearby_ca_record"]) & (same_isin_tight["gap_days"] <= 5)]
lineage_for_pin = con.execute("SELECT DISTINCT isin, entity_id FROM isin_lineage").fetchdf()
iso_to_entity_pin = lineage_for_pin.set_index("isin")["entity_id"].to_dict()
same_isin_excluded = set(same_isin_tight["isin"].map(iso_to_entity_pin).dropna().unique())

lineage_jumps = find_unexplained_jumps(con)
lineage_jumps = lineage_jumps[~lineage_jumps["has_nearby_ca_record"]].copy()
rows = []
for _, r in lineage_jumps.iterrows():
    pred_last = con.execute("select max(trade_date) from prices_eod where isin=?", [r["predecessor_isin"]]).fetchone()[0]
    succ_first = con.execute("select min(trade_date) from prices_eod where isin=?", [r["isin"]]).fetchone()[0]
    gap = (succ_first - pred_last).days if pred_last and succ_first else None
    rows.append({"entity_id": r["entity_id"], "transition_date": r["transition_date"], "gap_days": gap})
gap_df = pd.DataFrame(rows)
small_gap = gap_df[gap_df["gap_days"] <= 5]
NET_NEW_40 = small_gap[~small_gap["entity_id"].isin(same_isin_excluded)]
assert len(NET_NEW_40) == 40, f"expected 40 net-new lineage entities, got {len(NET_NEW_40)}"
jump_dates_40 = {row["entity_id"]: {row["transition_date"]} for _, row in NET_NEW_40.iterrows()}
entities_40 = set(NET_NEW_40["entity_id"])
print(f"Baseline same-ISIN exclusion: {len(same_isin_excluded)} entities. "
      f"Bug #26 follow-up 3 lineage entities to correct: {len(entities_40)}")

panel_all = read_full_entity_panel_authorized(con, authorize_holdout=True)
con.close()
panel_baseline = panel_all[~panel_all["entity_id"].isin(same_isin_excluded)].reset_index(drop=True)


def run_variant(panel, label, jump_dates):
    # jump_dates={} for BASELINE (correction is the same-ISIN entity
    # exclusion already in the panel) and ENTITY-LEVEL (correction is the
    # 40-entity exclusion already in the panel); the real 40-entity dict
    # only for WINDOW-LEVEL, the one variant this guard is meant to apply to.
    mom = compute_momentum_12_1(panel, unexplained_jump_dates=jump_dates)
    fwd_clean = compute_forward_return(panel, unexplained_jump_dates=jump_dates)

    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
    p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
        lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop") if s.notna().sum() >= 3 else pd.Series([np.nan]*len(s), index=s.index))

    full = mom.merge(p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]).dropna(subset=["value", "_tercile"])
    clean = mom.merge(fwd_clean, on=["entity_id", "trade_date"]).merge(
        p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]
    ).dropna(subset=["value", "fwd_return", "_tercile"])

    all_dates = sorted(full["trade_date"].unique())
    rebalance_dates_all = all_dates[::REBALANCE_DAYS]
    rebalance_dates_all = [d for d in rebalance_dates_all if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]

    holdout_start_ts = pd.Timestamp(SEALED_HOLDOUT_START)
    holdout_rebalance_dates = [d for d in rebalance_dates_all
                                if holdout_start_ts <= d <= ORIGINAL_HOLDOUT_LAST_DATE]

    momentum_nav = [1.0]
    prev_mom_set = None
    benchmark_nav = [1.0]
    prev_bench_set = None
    records = []
    decile_membership = {}

    for d in rebalance_dates_all:
        day_full = full[full["trade_date"] == d].copy()
        if len(day_full) < 20:
            continue
        pool = clean[clean["trade_date"] == d].rename(columns={"fwd_return": "realized_return"})
        if pool.empty:
            continue

        cutoff = pool["value"].quantile(1 - DECILE_FRAC)
        mom_sel = pool[pool["value"] >= cutoff]
        mom_set = set(mom_sel["entity_id"])
        bench_set = set(pool["entity_id"])
        if not mom_set or not bench_set:
            continue
        decile_membership[d] = mom_set

        gross_ret = mom_sel["realized_return"].mean()
        if prev_mom_set is None:
            turnover_frac = 1.0
            tercile_counts = mom_sel["_tercile"].value_counts(normalize=True)
            avg_cost = sum(tercile_counts.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE)
        else:
            entered = mom_set - prev_mom_set
            turnover_frac = len(entered) / max(len(mom_set), 1)
            entered_tercile = mom_sel[mom_sel["entity_id"].isin(entered)]["_tercile"].value_counts(normalize=True)
            avg_cost = sum(entered_tercile.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE) if len(entered) else 0.0
        period_cost = turnover_frac * (avg_cost / 10000.0)
        net_ret = gross_ret - period_cost
        momentum_nav.append(momentum_nav[-1] * (1 + net_ret))
        prev_mom_set = mom_set

        bgross = pool["realized_return"].mean()
        if prev_bench_set is None:
            bturnover = 1.0
        else:
            bentered = bench_set - prev_bench_set
            bturnover = len(bentered) / max(len(bench_set), 1)
        bcost = bturnover * (BLENDED_COST_BPS / 10000.0)
        bnet = bgross - bcost
        benchmark_nav.append(benchmark_nav[-1] * (1 + bnet))
        prev_bench_set = bench_set

        records.append({"date": d, "in_holdout": holdout_start_ts <= d <= ORIGINAL_HOLDOUT_LAST_DATE,
                         "mom_n": len(mom_set), "mom_net": net_ret, "bench_net": bnet})

    rec_df = pd.DataFrame(records)
    holdout_rec = rec_df[rec_df["in_holdout"]].reset_index(drop=True)

    hm_nav, hb_nav = [1.0], [1.0]
    for _, row in holdout_rec.iterrows():
        hm_nav.append(hm_nav[-1] * (1 + row["mom_net"]))
        hb_nav.append(hb_nav[-1] * (1 + row["bench_net"]))

    n_years = (holdout_rec["date"].iloc[-1] - holdout_rec["date"].iloc[0]).days / 365.25
    mom_cagr = hm_nav[-1] ** (1 / n_years) - 1
    bench_cagr = hb_nav[-1] ** (1 / n_years) - 1

    def max_dd(nav):
        nav = np.array(nav)
        peak = np.maximum.accumulate(nav)
        return ((nav - peak) / peak).min()

    mom_mdd, bench_mdd = max_dd(hm_nav), max_dd(hb_nav)
    margin_pp = (mom_cagr - bench_cagr) * 100
    mdd_diff_pp = (abs(mom_mdd) - abs(bench_mdd)) * 100
    cond_a, cond_b, cond_c = mom_cagr > bench_cagr, margin_pp >= MARGIN_REQUIRED_PP, mdd_diff_pp <= MAXDD_SLACK_PP

    print(f"\n--- {label} ---")
    print(f"Momentum CAGR {mom_cagr*100:.2f}%  Benchmark CAGR {bench_cagr*100:.2f}%  "
          f"Margin {margin_pp:+.2f}pts  MomMDD {mom_mdd*100:.2f}%  BenchMDD {bench_mdd*100:.2f}%")
    print(f"(a) mom>bench: {'PASS' if cond_a else 'FAIL'}  (b) margin>=3.0: {'PASS' if cond_b else 'FAIL'}  "
          f"(c) MDD slack: {'PASS' if cond_c else 'FAIL'}  OVERALL: {'PASS' if (cond_a and cond_b and cond_c) else 'FAIL'}")

    # how many of the 40 entered the top decile at a HOLDOUT rebalance, in THIS variant's own decile membership
    affected = {d: (decile_membership.get(d, set()) & entities_40) for d in holdout_rebalance_dates}
    for d, s in affected.items():
        if s:
            print(f"  {d.date()}: {len(s)} of the 40 in top decile -- {sorted(s)}")
    total_hits = sum(len(s) for s in affected.values())
    print(f"  Total entity-rebalance hits from the 40, across {len(holdout_rebalance_dates)} holdout rebalances: {total_hits}")

    return margin_pp, cond_a and cond_b and cond_c, affected


print("=" * 90)
print(f"BASELINE (78 same-ISIN excluded only, no lineage correction) -- recorded margin should reproduce {RECORDED['margin_78_excluded']}")
margin_baseline, pass_baseline, affected_baseline = run_variant(panel_baseline, "BASELINE (78 excluded)", jump_dates={})

print("\n" + "=" * 90)
print("(a) WINDOW-LEVEL correction: 40 entities' transition dates passed to compute_momentum_12_1/compute_forward_return")
margin_a, pass_a, affected_a = run_variant(panel_baseline, "WINDOW-LEVEL (78 excluded + 40 window-masked)", jump_dates=jump_dates_40)

print("\n" + "=" * 90)
print("(b) ENTITY-LEVEL correction: 40 entities dropped entirely, on top of the 78")
panel_entity = panel_baseline[~panel_baseline["entity_id"].isin(entities_40)].reset_index(drop=True)
margin_b, pass_b, affected_b = run_variant(panel_entity, "ENTITY-LEVEL (78 + 40 excluded)", jump_dates={})

print("\n" + "=" * 90)
print("SUMMARY")
print("=" * 90)
print(f"{'variant':45s}{'margin':>10s}{'pass?':>8s}")
print(f"{'ORIGINAL (no exclusion at all)':45s}{RECORDED['margin_original']:>9.2f}{'':>8s}")
print(f"{'RECORDED (78 same-ISIN excluded)':45s}{RECORDED['margin_78_excluded']:>9.2f}{'':>8s}")
print(f"{'REPRODUCED baseline (this run)':45s}{margin_baseline:>9.2f}{'PASS' if pass_baseline else 'FAIL':>8s}")
print(f"{'(a) WINDOW-LEVEL (78 + 40 window-masked)':45s}{margin_a:>9.2f}{'PASS' if pass_a else 'FAIL':>8s}")
print(f"{'(b) ENTITY-LEVEL (78 + 40 excluded)':45s}{margin_b:>9.2f}{'PASS' if pass_b else 'FAIL':>8s}")
print(f"\n(a) vs (b) disagree materially: {'YES' if abs(margin_a - margin_b) >= 0.5 else 'NO'} (diff={margin_a-margin_b:+.2f}pts)")

# This script PRODUCES these two results -- save the materialized
# exclusion lists it actually used, per OPERATIONS.md's pinning rule
# and BUGS.md's Bug #27/#28 resolution. A future REPRODUCTION of these
# numbers must load these files, never re-derive them live.
same_isin_component = {"guard": "same_isin", "mode": "entity_exclusion",
                        "entity_ids": sorted(same_isin_excluded)}
lineage_entity_component = {"guard": "lineage", "mode": "entity_exclusion",
                             "entity_ids": sorted(entities_40)}
lineage_window_component = {
    "guard": "lineage", "mode": "window_mask",
    "jump_dates": {eid: sorted(d.date().isoformat() for d in dates)
                   for eid, dates in jump_dates_40.items()},
}
save_exclusion_list(
    "run_holdout_study1_lineage_check.window_level",
    produced_by="scripts/run_holdout_study1_lineage_check.py",
    components=[same_isin_component, lineage_window_component],
    detector_paths=DETECTOR_PATHS,
    notes=f"margin={margin_a:.2f}pts, generated by this script's own run.",
)
save_exclusion_list(
    "run_holdout_study1_lineage_check.entity_level",
    produced_by="scripts/run_holdout_study1_lineage_check.py",
    components=[same_isin_component, lineage_entity_component],
    detector_paths=DETECTOR_PATHS,
    notes=f"margin={margin_b:.2f}pts, generated by this script's own run.",
)
print("\nExclusion lists saved to results/exclusions/ "
      "(run_holdout_study1_lineage_check.window_level.json, .entity_level.json)")
