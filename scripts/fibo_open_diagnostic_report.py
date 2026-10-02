"""PHASE 1 DIAGNOSTIC REPORT -- NOT a test. Assembles
scripts/fibo_open_diagnostic_backtest.py and
scripts/fibo_open_diagnostic_nulls.py's saved output into the report
FIBO_OPEN.md's Phase 1 section requires. One read; this script only
reports what the two upstream scripts already computed -- no new data
access, no new trade construction.

STATUS, repeated deliberately on every section below: this strategy's
rules were decided AFTER seeing src/fibo's own sealed-test TIMING-null
result on the SAME historical data reported here, so the data has already
been seen. This report is explicitly DIAGNOSTIC, not a validated result,
and carries NO pass/fail verdict -- its only purpose is to decide whether
a two-year forward test is worth starting (FIBO_OPEN.md).

Universe: top-100 by turnover only (Phase 1's frozen rule). Trades tagged
"101-200" by scripts/fibo_open_diagnostic_backtest.py are EXCLUDED from
every headline number below and reported ONLY as a trade-count cost of
that exclusion, per instruction.
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "data" / "fibo_open_diagnostic_results.pkl"
NULLS_PATH = ROOT / "data" / "fibo_open_diagnostic_nulls.pkl"

TOP100_BANDS = ["1-50", "51-100"]


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


def add_pessimistic_cost(trades: pd.DataFrame) -> pd.DataFrame:
    """1x (band 1-50) / 2x (band 51-100) pessimistic spread/impact
    multiplier -- fibo_test_backtest.py's BAND_MULTIPLIER convention,
    restricted to the two bands this top-100-only universe actually
    contains (band 101-200's 4x never applies -- that band is excluded)."""
    from swing.costs import buy_leg_cost_rs, sell_leg_cost_rs, SPREAD_IMPACT_ROUND_TRIP_BPS_HI
    mult = {"1-50": 1, "51-100": 2}
    trades = trades.copy()

    def cost_rs(r):
        fixed = buy_leg_cost_rs(r["position_size_rs"], "INTRADAY") + sell_leg_cost_rs(r["position_size_rs"], "INTRADAY")
        spread = r["position_size_rs"] * SPREAD_IMPACT_ROUND_TRIP_BPS_HI / 10_000 * mult.get(r["band"], 2)
        return fixed + spread

    trades["cost_pessimistic_rs"] = trades.apply(cost_rs, axis=1)
    trades["net_r_pessimistic"] = trades["gross_r"] - trades["cost_pessimistic_rs"] / (trades["r_rupees"] * trades["qty"])
    return trades


def report_entry_mechanism(label: str, trades_all: pd.DataFrame, nulls: dict | None):
    log(f"\n{'=' * 70}")
    log(f"=== DIAGNOSTIC -- {label}, top-100 universe only ===")
    log(f"{'=' * 70}")
    log("DIAGNOSTIC -- data already seen, not a validated result.")

    n_101_200 = int((trades_all["band"] == "101-200").sum())
    n_unranked = int((trades_all["band"] == "unranked").sum())
    trades = trades_all[trades_all["band"].isin(TOP100_BANDS)].copy()
    n = len(trades)
    log(f"\nTrades (top-100 only): {n}")
    log(f"Trades EXCLUDED by restricting to top-100 (band 101-200): {n_101_200} "
        "-- the trade count this exclusion costs us, per instruction.")
    if n_unranked:
        log(f"Trades with no resolvable band that year (unranked, excluded from this report): {n_unranked}")
    if n == 0:
        log("No top-100 trades -- nothing further to report for this entry mechanism.")
        return

    trades = add_pessimistic_cost(trades)
    win_rate = (trades["gross_r"] > 0).mean() * 100
    log(f"Win rate (gross R > 0): {win_rate:.1f}%")

    log("\n-- Exit-reason breakdown --")
    for reason, cnt in trades["exit_reason"].value_counts().items():
        log(f"  {reason:12s}: {cnt:4d}  ({cnt / n * 100:.1f}%)")

    log("\n-- By year --")
    for yr, grp in trades.groupby("year"):
        log(f"  {yr}: n={len(grp):4d}  win_rate={(grp['gross_r'] > 0).mean() * 100:.1f}%  "
            f"mean_gross={grp['gross_r'].mean():.4f}  mean_net_lo={grp['net_r_lo_cost'].mean():.4f}  "
            f"mean_net_hi={grp['net_r_hi_cost'].mean():.4f}  mean_net_pess={grp['net_r_pessimistic'].mean():.4f}")

    log("\n-- By rank band --")
    for band, grp in trades.groupby("band"):
        log(f"  {band:8s}: n={len(grp):4d}  win_rate={(grp['gross_r'] > 0).mean() * 100:.1f}%  "
            f"mean_gross={grp['gross_r'].mean():.4f}  mean_net_lo={grp['net_r_lo_cost'].mean():.4f}  "
            f"mean_net_hi={grp['net_r_hi_cost'].mean():.4f}  mean_net_pess={grp['net_r_pessimistic'].mean():.4f}")

    scenarios = {
        "(i) flat low": ("net_r_lo_cost", "mean_net_lo"),
        "(ii) flat high": ("net_r_hi_cost", "mean_net_hi"),
        "(iii) pessimistic banded (1x/2x)": ("net_r_pessimistic", "mean_net_pess"),
    }
    log("\n-- Mean net R under all three cost scenarios --")
    for scen_label, (col, dist_col) in scenarios.items():
        x = trades[col].to_numpy()
        mean, se, t = mean_se_t(x)
        line = f"  {scen_label:34s}: mean={mean:+.4f}  SE={se:.4f}  t={t:.3f}"
        if nulls is not None:
            pct_b = percentile_of(mean, nulls["selection_b"][dist_col])
            pct_b2 = percentile_of(mean, nulls["selection_b2"][dist_col])
            line += f"  vs(b)={pct_b:5.1f}th  vs(b2)={pct_b2:5.1f}th"
        log(line)

    if nulls is not None:
        log(f"\n-- Null pool sizes -- (b): {nulls['pool_size_b']}, "
            f"(b2): {nulls['pool_size_b2']} "
            f"({nulls['pool_size_b2'] / nulls['pool_size_b'] * 100:.1f}% of (b))")


def main():
    log("=== PHASE 1 DIAGNOSTIC REPORT -- data already seen, NOT a validated result ===")
    log("Purpose: decide whether a two-year forward test is worth starting. Not evidence the strategy works.\n")

    with open(RESULTS_PATH, "rb") as f:
        d = pickle.load(f)
    nulls = None
    if NULLS_PATH.exists():
        with open(NULLS_PATH, "rb") as f:
            nulls = pickle.load(f)

    log("=== Category breakdown (full range, all downloaded entity-days, BEFORE any universe filter) ===")
    total = sum(d["cat_counts_open"].values())
    log("-- OPEN entry --")
    for cat, cnt in sorted(d["cat_counts_open"].items(), key=lambda x: -x[1]):
        log(f"  {cat:25s}: {cnt:6d}  ({cnt / total * 100:.2f}%)")
    log("-- BREAKOUT entry --")
    for cat, cnt in sorted(d["cat_counts_breakout"].items(), key=lambda x: -x[1]):
        log(f"  {cat:25s}: {cnt:6d}  ({cnt / total * 100:.2f}%)")

    report_entry_mechanism("OPEN entry (this module's new rule)", d["trades_open"], nulls)
    report_entry_mechanism(
        "BREAKOUT entry (frozen src/fibo rule, restricted to top-100 here for comparison)",
        d["trades_breakout"], None,
    )

    log(f"\n{'=' * 70}")
    log("=== REMINDER: this entire report is DIAGNOSTIC. Data already seen, no untouched window remains.")
    log("Not evidence the strategy works. Decide only whether Phase 2 (forward-only logging) is worth starting.")
    log(f"{'=' * 70}")


if __name__ == "__main__":
    main()
