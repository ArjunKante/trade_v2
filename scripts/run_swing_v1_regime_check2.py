"""Swing trading: FULL re-run of the 2021/2024 investigation, with the two
observables the first pass (`run_swing_v1_regime_check.py`,
`swing_v1_regime_check_20260927T155639.txt`) omitted: V1's own trade count,
and structural differences in the candidate set (unique entities selected,
repeat rate, candidates/day).

Per instruction: this determines whether the 2021/2024 shortfall
(1.1st/10.1st percentile vs 93.5-100.0 in the other seven years) is an
"untestable caveat" (nothing measurable separates the two years) or a
"usable risk condition" (something observable in advance predicts it) --
decided BEFORE the holdout is read, since finding a condition afterwards
and adding it would be post-hoc fitting on a resource that cannot be
reused. No condition is added to V1 regardless of what is found here;
V1's configuration stays exactly as frozen in PREREGISTRATION_SWING_V1.md.

Reports, per year:
  - POOL_ML's own mean 5-day forward return
  - cross-sectional dispersion of 5-day returns (full EQ universe)
  - NIFTY return and realized (annualized) volatility
  - V1's own average dip magnitude of selected candidates
  - V1's trade count
  - V1's candidate count/day (mean, median) -- was the pool wider/narrower?
  - V1's unique entities selected, and trades-per-unique-entity ratio --
    was the SAME handful of names recurring, or genuine turnover?
  - V1's percentile vs matched-random null (recomputed here, same
    construction as CHECK 3)

Usage:
    python scripts/run_swing_v1_regime_check2.py
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
from swing.backtest import build_open_close_panel, entry_exit_returns, attach_trades_to_signals, random_entry_benchmark

ROOT = Path(__file__).resolve().parents[1]
JUMP_GAP_DAYS_CUTOFF = 5
FLAGGED_YEARS = {2021, 2024}
N_SEEDS = 1000


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
    V1_y = V1.copy()
    V1_y["year"] = V1_y["trade_date"].dt.year

    v1_dip = V1.merge(rev[["entity_id", "trade_date", "ret_5d"]], on=["entity_id", "trade_date"], how="left")
    v1_dip["year"] = v1_dip["trade_date"].dt.year

    daily_disp = rev.groupby("trade_date")["ret_5d"].std().to_frame("disp").reset_index()
    daily_disp["year"] = daily_disp["trade_date"].dt.year

    candidates_per_day = V1_y.groupby("trade_date").size().to_frame("n").reset_index()
    candidates_per_day["year"] = candidates_per_day["trade_date"].dt.year

    lines = []
    A = lines.append
    A("=" * 130)
    A("2021/2024 INVESTIGATION, FULL RE-RUN -- decided before the holdout is read, no condition added to V1 regardless")
    A("=" * 130)
    A("\nPer year: POOL_ML mean 5d fwd return | x-sec 5d dispersion | NIFTY return/vol | V1 avg dip | "
      "V1 n_trades | V1 candidates/day (mean/median) | V1 unique entities | trades/entity | percentile")
    A("-" * 130)

    rows = []
    for yr in sorted(trades_v1["year"].unique()):
        t_yr = trades_v1[trades_v1["year"] == yr]
        pool_yr = pool_trades[pool_trades["year"] == yr]
        pool_mean = pool_yr["gross_return"].mean()
        disp_yr = daily_disp.loc[daily_disp["year"] == yr, "disp"].mean()
        nifty_yr = regime[regime["year"] == yr].sort_values("trade_date")
        if len(nifty_yr) >= 2:
            nifty_ret = nifty_yr["nifty_close"].iloc[-1] / nifty_yr["nifty_close"].iloc[0] - 1
            nifty_vol = nifty_yr["nifty_close"].pct_change().dropna().std() * np.sqrt(252)
        else:
            nifty_ret, nifty_vol = float("nan"), float("nan")
        avg_dip = v1_dip.loc[v1_dip["year"] == yr, "ret_5d"].mean()

        cpd_yr = candidates_per_day[candidates_per_day["year"] == yr]["n"]
        n_trades_yr = len(t_yr)
        n_unique = t_yr["entity_id"].nunique()
        trades_per_entity = n_trades_yr / n_unique if n_unique else float("nan")

        re_yr = random_entry_benchmark(t_yr, pool_yr, n_seeds=N_SEEDS)
        null_means = re_yr["mean_gross_return"].to_numpy()
        real_mean = t_yr["gross_return"].mean()
        pctile = float((null_means < real_mean).mean() * 100) if len(null_means) else float("nan")

        rows.append({
            "year": yr, "pool_mean": pool_mean, "disp": disp_yr, "nifty_ret": nifty_ret, "nifty_vol": nifty_vol,
            "avg_dip": avg_dip, "n_trades": n_trades_yr, "cpd_mean": cpd_yr.mean(), "cpd_median": cpd_yr.median(),
            "n_unique": n_unique, "trades_per_entity": trades_per_entity, "pctile": pctile,
        })
        flag = " <<<" if yr in FLAGGED_YEARS else ""
        A(f"{yr}: pool={pool_mean*100:>7.3f}%  disp={disp_yr*100:>6.3f}%  nifty_ret={nifty_ret*100:>7.2f}%  "
          f"nifty_vol={nifty_vol*100:>6.2f}%  avg_dip={avg_dip*100:>7.3f}%  n_trades={n_trades_yr:>6}  "
          f"cand/day={cpd_yr.mean():>5.1f}/{cpd_yr.median():>4.1f}  unique_entities={n_unique:>4}  "
          f"trades/entity={trades_per_entity:>4.2f}  percentile={pctile:>5.1f}{flag}")

    df = pd.DataFrame(rows)
    flagged_df = df[df["year"].isin(FLAGGED_YEARS)]
    other_df = df[~df["year"].isin(FLAGGED_YEARS)]

    A("\n" + "-" * 130)
    A("FLAGGED (2021, 2024) VS OTHER SEVEN -- means")
    A("-" * 130)
    for col, label, fmt in [
        ("pool_mean", "POOL_ML mean 5d fwd return", "{:.3f}%"),
        ("disp", "cross-sectional 5d dispersion", "{:.3f}%"),
        ("nifty_ret", "NIFTY return", "{:.2f}%"),
        ("nifty_vol", "NIFTY realized vol (annualized)", "{:.2f}%"),
        ("avg_dip", "V1 avg dip magnitude", "{:.3f}%"),
        ("n_trades", "V1 n_trades", "{:.0f}"),
        ("cpd_mean", "V1 candidates/day (mean)", "{:.1f}"),
        ("n_unique", "V1 unique entities selected", "{:.0f}"),
        ("trades_per_entity", "V1 trades per unique entity", "{:.2f}"),
    ]:
        mult = 100 if "%" in fmt else 1
        fval = fmt.format(flagged_df[col].mean() * mult)
        oval = fmt.format(other_df[col].mean() * mult)
        A(f"  {label:<34} flagged={fval:>10}   other seven={oval:>10}")

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_v1_regime_check2_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
