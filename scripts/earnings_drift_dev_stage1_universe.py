"""DEV Stage 1: build the earnings-drift event universe, event returns,
entry/exit, and the real per-quarter top-decile-vs-rest spread.

Per PREREGISTRATION_EARNINGS_DRIFT.md (Amendments 1 and 2). Read-only
against data/warehouse.duckdb; restricted to known_date < 2025-07-01
(the sealed window, EARNINGS_DRIFT_PHASE0.md Section 0, is never
touched). Checkpoints the final event-level dataframe to the scratchpad
so later stages (nulls, gate checks) do not have to rebuild the universe.
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from data_layer.same_isin_jump_guard import find_unexplained_same_isin_jumps

SCRATCH = Path(r"C:\Users\ARJUNK~1\AppData\Local\Temp\claude\C--projects-trade-new\cee5e6e2-73d6-4e3c-af4a-e518efcfde77\scratchpad")
SCRATCH.mkdir(parents=True, exist_ok=True)

SEAL_DATE = "2025-07-01"
HORIZON = 60
DECILE_FRAC = 0.10
WINSOR_LO, WINSOR_HI = 0.01, 0.99

con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)

print("Loading filings, lineage, same-ISIN pin, price panel, benchmark universe...")

filings = con.execute(f"""
    SELECT isin, known_date, broadcast_ts FROM fundamentals_filings
    WHERE known_date < DATE '{SEAL_DATE}'
