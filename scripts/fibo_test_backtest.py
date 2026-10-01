"""THE SEALED TEST. One authorized read of 2023-01-01..2026-09-18, top-200
universe, frozen rules (PREREGISTRATION_FIBO.md Section 3), per the explicit
approval and additions frozen in Section 5b BEFORE this script was run.

Mirrors scripts/fibo_step5_backtest.py exactly in mechanism (same signal
computation, same evaluate_entity_day engine, same scale-probe pipeline) --
the only differences are: universe = top-200 (not top-50), date range = the
sealed test window with authorize_holdout=True (the ONE authorized call),
and this script additionally tags every trade with its rank band and
computes the Section 5b PESSIMISTIC banded cost scenario (scenarios (i) and
(ii) are already present as net_r_lo_cost/net_r_hi_cost from
evaluate_entity_day -- no new computation needed for those two).

NO RULE is touched. This is the same code path as development, pointed at
the sealed window for the first and only time.
"""
import sys
import pickle
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.holdout import guard_date_range, SEALED_TEST_START
from fibo.universe import reconstitute_annually
from fibo.daily_ohlc import build_daily_ohlc_panel
from fibo.signals import compute_daily_signals
from fibo.scale_probe import probe_scale, passes_gap_guard, to_raw_scale as scale_to_raw, ScaleDecision
from fibo.backtest import evaluate_entity_day
from fibo.intraday_db import get_read_connection as get_intraday_read_connection
from data_layer.db import get_read_connection
from swing.costs import buy_leg_cost_rs, sell_leg_cost_rs, SPREAD_IMPACT_ROUND_TRIP_BPS_HI

import datetime as dt

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"
RESULTS_PATH = ROOT / "data" / "fibo_test_results.pkl"

TEST_END = dt.date(2026, 9, 18)
TOP_N = 200

BAND_EDGES = [(1, 50, "1-50"), (51, 100, "51-100"), (101, 200, "101-200")]
BAND_MULTIPLIER = {"1-50": 1, "51-100": 2, "101-200": 4}


def band_for_rank(rank) -> str:
    if pd.isna(rank):
        return "unranked"
    rank = int(rank)
    for lo, hi, label in BAND_EDGES:
        if lo <= rank <= hi:
            return label
    return "unranked"


def pessimistic_cost_rs(position_size_rs: float, band: str) -> float:
    fixed = buy_leg_cost_rs(position_size_rs, "INTRADAY") + sell_leg_cost_rs(position_size_rs, "INTRADAY")
    mult = BAND_MULTIPLIER.get(band, 4)  # unranked (stub-year names) treated as worst case
    spread = position_size_rs * SPREAD_IMPACT_ROUND_TRIP_BPS_HI / 10_000 * mult
    return fixed + spread


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


