"""Quantify whether the eligibility filter (valid, non-gap-contaminated
forward return) removes entities symmetrically from the momentum strategy
and the benchmark, or disproportionately from one side. Rerun the backtest
with excluded entities assigned -100% (delisted-to-zero) as the pessimistic
bound. Report both, plus the requested year-by-year and per-period detail.
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
from factors.target import compute_forward_return, HORIZON_DAYS

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)
con.close()

mom = compute_momentum_12_1(panel)
fwd_clean = compute_forward_return(panel)  # gap-fixed (NaN'd where contaminated)

# RAW forward return, no gap-fix, so we can see what actually happened to excluded entities
p = panel.sort_values(["entity_id", "trade_date"]).copy()
grp = p.groupby("entity_id", group_keys=False)
p["future_close_raw"] = grp["adjusted_close"].shift(-HORIZON_DAYS)
p["raw_fwd_return"] = p["future_close_raw"] / p["adjusted_close"] - 1
p["has_any_future_row"] = p.groupby("entity_id")["trade_date"].transform(lambda s: s.index.isin(s.index)) # placeholder, replaced below

# does this entity have ANY row after this trade_date at all (regardless of 63-row alignment)?
p["_rownum_in_entity"] = p.groupby("entity_id").cumcount()
entity_max_rownum = p.groupby("entity_id")["_rownum_in_entity"].transform("max")
p["has_any_future_row"] = p["_rownum_in_entity"] < entity_max_rownum

# liquidity tercile
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop") if s.notna().sum() >= 3 else pd.Series([np.nan]*len(s), index=s.index)
)

full = mom.merge(p[["entity_id", "trade_date", "raw_fwd_return", "has_any_future_row", "_tercile", "adjusted_close"]],
                  on=["entity_id", "trade_date"])
full = full.dropna(subset=["value", "_tercile"])  # eligible-by-factor universe (momentum + liquidity known)

clean = mom.merge(fwd_clean, on=["entity_id", "trade_date"]).merge(
    p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]
).dropna(subset=["value", "fwd_return", "_tercile"])

all_dates = sorted(full["trade_date"].unique())
rebalance_dates = all_dates[::REBALANCE_DAYS]
# Drop any rebalance date whose 63-trading-day forward window would need data
# beyond the panel's own end (2025-03-18, the sealed-holdout boundary) -- that
# is not a survivorship finding, it's this backtest asking for data that was
# never materialized. Confirmed the cause directly: the final rebalance date
# showed 100% "exclusion" because literally no entity has a legitimate
# forward return that far out, not because of any real business outcome.
panel_max_date = panel["trade_date"].max()
last_safe_idx = None
for i, d in enumerate(all_dates):
    idx = all_dates.index(d)
    if idx + HORIZON_DAYS < len(all_dates):
        last_safe_idx = i
rebalance_dates = [d for d in rebalance_dates if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]
print(f"Dropped incomplete trailing rebalance dates; {len(rebalance_dates)} remain, "
      f"{rebalance_dates[0]} to {rebalance_dates[-1]} (panel ends {panel_max_date.date()})")

DECILE_FRAC = 0.10

print("=" * 78)
print("PART 1: exclusion audit per rebalance")
print("=" * 78)
audit_rows = []
for d in rebalance_dates:
    day_full = full[full["trade_date"] == d]
    if len(day_full) < 20:
        continue
    day_full = day_full.copy()
    day_full["_decile"] = pd.qcut(day_full["value"].rank(method="first"), 10, labels=False, duplicates="drop")

    clean_ids = set(clean[clean["trade_date"] == d]["entity_id"])
    day_full["excluded"] = ~day_full["entity_id"].isin(clean_ids)

    n_total = len(day_full)
    n_excluded = day_full["excluded"].sum()
    excl_deciles = day_full[day_full["excluded"]]["_decile"]
    audit_rows.append({
        "date": d, "n_total": n_total, "n_excluded": n_excluded,
        "pct_excluded": n_excluded / n_total * 100,
        "excl_mean_decile": excl_deciles.mean() if len(excl_deciles) else np.nan,
        "excl_pct_in_bottom3_deciles": (excl_deciles <= 2).mean() * 100 if len(excl_deciles) else np.nan,
        "excl_pct_in_top3_deciles": (excl_deciles >= 7).mean() * 100 if len(excl_deciles) else np.nan,
    })

audit_df = pd.DataFrame(audit_rows)
print(audit_df.to_string(index=False))
print()
print(f"Mean % of universe excluded per rebalance: {audit_df['pct_excluded'].mean():.1f}%")
print(f"Mean decile of excluded entities (0=lowest momentum, 9=highest): {audit_df['excl_mean_decile'].mean():.2f}  (uniform random would be 4.5)")
print(f"Mean %% of excluded entities in bottom-3 deciles: {audit_df['excl_pct_in_bottom3_deciles'].mean():.1f}%  (uniform would be ~30%)")
print(f"Mean %% of excluded entities in top-3 deciles: {audit_df['excl_pct_in_top3_deciles'].mean():.1f}%  (uniform would be ~30%)")

print()
print("=" * 78)
print("PART 2: resumed vs never-resumed among excluded entities")
print("=" * 78)
all_excluded = []
for d in rebalance_dates:
    day_full = full[full["trade_date"] == d]
    if len(day_full) < 20:
        continue
    clean_ids = set(clean[clean["trade_date"] == d]["entity_id"])
    excl = day_full[~day_full["entity_id"].isin(clean_ids)].copy()
    excl["rebalance_date"] = d
    all_excluded.append(excl)
all_excluded_df = pd.concat(all_excluded, ignore_index=True)

resumed = all_excluded_df["has_any_future_row"]
print(f"Total excluded (entity, rebalance-date) observations: {len(all_excluded_df)}")
print(f"  Resumed trading at some point after exclusion: {resumed.sum()} ({resumed.mean()*100:.1f}%)")
print(f"  Never traded again through panel end (2025-03-18): {(~resumed).sum()} ({(~resumed).mean()*100:.1f}%)")
print()
resumed_returns = all_excluded_df.loc[resumed, "raw_fwd_return"].dropna()
print(f"Of those that resumed, raw return across the halt (available for {len(resumed_returns)}):")
print(resumed_returns.describe(percentiles=[.1, .25, .5, .75, .9]))
print(f"  median: {resumed_returns.median()*100:+.1f}%   mean: {resumed_returns.mean()*100:+.1f}%")
print(f"  fraction with a POSITIVE return across the halt (recovery): {(resumed_returns > 0).mean()*100:.1f}%")
print(f"  fraction with return < -50% (effectively a loss even if not fully delisted): {(resumed_returns < -0.5).mean()*100:.1f}%")


print()
print("=" * 78)
print("PART 3: backtest rerun -- excluded entities assigned -100% (pessimistic bound)")
print("=" * 78)


def run_backtest(selection_source_full: bool):
    """selection_source_full=True: select decile & compute returns from the
    FULL eligible-by-factor universe, with excluded entities' return forced
    to -100% (pessimistic bound). False: original clean-only version."""
    momentum_nav = [1.0]
    benchmark_nav = [1.0]
    dates_out = [rebalance_dates[0]]
    prev_mom_set = None
    prev_bench_set = None
    records = []

    for d in rebalance_dates:
        day_full = full[full["trade_date"] == d].copy()
        if len(day_full) < 20:
            continue
        clean_ids = set(clean[clean["trade_date"] == d]["entity_id"])

        if selection_source_full:
            day_full["realized_return"] = np.where(
                day_full["entity_id"].isin(clean_ids),
                day_full.merge(clean[clean["trade_date"] == d][["entity_id", "fwd_return"]], on="entity_id", how="left")["fwd_return"],
                -1.0,  # pessimistic bound
            )
            pool = day_full
        else:
            pool = clean[clean["trade_date"] == d].rename(columns={"fwd_return": "realized_return"})
            if pool.empty:
                continue

        cutoff = pool["value"].quantile(1 - DECILE_FRAC)
        mom_sel = pool[pool["value"] >= cutoff]
        mom_set = set(mom_sel["entity_id"])
        bench_set = set(pool["entity_id"])
        if not mom_set or not bench_set:
            continue

        gross_ret = mom_sel["realized_return"].mean()
        if prev_mom_set is None:
            turnover_frac = 1.0
            tercile_counts = mom_sel["_tercile"].value_counts(normalize=True)
            avg_cost = sum(tercile_counts.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE)
        else:
            entered = mom_set - prev_mom_set
            turnover_frac = len(entered) / max(len(mom_set), 1)
            entered_tercile = mom_sel[mom_sel["entity_id"].isin(entered)]["_tercile"].value_counts(normalize=True)
            avg_cost = sum(entered_tercile.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE) if len(entered) else 0.0
        period_cost = turnover_frac * (avg_cost / 10000.0)
        net_ret = gross_ret - period_cost
        momentum_nav.append(momentum_nav[-1] * (1 + net_ret))
        prev_mom_set = mom_set

        bgross = pool["realized_return"].mean()
        if prev_bench_set is None:
            bturnover = 1.0
        else:
            bentered = bench_set - prev_bench_set
            bturnover = len(bentered) / max(len(bench_set), 1)
        bcost = bturnover * (BLENDED_COST_BPS / 10000.0)
        bnet = bgross - bcost
        benchmark_nav.append(benchmark_nav[-1] * (1 + bnet))
        prev_bench_set = bench_set

        records.append({"date": d, "mom_gross": gross_ret, "mom_turnover": turnover_frac, "mom_cost_bps_applied": avg_cost * turnover_frac,
                         "mom_net": net_ret, "bench_gross": bgross, "bench_turnover": bturnover, "bench_net": bnet,
                         "mom_n": len(mom_set), "bench_n": len(bench_set)})
        dates_out.append(d)

    return momentum_nav, benchmark_nav, dates_out, pd.DataFrame(records)


def summarize(momentum_nav, benchmark_nav, dates_out, label):
    n_years = (dates_out[-1] - dates_out[0]).days / 365.25
    mom_cagr = momentum_nav[-1] ** (1/n_years) - 1
    bench_cagr = benchmark_nav[-1] ** (1/n_years) - 1
    pr_m = np.diff(momentum_nav)/np.array(momentum_nav[:-1])
    pr_b = np.diff(benchmark_nav)/np.array(benchmark_nav[:-1])
    ppy = 252/REBALANCE_DAYS
    sh_m = pr_m.mean()/pr_m.std()*np.sqrt(ppy)
    sh_b = pr_b.mean()/pr_b.std()*np.sqrt(ppy)
    def mdd(nav):
        nav=np.array(nav); peak=np.maximum.accumulate(nav); return ((nav-peak)/peak).min()
    print(f"--- {label} ---")
    print(f"{'':22s}{'CAGR':>10s}{'Sharpe':>10s}{'MaxDD':>10s}{'FinalNAV':>12s}")
    print(f"{'Momentum (net)':22s}{mom_cagr*100:>9.2f}%{sh_m:>10.2f}{mdd(momentum_nav)*100:>9.2f}%{momentum_nav[-1]:>12.3f}")
    print(f"{'Equal-weight (net)':22s}{bench_cagr*100:>9.2f}%{sh_b:>10.2f}{mdd(benchmark_nav)*100:>9.2f}%{benchmark_nav[-1]:>12.3f}")
    print(f"gap (mom-bench CAGR): {(mom_cagr-bench_cagr)*100:+.2f} points")
    return mom_cagr, bench_cagr


nav_m1, nav_b1, dates1, rec1 = run_backtest(selection_source_full=False)
mc1, bc1 = summarize(nav_m1, nav_b1, dates1, "ORIGINAL (excluded entities dropped)")
print()
nav_m2, nav_b2, dates2, rec2 = run_backtest(selection_source_full=True)
mc2, bc2 = summarize(nav_m2, nav_b2, dates2, "PESSIMISTIC BOUND (excluded entities = -100%)")

print()
print("=" * 78)
print("PART 4: year-by-year, both versions")
print("=" * 78)
for label, rec in [("ORIGINAL", rec1), ("PESSIMISTIC", rec2)]:
    rec = rec.copy()
    rec["year"] = pd.to_datetime(rec["date"]).dt.year
    yearly = rec.groupby("year").apply(lambda g: pd.Series({
        "mom_net": (1+g["mom_net"]).prod()-1, "bench_net": (1+g["bench_net"]).prod()-1, "n": len(g)
    }))
    print(f"--- {label} ---")
    print(yearly.to_string())
    print()

print("=" * 78)
print("PART 5: all 31 individual period returns (ORIGINAL version, net)")
print("=" * 78)
print(rec1[["date", "mom_net", "bench_net", "mom_turnover"]].to_string(index=False))

print()
print("=" * 78)
print("PART 6: turnover/cost sanity check")
print("=" * 78)
print(f"Mean per-rebalance turnover: {rec1['mom_turnover'].mean()*100:.1f}%")
print(f"Rebalances/year: {252/REBALANCE_DAYS:.1f}")
print(f"Implied annualized turnover: {rec1['mom_turnover'].mean()*252/REBALANCE_DAYS*100:.0f}%")
print(f"Sum of all per-period cost drags over {len(rec1)} periods: {rec1['mom_cost_bps_applied'].sum():.0f}bps total ({rec1['mom_cost_bps_applied'].sum()/ (len(rec1)/ (252/REBALANCE_DAYS)):.0f}bps/year average)")
print("(cost per period = turnover_frac x tercile-weighted cost, summed across periods -- NOT a flat one-round-trip-per-period assumption)")

rec1.to_csv(ROOT/"data"/"backtest_original_records_v2.csv", index=False)
rec2.to_csv(ROOT/"data"/"backtest_pessimistic_records.csv", index=False)
