"""PREREGISTRATION_IPO.md Process Step 5: run DEV only (real trades, then
TIMING null, then SELECTION null, checkpointed at each stage) and report
per Section 10. Never touches the sealed TEST window (ipo_listing.
test_seal's own DEV_END/TEST_START constants bound every query here).
"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ipo_listing.backtest import load_usable_listings, load_day_bars, run_backtest
from ipo_listing.intraday_db import get_read_connection
from ipo_listing.costs import COST_SCENARIOS_BPS
from ipo_listing import test_seal
from ipo_listing.nulls import run_timing_null, _run_timing_trial
from box_theory.inference import day_clustered_bootstrap, excludes_zero, percentile_vs_null

ROOT = Path(__file__).resolve().parents[1]
INTRADAY_DB = ROOT / "data" / "ipo_listing" / "ipo_intraday.duckdb"
RESULTS_PATH = ROOT / "data" / "ipo_listing" / "dev_run_results.json"

N_SEEDS_TARGET = 1000
PROBE_SEEDS = 20
TIMING_BUDGET_SECONDS = 3600  # ~1 hour, same contingency convention as prior studies


def main():
    print(f"=== IPO listing DEV run starting {dt.datetime.now()} ===", flush=True)
    icon = get_read_connection(INTRADAY_DB)

    listings = load_usable_listings(icon)
    dev_listings = listings[pd.to_datetime(listings["listing_date"]) <= pd.Timestamp(test_seal.DEV_END)].copy()
    assert len(dev_listings) == test_seal.N_DEV, \
        f"DEV count mismatch: got {len(dev_listings)}, sealed N_DEV={test_seal.N_DEV}"
    print(f"DEV usable listings: {len(dev_listings)} (through {test_seal.DEV_END}, sealed)", flush=True)

    # ---- Stage 1: real strategy ----
    t0 = time.time()
    real = run_backtest(icon, dev_listings, ignore_color=False)
    print(f"Stage 1 (real strategy) done in {time.time()-t0:.1f}s. "
          f"Status counts:\n{real['status'].value_counts().to_string()}", flush=True)

    entered = real[real["status"] == "ENTERED"].copy()
    entered["listing_date"] = pd.to_datetime(entered["listing_date"])
    entered["year"] = entered["listing_date"].dt.year
    entered = entered.rename(columns={"listing_date": "trade_date"})

    skipped_red_flat = int((real["status"] == "SKIPPED_RED_OR_FLAT").sum())
    no_fill_bar = int((real["status"] == "NO_FILL_BAR").sum())
    zero_qty = int((real["status"] == "ZERO_QTY").sum())
    n_trades = len(entered)
    win_rate = float((entered["net_r_7bps"] > 0).mean()) * 100.0 if n_trades else float("nan")
    exit_mix = entered["exit_outcome"].value_counts().to_dict()
    time_exit_fallback_count = int(entered["time_exit_fallback"].sum())

    boot = day_clustered_bootstrap(entered, net_r_col="net_r_7bps")
    mde = boot["mde"]
    mean_7 = boot["mean_net_r"]
    ci_low, ci_high = boot["ci_low"], boot["ci_high"]
    dev_pass_ci = excludes_zero(ci_low, ci_high) and mean_7 > 0

    mean_14 = float(entered["net_r_14bps"].mean()) if n_trades else float("nan")
    mean_28 = float(entered["net_r_28bps"].mean()) if n_trades else float("nan")
    dev_pass_2x_cost = mean_14 > 0

    by_year = entered.groupby("year")["net_r_7bps"].agg(["mean", "count"])
    print(f"By year (net R, 7bps):\n{by_year.to_string()}", flush=True)
    if len(by_year):
        best_year = by_year["mean"].idxmax()
        ex_best = entered[entered["year"] != best_year]
        mean_ex_best = float(ex_best["net_r_7bps"].mean()) if len(ex_best) else float("nan")
    else:
        best_year, mean_ex_best = None, float("nan")
    dev_pass_ex_best_year = mean_ex_best > 0

    print(f"Stage 1 summary: n_trades={n_trades} win_rate={win_rate:.2f}% "
          f"mean_net_r_7bps={mean_7:.4f} CI=[{ci_low:.4f},{ci_high:.4f}] MDE={mde:.4f}", flush=True)

    # ---- Stage 2: TIMING null ----
    t0 = time.time()
    bars_by_listing = {int(lid): load_day_bars(icon, int(lid)) for lid in entered["listing_id"]}
    rng_probe = np.random.default_rng(0)
    probe_means = []
    for s in range(PROBE_SEEDS):
        rng = np.random.default_rng(s)
        vals = []
        for lid, bars in bars_by_listing.items():
            v = _run_timing_trial(bars, rng)
            if v is not None:
                vals.append(v)
        probe_means.append(np.mean(vals) if vals else np.nan)
    probe_elapsed = time.time() - t0
    projected_full = probe_elapsed / PROBE_SEEDS * N_SEEDS_TARGET
    n_seeds_timing = N_SEEDS_TARGET if projected_full <= TIMING_BUDGET_SECONDS else 500
    print(f"TIMING null preflight: {PROBE_SEEDS} seeds took {probe_elapsed:.1f}s, "
          f"projected {N_SEEDS_TARGET} seeds = {projected_full:.1f}s -> using {n_seeds_timing} seeds", flush=True)

    t0 = time.time()
    timing_null_means = run_timing_null(bars_by_listing, n_seeds_timing)
    print(f"Stage 2 (TIMING null, {n_seeds_timing} seeds) done in {time.time()-t0:.1f}s", flush=True)
    timing_pct = percentile_vs_null(mean_7, timing_null_means)
    dev_pass_timing = timing_pct >= 95.0

    # ---- Stage 3: SELECTION null ----
    t0 = time.time()
    selection_trades = run_backtest(icon, dev_listings, ignore_color=True)
    selection_entered = selection_trades[selection_trades["status"] == "ENTERED"].copy()
    selection_entered["listing_date"] = pd.to_datetime(selection_entered["listing_date"])
    selection_entered = selection_entered.rename(columns={"listing_date": "trade_date"})
    sel_boot = day_clustered_bootstrap(selection_entered, net_r_col="net_r_7bps")
    selection_pct = percentile_vs_null(mean_7, sel_boot["resample_means"])
    dev_pass_selection = selection_pct >= 95.0
    print(f"Stage 3 (SELECTION null, {len(selection_entered)} alternate trades) done in {time.time()-t0:.1f}s. "
          f"Alternate mean_net_r_7bps={sel_boot['mean_net_r']:.4f}", flush=True)

    dev_pass = dev_pass_ci and dev_pass_timing and dev_pass_selection and dev_pass_ex_best_year and dev_pass_2x_cost

    # ---- Report ----
    print("\n" + "=" * 70)
    print(f"DEV_PASS = {dev_pass}")
    print("=" * 70)
    print(f"MDE = {mde:.4f} (sample size n_trades={n_trades}, n_days={boot['n_days']}) -- "
          f"STATED PROMINENTLY per instruction, given the {len(dev_listings)}-listing DEV sample.")
    print(f"Trades taken: {n_trades} / Skipped (red/flat first candle): {skipped_red_flat} "
          f"/ NO_FILL_BAR: {no_fill_bar} / ZERO_QTY: {zero_qty}")
    print(f"Win rate: {win_rate:.2f}%")
    print(f"Mean net R (7bps): {mean_7:.4f}  97.5% CI=[{ci_low:.4f},{ci_high:.4f}]  "
          f"excludes_zero={excludes_zero(ci_low, ci_high)}")
    print(f"Median net R (7bps, descriptive): {boot['median_net_r']:.4f}")
    print(f"Cost sensitivity -- mean net R: 7bps={mean_7:.4f}  14bps={mean_14:.4f}  28bps={mean_28:.4f}")
    print(f"Ex-best-year (drops {best_year}) mean net R: {mean_ex_best:.4f}")
    print(f"Exit mix: {exit_mix}  time_exit_fallback_count={time_exit_fallback_count}")
    print(f"TIMING null: {n_seeds_timing} seeds, real mean percentile = {timing_pct:.1f}")
    print(f"SELECTION null: {len(selection_entered)} alternate trades, 10000 bootstrap resamples, "
          f"real mean percentile = {selection_pct:.1f}")
    print(f"Gate components: CI_excludes_zero_and_positive={dev_pass_ci}  "
          f"timing>=95th={dev_pass_timing}  selection>=95th={dev_pass_selection}  "
          f"ex_best_year>0={dev_pass_ex_best_year}  2x_cost>0={dev_pass_2x_cost}")

    results = {
        "generated_at": dt.datetime.now().isoformat(),
        "n_dev_listings": len(dev_listings),
        "n_trades": n_trades, "skipped_red_flat": skipped_red_flat,
        "no_fill_bar": no_fill_bar, "zero_qty": zero_qty,
        "win_rate_pct": win_rate,
        "mean_net_r_7bps": mean_7, "ci_low": ci_low, "ci_high": ci_high, "mde": mde,
        "median_net_r_7bps": boot["median_net_r"], "n_days": boot["n_days"],
        "mean_net_r_14bps": mean_14, "mean_net_r_28bps": mean_28,
        "best_year": int(best_year) if best_year is not None else None,
        "mean_net_r_ex_best_year": mean_ex_best,
        "exit_mix": exit_mix, "time_exit_fallback_count": time_exit_fallback_count,
        "by_year": by_year.reset_index().to_dict("records"),
        "n_seeds_timing": n_seeds_timing, "timing_null_percentile": timing_pct,
        "selection_null_percentile": selection_pct, "n_selection_alt_trades": len(selection_entered),
        "selection_alt_mean_net_r_7bps": sel_boot["mean_net_r"],
        "dev_pass": dev_pass,
        "gate_components": {
            "ci_excludes_zero_and_positive": dev_pass_ci, "timing_ge_95th": dev_pass_timing,
            "selection_ge_95th": dev_pass_selection, "ex_best_year_positive": dev_pass_ex_best_year,
            "cost_2x_positive": dev_pass_2x_cost,
        },
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
