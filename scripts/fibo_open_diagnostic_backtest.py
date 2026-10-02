"""PHASE 1 DIAGNOSTIC -- NOT a test. Runs BOTH entry mechanisms (the frozen
src/fibo breakout entry, and this module's new open entry) over the SAME
(entity, day) pairs, across the FULL available range 2016-10-04 to
2026-09-18. Per FIBO_OPEN.md: this module's rules were decided AFTER seeing
src/fibo's own sealed-test TIMING-null result, so the historical data has
already been seen and no untouched window remains -- there is no dev/test
split here, and no fibo.holdout guard is called (that guard protects a
DIFFERENT, unrelated sealed window for a hypothesis whose rules WERE frozen
before any data was read; this module's rules were not).

MECHANISM: one evaluation pass over every (entity, day) pair with resolved
scale and an active (uptrend AND has_swing) daily signal, mirroring
scripts/fibo_test_backtest.py's SQL/caching pattern exactly (same scale-probe
classification, same signal computation) but over the full range and with
NO universe pre-filter -- every such pair gets BOTH
fibo.backtest.evaluate_entity_day (breakout) and
fibo_open.backtest_open.evaluate_entity_day_open (open) evaluated on the
IDENTICAL (signal_row, scale_decision, scale, factor_d, bars) inputs. Since
both functions compute the SAME ORB and the SAME zone-overlap test from
those identical inputs, SETUP_OFF vs SETUP_ON classification is identical
between the two by construction -- no separate bookkeeping needed to
guarantee "identical stock-days."

Universe membership (top-100 AND top-200, both reconstituted point-in-time,
annual) is looked up and attached to every trade AFTERWARDS, as a tag --
not as a pre-filter -- so the top-100 headline result and the "what did
excluding band 101-200 cost us" report can both be read off one evaluation
pass without running it twice.
"""
import sys
import pickle
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.universe import reconstitute_annually
from fibo.daily_ohlc import build_daily_ohlc_panel
from fibo.signals import compute_daily_signals
from fibo.scale_probe import probe_scale, passes_gap_guard, to_raw_scale as scale_to_raw, ScaleDecision
from fibo.backtest import evaluate_entity_day
from fibo.intraday_db import get_read_connection as get_intraday_read_connection
from data_layer.db import get_read_connection
from fibo_open.backtest_open import evaluate_entity_day_open

import datetime as dt

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
RESULTS_PATH = ROOT / "data" / "fibo_open_diagnostic_results.pkl"

RANGE_START = dt.date(2016, 10, 4)
RANGE_END = dt.date(2026, 9, 18)
TOP_N_HEADLINE = 100
TOP_N_WIDE = 200


def log(msg):
    print(msg, flush=True)


def classify_scale_row(r):
    if r["is_ex_date"]:
        return ScaleDecision.EX_DATE_SKIP, None
    needed = ["prev_day", "angel_high_prev", "angel_low_prev", "bhav_high_prev", "bhav_low_prev", "angel_open_d"]
    if any(pd.isna(r[c]) for c in needed):
        return ScaleDecision.UNRESOLVED, None
    decision, scale = probe_scale(r["bhav_high_prev"], r["angel_high_prev"], r["bhav_low_prev"], r["angel_low_prev"])
    if decision == ScaleDecision.UNRESOLVED:
        return decision, None
    converted_open = scale_to_raw(r["angel_open_d"], scale)
    if not passes_gap_guard(converted_open, r["bhav_close_prev"]):
        return ScaleDecision.GAP_GUARD_SKIP, scale
    return decision, scale


BAND_EDGES = [(1, 50, "1-50"), (51, 100, "51-100"), (101, 200, "101-200")]


