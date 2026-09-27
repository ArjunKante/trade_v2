"""Descriptive-only: how many distinct momentum-persistence regimes exist
in trade-new's own pre-holdout history, by a mechanical definition fixed
BEFORE this script was run (see NEW_RESEARCH_DIRECTION.md's Hypothesis A
amendment). Directly answers: is there enough regime variation in history
to ever validate an ACTIONABLE version of the persistence monitor, or does
it face the same power problem as FINDINGS.md Section 12?

REFACTORED: the statistic and regime-rule computation now live in
src/monitor/persistence.py (built after this script, per instruction, to
be the module's single source of truth) -- this script imports from
there instead of duplicating the logic, so the two cannot drift apart.
Output is unchanged from the original run (3 regimes, 8 pre-holdout
years) -- this refactor changes where the code lives, not what it
computes.

Pre-holdout only (`read_entity_panel`'s default; `authorize_holdout` never
passed). No new holdout touch.

Usage:
    python scripts/run_momentum_persistence_regime_count.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from data_layer.holdout import SEALED_HOLDOUT_START
from monitor.persistence import compute_daily_persistence, annual_mean_sign, mechanical_regimes

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
    panel = read_entity_panel(con)  # pre-holdout by default, no authorize_holdout
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)
    con.close()

    daily = compute_daily_persistence(panel, jump_dates)
    print(f"Merged momentum+forward-return rows -> {len(daily)} distinct qualifying dates", file=sys.stderr)

    annual = annual_mean_sign(daily)

    print("\n" + "=" * 90)
    print("MOMENTUM PERSISTENCE, PER CALENDAR YEAR, PRE-HOLDOUT, trade-new's OWN universe")
    print("(Spearman rank corr: momentum_12_1 vs SAME-date forward-63d return, cross-sectional, daily, averaged/year)")
    print("=" * 90)
    for _, r in annual.iterrows():
        n_dates = (daily["trade_date"].dt.year == r["year"]).sum()
        print(f"  {int(r['year'])}: mean_persistence={r['mean_persistence']:+.4f}  "
              f"n_dates={n_dates}  sign={'+' if r['sign'] > 0 else '-'}")

    regimes = mechanical_regimes(annual)

    print("\n" + "-" * 90)
    print("MECHANICAL REGIMES (maximal contiguous same-sign year runs, rule fixed before this run)")
    print("-" * 90)
    for r0, r1, s in regimes:
        label = f"{r0}" if r0 == r1 else f"{r0}-{r1}"
        print(f"  {label}: sign={'+' if s > 0 else '-'}")
    print(f"\nTOTAL DISTINCT REGIMES IN PRE-HOLDOUT HISTORY: {len(regimes)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
