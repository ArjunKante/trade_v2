"""AMENDED RE-TEST UNDER CORRECTED COST INPUTS (PREREGISTRATION_FIBO.md
Section 9) -- NOT a new backtest and NOT a new null simulation. This script
changes exactly one thing relative to scripts/fibo_test_backtest.py and
scripts/fibo_test_nulls.py: the spread/impact bps used to cost a trade.
Everything else -- frozen rules, the sealed trade list already saved in
data/fibo_test_results.pkl, the universe, the scale-probe decisions, and
every null draw's entity/day/entry-time/stop/target/exit -- is reproduced
EXACTLY, not re-decided.

For the real strategy trades this needs no DB access at all: every field
amended_cost_rs() needs (position_size_rs, band) is already sitting in
data/fibo_test_results.pkl.

For the null draws, the saved data/fibo_test_nulls.pkl only kept each
seed's AGGREGATE mean (mean_gross, mean_net_lo, mean_net_hi, mean_net_pess)
-- not the per-draw (entity, day, qty, entry_price, r, band) needed to
recompute a new cost figure after the fact. The only way to get an amended
null distribution built from the SAME draws (not new ones) is to replay
the null generation with the identical seeds and identical RNG call
sequence -- which reproduces the identical entity/day/entry-time/stop/
target/exit for every draw, bit-for-bit -- and tally one additional cost
figure per draw alongside the original ones. No random call is added,
removed, or reordered relative to scripts/fibo_test_nulls.py; the code
below is that script with one extra accumulator. The original
data/fibo_test_nulls.pkl is read-only here and never modified.

Writes data/fibo_test_nulls_amended.pkl (new file) and prints the
Section 9 report.
"""
import datetime as dt
import sys
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.bars import aggregate_to_15min
from fibo.resolution import resolve_trade, position_size_shares
from swing.costs import buy_leg_cost_rs, sell_leg_cost_rs
from fibo.intraday_db import get_read_connection as get_intraday_read_connection

ROOT = Path(__file__).resolve().parents[1]
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
RESULTS_PATH = ROOT / "data" / "fibo_test_results.pkl"
ORIGINAL_NULLS_PATH = ROOT / "data" / "fibo_test_nulls.pkl"          # read-only, untouched
AMENDED_NULLS_PATH = ROOT / "data" / "fibo_test_nulls_amended.pkl"   # new
CHECKPOINT_PATH = ROOT / "data" / "fibo_test_nulls_amended_checkpoint.pkl"
CHECKPOINT_EVERY = 10

N_SEEDS = 1000
EXIT_TIME = dt.time(15, 15)
ENTRY_CANDLE_STARTS = [dt.time(h, m) for h, m in
                       [(9, 30), (9, 45), (10, 0), (10, 15), (10, 30), (10, 45), (11, 0), (11, 15)]]

BAND_EDGES = [(1, 50, "1-50"), (51, 100, "51-100"), (101, 200, "101-200")]

# PREREGISTRATION_FIBO.md Section 8c, frozen 2026-10-08: live-measured
# round-trip spread/impact by band (~2x the measured median, stated there
# as an explicit conservatism margin). Replaces, for this amended re-test
# ONLY, both the flat 6.0/19.0bps scenarios and the 19bps x {1,2,4}
# pessimistic-multiplier scheme -- Section 6b's original sealed verdict is
# untouched by this file. Unranked (stub-year) entities fall back to the
# worst (101-200) figure, the same conservative convention the original
# pessimistic scenario used (BAND_MULTIPLIER.get(band, 4)).
FROZEN_SPREAD_BPS = {"1-50": 2.0, "51-100": 4.0, "101-200": 7.0, "unranked": 7.0}

bars_cache: dict = {}
processed_cache: dict = {}


def log(msg):
    print(msg, flush=True)


def band_for_rank(rank_lookup, entity_id, year) -> str:
    rank = rank_lookup.get((year, entity_id))
    if rank is None:
        return "unranked"
    for lo, hi, label in BAND_EDGES:
        if lo <= rank <= hi:
            return label
    return "unranked"


def amended_cost_rs(position_size_rs: float, band: str) -> float:
    fixed = buy_leg_cost_rs(position_size_rs, "INTRADAY") + sell_leg_cost_rs(position_size_rs, "INTRADAY")
    spread = position_size_rs * FROZEN_SPREAD_BPS.get(band, 7.0) / 10_000
    return fixed + spread


def get_bars(intraday_con, entity_id, day):
    key = (entity_id, day)
    if key in bars_cache:
        return bars_cache[key]
    bars = intraday_con.execute(
        "SELECT entity_id, trade_date, ts, open, high, low, close, volume FROM bars_1min "
        "WHERE entity_id = ? AND trade_date = ?", [entity_id, day],
    ).fetchdf()
    result = bars if not bars.empty else None
    bars_cache[key] = result
    return result


