"""ISIN lineage: the NSDL structural rule, its two hard-reject cases, the
known_date-is-historical invariant, and ambiguous-case reporting.

Real-data checks use the actual backfilled warehouse (data/warehouse.duckdb)
so they exercise the real BAJFINANCE chain end to end; synthetic-fixture
checks exercise the two reject paths and the "different companies, same
symbol" danger case that don't occur in this project's real INE-equity data
(matching the prior project's own finding: real DVR/preference shares
always trade under a different symbol, so they never become same-symbol
candidates in the first place -- the reject logic still needs its own test
as defense in depth against future changes to candidate generation).
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.isin_lineage import parse_isin, build_lineage, build_entity_resolver

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"


def test_parse_isin_matches_known_real_structure():
    s = parse_isin("INE296A01024")
    assert s.prefix == "INE"
    assert s.issuer == "296A"
    assert s.sectype == "01"
    assert s.serial == 2


@pytest.fixture(scope="module")
def real_con():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    return get_read_connection(WAREHOUSE)


def test_bajfinance_three_isin_chain_resolves_to_one_entity(real_con):
    lineage_df, _ = build_lineage(real_con)
    chain = lineage_df[lineage_df["isin"].isin(["INE296A01016", "INE296A01024", "INE296A01032"])]
    assert chain["entity_id"].nunique() == 1
    assert chain["entity_id"].iloc[0] == "INE296A01016"  # earliest ISIN in the chain


def test_known_date_is_historical_transition_not_today(real_con):
    lineage_df, _ = build_lineage(real_con)
    row = lineage_df[lineage_df["isin"] == "INE296A01032"].iloc[0]
    assert row["known_date"] == dt.date(2025, 6, 16)  # the real transition date
    assert row["known_date"] != dt.date.today()


def test_entity_resolver_as_of_excludes_a_link_not_yet_established(real_con):
    """A link established in 2025 must not resolve for a query as_of a date
    before that link existed -- otherwise a historical backtest would use
    lineage knowledge it couldn't have had."""
    resolver_early = build_entity_resolver(real_con, as_of=dt.date(2020, 1, 1))
    resolver_late = build_entity_resolver(real_con, as_of=dt.date(2026, 1, 1))
    # the first link (2016-09-09) should already be visible by 2020
    assert resolver_early.get("INE296A01024") == "INE296A01016"
    # the second link (2025-06-16) should NOT be visible as-of 2020...
    assert resolver_early.get("INE296A01032") is None
    # ...but must be visible as-of 2026
    assert resolver_late.get("INE296A01032") == "INE296A01016"


# ---- synthetic fixtures: the two hard-reject paths and the danger case ----

def _fake_ranges(rows):
    return pd.DataFrame(rows)


def test_same_issuer_different_security_type_is_hard_rejected(monkeypatch):
    """Same issuer code, different security type (e.g. ordinary shares vs a
    DVR class) must NEVER be linked, even though it would pass a naive
    'same issuer prefix' check."""
    import data_layer.isin_lineage as mod

    fake_ranges = _fake_ranges([
        {"symbol": "DVRCO", "isin": "INE111A01011", "first_date": dt.date(2016, 1, 1), "last_date": dt.date(2018, 12, 31)},
        {"symbol": "DVRCO", "isin": "INE111A02018", "first_date": dt.date(2019, 1, 1), "last_date": dt.date(2020, 12, 31)},
    ])
    monkeypatch.setattr(mod, "build_isin_date_ranges", lambda con: fake_ranges)
    lineage_df, ambiguous_df = mod.build_lineage(con=None)

    assert len(ambiguous_df) == 1
    assert ambiguous_df.iloc[0]["reason"] == "same_issuer_different_security_type_HARD_REJECT"
    # neither ISIN should have been linked to the other
    a = lineage_df[lineage_df["isin"] == "INE111A02018"].iloc[0]
    assert a["predecessor_isin"] != "INE111A01011"


def test_overlapping_date_ranges_same_issuer_not_linked_and_reported(monkeypatch):
    """Same issuer+type, serial increases, but the date ranges overlap --
    not a clean handover, must not be linked."""
    import data_layer.isin_lineage as mod

    fake_ranges = _fake_ranges([
        {"symbol": "OVERLAP", "isin": "INE222B01015", "first_date": dt.date(2016, 1, 1), "last_date": dt.date(2019, 6, 30)},
        {"symbol": "OVERLAP", "isin": "INE222B01023", "first_date": dt.date(2019, 1, 1), "last_date": dt.date(2021, 12, 31)},
    ])
    monkeypatch.setattr(mod, "build_isin_date_ranges", lambda con: fake_ranges)
    lineage_df, ambiguous_df = mod.build_lineage(con=None)

    assert len(ambiguous_df) == 1
    assert ambiguous_df.iloc[0]["reason"] == "overlapping_date_ranges_not_a_clean_handover"


