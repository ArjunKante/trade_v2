"""EXTENSION of run_holdout_study1_bug11_check.py, same methodology,
same holdout window, same cost model, same decision rule -- the ONLY
thing varied here is WHICH same-ISIN-jump exclusion set is applied,
across the versions that have existed since the original 2026-09-27
check (78 entities) through today's (82). Written 2026-11-16 because
the unmodified script's own `read_full_entity_panel_authorized` has no
upper date bound, so a plain re-run also pulls in whatever NEW
rebalance dates have accumulated since 2026-09-27 (2026-07-23, a 6th
rebalance that did not exist in the original 5-rebalance evaluation) --
that is a SEPARATE variable (the window's own forward extension, not
the exclusion set) and conflates with the question actually being
asked here. This script holds the window FIXED to the original 5
rebalances (2025-04-11 through 2026-04-22, data/holdout_study1_records.csv)
and varies ONLY the excluded-entity set, to isolate exclusion-set
sensitivity cleanly.

Same holdout-access discipline as the script this extends: this is a
reread of an already-retired window (FINDINGS.md Section 7), logged as
a materiality check, not a new spend. No new hypothesis is tested
against the holdout; nothing about the strategy (universe, decile cut,
cost model, rebalance schedule) is varied -- only the exclusion-set
input.

Usage:
    python scripts/run_holdout_study1_bug11_check_versioned.py
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
from data_layer.same_isin_jump_guard import unexplained_same_isin_jump_entities
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return, HORIZON_DAYS
from monitor.persistence import JUMP_GAP_DAYS_CUTOFF

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10
COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5
MARGIN_REQUIRED_PP = 3.0
MAXDD_SLACK_PP = 10.0

# Original 5-rebalance holdout window, FIXED -- matches
# data/holdout_study1_records.csv exactly (last date 2026-04-22). Any
# later rebalance (2026-07-23 onward) is new forward data that did not
# exist in the original evaluation and is deliberately excluded here so
# only the exclusion-set input differs.
ORIGINAL_HOLDOUT_LAST_DATE = pd.Timestamp("2026-04-22")

ORIGINAL = {"mom_cagr": 0.1472, "bench_cagr": 0.1085, "margin_pp": 3.87,
            "mom_mdd": -0.0648, "bench_mdd": -0.1045}
PUBLISHED_78_EXCLUDED = {"mom_cagr": 0.1476, "bench_cagr": 0.1112, "margin_pp": 3.64,
                         "mom_mdd": -0.0785, "bench_mdd": -0.1045}

LOG_PATH = ROOT / "data" / "holdout_access_log.txt"
with open(LOG_PATH, "a") as f:
    f.write(f"{dt.datetime.now().isoformat()} | scripts/run_holdout_study1_bug11_check_versioned.py | "
            f"authorize_holdout=True | MATERIALITY CHECK (same as run_holdout_study1_bug11_check.py) "
            f"on the ALREADY-RETIRED historical holdout (FINDINGS.md Section 7), window held fixed to "
            f"the original 5 rebalances (through 2026-04-22) -- reruns Study 1 at each same-ISIN-jump "
            f"exclusion-set version that has existed since 2026-09-27, to check sensitivity of the "
            f"holdout margin to the exclusion set alone. Rereading a retired window, not a new spend.\n")
print(f"Holdout access logged to {LOG_PATH}", file=sys.stderr, flush=True)

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
flagged = unexplained_same_isin_jump_entities(con)
tight = flagged[flagged["gap_days"] <= JUMP_GAP_DAYS_CUTOFF]
panel_all = read_full_entity_panel_authorized(con, authorize_holdout=True)
con.close()

CHECKPOINTS = [
    ("2026-09-27 (build, ~78)", dt.date(2026, 9, 27)),
    ("2026-09-28 (~80)", dt.date(2026, 9, 28)),
    ("2026-10-10 (~81)", dt.date(2026, 10, 10)),
    ("2026-11-16 (today, 82)", dt.date(2026, 11, 16)),
]


def run_one(excluded_entities: set) -> dict:
    panel = panel_all[~panel_all["entity_id"].isin(excluded_entities)].reset_index(drop=True)
    # unexplained_jump_dates={}: this diagnostic isolates the same-ISIN
    # exclusion-set's own instability (entity-level, varied by snapshot
    # date); the lineage guard is a separate, orthogonal correction,
    # measured in run_holdout_study1_lineage_check.py instead.
    mom = compute_momentum_12_1(panel, unexplained_jump_dates={})
    fwd_clean = compute_forward_return(panel, unexplained_jump_dates={})

    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
    p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
        lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
        if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index)
    )

    full = mom.merge(p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]).dropna(subset=["value", "_tercile"])
    clean = mom.merge(fwd_clean, on=["entity_id", "trade_date"]).merge(
        p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]
    ).dropna(subset=["value", "fwd_return", "_tercile"])

    all_dates = sorted(full["trade_date"].unique())
    rebalance_dates_all = all_dates[::REBALANCE_DAYS]
    rebalance_dates_all = [d for d in rebalance_dates_all if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]

    holdout_start_ts = pd.Timestamp(SEALED_HOLDOUT_START)
    # FIXED window: only the original 5 rebalances, never the later ones
    holdout_rebalance_dates = [d for d in rebalance_dates_all
                                if holdout_start_ts <= d <= ORIGINAL_HOLDOUT_LAST_DATE]

    momentum_nav, benchmark_nav = [1.0], [1.0]
    prev_mom_set, prev_bench_set = None, None
    records = []

    for d in rebalance_dates_all:
        if d > ORIGINAL_HOLDOUT_LAST_DATE:
            break
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

        records.append({"date": d, "in_holdout": d >= holdout_start_ts, "mom_net": net_ret, "bench_net": bnet})

    rec_df = pd.DataFrame(records)
    holdout_rec = rec_df[rec_df["in_holdout"]].reset_index(drop=True)

    holdout_mom_nav, holdout_bench_nav = [1.0], [1.0]
    for _, row in holdout_rec.iterrows():
        holdout_mom_nav.append(holdout_mom_nav[-1] * (1 + row["mom_net"]))
        holdout_bench_nav.append(holdout_bench_nav[-1] * (1 + row["bench_net"]))

    n_years = (holdout_rec["date"].iloc[-1] - holdout_rec["date"].iloc[0]).days / 365.25
    mom_cagr = holdout_mom_nav[-1] ** (1 / n_years) - 1
    bench_cagr = holdout_bench_nav[-1] ** (1 / n_years) - 1

    def max_dd(nav):
        nav = np.array(nav)
        peak = np.maximum.accumulate(nav)
        return ((nav - peak) / peak).min()

    mom_mdd = max_dd(holdout_mom_nav)
    bench_mdd = max_dd(holdout_bench_nav)
    margin_pp = (mom_cagr - bench_cagr) * 100
    mdd_diff_pp = (abs(mom_mdd) - abs(bench_mdd)) * 100

    return {
        "n_rebalances": len(holdout_rec), "last_date": holdout_rec["date"].iloc[-1].date(),
        "mom_cagr": mom_cagr, "bench_cagr": bench_cagr, "margin_pp": margin_pp,
        "mom_mdd": mom_mdd, "bench_mdd": bench_mdd, "mdd_diff_pp": mdd_diff_pp,
        "cond_b_pass": margin_pp >= MARGIN_REQUIRED_PP,
    }


print("\n" + "=" * 100)
print("STUDY 1 HOLDOUT MARGIN, WINDOW HELD FIXED (5 rebalances through 2026-04-22), "
      "VARYING ONLY THE EXCLUSION-SET VERSION")
print("=" * 100)
print(f"{'version':30s}{'n_excl':>8s}{'n_reb':>7s}{'mom_cagr':>10s}{'bench_cagr':>12s}{'margin':>9s}{'cond_b':>8s}")

print(f"{'ORIGINAL (0 excluded)':30s}{0:>8d}{5:>7d}{ORIGINAL['mom_cagr']*100:>9.2f}%{ORIGINAL['bench_cagr']*100:>11.2f}%{ORIGINAL['margin_pp']:>9.2f}{'--':>8s}")
print(f"{'PUBLISHED 78-excluded (2026-09-27)':30s}{78:>8d}{5:>7d}{PUBLISHED_78_EXCLUDED['mom_cagr']*100:>9.2f}%{PUBLISHED_78_EXCLUDED['bench_cagr']*100:>11.2f}%{PUBLISHED_78_EXCLUDED['margin_pp']:>9.2f}{'PASS':>8s}")

results = {}
for label, cp in CHECKPOINTS:
    excl = set(tight[tight["jump_date"].dt.date <= cp]["entity_id"].unique())
    r = run_one(excl)
    results[label] = r
    print(f"{label:30s}{len(excl):>8d}{r['n_rebalances']:>7d}{r['mom_cagr']*100:>9.2f}%{r['bench_cagr']*100:>11.2f}%{r['margin_pp']:>9.2f}{'PASS' if r['cond_b_pass'] else 'FAIL':>8s}")

print("\nFull detail per checkpoint:")
for label, r in results.items():
    print(f"  {label}: mom_mdd={r['mom_mdd']*100:.2f}% bench_mdd={r['bench_mdd']*100:.2f}% "
          f"mdd_diff={r['mdd_diff_pp']:+.2f}pp last_date={r['last_date']}")
