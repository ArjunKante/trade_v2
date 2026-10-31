"""Two read-only diagnostics on Liquidity Study A's and Study B's own
ALREADY-CLOSED/ALREADY-RUN DEV trades (`data/liquidity/{a,b}/dev_backtest.pkl`).
NO new study, NO rule changes, NO recomputation of either study's own
verdict -- this script only reads each study's own real trade records and
cross-references them against (a) the six raw level values that formed
each trade's own confluence zone (recomputed live via each study's own
unchanged `_build_level_lookup_for_entity`/`to_raw_scale`, the same
read-only discipline every viz adapter already uses) and (b) the
warehouse's own `prices_eod.turnover` field (the exact quantity
`fibo.universe.reconstitute_annually` already ranks `rank`/`band` from).

1. DEGENERATE CONFLUENCE: of each study's own real trades, how many had
   two or more of the trade's OWN clustered levels (`confluence_members`)
   equal or within 0.1% of each other -- the timeframes collapsing onto
   the same number rather than independently agreeing -- and what was
   the mean net return for those trades vs. the rest.

2. TURNOVER RELATIONSHIP: split each study's own real trades into
   quintiles by the stock's own median daily turnover in that trade's
   own ranking year (the identical `median_turnover_prior_year` quantity
   `reconstitute_annually` already computed to produce every trade's own
   `rank`/`band`), and report mean net return and half-target reach rate
   per quintile.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from data_layer.db import get_read_connection as get_warehouse_con
from fibo.price_scale import to_raw_scale
from fibo.universe import reconstitute_annually

from liquidity.a import _build_level_lookup_for_entity
from poc.v4 import _build_adjustment_factor_lookup_for_entity

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"

DEGENERATE_REL_TOL = 0.001  # 0.1%, per instruction

STUDIES = {
    "A": {"path": ROOT / "data" / "liquidity" / "a" / "dev_backtest.pkl", "prefix": "lo"},
    "B": {"path": ROOT / "data" / "liquidity" / "b" / "dev_backtest.pkl", "prefix": "hi"},
}


def load_trades(path: Path) -> pd.DataFrame:
    with open(path, "rb") as f:
        res = pickle.load(f)
    return res["trades"].copy()


# ---------------------------------------------------------------------
# Diagnostic 1: degenerate confluence
# ---------------------------------------------------------------------

def flag_degenerate(warehouse_con, trades: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Adds `is_degenerate` (bool) and `degenerate_pair`/`degenerate_rel_diff`
    (the worst-offending pair, for spot-checking) to a copy of `trades`.
    Recomputes each trade's own raw-scale level values live via
    `liquidity.a._build_level_lookup_for_entity` (shared, unchanged --
    Study B's own module reuses this exact function too) and
    `poc.v4._build_adjustment_factor_lookup_for_entity` -- the identical
    functions every liquidity viz adapter already calls for display, now
    used read-only for an aggregate check instead of a single chart."""
    out = trades.copy()
    is_degenerate = np.zeros(len(out), dtype=bool)
    worst_pair = [None] * len(out)
    worst_rel_diff = np.full(len(out), np.nan)

    for entity_id, idx in out.groupby("entity_id").groups.items():
        level_lookup = _build_level_lookup_for_entity(warehouse_con, entity_id)
        factor_lookup = _build_adjustment_factor_lookup_for_entity(warehouse_con, entity_id)
        for i in idx:
            row = out.loc[i]
            trade_date, members = row["trade_date"], row["confluence_members"]
            lv = level_lookup.get(trade_date)
            factor = factor_lookup.get(trade_date)
            if lv is None or factor is None:
                continue  # should not happen -- every real trade had a resolvable level set
            raw = {m: to_raw_scale(lv[f"{prefix}_{m}"], factor) for m in members}
            best_rel, best_pair = None, None
            for a_idx in range(len(members)):
                for b_idx in range(a_idx + 1, len(members)):
                    a_m, b_m = members[a_idx], members[b_idx]
                    a_v, b_v = raw[a_m], raw[b_m]
                    rel_diff = abs(a_v - b_v) / ((a_v + b_v) / 2.0)
                    if best_rel is None or rel_diff < best_rel:
                        best_rel, best_pair = rel_diff, (a_m, b_m)
            worst_rel_diff[out.index.get_loc(i)] = best_rel
            worst_pair[out.index.get_loc(i)] = best_pair
            if best_rel is not None and best_rel <= DEGENERATE_REL_TOL:
                is_degenerate[out.index.get_loc(i)] = True

    out["is_degenerate"] = is_degenerate
    out["degenerate_closest_pair"] = worst_pair
    out["degenerate_closest_rel_diff"] = worst_rel_diff
    return out


