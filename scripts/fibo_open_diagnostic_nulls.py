"""PHASE 1 DIAGNOSTIC -- NOT a test. SELECTION nulls (b) and (b2) for the
open-entry rule (src/fibo_open/backtest_open.py), against
scripts/fibo_open_diagnostic_backtest.py's output. Same DIAGNOSTIC status
as that script -- see FIBO_OPEN.md: this module's rules were decided AFTER
seeing src/fibo's own sealed-test result, so the data has already been
seen and this is not a validated result.

RE-DERIVED, NOT COPIED: scripts/fibo_step5_nulls.py's selection_null draws
a random entry among 8 15-min candle starts (09:30-11:30) specifically to
avoid biasing the comparison toward or against the BREAKOUT rule's own
discretionary entry-timing choice (the breakout rule scans forward for a
trigger, so its "when do we enter" is itself part of what null (b)/(b2)
must marginalize over to isolate SELECTION alone). The open-entry strategy
has no entry-timing choice at all -- every setup-ON day enters at the
fixed 09:30 open, by rule. There is therefore nothing left to marginalize
over on the null side either: holding entry mechanism FIXED and identical
between the real strategy and its selection null is what isolates
SELECTION specifically (the stated purpose of (b)/(b2)), so this null
fixes entry at the SAME 09:30 open `fibo_open.backtest_open.find_open_entry`
reads for real trades, rather than blindly reusing the 8-candle-start
redraw. Stop distance is still drawn from the open-entry strategy's OWN
empirical R distribution (same role as in the original (b)/(b2)) and the
target is a flat entry+2R (a random day has no real swing high to cap
against -- same reasoning as the original). The monitoring window also
reuses backtest_open's own re-derived convention: it starts one minute
before the entry bar so the entry bar's own high/low is included as live
risk (see src/fibo_open/backtest_open.py's module docstring).

POOL: top-100 universe only, point-in-time annual reconstitution -- Phase
1's universe (FIBO_OPEN.md). Month-matched draw count, same method as
fibo_step5_nulls.py's build_month_pools. (b2) restricts the pool to
uptrend-only days, identical in spirit to fibo_step5_null_b2.py.

COSTING: lo/hi exactly as elsewhere (swing.costs.round_trip_cost_rs).
Pessimistic banded cost also computed per draw, using that draw's own
entity's rank band that year (1-50/51-100 only -- the pool is top-100-only
by construction) and fibo_test_backtest.py's BAND_MULTIPLIER convention
(1x/2x). Band 101-200's 4x multiplier never applies here because Phase 1
excludes that band from the universe entirely.
"""
import sys
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.scale_probe import ScaleDecision, to_raw_scale as scale_probe_to_raw
from fibo.resolution import resolve_trade, position_size_shares
from fibo_open.backtest_open import find_open_entry, EXIT_TIME
from swing.costs import buy_leg_cost_rs, sell_leg_cost_rs, round_trip_cost_rs, SPREAD_IMPACT_ROUND_TRIP_BPS_HI
from fibo.intraday_db import get_read_connection as get_intraday_read_connection

ROOT = Path(__file__).resolve().parents[1]
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
RESULTS_PATH = ROOT / "data" / "fibo_open_diagnostic_results.pkl"
NULLS_PATH = ROOT / "data" / "fibo_open_diagnostic_nulls.pkl"
CHECKPOINT_PATH = ROOT / "data" / "fibo_open_diagnostic_nulls_checkpoint.pkl"
CHECKPOINT_EVERY = 10
# this environment killed scripts/fibo_test_nulls.py's equivalent run externally
# dozens of times (FIBO.md, "THE SEALED TEST"); checkpointing every
# CHECKPOINT_EVERY seeds (same fix applied there) so a kill here loses at most
# that many seeds' work, never a whole null type's 1000-seed run.

N_SEEDS = 200
# Lowered from 1000 (2026-10-02), per instruction. Reasoning: 200 seeds gives
# percentile resolution of 0.5%, far finer than this DIAGNOSTIC needs -- its
# only job is to decide whether a two-year forward test is worth starting,
# and that decision does not change between the 97th and 98th percentile.
# 1000 seeds was inherited from fibo_step5_nulls.py's sealed-test convention,
# where precision mattered because a PASS/FAIL bar sat at the 95th percentile
# (PREREGISTRATION_FIBO.md Section 5b). There is no such bar here.
#
# ENGINEERING NOTE for future nulls scripts: this computation does NOT
# benefit from get_processed's lazy per-draw bars cache, measured live on
# 2026-10-02 at a flat ~12.6 sec/seed with no speedup from seed 1 through
# seed 270 -- because the candidate pool (223,860 pairs for (b)) is roughly
# two orders of magnitude larger than the ~400 draws made per seed, so each
# seed mostly hits NEW (entity, day) pairs rather than re-hitting cached
# ones; the cache never gets the chance to warm up the way
# fibo_step5_nulls.py's docstring describes (that module's pool/seed-count
# ratio was far smaller). The general lesson: before relying on lazy
# per-draw caching to make a many-seed Monte Carlo run cheap, check whether
# the pool size is actually comparable to (not orders of magnitude larger
# than) draws-per-seed x seeds. If it is not, either (a) size the seed count
# to the precision the decision actually needs (what was done here), or
# (b) pre-load/batch-fetch the whole pool's bars ONCE up front instead of
# caching lazily per draw.
BAND_MULTIPLIER = {"1-50": 1, "51-100": 2}  # 101-200 never appears -- excluded from the Phase 1 universe

