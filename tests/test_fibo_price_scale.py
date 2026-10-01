"""Regression test for src/fibo/price_scale.py, using a real split from the
DEVELOPMENT window: TATASTEEL's (INE081A01012) 2022-07-28 face-value split
(Rs10->Re1, combined ratio 10.0x, confirmed live in the warehouse:
factor(2022-07-27) = 0.1, factor(2022-07-28) = 1.0).

Originally written against BAJFINANCE's 2025-06-16 event -- REPLACED
2026-09-29 because that date falls inside the Fibo module's own sealed
test window (src/fibo/holdout.py, SEALED_TEST_START = 2023-01-01) and must
never be read for any purpose, including a test fixture. TATASTEEL's 2022
split is a real, in-development-window event of the same shape (this
project's own deterministic OWN-factor conversion, data_layer.adjustment --
a different, better-understood layer from src/fibo/scale_probe.py's
separate probe for ANGEL'S OWN archive inconsistency, discovered via this
same TATASTEEL split; see PREREGISTRATION_FIBO.md's revised PRICE SCALE
section and tests/test_fibo_scale_probe.py).

This is exactly the CRITICAL PITFALL the Fibo module's daily-side rules
must not fall into: a golden zone computed from adjusted daily prices
("today's scale") must be converted through the adjustment factor AS OF
the specific trade date before it is compared against that date's raw
intraday bars -- get the date wrong (e.g. use today's factor for a
pre-split date) and the zone is silently misplaced by the split ratio.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from fibo.price_scale import get_adjustment_factor, to_raw_scale, zone_to_raw_scale

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"
TATASTEEL_ENTITY = "INE081A01012"
PRE_SPLIT_DATE = "2022-07-27"   # last trading day before the ex_date
POST_SPLIT_DATE = "2022-07-28"  # the ex_date itself (already post-action, per data_layer.adjustment convention)
COMBINED_RATIO = 10.0           # Face Value Split Rs10->Re1, from corporate_actions


@pytest.fixture(scope="module")
def con():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    return get_connection(WAREHOUSE)


def test_factor_jumps_by_exactly_the_split_ratio_across_the_real_boundary(con):
    factor_before = get_adjustment_factor(con, TATASTEEL_ENTITY, PRE_SPLIT_DATE)
    factor_after = get_adjustment_factor(con, TATASTEEL_ENTITY, POST_SPLIT_DATE)
    assert factor_before == pytest.approx(0.1)
    assert factor_after == pytest.approx(1.0)
    assert factor_after / factor_before == pytest.approx(COMBINED_RATIO)


def test_same_adjusted_level_converts_to_different_raw_prices_either_side_of_the_split(con):
    """The actual bug this module prevents, made concrete: apply the SAME
    adjusted-scale golden-zone level to both sides of a real split. Using
    the wrong date's factor (e.g. always using the post-split factor of
    1.0) would place the pre-split zone at 1/10th its true raw level --
    exactly the kind of silent misplacement described in this module's
    docstring."""
    adjusted_level = 95.94  # TATASTEEL's real adjusted close on 2022-07-27 (959.40 raw x 0.1)

    raw_before = to_raw_scale(adjusted_level, get_adjustment_factor(con, TATASTEEL_ENTITY, PRE_SPLIT_DATE))
    raw_after = to_raw_scale(adjusted_level, get_adjustment_factor(con, TATASTEEL_ENTITY, POST_SPLIT_DATE))

    # raw_before must reproduce the entity's actual raw close that day (959.40) --
    # not an approximation, an exact round-trip through the real materialized factor
    assert raw_before == pytest.approx(959.40, rel=1e-6)
    # raw_after is the SAME adjusted level read as if it were already post-split scale --
    # exactly COMBINED_RATIO times smaller than raw_before
    assert raw_before / raw_after == pytest.approx(COMBINED_RATIO)


def test_zone_to_raw_scale_applies_the_correct_dates_factor_not_todays(con):
    """A realistic golden-zone pair (zone_low < zone_high, both in adjusted
    scale) converted for the PRE-split date must come back ~10x the level
    a caller would get by mistakenly using the post-split (or today's,
    factor=1.0) scale instead."""
    zone_low_adj, zone_high_adj = 92.0, 95.0

    raw_low_correct, raw_high_correct = zone_to_raw_scale(con, TATASTEEL_ENTITY, PRE_SPLIT_DATE, zone_low_adj, zone_high_adj)
    wrong_factor = get_adjustment_factor(con, TATASTEEL_ENTITY, POST_SPLIT_DATE)  # the bug: using the wrong date's factor
    raw_low_wrong = to_raw_scale(zone_low_adj, wrong_factor)

    assert raw_low_correct < raw_high_correct  # ordering preserved
    assert raw_low_correct / raw_low_wrong == pytest.approx(COMBINED_RATIO)


def test_missing_factor_raises_rather_than_silently_defaulting():
    """A date/entity with no materialized factor must raise, never fall
    back to factor=1.0 -- see module docstring on why silent defaulting is
    exactly the prior project's bug class."""
    import duckdb
    empty_con = duckdb.connect(":memory:")
    empty_con.execute("CREATE TABLE adjustment_factors (entity_id VARCHAR, trade_date DATE, factor DOUBLE)")
    with pytest.raises(ValueError):
        get_adjustment_factor(empty_con, "NOPE", "2020-01-01")
