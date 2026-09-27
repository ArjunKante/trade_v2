"""BUG #11 MATERIALITY CHECK on Study 1's holdout evaluation -- identical
to scripts/run_holdout_study1.py in every respect EXCEPT the 78
same-ISIN-jump entities (BUGS.md Bug #11) are excluded from the panel
before anything else runs. `run_holdout_study1.py` itself is NOT modified
-- this is a separate script, per instruction ("no rewriting of
published results").

The holdout is RETIRED (`FINDINGS.md` Section 7, 2026-09-27) -- rereading
it is permitted, and this run is logged to `data/holdout_access_log.txt`
as exactly that: a materiality check on an already-retired window, not a
new spend against a resource that no longer has slots to spend.

WHY THIS CHECK: see scripts/run_momentum_backtest_bug11_check.py's
docstring for the full mechanism (plausible missed splits among the 78
inflating a trailing-12-month return on artifact alone). This script is
the holdout-side half of the same check.

Usage:
    python scripts/run_holdout_study1_bug11_check.py
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
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return, HORIZON_DAYS
from monitor.persistence import same_isin_jump_excluded_entities

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10
COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5
MARGIN_REQUIRED_PP = 3.0
MAXDD_SLACK_PP = 10.0

# --- published (original, unexcluded) figures, FINDINGS.md Section 2 ---
ORIGINAL = {
    "mom_cagr": 0.1472, "bench_cagr": 0.1085, "margin_pp": 3.87,
    "mom_mdd": -0.0648, "bench_mdd": -0.1045,
    "cond_a": True, "cond_b": True, "cond_c": True,
}

LOG_PATH = ROOT / "data" / "holdout_access_log.txt"
with open(LOG_PATH, "a") as f:
    f.write(f"{dt.datetime.now().isoformat()} | scripts/run_holdout_study1_bug11_check.py | "
            f"authorize_holdout=True | MATERIALITY CHECK on the ALREADY-RETIRED historical "
            f"holdout (FINDINGS.md Section 7) -- reruns Study 1 with the 78 Bug #11 entities "
            f"excluded to check whether the momentum holdout pass (the only positive result "
            f"across all three projects) rests on same-ISIN-jump contamination. Rereading a "
            f"retired window, not a new spend.\n")
print(f"Holdout access logged (materiality check on a retired window) to {LOG_PATH}", file=sys.stderr, flush=True)

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
excluded = same_isin_jump_excluded_entities(con)  # BUGS.md Bug #11
panel_all = read_full_entity_panel_authorized(con, authorize_holdout=True)
panel = panel_all[~panel_all["entity_id"].isin(excluded)].reset_index(drop=True)
con.close()
print(f"Excluded {len(excluded)} same-ISIN-jump entities. Full panel: {len(panel)} rows, "
      f"{panel['entity_id'].nunique()} entities, {panel['trade_date'].min().date()} to "
      f"{panel['trade_date'].max().date()}")

mom = compute_momentum_12_1(panel)
fwd_clean = compute_forward_return(panel)

p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop") if s.notna().sum() >= 3 else pd.Series([np.nan]*len(s), index=s.index)
)

full = mom.merge(p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]).dropna(subset=["value", "_tercile"])
clean = mom.merge(fwd_clean, on=["entity_id", "trade_date"]).merge(
    p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]
).dropna(subset=["value", "fwd_return", "_tercile"])

all_dates = sorted(full["trade_date"].unique())
rebalance_dates_all = all_dates[::REBALANCE_DAYS]
rebalance_dates_all = [d for d in rebalance_dates_all if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]
print(f"{len(rebalance_dates_all)} total rebalances, 2016 through end of available data")

holdout_start_ts = pd.Timestamp(SEALED_HOLDOUT_START)
holdout_rebalance_dates = [d for d in rebalance_dates_all if d >= holdout_start_ts]
print(f"{len(holdout_rebalance_dates)} rebalances fall inside the (retired) sealed holdout "
      f"({holdout_rebalance_dates[0].date()} to {holdout_rebalance_dates[-1].date()})")

momentum_nav = [1.0]
benchmark_nav = [1.0]
nav_dates = [rebalance_dates_all[0]]
prev_mom_set = None
prev_bench_set = None
records = []

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

    records.append({
        "date": d, "in_holdout": d >= holdout_start_ts,
        "mom_n": len(mom_set), "mom_gross": gross_ret, "mom_net": net_ret,
        "bench_n": len(bench_set), "bench_gross": bgross, "bench_net": bnet,
    })
    nav_dates.append(d)

rec_df = pd.DataFrame(records)
holdout_rec = rec_df[rec_df["in_holdout"]].reset_index(drop=True)

holdout_mom_nav = [1.0]
holdout_bench_nav = [1.0]
for _, row in holdout_rec.iterrows():
    holdout_mom_nav.append(holdout_mom_nav[-1] * (1 + row["mom_net"]))
    holdout_bench_nav.append(holdout_bench_nav[-1] * (1 + row["bench_net"]))

n_years_holdout = (holdout_rec["date"].iloc[-1] - holdout_rec["date"].iloc[0]).days / 365.25
mom_cagr = holdout_mom_nav[-1] ** (1 / n_years_holdout) - 1
bench_cagr = holdout_bench_nav[-1] ** (1 / n_years_holdout) - 1


def max_dd(nav):
    nav = np.array(nav)
    peak = np.maximum.accumulate(nav)
    return ((nav - peak) / peak).min()


mom_mdd = max_dd(holdout_mom_nav)
bench_mdd = max_dd(holdout_bench_nav)
margin_pp = (mom_cagr - bench_cagr) * 100
mdd_diff_pp = (abs(mom_mdd) - abs(bench_mdd)) * 100

cond_a = mom_cagr > bench_cagr
cond_b = margin_pp >= MARGIN_REQUIRED_PP
cond_c = mdd_diff_pp <= MAXDD_SLACK_PP
overall = cond_a and cond_b and cond_c

print("\n" + "=" * 90)
print("BUG #11 MATERIALITY CHECK -- STUDY 1 HOLDOUT, 78 SAME-ISIN-JUMP ENTITIES EXCLUDED")
print("=" * 90)
print(f"Holdout window: {holdout_rec['date'].iloc[0].date()} to {holdout_rec['date'].iloc[-1].date()}, "
      f"{len(holdout_rec)} rebalances")

print(f"\n{'':22s}{'ORIGINAL':>12s}{'EXCLUDED-78':>14s}{'DIFF':>10s}")
print(f"{'Momentum CAGR':22s}{ORIGINAL['mom_cagr']*100:>11.2f}%{mom_cagr*100:>13.2f}%{(mom_cagr-ORIGINAL['mom_cagr'])*100:>+9.2f}pp")
print(f"{'Benchmark CAGR':22s}{ORIGINAL['bench_cagr']*100:>11.2f}%{bench_cagr*100:>13.2f}%{(bench_cagr-ORIGINAL['bench_cagr'])*100:>+9.2f}pp")
print(f"{'Margin (pts)':22s}{ORIGINAL['margin_pp']:>11.2f} {margin_pp:>13.2f} {margin_pp-ORIGINAL['margin_pp']:>+9.2f}")
print(f"{'Momentum MaxDD':22s}{ORIGINAL['mom_mdd']*100:>11.2f}%{mom_mdd*100:>13.2f}%{(mom_mdd-ORIGINAL['mom_mdd'])*100:>+9.2f}pp")
print(f"{'Benchmark MaxDD':22s}{ORIGINAL['bench_mdd']*100:>11.2f}%{bench_mdd*100:>13.2f}%{(bench_mdd-ORIGINAL['bench_mdd'])*100:>+9.2f}pp")

print("\n--- DECISION RULE, old vs new ---")
print(f"(a) momentum CAGR > benchmark CAGR: ORIGINAL={'PASS' if ORIGINAL['cond_a'] else 'FAIL'}  "
      f"NEW={'PASS' if cond_a else 'FAIL'} ({mom_cagr*100:.2f}% vs {bench_cagr*100:.2f}%)")
print(f"(b) margin >= {MARGIN_REQUIRED_PP:.1f}pts: ORIGINAL={'PASS' if ORIGINAL['cond_b'] else 'FAIL'}  "
      f"NEW={'PASS' if cond_b else 'FAIL'} (margin={margin_pp:.2f}pts)")
print(f"(c) MaxDD not >{MAXDD_SLACK_PP:.1f}pts worse: ORIGINAL={'PASS' if ORIGINAL['cond_c'] else 'FAIL'}  "
      f"NEW={'PASS' if cond_c else 'FAIL'} (diff={mdd_diff_pp:+.2f}pts)")
print(f"\nOVERALL: {'PASS (replicates)' if overall else 'FAIL'}")
any_flip = (cond_a != ORIGINAL["cond_a"]) or (cond_b != ORIGINAL["cond_b"]) or (cond_c != ORIGINAL["cond_c"])
print(f"ANY CONDITION FLIPPED vs original: {'YES -- STOP, per instruction' if any_flip else 'NO'}")

# --- how many of the 78 ever entered the top decile within the HOLDOUT window, and clustering ---
mom_full_raw = compute_momentum_12_1(panel_all)
holdout_hits = []
for d in holdout_rebalance_dates:
    day = mom_full_raw[mom_full_raw["trade_date"] == d].dropna(subset=["value"])
    if len(day) < 20:
        continue
    cutoff = day["value"].quantile(1 - DECILE_FRAC)
    in_decile = day[(day["value"] >= cutoff) & (day["entity_id"].isin(excluded))]
    for _, row in in_decile.iterrows():
        holdout_hits.append({"date": d, "entity_id": row["entity_id"], "momentum_value": row["value"]})
holdout_hits_df = pd.DataFrame(holdout_hits)

print(f"\n--- Of the 78 excluded entities: how many entered momentum's top decile at any HOLDOUT-window rebalance ---")
if len(holdout_hits_df):
    print(f"{holdout_hits_df['entity_id'].nunique()} of 78 entities entered the top decile at "
          f">=1 holdout rebalance ({len(holdout_hits_df)} entity-rebalance hits).")
    print(holdout_hits_df.to_string(index=False))
else:
    print("0 of 78 entities entered the top decile at any holdout-window rebalance.")

holdout_rec.to_csv(ROOT / "data" / "holdout_study1_bug11_check_records.csv", index=False)
print(f"\nSaved to data/holdout_study1_bug11_check_records.csv")
