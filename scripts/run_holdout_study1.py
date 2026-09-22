"""STUDY 1 HOLDOUT EVALUATION -- run exactly once, per PREREGISTRATION.md.

This is the one script authorized to read past SEALED_HOLDOUT_START. Every
factor definition, cost figure, and construction rule here is copied
unchanged from the frozen configuration in PREREGISTRATION.md and the
already-validated pre-holdout backtest -- nothing is tuned here.

The full price panel is read once (validated separately, on pre-holdout
data only, to reproduce the trusted entity_prices_daily table exactly
before this script was written). The backtest simulation runs continuously
from 2016 through the end of available data, so portfolio/turnover state
carries naturally across the holdout boundary exactly as a live strategy's
would -- but only holdout-window rebalances are used for the decision rule.
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

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10
COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5
MARGIN_REQUIRED_PP = 3.0
MAXDD_SLACK_PP = 10.0

LOG_PATH = ROOT / "data" / "holdout_access_log.txt"
with open(LOG_PATH, "a") as f:
    f.write(f"{dt.datetime.now().isoformat()} | scripts/run_holdout_study1.py | "
            f"authorize_holdout=True | Study 1 of 3 | momentum_12_1 holdout evaluation\n")
print(f"Holdout access authorized and logged to {LOG_PATH}")

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_full_entity_panel_authorized(con, authorize_holdout=True)
con.close()
print(f"Full panel: {len(panel)} rows, {panel['entity_id'].nunique()} entities, "
      f"{panel['trade_date'].min().date()} to {panel['trade_date'].max().date()}")

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
# drop any rebalance whose forward window runs past currently available data
rebalance_dates_all = [d for d in rebalance_dates_all if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]
print(f"{len(rebalance_dates_all)} total rebalances, 2016 through end of available data")

holdout_start_ts = pd.Timestamp(SEALED_HOLDOUT_START)
holdout_rebalance_dates = [d for d in rebalance_dates_all if d >= holdout_start_ts]
print(f"{len(holdout_rebalance_dates)} rebalances fall inside the sealed holdout "
      f"({holdout_rebalance_dates[0].date()} to {holdout_rebalance_dates[-1].date()})")

# ---- continuous simulation, 2016 through end, for portfolio-state continuity ----
momentum_nav = [1.0]
benchmark_nav = [1.0]
nav_dates = [rebalance_dates_all[0]]
prev_mom_set = None
prev_bench_set = None
records = []
exclusion_audit = []

for d in rebalance_dates_all:
    day_full = full[full["trade_date"] == d].copy()
    if len(day_full) < 20:
        continue
    clean_ids = set(clean[clean["trade_date"] == d]["entity_id"])
    pool = clean[clean["trade_date"] == d].rename(columns={"fwd_return": "realized_return"})
    if pool.empty:
        continue

    n_total = len(day_full)
    n_excluded = (~day_full["entity_id"].isin(clean_ids)).sum()

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
        "mom_n": len(mom_set), "mom_gross": gross_ret, "mom_turnover": turnover_frac, "mom_net": net_ret,
        "bench_n": len(bench_set), "bench_gross": bgross, "bench_turnover": bturnover, "bench_net": bnet,
        "n_total_eligible_by_factor": n_total, "n_excluded": n_excluded,
        "pct_excluded": n_excluded / n_total * 100,
    })
    nav_dates.append(d)

rec_df = pd.DataFrame(records)
holdout_rec = rec_df[rec_df["in_holdout"]].reset_index(drop=True)

print("\n" + "=" * 80)
print("HOLDOUT PERIOD RESULTS -- STUDY 1 (momentum_12_1)")
print("=" * 80)
print(f"Holdout window evaluated: {holdout_rec['date'].iloc[0].date()} to {holdout_rec['date'].iloc[-1].date()}")
print(f"Number of holdout rebalance periods: {len(holdout_rec)}")

print("\n--- Individual period returns, strategy vs benchmark side by side ---")
print(holdout_rec[["date", "mom_n", "mom_gross", "mom_turnover", "mom_net",
                    "bench_n", "bench_gross", "bench_turnover", "bench_net"]].to_string(index=False))

print("\n--- Eligibility exclusion count per holdout rebalance ---")
print(holdout_rec[["date", "n_total_eligible_by_factor", "n_excluded", "pct_excluded"]].to_string(index=False))
print(f"\nMean %% excluded in holdout: {holdout_rec['pct_excluded'].mean():.2f}%")
print(f"Mean %% excluded in original 2017-2024 backtest (for comparison, from prior report): 7.4%")

# ---- holdout-only CAGR/Sharpe/MaxDD, computed on the holdout-only NAV path ----
holdout_mom_nav = [1.0]
holdout_bench_nav = [1.0]
for _, row in holdout_rec.iterrows():
    holdout_mom_nav.append(holdout_mom_nav[-1] * (1 + row["mom_net"]))
    holdout_bench_nav.append(holdout_bench_nav[-1] * (1 + row["bench_net"]))

n_years_holdout = (holdout_rec["date"].iloc[-1] - holdout_rec["date"].iloc[0]).days / 365.25
if n_years_holdout <= 0:
    n_years_holdout = len(holdout_rec) * REBALANCE_DAYS / 252

mom_cagr = holdout_mom_nav[-1] ** (1 / n_years_holdout) - 1 if n_years_holdout > 0 else np.nan
bench_cagr = holdout_bench_nav[-1] ** (1 / n_years_holdout) - 1 if n_years_holdout > 0 else np.nan

pr_m = np.diff(holdout_mom_nav) / np.array(holdout_mom_nav[:-1])
pr_b = np.diff(holdout_bench_nav) / np.array(holdout_bench_nav[:-1])
ppy = 252 / REBALANCE_DAYS
mom_sharpe = (pr_m.mean() / pr_m.std()) * np.sqrt(ppy) if pr_m.std() > 0 else np.nan
bench_sharpe = (pr_b.mean() / pr_b.std()) * np.sqrt(ppy) if pr_b.std() > 0 else np.nan


def max_dd(nav):
    nav = np.array(nav)
    peak = np.maximum.accumulate(nav)
    return ((nav - peak) / peak).min()


mom_mdd = max_dd(holdout_mom_nav)
bench_mdd = max_dd(holdout_bench_nav)

print("\n--- Holdout-only NAV summary ---")
print(f"{'':22s}{'CAGR':>10s}{'Sharpe':>10s}{'MaxDD':>10s}{'FinalNAV':>12s}")
print(f"{'Momentum (net)':22s}{mom_cagr*100:>9.2f}%{mom_sharpe:>10.2f}{mom_mdd*100:>9.2f}%{holdout_mom_nav[-1]:>12.3f}")
print(f"{'Equal-weight (net)':22s}{bench_cagr*100:>9.2f}%{bench_sharpe:>10.2f}{bench_mdd*100:>9.2f}%{holdout_bench_nav[-1]:>12.3f}")

margin_pp = (mom_cagr - bench_cagr) * 100
mdd_diff_pp = (abs(mom_mdd) - abs(bench_mdd)) * 100

cond_a = mom_cagr > bench_cagr
cond_b = margin_pp >= MARGIN_REQUIRED_PP
cond_c = mdd_diff_pp <= MAXDD_SLACK_PP

print("\n" + "=" * 80)
print("DECISION RULE -- all three required (PREREGISTRATION.md, fixed before this run)")
print("=" * 80)
print(f"(a) Holdout CAGR exceeds benchmark CAGR, net of costs:")
print(f"    momentum {mom_cagr*100:.2f}%  vs  benchmark {bench_cagr*100:.2f}%  ->  {'PASS' if cond_a else 'FAIL'}")
print(f"(b) Margin >= {MARGIN_REQUIRED_PP:.1f} percentage points annualized:")
print(f"    margin = {margin_pp:.2f} points  ->  {'PASS' if cond_b else 'FAIL'}")
print(f"(c) MaxDD not more than {MAXDD_SLACK_PP:.1f} points worse than benchmark's:")
print(f"    momentum MaxDD {mom_mdd*100:.2f}%  vs  benchmark MaxDD {bench_mdd*100:.2f}%  "
      f"(diff {mdd_diff_pp:+.2f} pts)  ->  {'PASS' if cond_c else 'FAIL'}")

overall = cond_a and cond_b and cond_c
print(f"\nOVERALL: {'PASS -- momentum replicated out of sample (thin sample, see PREREGISTRATION.md)' if overall else 'FAIL -- momentum did not replicate'}")

print("\n" + "=" * 80)
print("STUDY COUNTER: Study 1 of 3 complete. Holdout for this dataset is now SPENT.")
print("=" * 80)

holdout_rec.to_csv(ROOT / "data" / "holdout_study1_records.csv", index=False)
rec_df.to_csv(ROOT / "data" / "holdout_study1_full_continuous_records.csv", index=False)
print("\nSaved holdout_rec to data/holdout_study1_records.csv, full continuous sim to data/holdout_study1_full_continuous_records.csv")
