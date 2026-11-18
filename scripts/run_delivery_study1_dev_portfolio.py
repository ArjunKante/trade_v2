"""PREREGISTRATION_DELIVERY.md Section 10 step 4, PHASE A ONLY: the real
abnormal-delivery top-decile portfolio vs. benchmark, over all usable DEV
rebalance dates. Deliberately STOPS before the SELECTION null (checkpoint
per instruction -- the null's 5,000 seeds is the expensive stage).

Loads (never recomputes) the exclusion set persisted by
`scripts/run_delivery_study1_handtrace.py`
(`results/exclusions/run_delivery_study1_dev.json`), per this project's
no-silent-recompute discipline.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from data_layer.db import get_read_connection  # noqa: E402
from data_layer.entity_panel import read_full_entity_panel_authorized  # noqa: E402
from data_layer.exclusion_list import load_exclusion_list, all_jump_dates  # noqa: E402
from delivery.signal import (  # noqa: E402
    build_up_day_panel, abnormal_delivery_at, select_top_decile,
    rebalance_dates, DECILE_FRAC,
)
from factors.target import compute_forward_return, HORIZON_DAYS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
RESULT_ID = "run_delivery_study1_dev"

COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
BLENDED_COST_BPS = 32.5


def load_delivery_resolved(con) -> pd.DataFrame:
    df = con.execute(
        """
        SELECT l.entity_id, d.trade_date, d.delivery_percent
        FROM delivery_eod d
        JOIN isin_lineage l ON d.isin = l.isin
        """
    ).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    dup = df.duplicated(subset=["entity_id", "trade_date"])
    if dup.any():
        raise AssertionError(f"{dup.sum()} duplicate (entity_id, trade_date) delivery rows -- not expected.")
    return df


def main() -> None:
    t0 = time.time()
    con = get_read_connection(WAREHOUSE_DB)
    panel = read_full_entity_panel_authorized(con, authorize_holdout=True)
    delivery = load_delivery_resolved(con)
    con.close()
    print(f"Loaded panel ({len(panel):,} rows) and delivery ({len(delivery):,} rows) in {time.time()-t0:.1f}s.")

    record = load_exclusion_list(RESULT_ID)
    jump_dates = all_jump_dates(record)
    print(f"Loaded (not recomputed) exclusion set: {len(jump_dates)} entities, "
          f"{sum(len(v) for v in jump_dates.values())} flagged rows "
          f"(content_hash={record['content_hash'][:16]}...).")

    price_cols = panel[["entity_id", "trade_date", "adjusted_close"]].copy()
    up_panel = build_up_day_panel(price_cols, delivery, unexplained_jump_dates=jump_dates)

    t1 = time.time()
    fwd = compute_forward_return(panel[["entity_id", "trade_date", "adjusted_close"]],
                                  horizon=HORIZON_DAYS, unexplained_jump_dates=jump_dates)
    print(f"Forward returns computed in {time.time()-t1:.1f}s ({len(fwd):,} rows).")

    # Liquidity tercile -- identical construction to
    # scripts/run_holdout_study1_lineage_check.py (rolling-20-trading-day
    # median turnover per entity, qcut into terciles per date).
    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
    p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
        lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
        if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index))
    tercile = p[["entity_id", "trade_date", "_tercile"]]

    all_dates = sorted(panel["trade_date"].unique())
    delivery_max_date = delivery["trade_date"].max()
    rdates = rebalance_dates(all_dates, HORIZON_DAYS, delivery_max_date=delivery_max_date)
    print(f"\n{len(rdates)} usable rebalance dates, {pd.Timestamp(rdates[0]).date()} to {pd.Timestamp(rdates[-1]).date()}.\n")

    records = []
    prev_sel_set = None
    prev_bench_set = None
    t2 = time.time()
    for i, d in enumerate(rdates):
        sig = abnormal_delivery_at(up_panel, d)
        elig = sig[sig["eligible"]][["entity_id", "abnormal_delivery"]]

        fwd_d = fwd[fwd["trade_date"] == d][["entity_id", "fwd_return"]]
        ter_d = tercile[tercile["trade_date"] == d][["entity_id", "_tercile"]]

        pool = elig.merge(fwd_d, on="entity_id").merge(ter_d, on="entity_id").dropna(subset=["abnormal_delivery", "fwd_return", "_tercile"])
        if pool.empty:
            print(f"  {pd.Timestamp(d).date()}: empty pool after merge -- SKIPPED.")
            continue

        sel, cutoff = select_top_decile(pool.rename(columns={"abnormal_delivery": "abnormal_delivery"}).assign(eligible=True))
        sel_set = set(sel["entity_id"])
        bench_set = set(pool["entity_id"])
        if not sel_set or not bench_set:
            print(f"  {pd.Timestamp(d).date()}: empty selection/benchmark set -- SKIPPED.")
            continue

        gross_ret = sel["fwd_return"].mean()
        if prev_sel_set is None:
            turnover_frac = 1.0
            tcounts = sel["_tercile"].value_counts(normalize=True)
            avg_cost = sum(tcounts.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE)
        else:
            entered = sel_set - prev_sel_set
            turnover_frac = len(entered) / max(len(sel_set), 1)
            entered_t = sel[sel["entity_id"].isin(entered)]["_tercile"].value_counts(normalize=True)
            avg_cost = sum(entered_t.get(t, 0) * COST_BY_TERCILE[t] for t in COST_BY_TERCILE) if entered else 0.0
        net_ret = gross_ret - turnover_frac * (avg_cost / 10000.0)
        prev_sel_set = sel_set

        bgross = pool["fwd_return"].mean()
        if prev_bench_set is None:
            bturnover = 1.0
        else:
            bentered = bench_set - prev_bench_set
            bturnover = len(bentered) / max(len(bench_set), 1)
        bnet = bgross - bturnover * (BLENDED_COST_BPS / 10000.0)
        prev_bench_set = bench_set

        spread = net_ret - bnet
        records.append({
            "rebalance_date": d, "pool_n": len(pool), "sel_n": len(sel_set),
            "cutoff": cutoff, "gross_ret": gross_ret, "net_ret": net_ret,
            "bench_gross": bgross, "bench_net": bnet, "spread": spread,
        })
        print(f"  {pd.Timestamp(d).date()}: pool={len(pool):4d}  sel={len(sel_set):4d}  "
              f"net={net_ret:+.4f}  bench_net={bnet:+.4f}  spread={spread:+.4f}")

    print(f"\nPortfolio loop took {time.time()-t2:.1f}s for {len(rdates)} rebalance dates.")

    rec_df = pd.DataFrame(records)
    out_path = ROOT / "results" / "run_delivery_study1_dev_portfolio.csv"
    rec_df.to_csv(out_path, index=False)
    print(f"Per-rebalance records written to {out_path}.")

    spreads = rec_df["spread"].to_numpy()
    n = len(spreads)
    mean_spread = spreads.mean()
    sd_spread = spreads.std(ddof=1)
    se_spread = sd_spread / np.sqrt(n)
    best_idx = int(np.argmax(spreads))
    mean_spread_drop_best = (spreads.sum() - spreads[best_idx]) / (n - 1)

    print("\n" + "=" * 80)
    print("REAL PORTFOLIO RESULT -- DEV window, before any null (checkpoint)")
    print("=" * 80)
    print(f"Usable quarters: {n} (of {len(rdates)} rebalance dates attempted, "
          f"{len(rdates) - n} skipped for an empty pool).")
    print(f"Mean quarterly spread (net of costs): {mean_spread:+.4f} ({mean_spread*100:+.2f}%)")
    print(f"SD of quarterly spread: {sd_spread:.4f} ({sd_spread*100:.2f}%)  SE: {se_spread:.4f}")
    print(f"Win rate (spread > 0): {(spreads > 0).mean()*100:.1f}%  ({(spreads > 0).sum()}/{n})")
    print(f"Mean spread after dropping single best quarter "
          f"({pd.Timestamp(rec_df.loc[best_idx, 'rebalance_date']).date()}, "
          f"{spreads[best_idx]:+.4f}): {mean_spread_drop_best:+.4f} ({mean_spread_drop_best*100:+.2f}%)")
    print(f"\nFor comparison, Section 6's Phase 0 random-decile null SD was 2.12% quarterly "
          f"-- this run's own measured SD is {sd_spread*100:.2f}%.")
    print("\n>>> CHECKPOINT: stopping here, before the SELECTION null (5,000 seeds). "
          "Report before proceeding, per instruction.")


if __name__ == "__main__":
    main()