def test_two_different_companies_sharing_a_symbol_are_not_linked(monkeypatch):
    """The danger case: a delisted company's symbol reused years later by a
    genuinely unrelated company. Different issuer code -> must not link,
    regardless of how clean the date-range handover looks."""
    import data_layer.isin_lineage as mod

    fake_ranges = _fake_ranges([
        {"symbol": "REUSED", "isin": "INE333C01019", "first_date": dt.date(2016, 1, 1), "last_date": dt.date(2018, 12, 31)},
        {"symbol": "REUSED", "isin": "INE999Z01027", "first_date": dt.date(2021, 1, 1), "last_date": dt.date(2023, 12, 31)},
    ])
    monkeypatch.setattr(mod, "build_isin_date_ranges", lambda con: fake_ranges)
    lineage_df, ambiguous_df = mod.build_lineage(con=None)

    assert len(ambiguous_df) == 1
    assert ambiguous_df.iloc[0]["reason"] == "different_issuer_or_type_not_a_reissue_candidate"
    entities = dict(zip(lineage_df["isin"], lineage_df["entity_id"]))
    assert entities["INE333C01019"] != entities["INE999Z01027"]  # NOT merged into one entity


def test_known_date_deterministic_for_an_isin_traded_under_two_symbol_names(monkeypatch):
    """Found 2026-11-18 while building gap_backfill's before/after lineage
    diff (BUGS.md Bug #33's fix): an isin that traded under more than one
    SYMBOL (a rename, same ISIN -- real, e.g. IN9623B01058: FRLDVR through
    2016-05-12, then FELDVR from 2016-05-13) produces TWO rows in `ranges`
    grouped by (symbol, isin). An unlinked isin's known_date fallback used
    to be `.iloc[0]` of that unordered multi-row match -- non-deterministic
    across calls on byte-identical data, since build_isin_date_ranges has
    no ORDER BY and DuckDB's own GROUP BY row order is not guaranteed
    stable. Two independent build_lineage() calls back to back, nothing
    else touching prices_eod in between, disagreed on 74-104 isins'
    known_date in the real warehouse before this was fixed to `.min()`.
    This fixture reproduces the exact two-symbol-same-isin shape and
    asserts both calls agree, and agree on the semantically correct
    (earliest) date."""
    import data_layer.isin_lineage as mod

    fake_ranges = _fake_ranges([
        {"symbol": "OLDNAME", "isin": "INE999Z01011", "first_date": dt.date(2016, 1, 1), "last_date": dt.date(2016, 5, 12)},
        {"symbol": "NEWNAME", "isin": "INE999Z01011", "first_date": dt.date(2016, 5, 13), "last_date": dt.date(2026, 11, 18)},
    ])
    monkeypatch.setattr(mod, "build_isin_date_ranges", lambda con: fake_ranges)

    results = [mod.build_lineage(con=None)[0] for _ in range(10)]
    known_dates = {df.loc[df["isin"] == "INE999Z01011", "known_date"].iloc[0] for df in results}
    assert known_dates == {dt.date(2016, 1, 1)}  # deterministic AND the true earliest date


def test_serial_not_increasing_in_date_order_is_ambiguous_not_guessed(monkeypatch):
    import data_layer.isin_lineage as mod

    fake_ranges = _fake_ranges([
        {"symbol": "BACKWARDS", "isin": "INE444D01023", "first_date": dt.date(2016, 1, 1), "last_date": dt.date(2018, 12, 31)},
        {"symbol": "BACKWARDS", "isin": "INE444D01015", "first_date": dt.date(2019, 1, 1), "last_date": dt.date(2021, 12, 31)},
    ])
    monkeypatch.setattr(mod, "build_isin_date_ranges", lambda con: fake_ranges)
    lineage_df, ambiguous_df = mod.build_lineage(con=None)

    assert len(ambiguous_df) == 1
    assert ambiguous_df.iloc[0]["reason"] == "serial_does_not_increase_in_date_order"
