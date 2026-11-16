"""DEV Stage 3: SELECTION null -- random decile assignment within each
quarter (same construction as Phase 0's corrected MDE null), many
draws, building a null distribution of the "mean spread across
quarters" statistic, then the real spread's percentile within it.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SCRATCH = Path(r"C:\Users\ARJUNK~1\AppData\Local\Temp\claude\C--projects-trade-new\cee5e6e2-73d6-4e3c-af4a-e518efcfde77\scratchpad")
DECILE_FRAC = 0.10
N_DRAWS = 500

events = pd.read_parquet(SCRATCH / "earnings_drift_dev_events_ranked.parquet")
real_mean_raw = pd.read_parquet(SCRATCH / "earnings_drift_dev_spread_raw.parquet")["spread"].mean()
real_mean_wins = pd.read_parquet(SCRATCH / "earnings_drift_dev_spread_wins.parquet")["spread"].mean()
print(f"Real mean spread: raw={real_mean_raw*100:.3f}%  winsorized={real_mean_wins*100:.3f}%")

quarters = sorted(events["quarter"].unique())
groups = {q: g.reset_index(drop=True) for q, g in events.groupby("quarter")}

def one_draw(seed, col):
    rng = np.random.RandomState(seed)
    spreads = []
    for q in quarters:
        g = groups[q]
        n = len(g)
        n_top = max(1, int(round(n * DECILE_FRAC)))
        idx = rng.permutation(n)
        top_idx, rest_idx = idx[:n_top], idx[n_top:]
        spread = g[col].iloc[top_idx].mean() - g[col].iloc[rest_idx].mean()
        spreads.append(spread)
    return np.mean(spreads)

null_raw = np.array([one_draw(s, "holding_return") for s in range(N_DRAWS)])
null_wins = np.array([one_draw(s, "holding_return_wins") for s in range(N_DRAWS)])

pct_raw = (null_raw < real_mean_raw).mean() * 100
pct_wins = (null_wins < real_mean_wins).mean() * 100
print(f"\nSELECTION null, {N_DRAWS} draws:")
print(f"  RAW:        null mean={null_raw.mean()*100:.3f}% sd={null_raw.std()*100:.3f}%  "
      f"real value percentile = {pct_raw:.1f}")
print(f"  WINSORIZED: null mean={null_wins.mean()*100:.3f}% sd={null_wins.std()*100:.3f}%  "
      f"real value percentile = {pct_wins:.1f}")
print(f"\nGate condition 2a (SELECTION null, >=95th pctile) -- RAW: {pct_raw>=95}  WINSORIZED: {pct_wins>=95}")

np.save(SCRATCH / "earnings_drift_dev_selection_null_raw.npy", null_raw)
np.save(SCRATCH / "earnings_drift_dev_selection_null_wins.npy", null_wins)
print("\nCheckpoints written.")
