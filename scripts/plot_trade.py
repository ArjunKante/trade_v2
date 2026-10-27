"""CLI for src/viz/ -- plot one entity-day's 1-minute candles, optionally
with a strategy's own overlay. Usage:

    python scripts/plot_trade.py --entity <id> --date YYYY-MM-DD
        # core chart only, no overlay

    python scripts/plot_trade.py --study poc --entity <id> --date YYYY-MM-DD
        # POC overlay (POC/PREV_HIGH levels, touch/confirm markers, stop/
        # target, entry/exit, text panel) -- works for a REAL TRADE or a
        # SKIPPED setup alike, since the adapter recomputes live

    python scripts/plot_trade.py --study poc --csv <path> --index N
        # looks up entity_id/trade_date from row N of an exported trades
        # CSV (e.g. data/poc/dev_trades.csv), then plots the same way --
        # the CSV is only ever used to find WHICH entity-day to plot, not
        # as the source of the numbers shown (those are always recomputed
        # live, so the chart can never disagree with the adapter's own logic)

Only `--study poc` exists today; `src/viz/` itself has no idea POC
exists -- a future strategy adds its own `src/viz/<study>_adapter.py`
and this script's --study dispatch grows by one line.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con

from viz.chart import plot_trade_chart
from viz.data import fetch_raw_day_bars

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
OUT_DIR = ROOT / "data" / "viz"

ADAPTERS = {}


def _poc_adapter(warehouse_con, intraday_con, entity_id, trade_date):
    from viz.poc_adapter import build_poc_overlay
    return build_poc_overlay(warehouse_con, intraday_con, entity_id, trade_date)


ADAPTERS["poc"] = _poc_adapter


def resolve_entity_date_from_csv(csv_path: Path, index: int) -> tuple[str, dt.date]:
    df = pd.read_csv(csv_path)
    if index < 0 or index >= len(df):
        raise ValueError(f"--index {index} out of range for {csv_path} ({len(df)} rows)")
    row = df.iloc[index]
    entity_id = str(row["entity_id"])
    trade_date = pd.to_datetime(row["trade_date"]).date()
    return entity_id, trade_date


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--study", choices=sorted(ADAPTERS.keys()), default=None,
                         help="which strategy's overlay to apply (omit for a plain core chart)")
    parser.add_argument("--entity", type=str, default=None, help="entity_id, e.g. INE002A01018")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--csv", type=str, default=None, help="path to an exported trades CSV")
    parser.add_argument("--index", type=int, default=None, help="row index into --csv")
    parser.add_argument("--out", type=str, default=None, help="output PNG path (default: data/viz/<auto>.png)")
    parser.add_argument("--window", type=str, default=None,
                         help="zoom to a sub-window of the session, e.g. --window 09:30-10:30 "
                              "(a marker outside the window is dropped, not relocated)")
    args = parser.parse_args()

    window = None
    if args.window:
        try:
            start_s, end_s = args.window.split("-")
            window = (dt.time.fromisoformat(start_s.strip()), dt.time.fromisoformat(end_s.strip()))
        except ValueError:
            parser.error(f"--window must look like HH:MM-HH:MM, got {args.window!r}")

    if args.csv is not None:
        if args.index is None:
            parser.error("--csv requires --index")
        entity_id, trade_date = resolve_entity_date_from_csv(Path(args.csv), args.index)
    else:
        if not args.entity or not args.date:
            parser.error("either --csv/--index, or both --entity and --date, are required")
        entity_id = args.entity
        trade_date = dt.date.fromisoformat(args.date)

    warehouse_con = get_warehouse_con(WAREHOUSE_DB)
    intraday_con = get_intraday_con(INTRADAY_DB)

    overlay = None
    status_note = ""
    bars_source = None

    if args.study:
        adapter = ADAPTERS[args.study]
        result = adapter(warehouse_con, intraday_con, entity_id, trade_date)
        status_note = result["status"]
        print(f"[{args.study}] status={status_note}  detail={result['detail']}")
        if result["bars"] is None:
            print("Nothing to plot -- the adapter could not compute a chart for this entity-day "
                  f"({status_note}: {result['detail']}).")
            return
        bars_source = result["bars"][["ts", "open", "high", "low", "close", "volume"]]
        overlay = result["overlay"]
        scale_label = f"RAW rupee scale (resolved via {args.study} adapter's own Section-3 lookback chain)"
    else:
        res = fetch_raw_day_bars(warehouse_con, intraday_con, entity_id, trade_date)
        bars_source = res["bars"]
        scale_label = res["scale_label"]
        if bars_source.empty:
            print(f"No bars for {entity_id} on {trade_date} -- {scale_label}")
            return

    if args.out:
        out_path = Path(args.out)
    else:
        suffix = f"_{status_note}" if status_note else ""
        out_path = OUT_DIR / f"{entity_id}_{trade_date}{suffix}.png"

    saved = plot_trade_chart(bars_source, entity_id, trade_date, scale_label, overlay=overlay, out_path=out_path,
                              window=window)
    print(f"Saved: {saved}")


if __name__ == "__main__":
    main()
