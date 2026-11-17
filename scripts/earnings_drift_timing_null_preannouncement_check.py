"""For-the-record check on the closed earnings-drift study's DEV Stage 4
TIMING null (scripts/earnings_drift_dev_stage4_timing_null.py). The
study stays CLOSED -- condition 1 (DEV gate) failed independently of
this, on both RAW and WINSORIZED configs; nothing here reopens it.

Question: was the TIMING null's random entry date constrained to fall
AFTER each event's own announcement (known_date), or could it draw any
day in the same calendar year, including before the announcement?

Reads stage4's own `eligible_indices` verbatim (same contamination
guard, same HORIZON=60, same N_DRAWS=50, same seeds 0..49) and first
reproduces the ORIGINAL null bit-for-bit as a checkpoint -- if it
doesn't match the saved null_raw/null_wins arrays, the warehouse has
moved since the DEV run and nothing below can be trusted as "what
actually happened," only as a fresh, differently-dated re-measurement.
Then re-runs the same procedure with an added `dates[i] >= known_date`
constraint per event (post-announcement only) and reports the
restricted mean alongside the fraction of the original, unconstrained
draws that landed before their own event's known_date.
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
saved_null_raw = np.load(SCRATCH / "earnings_drift_dev_timing_null_raw.npy")
saved_null_wins = np.load(SCRATCH / "earnings_drift_dev_timing_null_wins.npy")

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

dates_by_entity = {eid: grp["trade_date"].to_numpy() for eid, grp in prices.groupby("entity_id")}
close_by_entity = {eid: grp.set_index("trade_date")["adjusted_close"] for eid, grp in prices.groupby("entity_id")}

events["year"] = pd.to_datetime(events["known_date"]).dt.year
events["known_date_dt64"] = events["known_date"].to_numpy().astype("datetime64[ns]")

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

def random_holding_return(eid, year, rng, post_only=False, known_date=None):
    idx = eligible_indices(eid, year)
    dates = dates_by_entity.get(eid)
    if dates is None or len(idx) == 0:
        return np.nan, None
    if post_only:
        idx = idx[dates[idx] >= np.datetime64(known_date)]
        if len(idx) == 0:
            return np.nan, None
    i = rng.choice(idx)
    d_entry, d_exit = dates[i], dates[i + HORIZON]
    s = close_by_entity[eid]
    p0, p1 = s.get(pd.Timestamp(d_entry), np.nan), s.get(pd.Timestamp(d_exit), np.nan)
    if pd.isna(p0) or pd.isna(p1):
        return np.nan, d_entry
    return p1 / p0 - 1, d_entry

def one_draw(seed, post_only=False, record_dates=False):
    rng = np.random.RandomState(seed)
    rets, entries = [], []
    for _, r in events.iterrows():
        ret, d_entry = random_holding_return(r["entity_id"], r["year"], rng, post_only=post_only, known_date=r["known_date"])
        rets.append(ret)
        entries.append(d_entry)
    ret = pd.Series(rets, index=events.index)
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
    pre_announcement = None
    if record_dates:
        entries_arr = pd.Series(entries)
        valid = entries_arr.notna().to_numpy()
        known_arr = events["known_date_dt64"].to_numpy()
        pre_announcement = (entries_arr.to_numpy()[valid].astype("datetime64[ns]")
                             < known_arr[valid]).mean()
    return spreads["raw"], spreads["wins"], pre_announcement

print("=== Step 1: reproduce the ORIGINAL (unconstrained) null as a checkpoint ===")
orig_results = [one_draw(s, post_only=False, record_dates=True) for s in range(N_DRAWS)]
orig_raw = np.array([r[0] for r in orig_results])
orig_wins = np.array([r[1] for r in orig_results])
pre_fracs = np.array([r[2] for r in orig_results])

matches = np.allclose(orig_raw, saved_null_raw, equal_nan=True) and np.allclose(orig_wins, saved_null_wins, equal_nan=True)
print(f"Reproduces saved DEV Stage 4 arrays bit-for-bit: {matches}")
if not matches:
    print("  WARNING: does not match -- warehouse state has moved since the DEV run.")
    print(f"  max |diff| raw:  {np.nanmax(np.abs(orig_raw - saved_null_raw)):.6f}")
    print(f"  max |diff| wins: {np.nanmax(np.abs(orig_wins - saved_null_wins)):.6f}")

print(f"\nFraction of individual event-draws, per repetition, that fell BEFORE "
      f"that event's own known_date (pre-announcement):")
print(f"  mean across {N_DRAWS} repetitions: {pre_fracs.mean()*100:.1f}%")
print(f"  min/max across repetitions: {pre_fracs.min()*100:.1f}% / {pre_fracs.max()*100:.1f}%")

print("\n=== Step 2: re-run with entries constrained to known_date or later ===")
post_results = [one_draw(s, post_only=True, record_dates=False) for s in range(N_DRAWS)]
post_raw = np.array([r[0] for r in post_results])
post_wins = np.array([r[1] for r in post_results])

pct_raw_orig = (orig_raw < real_mean_raw).mean() * 100
pct_wins_orig = (orig_wins < real_mean_wins).mean() * 100
pct_raw_post = (post_raw < real_mean_raw).mean() * 100
pct_wins_post = (post_wins < real_mean_wins).mean() * 100

print(f"\nReal observed spread:       RAW={real_mean_raw*100:.3f}%   WINS={real_mean_wins*100:.3f}%")
print(f"ORIGINAL null (unconstrained, any day in calendar year):")
print(f"  RAW:  mean={np.nanmean(orig_raw)*100:.3f}%  pctile of real={pct_raw_orig:.1f}")
print(f"  WINS: mean={np.nanmean(orig_wins)*100:.3f}%  pctile of real={pct_wins_orig:.1f}")
print(f"POST-ANNOUNCEMENT-ONLY null (entry >= known_date):")
print(f"  RAW:  mean={np.nanmean(post_raw)*100:.3f}%  pctile of real={pct_raw_post:.1f}")
print(f"  WINS: mean={np.nanmean(post_wins)*100:.3f}%  pctile of real={pct_wins_post:.1f}")
print(f"\nShift in null mean (post-only minus original), i.e. how much of the "
      f"null's level was attributable to unattainable pre-announcement draws:")
print(f"  RAW:  {(np.nanmean(post_raw) - np.nanmean(orig_raw))*100:+.3f} pts")
print(f"  WINS: {(np.nanmean(post_wins) - np.nanmean(orig_wins))*100:+.3f} pts")
