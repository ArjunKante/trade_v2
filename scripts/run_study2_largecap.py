"""STUDY 2 -- large-cap replication. CV-only, no holdout (pre-holdout data
already seen in Study 1's own diagnostics). Universe: top 200 by trailing
median turnover, annual reconstitution, plain rank band, no buffer.
Configuration otherwise IDENTICAL to Study 1 -- momentum_12_1, long-only,
top decile, equal weight, 63-day rebalance, STALE_GAP_DAYS=5. Cost: flat
high-liquidity tercile rate (~23bps), not blended -- this universe is
large-cap by construction.
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

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10
TOP_N_LARGECAP = 200
FLAT_COST_BPS = 23.0  # high-liquidity tercile rate; large-cap universe by construction
MARGIN_REQUIRED_PP = 2.0
MAXDD_SLACK_PP = 10.0  # same operationalization as Study 1

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)
con.close()
print(f"Pre-holdout panel: {len(panel)} rows, {panel['entity_id'].nunique()} entities, "
      f"{panel['trade_date'].min().date()} to {panel['trade_date'].max().date()}")

# --- annual reconstitution: top 200 by trailing 252-day median turnover, decided using
#     only data through the LAST trading day of the PRIOR year (no lookahead) ---
p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_year"] = p["trade_date"].dt.year
p["_trailing_turnover"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(252, min_periods=252).median())

year_end_snapshot = p.sort_values("trade_date").groupby(["entity_id", "_year"]).tail(1)
cohort_by_year = {}
for y in sorted(year_end_snapshot["_year"].unique()):
    snap = year_end_snapshot[year_end_snapshot["_year"] == y].dropna(subset=["_trailing_turnover"])
    top200 = snap.nlargest(TOP_N_LARGECAP, "_trailing_turnover")["entity_id"]
    cohort_by_year[y + 1] = set(top200)  # this cohort governs membership for year y+1

print("\nAnnual large-cap cohort sizes (entities with valid trailing turnover at year-end):")
for y, cohort in sorted(cohort_by_year.items()):
    print(f"  membership for {y}: {len(cohort)} entities (decided from {y-1} year-end data)")

mom = compute_momentum_12_1(panel)
fwd = compute_forward_return(panel)
m = mom.merge(fwd, on=["entity_id", "trade_date"]).dropna(subset=["value", "fwd_return"])
m["_year"] = m["trade_date"].dt.year
m["_in_largecap"] = m.apply(lambda r: r["entity_id"] in cohort_by_year.get(r["_year"], set()), axis=1)
lc = m[m["_in_largecap"]].copy()

all_dates = sorted(lc["trade_date"].unique())
rebalance_dates = all_dates[::REBALANCE_DAYS]
rebalance_dates = [d for d in rebalance_dates if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]
print(f"\n{len(rebalance_dates)} rebalance dates in the large-cap universe, "
      f"{rebalance_dates[0].date()} to {rebalance_dates[-1].date()}")

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

    records.append({
        "date": d, "n_universe": len(pool), "n_holdings": len(mom_set),
        "mom_gross": gross_ret, "mom_turnover": turnover_frac, "mom_net": net_ret,
        "bench_gross": bgross, "bench_turnover": bturnover, "bench_net": bnet,
    })

rec_df = pd.DataFrame(records)

n_years = (rec_df["date"].iloc[-1] - rec_df["date"].iloc[0]).days / 365.25
mom_cagr = momentum_nav[-1] ** (1 / n_years) - 1
bench_cagr = benchmark_nav[-1] ** (1 / n_years) - 1
pr_m = np.diff(momentum_nav) / np.array(momentum_nav[:-1])
pr_b = np.diff(benchmark_nav) / np.array(benchmark_nav[:-1])
ppy = 252 / REBALANCE_DAYS
mom_sharpe = (pr_m.mean() / pr_m.std()) * np.sqrt(ppy)
bench_sharpe = (pr_b.mean() / pr_b.std()) * np.sqrt(ppy)


def max_dd(nav):
    nav = np.array(nav)
    peak = np.maximum.accumulate(nav)
    return ((nav - peak) / peak).min()


mom_mdd = max_dd(momentum_nav)
bench_mdd = max_dd(benchmark_nav)
margin_pp = (mom_cagr - bench_cagr) * 100
mdd_diff_pp = (abs(mom_mdd) - abs(bench_mdd)) * 100

print("\n" + "=" * 80)
print("STUDY 2 RESULTS -- large-cap (top 200 by turnover) momentum_12_1, CV-ONLY, NO HOLDOUT")
print("=" * 80)
print("*** THIS IS CV-ONLY EVIDENCE ON DATA ALREADY SEEN (pre-holdout). ***")
print("*** Weaker evidence than Study 1's holdout test. Not to be presented as equivalent. ***\n")

print(f"{'':22s}{'CAGR':>10s}{'Sharpe':>10s}{'MaxDD':>10s}{'FinalNAV':>12s}")
print(f"{'Momentum (net)':22s}{mom_cagr*100:>9.2f}%{mom_sharpe:>10.2f}{mom_mdd*100:>9.2f}%{momentum_nav[-1]:>12.3f}")
print(f"{'Equal-weight (net)':22s}{bench_cagr*100:>9.2f}%{bench_sharpe:>10.2f}{bench_mdd*100:>9.2f}%{benchmark_nav[-1]:>12.3f}")

cond_a = mom_cagr > bench_cagr
cond_b = margin_pp >= MARGIN_REQUIRED_PP
cond_c = mdd_diff_pp <= MAXDD_SLACK_PP

print("\n--- DECISION RULE (fixed before this run) ---")
print(f"(a) momentum CAGR > benchmark CAGR: {mom_cagr*100:.2f}% vs {bench_cagr*100:.2f}%  -> {'PASS' if cond_a else 'FAIL'}")
print(f"(b) margin >= {MARGIN_REQUIRED_PP:.1f} pts: margin = {margin_pp:.2f} pts  -> {'PASS' if cond_b else 'FAIL'}")
print(f"(c) MaxDD not >{MAXDD_SLACK_PP:.1f}pts worse: mom {mom_mdd*100:.2f}% vs bench {bench_mdd*100:.2f}% "
      f"(diff {mdd_diff_pp:+.2f} pts)  -> {'PASS' if cond_c else 'FAIL'}")
overall = cond_a and cond_b and cond_c
print(f"\nOVERALL: {'REPLICATES' if overall else 'DOES NOT REPLICATE'}")

print("\n--- Individual period returns ---")
print(rec_df[["date", "n_universe", "n_holdings", "mom_gross", "mom_turnover", "mom_net",
              "bench_gross", "bench_turnover", "bench_net"]].to_string(index=False))

print("\n--- Entity count per rebalance (universe size check) ---")
print(rec_df[["date", "n_universe"]].to_string(index=False))

rec_df.to_csv(ROOT / "data" / "study2_largecap_records.csv", index=False)
