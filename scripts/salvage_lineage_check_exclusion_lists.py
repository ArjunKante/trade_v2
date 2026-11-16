"""ONE-TIME salvage: materializes and saves the exclusion lists actually
used by scripts/run_holdout_study1_lineage_check.py's last run
(2026-11-17T00:17:46, data/holdout_access_log.txt), for the 3.50
(window-level) and 5.97 (entity-level) margin figures.

Does NOT recompute the margin/backtest -- only re-derives the entity
lists, using the exact same code the original run used. Safe to do
because corporate_actions, isin_lineage, prices_eod, and
adjustment_factors were all verified to have zero rows with
fetched_at > 2026-11-17T00:17:46.882164 (checked directly before this
script was written) -- nothing the detectors read has changed since,
so re-deriving now gives the identical lists, not new ones.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.lineage_jump_guard import find_unexplained_jumps
from data_layer.same_isin_jump_guard import find_unexplained_same_isin_jumps
from data_layer.exclusion_list import save_exclusion_list

ROOT = Path(__file__).resolve().parents[1]
DETECTOR_PATHS = [
    ROOT / "src" / "data_layer" / "same_isin_jump_guard.py",
    ROOT / "src" / "data_layer" / "lineage_jump_guard.py",
]

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

# --- same-ISIN base, pinned to the 2026-09-27 read date (79 entities) ---
same_isin_tight = find_unexplained_same_isin_jumps(con, before=dt.date(2026, 9, 28))
same_isin_tight = same_isin_tight[(~same_isin_tight["has_nearby_ca_record"]) & (same_isin_tight["gap_days"] <= 5)]
lineage_for_pin = con.execute("SELECT DISTINCT isin, entity_id FROM isin_lineage").fetchdf()
iso_to_entity_pin = lineage_for_pin.set_index("isin")["entity_id"].to_dict()
same_isin_excluded = sorted(set(same_isin_tight["isin"].map(iso_to_entity_pin).dropna().unique()))
print(f"same-ISIN base: {len(same_isin_excluded)} entities")

# --- lineage, 40 net-new entities (BUGS.md Bug #26 follow-up 3) ---
lineage_jumps = find_unexplained_jumps(con)
lineage_jumps = lineage_jumps[~lineage_jumps["has_nearby_ca_record"]].copy()
rows = []
for _, r in lineage_jumps.iterrows():
    pred_last = con.execute("select max(trade_date) from prices_eod where isin=?", [r["predecessor_isin"]]).fetchone()[0]
    succ_first = con.execute("select min(trade_date) from prices_eod where isin=?", [r["isin"]]).fetchone()[0]
    gap = (succ_first - pred_last).days if pred_last and succ_first else None
    rows.append({"entity_id": r["entity_id"], "transition_date": r["transition_date"], "gap_days": gap})
import pandas as pd
gap_df = pd.DataFrame(rows)
small_gap = gap_df[gap_df["gap_days"] <= 5]
net_new_40 = small_gap[~small_gap["entity_id"].isin(same_isin_excluded)].copy()
con.close()
assert len(net_new_40) == 40, f"expected 40 net-new lineage entities, got {len(net_new_40)}"
print(f"lineage net-new: {len(net_new_40)} entities")

same_isin_component = {"guard": "same_isin", "mode": "entity_exclusion", "entity_ids": same_isin_excluded}

lineage_entity_component = {"guard": "lineage", "mode": "entity_exclusion",
                             "entity_ids": sorted(net_new_40["entity_id"].tolist())}

lineage_window_component = {
    "guard": "lineage", "mode": "window_mask",
    "jump_dates": {row["entity_id"]: [row["transition_date"].date().isoformat()]
                   for _, row in net_new_40.iterrows()},
}

NOTES = ("Salvaged 2026-11-17 for a result computed at 2026-11-17T00:17:46 "
         "(data/holdout_access_log.txt), hours before this list was saved. "
         "Verified before salvage: corporate_actions, isin_lineage, "
         "prices_eod, adjustment_factors all have zero rows with "
         "fetched_at > 2026-11-17T00:17:46.882164 -- nothing the detectors "
         "read has changed, so this re-derivation matches the original run "
         "exactly, not a new computation.")

path_a = save_exclusion_list(
    "run_holdout_study1_lineage_check.window_level",
    produced_by="scripts/run_holdout_study1_lineage_check.py",
    components=[same_isin_component, lineage_window_component],
    detector_paths=DETECTOR_PATHS, notes=NOTES,
)
print(f"Saved: {path_a}")

path_b = save_exclusion_list(
    "run_holdout_study1_lineage_check.entity_level",
    produced_by="scripts/run_holdout_study1_lineage_check.py",
    components=[same_isin_component, lineage_entity_component],
    detector_paths=DETECTOR_PATHS, notes=NOTES,
)
print(f"Saved: {path_b}")
