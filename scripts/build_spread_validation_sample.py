"""SPREAD_ESTIMATOR_VALIDATION.md's own stratified sample -- run ONCE,
tonight, before any live collection starts. Read-only against the
warehouse (historical prices_eod, no Angel One call, no live quote).
Writes config/spread_validation_symbols.txt (consumed later, unchanged,
by src/spread_monitor/config.py::load_symbols) and prints the full
selection with every entity's own band/series/price/vol/reason.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from data_layer.db import get_read_connection
from spread_validation.sampling import select_be_sample, select_eq_band_sample

ROOT = Path(__file__).resolve().parents[1]
OUT_SYMBOLS_PATH = ROOT / "config" / "spread_validation_symbols.txt"

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

eq = select_eq_band_sample(con, n_per_band=6)
be = select_be_sample(con, n=6)

print("=" * 100)
print("EQ sample, by turnover band")
print("=" * 100)
print(eq[["entity_id", "symbol", "band", "rank", "close", "vol", "selection_reason"]]
      .sort_values(["band", "rank"]).to_string(index=False))

print("\n" + "=" * 100)
print("BE (trade-to-trade) sample")
print("=" * 100)
print(be.to_string(index=False))

total_n = len(eq) + len(be)
print(f"\nTotal names: {total_n} ({len(eq)} EQ across {eq['band'].nunique()} bands, {len(be)} BE)")
print(f"getMarketData token budget: {total_n} symbols + 1 (Nifty index) = {total_n + 1} of 50 max "
      f"({50 - total_n - 1} free headroom)")

by_band = eq.groupby("band").size()
print(f"\nPer-band EQ counts: {dict(by_band)}  (requirement: >=6 each)")
print(f"BE count: {len(be)}  (requirement: >=6)")
print(f"Price range, EQ: Rs {eq['close'].min():.2f} to Rs {eq['close'].max():.2f}")
print(f"Price range, BE: Rs {be['close'].min():.2f} to Rs {be['close'].max():.2f}")
print(f"Vol range, EQ (annualized): {eq['vol'].min()*100:.1f}% to {eq['vol'].max()*100:.1f}%")

all_symbols = pd.concat([eq[["symbol"]], be[["symbol"]]]).drop_duplicates()
OUT_SYMBOLS_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_SYMBOLS_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("# Stratified sample for SPREAD_ESTIMATOR_VALIDATION.md -- built by\n")
    f.write("# scripts/build_spread_validation_sample.py, read-only against the\n")
    f.write("# warehouse, NO live data collected to produce this list. Consumed by\n")
    f.write("# src/spread_monitor/config.py::load_symbols(path=...), same format as\n")
    f.write("# config/spread_monitor_symbols.txt (one symbol per line, no -EQ suffix).\n")
    f.write("#\n")
    f.write(f"# {len(eq)} EQ names across 3 turnover bands (band=1-50/51-100/101-200,\n")
    f.write("# 6 per band: 2 highest-vol, 2 lowest-vol, 2 price-extreme within band)\n")
    f.write("# plus {0} BE/T2T names (turnover-percentile-spread within the active\n".format(len(be)))
    f.write("# BE population). See SPREAD_ESTIMATOR_VALIDATION.md Section on SAMPLE.\n#\n")
    for band_name, grp in eq.sort_values(["band", "rank"]).groupby("band", sort=False):
        f.write(f"# Band {band_name}:\n")
        for _, r in grp.iterrows():
            f.write(f"{r['symbol']}\n")
            f.write(f"#   entity_id={r['entity_id']} rank={r['rank']} close={r['close']:.2f} "
                    f"vol={r['vol']*100:.1f}% reason={r['selection_reason']}\n")
        f.write("#\n")
    f.write("# BE / T2T (trade-to-trade):\n")
    for _, r in be.iterrows():
        f.write(f"{r['symbol']}\n")
        f.write(f"#   entity_id={r['entity_id']} close={r['close']:.2f} "
                f"median_turnover={r['median_turnover']:.0f} active_days={r['active_days']} "
                f"reason={r['selection_reason']}\n")

print(f"\nWrote {OUT_SYMBOLS_PATH}")
con.close()
