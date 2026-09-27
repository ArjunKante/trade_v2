"""THE SWING V1 HOLDOUT EVALUATION -- run exactly once, per
PREREGISTRATION_SWING_V1.md. This is the one script authorized to read
past SEALED_HOLDOUT_START for the swing project. Every condition,
threshold, and construction rule here is copied unchanged from that frozen
document -- nothing is tuned here, nothing changes in response to what
this run shows.

Charges ONE of the two remaining project-wide holdout slots
(`FINDINGS.md` Section 6/7) -- that ledger is updated in the same change
that runs this script, not separately.

Continuous computation from the full available panel (2016 through the
latest available date), matching `scripts/run_holdout_study1.py`'s own
precedent, so momentum/liquidity/reversal lookbacks carry naturally across
the holdout boundary -- but only holdout-window signals are used for the
decision rule.

Decision rule (PREREGISTRATION_SWING_V1.md Section 5):
  PRIMARY GATE: V1 (Top-10/day by dip magnitude)'s holdout-window trades'
    mean gross return percentile vs. a matched-random null drawn from
    POOL_ML, restricted to the SAME holdout window, same day-count/timing,
    1000 seeds. PASS if percentile >= 95, FAIL otherwise. NOT EVALUATED AT
    ALL if holdout trade count < 1,080 (Section 6's power threshold) --
    the pre-registration is explicit that this is not softened into a weak
    read.
  REPORTED, NOT GATING: expectancy net of costs at Rs 3L, with the
    pool-contamination caveat attached verbatim.
  SECONDARY, DESCRIPTIVE ONLY: trade count, peak concurrent positions,
    peak capital, win rate, avg win, avg loss, profit factor, the trade
    return distribution, and a by-month breakdown.

Usage:
    python scripts/run_swing_v1_holdout.py
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
    historical_bottom_tercile_5d_return,
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
TOP_N = 10
POWER_THRESHOLD_TRADES = 1080
PERCENTILE_PASS_THRESHOLD = 95.0

LOG_PATH = ROOT / "data" / "holdout_access_log.txt"


def _fmt_pct(x):
    return f"{x*100:.3f}%" if pd.notna(x) else "n/a"


def main() -> int:
    with open(LOG_PATH, "a") as f:
        f.write(f"{dt.datetime.now().isoformat()} | scripts/run_swing_v1_holdout.py | "
                f"authorize_holdout=True | swing project, V1 Top-10 holdout evaluation "
                f"(PREREGISTRATION_SWING_V1.md) | charges 1 of the 2 remaining project-wide "
                f"holdout slots (FINDINGS.md Section 6/7)\n")
    print(f"Holdout access authorized and logged to {LOG_PATH}", file=sys.stderr, flush=True)

    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    max_date = con.execute("SELECT MAX(trade_date) FROM prices_eod").fetchone()[0]
    read_through = max_date + dt.timedelta(days=1)  # exclusive upper bound, captures max_date itself
    print(f"Latest available trade_date in warehouse: {max_date}. Reading full panel through it.",
          file=sys.stderr, flush=True)

    flagged = unexplained_same_isin_jump_entities(con)  # full warehouse, established precedent
    flagged_tight = flagged[flagged["gap_days"] <= JUMP_GAP_DAYS_CUTOFF]
    excluded_entities = set(flagged_tight["entity_id"].unique())

    panel_all = build_open_close_panel(con, read_through, authorize_holdout=True)
    panel = panel_all[~panel_all["entity_id"].isin(excluded_entities)].reset_index(drop=True)
    jump_dates = unexplained_jump_boundaries(con, before=None)  # full-range gap guard, holdout included

    mom = historical_momentum_top_decile(panel, jump_dates)
    liq = historical_liquidity_tercile(panel)
    rev = historical_bottom_tercile_5d_return(panel, jump_dates)
    con.close()

    liq_pass = liq[liq["tercile"].isin(["high_liq", "mid_liq"])][["entity_id", "trade_date"]]
    mom_top = mom[mom["in_top_decile"]][["entity_id", "trade_date"]]
    POOL_ML = mom_top.merge(liq_pass, on=["entity_id", "trade_date"], how="inner")
    rev_bottom = rev[rev["bottom_tercile"]][["entity_id", "trade_date"]]
    V1 = POOL_ML.merge(rev_bottom, on=["entity_id", "trade_date"], how="inner")

    v1_dip = V1.merge(rev[["entity_id", "trade_date", "ret_5d"]], on=["entity_id", "trade_date"], how="left")
    v1_dip["dip_rank"] = v1_dip.groupby("trade_date")["ret_5d"].rank(method="first", ascending=True)
    TOP10 = v1_dip[v1_dip["dip_rank"] <= TOP_N][["entity_id", "trade_date"]]

    entry_exit = entry_exit_returns(panel, jump_dates)
    trades_top10_all = attach_trades_to_signals(TOP10, panel, entry_exit)
    pool_trades_all = attach_trades_to_signals(POOL_ML, panel, entry_exit)

    holdout_start_ts = pd.Timestamp(SEALED_HOLDOUT_START)
    trades_top10 = trades_top10_all[trades_top10_all["signal_date"] >= holdout_start_ts].reset_index(drop=True)
    pool_trades_holdout = pool_trades_all[pool_trades_all["signal_date"] >= holdout_start_ts].reset_index(drop=True)

    all_dates_holdout = pd.Index(sorted(panel.loc[panel["trade_date"] >= holdout_start_ts, "trade_date"].unique()))

    cost_lo, cost_hi = round_trip_cost_bps(POSITION_SIZE, "DELIVERY")

    lines = []
    A = lines.append
    A("=" * 110)
    A("SWING V1 (TOP-10 CONCENTRATED) -- SEALED HOLDOUT EVALUATION")
    A("Per PREREGISTRATION_SWING_V1.md. One read. No changes made in response to this result.")
    A("=" * 110)
    A(f"\nHoldout window: {SEALED_HOLDOUT_START} through {max_date} "
      f"({len(all_dates_holdout)} trading dates)")
    A(f"Position size: Rs {POSITION_SIZE:,}  (round-trip DELIVERY cost {cost_lo:.1f}-{cost_hi:.1f}bps)")
    A(f"Same-ISIN jump exclusion (BUGS.md Bug #11): {len(excluded_entities)} entities excluded.")

    n_trades = len(trades_top10)
    A(f"\n--- TRADE COUNT vs. POWER THRESHOLD ---")
    A(f"V1 (Top-10) holdout trades: {n_trades}")
    A(f"Power threshold (PREREGISTRATION_SWING_V1.md Section 6): {POWER_THRESHOLD_TRADES}")

    if n_trades < POWER_THRESHOLD_TRADES:
        A(f"\nPRIMARY GATE: NOT EVALUATED. n={n_trades} is below the pre-registered power threshold "
          f"of {POWER_THRESHOLD_TRADES} trades. Per Section 6, this is the recorded outcome, not a "
          f"weak or interim read -- no percentile is computed or reported as a decision.")
        gate_result = "NOT EVALUATED"
        pctile = None
    else:
        real_mean = trades_top10["gross_return"].mean()
        re = random_entry_benchmark(trades_top10, pool_trades_holdout, n_seeds=N_SEEDS)
        null_means = re["mean_gross_return"].to_numpy()
        pctile = float((null_means < real_mean).mean() * 100) if len(null_means) else float("nan")
        pval = (np.sum(null_means >= real_mean) + 1) / (len(null_means) + 1) if len(null_means) else float("nan")
        gate_result = "PASS" if pctile >= PERCENTILE_PASS_THRESHOLD else "FAIL"

        A(f"\n--- PRIMARY GATE: percentile vs. matched-random null from POOL_ML, holdout window only ---")
        A(f"POOL_ML holdout trades (null-draw pool): {len(pool_trades_holdout)}")
        A(f"V1 (Top-10) mean gross return, holdout: {_fmt_pct(real_mean)}")
        A(f"Matched-random null (1000 seeds, same day-count/timing): mean of seed-means="
          f"{_fmt_pct(null_means.mean())}  std of seed-means={_fmt_pct(null_means.std())}")
        A(f"PERCENTILE: {pctile:.1f}")
        A(f"One-sided p-value (P[null >= observed]): {pval:.4f}")
        A(f"THRESHOLD: PASS requires percentile >= {PERCENTILE_PASS_THRESHOLD:.0f}")
        A(f"RESULT: {gate_result}")

    A(f"\n--- REPORTED, NOT GATING: expectancy net of costs at Rs {POSITION_SIZE:,} ---")
    A("CAVEAT (verbatim, per PREREGISTRATION_SWING_V1.md Section 5): \"POOL_ML's own performance in "
      "this window is already known, directionally, to have been strong (Study 1's related momentum "
      "measurement, 14.72% vs 10.85% CAGR) before this figure was computed. This number reflects the "
      "pool's own drift as much as V1's own selection, and carries little information on its own -- it "
      "is not a pass/fail condition.\"")
    if n_trades > 0:
        s_hi = trade_stats(trades_top10, cost_hi, TRADES_PER_YEAR_ASSUMED)
        s_lo = trade_stats(trades_top10, cost_lo, TRADES_PER_YEAR_ASSUMED)
        A(f"[worst-case cost] expectancy={_fmt_pct(s_hi['expectancy'])}  win_rate={s_hi['win_rate']*100:.1f}%  "
          f"avg_win={_fmt_pct(s_hi['avg_win'])}  avg_loss={_fmt_pct(s_hi['avg_loss'])}  "
          f"profit_factor={s_hi['profit_factor']:.2f}")
        A(f"[optimistic cost]  expectancy={_fmt_pct(s_lo['expectancy'])}  win_rate={s_lo['win_rate']*100:.1f}%  "
          f"avg_win={_fmt_pct(s_lo['avg_win'])}  avg_loss={_fmt_pct(s_lo['avg_loss'])}  "
          f"profit_factor={s_lo['profit_factor']:.2f}")

    A(f"\n--- SECONDARY, DESCRIPTIVE ONLY ---")
    if n_trades > 0:
        conc = concurrent_positions(trades_top10, all_dates_holdout)
        max_conc = int(conc.max())
        A(f"Trade count: {n_trades}")
        A(f"Peak concurrent positions: {max_conc}")
        A(f"Peak deployed capital at Rs {POSITION_SIZE:,} floor: Rs {max_conc*POSITION_SIZE:,} "
          f"(Rs {max_conc*POSITION_SIZE/1e7:.2f} crore)")

        A(f"\nTrade return distribution (gross, before costs):")
        q = trades_top10["gross_return"].quantile([0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0])
        A(f"  min={_fmt_pct(q[0.0])}  p10={_fmt_pct(q[0.10])}  p25={_fmt_pct(q[0.25])}  "
          f"median={_fmt_pct(q[0.50])}  p75={_fmt_pct(q[0.75])}  p90={_fmt_pct(q[0.90])}  max={_fmt_pct(q[1.0])}")

        A(f"\nBy month (worst-case cost):")
        t = trades_top10.copy()
        t["month"] = pd.to_datetime(t["signal_date"]).dt.to_period("M")
        net = t["gross_return"] - cost_hi / 10_000
        t = t.assign(net=net)
        for mo, g in t.groupby("month"):
            wins = g["net"][g["net"] > 0]
            A(f"  {mo}: n={len(g):>4}  expectancy={_fmt_pct(g['net'].mean())}  "
              f"win_rate={len(wins)/len(g)*100:.1f}%")
    else:
        A("No holdout trades produced -- nothing further to report.")

    A("\n" + "=" * 110)
    A(f"PRIMARY GATE RESULT: {gate_result}")
    A("=" * 110)

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_v1_holdout_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)

    trades_top10.to_csv(ROOT / "data" / "swing_v1_holdout_trades.csv", index=False)
    print(f"Trade-level detail saved to data/swing_v1_holdout_trades.csv", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