def band_for_rank(rank100_lookup, rank200_lookup, entity_id, year) -> str:
    """Fine band by actual rank (1-50/51-100/101-200), not just top100
    membership -- needed downstream for the pessimistic banded cost
    scenario's per-band multiplier (fibo_test_backtest.py's convention)."""
    rank = rank100_lookup.get((year, entity_id))
    if rank is None:
        rank = rank200_lookup.get((year, entity_id))
    if rank is None:
        return "unranked"
    rank = int(rank)
    for lo, hi, label in BAND_EDGES:
        if lo <= rank <= hi:
            return label
    return "unranked"


def main():
    log("=== PHASE 1 DIAGNOSTIC -- data already seen, NOT a validated result ===")
    log(f"Range: {RANGE_START} to {RANGE_END} (full available history, no dev/test split)")

    warehouse_con = get_read_connection(WAREHOUSE)
    intraday_con = get_intraday_read_connection(INTRADAY_DB)

    universe100 = reconstitute_annually(warehouse_con, top_n=TOP_N_HEADLINE)
    universe200 = reconstitute_annually(warehouse_con, top_n=TOP_N_WIDE)
    rank100_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe100.iterrows()}
    rank200_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe200.iterrows()}

    downloaded_pairs = intraday_con.execute(
        "SELECT DISTINCT entity_id, trade_date FROM bars_1min WHERE trade_date >= ? AND trade_date <= ?",
        [RANGE_START, RANGE_END],
    ).fetchdf()
    downloaded_pairs["trade_date"] = pd.to_datetime(downloaded_pairs["trade_date"]).dt.date
    entities = downloaded_pairs["entity_id"].unique().tolist()
    log(f"Entities with any downloaded bars in range: {len(entities)}, (entity,day) pairs: {len(downloaded_pairs)}")

    placeholders = ", ".join(["?"] * len(entities))

    log("Building scale-probe inputs (D-1 high/low/close, ex-dates, D's open)...")
    full_lag = warehouse_con.execute(
        f"""SELECT l.entity_id, p.trade_date,
                   LAG(p.trade_date) OVER (PARTITION BY l.entity_id ORDER BY p.trade_date) AS prev_day,
                   LAG(p.high) OVER (PARTITION BY l.entity_id ORDER BY p.trade_date) AS bhav_high_prev,
                   LAG(p.low) OVER (PARTITION BY l.entity_id ORDER BY p.trade_date) AS bhav_low_prev,
                   LAG(p.close) OVER (PARTITION BY l.entity_id ORDER BY p.trade_date) AS bhav_close_prev
            FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
            WHERE p.series = 'EQ' AND l.entity_id IN ({placeholders})""",
        entities,
    ).fetchdf()
    full_lag["trade_date"] = pd.to_datetime(full_lag["trade_date"]).dt.date
    full_lag["prev_day"] = pd.to_datetime(full_lag["prev_day"]).dt.date

    ex_dates_df = warehouse_con.execute(
        f"""SELECT l.entity_id, ca.ex_date FROM corporate_actions ca JOIN isin_lineage l ON ca.isin = l.isin
            WHERE l.entity_id IN ({placeholders})""",
        entities,
    ).fetchdf()
    ex_date_set = set(zip(ex_dates_df["entity_id"], pd.to_datetime(ex_dates_df["ex_date"]).dt.date))

    angel_daily = intraday_con.execute(
        f"""SELECT entity_id, trade_date, MAX(high) AS a_high, MIN(low) AS a_low
            FROM bars_1min WHERE entity_id IN ({placeholders}) GROUP BY entity_id, trade_date""",
        entities,
    ).fetchdf()
    angel_daily["trade_date"] = pd.to_datetime(angel_daily["trade_date"]).dt.date
    angel_prev = angel_daily.rename(columns={"trade_date": "prev_day", "a_high": "angel_high_prev", "a_low": "angel_low_prev"})

    angel_open = intraday_con.execute(
        f"""SELECT entity_id, trade_date, open AS angel_open_d FROM (
                SELECT entity_id, trade_date, open, ROW_NUMBER() OVER (PARTITION BY entity_id, trade_date ORDER BY ts ASC) AS rn
                FROM bars_1min WHERE entity_id IN ({placeholders})
            ) WHERE rn = 1""",
        entities,
    ).fetchdf()
    angel_open["trade_date"] = pd.to_datetime(angel_open["trade_date"]).dt.date

    m = downloaded_pairs.merge(full_lag, on=["entity_id", "trade_date"], how="left")
    m = m.merge(angel_prev, on=["entity_id", "prev_day"], how="left")
    m = m.merge(angel_open, on=["entity_id", "trade_date"], how="left")
    m["is_ex_date"] = m.apply(lambda r: (r["entity_id"], r["trade_date"]) in ex_date_set, axis=1)

    log("Classifying scale for every (entity, day)...")
    decisions_scales = m.apply(classify_scale_row, axis=1)
    m["scale_decision"] = [d for d, s in decisions_scales]
    m["scale"] = [s for d, s in decisions_scales]

    factors = warehouse_con.execute(
        f"SELECT entity_id, trade_date, factor FROM adjustment_factors WHERE entity_id IN ({placeholders})",
        entities,
    ).fetchdf()
    factors["trade_date"] = pd.to_datetime(factors["trade_date"]).dt.date
    m = m.merge(factors, on=["entity_id", "trade_date"], how="left")

    log("Computing daily signals (Alligator uptrend + swing + golden zone) per entity...")
    signal_frames = []
    for i, eid in enumerate(entities):
        panel = build_daily_ohlc_panel(warehouse_con, entity_ids=[eid])
        panel = panel[panel["trade_date"] <= pd.Timestamp(RANGE_END)]  # defense in depth
        if panel.empty:
            continue
        signal_frames.append(compute_daily_signals(panel))
        if (i + 1) % 50 == 0:
            log(f"  signals: {i + 1}/{len(entities)} entities done")
    signals_all = pd.concat(signal_frames, ignore_index=True)
    signals_all["trade_date"] = pd.to_datetime(signals_all["trade_date"]).dt.date
    log(f"Signals computed: {len(signals_all)} rows across {len(entities)} entities.")

    m = m.merge(signals_all, on=["entity_id", "trade_date"], how="left")

    needs_intraday_mask = (
        m["scale_decision"].isin([ScaleDecision.RAW_EQUIVALENT, ScaleDecision.SCALED])
        & (m["uptrend"] == True) & (m["has_swing"] == True)  # noqa: E712
    )
    needs_intraday = m[needs_intraday_mask]
    log(f"(entity, day) pairs needing full intraday evaluation: {len(needs_intraday)} of {len(m)}")

    log("Evaluating every (entity, day) under BOTH entry mechanisms "
        "(bars fetched and discarded one entity at a time -- the full-range, "
        "no-universe-filter pass needs ~47M intraday rows; a single combined "
        "cache for all 386 entities at once is what OOM'd the first run)...")
    needs_intraday_days_by_entity = {
        eid: sorted(set(grp["trade_date"])) for eid, grp in needs_intraday.groupby("entity_id")
    }
    trades_breakout, trades_open = [], []
    setup_off_rows = []
    cat_counts_breakout, cat_counts_open = {}, {}
    n_entities_done = 0
    for eid, grp in m.groupby("entity_id"):
        days_needed = needs_intraday_days_by_entity.get(eid)
        day_bars_by_date = {}
        if days_needed:
            days_list = ", ".join(f"'{d}'" for d in days_needed)
            bars = intraday_con.execute(
                f"""SELECT entity_id, trade_date, ts, open, high, low, close, volume
                    FROM bars_1min WHERE entity_id = ? AND trade_date IN ({days_list})""",
                [eid],
            ).fetchdf()
            bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.date
            for d, day_bars in bars.groupby("trade_date"):
                day_bars_by_date[d] = day_bars.reset_index(drop=True)
            del bars

        for _, row in grp.iterrows():
            decision = row["scale_decision"]
            if decision not in (ScaleDecision.RAW_EQUIVALENT, ScaleDecision.SCALED):
                cat_b = cat_o = "EXCLUDED_SCALE"
            elif not row["uptrend"] or not row["has_swing"]:
                cat_b = cat_o = "NO_SIGNAL"
            else:
                bars_for_day = day_bars_by_date.get(row["trade_date"])
                signal_row = {
                    "uptrend": row["uptrend"], "has_swing": row["has_swing"],
                    "zone_low": row["zone_low"], "zone_high": row["zone_high"],
                    "swing_high_price": row["swing_high_price"],
                }
                result_b = evaluate_entity_day(
                    row["entity_id"], row["trade_date"], signal_row, decision, row["scale"], row["factor"], bars_for_day,
                )
                result_o = evaluate_entity_day_open(
                    row["entity_id"], row["trade_date"], signal_row, decision, row["scale"], row["factor"], bars_for_day,
                )
                cat_b, cat_o = result_b["category"], result_o["category"]
                if cat_b == "TRADE":
                    trades_breakout.append(result_b["trade"])
                elif cat_b == "SETUP_OFF":
                    setup_off_rows.append((row["entity_id"], row["trade_date"]))
                if cat_o == "TRADE":
                    trades_open.append(result_o["trade"])
            cat_counts_breakout[cat_b] = cat_counts_breakout.get(cat_b, 0) + 1
            cat_counts_open[cat_o] = cat_counts_open.get(cat_o, 0) + 1

        del day_bars_by_date
        n_entities_done += 1
        if n_entities_done % 50 == 0:
            log(f"  evaluated: {n_entities_done}/{len(entities)} entities done")

    log("\n=== Category breakdown -- BREAKOUT entry (full range, all downloaded entity-days) ===")
    total = len(m)
    for cat, n in sorted(cat_counts_breakout.items(), key=lambda x: -x[1]):
        log(f"{cat:25s}: {n:6d}  ({n / total * 100:.2f}%)")
    log("\n=== Category breakdown -- OPEN entry (full range, all downloaded entity-days) ===")
    for cat, n in sorted(cat_counts_open.items(), key=lambda x: -x[1]):
        log(f"{cat:25s}: {n:6d}  ({n / total * 100:.2f}%)")

    def tag_bands(trades_list):
        df = pd.DataFrame(trades_list)
        if df.empty:
            return df
        df["year"] = df["trade_date"].apply(lambda d: d.year)
        df["band"] = df.apply(lambda r: band_for_rank(rank100_lookup, rank200_lookup, r["entity_id"], r["year"]), axis=1)
        return df

    trades_breakout_df = tag_bands(trades_breakout)
    trades_open_df = tag_bands(trades_open)

    log(f"\nTotal BREAKOUT trades (any band): {len(trades_breakout_df)}")
    log(f"Total OPEN trades (any band): {len(trades_open_df)}")
    if len(trades_breakout_df) > 0:
        log("BREAKOUT trades by band: " + str(trades_breakout_df["band"].value_counts().to_dict()))
    if len(trades_open_df) > 0:
        log("OPEN trades by band: " + str(trades_open_df["band"].value_counts().to_dict()))

    with open(RESULTS_PATH, "wb") as f:
        pickle.dump({
            "trades_breakout": trades_breakout_df,
            "trades_open": trades_open_df,
            "cat_counts_breakout": cat_counts_breakout,
            "cat_counts_open": cat_counts_open,
            "setup_off": setup_off_rows,
            "m": m[["entity_id", "trade_date", "scale_decision", "scale", "uptrend", "has_swing"]],
            "universe100": universe100,
            "universe200": universe200,
        }, f)
    log(f"\nSaved results to {RESULTS_PATH}")

    warehouse_con.close()
    intraday_con.close()


if __name__ == "__main__":
    main()
