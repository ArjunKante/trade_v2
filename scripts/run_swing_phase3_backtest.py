"""Swing trading, Phase 3: the frozen rule's backtest. Per instruction,
this reports numbers only -- no interpretation, no viability verdict, no
threshold changes. See PREREGISTRATION_SWING.md for what is frozen.

Per instruction: the 1.5x volume threshold stays exactly as pre-
registered. Relaxing it now, after seeing the candidate-count sparsity,
would make this a search rather than a test of the pre-registered rule.

STEP 1: recompute dispersion on the EXACT construction this rule uses
(open-to-open, on the fully-filtered signal population) -- Phase 1's 8.80%
was close-to-close on the whole market; that number is superseded here for
the power calculation, not reused.

STEP 2: run the backtest and compute the requested statistics net of cost
at Rs 3L and Rs 5L, both ends of the cost range, never blended.

STEP 3: benchmarks -- buy-and-hold the candidate universe (every stage-1
member every day, same trade construction, same cost), random entry
(matched trade count and timing, 1000 seeds), coin-flip (same trades,
random long/short sign, 1000 seeds).

Usage:
    python scripts/run_swing_phase3_backtest.py
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
from swing.universe import (
    historical_momentum_top_decile, historical_liquidity_tercile,
    historical_bottom_tercile_5d_return, historical_volume_ratio, nifty_regime,
)
from swing.backtest import (
    build_open_close_panel, entry_exit_returns, attach_trades_to_signals,
    concurrent_positions, trade_stats, random_entry_benchmark, coin_flip_benchmark,
)
from swing.costs import round_trip_cost_bps

ROOT = Path(__file__).resolve().parents[1]
POSITION_SIZES = (300_000, 500_000)
TRADES_PER_YEAR_ASSUMED = 550  # from Phase 2's own arithmetic (2.2/day x ~250 trading days) -- reported, not re-derived here
N_SEEDS = 1000


def _fmt_pct(x):
    return f"{x*100:.3f}%" if pd.notna(x) else "n/a"


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    print("Loading pre-holdout open/close panel...", file=sys.stderr, flush=True)
    panel = build_open_close_panel(con, SEALED_HOLDOUT_START)
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)

    print("Computing signal conditions (momentum, liquidity, reversal, volume, regime)...", file=sys.stderr, flush=True)
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

    print("Precomputing entry-to-exit open-to-open returns for every row...", file=sys.stderr, flush=True)
    entry_exit = entry_exit_returns(panel, jump_dates)

    print("Building the frozen rule's trades...", file=sys.stderr, flush=True)
    trades = attach_trades_to_signals(stage3, panel, entry_exit)

    all_dates = pd.Index(sorted(panel["trade_date"].unique()))

    lines = []
    A = lines.append
    A("=" * 100)
    A("SWING PHASE 3: BACKTEST OF THE FROZEN RULE -- NUMBERS ONLY, NO INTERPRETATION")
    A("Volume threshold (1.5x) unchanged from PREREGISTRATION_SWING.md, per instruction.")
    A("=" * 100)

    # ---- STEP 1: real dispersion on the exact construction ----
    real_std = trades["gross_return"].std()
    real_mean = trades["gross_return"].mean()
    A(f"\n--- STEP 1: dispersion on the EXACT construction (open-to-open, fully-filtered signal population) ---")
    A(f"n_trades={len(trades)}   mean gross return={_fmt_pct(real_mean)}   std gross return={_fmt_pct(real_std)}")
    A(f"(Phase 1's placeholder was 8.80% -- close-to-close, whole market. This std supersedes it.)")
    t_thresh, target_effect = 2.0, 0.005
    n_required = (t_thresh * real_std / target_effect) ** 2
    A(f"RECOMPUTED POWER: n = (2.0 x {real_std:.4f} / 0.005)^2 = {n_required:,.0f} trades "
      f"(was ~1,239 provisional; PREREGISTRATION_SWING.md updated to this real figure).")

    # ---- STEP 2: backtest stats at both position sizes, both cost-range ends ----
    A(f"\n--- STEP 2: backtest stats, net of cost (both ends of the cost range; never blended) ---")
    for size in POSITION_SIZES:
        cost_lo, cost_hi = round_trip_cost_bps(size, "DELIVERY")
        A(f"\nPosition size Rs {size:,} (round-trip cost {cost_lo:.1f}-{cost_hi:.1f}bps):")
        for label, cbps in (("worst-case cost (hi)", cost_hi), ("optimistic cost (lo)", cost_lo)):
            s = trade_stats(trades, cbps, TRADES_PER_YEAR_ASSUMED)
            A(f"  [{label}] n={s['n_trades']}  win_rate={s['win_rate']*100:.1f}%  "
              f"avg_win={_fmt_pct(s['avg_win'])}  avg_loss={_fmt_pct(s['avg_loss'])}  "
              f"expectancy={_fmt_pct(s['expectancy'])}  profit_factor={s['profit_factor']:.2f}  "
              f"sharpe(ann,~{TRADES_PER_YEAR_ASSUMED}/yr)={s['sharpe_annualized']:.2f}  "
              f"max_dd={s['max_drawdown_cum_return']*100:.2f}% (cum-return units) "
              f"= Rs {s['max_drawdown_cum_return']*size:,.0f} at this size")
    gross_stats = trade_stats(trades, 0.0, TRADES_PER_YEAR_ASSUMED)
    A(f"\n[reference, GROSS, no cost] n={gross_stats['n_trades']}  win_rate={gross_stats['win_rate']*100:.1f}%  "
      f"expectancy={_fmt_pct(gross_stats['expectancy'])}  profit_factor={gross_stats['profit_factor']:.2f}  "
      f"sharpe={gross_stats['sharpe_annualized']:.2f}")

    # ---- concurrency / capital ----
    conc = concurrent_positions(trades, all_dates)
    max_conc = int(conc.max())
    mean_conc_active = conc[conc > 0].mean() if (conc > 0).any() else float("nan")
    A(f"\n--- CONCURRENCY / CAPITAL ---")
    A(f"max concurrent positions: {max_conc}   mean concurrent positions (days with >=1 open): {mean_conc_active:.2f}")
    for size in POSITION_SIZES:
        A(f"  peak deployed capital at Rs {size:,}/position: Rs {max_conc*size:,.0f}")

    # ---- per-trade distribution, by year (does one period dominate?) ----
    A(f"\n--- PER-TRADE DISTRIBUTION (gross return, before cost) ---")
    q = trades["gross_return"].quantile([0, 0.10, 0.25, 0.5, 0.75, 0.90, 1.0])
    for p, v in q.items():
        A(f"  p{int(p*100):>3}: {_fmt_pct(v)}")
    A(f"\n--- BY CALENDAR YEAR OF ENTRY (does one period dominate?) ---")
    by_year = trades.assign(year=trades["entry_date"].dt.year).groupby("year")["gross_return"].agg(["count", "mean", "sum"])
    for yr, row in by_year.iterrows():
        A(f"  {yr}: n={int(row['count']):>4}  mean={_fmt_pct(row['mean'])}  sum(cum-return units)={row['sum']*100:.1f}%")

    # ---- STEP 3: benchmarks ----
    A(f"\n--- STEP 3: BENCHMARKS ---")

    print("Building the buy-and-hold candidate-universe trade set (also used as the random-entry pool)...",
          file=sys.stderr, flush=True)
    bh_trades = attach_trades_to_signals(stage1, panel, entry_exit)
    A(f"\nBuy-and-hold candidate universe (every stage-1 member, every day, same 5-day open-to-open "
      f"construction, same costs): n={len(bh_trades)}")
    for size in POSITION_SIZES:
        cost_lo, cost_hi = round_trip_cost_bps(size, "DELIVERY")
        s_hi = trade_stats(bh_trades, cost_hi, TRADES_PER_YEAR_ASSUMED)
        s_lo = trade_stats(bh_trades, cost_lo, TRADES_PER_YEAR_ASSUMED)
        A(f"  Rs {size:,}: expectancy net worst-case={_fmt_pct(s_hi['expectancy'])}  "
          f"net optimistic={_fmt_pct(s_lo['expectancy'])}  win_rate={s_hi['win_rate']*100:.1f}%  "
          f"sharpe(worst-case cost)={s_hi['sharpe_annualized']:.2f}")

    print("Running random-entry benchmark (1000 seeds)...", file=sys.stderr, flush=True)
    re = random_entry_benchmark(trades, bh_trades, n_seeds=N_SEEDS)
    A(f"\nRandom entry, matched trade count and timing, {len(re)} seeds "
      f"(mean gross return per seed, distribution across seeds):")
    A(f"  mean of seed-means: {_fmt_pct(re['mean_gross_return'].mean())}   "
      f"std of seed-means: {_fmt_pct(re['mean_gross_return'].std())}")
    for p in (0.05, 0.25, 0.5, 0.75, 0.95):
        A(f"  seed-mean p{int(p*100)}: {_fmt_pct(re['mean_gross_return'].quantile(p))}")
    A(f"  STRATEGY's own mean gross return ({_fmt_pct(real_mean)}) sits at percentile "
      f"{(re['mean_gross_return'] < real_mean).mean()*100:.1f} of this random-entry seed distribution.")

    print("Running coin-flip benchmark (1000 seeds)...", file=sys.stderr, flush=True)
    cf = coin_flip_benchmark(trades, n_seeds=N_SEEDS)
    A(f"\nCoin-flip (same trades, random long/short sign), {len(cf)} seeds:")
    A(f"  mean of seed-means: {_fmt_pct(cf['mean_gross_return'].mean())}   "
      f"std of seed-means: {_fmt_pct(cf['mean_gross_return'].std())}")
    for p in (0.05, 0.25, 0.5, 0.75, 0.95):
        A(f"  seed-mean p{int(p*100)}: {_fmt_pct(cf['mean_gross_return'].quantile(p))}")
    A(f"  STRATEGY's own mean gross return ({_fmt_pct(real_mean)}) sits at percentile "
      f"{(cf['mean_gross_return'] < real_mean).mean()*100:.1f} of this coin-flip seed distribution.")

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_phase3_backtest_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
