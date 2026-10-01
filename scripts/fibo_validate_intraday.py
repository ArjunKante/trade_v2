"""Step 3's validation: aggregate downloaded 1-minute bars to daily OHLC
and compare against bhavcopy, on a SAMPLE of days from the DEVELOPMENT
window ONLY (2016-10-04 .. 2022-12-31) -- the sealed test window
(2023-01-01 onward, src/fibo/holdout.py) is never read here, enforced both
by the SQL filter below and by an explicit guard_date_range call (defense
in depth, same discipline as every other date-bounded read in this
project).

Uses src/fibo/validation.py's compare_daily_to_bhavcopy (already tested on
synthetic data in tests/test_fibo_validation.py) against the REAL data
just downloaded. Pulls exactly the sampled (entity, day) pairs via a
DuckDB JOIN against a registered sample table -- an earlier version of
this script pulled EVERY bar for the sampled entities across their whole
pre-seal history (tens of millions of rows) and filtered in Python with a
row-wise .apply(), which ran out of memory. Filtering in SQL, before
anything reaches pandas, avoids that entirely.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.holdout import guard_date_range, DEV_START, DEV_END, SEALED_TEST_START
from fibo.validation import compare_daily_to_bhavcopy, mismatch_rate
from fibo.intraday_db import get_read_connection as get_intraday_read_connection
from data_layer.db import get_read_connection

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

SAMPLE_SIZE = 500
SEED = 0


def log(msg: str):
    print(msg, flush=True)


def main():
    guard_date_range(DEV_START, DEV_END)  # must not raise -- defense in depth, this range is never sealed

    intraday_con = get_intraday_read_connection(INTRADAY_DB)
    warehouse_con = get_read_connection(WAREHOUSE)

    pairs = intraday_con.execute(
        "SELECT DISTINCT entity_id, trade_date FROM bars_1min WHERE trade_date < ?",
        [SEALED_TEST_START],
    ).fetchdf()
    log(f"Development-window (entity, day) pairs available: {len(pairs)}")

    sample = pairs.sample(n=min(SAMPLE_SIZE, len(pairs)), random_state=SEED).reset_index(drop=True)
    sample["trade_date"] = pd.to_datetime(sample["trade_date"]).dt.date
    log(f"Sampling {len(sample)} (entity, day) pairs for validation.")

    intraday_con.register("sample_pairs", sample)
    bars_1min = intraday_con.execute(
        """
        SELECT b.entity_id, b.trade_date, b.ts, b.open, b.high, b.low, b.close, b.volume
        FROM bars_1min b
        JOIN sample_pairs s ON b.entity_id = s.entity_id AND b.trade_date = s.trade_date
        """
    ).fetchdf()
    intraday_con.unregister("sample_pairs")
    bars_1min["trade_date"] = pd.to_datetime(bars_1min["trade_date"]).dt.date
    log(f"1-minute bars pulled for the sample: {len(bars_1min)}")

    warehouse_con.register("sample_pairs", sample)
    bhavcopy_daily = warehouse_con.execute(
        """
        SELECT l.entity_id, p.trade_date, p.open, p.high, p.low, p.close
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        JOIN sample_pairs s ON l.entity_id = s.entity_id AND p.trade_date = s.trade_date
        WHERE p.series = 'EQ'
        """
    ).fetchdf()
    warehouse_con.unregister("sample_pairs")
    bhavcopy_daily["trade_date"] = pd.to_datetime(bhavcopy_daily["trade_date"]).dt.date
    log(f"Bhavcopy daily rows pulled for the sample: {len(bhavcopy_daily)}")

    comparison = compare_daily_to_bhavcopy(bars_1min, bhavcopy_daily)
    rate = mismatch_rate(comparison)

    log(f"\n(entity, day) pairs actually compared (present in both sources): {len(comparison)}")
    log(f"Mismatch rate: {rate:.4f} ({rate*100:.2f}%)")
    if not comparison.empty:
        for field in ["open_pct_diff", "high_pct_diff", "low_pct_diff", "close_pct_diff"]:
            log(f"  {field}: mean={comparison[field].mean():.4f}%  max={comparison[field].max():.4f}%")
        mismatches = comparison[comparison["mismatch"]]
        if not mismatches.empty:
            log(f"\nWorst {min(10, len(mismatches))} mismatches by close_pct_diff:")
            log(mismatches.sort_values("close_pct_diff", ascending=False).head(10).to_string(index=False))

    intraday_con.close()
    warehouse_con.close()


if __name__ == "__main__":
    main()
