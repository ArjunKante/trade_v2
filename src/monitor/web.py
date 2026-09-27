"""Assembles the JSON-serializable payload the screener web app's
momentum-persistence-monitor panel reads. Read-only; computed once, at
server startup, exactly like reports.screener_web.build_cache does for
the screener's own data. See src/monitor/persistence.py's module
docstring for the full "what this is and is not" statement -- not
repeated here.

Deliberately does NOT wire into the screener's own cache/filtering/
ranking in any way -- this module only builds a SEPARATE payload, merged
into the screener's cache dict under a "monitor" key by the caller
(scripts/serve_screener.py), and the web app exposes it via its own
`/api/monitor` route, read-only, no action taken on any value here.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from data_layer.entity_panel import read_full_entity_panel_authorized
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from monitor.persistence import (
    compute_daily_persistence, annual_mean_sign, mechanical_regimes,
    nonoverlapping_periods, rolling_mean_se, current_readout,
)


def _log_holdout_access(root) -> None:
    path = root / "data" / "holdout_access_log.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(
            f"{dt.datetime.now().isoformat()} | src/monitor/web.py (screener web app startup) | "
            f"authorize_holdout=True | DESCRIPTIVE, NON-EVALUATIVE regime-indicator audit "
            f"(momentum-persistence monitor panel) -- same reasoning as "
            f"scripts/run_momentum_persistence_monitor.py's own docstring, does NOT charge a "
            f"project-wide holdout slot under that reasoning, flagged as an inference not an "
            f"established rule\n"
        )


def build_monitor_payload(con: duckdb.DuckDBPyConnection, root, progress=print) -> dict:
    """Returns a dict ready for JSON serialization: per-period chart series
    (mean persistence, rolling mean, 95% CI band), the mechanical regime
    history, and the current plain-language readout. No threshold, no
    action, no ranking -- read-only description."""
    progress("Computing the momentum-persistence monitor (descriptive only, ~1 minute)...")
    _log_holdout_access(root)

    panel = read_full_entity_panel_authorized(con, authorize_holdout=True)
    jump_dates = unexplained_jump_boundaries(con, before=None)

    daily = compute_daily_persistence(panel, jump_dates)
    if daily.empty:
        return {"available": False}

    annual = annual_mean_sign(daily)
    regimes = mechanical_regimes(annual)
    periods = nonoverlapping_periods(daily)
    rolling = rolling_mean_se(periods)
    readout = current_readout(daily, periods, rolling)

    chart = periods.merge(
        rolling[["period_index", "rolling_mean", "ci_lo", "ci_hi"]],
        on="period_index", how="left",
    )
    chart_rows = []
    for _, r in chart.iterrows():
        chart_rows.append({
            "period_end": pd.Timestamp(r["period_end"]).date().isoformat(),
            "mean_persistence": float(r["mean_persistence"]),
            "rolling_mean": None if pd.isna(r["rolling_mean"]) else float(r["rolling_mean"]),
            "ci_lo": None if pd.isna(r["ci_lo"]) else float(r["ci_lo"]),
            "ci_hi": None if pd.isna(r["ci_hi"]) else float(r["ci_hi"]),
        })

    regime_rows = [
        {"start_year": r0, "end_year": r1, "sign": "positive" if s > 0 else "negative"}
        for r0, r1, s in regimes
    ]

    progress("Momentum-persistence monitor computed.")
    return {
        "available": True,
        "periods": chart_rows,
        "regimes": regime_rows,
        "readout": readout,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
