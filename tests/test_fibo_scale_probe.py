"""Regression tests for src/fibo/scale_probe.py -- the per-entity-per-day
Angel-archive scale detector, REVISED 2026-09-29 to measure scale directly
from D-1's HIGH/LOW in both sources rather than deriving it from this
project's own adjustment_factors table.

Four real development-window cases, never BAJFINANCE's 2025-06-16 event
(sealed test window):
  - BPCL (INE029A01011): a real bonus history, scale ~2.0 (SCALED).
  - TATASTEEL (INE081A01012): a real 2022-07-28 split, scale ~1.0
    (RAW_EQUIVALENT) the day before its own ex-date.
  - KOTAKBANK (INE237A01028): UNRESOLVED under the FIRST version of this
    module (its 2015 ING Vysya Bank merger predates this project's
    corporate_actions coverage, ex_date >= 2016-01-05) -- the new,
    factor-table-independent method resolves it cleanly: scale = EXACTLY
    5.0, measured directly from D-1's real high/low, no lookup needed.
  - RELIANCE (INE002A01018): also UNRESOLVED under the first version (a
    ~1.27% CLOSE-vs-CLOSE drift, plausibly a dividend-adjustment artifact)
    -- the new method resolves it too, because HIGH and LOW (unlike
    CLOSE) are the same real trade prints in both sources and agree with
    each other even though the derived scale (~2.0257) isn't a round
    number.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from fibo.intraday_db import get_read_connection as get_intraday_connection
from fibo.scale_probe import (
    ScaleDecision, probe_scale, passes_gap_guard, to_raw_scale,
    is_ex_date, previous_trading_day, decide_scale_for_day,
)

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"
INTRADAY_DB = Path(__file__).resolve().parents[1] / "data" / "fibo_intraday.duckdb"

BPCL = "INE029A01011"
TATASTEEL = "INE081A01012"
KOTAKBANK = "INE237A01028"
RELIANCE = "INE002A01018"


# ---- synthetic: the pure decision functions ----

def test_probe_scale_resolves_when_high_and_low_ratios_agree():
    # bhav = angel x 2.0 for both high and low -> clean SCALED at 2.0
    decision, scale = probe_scale(bhav_high_prev=200.0, angel_high_prev=100.0, bhav_low_prev=196.0, angel_low_prev=98.0)
    assert decision == ScaleDecision.SCALED
    assert scale == pytest.approx(2.0)


def test_probe_scale_raw_equivalent_when_ratios_are_near_one():
    decision, scale = probe_scale(bhav_high_prev=100.05, angel_high_prev=100.0, bhav_low_prev=99.95, angel_low_prev=100.0)
    assert decision == ScaleDecision.RAW_EQUIVALENT
    assert scale == pytest.approx(1.0, abs=0.001)


def test_probe_scale_unresolved_when_high_and_low_ratios_disagree():
    # r_high = 2.0, r_low = 3.0 -- wildly inconsistent, not a real single scale
    decision, scale = probe_scale(bhav_high_prev=200.0, angel_high_prev=100.0, bhav_low_prev=300.0, angel_low_prev=100.0)
    assert decision == ScaleDecision.UNRESOLVED
    assert scale is None


def test_probe_scale_tolerance_boundary():
    # r_high=1.0009, r_low=1.0 -> relative disagreement ~0.045%, within 0.1%
    decision, _ = probe_scale(bhav_high_prev=100.09, angel_high_prev=100.0, bhav_low_prev=100.0, angel_low_prev=100.0)
    assert decision != ScaleDecision.UNRESOLVED
    # r_high=1.002, r_low=1.0 -> relative disagreement ~0.1996%, beyond 0.1%
    decision, _ = probe_scale(bhav_high_prev=100.2, angel_high_prev=100.0, bhav_low_prev=100.0, angel_low_prev=100.0)
    assert decision == ScaleDecision.UNRESOLVED


def test_probe_scale_missing_inputs_is_unresolved_not_a_crash():
    decision, scale = probe_scale(0.0, 100.0, 99.0, 98.0)
    assert decision == ScaleDecision.UNRESOLVED
    assert scale is None


def test_passes_gap_guard_true_within_threshold_false_beyond():
    assert passes_gap_guard(converted_open_d=105.0, bhav_close_prev=100.0)  # 5% gap, within 20%
    assert not passes_gap_guard(converted_open_d=130.0, bhav_close_prev=100.0)  # 30% gap, beyond 20%


def test_to_raw_scale_arithmetic():
    assert to_raw_scale(50.0, 2.0) == pytest.approx(100.0)
    assert to_raw_scale(100.0, 1.0) == pytest.approx(100.0)


# ---- real development-window cases ----

@pytest.fixture(scope="module")
def warehouse_con():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    return get_connection(WAREHOUSE)


@pytest.fixture(scope="module")
def intraday_con():
    if not INTRADAY_DB.exists():
        pytest.skip("real intraday DB not present -- Step 3 download not run in this environment")
    return get_intraday_connection(INTRADAY_DB)


def _assert_resolved_and_zone_lands_right(warehouse_con, intraday_con, entity_id, d, expected_decision, expected_scale):
    result = decide_scale_for_day(intraday_con, warehouse_con, entity_id, d)
    assert result["decision"] == expected_decision
    assert result["scale"] == pytest.approx(expected_scale, rel=1e-3)

    angel_d = intraday_con.execute(
        "SELECT open, high, low, close FROM bars_1min WHERE entity_id=? AND trade_date=? ORDER BY ts",
        [entity_id, d],
    ).fetchdf()
    angel_open, angel_high, angel_low, angel_close = (
        angel_d["open"].iloc[0], angel_d["high"].max(), angel_d["low"].min(), angel_d["close"].iloc[-1])

    bhav_d = warehouse_con.execute(
        "SELECT p.open, p.high, p.low, p.close FROM prices_eod p JOIN isin_lineage l ON p.isin=l.isin "
        "WHERE l.entity_id=? AND p.trade_date=? AND p.series='EQ'",
        [entity_id, d],
    ).fetchone()
    bhav_open, bhav_high, bhav_low, bhav_close = bhav_d

    scale = result["scale"]
    # high/low must land almost exactly (the two prices the scale was itself derived to satisfy);
    # open/close are looser since D-1's scale is being applied to D (not derived from D itself)
    assert to_raw_scale(angel_high, scale) == pytest.approx(bhav_high, rel=0.002)
    assert to_raw_scale(angel_low, scale) == pytest.approx(bhav_low, rel=0.002)
    assert to_raw_scale(angel_open, scale) == pytest.approx(bhav_open, rel=0.01)


def test_real_bpcl_case(warehouse_con, intraday_con):
    _assert_resolved_and_zone_lands_right(warehouse_con, intraday_con, BPCL, dt.date(2019, 12, 27), ScaleDecision.SCALED, 2.0)


def test_real_tatasteel_case(warehouse_con, intraday_con):
    _assert_resolved_and_zone_lands_right(warehouse_con, intraday_con, TATASTEEL, dt.date(2022, 7, 27), ScaleDecision.RAW_EQUIVALENT, 1.0)


def test_real_kotakbank_case_now_resolved_without_corporate_actions_table(warehouse_con, intraday_con):
    """KOTAKBANK was UNRESOLVED under the first version of this module (its
    2015 merger predates corporate_actions coverage). The new HIGH/LOW
    method resolves it cleanly to an EXACT 5.0 scale, with no dependency
    on this project's own factor table at all."""
    _assert_resolved_and_zone_lands_right(warehouse_con, intraday_con, KOTAKBANK, dt.date(2020, 1, 7), ScaleDecision.SCALED, 5.0)


