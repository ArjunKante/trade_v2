"""Swing trading: understand why V1's percentile against its own matched-
random null fell to the 1.1st (2021) and 10.1st (2024) percentile,
against 93.5-100.0 in the other seven years
(`data/swing_logs/swing_v1_checks_20260927T154446.txt`, CHECK 3).

Reports, per year, four observable-in-advance quantities, so 2021/2024 can
be compared directly against the other seven years:
  - POOL_ML's own mean gross return (was the whole candidate pool running
    hot in these years?)
  - cross-sectional dispersion of 5-day returns (mean daily std of ret_5d
    across the full EQ universe) -- a measure of how much genuine
    dispersion existed for a reversal signal to select from
  - NIFTY50's own return and realized volatility over the year
  - the average dip magnitude (mean ret_5d) of V1's own selected
    candidates

No threshold changed, no new variant, no pre-registration decision made
here -- descriptive only, to check whether the 2021/2024 shortfall
correlates with anything observable in advance.

Usage:
    python scripts/run_swing_v1_regime_check.py
"""
from __future__ import annotations

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
from swing.backtest import build_open_close_panel, entry_exit_returns, attach_trades_to_signals

ROOT = Path(__file__).resolve().parents[1]
JUMP_GAP_DAYS_CUTOFF = 5
FLAGGED_YEARS = {2021, 2024}


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

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
    con.close()

    liq_pass = liq[liq["tercile"].isin(["high_liq", "mid_liq"])][["entity_id", "trade_date"]]
    mom_top = mom[mom["in_top_decile"]][["entity_id", "trade_date"]]
    POOL_ML = mom_top.merge(liq_pass, on=["entity_id", "trade_date"], how="inner")
    rev_bottom = rev[rev["bottom_tercile"]][["entity_id", "trade_date"]]
    V1 = POOL_ML.merge(rev_bottom, on=["entity_id", "trade_date"], how="inner")

    entry_exit = entry_exit_returns(panel, jump_dates)
    trades_v1 = attach_trades_to_signals(V1, panel, entry_exit)
    pool_trades = attach_trades_to_signals(POOL_ML, panel, entry_exit)

    trades_v1["year"] = pd.to_datetime(trades_v1["signal_date"]).dt.year
    pool_trades["year"] = pd.to_datetime(pool_trades["signal_date"]).dt.year
    rev["year"] = rev["trade_date"].dt.year
    regime["year"] = regime["trade_date"].dt.year

    # V1's own selected candidates' dip magnitude -- need ret_5d attached, keyed by (entity_id, signal_date)
    v1_dip = V1.merge(rev[["entity_id", "trade_date", "ret_5d"]], on=["entity_id", "trade_date"], how="left")
    v1_dip["year"] = v1_dip["trade_date"].dt.year

    # daily cross-sectional dispersion of 5-day returns, full EQ universe
    daily_disp = rev.groupby("trade_date")["ret_5d"].std()
    daily_disp = daily_disp.to_frame("disp").reset_index()
    daily_disp["year"] = daily_disp["trade_date"].dt.year

    lines = []
    A = lines.append
    A("=" * 110)
    A("WHY DID V1's PERCENTILE FALL IN 2021 AND 2024? -- descriptive, four observables per year")
    A("=" * 110)
    A(f"{'year':<6}{'POOL_ML mean':>14}{'x-sec 5d disp':>16}{'NIFTY return':>14}{'NIFTY vol(ann)':>16}{'V1 avg dip':>13}{'V1 percentile':>15}{'flag':>6}")

    percentiles = {2017: 93.5, 2018: 100.0, 2019: 96.3, 2020: 99.1, 2021: 1.1,
                   2022: 100.0, 2023: 98.6, 2024: 10.1, 2025: 97.8}

    for yr in sorted(trades_v1["year"].unique()):
        pool_mean = pool_trades.loc[pool_trades["year"] == yr, "gross_return"].mean()
        disp_yr = daily_disp.loc[daily_disp["year"] == yr, "disp"].mean()
        nifty_yr = regime[regime["year"] == yr].sort_values("trade_date")
        if len(nifty_yr) >= 2:
            nifty_ret = nifty_yr["nifty_close"].iloc[-1] / nifty_yr["nifty_close"].iloc[0] - 1
            daily_ret = nifty_yr["nifty_close"].pct_change().dropna()
            nifty_vol = daily_ret.std() * np.sqrt(252)
        else:
            nifty_ret, nifty_vol = float("nan"), float("nan")
        avg_dip = v1_dip.loc[v1_dip["year"] == yr, "ret_5d"].mean()
        flag = "<<<" if yr in FLAGGED_YEARS else ""
        A(f"{yr:<6}{pool_mean*100:>13.3f}%{disp_yr*100:>15.3f}%{nifty_ret*100:>13.2f}%{nifty_vol*100:>15.2f}%"
          f"{avg_dip*100:>12.3f}%{percentiles.get(yr, float('nan')):>15.1f}{flag:>6}")

    A("\n" + "-" * 110)
    A("FLAGGED YEARS (2021, 2024) VS THE OTHER SEVEN -- summary")
    A("-" * 110)
    flagged_mask_pool = pool_trades["year"].isin(FLAGGED_YEARS)
    other_mask_pool = ~flagged_mask_pool
    flagged_mask_disp = daily_disp["year"].isin(FLAGGED_YEARS)
    other_mask_disp = ~flagged_mask_disp
    flagged_mask_dip = v1_dip["year"].isin(FLAGGED_YEARS)
    other_mask_dip = ~flagged_mask_dip

    A(f"POOL_ML mean gross return -- flagged years: {pool_trades.loc[flagged_mask_pool, 'gross_return'].mean()*100:.3f}%   "
      f"other seven: {pool_trades.loc[other_mask_pool, 'gross_return'].mean()*100:.3f}%")
    A(f"Cross-sectional 5d dispersion (mean daily std) -- flagged years: {daily_disp.loc[flagged_mask_disp, 'disp'].mean()*100:.3f}%   "
      f"other seven: {daily_disp.loc[other_mask_disp, 'disp'].mean()*100:.3f}%")
    A(f"V1 avg dip magnitude (mean ret_5d of selected candidates) -- flagged years: {v1_dip.loc[flagged_mask_dip, 'ret_5d'].mean()*100:.3f}%   "
      f"other seven: {v1_dip.loc[other_mask_dip, 'ret_5d'].mean()*100:.3f}%")

    nifty_flagged = regime[regime["year"].isin(FLAGGED_YEARS)].sort_values("trade_date")
    nifty_other = regime[~regime["year"].isin(FLAGGED_YEARS)].sort_values("trade_date")
    nifty_flagged_vol = nifty_flagged["nifty_close"].pct_change().dropna().std() * np.sqrt(252)
    nifty_other_vol = nifty_other["nifty_close"].pct_change().dropna().std() * np.sqrt(252)
    A(f"NIFTY realized volatility (annualized) -- flagged years: {nifty_flagged_vol*100:.2f}%   "
      f"other seven (pooled daily returns): {nifty_other_vol*100:.2f}%")

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    import datetime as dt
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_v1_regime_check_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
