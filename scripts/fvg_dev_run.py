"""PREREGISTRATION_FVG.md Process Step 3: run the FVG study's DEV window
only (2016-10-04 to 2022-12-31) and produce the Section 10 report for
BOTH configurations. Does NOT authorize the sealed TEST window --
`fvg.test_seal.guard_date_range` is called with `authorize_test=False`
against the DEV range, a no-op since DEV never intersects the sealed
window.

BASELINE is NOT recomputed. It is reused directly from box theory's own
`data/box_theory/dev_baseline.pkl` -- BASELINE (buy 09:30 open / sell
15:15 close, every eligible top-200 DEV stock-day) depends only on the
universe, the DEV window, and the cost model, all three identical
between box theory and this study. Stated here, not silently reused
(PREREGISTRATION_FVG.md Section 0/8).

Checkpointed in stages from the start (per instruction, not added
reactively): 1 backtest, 2 inference (per config), 3 TIMING null (per
config, per-seed-batch checkpointed), 4 SELECTION null (per config,
per-month checkpointed), 5 baseline (reused, no file), 6 report.

Seed count (1000 vs 500), per null, per configuration, decided from a
timed small run that ALSO measures peak process memory (psutil) BEFORE
either null's real stage commits to the full count -- per instruction.
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

from fvg import test_seal
from fvg.backtest import run_backtest, CONFIG_NAMES
from box_theory.inference import day_clustered_bootstrap, percentile_vs_null, excludes_zero
from fvg.nulls import build_timing_pool, timing_null_seed_mean, build_month_pool, selection_null_seed_mean

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
V1_BASELINE_PATH = ROOT / "data" / "box_theory" / "dev_baseline.pkl"

N_SEEDS_TARGET = 1000
N_SEEDS_FALLBACK = 500
SMALL_RUN_SEEDS = 20
TIME_BUDGET_SECONDS = 3600
CHECKPOINT_EVERY_SEEDS = 50
PEAK_MEMORY_WARN_MB = 2000

OUT_DIR = None
TRADES_PATH = INFERENCE_PATH = REPORT_PATH = LOG_PATH = None

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


def log_memory_checkpoint(label: str) -> float:
    peak = peak_wset_mb()
    log(f"[{label}] RSS {rss_mb():.0f} MB, peak working set so far {peak:.0f} MB")
    if peak > PEAK_MEMORY_WARN_MB:
        log(f"[{label}] WARNING: peak working set ({peak:.0f} MB) exceeds the "
            f"{PEAK_MEMORY_WARN_MB} MB watch threshold -- check before committing to the full seed count.")
    return peak


def decide_seed_count(small_run_seconds: float, small_run_n: int, label: str) -> int:
    projected_1000 = small_run_seconds / small_run_n * N_SEEDS_TARGET
    log(f"[{label}] {small_run_n}-seed timed run took {small_run_seconds:.1f}s -> "
        f"projected {N_SEEDS_TARGET}-seed runtime = {projected_1000/60:.1f} min")
    if projected_1000 > TIME_BUDGET_SECONDS:
        log(f"[{label}] projection exceeds ~1 hour -- using {N_SEEDS_FALLBACK} seeds instead of "
            f"{N_SEEDS_TARGET}, per PREREGISTRATION_FVG.md Section 8's contingency")
        return N_SEEDS_FALLBACK
    return N_SEEDS_TARGET


def run_timing_null(config: str, trades: pd.DataFrame, intraday_con, warehouse_con,
                     rank_lookup: dict, jump_dates_by_entity: dict) -> dict:
    path = OUT_DIR / f"fvg_dev_timing_null_{config}.pkl"
    ckpt_path = OUT_DIR / f"fvg_dev_timing_null_{config}_checkpoint.pkl"
    if path.exists():
        log(f"Stage 3 [timing null {config}]: found existing {path}, loading")
        with open(path, "rb") as f:
            return pickle.load(f)

    log(f"Stage 3 [timing null {config}]: building pool for {len(trades)} trades ...")
    t0 = time.time()
    pool = build_timing_pool(intraday_con, warehouse_con, trades, rank_lookup, jump_dates_by_entity)
    log(f"  [{config}] pool built in {time.time()-t0:.1f}s, size={len(pool)}")
    log_memory_checkpoint(f"timing-{config}-pool-built")

    ckpt = _load_checkpoint(ckpt_path) or {}
    if ckpt.get("n_seeds") is not None:
        n_seeds = ckpt["n_seeds"]
        means = list(ckpt["means"])
        log(f"Stage 3 [timing null {config}]: resuming at seed {len(means)}/{n_seeds} from checkpoint")
    else:
        t0 = time.time()
        for s in range(SMALL_RUN_SEEDS):
            timing_null_seed_mean(pool, np.random.default_rng(s))
        elapsed = time.time() - t0
        log(f"  [{config}] {SMALL_RUN_SEEDS}-seed probe in {elapsed:.1f}s")
        log_memory_checkpoint(f"timing-{config}-probe-done")
        n_seeds = decide_seed_count(elapsed, SMALL_RUN_SEEDS, f"timing-{config}")
        means = [timing_null_seed_mean(pool, np.random.default_rng(s)) for s in range(SMALL_RUN_SEEDS)]
        means = means[:n_seeds]

    t0 = time.time()
    start_seed = len(means)
    for s in range(start_seed, n_seeds):
        means.append(timing_null_seed_mean(pool, np.random.default_rng(s)))
        if (s + 1) % CHECKPOINT_EVERY_SEEDS == 0 or (s + 1) == n_seeds:
            _save_checkpoint(ckpt_path, {"means": means, "n_seeds": n_seeds})
            log(f"  [{config}] timing: {s+1}/{n_seeds} seeds done ({time.time()-t0:.0f}s elapsed, checkpointed)")

    result = {"means": np.array(means), "n_seeds": n_seeds, "pool_size": len(pool)}
    with open(path, "wb") as f:
        pickle.dump(result, f)
    log(f"Stage 3 [timing null {config}]: saved to {path}")
    if ckpt_path.exists():
        ckpt_path.unlink()
    return result


def run_selection_null(config: str, trades: pd.DataFrame, universe: pd.DataFrame, intraday_con, warehouse_con,
                        rank_lookup: dict, jump_dates_by_entity: dict) -> dict:
    path = OUT_DIR / f"fvg_dev_selection_null_{config}.pkl"
    ckpt_path = OUT_DIR / f"fvg_dev_selection_{config}_checkpoint.pkl"
    if path.exists():
        log(f"Stage 4 [selection null {config}]: found existing {path}, loading")
        with open(path, "rb") as f:
            return pickle.load(f)

    room_pct_pool = trades["room_pct"].to_numpy()
    trades_by_month = (
        trades.assign(ym=trades["trade_date"].apply(lambda d: (d.year, d.month)))
        .groupby("ym").size().to_dict()
    )
    all_months = sorted(trades_by_month.keys())
    log(f"Stage 4 [selection null {config}]: {len(all_months)} distinct (year,month) pairs with real "
        f"trades (matched counts: {trades_by_month})")

    ckpt = _load_checkpoint(ckpt_path)
    if ckpt is not None:
        n_seeds = ckpt["n_seeds"]
        seed_sums, seed_counts = ckpt["seed_sums"], ckpt["seed_counts"]
        completed_months = ckpt["completed_months"]
        log(f"Stage 4 [selection null {config}]: resumed, {len(completed_months)}/{len(all_months)} months done")
    else:
        probe_year, probe_month = all_months[len(all_months) // 2]
        probe_count = trades_by_month[(probe_year, probe_month)]
        t0 = time.time()
        probe_pool = build_month_pool(intraday_con, warehouse_con, universe, probe_year, probe_month,
                                       rank_lookup, jump_dates_by_entity)
        probe_build_time = time.time() - t0
        log_memory_checkpoint(f"selection-{config}-probe-build")
        t0 = time.time()
        for s in range(SMALL_RUN_SEEDS):
            selection_null_seed_mean(probe_pool, probe_count, np.random.default_rng([s, probe_year, probe_month]),
                                      room_pct_pool)
        probe_draw_time = time.time() - t0
        projected_total = (
            probe_build_time * len(all_months) + (probe_draw_time / SMALL_RUN_SEEDS) * N_SEEDS_TARGET
        )
        log(f"Stage 4 [selection null {config}]: probe month build={probe_build_time:.1f}s, "
            f"{SMALL_RUN_SEEDS}-seed draw time={probe_draw_time:.1f}s for {probe_count} draws/seed -- "
            f"projected FULL {N_SEEDS_TARGET}-seed runtime = {projected_total/60:.1f} min, "
            f"peak working set so far {peak_wset_mb():.0f} MB")
        n_seeds = N_SEEDS_FALLBACK if projected_total > TIME_BUDGET_SECONDS else N_SEEDS_TARGET
        if n_seeds == N_SEEDS_FALLBACK:
            log(f"Stage 4 [selection null {config}]: projection exceeds budget -- using {N_SEEDS_FALLBACK} seeds")
        del probe_pool
        seed_sums = np.zeros(n_seeds)
        seed_counts = np.zeros(n_seeds)
        completed_months = set()

    for mi, (year, month) in enumerate(all_months):
        if (year, month) in completed_months:
            continue
        count = trades_by_month[(year, month)]
        t0 = time.time()
        pool = build_month_pool(intraday_con, warehouse_con, universe, year, month, rank_lookup, jump_dates_by_entity)
        log(f"Stage 4 [selection null {config}]: month {mi+1}/{len(all_months)} ({year}-{month:02d}) "
            f"pool built in {time.time()-t0:.1f}s, size={len(pool)}, matched count={count}")
        for s in range(n_seeds):
            rng = np.random.default_rng([s, year, month, hash(config) % 1000])
            draws = selection_null_seed_mean(pool, count, rng, room_pct_pool)
            if draws:
                seed_sums[s] += sum(draws)
                seed_counts[s] += len(draws)
        del pool
        completed_months.add((year, month))
        _save_checkpoint(ckpt_path, {
            "n_seeds": n_seeds, "seed_sums": seed_sums, "seed_counts": seed_counts,
            "completed_months": completed_months,
        })

    with np.errstate(invalid="ignore", divide="ignore"):
        means = np.where(seed_counts > 0, seed_sums / seed_counts, np.nan)
    result = {"means": means, "n_seeds": n_seeds, "matched_counts_per_month": trades_by_month}
    with open(path, "wb") as f:
        pickle.dump(result, f)
    log(f"Stage 4 [selection null {config}]: saved to {path}")
    if ckpt_path.exists():
        ckpt_path.unlink()
    return result


def main(dev_start: dt.date, dev_end: dt.date, entity_ids, smoke: bool):
    t_start = time.time()
    log(f"=== FVG DEV run starting ({'SMOKE TEST' if smoke else 'REAL'}) ===")

    intraday_con = get_intraday_con(INTRADAY_DB)
    warehouse_con = get_warehouse_con(WAREHOUSE_DB)

    if not smoke:
        assert (dev_start, dev_end) == (test_seal.DEV_START, test_seal.DEV_END), \
            "real (non-smoke) run must use the exact frozen DEV window"
    test_seal.guard_date_range(dev_start, dev_end, authorize_test=False,
                                caller="fvg_dev_run.py", reason="FVG DEV-only run")
    log(f"DEV window: {dev_start} to {dev_end} (test_seal guard passed, authorize_test=False)"
        + (f", entity_ids restricted to {len(entity_ids)}" if entity_ids else ""))

    # ---------------- Stage 1: backtest ----------------
    if TRADES_PATH.exists():
        log(f"Stage 1 [backtest]: found existing {TRADES_PATH}, loading instead of re-running")
        with open(TRADES_PATH, "rb") as f:
            saved = pickle.load(f)
        trades, universe = saved["trades"], saved["universe"]
        skips, diagnostics = saved["skips"], saved["diagnostics"]
        total_gaps, inside_bar_rejected = saved["total_gaps"], saved["inside_bar_rejected"]
        overnight_excluded, errors = saved["overnight_excluded"], saved["errors"]
    else:
        log("Stage 1 [backtest]: running full FVG DEV backtest (both configurations) ...")
        t0 = time.time()
        result = run_backtest(intraday_con, warehouse_con, dev_start, dev_end, entity_ids=entity_ids)
        trades, universe = result["trades"], result["universe"]
        skips, diagnostics = result["skips"], result["diagnostics"]
        total_gaps, inside_bar_rejected = result["total_gaps"], result["inside_bar_rejected"]
        overnight_excluded, errors = result["overnight_excluded"], result["errors"]
        elapsed = time.time() - t0
        log(f"Stage 1 [backtest]: done in {elapsed/60:.1f} min -- "
            f"A={len(trades['A'])} trades, B={len(trades['B'])} trades, "
            f"total_gaps={total_gaps}, inside_bar_rejected={inside_bar_rejected}, "
            f"overnight_excluded={overnight_excluded}, skips={skips}, errors={len(errors)}")
        if errors:
            for e in errors[:20]:
                log(f"  DAY ERROR: {e}")
        with open(TRADES_PATH, "wb") as f:
            pickle.dump({
                "trades": trades, "universe": universe, "skips": skips, "diagnostics": diagnostics,
                "total_gaps": total_gaps, "inside_bar_rejected": inside_bar_rejected,
                "overnight_excluded": overnight_excluded, "errors": errors,
            }, f)
        log(f"Stage 1 [backtest]: saved to {TRADES_PATH}")

    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)

    per_config_report = {}
    for config in CONFIG_NAMES:
        cdf = trades[config]
        log(f"=== Configuration {config}: {len(cdf)} trades ===")
        if cdf.empty:
            per_config_report[config] = {"n_trades": 0, "DEV_PASS": False, "note": "zero trades produced"}
            continue

        # ---------------- Stage 2: inference ----------------
        inf_path = OUT_DIR / f"fvg_dev_inference_{config}.pkl"
        if inf_path.exists():
            with open(inf_path, "rb") as f:
                inference = pickle.load(f)
        else:
            inference = day_clustered_bootstrap(cdf, seed=0)
            with open(inf_path, "wb") as f:
                pickle.dump(inference, f)
        log(f"Stage 2 [inference {config}]: n_trades={inference['n_trades']} n_days={inference['n_days']} "
            f"mean_net_r={inference['mean_net_r']:.4f} CI=[{inference['ci_low']:.4f},{inference['ci_high']:.4f}] "
            f"mde={inference['mde']:.4f}")

        # ---------------- Stage 3: TIMING null ----------------
        timing_result = run_timing_null(config, cdf, intraday_con, warehouse_con, rank_lookup, jump_dates_by_entity)

        # ---------------- Stage 4: SELECTION null ----------------
        selection_result = run_selection_null(config, cdf, universe, intraday_con, warehouse_con,
                                               rank_lookup, jump_dates_by_entity)

        timing_means = timing_result["means"]
        selection_means = selection_result["means"]
        valid_timing = timing_means[~np.isnan(timing_means)]
        valid_selection = selection_means[~np.isnan(selection_means)]
        pct_timing = percentile_vs_null(inference["mean_net_r"], valid_timing) if len(valid_timing) else float("nan")
        pct_selection = percentile_vs_null(inference["mean_net_r"], valid_selection) if len(valid_selection) else float("nan")

        by_year = cdf.groupby("year")["net_r"].agg(["mean", "count"]).to_dict(orient="index")
        best_year = max(by_year, key=lambda y: by_year[y]["mean"]) if by_year else None
        ex_best = cdf[cdf["year"] != best_year] if best_year is not None else cdf
        mean_ex_best = float(ex_best["net_r"].mean()) if len(ex_best) else float("nan")

        bands_1_100 = cdf[cdf["band"].isin(["1-50", "51-100"])]
        mean_bands_1_100 = float(bands_1_100["net_r"].mean()) if len(bands_1_100) else float("nan")

        exit_mix = cdf["outcome"].value_counts().to_dict()
        by_band = cdf.groupby("band")["net_r"].agg(["mean", "count"]).to_dict(orient="index")

        passes = (
            inference["mean_net_r"] > 0 and excludes_zero(inference["ci_low"], inference["ci_high"])
            and pct_timing >= 95.0 and pct_selection >= 95.0
            and mean_ex_best > 0 and mean_bands_1_100 > 0
        )

        per_config_report[config] = {
            "n_trades": inference["n_trades"], "n_days": inference["n_days"],
            "win_rate": float((cdf["net_r"] > 0).mean()),
            "mean_net_r": inference["mean_net_r"], "median_net_r": inference["median_net_r"],
            "ci_low": inference["ci_low"], "ci_high": inference["ci_high"], "mde": inference["mde"],
            "timing_null_percentile": pct_timing, "selection_null_percentile": pct_selection,
            "timing_null_n_seeds": timing_result["n_seeds"], "selection_null_n_seeds": selection_result["n_seeds"],
            "selection_null_matched_counts_per_month": {
                f"{y}-{m:02d}": c for (y, m), c in selection_result["matched_counts_per_month"].items()
            },
            "mean_net_r_excl_best_year": mean_ex_best, "best_year_excluded": best_year,
            "mean_net_r_bands_1_100": mean_bands_1_100,
            "exit_mix": exit_mix, "by_year": by_year, "by_band": by_band,
            "diagnostics": diagnostics[config],
            "room_pct_distribution": cdf["room_pct"].describe().to_dict(),
            "time_exit_fallback_count": int((cdf["time_exit_fallback"]).sum()),
            "monitoring_gap_days_total": int(cdf["monitoring_gap_days"].sum()),
            "touched_count": int(cdf["touched"].sum()) if config == "B" else None,
            "DEV_PASS": bool(passes),
        }
        log(f"=== Configuration {config} DEV result: PASS={passes} mean_net_r={inference['mean_net_r']:.4f} "
            f"CI=[{inference['ci_low']:.4f},{inference['ci_high']:.4f}] timing_pct={pct_timing:.1f} "
            f"selection_pct={pct_selection:.1f} ex_best_year={mean_ex_best:.4f} "
            f"bands_1_100={mean_bands_1_100:.4f} n_trades={inference['n_trades']} ===")

    # ---------------- overlap count ----------------
    overlap = 0
    if not trades["A"].empty and not trades["B"].empty:
        keys_a = set(trades["A"]["gap_key"])
        keys_b = set(trades["B"]["gap_key"])
        overlap = len(keys_a & keys_b)

    # ---------------- BASELINE (reused from box theory V1, not recomputed) ----------------
    if V1_BASELINE_PATH.exists():
        with open(V1_BASELINE_PATH, "rb") as f:
            baseline_stats = pickle.load(f)
        log(f"Stage 5 [baseline]: REUSED from box theory's {V1_BASELINE_PATH} (not recomputed -- "
            f"BASELINE depends only on universe/window/costs, identical here): {baseline_stats}")
    else:
        baseline_stats = {"note": f"{V1_BASELINE_PATH} not found -- not recomputed, see "
                                    "PREREGISTRATION_FVG.md Section 0/8"}
        log(f"Stage 5 [baseline]: WARNING -- {V1_BASELINE_PATH} not found, cannot reuse")

    both_pass = all(per_config_report.get(c, {}).get("DEV_PASS") for c in CONFIG_NAMES)
    any_pass = any(per_config_report.get(c, {}).get("DEV_PASS") for c in CONFIG_NAMES)
    disposition = "BOTH PASS" if both_pass else ("ONE PASSES" if any_pass else "BOTH FAIL -- study closes")

    report = {
        "generated_at": dt.datetime.now().isoformat(), "window": "DEV", "study": "FVG",
        "disposition": disposition,
        "total_valid_gaps": total_gaps, "inside_bar_rejected": inside_bar_rejected,
        "overnight_excluded": overnight_excluded, "ab_overlap_count": overlap,
        "skipped_days": skips,
        "day_errors": {"count": len(errors), "is_finding": len(errors) > 5},
        "baseline": baseline_stats,
        "configurations": per_config_report,
    }
    log(f"=== FVG DEV disposition: {disposition} ===")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"Stage 6 [report]: saved to {REPORT_PATH}")
    log(f"=== FVG DEV run complete in {(time.time()-t_start)/60:.1f} min total ===")


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.smoke:
        OUT_DIR = ROOT / "data" / "fvg" / "smoke"
        dev_start, dev_end = dt.date(2017, 1, 1), dt.date(2017, 6, 30)
        N_SEEDS_TARGET, SMALL_RUN_SEEDS = 10, 5
        tmp_con = get_intraday_con(INTRADAY_DB)
        entity_ids = [r[0] for r in tmp_con.execute(
            "select distinct entity_id from bars_1min where trade_date between '2017-01-01' and '2017-06-30' limit 25"
        ).fetchall()]
    else:
        OUT_DIR = ROOT / "data" / "fvg" / "dev"
        dev_start, dev_end = test_seal.DEV_START, test_seal.DEV_END
        entity_ids = None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TRADES_PATH = OUT_DIR / "fvg_dev_trades.pkl"
    REPORT_PATH = OUT_DIR / "fvg_dev_report.json"
    LOG_PATH = OUT_DIR / "fvg_dev_run.log"

    main(dev_start, dev_end, entity_ids, args.smoke)
