"""PREREGISTRATION_BOX.md Process Step 3: run DEV ONLY (2016-10-04 to
2022-12-31), both configurations (FAST, SLOW), and produce the Section 8
report. Does NOT authorize the sealed TEST window -- `box_theory.
test_seal.guard_date_range` is called with `authorize_test=False`
(the default) against the DEV range, which is a no-op since DEV never
intersects the sealed window; TEST is never touched by this script.

Checkpointed in stages (each stage's result is pickled to data/box_theory/
before the next stage starts) so a kill does not lose completed work:
  1. dev_trades.pkl       -- the real backtest's trade list (both configs)
  2. dev_inference.pkl    -- day-clustered bootstrap per config
  3. dev_timing_null.pkl  -- TIMING null seed-mean arrays per config
  4. dev_selection_null.pkl -- SELECTION null seed-mean arrays per config
  5. dev_baseline.pkl     -- BASELINE descriptive stats
  6. dev_report.json      -- the final Section 8 report, human-readable

Seed count (1000 vs 500) is decided PER NULL TYPE from a timed small run
(20 seeds), per PREREGISTRATION_BOX.md Section 6 -- not fixed in advance.
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

from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con
from fibo.jump_guard import combined_unexplained_jump_dates

from box_theory import test_seal
from box_theory.backtest import run_backtest, build_universe, CONFIG_NAMES
from box_theory.inference import day_clustered_bootstrap, percentile_vs_null, excludes_zero
from box_theory.nulls import (
    build_timing_pool, timing_null_seed_mean, build_month_pool, selection_null_seed_mean,
    baseline_return,
)
ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

N_SEEDS_TARGET = 1000
N_SEEDS_FALLBACK = 500
SMALL_RUN_SEEDS = 20
TIME_BUDGET_SECONDS = 3600  # "~1 hour" per null, per instruction
CHECKPOINT_EVERY_SEEDS = 50  # Stage 3 (per config); Stage 4+5 checkpoints every month instead

# module-level, set by main() from CLI args -- real DEV run leaves these at
# their PREREGISTRATION_BOX.md defaults; --smoke overrides them for a quick
# end-to-end integration check against a real but tiny slice of the archive,
# writing to a SEPARATE directory so it can never collide with or be
# mistaken for the real DEV run's checkpoints.
OUT_DIR = None
TRADES_PATH = INFERENCE_PATH = TIMING_NULL_PATH = SELECTION_NULL_PATH = None
BASELINE_PATH = REPORT_PATH = LOG_PATH = None
TIMING_CHECKPOINT_PATH = SEL_CHECKPOINT_PATH = None


def _load_checkpoint(path):
    if path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def _save_checkpoint(path, state):
    """Atomic swap write -- same convention scripts/fibo_test_nulls.py
    already uses for its own long-running checkpoints, so a kill mid-write
    never leaves a half-written, unreadable checkpoint file behind."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(state, f)
    tmp.replace(path)


def log(msg: str) -> None:
    line = f"{dt.datetime.now().isoformat()} | {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def decide_seed_count(small_run_seconds: float, small_run_n: int, label: str) -> int:
    projected_1000 = small_run_seconds / small_run_n * N_SEEDS_TARGET
    log(f"[{label}] {small_run_n}-seed timed run took {small_run_seconds:.1f}s -> "
        f"projected {N_SEEDS_TARGET}-seed runtime = {projected_1000/60:.1f} min")
    if projected_1000 > TIME_BUDGET_SECONDS:
        log(f"[{label}] projection exceeds ~1 hour -- using {N_SEEDS_FALLBACK} seeds instead of "
            f"{N_SEEDS_TARGET}, per PREREGISTRATION_BOX.md Section 6's contingency")
        return N_SEEDS_FALLBACK
    return N_SEEDS_TARGET


