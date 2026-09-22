"""Explicit, one-time (re-runnable) write step. Read paths never call this."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.adjustment import materialize_adjustment_factors, read_adjusted_prices

ROOT = Path(__file__).resolve().parents[1]
con = get_connection(ROOT / "data" / "warehouse.duckdb")

n = materialize_adjustment_factors(con, impl="sql")
print(f"adjustment_factors materialized: {n} rows")

print()
print("--- distinct factor value count (must be > 1) ---")
print(con.execute("SELECT COUNT(DISTINCT factor) FROM adjustment_factors").fetchone())

print()
print("--- BAJFINANCE entity, adjusted prices around BOTH transitions ---")
df = read_adjusted_prices(con, "INE296A01016")
print(df[(df["trade_date"] >= "2016-09-05") & (df["trade_date"] <= "2016-09-13")].to_string())
print(df[(df["trade_date"] >= "2025-06-10") & (df["trade_date"] <= "2025-06-20")].to_string())

con.close()
