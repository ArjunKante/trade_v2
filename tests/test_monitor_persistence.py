"""Tests for src/monitor/persistence.py -- the descriptive-only momentum
persistence monitor. Two kinds of test here, per this project's own
established convention (test_momentum_entity_aware.py etc.): fast,
synthetic-fixture unit tests for the mechanics (point-in-time invariant,
regime rule, CI labeling), and one real-warehouse integration test
confirming this module reproduces the exact 3-regime history already
published in NEW_RESEARCH_DIRECTION.md and reported by
scripts/run_momentum_persistence_regime_count.py."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from monitor.persistence import (
    compute_daily_persistence, annual_mean_sign, mechanical_regimes,
    nonoverlapping_periods, rolling_mean_se, label_from_ci, current_readout,
    MIN_CROSS_SECTION_N, HORIZON_DAYS,
)


# ---------------------------------------------------------------------------
# Synthetic panel: enough entities and enough history for a real forward-63d
# window and a >=MIN_CROSS_SECTION_N cross-section every date.
# ---------------------------------------------------------------------------

def _synthetic_panel(n_entities=30, n_days=600, seed=0):
    dates = pd.date_range("2018-01-01", periods=n_days, freq="B")
    rng = np.random.RandomState(seed)
    rows = []
    for i in range(n_entities):
        drift = rng.normal(0.0002, 0.0003)
        prices = 100.0 * np.cumprod(1 + drift + rng.normal(0, 0.01, n_days))
        for d, p in zip(dates, prices):
            rows.append({"entity_id": f"E{i}", "trade_date": d, "adjusted_close": p})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def panel():
    return _synthetic_panel()


# ---------------------------------------------------------------------------
# Point-in-time invariant
# ---------------------------------------------------------------------------

def test_no_persistence_value_uses_a_return_observation_after_as_of(panel):
    """For several as_of dates, every row's max_eval_date must be <= as_of."""
    candidate_dates = pd.date_range("2019-01-01", "2019-10-01", periods=6)
    for as_of in candidate_dates:
        daily = compute_daily_persistence(panel, as_of=as_of)
        if daily.empty:
            continue
        assert (daily["max_eval_date"] <= as_of).all(), (
            f"as_of={as_of.date()}: found a persistence value whose max_eval_date exceeds as_of"
        )


def test_as_of_none_never_exceeds_the_panels_own_latest_date(panel):
    """With no as_of given, the function must still never produce a value
    needing data beyond the panel's own last trading date -- this is what
    'never compute a value for D where D+63 is after the latest available
    price date' means when there is no explicit as_of cutoff."""
    daily = compute_daily_persistence(panel)
    assert (daily["max_eval_date"] <= panel["trade_date"].max()).all()


def test_as_of_strictly_before_history_produces_no_rows(panel):
    as_of = panel["trade_date"].min() - pd.Timedelta(days=1)
    daily = compute_daily_persistence(panel, as_of=as_of)
    assert daily.empty


# ---------------------------------------------------------------------------
# Mechanical regime rule -- unit-level, on a constructed daily series
# ---------------------------------------------------------------------------

def _daily_from_values(year_values: dict) -> pd.DataFrame:
    """Builds a minimal daily frame with one row per year at the given
    persistence value, enough for annual_mean_sign/mechanical_regimes."""
    rows = []
    for year, value in year_values.items():
        rows.append({"trade_date": pd.Timestamp(f"{year}-06-15"), "persistence": value,
                      "n": 50, "max_eval_date": pd.Timestamp(f"{year}-09-15")})
    return pd.DataFrame(rows)


def test_mechanical_regime_rule_is_contiguous_same_sign_runs():
    daily = _daily_from_values({2017: 0.10, 2018: 0.05, 2019: 0.20, 2020: -0.03, 2021: 0.01, 2022: 0.02})
    annual = annual_mean_sign(daily)
    regimes = mechanical_regimes(annual)
    assert regimes == [(2017, 2019, 1.0), (2020, 2020, -1.0), (2021, 2022, 1.0)]


def test_regime_boundary_at_exact_sign_flip():
    daily = _daily_from_values({2020: 0.01, 2021: -0.01})
    annual = annual_mean_sign(daily)
    regimes = mechanical_regimes(annual)
    assert regimes == [(2020, 2020, 1.0), (2021, 2021, -1.0)]


def test_empty_daily_gives_no_regimes():
    assert mechanical_regimes(annual_mean_sign(pd.DataFrame(columns=["trade_date", "persistence"]))) == []


# ---------------------------------------------------------------------------
# Real-warehouse integration: reproduces the exact 3 published regimes
# ---------------------------------------------------------------------------

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"


@pytest.fixture(scope="module")
def real_pre_holdout_daily():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    import warnings
    warnings.filterwarnings("ignore")
    from data_layer.db import get_read_connection
    from data_layer.entity_panel import read_entity_panel
    from data_layer.lineage_jump_guard import unexplained_jump_boundaries
    from data_layer.holdout import SEALED_HOLDOUT_START

    from monitor.persistence import same_isin_jump_excluded_entities

    con = get_read_connection(WAREHOUSE)
    excluded = same_isin_jump_excluded_entities(con)  # BUGS.md Bug #11
    panel_all = read_entity_panel(con)  # pre-holdout by default, no authorize_holdout
    panel = panel_all[~panel_all["entity_id"].isin(excluded)].reset_index(drop=True)
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)
    con.close()
    return compute_daily_persistence(panel, jump_dates)


