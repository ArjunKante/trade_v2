"""Diagnostic (no study slot spent): how sensitive is the pre-holdout
backtest's net CAGR margin to the low-liquidity tercile's cost assumption?

Reruns run_momentum_backtest.py's exact strategy/benchmark logic across a
range of low_liq round-trip cost assumptions, holding everything else fixed
(high_liq=23bps, mid_liq=32.5bps, both ground-truth-anchored and not in
question here). 118bps is the current uncalibrated-Corwin-Schultz estimate;
40bps and 25bps bracket what a calibrated (T2T-style ~21x correction, like
the high-liq tercile gets) estimate would look like if run_lowliq_cost_
calibration_diagnostic.py's finding -- that this tercile is 0% actual T2T --
means the calibration SHOULD have been applied here too, not skipped.
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
BLENDED_COST_BPS = 32.5

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)
con.close()

mom = compute_momentum_12_1(panel)
fwd = compute_forward_return(panel)

p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
    if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index)
)
liq = p[["entity_id", "trade_date", "_tercile"]]

m = mom.merge(fwd, on=["entity_id", "trade_date"]).merge(liq, on=["entity_id", "trade_date"])
m = m.dropna(subset=["value", "fwd_return", "_tercile"])

all_dates = sorted(m["trade_date"].unique())
rebalance_dates = all_dates[::REBALANCE_DAYS]
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


def max_dd(nav):
    nav = np.array(nav)
    peak = np.maximum.accumulate(nav)
    dd = (nav - peak) / peak
    return dd.min()


def run_backtest(low_liq_cost_bps: float) -> dict:
    cost_by_tercile = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": low_liq_cost_bps}
    momentum_nav = [1.0]
    benchmark_nav = [1.0]
    momentum_dates = [rebalance_dates[0]]
    prev_mom_set = None
    prev_bench_set = None

    for d in rebalance_dates:
        mom_set, mom_day = top_decile_names(d)
        bench_set, bench_day = universe_names(d)
        if not mom_set or not bench_set:
            continue

        gross_ret = mom_day["fwd_return"].mean()
        if prev_mom_set is None:
            turnover_frac = 1.0
            tercile_counts = mom_day["_tercile"].value_counts(normalize=True)
            avg_cost = sum(tercile_counts.get(t, 0) * cost_by_tercile[t] for t in cost_by_tercile)
        else:
            entered = mom_set - prev_mom_set
            turnover_frac = len(entered) / max(len(mom_set), 1)
            entered_tercile = mom_day[mom_day["entity_id"].isin(entered)]["_tercile"].value_counts(normalize=True)
            avg_cost = sum(entered_tercile.get(t, 0) * cost_by_tercile[t] for t in cost_by_tercile) if len(entered) else 0.0

        period_cost = turnover_frac * (avg_cost / 10000.0)
        net_ret = gross_ret - period_cost
        momentum_nav.append(momentum_nav[-1] * (1 + net_ret))
        prev_mom_set = mom_set

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
        momentum_dates.append(d)

    n_years = (momentum_dates[-1] - momentum_dates[0]).days / 365.25
    mom_cagr = momentum_nav[-1] ** (1 / n_years) - 1
    bench_cagr = benchmark_nav[-1] ** (1 / n_years) - 1
    return {
        "low_liq_cost_bps": low_liq_cost_bps,
        "mom_cagr": mom_cagr * 100,
        "bench_cagr": bench_cagr * 100,
        "margin_pts": (mom_cagr - bench_cagr) * 100,
        "mom_maxdd": max_dd(momentum_nav) * 100,
    }


print("=== Sensitivity: momentum net CAGR / margin vs low-liquidity tercile cost assumption ===")
print("(high_liq=23bps and mid_liq=32.5bps held fixed throughout -- both ground-truth-anchored, not in question)\n")

scenarios = [118.0, 90.0, 60.0, 40.0, 25.0]
results = [run_backtest(c) for c in scenarios]
res_df = pd.DataFrame(results)
res_df["label"] = ["118 (current, uncalibrated CS)", "90", "60",
                    "40 (user hypothesis)", "25 (if calibrated like high_liq, ~21x correction)"]
print(res_df[["label", "mom_cagr", "bench_cagr", "margin_pts", "mom_maxdd"]].to_string(
    index=False, formatters={c: "{:.2f}".format for c in ["mom_cagr", "bench_cagr", "margin_pts", "mom_maxdd"]}
))

baseline = res_df[res_df["low_liq_cost_bps"] == 118.0].iloc[0]
at_40 = res_df[res_df["low_liq_cost_bps"] == 40.0].iloc[0]
print(f"\n118bps -> 40bps: momentum net CAGR {baseline['mom_cagr']:.2f}% -> {at_40['mom_cagr']:.2f}% "
      f"({at_40['mom_cagr']-baseline['mom_cagr']:+.2f} pts), "
      f"margin over benchmark {baseline['margin_pts']:.2f} -> {at_40['margin_pts']:.2f} pts.")
