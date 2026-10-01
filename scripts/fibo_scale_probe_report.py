"""Runs src/fibo/scale_probe.py's REVISED (HIGH/LOW-based, factor-table-
independent) per-entity-per-day decision across every (entity, day) pair
with downloaded 1-minute bars in the DEVELOPMENT window
(2016-10-04..2022-12-31) -- never the sealed test window -- and reports the
fraction RAW_EQUIVALENT / SCALED / UNRESOLVED / EX_DATE_SKIP /
GAP_GUARD_SKIP. Also reports the 7 entities the FIRST version of this
report flagged as concentrated UNRESOLVED offenders, before and after, to
confirm the new method actually resolves them.

Vectorized (SQL + pandas), not a 70k-row loop calling decide_scale_for_day
individually -- same reasoning as the first version of this script.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.holdout import guard_date_range, DEV_START, DEV_END, SEALED_TEST_START
from fibo.scale_probe import probe_scale, passes_gap_guard, to_raw_scale, ScaleDecision
from fibo.intraday_db import get_read_connection as get_intraday_read_connection
from data_layer.db import get_read_connection

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

UNRESOLVED_STOP_THRESHOLD = 0.02
FIRST_VERSION_OFFENDERS = {
    "INE148I01020": "IBULHSGFIN/SAMMAANCAP", "INE155A01022": "TATAMOTORS/TMPV",
    "INE205A01025": "VEDL", "INE237A01028": "KOTAKBANK", "INE002A01018": "RELIANCE",
    "INE628A01036": "UPL", "INE397D01024": "BHARTIARTL",
}


def classify(row) -> str:
    if row["is_ex_date"]:
        return ScaleDecision.EX_DATE_SKIP.value
    if pd.isna(row["prev_day"]) or pd.isna(row["angel_high_prev"]) or pd.isna(row["angel_low_prev"]) \
            or pd.isna(row["bhav_high_prev"]) or pd.isna(row["bhav_low_prev"]) or pd.isna(row["angel_open_d"]):
        return ScaleDecision.UNRESOLVED.value
    decision, scale = probe_scale(row["bhav_high_prev"], row["angel_high_prev"], row["bhav_low_prev"], row["angel_low_prev"])
    if decision == ScaleDecision.UNRESOLVED:
        return decision.value
    converted_open = to_raw_scale(row["angel_open_d"], scale)
    if not passes_gap_guard(converted_open, row["bhav_close_prev"]):
        return ScaleDecision.GAP_GUARD_SKIP.value
    return decision.value


def build_classified(entities, downloaded_pairs, warehouse_con, intraday_con):
    placeholders = ", ".join(["?"] * len(entities))

    full_lag = warehouse_con.execute(
        f"""
        SELECT l.entity_id, p.trade_date,
               LAG(p.trade_date) OVER (PARTITION BY l.entity_id ORDER BY p.trade_date) AS prev_day,
               LAG(p.high) OVER (PARTITION BY l.entity_id ORDER BY p.trade_date) AS bhav_high_prev,
               LAG(p.low) OVER (PARTITION BY l.entity_id ORDER BY p.trade_date) AS bhav_low_prev,
               LAG(p.close) OVER (PARTITION BY l.entity_id ORDER BY p.trade_date) AS bhav_close_prev
        FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
        WHERE p.series = 'EQ' AND l.entity_id IN ({placeholders})
        """,
        entities,
    ).fetchdf()
    full_lag["trade_date"] = pd.to_datetime(full_lag["trade_date"]).dt.date
    full_lag["prev_day"] = pd.to_datetime(full_lag["prev_day"]).dt.date

    ex_dates = warehouse_con.execute(
        f"""SELECT l.entity_id, ca.ex_date FROM corporate_actions ca
            JOIN isin_lineage l ON ca.isin = l.isin WHERE l.entity_id IN ({placeholders})""",
        entities,
    ).fetchdf()
    ex_date_set = set(zip(ex_dates["entity_id"], pd.to_datetime(ex_dates["ex_date"]).dt.date))

    angel_daily = intraday_con.execute(
        f"""SELECT entity_id, trade_date, MAX(high) AS a_high, MIN(low) AS a_low
            FROM bars_1min WHERE entity_id IN ({placeholders}) GROUP BY entity_id, trade_date""",
        entities,
    ).fetchdf()
    angel_daily["trade_date"] = pd.to_datetime(angel_daily["trade_date"]).dt.date
    angel_prev = angel_daily.rename(columns={"trade_date": "prev_day", "a_high": "angel_high_prev", "a_low": "angel_low_prev"})

    angel_open = intraday_con.execute(
        f"""
        SELECT entity_id, trade_date, open AS angel_open_d FROM (
            SELECT entity_id, trade_date, open, ROW_NUMBER() OVER (PARTITION BY entity_id, trade_date ORDER BY ts ASC) AS rn
            FROM bars_1min WHERE entity_id IN ({placeholders})
        ) WHERE rn = 1
        """,
        entities,
    ).fetchdf()
    angel_open["trade_date"] = pd.to_datetime(angel_open["trade_date"]).dt.date

    m = downloaded_pairs.merge(full_lag, on=["entity_id", "trade_date"], how="left")
    m = m.merge(angel_prev, on=["entity_id", "prev_day"], how="left")
    m = m.merge(angel_open, on=["entity_id", "trade_date"], how="left")
    m["is_ex_date"] = m.apply(lambda r: (r["entity_id"], r["trade_date"]) in ex_date_set, axis=1)
    m["decision"] = m.apply(classify, axis=1)
    return m


def report(m, label):
    print(f"\n=== {label} ===", flush=True)
    counts = m["decision"].value_counts()
    total = len(m)
    for lab in ["RAW_EQUIVALENT", "SCALED", "UNRESOLVED", "EX_DATE_SKIP", "GAP_GUARD_SKIP"]:
        n = int(counts.get(lab, 0))
        print(f"{lab:15s}: {n:7d}  ({n/total*100:.2f}%)", flush=True)
    print(f"{'TOTAL':15s}: {total:7d}", flush=True)
    return counts.get("UNRESOLVED", 0) / total if total else float("nan")


def main():
    guard_date_range(DEV_START, DEV_END)

    intraday_con = get_intraday_read_connection(INTRADAY_DB)
    warehouse_con = get_read_connection(WAREHOUSE)

    downloaded_pairs = intraday_con.execute(
        "SELECT DISTINCT entity_id, trade_date FROM bars_1min WHERE trade_date < ?", [SEALED_TEST_START]
    ).fetchdf()
    downloaded_pairs["trade_date"] = pd.to_datetime(downloaded_pairs["trade_date"]).dt.date
    entities = downloaded_pairs["entity_id"].unique().tolist()
    print(f"Entities with development-window bars: {len(entities)}", flush=True)
    print(f"(entity, day) pairs actually downloaded: {len(downloaded_pairs)}", flush=True)

    m = build_classified(entities, downloaded_pairs, warehouse_con, intraday_con)
    unresolved_frac = report(m, "Development-window scale-probe report (revised, HIGH/LOW method)")

    print(f"\nGap guard fired (GAP_GUARD_SKIP) on {int((m['decision']=='GAP_GUARD_SKIP').sum())} of {len(m)} "
          f"resolvable pairs ({(m['decision']=='GAP_GUARD_SKIP').mean()*100:.3f}%).", flush=True)

    if unresolved_frac > UNRESOLVED_STOP_THRESHOLD:
        print(f"\nSTOP-WORTHY: UNRESOLVED fraction {unresolved_frac*100:.2f}% exceeds the "
              f"{UNRESOLVED_STOP_THRESHOLD*100:.0f}% threshold.", flush=True)
    else:
        print(f"\nUNRESOLVED fraction {unresolved_frac*100:.2f}% is within the "
              f"{UNRESOLVED_STOP_THRESHOLD*100:.0f}% threshold -- target met.", flush=True)

    print("\n=== The 7 first-version concentrated-UNRESOLVED offenders, before vs after ===", flush=True)
    for eid, name in FIRST_VERSION_OFFENDERS.items():
        sub = m[m["entity_id"] == eid]
        if sub.empty:
            continue
        counts = sub["decision"].value_counts()
        n = len(sub)
        unresolved_n = int(counts.get("UNRESOLVED", 0))
        print(f"{name:20s} ({eid}): n={n:5d}  UNRESOLVED now={unresolved_n:4d} ({unresolved_n/n*100:.2f}%)  "
              f"[{dict(counts)}]", flush=True)

    intraday_con.close()
    warehouse_con.close()


if __name__ == "__main__":
    main()
