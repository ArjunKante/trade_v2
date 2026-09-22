"""IC-based power analysis for PREREGISTRATION_COMBINATION.md, computed
because the portfolio-margin power analysis (run_combination_power_analysis.py)
found the margin metric itself is the problem: collapsing ~1,200 stocks into
one top-decile portfolio return per quarter throws away almost all the
cross-sectional information, leaving a per-period std of 4.657 (vs
momentum-alone) / 6.032 (vs benchmark) points relative to economically
plausible effect sizes of a few points. Rank IC uses the entire
cross-section every date instead of one decile cut, and Phase E's own
earnings_yield IC std (0.0756 per date) is far tighter relative to its
effect size than the portfolio margin was.

Same variance-only discipline as the margin power analysis: this script
never calls .mean() on any IC or paired-difference series. Using the mean
to size a test is fitting the threshold to a result already seen; variance
is a property of the data's noisiness and is what a power calculation is
supposed to use.

Paired difference (IC_combo - IC_momentum, same date) is the primary
comparison, not two separate ICs -- pairing removes the common
market-wide component that inflates each individual IC's variance (both
ICs move together with overall cross-sectional dispersion on a given date;
subtracting removes that shared noise, leaving only the part attributable
to EY's actual contribution to the ranking).
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
from factors.ic_eval import daily_rank_ic

ROOT = Path(__file__).resolve().parents[1]

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

# combined rank: equal-weight average of the two factors' own cross-sectional
# percentile ranks, per date -- same construction as the pre-registered
# strategy itself, just scored by IC here instead of top-decile portfolio return.
m["mom_rank"] = m.groupby("trade_date")["momentum_12_1"].rank(pct=True)
m["ey_rank"] = m.groupby("trade_date")["earnings_yield"].rank(pct=True)
m["combo_rank"] = (m["mom_rank"] + m["ey_rank"]) / 2

ic_combo = daily_rank_ic(m, factor_col="combo_rank", target_col="fwd_return").rename(columns={"ic": "ic_combo"})
ic_mom = daily_rank_ic(m, factor_col="momentum_12_1", target_col="fwd_return").rename(columns={"ic": "ic_mom"})

paired = ic_combo.merge(ic_mom, on="trade_date").dropna()
paired["paired_diff"] = paired["ic_combo"] - paired["ic_mom"]
n_dates = len(paired)
print(f"\n{n_dates} dates with both ICs computable.")

std_ic_combo = paired["ic_combo"].std(ddof=1)
std_ic_mom = paired["ic_mom"].std(ddof=1)
std_paired = paired["paired_diff"].std(ddof=1)

N8 = 8
se_ic_combo = std_ic_combo / np.sqrt(N8)
se_ic_mom = std_ic_mom / np.sqrt(N8)
se_paired = std_paired / np.sqrt(N8)

print("\n=== IC-BASED POWER ANALYSIS (variance only -- no mean IC computed or examined) ===")
print(f"std, IC of combined rank:      {std_ic_combo:.4f}   SE at n=8: {se_ic_combo:.4f}")
print(f"std, IC of momentum_12_1:      {std_ic_mom:.4f}   SE at n=8: {se_ic_mom:.4f}")
print(f"std, PAIRED DIFFERENCE:        {std_paired:.4f}   SE at n=8: {se_paired:.4f}")

diff_needed_t2 = 2.0 * se_paired
print(f"\nPaired IC difference needed for t>=2.0 at n=8: {diff_needed_t2:.4f}")

print("\nn needed for t>=2.0 to detect a given true paired IC difference:")
for target_diff in [0.01, 0.02, 0.03]:
    n_needed = (2.0 * std_paired / target_diff) ** 2
    print(f"  true difference = {target_diff:.2f}: n = {n_needed:.1f} quarters "
          f"({n_needed/4:.1f} years)")

paired.to_csv(ROOT / "data" / "combination_ic_power_analysis_records.csv", index=False)
print("\nSaved per-date IC records (no mean reported above) to "
      "data/combination_ic_power_analysis_records.csv")
