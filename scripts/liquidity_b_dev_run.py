"""PREREGISTRATION_LIQUIDITY_B.md Process Step 4: run DEV ONLY
(2016-10-04 to 2022-12-31), real trades + TIMING + SELECTION nulls, in
that order, and produce the Section 11 report. Does NOT authorize the
sealed TEST window -- `liquidity.b.guard_date_range` is called with
`authorize_test=False` (the default) against the DEV range, a no-op
since DEV never intersects the sealed window; TEST is never touched.

Checkpointed in stages, mirroring scripts/liquidity_a_dev_run.py exactly,
adapted for Study B's own module (`liquidity.b`) and field names
(new_high_during_reclaim instead of new_low_during_reclaim; HIGH-side
`hi_3m` NaN check instead of `lo_3m`; short-side pnl sign convention is
already baked into liquidity.b's own trade records, not re-derived here).
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

import liquidity.b as b
from poc.backtest import build_universe

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

# Study A's own headline DEV figures -- orientation only, the real
# comparison this report is built around (PREREGISTRATION_LIQUIDITY_B.md
# Section 11).
STUDY_A_N_TRADES = 8_131
STUDY_A_MEAN_NET_RETURN_PCT = -0.2841
STUDY_A_TIMING_PCT = 100.0
STUDY_A_SELECTION_PCT = 100.0
STUDY_A_HALF_REACH_RATE = 0.216
STUDY_A_FULL_AFTER_HALF_RATE = 0.231
STUDY_A_1D_1W_SHARE = 0.786

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
            f"{N_SEEDS_TARGET}, same contingency as the POC family's own dev runs")
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
        total_skips = ckpt["total_skips"]
        all_sweep_depths = ckpt["all_sweep_depths"]
        total_new_high_during_reclaim = ckpt["total_new_high_during_reclaim"]
        total_reached_reclaim = ckpt["total_reached_reclaim"]
        all_errors = ckpt["all_errors"]
        done_entities = set(ckpt["done_entities"])
        log(f"Stage 1 [backtest]: resuming at {len(done_entities)}/{len(ordered_entities)} entities from checkpoint")
    else:
        all_trades, all_errors = [], []
        total_skips = {r: 0 for r in b.SKIP_REASONS}
        all_sweep_depths: list[float] = []
        total_new_high_during_reclaim = 0
        total_reached_reclaim = 0
        done_entities: set = set()

    remaining = [e for e in ordered_entities if e not in done_entities]
    t0 = time.time()
    for i, entity_id in enumerate(remaining):
        jump_dates = jump_dates_by_entity.get(entity_id, set())
        result = b.evaluate_entity_b(
            intraday_con, warehouse_con, entity_id, filtered_entity_years[entity_id],
            dev_start, dev_end, jump_dates, rank_lookup,
        )
        all_trades.extend(result["trades"])
        for k in total_skips:
            total_skips[k] += result["skips"][k]
        all_sweep_depths.extend(result["sweep_depths_atr"])
        total_new_high_during_reclaim += result["new_high_during_reclaim_count"]
        total_reached_reclaim += result["reached_reclaim_count"]
        all_errors.extend(result["errors"])
        done_entities.add(entity_id)

        if (i + 1) % ENTITY_CHECKPOINT_EVERY == 0 or (i + 1) == len(remaining):
            _save_checkpoint(BACKTEST_CKPT_PATH, {
                "all_trades": all_trades, "total_skips": total_skips, "all_sweep_depths": all_sweep_depths,
                "total_new_high_during_reclaim": total_new_high_during_reclaim,
                "total_reached_reclaim": total_reached_reclaim,
                "all_errors": all_errors, "done_entities": list(done_entities),
            })
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining_n = len(remaining) - (i + 1)
            eta_min = (remaining_n / rate / 60) if rate > 0 else float("nan")
            log(f"  backtest: {len(done_entities)}/{len(ordered_entities)} entities done "
                f"({elapsed:.0f}s elapsed this run, ~{rate:.2f} entities/s, ETA {eta_min:.1f} min) | "
                f"trades so far={len(all_trades)} | mem={_mem_mb():.0f}MB")

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        check = trades_df[["entity_id", "year"]].drop_duplicates()
        assert_universe_membership(check, universe, label="liquidity study B trade list")

    return {
        "trades": trades_df, "skips": total_skips, "sweep_depths_atr": all_sweep_depths,
        "new_high_during_reclaim_count": total_new_high_during_reclaim,
        "reached_reclaim_count": total_reached_reclaim, "errors": all_errors, "universe": universe,
    }


def _confluence_breakdown(trades: pd.DataFrame) -> dict:
    labels = trades["confluence_members"].apply(lambda m: "+".join(m))
    out = {}
    for label, grp in trades.groupby(labels):
        out[label] = {
            "count": int(len(grp)), "mean_net_return_pct": float(grp["net_return_pct"].mean()),
            "win_rate": float((grp["net_return_pct"] > 0).mean()),
        }
    return out


def _half_full_breakdown(trades: pd.DataFrame) -> dict:
    qty1 = trades[trades["qty1_path"]]
    scaled = trades[~trades["qty1_path"]]
    half_reached = scaled[scaled["half_exit_happened"]]
    full_reached = half_reached[half_reached["outcome"].isin(["FULL_EXIT", "FULL_EXIT_SAME_BAR"])]
    half_then_stopped = half_reached[half_reached["outcome"] == "HALF_THEN_STOP"]
    return {
        "n_trades": int(len(trades)), "n_qty1_path": int(len(qty1)), "n_scaled_eligible": int(len(scaled)),
        "n_half_exit_reached": int(len(half_reached)),
        "half_exit_reach_rate_of_scaled": float(len(half_reached) / len(scaled)) if len(scaled) else None,
        "n_full_target_after_half": int(len(full_reached)),
        "full_target_rate_of_half_reached": float(len(full_reached) / len(half_reached)) if len(half_reached) else None,
        "n_half_then_stopped": int(len(half_then_stopped)),
        "half_then_stopped_rate_of_half_reached": (
            float(len(half_then_stopped) / len(half_reached)) if len(half_reached) else None
        ),
    }


def _peak_concurrent_and_capital(trades: pd.DataFrame) -> dict:
    """Identical two-separate-event-sweep logic to liquidity_a_dev_run.py's
    own (already fixed-forward) version -- a half-exited trade is still
    exactly ONE open position until its own final exit; capital steps
    down twice for such a trade. Not re-derived from the buggy first
    version Study A found and fixed; built correctly from the start."""
    position_events = []
    capital_events = []
    for _, tr in trades.iterrows():
        qty, entry_price = tr["qty"], tr["entry_price"]
        position_events.append((tr["fill_ts"], 1))
        position_events.append((tr["final_exit_ts"], -1))
        capital_events.append((tr["fill_ts"], qty * entry_price))
        if tr["half_exit_happened"]:
            half_qty = tr["half_qty"]
            capital_events.append((tr["half_exit_ts"], -(half_qty * entry_price)))
            capital_events.append((tr["final_exit_ts"], -((qty - half_qty) * entry_price)))
        else:
            capital_events.append((tr["final_exit_ts"], -(qty * entry_price)))

    position_events.sort(key=lambda x: (x[0], -x[1]))
    cur_positions = peak_positions = 0
    for _, delta in position_events:
        cur_positions += delta
        peak_positions = max(peak_positions, cur_positions)

    capital_events.sort(key=lambda x: (x[0], 0 if x[1] > 0 else 1))
    cur_capital = peak_capital = 0.0
    for _, delta in capital_events:
        cur_capital += delta
        peak_capital = max(peak_capital, cur_capital)

    return {"peak_concurrent_positions": int(peak_positions), "peak_deployed_capital_rs": float(peak_capital)}


def main(dev_start: dt.date, dev_end: dt.date, entity_ids: list[str] | None, smoke: bool):
    t_start = time.time()
    log(f"=== Liquidity Study B DEV run starting ({'SMOKE TEST' if smoke else 'REAL'}) | mem={_mem_mb():.0f}MB ===")

    warehouse_con = get_warehouse_con(WAREHOUSE_DB)
    intraday_con = get_intraday_con(INTRADAY_DB)
    if not smoke:
        assert (dev_start, dev_end) == (b.DEV_START, b.DEV_END), \
            "real (non-smoke) run must use the exact frozen DEV window"
    b.guard_date_range(dev_start, dev_end, authorize_test=False,
                        caller="liquidity_b_dev_run.py", reason="DEV-only run")
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
            f"{len(res['trades'])} trades, errors={len(res['errors'])}")
        if res["errors"]:
            for e in res["errors"][:20]:
                log(f"  ENTITY ERROR: {e}")
        with open(BACKTEST_PATH, "wb") as f:
            pickle.dump(res, f)
        log(f"Stage 1 [backtest]: saved to {BACKTEST_PATH}")
        if BACKTEST_CKPT_PATH.exists():
            BACKTEST_CKPT_PATH.unlink()

    trades = res["trades"]
    universe = res["universe"]

    log(f"  skip breakdown: {res['skips']}")
    if res["reached_reclaim_count"]:
        log(f"  new high during reclaim wait: {res['new_high_during_reclaim_count']}/"
            f"{res['reached_reclaim_count']} days that reached RECLAIM "
            f"({res['new_high_during_reclaim_count']/res['reached_reclaim_count']*100:.1f}%)")
    if res["sweep_depths_atr"]:
        sd = np.array(res["sweep_depths_atr"])
        log(f"  sweep depth (x ATR) at detection: min={sd.min():.4f} median={np.median(sd):.4f} max={sd.max():.4f} "
            f"n={len(sd)}")
    log(f"  trade count vs. Study A's own headline: {len(trades)} vs A's {STUDY_A_N_TRADES}")

    if trades.empty:
        log("=== NO TRADES in DEV window. NO EDGE by construction -- stopping here. ===")
        return

    # ---------------- Stage 2: inference ----------------
    if INFERENCE_PATH.exists():
        log(f"Stage 2 [inference]: found existing {INFERENCE_PATH}, loading")
        with open(INFERENCE_PATH, "rb") as f:
            inf = pickle.load(f)
    else:
        log("Stage 2 [inference]: day-clustered bootstrap on real trades (net_return_pct) ...")
        inf = day_clustered_bootstrap(trades, net_r_col="net_return_pct", seed=0)
        log(f"  n_trades={inf['n_trades']} n_days={inf['n_days']} mean_net_return_pct={inf['mean_net_r']*100:.4f}% "
            f"CI=[{inf['ci_low']*100:.4f}%,{inf['ci_high']*100:.4f}%] mde={inf['mde']*100:.4f}%")
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
        log(f"Stage 3 [timing null]: building pool ... | mem={_mem_mb():.0f}MB")
        t0 = time.time()
        pool = b.build_timing_pool_b(intraday_con, warehouse_con, trades, rank_lookup, jump_dates_by_entity)
        log(f"  pool size={len(pool)} ({time.time()-t0:.1f}s)")

        ckpt = _load_checkpoint(TIMING_CKPT_PATH)
        if ckpt:
            means = list(ckpt["means"])
            n_seeds = ckpt["n_seeds"]
            log(f"Stage 3 [timing null]: resuming at seed {len(means)}/{n_seeds} from checkpoint")
        else:
            t0 = time.time()
            small_means = [b.timing_null_seed_mean_b(pool, np.random.default_rng(s))
                           for s in range(SMALL_RUN_SEEDS)]
            small_elapsed = time.time() - t0
            n_seeds = decide_seed_count(small_elapsed, SMALL_RUN_SEEDS, "timing")
            means = list(small_means[:n_seeds]) if n_seeds <= SMALL_RUN_SEEDS else list(small_means)

        t0 = time.time()
        for s in range(len(means), n_seeds):
            means.append(b.timing_null_seed_mean_b(pool, np.random.default_rng(s)))
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
    rho_pool = trades["stop_distance_pct"].to_numpy()
    if SELECTION_NULL_PATH.exists():
        log(f"Stage 4 [selection null]: found existing {SELECTION_NULL_PATH}, loading")
        with open(SELECTION_NULL_PATH, "rb") as f:
            selection_result = pickle.load(f)
    else:
        log(f"Stage 4 [selection null]: building month pools ... | mem={_mem_mb():.0f}MB")
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
            month_pool = b.build_month_pool_b(
                intraday_con, warehouse_con, universe, year, month, rank_lookup, jump_dates_by_entity,
                entity_setup_cache, dev_start, dev_end,
            )
            if n_seeds is None:
                t1 = time.time()
                small_draws = [
                    b.selection_null_seed_mean_b(month_pool, count, np.random.default_rng(s), rho_pool)
                    for s in range(SMALL_RUN_SEEDS)
                ]
                small_elapsed = time.time() - t1
                n_seeds = decide_seed_count(small_elapsed * len(months), SMALL_RUN_SEEDS, "selection")
                per_month_draws[(year, month)] = small_draws + [
                    b.selection_null_seed_mean_b(month_pool, count, np.random.default_rng(s), rho_pool)
                    for s in range(SMALL_RUN_SEEDS, n_seeds)
                ]
            else:
                per_month_draws[(year, month)] = [
                    b.selection_null_seed_mean_b(month_pool, count, np.random.default_rng(s), rho_pool)
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
    exit_mix = trades["outcome"].value_counts().to_dict()
    time_exit_fallback_count = int(trades["time_exit_fallback"].sum())
    multi_cluster_count = int(trades["multi_cluster"].sum())

    hp = trades["sweep_depth_atr"]
    sd = trades["stop_distance_pct"]
    extra_cost = trades["extra_cost_rs"]
    extra_cost_pct = extra_cost / trades["position_size_rs"]
    peak = _peak_concurrent_and_capital(trades)
    confluence_breakdown = _confluence_breakdown(trades)
    half_full = _half_full_breakdown(trades)

    # STT asymmetry check (Section 6 prediction): entry-leg STT is fixed
    # at entry_value_rs * 2.5bps on EVERY trade -- compute it directly and
    # report its own (near-zero) variance relative to position size.
    entry_stt_rs = trades["qty"] * trades["entry_price"] * 2.5 / 10_000
    entry_stt_pct_of_position = entry_stt_rs / trades["position_size_rs"]

    total_setups_checked = sum(res["skips"].values()) + len(trades)

    # Direct Study A vs. Study B comparison block (Section 11's own point)
    one_d_one_w = confluence_breakdown.get("1d+1w", {"count": 0})
    study_a_vs_b = {
        "n_trades": {"study_a": STUDY_A_N_TRADES, "study_b": int(len(trades))},
        "mean_net_return_pct": {"study_a": STUDY_A_MEAN_NET_RETURN_PCT, "study_b": inf["mean_net_r"] * 100},
        "timing_null_percentile": {"study_a": STUDY_A_TIMING_PCT, "study_b": pct_timing},
        "selection_null_percentile": {"study_a": STUDY_A_SELECTION_PCT, "study_b": pct_selection},
        "half_target_reach_rate": {
            "study_a": STUDY_A_HALF_REACH_RATE, "study_b": half_full["half_exit_reach_rate_of_scaled"],
        },
        "full_after_half_rate": {
            "study_a": STUDY_A_FULL_AFTER_HALF_RATE, "study_b": half_full["full_target_rate_of_half_reached"],
        },
        "1d_1w_confluence_share": {
            "study_a": STUDY_A_1D_1W_SHARE,
            "study_b": (one_d_one_w["count"] / len(trades)) if len(trades) else None,
        },
    }

    report = {
        "generated_at": dt.datetime.now().isoformat(), "window": "DEV",
        "unit": "PERCENTAGE OF POSITION VALUE (entry qty x entry_price)",
        "dev_start": str(dev_start), "dev_end": str(dev_end),
        "n_trades": inf["n_trades"], "n_distinct_entry_days": inf["n_days"],
        "study_a_vs_study_b": study_a_vs_b,
        "win_rate": float((trades["net_return_pct"] > 0).mean()),
        "mean_net_return_pct": inf["mean_net_r"], "median_net_return_pct": inf["median_net_r"],
        "ci_low": inf["ci_low"], "ci_high": inf["ci_high"], "mde": inf["mde"],
        "timing_null_percentile": pct_timing, "timing_null_n_seeds": int(timing_result["n_seeds"]),
        "timing_null_pool_size": timing_result["pool_size"],
        "selection_null_percentile": pct_selection, "selection_null_n_seeds": int(selection_result["n_seeds"]),
        "mean_net_return_pct_excl_best_year": mean_ex_best, "best_year_excluded": best_year,
        "mean_net_return_pct_bands_1_100": mean_band_100,
        "by_year": by_year, "by_band": by_band,
        "sweep_depth_atr_at_detection": {"mean": float(hp.mean()), "median": float(hp.median()),
                                          "min": float(hp.min()), "max": float(hp.max())},
        "realised_stop_distance_pct": {"min": float(sd.min()), "median": float(sd.median()), "max": float(sd.max())},
        "exit_mix": exit_mix, "time_exit_fallback_count": time_exit_fallback_count,
        "multi_cluster_count": multi_cluster_count,
        "confluence_breakdown": confluence_breakdown,
        "half_full_breakdown": half_full,
        "extra_cost_three_order_vs_hypothetical": {
            "total_rs": float(extra_cost.sum()), "mean_rs": float(extra_cost.mean()),
            "mean_pct_of_position": float(extra_cost_pct.mean()),
        },
        "entry_leg_stt_rs": {
            "mean": float(entry_stt_rs.mean()), "std": float(entry_stt_rs.std()),
            "mean_pct_of_position": float(entry_stt_pct_of_position.mean()),
            "std_pct_of_position": float(entry_stt_pct_of_position.std()),
        },
        "skips": res["skips"], "total_setups_checked": total_setups_checked,
        "new_high_during_reclaim": {
            "count": res["new_high_during_reclaim_count"], "reached_reclaim_count": res["reached_reclaim_count"],
            "fraction": (res["new_high_during_reclaim_count"] / res["reached_reclaim_count"]
                         if res["reached_reclaim_count"] else None),
        },
        "peak_concurrent_positions": peak["peak_concurrent_positions"],
        "peak_deployed_capital_rs": peak["peak_deployed_capital_rs"],
        "DEV_PASS": bool(passes),
        "claude_prediction": "DEV fails, mean net return between -0.5% and 0%, trade count similar to Study A's 8,131",
    }

    if report["mean_net_return_pct"] <= 0 or not passes:
        log(f"=== BAD RESULT: DEV_PASS={passes} mean_net_return_pct={report['mean_net_return_pct']*100:.4f}% "
            f"-- see report for detail ===")
    log(f"=== Liquidity Study B DEV result: PASS={passes} mean_net_return_pct={inf['mean_net_r']*100:.4f}% "
        f"CI=[{inf['ci_low']*100:.4f}%,{inf['ci_high']*100:.4f}%] timing_pct={pct_timing:.1f} "
        f"selection_pct={pct_selection:.1f} ex_best_year={mean_ex_best*100:.4f}% bands_1_100={mean_band_100*100:.4f}% "
        f"n_trades={inf['n_trades']} (Study A: n={STUDY_A_N_TRADES} mean={STUDY_A_MEAN_NET_RETURN_PCT:.4f}%) ===")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"Stage 5 [report]: saved to {REPORT_PATH}")
    log(f"=== Liquidity Study B DEV run complete in {(time.time()-t_start)/60:.1f} min total | mem={_mem_mb():.0f}MB ===")


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke", action="store_true",
                    help="Tiny real-data integration check: 15 entities, a short window, "
                         "5-seed nulls, separate output dir (data/liquidity/b/_smoke/). Never the real DEV run.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.smoke:
        OUT_DIR = ROOT / "data" / "liquidity" / "b" / "_smoke"
        dev_start, dev_end = dt.date(2016, 10, 4), dt.date(2017, 12, 31)
        N_SEEDS_TARGET, SMALL_RUN_SEEDS = 10, 5
        con_tmp = get_warehouse_con(WAREHOUSE_DB)
        u_tmp = build_universe(con_tmp)
        entity_ids = sorted(u_tmp["entity_id"].unique())[:15]
    else:
        OUT_DIR = ROOT / "data" / "liquidity" / "b"
        dev_start, dev_end = b.DEV_START, b.DEV_END
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
