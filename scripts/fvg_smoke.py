"""Quick smoke test of the FVG pipeline on a small real-data slice --
NOT the official Process Step 2 hand-trace script (that one picks 5
specific, hand-verified cases and is written separately). This just
checks the plumbing runs end to end without error and produces sane
numbers.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con

from fvg.backtest import run_backtest

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"


def main():
    intraday_con = get_intraday_con(INTRADAY_DB)
    warehouse_con = get_warehouse_con(WAREHOUSE_DB)

    tmp_con = get_intraday_con(INTRADAY_DB)
    entity_ids = [r[0] for r in tmp_con.execute(
        "select distinct entity_id from bars_1min where trade_date between '2017-01-01' and '2017-12-31' limit 15"
    ).fetchall()]
    print("entities:", entity_ids)

    result = run_backtest(intraday_con, warehouse_con, dt.date(2017, 1, 1), dt.date(2017, 6, 30), entity_ids=entity_ids)
    print("total_gaps", result["total_gaps"], "inside_bar_rejected", result["inside_bar_rejected"],
          "overnight_excluded", result["overnight_excluded"])
    print("skips", result["skips"])
    for c in ("A", "B"):
        df = result["trades"][c]
        print(f"--- config {c}: {len(df)} trades ---")
        print("diagnostics", result["diagnostics"][c])
        if not df.empty:
            print(df[["entity_id", "trade_date", "entry_price", "gap_low", "qty", "outcome", "net_r"]].head(10))
    if result["errors"]:
        print("ERRORS:", result["errors"][:10])


if __name__ == "__main__":
    main()
