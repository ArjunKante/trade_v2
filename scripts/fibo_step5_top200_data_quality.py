"""Universe-widening data-quality check, 2026-09-29: for the top-200
universe (existing top-50 PLUS the new 51-200 additions), on the
DEVELOPMENT WINDOW ONLY, report the scale-probe decision breakdown and the
D-1 HIGH/LOW agreement statistics, BY LIQUIDITY RANK BAND (1-50, 51-100,
101-200). Per instruction: this computes DATA QUALITY ONLY -- no strategy
trade, no R, no null is computed here for any entity, so this cannot be a
second look at strategy performance for the new names. If UNRESOLVED
exceeds 2% in any band, this script says so plainly and does not proceed
to any further step on its own.

Bands are assigned per (entity, year) using that year's OWN point-in-time
rank (Section 1) -- an entity's band can differ across years, matching how
the universe itself is annually reconstituted.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.holdout import guard_date_range, DEV_START, DEV_END, SEALED_TEST_START
from fibo.universe import reconstitute_annually
from fibo.scale_probe import probe_scale, passes_gap_guard, to_raw_scale, ScaleDecision
from fibo.intraday_db import get_read_connection as get_intraday_read_connection
from data_layer.db import get_read_connection

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

UNRESOLVED_STOP_THRESHOLD = 0.02
BAND_EDGES = [(1, 50, "1-50"), (51, 100, "51-100"), (101, 200, "101-200")]


def band_for_rank(rank: int) -> str:
    for lo, hi, label in BAND_EDGES:
        if lo <= rank <= hi:
            return label
    return "unranked"


def log(msg):
    print(msg, flush=True)


def classify_row(r):
    if r["is_ex_date"]:
        return ScaleDecision.EX_DATE_SKIP.value, None, None
    needed = ["prev_day", "angel_high_prev", "angel_low_prev", "bhav_high_prev", "bhav_low_prev", "angel_open_d"]
    if any(pd.isna(r[c]) for c in needed):
        return ScaleDecision.UNRESOLVED.value, None, None
    r_high = r["bhav_high_prev"] / r["angel_high_prev"]
    r_low = r["bhav_low_prev"] / r["angel_low_prev"]
    mean_r = (r_high + r_low) / 2.0
    rel_diff = abs(r_high - r_low) / mean_r if mean_r else float("nan")
    decision, scale = probe_scale(r["bhav_high_prev"], r["angel_high_prev"], r["bhav_low_prev"], r["angel_low_prev"])
    if decision == ScaleDecision.UNRESOLVED:
        return decision.value, rel_diff, None
    converted_open = to_raw_scale(r["angel_open_d"], scale)
    if not passes_gap_guard(converted_open, r["bhav_close_prev"]):
        return ScaleDecision.GAP_GUARD_SKIP.value, rel_diff, scale
    return decision.value, rel_diff, scale


def main():
    guard_date_range(DEV_START, DEV_END)

    warehouse_con = get_read_connection(WAREHOUSE)
    intraday_con = get_intraday_read_connection(INTRADAY_DB)

    log("Building rank lookup (top-200 universe, per year)...")
    universe200 = reconstitute_annually(warehouse_con, top_n=200)
    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe200.iterrows()}

    downloaded_pairs = intraday_con.execute(
        "SELECT DISTINCT entity_id, trade_date FROM bars_1min WHERE trade_date < ?", [SEALED_TEST_START]
    ).fetchdf()
    downloaded_pairs["trade_date"] = pd.to_datetime(downloaded_pairs["trade_date"]).dt.date
    entities = downloaded_pairs["entity_id"].unique().tolist()
    log(f"Entities with development-window bars (top-200, all bands): {len(entities)}")
    log(f"(entity, day) pairs: {len(downloaded_pairs)}")

    placeholders = ", ".join(["?"] * len(entities))
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
    m["year"] = m["trade_date"].apply(lambda d: d.year)
    m["rank"] = m.apply(lambda r: rank_lookup.get((r["year"], r["entity_id"])), axis=1)
    m["band"] = m["rank"].apply(lambda r: band_for_rank(r) if pd.notna(r) else "unranked")

    log("Classifying scale for every (entity, day)...")
    classified = m.apply(classify_row, axis=1, result_type="expand")
    m["decision"] = classified[0]
    m["rel_diff"] = classified[1]

    log(f"\n{'unranked (no top-200 membership that year -- should be ~0)':70s}: {(m['band']=='unranked').sum()}")

    log("\n=== Scale-probe breakdown by rank band (development window) ===")
    stop_worthy = False
    for band in ["1-50", "51-100", "101-200"]:
        sub = m[m["band"] == band]
        total = len(sub)
        if total == 0:
            log(f"\nBand {band}: no data")
            continue
        log(f"\nBand {band}: {total} (entity, day) pairs, {sub['entity_id'].nunique()} entities")
        counts = sub["decision"].value_counts()
        for label in ["RAW_EQUIVALENT", "SCALED", "UNRESOLVED", "EX_DATE_SKIP", "GAP_GUARD_SKIP"]:
            n = int(counts.get(label, 0))
            log(f"  {label:15s}: {n:7d}  ({n/total*100:.2f}%)")
        unresolved_frac = counts.get("UNRESOLVED", 0) / total
        rel_diff_valid = sub["rel_diff"].dropna()
        if len(rel_diff_valid):
            log(f"  r_high/r_low relative disagreement: median={rel_diff_valid.median()*100:.4f}%  "
                f"p90={rel_diff_valid.quantile(0.9)*100:.4f}%  p99={rel_diff_valid.quantile(0.99)*100:.4f}%")
        if unresolved_frac > UNRESOLVED_STOP_THRESHOLD:
            log(f"  *** STOP-WORTHY: UNRESOLVED {unresolved_frac*100:.2f}% exceeds {UNRESOLVED_STOP_THRESHOLD*100:.0f}% in band {band} ***")
            stop_worthy = True

    log("\n=== Overall verdict ===")
    if stop_worthy:
        log("STOP: at least one rank band exceeds the 2% UNRESOLVED threshold. Reporting, not proceeding further automatically.")
    else:
        log("All rank bands within the 2% UNRESOLVED threshold.")

    warehouse_con.close()
    intraday_con.close()


if __name__ == "__main__":
    main()
