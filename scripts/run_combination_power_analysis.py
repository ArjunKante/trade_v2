"""Power analysis for PREREGISTRATION_COMBINATION.md -- run BEFORE any
threshold is fixed, using historical margin VARIANCE only, never the
historical margin MEAN. Variance is a property of the data's noisiness
(how much a margin swings period to period); using it to size a test is
standard power analysis. Using the MEAN to size a test would be fitting the
threshold to a result already seen, which this project's whole discipline
exists to prevent -- so this script never calls .mean() on any margin
series, by construction, not just by omission from the printed output.

Universe, per rebalance date: entities with BOTH momentum_12_1 AND
earnings_yield computable (the same restriction PREREGISTRATION_COMBINATION.md
itself specifies), on the same 2018-2024 pre-holdout dates already used in
Phase E (loaded from data/phase_e_master_frame.csv rather than recomputed,
since that frame already has earnings_yield + fwd_return on the exact
rebalance grid this needs).

Three legs, same restricted universe, same dates, GROSS returns (costs not
applied here -- this is a variance/noise-magnitude estimate, not a CAGR
estimate, and costs are similar enough across the three legs, given they
share a rebalance cadence and a momentum-tilted composition, that they are
not expected to change the variance conclusion; flagged as a simplification,
not hidden):
  - combination: top decile by mean of (percentile rank of momentum_12_1,
    percentile rank of earnings_yield), equal-weighted.
  - momentum-alone: top decile by momentum_12_1 alone, equal-weighted.
  - benchmark: equal-weight of the full restricted universe.
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

ROOT = Path(__file__).resolve().parents[1]
DECILE_FRAC = 0.10

master = pd.read_csv(ROOT / "data" / "phase_e_master_frame.csv", parse_dates=["trade_date", "eval_date"])
ey = master[["entity_id", "trade_date", "earnings_yield", "fwd_return"]].dropna()
ey = ey[np.isfinite(ey["earnings_yield"])]

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)
con.close()

print("Computing momentum_12_1 on the full panel...")
mom = compute_momentum_12_1(panel.sort_values(["entity_id", "trade_date"]))
mom = mom.rename(columns={"value": "momentum_12_1"}).dropna()

m = ey.merge(mom, on=["entity_id", "trade_date"], how="inner")
print(f"{len(m)} obs after requiring both earnings_yield and momentum_12_1, "
      f"{m['trade_date'].nunique()} distinct rebalance dates.")

records = []
for d, day in m.groupby("trade_date"):
    if len(day) < 20:
        continue
    day = day.copy()
    day["mom_rank"] = day["momentum_12_1"].rank(pct=True)
    day["ey_rank"] = day["earnings_yield"].rank(pct=True)
    day["combo_rank"] = (day["mom_rank"] + day["ey_rank"]) / 2

    combo_cutoff = day["combo_rank"].quantile(1 - DECILE_FRAC)
    mom_cutoff = day["mom_rank"].quantile(1 - DECILE_FRAC)

    combo_ret = day.loc[day["combo_rank"] >= combo_cutoff, "fwd_return"].mean()
    mom_ret = day.loc[day["mom_rank"] >= mom_cutoff, "fwd_return"].mean()
    bench_ret = day["fwd_return"].mean()

    records.append({
        "trade_date": d, "n": len(day),
        "combo_ret": combo_ret, "mom_ret": mom_ret, "bench_ret": bench_ret,
        "margin_over_momentum": combo_ret - mom_ret,
        "margin_over_benchmark": combo_ret - bench_ret,
    })

rec = pd.DataFrame(records).sort_values("trade_date").reset_index(drop=True)
n_periods_available = len(rec)
print(f"\n{n_periods_available} usable rebalance periods (n>=20 per period).")

# --- power analysis: VARIANCE only, mean never computed ---
std_over_momentum = rec["margin_over_momentum"].std(ddof=1)
std_over_benchmark = rec["margin_over_benchmark"].std(ddof=1)

N_FORWARD_QUARTERS = 8
se_over_momentum_n8 = std_over_momentum / np.sqrt(N_FORWARD_QUARTERS)
se_over_benchmark_n8 = std_over_benchmark / np.sqrt(N_FORWARD_QUARTERS)
margin_needed_t2_momentum = 2.0 * se_over_momentum_n8
margin_needed_t2_benchmark = 2.0 * se_over_benchmark_n8

print("\n=== POWER ANALYSIS (variance only -- historical mean margin NOT computed) ===")
print(f"n historical periods used for variance estimate: {n_periods_available}")
print(f"std of per-period margin over momentum-alone:  {std_over_momentum*100:.3f} pts")
print(f"std of per-period margin over equal-weight:     {std_over_benchmark*100:.3f} pts")
print(f"\nAt n={N_FORWARD_QUARTERS} forward quarters:")
print(f"  SE (margin over momentum-alone):  {se_over_momentum_n8*100:.3f} pts")
print(f"  SE (margin over equal-weight):    {se_over_benchmark_n8*100:.3f} pts")
print(f"\nMargin needed for t>=2.0 at n={N_FORWARD_QUARTERS}:")
print(f"  vs momentum-alone:  {margin_needed_t2_momentum*100:.3f} pts (annualized CAGR-equivalent scaling not applied -- this is per-period)")
print(f"  vs equal-weight:    {margin_needed_t2_benchmark*100:.3f} pts")

# annualized scaling note: margins here are PER-63-TRADING-DAY-PERIOD, not
# annualized. Rough annualization for interpretability: ~4 periods/year,
# so an annualized margin needed is on the order of margin_needed * 4 IF
# margins compounded independently per period (a simplification -- real
# CAGR compounding is multiplicative, not additive, but adequate for an
# order-of-magnitude power check).
periods_per_year = 252 / 63
print(f"\nRough annualized-scale equivalent (x{periods_per_year:.0f} periods/year, additive approximation):")
print(f"  vs momentum-alone:  ~{margin_needed_t2_momentum*100*periods_per_year:.2f} annualized pts needed for t>=2.0")
print(f"  vs equal-weight:    ~{margin_needed_t2_benchmark*100*periods_per_year:.2f} annualized pts needed for t>=2.0")

rec.to_csv(ROOT / "data" / "combination_power_analysis_records.csv", index=False)
print("\nSaved per-period records (margins only, no mean reported above) to "
      "data/combination_power_analysis_records.csv")
