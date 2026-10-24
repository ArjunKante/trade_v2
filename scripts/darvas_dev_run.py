"""PREREGISTRATION_DARVAS.md Process Step 3: run DEV ONLY (2016-01-01 to
2022-12-31), real trades + TIMING + SELECTION + MOMENTUM nulls, in that
order, and produce the Section 7 report. Does NOT authorize the sealed
TEST window -- `darvas.test_seal.guard_date_range` is called with
`authorize_test=False` (the default) against the DEV range, a no-op
since DEV never intersects the sealed window; TEST is never touched.

Checkpointed in stages (each stage's result is pickled to data/darvas/
before the next stage starts), same convention `scripts/box_theory_
dev_run.py` already uses:
  1. dev_backtest.pkl      -- real trades, boxes, universe, entity_context
  2. dev_inference.pkl     -- day-clustered bootstrap on real trades
  3. dev_timing_null.pkl   -- TIMING null seed-mean array
  4. dev_selection_null.pkl -- SELECTION null seed-mean array
  5. dev_momentum_null.pkl -- MOMENTUM null's single deterministic trade
     set + its own day-clustered bootstrap
  6. dev_report.json       -- the final Section 7 report, human-readable

Seed count (1000 vs 500) is decided PER NULL TYPE from a timed small run
(20 seeds), per PREREGISTRATION_DARVAS.md "Nulls" section's own
contingency (the same one PREREGISTRATION_BOX.md Section 6 / FVG Section
8 / IPO Section 8 already use) -- not fixed in advance.

Timing and memory are measured before each long stage, per instruction.
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

from box_theory.inference import day_clustered_bootstrap, excludes_zero, percentile_vs_null
from data_layer.db import get_read_connection
from darvas import nulls, test_seal
from darvas.backtest import run_backtest
from darvas.boxes import (
    COMPLETE_OUTCOMES, OUTCOME_BOTTOM_NEVER_CONFIRMED, OUTCOME_BROKE_OUT_BEFORE_BOTTOM,
    OUTCOME_COMPLETE_BREAKDOWN, OUTCOME_COMPLETE_BREAKOUT, OUTCOME_COMPLETE_UNRESOLVED,
    OUTCOME_TOP_NEVER_CONFIRMED, OUTCOME_TREND_FILTER_FAILED,
)

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"

N_SEEDS_TARGET = 1000
N_SEEDS_FALLBACK = 500
SMALL_RUN_SEEDS = 20
TIME_BUDGET_SECONDS = 3600
CHECKPOINT_EVERY_SEEDS = 100

OUT_DIR = None
BACKTEST_PATH = INFERENCE_PATH = TIMING_NULL_PATH = SELECTION_NULL_PATH = None
MOMENTUM_NULL_PATH = REPORT_PATH = LOG_PATH = None
TIMING_CKPT_PATH = SELECTION_CKPT_PATH = None


def _mem_mb() -> float:
    """Peak process RSS in MB, for the "measure memory before the long
    stages" instruction. `resource` (ru_maxrss, KB on Linux/bytes on
    macOS) is POSIX-only and doesn't exist on native Windows Python, so
    this falls back to `psutil` (already a transitive dependency of this
    project's data stack) and then to 0.0 (reported, not fatal) if
    neither is importable -- never lets a memory-reporting line crash
    the run itself."""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:
        pass
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def log(msg: str) -> None:
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


def decide_seed_count(small_run_seconds: float, small_run_n: int, label: str) -> int:
    projected = small_run_seconds / small_run_n * N_SEEDS_TARGET
    log(f"[{label}] {small_run_n}-seed timed run took {small_run_seconds:.1f}s -> "
        f"projected {N_SEEDS_TARGET}-seed runtime = {projected/60:.1f} min")
    if projected > TIME_BUDGET_SECONDS:
        log(f"[{label}] projection exceeds ~1 hour -- using {N_SEEDS_FALLBACK} seeds instead of "
            f"{N_SEEDS_TARGET}, per PREREGISTRATION_DARVAS.md's stated contingency")
        return N_SEEDS_FALLBACK
    return N_SEEDS_TARGET


def main(dev_start: dt.date, dev_end: dt.date, entity_ids: list[str] | None, smoke: bool):
    t_start = time.time()
    log(f"=== Darvas DEV run starting ({'SMOKE TEST' if smoke else 'REAL'}) | mem={_mem_mb():.0f}MB ===")

    con = get_read_connection(WAREHOUSE_DB)
    if not smoke:
        assert (dev_start, dev_end) == (test_seal.DEV_START, test_seal.DEV_END), \
            "real (non-smoke) run must use the exact frozen DEV window"
    test_seal.guard_date_range(dev_start, dev_end, authorize_test=False,
                                caller="darvas_dev_run.py", reason="DEV-only run")
    log(f"DEV window: {dev_start} to {dev_end} (test_seal guard passed, authorize_test=False)")

    # ---------------- Stage 1: backtest ----------------
    if BACKTEST_PATH.exists():
        log(f"Stage 1 [backtest]: found existing {BACKTEST_PATH}, loading")
        with open(BACKTEST_PATH, "rb") as f:
            res = pickle.load(f)
    else:
        log(f"Stage 1 [backtest]: running full DEV backtest ... | mem={_mem_mb():.0f}MB")
        t0 = time.time()
        res = run_backtest(con, dev_start, dev_end, authorize_test=False,
                            entity_ids=entity_ids, return_context=True)
        elapsed = time.time() - t0
        log(f"Stage 1 [backtest]: done in {elapsed/60:.1f} min | mem={_mem_mb():.0f}MB -- "
            f"{len(res['trades'])} trades, {len(res['boxes'])} box records, "
            f"zero_qty_skips={res['zero_qty_skips']}, "
            f"breakouts_skipped_in_position={res['breakouts_skipped_in_position']}, "
            f"non_member_year_trades_dropped={res['non_member_year_trades_dropped']}, "
            f"errors={len(res['errors'])}")
        if res["errors"]:
            for e in res["errors"][:20]:
                log(f"  ENTITY ERROR: {e}")
        with open(BACKTEST_PATH, "wb") as f:
            pickle.dump(res, f)
        log(f"Stage 1 [backtest]: saved to {BACKTEST_PATH}")

    trades = res["trades"]
    boxes = res["boxes"]
    universe = res["universe"]
    entity_context = res["entity_context"]

    if trades.empty:
        log("=== NO TRADES in DEV window. NO EDGE by construction -- stopping here. ===")
        return

    # ---------------- Stage 2: inference ----------------
    if INFERENCE_PATH.exists():
        log(f"Stage 2 [inference]: found existing {INFERENCE_PATH}, loading")
        with open(INFERENCE_PATH, "rb") as f:
            inf = pickle.load(f)
    else:
        log("Stage 2 [inference]: day-clustered bootstrap on real trades ...")
        inf = day_clustered_bootstrap(trades, seed=0)
        log(f"  n_trades={inf['n_trades']} n_days={inf['n_days']} mean_net_r={inf['mean_net_r']:.4f} "
            f"CI=[{inf['ci_low']:.4f},{inf['ci_high']:.4f}] mde={inf['mde']:.4f}")
        with open(INFERENCE_PATH, "wb") as f:
            pickle.dump(inf, f)
        log(f"Stage 2 [inference]: saved to {INFERENCE_PATH}")

    # ---------------- Stage 3: TIMING null ----------------
    if TIMING_NULL_PATH.exists():
        log(f"Stage 3 [timing null]: found existing {TIMING_NULL_PATH}, loading")
        with open(TIMING_NULL_PATH, "rb") as f:
            timing_result = pickle.load(f)
    else:
        log(f"Stage 3 [timing null]: building pool ... | mem={_mem_mb():.0f}MB")
        pool, missing = nulls.build_timing_pool(trades, entity_context)
        log(f"  pool size={len(pool)}, missing-context trades={missing}")

        ckpt = _load_checkpoint(TIMING_CKPT_PATH)
        if ckpt:
            means = list(ckpt["means"])
            n_seeds = ckpt["n_seeds"]
            log(f"Stage 3 [timing null]: resuming at seed {len(means)}/{n_seeds} from checkpoint")
        else:
            t0 = time.time()
            small_means = [nulls.timing_null_seed_mean(pool, np.random.default_rng(s))
                           for s in range(SMALL_RUN_SEEDS)]
            small_elapsed = time.time() - t0
            n_seeds = decide_seed_count(small_elapsed, SMALL_RUN_SEEDS, "timing")
            means = list(small_means[:n_seeds]) if n_seeds <= SMALL_RUN_SEEDS else list(small_means)

        t0 = time.time()
        for s in range(len(means), n_seeds):
            means.append(nulls.timing_null_seed_mean(pool, np.random.default_rng(s)))
            if (s + 1) % CHECKPOINT_EVERY_SEEDS == 0 or (s + 1) == n_seeds:
                _save_checkpoint(TIMING_CKPT_PATH, {"means": means, "n_seeds": n_seeds})
                log(f"  timing: {s+1}/{n_seeds} seeds done ({time.time()-t0:.0f}s elapsed)")
        timing_result = {"means": np.array(means), "n_seeds": n_seeds, "pool_size": len(pool)}
        with open(TIMING_NULL_PATH, "wb") as f:
            pickle.dump(timing_result, f)
        log(f"Stage 3 [timing null]: saved to {TIMING_NULL_PATH}")
        if TIMING_CKPT_PATH.exists():
            TIMING_CKPT_PATH.unlink()

    # ---------------- Stage 4: SELECTION null ----------------
    if SELECTION_NULL_PATH.exists():
        log(f"Stage 4 [selection null]: found existing {SELECTION_NULL_PATH}, loading")
        with open(SELECTION_NULL_PATH, "rb") as f:
            selection_result = pickle.load(f)
    else:
        log(f"Stage 4 [selection null]: building month pool ... | mem={_mem_mb():.0f}MB")
        t0 = time.time()
        pool_by_month = nulls.build_selection_pool_by_month(entity_context, universe)
        log(f"  pool built in {time.time()-t0:.1f}s, {len(pool_by_month)} (year,month) buckets")
        trades_by_month = (
            trades.assign(ym=trades["entry_date"].apply(lambda d: (d.year, d.month)))
            .groupby("ym").size().to_dict()
        )
        rho_pool = trades["rho"].to_numpy()

        ckpt = _load_checkpoint(SELECTION_CKPT_PATH)
        if ckpt:
            means = list(ckpt["means"])
            n_seeds = ckpt["n_seeds"]
            log(f"Stage 4 [selection null]: resuming at seed {len(means)}/{n_seeds} from checkpoint")
        else:
            t0 = time.time()
            small_means = [nulls.selection_null_seed_mean(pool_by_month, trades_by_month, rho_pool,
                                                           entity_context, np.random.default_rng(s))
                           for s in range(SMALL_RUN_SEEDS)]
            small_elapsed = time.time() - t0
            n_seeds = decide_seed_count(small_elapsed, SMALL_RUN_SEEDS, "selection")
            means = list(small_means[:n_seeds]) if n_seeds <= SMALL_RUN_SEEDS else list(small_means)

        t0 = time.time()
        for s in range(len(means), n_seeds):
            means.append(nulls.selection_null_seed_mean(pool_by_month, trades_by_month, rho_pool,
                                                         entity_context, np.random.default_rng(s)))
            if (s + 1) % CHECKPOINT_EVERY_SEEDS == 0 or (s + 1) == n_seeds:
                _save_checkpoint(SELECTION_CKPT_PATH, {"means": means, "n_seeds": n_seeds})
                log(f"  selection: {s+1}/{n_seeds} seeds done ({time.time()-t0:.0f}s elapsed)")
        selection_result = {"means": np.array(means), "n_seeds": n_seeds}
        with open(SELECTION_NULL_PATH, "wb") as f:
            pickle.dump(selection_result, f)
        log(f"Stage 4 [selection null]: saved to {SELECTION_NULL_PATH}")
        if SELECTION_CKPT_PATH.exists():
            SELECTION_CKPT_PATH.unlink()

    # ---------------- Stage 5: MOMENTUM null (the primary one) ----------------
    if MOMENTUM_NULL_PATH.exists():
        log(f"Stage 5 [momentum null]: found existing {MOMENTUM_NULL_PATH}, loading")
        with open(MOMENTUM_NULL_PATH, "rb") as f:
            momentum_result = pickle.load(f)
    else:
        log(f"Stage 5 [momentum null]: building momentum lookup ... | mem={_mem_mb():.0f}MB")
        t0 = time.time()
        mom_lookup = nulls.build_momentum_lookup(res["panel"], res["jump_dates"])
        log(f"  momentum lookup built in {time.time()-t0:.1f}s, {len(mom_lookup)} rows")
        t0 = time.time()
        mom_trades = nulls.momentum_null_trades(trades, mom_lookup, universe, entity_context)
        log(f"  momentum alternate trades: {len(mom_trades)} of {len(trades)} real trades "
            f"({time.time()-t0:.1f}s)")
        mom_inf = day_clustered_bootstrap(mom_trades, seed=0) if not mom_trades.empty else None
        momentum_result = {"trades": mom_trades, "inference": mom_inf,
                            "n_matched": len(mom_trades), "n_real": len(trades)}
        with open(MOMENTUM_NULL_PATH, "wb") as f:
            pickle.dump(momentum_result, f)
        log(f"Stage 5 [momentum null]: saved to {MOMENTUM_NULL_PATH}")

    # ---------------- Stage 6: final report ----------------
    log("Stage 6 [report]: assembling Section 7 report ...")
    pct_timing = percentile_vs_null(inf["mean_net_r"], timing_result["means"][~np.isnan(timing_result["means"])])
    pct_selection = percentile_vs_null(inf["mean_net_r"],
                                        selection_result["means"][~np.isnan(selection_result["means"])])
    mom_means = momentum_result["inference"]["resample_means"] if momentum_result["inference"] else np.array([])
    pct_momentum = percentile_vs_null(inf["mean_net_r"], mom_means) if len(mom_means) else float("nan")

    by_year = trades.groupby("year")["net_r"].agg(["mean", "count"]).to_dict(orient="index")
    best_year = max(by_year, key=lambda y: by_year[y]["mean"]) if by_year else None
    ex_best = trades[trades["year"] != best_year] if best_year is not None else trades
    mean_ex_best = float(ex_best["net_r"].mean()) if len(ex_best) else float("nan")

    passes = (
        inf["mean_net_r"] > 0 and excludes_zero(inf["ci_low"], inf["ci_high"])
        and pct_timing >= 95.0 and pct_selection >= 95.0 and pct_momentum >= 95.0
        and mean_ex_best > 0
    )

    by_band = trades.groupby("band")["net_r"].agg(["mean", "count"]).to_dict(orient="index")
    exit_mix = trades["exit_reason"].value_counts().to_dict()
    forced = trades[trades["exit_reason"] == "FORCED_WINDOW_CLOSE"]
    forced_contrib = float(forced["net_r"].sum()) if len(forced) else 0.0

    outcome_counts = boxes["outcome"].value_counts().to_dict() if not boxes.empty else {}
    complete_boxes_df = boxes[boxes["outcome"].isin(COMPLETE_OUTCOMES)] if not boxes.empty else boxes
    same_day_count = int(complete_boxes_df["same_day_top_bottom"].sum()) if len(complete_boxes_df) else 0
    never_broke_out = outcome_counts.get(OUTCOME_COMPLETE_BREAKDOWN, 0) + outcome_counts.get(
        OUTCOME_COMPLETE_UNRESOLVED, 0)

    hp = trades["holding_trading_days"]
    peak_concurrent = _peak_concurrent_positions(trades)
    peak_capital = _peak_capital(trades)

    report = {
        "generated_at": dt.datetime.now().isoformat(), "window": "DEV",
        "dev_start": str(dev_start), "dev_end": str(dev_end),
        "n_trades": inf["n_trades"], "n_distinct_entry_days": inf["n_days"],
        "win_rate": float((trades["net_r"] > 0).mean()),
        "mean_net_r": inf["mean_net_r"], "median_net_r": inf["median_net_r"],
        "ci_low": inf["ci_low"], "ci_high": inf["ci_high"], "mde": inf["mde"],
        "timing_null_percentile": pct_timing, "timing_null_n_seeds": int(timing_result["n_seeds"]),
        "selection_null_percentile": pct_selection, "selection_null_n_seeds": int(selection_result["n_seeds"]),
        "momentum_null_percentile": pct_momentum,
        "momentum_null_n_matched": momentum_result["n_matched"], "momentum_null_n_real": momentum_result["n_real"],
        "mean_net_r_excl_best_year": mean_ex_best, "best_year_excluded": best_year,
        "by_year": by_year, "by_band": by_band,
        "holding_trading_days": {"mean": float(hp.mean()), "median": float(hp.median()), "max": int(hp.max())},
        "exit_mix": exit_mix,
        "forced_window_close_count": int(len(forced)), "forced_window_close_net_r_contribution": forced_contrib,
        "zero_qty_skips": res["zero_qty_skips"],
        "breakouts_skipped_in_position": res["breakouts_skipped_in_position"],
        "non_member_year_trades_dropped": res["non_member_year_trades_dropped"],
        "box_outcome_counts": outcome_counts,
        "same_day_top_bottom_count": same_day_count,
        "same_day_top_bottom_rate": same_day_count / len(complete_boxes_df) if len(complete_boxes_df) else float("nan"),
        "never_broke_out_count": never_broke_out,
        "peak_concurrent_positions": peak_concurrent, "peak_deployed_capital_rs": peak_capital,
        "DEV_PASS": bool(passes),
    }

    if report["mean_net_r"] <= 0 or not passes:
        log(f"=== BAD RESULT: DEV_PASS={passes} mean_net_r={report['mean_net_r']:.4f} -- see report for detail ===")
    log(f"=== DEV result: PASS={passes} mean_net_r={inf['mean_net_r']:.4f} "
        f"CI=[{inf['ci_low']:.4f},{inf['ci_high']:.4f}] timing_pct={pct_timing:.1f} "
        f"selection_pct={pct_selection:.1f} momentum_pct={pct_momentum:.1f} ex_best_year={mean_ex_best:.4f} ===")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"Stage 6 [report]: saved to {REPORT_PATH}")
    log(f"=== Darvas DEV run complete in {(time.time()-t_start)/60:.1f} min total | mem={_mem_mb():.0f}MB ===")


def _peak_concurrent_positions(trades: pd.DataFrame) -> int:
    events = []
    for _, tr in trades.iterrows():
        events.append((tr["entry_date"], 1))
        events.append((tr["exit_date"], -1))
    events.sort(key=lambda x: (x[0], -x[1]))  # entries before exits on a tie
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak


def _peak_capital(trades: pd.DataFrame) -> float:
    events = []
    for _, tr in trades.iterrows():
        events.append((tr["entry_date"], tr["position_size_rs"]))
        events.append((tr["exit_date"], -tr["position_size_rs"]))
    events.sort(key=lambda x: (x[0], -x[1]))
    cur = peak = 0.0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return float(peak)


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke", action="store_true",
                    help="Tiny real-data integration check: 15 entities, a short window, "
                         "5-seed nulls, separate output dir (data/darvas/_smoke/). Never the real DEV run.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.smoke:
        OUT_DIR = ROOT / "data" / "darvas" / "_smoke"
        dev_start, dev_end = dt.date(2016, 1, 1), dt.date(2018, 12, 31)
        N_SEEDS_TARGET, SMALL_RUN_SEEDS = 10, 5
        con_tmp = get_read_connection(WAREHOUSE_DB)
        from darvas.backtest import build_universe
        u_tmp = build_universe(con_tmp)
        entity_ids = sorted(u_tmp["entity_id"].unique())[:15]
    else:
        OUT_DIR = ROOT / "data" / "darvas"
        dev_start, dev_end = test_seal.DEV_START, test_seal.DEV_END
        entity_ids = None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKTEST_PATH = OUT_DIR / "dev_backtest.pkl"
    INFERENCE_PATH = OUT_DIR / "dev_inference.pkl"
    TIMING_NULL_PATH = OUT_DIR / "dev_timing_null.pkl"
    SELECTION_NULL_PATH = OUT_DIR / "dev_selection_null.pkl"
    MOMENTUM_NULL_PATH = OUT_DIR / "dev_momentum_null.pkl"
    TIMING_CKPT_PATH = OUT_DIR / "dev_timing_null_checkpoint.pkl"
    SELECTION_CKPT_PATH = OUT_DIR / "dev_selection_null_checkpoint.pkl"
    REPORT_PATH = OUT_DIR / "dev_report.json"
    LOG_PATH = OUT_DIR / "dev_run.log"

    main(dev_start, dev_end, entity_ids, args.smoke)
