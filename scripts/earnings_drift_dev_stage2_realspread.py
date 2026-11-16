"""DEV Stage 2: rank within quarter, assign top decile vs rest, compute
the REAL per-quarter spread (raw and winsorized), and the quarter-
clustered bootstrap CI on the mean spread (Gate condition 1).
Reads Stage 1's checkpoint; writes its own checkpoint for later stages.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SCRATCH = Path(r"C:\Users\ARJUNK~1\AppData\Local\Temp\claude\C--projects-trade-new\cee5e6e2-73d6-4e3c-af4a-e518efcfde77\scratchpad")
DECILE_FRAC = 0.10
WINSOR_LO, WINSOR_HI = 0.01, 0.99
N_BOOT = 5000
RNG = np.random.RandomState(20261116)

events = pd.read_parquet(SCRATCH / "earnings_drift_dev_events.parquet")
print(f"Loaded {len(events):,} events, {events['quarter'].nunique()} quarters")

# within-quarter winsorization of the HOLDING return (1st/99th pctile, Section 6 frozen rule)
bounds = events.groupby("quarter")["holding_return"].quantile([WINSOR_LO, WINSOR_HI]).unstack()
bounds.columns = ["q_lo", "q_hi"]
events = events.join(bounds, on="quarter")
events["holding_return_wins"] = events["holding_return"].clip(events["q_lo"], events["q_hi"])

# rank by EVENT RETURN within quarter; top decile vs rest
events["rank_pct"] = events.groupby("quarter")["event_return"].rank(pct=True, method="first")
events["is_top_decile"] = events["rank_pct"] > (1 - DECILE_FRAC)

def quarterly_spread(df, col):
    g = df.groupby(["quarter", "is_top_decile"])[col].mean().unstack()
    g.columns = ["rest", "top"]
    return (g["top"] - g["rest"]).dropna()

spread_raw = quarterly_spread(events, "holding_return")
spread_wins = quarterly_spread(events, "holding_return_wins")

print(f"\nQuarters with both top-decile and rest present: raw={len(spread_raw)}, winsorized={len(spread_wins)}")
print(f"\nRAW spread: mean={spread_raw.mean()*100:.3f}%  median={spread_raw.median()*100:.3f}%  "
      f"sd={spread_raw.std()*100:.3f}%  min={spread_raw.min()*100:.2f}%  max={spread_raw.max()*100:.2f}%")
print(f"WINSORIZED spread: mean={spread_wins.mean()*100:.3f}%  median={spread_wins.median()*100:.3f}%  "
      f"sd={spread_wins.std()*100:.3f}%  min={spread_wins.min()*100:.2f}%  max={spread_wins.max()*100:.2f}%")

def cluster_bootstrap_ci(spread_series, n_boot=N_BOOT, rng=RNG):
    vals = spread_series.to_numpy()
    n = len(vals)
    boots = rng.choice(vals, size=(n_boot, n), replace=True).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return lo, hi, boots

lo_raw, hi_raw, boots_raw = cluster_bootstrap_ci(spread_raw)
lo_wins, hi_wins, boots_wins = cluster_bootstrap_ci(spread_wins)
print(f"\nQuarter-clustered bootstrap 95% CI (RAW):        [{lo_raw*100:.3f}%, {hi_raw*100:.3f}%]  "
      f"{'EXCLUDES zero' if lo_raw>0 or hi_raw<0 else 'INCLUDES zero'}")
print(f"Quarter-clustered bootstrap 95% CI (WINSORIZED): [{lo_wins*100:.3f}%, {hi_wins*100:.3f}%]  "
      f"{'EXCLUDES zero' if lo_wins>0 or hi_wins<0 else 'INCLUDES zero'}")

gate1_raw = (spread_raw.mean() > 0) and (lo_raw > 0 or hi_raw < 0) and lo_raw > 0
gate1_wins = (spread_wins.mean() > 0) and (lo_wins > 0 or hi_wins < 0) and lo_wins > 0
print(f"\nGate condition 1 (mean>0 AND CI excludes zero on the positive side) -- RAW: {gate1_raw}  WINSORIZED: {gate1_wins}")

events.to_parquet(SCRATCH / "earnings_drift_dev_events_ranked.parquet")
spread_raw.to_frame("spread").to_parquet(SCRATCH / "earnings_drift_dev_spread_raw.parquet")
spread_wins.to_frame("spread").to_parquet(SCRATCH / "earnings_drift_dev_spread_wins.parquet")
print("\nCheckpoints written.")
