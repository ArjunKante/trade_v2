"""A 252-trading-day lookback computed shortly after an ISIN change must use
the entity's full pre-change history, not truncate at the change. This is
the concrete consequence of the lineage+adjustment layers existing: without
them, BAJFINANCE's 252-day momentum computed anytime in 2017 would see only
~190 trading days of history (back to the 2016-09-09 ISIN change) instead of
the true continuous series reaching back to 2016-01-01.
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.entity_features import trailing_return

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"


@pytest.fixture(scope="module")
def con():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    return get_connection(WAREHOUSE)


def test_252d_window_shortly_after_2016_transition_spans_both_isins(con):
    # ~230 trading days after the 2016-09-09 transition; a 252-day lookback
    # from here must reach back before it, into INE296A01016's own history.
    result = trailing_return(con, "INE296A01016", as_of=dt.date(2017, 8, 1), lookback_days=252)
    assert result["return"] is not None
    assert result["window_start"] < pd.Timestamp(2016, 9, 9)
    assert result["n_isins_in_window"] >= 2  # genuinely spans the ISIN boundary, not a same-ISIN coincidence


def test_252d_window_return_is_not_a_fabricated_split_crash(con):
    """If this read were NOT entity-aware (bare-ISIN, no lineage), a window
    crossing 2025-06-16 would show a fabricated ~-90% return. Confirm the
    entity-aware version does not."""
    result = trailing_return(con, "INE296A01016", as_of=dt.date(2025, 7, 1), lookback_days=252)
    assert result["return"] is not None
    assert result["return"] > -0.5  # a real 252d return, not a fabricated near-total wipeout
    assert result["n_isins_in_window"] >= 2
