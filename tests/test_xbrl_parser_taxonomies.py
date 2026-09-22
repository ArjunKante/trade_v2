"""Regression tests for xbrl_parser.py's two-taxonomy support, written
before trusting it against real Integrated Filing documents -- same
discipline as tests/test_fundamentals_factors_ttm.py: verify the mechanism
on a small, hand-checkable case first.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import duckdb

from data_layer.db import get_connection
from data_layer.xbrl_parser import extract_isin, facts_to_df, load_facts_to_duckdb, parse_xbrl_facts

OLD_TAXONOMY_SNIPPET = """
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2016-03-31/in-bse-fin">
  <in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-3">2190000000</in-bse-fin:RevenueFromOperations>
  <in-bse-fin:ProfitLossForPeriod contextRef="OneD" unitRef="INR" decimals="-3">150000000</in-bse-fin:ProfitLossForPeriod>
</xbrli:xbrl>
"""

NEW_TAXONOMY_SNIPPET = """
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt">
  <in-capmkt:ISIN contextRef="OneD">INE185Q01025</in-capmkt:ISIN>
  <in-capmkt:RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-3">5214296000</in-capmkt:RevenueFromOperations>
  <in-capmkt:Assets contextRef="I_Audited" unitRef="INR" decimals="-3">2971797000</in-capmkt:Assets>
  <in-capmkt:NatureOfReportStandaloneConsolidated contextRef="PY_I">Standalone</in-capmkt:NatureOfReportStandaloneConsolidated>
</xbrli:xbrl>
"""


def test_parses_old_in_bse_fin_taxonomy_unchanged():
    facts = parse_xbrl_facts(OLD_TAXONOMY_SNIPPET)
    tags = {f["tag"]: f["value"] for f in facts}
    assert tags["RevenueFromOperations"] == "2190000000"
    assert tags["ProfitLossForPeriod"] == "150000000"


def test_parses_new_in_capmkt_taxonomy_same_tag_names():
    facts = parse_xbrl_facts(NEW_TAXONOMY_SNIPPET)
    tags = {f["tag"]: f["value"] for f in facts}
    assert tags["RevenueFromOperations"] == "5214296000"
    assert tags["ISIN"] == "INE185Q01025"


def test_parses_underscore_context_ids_from_new_taxonomy():
    facts = parse_xbrl_facts(NEW_TAXONOMY_SNIPPET)
    ctxs = {f["tag"]: f["context_ref"] for f in facts}
    assert ctxs["Assets"] == "I_Audited"
    assert ctxs["NatureOfReportStandaloneConsolidated"] == "PY_I"


def test_extract_isin_returns_the_tagged_value():
    facts = parse_xbrl_facts(NEW_TAXONOMY_SNIPPET)
    assert extract_isin(facts) == "INE185Q01025"


def test_extract_isin_returns_none_when_absent():
    facts = parse_xbrl_facts(OLD_TAXONOMY_SNIPPET)
    assert extract_isin(facts) is None


def test_load_facts_scopes_dedup_by_source_not_bare_seq_number(tmp_path):
    """The real risk this guards against: two different sources assigning
    the same literal seq_number/seq_Id. Before the fix, inserting source B's
    fact with the same seq_number as an existing source-A fact would be
    silently skipped as if it were a duplicate of source A's row."""
    con = get_connection(tmp_path / "test.duckdb")
    now = dt.datetime.now()

    df_a = facts_to_df(
        [{"context_ref": "OneD", "tag": "RevenueFromOperations", "unit": "INR", "value": "100"}],
        isin="INE000A00001", seq_number="195303", period_end=dt.date(2025, 3, 31),
        consolidated="Standalone", known_date=dt.date(2025, 5, 1), source="SOURCE_A",
    )
    n1 = load_facts_to_duckdb(con, df_a)
    assert n1 == 1

    df_b = facts_to_df(
        [{"context_ref": "OneD", "tag": "RevenueFromOperations", "unit": "INR", "value": "999"}],
        isin="INE999Z99999", seq_number="195303", period_end=dt.date(2025, 6, 30),
        consolidated="Consolidated", known_date=dt.date(2025, 8, 1), source="SOURCE_B",
    )
    n2 = load_facts_to_duckdb(con, df_b)
    assert n2 == 1, "source B's fact with a colliding seq_number must still be inserted"

    rows = con.execute(
        "SELECT source, isin, value FROM fundamentals_xbrl_facts WHERE seq_number = '195303' ORDER BY source"
    ).fetchdf()
    assert len(rows) == 2
    assert set(rows["source"]) == {"SOURCE_A", "SOURCE_B"}

    # re-inserting the same (source, seq_number) is still correctly a no-op
    n3 = load_facts_to_duckdb(con, df_a)
    assert n3 == 0
    con.close()
