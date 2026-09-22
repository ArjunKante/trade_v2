"""Regression tests for integrated_filing_nse.py's metadata parsing --
written before running the real backfill, same discipline as every other
point-in-time mechanism in this project."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

from data_layer.integrated_filing_nse import (
    to_metadata_df, scope_to_price_covered_symbols, fetch_all_integrated_filing_metadata,
)
from data_layer.db import get_connection


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    """Stands in for requests.Session -- returns a scripted sequence of
    pages regardless of the actual page/size params requested, so the
    pagination LOOP's stopping logic can be tested without live network."""
    def __init__(self, pages):
        self._pages = pages
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        page = self._pages[min(self.calls, len(self._pages) - 1)]
        self.calls += 1
        return _FakeResponse(page)


def _record(**overrides):
    base = {
        "symbol": "LUMINO", "cmName": "Lumino Industries Limited",
        "qe_Date": "30-JUN-2026", "consolidated": "Consolidated", "audited": "Un-Audited",
        "type_Sub": "Original", "revision_Remark": None, "seq_Id": "195130",
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/x.xml",
        "broadcast_Date": "21-Sep-2026 20:42:13", "revised_Date": None,
    }
    base.update(overrides)
    return base


def test_original_filing_known_date_is_broadcast_date():
    df = to_metadata_df([_record()])
    assert len(df) == 1
    assert df.iloc[0]["known_date"] == dt.date(2026, 9, 21)


def test_revision_filing_known_date_is_revised_date_not_broadcast():
    df = to_metadata_df([_record(
        type_Sub="Revision", broadcast_Date=None, revised_Date="22-SEP-2026 16:37:22",
        revision_Remark="Revised based on BSE Query.",
    )])
    assert len(df) == 1
    assert df.iloc[0]["known_date"] == dt.date(2026, 9, 22)


def test_period_end_never_used_as_known_date():
    """qe_Date is period_end, not known_date -- must never be conflated,
    same invariant as the old fundamentals_nse.py fetcher."""
    df = to_metadata_df([_record(qe_Date="31-MAR-2025", broadcast_Date="15-May-2025 10:00:00")])
    row = df.iloc[0]
    assert row["period_end"] == dt.date(2025, 3, 31)
    assert row["known_date"] == dt.date(2025, 5, 15)
    assert row["known_date"] != row["period_end"]


def test_mixed_case_month_abbreviations_both_parse():
    """NSE's own API is inconsistent (broadcast_Date: 'Sep', revised_Date:
    'SEP') -- confirmed directly against real API responses. Both must
    parse to the same result."""
    df1 = to_metadata_df([_record(broadcast_Date="21-Sep-2026 20:42:13")])
    df2 = to_metadata_df([_record(broadcast_Date="21-SEP-2026 20:42:13")])
    assert df1.iloc[0]["known_date"] == df2.iloc[0]["known_date"]


def test_row_dropped_when_no_known_date_available():
    df = to_metadata_df([_record(type_Sub="Original", broadcast_Date=None, revised_Date=None)])
    assert df.empty


def test_pagination_stops_on_short_page_not_on_totalcount():
    """Reproduces the real failure: totalCount fluctuates (26765, 26765,
    then 26829) while three full-size pages are still available. Must not
    stop early just because len(all_rows) happened to reach an
    earlier-reported totalCount -- must keep going until a page is
    actually short."""
    pages = [
        {"totalCount": 5, "data": [{"seq_Id": "1"}, {"seq_Id": "2"}]},  # size=2, full page, low total
        {"totalCount": 5, "data": [{"seq_Id": "3"}, {"seq_Id": "4"}]},  # still full-size
        {"totalCount": 9, "data": [{"seq_Id": "5"}]},  # short page -- real end, despite total having grown
    ]
    session = _FakeSession(pages)
    rows = fetch_all_integrated_filing_metadata(session, size=2, sleep_seconds=0)
    assert [r["seq_Id"] for r in rows] == ["1", "2", "3", "4", "5"]
    assert session.calls == 3


def test_pagination_raises_rather_than_looping_forever_on_a_broken_endpoint():
    """If pages never come back short (a genuinely broken/looping endpoint),
    the safety net must trip instead of running forever."""
    pages = [{"totalCount": 2, "data": [{"seq_Id": "x"}, {"seq_Id": "y"}]}]  # always full-size, low total
    session = _FakeSession(pages)
    with pytest.raises(RuntimeError):
        fetch_all_integrated_filing_metadata(session, size=2, sleep_seconds=0)


def test_scope_to_price_covered_symbols_filters_out_untracked_names(tmp_path):
    con = get_connection(tmp_path / "test.duckdb")
    con.execute("""
        INSERT INTO prices_eod VALUES
        ('INE000A00001', DATE '2024-01-01', 'TRACKED', 'EQ', 1,1,1,1,1,1,100,100,1,
         DATE '2024-01-01', now(), 'test', 1)
    """)
    df = pd.DataFrame({"symbol": ["TRACKED", "UNTRACKED"], "value": [1, 2]})
    scoped = scope_to_price_covered_symbols(con, df)
    assert list(scoped["symbol"]) == ["TRACKED"]
    con.close()
