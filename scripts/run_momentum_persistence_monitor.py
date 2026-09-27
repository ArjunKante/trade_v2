"""THE MOMENTUM PERSISTENCE MONITOR -- descriptive only. Run this to
compute and log the CURRENT reading. See src/monitor/persistence.py's
module docstring for the full "what this is and is not" statement, the
statistic's exact definition, the lag explanation, and the Study-3/
trade-new-holdout firewall reasoning -- not repeated in full here.

THIS SCRIPT, LIKE `scripts/run_holdout_study1.py` and
`scripts/run_swing_v1_holdout.py` before it, PASSES `authorize_holdout=
True`. Per `FINDINGS.md` Section 7 (updated) and
`src/monitor/persistence.py`'s own docstring: the historical holdout
(`SEALED_HOLDOUT_START` onward) is now RETIRED, not merely "not charged"
-- a window this monitor reads on every run is not sealed in any
meaningful sense, and it had already been read twice by actual strategies
before this monitor existed. Every run is still logged to
`data/holdout_access_log.txt` for the audit trail, but that log no longer
represents a resource being preserved -- there is nothing left to spend.

Appends exactly ONE row to `monitor_logs/momentum_persistence_log.csv`
per run -- never rewrites a past row. That file is committed with the
code (it is NOT under `data/`, which is gitignored, specifically so this
audit trail survives in git history).

Usage:
    python scripts/run_momentum_persistence_monitor.py
"""
from __future__ import annotations

import csv
import datetime as dt
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_full_entity_panel_authorized
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from monitor.persistence import (
    compute_daily_persistence, annual_mean_sign, mechanical_regimes,
    nonoverlapping_periods, rolling_mean_se, current_readout,
    same_isin_jump_excluded_entities,
)

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT_LOG_PATH = ROOT / "data" / "holdout_access_log.txt"
MONITOR_LOG_PATH = ROOT / "monitor_logs" / "momentum_persistence_log.csv"
MONITOR_LOG_HEADER = [
    "run_timestamp", "latest_signal_date", "measured_through_date",
    "latest_value", "rolling_mean", "se", "regime_label",
]


def _append_holdout_access_log() -> None:
    HOLDOUT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HOLDOUT_LOG_PATH, "a") as f:
        f.write(
            f"{dt.datetime.now().isoformat()} | scripts/run_momentum_persistence_monitor.py | "
            f"authorize_holdout=True | DESCRIPTIVE, NON-EVALUATIVE regime-indicator audit "
            f"(momentum-persistence monitor, src/monitor/persistence.py) -- read against the "
            f"HISTORICAL HOLDOUT, now RETIRED per FINDINGS.md Section 7 (a window this monitor "
            f"reads on every run is not sealed in any meaningful sense; already read twice by "
            f"actual strategies before this monitor existed). This log entry is an audit-trail "
            f"record of when data was read, not a charge against a resource that still exists\n"
        )


def _append_monitor_log(row: dict) -> None:
    MONITOR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not MONITOR_LOG_PATH.exists()
    with open(MONITOR_LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MONITOR_LOG_HEADER)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    _append_holdout_access_log()
    print(f"Holdout access logged (descriptive, non-evaluative -- see script docstring) to {HOLDOUT_LOG_PATH}",
          file=sys.stderr, flush=True)

    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
    excluded = same_isin_jump_excluded_entities(con)  # BUGS.md Bug #11
    panel_all = read_full_entity_panel_authorized(con, authorize_holdout=True)
    panel = panel_all[~panel_all["entity_id"].isin(excluded)].reset_index(drop=True)
    jump_dates = unexplained_jump_boundaries(con, before=None)  # full-range gap guard
    con.close()
    print(f"Excluded {len(excluded)} same-ISIN-jump entities (BUGS.md Bug #11)", file=sys.stderr)

    daily = compute_daily_persistence(panel, jump_dates)
    if daily.empty:
        print("No qualifying persistence value could be computed (insufficient cross-section or history).",
              file=sys.stderr)
        return 1

    annual = annual_mean_sign(daily)
    regimes = mechanical_regimes(annual)
    periods = nonoverlapping_periods(daily)
    rolling = rolling_mean_se(periods)
    readout = current_readout(daily, periods, rolling)

    lines = []
    A = lines.append
    A("=" * 100)
    A("MOMENTUM PERSISTENCE MONITOR -- DESCRIPTIVE ONLY")
    A("Measures whether momentum_12_1 has recently been ranking stocks in the order their subsequent")
    A("returns turned out. Does NOT predict returns, does NOT change any position, emits no signal,")
    A("and makes no claim that any regime will persist.")
    A("=" * 100)

    A(f"\n{readout['lag_sentence']}")
    if readout.get("rolling_mean") is not None:
        A(f"Rolling mean (trailing {12} non-overlapping 63-day periods): "
          f"{readout['rolling_mean']:+.4f}  SE={readout['se']:.4f}  "
          f"95% CI=[{readout['ci_lo']:+.4f}, {readout['ci_hi']:+.4f}]")
    A(f"Label: {readout['label']}")

    A(f"\n--- Mechanical regime history (annual mean sign, contiguous runs) ---")
    for r0, r1, s in regimes:
        label = f"{r0}" if r0 == r1 else f"{r0}-{r1}"
        A(f"  {label}: sign={'+' if s > 0 else '-'}")
    A(f"  ({len(regimes)} distinct regimes on record)")

    report = "\n".join(lines)
    print(report)

    _append_monitor_log({
        "run_timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "latest_signal_date": readout["latest_signal_date"],
        "measured_through_date": readout["measured_through"],
        "latest_value": f"{readout['latest_value']:.6f}",
        "rolling_mean": f"{readout['rolling_mean']:.6f}" if readout.get("rolling_mean") is not None else "",
        "se": f"{readout['se']:.6f}" if readout.get("se") is not None else "",
        "regime_label": readout["label"],
    })
    print(f"\nAppended one row to {MONITOR_LOG_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
