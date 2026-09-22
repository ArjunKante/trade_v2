"""Phase 2 gate: per-factor rank IC on forward 63-day returns, individually,
before any composite. Reads the pre-holdout-only entity_prices_daily panel
(materialized separately, already excludes the sealed window).
"""
import datetime as dt
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.holdout import SEALED_HOLDOUT_START, guard_date_range
from data_layer.entity_panel import read_entity_panel
from factors.momentum import compute_momentum_12_1, compute_momentum_6_1
from factors.lowvol import compute_trailing_vol, compute_beta
from factors.target import compute_forward_return
from factors.ic_eval import fold_level_ic_report, ic_by_year

ROOT = Path(__file__).resolve().parents[1]
N_SPLITS = 10
EXPERIMENTS_CSV = ROOT / "experiments.csv"

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

print("Loading entity panel (read-only connection)...")
panel = read_entity_panel(con)
guard_date_range(panel["trade_date"].min().date(), panel["trade_date"].max().date())
print(f"  {len(panel)} rows, {panel['entity_id'].nunique()} entities, "
      f"{panel['trade_date'].min().date()} to {panel['trade_date'].max().date()}")
assert panel["trade_date"].max().date() < SEALED_HOLDOUT_START, "panel must never reach the sealed holdout"

index_raw = con.execute("SELECT trade_date, close FROM index_eod WHERE index_name='NIFTY50' ORDER BY trade_date").fetchdf()
index_raw["trade_date"] = pd.to_datetime(index_raw["trade_date"])
index_raw["mkt_logret"] = np.log(index_raw["close"] / index_raw["close"].shift(1))
index_returns = index_raw[["trade_date", "mkt_logret"]]
print(f"  index series: {len(index_returns)} rows")

print("\nComputing factors...")
t0 = time.time()
mom_12_1 = compute_momentum_12_1(panel)
print(f"  momentum_12_1: {time.time()-t0:.1f}s")
t0 = time.time()
mom_6_1 = compute_momentum_6_1(panel)
print(f"  momentum_6_1: {time.time()-t0:.1f}s")
t0 = time.time()
vol_252 = compute_trailing_vol(panel)
print(f"  trailing_vol_252: {time.time()-t0:.1f}s")
t0 = time.time()
beta_252 = compute_beta(panel, index_returns)
print(f"  beta_252: {time.time()-t0:.1f}s")

t0 = time.time()
fwd = compute_forward_return(panel)
print(f"  forward_return_63d: {time.time()-t0:.1f}s ({len(fwd)} rows)")

factors = {
    "momentum_12_1": mom_12_1,
    "momentum_6_1": mom_6_1,
    "trailing_vol_252": vol_252,
    "beta_252": beta_252,
}

results = []
experiments_rows = []
run_ts = dt.datetime.now().isoformat()

for name, fdf in factors.items():
    merged = fdf.merge(fwd, on=["entity_id", "trade_date"], how="inner")
    merged = merged.dropna(subset=["value", "fwd_return", "eval_date"])
    print(f"\n=== {name} === ({len(merged)} obs, {merged['entity_id'].nunique()} entities)")

    report = fold_level_ic_report(merged, n_splits=N_SPLITS)
    yearly = ic_by_year(merged)

    print(f"  n_folds_used: {report['n_folds_used']} / {report['n_folds_requested']} requested")
    print(f"  mean IC: {report['mean_ic']:.4f}  SE: {report['se_ic']:.4f}  t-stat: {report['t_stat']:.2f}")
    print(f"  fold ICs: {[round(x,4) for x in report['fold_ics']]}")
    print("  IC by year:")
    print(yearly.to_string(index=False))

    leak_flag = abs(report["mean_ic"]) > 0.15
    if leak_flag:
        print(f"  !!! IC magnitude {report['mean_ic']:.4f} exceeds 0.15 -- STOP, hunt for leakage before believing this.")

    results.append({
        "factor": name, "n_obs": len(merged), "n_entities": merged["entity_id"].nunique(),
        "n_folds_used": report["n_folds_used"], "mean_ic": report["mean_ic"],
        "se_ic": report["se_ic"], "t_stat": report["t_stat"], "leak_flag": leak_flag,
    })
    experiments_rows.append({
        "run_ts": run_ts, "phase": "phase2_factor_ic", "factor": name,
        "n_splits_requested": N_SPLITS, "n_folds_used": report["n_folds_used"],
        "purge": "63D", "embargo": "5D", "horizon_days": 63,
        "universe": "all INE/IN9 EQ entities, no liquidity filter, pre-holdout only",
        "n_obs": len(merged), "n_entities": merged["entity_id"].nunique(),
        "mean_ic": report["mean_ic"], "se_ic": report["se_ic"], "t_stat": report["t_stat"],
        "leak_flag_ic_gt_0.15": leak_flag, "status": "completed",
        "notes": "individual factor IC, no composite, per user gate",
    })

summary = pd.DataFrame(results)
print("\n\n=== SUMMARY: all factors ===")
print(summary.to_string(index=False))

exp_df = pd.DataFrame(experiments_rows)
if EXPERIMENTS_CSV.exists():
    exp_df.to_csv(EXPERIMENTS_CSV, mode="a", header=False, index=False)
else:
    exp_df.to_csv(EXPERIMENTS_CSV, mode="w", header=True, index=False)
print(f"\nLogged {len(exp_df)} rows to {EXPERIMENTS_CSV}")

con.close()