bars_cache: dict = {}
processed_cache: dict = {}  # (entity_id, day, scale) -> scaled bars_1min df | None


def log(msg):
    print(msg, flush=True)


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
        bars[c] = scale_probe_to_raw(bars[c], scale)
    processed_cache[key] = bars
    return bars


def pessimistic_cost_rs(position_size_rs: float, band: str) -> float:
    fixed = buy_leg_cost_rs(position_size_rs, "INTRADAY") + sell_leg_cost_rs(position_size_rs, "INTRADAY")
    mult = BAND_MULTIPLIER.get(band, 2)  # unranked treated as the worse of the two bands actually in-universe
    spread = position_size_rs * SPREAD_IMPACT_ROUND_TRIP_BPS_HI / 10_000 * mult
    return fixed + spread


def net_r_all(gross_r, entry_price, qty, r, band):
    position_size_rs = qty * entry_price
    cost_lo, cost_hi = round_trip_cost_rs(position_size_rs, "INTRADAY")
    cost_pess = pessimistic_cost_rs(position_size_rs, band)
    return (
        gross_r - cost_lo / (r * qty),
        gross_r - cost_hi / (r * qty),
        gross_r - cost_pess / (r * qty),
    )


def build_month_pools(m: pd.DataFrame, universe100: pd.DataFrame, require_uptrend: bool = False) -> dict:
    """{(year, month): [(entity_id, day, scale, band), ...]} restricted to
    top-100 membership that year (Phase 1's universe). require_uptrend=True
    builds (b2)'s pool -- isolates whether the confluence adds anything
    beyond being in an uptrend, same reasoning as fibo_step5_null_b2.py."""
    resolved = m[m["scale_decision"].isin([ScaleDecision.RAW_EQUIVALENT, ScaleDecision.SCALED])].copy()
    if require_uptrend:
        resolved = resolved[resolved["uptrend"] == True]  # noqa: E712
    resolved["year"] = resolved["trade_date"].apply(lambda d: d.year)
    resolved["month"] = resolved["trade_date"].apply(lambda d: d.month)
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe100.iterrows()}
    resolved["rank"] = resolved.apply(lambda r: rank_lookup.get((r["year"], r["entity_id"])), axis=1)
    resolved = resolved[resolved["rank"].notna()]
    resolved["band"] = resolved["rank"].apply(lambda rk: "1-50" if rk <= 50 else "51-100")

    pools = {}
    for (y, mo), grp in resolved.groupby(["year", "month"]):
        pools[(y, mo)] = list(zip(grp["entity_id"], grp["trade_date"], grp["scale"], grp["band"]))
    return pools


def selection_null_open(intraday_con, trades_open: pd.DataFrame, month_pools: dict,
                         r_distribution: np.ndarray, rng: np.random.Generator) -> dict:
    """SELECTION null for the open-entry rule: matched trade count per
    month, random (entity, day) from that year's top-100 universe, entry
    FIXED at that day's own 09:30 open (no redraw -- see module docstring),
    stop distance drawn from the strategy's own empirical R distribution,
    flat 2R target, entry bar's own high/low included in monitoring
    (backtest_open's convention)."""
    counts_per_month = trades_open.groupby(trades_open["trade_date"].apply(lambda d: (d.year, d.month))).size()
    gross_list, net_lo_list, net_hi_list, net_pess_list = [], [], [], []
    for ym, count in counts_per_month.items():
        pool = month_pools.get(ym, [])
        if not pool:
            continue
        for _ in range(count):
            for _attempt in range(10):  # a handful of resample attempts if a draw has no usable bars
                entity_id, day, scale, band = pool[rng.integers(len(pool))]
                bars = get_processed(intraday_con, entity_id, day, scale)
                if bars is None:
                    continue
                entry = find_open_entry(bars, day)
                if entry is None:
                    continue
                entry_ts, entry_price = entry
                r = float(rng.choice(r_distribution))
                stop = entry_price - r
                target = entry_price + 2 * r  # FLAT 2R, per instruction
                exit_ts = pd.Timestamp.combine(pd.Timestamp(day), EXIT_TIME)
                monitor_from_ts = entry_ts - pd.Timedelta(minutes=1)
                res = resolve_trade(bars, monitor_from_ts, stop, target, exit_ts)
                gross = (res["exit_price"] - entry_price) / r
                try:
                    qty = position_size_shares(entry_price, stop)
                except ValueError:
                    break
                if qty < 1:
                    break
                nlo, nhi, npess = net_r_all(gross, entry_price, qty, r, band)
                gross_list.append(gross); net_lo_list.append(nlo)
                net_hi_list.append(nhi); net_pess_list.append(npess)
                break
    if not gross_list:
        return {k: float("nan") for k in ("mean_gross", "mean_net_lo", "mean_net_hi", "mean_net_pess")}
    return {
        "mean_gross": np.mean(gross_list), "mean_net_lo": np.mean(net_lo_list),
        "mean_net_hi": np.mean(net_hi_list), "mean_net_pess": np.mean(net_pess_list),
    }


