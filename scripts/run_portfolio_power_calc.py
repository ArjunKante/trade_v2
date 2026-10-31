"""PREREGISTRATION_PORTFOLIO.md Section 7 -- POWER CALCULATION, run
FIRST, before any non-baseline configuration is evaluated. Runs ONLY the
baseline configuration (equal weight, full decile, PREREGISTRATION.md's
own passed-sealed-test construction) at each of the three rebalance
frequencies (21, 63, 126 trading days) on development data (2016-01-01
to 2025-03-18, entity_prices_daily's own physical truncation -- no
holdout authorization used or needed). Reports N periods, observed
period-return mean/std, and the minimum detectable difference in
annualized return at p<0.002 (Bonferroni, 24 trials) per frequency, both
as a bare detection threshold and as an 80%-power MDE.

STOPS HERE. Does not touch any of the other 23 configurations.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return
from monitor.persistence import same_isin_jump_excluded_entities

from portfolio.backtest import build_tercile_lookup, max_drawdown, run_config
from portfolio.power import ALPHA_BONFERRONI, false_positive_probability, minimum_detectable_difference, N_TRIALS

ROOT = Path(__file__).resolve().parents[1]
FREQUENCIES = [21, 63, 126]

print("=" * 90)
print("PREREGISTRATION_PORTFOLIO.md Section 7: POWER CALCULATION")
print("Baseline only (equal weight, full decile) at 21/63/126-day rebalance. Development data only.")
print("=" * 90)

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

excluded = same_isin_jump_excluded_entities(con)  # BUGS.md Bug #11
panel_all = read_entity_panel(con)  # entity_prices_daily -- physically pre-holdout-truncated, no authorization
panel = panel_all[~panel_all["entity_id"].isin(excluded)].reset_index(drop=True)
jump_dates = unexplained_jump_boundaries(con, before=None)  # BUGS.md Bug #1
con.close()

print(f"\nPanel: {len(panel):,} rows, {panel['entity_id'].nunique():,} entities, "
      f"{panel['trade_date'].min().date()} to {panel['trade_date'].max().date()} "
      f"({len(excluded)} same-ISIN-jump entities excluded)")

mom = compute_momentum_12_1(panel, unexplained_jump_dates=jump_dates)
tercile = build_tercile_lookup(panel)
all_dates = sorted(panel["trade_date"].unique())
print(f"{len(all_dates):,} distinct trading days in the development window")

print(f"\nBonferroni threshold for {N_TRIALS} trials: alpha = 0.05 / {N_TRIALS} = {ALPHA_BONFERRONI:.6f}")
print(f"P(>=1 false positive across {N_TRIALS} trials at UNCORRECTED alpha=0.05) = "
      f"{false_positive_probability(N_TRIALS, 0.05) * 100:.1f}%")

results = {}
for f in FREQUENCIES:
    print("\n" + "-" * 90)
    print(f"REBALANCE FREQUENCY: {f} trading days")
    print("-" * 90)

    fwd = compute_forward_return(panel, horizon=f, unexplained_jump_dates=jump_dates)
    res = run_config(mom, fwd, tercile, all_dates, concentration="decile", weighting="equal", rebalance_days=f)
    rec = res["records"]
    n = len(rec)
    print(f"N (realized, fully-trimmed rebalance periods): {n}")
    if n < 3:
        print("Fewer than 3 periods -- power calculation not meaningful at this frequency.")
        results[f] = {"n": n}
        continue

    period_returns = rec["net"].to_numpy()
    mean_period = float(period_returns.mean())
    std_period = float(period_returns.std(ddof=1))
    periods_per_year = 252 / f
    mean_annualized = (1 + mean_period) ** periods_per_year - 1
    print(f"Observed period NET return: mean={mean_period*100:.4f}%  std={std_period*100:.4f}%  "
          f"(annualized mean ~{mean_annualized*100:.2f}%)")
    print(f"Mean n_held: {rec['n_held'].mean():.1f}  Mean turnover: {rec['turnover'].mean()*100:.2f}%  "
          f"Mean cost/period: {rec['cost'].mean()*100:.4f}%")

    mdd = max_drawdown(res["nav"])
    print(f"MaxDD: {mdd['mdd']*100:.2f}%  duration: {mdd['duration_periods']} periods "
          f"(~{mdd['duration_periods']*f} trading days)")

    mde = minimum_detectable_difference(n, std_period, f)
    print(f"\nMinimum detectable difference vs. baseline, annualized, at p<{ALPHA_BONFERRONI:.4f} "
          f"(Bonferroni, {N_TRIALS} trials):")
    print(f"  bare detection threshold (no power term):  {mde['detection_threshold_annual']*100:+.2f} pp")
    print(f"  minimum detectable EFFECT at 80% power:     {mde['mde_annual']*100:+.2f} pp")
    print(f"  (t_alpha={mde['t_alpha']:.3f}, t_beta={mde['t_beta']:.3f}, df={mde['df']}, "
          f"SE_period={mde['se_period']*100:.4f}%)")

    results[f] = {
        "n": n, "mean_period": mean_period, "std_period": std_period, "mean_annualized": mean_annualized,
        "mdd": mdd["mdd"], "mdd_duration_periods": mdd["duration_periods"],
        "mean_turnover": float(rec["turnover"].mean()), "mean_cost": float(rec["cost"].mean()),
        **mde,
    }

print("\n" + "=" * 90)
print("SUMMARY -- minimum detectable annualized difference vs. baseline, by rebalance frequency")
print("=" * 90)
print(f"{'freq':>6s}{'N':>6s}{'baseline CAGR':>16s}{'period std':>14s}{'MDE (80% power)':>18s}{'threshold only':>16s}")
for f in FREQUENCIES:
    r = results.get(f, {})
    if "mde_annual" not in r:
        print(f"{f:>6d}{r.get('n', 0):>6d}{'(insufficient N)':>16s}")
        continue
    print(f"{f:>6d}{r['n']:>6d}{r['mean_annualized']*100:>15.2f}%{r['std_period']*100:>13.3f}%"
          f"{r['mde_annual']*100:>17.2f}pp{r['detection_threshold_annual']*100:>15.2f}pp")

print("\n=== STOPPING per PREREGISTRATION_PORTFOLIO.md Section 11 Step 2. "
      "No other configuration has been run. ===")