def test_real_reliance_case_now_resolved_despite_dividend_drift(warehouse_con, intraday_con):
    """RELIANCE was UNRESOLVED under the first version (close-vs-close
    disagreed with the project's own factor by ~1.27%, plausibly dividend
    adjustment). HIGH and LOW, unlike close, are real trade prints in both
    sources and agree with EACH OTHER even though the resulting scale
    (~2.0257) isn't the theoretically \"clean\" 2.0."""
    result = decide_scale_for_day(intraday_con, warehouse_con, RELIANCE, dt.date(2017, 9, 11))
    assert result["decision"] == ScaleDecision.SCALED
    assert result["scale"] == pytest.approx(2.0257, rel=1e-3)
    assert result["scale"] != pytest.approx(2.0, rel=1e-3)  # NOT the naive combined-bonus factor -- the real, measured one


def test_real_tatasteel_ex_date_is_flagged(warehouse_con):
    assert is_ex_date(warehouse_con, TATASTEEL, dt.date(2022, 7, 28))
    assert not is_ex_date(warehouse_con, TATASTEEL, dt.date(2022, 7, 27))


def test_decide_scale_for_day_skips_the_real_ex_date(warehouse_con, intraday_con):
    result = decide_scale_for_day(intraday_con, warehouse_con, TATASTEEL, dt.date(2022, 7, 28))
    assert result["decision"] == ScaleDecision.EX_DATE_SKIP
    assert result["scale"] is None


def test_previous_trading_day_is_the_entitys_own_prior_row_not_a_calendar_day(warehouse_con):
    prev = previous_trading_day(warehouse_con, TATASTEEL, dt.date(2022, 7, 27))
    assert prev == dt.date(2022, 7, 26)