def get_processed(intraday_con, entity_id, day, scale):
    key = (entity_id, day, scale)
    if key in processed_cache:
        return processed_cache[key]
    bars = get_bars(intraday_con, entity_id, day)
    if bars is None:
        processed_cache[key] = None
        return None
    bars = bars.copy()
    for c in ("open", "high", "low", "close"):
        bars[c] = bars[c] * scale
    result = {"bars_1min": bars, "bars_15min": aggregate_to_15min(bars)}
    processed_cache[key] = result
    return result


def net_r_amended(gross_r, entry_price, qty, r, band):
    position_size_rs = qty * entry_price
    cost = amended_cost_rs(position_size_rs, band)
    return gross_r - cost / (r * qty)


def timing_null_amended(intraday_con, trades, scale_lookup, rank_lookup, rng):
    gross_list, amended_list = [], []
    for _, t in trades.iterrows():
        scale = scale_lookup[(t["entity_id"], t["trade_date"])]
        processed = get_processed(intraday_con, t["entity_id"], t["trade_date"], scale)
        if processed is None:
            continue
        bars, bars_15 = processed["bars_1min"], processed["bars_15min"]
        start = rng.choice(ENTRY_CANDLE_STARTS)
        candle = bars_15[bars_15["ts"].dt.time == start]
        if candle.empty:
            continue
        entry_price = float(candle["close"].iloc[0])
        entry_ts = candle["ts"].iloc[0] + pd.Timedelta(minutes=14)
        r = t["r_rupees"]
        stop = entry_price - r
        target = min(entry_price + 2 * r, t["swing_high_raw"])
        exit_ts = pd.Timestamp.combine(pd.Timestamp(t["trade_date"]), EXIT_TIME)
        res = resolve_trade(bars, entry_ts, stop, target, exit_ts)
        gross = (res["exit_price"] - entry_price) / r
        qty = t["qty"]
        band = band_for_rank(rank_lookup, t["entity_id"], t["trade_date"].year)
        gross_list.append(gross)
        amended_list.append(net_r_amended(gross, entry_price, qty, r, band))
    if not gross_list:
        return {"mean_gross": float("nan"), "mean_net_amended": float("nan")}
    return {"mean_gross": np.mean(gross_list), "mean_net_amended": np.mean(amended_list)}


def build_month_pools(m: pd.DataFrame, universe: pd.DataFrame, require_uptrend: bool = False) -> dict:
    from fibo.scale_probe import ScaleDecision
    resolved = m[m["scale_decision"].isin([ScaleDecision.RAW_EQUIVALENT, ScaleDecision.SCALED])].copy()
    if require_uptrend:
        resolved = resolved[resolved["uptrend"] == True]  # noqa: E712
    resolved["year"] = resolved["trade_date"].apply(lambda d: d.year)
    resolved["month"] = resolved["trade_date"].apply(lambda d: d.month)
    year_members = {y: set(g["entity_id"]) for y, g in universe.groupby("year")}

    pools = {}
    for (y, mo), grp in resolved.groupby(["year", "month"]):
        members = year_members.get(y, set())
        eligible = grp[grp["entity_id"].isin(members)]
        pools[(y, mo)] = list(zip(eligible["entity_id"], eligible["trade_date"], eligible["scale"]))
    return pools


def selection_null_amended(intraday_con, trades, month_pools, r_distribution, rank_lookup, rng):
    counts_per_month = trades.groupby(trades["trade_date"].apply(lambda d: (d.year, d.month))).size()
    gross_list, amended_list = [], []
    for ym, count in counts_per_month.items():
        pool = month_pools.get(ym, [])
        if not pool:
            continue
        for _ in range(count):
            for _attempt in range(10):
                entity_id, day, scale = pool[rng.integers(len(pool))]
                processed = get_processed(intraday_con, entity_id, day, scale)
                if processed is None:
                    continue
                bars, bars_15 = processed["bars_1min"], processed["bars_15min"]
                start = rng.choice(ENTRY_CANDLE_STARTS)
                candle = bars_15[bars_15["ts"].dt.time == start]
                if candle.empty:
                    continue
                entry_price = float(candle["close"].iloc[0])
                entry_ts = candle["ts"].iloc[0] + pd.Timedelta(minutes=14)
                r = float(rng.choice(r_distribution))
                stop = entry_price - r
                target = entry_price + 2 * r
                exit_ts = pd.Timestamp.combine(pd.Timestamp(day), EXIT_TIME)
                res = resolve_trade(bars, entry_ts, stop, target, exit_ts)
                gross = (res["exit_price"] - entry_price) / r
                try:
                    qty = position_size_shares(entry_price, stop)
                except ValueError:
                    break
                if qty < 1:
                    break
                band = band_for_rank(rank_lookup, entity_id, day.year)
                gross_list.append(gross)
                amended_list.append(net_r_amended(gross, entry_price, qty, r, band))
                break
    if not gross_list:
        return {"mean_gross": float("nan"), "mean_net_amended": float("nan")}
    return {"mean_gross": np.mean(gross_list), "mean_net_amended": np.mean(amended_list)}


def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "rb") as f:
            return pickle.load(f)
    return {}


