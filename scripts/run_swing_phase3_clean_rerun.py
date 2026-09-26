"""Swing trading, Phase 3 CLEAN RERUN: same frozen rule, same volume
threshold (unchanged), but with entities carrying an unexplained same-isin
price jump (BUGS.md Bug #11 -- found via this backtest's own worst trade,
MAJESCO) excluded from both the strategy and the random-entry benchmark
pool. Also fixes the drawdown reporting: a real rupee equity curve with a
stated starting capital, not a dimensionless sum of overlapping fractional
returns.

Per instruction, the headline number this script exists to answer:
where does the strategy's own mean gross return fall in the random-entry
(matched count and timing) null distribution, on CLEAN data -- the
contaminated run put it at the 9th percentile.

Usage:
    python scripts/run_swing_phase3_clean_rerun.py
"""
from __future__ import annotations

import datetime as dt
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from data_layer.db import get_read_connection
from data_layer.holdout import SEALED_HOLDOUT_START
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from data_layer.same_isin_jump_guard import unexplained_same_isin_jump_entities
from swing.universe import (
    historical_momentum_top_decile, historical_liquidity_tercile,
    historical_bottom_tercile_5d_return, historical_volume_ratio, nifty_regime,
)
from swing.backtest import (
    build_open_close_panel, entry_exit_returns, attach_trades_to_signals,
    concurrent_positions, trade_stats, equity_curve_drawdown,
    random_entry_benchmark, coin_flip_benchmark,
)
from swing.costs import round_trip_cost_bps

ROOT = Path(__file__).resolve().parents[1]
POSITION_SIZES = (300_000, 500_000)
TRADES_PER_YEAR_ASSUMED = 550
N_SEEDS = 1000
JUMP_GAP_DAYS_CUTOFF = 5  # matches STALE_GAP_DAYS -- longer gaps are already NaN-guarded elsewhere


