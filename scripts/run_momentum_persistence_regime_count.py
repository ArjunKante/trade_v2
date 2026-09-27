"""Descriptive-only: how many distinct momentum-persistence regimes exist
in trade-new's own pre-holdout history, by a mechanical definition fixed
BEFORE this script was run (see NEW_RESEARCH_DIRECTION.md's Hypothesis A
amendment). Directly answers: is there enough regime variation in history
to ever validate an ACTIONABLE version of the persistence monitor, or does
it face the same power problem as FINDINGS.md Section 12?

METHODOLOGY, matching trade-info's own already-validated regime
diagnostic (`trade-info/DESIGN.md`, `trade-info/FINDINGS.md` Section 3):
per trading date, the cross-sectional Spearman rank correlation between
momentum_12_1 (trailing 12-1 return) and the SAME date's forward 63-day
return -- i.e. does this date's momentum ranking predict this date's own
forward-return ranking. Averaged per calendar year for a stable read
(day-level correlations are noisy; annual averaging is the same
granularity swing/momentum work in this project already reports at).

MECHANICAL REGIME RULE, fixed before running: a regime is a maximal
contiguous run of calendar years whose annual-mean persistence
correlation shares the same sign. A boundary is crossed when consecutive
years' annual means differ in sign. No magnitude threshold, no smoothing,
no data-dependent tuning.

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

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from data_layer.holdout import SEALED_HOLDOUT_START
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
    panel = read_entity_panel(con)  # pre-holdout by default, no authorize_holdout
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)
    con.close()

    mom = compute_momentum_12_1(panel, jump_dates).dropna(subset=["value"]).rename(columns={"value": "mom"})
    fwd = compute_forward_return(panel, unexplained_jump_dates=jump_dates).dropna(subset=["fwd_return"])

    merged = mom.merge(fwd[["entity_id", "trade_date", "fwd_return"]], on=["entity_id", "trade_date"], how="inner")
    print(f"Merged momentum+forward-return rows: {len(merged)}, "
          f"{merged['trade_date'].nunique()} distinct dates", file=sys.stderr)

    rows = []
    for d, g in merged.groupby("trade_date"):
        if len(g) < 20:
            continue
        rho, _ = spearmanr(g["mom"], g["fwd_return"])
        rows.append({"trade_date": d, "persistence": rho, "n": len(g)})
    daily = pd.DataFrame(rows)
    daily["year"] = pd.to_datetime(daily["trade_date"]).dt.year

    annual = daily.groupby("year").agg(
        mean_persistence=("persistence", "mean"),
        std_persistence=("persistence", "std"),
        n_dates=("persistence", "count"),
    ).reset_index()
    annual["sign"] = np.sign(annual["mean_persistence"])

    print("\n" + "=" * 90)
    print("MOMENTUM PERSISTENCE, PER CALENDAR YEAR, PRE-HOLDOUT, trade-new's OWN universe")
    print("(Spearman rank corr: momentum_12_1 vs SAME-date forward-63d return, cross-sectional, daily, averaged/year)")
    print("=" * 90)
    for _, r in annual.iterrows():
        print(f"  {int(r['year'])}: mean_persistence={r['mean_persistence']:+.4f}  "
              f"std={r['std_persistence']:.4f}  n_dates={int(r['n_dates'])}  sign={'+' if r['sign']>0 else '-'}")

    # mechanical regime count: maximal contiguous runs of same-signed annual mean
    signs = annual["sign"].tolist()
    years = annual["year"].tolist()
    regimes = []
    start_idx = 0
    for i in range(1, len(signs)):
        if signs[i] != signs[start_idx]:
            regimes.append((years[start_idx], years[i - 1], signs[start_idx]))
            start_idx = i
    regimes.append((years[start_idx], years[-1], signs[start_idx]))

    print("\n" + "-" * 90)
    print("MECHANICAL REGIMES (maximal contiguous same-sign year runs, rule fixed before this run)")
    print("-" * 90)
    for r0, r1, s in regimes:
        label = f"{r0}" if r0 == r1 else f"{r0}-{r1}"
        print(f"  {label}: sign={'+' if s>0 else '-'}")
    print(f"\nTOTAL DISTINCT REGIMES IN PRE-HOLDOUT HISTORY: {len(regimes)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
