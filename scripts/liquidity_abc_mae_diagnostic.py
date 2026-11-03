"""DIAGNOSTIC on CLOSED Liquidity Studies A, B, C. Not a study, no new
strategy, no gate, no verdict change.

For every trade whose REAL, ACTUAL outcome was a stop-out
(final_exit_kind == 'STOP' -- covers STOP_NO_HALF, HALF_THEN_STOP,
STOP_QTY1), measure what price did afterward if no stop had existed:
maximum adverse excursion (MAE) from the ORIGINAL entry price, tracked
forward 30 trading days, plus whether/when price recovered to the
trade's own 1.5R/3R levels.

Same scale method as scripts/liquidity_abc_horizon_diagnostic.py
(fibo.scale_probe throughout, validated against Study A's own hand-trace
there) extended from 10 to 30 forward trading days, and extended from
"first touch of 5 preset levels" to tracking the full daily high/low
path so MAE can be measured at any horizon cutoff, not just reported at
one.
"""
from __future__ import annotations

import datetime as dt
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from box_theory.universe_data import fetch_bhav_daily, fetch_ex_dates
from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con
from fibo.scale_probe import ScaleDecision, passes_gap_guard, probe_scale

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
CHECKPOINT_PATH = ROOT / "data" / "liquidity" / "mae_diagnostic_checkpoint.pkl"
OUT_PATH = ROOT / "data" / "liquidity" / "mae_diagnostic_trades.pkl"

TRADE_PATHS = {
    "A": ROOT / "data" / "liquidity" / "a" / "dev_backtest.pkl",
    "B": ROOT / "data" / "liquidity" / "b" / "dev_backtest.pkl",
    "C_long": ROOT / "data" / "liquidity" / "c" / "long" / "dev_backtest.pkl",
    "C_short": ROOT / "data" / "liquidity" / "c" / "short" / "dev_backtest.pkl",
}
N_FUTURE_DAYS = 30
DAILY_BUFFER = dt.timedelta(days=55)  # calendar-day buffer to guarantee >=30 trading days


def load_stopped_trades() -> pd.DataFrame:
    frames = []
    for study, path in TRADE_PATHS.items():
        with open(path, "rb") as f:
            df = pickle.load(f)["trades"].copy()
        df = df[df["final_exit_kind"] == "STOP"].copy()
        df["study"] = study
        keep = ["study", "entity_id", "trade_date", "fill_ts", "entry_price", "stop_price",
                "half_target_price", "full_target_price", "final_exit_kind", "outcome"]
        frames.append(df[keep])
    out = pd.concat(frames, ignore_index=True)
    out["direction"] = np.where(out["full_target_price"] > out["entry_price"], "long", "short")
    bad = out[((out["study"].isin(["A", "C_long"])) & (out["direction"] != "long")) |
              ((out["study"].isin(["B", "C_short"])) & (out["direction"] != "short"))]
    if len(bad):
        raise ValueError(f"{len(bad)} trades have direction inconsistent with their study")
    sign = np.where(out["direction"] == "long", 1.0, -1.0)
    out["sign"] = sign
    out["R"] = (out["full_target_price"] - out["entry_price"]).abs() / 3.0
    out["trade_id"] = out.index
    return out.reset_index(drop=True)


def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "rb") as f:
            return pickle.load(f)
    return {"done_entities": set(), "results": []}


def save_checkpoint(state: dict) -> None:
    tmp = CHECKPOINT_PATH.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(state, f)
    tmp.replace(CHECKPOINT_PATH)


