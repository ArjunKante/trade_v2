"""VSTTILLERS Q3 FY25 is the canonical example of why known_date must be the
announcement timestamp, never fiscal_period_end: period ended 2024-12-31,
but the result was not announced until 2026-07-30 -- a 576-day (~19-month)
gap. A system keying on period_end would have treated this quarter's
numbers as available to any as_of date from 2025-01-01 onward, when in
reality nobody outside the company knew them until 2026-07-30.

Real values, fetched live from NSE's corporates-financial-results API on
2026-09-19 (seqNumber 1197616, ISIN INE764D01017, non-consolidated seqNumber
1197614). These are pinned exactly, not regenerated, so a future refactor
that silently reverts to period_end can't pass this test by accident.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.fundamentals_nse import to_filings_df

VSTTILLERS_RAW_RECORD = {
    "isin": "INE764D01017",
    "symbol": "VSTTILLERS",
    "companyName": "V.S.T Tillers Tractors Limited",
    "fromDate": "01-Oct-2024",
    "toDate": "31-Dec-2024",
    "financialYear": "01-Apr-2024 To 31-Mar-2025",
    "relatingTo": "Third Quarter",
    "consolidated": "Consolidated",
    "audited": "Un-Audited",
    "seqNumber": "1197616",
    "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_121277_1705282_30072026051753.xml",
    "broadCastDate": "30-Jul-2026 17:17:53",
}

PERIOD_END = dt.date(2024, 12, 31)
ANNOUNCEMENT_DATE = dt.date(2026, 7, 30)
EXPECTED_LAG_DAYS = 576  # (2026-07-30 - 2024-12-31).days -- ~19 months


def test_vsttillers_lag_is_the_real_576_days():
    assert (ANNOUNCEMENT_DATE - PERIOD_END).days == EXPECTED_LAG_DAYS


def test_known_date_is_announcement_not_period_end():
    df = to_filings_df([VSTTILLERS_RAW_RECORD])
    row = df.iloc[0]
    assert row["period_end"] == PERIOD_END
    assert row["known_date"] == ANNOUNCEMENT_DATE
    assert row["known_date"] != row["period_end"]
    assert (row["known_date"] - row["period_end"]).days == EXPECTED_LAG_DAYS


def test_a_naive_period_end_keyed_query_would_have_leaked_this_row_for_19_months():
    """The failure mode this whole test file exists to prevent: if some future
    code path used period_end as the point-in-time cutoff instead of known_date,
    this row would appear 'available' to any as_of date from 2025-01-01 --
    576 days before it was actually announced."""
    df = to_filings_df([VSTTILLERS_RAW_RECORD])
    row = df.iloc[0]

    as_of_naive_wrong_way = dt.date(2025, 6, 1)  # after period_end, well before real announcement
    naively_visible = row["period_end"] <= as_of_naive_wrong_way  # the bug: keying on period_end
    correctly_visible = row["known_date"] <= as_of_naive_wrong_way  # the fix: keying on known_date

    assert naively_visible is True  # this is the leak
    assert correctly_visible is False  # this is what must actually happen