def report_degenerate(label: str, trades: pd.DataFrame) -> None:
    n = len(trades)
    deg = trades[trades["is_degenerate"]]
    rest = trades[~trades["is_degenerate"]]
    print(f"\n--- Study {label}: DEGENERATE CONFLUENCE ---")
    print(f"  n_trades = {n:,}")
    print(f"  n_degenerate (>=2 clustered levels within {DEGENERATE_REL_TOL*100:.1f}%) = "
          f"{len(deg):,}  ({len(deg)/n*100:.1f}%)")
    print(f"  mean net_return_pct, degenerate     = {deg['net_return_pct'].mean()*100:+.4f}%  "
          f"(n={len(deg):,})")
    print(f"  mean net_return_pct, non-degenerate = {rest['net_return_pct'].mean()*100:+.4f}%  "
          f"(n={len(rest):,})")
    print(f"  mean net_return_pct, ALL            = {trades['net_return_pct'].mean()*100:+.4f}%")
    if len(deg):
        print(f"  win_rate degenerate = {(deg['net_return_pct']>0).mean()*100:.1f}%   "
              f"win_rate non-degenerate = {(rest['net_return_pct']>0).mean()*100:.1f}%")
        by_pair = deg.groupby(deg["degenerate_closest_pair"].apply(lambda p: "+".join(p))).agg(
            count=("net_return_pct", "size"), mean_net_return_pct=("net_return_pct", "mean"))
        print("  degenerate breakdown by which pair collapsed:")
        print(by_pair.to_string())


def spot_check_example(warehouse_con, trades: pd.DataFrame, prefix: str,
                        entity_id: str, trade_date) -> None:
    row = trades[(trades["entity_id"] == entity_id) & (trades["trade_date"] == trade_date)]
    if row.empty:
        print(f"  [spot-check] {entity_id} {trade_date}: not found in this study's own trades")
        return
    row = row.iloc[0]
    print(f"  [spot-check] {entity_id} {trade_date}: confluence_members={row['confluence_members']} "
          f"zone_price={row['zone_price']:.4f} is_degenerate={row['is_degenerate']} "
          f"closest_pair={row['degenerate_closest_pair']} "
          f"closest_rel_diff={row['degenerate_closest_rel_diff']*100:.4f}%")


# ---------------------------------------------------------------------
# Diagnostic 2: turnover relationship
# ---------------------------------------------------------------------

def attach_turnover(trades: pd.DataFrame, turnover_lookup: dict) -> pd.DataFrame:
    out = trades.copy()
    out["median_turnover"] = out.apply(
        lambda r: turnover_lookup.get((r["year"], r["entity_id"])), axis=1)
    return out


def report_turnover_quintiles(label: str, trades: pd.DataFrame) -> None:
    n_total = len(trades)
    missing = trades["median_turnover"].isna().sum()
    present = trades[trades["median_turnover"].notna()].copy()
    print(f"\n--- Study {label}: TURNOVER RELATIONSHIP ---")
    if missing:
        print(f"  WARNING: {missing}/{n_total} trades had no (year, entity_id) match in the "
              f"top-200 annual turnover table -- excluded from the quintile split below.")

    present["quintile"] = pd.qcut(present["median_turnover"], 5,
                                   labels=["Q1 (lowest)", "Q2", "Q3", "Q4", "Q5 (highest)"])

    qty1 = present[present["qty1_path"]]
    rows = []
    for q in ["Q1 (lowest)", "Q2", "Q3", "Q4", "Q5 (highest)"]:
        grp = present[present["quintile"] == q]
        scaled = grp[~grp["qty1_path"]]
        half_reached = scaled[scaled["half_exit_happened"]]
        rows.append({
            "quintile": q, "n_trades": len(grp),
            "turnover_range_rs": f"[{grp['median_turnover'].min():,.0f}, {grp['median_turnover'].max():,.0f}]",
            "mean_net_return_pct": grp["net_return_pct"].mean() * 100,
            "win_rate_pct": (grp["net_return_pct"] > 0).mean() * 100,
            "half_target_reach_rate_pct": (
                len(half_reached) / len(scaled) * 100 if len(scaled) else float("nan")),
        })
    out_df = pd.DataFrame(rows)
    print(out_df.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    # monotonicity check, stated plainly rather than left for the reader to eyeball
    means = out_df["mean_net_return_pct"].to_numpy()
    diffs = np.diff(means)
    monotonic_nondecreasing = bool(np.all(diffs >= -1e-9))
    print(f"  mean net return strictly/weakly increasing Q1->Q5: {monotonic_nondecreasing}  "
          f"(diffs: {[f'{d:+.4f}' for d in diffs]})")


def main():
    warehouse_con = get_warehouse_con(WAREHOUSE_DB)

    print("Building top-200 annual turnover table (fibo.universe.reconstitute_annually) ...")
    universe = reconstitute_annually(warehouse_con, top_n=200)
    turnover_lookup = {
        (r["year"], r["entity_id"]): r["median_turnover_prior_year"] for _, r in universe.iterrows()
    }
    print(f"  {len(turnover_lookup):,} (year, entity_id) turnover entries available")

    degenerate_results = {}
    for label, cfg in STUDIES.items():
        print(f"\n=== Study {label}: loading trades and recomputing levels (read-only) ===")
        trades = load_trades(cfg["path"])
        trades = flag_degenerate(warehouse_con, trades, cfg["prefix"])
        degenerate_results[label] = trades
        report_degenerate(label, trades)

    print("\n=== Spot-check against the user's own named example ===")
    spot_check_example(warehouse_con, degenerate_results["A"], "lo", "INE019A01020",
                        pd.Timestamp("2020-03-23").date())
    spot_check_example(warehouse_con, degenerate_results["B"], "hi", "INE019A01020",
                        pd.Timestamp("2020-03-23").date())

    for label, trades in degenerate_results.items():
        trades = attach_turnover(trades, turnover_lookup)
        report_turnover_quintiles(label, trades)


if __name__ == "__main__":
    main()
