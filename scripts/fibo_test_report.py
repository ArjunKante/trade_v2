"""THE SEALED TEST report. Assembles scripts/fibo_test_backtest.py and
scripts/fibo_test_nulls.py's saved output into the PREREGISTRATION_FIBO.md
Section 5b TEST PASS table (4 criteria x 3 cost scenarios), plus the
descriptive breakdowns Section 5b also requires (by rank band, exit-reason,
by year, TIMING null). One read; this script only reports what the two
upstream scripts already computed -- no new data access.
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "data" / "fibo_test_results.pkl"
NULLS_PATH = ROOT / "data" / "fibo_test_nulls.pkl"

MIN_TRADES = 100
MIN_T = 2.0
MIN_PERCENTILE = 95.0


def log(msg):
    print(msg, flush=True)


def mean_se_t(x: np.ndarray) -> tuple[float, float, float]:
    n = len(x)
    mean = x.mean()
    se = x.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    t = mean / se if se and not np.isnan(se) and se != 0 else float("nan")
    return mean, se, t


def percentile_of(value, dist):
    dist = dist.dropna()
    return (dist < value).mean() * 100 if len(dist) else float("nan")


def main():
    with open(RESULTS_PATH, "rb") as f:
        d = pickle.load(f)
    trades = d["trades"]
    with open(NULLS_PATH, "rb") as f:
        nulls = pickle.load(f)

    n = len(trades)
    log(f"=== SEALED TEST RESULT: {n} trades, 2023-01-01 to 2026-09-18, top-200 universe ===\n")

    log("=== Exit-reason breakdown ===")
    for reason, cnt in trades["exit_reason"].value_counts().items():
        log(f"  {reason:12s}: {cnt:4d}  ({cnt/n*100:.1f}%)")

    log("\n=== By rank band ===")
    for band, grp in trades.groupby("band"):
        log(f"  {band:10s}: n={len(grp):4d}  win_rate={(grp['gross_r']>0).mean()*100:.1f}%  "
            f"mean_gross={grp['gross_r'].mean():.4f}  mean_net_lo={grp['net_r_lo_cost'].mean():.4f}  "
            f"mean_net_hi={grp['net_r_hi_cost'].mean():.4f}  mean_net_pess={grp['net_r_pessimistic'].mean():.4f}")

    log("\n=== By year ===")
    for yr, grp in trades.groupby("year"):
        log(f"  {yr}: n={len(grp):4d}  win_rate={(grp['gross_r']>0).mean()*100:.1f}%  "
            f"mean_gross={grp['gross_r'].mean():.4f}  mean_net_lo={grp['net_r_lo_cost'].mean():.4f}")

    log("\n=== TIMING null (descriptive, not a TEST PASS criterion) ===")
    timing = nulls["timing"]
    for col, label in [("gross_r", "gross"), ("net_r_lo_cost", "net lo"), ("net_r_hi_cost", "net hi"),
                        ("net_r_pessimistic", "net pessimistic")]:
        dist_col = {"gross_r": "mean_gross", "net_r_lo_cost": "mean_net_lo",
                    "net_r_hi_cost": "mean_net_hi", "net_r_pessimistic": "mean_net_pess"}[col]
        pct = percentile_of(trades[col].mean(), timing[dist_col])
        log(f"  vs TIMING null ({label}): {pct:.1f}th percentile")

    scenarios = {
        "(i) flat low": ("net_r_lo_cost", "mean_net_lo"),
        "(ii) flat high": ("net_r_hi_cost", "mean_net_hi"),
        "(iii) pessimistic banded": ("net_r_pessimistic", "mean_net_pess"),
    }

    log("\n=== TEST PASS TABLE (Section 5b: all 4 criteria, all 3 scenarios) ===")
    overall_pass = True
    trade_count_ok = n >= MIN_TRADES
    log(f"Criterion 1 -- trades >= {MIN_TRADES}: {n} -- {'PASS' if trade_count_ok else 'NOT EVALUATED (too few trades)'}")
    if not trade_count_ok:
        log("\n*** NOT EVALUATED: fewer than 100 trades. Per Section 5a, this is a third outcome, not a fail. ***")
        return

    for label, (col, dist_col) in scenarios.items():
        x = trades[col].to_numpy()
        mean, se, t = mean_se_t(x)
        pct_b = percentile_of(mean, nulls["selection_b"][dist_col])
        pct_b2 = percentile_of(mean, nulls["selection_b2"][dist_col])
        c2 = mean > 0 and t >= MIN_T
        c3 = pct_b >= MIN_PERCENTILE
        c4 = pct_b2 >= MIN_PERCENTILE
        scenario_pass = c2 and c3 and c4
        overall_pass = overall_pass and scenario_pass
        log(f"\n{label}:")
        log(f"  mean net R = {mean:.4f}, SE = {se:.4f}, t = {t:.3f}  -- "
            f"{'PASS' if mean > 0 and t >= MIN_T else 'FAIL'} (criterion 2: >0 and t>=2)")
        log(f"  vs null (b):  {pct_b:.1f}th percentile -- {'PASS' if c3 else 'FAIL'} (criterion 3: >=95th)")
        log(f"  vs null (b2): {pct_b2:.1f}th percentile -- {'PASS' if c4 else 'FAIL'} (criterion 4: >=95th)")
        log(f"  SCENARIO VERDICT: {'PASS' if scenario_pass else 'FAIL'}")

    log(f"\n=== FINAL VERDICT: {'TEST PASS' if overall_pass else 'NO EDGE for these rules'} ===")
    log("(Per Section 5b: all four criteria must hold under all three scenarios for a pass. "
        "No tuning, no second pass -- this is the one read.)")


if __name__ == "__main__":
    main()