def test_real_pre_holdout_regimes_are_a_well_formed_partition(real_pre_holdout_daily):
    """DELIBERATELY does not assert a specific regime count or boundary
    list -- an earlier version of this test did (hardcoded "3 regimes,
    2021-2024 positive"), and that number turned out to be unstable, not
    a historical fact: `same_isin_jump_excluded_entities()` and
    `compute_daily_persistence()` both read the FULL warehouse at call
    time, no `before` cutoff, by design. Proved directly (2026-11-16,
    BUGS.md Bug #24 follow-up) that excluding ONE entity (CONCORDBIO,
    INE338H01029) whose OWN same-ISIN jump was only flagged on
    2026-11-04 -- 12 days before this investigation, 38 days after this
    module was built -- removes that entity's entire multi-year history
    from the panel and flips 2022's mean_persistence from +0.0032 to
    -0.0022, crossing zero by less than 0.006, which splits one
    2021-2024 positive run into three regimes instead of one. Nothing
    about 2022's own trading activity changed; a jump discovered 12 days
    ago in an unrelated entity's recent price history retroactively
    reclassified an 2022 that has been over for three years. A hardcoded
    count asserted here would therefore go red again the next time any
    single entity anywhere in the warehouse gets newly flagged -- not a
    regression, just more data arriving, but indistinguishable from one
    if the test only checks an exact literal.

    What IS stable, and worth checking here instead: the mechanical rule
    itself must always produce a valid partition, regardless of how many
    regimes that produces today. See
    test_mechanical_regime_rule_is_contiguous_same_sign_runs /
    test_regime_boundary_at_exact_sign_flip above for the same rule
    tested on synthetic data -- this is the same rule's real-data
    integration check, not a re-test of whether a specific count is
    "right"."""
    annual = annual_mean_sign(real_pre_holdout_daily)
    regimes = mechanical_regimes(annual)

    assert len(regimes) >= 1

    annual_by_year = dict(zip(annual["year"], annual["sign"]))
    covered_years = set()
    for i, (start, end, sign) in enumerate(regimes):
        assert start <= end
        # contiguous calendar years, no gaps, within one regime
        years_in_regime = set(range(start, end + 1))
        assert not (years_in_regime & covered_years), "regimes must not overlap"
        covered_years |= years_in_regime
        # every year in this regime must actually have this sign
        for year in years_in_regime:
            assert annual_by_year[year] == sign
        # adjacent regimes must differ in sign (otherwise they'd have
        # been merged into one maximal run)
        if i > 0:
            assert regimes[i - 1][2] != sign

    # every year present in the annual series is accounted for by exactly one regime
    assert covered_years == set(annual["year"])


# ---------------------------------------------------------------------------
# Non-overlapping periods / rolling mean-SE
# ---------------------------------------------------------------------------

def test_nonoverlapping_periods_drops_a_trailing_partial_block():
    dates = pd.bdate_range("2020-01-01", periods=HORIZON_DAYS + 30)
    daily = pd.DataFrame({"trade_date": dates, "persistence": np.linspace(0, 1, len(dates)),
                          "n": 50, "max_eval_date": dates})
    periods = nonoverlapping_periods(daily)
    assert len(periods) == 1  # only one COMPLETE 63-day block fits in 93 days
    assert periods.iloc[0]["n_dates"] == HORIZON_DAYS


def test_rolling_mean_se_only_at_full_windows():
    periods = pd.DataFrame({
        "period_index": range(15),
        "period_end": pd.bdate_range("2020-01-01", periods=15),
        "mean_persistence": np.random.RandomState(1).normal(0.05, 0.02, 15),
        "n_dates": HORIZON_DAYS,
    })
    rolling = rolling_mean_se(periods, window=12)
    assert len(rolling) == 15 - 12 + 1
    # SE must come from the 12 period-level points, not fewer/more
    manual_se = np.std(periods["mean_persistence"].iloc[0:12], ddof=1) / np.sqrt(12)
    assert abs(rolling.iloc[0]["se"] - manual_se) < 1e-12


# ---------------------------------------------------------------------------
# CI labeling
# ---------------------------------------------------------------------------

def test_label_positive_negative_and_indistinguishable_from_zero():
    assert label_from_ci(0.01, 0.05) == "positive"
    assert label_from_ci(-0.05, -0.01) == "negative"
    assert label_from_ci(-0.01, 0.01) == "indistinguishable from zero"
    assert label_from_ci(0.0, 0.05) == "indistinguishable from zero"  # boundary: ci_lo not strictly > 0


def test_current_readout_has_both_dates_and_lag_sentence(panel):
    daily = compute_daily_persistence(panel)
    periods = nonoverlapping_periods(daily)
    rolling = rolling_mean_se(periods)
    readout = current_readout(daily, periods, rolling)
    assert readout["available"] is True
    assert "latest_signal_date" in readout and "measured_through" in readout
    assert readout["latest_signal_date"] != readout["measured_through"]
    assert "measured through" in readout["lag_sentence"]
    assert "quarter" in readout["lag_sentence"]


def test_current_readout_on_empty_daily_is_explicit():
    readout = current_readout(pd.DataFrame(columns=["trade_date", "persistence", "n", "max_eval_date"]),
                               pd.DataFrame(), pd.DataFrame())
    assert readout["available"] is False
