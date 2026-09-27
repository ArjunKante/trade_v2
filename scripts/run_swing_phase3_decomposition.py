"""Swing trading, Phase 3 DIAGNOSTIC DECOMPOSITION of the frozen rule.

Per instruction: this is a diagnostic, not a new strategy search. The
frozen rule (V4 below) scored at the 9.8th percentile against matched
random entry from its own candidate pool (worse-than-chance selection,
`swing_phase3_clean_rerun_20260926T202040.txt`). This script decomposes
WHICH condition is responsible, via ONE pre-specified trial set of 8
variants, each compared to its own matched-random null, with Bonferroni
and Benjamini-Hochberg correction applied across the family.

ALL 8 VARIANTS ARE SPECIFIED BEFORE ANY IS RUN (this file, written once,
not edited after seeing a result). No ninth variant, no threshold tuning.

  V1  momentum ^ liquidity ^ bottom-tercile-5d          (dip only)
  V2  V1 + volume > 1.5x                                 (dip + volume)
  V3  V1 + Nifty regime-on                               (dip + regime)
  V4  V1 + volume + regime                               (the original rule)
  V5  V1 + fundamentals screener PASS                    (dip + quality)
  V6  V1 + regime + screener PASS                        (dip + regime + quality)
  V7  momentum ^ liquidity only, no dip condition
  V8  bottom-tercile-5d across full universe, WITHOUT the momentum filter

V5 and V6 CANNOT BE COMPUTED -- see BUGS.md Bug #12. `fundamental_screener.py`
only evaluates a CURRENT, as-of-today verdict (`load_current_price_panel`,
`compute_liquidity_tercile` are both "as of the latest date" by
construction); no point-in-time historical series exists across the nine
years this backtest spans. Building one is a separate undertaking (flagged
in `src/swing/universe.py`'s docstring before this script was written), not
attempted here as a shortcut. V5/V6 are reported as NOT COMPUTABLE, and the
multiple-comparisons family is the 6 variants that could actually be run
(V1, V2, V3, V4, V7, V8) -- stated explicitly, not silently re-labeled as
"8" to match the original brief.

CANDIDATE-POOL CONVENTION for the matched-random null (stated once,
applied uniformly): "the same candidate pool as that variant" is read as
the broadest population each variant's own conditions draw from, following
this project's own established usage of "candidate pool" (SWING.md Phase
2/3: the momentum ^ liquidity intersection is called the candidate pool
that the rest of the frozen rule filters down from):
  - V1, V2, V3, V4: pool = POOL_ML (momentum top decile ^ liquidity
    tercile), the SAME pool the original Phase 3 benchmark used -- this
    reproduces the known 9.8th-percentile figure for V4 exactly, as an
    internal consistency check.
  - V7: pool = POOL_ML also -- but V7 IS POOL_ML (no differentiating
    condition beyond it), so the matched-random draw samples the same
    number of entities per day as POOL_ML itself contains that day. That
    is degenerate by construction (sampling without replacement at full
    size reproduces the same set every seed) and is reported as such, not
    forced into a misleading percentile.
  - V8: pool = POOL_LIQ (liquidity tercile only, full universe, no
    momentum filter) -- the broadest population V8's own bottom-tercile
    condition draws from.

DATA HYGIENE, reused from the clean rerun, not rebuilt:
  - the 78 same-ISIN-jump entities (BUGS.md Bug #11, gap_days<=5) excluded
    from every variant AND every matched null.
  - STALE_GAP_DAYS gap-guarding on every return (via unexplained_jump_dates,
    same as every other factor computation in this project).
  - same DELIVERY cost model, same Rs 3L floor, both cost-bound ends
    reported, never blended.
  - same open-to-open entry/exit construction (`swing.backtest`).

Usage:
    python scripts/run_swing_phase3_decomposition.py
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
    trade_stats, random_entry_benchmark,
)
from swing.costs import round_trip_cost_bps

ROOT = Path(__file__).resolve().parents[1]
POSITION_SIZE = 300_000
TRADES_PER_YEAR_ASSUMED = 550
N_SEEDS = 1000
JUMP_GAP_DAYS_CUTOFF = 5
WARMUP_DAYS = 273  # momentum_12_1 lookback warm-up, same cutoff as Phase 2's table
ALPHA = 0.05


def _fmt_pct(x):
    return f"{x*100:.3f}%" if pd.notna(x) else "n/a"


def _candidate_count_stats(signals: pd.DataFrame, all_dates: pd.Index) -> dict:
    counts = signals.groupby("trade_date").size().reindex(all_dates, fill_value=0)
    return {
        "mean": counts.mean(), "median": counts.median(),
        "p10": counts.quantile(0.10), "p90": counts.quantile(0.90),
        "pct_zero": (counts == 0).mean() * 100,
    }


def _permutation_pvalue(null_means: np.ndarray, real_mean: float) -> float:
    """One-sided: P(null >= observed), +1/+1 continuity correction so a
    result better than all 1000 seeds reports p=1/1001, never p=0."""
    return (np.sum(null_means >= real_mean) + 1) / (len(null_means) + 1)


def _by_year(trades: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    t = trades.copy()
    t["year"] = pd.to_datetime(t["signal_date"]).dt.year
    net = t["gross_return"] - cost_bps / 10_000
    t = t.assign(net=net)
    rows = []
    for yr, g in t.groupby("year"):
        wins = g["net"][g["net"] > 0]
        rows.append({
            "year": yr, "n_trades": len(g), "expectancy": g["net"].mean(),
            "win_rate": len(wins) / len(g) if len(g) else float("nan"),
        })
    return pd.DataFrame(rows)


def _bh_correction(pvals: dict) -> dict:
    """Benjamini-Hochberg step-up. Returns {name: (rank, threshold, passes)}."""
    m = len(pvals)
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    passed_any = False
    result = {}
    # find largest k with p_(k) <= (k/m)*alpha, then everything <= that k passes
    max_k = 0
    for k, (name, p) in enumerate(items, start=1):
        thresh = (k / m) * ALPHA
        if p <= thresh:
            max_k = k
    for k, (name, p) in enumerate(items, start=1):
        thresh = (k / m) * ALPHA
        result[name] = {"rank": k, "bh_threshold": thresh, "passes": k <= max_k}
    return result


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    print("Scanning full warehouse for unexplained same-isin jumps (BUGS.md Bug #11)...",
          file=sys.stderr, flush=True)
    flagged = unexplained_same_isin_jump_entities(con)
    flagged_tight = flagged[flagged["gap_days"] <= JUMP_GAP_DAYS_CUTOFF]
    excluded_entities = set(flagged_tight["entity_id"].unique())

    print("Loading pre-holdout open/close panel, excluding flagged entities...", file=sys.stderr, flush=True)
    panel_all = build_open_close_panel(con, SEALED_HOLDOUT_START)
    panel = panel_all[~panel_all["entity_id"].isin(excluded_entities)].reset_index(drop=True)
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)

    print("Computing momentum / liquidity / reversal / volume / regime at every historical date...",
          file=sys.stderr, flush=True)
    mom = historical_momentum_top_decile(panel, jump_dates)
    liq = historical_liquidity_tercile(panel)
    rev = historical_bottom_tercile_5d_return(panel, jump_dates)
    vol = historical_volume_ratio(panel)
    regime = nifty_regime(con, before=SEALED_HOLDOUT_START)
    con.close()

    all_dates = pd.Index(sorted(panel["trade_date"].unique()))
    post_warmup_dates = all_dates[WARMUP_DAYS:]

    # ---- pools ----
    liq_pass = liq[liq["tercile"].isin(["high_liq", "mid_liq"])][["entity_id", "trade_date"]]
    mom_top = mom[mom["in_top_decile"]][["entity_id", "trade_date"]]
    POOL_ML = mom_top.merge(liq_pass, on=["entity_id", "trade_date"], how="inner")   # momentum ^ liquidity
    POOL_LIQ = liq_pass.copy()                                                       # liquidity only, no momentum
    rev_bottom = rev[rev["bottom_tercile"]][["entity_id", "trade_date"]]
    vol_high = vol[vol["high_volume"]][["entity_id", "trade_date"]]
    regime_on_dates = regime[regime["regime_on"]][["trade_date"]]

    def _isect(a, b, on=("entity_id", "trade_date")):
        return a.merge(b, on=list(on), how="inner")

    V1 = _isect(POOL_ML, rev_bottom)
    V2 = _isect(V1, vol_high)
    V3 = V1.merge(regime_on_dates, on="trade_date", how="inner")
    V4 = _isect(V1, vol_high).merge(regime_on_dates, on="trade_date", how="inner")
    V7 = POOL_ML.copy()
    V8 = _isect(POOL_LIQ, rev_bottom)

    entry_exit = entry_exit_returns(panel, jump_dates)

    variants = {
        "V1 (dip only)": (V1, POOL_ML),
        "V2 (dip+volume)": (V2, POOL_ML),
        "V3 (dip+regime)": (V3, POOL_ML),
        "V4 (dip+volume+regime, ORIGINAL)": (V4, POOL_ML),
        "V7 (momentum+liquidity only, no dip)": (V7, POOL_ML),
        "V8 (dip, full universe, no momentum)": (V8, POOL_LIQ),
    }

    cost_lo, cost_hi = round_trip_cost_bps(POSITION_SIZE, "DELIVERY")

    results = {}
    print("Building trades and running matched-random nulls for each variant...", file=sys.stderr, flush=True)
    for name, (signals, pool) in variants.items():
        trades = attach_trades_to_signals(signals, panel, entry_exit)
        pool_trades = attach_trades_to_signals(pool, panel, entry_exit)
        cc = _candidate_count_stats(signals[signals["trade_date"].isin(post_warmup_dates)], post_warmup_dates)

        real_mean = trades["gross_return"].mean()
        re = random_entry_benchmark(trades, pool_trades, n_seeds=N_SEEDS)
        null_means = re["mean_gross_return"].to_numpy()
        pctile = float((null_means < real_mean).mean() * 100) if len(null_means) else float("nan")
        pval = _permutation_pvalue(null_means, real_mean) if len(null_means) else float("nan")
        degenerate = bool(len(null_means) and np.allclose(null_means, null_means[0]))

        stats_lo = trade_stats(trades, cost_lo, TRADES_PER_YEAR_ASSUMED)
        stats_hi = trade_stats(trades, cost_hi, TRADES_PER_YEAR_ASSUMED)
        by_year = _by_year(trades, cost_hi)

        results[name] = {
            "n_trades": len(trades), "candidate_counts": cc,
            "real_mean_gross": real_mean, "null_mean_of_means": null_means.mean() if len(null_means) else float("nan"),
            "null_std_of_means": null_means.std() if len(null_means) else float("nan"),
            "percentile": pctile, "pvalue": pval, "degenerate": degenerate,
            "stats_worstcost": stats_hi, "stats_optcost": stats_lo, "by_year": by_year,
        }

    # ---- multiple comparisons correction, over the 6 COMPUTABLE variants ----
    pvals = {name: r["pvalue"] for name, r in results.items() if pd.notna(r["pvalue"])}
    m = len(pvals)
    bonferroni_thresh = ALPHA / m
    bh = _bh_correction(pvals)

    # ---- report ----
    lines = []
    A = lines.append
    A("=" * 110)
    A("SWING PHASE 3 -- DIAGNOSTIC DECOMPOSITION OF THE FROZEN RULE")
    A("One pre-specified trial set (8 variants), multiple-comparisons corrected. No interpretation below the table.")
    A("=" * 110)

    A(f"\nV5/V6 (fundamentals-screener variants): NOT COMPUTABLE -- see BUGS.md Bug #12. "
      f"fundamental_screener.py evaluates a CURRENT as-of-today verdict only; no point-in-time historical "
      f"series exists across this backtest's 9-year span. Multiple-comparisons family below is the "
      f"{m} variants that could actually be run (V1, V2, V3, V4, V7, V8), stated explicitly rather than "
      f"silently kept at 8.")

    A(f"\nPosition size: Rs {POSITION_SIZE:,}  (round-trip DELIVERY cost {cost_lo:.1f}-{cost_hi:.1f}bps, "
      f"worst-case/optimistic ends, never blended)")
    A(f"Same-ISIN jump exclusion (BUGS.md Bug #11): {len(excluded_entities)} entities excluded from every "
      f"variant and every matched null.")
    A(f"Candidate-count stats below exclude the first {WARMUP_DAYS} trading days (momentum_12_1 warm-up, "
      f"same convention as Phase 2's table).")

    for name, r in results.items():
        A("\n" + "-" * 110)
        A(name)
        A("-" * 110)
        cc = r["candidate_counts"]
        A(f"  candidate count/day: mean={cc['mean']:.1f}  median={cc['median']:.1f}  "
          f"p10={cc['p10']:.1f}  p90={cc['p90']:.1f}  zero-days%={cc['pct_zero']:.1f}%")
        A(f"  n_trades={r['n_trades']}")
        for label, s in (("worst-case cost", r["stats_worstcost"]), ("optimistic cost", r["stats_optcost"])):
            A(f"  [{label}] expectancy={_fmt_pct(s['expectancy'])}  win_rate={s['win_rate']*100:.1f}%  "
              f"avg_win={_fmt_pct(s['avg_win'])}  avg_loss={_fmt_pct(s['avg_loss'])}  "
              f"profit_factor={s['profit_factor']:.2f}")
        if r["degenerate"]:
            A(f"  MATCHED-RANDOM NULL: DEGENERATE -- this variant's candidate count equals its own pool's "
              f"count every day (no differentiating condition beyond the pool), so sampling without "
              f"replacement at full size reproduces the identical set every seed (null std of means = "
              f"{r['null_std_of_means']:.6f}). Percentile/p-value not meaningful; reported for completeness: "
              f"percentile={r['percentile']:.1f}, p={r['pvalue']:.4f}.")
        else:
            A(f"  matched-random null (1000 seeds): mean of seed-means={_fmt_pct(r['null_mean_of_means'])}  "
              f"std of seed-means={_fmt_pct(r['null_std_of_means'])}")
            A(f"  STRATEGY MEAN GROSS RETURN: {_fmt_pct(r['real_mean_gross'])}")
            A(f"  PERCENTILE IN MATCHED-RANDOM NULL: {r['percentile']:.1f}")
            A(f"  one-sided p-value (P[null >= observed]): {r['pvalue']:.4f}")
            bonf_pass = r["pvalue"] <= bonferroni_thresh
            A(f"  Bonferroni (alpha={ALPHA}/{m}={bonferroni_thresh:.4f}): {'CLEARS' if bonf_pass else 'does NOT clear'}")
            bh_entry = bh.get(name)
            if bh_entry:
                A(f"  Benjamini-Hochberg (rank {bh_entry['rank']}/{m}, threshold {bh_entry['bh_threshold']:.4f}): "
                  f"{'CLEARS' if bh_entry['passes'] else 'does NOT clear'}")
        A(f"  by year (worst-case cost):")
        for _, row in r["by_year"].iterrows():
            A(f"    {int(row['year'])}: n={int(row['n_trades']):>4}  expectancy={_fmt_pct(row['expectancy'])}  "
              f"win_rate={row['win_rate']*100:.1f}%")

    A("\n" + "=" * 110)
    A("SUMMARY TABLE")
    A("=" * 110)
    A(f"{'variant':<40}{'n':>7}{'exp(worst)':>13}{'exp(opt)':>11}{'pctile':>9}{'p-value':>10}{'Bonf':>7}{'BH':>6}")
    for name, r in results.items():
        s_hi = r["stats_worstcost"]
        s_lo = r["stats_optcost"]
        if r["degenerate"] or pd.isna(r["pvalue"]):
            bonf_s, bh_s = "n/a", "n/a"
        else:
            bonf_s = "YES" if r["pvalue"] <= bonferroni_thresh else "no"
            bh_entry = bh.get(name)
            bh_s = "YES" if bh_entry and bh_entry["passes"] else "no"
        pctile_s = f"{r['percentile']:.1f}" + ("*" if r["degenerate"] else "")
        pval_s = f"{r['pvalue']:.4f}" if pd.notna(r["pvalue"]) else "n/a"
        A(f"{name:<40}{r['n_trades']:>7}{_fmt_pct(s_hi['expectancy']):>13}{_fmt_pct(s_lo['expectancy']):>11}"
          f"{pctile_s:>9}{pval_s:>10}{bonf_s:>7}{bh_s:>6}")
    A("\n* = degenerate null (V7 has no differentiating condition beyond its own pool; see its section above).")
    A(f"\nA variant clearing the uncorrected p<0.05 threshold but not Bonferroni/BH has NOT been established.")

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_phase3_decomposition_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
