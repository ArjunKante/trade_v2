"""THE SEALED TEST's nulls: (a) TIMING, (b) SELECTION, (b2) SELECTION
UPTREND-RESTRICTED -- all computed on the TEST WINDOW's own data (per
PREREGISTRATION_FIBO.md Section 5a/5b: nulls (b)/(b2) must be computed on
the test window's own data, not reused from development). 1000 seeds each.

Each null draw also gets a PESSIMISTIC banded cost (Section 5b scenario
iii), using that draw's OWN (entity, day)'s rank band -- a fair
like-for-like comparison against the strategy's own pessimistic-cost mean,
not the strategy held to a harsher standard than the null it's compared
against.

Mirrors scripts/fibo_step5_nulls.py's mechanism (same caching strategy,
same resolve_trade/position_size_shares plumbing) -- extended with the
third cost scenario and run against scripts/fibo_test_backtest.py's output
instead of development's.
"""
import datetime as dt
import sys
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.bars import aggregate_to_15min
from fibo.backtest import ENTRY_WINDOW_START
from fibo.resolution import resolve_trade, position_size_shares
from swing.costs import round_trip_cost_rs, buy_leg_cost_rs, sell_leg_cost_rs, SPREAD_IMPACT_ROUND_TRIP_BPS_HI
from fibo.intraday_db import get_read_connection as get_intraday_read_connection

ROOT = Path(__file__).resolve().parents[1]
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
RESULTS_PATH = ROOT / "data" / "fibo_test_results.pkl"
NULLS_PATH = ROOT / "data" / "fibo_test_nulls.pkl"
CHECKPOINT_PATH = ROOT / "data" / "fibo_test_nulls_checkpoint.pkl"
CHECKPOINT_EVERY = 10
# This environment has repeatedly killed this long-running process externally
# (no rate-limit/error -- just an abrupt stop) before any null type finishes
# its 1000 seeds. Without a checkpoint, every kill meant redoing the whole
# thing from seed 0 -- found live, twice, on the sealed-test run itself.
# Checkpointing per-seed results to disk (not re-deciding anything, not
# touching the frozen trade list) lets a relaunch resume mid-null-type
# instead of restarting, same resumability discipline as the download
# scripts' fetch_log_intraday table.

N_SEEDS = 1000
EXIT_TIME = dt.time(15, 15)
ENTRY_CANDLE_STARTS = [dt.time(h, m) for h, m in
                       [(9, 30), (9, 45), (10, 0), (10, 15), (10, 30), (10, 45), (11, 0), (11, 15)]]

BAND_EDGES = [(1, 50, "1-50"), (51, 100, "51-100"), (101, 200, "101-200")]
BAND_MULTIPLIER = {"1-50": 1, "51-100": 2, "101-200": 4}

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


def pessimistic_cost_rs(position_size_rs: float, band: str) -> float:
    fixed = buy_leg_cost_rs(position_size_rs, "INTRADAY") + sell_leg_cost_rs(position_size_rs, "INTRADAY")
    mult = BAND_MULTIPLIER.get(band, 4)
    spread = position_size_rs * SPREAD_IMPACT_ROUND_TRIP_BPS_HI / 10_000 * mult
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


def net_r_all(gross_r, entry_price, qty, r, band):
    position_size_rs = qty * entry_price
    cost_lo, cost_hi = round_trip_cost_rs(position_size_rs, "INTRADAY")
    cost_pess = pessimistic_cost_rs(position_size_rs, band)
    return (gross_r - cost_lo / (r * qty), gross_r - cost_hi / (r * qty), gross_r - cost_pess / (r * qty))


def timing_null(intraday_con, trades, scale_lookup, rank_lookup, rng):
    gross_list, lo_list, hi_list, pess_list = [], [], [], []
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
        nlo, nhi, npess = net_r_all(gross, entry_price, qty, r, band)
        gross_list.append(gross); lo_list.append(nlo); hi_list.append(nhi); pess_list.append(npess)
    if not gross_list:
        return {"mean_gross": float("nan"), "mean_net_lo": float("nan"), "mean_net_hi": float("nan"), "mean_net_pess": float("nan")}
    return {"mean_gross": np.mean(gross_list), "mean_net_lo": np.mean(lo_list),
            "mean_net_hi": np.mean(hi_list), "mean_net_pess": np.mean(pess_list)}


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


