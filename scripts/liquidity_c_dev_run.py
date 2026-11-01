"""PREREGISTRATION_LIQUIDITY_C.md Process Step 3: run DEV ONLY, BOTH
SIDES, real trades + TIMING + SELECTION nulls per side, in that order,
and produce the Section 9 report. Does NOT authorize the sealed TEST
window -- `liquidity.c.guard_date_range` is called with
`authorize_test=False` against the DEV range, a no-op since DEV never
intersects the sealed window.

Checkpointed in stages per side (long fully, then short fully), same
convention as liquidity_a_dev_run.py / liquidity_b_dev_run.py, adapted
for Study C's own module and its own extra Section 9 report items:
NO_RETEST/RETEST_FAILED attrition, delay-vs-reclaim and give-up
distributions, and the filtered-out-trades counterfactual comparison.
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
from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con
from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import restrict_to_universe, assert_universe_membership

import liquidity.c as c
from poc.backtest import build_universe

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

STUDY_A_N_TRADES, STUDY_A_MEAN = 8_131, -0.2841
STUDY_B_N_TRADES, STUDY_B_MEAN = 9_222, -0.1212
STUDY_A_HALF_REACH, STUDY_B_HALF_REACH = 0.216, 0.265

N_SEEDS_TARGET = 1000
N_SEEDS_FALLBACK = 500
SMALL_RUN_SEEDS = 20
TIME_BUDGET_SECONDS = 3600
CHECKPOINT_EVERY_SEEDS = 100
ENTITY_CHECKPOINT_EVERY = 10


def _mem_mb() -> float:
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


def make_log(log_path: Path):
    def log(msg: str) -> None:
        line = f"{dt.datetime.now().isoformat()} | {msg}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return log


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


def decide_seed_count(small_run_seconds, small_run_n, label, log):
    projected = small_run_seconds / small_run_n * N_SEEDS_TARGET
    log(f"[{label}] {small_run_n}-seed timed run took {small_run_seconds:.1f}s -> "
        f"projected {N_SEEDS_TARGET}-seed runtime = {projected/60:.1f} min")
    if projected > TIME_BUDGET_SECONDS:
        log(f"[{label}] projection exceeds ~1 hour -- using {N_SEEDS_FALLBACK} seeds")
        return N_SEEDS_FALLBACK
    return N_SEEDS_TARGET


def run_backtest_checkpointed(side, paths, log, intraday_con, warehouse_con, dev_start, dev_end):
    evaluate_fn = c.evaluate_entity_c_long if side == "long" else c.evaluate_entity_c_short
    skip_reasons = c.SKIP_REASONS_LONG if side == "long" else c.SKIP_REASONS_SHORT

    universe = build_universe(warehouse_con)
    in_window = universe[(universe["year"] >= dev_start.year) & (universe["year"] <= dev_end.year)]
    entity_years: dict[str, list[int]] = {}
    for eid, grp in in_window.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())

    candidates = pd.DataFrame([{"entity_id": e, "year": y} for e, years in entity_years.items() for y in years])
    candidates = restrict_to_universe(candidates, universe)
    filtered_entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        filtered_entity_years[eid] = sorted(grp["year"].unique().tolist())

    ordered_entities = sorted(filtered_entity_years.keys())
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)

    ckpt = _load_checkpoint(paths["backtest_ckpt"])
    if ckpt:
        all_trades, total_skips = ckpt["all_trades"], ckpt["total_skips"]
        all_filtered_out, all_errors = ckpt["all_filtered_out"], ckpt["all_errors"]
        all_sweep_depths = ckpt["all_sweep_depths"]
        done_entities = set(ckpt["done_entities"])
        log(f"Stage 1 [{side}]: resuming at {len(done_entities)}/{len(ordered_entities)} entities")
    else:
        all_trades, all_filtered_out, all_errors = [], [], []
        total_skips = {r: 0 for r in skip_reasons}
        all_sweep_depths: list[float] = []
        done_entities: set = set()

    remaining = [e for e in ordered_entities if e not in done_entities]
    t0 = time.time()
    for i, entity_id in enumerate(remaining):
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = evaluate_fn(intraday_con, warehouse_con, entity_id, filtered_entity_years[entity_id],
                              dev_start, dev_end, jump_dates, rank_lookup)
        all_trades.extend(result["trades"])
        all_filtered_out.extend(result["filtered_out"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        all_sweep_depths.extend(result["sweep_depths_atr"])
        all_errors.extend(result["errors"])
        done_entities.add(entity_id)

        if (i + 1) % ENTITY_CHECKPOINT_EVERY == 0 or (i + 1) == len(remaining):
            _save_checkpoint(paths["backtest_ckpt"], {
                "all_trades": all_trades, "total_skips": total_skips, "all_filtered_out": all_filtered_out,
                "all_sweep_depths": all_sweep_depths, "all_errors": all_errors, "done_entities": list(done_entities),
            })
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta_min = ((len(remaining) - (i + 1)) / rate / 60) if rate > 0 else float("nan")
            log(f"  [{side}] backtest: {len(done_entities)}/{len(ordered_entities)} entities "
                f"({elapsed:.0f}s, ETA {eta_min:.1f} min) | trades={len(all_trades)} "
                f"filtered_out={len(all_filtered_out)} | mem={_mem_mb():.0f}MB")

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label=f"liquidity study C ({side}) trade list")

    return {
        "trades": trades_df, "skips": total_skips, "filtered_out": pd.DataFrame(all_filtered_out),
        "sweep_depths_atr": all_sweep_depths, "errors": all_errors, "universe": universe,
    }


def _half_full_breakdown(trades: pd.DataFrame) -> dict:
    qty1 = trades[trades["qty1_path"]]
    scaled = trades[~trades["qty1_path"]]
    half_reached = scaled[scaled["half_exit_happened"]]
    full_reached = half_reached[half_reached["outcome"].isin(["FULL_EXIT", "FULL_EXIT_SAME_BAR"])]
    return {
        "n_trades": int(len(trades)), "n_qty1_path": int(len(qty1)), "n_scaled_eligible": int(len(scaled)),
        "n_half_exit_reached": int(len(half_reached)),
        "half_exit_reach_rate_of_scaled": float(len(half_reached) / len(scaled)) if len(scaled) else None,
        "n_full_target_after_half": int(len(full_reached)),
        "full_target_rate_of_half_reached": (
            float(len(full_reached) / len(half_reached)) if len(half_reached) else None),
    }


def run_side(side: str, dev_start: dt.date, dev_end: dt.date) -> dict:
    out_dir = ROOT / "data" / "liquidity" / "c" / side
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "backtest": out_dir / "dev_backtest.pkl", "backtest_ckpt": out_dir / "dev_backtest_checkpoint.pkl",
        "inference": out_dir / "dev_inference.pkl",
        "timing_null": out_dir / "dev_timing_null.pkl", "timing_ckpt": out_dir / "dev_timing_null_checkpoint.pkl",
        "selection_null": out_dir / "dev_selection_null.pkl",
        "selection_ckpt": out_dir / "dev_selection_null_checkpoint.pkl",
        "report": out_dir / "dev_report.json", "log": out_dir / "dev_run.log",
    }
    log = make_log(paths["log"])
    log(f"=== Liquidity Study C DEV run ({side}) starting | mem={_mem_mb():.0f}MB ===")

    warehouse_con = get_warehouse_con(WAREHOUSE_DB)
    intraday_con = get_intraday_con(INTRADAY_DB)
    c.guard_date_range(dev_start, dev_end, authorize_test=False,
                        caller=f"liquidity_c_dev_run.py:{side}", reason="DEV-only run")

    skip_reasons = c.SKIP_REASONS_LONG if side == "long" else c.SKIP_REASONS_SHORT
    level_key = "lo_3m" if side == "long" else "hi_3m"
    resolve_fn = c.resolve_scaled_exit_a if side == "long" else c.resolve_scaled_exit_b
    cost_fn = c.three_order_cost_rs if side == "long" else c.three_order_cost_rs_b
    timing_draw_fn = c._timing_draw_c_long if side == "long" else c._timing_draw_c_short
    selection_draw_fn = c._selection_draw_c_long if side == "long" else c._selection_draw_c_short
    study_a_or_b_n = STUDY_A_N_TRADES if side == "long" else STUDY_B_N_TRADES
    study_a_or_b_mean = STUDY_A_MEAN if side == "long" else STUDY_B_MEAN
    study_a_or_b_half_reach = STUDY_A_HALF_REACH if side == "long" else STUDY_B_HALF_REACH

    # ---------------- Stage 1: backtest ----------------
    if paths["backtest"].exists():
        log(f"Stage 1 [{side}]: found existing {paths['backtest']}, loading")
        with open(paths["backtest"], "rb") as f:
            res = pickle.load(f)
    else:
        t0 = time.time()
        res = run_backtest_checkpointed(side, paths, log, intraday_con, warehouse_con, dev_start, dev_end)
        log(f"Stage 1 [{side}]: done in {(time.time()-t0)/60:.1f} min -- {len(res['trades'])} trades, "
            f"{len(res['filtered_out'])} filtered-out counterfactuals, errors={len(res['errors'])}")
        with open(paths["backtest"], "wb") as f:
            pickle.dump(res, f)
        if paths["backtest_ckpt"].exists():
            paths["backtest_ckpt"].unlink()

    trades = res["trades"]
    filtered_out = res["filtered_out"]
    universe = res["universe"]
    log(f"  [{side}] skip breakdown: {res['skips']}")
    log(f"  [{side}] trade count vs Study A/B's own: {len(trades)} vs {study_a_or_b_n}")

    if trades.empty:
        log(f"=== [{side}] NO TRADES. NO EDGE by construction. ===")
        return {"side": side, "n_trades": 0}

    # ---------------- Stage 2: inference ----------------
    if paths["inference"].exists():
        with open(paths["inference"], "rb") as f:
            inf = pickle.load(f)
    else:
        inf = day_clustered_bootstrap(trades, net_r_col="net_return_pct", seed=0)
        log(f"  [{side}] mean_net_return_pct={inf['mean_net_r']*100:.4f}% "
            f"CI=[{inf['ci_low']*100:.4f}%,{inf['ci_high']*100:.4f}%]")
        with open(paths["inference"], "wb") as f:
            pickle.dump(inf, f)

    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}

    # ---------------- Stage 3: TIMING null ----------------
    if paths["timing_null"].exists():
        with open(paths["timing_null"], "rb") as f:
            timing_result = pickle.load(f)
    else:
        pool = c.build_timing_pool_c(intraday_con, warehouse_con, trades, rank_lookup, jump_dates_by_entity)
        log(f"  [{side}] timing pool size={len(pool)}")
        ckpt = _load_checkpoint(paths["timing_ckpt"])
        if ckpt:
            means, n_seeds = list(ckpt["means"]), ckpt["n_seeds"]
        else:
            t0 = time.time()
            small_means = [c.timing_null_seed_mean_c(pool, timing_draw_fn, np.random.default_rng(s))
                           for s in range(SMALL_RUN_SEEDS)]
            n_seeds = decide_seed_count(time.time() - t0, SMALL_RUN_SEEDS, f"{side}-timing", log)
            means = list(small_means[:n_seeds]) if n_seeds <= SMALL_RUN_SEEDS else list(small_means)
        for s in range(len(means), n_seeds):
            means.append(c.timing_null_seed_mean_c(pool, timing_draw_fn, np.random.default_rng(s)))
            if (s + 1) % CHECKPOINT_EVERY_SEEDS == 0 or (s + 1) == n_seeds:
                _save_checkpoint(paths["timing_ckpt"], {"means": means, "n_seeds": n_seeds})
                log(f"  [{side}] timing: {s+1}/{n_seeds} seeds done")
        timing_result = {"means": np.array(means), "n_seeds": n_seeds, "pool_size": len(pool)}
        with open(paths["timing_null"], "wb") as f:
            pickle.dump(timing_result, f)
        if paths["timing_ckpt"].exists():
            paths["timing_ckpt"].unlink()

    # ---------------- Stage 4: SELECTION null ----------------
    rho_pool = trades["stop_distance_pct"].to_numpy()
    if paths["selection_null"].exists():
        with open(paths["selection_null"], "rb") as f:
            selection_result = pickle.load(f)
    else:
        trades_by_month = (trades.assign(ym=trades["trade_date"].apply(lambda d: (d.year, d.month)))
                            .groupby("ym").size().to_dict())
        months = sorted(trades_by_month.keys())
        log(f"  [{side}] {len(months)} (year,month) buckets with real trades")
        ckpt = _load_checkpoint(paths["selection_ckpt"])
        if ckpt:
            per_month_draws, n_seeds, done_months = ckpt["per_month_draws"], ckpt["n_seeds"], set(ckpt["done_months"])
        else:
            per_month_draws, done_months, n_seeds = {}, set(), None

        entity_setup_cache: dict = {}
        t0 = time.time()
        for (year, month) in months:
            if (year, month) in done_months:
                continue
            count = trades_by_month[(year, month)]
            month_pool = c.build_month_pool_c(intraday_con, warehouse_con, universe, year, month, rank_lookup,
                                               jump_dates_by_entity, entity_setup_cache, dev_start, dev_end, level_key)
            if n_seeds is None:
                t1 = time.time()
                small_draws = [c.selection_null_seed_mean_c(month_pool, count, np.random.default_rng(s),
                                                              rho_pool, selection_draw_fn)
                               for s in range(SMALL_RUN_SEEDS)]
                n_seeds = decide_seed_count((time.time() - t1) * len(months), SMALL_RUN_SEEDS,
                                             f"{side}-selection", log)
                per_month_draws[(year, month)] = small_draws + [
                    c.selection_null_seed_mean_c(month_pool, count, np.random.default_rng(s), rho_pool, selection_draw_fn)
                    for s in range(SMALL_RUN_SEEDS, n_seeds)]
            else:
                per_month_draws[(year, month)] = [
                    c.selection_null_seed_mean_c(month_pool, count, np.random.default_rng(s), rho_pool, selection_draw_fn)
                    for s in range(n_seeds)]
            done_months.add((year, month))
            _save_checkpoint(paths["selection_ckpt"], {
                "per_month_draws": per_month_draws, "n_seeds": n_seeds, "done_months": list(done_months)})
            log(f"  [{side}] selection: month {year}-{month:02d} done ({len(done_months)}/{len(months)}) "
                f"| pool_size={len(month_pool)} | elapsed {time.time()-t0:.0f}s")

        seed_means = []
        for s in range(n_seeds):
            all_draws = [d for (year, month) in months for d in per_month_draws[(year, month)][s]]
            seed_means.append(float(np.mean(all_draws)) if all_draws else float("nan"))
        selection_result = {"means": np.array(seed_means), "n_seeds": n_seeds}
        with open(paths["selection_null"], "wb") as f:
            pickle.dump(selection_result, f)
        if paths["selection_ckpt"].exists():
            paths["selection_ckpt"].unlink()

    # ---------------- Stage 5: report ----------------
    pct_timing = percentile_vs_null(inf["mean_net_r"], timing_result["means"][~np.isnan(timing_result["means"])])
    pct_selection = percentile_vs_null(inf["mean_net_r"],
                                        selection_result["means"][~np.isnan(selection_result["means"])])

    by_year = trades.groupby("year")["net_return_pct"].agg(["mean", "count"]).to_dict(orient="index")
    best_year = max(by_year, key=lambda y: by_year[y]["mean"]) if by_year else None
    ex_best = trades[trades["year"] != best_year] if best_year is not None else trades
    mean_ex_best = float(ex_best["net_return_pct"].mean()) if len(ex_best) else float("nan")
    band_100 = trades[trades["band"].isin(["1-50", "51-100"])]
    mean_band_100 = float(band_100["net_return_pct"].mean()) if len(band_100) else float("nan")

    passes = (inf["mean_net_r"] > 0 and excludes_zero(inf["ci_low"], inf["ci_high"])
              and pct_timing >= 95.0 and pct_selection >= 95.0 and mean_ex_best > 0 and mean_band_100 > 0)

    half_full = _half_full_breakdown(trades)
    exit_mix = trades["outcome"].value_counts().to_dict()

    # Study-specific: attrition, delay/give-up, filtered-out comparison
    attrition = {k: int(res["skips"].get(k, 0)) for k in ("no_retest", "retest_failed")}
    delay = trades["delay_minutes"].dropna()
    give_up = trades["pct_given_up"].dropna()

    fout = filtered_out
    fout_mean = float(fout["original_net_return_pct"].mean()) if len(fout) else None
    fout_by_reason = (
        fout.groupby("skip_reason")["original_net_return_pct"].agg(["mean", "count"]).to_dict(orient="index")
        if len(fout) else {}
    )

    report = {
        "side": side, "generated_at": dt.datetime.now().isoformat(), "window": "DEV",
        "dev_start": str(dev_start), "dev_end": str(dev_end),
        "n_trades": inf["n_trades"], "n_distinct_entry_days": inf["n_days"],
        "n_trades_vs_prior_study": {"study": "A" if side == "long" else "B", "n_c": inf["n_trades"],
                                     "n_prior": study_a_or_b_n},
        "mean_net_return_pct": inf["mean_net_r"], "median_net_return_pct": inf["median_net_r"],
        "ci_low": inf["ci_low"], "ci_high": inf["ci_high"],
        "mean_vs_prior_study": {"c": inf["mean_net_r"] * 100, "prior": study_a_or_b_mean},
        "timing_null_percentile": pct_timing, "timing_null_n_seeds": int(timing_result["n_seeds"]),
        "selection_null_percentile": pct_selection, "selection_null_n_seeds": int(selection_result["n_seeds"]),
        "mean_net_return_pct_excl_best_year": mean_ex_best, "best_year_excluded": best_year,
        "mean_net_return_pct_bands_1_100": mean_band_100,
        "by_year": by_year, "exit_mix": exit_mix,
        "half_full_breakdown": half_full,
        "half_reach_rate_vs_prior_study": {"c": half_full["half_exit_reach_rate_of_scaled"],
                                            "prior": study_a_or_b_half_reach},
        "attrition_no_retest_retest_failed": attrition,
        "skips": res["skips"],
        "delay_minutes": {"mean": float(delay.mean()) if len(delay) else None,
                           "median": float(delay.median()) if len(delay) else None,
                           "min": float(delay.min()) if len(delay) else None,
                           "max": float(delay.max()) if len(delay) else None},
        "pct_given_up": {"mean": float(give_up.mean()) if len(give_up) else None,
                          "median": float(give_up.median()) if len(give_up) else None},
        "filtered_out_trades": {
            "n": int(len(fout)), "mean_original_net_return_pct": fout_mean, "by_reason": fout_by_reason,
            "vs_actual_c_mean": (fout_mean - inf["mean_net_r"] * 100) if fout_mean is not None else None,
        },
        "DEV_PASS": bool(passes),
    }

    log(f"=== [{side}] DEV result: PASS={passes} mean={inf['mean_net_r']*100:.4f}% "
        f"CI=[{inf['ci_low']*100:.4f}%,{inf['ci_high']*100:.4f}%] timing_pct={pct_timing:.1f} "
        f"selection_pct={pct_selection:.1f} n_trades={inf['n_trades']} "
        f"half_reach={half_full['half_exit_reach_rate_of_scaled']} "
        f"no_retest={attrition['no_retest']} retest_failed={attrition['retest_failed']} "
        f"filtered_out_mean={fout_mean} ===")

    with open(paths["report"], "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"Stage 5 [{side}]: saved to {paths['report']}")

    warehouse_con.close()
    intraday_con.close()
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--side", choices=["long", "short", "both"], default="both")
    args = p.parse_args()

    sides = ["long", "short"] if args.side == "both" else [args.side]
    results = {}
    for side in sides:
        results[side] = run_side(side, c.DEV_START, c.DEV_END)

    if len(results) == 2 and all(r.get("n_trades", 0) != 0 for r in results.values()):
        print("\n" + "=" * 90)
        print("COMBINED SUMMARY -- LONG vs SHORT vs Study A/B")
        print("=" * 90)
        for side, r in results.items():
            print(f"{side:6s}  n={r['n_trades']:6d}  mean={r['mean_net_return_pct']*100:+.4f}%  "
                  f"CI=[{r['ci_low']*100:+.4f}%,{r['ci_high']*100:+.4f}%]  "
                  f"timing_pct={r['timing_null_percentile']:.1f}  selection_pct={r['selection_null_percentile']:.1f}  "
                  f"DEV_PASS={r['DEV_PASS']}")
        combined_mean = np.average(
            [results["long"]["mean_net_return_pct"], results["short"]["mean_net_return_pct"]],
            weights=[results["long"]["n_trades"], results["short"]["n_trades"]])
        print(f"combined (trade-weighted mean): {combined_mean*100:+.4f}%")
