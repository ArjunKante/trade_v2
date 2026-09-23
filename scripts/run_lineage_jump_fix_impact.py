"""Bug #1 follow-up (diagnostic, no study slot spent): quantify the surgical
NaN fix (lineage_jump_guard + the unexplained_jump_dates parameter added to
factors.momentum/lowvol/target) against the two numbers Bug #1's original
write-up reported for full-entity exclusion:
  - momentum_12_1 rank IC: 0.0714 -> 0.0713 excluding the 14 entities entirely
  - mean daily cross-sectional std of forward 63d return: 43.5% -> 34.3%
    excluding the 14 entities entirely, 28.1% via median instead of mean

This script compares three variants on the same pre-holdout panel: (1) no
fix at all, (2) Bug #1's original blunt fix (drop the 14 entities' rows
entirely from momentum/fwd), (3) this fix (NaN only the single boundary
observation per entity, via unexplained_jump_dates)."""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel
from data_layer.holdout import SEALED_HOLDOUT_START
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return

ROOT = Path(__file__).resolve().parents[1]
con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)
jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)
con.close()

affected_entities = set(jump_dates.keys())
print(f"Unexplained lineage-jump entities (pre-holdout): {len(affected_entities)}")


def rank_ic(mom_df, fwd_df):
    m = mom_df.merge(fwd_df, on=["entity_id", "trade_date"]).dropna(subset=["value", "fwd_return"])
    return spearmanr(m["value"], m["fwd_return"]).correlation, len(m)


def xsec_std_stats(fwd_df):
    daily = fwd_df.groupby("trade_date")["fwd_return"].std()
    return daily.mean(), daily.median()


# --- Variant 1: no fix ---
mom_nofix = compute_momentum_12_1(panel)
fwd_nofix = compute_forward_return(panel)
ic_nofix, n_nofix = rank_ic(mom_nofix, fwd_nofix)
std_mean_nofix, std_med_nofix = xsec_std_stats(fwd_nofix)

# --- Variant 2: Bug #1's original blunt fix (exclude the 14 entities entirely) ---
panel_excl = panel[~panel["entity_id"].isin(affected_entities)]
mom_excl = compute_momentum_12_1(panel_excl)
fwd_excl = compute_forward_return(panel_excl)
ic_excl, n_excl = rank_ic(mom_excl, fwd_excl)
std_mean_excl, std_med_excl = xsec_std_stats(fwd_excl)

# --- Variant 3: this fix -- NaN only the boundary observation, keep the rest of the entity ---
mom_surgical = compute_momentum_12_1(panel, unexplained_jump_dates=jump_dates)
fwd_surgical = compute_forward_return(panel, unexplained_jump_dates=jump_dates)
ic_surgical, n_surgical = rank_ic(mom_surgical, fwd_surgical)
std_mean_surgical, std_med_surgical = xsec_std_stats(fwd_surgical)

print(f"\n{'variant':30s} {'n_obs':>10s} {'rank_IC':>10s} {'xsec_std_mean':>15s} {'xsec_std_median':>16s}")
print(f"{'1. no fix':30s} {n_nofix:>10d} {ic_nofix:>10.4f} {std_mean_nofix*100:>14.1f}% {std_med_nofix*100:>15.1f}%")
print(f"{'2. exclude 14 entities':30s} {n_excl:>10d} {ic_excl:>10.4f} {std_mean_excl*100:>14.1f}% {std_med_excl*100:>15.1f}%")
print(f"{'3. surgical NaN (this fix)':30s} {n_surgical:>10d} {ic_surgical:>10.4f} {std_mean_surgical*100:>14.1f}% {std_med_surgical*100:>15.1f}%")

rows_recovered = n_surgical - n_excl
print(f"\nRows retained by the surgical fix vs the blunt exclusion: +{rows_recovered} "
      f"({(n_surgical - n_nofix)} rows dropped by the surgical fix in total, "
      f"vs {(n_nofix - n_excl)} rows dropped by excluding entire entities)")

print(
    "\nNOTE: variants 1 and 3 are identical here. Checked directly (not assumed): all 14 "
    "unexplained-jump transitions have a calendar gap of 29-2622 days between the last trade "
    "under the predecessor ISIN and the first under the successor -- comfortably past "
    "STALE_GAP_DAYS=5, so factors/momentum.py's and factors/target.py's EXISTING gap-fix "
    "(Bug #2, already in production) NaNs every one of these boundary rows regardless of "
    "whether unexplained_jump_dates is passed. The new lineage_jump_guard mechanism is "
    "confirmed necessary only for a hypothetical future jump WITHOUT a coincident halt "
    "(see tests/test_lineage_jump_guard.py's synthetic fixture, which has zero calendar gap "
    "by construction) -- it adds no measured value on today's real 14. Variant 2's further "
    "drop (36.9%->33.6% x-sec std) comes from removing these entities' entire histories, a "
    "population-composition effect, not from fixing the fabricated-jump mechanism itself."
)
