"""Swing trading, Phase 2 (candidate-count check, BEFORE any backtest):
how many names actually survive the frozen rule's universe/condition
intersection, per day, across the pre-holdout history? Per instruction,
this must be shown and reviewed before the backtest itself is built.

MECHANISM CORRECTION applied here (see src/swing/universe.py's module
docstring, and PREREGISTRATION_SWING.md's amendment): the 5-day-return
bottom-tercile condition ranks across the FULL EQ universe, not within the
momentum-top-decile-filtered candidate set.

FUNNEL REPORTED, one stage at a time (never collapsed to one number):
  1. momentum top decile AND {high_liq, mid_liq} liquidity tercile
     (fundamentals-screener condition OMITTED here -- see
     src/swing/universe.py's module docstring: no historical point-in-time
     screener series exists yet, flagged as an open item, not silently
     dropped from the rule going forward)
  2. (1) AND bottom-tercile 5-day return (ranked across the full EQ universe)
  3. (2) AND high-volume (20d ratio > 1.5x) AND Nifty regime-on -- the full
     three-condition rule

Usage:
    python scripts/run_swing_phase2_candidate_counts.py
"""
from __future__ import annotations

import datetime as dt
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel
from data_layer.holdout import SEALED_HOLDOUT_START
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from swing.universe import (
    historical_momentum_top_decile, historical_liquidity_tercile,
    historical_bottom_tercile_5d_return, historical_volume_ratio, nifty_regime,
)

ROOT = Path(__file__).resolve().parents[1]


def _count_stats(counts: pd.Series, label: str) -> list[str]:
    lines = [f"\n--- {label} ---"]
    lines.append(f"n_dates={len(counts)}  mean={counts.mean():.2f}  median={counts.median():.1f}  "
                 f"min={counts.min()}  max={counts.max()}")
    pct_under_5 = (counts < 5).mean() * 100
    pct_zero = (counts == 0).mean() * 100
    lines.append(f"days with < 5 candidates: {pct_under_5:.1f}%   days with 0 candidates: {pct_zero:.1f}%")
    for q in (0.10, 0.25, 0.50, 0.75, 0.90):
        lines.append(f"  p{int(q*100)}: {counts.quantile(q):.1f}")
    return lines


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    print("Loading pre-holdout entity panel...", file=sys.stderr, flush=True)
    panel = read_entity_panel(con)
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)

    print("Computing momentum top decile at every historical date...", file=sys.stderr, flush=True)
    mom = historical_momentum_top_decile(panel, jump_dates)

    print("Computing liquidity tercile at every historical date...", file=sys.stderr, flush=True)
    liq = historical_liquidity_tercile(panel)

    print("Computing 5-day-return bottom tercile across the FULL universe at every date...", file=sys.stderr, flush=True)
    rev = historical_bottom_tercile_5d_return(panel, jump_dates)

    print("Computing 20-day volume ratio...", file=sys.stderr, flush=True)
    vol = historical_volume_ratio(panel)

    print("Computing Nifty regime filter...", file=sys.stderr, flush=True)
    regime = nifty_regime(con, before=SEALED_HOLDOUT_START)
    con.close()

    print("Assembling the funnel...", file=sys.stderr, flush=True)
    base = mom[mom["in_top_decile"]].merge(liq, on=["entity_id", "trade_date"], how="inner")
    base = base[base["tercile"].isin(["high_liq", "mid_liq"])]

    stage2 = base.merge(rev[rev["bottom_tercile"]], on=["entity_id", "trade_date"], how="inner")

    stage3 = stage2.merge(vol[vol["high_volume"]], on=["entity_id", "trade_date"], how="inner")
    stage3 = stage3.merge(regime[regime["regime_on"]][["trade_date"]], on="trade_date", how="inner")

    lines = []
    A = lines.append
    A("=" * 100)
    A("SWING PHASE 2: CANDIDATE COUNTS PER DAY, BEFORE ANY BACKTEST")
    A("Mechanism correction applied: 5-day-return bottom tercile ranks across the FULL EQ universe, "
      "not within the momentum-top-decile subset. See src/swing/universe.py and PREREGISTRATION_SWING.md.")
    A("Fundamentals-screener condition OMITTED (no historical point-in-time series exists yet) -- flagged, "
      "not silently dropped from the rule going forward.")
    A("=" * 100)

    base_counts = base.groupby("trade_date").size()
    stage2_counts = stage2.groupby("trade_date").size()
    stage3_counts = stage3.groupby("trade_date").size()
    # dates with zero candidates never appear via groupby -- reindex onto the full trading-day calendar
    all_dates = pd.Index(sorted(panel["trade_date"].unique()))
    base_counts = base_counts.reindex(all_dates, fill_value=0)
    stage2_counts = stage2_counts.reindex(all_dates, fill_value=0)
    stage3_counts = stage3_counts.reindex(all_dates, fill_value=0)

    lines += _count_stats(base_counts, "STAGE 1: momentum top decile AND {high_liq, mid_liq}")
    lines += _count_stats(stage2_counts, "STAGE 2: (1) AND bottom-tercile 5-day return (full-universe ranked)")
    lines += _count_stats(stage3_counts, "STAGE 3 (FULL RULE): (2) AND high-volume(>1.5x) AND Nifty regime-on")

    A("\n" + "=" * 100)
    A("VIABILITY READING (per instruction: if routinely under 5, flag before proceeding)")
    A("=" * 100)
    pct_stage3_under5 = (stage3_counts < 5).mean() * 100
    pct_stage3_zero = (stage3_counts == 0).mean() * 100
    A(f"Full rule produces < 5 candidates on {pct_stage3_under5:.1f}% of days, "
      f"0 candidates on {pct_stage3_zero:.1f}% of days.")
    if pct_stage3_under5 > 50:
        A("FLAG: the full three-condition rule is under 5 candidates on a MAJORITY of days. "
          "Per instruction, this is reported for discussion before proceeding, not proceeded past silently.")
    else:
        A("Full rule clears 5+ candidates on a majority of days -- not flagged as routinely too restrictive "
          "by that specific bar, though see the percentile breakdown above for the full distribution.")

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_phase2_candidate_counts_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