""").fetchdf()
lineage = con.execute("SELECT DISTINCT isin, entity_id FROM isin_lineage").fetchdf()
filings = filings.merge(lineage, on="isin", how="left")
n_total = len(filings)
n_unmatched = filings["entity_id"].isna().sum()
filings = filings[filings["entity_id"].notna()].copy()
print(f"Total events in unsealed window: {n_total:,}; no isin_lineage match: {n_unmatched:,}; matched: {len(filings):,}")

# the 78-entity canonical same-ISIN pin, pinned 2026-09-27 (tight gap_days<=5)
import datetime as dt
same_isin_tight = find_unexplained_same_isin_jumps(con, before=dt.date(2026, 9, 28))
same_isin_tight = same_isin_tight[(~same_isin_tight["has_nearby_ca_record"]) & (same_isin_tight["gap_days"] <= 5)]
iso_to_entity = lineage.set_index("isin")["entity_id"].to_dict()
pinned_excluded_entities = set(same_isin_tight["isin"].map(iso_to_entity).dropna().unique())
print(f"78-entity canonical same-ISIN pin: {len(pinned_excluded_entities)} entities excluded")
filings = filings[~filings["entity_id"].isin(pinned_excluded_entities)].copy()
print(f"After canonical pin: {len(filings):,} events remain")

# real NSE trading calendar (NIFTY50, not entity_prices_daily's own truncated one)
cal_df = con.execute("SELECT DISTINCT trade_date FROM index_eod WHERE index_name='NIFTY50' ORDER BY trade_date").fetchdf()["trade_date"]
cal_set = set(cal_df)
cal_arr = np.array(sorted(cal_df.to_numpy()))

filings["tod"] = filings["broadcast_ts"].dt.time
filings["is_trading_day"] = filings["known_date"].isin(cal_set)

def day0_index(known_date, tod, is_trading_day):
    kd = np.datetime64(known_date)
    if is_trading_day and tod < pd.Timestamp("15:30").time():
        return int(np.searchsorted(cal_arr, kd, side="left"))
    side = "right" if is_trading_day else "left"
    return int(np.searchsorted(cal_arr, kd, side=side))

idx0 = [day0_index(r["known_date"], r["tod"], r["is_trading_day"]) for _, r in filings.iterrows()]
filings["i0"] = idx0
# drop events whose day0..entry window would run off the end of the calendar array
filings = filings[filings["i0"] + 3 < len(cal_arr)].copy()
filings["d0"] = filings["i0"].apply(lambda i: pd.Timestamp(cal_arr[i]))
filings["d1"] = filings["i0"].apply(lambda i: pd.Timestamp(cal_arr[i+1]))
filings["d2"] = filings["i0"].apply(lambda i: pd.Timestamp(cal_arr[i+2]))
filings["entry_date"] = filings["i0"].apply(lambda i: pd.Timestamp(cal_arr[i+3]))
print(f"Day-0/entry resolved for {len(filings):,} events")

prices = con.execute("SELECT entity_id, trade_date, adjusted_close FROM entity_prices_daily ORDER BY entity_id, trade_date").fetchdf()
price_dates_by_entity = {eid: grp["trade_date"].to_numpy() for eid, grp in prices.groupby("entity_id")}
price_close_by_entity = {eid: grp.set_index("trade_date")["adjusted_close"] for eid, grp in prices.groupby("entity_id")}

def entity_close(eid, date):
    s = price_close_by_entity.get(eid)
    if s is None:
        return np.nan
    return s.get(pd.Timestamp(date), np.nan)

print("Pulling event-window and entry/exit prices (this is the slow step)...")
rows = []
for _, r in filings.iterrows():
    eid = r["entity_id"]
    dates = price_dates_by_entity.get(eid)
    if dates is None or len(dates) == 0:
        continue
    c_prev = entity_close(eid, cal_arr[r["i0"] - 1]) if r["i0"] > 0 else np.nan
    c0, c1, c2 = entity_close(eid, r["d0"]), entity_close(eid, r["d1"]), entity_close(eid, r["d2"])
    c_entry = entity_close(eid, r["entry_date"])
    if any(pd.isna(x) for x in (c_prev, c0, c1, c2, c_entry)):
        continue
    idx_entry = np.searchsorted(dates, np.datetime64(r["entry_date"]))
    if dates[idx_entry] != np.datetime64(r["entry_date"]) or idx_entry + HORIZON >= len(dates):
        continue
    exit_date = dates[idx_entry + HORIZON]
    c_exit = entity_close(eid, exit_date)
    if pd.isna(c_exit):
        continue
    rows.append({
        "isin": r["isin"], "entity_id": eid, "known_date": r["known_date"],
        "d0": r["d0"], "d1": r["d1"], "d2": r["d2"], "entry_date": r["entry_date"], "exit_date": pd.Timestamp(exit_date),
        "c_prev": c_prev, "c0": c0, "c1": c1, "c2": c2, "c_entry": c_entry, "c_exit": c_exit,
    })
events = pd.DataFrame(rows)
print(f"Events with complete event-window + entry + exit prices: {len(events):,}")

# Amendment 2: drop events whose [d0, exit_date] window contains an unexplained jump
lineage_jumps = unexplained_jump_boundaries(con, before=None)
same_isin_full = find_unexplained_same_isin_jumps(con, before=None)
same_isin_full = same_isin_full[~same_isin_full["has_nearby_ca_record"]]
entity_same_isin_dates = {}
for _, r in same_isin_full.iterrows():
    e = iso_to_entity.get(r["isin"])
    if e:
        entity_same_isin_dates.setdefault(e, []).append(np.datetime64(r["jump_date"]))

def contaminated(row):
    eid = row["entity_id"]
    lo, hi = np.datetime64(row["d0"]), np.datetime64(row["exit_date"])
    for d in lineage_jumps.get(eid, []):
        if lo < np.datetime64(d) <= hi:
            return True
    for d in entity_same_isin_dates.get(eid, []):
        if lo < np.datetime64(d) <= hi:
            return True
    return False

events["contaminated"] = events.apply(contaminated, axis=1)
n_contam = events["contaminated"].sum()
events = events[~events["contaminated"]].copy()
print(f"Amendment 2 exclusion: dropped {n_contam:,} jump-contaminated events; {len(events):,} remain")

# event return: 3-session compounded return, market-adjusted against the event-universe EW benchmark
print("Building the event-universe equal-weight daily benchmark...")
universe_entities = events["entity_id"].unique()
bench_px = prices[prices["entity_id"].isin(universe_entities)].copy()
bench_px = bench_px.sort_values(["entity_id", "trade_date"])
bench_px["ret"] = bench_px.groupby("entity_id")["adjusted_close"].pct_change()
ew_bench = bench_px.groupby("trade_date")["ret"].mean()

def bench_ret(date):
    return ew_bench.get(pd.Timestamp(date), np.nan)

events["r0"] = events["c0"] / events["c_prev"] - 1
events["r1"] = events["c1"] / events["c0"] - 1
events["r2"] = events["c2"] / events["c1"] - 1
events["b0"] = events["d0"].apply(bench_ret)
events["b1"] = events["d1"].apply(bench_ret)
events["b2"] = events["d2"].apply(bench_ret)
events = events.dropna(subset=["b0", "b1", "b2"])
events["event_return"] = (1 + events["r0"] - events["b0"]) * (1 + events["r1"] - events["b1"]) * (1 + events["r2"] - events["b2"]) - 1
events["holding_return"] = events["c_exit"] / events["c_entry"] - 1
events["quarter"] = pd.to_datetime(events["known_date"]).dt.to_period("Q")
events["year"] = pd.to_datetime(events["known_date"]).dt.year
print(f"Final DEV event universe: {len(events):,} events, {events['entity_id'].nunique():,} entities, "
      f"{events['quarter'].nunique()} quarters")

out_path = SCRATCH / "earnings_drift_dev_events.parquet"
events.to_parquet(out_path)
print(f"Checkpoint written: {out_path}")
con.close()
