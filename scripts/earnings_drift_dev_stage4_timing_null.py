"""DEV Stage 4: TIMING null -- same selected events (real top-decile/
rest labels fixed), each entity's 60-day holding return recomputed from
a RANDOM trading day elsewhere in the same calendar year, instead of
the real post-announcement entry. Tests whether announcement timing
matters, or only which stock/year combinations were selected.
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(r"C:\projects\trade-new")
sys.path.insert(0, str(ROOT / "src"))
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from data_layer.same_isin_jump_guard import find_unexplained_same_isin_jumps

SCRATCH = Path(r"C:\Users\ARJUNK~1\AppData\Local\Temp\claude\C--projects-trade-new\cee5e6e2-73d6-4e3c-af4a-e518efcfde77\scratchpad")
HORIZON = 60
N_DRAWS = 50

events = pd.read_parquet(SCRATCH / "earnings_drift_dev_events_ranked.parquet")
real_mean_raw = pd.read_parquet(SCRATCH / "earnings_drift_dev_spread_raw.parquet")["spread"].mean()
real_mean_wins = pd.read_parquet(SCRATCH / "earnings_drift_dev_spread_wins.parquet")["spread"].mean()

con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)
prices = con.execute("SELECT entity_id, trade_date, adjusted_close FROM entity_prices_daily ORDER BY entity_id, trade_date").fetchdf()
lineage = con.execute("SELECT DISTINCT isin, entity_id FROM isin_lineage").fetchdf()
iso_to_entity = lineage.set_index("isin")["entity_id"].to_dict()
lineage_jumps = unexplained_jump_boundaries(con, before=None)
same_isin_full = find_unexplained_same_isin_jumps(con, before=None)
same_isin_full = same_isin_full[~same_isin_full["has_nearby_ca_record"]]
con.close()
entity_jump_dates = {}
for eid, dts in lineage_jumps.items():
    entity_jump_dates.setdefault(eid, set()).update(np.datetime64(d) for d in dts)
for _, r in same_isin_full.iterrows():
    e = iso_to_entity.get(r["isin"])
    if e:
        entity_jump_dates.setdefault(e, set()).add(np.datetime64(r["jump_date"]))
print(f"Contamination-guard dates loaded for {len(entity_jump_dates)} entities (Amendment 2, applied to null draws too)")

dates_by_entity = {eid: grp["trade_date"].to_numpy() for eid, grp in prices.groupby("entity_id")}
close_by_entity = {eid: grp.set_index("trade_date")["adjusted_close"] for eid, grp in prices.groupby("entity_id")}

events["year"] = pd.to_datetime(events["known_date"]).dt.year
quarters = sorted(events["quarter"].unique())

# precompute, per entity/year, the eligible index range (indices with idx+HORIZON < len(dates) AND trade_date.year == year)
eligible_idx_cache = {}
def eligible_indices(eid, year):
    key = (eid, year)
    if key in eligible_idx_cache:
        return eligible_idx_cache[key]
    dates = dates_by_entity.get(eid)
    if dates is None:
        eligible_idx_cache[key] = np.array([], dtype=int)
        return eligible_idx_cache[key]
    years = pd.to_datetime(dates).year
    mask = (years == year) & (np.arange(len(dates)) + HORIZON < len(dates))
    idx = np.flatnonzero(mask)
    jump_dates = entity_jump_dates.get(eid)
    if jump_dates:
        keep = []
        for i in idx:
            lo, hi = dates[i], dates[i + HORIZON]
            if not any(lo < d <= hi for d in jump_dates):
                keep.append(i)
        idx = np.array(keep, dtype=int)
    eligible_idx_cache[key] = idx
    return idx

def random_holding_return(eid, year, rng):
    idx = eligible_indices(eid, year)
    if len(idx) == 0:
        return np.nan
    i = rng.choice(idx)
    dates = dates_by_entity[eid]
    d_entry, d_exit = dates[i], dates[i + HORIZON]
    s = close_by_entity[eid]
    p0, p1 = s.get(pd.Timestamp(d_entry), np.nan), s.get(pd.Timestamp(d_exit), np.nan)
    if pd.isna(p0) or pd.isna(p1):
        return np.nan
    return p1 / p0 - 1

def one_draw(seed):
    rng = np.random.RandomState(seed)
    ret = events.apply(lambda r: random_holding_return(r["entity_id"], r["year"], rng), axis=1)
    bounds = ret.groupby(events["quarter"]).quantile([0.01, 0.99]).unstack()
    bounds.columns = ["q_lo", "q_hi"]
    wins = ret.clip(bounds["q_lo"].reindex(events["quarter"]).to_numpy(),
                     bounds["q_hi"].reindex(events["quarter"]).to_numpy())
    df = pd.DataFrame({"quarter": events["quarter"], "is_top_decile": events["is_top_decile"],
                        "raw": ret, "wins": wins})
    spreads = {}
    for col in ("raw", "wins"):
        g = df.groupby(["quarter", "is_top_decile"])[col].mean().unstack()
        g.columns = ["rest", "top"]
        spreads[col] = (g["top"] - g["rest"]).dropna().mean()
    return spreads["raw"], spreads["wins"]

print(f"Running TIMING null, {N_DRAWS} draws (each redraws a random entry date per event)...")
results = [one_draw(s) for s in range(N_DRAWS)]
null_raw = np.array([r[0] for r in results])
null_wins = np.array([r[1] for r in results])

pct_raw = (null_raw < real_mean_raw).mean() * 100
pct_wins = (null_wins < real_mean_wins).mean() * 100
print(f"\nTIMING null, {N_DRAWS} draws:")
print(f"  RAW:        null mean={np.nanmean(null_raw)*100:.3f}% sd={np.nanstd(null_raw)*100:.3f}%  "
      f"real value percentile = {pct_raw:.1f}")
print(f"  WINSORIZED: null mean={np.nanmean(null_wins)*100:.3f}% sd={np.nanstd(null_wins)*100:.3f}%  "
      f"real value percentile = {pct_wins:.1f}")
print(f"\nGate condition 2b (TIMING null, >=95th pctile) -- RAW: {pct_raw>=95}  WINSORIZED: {pct_wins>=95}")

np.save(SCRATCH / "earnings_drift_dev_timing_null_raw.npy", null_raw)
np.save(SCRATCH / "earnings_drift_dev_timing_null_wins.npy", null_wins)
print("\nCheckpoints written.")
