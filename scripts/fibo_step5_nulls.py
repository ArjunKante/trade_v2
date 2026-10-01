"""Step 5's three benchmarks against the 67 real development-window trades
(scripts/fibo_step5_backtest.py's output): (a) TIMING null, (b) SELECTION
null (primary), (c) buy-and-hold baseline. 1000 seeds each for (a)/(b);
(c) is deterministic. See PREREGISTRATION_FIBO.md Section 6 for the exact
definitions this implements.
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
from swing.costs import round_trip_cost_rs
from fibo.intraday_db import get_read_connection as get_intraday_read_connection

ROOT = Path(__file__).resolve().parents[1]
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
RESULTS_PATH = ROOT / "data" / "fibo_step5_dev_results.pkl"
NULLS_PATH = ROOT / "data" / "fibo_step5_nulls.pkl"

N_SEEDS = 1000
EXIT_TIME = dt.time(15, 15)
ENTRY_CANDLE_STARTS = [dt.time(h, m) for h, m in
                       [(9, 30), (9, 45), (10, 0), (10, 15), (10, 30), (10, 45), (11, 0), (11, 15)]]

bars_cache: dict = {}


def log(msg):
    print(msg, flush=True)


def get_bars(intraday_con, entity_id, day) -> pd.DataFrame | None:
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


processed_cache: dict = {}  # (entity_id, day, scale) -> {"bars_1min": df, "bars_15min": df} | None
# Computing the raw-scale 1-min bars AND their 15-min aggregation is the
# same work on every draw of the same (entity, day) across all 1000 seeds
# -- caching this (found live: an uncached first version took >10 minutes
# to reach 20% of just the TIMING null) turns 1000 seeds into a near-
# instant replay after the first pass over each distinct pair.


def get_processed(intraday_con, entity_id, day, scale) -> dict | None:
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


def net_r(gross_r, entry_price, qty, r):
    position_size_rs = qty * entry_price
    cost_lo, cost_hi = round_trip_cost_rs(position_size_rs, "INTRADAY")
    return gross_r - cost_lo / (r * qty), gross_r - cost_hi / (r * qty)


def timing_null(intraday_con, trades: pd.DataFrame, scale_lookup: dict, rng: np.random.Generator) -> dict:
    """(a): same (entity, day) as each real trade, entry redrawn uniformly
    among the 8 valid 15-min candle starts, SAME stop distance (R) and
    SAME target rule (min(entry+2R, swing_high)) as that day's real trade."""
    gross_list, net_lo_list, net_hi_list = [], [], []
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
        nlo, nhi = net_r(gross, entry_price, qty, r)
        gross_list.append(gross); net_lo_list.append(nlo); net_hi_list.append(nhi)
    if not gross_list:
        return {"mean_gross": float("nan"), "mean_net_lo": float("nan"), "mean_net_hi": float("nan")}
    return {"mean_gross": np.mean(gross_list), "mean_net_lo": np.mean(net_lo_list), "mean_net_hi": np.mean(net_hi_list)}


def build_month_pools(m: pd.DataFrame, universe: pd.DataFrame, require_uptrend: bool = False) -> dict:
    """{(year, month): [(entity_id, day), ...]} -- every downloaded pair
    with RESOLVED scale, entity restricted to THAT YEAR's own point-in-time
    universe membership (Section 1). `require_uptrend=True` builds null
    (b2)'s pool instead of null (b)'s: ALSO restricted to days where the
    entity satisfies the daily Alligator uptrend -- isolating whether the
    Fibonacci+ORB confluence adds anything BEYOND being in an uptrend,
    since every real strategy trade is, by construction, an uptrend day."""
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


def selection_null(intraday_con, trades: pd.DataFrame, month_pools: dict, r_distribution: np.ndarray,
                    rng: np.random.Generator) -> dict:
    """(b), PRIMARY: matched trade count per month, random (entity, day)
    from that year's universe, entry drawn 09:30-11:30, stop distance
    drawn from the strategy's OWN empirical R distribution, FLAT 2R target
    (not swing-high-capped -- a random day has no real swing to cap against)."""
    counts_per_month = trades.groupby(trades["trade_date"].apply(lambda d: (d.year, d.month))).size()
    gross_list, net_lo_list, net_hi_list = [], [], []
    for ym, count in counts_per_month.items():
        pool = month_pools.get(ym, [])
        if not pool:
            continue
        for _ in range(count):
            for _attempt in range(10):  # a handful of resample attempts if a draw has no usable bars
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
                target = entry_price + 2 * r  # FLAT 2R, per instruction
                exit_ts = pd.Timestamp.combine(pd.Timestamp(day), EXIT_TIME)
                res = resolve_trade(bars, entry_ts, stop, target, exit_ts)
                gross = (res["exit_price"] - entry_price) / r
                try:
                    qty = position_size_shares(entry_price, stop)
                except ValueError:
                    break
                if qty < 1:
                    break
                nlo, nhi = net_r(gross, entry_price, qty, r)
                gross_list.append(gross); net_lo_list.append(nlo); net_hi_list.append(nhi)
                break
    if not gross_list:
        return {"mean_gross": float("nan"), "mean_net_lo": float("nan"), "mean_net_hi": float("nan")}
    return {"mean_gross": np.mean(gross_list), "mean_net_lo": np.mean(net_lo_list), "mean_net_hi": np.mean(net_hi_list)}


