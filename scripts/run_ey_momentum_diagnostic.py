"""ONE DIAGNOSTIC -- no slot spent, no pre-registration. Decides whether an
earnings_yield + momentum combination is even worth pre-registering as a
future study; does not itself constitute that study.

Two questions:
  (1) Cross-sectional rank correlation between earnings_yield and
      momentum_12_1, per rebalance date -- mean, std, by year. Negative =
      genuinely diversifying (matches the literature's cheap-stocks-are-
      recent-losers finding); near zero = independent information; positive
      = EY largely duplicates momentum.
  (2) earnings_yield's IC computed only on entities NOT in momentum's top
      decile per date -- if EY's signal lives mostly among names momentum
      already selects, it's redundant.

STOP after this diagnostic -- no composite, no pre-registration here.
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
from factors.ic_eval import daily_rank_ic, ic_by_year, rebalance_spacing_trading_days, nonoverlapping_ic_report, HORIZON_DAYS

ROOT = Path(__file__).resolve().parents[1]

master = pd.read_csv(ROOT / "data" / "phase_e_master_frame.csv", parse_dates=["trade_date", "eval_date"])

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)
con.close()

print("Computing momentum_12_1 on the full panel...")
mom = compute_momentum_12_1(panel.sort_values(["entity_id", "trade_date"]))
mom = mom.rename(columns={"value": "momentum_12_1"})

m = master.merge(mom, on=["entity_id", "trade_date"], how="left")

# --- (1) cross-sectional rank correlation, EY vs momentum, per rebalance date ---
print("\n" + "=" * 90)
print("(1) Cross-sectional rank correlation: earnings_yield vs momentum_12_1, per rebalance date")
print("=" * 90)
corr_sub = m[["trade_date", "earnings_yield", "momentum_12_1"]].rename(
    columns={"earnings_yield": "value"}
).dropna(subset=["value", "momentum_12_1"])
corr_sub = corr_sub[np.isfinite(corr_sub["value"]) & np.isfinite(corr_sub["momentum_12_1"])]
daily_corr = daily_rank_ic(corr_sub, factor_col="value", target_col="momentum_12_1").dropna(subset=["ic"])
print(f"n_dates={len(daily_corr)}  mean_corr={daily_corr['ic'].mean():+.4f}  std={daily_corr['ic'].std(ddof=1):.4f}")
print("\nBy year:")
daily_corr_y = daily_corr.copy()
daily_corr_y["year"] = pd.to_datetime(daily_corr_y["trade_date"]).dt.year
print(daily_corr_y.groupby("year")["ic"].agg(["mean", "std", "count"]).reset_index().to_string(index=False))

mean_corr = daily_corr["ic"].mean()
if mean_corr < -0.05:
    verdict = "NEGATIVE -- EY appears genuinely diversifying relative to momentum (matches the literature)."
elif abs(mean_corr) <= 0.05:
    verdict = "NEAR ZERO -- EY appears to carry information largely independent of momentum."
else:
    verdict = "POSITIVE -- EY overlaps with momentum; a combination may add little beyond momentum alone."
print(f"\nVerdict: {verdict}")

# --- (2) EY's IC restricted to entities NOT in momentum's top decile, per date ---
print("\n" + "=" * 90)
print("(2) earnings_yield IC restricted to entities NOT in momentum's top decile (per rebalance date)")
print("=" * 90)
mom_sub = m[["entity_id", "trade_date", "momentum_12_1"]].dropna(subset=["momentum_12_1"])
mom_sub = mom_sub[np.isfinite(mom_sub["momentum_12_1"])].copy()
mom_sub["mom_decile"] = mom_sub.groupby("trade_date")["momentum_12_1"].transform(
    lambda s: pd.qcut(s.rank(method="first"), 10, labels=False, duplicates="drop")
)
top_decile_mask = mom_sub[mom_sub["mom_decile"] == mom_sub["mom_decile"].max()][["entity_id", "trade_date"]]
top_decile_mask["_in_top_momentum"] = True

ey_sub = m[["entity_id", "trade_date", "eval_date", "fwd_return", "earnings_yield"]].rename(
    columns={"earnings_yield": "value"}
).dropna(subset=["value", "fwd_return"])
ey_sub = ey_sub[np.isfinite(ey_sub["value"])]
ey_sub = ey_sub.merge(top_decile_mask, on=["entity_id", "trade_date"], how="left")
ey_ex_top_mom = ey_sub[ey_sub["_in_top_momentum"].isna()].drop(columns=["_in_top_momentum"])

n = len(ey_ex_top_mom)
print(f"n_obs={n} (full EY set was {len(ey_sub)}; excluded {len(ey_sub) - n} obs in momentum's top decile)")
all_dates_ref = sorted(panel["trade_date"].unique())
spacing = rebalance_spacing_trading_days(ey_ex_top_mom["trade_date"].unique(), all_dates_ref)
print(f"rebalance spacing (trading days): min={spacing['min']} median={spacing['median']} max={spacing['max']}")
if spacing["min"] is not None and spacing["min"] >= HORIZON_DAYS:
    rep = nonoverlapping_ic_report(ey_ex_top_mom, min_spacing_trading_days=spacing["min"])
    print(f"mean_ic={rep['mean_ic']:+.4f}  std_ic={rep['std_ic']:.4f}  se={rep['se_ic']:.4f}"
          f"  t={rep['t_stat']:+.2f}  n_dates={rep['n_dates']}")
    print("(compare to the full-universe earnings_yield raw t=+2.86 from run_phase_e_factors.py --")
    print(" if this ex-top-momentum IC is similar or stronger, EY's signal does not live mainly")
    print(" inside names momentum already selects; if it collapses, EY is largely redundant.)")
else:
    print("spacing check failed -- cannot report a direct SE here without risking understatement.")

print("\n" + "=" * 90)
print("RECORDED CONSTRAINTS (apply to any future combined study, not just this diagnostic)")
print("=" * 90)
print("- Fundamentals have ZERO coverage in the sealed holdout window (April 2025 Integrated Filing")
print("  format change broke the quarterly XBRL extractor's tag conventions). Any momentum+fundamentals")
print("  combination is CV-only on data already seen in Study 1/Study 2 -- NOT a sealed test. No sealed")
print("  test is possible until an Integrated Filing fetcher is built. State this alongside any future")
print("  combined-backtest result so it is never read as validated out-of-sample.")
print("- Stale-beats-fresh anomaly (earnings_yield/pe more significant on stale than fresh half): a")
print("  possible post-earnings-announcement-drift (PEAD) mechanism is plausible, but the fresh/stale")
print("  split halves an already-small sample (26 -> 13ish independent dates each) -- within noise at")
print("  this sample size. NOT investigated further, per instruction.")
print("- Piotroski F-Score and Altman Z-Score were not implemented (Altman Z needs a RetainedEarnings")
print("  tag unavailable in the extracted set; a time-boxing choice). Recorded, not silently dropped.")

print("\nSTOP after this diagnostic. No composite, no pre-registration.")
