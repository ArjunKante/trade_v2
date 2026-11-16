"""Correction to scripts/earnings_drift_phase0.py's Section 5 MDE.

THE ERROR (identified by the user, not discovered by rerunning anything):
the original script computed the cross-sectional SD of the 60-day forward
RETURN LEVEL and fed that into a two-sample MDE formula. The study tests a
DIFFERENCE -- top decile minus the rest, within the same quarter. The
market-wide shock that inflates quarter-clustered variance on a LEVEL
mostly cancels in a WITHIN-QUARTER DIFFERENCE, because both legs of the
spread sit in the same quarter and share that shock. PROJECT_CONTEXT.md's
own standing finding #3 ("Variance of the difference, not effect size, is
the binding constraint") says exactly this, and flags it as the thing to
check BEFORE trusting an MDE -- it was checkable against that finding
without seeing this script's output at all.

THE CORRECTION: compute the NULL spread variance directly -- assign decile
membership AT RANDOM (never by the real announcement return, so this
reveals nothing about actual drift), take the quarterly top-decile-minus-
rest mean-return spread for each of the 38 quarters, and use the
cross-quarter standard deviation of THAT spread as sigma_period in this
project's own existing one-sample MDE machinery
(src/portfolio/power.py::minimum_detectable_difference, n=38=quarters,
df=37), repeated over many random assignments for stability, raw and
winsorized.
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from portfolio.power import minimum_detectable_difference

SEAL_DATE = "2025-07-01"
HORIZON = 60
N_SEEDS = 200
DECILE_FRAC = 0.10
WINSOR_LO, WINSOR_HI = 0.01, 0.99

con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)

filings = con.execute(f"""
    SELECT isin, known_date FROM fundamentals_filings
    WHERE known_date < DATE '{SEAL_DATE}'
""").fetchdf()
lineage = con.execute("SELECT DISTINCT isin, entity_id FROM isin_lineage").fetchdf()
filings = filings.merge(lineage, on="isin", how="left")
matched = filings[filings["entity_id"].notna()].copy()

prices = con.execute("SELECT entity_id, trade_date FROM entity_prices_daily ORDER BY entity_id, trade_date").fetchdf()
prices_by_entity = {eid: grp["trade_date"].sort_values().to_numpy() for eid, grp in prices.groupby("entity_id")}

def classify(row):
    eid = row["entity_id"]; kd = np.datetime64(row["known_date"])
    dates = prices_by_entity.get(eid)
    if dates is None or len(dates) == 0:
        return "x"
    idx = np.searchsorted(dates, kd, side="left")
    if idx >= len(dates):
        return "x"
    t0 = dates[idx]
    if (t0 - kd) / np.timedelta64(1, "D") > 10:
        return "x"
    if idx == 0:
        return "x"
    pre = dates[idx - 1]
    if (t0 - pre) / np.timedelta64(1, "D") > 10:
        return "x"
    if len(dates) - idx - 1 < HORIZON:
        return "x"
    return "survives"

matched["reason"] = matched.apply(classify, axis=1)
survivors = matched[matched["reason"] == "survives"].copy()

px = con.execute("SELECT entity_id, trade_date, adjusted_close FROM entity_prices_daily").fetchdf()
px = px.set_index(["entity_id", "trade_date"])["adjusted_close"]

def fwd_ret(row):
    eid = row["entity_id"]; kd = np.datetime64(row["known_date"])
    dates = prices_by_entity[eid]
    idx = np.searchsorted(dates, kd, side="left")
    t0, tf = dates[idx], dates[idx + HORIZON]
    try:
        p0 = px.loc[(eid, pd.Timestamp(t0))]
        p1 = px.loc[(eid, pd.Timestamp(tf))]
        return p1 / p0 - 1
    except KeyError:
        return np.nan

survivors["fwd_return"] = survivors.apply(fwd_ret, axis=1)
survivors = survivors.dropna(subset=["fwd_return"])
survivors["quarter"] = pd.to_datetime(survivors["known_date"]).dt.to_period("Q")

n_quarters = survivors["quarter"].nunique()
print(f"Survivors with a computed forward return: {len(survivors):,} across {n_quarters} quarters")

lo, hi = survivors["fwd_return"].quantile([WINSOR_LO, WINSOR_HI])
survivors["fwd_return_wins"] = survivors["fwd_return"].clip(lo, hi)
print(f"Winsorizing at [{WINSOR_LO},{WINSOR_HI}] pctiles: clip to [{lo*100:.1f}%, {hi*100:.1f}%]")

quarters = sorted(survivors["quarter"].unique())
groups = {q: grp.reset_index(drop=True) for q, grp in survivors.groupby("quarter")}

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
    return np.array(spreads)

records = []
for seed in range(N_SEEDS):
    for col, label in [("fwd_return", "raw"), ("fwd_return_wins", "winsorized")]:
        spreads = one_draw(seed, col)
        sd = spreads.std(ddof=1)
        mde = minimum_detectable_difference(n_quarters, sd, rebalance_days=63, alpha=0.05, power=0.80)
        records.append({"seed": seed, "variant": label, "sd_spread": sd, "mde_period": mde["mde_period"]})

df = pd.DataFrame(records)
print("\n" + "=" * 78)
print(f"NULL SPREAD, {N_SEEDS} random decile-assignment draws, {n_quarters} quarter-clusters, "
      f"n_top/quarter ~= {int(round(len(survivors)/n_quarters*DECILE_FRAC))}")
print("=" * 78)
for label in ["raw", "winsorized"]:
    sub = df[df["variant"] == label]
    print(f"\n{label.upper()}:")
    print(f"  SD of quarterly null spread -- mean={sub['sd_spread'].mean()*100:.3f}%  "
          f"min={sub['sd_spread'].min()*100:.3f}%  max={sub['sd_spread'].max()*100:.3f}%  "
          f"std-across-draws={sub['sd_spread'].std()*100:.3f}pp")
    print(f"  MDE (80% power, quarter-clustered, df={n_quarters-1}) -- "
          f"mean={sub['mde_period'].mean()*100:.2f}%  "
          f"min={sub['mde_period'].min()*100:.2f}%  max={sub['mde_period'].max()*100:.2f}%")

print(f"\nPlausible PEAD effect band: 1%-3% over 60 days")
print(f"Round-trip cost band: 0.2%-0.3%")
con.close()
