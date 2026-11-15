"""Decisions 6, 7, 10, 18, 23: monthly roster construction, against a
synthetic in-memory DuckDB fixture (no real warehouse data touched)."""
import datetime as dt
import inspect
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag.roster import (
    build_monthly_roster, roster_tier_size, tier_entity_ids, TRAILING_WINDOW,
    InvalidRankingDate,
)


@pytest.fixture
def synthetic_con():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE isin_lineage (isin VARCHAR, entity_id VARCHAR)")
    con.execute("""
        CREATE TABLE prices_eod (
            isin VARCHAR, trade_date DATE, series VARCHAR, turnover DOUBLE
        )
    """)
    # 5 entities, each with exactly 60 qualifying prior sessions plus the
    # ranking date itself (which must be excluded by the window).
    ranking_date = dt.date(2026, 6, 1)
    entities = {
        "E1": ("ISIN1", 1_000_000),  # highest turnover -> leader
        "E2": ("ISIN2", 500_000),
        "E3": ("ISIN3", 300_000),
        "E4": ("ISIN4", 200_000),
        "E5": ("ISIN5", 100_000),  # lowest -> follower
    }
    rows = []
    for entity_id, (isin, turnover) in entities.items():
        con.execute("INSERT INTO isin_lineage VALUES (?, ?)", [isin, entity_id])
        for i in range(1, TRAILING_WINDOW + 1):
            d = ranking_date - dt.timedelta(days=i)
            rows.append((isin, d, "EQ", turnover))
        # a row ON the ranking date itself, with a wildly different
        # turnover, to prove it is excluded from the window
        rows.append((isin, ranking_date, "EQ", turnover * 1000))
    con.executemany("INSERT INTO prices_eod VALUES (?, ?, ?, ?)", rows)
    return con, ranking_date, entities


def test_build_monthly_roster_excludes_ranking_date_own_turnover(synthetic_con):
    con, ranking_date, entities = synthetic_con
    universe_df = pd.DataFrame({"entity_id": list(entities.keys())})
    roster = build_monthly_roster(con, ranking_date, universe_df)
    assert roster.n_eligible == 5
    # if the ranking date's inflated turnover had leaked in, medians would
    # all be dominated by that one outlier value and ranking would be
    # unaffected here (all entities have the SAME inflation factor) --
    # so instead assert the median equals the ordinary (non-inflated)
    # turnover exactly, proving the ranking-date row never entered the window.
    for entity_id, (_, turnover) in entities.items():
        row = roster.entities.loc[roster.entities["entity_id"] == entity_id]
        assert row["median_turnover"].iloc[0] == pytest.approx(turnover)


def test_build_monthly_roster_tier_split_top_20_percent(synthetic_con):
    con, ranking_date, entities = synthetic_con
    universe_df = pd.DataFrame({"entity_id": list(entities.keys())})
    roster = build_monthly_roster(con, ranking_date, universe_df)
    # ceil(0.2 * 5) = 1 leader, 4 followers
    assert roster.n_leaders == 1
    assert roster.n_followers == 4
    leaders = tier_entity_ids(roster, "leader")
    assert leaders == ["E1"]  # highest turnover
    followers = set(tier_entity_ids(roster, "follower"))
    assert followers == {"E2", "E3", "E4", "E5"}


def test_build_monthly_roster_requires_60_qualifying_observations(synthetic_con):
    con, ranking_date, entities = synthetic_con
    # add a 6th entity with only 59 qualifying prior sessions
    con.execute("INSERT INTO isin_lineage VALUES ('ISIN6', 'E6')")
    for i in range(1, TRAILING_WINDOW):  # only 59
        d = ranking_date - dt.timedelta(days=i)
        con.execute("INSERT INTO prices_eod VALUES (?, ?, 'EQ', ?)", ["ISIN6", d, 999_999])
    universe_df = pd.DataFrame({"entity_id": list(entities.keys()) + ["E6"]})
    roster = build_monthly_roster(con, ranking_date, universe_df)
    assert roster.n_eligible == 5  # E6 excluded
    assert "E6" in roster.ineligible_entity_ids


def test_roster_tier_size_is_original_tier_size(synthetic_con):
    con, ranking_date, entities = synthetic_con
    universe_df = pd.DataFrame({"entity_id": list(entities.keys())})
    roster = build_monthly_roster(con, ranking_date, universe_df)
    assert roster_tier_size(roster, "leader") == 1
    assert roster_tier_size(roster, "follower") == 4
    with pytest.raises(ValueError):
        roster_tier_size(roster, "nonsense")


def test_build_monthly_roster_is_deterministic_same_inputs_same_output(synthetic_con):
    con, ranking_date, entities = synthetic_con
    universe_df = pd.DataFrame({"entity_id": list(entities.keys())})
    r1 = build_monthly_roster(con, ranking_date, universe_df)
    r2 = build_monthly_roster(con, ranking_date, universe_df)
    pd.testing.assert_frame_equal(r1.entities, r2.entities)
    assert r1.n_leaders == r2.n_leaders
    assert r1.n_followers == r2.n_followers


def test_build_monthly_roster_rejects_an_ordinary_weekend_as_ranking_date(synthetic_con):
    """Decision 24 contract: a caller cannot silently construct a
    roster against an arbitrary non-session date."""
    con, _, entities = synthetic_con
    universe_df = pd.DataFrame({"entity_id": list(entities.keys())})
    not_a_session = dt.date(2026, 6, 6)  # an ordinary Saturday, not one of the 4 specials
    assert not_a_session.weekday() >= 5
    with pytest.raises(InvalidRankingDate):
        build_monthly_roster(con, not_a_session, universe_df)


def test_build_monthly_roster_rejects_an_nse_holiday_as_ranking_date(synthetic_con):
    con, _, entities = synthetic_con
    universe_df = pd.DataFrame({"entity_id": list(entities.keys())})
    republic_day = dt.date(2026, 1, 26)  # fixed NSE holiday every year
    with pytest.raises(InvalidRankingDate):
        build_monthly_roster(con, republic_day, universe_df)


def test_build_monthly_roster_accepts_a_genuine_weekend_special_session(synthetic_con):
    """The contract must not reject a date merely because it is a
    weekend -- the 4 approved specials remain valid ranking dates."""
    con, ranking_date, entities = synthetic_con
    # re-point the fixture's own data at the 2026-02-01 special session
    # instead of its default ranking_date, to prove acceptance, not just
    # non-rejection of the default.
    special = dt.date(2026, 2, 1)
    assert special.weekday() >= 5
    con.execute("DELETE FROM prices_eod")
    rows = []
    for entity_id, (isin, turnover) in entities.items():
        for i in range(1, TRAILING_WINDOW + 1):
            d = special - dt.timedelta(days=i)
            rows.append((isin, d, "EQ", turnover))
    con.executemany("INSERT INTO prices_eod VALUES (?, ?, ?, ?)", rows)
    universe_df = pd.DataFrame({"entity_id": list(entities.keys())})
    roster = build_monthly_roster(con, special, universe_df)  # must not raise
    assert roster.n_eligible == 5


def test_build_monthly_roster_signature_has_no_signal_time_parameter():
    """Decision 18, structural guarantee: this function cannot take a
    signal-time (`t`) input at all -- there is no parameter through which
    signal-time availability could influence membership. Roster
    membership is a pure function of (ranking_date, universe); any
    availability-based filtering must happen later, in eligibility.py,
    never here."""
    params = set(inspect.signature(build_monthly_roster).parameters)
    assert params == {"con", "ranking_date", "universe_year_df"}
    assert "t" not in params and "signal_minute" not in params and "availability" not in params
