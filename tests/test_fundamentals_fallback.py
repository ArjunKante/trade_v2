"""The 45-day period_end fallback has never executed on real data --
0.000% of 108,996 backfilled rows needed it, since this endpoint always
carries a real broadCastDate. Untested code that only runs on rare inputs
is exactly where bugs live; this exercises it directly with a synthetic
record missing broadCastDate.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.fundamentals_nse import to_filings_df, FALLBACK_LAG_DAYS, FALLBACK_FLAG

RECORD_MISSING_BROADCAST = {
    "isin": "INE999X01011",
    "symbol": "TESTCO",
    "companyName": "Test Company Limited",
    "fromDate": "01-Oct-2024",
    "toDate": "31-Dec-2024",
    "financialYear": "01-Apr-2024 To 31-Mar-2025",
    "relatingTo": "Third Quarter",
    "consolidated": "Consolidated",
    "audited": "Un-Audited",
    "seqNumber": "9999999",
    "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/fake.xml",
    "broadCastDate": None,  # the missing-data case
}

RECORD_WITH_BROADCAST = dict(RECORD_MISSING_BROADCAST, broadCastDate="15-Feb-2025 10:00:00", seqNumber="8888888")


def test_fallback_fires_when_broadcast_date_missing():
    df = to_filings_df([RECORD_MISSING_BROADCAST])
    assert len(df) == 1
    row = df.iloc[0]
    assert row["data_quality"] == FALLBACK_FLAG


def test_fallback_known_date_is_period_end_plus_45_days():
    df = to_filings_df([RECORD_MISSING_BROADCAST])
    row = df.iloc[0]
    expected = dt.date(2024, 12, 31) + dt.timedelta(days=FALLBACK_LAG_DAYS)
    assert row["known_date"] == expected


def test_normal_row_with_broadcast_date_is_not_flagged():
    df = to_filings_df([RECORD_WITH_BROADCAST])
    row = df.iloc[0]
    assert row["data_quality"] is None
    assert row["known_date"] == dt.date(2025, 2, 15)


def test_mixed_batch_flags_only_the_missing_one():
    df = to_filings_df([RECORD_MISSING_BROADCAST, RECORD_WITH_BROADCAST])
    assert len(df) == 2
    flagged = df[df["data_quality"] == FALLBACK_FLAG]
    unflagged = df[df["data_quality"].isna()]
    assert len(flagged) == 1
    assert len(unflagged) == 1
    assert flagged.iloc[0]["seq_number"] == "9999999"
