"""PREREGISTRATION_DARVAS.md Process Step 2: hand-trace 5 real DEV-window
trades before any aggregate number is computed. Runs the real backtest
over the DEV window ONLY (test_seal.guard_date_range with
authorize_test=False -- a no-op since DEV never intersects the sealed
window), then searches the resulting trades/boxes for 5 required shapes:
one stopped at the initial box bottom, one where the stop trailed up
through a genuinely new box, one long-running winner, one box that formed
but never broke out, one same-day top-and-bottom box. Prints a full trace
for each -- box lineage (top/bottom prices and confirm dates), the
position's own stop history, and the resulting net R.
"""
from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from data_layer.db import get_read_connection
from darvas import test_seal
from darvas.backtest import run_backtest

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"


def fmt_box(b: dict) -> str:
    return (
        f"top={b['top_price']:.2f} (peak {pd.Timestamp(b['peak_date']).date()}, "
        f"confirmed {pd.Timestamp(b['top_confirm_date']).date() if b['top_confirm_date'] is not None else None}) | "
        f"bottom={b['bottom_price'] if b['bottom_price'] is None else round(b['bottom_price'], 2)} "
        f"(confirmed {pd.Timestamp(b['bottom_confirm_date']).date() if b['bottom_confirm_date'] is not None else None}) | "
        f"outcome={b['outcome']} resolve={pd.Timestamp(b['resolve_date']).date() if b['resolve_date'] is not None else None} "
        f"same_day={b['same_day_top_bottom']}"
    )


def print_trade_trace(label: str, trade: pd.Series, all_boxes: pd.DataFrame):
    print(f"\n{'='*100}\n{label}: {trade['entity_id']}\n{'='*100}")
    print(f"ENTRY  {trade['entry_date'].date()}  price={trade['entry_price']:.2f}  "
          f"qty={trade['qty']}  position_size_rs={trade['position_size_rs']:.0f}")
    print(f"       initial_stop (entry box bottom) = {trade['initial_stop']:.2f}")
    print(f"       entry_box_top = {trade['entry_box_top']:.2f}  rho = {trade['rho']:.4f}")
    print(f"EXIT   {trade['exit_date'].date()}  price={trade['exit_price']:.2f}  reason={trade['exit_reason']}")
    print(f"       holding: {trade['holding_trading_days']} trading days "
          f"({trade['holding_days']} calendar days)")
    print(f"       pnl_rs={trade['pnl_rs']:.2f}  cost_rs={trade['cost_rs']:.2f}  net_r={trade['net_r']:.4f}")
    print(f"       stop raises: {trade['n_stop_raises']}  final_stop={trade['final_stop']:.2f}")
    print(f"\n  Stop history for this position:")
    for h in trade["stop_history"]:
        box_note = ""
        if h["box"] is not None:
            b = h["box"]
            box_note = (f"  [box top={b['top_price']:.2f} bottom={b['bottom_price']:.2f} "
                        f"top_confirm={pd.Timestamp(b['top_confirm_date']).date()} "
                        f"bottom_confirm={pd.Timestamp(b['bottom_confirm_date']).date()}]")
        print(f"    {h['date'].date()}  stop -> {h['stop']:.2f}  ({h['reason']}){box_note}")

    print(f"\n  Full box lineage for {trade['entity_id']} around this trade:")
    eb = all_boxes[all_boxes["entity_id"] == trade["entity_id"]].sort_values("peak_date")
    window_lo = trade["entry_date"] - pd.Timedelta(days=400)
    window_hi = trade["exit_date"] + pd.Timedelta(days=30)
    nearby = eb[(eb["peak_date"] >= window_lo) & (eb["peak_date"] <= window_hi)]
    for _, b in nearby.iterrows():
        print(f"    {fmt_box(b.to_dict())}")