def main():
    log("=== THE SEALED TEST -- ONE AUTHORIZED READ, 2023-01-01 to 2026-09-18, top-200 universe ===")
    guard_date_range(SEALED_TEST_START, TEST_END, authorize_holdout=True)  # the one authorized call

    warehouse_con = get_read_connection(WAREHOUSE)
    intraday_con = get_intraday_read_connection(INTRADAY_DB)

    universe = reconstitute_annually(warehouse_con, top_n=TOP_N)
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}

    downloaded_pairs = intraday_con.execute(
        "SELECT DISTINCT entity_id, trade_date FROM bars_1min WHERE trade_date >= ? AND trade_date <= ?",
        [SEALED_TEST_START, TEST_END],
    ).fetchdf()
    downloaded_pairs["trade_date"] = pd.to_datetime(downloaded_pairs["trade_date"]).dt.date
    entities = downloaded_pairs["entity_id"].unique().tolist()
    log(f"Entities: {len(entities)}, (entity,day) pairs: {len(downloaded_pairs)}")

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
        panel = panel[panel["trade_date"] <= pd.Timestamp(TEST_END)]  # defense in depth: never beyond test end
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

    log("Fetching 1-minute bars for exactly those pairs...")
    bars_cache = {}
    for eid, grp in needs_intraday.groupby("entity_id"):
        days = grp["trade_date"].tolist()
        days_list = ", ".join(f"'{d}'" for d in days)
        bars = intraday_con.execute(
            f"""SELECT entity_id, trade_date, ts, open, high, low, close, volume
                FROM bars_1min WHERE entity_id = ? AND trade_date IN ({days_list})""",
            [eid],
        ).fetchdf()
        bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.date
        for d, day_bars in bars.groupby("trade_date"):
            bars_cache[(eid, d)] = day_bars.reset_index(drop=True)
    log(f"Bars cached for {len(bars_cache)} (entity, day) pairs.")

    log("Evaluating every (entity, day)...")
    trades = []
    setup_off_rows, setup_on_no_trigger_rows = [], []
    category_counts = {}
    for _, row in m.iterrows():
        decision = row["scale_decision"]
        if decision not in (ScaleDecision.RAW_EQUIVALENT, ScaleDecision.SCALED):
            cat = "EXCLUDED_SCALE"
        elif not row["uptrend"] or not row["has_swing"]:
            cat = "NO_SIGNAL"
        else:
            bars = bars_cache.get((row["entity_id"], row["trade_date"]))
            signal_row = {
                "uptrend": row["uptrend"], "has_swing": row["has_swing"],
                "zone_low": row["zone_low"], "zone_high": row["zone_high"],
                "swing_high_price": row["swing_high_price"],
            }
            result = evaluate_entity_day(
                row["entity_id"], row["trade_date"], signal_row, decision, row["scale"], row["factor"], bars,
            )
            cat = result["category"]
            if cat == "TRADE":
                trades.append(result["trade"])
            elif cat == "SETUP_OFF":
                setup_off_rows.append((row["entity_id"], row["trade_date"]))
            elif cat == "SETUP_ON_NO_TRIGGER":
                setup_on_no_trigger_rows.append((row["entity_id"], row["trade_date"]))
        category_counts[cat] = category_counts.get(cat, 0) + 1

    log("\n=== Category breakdown (sealed test window, all downloaded entity-days) ===")
    total = len(m)
    for cat, n in sorted(category_counts.items(), key=lambda x: -x[1]):
        log(f"{cat:25s}: {n:6d}  ({n / total * 100:.2f}%)")
    log(f"{'TOTAL':25s}: {total:6d}")

    trades_df = pd.DataFrame(trades)
    log(f"\nTotal trades: {len(trades_df)}")

    if len(trades_df) > 0:
        trades_df["year"] = trades_df["trade_date"].apply(lambda d: d.year)
        trades_df["rank"] = trades_df.apply(lambda r: rank_lookup.get((r["year"], r["entity_id"])), axis=1)
        trades_df["band"] = trades_df["rank"].apply(band_for_rank)
        trades_df["cost_pessimistic_rs"] = trades_df.apply(
            lambda r: pessimistic_cost_rs(r["position_size_rs"], r["band"]), axis=1
        )
        trades_df["cost_pessimistic_r"] = trades_df["cost_pessimistic_rs"] / (trades_df["r_rupees"] * trades_df["qty"])
        trades_df["net_r_pessimistic"] = trades_df["gross_r"] - trades_df["cost_pessimistic_r"]

        log("\n=== Band breakdown (trade count) ===")
        for band, grp in trades_df.groupby("band"):
            log(f"  {band:10s}: {len(grp)} trades")

    with open(RESULTS_PATH, "wb") as f:
        pickle.dump({
            "trades": trades_df,
            "category_counts": category_counts,
            "setup_on_no_trigger": setup_on_no_trigger_rows,
            "setup_off": setup_off_rows,
            "m": m[["entity_id", "trade_date", "scale_decision", "scale", "uptrend", "has_swing"]],
            "universe": universe,
        }, f)
    log(f"\nSaved results to {RESULTS_PATH}")

    warehouse_con.close()
    intraday_con.close()


if __name__ == "__main__":
    main()
