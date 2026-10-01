"""Cost-model liquidity check by rank band, 2026-09-29 instruction: the flat
6.0-19.0bps round-trip spread/impact range in src/swing/costs.py
(SPREAD_IMPACT_ROUND_TRIP_BPS_LO/HI) was ported from a sibling project's
ground-truth measurement at turnover RANK 300-600 in THAT project's
whole-market universe (src/swing/costs.py's own docstring, section
"SPREAD + MARKET IMPACT"). This project's Fibo universe ranks 1-200 by the
SAME turnover quantity (raw close x volume) but is a different, narrower
population (top-200 only, not whole-market), so rank-for-rank comparison
across the two universes is not directly available in this repo -- no
absolute trade-info turnover figures are stored here to compare against.

What IS available and reported below: Fibo's OWN median turnover by rank
band (1-50 / 51-100 / 101-200), across all reconstituted years. This shows
how much turnover -- and by extension, presumably, real spread -- actually
declines within Fibo's own universe as rank widens. The cost-model
optimism question is then a judgment call stated plainly, not a computed
statistic: flat bps applied to a band with materially lower turnover than
the band the model was tuned for is a directional risk, not a proven
number.

Also computes the EXPECTED test-trade count at top-200, scaled from the
development-window top-50 trade frequency, per instruction ("Record the
expected test trade count at top-200 ... BEFORE the test runs").
"""
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.universe import reconstitute_annually
from fibo.holdout import DEV_START, DEV_END, SEALED_TEST_START
from data_layer.db import get_read_connection
from swing.costs import SPREAD_IMPACT_ROUND_TRIP_BPS_LO, SPREAD_IMPACT_ROUND_TRIP_BPS_HI

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
DEV_RESULTS_PATH = ROOT / "data" / "fibo_step5_dev_results.pkl"

BAND_EDGES = [(1, 50, "1-50"), (51, 100, "51-100"), (101, 200, "101-200")]

import datetime as dt

TEST_START = SEALED_TEST_START
TEST_END = dt.date(2026, 9, 18)


def band_for_rank(rank: int) -> str:
    for lo, hi, label in BAND_EDGES:
        if lo <= rank <= hi:
            return label
    return "unranked"


def log(msg):
    print(msg, flush=True)


def main():
    warehouse_con = get_read_connection(WAREHOUSE)
    universe200 = reconstitute_annually(warehouse_con, top_n=200)
    universe200["band"] = universe200["rank"].apply(band_for_rank)

    log("=== Median daily turnover by rank band (Fibo top-200 universe, all reconstituted years) ===")
    for band in ["1-50", "51-100", "101-200"]:
        sub = universe200[universe200["band"] == band]["median_turnover_prior_year"]
        log(f"Band {band:8s}: n={len(sub):4d}  median={sub.median():,.0f}  "
            f"p10={sub.quantile(0.1):,.0f}  p90={sub.quantile(0.9):,.0f}  (rupees/day)")

    b1 = universe200[universe200["band"] == "1-50"]["median_turnover_prior_year"].median()
    b3 = universe200[universe200["band"] == "101-200"]["median_turnover_prior_year"].median()
    log(f"\nBand 101-200 median turnover is {b3/b1*100:.1f}% of band 1-50's median turnover.")

    log(f"\n=== Cost model assumption in force ===")
    log(f"src/swing/costs.py spread+impact round trip: {SPREAD_IMPACT_ROUND_TRIP_BPS_LO:.1f}-"
        f"{SPREAD_IMPACT_ROUND_TRIP_BPS_HI:.1f}bps, FLAT across all ranks/liquidity, applied UNCHANGED "
        f"to every Fibo band including 101-200.")
    log("This flat range was ground-truth-measured at rank 300-600 in a DIFFERENT (whole-market) "
        "universe -- not this project's own top-200 population. No absolute trade-info turnover "
        "figures are available in this repo to place Fibo's rank 101-200 against that rank 300-600 "
        "benchmark numerically.")
    log(f"OBSERVATION (this project's own data): turnover falls to {b3/b1*100:.1f}% of the top-50 level "
        "by rank 101-200. Real bid-ask spreads and market impact widen as turnover falls -- this is a "
        "structural relationship, not specific to this cost model. Applying the SAME flat bps range to a "
        "band with materially lower turnover than the band the range was tuned for is a directional risk "
        "of UNDERSTATING true cost at rank 101-200, in the opposite direction from costs.py's own claim "
        "(made for the SWING project's more-liquid population) that the flat range is 'probably "
        "conservative.' That conservatism claim does NOT automatically transfer to Fibo's 101-200 band.")
    log("FLAG: this is a judgment call, not a re-measurement -- record as an assumption, not a corrected "
        "number, since no fresh spread measurement was taken for rank 101-200 names this session.")

    log("\n=== Expected test-window trade count at top-200, scaled from development frequency ===")
    with open(DEV_RESULTS_PATH, "rb") as f:
        dev = pickle.load(f)
    n_dev_trades_top50 = len(dev["trades"])
    dev_days = (DEV_END - DEV_START).days
    dev_months = dev_days / 30.44
    test_days = (TEST_END - TEST_START).days
    test_months = test_days / 30.44
    trades_per_month_top50 = n_dev_trades_top50 / dev_months
    log(f"Development window: {DEV_START} .. {DEV_END} ({dev_months:.1f} months), "
        f"{n_dev_trades_top50} trades on top-50 -- {trades_per_month_top50:.3f} trades/month.")
    log(f"Sealed test window: {TEST_START} .. {TEST_END} ({test_months:.1f} months).")

    scale_universe = 200 / 50
    expected_flat_scale = trades_per_month_top50 * scale_universe * test_months
    log(f"\nAssumption A -- FLAT per-name rate: trade rate per name in the 101-200 band equals the "
        f"top-50 rate (i.e. widening the universe 4x scales trade count ~4x). "
        f"Expected test trades = {trades_per_month_top50:.3f}/mo x 4 x {test_months:.1f}mo "
        f"= {expected_flat_scale:.0f}.")
    log("This is almost certainly an OVERESTIMATE: the Alligator-uptrend and 2xATR-swing setup "
        "conditions that gate a TRADE are not turnover-dependent by construction, but names ranked "
        "101-200 have thinner intraday data (more NO_ORB_DATA / EXCLUDED_SCALE removals expected, "
        "per Task 28's data-quality check) and lower per-name signal frequency has not been measured "
        "for this band -- Assumption A is a scaling upper bound, not a calibrated forecast.")

    log(f"\nGiven the TEST PASS bar requires >= 100 trades, and Assumption A alone projects "
        f"~{expected_flat_scale:.0f} (comfortably above 100 even after generous haircuts for "
        f"thinner-band data quality), the universe widening is expected to be sufficient -- but this "
        f"is a projection recorded BEFORE the test runs, not a guarantee.")

    warehouse_con.close()


if __name__ == "__main__":
    main()
