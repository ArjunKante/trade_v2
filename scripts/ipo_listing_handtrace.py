"""PREREGISTRATION_IPO.md Process Step 4: hand-trace 5 real DEV-window
cases before any aggregate number is computed. Finds one target hit,
one stop hit, one 15:15 time exit, one red/flat-first-candle skip, and
one scale-corrected listing, and prints every value needed to verify
each by hand against the frozen Section 5 rules.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ipo_listing.backtest import load_usable_listings, load_day_bars, run_one
from ipo_listing.intraday_db import get_read_connection
from ipo_listing import test_seal

ROOT = Path(__file__).resolve().parents[1]
INTRADAY_DB = ROOT / "data" / "ipo_listing" / "ipo_intraday.duckdb"


def main():
    icon = get_read_connection(INTRADAY_DB)

    listings = load_usable_listings(icon)
    dev = listings[pd.to_datetime(listings["listing_date"]) <= pd.Timestamp(test_seal.DEV_END)]
    print(f"DEV usable listings: {len(dev)}")

    target_ex = stop_ex = time_ex = skip_ex = scale_ex = None
    for _, r in dev.iterrows():
        bars = load_day_bars(icon, int(r["listing_id"]))
        rec = run_one(bars, r)
        if rec["status"] == "SKIPPED_RED_OR_FLAT" and skip_ex is None:
            skip_ex = (r, bars, rec)
        if rec["status"] == "ENTERED":
            if rec["exit_outcome"] == "TARGET" and target_ex is None:
                target_ex = (r, bars, rec)
            if rec["exit_outcome"] == "STOP" and stop_ex is None:
                stop_ex = (r, bars, rec)
            if rec["exit_outcome"] == "TIME_EXIT" and time_ex is None:
                time_ex = (r, bars, rec)
            has_rev2 = icon.execute(
                "SELECT COUNT(*) FROM bars_1min WHERE listing_id = ? AND revision_seq = 2", [int(r["listing_id"])]
            ).fetchone()[0]
            if has_rev2 and scale_ex is None:
                scale_ex = (r, bars, rec)
        if target_ex and stop_ex and time_ex and skip_ex and scale_ex:
            break

    def show(label, item):
        if item is None:
            print(f"\n=== {label}: NONE FOUND ===")
            return
        r, bars, rec = item
        print(f"\n=== {label} ===")
        print(f"listing_id={r['listing_id']} company={r['company_name']} symbol={r['symbol_used']} "
              f"listing_date={r['listing_date']}")
        print("First 5 archived bars of the day:")
        print(bars.head(5).to_string(index=False))
        print(f"status={rec['status']}  is_green={rec.get('is_green')}")
        if rec["status"] == "ENTERED":
            print(f"fill_ts={rec['fill_ts']} entry_price={rec['entry_price']:.4f} qty={rec['qty']} "
                  f"stop={rec['stop']:.4f} target={rec['target']:.4f}")
            print(f"exit_outcome={rec['exit_outcome']} exit_price={rec['exit_price']:.4f} "
                  f"exit_ts={rec['exit_ts']} time_exit_fallback={rec['time_exit_fallback']}")
            print(f"pnl_rs={rec['pnl_rs']:.4f} position_size_rs={rec['position_size_rs']:.2f}")
            print(f"net_r_7bps={rec['net_r_7bps']:.6f} net_r_14bps={rec['net_r_14bps']:.6f} "
                  f"net_r_28bps={rec['net_r_28bps']:.6f}")
            rev2 = icon.execute(
                "SELECT COUNT(*) FROM bars_1min WHERE listing_id = ? AND revision_seq = 2", [int(r["listing_id"])]
            ).fetchone()[0]
            print(f"scale-corrected (revision_seq=2 rows present): {bool(rev2)}")
            if rev2:
                raw_first = icon.execute(
                    "SELECT open, close FROM bars_1min WHERE listing_id = ? AND revision_seq = 1 ORDER BY ts LIMIT 1",
                    [int(r["listing_id"])],
                ).fetchone()
                print(f"  AS-FETCHED (revision_seq=1, Angel-adjusted) first-bar open/close: {raw_first}")
                print(f"  RAW-CORRECTED (revision_seq=2) first-bar open: {bars.iloc[0]['open']:.4f}")

    show("1. TARGET hit", target_ex)
    show("2. STOP hit", stop_ex)
    show("3. 15:15 TIME_EXIT", time_ex)
    show("4. SKIPPED (red/flat first candle)", skip_ex)
    show("5. SCALE-CORRECTED listing", scale_ex)


if __name__ == "__main__":
    main()