def _fmt_pct(x):
    return f"{x*100:.3f}%" if pd.notna(x) else "n/a"


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    print("Scanning the FULL warehouse for unexplained same-isin jumps (BUGS.md Bug #11)...",
          file=sys.stderr, flush=True)
    flagged = unexplained_same_isin_jump_entities(con)  # no `before` -- full warehouse, blast-radius count
    flagged_tight = flagged[flagged["gap_days"] <= JUMP_GAP_DAYS_CUTOFF]
    excluded_entities = set(flagged_tight["entity_id"].unique())
    per_symbol = flagged_tight.groupby("symbol").size().sort_values(ascending=False)
    repeaters = per_symbol[per_symbol > 3]  # illiquid-pricing-artifact shape, not a discrete event

    print("Loading pre-holdout open/close panel and excluding flagged entities...", file=sys.stderr, flush=True)
    panel_all = build_open_close_panel(con, SEALED_HOLDOUT_START)
    panel = panel_all[~panel_all["entity_id"].isin(excluded_entities)].reset_index(drop=True)
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)

    mom = historical_momentum_top_decile(panel, jump_dates)
    liq = historical_liquidity_tercile(panel)
    rev = historical_bottom_tercile_5d_return(panel, jump_dates)
    vol = historical_volume_ratio(panel)
    regime = nifty_regime(con, before=SEALED_HOLDOUT_START)
    con.close()

    stage1 = mom[mom["in_top_decile"]].merge(liq, on=["entity_id", "trade_date"], how="inner")
    stage1 = stage1[stage1["tercile"].isin(["high_liq", "mid_liq"])][["entity_id", "trade_date"]]
    stage3 = stage1.merge(rev[rev["bottom_tercile"]][["entity_id", "trade_date"]], on=["entity_id", "trade_date"], how="inner")
    stage3 = stage3.merge(vol[vol["high_volume"]][["entity_id", "trade_date"]], on=["entity_id", "trade_date"], how="inner")
    stage3 = stage3.merge(regime[regime["regime_on"]][["trade_date"]], on="trade_date", how="inner")

    entry_exit = entry_exit_returns(panel, jump_dates)
    trades = attach_trades_to_signals(stage3, panel, entry_exit)
    all_dates = pd.Index(sorted(panel["trade_date"].unique()))

    lines = []
    A = lines.append
    A("=" * 100)
    A("SWING PHASE 3 -- CLEAN RERUN (Bug #11 entities excluded), CORRECTED DRAWDOWN REPORTING")
    A("=" * 100)

    A(f"\n--- BUG #11 SCAN (full warehouse, no holdout cutoff -- this is a data-integrity check, not a strategy test) ---")
    A(f"Total unexplained same-isin jump rows (ratio outside [0.667x,1.5x], no corporate_actions record within "
      f"+-10 days): see BUGS.md Bug #11 for the full breakdown.")
    A(f"Rows with gap_days <= {JUMP_GAP_DAYS_CUTOFF} (the Majesco shape -- NOT already guarded by STALE_GAP_DAYS "
      f"elsewhere in this codebase): {len(flagged_tight)} rows, {len(excluded_entities)} distinct entities.")
    A(f"Of those, {len(repeaters)} symbols contribute >3 flagged rows each ({int(repeaters.sum())} rows total) -- "
      f"an exact-ratio (2.0x/0.5x) repeating pattern on illiquid names (VISESHINFO, UVSL, BIRLACOT, VKSPL, "
      f"KSERASERA), almost certainly a DIFFERENT mechanism (thin/erratic pricing) from a missed corporate action, "
      f"not individually diagnosed here. The remaining {len(per_symbol) - len(repeaters)} symbols each have 1-2 "
      f"flagged rows, consistent with a one-off event -- some confirmed real market crashes needing no adjustment "
      f"(e.g. YES Bank Mar 2020, Jet Airways 2019 -- spot-checked, not corrected-for-a-reason), some plausible "
      f"missed splits/bonuses on names with ZERO corporate_actions coverage at all (e.g. JSWSTEEL, GRASIM, TRENT --"
      f" ratios close to common split factors). NOT individually verified one by one -- all {len(excluded_entities)} "
      f"excluded from this rerun per instruction, conservatively, regardless of which sub-mechanism applies.")

    # ---- dispersion / power, clean ----
    real_std = trades["gross_return"].std()
    real_mean = trades["gross_return"].mean()
    n_required = (2.0 * real_std / 0.005) ** 2
    A(f"\n--- DISPERSION / POWER, CLEAN ---")
    A(f"n_trades={len(trades)} (was 4,346 contaminated)   mean gross={_fmt_pct(real_mean)} (was 0.792%)   "
      f"std gross={_fmt_pct(real_std)} (was 7.656%)")
    A(f"Recomputed power target: n = (2.0 x {real_std:.4f} / 0.005)^2 = {n_required:,.0f} trades")

    # ---- concurrency, clean, and the CORRECTED equity curve ----
    conc = concurrent_positions(trades, all_dates)
    max_conc = int(conc.max())
    A(f"\n--- CONCURRENCY / CAPITAL, CLEAN ---")
    A(f"max concurrent positions: {max_conc}")

    A(f"\n--- STEP 2 CORRECTED: backtest stats + REAL equity-curve drawdown "
      f"(starting capital = measured peak concurrent capital, stated) ---")
    for size in POSITION_SIZES:
        cost_lo, cost_hi = round_trip_cost_bps(size, "DELIVERY")
        starting_capital = max_conc * size
        A(f"\nPosition size Rs {size:,} (round-trip cost {cost_lo:.1f}-{cost_hi:.1f}bps, "
          f"starting capital = {max_conc} x Rs {size:,} = Rs {starting_capital:,.0f}):")
        for label, cbps in (("worst-case cost", cost_hi), ("optimistic cost", cost_lo)):
            s = trade_stats(trades, cbps, TRADES_PER_YEAR_ASSUMED)
            eq = equity_curve_drawdown(trades, cbps, size, starting_capital)
            A(f"  [{label}] n={s['n_trades']}  win_rate={s['win_rate']*100:.1f}%  "
              f"expectancy={_fmt_pct(s['expectancy'])}  profit_factor={s['profit_factor']:.2f}  "
              f"sharpe={s['sharpe_annualized']:.2f}  "
              f"max_drawdown={eq['max_drawdown_pct_of_peak']*100:.1f}% of peak capital "
              f"(Rs {eq['max_drawdown_rs']:,.0f})  ending_equity=Rs {eq['ending_equity']:,.0f}")

    # ---- STEP 3: benchmarks, clean -- THE HEADLINE ----
    bh_trades = attach_trades_to_signals(stage1, panel, entry_exit)
    print("Running random-entry benchmark on clean data (1000 seeds)...", file=sys.stderr, flush=True)
    re = random_entry_benchmark(trades, bh_trades, n_seeds=N_SEEDS)
    pctile_clean = (re["mean_gross_return"] < real_mean).mean() * 100

    print("Running coin-flip benchmark on clean data (1000 seeds)...", file=sys.stderr, flush=True)
    cf = coin_flip_benchmark(trades, n_seeds=N_SEEDS)
    pctile_cf_clean = (cf["mean_gross_return"] < real_mean).mean() * 100

    A(f"\n" + "=" * 100)
    A(f"HEADLINE: STRATEGY vs RANDOM ENTRY FROM THE SAME UNIVERSE, MATCHED COUNT AND TIMING -- CLEAN DATA")
    A(f"=" * 100)
    A(f"Strategy mean gross return: {_fmt_pct(real_mean)} (n={len(trades)})")
    A(f"Random-entry null distribution (1000 seeds): mean of seed-means {_fmt_pct(re['mean_gross_return'].mean())}, "
      f"std {_fmt_pct(re['mean_gross_return'].std())}")
    A(f"STRATEGY PERCENTILE IN THE NULL DISTRIBUTION (CLEAN): {pctile_clean:.1f} (was 9.0 contaminated)")
    A(f"Coin-flip percentile (CLEAN): {pctile_cf_clean:.1f} (was 100.0 contaminated)")
    for p in (0.05, 0.25, 0.5, 0.75, 0.95):
        A(f"  random-entry seed-mean p{int(p*100)}: {_fmt_pct(re['mean_gross_return'].quantile(p))}")

    bh_s = trade_stats(bh_trades, round_trip_cost_bps(POSITION_SIZES[0], "DELIVERY")[1], TRADES_PER_YEAR_ASSUMED)
    A(f"\nBuy-and-hold candidate universe (clean), Rs {POSITION_SIZES[0]:,} worst-case cost: "
      f"n={bh_s['n_trades']}  expectancy={_fmt_pct(bh_s['expectancy'])}")

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_phase3_clean_rerun_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
