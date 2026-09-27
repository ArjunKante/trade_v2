"""BUG #11 MATERIALITY CHECK on Study 2's large-cap replication -- identical
to scripts/run_study2_largecap.py in every respect EXCEPT the 78
same-ISIN-jump entities (BUGS.md Bug #11) are excluded from the panel
before anything else runs. `run_study2_largecap.py` itself is NOT
modified. CV-only, no holdout touched (same as the original -- pre-holdout
data only).

Usage:
    python scripts/run_study2_largecap_bug11_check.py
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return, HORIZON_DAYS
from monitor.persistence import same_isin_jump_excluded_entities

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10
TOP_N_LARGECAP = 200
FLAT_COST_BPS = 23.0
MARGIN_REQUIRED_PP = 2.0
MAXDD_SLACK_PP = 10.0

ORIGINAL = {
    "mom_cagr": 0.1795, "bench_cagr": 0.1139, "margin_pp": 6.56,
    "mom_mdd": -0.3652, "bench_mdd": -0.4451,
    "cond_a": True, "cond_b": True, "cond_c": True,
}

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
excluded = same_isin_jump_excluded_entities(con)  # BUGS.md Bug #11
panel_all = read_entity_panel(con)
panel = panel_all[~panel_all["entity_id"].isin(excluded)].reset_index(drop=True)
con.close()
print(f"Excluded {len(excluded)} same-ISIN-jump entities. Pre-holdout panel: {len(panel)} rows, "
      f"{panel['entity_id'].nunique()} entities, {panel['trade_date'].min().date()} to "
      f"{panel['trade_date'].max().date()}")

p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_year"] = p["trade_date"].dt.year
p["_trailing_turnover"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(252, min_periods=252).median())

year_end_snapshot = p.sort_values("trade_date").groupby(["entity_id", "_year"]).tail(1)
cohort_by_year = {}
for y in sorted(year_end_snapshot["_year"].unique()):
    snap = year_end_snapshot[year_end_snapshot["_year"] == y].dropna(subset=["_trailing_turnover"])
    top200 = snap.nlargest(TOP_N_LARGECAP, "_trailing_turnover")["entity_id"]
    cohort_by_year[y + 1] = set(top200)

mom = compute_momentum_12_1(panel)
fwd = compute_forward_return(panel)
m = mom.merge(fwd, on=["entity_id", "trade_date"]).dropna(subset=["value", "fwd_return"])
m["_year"] = m["trade_date"].dt.year
m["_in_largecap"] = m.apply(lambda r: r["entity_id"] in cohort_by_year.get(r["_year"], set()), axis=1)
lc = m[m["_in_largecap"]].copy()

all_dates = sorted(lc["trade_date"].unique())
rebalance_dates = all_dates[::REBALANCE_DAYS]
rebalance_dates = [d for d in rebalance_dates if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]
print(f"{len(rebalance_dates)} rebalance dates, {rebalance_dates[0].date()} to {rebalance_dates[-1].date()}")

momentum_nav = [1.0]
benchmark_nav = [1.0]
prev_mom_set = None
prev_bench_set = None
records = []

for d in rebalance_dates:
    pool = lc[lc["trade_date"] == d]
    if len(pool) < 20:
        continue
    cutoff = pool["value"].quantile(1 - DECILE_FRAC)
    mom_sel = pool[pool["value"] >= cutoff]
    mom_set = set(mom_sel["entity_id"])
    bench_set = set(pool["entity_id"])
    if not mom_set or not bench_set:
        continue

    gross_ret = mom_sel["fwd_return"].mean()
    if prev_mom_set is None:
        turnover_frac = 1.0
    else:
        entered = mom_set - prev_mom_set
        turnover_frac = len(entered) / max(len(mom_set), 1)
    net_ret = gross_ret - turnover_frac * (FLAT_COST_BPS / 10000.0)
    momentum_nav.append(momentum_nav[-1] * (1 + net_ret))
    prev_mom_set = mom_set

    bgross = pool["fwd_return"].mean()
    if prev_bench_set is None:
        bturnover = 1.0
    else:
        bentered = bench_set - prev_bench_set
        bturnover = len(bentered) / max(len(bench_set), 1)
    bnet = bgross - bturnover * (FLAT_COST_BPS / 10000.0)
    benchmark_nav.append(benchmark_nav[-1] * (1 + bnet))
    prev_bench_set = bench_set

    records.append({"date": d, "n_universe": len(pool), "mom_net": net_ret, "bench_net": bnet})

rec_df = pd.DataFrame(records)
n_years = (rec_df["date"].iloc[-1] - rec_df["date"].iloc[0]).days / 365.25
mom_cagr = momentum_nav[-1] ** (1 / n_years) - 1
bench_cagr = benchmark_nav[-1] ** (1 / n_years) - 1


def max_dd(nav):
    nav = np.array(nav)
    peak = np.maximum.accumulate(nav)
    return ((nav - peak) / peak).min()


mom_mdd = max_dd(momentum_nav)
bench_mdd = max_dd(benchmark_nav)
margin_pp = (mom_cagr - bench_cagr) * 100
mdd_diff_pp = (abs(mom_mdd) - abs(bench_mdd)) * 100

cond_a = mom_cagr > bench_cagr
cond_b = margin_pp >= MARGIN_REQUIRED_PP
cond_c = mdd_diff_pp <= MAXDD_SLACK_PP
overall = cond_a and cond_b and cond_c

print("\n" + "=" * 90)
print("BUG #11 MATERIALITY CHECK -- STUDY 2 LARGE-CAP REPLICATION, 78 ENTITIES EXCLUDED")
print("=" * 90)
print(f"\n{'':22s}{'ORIGINAL':>12s}{'EXCLUDED-78':>14s}{'DIFF':>10s}")
print(f"{'Momentum CAGR':22s}{ORIGINAL['mom_cagr']*100:>11.2f}%{mom_cagr*100:>13.2f}%{(mom_cagr-ORIGINAL['mom_cagr'])*100:>+9.2f}pp")
print(f"{'Benchmark CAGR':22s}{ORIGINAL['bench_cagr']*100:>11.2f}%{bench_cagr*100:>13.2f}%{(bench_cagr-ORIGINAL['bench_cagr'])*100:>+9.2f}pp")
print(f"{'Margin (pts)':22s}{ORIGINAL['margin_pp']:>11.2f} {margin_pp:>13.2f} {margin_pp-ORIGINAL['margin_pp']:>+9.2f}")
print(f"{'Momentum MaxDD':22s}{ORIGINAL['mom_mdd']*100:>11.2f}%{mom_mdd*100:>13.2f}%{(mom_mdd-ORIGINAL['mom_mdd'])*100:>+9.2f}pp")
print(f"{'Benchmark MaxDD':22s}{ORIGINAL['bench_mdd']*100:>11.2f}%{bench_mdd*100:>13.2f}%{(bench_mdd-ORIGINAL['bench_mdd'])*100:>+9.2f}pp")

print("\n--- DECISION RULE, old vs new ---")
print(f"(a) CAGR>benchmark: ORIGINAL=PASS  NEW={'PASS' if cond_a else 'FAIL'} ({mom_cagr*100:.2f}% vs {bench_cagr*100:.2f}%)")
print(f"(b) margin>={MARGIN_REQUIRED_PP:.1f}pts: ORIGINAL=PASS  NEW={'PASS' if cond_b else 'FAIL'} (margin={margin_pp:.2f}pts)")
print(f"(c) MaxDD slack: ORIGINAL=PASS  NEW={'PASS' if cond_c else 'FAIL'} (diff={mdd_diff_pp:+.2f}pts)")
print(f"\nOVERALL: {'REPLICATES' if overall else 'DOES NOT REPLICATE'}")
any_flip = (cond_a != ORIGINAL["cond_a"]) or (cond_b != ORIGINAL["cond_b"]) or (cond_c != ORIGINAL["cond_c"])
print(f"ANY CONDITION FLIPPED vs original: {'YES -- STOP, per instruction' if any_flip else 'NO'}")

# --- how many of the 78 ever entered the large-cap top decile, and clustering ---
mom_full = compute_momentum_12_1(panel_all)
hits = []
for d in rebalance_dates:
    day = mom_full[mom_full["trade_date"] == d].dropna(subset=["value"])
    yr = pd.Timestamp(d).year
    cohort = cohort_by_year.get(yr, set())
    day = day[day["entity_id"].isin(cohort)]
    if len(day) < 20:
        continue
    cutoff = day["value"].quantile(1 - DECILE_FRAC)
    in_decile = day[(day["value"] >= cutoff) & (day["entity_id"].isin(excluded))]
    for _, row in in_decile.iterrows():
        hits.append({"date": d, "entity_id": row["entity_id"], "momentum_value": row["value"]})
hits_df = pd.DataFrame(hits)

print(f"\n--- Of the 78 excluded entities: how many entered the large-cap top decile at any rebalance ---")
if len(hits_df):
    print(f"{hits_df['entity_id'].nunique()} of 78 entities entered the top decile at "
          f">=1 rebalance ({len(hits_df)} entity-rebalance hits).")
    print(hits_df.to_string(index=False))
else:
    print("0 of 78 entities entered the large-cap top decile at any rebalance (unsurprising -- "
          "the 78 are mostly illiquid/thin names, and this universe is top-200-by-turnover).")

rec_df.to_csv(ROOT / "data" / "study2_largecap_bug11_check_records.csv", index=False)
print(f"\nSaved to data/study2_largecap_bug11_check_records.csv")