def buy_and_hold_baseline(intraday_con, trades: pd.DataFrame, scale_lookup: dict) -> dict:
    """(c): buy 09:30, sell 15:15, same (entity, day) pairs as the
    strategy's real trades, R-equivalent using each trade's own R distance
    as the sizing reference. Deterministic -- no seeds."""
    r_equiv_list = []
    for _, t in trades.iterrows():
        scale = scale_lookup[(t["entity_id"], t["trade_date"])]
        processed = get_processed(intraday_con, t["entity_id"], t["trade_date"], scale)
        if processed is None:
            continue
        bars = processed["bars_1min"]
        buy = bars[bars["ts"].dt.time == ENTRY_WINDOW_START]
        sell = bars[bars["ts"].dt.time == EXIT_TIME]
        if buy.empty or sell.empty:
            continue
        buy_price = float(buy["open"].iloc[0])
        sell_price = float(sell["close"].iloc[0])
        r_equiv_list.append((sell_price - buy_price) / t["r_rupees"])
    return {"mean_r_equivalent": np.mean(r_equiv_list) if r_equiv_list else float("nan"), "n": len(r_equiv_list)}


def main():
    with open(RESULTS_PATH, "rb") as f:
        d = pickle.load(f)
    trades = d["trades"]
    m = d["m"]
    universe = d["universe"]
    scale_lookup = dict(zip(zip(m["entity_id"], m["trade_date"]), m["scale"]))
    r_distribution = trades["r_rupees"].to_numpy()

    intraday_con = get_intraday_read_connection(INTRADAY_DB)

    log(f"Strategy: {len(trades)} trades. Mean gross R = {trades['gross_r'].mean():.4f}, "
        f"mean net R (lo cost) = {trades['net_r_lo_cost'].mean():.4f}, "
        f"mean net R (hi cost) = {trades['net_r_hi_cost'].mean():.4f}")

    log("\n=== (c) Buy-and-hold baseline ===")
    baseline = buy_and_hold_baseline(intraday_con, trades, scale_lookup)
    log(f"Mean R-equivalent: {baseline['mean_r_equivalent']:.4f} (n={baseline['n']})")

    log(f"\n=== (a) TIMING null: {N_SEEDS} seeds ===")
    timing_results = []
    for seed in range(N_SEEDS):
        rng = np.random.default_rng(seed)
        timing_results.append(timing_null(intraday_con, trades, scale_lookup, rng))
        if (seed + 1) % 200 == 0:
            log(f"  timing null: {seed + 1}/{N_SEEDS} seeds done")
    timing_df = pd.DataFrame(timing_results)

    log(f"\n=== (b) SELECTION null (PRIMARY): {N_SEEDS} seeds ===")
    month_pools = build_month_pools(m, universe)
    selection_results = []
    for seed in range(N_SEEDS):
        rng = np.random.default_rng(seed)
        selection_results.append(selection_null(intraday_con, trades, month_pools, r_distribution, rng))
        if (seed + 1) % 200 == 0:
            log(f"  selection null: {seed + 1}/{N_SEEDS} seeds done")
    selection_df = pd.DataFrame(selection_results)

    strategy_mean_gross = trades["gross_r"].mean()
    strategy_mean_net_lo = trades["net_r_lo_cost"].mean()
    strategy_mean_net_hi = trades["net_r_hi_cost"].mean()

    def percentile_of(value, dist):
        dist = dist.dropna()
        return (dist < value).mean() * 100 if len(dist) else float("nan")

    log("\n=== Strategy percentile vs nulls ===")
    log(f"vs TIMING null (gross R):    {percentile_of(strategy_mean_gross, timing_df['mean_gross']):.1f}th percentile")
    log(f"vs TIMING null (net R, lo):  {percentile_of(strategy_mean_net_lo, timing_df['mean_net_lo']):.1f}th percentile")
    log(f"vs TIMING null (net R, hi):  {percentile_of(strategy_mean_net_hi, timing_df['mean_net_hi']):.1f}th percentile")
    log(f"vs SELECTION null (gross R): {percentile_of(strategy_mean_gross, selection_df['mean_gross']):.1f}th percentile")
    log(f"vs SELECTION null (net R, lo): {percentile_of(strategy_mean_net_lo, selection_df['mean_net_lo']):.1f}th percentile")
    log(f"vs SELECTION null (net R, hi): {percentile_of(strategy_mean_net_hi, selection_df['mean_net_hi']):.1f}th percentile")

    with open(NULLS_PATH, "wb") as f:
        pickle.dump({"timing": timing_df, "selection": selection_df, "baseline": baseline}, f)
    log(f"\nSaved to {NULLS_PATH}")


if __name__ == "__main__":
    main()