def save_checkpoint(ckpt: dict) -> None:
    tmp = CHECKPOINT_PATH.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(ckpt, f)
    tmp.replace(CHECKPOINT_PATH)


def run_seeds(name: str, seed_fn, n_seeds: int, ckpt: dict) -> pd.DataFrame:
    results = ckpt.get(name, [])
    start = len(results)
    if start >= n_seeds:
        log(f"  {name}: {start}/{n_seeds} already done (checkpoint) -- skipping")
        return pd.DataFrame(results[:n_seeds])
    if start:
        log(f"  {name}: resuming from checkpoint at seed {start}/{n_seeds}")
    for seed in range(start, n_seeds):
        rng = np.random.default_rng(seed)
        results.append(seed_fn(rng))
        if (seed + 1) % CHECKPOINT_EVERY == 0 or seed + 1 == n_seeds:
            ckpt[name] = results
            save_checkpoint(ckpt)
            log(f"  {name}: {seed + 1}/{n_seeds} seeds done (checkpointed)")
    return pd.DataFrame(results)


def main():
    with open(RESULTS_PATH, "rb") as f:
        d = pickle.load(f)
    trades = d["trades"]
    m = d["m"]
    universe = d["universe"]
    scale_lookup = dict(zip(zip(m["entity_id"], m["trade_date"]), m["scale"]))
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}
    r_distribution = trades["r_rupees"].to_numpy()

    with open(ORIGINAL_NULLS_PATH, "rb") as f:
        original_nulls = pickle.load(f)

    # Amended cost for the real strategy trades: no DB access needed, every
    # field is already in data/fibo_test_results.pkl.
    trades = trades.copy()
    trades["cost_amended_rs"] = trades.apply(
        lambda r: amended_cost_rs(r["position_size_rs"], r["band"]), axis=1
    )
    trades["cost_amended_r"] = trades["cost_amended_rs"] / (trades["r_rupees"] * trades["qty"])
    trades["net_r_amended"] = trades["gross_r"] - trades["cost_amended_r"]

    intraday_con = get_intraday_read_connection(INTRADAY_DB)
    ckpt = load_checkpoint()

    log(f"Strategy (sealed test, {len(trades)} trades): mean gross R = {trades['gross_r'].mean():.4f}, "
        f"mean net R (amended) = {trades['net_r_amended'].mean():.4f}")

    log(f"\n=== (a) TIMING null, amended cost, {N_SEEDS} seeds (same draws as the original run) ===")
    timing_df = run_seeds(
        "timing", lambda rng: timing_null_amended(intraday_con, trades, scale_lookup, rank_lookup, rng),
        N_SEEDS, ckpt,
    )

    log(f"\n=== (b) SELECTION null, amended cost, {N_SEEDS} seeds ===")
    month_pools_b = build_month_pools(m, universe, require_uptrend=False)
    selection_b_df = run_seeds(
        "selection_b",
        lambda rng: selection_null_amended(intraday_con, trades, month_pools_b, r_distribution, rank_lookup, rng),
        N_SEEDS, ckpt,
    )

    log(f"\n=== (b2) SELECTION null, UPTREND-RESTRICTED, amended cost, {N_SEEDS} seeds ===")
    month_pools_b2 = build_month_pools(m, universe, require_uptrend=True)
    selection_b2_df = run_seeds(
        "selection_b2",
        lambda rng: selection_null_amended(intraday_con, trades, month_pools_b2, r_distribution, rank_lookup, rng),
        N_SEEDS, ckpt,
    )

    # Sanity check: mean_gross here should reproduce the ORIGINAL run's
    # mean_gross almost exactly (same seeds, same RNG call sequence, same
    # bars) -- confirms this is a replay of the same draws, not a new
    # simulation, before trusting the amended cost numbers built on top of it.
    for name, amended_df in [("timing", timing_df), ("selection_b", selection_b_df), ("selection_b2", selection_b2_df)]:
        orig_mean_gross = original_nulls[name]["mean_gross"].mean()
        repl_mean_gross = amended_df["mean_gross"].mean()
        diff = abs(orig_mean_gross - repl_mean_gross)
        log(f"\nReplay check [{name}]: original mean_gross={orig_mean_gross:.6f}, "
            f"replayed mean_gross={repl_mean_gross:.6f}, diff={diff:.2e} "
            f"{'(MATCH)' if diff < 1e-9 else '*** MISMATCH -- NOT a faithful replay ***'}")

    with open(AMENDED_NULLS_PATH, "wb") as f:
        pickle.dump({
            "timing": timing_df, "selection_b": selection_b_df, "selection_b2": selection_b2_df,
        }, f)
    log(f"\nSaved to {AMENDED_NULLS_PATH}")

    with open(RESULTS_PATH.with_name("fibo_test_results_amended.pkl"), "wb") as f:
        pickle.dump({"trades": trades}, f)
    log(f"Saved amended trade costs to {RESULTS_PATH.with_name('fibo_test_results_amended.pkl')}")


if __name__ == "__main__":
    main()
