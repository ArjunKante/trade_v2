"""The actual answer, not the analytical proxy: long-only top-decile
momentum_12_1, rebalanced every 63 trading days, real tercile-specific
costs, real realized turnover, vs equal-weight buy-and-hold of the same
universe. Pre-holdout only (panel physically ends 2025-03-18).
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
from factors.target import compute_forward_return

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63

# Tercile-specific round-trip costs (bps). MID = prior project's own
# ground-truth measurement (26-39bps, rank 300-600, live order book,
# 2026-09-15). HIGH/LOW are NOT new ground-truth measurements -- they are
# Corwin-Schultz spreads computed directly on this project's own tercile
# samples, combined with the prior project's own calibration finding (CS
# overstates by ~12-31x, mean ~21x, on normally-traded names; is ~accurate
# on T2T/thin names). HIGH: raw CS median 62.7bps / 21 = 3.0bps spread +
# ~20bps statutory/brokerage floor = ~23bps. LOW: raw CS median 97.7bps
# used AS-IS (thin-name regime, where CS was found accurate not
# overstated) + ~20bps floor = ~118bps. Labeled as an estimate, not a
# re-measurement, throughout.
COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5  # used for the equal-weight benchmark (no tercile targeting)

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)
con.close()

print("Computing momentum_12_1, forward returns, liquidity terciles...")
mom = compute_momentum_12_1(panel)
fwd = compute_forward_return(panel)

p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop") if s.notna().sum() >= 3 else pd.Series([np.nan]*len(s), index=s.index)
)
liq = p[["entity_id", "trade_date", "_tercile"]]

m = mom.merge(fwd, on=["entity_id", "trade_date"]).merge(liq, on=["entity_id", "trade_date"])
m = m.dropna(subset=["value", "fwd_return", "_tercile"])

all_dates = sorted(m["trade_date"].unique())
rebalance_dates = all_dates[::REBALANCE_DAYS]
print(f"{len(rebalance_dates)} rebalance dates, {rebalance_dates[0]} to {rebalance_dates[-1]}")

DECILE_FRAC = 0.10


def top_decile_names(date):
    day = m[m["trade_date"] == date]
    if len(day) < 20:
        return set(), day
    cutoff = day["value"].quantile(1 - DECILE_FRAC)
    top = day[day["value"] >= cutoff]
    return set(top["entity_id"]), top


def universe_names(date):
    day = m[m["trade_date"] == date]
    return set(day["entity_id"]), day


momentum_nav = [1.0]
benchmark_nav = [1.0]
momentum_dates = [rebalance_dates[0]]
records = []
prev_mom_set = None
prev_bench_set = None

for d in rebalance_dates:
    mom_set, mom_day = top_decile_names(d)
    bench_set, bench_day = universe_names(d)
    if not mom_set or not bench_set:
        continue

    # --- momentum strategy leg ---
    gross_ret = mom_day["fwd_return"].mean()
    if prev_mom_set is None:
        turnover_frac = 1.0  # initial purchase, one-time buy-only cost
        cost_bps = mom_day.groupby("_tercile", observed=True).apply(lambda g: len(g)).to_dict()
        # weighted avg cost across this period's holdings by tercile composition
        tercile_counts = mom_day["_tercile"].value_counts(normalize=True)
        avg_cost = sum(tercile_counts.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE)
    else:
        entered = mom_set - prev_mom_set
        exited = prev_mom_set - prev_mom_set.intersection(mom_set)
        turnover_frac = len(entered) / max(len(mom_set), 1)
        entered_tercile = mom_day[mom_day["entity_id"].isin(entered)]["_tercile"].value_counts(normalize=True)
        avg_cost = sum(entered_tercile.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE) if len(entered) else 0.0

    period_cost = turnover_frac * (avg_cost / 10000.0)
    net_ret = gross_ret - period_cost
    momentum_nav.append(momentum_nav[-1] * (1 + net_ret))
    prev_mom_set = mom_set

    # --- benchmark: equal-weight, whole universe, same rebalance cadence ---
    bgross = bench_day["fwd_return"].mean()
    if prev_bench_set is None:
        bturnover = 1.0
    else:
        bentered = bench_set - prev_bench_set
        bturnover = len(bentered) / max(len(bench_set), 1)
    bcost = bturnover * (BLENDED_COST_BPS / 10000.0)
    bnet = bgross - bcost
    benchmark_nav.append(benchmark_nav[-1] * (1 + bnet))
    prev_bench_set = bench_set

    records.append({
        "date": d, "mom_n": len(mom_set), "mom_gross": gross_ret, "mom_turnover": turnover_frac,
        "mom_cost_bps_applied": avg_cost * turnover_frac, "mom_net": net_ret,
        "bench_n": len(bench_set), "bench_gross": bgross, "bench_turnover": bturnover, "bench_net": bnet,
    })
    momentum_dates.append(d)

rec_df = pd.DataFrame(records)
nav_df = pd.DataFrame({"date": momentum_dates, "momentum_nav": momentum_nav, "benchmark_nav": benchmark_nav})

n_years = (nav_df["date"].iloc[-1] - nav_df["date"].iloc[0]).days / 365.25
mom_cagr = momentum_nav[-1] ** (1 / n_years) - 1
bench_cagr = benchmark_nav[-1] ** (1 / n_years) - 1

period_rets_mom = np.diff(momentum_nav) / momentum_nav[:-1]
period_rets_bench = np.diff(benchmark_nav) / benchmark_nav[:-1]
periods_per_year = 252 / REBALANCE_DAYS
mom_sharpe = (period_rets_mom.mean() / period_rets_mom.std()) * np.sqrt(periods_per_year)
bench_sharpe = (period_rets_bench.mean() / period_rets_bench.std()) * np.sqrt(periods_per_year)

def max_dd(nav):
    nav = np.array(nav)
    peak = np.maximum.accumulate(nav)
    dd = (nav - peak) / peak
    return dd.min()

print("\n=== BACKTEST: long-only top-decile momentum_12_1 vs equal-weight universe ===")
print(f"Period: {nav_df['date'].iloc[0].date()} to {nav_df['date'].iloc[-1].date()} ({n_years:.1f} years, {len(rec_df)} rebalances)")
print(f"{'':20s} {'CAGR':>10s} {'Sharpe':>10s} {'MaxDD':>10s} {'Final NAV':>12s}")
print(f"{'Momentum (net)':20s} {mom_cagr*100:>9.2f}% {mom_sharpe:>10.2f} {max_dd(momentum_nav)*100:>9.2f}% {momentum_nav[-1]:>12.3f}")
print(f"{'Equal-weight (net)':20s} {bench_cagr*100:>9.2f}% {bench_sharpe:>10.2f} {max_dd(benchmark_nav)*100:>9.2f}% {benchmark_nav[-1]:>12.3f}")

print(f"\nMean turnover per rebalance (momentum): {rec_df['mom_turnover'].mean()*100:.1f}%")
print(f"Mean cost drag per rebalance (momentum): {rec_df['mom_cost_bps_applied'].mean():.1f}bps")
print(f"Total periods: {len(rec_df)}  Rebalance freq: every {REBALANCE_DAYS} trading days")

print("\n=== Year-by-year net returns ===")
rec_df["year"] = pd.to_datetime(rec_df["date"]).dt.year
yearly = rec_df.groupby("year").apply(
    lambda g: pd.Series({
        "mom_net_compounded": (1 + g["mom_net"]).prod() - 1,
        "bench_net_compounded": (1 + g["bench_net"]).prod() - 1,
        "n_periods": len(g),
    })
)
print(yearly.to_string())

print("\n=== 2020 SPECIFICALLY (the tail-risk number) ===")
y2020 = rec_df[rec_df["year"] == 2020]
if len(y2020):
    mom_2020 = (1 + y2020["mom_net"]).prod() - 1
    bench_2020 = (1 + y2020["bench_net"]).prod() - 1
    print(f"momentum strategy net return, 2020 rebalances only: {mom_2020*100:+.2f}%")
    print(f"equal-weight benchmark net return, 2020 rebalances only: {bench_2020*100:+.2f}%")
    print(y2020[["date", "mom_n", "mom_gross", "mom_turnover", "mom_net"]].to_string())

rec_df.to_csv(ROOT / "data" / "backtest_momentum_records.csv", index=False)
nav_df.to_csv(ROOT / "data" / "backtest_momentum_nav.csv", index=False)
print(f"\nSaved records to data/backtest_momentum_records.csv, NAV to data/backtest_momentum_nav.csv")
