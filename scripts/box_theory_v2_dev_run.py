"""PREREGISTRATION_BOX_V2.md Process Step 3: run V2's DEV window only
(2016-10-04 to 2022-12-31) and produce the Section 8 report. Does NOT
authorize the sealed TEST window -- `box_theory.test_seal.guard_date_
range` is called with `authorize_test=False` against the DEV range,
a no-op since DEV never intersects the sealed window.

BASELINE is NOT recomputed here. It is reused directly from V1's own
data/box_theory/dev_baseline.pkl -- BASELINE (buy 09:30/sell 15:15,
every eligible top-200 DEV stock-day) depends only on the universe, the
window, and the cost model, none of which differ between V1 and V2;
recomputing it would mean rebuilding ~75 months of pools to reproduce a
number that cannot come out different. Stated here, not silently
reused (PREREGISTRATION_BOX_V2.md Section 6).

Checkpointed in stages, same discipline V1's dev run script was given
AFTER paying for its absence twice -- built in here from the start:
  1. v2_dev_trades.pkl
  2. v2_dev_inference.pkl
  3. v2_dev_timing_null.pkl    -- per-seed-batch checkpointed
  4. v2_dev_selection_null.pkl -- per-month checkpointed
  5. (baseline: reused from V1, no file of its own)
  6. v2_dev_report.json

Seed count (1000 vs 500) is decided from a timed small run, same
contingency as V1 -- and that SAME small run also measures peak process
memory (psutil, OS-tracked peak working set), BEFORE the real stage
commits to the full seed count. V1's first DEV run discovered a memory
problem reactively, deep into a slow run; this script checks before
committing, per instruction.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import psutil

from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con
from fibo.jump_guard import combined_unexplained_jump_dates

from box_theory import test_seal
from box_theory.v2 import run_backtest_v2, EXIT_STYLE
from box_theory.inference import day_clustered_bootstrap, percentile_vs_null, excludes_zero
from box_theory.nulls import build_timing_pool, timing_null_seed_mean, build_month_pool, selection_null_seed_mean

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
V1_BASELINE_PATH = ROOT / "data" / "box_theory" / "dev_baseline.pkl"

N_SEEDS_TARGET = 1000
N_SEEDS_FALLBACK = 500
SMALL_RUN_SEEDS = 20
TIME_BUDGET_SECONDS = 3600
CHECKPOINT_EVERY_SEEDS = 50
PEAK_MEMORY_WARN_MB = 1500  # log loudly if a 20-seed probe already approaches this

OUT_DIR = None
TRADES_PATH = INFERENCE_PATH = TIMING_NULL_PATH = SELECTION_NULL_PATH = None
TIMING_CHECKPOINT_PATH = SEL_CHECKPOINT_PATH = None
REPORT_PATH = LOG_PATH = None

proc = psutil.Process()


def log(msg) -> None:
    line = f"{dt.datetime.now().isoformat()} | {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _load_checkpoint(path):
    if path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def _save_checkpoint(path, state):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(state, f)
    tmp.replace(path)


def peak_wset_mb() -> float:
    mi = proc.memory_info()
    peak = getattr(mi, "peak_wset", None)
    return (peak / (1024 * 1024)) if peak is not None else float("nan")


def rss_mb() -> float:
    return proc.memory_info().rss / (1024 * 1024)


def decide_seed_count(small_run_seconds: float, small_run_n: int, label: str) -> int:
    projected_1000 = small_run_seconds / small_run_n * N_SEEDS_TARGET
    log(f"[{label}] {small_run_n}-seed timed run took {small_run_seconds:.1f}s -> "
        f"projected {N_SEEDS_TARGET}-seed runtime = {projected_1000/60:.1f} min")
    if projected_1000 > TIME_BUDGET_SECONDS:
        log(f"[{label}] projection exceeds ~1 hour -- using {N_SEEDS_FALLBACK} seeds instead of "
            f"{N_SEEDS_TARGET}, per PREREGISTRATION_BOX_V2.md Section 6's contingency")
        return N_SEEDS_FALLBACK
    return N_SEEDS_TARGET


def log_memory_checkpoint(label: str) -> float:
    """Logs current RSS and the OS-tracked PEAK working set reached so
    far in this process's lifetime. Called right after each pool build
    and again after each small probe, so a memory problem shows up in
    the log BEFORE the real stage commits to its full seed count --
    not discovered reactively, partway through a slow run, the way
    V1's first DEV attempt found its own retained-DataFrame bug."""
    peak = peak_wset_mb()
    log(f"[{label}] RSS {rss_mb():.0f} MB, peak working set so far {peak:.0f} MB")
    if peak > PEAK_MEMORY_WARN_MB:
        log(f"[{label}] WARNING: peak working set ({peak:.0f} MB) already exceeds the "
            f"{PEAK_MEMORY_WARN_MB} MB watch threshold -- check before committing to the full seed count.")
    return peak


