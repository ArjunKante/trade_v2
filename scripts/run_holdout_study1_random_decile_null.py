"""CALIBRATION of the 3.0pp margin threshold (PREREGISTRATION.md Section
"Decision rule"), not a re-test. Nothing about the strategy varies and no
new data is read -- the holdout window is already spent (FINDINGS.md
Section 7, retired). This reuses the WINDOW-LEVEL-corrected pipeline that
produced the recorded 3.50 margin (scripts/run_holdout_study1_lineage_
check.py) and its SAVED exclusion list (loaded, never recomputed, per
BUGS.md Bug #27/#28's resolution and OPERATIONS.md's pinning rule).

At each of the 5 holdout rebalance dates, draw a random subset of
entities of the SAME SIZE as the real top-decile, from the SAME
point-in-time eligible pool (`clean` at that date -- momentum, forward
return, and liquidity tercile all available, identical population the
real selection draws from). Compound through the same 63-day hold, same
turnover-weighted cost model, same benchmark (which does not depend on
decile choice and is therefore identical across every draw and to the
recorded real result). Report the distribution of margins and where
3.50 sits in it.

Simplification, stated not hidden: the real strategy's FIRST holdout
rebalance has a turnover_frac inherited from a REAL pre-holdout decile
(rebalance_dates_all spans the full panel). The null has no "random
pre-holdout decile" to inherit from, so each null trial's first holdout
period pays full entry cost (turnover_frac=1.0), same convention the
real run itself uses whenever prev_mom_set is None. This can only make
a null trial's margin slightly WORSE than a true steady-state random
strategy would be, i.e. it is conservative against the hypothesis that
the threshold is uncalibrated, not biased toward finding uncalibration.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.holdout import SEALED_HOLDOUT_START
from data_layer.entity_panel import read_full_entity_panel_authorized
from data_layer.exclusion_list import load_exclusion_list, entity_ids_from, jump_dates_from
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return, HORIZON_DAYS

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10
COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5
MARGIN_REQUIRED_PP = 3.0
ORIGINAL_HOLDOUT_LAST_DATE = pd.Timestamp("2026-04-22")
N_SEEDS = 5000

record = load_exclusion_list("run_holdout_study1_lineage_check.window_level")
same_isin_excluded = entity_ids_from(record, "same_isin")
jump_dates_40 = jump_dates_from(record, "lineage")
print(f"Loaded exclusion list: {len(same_isin_excluded)} same-ISIN entities, "
      f"{len(jump_dates_40)} lineage-window entities (window-level correction).")

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel_all = read_full_entity_panel_authorized(con, authorize_holdout=True)
con.close()
panel = panel_all[~panel_all["entity_id"].isin(same_isin_excluded)].reset_index(drop=True)

mom = compute_momentum_12_1(panel, unexplained_jump_dates=jump_dates_40)
fwd_clean = compute_forward_return(panel, unexplained_jump_dates=jump_dates_40)

p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
    if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index))

full = mom.merge(p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]).dropna(subset=["value", "_tercile"])
clean = mom.merge(fwd_clean, on=["entity_id", "trade_date"]).merge(
    p[["entity_id", "trade_date", "_tercile"]], on=["entity_id", "trade_date"]
).dropna(subset=["value", "fwd_return", "_tercile"])

all_dates = sorted(full["trade_date"].unique())
rebalance_dates_all = all_dates[::REBALANCE_DAYS]
rebalance_dates_all = [d for d in rebalance_dates_all if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]
holdout_start_ts = pd.Timestamp(SEALED_HOLDOUT_START)
holdout_rebalance_dates = [d for d in rebalance_dates_all
                           if holdout_start_ts <= d <= ORIGINAL_HOLDOUT_LAST_DATE]
print(f"Holdout rebalance dates ({len(holdout_rebalance_dates)}): "
      f"{[d.date().isoformat() for d in holdout_rebalance_dates]}")


def cost_bps_for(tercile_counts_normalized):
    return sum(tercile_counts_normalized.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE)


# ---------------------------------------------------------------------
# REAL top-decile run over the FULL rebalance history (matching
# run_holdout_study1_lineage_check.py's run_variant exactly, including
# the real turnover carried INTO the first holdout rebalance from the
# real pre-holdout decile) -- this is the checkpoint, and also how
# pools/real_mom_set_by_date are captured for the null below.
# ---------------------------------------------------------------------
pools = {}
real_mom_set_by_date = {}
prev_mom_set, prev_bench_set = None, None
mom_nav, bench_nav = [1.0], [1.0]
records = []
for d in rebalance_dates_all:
    day_full = full[full["trade_date"] == d]
    if len(day_full) < 20:
        continue
    pool = clean[clean["trade_date"] == d]
    if pool.empty:
        continue
    cutoff = pool["value"].quantile(1 - DECILE_FRAC)
    mom_sel = pool[pool["value"] >= cutoff]
    mom_set = set(mom_sel["entity_id"])
    bench_set = set(pool["entity_id"])
    if not mom_set or not bench_set:
        continue
    if holdout_start_ts <= d <= ORIGINAL_HOLDOUT_LAST_DATE:
        pools[d] = pool
        real_mom_set_by_date[d] = mom_set

    gross = mom_sel["fwd_return"].mean()
    entered = mom_set if prev_mom_set is None else (mom_set - prev_mom_set)
    turnover = 1.0 if prev_mom_set is None else len(entered) / max(len(mom_set), 1)
    if entered:
        tc = mom_sel[mom_sel["entity_id"].isin(entered)]["_tercile"].value_counts(normalize=True)
        cost = turnover * (cost_bps_for(tc) / 10000.0)
    else:
        cost = 0.0
    net_ret = gross - cost
    mom_nav.append(mom_nav[-1] * (1 + net_ret))
    prev_mom_set = mom_set

    bgross = pool["fwd_return"].mean()
    bturnover = 1.0 if prev_bench_set is None else len(bench_set - prev_bench_set) / max(len(bench_set), 1)
    bcost = bturnover * (BLENDED_COST_BPS / 10000.0)
    bnet = bgross - bcost
    bench_nav.append(bench_nav[-1] * (1 + bnet))
    prev_bench_set = bench_set

    records.append({"date": d, "in_holdout": holdout_start_ts <= d <= ORIGINAL_HOLDOUT_LAST_DATE,
                     "mom_net": net_ret, "bench_net": bnet})

rec_df = pd.DataFrame(records)
holdout_rec = rec_df[rec_df["in_holdout"]].reset_index(drop=True)
hm_nav, hb_nav = [1.0], [1.0]
for _, row in holdout_rec.iterrows():
    hm_nav.append(hm_nav[-1] * (1 + row["mom_net"]))
    hb_nav.append(hb_nav[-1] * (1 + row["bench_net"]))

n_years = (holdout_rec["date"].iloc[-1] - holdout_rec["date"].iloc[0]).days / 365.25
real_mom_cagr = hm_nav[-1] ** (1 / n_years) - 1
real_bench_cagr = hb_nav[-1] ** (1 / n_years) - 1
real_margin_pp = (real_mom_cagr - real_bench_cagr) * 100
print(f"\nCHECKPOINT -- real top-decile margin, this script's own computation: "
      f"{real_margin_pp:+.2f}pts (expect 3.50, same window-level-corrected pipeline, "
      f"full rebalance history so the real first-holdout-period turnover carries in correctly)")

# ---------------------------------------------------------------------
# Random-decile null, same benchmark (decile-independent, computed once)
# ---------------------------------------------------------------------
rng_master = np.random.default_rng(0)
null_margins = np.empty(N_SEEDS)
for s in range(N_SEEDS):
    rng = np.random.default_rng(s)
    prev_set = None
    nav = [1.0]
    for d in holdout_rebalance_dates:
        pool = pools[d]
        n = len(real_mom_set_by_date[d])
        idx = rng.choice(len(pool), size=min(n, len(pool)), replace=False)
        draw = pool.iloc[idx]
        draw_set = set(draw["entity_id"])

        gross = draw["fwd_return"].mean()
        turnover = 1.0 if prev_set is None else len(draw_set - prev_set) / max(len(draw_set), 1)
        if turnover > 0:
            entered = draw[draw["entity_id"].isin(draw_set if prev_set is None else (draw_set - prev_set))]
            tc = entered["_tercile"].value_counts(normalize=True)
            cost = turnover * (cost_bps_for(tc) / 10000.0)
        else:
            cost = 0.0
        nav.append(nav[-1] * (1 + gross - cost))
        prev_set = draw_set

    seed_cagr = nav[-1] ** (1 / n_years) - 1
    null_margins[s] = (seed_cagr - real_bench_cagr) * 100

pctile = float((null_margins < real_margin_pp).mean() * 100)
print(f"\n{N_SEEDS}-draw random-decile null, holdout window, benchmark held fixed at "
      f"{real_bench_cagr*100:.2f}% CAGR:")
print(f"  null margin mean={null_margins.mean():+.2f}pts  sd={null_margins.std():.2f}pts  "
      f"min={null_margins.min():+.2f}  max={null_margins.max():+.2f}")
print(f"  fraction of null draws clearing the 3.0pp threshold: {(null_margins >= MARGIN_REQUIRED_PP).mean()*100:.1f}%")
print(f"\nReal margin ({real_margin_pp:+.2f}pts) sits at the {pctile:.1f}th percentile of the random-decile null.")
print(f"Calibration verdict: {'THRESHOLD CALIBRATED (>=95th pctile)' if pctile >= 95 else 'THRESHOLD UNCALIBRATED (<95th pctile)'}")

np.save(Path(r"C:\Users\ARJUNK~1\AppData\Local\Temp\claude\C--projects-trade-new\cee5e6e2-73d6-4e3c-af4a-e518efcfde77\scratchpad") / "study1_random_decile_null_margins.npy", null_margins)
