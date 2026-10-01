"""Adds null (b2) -- the UPTREND-RESTRICTED selection null, per instruction
2026-09-29 -- to the existing Step 5 nulls results (scripts/
fibo_step5_nulls.py's output), without re-running the already-completed
(a) TIMING / (b) SELECTION 1000-seed computations.

(b2) reuses selection_null and build_month_pools from fibo_step5_nulls.py
unchanged (require_uptrend=True is the only difference from (b))."""
import sys
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fibo_step5_nulls as base

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "data" / "fibo_step5_dev_results.pkl"
NULLS_PATH = ROOT / "data" / "fibo_step5_nulls.pkl"


def main():
    with open(RESULTS_PATH, "rb") as f:
        d = pickle.load(f)
    trades = d["trades"]
    m = d["m"]
    universe = d["universe"]
    r_distribution = trades["r_rupees"].to_numpy()

    with open(NULLS_PATH, "rb") as f:
        existing = pickle.load(f)

    intraday_con = base.get_intraday_read_connection(base.INTRADAY_DB)

    print("Building uptrend-only month pools for null (b2)...", flush=True)
    month_pools_b2 = base.build_month_pools(m, universe, require_uptrend=True)
    pool_size = sum(len(v) for v in month_pools_b2.values())
    pool_size_b = sum(len(v) for v in base.build_month_pools(m, universe, require_uptrend=False).values())
    print(f"(b2) pool size: {pool_size} candidate (entity, day) pairs "
          f"(vs {pool_size_b} for (b) -- uptrend restricts the pool to {pool_size/pool_size_b*100:.1f}%).", flush=True)

    print(f"\n=== (b2) SELECTION null, UPTREND-RESTRICTED: {base.N_SEEDS} seeds ===", flush=True)
    b2_results = []
    for seed in range(base.N_SEEDS):
        rng = np.random.default_rng(seed)
        b2_results.append(base.selection_null(intraday_con, trades, month_pools_b2, r_distribution, rng))
        if (seed + 1) % 200 == 0:
            print(f"  selection null (b2): {seed + 1}/{base.N_SEEDS} seeds done", flush=True)
    b2_df = pd.DataFrame(b2_results)

    strategy_mean_gross = trades["gross_r"].mean()
    strategy_mean_net_lo = trades["net_r_lo_cost"].mean()
    strategy_mean_net_hi = trades["net_r_hi_cost"].mean()

    def percentile_of(value, dist):
        dist = dist.dropna()
        return (dist < value).mean() * 100 if len(dist) else float("nan")

    print("\n=== Strategy percentile vs null (b2) ===", flush=True)
    print(f"vs (b2) (gross R):    {percentile_of(strategy_mean_gross, b2_df['mean_gross']):.1f}th percentile", flush=True)
    print(f"vs (b2) (net R, lo):  {percentile_of(strategy_mean_net_lo, b2_df['mean_net_lo']):.1f}th percentile", flush=True)
    print(f"vs (b2) (net R, hi):  {percentile_of(strategy_mean_net_hi, b2_df['mean_net_hi']):.1f}th percentile", flush=True)
    print(f"\n(b2) null distribution: mean_gross mean={b2_df['mean_gross'].mean():.4f} "
          f"std={b2_df['mean_gross'].std():.4f}", flush=True)

    existing["selection_b2"] = b2_df
    existing["selection_b2_pool_size"] = pool_size
    existing["selection_pool_size"] = pool_size_b
    with open(NULLS_PATH, "wb") as f:
        pickle.dump(existing, f)
    print(f"\nUpdated {NULLS_PATH} with null (b2) results.", flush=True)


if __name__ == "__main__":
    main()
