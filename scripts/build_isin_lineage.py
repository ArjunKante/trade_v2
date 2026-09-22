"""Explicit, one-time (re-runnable) write step. isin_lineage is a fully
recomputed resolution layer, not append-only facts -- safe to rebuild from
scratch every time prices_eod grows."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.isin_lineage import build_lineage, load_lineage_to_duckdb

ROOT = Path(__file__).resolve().parents[1]
con = get_connection(ROOT / "data" / "warehouse.duckdb")

lineage_df, ambiguous_df = build_lineage(con)
n_lineage, n_ambiguous = load_lineage_to_duckdb(con, lineage_df, ambiguous_df)

print(f"isin_lineage: {n_lineage} ISINs resolved to an entity_id")
print(f"  of which linked via nsdl_structural: {(lineage_df['link_method']=='nsdl_structural').sum()}")
print(f"  of which chain_start (own entity, possibly a singleton): {(lineage_df['link_method']=='chain_start').sum()}")
print(f"isin_lineage_ambiguous: {n_ambiguous} candidate pairs NOT linked")
print()
print("--- ambiguous reasons breakdown ---")
if not ambiguous_df.empty:
    print(ambiguous_df["reason"].value_counts().to_string())
print()
print("--- BAJFINANCE entity check ---")
print(con.execute("SELECT * FROM isin_lineage WHERE isin IN ('INE296A01016','INE296A01024','INE296A01032') ORDER BY known_date").fetchdf().to_string())

con.close()
