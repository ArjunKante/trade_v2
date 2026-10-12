"""Runs the study specified in PREREGISTRATION_OPTIONS.md, DEV and TEST
windows in the same run (so nothing can change between them), and
prints every figure that document commits to reporting. No definition
here was changed after seeing a number -- this script was written after
PREREGISTRATION_OPTIONS.md's amendment was committed and pushed on its
own (3974d09), and is being run for the first time right now.

Authorizes the sealed test window through src/options_history/
test_seal.py's one bypass path, which logs the access itself
(data/options_history/test_window_access_log.txt) -- not left to this
script to remember separately.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from data_layer.db import get_read_connection
from options_history.db import get_connection as get_options_connection
from options_history.study import (
    AUTOCORR_MATERIALITY, BLOCK_SIZE_IF_TRIGGERED, BOOTSTRAP_RESAMPLES,
    block_bootstrap_mean_ci, bootstrap_mean_ci, build_window, lag1_autocorrelation,
    trading_days_series,
)
from options_history.test_seal import DEV_END, DEV_START, TEST_END, TEST_START, guard_date_range

WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"


def summarize(label: str, obs: list) -> dict:
    kept = [o for o in obs if not o.dropped]
    dropped = [o for o in obs if o.dropped]
    r_values = [o.R for o in kept]
    realised = [o.realised_move for o in kept]

    autocorr = lag1_autocorrelation(r_values)
    threshold = AUTOCORR_MATERIALITY(len(r_values)) if len(r_values) > 0 else float("nan")
    material = abs(autocorr) > threshold if r_values and not np.isnan(autocorr) else False

    if material:
        ci_lo, ci_hi = block_bootstrap_mean_ci(r_values, block_size=BLOCK_SIZE_IF_TRIGGERED)
        bootstrap_kind = f"block bootstrap (block_size={BLOCK_SIZE_IF_TRIGGERED}, MATERIAL autocorrelation)"
    else:
        ci_lo, ci_hi = bootstrap_mean_ci(r_values) if r_values else (float("nan"), float("nan"))
        bootstrap_kind = "plain i.i.d. bootstrap (autocorrelation not material)"

    mean_r = float(np.mean(r_values)) if r_values else float("nan")
    median_r = float(np.median(r_values)) if r_values else float("nan")

    return {
        "label": label, "n_calendar_months": len(obs), "n_kept": len(kept), "n_dropped": len(dropped),
        "dropped_detail": [(o.expiry, o.reason) for o in dropped],
        "mean_R": mean_r, "median_R": median_r, "ci_lo": ci_lo, "ci_hi": ci_hi,
        "bootstrap_kind": bootstrap_kind, "autocorr": autocorr, "autocorr_threshold": threshold,
        "autocorr_material": material,
        "realised_move_mean": float(np.mean(realised)) if realised else float("nan"),
        "realised_move_median": float(np.median(realised)) if realised else float("nan"),
        "r_values": r_values, "kept_obs": kept,
    }


def print_summary(s: dict) -> None:
    print(f"\n=== {s['label']} ===")
    print(f"Calendar months in window: {s['n_calendar_months']}")
    print(f"Achieved n (kept): {s['n_kept']}")
    print(f"Dropped: {s['n_dropped']}")
    for expiry, reason in s["dropped_detail"]:
        print(f"  DROPPED {expiry}: {reason}")
    print(f"Mean R: {s['mean_R']:.4f}")
    print(f"  95% CI ({s['bootstrap_kind']}, {BOOTSTRAP_RESAMPLES} resamples): "
          f"[{s['ci_lo']:.4f}, {s['ci_hi']:.4f}]")
    print(f"Median R (descriptive, NOT the test): {s['median_R']:.4f}")
    print(f"Lag-1 autocorrelation of R: {s['autocorr']:.4f} "
          f"(materiality threshold 2/sqrt(n) = {s['autocorr_threshold']:.4f}, "
          f"{'MATERIAL -> block bootstrap used' if s['autocorr_material'] else 'not material -> plain bootstrap used'})")
    print(f"Secondary descriptive realised-move: mean={s['realised_move_mean']:.2f}, "
          f"median={s['realised_move_median']:.2f} (NIFTY points)")


def main() -> None:
    con_idx = get_read_connection(WAREHOUSE_DB)
    con_opts = get_options_connection()

    trading_days = trading_days_series(con_idx)

    # DEV needs no authorization -- entirely before the sealed window.
    guard_date_range(DEV_START, DEV_END)
    dev_obs = build_window(con_opts, con_idx, trading_days, DEV_START, DEV_END)

    # TEST is the sealed window -- the one authorized access, logged by
    # guard_date_range itself.
    guard_date_range(
        TEST_START, TEST_END, authorize_test=True,
        caller="scripts/run_options_study.py::main",
        reason="the single, real, end-of-study test evaluation specified in "
               "PREREGISTRATION_OPTIONS.md Section 5d, run once, same construction as DEV, "
               "approved by the user before this script was run.",
    )
    test_obs = build_window(con_opts, con_idx, trading_days, TEST_START, TEST_END)

    con_idx.close()
    con_opts.close()

    dev_summary = summarize("DEVELOPMENT (2016-01 to 2022-12)", dev_obs)
    print_summary(dev_summary)

    dev_ex2020_obs = [o for o in dev_obs if o.dropped or o.expiry.year != 2020]
    dev_ex2020_summary = summarize("DEVELOPMENT EXCLUDING 2020", dev_ex2020_obs)
    print_summary(dev_ex2020_summary)

    test_summary = summarize("TEST (2023-01 to 2026-09, SEALED)", test_obs)
    print_summary(test_summary)

    print("\n=== Section 5f decision rule ===")
    dev_sig_neg = dev_summary["mean_R"] < 0 and dev_summary["ci_hi"] < 0
    test_same_sign_neg = test_summary["mean_R"] < 0
    print(f"DEV mean R < 0 with CI excluding 0: {dev_sig_neg} "
          f"(mean={dev_summary['mean_R']:.4f}, CI=[{dev_summary['ci_lo']:.4f},{dev_summary['ci_hi']:.4f}])")
    print(f"TEST mean R < 0 (same sign, CI not required to exclude 0): {test_same_sign_neg} "
          f"(mean={test_summary['mean_R']:.4f}, CI=[{test_summary['ci_lo']:.4f},{test_summary['ci_hi']:.4f}])")

    if dev_sig_neg and test_same_sign_neg:
        verdict = "OPTIONS ARE SYSTEMATICALLY OVERPRICED (both conditions met)."
    elif dev_sig_neg and not test_same_sign_neg:
        verdict = "NOT ESTABLISHED -- DEV significant, TEST opposite sign (does not replicate directionally)."
    else:
        verdict = "NO DETECTABLE MISPRICING AT THIS SAMPLE SIZE (absence of evidence, not evidence of fairness)."
    print(f"\nVERDICT: {verdict}")


if __name__ == "__main__":
    main()
