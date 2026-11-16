"""Descriptive measurement, pre-committed in EARNINGS_DRIFT_FINDINGS.md
before this script was written: per-quarter overlap between the
(closed) earnings-drift study's top decile and momentum_12_1's own
point-in-time top decile at the same date, and the per-quarter Spearman
correlation between event_return and momentum_12_1. NOT a new trial;
the closed study is not varied.
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(r"C:\projects\trade-new")
sys.path.insert(0, str(ROOT / "src"))
from data_layer.entity_panel import read_entity_panel
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return

SCRATCH = Path(r"C:\Users\ARJUNK~1\AppData\Local\Temp\claude\C--projects-trade-new\cee5e6e2-73d6-4e3c-af4a-e518efcfde77\scratchpad")
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10

events = pd.read_parquet(SCRATCH / "earnings_drift_dev_events_ranked.parquet")
events = events.drop_duplicates(subset=["entity_id", "d0"]).copy()
print(f"Deduplicated earnings events (1 row per entity/d0): {len(events):,}")

con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)
panel = read_entity_panel(con)
con.close()
print(f"Panel: {len(panel):,} rows, {panel['entity_id'].nunique():,} entities")

mom = compute_momentum_12_1(panel)  # no jump-date guard -- matches run_holdout_study1.py exactly
fwd = compute_forward_return(panel)

p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop") if s.notna().sum() >= 3 else pd.Series([np.nan]*len(s), index=s.index))

clean = mom.merge(fwd, on=["entity_id", "trade_date"]).merge(
    p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]
).dropna(subset=["value", "fwd_return", "_tercile"])

all_dates = sorted(mom["trade_date"].unique())
rebalance_dates = all_dates[::REBALANCE_DAYS]
print(f"Momentum rebalance dates (same schedule as run_holdout_study1.py): {len(rebalance_dates)}")

mom_top_decile_by_date = {}
for d in rebalance_dates:
    pool = clean[clean["trade_date"] == d]
    if pool.empty:
        continue
    cutoff = pool["value"].quantile(1 - DECILE_FRAC)
    mom_top_decile_by_date[d] = set(pool.loc[pool["value"] >= cutoff, "entity_id"])

rebalance_arr = np.array(sorted(mom_top_decile_by_date.keys()))

def momentum_top_decile_as_of(entity_id, d0):
    idx = np.searchsorted(rebalance_arr, np.datetime64(d0), side="right") - 1
    if idx < 0:
        return None
    d_reb = rebalance_arr[idx]
    return entity_id in mom_top_decile_by_date[pd.Timestamp(d_reb)]

# dense daily momentum value at d0, for the rank correlation
mom_indexed = mom.set_index(["entity_id", "trade_date"])["value"]

def mom_value_at(entity_id, d0):
    return mom_indexed.get((entity_id, pd.Timestamp(d0)), np.nan)

events["mom_top_decile_as_of_d0"] = events.apply(lambda r: momentum_top_decile_as_of(r["entity_id"], r["d0"]), axis=1)
events["mom_value_at_d0"] = events.apply(lambda r: mom_value_at(r["entity_id"], r["d0"]), axis=1)

# --- overlap, per quarter ---
earn_top = events[events["is_top_decile"] & events["mom_top_decile_as_of_d0"].notna()]
overlap = earn_top.groupby("quarter").apply(
    lambda g: g["mom_top_decile_as_of_d0"].mean(), include_groups=False
)
print("\nPer-quarter overlap fraction (earnings top decile also in momentum top decile at d0):")
print(overlap.to_string())
print(f"\nOverlap distribution: mean={overlap.mean():.3f} median={overlap.median():.3f} "
      f"min={overlap.min():.3f} max={overlap.max():.3f}  (n quarters={len(overlap)})")

# --- Spearman correlation, per quarter ---
corrs = {}
for q, g in events.dropna(subset=["mom_value_at_d0"]).groupby("quarter"):
    if len(g) >= 10:
        rho, _ = spearmanr(g["event_return"], g["mom_value_at_d0"])
        corrs[q] = rho
corrs = pd.Series(corrs)
print("\nPer-quarter Spearman correlation (event_return vs momentum_12_1 at d0):")
print(corrs.to_string())
print(f"\nCorrelation distribution: mean={corrs.mean():.3f} median={corrs.median():.3f} "
      f"min={corrs.min():.3f} max={corrs.max():.3f}  (n quarters={len(corrs)})")