def build_scale_map(entity_id, needed_dates, bhav, ex_dates, warehouse_con, intraday_con) -> dict:
    bhav_dates_sorted = list(bhav.index)
    prev_day_of = {}
    for d in needed_dates:
        pos = np.searchsorted(bhav_dates_sorted, d)
        prev_day_of[d] = bhav_dates_sorted[pos - 1] if pos > 0 else None

    prev_days_needed = sorted({p for p in prev_day_of.values() if p is not None})
    all_relevant_dates = sorted(set(needed_dates) | set(prev_days_needed))

    angel_minmax = intraday_con.execute(
        "SELECT trade_date, MAX(high) h, MIN(low) l FROM bars_1min WHERE entity_id = ? AND trade_date = ANY(?) "
        "GROUP BY trade_date",
        [entity_id, all_relevant_dates],
    ).fetchdf()
    angel_minmax["trade_date"] = pd.to_datetime(angel_minmax["trade_date"]).dt.date
    angel_hl = {row.trade_date: (row.h, row.l) for row in angel_minmax.itertuples()}

    angel_open = intraday_con.execute(
        "SELECT trade_date, FIRST(open ORDER BY ts) o FROM bars_1min WHERE entity_id = ? AND trade_date = ANY(?) "
        "GROUP BY trade_date",
        [entity_id, needed_dates],
    ).fetchdf()
    angel_open["trade_date"] = pd.to_datetime(angel_open["trade_date"]).dt.date
    angel_open_map = dict(zip(angel_open["trade_date"], angel_open["o"]))

    scale_map = {}
    for d in needed_dates:
        if d in ex_dates:
            scale_map[d] = None
            continue
        prev_day = prev_day_of.get(d)
        if prev_day is None or prev_day not in bhav.index or prev_day not in angel_hl:
            scale_map[d] = None
            continue
        bhav_high_prev, bhav_low_prev, bhav_close_prev = (
            bhav.loc[prev_day, "high"], bhav.loc[prev_day, "low"], bhav.loc[prev_day, "close"],
        )
        angel_high_prev, angel_low_prev = angel_hl[prev_day]
        decision, scale = probe_scale(bhav_high_prev, angel_high_prev, bhav_low_prev, angel_low_prev)
        if decision == ScaleDecision.UNRESOLVED:
            scale_map[d] = None
            continue
        angel_open_d = angel_open_map.get(d)
        if angel_open_d is None:
            scale_map[d] = None
            continue
        converted_open_d = angel_open_d * scale
        if not passes_gap_guard(converted_open_d, bhav_close_prev):
            scale_map[d] = None
            continue
        scale_map[d] = scale
    return scale_map


def first_touch(level_price, direction, adverse, day0_bars, future_rows):
    """adverse=True means this level is on the losing side (stop-direction);
    adverse=False means the winning side (target-direction). Returns
    (session, when) or (None, None)."""
    if direction == "long":
        cond_intraday = (day0_bars["raw_low"] <= level_price) if adverse else (day0_bars["raw_high"] >= level_price)
    else:
        cond_intraday = (day0_bars["raw_high"] >= level_price) if adverse else (day0_bars["raw_low"] <= level_price)
    hit = day0_bars[cond_intraday]
    if not hit.empty:
        return 0, hit.iloc[0]["ts"]
    for day_idx, (d, high, low) in enumerate(future_rows, start=1):
        if direction == "long":
            touched = (low <= level_price) if adverse else (high >= level_price)
        else:
            touched = (high >= level_price) if adverse else (low <= level_price)
        if touched:
            return day_idx, d
    return None, None


