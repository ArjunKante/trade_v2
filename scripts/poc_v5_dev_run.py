"""PREREGISTRATION_POC_V5.md Process Step 3: run DEV ONLY (2016-10-04 to
2022-12-31), real trades + TIMING + SELECTION nulls, in that order, and
produce the Section 11 report. Does NOT authorize the sealed TEST window.

Checkpointed in stages, same convention as `scripts/poc_v4_dev_run.py`.
V5-specific additions: population check against V4's own 3,256 expected
entry count (prereg's own stated prediction), holding-period
distribution, gap-through count/cost, peak concurrent positions/capital
reported prominently, DEV_BOUNDARY_TRUNCATED reported separately and
excluded from the gate population, lo/mid/hi cost sensitivity.
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

from poc import v5
from poc.backtest import build_universe

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

V4_ENTERED_COUNT = 3_225
V4_NO_ROOM_COUNT = 31
V5_EXPECTED_ENTRY_COUNT = V4_ENTERED_COUNT + V4_NO_ROOM_COUNT  # 3,256 -- prereg's own stated prediction

N_SEEDS_TARGET = 1000
N_SEEDS_FALLBACK = 500
SMALL_RUN_SEEDS = 20
TIME_BUDGET_SECONDS = 3600
CHECKPOINT_EVERY_SEEDS = 100
ENTITY_CHECKPOINT_EVERY = 10

OUT_DIR = None
BACKTEST_PATH = INFERENCE_PATH = TIMING_NULL_PATH = SELECTION_NULL_PATH = None
REPORT_PATH = LOG_PATH = None
BACKTEST_CKPT_PATH = TIMING_CKPT_PATH = SELECTION_CKPT_PATH = None


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
            f"{N_SEEDS_TARGET}, same contingency as V1-V4")
        return N_SEEDS_FALLBACK
    return N_SEEDS_TARGET


def run_backtest_checkpointed(intraday_con, warehouse_con, dev_start, dev_end, entity_ids=None):
    universe = build_universe(warehouse_con)
    in_window = universe[(universe["year"] >= dev_start.year) & (universe["year"] <= dev_end.year)]
    entity_years: dict[str, list[int]] = {}
    for eid, grp in in_window.groupby("entity_id"):
        entity_years[eid] = sorted(grp["year"].unique().tolist())
    if entity_ids is not None:
        entity_years = {e: y for e, y in entity_years.items() if e in entity_ids}

    candidates = pd.DataFrame(
        [{"entity_id": e, "year": y} for e, years in entity_years.items() for y in years]
    )
    candidates = restrict_to_universe(candidates, universe)
    filtered_entity_years: dict[str, list[int]] = {}
    for eid, grp in candidates.groupby("entity_id"):
        filtered_entity_years[eid] = sorted(grp["year"].unique().tolist())

    ordered_entities = sorted(filtered_entity_years.keys())
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)

    ckpt = _load_checkpoint(BACKTEST_CKPT_PATH)
    if ckpt:
        all_trades = ckpt["all_trades"]
        all_boundary = ckpt["all_boundary"]
        total_skips = ckpt["total_skips"]
        total_lookback_detail = ckpt["total_lookback_detail"]
        all_errors = ckpt["all_errors"]
        done_entities = set(ckpt["done_entities"])
        log(f"Stage 1 [backtest]: resuming at {len(done_entities)}/{len(ordered_entities)} entities from checkpoint")
    else:
        all_trades, all_boundary, all_errors = [], [], []
        total_skips = {r: 0 for r in v5.SKIP_REASONS}
        total_lookback_detail: dict = {}
        done_entities: set = set()

    remaining = [e for e in ordered_entities if e not in done_entities]
    t0 = time.time()
    for i, entity_id in enumerate(remaining):
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = v5.evaluate_entity_v5(
            intraday_con, warehouse_con, entity_id, filtered_entity_years[entity_id],
            dev_start, dev_end, jump_dates, rank_lookup,
        )
        all_trades.extend(result["trades"])
        all_boundary.extend(result["boundary_trades"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        for key, v_ in result["lookback_incomplete_detail"].items():
            total_lookback_detail[key] = total_lookback_detail.get(key, 0) + v_
        all_errors.extend(result["errors"])
        done_entities.add(entity_id)

        if (i + 1) % ENTITY_CHECKPOINT_EVERY == 0 or (i + 1) == len(remaining):
            _save_checkpoint(BACKTEST_CKPT_PATH, {
                "all_trades": all_trades, "all_boundary": all_boundary, "total_skips": total_skips,
                "total_lookback_detail": total_lookback_detail, "all_errors": all_errors,
                "done_entities": list(done_entities),
            })
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining_n = len(remaining) - (i + 1)
            eta_min = (remaining_n / rate / 60) if rate > 0 else float("nan")
            log(f"  backtest: {len(done_entities)}/{len(ordered_entities)} entities done "
                f"({elapsed:.0f}s elapsed this run, ~{rate:.2f} entities/s, ETA {eta_min:.1f} min) | "
                f"trades so far={len(all_trades)} (+{len(all_boundary)} boundary-truncated) | "
                f"mem={_mem_mb():.0f}MB")

    trades_df = pd.DataFrame(all_trades)
    boundary_df = pd.DataFrame(all_boundary)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label="poc v5 trade list")

    return {
        "trades": trades_df, "boundary_trades": boundary_df, "skips": total_skips,
        "lookback_incomplete_detail": total_lookback_detail, "errors": all_errors, "universe": universe,
    }


def _peak_concurrent_positions(trades: pd.DataFrame) -> int:
    events = []
    for _, tr in trades.iterrows():
        entry_ts = pd.Timestamp(tr["fill_ts"])
        exit_ts = pd.Timestamp(tr["exit_date"]) + pd.Timedelta(hours=15, minutes=30)  # end of exit day
        events.append((entry_ts, 1))
        events.append((exit_ts, -1))
    events.sort(key=lambda x: (x[0], -x[1]))
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak


def _peak_capital(trades: pd.DataFrame) -> float:
    events = []
    for _, tr in trades.iterrows():
        entry_ts = pd.Timestamp(tr["fill_ts"])
        exit_ts = pd.Timestamp(tr["exit_date"]) + pd.Timedelta(hours=15, minutes=30)
        events.append((entry_ts, tr["position_size_rs"]))
        events.append((exit_ts, -tr["position_size_rs"]))
    events.sort(key=lambda x: (x[0], -x[1]))
    cur = peak = 0.0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return float(peak)


def main(dev_start: dt.date, dev_end: dt.date, entity_ids: list[str] | None, smoke: bool):
    t_start = time.time()
    log(f"=== POC V5 DEV run starting ({'SMOKE TEST' if smoke else 'REAL'}) | mem={_mem_mb():.0f}MB ===")

    warehouse_con = get_warehouse_con(WAREHOUSE_DB)
    intraday_con = get_intraday_con(INTRADAY_DB)
    if not smoke:
        assert (dev_start, dev_end) == (v5.DEV_START, v5.DEV_END), \
            "real (non-smoke) run must use the exact frozen DEV window"
    v5.guard_date_range(dev_start, dev_end, authorize_test=False,
                         caller="poc_v5_dev_run.py", reason="DEV-only run")
    log(f"DEV window: {dev_start} to {dev_end} (test_seal guard passed, authorize_test=False)")

    # ---------------- Stage 1: backtest ----------------
    if BACKTEST_PATH.exists():
        log(f"Stage 1 [backtest]: found existing {BACKTEST_PATH}, loading")
        with open(BACKTEST_PATH, "rb") as f:
            res = pickle.load(f)
    else:
        log(f"Stage 1 [backtest]: running full DEV backtest ... | mem={_mem_mb():.0f}MB")
        t0 = time.time()
        res = run_backtest_checkpointed(intraday_con, warehouse_con, dev_start, dev_end, entity_ids)
        elapsed = time.time() - t0
        log(f"Stage 1 [backtest]: done in {elapsed/60:.1f} min | mem={_mem_mb():.0f}MB -- "
            f"{len(res['trades'])} trades (+{len(res['boundary_trades'])} boundary-truncated), "
            f"errors={len(res['errors'])}")
        if res["errors"]:
            for e in res["errors"][:20]:
                log(f"  ENTITY ERROR: {e}")
        with open(BACKTEST_PATH, "wb") as f:
            pickle.dump(res, f)
        log(f"Stage 1 [backtest]: saved to {BACKTEST_PATH}")
        if BACKTEST_CKPT_PATH.exists():
            BACKTEST_CKPT_PATH.unlink()

    trades = res["trades"]
    boundary = res["boundary_trades"]
    universe = res["universe"]

    log(f"  skip breakdown so far: {res['skips']}")

    # --- population check against V4, per instruction ---
    total_entries = len(trades) + len(boundary)
    pop_match = (total_entries == V5_EXPECTED_ENTRY_COUNT)
    log(f"  POPULATION CHECK: V5 total entries (gate population + boundary-truncated) = {total_entries}, "
        f"expected {V5_EXPECTED_ENTRY_COUNT} (V4's {V4_ENTERED_COUNT} ENTERED + its own {V4_NO_ROOM_COUNT} "
        f"NO_ROOM, which V5's risk-multiple target can never trigger) -- {'MATCH' if pop_match else 'MISMATCH'}")
    if not pop_match:
        log(f"  MISMATCH: gate population={len(trades)}, boundary-truncated={len(boundary)}, "
            f"total={total_entries} vs expected {V5_EXPECTED_ENTRY_COUNT}. Full skip breakdown above -- "
            f"investigate stage by stage before trusting any aggregate number.")

    if trades.empty:
        log("=== NO TRADES in DEV window gate population. NO EDGE by construction -- stopping here. ===")
        return

    # --- holding-period distribution, gap-through, peak concurrency (reported prominently) ---
    exit_mix = trades["outcome"].value_counts().to_dict()
    entry_day_exits = trades[trades["trading_days_held"] == 1]["outcome"].value_counts().to_dict()
    overnight_exits = trades[trades["trading_days_held"] > 1]["outcome"].value_counts().to_dict()
    gap_through = trades[trades["gap_through"]]
    gap_through_count = len(gap_through)
    gap_through_extra_loss_rs = float(
        ((gap_through["stop_price"] - gap_through["exit_price"]) * gap_through["qty"]).sum()
    ) if gap_through_count else 0.0
    peak_concurrent = _peak_concurrent_positions(trades)
    peak_capital = _peak_capital(trades)

    log(f"  exit mix (gate population): {exit_mix}")
    log(f"  entry-day exits: {entry_day_exits}  |  overnight exits: {overnight_exits}")
    log(f"  gap-through count: {gap_through_count}/{len(trades)} "
        f"({gap_through_count/len(trades)*100:.2f}% of gate trades) | "
        f"total extra loss attributable to gaps: Rs {gap_through_extra_loss_rs:,.2f}")
    log(f"  PEAK CONCURRENT POSITIONS: {peak_concurrent}  |  PEAK DEPLOYED CAPITAL: Rs {peak_capital:,.2f}")

    if not boundary.empty:
        log(f"  DEV_BOUNDARY_TRUNCATED: {len(boundary)} trades, excluded from gate, "
            f"mean net_return_pct (descriptive only) = {boundary['net_return_pct'].mean()*100:.4f}%")

    # ---------------- Stage 2: inference ----------------
    if INFERENCE_PATH.exists():
        log(f"Stage 2 [inference]: found existing {INFERENCE_PATH}, loading")
        with open(INFERENCE_PATH, "rb") as f:
            inf = pickle.load(f)
    else:
        log("Stage 2 [inference]: day-clustered bootstrap on real trades (net_return_pct, midpoint cost) ...")
        inf = day_clustered_bootstrap(trades, net_r_col="net_return_pct", seed=0)
        log(f"  n_trades={inf['n_trades']} n_days={inf['n_days']} mean_net_return_pct={inf['mean_net_r']*100:.4f}% "
            f"CI=[{inf['ci_low']*100:.4f}%,{inf['ci_high']*100:.4f}%] mde={inf['mde']*100:.4f}%")
        log(f"  cost sensitivity: lo-cost mean={trades['net_return_pct_lo_cost'].mean()*100:.4f}%  "
            f"hi-cost mean={trades['net_return_pct_hi_cost'].mean()*100:.4f}%")
        with open(INFERENCE_PATH, "wb") as f:
            pickle.dump(inf, f)
        log(f"Stage 2 [inference]: saved to {INFERENCE_PATH}")

    jump_dates_by_entity = combined_unexplained_jump_dates(warehouse_con)
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}

    # ---------------- Stage 3: TIMING null ----------------
    if TIMING_NULL_PATH.exists():
        log(f"Stage 3 [timing null]: found existing {TIMING_NULL_PATH}, loading")
        with open(TIMING_NULL_PATH, "rb") as f:
            timing_result = pickle.load(f)
    else:
        log(f"Stage 3 [timing null]: building pool (fetching subsequent bars ONCE per pool entry) ... "
            f"| mem={_mem_mb():.0f}MB")
        t0 = time.time()
        pool = v5.build_timing_pool_v5(intraday_con, warehouse_con, trades, rank_lookup, jump_dates_by_entity,
                                        dev_end)
        log(f"  pool size={len(pool)} ({time.time()-t0:.1f}s)")

        ckpt = _load_checkpoint(TIMING_CKPT_PATH)
        if ckpt:
            means = list(ckpt["means"])
            n_seeds = ckpt["n_seeds"]
            log(f"Stage 3 [timing null]: resuming at seed {len(means)}/{n_seeds} from checkpoint")
        else:
            t0 = time.time()
            small_means = [v5.timing_null_seed_mean_v5(pool, np.random.default_rng(s))
                           for s in range(SMALL_RUN_SEEDS)]
            small_elapsed = time.time() - t0
            n_seeds = decide_seed_count(small_elapsed, SMALL_RUN_SEEDS, "timing")
            means = list(small_means[:n_seeds]) if n_seeds <= SMALL_RUN_SEEDS else list(small_means)

        t0 = time.time()
        for s in range(len(means), n_seeds):
            means.append(v5.timing_null_seed_mean_v5(pool, np.random.default_rng(s)))
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
        log(f"Stage 4 [selection null]: building month pools (subsequent bars fetched ONCE per pooled "
            f"entity-day) ... | mem={_mem_mb():.0f}MB")
        trades_by_month = (
            trades.assign(ym=trades["trade_date"].apply(lambda d: (d.year, d.month)))
            .groupby("ym").size().to_dict()
        )
        months = sorted(trades_by_month.keys())
        log(f"  {len(months)} (year,month) buckets with real trades")

        ckpt = _load_checkpoint(SELECTION_CKPT_PATH)
        if ckpt:
            per_month_draws = ckpt["per_month_draws"]
            n_seeds = ckpt["n_seeds"]
            done_months = set(ckpt["done_months"])
            log(f"Stage 4 [selection null]: resuming at {len(done_months)}/{len(months)} months from checkpoint")
        else:
            per_month_draws: dict = {}
            done_months: set = set()
            n_seeds = None

        entity_setup_cache: dict = {}
        t0 = time.time()
        for (year, month) in months:
            if (year, month) in done_months:
                continue
            count = trades_by_month[(year, month)]
            month_pool = v5.build_month_pool_v5(
                intraday_con, warehouse_con, universe, year, month, rank_lookup, jump_dates_by_entity,
                entity_setup_cache, dev_start, dev_end, dev_end,
            )
            if n_seeds is None:
                t1 = time.time()
                small_draws = [
                    v5.selection_null_seed_mean_v5(month_pool, count, np.random.default_rng(s))
                    for s in range(SMALL_RUN_SEEDS)
                ]
                small_elapsed = time.time() - t1
                n_seeds = decide_seed_count(small_elapsed * len(months), SMALL_RUN_SEEDS, "selection")
                per_month_draws[(year, month)] = small_draws + [
                    v5.selection_null_seed_mean_v5(month_pool, count, np.random.default_rng(s))
                    for s in range(SMALL_RUN_SEEDS, n_seeds)
                ]
            else:
                per_month_draws[(year, month)] = [
                    v5.selection_null_seed_mean_v5(month_pool, count, np.random.default_rng(s))
                    for s in range(n_seeds)
                ]
            done_months.add((year, month))
            _save_checkpoint(SELECTION_CKPT_PATH, {
                "per_month_draws": per_month_draws, "n_seeds": n_seeds, "done_months": list(done_months),
            })
            log(f"  selection: month {year}-{month:02d} done ({len(done_months)}/{len(months)}) "
                f"| pool_size={len(month_pool)} | mem={_mem_mb():.0f}MB | elapsed {time.time()-t0:.0f}s")

        seed_means = []
        for s in range(n_seeds):
            all_draws = [d for (year, month) in months for d in per_month_draws[(year, month)][s]]
            seed_means.append(float(np.mean(all_draws)) if all_draws else float("nan"))
        selection_result = {"means": np.array(seed_means), "n_seeds": n_seeds}
        with open(SELECTION_NULL_PATH, "wb") as f:
            pickle.dump(selection_result, f)
        log(f"Stage 4 [selection null]: saved to {SELECTION_NULL_PATH}")
        if SELECTION_CKPT_PATH.exists():
            SELECTION_CKPT_PATH.unlink()

    # ---------------- Stage 5: final report ----------------
    log("Stage 5 [report]: assembling Section 11 report ...")
    pct_timing = percentile_vs_null(inf["mean_net_r"], timing_result["means"][~np.isnan(timing_result["means"])])
    pct_selection = percentile_vs_null(inf["mean_net_r"],
                                        selection_result["means"][~np.isnan(selection_result["means"])])

    by_year = trades.groupby("year")["net_return_pct"].agg(["mean", "count"]).to_dict(orient="index")
    best_year = max(by_year, key=lambda y: by_year[y]["mean"]) if by_year else None
    ex_best = trades[trades["year"] != best_year] if best_year is not None else trades
    mean_ex_best = float(ex_best["net_return_pct"].mean()) if len(ex_best) else float("nan")

    band_100 = trades[trades["band"].isin(["1-50", "51-100"])]
    mean_band_100 = float(band_100["net_return_pct"].mean()) if len(band_100) else float("nan")

    passes = (
        inf["mean_net_r"] > 0 and excludes_zero(inf["ci_low"], inf["ci_high"])
        and pct_timing >= 95.0 and pct_selection >= 95.0
        and mean_ex_best > 0 and mean_band_100 > 0
    )

    by_band = trades.groupby("band")["net_return_pct"].agg(["mean", "count"]).to_dict(orient="index")
    sd = trades["stop_distance_pct"]
    hp = trades["entry_above_lookback_low_frac"]
    held = trades["trading_days_held"]

    total_setups_checked = sum(res["skips"].values()) + total_entries

    report = {
        "generated_at": dt.datetime.now().isoformat(), "window": "DEV",
        "unit": "PERCENTAGE OF POSITION VALUE (midpoint delivery cost) -- NOT R, NOT comparable to V1. "
                "Directly comparable to V2/V3/V4 (percentage of capital) but NOT the same cost model "
                "(delivery, not intraday).",
        "dev_start": str(dev_start), "dev_end": str(dev_end),
        "population_check": {
            "gate_population": len(trades), "boundary_truncated": len(boundary),
            "total_entries": total_entries, "expected": V5_EXPECTED_ENTRY_COUNT, "match": pop_match,
        },
        "n_trades": inf["n_trades"], "n_distinct_entry_days": inf["n_days"],
        "win_rate": float((trades["net_return_pct"] > 0).mean()),
        "mean_net_return_pct": inf["mean_net_r"], "median_net_return_pct": inf["median_net_r"],
        "ci_low": inf["ci_low"], "ci_high": inf["ci_high"], "mde": inf["mde"],
        "mean_net_return_pct_lo_cost": float(trades["net_return_pct_lo_cost"].mean()),
        "mean_net_return_pct_hi_cost": float(trades["net_return_pct_hi_cost"].mean()),
        "timing_null_percentile": pct_timing, "timing_null_n_seeds": int(timing_result["n_seeds"]),
        "timing_null_pool_size": timing_result["pool_size"],
        "selection_null_percentile": pct_selection, "selection_null_n_seeds": int(selection_result["n_seeds"]),
        "mean_net_return_pct_excl_best_year": mean_ex_best, "best_year_excluded": best_year,
        "mean_net_return_pct_bands_1_100": mean_band_100,
        "by_year": by_year, "by_band": by_band,
        "holding_period": {
            "trading_days_held": {"min": int(held.min()), "median": float(held.median()), "max": int(held.max())},
            "exit_mix_all": exit_mix, "exit_mix_entry_day": entry_day_exits, "exit_mix_overnight": overnight_exits,
        },
        "gap_through": {"count": gap_through_count, "fraction_of_trades": gap_through_count / len(trades),
                         "total_extra_loss_rs": gap_through_extra_loss_rs},
        "peak_concurrent_positions": peak_concurrent, "peak_deployed_capital_rs": peak_capital,
        "entry_above_lookback_low_frac": {"mean": float(hp.mean()), "median": float(hp.median()),
                                           "min": float(hp.min()), "max": float(hp.max())},
        "realised_stop_distance_pct": {"min": float(sd.min()), "median": float(sd.median()), "max": float(sd.max())},
        "total_cost_rs_mid": float(trades["cost_rs_mid"].sum()),
        "skips": res["skips"], "total_setups_checked": total_setups_checked,
        "lookback_incomplete_detail": {str(k): v for k, v in res["lookback_incomplete_detail"].items()},
        "boundary_truncated_count": len(boundary),
        "boundary_truncated_mean_net_return_pct": (
            float(boundary["net_return_pct"].mean()) if not boundary.empty else None
        ),
        "DEV_PASS": bool(passes),
        "claude_prediction": "DEV fails, mean net return between -1.5% and +0.5%",
    }

    if report["mean_net_return_pct"] <= 0 or not passes:
        log(f"=== BAD RESULT: DEV_PASS={passes} mean_net_return_pct={report['mean_net_return_pct']*100:.4f}% "
            f"-- see report for detail ===")
    log(f"=== POC V5 DEV result: PASS={passes} mean_net_return_pct={inf['mean_net_r']*100:.4f}% "
        f"CI=[{inf['ci_low']*100:.4f}%,{inf['ci_high']*100:.4f}%] timing_pct={pct_timing:.1f} "
        f"selection_pct={pct_selection:.1f} ex_best_year={mean_ex_best*100:.4f}% bands_1_100={mean_band_100*100:.4f}% "
        f"n_trades={inf['n_trades']} population_check={'MATCH' if pop_match else 'MISMATCH'} ===")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"Stage 5 [report]: saved to {REPORT_PATH}")
    log(f"=== POC V5 DEV run complete in {(time.time()-t_start)/60:.1f} min total | mem={_mem_mb():.0f}MB ===")


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke", action="store_true",
                    help="Tiny real-data integration check: 15 entities, a short window, "
                         "5-seed nulls, separate output dir (data/poc/v5/_smoke/). Never the real DEV run.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.smoke:
        OUT_DIR = ROOT / "data" / "poc" / "v5" / "_smoke"
        dev_start, dev_end = dt.date(2016, 10, 4), dt.date(2017, 12, 31)
        N_SEEDS_TARGET, SMALL_RUN_SEEDS = 10, 5
        con_tmp = get_warehouse_con(WAREHOUSE_DB)
        u_tmp = build_universe(con_tmp)
        entity_ids = sorted(u_tmp["entity_id"].unique())[:15]
    else:
        OUT_DIR = ROOT / "data" / "poc" / "v5"
        dev_start, dev_end = v5.DEV_START, v5.DEV_END
        entity_ids = None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKTEST_PATH = OUT_DIR / "dev_backtest.pkl"
    INFERENCE_PATH = OUT_DIR / "dev_inference.pkl"
    TIMING_NULL_PATH = OUT_DIR / "dev_timing_null.pkl"
    SELECTION_NULL_PATH = OUT_DIR / "dev_selection_null.pkl"
    BACKTEST_CKPT_PATH = OUT_DIR / "dev_backtest_checkpoint.pkl"
    TIMING_CKPT_PATH = OUT_DIR / "dev_timing_null_checkpoint.pkl"
    SELECTION_CKPT_PATH = OUT_DIR / "dev_selection_null_checkpoint.pkl"
    REPORT_PATH = OUT_DIR / "dev_report.json"
    LOG_PATH = OUT_DIR / "dev_run.log"

    main(dev_start, dev_end, entity_ids, args.smoke)