def selection_null(intraday_con, trades, month_pools, r_distribution, rank_lookup, rng):
    counts_per_month = trades.groupby(trades["trade_date"].apply(lambda d: (d.year, d.month))).size()
    gross_list, lo_list, hi_list, pess_list = [], [], [], []
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
                nlo, nhi, npess = net_r_all(gross, entry_price, qty, r, band)
                gross_list.append(gross); lo_list.append(nlo); hi_list.append(nhi); pess_list.append(npess)
                break
    if not gross_list:
        return {"mean_gross": float("nan"), "mean_net_lo": float("nan"), "mean_net_hi": float("nan"), "mean_net_pess": float("nan")}
    return {"mean_gross": np.mean(gross_list), "mean_net_lo": np.mean(lo_list),
            "mean_net_hi": np.mean(hi_list), "mean_net_pess": np.mean(pess_list)}


def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "rb") as f:
            return pickle.load(f)
    return {}


def save_checkpoint(ckpt: dict) -> None:
    tmp = CHECKPOINT_PATH.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(ckpt, f)
    tmp.replace(CHECKPOINT_PATH)  # atomic-ish swap, never leaves a half-written checkpoint


def run_seeds(name: str, seed_fn, n_seeds: int, ckpt: dict) -> pd.DataFrame:
    """Runs seed_fn(rng) for seeds not already in ckpt[name], saving progress
    every CHECKPOINT_EVERY seeds so an external kill mid-run loses at most
    that many seeds' work, never the whole null type."""
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

    intraday_con = get_intraday_read_connection(INTRADAY_DB)
    ckpt = load_checkpoint()

    log(f"Strategy (sealed test): {len(trades)} trades. Mean gross R = {trades['gross_r'].mean():.4f}, "
        f"mean net R (lo) = {trades['net_r_lo_cost'].mean():.4f}, "
        f"mean net R (hi) = {trades['net_r_hi_cost'].mean():.4f}, "
        f"mean net R (pessimistic) = {trades['net_r_pessimistic'].mean():.4f}")

    log(f"\n=== (a) TIMING null: {N_SEEDS} seeds ===")
    timing_df = run_seeds(
        "timing", lambda rng: timing_null(intraday_con, trades, scale_lookup, rank_lookup, rng), N_SEEDS, ckpt
    )

    log(f"\n=== (b) SELECTION null: {N_SEEDS} seeds ===")
    month_pools_b = build_month_pools(m, universe, require_uptrend=False)
    selection_b_df = run_seeds(
        "selection_b",
        lambda rng: selection_null(intraday_con, trades, month_pools_b, r_distribution, rank_lookup, rng),
        N_SEEDS, ckpt,
    )

    log(f"\n=== (b2) SELECTION null, UPTREND-RESTRICTED: {N_SEEDS} seeds ===")
    month_pools_b2 = build_month_pools(m, universe, require_uptrend=True)
    pool_size_b = sum(len(v) for v in month_pools_b.values())
    pool_size_b2 = sum(len(v) for v in month_pools_b2.values())
    log(f"(b2) pool size: {pool_size_b2} of {pool_size_b} (b) pairs ({pool_size_b2/pool_size_b*100:.1f}%).")
    selection_b2_df = run_seeds(
        "selection_b2",
        lambda rng: selection_null(intraday_con, trades, month_pools_b2, r_distribution, rank_lookup, rng),
        N_SEEDS, ckpt,
    )

    def percentile_of(value, dist):
        dist = dist.dropna()
        return (dist < value).mean() * 100 if len(dist) else float("nan")

    strategy_gross = trades["gross_r"].mean()
    strategy_lo = trades["net_r_lo_cost"].mean()
    strategy_hi = trades["net_r_hi_cost"].mean()
    strategy_pess = trades["net_r_pessimistic"].mean()

    log("\n=== Strategy percentile vs nulls (sealed test) ===")
    for label, dist in [("TIMING", timing_df), ("SELECTION (b)", selection_b_df), ("SELECTION (b2)", selection_b2_df)]:
        log(f"vs {label} (gross):       {percentile_of(strategy_gross, dist['mean_gross']):.1f}th percentile")
        log(f"vs {label} (net, lo):     {percentile_of(strategy_lo, dist['mean_net_lo']):.1f}th percentile")
        log(f"vs {label} (net, hi):     {percentile_of(strategy_hi, dist['mean_net_hi']):.1f}th percentile")
        log(f"vs {label} (net, pess.):  {percentile_of(strategy_pess, dist['mean_net_pess']):.1f}th percentile")

    with open(NULLS_PATH, "wb") as f:
        pickle.dump({
            "timing": timing_df, "selection_b": selection_b_df, "selection_b2": selection_b2_df,
            "pool_size_b": pool_size_b, "pool_size_b2": pool_size_b2,
        }, f)
    log(f"\nSaved to {NULLS_PATH}")


if __name__ == "__main__":
    main()