def percentile_of(value, dist):
    dist = dist.dropna()
    return (dist < value).mean() * 100 if len(dist) else float("nan")


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
    log("=== PHASE 1 DIAGNOSTIC -- open-entry SELECTION nulls (b)/(b2), data already seen, NOT a validated result ===")
    with open(RESULTS_PATH, "rb") as f:
        d = pickle.load(f)
    m = d["m"]
    universe100 = d["universe100"]
    trades_open_all = d["trades_open"]
    trades_open = trades_open_all[trades_open_all["band"].isin(["1-50", "51-100"])].copy()
    log(f"Open-entry top-100 trades for null matching: {len(trades_open)} "
        f"(of {len(trades_open_all)} total across all bands)")

    trades_open["cost_pess_rs"] = trades_open.apply(
        lambda r: pessimistic_cost_rs(r["position_size_rs"], r["band"]), axis=1
    )
    trades_open["net_r_pessimistic"] = (
        trades_open["gross_r"] - trades_open["cost_pess_rs"] / (trades_open["r_rupees"] * trades_open["qty"])
    )
    r_distribution = trades_open["r_rupees"].to_numpy()
    intraday_con = get_intraday_read_connection(INTRADAY_DB)
    ckpt = load_checkpoint()

    log("Building top-100 month pools for null (b)...")
    pools_b = build_month_pools(m, universe100, require_uptrend=False)
    log("Building top-100, uptrend-only month pools for null (b2)...")
    pools_b2 = build_month_pools(m, universe100, require_uptrend=True)
    pool_size_b = sum(len(v) for v in pools_b.values())
    pool_size_b2 = sum(len(v) for v in pools_b2.values())
    log(f"(b) pool size: {pool_size_b}, (b2) pool size: {pool_size_b2} "
        f"({pool_size_b2 / pool_size_b * 100:.1f}% of (b))")

    log(f"\n=== (b) SELECTION null, open entry, top-100: {N_SEEDS} seeds ===")
    b_df = run_seeds(
        "selection_b",
        lambda rng: selection_null_open(intraday_con, trades_open, pools_b, r_distribution, rng),
        N_SEEDS, ckpt,
    )

    log(f"\n=== (b2) SELECTION null, open entry, top-100, uptrend-only pool: {N_SEEDS} seeds ===")
    b2_df = run_seeds(
        "selection_b2",
        lambda rng: selection_null_open(intraday_con, trades_open, pools_b2, r_distribution, rng),
        N_SEEDS, ckpt,
    )

    strategy_mean_gross = trades_open["gross_r"].mean()
    strategy_mean_net_lo = trades_open["net_r_lo_cost"].mean()
    strategy_mean_net_hi = trades_open["net_r_hi_cost"].mean()
    strategy_mean_net_pess = trades_open["net_r_pessimistic"].mean()

    log("\n=== DIAGNOSTIC -- open-entry, top-100 strategy percentile vs nulls (data already seen, NOT a validated result) ===")
    for label, df in (("(b)", b_df), ("(b2)", b2_df)):
        log(f"vs {label} gross R:        {percentile_of(strategy_mean_gross, df['mean_gross']):.1f}th percentile")
        log(f"vs {label} net R (lo):     {percentile_of(strategy_mean_net_lo, df['mean_net_lo']):.1f}th percentile")
        log(f"vs {label} net R (hi):     {percentile_of(strategy_mean_net_hi, df['mean_net_hi']):.1f}th percentile")
        log(f"vs {label} net R (pess):   {percentile_of(strategy_mean_net_pess, df['mean_net_pess']):.1f}th percentile")

    with open(NULLS_PATH, "wb") as f:
        pickle.dump({
            "selection_b": b_df, "selection_b2": b2_df,
            "pool_size_b": pool_size_b, "pool_size_b2": pool_size_b2,
        }, f)
    log(f"\nSaved to {NULLS_PATH}")

    intraday_con.close()


if __name__ == "__main__":
    main()