def main(dev_start: dt.date, dev_end: dt.date, entity_ids: list[str] | None, smoke: bool):
    t_start = time.time()
    log(f"=== Box Theory DEV run starting ({'SMOKE TEST' if smoke else 'REAL'}) ===")

    intraday_con = get_intraday_con(INTRADAY_DB)
    warehouse_con = get_warehouse_con(WAREHOUSE_DB)

    if not smoke:
        assert (dev_start, dev_end) == (test_seal.DEV_START, test_seal.DEV_END), \
            "real (non-smoke) run must use the exact frozen DEV window"
    test_seal.guard_date_range(dev_start, dev_end, authorize_test=False,
                                caller="box_theory_dev_run.py", reason="DEV-only run")
    log(f"DEV window: {dev_start} to {dev_end} (test_seal guard passed, authorize_test=False)"
        + (f", entity_ids restricted to {len(entity_ids)}" if entity_ids else ""))

    # ---------------- Stage 1: backtest ----------------
    if TRADES_PATH.exists():
        log(f"Stage 1 [backtest]: found existing {TRADES_PATH}, loading instead of re-running")
        with open(TRADES_PATH, "rb") as f:
            saved = pickle.load(f)
        trades, universe = saved["trades"], saved["universe"]
    else:
        log("Stage 1 [backtest]: running full DEV backtest, both configs ...")
        t0 = time.time()
        result = run_backtest(intraday_con, warehouse_con, dev_start, dev_end, entity_ids=entity_ids)
        trades, universe = result["trades"], result["universe"]
        elapsed = time.time() - t0
        log(f"Stage 1 [backtest]: done in {elapsed/60:.1f} min -- {len(trades)} trades total, "
            f"skips={result['skips']}, diagnostics={result['diagnostics']}, "
            f"errors={len(result['errors'])}")
        if result["errors"]:
            for e in result["errors"][:20]:
                log(f"  DAY ERROR: {e['entity_id']} {e['trade_date']} {e['config']}: {e['error']}")
            if len(result["errors"]) > 20:
                log(f"  ... and {len(result['errors']) - 20} more (see dev_trades.pkl's 'errors' key)")
        with open(TRADES_PATH, "wb") as f:
            pickle.dump({"trades": trades, "universe": universe, "skips": result["skips"],
                         "diagnostics": result["diagnostics"], "errors": result["errors"]}, f)
        log(f"Stage 1 [backtest]: saved to {TRADES_PATH}")

    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)

    # ---------------- Stage 2: inference (day-clustered bootstrap) ----------------
    if INFERENCE_PATH.exists():
        log(f"Stage 2 [inference]: found existing {INFERENCE_PATH}, loading")
        with open(INFERENCE_PATH, "rb") as f:
            inference_by_config = pickle.load(f)
    else:
        log("Stage 2 [inference]: day-clustered bootstrap per config ...")
        inference_by_config = {}
        for config in CONFIG_NAMES:
            sub = trades[trades["config"] == config]
            inference_by_config[config] = day_clustered_bootstrap(sub, seed=0)
            r = inference_by_config[config]
            log(f"  {config}: n_trades={r['n_trades']} n_days={r['n_days']} "
                f"mean_net_r={r['mean_net_r']:.4f} CI=[{r['ci_low']:.4f},{r['ci_high']:.4f}] "
                f"mde={r['mde']:.4f}")
        with open(INFERENCE_PATH, "wb") as f:
            pickle.dump(inference_by_config, f)
        log(f"Stage 2 [inference]: saved to {INFERENCE_PATH}")

    # ---------------- Stage 3: TIMING null ----------------
    # Checkpointed every CHECKPOINT_EVERY_SEEDS seeds, per config, to
    # TIMING_CHECKPOINT_PATH -- added after this study's real DEV run paid
    # for its absence twice (100 and then 300 of 500 FAST seeds lost to
    # kills that had nothing to do with the computation itself). The pool
    # itself is NOT checkpointed (tens of thousands of contexts -- not
    # practical to pickle/reload cheaply); a resume still rebuilds it once
    # per config, then continues seed generation from the checkpointed
    # count instead of seed 0.
    if TIMING_NULL_PATH.exists():
        log(f"Stage 3 [timing null]: found existing {TIMING_NULL_PATH}, loading")
        with open(TIMING_NULL_PATH, "rb") as f:
            timing_results = pickle.load(f)
    else:
        timing_results = {}
        ckpt = _load_checkpoint(TIMING_CHECKPOINT_PATH) or {}
        if ckpt:
            log(f"Stage 3 [timing null]: found checkpoint, resuming "
                f"({list(ckpt.keys())} already recorded)")

        for config in CONFIG_NAMES:
            if config in ckpt and ckpt[config].get("done"):
                timing_results[config] = ckpt[config]["result"]
                log(f"Stage 3 [timing null, {config}]: already complete per checkpoint, skipping")
                continue

            sub = trades[trades["config"] == config]
            log(f"Stage 3 [timing null, {config}]: building pool for {len(sub)} trades ...")
            t0 = time.time()
            pool = build_timing_pool(intraday_con, warehouse_con, sub, rank_lookup, jump_dates_by_entity)
            log(f"  pool built in {time.time()-t0:.1f}s, size={len(pool)}")

            prior = ckpt.get(config)
            if prior and prior.get("n_seeds") is not None:
                n_seeds = prior["n_seeds"]
                means = list(prior["means"])
                log(f"Stage 3 [timing null, {config}]: resuming at seed {len(means)}/{n_seeds} "
                    f"from checkpoint")
            else:
                t0 = time.time()
                small_means = [timing_null_seed_mean(pool, np.random.default_rng(s)) for s in range(SMALL_RUN_SEEDS)]
                small_elapsed = time.time() - t0
                n_seeds = decide_seed_count(small_elapsed, SMALL_RUN_SEEDS, f"timing/{config}")
                means = list(small_means[:n_seeds]) if n_seeds <= SMALL_RUN_SEEDS else list(small_means)
                log(f"Stage 3 [timing null, {config}]: running {n_seeds} seeds ...")

            t0 = time.time()
            start_seed = len(means)
            for s in range(start_seed, n_seeds):
                means.append(timing_null_seed_mean(pool, np.random.default_rng(s)))
                if (s + 1) % CHECKPOINT_EVERY_SEEDS == 0 or (s + 1) == n_seeds:
                    ckpt[config] = {"means": means, "n_seeds": n_seeds, "done": False}
                    _save_checkpoint(TIMING_CHECKPOINT_PATH, ckpt)
                    log(f"  {config}: {s+1}/{n_seeds} seeds done ({time.time()-t0:.0f}s elapsed, checkpointed)")
            timing_results[config] = {"means": np.array(means), "n_seeds": n_seeds, "pool_size": len(pool)}
            ckpt[config] = {"means": means, "n_seeds": n_seeds, "done": True, "result": timing_results[config]}
            _save_checkpoint(TIMING_CHECKPOINT_PATH, ckpt)
            log(f"Stage 3 [timing null, {config}]: done, {n_seeds} seeds in {(time.time()-t0)/60:.1f} min")
            del pool

        with open(TIMING_NULL_PATH, "wb") as f:
            pickle.dump(timing_results, f)
        log(f"Stage 3 [timing null]: saved to {TIMING_NULL_PATH}")
        if TIMING_CHECKPOINT_PATH.exists():
            TIMING_CHECKPOINT_PATH.unlink()

    # ---------------- Stage 4+5: SELECTION null and BASELINE, ONE shared ----------------
    # month-pool pass. Previously two independent loops each called
    # build_month_pool for (nearly) the same set of months -- Stage 4 for
    # months with real trades, Stage 5 for every DEV month (a superset,
    # since a trade can only happen inside the DEV window in the first
    # place) -- paying the ~30s/month pool-build cost TWICE for the same
    # data. Merged: one loop over every DEV month builds each pool once,
    # and feeds whichever of the two computations still needs that month.
    # Pure engineering reuse -- identical inputs, identical formulas,
    # identical outputs (SELECTION_NULL_PATH and BASELINE_PATH unchanged
    # in shape) -- no rule, seed count, or gate touched.
    need_selection = not SELECTION_NULL_PATH.exists()
    need_baseline = not BASELINE_PATH.exists()

    if not need_selection:
        log(f"Stage 4 [selection null]: found existing {SELECTION_NULL_PATH}, loading")
        with open(SELECTION_NULL_PATH, "rb") as f:
            selection_results = pickle.load(f)
    if not need_baseline:
        log(f"Stage 5 [baseline]: found existing {BASELINE_PATH}, loading")
        with open(BASELINE_PATH, "rb") as f:
            baseline_stats = pickle.load(f)

    if need_selection or need_baseline:
        trades_by_month = {}
        for config in CONFIG_NAMES:
            sub = trades[trades["config"] == config].copy()
            sub["ym"] = sub["trade_date"].apply(lambda d: (d.year, d.month))
            trades_by_month[config] = sub.groupby("ym").size().to_dict()
        all_months = sorted(set().union(*[set(d.keys()) for d in trades_by_month.values()]))
        all_dev_months = sorted({
            (p.year, p.month) for p in pd.period_range(dev_start, dev_end, freq="M")
        })
        log(f"Stage 4+5: {len(all_months)} distinct (year,month) pairs with real trades "
            f"(selection null), {len(all_dev_months)} total DEV months (baseline) -- "
            f"{len(all_dev_months)} pool build(s) total, down from "
            f"{len(all_months) + len(all_dev_months)} before this merge")

        # Resume from a per-month checkpoint if one exists -- added after
        # this study's real DEV run lost a restart's worth of month-pool
        # work to a kill unrelated to the computation. Each month costs
        # 15-45s to rebuild AND process here, so checkpointing every
        # month (not batching several) is cheap relative to what a kill
        # would otherwise cost.
        ckpt = _load_checkpoint(SEL_CHECKPOINT_PATH)
        resumed = ckpt is not None and ckpt.get("need_selection") == need_selection
        if resumed:
            n_seeds = ckpt["n_seeds"]
            seed_sums = ckpt["seed_sums"]
            seed_counts = ckpt["seed_counts"]
            baseline_draws = ckpt["baseline_draws"]
            completed_months = ckpt["completed_months"]
            log(f"Stage 4+5: resumed from checkpoint, {len(completed_months)}/{len(all_dev_months)} "
                f"months already done")
        else:
            n_seeds = None
            baseline_draws = []
            completed_months = set()
            if need_selection:
                # timed small run: build ONE month's pool, time SMALL_RUN_SEEDS draws for FAST
                probe_year, probe_month = all_months[len(all_months) // 2]
                t0 = time.time()
                probe_pool = build_month_pool(intraday_con, warehouse_con, universe, probe_year, probe_month,
                                               rank_lookup, jump_dates_by_entity)
                probe_build_time = time.time() - t0
                probe_count = trades_by_month["FAST"].get((probe_year, probe_month), 10)
                t0 = time.time()
                for s in range(SMALL_RUN_SEEDS):
                    selection_null_seed_mean(probe_pool, probe_count,
                                              np.random.default_rng([s, probe_year, probe_month]), "FAST")
                probe_draw_time = time.time() - t0
                projected_total = (
                    probe_build_time * len(all_months)
                    + (probe_draw_time / SMALL_RUN_SEEDS) * N_SEEDS_TARGET * len(all_months) * len(CONFIG_NAMES)
                )
                log(f"Stage 4 [selection null]: probe month build={probe_build_time:.1f}s, "
                    f"{SMALL_RUN_SEEDS}-seed draw time={probe_draw_time:.1f}s for {probe_count} draws/seed -- "
                    f"projected FULL {N_SEEDS_TARGET}-seed, both-config runtime = {projected_total/60:.1f} min")
                n_seeds = N_SEEDS_FALLBACK if projected_total > TIME_BUDGET_SECONDS * 2 else N_SEEDS_TARGET
                if n_seeds == N_SEEDS_FALLBACK:
                    log(f"Stage 4 [selection null]: projection exceeds budget -- using {N_SEEDS_FALLBACK} seeds "
                        f"instead of {N_SEEDS_TARGET}, per PREREGISTRATION_BOX.md Section 6's contingency")
                del probe_pool

                seed_sums = {config: np.zeros(n_seeds) for config in CONFIG_NAMES}
                seed_counts = {config: np.zeros(n_seeds) for config in CONFIG_NAMES}
            else:
                seed_sums = seed_counts = None

        for mi, (year, month) in enumerate(all_dev_months):
            if (year, month) in completed_months:
                continue
            t0 = time.time()
            pool = build_month_pool(intraday_con, warehouse_con, universe, year, month,
                                     rank_lookup, jump_dates_by_entity)
            log(f"Stage 4+5: month {mi+1}/{len(all_dev_months)} ({year}-{month:02d}) "
                f"pool built in {time.time()-t0:.1f}s, size={len(pool)}")

            if need_selection and (year, month) in all_months:
                for config in CONFIG_NAMES:
                    count = trades_by_month[config].get((year, month), 0)
                    if count == 0 or not pool:
                        continue
                    for s in range(n_seeds):
                        rng = np.random.default_rng([s, year, month, hash(config) & 0xFFFF])
                        draws = selection_null_seed_mean(pool, count, rng, config)
                        if draws:
                            seed_sums[config][s] += sum(draws)
                            seed_counts[config][s] += len(draws)

            if need_baseline:
                for ctx in pool:
                    r = baseline_return(ctx["day_raw"], ctx["candles5"], ctx["band"])
                    if r is not None:
                        baseline_draws.append(r)

            del pool
            completed_months.add((year, month))
            _save_checkpoint(SEL_CHECKPOINT_PATH, {
                "need_selection": need_selection, "n_seeds": n_seeds, "seed_sums": seed_sums,
                "seed_counts": seed_counts, "baseline_draws": baseline_draws,
                "completed_months": completed_months,
            })

        if need_selection:
            selection_results = {}
            for config in CONFIG_NAMES:
                with np.errstate(invalid="ignore", divide="ignore"):
                    means = np.where(seed_counts[config] > 0, seed_sums[config] / seed_counts[config], np.nan)
                selection_results[config] = {"means": means, "n_seeds": n_seeds}
            with open(SELECTION_NULL_PATH, "wb") as f:
                pickle.dump(selection_results, f)
            log(f"Stage 4 [selection null]: saved to {SELECTION_NULL_PATH}")

        if need_baseline:
            arr = np.array(baseline_draws)
            baseline_stats = {
                "n_stock_days": int(len(arr)),
                "mean_net_return": float(np.mean(arr)) if len(arr) else float("nan"),
                "median_net_return": float(np.median(arr)) if len(arr) else float("nan"),
                "note": "descriptive only -- buy 09:30 open, sell 15:15 close, same intraday archive, "
                        "same cost model (sized the same fixed-Rs-500-at-3% way) as the real strategy",
            }
            log(f"Stage 5 [baseline]: {baseline_stats}")
            with open(BASELINE_PATH, "wb") as f:
                pickle.dump(baseline_stats, f)
            log(f"Stage 5 [baseline]: saved to {BASELINE_PATH}")

        if SEL_CHECKPOINT_PATH.exists():
            SEL_CHECKPOINT_PATH.unlink()

    # ---------------- Stage 6: final report ----------------
    report = {"generated_at": dt.datetime.now().isoformat(), "window": "DEV", "configs": {}}
    for config in CONFIG_NAMES:
        inf = inference_by_config[config]
        timing_means = timing_results[config]["means"]
        selection_means = selection_results[config]["means"]
        valid_timing = timing_means[~np.isnan(timing_means)]
        valid_selection = selection_means[~np.isnan(selection_means)]
        pct_timing = percentile_vs_null(inf["mean_net_r"], valid_timing) if len(valid_timing) else float("nan")
        pct_selection = percentile_vs_null(inf["mean_net_r"], valid_selection) if len(valid_selection) else float("nan")

        sub = trades[trades["config"] == config]
        by_year = sub.groupby("year")["net_r"].agg(["mean", "count"]).to_dict(orient="index")
        best_year = max(by_year, key=lambda y: by_year[y]["mean"]) if by_year else None
        ex_best = sub[sub["year"] != best_year] if best_year is not None else sub
        mean_ex_best = float(ex_best["net_r"].mean()) if len(ex_best) else float("nan")

        bands_1_100 = sub[sub["band"].isin(["1-50", "51-100"])]
        mean_bands_1_100 = float(bands_1_100["net_r"].mean()) if len(bands_1_100) else float("nan")

        exit_mix = sub["outcome"].value_counts().to_dict()
        armed_counts = sub["armed"].value_counts().to_dict()
        by_band = sub.groupby("band")["net_r"].agg(["mean", "count"]).to_dict(orient="index")
        time_exit_fallback_count = int(sub["time_exit_fallback"].sum()) if "time_exit_fallback" in sub else 0

        passes = (
            inf["mean_net_r"] > 0 and excludes_zero(inf["ci_low"], inf["ci_high"])
            and pct_timing >= 95.0 and pct_selection >= 95.0
            and mean_ex_best > 0
            and mean_bands_1_100 > 0
        )

        report["configs"][config] = {
            "n_trades": inf["n_trades"], "n_days": inf["n_days"],
            "win_rate": float((sub["net_r"] > 0).mean()) if len(sub) else float("nan"),
            "mean_net_r": inf["mean_net_r"], "median_net_r": inf["median_net_r"],
            "ci_low": inf["ci_low"], "ci_high": inf["ci_high"], "mde": inf["mde"],
            "timing_null_percentile": pct_timing, "selection_null_percentile": pct_selection,
            "timing_null_n_seeds": timing_results[config]["n_seeds"],
            "selection_null_n_seeds": selection_results[config]["n_seeds"],
            "mean_net_r_excl_best_year": mean_ex_best, "best_year_excluded": best_year,
            "mean_net_r_bands_1_100": mean_bands_1_100,
            "exit_mix": exit_mix, "armed_counts": armed_counts, "by_year": by_year, "by_band": by_band,
            "time_exit_fallback_count": time_exit_fallback_count,
            "DEV_PASS": bool(passes),
        }
        log(f"=== {config} DEV result: PASS={passes} mean_net_r={inf['mean_net_r']:.4f} "
            f"CI=[{inf['ci_low']:.4f},{inf['ci_high']:.4f}] timing_pct={pct_timing:.1f} "
            f"selection_pct={pct_selection:.1f} ex_best_year={mean_ex_best:.4f} "
            f"bands_1_100={mean_bands_1_100:.4f} time_exit_fallback={time_exit_fallback_count} ===")

    with open(TRADES_PATH, "rb") as f:
        saved = pickle.load(f)
    report["skipped_days"] = saved["skips"]
    report["diagnostics"] = saved["diagnostics"]

    # Per-trade exception handler (backtest.evaluate_entity's bounded
    # try/except around resolve_exit) -- every skip it ever produces must
    # be visible here, not just counted. ">5" ("more than a handful") is
    # treated as a FINDING per instruction: logged loudly, not left to be
    # noticed only by someone reading the JSON closely.
    day_errors = saved.get("errors", [])
    HANDFUL = 5
    report["day_errors"] = {
        "count": len(day_errors),
        "is_finding": len(day_errors) > HANDFUL,
        "distinct_entities": sorted({e["entity_id"] for e in day_errors}),
        "distinct_dates": sorted({str(e["trade_date"]) for e in day_errors}),
        "detail": [
            {"entity_id": e["entity_id"], "trade_date": str(e["trade_date"]), "config": e["config"],
             "error": e["error"]}
            for e in day_errors
        ],
    }
    if day_errors:
        header = "FINDING" if len(day_errors) > HANDFUL else "note"
        log(f"=== [{header}] {len(day_errors)} trade(s) skipped by the per-trade exception handler, "
            f"across {len(report['day_errors']['distinct_entities'])} entities, "
            f"{len(report['day_errors']['distinct_dates'])} distinct dates ===")
        for e in day_errors:
            log(f"  SKIPPED: {e['entity_id']} {e['trade_date']} {e['config']}: {e['error']}")
    else:
        log("=== 0 trades skipped by the per-trade exception handler ===")

    total_time_exit_fallback = sum(c["time_exit_fallback_count"] for c in report["configs"].values())
    log(f"=== {total_time_exit_fallback} TIME_EXIT trade(s) across both configs used the missing-15:15 "
        f"fallback (archive did not reach 15:15 that stock-day) ===")

    report["baseline"] = baseline_stats

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"Stage 6 [report]: saved to {REPORT_PATH}")
    log(f"=== Box Theory DEV run complete in {(time.time()-t_start)/60:.1f} min total ===")


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke", action="store_true",
                    help="Tiny real-data integration check: 5 entities, 2 months, 5-seed nulls, "
                         "separate output dir (data/box_theory/_smoke/). Never the real DEV run.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.smoke:
        OUT_DIR = ROOT / "data" / "box_theory" / "_smoke"
        dev_start, dev_end = dt.date(2017, 1, 1), dt.date(2017, 2, 28)
        N_SEEDS_TARGET, SMALL_RUN_SEEDS = 10, 5
        tmp_con = get_intraday_con(INTRADAY_DB)
        entity_ids = [r[0] for r in tmp_con.execute(
            "select distinct entity_id from bars_1min where trade_date between '2017-01-01' and '2017-02-28' limit 5"
        ).fetchall()]
    else:
        OUT_DIR = ROOT / "data" / "box_theory"
        dev_start, dev_end = test_seal.DEV_START, test_seal.DEV_END
        entity_ids = None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TRADES_PATH = OUT_DIR / "dev_trades.pkl"
    INFERENCE_PATH = OUT_DIR / "dev_inference.pkl"
    TIMING_NULL_PATH = OUT_DIR / "dev_timing_null.pkl"
    SELECTION_NULL_PATH = OUT_DIR / "dev_selection_null.pkl"
    BASELINE_PATH = OUT_DIR / "dev_baseline.pkl"
    TIMING_CHECKPOINT_PATH = OUT_DIR / "dev_timing_null_checkpoint.pkl"
    SEL_CHECKPOINT_PATH = OUT_DIR / "dev_selection_baseline_checkpoint.pkl"
    REPORT_PATH = OUT_DIR / "dev_report.json"
    LOG_PATH = OUT_DIR / "dev_run.log"

    main(dev_start, dev_end, entity_ids, args.smoke)
