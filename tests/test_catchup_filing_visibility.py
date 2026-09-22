"""BHARATIDIL filed 28 consecutive quarters (2017-06-30 through 2024-03-31)
on a single day, 2025-11-15, after apparently going dark for years -- the
most extreme real case of the catch-up-filing pattern found in the Phase A
backfill (a separate, smaller dump of 3 more quarters landed on
2025-02-17). A naive TTM sum would treat these 28 periods as if each had
been knowable in its own historical quarter; in reality NONE of them was
knowable before 2025-11-15, and any point-in-time query dated before that
must see none of them.
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.fundamentals_pit import point_in_time_fundamentals

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"

DUMP_DATE = dt.date(2025, 11, 15)
DUMPED_PERIOD_ENDS = [
    dt.date(2017, 6, 30), dt.date(2017, 9, 30), dt.date(2017, 12, 31),
    dt.date(2018, 3, 31), dt.date(2020, 12, 31), dt.date(2022, 6, 30),
    dt.date(2024, 3, 31),  # a representative sample of the 28, not all of them
]


@pytest.fixture(scope="module")
def con():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    return get_read_connection(WAREHOUSE)


def _bharatidil_periods_visible(con, as_of):
    df = point_in_time_fundamentals(con, as_of)
    rows = df[df["symbol"] == "BHARATIDIL"]
    return set(rows["period_end"].dt.date)


def test_none_of_the_dumped_periods_visible_the_day_before_the_dump(con):
    visible = _bharatidil_periods_visible(con, DUMP_DATE - dt.timedelta(days=1))
    for pe in DUMPED_PERIOD_ENDS:
        assert pe not in visible, f"{pe} leaked before the real 2025-11-15 dump date"


def test_all_sampled_dumped_periods_visible_on_the_dump_date(con):
    visible = _bharatidil_periods_visible(con, DUMP_DATE)
    for pe in DUMPED_PERIOD_ENDS:
        assert pe in visible, f"{pe} should be visible on the day it was actually announced"


def test_dumped_periods_share_one_known_date_not_28_distinct_ones(con):
    """The dump is one event, not 28 -- confirm at the data layer, not just
    asserted, that these rows all carry the same known_date."""
    df = point_in_time_fundamentals(con, DUMP_DATE)
    rows = df[(df["symbol"] == "BHARATIDIL") & (df["period_end"].dt.date.isin(DUMPED_PERIOD_ENDS))]
    assert rows["known_date"].dt.date.nunique() == 1
    assert rows["known_date"].dt.date.iloc[0] == DUMP_DATE


def test_ttm_after_the_dump_orders_by_period_end_not_by_filing_order():
    """A TTM sum must select the four periods immediately preceding a target
    date BY THEIR OWN period_end sequence, never by the order rows happened
    to be inserted/filed in -- all 28 of these rows were inserted in the
    same filing-order batch on 2025-11-15, which carries no information
    about which four quarters are chronologically adjacent."""
    con = get_read_connection(WAREHOUSE) if WAREHOUSE.exists() else pytest.skip("real warehouse not present")
    df = point_in_time_fundamentals(con, DUMP_DATE)
    rows = df[df["symbol"] == "BHARATIDIL"].sort_values("period_end")
    period_ends = rows["period_end"].dt.date.tolist()

    target = dt.date(2024, 3, 31)
    trailing_four = [pe for pe in period_ends if pe <= target][-4:]
    assert trailing_four == [dt.date(2023, 6, 30), dt.date(2023, 9, 30),
                              dt.date(2023, 12, 31), dt.date(2024, 3, 31)]
