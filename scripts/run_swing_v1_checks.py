"""Swing trading, THREE CHECKS ON V1 BEFORE ANY PRE-REGISTRATION.

Per instruction: V1 (momentum top decile ^ liquidity ^ bottom-tercile-5d,
no volume/regime filter) cleared its matched-random null at the 100th
percentile (p=0.0010), Bonferroni- and BH-significant
(`swing_phase3_decomposition_20260927T152209.txt`). V1 is NOT treated as
validated by that result alone -- three specific checks, named by the
user, are answered here before anything is pre-registered or forward-
tested:

  1. CAPITAL: V1's actual peak concurrent positions and peak deployed
     capital at the Rs 3L floor (not the ~165-position arithmetic
     estimate) -- plus whether the edge survives concentrating to the
     top N candidates/day by dip magnitude (N=5,10,20), or is spread thin.
  2. THE 2025 COLLAPSE: is 2025's sharply negative showing partial data,
     a regime shift, or a data-quality issue -- how many trades, over
     what date range, and does the aggregate result depend on excluding it.
  3. YEAR-BY-YEAR ROBUSTNESS: V1's own percentile vs its own matched-random
     null, computed SEPARATELY per year, so the aggregate 100th-percentile
     figure can be checked against whether it holds broadly or is carried
     by a few strong years.

No new variant, no threshold change, no pre-registration or forward-test
decision made here -- this script only answers the three questions above,
reusing V1 exactly as decomposed (same 78-entity exclusion, same cost
model, same Rs 3L floor, same POOL_ML matched-random convention).

Usage:
    python scripts/run_swing_v1_checks.py
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
    historical_bottom_tercile_5d_return, nifty_regime,
)
from swing.backtest import (
    build_open_close_panel, entry_exit_returns, attach_trades_to_signals,
    concurrent_positions, trade_stats, random_entry_benchmark,
)
from swing.costs import round_trip_cost_bps

ROOT = Path(__file__).resolve().parents[1]
POSITION_SIZE = 300_000
TRADES_PER_YEAR_ASSUMED = 550
N_SEEDS = 1000
JUMP_GAP_DAYS_CUTOFF = 5
TOP_N_LEVELS = (5, 10, 20)


def _fmt_pct(x):
    return f"{x*100:.3f}%" if pd.notna(x) else "n/a"


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    print("Rebuilding V1 exactly as decomposed (78-entity exclusion, same pipeline)...",
          file=sys.stderr, flush=True)
    flagged = unexplained_same_isin_jump_entities(con)
    flagged_tight = flagged[flagged["gap_days"] <= JUMP_GAP_DAYS_CUTOFF]
    excluded_entities = set(flagged_tight["entity_id"].unique())

    panel_all = build_open_close_panel(con, SEALED_HOLDOUT_START)
    panel = panel_all[~panel_all["entity_id"].isin(excluded_entities)].reset_index(drop=True)
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)

    mom = historical_momentum_top_decile(panel, jump_dates)
    liq = historical_liquidity_tercile(panel)
    rev = historical_bottom_tercile_5d_return(panel, jump_dates)
    regime = nifty_regime(con, before=SEALED_HOLDOUT_START)

    liq_pass = liq[liq["tercile"].isin(["high_liq", "mid_liq"])][["entity_id", "trade_date"]]
    mom_top = mom[mom["in_top_decile"]][["entity_id", "trade_date"]]
    POOL_ML = mom_top.merge(liq_pass, on=["entity_id", "trade_date"], how="inner")
    rev_bottom = rev[rev["bottom_tercile"]][["entity_id", "trade_date"]]
    V1 = POOL_ML.merge(rev_bottom, on=["entity_id", "trade_date"], how="inner")

    entry_exit = entry_exit_returns(panel, jump_dates)
    trades_v1 = attach_trades_to_signals(V1, panel, entry_exit)
    pool_trades = attach_trades_to_signals(POOL_ML, panel, entry_exit)
    all_dates = pd.Index(sorted(panel["trade_date"].unique()))

    cost_lo, cost_hi = round_trip_cost_bps(POSITION_SIZE, "DELIVERY")

    lines = []
    A = lines.append
    A("=" * 110)
    A("V1 -- THREE CHECKS BEFORE ANY PRE-REGISTRATION")
    A("=" * 110)
    A(f"V1 recap: n_trades={len(trades_v1)}, mean gross return={_fmt_pct(trades_v1['gross_return'].mean())}, "
      f"100th percentile vs matched-random null from POOL_ML (p=0.0010, Bonferroni- and BH-significant "
      f"across the 6-variant decomposition family).")

    # =========================================================================
    # CHECK 1: CAPITAL
    # =========================================================================
    A("\n" + "=" * 110)
    A("CHECK 1: CAPITAL -- actual peak concurrent positions, and does the edge survive concentration")
    A("=" * 110)

    conc = concurrent_positions(trades_v1, all_dates)
    max_conc = int(conc.max())
    peak_capital = max_conc * POSITION_SIZE
    A(f"V1 actual peak concurrent positions: {max_conc}")
    A(f"Peak deployed capital at Rs {POSITION_SIZE:,} floor: Rs {peak_capital:,} "
      f"(Rs {peak_capital/1e7:.2f} crore)")
    A(f"(Arithmetic estimate from mean candidates/day x 5-day hold was ~165 positions / ~Rs 4.95 crore -- "
      f"same kind of gap V4 showed, ~7.6x, between mean-based arithmetic and actual peak, per the clean "
      f"rerun's own recorded correction.)")

    A(f"\n--- Concentration: top N candidates/day by dip magnitude (deepest 5-day return first) ---")
    v1_with_ret = V1.merge(rev, on=["entity_id", "trade_date"], how="left")
    v1_with_ret["dip_rank"] = v1_with_ret.groupby("trade_date")["ret_5d"].rank(method="first", ascending=True)
    full_candidates_per_day = v1_with_ret.groupby("trade_date").size()
    pct_days_ge_N = {N: (full_candidates_per_day >= N).mean() * 100 for N in TOP_N_LEVELS}

    for N in TOP_N_LEVELS:
        capped = v1_with_ret[v1_with_ret["dip_rank"] <= N][["entity_id", "trade_date"]]
        trades_capped = attach_trades_to_signals(capped, panel, entry_exit)
        conc_capped = concurrent_positions(trades_capped, all_dates)
        max_conc_capped = int(conc_capped.max())
        s_hi = trade_stats(trades_capped, cost_hi, TRADES_PER_YEAR_ASSUMED)
        s_lo = trade_stats(trades_capped, cost_lo, TRADES_PER_YEAR_ASSUMED)
        re = random_entry_benchmark(trades_capped, pool_trades, n_seeds=N_SEEDS)
        null_means = re["mean_gross_return"].to_numpy()
        real_mean = trades_capped["gross_return"].mean()
        pctile = float((null_means < real_mean).mean() * 100) if len(null_means) else float("nan")
        A(f"\n  TOP {N}/day: n_trades={s_hi['n_trades']}  "
          f"(days with >= {N} pre-cap V1 candidates: {pct_days_ge_N[N]:.1f}% -- "
          f"{'cap usually binding' if pct_days_ge_N[N] > 50 else 'cap rarely binding, most days have fewer than N candidates'})")
        A(f"    peak concurrent positions: {max_conc_capped}   "
          f"peak capital: Rs {max_conc_capped*POSITION_SIZE:,} (Rs {max_conc_capped*POSITION_SIZE/1e7:.2f} crore)")
        A(f"    [worst-case cost] expectancy={_fmt_pct(s_hi['expectancy'])}  win_rate={s_hi['win_rate']*100:.1f}%  "
          f"profit_factor={s_hi['profit_factor']:.2f}")
        A(f"    [optimistic cost] expectancy={_fmt_pct(s_lo['expectancy'])}  win_rate={s_lo['win_rate']*100:.1f}%")
        A(f"    percentile vs matched-random null (POOL_ML, 1000 seeds): {pctile:.1f}")

    A(f"\n  UNCAPPED V1 (all ~32.9/day): n_trades={len(trades_v1)}  peak concurrent={max_conc}  "
      f"peak capital=Rs {peak_capital:,}  "
      f"[worst-case cost] expectancy={_fmt_pct(trade_stats(trades_v1, cost_hi, TRADES_PER_YEAR_ASSUMED)['expectancy'])}")

    # =========================================================================
    # CHECK 2: THE 2025 COLLAPSE
    # =========================================================================
    A("\n" + "=" * 110)
    A("CHECK 2: THE 2025 COLLAPSE -- partial data, regime shift, or data-quality issue?")
    A("=" * 110)

    t = trades_v1.copy()
    t["signal_year"] = pd.to_datetime(t["signal_date"]).dt.year
    t2025 = t[t["signal_year"] == 2025]
    A(f"V1 trades with signal_date in 2025: {len(t2025)} of {len(t)} total ({len(t2025)/len(t)*100:.2f}%)")
    if len(t2025):
        A(f"2025 signal_date range: {t2025['signal_date'].min().date()} to {t2025['signal_date'].max().date()}")
        A(f"2025 entry_date range: {t2025['entry_date'].min().date()} to {t2025['entry_date'].max().date()}")
        A(f"2025 exit_date range: {t2025['exit_date'].min().date()} to {t2025['exit_date'].max().date()}")
    A(f"SEALED_HOLDOUT_START = {SEALED_HOLDOUT_START} -- panel is truncated strictly before this date, so "
      f"2025 necessarily covers only Jan 1 through mid-March, ~2.5 of 12 months, not a full year like every "
      f"other year in the by-year table. This applies identically to every variant in the decomposition, "
      f"not a V1-specific artifact.")

    # Full-panel trading-date coverage in 2025, for the "how much of the year" comparison
    dates_2025 = [d for d in all_dates if pd.Timestamp(d).year == 2025]
    dates_full_year_avg = pd.Series([pd.Timestamp(d).year for d in all_dates]).value_counts()
    A(f"Trading dates available in 2025 in this panel: {len(dates_2025)} "
      f"(vs. ~{int(dates_full_year_avg[dates_full_year_avg.index != 2025].median())} in a typical full year)")

    # Regime-shift check: was the BROADER momentum/liquidity universe also negative in this window,
    # or is this specific to V1's own selection?
    pool_t = pool_trades.copy()
    pool_t["signal_year"] = pd.to_datetime(pool_t["signal_date"]).dt.year
    pool_2025 = pool_t[pool_t["signal_year"] == 2025]
    A(f"\nBroader POOL_ML (momentum+liquidity candidates, no dip/volume/regime condition) in the SAME "
      f"2025 window: n={len(pool_2025)}, mean gross return={_fmt_pct(pool_2025['gross_return'].mean())} "
      f"(vs V1's {_fmt_pct(t2025['gross_return'].mean())}) -- "
      f"{'negative for the whole candidate pool, not just V1 -- consistent with a market-wide event, not a V1-specific data issue' if pool_2025['gross_return'].mean() < 0 else 'POOL_ML itself was NOT negative in this window -- V1 selection itself concentrated the loss'}")

    nifty_2025 = regime[regime["trade_date"].dt.year == 2025].sort_values("trade_date")
    if len(nifty_2025) >= 2:
        nifty_ret = nifty_2025["nifty_close"].iloc[-1] / nifty_2025["nifty_close"].iloc[0] - 1
        A(f"NIFTY50 close, first available 2025 date ({nifty_2025['trade_date'].iloc[0].date()}) to last "
          f"({nifty_2025['trade_date'].iloc[-1].date()}): {nifty_ret*100:+.2f}% -- "
          f"{'a real market decline over this window, consistent with the negative expectancy being a regime effect' if nifty_ret < 0 else 'NIFTY itself was flat-to-positive over this window -- the negative expectancy is not explained by a broad market decline'}")

    real_mean_all = trades_v1["gross_return"].mean()
    trades_ex2025 = t[t["signal_year"] != 2025]
    real_mean_ex2025 = trades_ex2025["gross_return"].mean()
    re_ex2025 = random_entry_benchmark(trades_ex2025, pool_trades[~pool_t["signal_year"].eq(2025)], n_seeds=N_SEEDS)
    null_means_ex2025 = re_ex2025["mean_gross_return"].to_numpy()
    pctile_ex2025 = float((null_means_ex2025 < real_mean_ex2025).mean() * 100) if len(null_means_ex2025) else float("nan")
    A(f"\nV1 mean gross return, FULL sample (incl. partial 2025): {_fmt_pct(real_mean_all)}, n={len(t)}")
    A(f"V1 mean gross return, EXCLUDING 2025: {_fmt_pct(real_mean_ex2025)}, n={len(trades_ex2025)}")
    A(f"V1 percentile vs matched-random null, EXCLUDING 2025: {pctile_ex2025:.1f} "
      f"(full-sample percentile was 100.0) -- "
      f"{'result does NOT depend on 2025 -- both include and exclude land at the same extreme' if pctile_ex2025 >= 95 else 'result is SENSITIVE to 2025 -- removing it changes the percentile materially, stated explicitly per instruction'}")

    # =========================================================================
    # CHECK 3: YEAR-BY-YEAR PERCENTILE
    # =========================================================================
    A("\n" + "=" * 110)
    A("CHECK 3: V1 percentile vs matched-random null, COMPUTED SEPARATELY PER YEAR")
    A("=" * 110)

    for yr in sorted(t["signal_year"].unique()):
        t_yr = t[t["signal_year"] == yr]
        pool_yr = pool_t[pool_t["signal_year"] == yr]
        if len(t_yr) == 0:
            continue
        real_mean_yr = t_yr["gross_return"].mean()
        re_yr = random_entry_benchmark(t_yr, pool_yr, n_seeds=N_SEEDS)
        null_means_yr = re_yr["mean_gross_return"].to_numpy()
        pctile_yr = float((null_means_yr < real_mean_yr).mean() * 100) if len(null_means_yr) else float("nan")
        pval_yr = (np.sum(null_means_yr >= real_mean_yr) + 1) / (len(null_means_yr) + 1) if len(null_means_yr) else float("nan")
        s_hi_yr = trade_stats(t_yr, cost_hi, TRADES_PER_YEAR_ASSUMED)
        A(f"  {yr}: n={len(t_yr):>6}  mean_gross={_fmt_pct(real_mean_yr)}  "
          f"exp(worst-cost)={_fmt_pct(s_hi_yr['expectancy'])}  win_rate={s_hi_yr['win_rate']*100:.1f}%  "
          f"percentile={pctile_yr:>5.1f}  p={pval_yr:.4f}")

    A("\n" + "=" * 110)
    A("END OF THE THREE CHECKS. No pre-registration or forward-test decision made here.")
    A("=" * 110)

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_v1_checks_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
