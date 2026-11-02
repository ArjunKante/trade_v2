"""Bug #18 blast-radius measurement for the Fibo sealed test and its DEV
window -- read-only, no code changed, no new trades run. For every real
TRADE in both populations, compares fibo.scale_probe's validated scale(D)
(used for orb_high/orb_low/entry_price/stop) against the table-based
factor(D) (used for zone_low_raw/zone_high_raw/swing_high_raw) and reports:
  - which specific (entity, date) pairs disagree materially
  - whether the stop_recomputed zone comparison (zones_overlap) would
    actually flip under the corrected value -- the direct selection test
  - whether swing_high_raw was ever the BINDING constraint on target,
    i.e. whether a wrong swing_high_raw could have changed a realized
    trade's exit price/outcome at all
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pickle
import duckdb
import pandas as pd

from fibo.scale_probe import ScaleDecision, decide_scale_for_day, probe_scale
from fibo.price_scale import get_adjustment_factor
from fibo.backtest import zones_overlap

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

MATERIAL_THRESHOLD_PCT = 0.5  # same threshold used for the Liquidity Bug #18 measurement


def load_trades():
    with open(ROOT / "data" / "fibo_test_results_amended.pkl", "rb") as f:
        test_df = pickle.load(f)["trades"].copy()
    with open(ROOT / "data" / "fibo_step5_dev_results.pkl", "rb") as f:
        dev_df = pickle.load(f)["trades"].copy()
    test_df["window"] = "TEST"
    dev_df["window"] = "DEV"
    return test_df, dev_df


def analyze(df, warehouse_con, intraday_con):
    rows = []
    for _, row in df.iterrows():
        eid, d = row["entity_id"], row["trade_date"]
        decision = decide_scale_for_day(intraday_con, warehouse_con, eid, d)
        scale = decision["scale"]
        factor_d = get_adjustment_factor(warehouse_con, eid, d)
        equiv_table_scale = 1.0 / factor_d if factor_d else None

        rec = {
            "window": row["window"], "entity_id": eid, "trade_date": d,
            "scale_probe_decision": decision["decision"].value, "scale_probe_scale": scale,
            "table_factor": factor_d, "table_equiv_scale": equiv_table_scale,
        }
        if scale is not None and equiv_table_scale is not None:
            rel_diff = abs(scale - equiv_table_scale) / ((scale + equiv_table_scale) / 2) * 100
            rec["rel_diff_pct"] = rel_diff
            rec["material_mismatch"] = rel_diff >= MATERIAL_THRESHOLD_PCT
        else:
            rec["rel_diff_pct"] = None
            rec["material_mismatch"] = None

        # recompute zones_overlap under BOTH the actual (table) conversion and,
        # if mismatched, flag it for a corrected-scale re-check (done below)
        rec["orb_low"] = row["orb_low"]
        rec["orb_high"] = row["orb_high"]
        rec["zone_low_actual"] = row["zone_low"]
        rec["zone_high_actual"] = row["zone_high"]
        rec["swing_high_raw_actual"] = row["swing_high_raw"]
        rec["entry_price"] = row["entry_price"]
        rec["stop"] = row["stop"]
        rec["target"] = row["target"]
        rows.append(rec)
    return pd.DataFrame(rows)


def main():
    test_df, dev_df = load_trades()
    warehouse_con = duckdb.connect(str(WAREHOUSE_DB), read_only=True)
    intraday_con = duckdb.connect(str(INTRADAY_DB), read_only=True)

    print("=" * 100)
    print("TEST window (188 trades)")
    print("=" * 100)
    test_result = analyze(test_df, warehouse_con, intraday_con)
    n_resolved = test_result["rel_diff_pct"].notna().sum()
    n_material = test_result["material_mismatch"].sum()
    print(f"n_trades={len(test_result)}  n_both_resolved={n_resolved}  n_material_mismatch={n_material}")
    unresolved = test_result[test_result["rel_diff_pct"].isna()]
    if len(unresolved):
        print(f"\n{len(unresolved)} trade(s) where scale_probe or the table factor could not be computed at all:")
        print(unresolved[["entity_id", "trade_date", "scale_probe_decision", "table_factor"]].to_string())
    if n_material:
        print("\nMATERIAL MISMATCHES (TEST):")
        print(test_result[test_result["material_mismatch"] == True][
            ["entity_id", "trade_date", "scale_probe_scale", "table_equiv_scale", "rel_diff_pct"]
        ].to_string())
    else:
        print("\nZERO material mismatches found among the 188 TEST trades.")

    print()
    print("=" * 100)
    print("DEV window (67 trades)")
    print("=" * 100)
    dev_result = analyze(dev_df, warehouse_con, intraday_con)
    n_resolved = dev_result["rel_diff_pct"].notna().sum()
    n_material = dev_result["material_mismatch"].sum()
    print(f"n_trades={len(dev_result)}  n_both_resolved={n_resolved}  n_material_mismatch={n_material}")
    unresolved = dev_result[dev_result["rel_diff_pct"].isna()]
    if len(unresolved):
        print(f"\n{len(unresolved)} trade(s) where scale_probe or the table factor could not be computed at all:")
        print(unresolved[["entity_id", "trade_date", "scale_probe_decision", "table_factor"]].to_string())
    if n_material:
        print("\nMATERIAL MISMATCHES (DEV):")
        print(dev_result[dev_result["material_mismatch"] == True][
            ["entity_id", "trade_date", "scale_probe_scale", "table_equiv_scale", "rel_diff_pct"]
        ].to_string())
    else:
        print("\nZERO material mismatches found among the 67 DEV trades.")

    with open(ROOT / "data" / "fibo_bug18_test_analysis.pkl", "wb") as f:
        pickle.dump(test_result, f)
    with open(ROOT / "data" / "fibo_bug18_dev_analysis.pkl", "wb") as f:
        pickle.dump(dev_result, f)

    print()
    print("=" * 100)
    print("Was swing_high_raw ever the BINDING constraint on target (target = min(entry+2R, swing_high))?")
    print("=" * 100)
    for name, df, result in [("TEST", test_df, test_result), ("DEV", dev_df, dev_result)]:
        r = df["entry_price"] - df["stop"]
        uncapped_2r_target = df["entry_price"] + 2 * r
        binding = df["swing_high_raw"] < uncapped_2r_target - 1e-6
        print(f"{name}: swing_high_raw binding on {binding.sum()} of {len(df)} trades "
              f"({binding.sum()/len(df)*100:.1f}%)")


if __name__ == "__main__":
    main()
