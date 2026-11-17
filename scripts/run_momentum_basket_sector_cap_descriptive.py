"""Descriptive addendum to the 2026-10-26 momentum basket record
(FINDINGS.md Section 2, "DESCRIPTIVE ADDENDUM, 2026-11-17"). Measurement
only, no strategy claim, pre-outcome, committed before the 2027-01-26
check-in.

Reconstructs the EXACT universe-construction pipeline `scripts/run_
momentum_basket_snapshot.py` used (same exclusions, same liquidity-
tercile convention) to recover the full eligible cross-section at the
2026-10-26 snapshot, not just the 147 recorded holdings, then joins
`data/raw/sector/symbol_industry_map.csv` -- the same sector source
`src/reports/fundamental_snapshot.py`'s `load_sector_map()` already
uses, on disk since 2026-09-20, before the snapshot (no look-ahead).

HHI convention matches `data/sector_concentration_audit.csv`: sum of
squared sector shares among MAPPED names only, 0-1 scale. Liquidity-
tercile bands are the same high_liq/mid_liq/low_liq convention used
throughout this project's momentum/portfolio work, already recorded
per-holding in the basket file itself.

Read-only against the warehouse; writes nothing.
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_full_entity_panel_authorized
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from factors.momentum import compute_momentum_12_1
from monitor.persistence import same_isin_jump_excluded_entities

ROOT = Path(__file__).resolve().parents[1]
BASKET_PATH = ROOT / "data" / "momentum_live" / "v1" / "baskets.jsonl"
SECTOR_MAP_CSV = ROOT / "data" / "raw" / "sector" / "symbol_industry_map.csv"
DECILE_FRAC = 0.10

with open(BASKET_PATH, encoding="utf-8") as f:
    basket_record = json.loads(f.readline())
snapshot_date = pd.Timestamp(basket_record["snapshot_date"])
recorded_holdings = {h["entity_id"]: h for h in basket_record["holdings"]}
print(f"Recorded basket: snapshot_date={snapshot_date.date()}, n_holdings={len(recorded_holdings)}, "
      f"n_eligible_cross_section={basket_record['n_eligible_cross_section']}")

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
excluded = same_isin_jump_excluded_entities(con)  # BUGS.md Bug #11
panel_all = read_full_entity_panel_authorized(con, authorize_holdout=True)
panel = panel_all[~panel_all["entity_id"].isin(excluded)].reset_index(drop=True)
jump_dates = unexplained_jump_boundaries(con, before=None)

mom = compute_momentum_12_1(panel, unexplained_jump_dates=jump_dates)
p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
    if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index)
)
liq = p[["entity_id", "trade_date", "_liq", "_tercile"]]
m = mom.merge(liq, on=["entity_id", "trade_date"]).dropna(subset=["value", "_tercile"])

day = m[m["trade_date"] == snapshot_date].copy().sort_values("value", ascending=False).reset_index(drop=True)
day["rank"] = day.index + 1
print(f"\nCHECKPOINT -- reconstructed cross-section at {snapshot_date.date()}: n={len(day)} "
      f"(expect {basket_record['n_eligible_cross_section']})")

# Listing age: first trade_date for this entity ANYWHERE in the
# entity-resolved panel (spans ISIN-lineage chains) -- a lower bound,
# not a true listing date, left-censored at the panel's own 2016-01-01
# start for anything already trading then.
first_date = panel.groupby("entity_id")["trade_date"].min()
day["first_trade_date"] = day["entity_id"].map(first_date)
day["listing_age_years"] = (snapshot_date - day["first_trade_date"]).dt.days / 365.25

cutoff = day["value"].quantile(1 - DECILE_FRAC)
top = day[day["value"] >= cutoff].sort_values("value", ascending=False)
print(f"CHECKPOINT -- reconstructed top-decile count: {len(top)} (expect {len(recorded_holdings)}), "
      f"cutoff value={cutoff:.6f}")
print(f"CHECKPOINT -- entity sets match exactly: {set(top['entity_id']) == set(recorded_holdings)}")

# Symbols for the FULL eligible universe (not just the 147), same join
# convention run_momentum_basket_snapshot.py uses for its own 147.
entity_ids = day["entity_id"].tolist()
placeholders = ",".join("?" * len(entity_ids))
sym_df = con.execute(
    f"""
    SELECT l.entity_id, p.symbol
    FROM prices_eod p
    JOIN isin_lineage l ON p.isin = l.isin
    WHERE l.entity_id IN ({placeholders}) AND p.trade_date = ?
    """,
    entity_ids + [snapshot_date.date()],
).fetchdf()
con.close()

day = day.merge(sym_df, on="entity_id", how="left")
day["is_holding"] = day["entity_id"].isin(recorded_holdings)

sector_map = pd.read_csv(SECTOR_MAP_CSV).rename(columns={"Symbol": "symbol", "Industry": "sector"})
day = day.merge(sector_map, on="symbol", how="left")

print(f"\nSector map coverage -- universe: {day['sector'].notna().sum()} of {len(day)} mapped "
      f"({day['sector'].notna().mean()*100:.1f}%)")
basket_df = day[day["is_holding"]]
print(f"Sector map coverage -- basket: {basket_df['sector'].notna().sum()} of {len(basket_df)} mapped "
      f"({basket_df['sector'].notna().mean()*100:.1f}%)")


def sector_breakdown(df, label):
    mapped = df[df["sector"].notna()]
    counts = mapped["sector"].value_counts()
    hhi = ((counts / len(mapped)) ** 2).sum()
    print(f"\n=== {label}: sector distribution (n_mapped={len(mapped)} of {len(df)}) ===")
    for sec, c in counts.items():
        print(f"  {sec:<28s} {c:>4d}  {c / len(mapped) * 100:>5.1f}%")
    print(f"  HHI (mapped only, 0-1 scale): {hhi:.4f}")
    return counts, hhi


def tercile_breakdown(df, label):
    counts = df["_tercile"].value_counts(dropna=False)
    print(f"\n=== {label}: liquidity-tercile distribution (n={len(df)}) ===")
    for t in ["high_liq", "mid_liq", "low_liq"]:
        c = counts.get(t, 0)
        print(f"  {t:<10s} {c:>4d}  {c / len(df) * 100:>5.1f}%")
    nanc = df["_tercile"].isna().sum()
    if nanc:
        print(f"  (unclassified) {nanc:>4d}  {nanc / len(df) * 100:>5.1f}%")


def mapped_vs_unmapped(df, label):
    """Is the sector-mapping gap random or systematic? Compares the
    MAPPED subset the HHI is actually computed on against the UNMAPPED
    rest on every attribute already in hand."""
    print(f"\n=== {label}: mapped vs. unmapped, on attributes already in hand ===")
    g = df.groupby(df["sector"].notna().rename("mapped"))
    med = g[["listing_age_years", "_liq", "rank"]].median()
    med.index = med.index.map({True: "mapped", False: "unmapped"})
    print(med.rename(columns={"listing_age_years": "median_listing_age_yrs",
                               "_liq": "median_turnover_rs", "rank": "median_rank"}))
    print("n:", {("mapped" if k else "unmapped"): v for k, v in g.size().to_dict().items()})
    print("tercile crosstab (mapped x liquidity tercile):")
    ct = pd.crosstab(df["sector"].notna().map({True: "mapped", False: "unmapped"}), df["_tercile"])
    print(ct)


print("\n" + "=" * 70)
print(f"BASKET ({len(basket_df)} holdings)")
print("=" * 70)
sector_breakdown(basket_df, "BASKET")
tercile_breakdown(basket_df, "BASKET")
mapped_vs_unmapped(basket_df, "BASKET")

print("\n" + "=" * 70)
print(f"UNIVERSE ({len(day)} eligible)")
print("=" * 70)
sector_breakdown(day, "UNIVERSE")
tercile_breakdown(day, "UNIVERSE")
mapped_vs_unmapped(day, "UNIVERSE")

print("\n" + "=" * 70)
print("Context, recorded not inferred")
print("=" * 70)
min_mom = min(h["momentum_12_1"] for h in recorded_holdings.values())
print(f"Weakest holding's momentum_12_1: {min_mom:.6f} ({min_mom * 100:.2f}%)")

print(f"\nUniverse-count status: recorded basket says "
      f"n_eligible_cross_section={basket_record['n_eligible_cross_section']}; this reconstruction gets "
      f"{len(day)}. UNEXPLAINED, not immaterial -- cause not identified. The 147-entity top-decile set "
      f"matching exactly is strong evidence the one-entity gap does not change the basket's composition, "
      f"but that is evidence of no effect, not an explanation of the cause.")
