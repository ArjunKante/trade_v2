"""Explicit, one-time (re-runnable) write step. Never called from a read path."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.corporate_actions import (
    fetch_raw_actions, build_symbol_isin_observations, to_corporate_actions_df,
    load_corporate_actions_to_duckdb,
)

ROOT = Path(__file__).resolve().parents[1]
con = get_connection(ROOT / "data" / "warehouse.duckdb")

print("Fetching raw corporate actions 2016-01-01 to 2025-12-31...")
raw = fetch_raw_actions(dt.date(2016, 1, 1), dt.date(2025, 12, 31))
print(f"  {len(raw)} raw records")

symbol_obs = build_symbol_isin_observations(con)
print(f"  {len(symbol_obs)} symbol/date/isin observations to resolve against")

df = to_corporate_actions_df(raw, symbol_obs)
print(f"  {len(df)} bonus/split components parsed (dividends/AGM/buyback/etc excluded)")
print(f"  unresolved ISIN (symbol never observed in prices_eod): {len(raw) - len(df) if False else 'see below'}")

n = load_corporate_actions_to_duckdb(con, df)
print(f"Inserted {n} new rows into corporate_actions")

print("\n--- action_type distribution ---")
print(con.execute("SELECT action_type, COUNT(*) FROM corporate_actions GROUP BY action_type").fetchdf().to_string())

con.close()
