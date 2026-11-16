"""DEV Stage 5: best-year-drop, liquid-bands-only, and cost checks.
Cheap (no simulation) -- run for a complete picture even though Gate
conditions 1 and 2 already failed decisively.
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(r"C:\projects\trade-new")
SCRATCH = Path(r"C:\Users\ARJUNK~1\AppData\Local\Temp\claude\C--projects-trade-new\cee5e6e2-73d6-4e3c-af4a-e518efcfde77\scratchpad")

events = pd.read_parquet(SCRATCH / "earnings_drift_dev_events_ranked.parquet")

def spread_by(df, col):
    g = df.groupby(["quarter", "is_top_decile"])[col].mean().unstack()
    g.columns = ["rest", "top"]
    return (g["top"] - g["rest"]).dropna()

# --- best-year-drop ---
events["year"] = pd.to_datetime(events["known_date"]).dt.year
spread_raw = spread_by(events, "holding_return")
spread_wins = spread_by(events, "holding_return_wins")
year_of_quarter = {q: q.year for q in spread_raw.index}
by_year_raw = spread_raw.groupby([year_of_quarter[q] for q in spread_raw.index]).mean()
by_year_wins = spread_wins.groupby([year_of_quarter[q] for q in spread_wins.index]).mean()
best_year_raw = by_year_raw.idxmax()
best_year_wins = by_year_wins.idxmax()
print(f"Best year (raw): {best_year_raw} (mean spread {by_year_raw[best_year_raw]*100:.3f}%)")
print(f"Best year (winsorized): {best_year_wins} (mean spread {by_year_wins[best_year_wins]*100:.3f}%)")

dropped_raw = spread_raw[[year_of_quarter[q] != best_year_raw for q in spread_raw.index]]
dropped_wins = spread_wins[[year_of_quarter[q] != best_year_wins for q in spread_wins.index]]
print(f"\nGate condition 3 (still positive after dropping best year):")
print(f"  RAW: mean after drop = {dropped_raw.mean()*100:.3f}%  -> {'PASS' if dropped_raw.mean()>0 else 'FAIL'}")
print(f"  WINSORIZED: mean after drop = {dropped_wins.mean()*100:.3f}%  -> {'PASS' if dropped_wins.mean()>0 else 'FAIL'}")

# --- liquid bands only ---
con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)
turnover = con.execute("SELECT entity_id, trade_date, turnover FROM entity_prices_daily ORDER BY entity_id, trade_date").fetchdf()
con.close()
turnover["liq"] = turnover.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
turnover["tercile"] = turnover.groupby("trade_date")["liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop") if s.notna().sum() >= 3 else pd.Series([np.nan]*len(s), index=s.index))
tmap = turnover.set_index(["entity_id", "trade_date"])["tercile"]
events["tercile"] = events.apply(lambda r: tmap.get((r["entity_id"], r["entry_date"]), np.nan), axis=1)
liquid = events[events["tercile"].isin(["high_liq", "mid_liq"])]
print(f"\nLiquid-bands-only subset: {len(liquid):,} of {len(events):,} events ({len(liquid)/len(events)*100:.1f}%)")
spread_liq_raw = spread_by(liquid, "holding_return")
spread_liq_wins = spread_by(liquid, "holding_return_wins")
print(f"Gate condition 4 (positive within liquid bands alone):")
print(f"  RAW: mean = {spread_liq_raw.mean()*100:.3f}%  -> {'PASS' if spread_liq_raw.mean()>0 else 'FAIL'}")
print(f"  WINSORIZED: mean = {spread_liq_wins.mean()*100:.3f}%  -> {'PASS' if spread_liq_wins.mean()>0 else 'FAIL'}")

# --- costs ---
print(f"\nGate condition 5 (net of 0.20%-0.30% round-trip costs on the top-decile leg only):")
for cost in (0.0020, 0.0030):
    top_mean_raw = events.loc[events["is_top_decile"], "holding_return"].mean()
    rest_mean_raw = events.loc[~events["is_top_decile"], "holding_return"].mean()
    net_spread_raw = (top_mean_raw - cost) - rest_mean_raw
    top_mean_wins = events.loc[events["is_top_decile"], "holding_return_wins"].mean()
    rest_mean_wins = events.loc[~events["is_top_decile"], "holding_return_wins"].mean()
    net_spread_wins = (top_mean_wins - cost) - rest_mean_wins
    print(f"  cost={cost*100:.2f}%: RAW net spread = {net_spread_raw*100:.3f}%  "
          f"WINSORIZED net spread = {net_spread_wins*100:.3f}%")