def process_entity(entity_id, sub, warehouse_con, intraday_con) -> list[dict]:
    trade_dates = sorted(sub["trade_date"].unique())
    min_d, max_d = min(trade_dates), max(trade_dates)
    bhav = fetch_bhav_daily(warehouse_con, entity_id, min_d - DAILY_BUFFER, max_d + DAILY_BUFFER)
    bhav_dates = list(bhav.index)
    ex_dates = fetch_ex_dates(warehouse_con, entity_id)

    future_idx_by_entry = {}
    needed_dates_set = set()
    for entry_date in trade_dates:
        future_idx = [d for d in bhav_dates if d > entry_date][:N_FUTURE_DAYS]
        future_idx_by_entry[entry_date] = future_idx
        needed_dates_set.add(entry_date)
        needed_dates_set.update(future_idx)
    needed_dates = sorted(needed_dates_set)

    scale_map = build_scale_map(entity_id, needed_dates, bhav, ex_dates, warehouse_con, intraday_con)
    resolved_dates = [d for d, s in scale_map.items() if s is not None]

    bars = intraday_con.execute(
        "SELECT trade_date, ts, high, low, close FROM bars_1min WHERE entity_id = ? AND trade_date = ANY(?) "
        "ORDER BY ts",
        [entity_id, resolved_dates],
    ).fetchdf()
    bars_by_date: dict = {}
    if not bars.empty:
        bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.date
        for d, grp in bars.groupby("trade_date"):
            scale = scale_map[d]
            g = grp.sort_values("ts").copy()
            g["raw_high"] = g["high"] * scale
            g["raw_low"] = g["low"] * scale
            g["raw_close"] = g["close"] * scale
            bars_by_date[d] = g

    day_high_low = {
        d: (float(g["raw_high"].max()), float(g["raw_low"].min()), float(g.iloc[-1]["raw_close"]))
        for d, g in bars_by_date.items()
    }

    results = []
    for _, row in sub.iterrows():
        entry_date = row["trade_date"]
        fill_ts = row["fill_ts"]
        direction = row["direction"]
        sign = row["sign"]
        entry_price = row["entry_price"]
        day0 = bars_by_date.get(entry_date)
        if day0 is not None:
            day0 = day0[day0["ts"] >= fill_ts]
        no_intraday_data = day0 is None or day0.empty
        day0_arg = day0 if day0 is not None else pd.DataFrame(columns=["raw_high", "raw_low", "ts"])

        future_idx = future_idx_by_entry[entry_date]
        future_rows = []
        n_future_unresolved = 0
        for d in future_idx:
            hl = day_high_low.get(d)
            if hl is None:
                n_future_unresolved += 1
                continue
            future_rows.append((d, hl[0], hl[1]))
        n_future_available = len(future_rows)

        # --- MAE: worst adverse price at or before session k, for k in {10, 30} ---
        def worst_adverse_pct(horizon_days):
            worst = None
            if not day0_arg.empty:
                worst = float(day0_arg["raw_low"].min()) if direction == "long" else float(day0_arg["raw_high"].max())
            for day_idx, (d, high, low) in enumerate(future_rows, start=1):
                if day_idx > horizon_days:
                    break
                val = low if direction == "long" else high
                if worst is None:
                    worst = val
                elif direction == "long":
                    worst = min(worst, val)
                else:
                    worst = max(worst, val)
            if worst is None:
                return None
            if direction == "long":
                return (entry_price - worst) / entry_price * 100.0
            return (worst - entry_price) / entry_price * 100.0

        mae_10 = worst_adverse_pct(10)
        mae_30 = worst_adverse_pct(30)

        levels = {"r1_5": row["half_target_price"], "r3": row["full_target_price"]}
        touch = {}
        for name, price in levels.items():
            session, when = first_touch(price, direction, adverse=False, day0_bars=day0_arg, future_rows=future_rows)
            touch[f"{name}_session"] = session
            touch[f"{name}_when"] = when

        def close_at_horizon(horizon_days):
            sel = [fr for i, fr in enumerate(future_rows, start=1) if i <= horizon_days]
            if not sel:
                return None
            last_date = sel[-1][0]
            return day_high_low.get(last_date, (None, None, None))[2]

        day10_close = close_at_horizon(10)
        day30_close = close_at_horizon(30)
        day10_return = sign * (day10_close - entry_price) / entry_price if day10_close is not None else None
        day30_return = sign * (day30_close - entry_price) / entry_price if day30_close is not None else None

        rec = {
            "trade_id": row["trade_id"], "study": row["study"], "entity_id": entity_id,
            "trade_date": entry_date, "direction": direction, "fill_ts": fill_ts,
            "entry_price": entry_price, "stop_price": row["stop_price"],
            "half_target_price": row["half_target_price"], "full_target_price": row["full_target_price"],
            "n_future_days_available": n_future_available, "n_future_days_unresolved": n_future_unresolved,
            "no_intraday_data": bool(no_intraday_data),
            "mae_pct_10d": mae_10, "mae_pct_30d": mae_30,
            "day10_return": day10_return, "day30_return": day30_return,
        }
        rec.update(touch)
        results.append(rec)
    return results


def main():
    t0 = time.time()
    trades = load_stopped_trades()
    print(f"[{time.time()-t0:.0f}s] loaded {len(trades)} STOPPED-OUT trades across {trades['study'].nunique()} "
          f"studies, {trades['entity_id'].nunique()} distinct entities", flush=True)

    state = load_checkpoint()
    done = state["done_entities"]
    results = state["results"]
    print(f"[{time.time()-t0:.0f}s] resuming: {len(done)} entities already done, {len(results)} trades recorded",
          flush=True)

    entities = sorted(trades["entity_id"].unique())
    remaining = [e for e in entities if e not in done]
    print(f"[{time.time()-t0:.0f}s] {len(remaining)} entities remaining", flush=True)

    warehouse_con = get_warehouse_con(WAREHOUSE_DB)
    intraday_con = get_intraday_con(INTRADAY_DB)

    for i, entity_id in enumerate(remaining):
        sub = trades[trades["entity_id"] == entity_id]
        try:
            recs = process_entity(entity_id, sub, warehouse_con, intraday_con)
        except Exception as e:
            print(f"[{time.time()-t0:.0f}s] ERROR on {entity_id}: {e}", flush=True)
            raise
        results.extend(recs)
        done.add(entity_id)
        if (i + 1) % 10 == 0 or (i + 1) == len(remaining):
            save_checkpoint({"done_entities": done, "results": results})
            print(f"[{time.time()-t0:.0f}s] {i+1}/{len(remaining)} entities, {len(results)} trades total",
                  flush=True)

    save_checkpoint({"done_entities": done, "results": results})
    out_df = pd.DataFrame(results)
    with open(OUT_PATH, "wb") as f:
        pickle.dump(out_df, f)
    print(f"[{time.time()-t0:.0f}s] DONE. wrote {len(out_df)} trade-level records to {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