def main():
    t0 = time.time()
    con = get_read_connection(WAREHOUSE_DB)
    test_seal.guard_date_range(test_seal.DEV_START, test_seal.DEV_END, authorize_test=False,
                                caller="darvas_handtrace.py", reason="hand-trace, DEV window only")
    print(f"Running DEV backtest {test_seal.DEV_START} to {test_seal.DEV_END} ...")
    result = run_backtest(con, test_seal.DEV_START, test_seal.DEV_END, authorize_test=False)
    elapsed = time.time() - t0
    trades = result["trades"]
    boxes = result["boxes"]
    print(f"Done in {elapsed/60:.1f} min. {len(trades)} trades, {len(boxes)} box records, "
          f"{result['zero_qty_skips']} zero-qty skips, "
          f"{result['breakouts_skipped_in_position']} breakouts skipped (already in position), "
          f"{result['non_member_year_trades_dropped']} trades dropped (not a declared universe member that year), "
          f"{len(result['errors'])} entity errors")
    if result["errors"]:
        for e in result["errors"][:10]:
            print("  ERROR:", e)

    if trades.empty:
        print("NO TRADES in DEV window -- cannot hand-trace. Stopping here.")
        return

    trades = trades.sort_values("entry_date").reset_index(drop=True)

    # ---- 1. stopped at the initial box bottom (never raised) ----
    never_raised_stop = trades[(trades["exit_reason"] == "STOP") & (trades["n_stop_raises"] == 0)]
    # ---- 2. stop trailed up through a genuinely new box ----
    new_box_raised = trades[trades["stop_history"].apply(
        lambda h: any(x["reason"] == "NEW_BOX" for x in h))]
    # ---- 3. long-running winner with RUN_UP active ----
    run_up_winner = trades[(trades["net_r"] > 0) & trades["stop_history"].apply(
        lambda h: any(x["reason"] == "RUN_UP" for x in h))].sort_values("holding_trading_days", ascending=False)

    print(f"\nCandidate counts: never_raised_stop={len(never_raised_stop)}, "
          f"new_box_raised={len(new_box_raised)}, run_up_winner={len(run_up_winner)}")

    if len(never_raised_stop):
        print_trade_trace("TRACE 1 -- stopped at the initial box bottom", never_raised_stop.iloc[0], boxes)
    else:
        print("\nTRACE 1 -- NO trade found that was stopped at the initial box bottom with zero raises. "
              "Stated plainly, per instruction, rather than manufactured.")

    if len(new_box_raised):
        # prefer one that actually exited via STOP after the raise, to show the raise mattering
        exited_after_raise = new_box_raised[new_box_raised["exit_reason"] == "STOP"]
        pick = exited_after_raise.iloc[0] if len(exited_after_raise) else new_box_raised.iloc[0]
        print_trade_trace("TRACE 2 -- stop trailed up through a NEW BOX", pick, boxes)
    else:
        print("\nTRACE 2 -- NO trade found where the stop trailed through a new box. "
              "Stated plainly, per instruction, rather than manufactured.")

    if len(run_up_winner):
        print_trade_trace("TRACE 3 -- long-running winner (Sub-rule 2 run-up trailing active)",
                           run_up_winner.iloc[0], boxes)
    else:
        print("\nTRACE 3 -- NO run-up-trailing winner found. Stated plainly, per instruction.")

    # ---- 4. a box that formed (top+bottom confirmed) but never broke out ----
    never_broke_out = boxes[boxes["outcome"].isin(["COMPLETE_BREAKDOWN", "COMPLETE_UNRESOLVED_AT_WINDOW_END"])]
    if len(never_broke_out):
        b = never_broke_out.iloc[0]
        print(f"\n{'='*100}\nTRACE 4 -- a box that formed but never broke out: {b['entity_id']}\n{'='*100}")
        print(f"  {fmt_box(b.to_dict())}")
    else:
        print("\nTRACE 4 -- NO box found that formed but never broke out. Stated plainly, per instruction.")

    # ---- 5. same-day top-and-bottom box ----
    same_day = boxes[boxes["same_day_top_bottom"] == True]  # noqa: E712
    if len(same_day):
        b = same_day.iloc[0]
        print(f"\n{'='*100}\nTRACE 5 -- same-day top-and-bottom box: {b['entity_id']}\n{'='*100}")
        print(f"  {fmt_box(b.to_dict())}")
        print(f"  (same-day confirmations found: {len(same_day)} out of "
              f"{len(boxes[boxes['outcome'].isin(['COMPLETE_BREAKOUT','COMPLETE_BREAKDOWN','COMPLETE_UNRESOLVED_AT_WINDOW_END'])])} complete boxes)")
    else:
        print("\nTRACE 5 -- NO same-day top-and-bottom box found. Stated plainly, per instruction.")

    out_dir = ROOT / "data" / "darvas"
    out_dir.mkdir(parents=True, exist_ok=True)
    trades.drop(columns=["stop_history"]).to_pickle(out_dir / "handtrace_dev_trades.pkl")
    boxes.to_pickle(out_dir / "handtrace_dev_boxes.pkl")
    print(f"\nSaved full DEV trades/boxes to {out_dir} for later reuse (DEV run will recompute, "
          f"not depend on these pickles).")


if __name__ == "__main__":
    main()
