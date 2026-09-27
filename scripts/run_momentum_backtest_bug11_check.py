"""BUG #11 MATERIALITY CHECK on the pre-holdout momentum backtest --
identical to scripts/run_momentum_backtest.py in every respect EXCEPT the
78 same-ISIN-jump entities (BUGS.md Bug #11) are excluded from the panel
before anything else runs. `run_momentum_backtest.py` itself is NOT
modified -- this is a separate script, per instruction ("no rewriting of
published results").

WHY THIS CHECK, stated plainly: the momentum holdout pass (Study 1,
14.72% vs 10.85%, +3.87pts) is the only positive result across all three
projects in this repository. Some of the 78 flagged entities are
plausible missed splits (JSWSTEEL, GRASIM, TRENT -- zero corporate_actions
coverage, ratios close to common split factors, per BUGS.md Bug #11). An
uncorrected split creates an artificial price jump; if upward, it
fabricates a strong trailing-12-month return, which could put the name in
momentum's top decile on artifact alone and inflate the measured edge.
The swing project checked this exact contamination and found it
immaterial there (9.0 -> 9.8 percentile) -- but swing selects on a 5-day
DIP, a different exposure to a single-day jump than momentum's top-decile
selection on a 12-MONTH return. Not assumed to generalize; checked here
directly.

Usage:
    python scripts/run_momentum_backtest_bug11_check.py
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
from monitor.persistence import same_isin_jump_excluded_entities

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5
DECILE_FRAC = 0.10

# --- published (original, unexcluded) figures, FINDINGS.md Section 2, for the printed diff ---
ORIGINAL = {
    "mom_cagr": 0.3043, "bench_cagr": 0.1811, "margin_pp": 12.32,
    "mom_sharpe": 1.06, "bench_sharpe": 0.76,
    "mom_mdd": -0.3595, "bench_mdd": -0.4982,
}

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
excluded = same_isin_jump_excluded_entities(con)  # BUGS.md Bug #11
panel_all = read_entity_panel(con)
panel = panel_all[~panel_all["entity_id"].isin(excluded)].reset_index(drop=True)
con.close()
print(f"Excluded {len(excluded)} same-ISIN-jump entities (BUGS.md Bug #11). "
      f"Panel: {len(panel_all)} -> {len(panel)} rows.", file=sys.stderr)

print("Computing momentum_12_1, forward returns, liquidity terciles (78 entities excluded)...")
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
entered_top_decile_by_date = {}  # for the "how many of the 78 entered the top decile" check below

for d in rebalance_dates:
    mom_set, mom_day = top_decile_names(d)
    bench_set, bench_day = universe_names(d)
    if not mom_set or not bench_set:
        continue

    gross_ret = mom_day["fwd_return"].mean()
    if prev_mom_set is None:
        turnover_frac = 1.0
        tercile_counts = mom_day["_tercile"].value_counts(normalize=True)
        avg_cost = sum(tercile_counts.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE)
    else:
        entered = mom_set - prev_mom_set
        turnover_frac = len(entered) / max(len(mom_set), 1)
        entered_tercile = mom_day[mom_day["entity_id"].isin(entered)]["_tercile"].value_counts(normalize=True)
        avg_cost = sum(entered_tercile.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE) if len(entered) else 0.0

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

    records.append({
        "date": d, "mom_n": len(mom_set), "mom_gross": gross_ret, "mom_turnover": turnover_frac,
        "mom_net": net_ret, "bench_n": len(bench_set), "bench_gross": bgross,
        "bench_turnover": bturnover, "bench_net": bnet,
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
    return ((nav - peak) / peak).min()


mom_mdd = max_dd(momentum_nav)
bench_mdd = max_dd(benchmark_nav)
margin_pp = (mom_cagr - bench_cagr) * 100

print("\n" + "=" * 90)
print("BUG #11 MATERIALITY CHECK -- PRE-HOLDOUT BACKTEST, 78 SAME-ISIN-JUMP ENTITIES EXCLUDED")
print("=" * 90)
print(f"Period: {nav_df['date'].iloc[0].date()} to {nav_df['date'].iloc[-1].date()} ({n_years:.1f} years, {len(rec_df)} rebalances)")

print(f"\n{'':22s}{'ORIGINAL':>12s}{'EXCLUDED-78':>14s}{'DIFF':>10s}")
print(f"{'Momentum CAGR':22s}{ORIGINAL['mom_cagr']*100:>11.2f}%{mom_cagr*100:>13.2f}%{(mom_cagr-ORIGINAL['mom_cagr'])*100:>+9.2f}pp")
print(f"{'Benchmark CAGR':22s}{ORIGINAL['bench_cagr']*100:>11.2f}%{bench_cagr*100:>13.2f}%{(bench_cagr-ORIGINAL['bench_cagr'])*100:>+9.2f}pp")
print(f"{'Margin (pts)':22s}{ORIGINAL['margin_pp']:>11.2f} {margin_pp:>13.2f} {margin_pp-ORIGINAL['margin_pp']:>+9.2f}")
print(f"{'Momentum Sharpe':22s}{ORIGINAL['mom_sharpe']:>11.2f} {mom_sharpe:>13.2f} {mom_sharpe-ORIGINAL['mom_sharpe']:>+9.2f}")
print(f"{'Benchmark Sharpe':22s}{ORIGINAL['bench_sharpe']:>11.2f} {bench_sharpe:>13.2f} {bench_sharpe-ORIGINAL['bench_sharpe']:>+9.2f}")
print(f"{'Momentum MaxDD':22s}{ORIGINAL['mom_mdd']*100:>11.2f}%{mom_mdd*100:>13.2f}%{(mom_mdd-ORIGINAL['mom_mdd'])*100:>+9.2f}pp")
print(f"{'Benchmark MaxDD':22s}{ORIGINAL['bench_mdd']*100:>11.2f}%{bench_mdd*100:>13.2f}%{(bench_mdd-ORIGINAL['bench_mdd'])*100:>+9.2f}pp")

# --- how many of the 78 ever entered the top decile, and clustering ---
mom_full = compute_momentum_12_1(panel_all)
excluded_hits = mom_full[mom_full["entity_id"].isin(excluded)].dropna(subset=["value"]).copy()
if len(excluded_hits):
    excluded_hits_rebal = excluded_hits[excluded_hits["trade_date"].isin(rebalance_dates)]
    entered_rows = []
    for d in rebalance_dates:
        day = mom_full[mom_full["trade_date"] == d].dropna(subset=["value"])
        if len(day) < 20:
            continue
        cutoff = day["value"].quantile(1 - DECILE_FRAC)
        in_decile = day[(day["value"] >= cutoff) & (day["entity_id"].isin(excluded))]
        for _, row in in_decile.iterrows():
            entered_rows.append({"date": d, "entity_id": row["entity_id"], "momentum_value": row["value"]})
    entered_df = pd.DataFrame(entered_rows)
else:
    entered_df = pd.DataFrame(columns=["date", "entity_id", "momentum_value"])

print(f"\n--- Of the 78 excluded entities: how many ever entered momentum's top decile at any rebalance ---")
if len(entered_df):
    n_distinct = entered_df["entity_id"].nunique()
    print(f"{n_distinct} of 78 entities entered the top decile at >=1 rebalance ({len(entered_df)} entity-rebalance hits total).")
    print("\nBy year (clustering check):")
    entered_df["year"] = pd.to_datetime(entered_df["date"]).dt.year
    print(entered_df.groupby("year").size().to_string())
    print("\nDistinct entities and their rebalance dates:")
    print(entered_df.groupby("entity_id")["date"].apply(lambda s: [d.date().isoformat() for d in s]).to_string())
else:
    print("0 of 78 entities ever entered the top decile at any rebalance.")

rec_df.to_csv(ROOT / "data" / "backtest_momentum_bug11_check_records.csv", index=False)
entered_df.to_csv(ROOT / "data" / "backtest_momentum_bug11_check_entered_topdecile.csv", index=False)
print(f"\nSaved to data/backtest_momentum_bug11_check_records.csv and "
      f"data/backtest_momentum_bug11_check_entered_topdecile.csv")