def preflight_measure_timing(pool: list[dict]) -> float:
    """Runs SMALL_RUN_SEEDS TIMING-null draws against an already-built
    pool, logging per-seed time AND the peak memory reached, before the
    caller commits to the real seed count. Returns elapsed seconds."""
    log_memory_checkpoint("timing-pool-built")
    t0 = time.time()
    for s in range(SMALL_RUN_SEEDS):
        timing_null_seed_mean(pool, np.random.default_rng(s))
    elapsed = time.time() - t0
    log(f"[timing-probe] {SMALL_RUN_SEEDS} seeds in {elapsed:.1f}s")
    log_memory_checkpoint("timing-probe-done")
    return elapsed


def main(dev_start: dt.date, dev_end: dt.date, entity_ids: list[str] | None, smoke: bool):
    t_start = time.time()
    log(f"=== Box Theory V2 DEV run starting ({'SMOKE TEST' if smoke else 'REAL'}) ===")

    intraday_con = get_intraday_con(INTRADAY_DB)
    warehouse_con = get_warehouse_con(WAREHOUSE_DB)

    if not smoke:
        assert (dev_start, dev_end) == (test_seal.DEV_START, test_seal.DEV_END), \
            "real (non-smoke) run must use the exact frozen DEV window"
    test_seal.guard_date_range(dev_start, dev_end, authorize_test=False,
                                caller="box_theory_v2_dev_run.py", reason="V2 DEV-only run")
    log(f"DEV window: {dev_start} to {dev_end} (test_seal guard passed, authorize_test=False)"
        + (f", entity_ids restricted to {len(entity_ids)}" if entity_ids else ""))

    # ---------------- Stage 1: backtest ----------------
    if TRADES_PATH.exists():
        log(f"Stage 1 [backtest]: found existing {TRADES_PATH}, loading instead of re-running")
        with open(TRADES_PATH, "rb") as f:
            saved = pickle.load(f)
        trades, universe = saved["trades"], saved["universe"]
    else:
        log("Stage 1 [backtest]: running full V2 DEV backtest ...")
        t0 = time.time()
        result = run_backtest_v2(intraday_con, warehouse_con, dev_start, dev_end, entity_ids=entity_ids)
        trades, universe = result["trades"], result["universe"]
        if not trades.empty:
            trades["config"] = EXIT_STYLE  # "FAST" -- selects the single-red-candle exit in resolve_exit_arrays
        elapsed = time.time() - t0
        log(f"Stage 1 [backtest]: done in {elapsed/60:.1f} min -- {len(trades)} trades total, "
            f"skips={result['skips']}, diagnostics={result['diagnostics']}, errors={len(result['errors'])}")
        if result["errors"]:
            for e in result["errors"][:20]:
                log(f"  DAY ERROR: {e['entity_id']} {e['trade_date']}: {e['error']}")
        with open(TRADES_PATH, "wb") as f:
            pickle.dump({"trades": trades, "universe": universe, "skips": result["skips"],
                         "diagnostics": result["diagnostics"], "errors": result["errors"]}, f)
        log(f"Stage 1 [backtest]: saved to {TRADES_PATH}")

    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)

    # ---------------- Stage 2: inference ----------------
    if INFERENCE_PATH.exists():
        log(f"Stage 2 [inference]: found existing {INFERENCE_PATH}, loading")
        with open(INFERENCE_PATH, "rb") as f:
            inference = pickle.load(f)
    else:
        log("Stage 2 [inference]: day-clustered bootstrap, V2's single configuration ...")
        inference = day_clustered_bootstrap(trades, seed=0)
        log(f"  V2: n_trades={inference['n_trades']} n_days={inference['n_days']} "
            f"mean_net_r={inference['mean_net_r']:.4f} CI=[{inference['ci_low']:.4f},{inference['ci_high']:.4f}] "
            f"mde={inference['mde']:.4f}")
        with open(INFERENCE_PATH, "wb") as f:
            pickle.dump(inference, f)
        log(f"Stage 2 [inference]: saved to {INFERENCE_PATH}")

    if trades.empty or inference["n_trades"] == 0:
        log("=== V2 produced ZERO trades in DEV -- cannot run nulls or inference meaningfully. "
            "Reporting this as the result. ===")
        report = {
            "generated_at": dt.datetime.now().isoformat(), "window": "DEV", "study": "V2",
            "n_trades": 0, "DEV_PASS": False, "note": "zero trades produced",
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        return

    # ---------------- Stage 3: TIMING null ----------------
    if TIMING_NULL_PATH.exists():
        log(f"Stage 3 [timing null]: found existing {TIMING_NULL_PATH}, loading")
        with open(TIMING_NULL_PATH, "rb") as f:
            timing_result = pickle.load(f)
    else:
        ckpt = _load_checkpoint(TIMING_CHECKPOINT_PATH) or {}
        log(f"Stage 3 [timing null]: building pool for {len(trades)} trades ...")
        t0 = time.time()
        pool = build_timing_pool(intraday_con, warehouse_con, trades, rank_lookup, jump_dates_by_entity)
        log(f"  pool built in {time.time()-t0:.1f}s, size={len(pool)}")

        if ckpt.get("n_seeds") is not None:
            n_seeds = ckpt["n_seeds"]
            means = list(ckpt["means"])
            log(f"Stage 3 [timing null]: resuming at seed {len(means)}/{n_seeds} from checkpoint")
        else:
            # PRE-FLIGHT: timing AND peak memory, measured together, before
            # committing to the full seed count -- per instruction.
            elapsed = preflight_measure_timing(pool)
            n_seeds = decide_seed_count(elapsed, SMALL_RUN_SEEDS, "timing")
            means = [timing_null_seed_mean(pool, np.random.default_rng(s)) for s in range(SMALL_RUN_SEEDS)]
            means = means[:n_seeds]

        t0 = time.time()
        start_seed = len(means)
        for s in range(start_seed, n_seeds):
            means.append(timing_null_seed_mean(pool, np.random.default_rng(s)))
            if (s + 1) % CHECKPOINT_EVERY_SEEDS == 0 or (s + 1) == n_seeds:
                _save_checkpoint(TIMING_CHECKPOINT_PATH, {"means": means, "n_seeds": n_seeds})
                log(f"  timing: {s+1}/{n_seeds} seeds done ({time.time()-t0:.0f}s elapsed, checkpointed)")
        timing_result = {"means": np.array(means), "n_seeds": n_seeds, "pool_size": len(pool)}
        with open(TIMING_NULL_PATH, "wb") as f:
            pickle.dump(timing_result, f)
        log(f"Stage 3 [timing null]: saved to {TIMING_NULL_PATH}")
        if TIMING_CHECKPOINT_PATH.exists():
            TIMING_CHECKPOINT_PATH.unlink()
        del pool

    # ---------------- Stage 4: SELECTION null (V2's own trade-month set only) ----------------
    if SELECTION_NULL_PATH.exists():
        log(f"Stage 4 [selection null]: found existing {SELECTION_NULL_PATH}, loading")
        with open(SELECTION_NULL_PATH, "rb") as f:
            selection_result = pickle.load(f)
    else:
        trades_by_month = (
            trades.assign(ym=trades["trade_date"].apply(lambda d: (d.year, d.month)))
            .groupby("ym").size().to_dict()
        )
        all_months = sorted(trades_by_month.keys())
        log(f"Stage 4 [selection null]: {len(all_months)} distinct (year,month) pairs with real "
            f"V2 trades (matched counts: {trades_by_month})")

        ckpt = _load_checkpoint(SEL_CHECKPOINT_PATH)
        if ckpt is not None:
            n_seeds = ckpt["n_seeds"]
            seed_sums = ckpt["seed_sums"]
            seed_counts = ckpt["seed_counts"]
            completed_months = ckpt["completed_months"]
            log(f"Stage 4 [selection null]: resumed from checkpoint, "
                f"{len(completed_months)}/{len(all_months)} months already done")
        else:
            probe_year, probe_month = all_months[len(all_months) // 2]
            probe_count = trades_by_month[(probe_year, probe_month)]
            t0 = time.time()
            probe_pool = build_month_pool(intraday_con, warehouse_con, universe, probe_year, probe_month,
                                           rank_lookup, jump_dates_by_entity)
            probe_build_time = time.time() - t0
            log_memory_checkpoint("selection-probe-build")
            t0 = time.time()
            for s in range(SMALL_RUN_SEEDS):
                selection_null_seed_mean(probe_pool, probe_count,
                                          np.random.default_rng([s, probe_year, probe_month]), EXIT_STYLE)
            probe_draw_time = time.time() - t0
            projected_total = (
                probe_build_time * len(all_months)
                + (probe_draw_time / SMALL_RUN_SEEDS) * N_SEEDS_TARGET
            )
            log(f"Stage 4 [selection null]: probe month build={probe_build_time:.1f}s, "
                f"{SMALL_RUN_SEEDS}-seed draw time={probe_draw_time:.1f}s for {probe_count} draws/seed -- "
                f"projected FULL {N_SEEDS_TARGET}-seed runtime = {projected_total/60:.1f} min, "
                f"peak working set so far {peak_wset_mb():.0f} MB")
            n_seeds = N_SEEDS_FALLBACK if projected_total > TIME_BUDGET_SECONDS else N_SEEDS_TARGET
            if n_seeds == N_SEEDS_FALLBACK:
                log(f"Stage 4 [selection null]: projection exceeds budget -- using {N_SEEDS_FALLBACK} seeds "
                    f"instead of {N_SEEDS_TARGET}, per PREREGISTRATION_BOX_V2.md Section 6's contingency")
            del probe_pool

            seed_sums = np.zeros(n_seeds)
            seed_counts = np.zeros(n_seeds)
            completed_months = set()

        for mi, (year, month) in enumerate(all_months):
            if (year, month) in completed_months:
                continue
            count = trades_by_month[(year, month)]
            t0 = time.time()
            pool = build_month_pool(intraday_con, warehouse_con, universe, year, month,
                                     rank_lookup, jump_dates_by_entity)
            log(f"Stage 4 [selection null]: month {mi+1}/{len(all_months)} ({year}-{month:02d}) "
                f"pool built in {time.time()-t0:.1f}s, size={len(pool)}, matched count={count}")
            for s in range(n_seeds):
                rng = np.random.default_rng([s, year, month])
                draws = selection_null_seed_mean(pool, count, rng, EXIT_STYLE)
                if draws:
                    seed_sums[s] += sum(draws)
                    seed_counts[s] += len(draws)
            del pool
            completed_months.add((year, month))
            _save_checkpoint(SEL_CHECKPOINT_PATH, {
                "n_seeds": n_seeds, "seed_sums": seed_sums, "seed_counts": seed_counts,
                "completed_months": completed_months,
            })

        with np.errstate(invalid="ignore", divide="ignore"):
            means = np.where(seed_counts > 0, seed_sums / seed_counts, np.nan)
        selection_result = {"means": means, "n_seeds": n_seeds, "matched_counts_per_month": trades_by_month}
        with open(SELECTION_NULL_PATH, "wb") as f:
            pickle.dump(selection_result, f)
        log(f"Stage 4 [selection null]: saved to {SELECTION_NULL_PATH}")
        if SEL_CHECKPOINT_PATH.exists():
            SEL_CHECKPOINT_PATH.unlink()

    # ---------------- Stage 5: BASELINE (reused from V1, not recomputed) ----------------
    if V1_BASELINE_PATH.exists():
        with open(V1_BASELINE_PATH, "rb") as f:
            baseline_stats = pickle.load(f)
        log(f"Stage 5 [baseline]: REUSED from V1's {V1_BASELINE_PATH} (not recomputed -- "
            f"BASELINE depends only on universe/window/costs, identical for V1 and V2): {baseline_stats}")
    else:
        baseline_stats = {"note": "V1 baseline file not found -- not recomputed for V2, "
                                    "see PREREGISTRATION_BOX_V2.md Section 6"}
        log(f"Stage 5 [baseline]: WARNING -- {V1_BASELINE_PATH} not found, cannot reuse")

    # ---------------- Stage 6: final report ----------------
    timing_means = timing_result["means"]
    selection_means = selection_result["means"]
    valid_timing = timing_means[~np.isnan(timing_means)]
    valid_selection = selection_means[~np.isnan(selection_means)]
    pct_timing = percentile_vs_null(inference["mean_net_r"], valid_timing) if len(valid_timing) else float("nan")
    pct_selection = percentile_vs_null(inference["mean_net_r"], valid_selection) if len(valid_selection) else float("nan")

    by_year = trades.groupby("year")["net_r"].agg(["mean", "count"]).to_dict(orient="index")
    best_year = max(by_year, key=lambda y: by_year[y]["mean"]) if by_year else None
    ex_best = trades[trades["year"] != best_year] if best_year is not None else trades
    mean_ex_best = float(ex_best["net_r"].mean()) if len(ex_best) else float("nan")

    bands_1_100 = trades[trades["band"].isin(["1-50", "51-100"])]
    mean_bands_1_100 = float(bands_1_100["net_r"].mean()) if len(bands_1_100) else float("nan")

    exit_mix = trades["outcome"].value_counts().to_dict()
    armed_counts = trades["armed"].value_counts().to_dict()
    by_band = trades.groupby("band")["net_r"].agg(["mean", "count"]).to_dict(orient="index")
    which_candle_counts = trades["which_candle"].value_counts().to_dict()
    room_dist = trades["room_at_entry"].describe().to_dict()

    passes = (
        inference["mean_net_r"] > 0 and excludes_zero(inference["ci_low"], inference["ci_high"])
        and pct_timing >= 95.0 and pct_selection >= 95.0
        and mean_ex_best > 0
        and mean_bands_1_100 > 0
    )

    with open(TRADES_PATH, "rb") as f:
        saved = pickle.load(f)

    report = {
        "generated_at": dt.datetime.now().isoformat(), "window": "DEV", "study": "V2",
        "n_trades": inference["n_trades"], "n_days": inference["n_days"],
        "n_trades_vs_v1": {"v1_fast": 82365, "v1_slow": 100338, "v2": inference["n_trades"]},
        "win_rate": float((trades["net_r"] > 0).mean()) if len(trades) else float("nan"),
        "mean_net_r": inference["mean_net_r"], "median_net_r": inference["median_net_r"],
        "ci_low": inference["ci_low"], "ci_high": inference["ci_high"], "mde": inference["mde"],
        "timing_null_percentile": pct_timing, "selection_null_percentile": pct_selection,
        "timing_null_n_seeds": timing_result["n_seeds"], "selection_null_n_seeds": selection_result["n_seeds"],
        "selection_null_matched_counts_per_month": {f"{y}-{m:02d}": c for (y, m), c in
                                                      selection_result["matched_counts_per_month"].items()},
        "mean_net_r_excl_best_year": mean_ex_best, "best_year_excluded": best_year,
        "mean_net_r_bands_1_100": mean_bands_1_100,
        "exit_mix": exit_mix, "armed_counts": armed_counts, "by_year": by_year, "by_band": by_band,
        "which_candle_counts": which_candle_counts,
        "room_at_entry_distribution": room_dist,
        "time_exit_fallback_count": int(trades["time_exit_fallback"].sum()),
        "skipped_days": saved["skips"], "diagnostics": saved["diagnostics"],
        "day_errors": {"count": len(saved["errors"]), "is_finding": len(saved["errors"]) > 5,
                       "detail": [{"entity_id": e["entity_id"], "trade_date": str(e["trade_date"]),
                                    "error": e["error"]} for e in saved["errors"]]},
        "baseline": baseline_stats,
        "DEV_PASS": bool(passes),
    }
    log(f"=== V2 DEV result: PASS={passes} mean_net_r={inference['mean_net_r']:.4f} "
        f"CI=[{inference['ci_low']:.4f},{inference['ci_high']:.4f}] timing_pct={pct_timing:.1f} "
        f"selection_pct={pct_selection:.1f} ex_best_year={mean_ex_best:.4f} bands_1_100={mean_bands_1_100:.4f} "
        f"n_trades={inference['n_trades']} (vs V1 FAST 82365 / SLOW 100338) ===")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"Stage 6 [report]: saved to {REPORT_PATH}")
    log(f"=== Box Theory V2 DEV run complete in {(time.time()-t_start)/60:.1f} min total ===")


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke", action="store_true",
                    help="Tiny real-data integration check: a handful of entities, 2 months, "
                         "small seed counts, separate output dir (data/box_theory/v2_smoke/).")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.smoke:
        OUT_DIR = ROOT / "data" / "box_theory" / "v2_smoke"
        dev_start, dev_end = dt.date(2017, 1, 1), dt.date(2017, 12, 31)
        N_SEEDS_TARGET, SMALL_RUN_SEEDS = 10, 5
        tmp_con = get_intraday_con(INTRADAY_DB)
        entity_ids = [r[0] for r in tmp_con.execute(
            "select distinct entity_id from bars_1min where trade_date between '2017-01-01' and '2017-12-31' limit 80"
        ).fetchall()]
    else:
        OUT_DIR = ROOT / "data" / "box_theory" / "v2"
        dev_start, dev_end = test_seal.DEV_START, test_seal.DEV_END
        entity_ids = None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TRADES_PATH = OUT_DIR / "v2_dev_trades.pkl"
    INFERENCE_PATH = OUT_DIR / "v2_dev_inference.pkl"
    TIMING_NULL_PATH = OUT_DIR / "v2_dev_timing_null.pkl"
    SELECTION_NULL_PATH = OUT_DIR / "v2_dev_selection_null.pkl"
    TIMING_CHECKPOINT_PATH = OUT_DIR / "v2_dev_timing_null_checkpoint.pkl"
    SEL_CHECKPOINT_PATH = OUT_DIR / "v2_dev_selection_checkpoint.pkl"
    REPORT_PATH = OUT_DIR / "v2_dev_report.json"
    LOG_PATH = OUT_DIR / "v2_dev_run.log"

    main(dev_start, dev_end, entity_ids, args.smoke)
