"""Regression test for the fundamentals-feed ISIN bug: NSE's
corporates-financial-results API reports a stale ISIN for the company
identification field, exactly the defect corporate_actions.py's
resolve_isin_for_actions already solved for the corporate-actions feed --
this is the same mechanism, ported to fundamentals_nse.py after the bug
was found to affect 166 of 2,487 distinct ISINs project-wide.

BHEL is the real, pinned case that caught this (checked live against NSE's
API on 2026-09-24): a 2024-05-21 FY2024 annual filing broadcast is tagged
isin=INE257A01018 by the feed, but this warehouse's own price data has
never seen that ISIN trade at all -- BHEL's actual, currently-trading ISIN
is INE257A01026. Before the fix, this orphaned 555 quarterly + 1,523
annual facts from every join that goes through isin_lineage/prices_eod.
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.fundamentals_nse import to_filings_df, resolve_isin_for_filings

BHEL_RECORD = {
    "isin": "INE257A01018",  # the feed's stale isin -- never appears in this warehouse's prices_eod
    "symbol": "BHEL",
    "companyName": "Bharat Heavy Electricals Limited",
    "fromDate": "01-Apr-2023",
    "toDate": "31-Mar-2024",
    "financialYear": "01-Apr-2023 To 31-Mar-2024",
    "relatingTo": "Annual",
    "consolidated": "Consolidated",
    "audited": "Audited",
    "seqNumber": "1172813",
    "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_106551_1131966_21052024060049.xml",
    "broadCastDate": "21-May-2024 18:00:50",
}


def _symbol_obs(rows):
    df = pd.DataFrame(rows, columns=["symbol", "trade_date", "isin"])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def test_bhel_stale_feed_isin_resolves_to_the_real_trading_isin():
    symbol_obs = _symbol_obs([
        ("BHEL", "2024-05-15", "INE257A01026"),
        ("BHEL", "2024-05-22", "INE257A01026"),
    ])
    df = to_filings_df([BHEL_RECORD], symbol_obs=symbol_obs)
    assert len(df) == 1
    assert df.iloc[0]["isin"] == "INE257A01026"
    assert df.iloc[0]["isin"] != "INE257A01018"  # the feed's own (wrong) value, confirmed corrected


def test_without_symbol_obs_the_old_unresolved_behavior_is_unchanged():
    """Backward compatibility: existing callers/tests that never pass
    symbol_obs keep getting the raw feed isin, exactly as before this fix."""
    df = to_filings_df([BHEL_RECORD])
    assert df.iloc[0]["isin"] == "INE257A01018"


def test_symbol_never_seen_in_prices_is_dropped_not_guessed():
    symbol_obs = _symbol_obs([("SOMEOTHERCO", "2024-05-15", "INE999Z01011")])
    df = to_filings_df([BHEL_RECORD], symbol_obs=symbol_obs)
    assert len(df) == 0  # BHEL never appears in symbol_obs here -- unresolvable, correctly dropped


def test_resolution_is_point_in_time_not_current_isin():
    """A filing known BEFORE an ISIN change must resolve to the OLD isin
    that was actually active then, never the symbol's later/current one --
    the exact contamination this project's point-in-time discipline exists
    to prevent (11.1% of symbols have mapped to more than one ISIN)."""
    symbol_obs = _symbol_obs([
        ("BHEL", "2020-01-01", "INE_OLD_ISIN01"),
        ("BHEL", "2020-06-01", "INE_OLD_ISIN01"),
        ("BHEL", "2023-01-01", "INE257A01026"),  # ISIN change partway through history
        ("BHEL", "2023-06-01", "INE257A01026"),
    ])
    old_filing = dict(BHEL_RECORD, broadCastDate="15-Mar-2020 10:00:00", seqNumber="1000001")
    new_filing = dict(BHEL_RECORD, broadCastDate="15-Mar-2023 10:00:00", seqNumber="1000002")
    df = to_filings_df([old_filing, new_filing], symbol_obs=symbol_obs)
    df = df.sort_values("known_date").reset_index(drop=True)
    assert df.iloc[0]["isin"] == "INE_OLD_ISIN01"   # 2020 filing -> the ISIN active in 2020
    assert df.iloc[1]["isin"] == "INE257A01026"     # 2023 filing -> the ISIN active in 2023


def test_passenger_columns_stay_aligned_across_multiple_symbols():
    """resolve_isin_for_filings sorts internally by known_date -- a caller
    that reattaches an extra column (e.g. seq_number) from the PRE-sort
    frame by positional .values afterward will silently misalign every row
    once more than one symbol is present and the sort reorders them. This
    caught a real bug in scripts/fix_fundamentals_isin_resolution.py's
    first draft (CLCIND's rows appeared to "resolve" to BHEL's isin) before
    it reached the live database. The correct pattern -- carry passenger
    columns straight through the same call, as fixed here -- must stay
    aligned no matter how many symbols or what order they arrive in."""
    filings = pd.DataFrame({
        "isin": ["INE_A_OLD", "INE_B_OLD", "INE_A_OLD", "INE_B_OLD"],
        "symbol": ["ACO", "BCO", "ACO", "BCO"],
        "known_date": [dt.date(2024, 6, 1), dt.date(2023, 3, 1), dt.date(2022, 1, 1), dt.date(2025, 8, 1)],
        "seq_number": ["seq-A2", "seq-B1", "seq-A1", "seq-B2"],
    })
    symbol_obs = _symbol_obs([
        ("ACO", "2020-01-01", "INE_A_REAL"),
        ("ACO", "2026-01-01", "INE_A_REAL"),
        ("BCO", "2020-01-01", "INE_B_REAL"),
        ("BCO", "2026-01-01", "INE_B_REAL"),
    ])
    out = resolve_isin_for_filings(filings, symbol_obs).set_index("seq_number")
    assert out.loc["seq-A1", "isin"] == "INE_A_REAL"
    assert out.loc["seq-A2", "isin"] == "INE_A_REAL"
    assert out.loc["seq-B1", "isin"] == "INE_B_REAL"
    assert out.loc["seq-B2", "isin"] == "INE_B_REAL"
    # every row's symbol must still match its own seq_number, not a neighbor's
    assert out.loc["seq-A1", "symbol"] == "ACO"
    assert out.loc["seq-B1", "symbol"] == "BCO"


def test_resolve_isin_for_filings_directly_forward_and_backward_fallback():
    """No exact/nearby observation on one side -- merge_asof must still
    find the nearest available observation in the other direction, same
    fallback shape as corporate_actions.resolve_isin_for_actions."""
    filings = pd.DataFrame({
        "isin": ["INE_STALE_01"], "symbol": ["XCO"], "known_date": [dt.date(2024, 6, 15)],
    })
    symbol_obs = _symbol_obs([("XCO", "2024-01-01", "INE_REAL_01")])  # only a much-earlier observation exists
    out = resolve_isin_for_filings(filings, symbol_obs)
    assert out.iloc[0]["isin"] == "INE_REAL_01"


def test_burnpur_gap_window_filing_resolves_backward_not_forward():
    """Real case (checked live, 2026-09-26): BURNPUR's old ISIN
    (INE817H01014) last traded 2025-01-29; its new ISIN (INE817H01022)
    did not start trading until 2026-08-11, a 559-day gap. Two real
    filings -- known 2025-02-10 and 2025-03-11 -- fall inside that gap.
    The first version of resolve_isin_for_filings (forward-preferred,
    copied from resolve_isin_for_actions without re-deriving whether that
    preference still held) resolved both to the NEW isin -- an identity
    BURNPUR would not trade under for another 17 months. Backward-first
    must resolve to the OLD isin: the one actually trading as of each
    filing's known_date, matching every other point-in-time convention in
    this codebase."""
    symbol_obs = _symbol_obs([
        ("BURNPUR", "2025-01-20", "INE817H01014"),
        ("BURNPUR", "2025-01-29", "INE817H01014"),
        ("BURNPUR", "2026-08-11", "INE817H01022"),
        ("BURNPUR", "2026-08-20", "INE817H01022"),
    ])
    filings = pd.DataFrame({
        "isin": ["INE817H01014", "INE817H01014"],  # the feed's own value here was already correct
        "symbol": ["BURNPUR", "BURNPUR"],
        "known_date": [dt.date(2025, 2, 10), dt.date(2025, 3, 11)],
    })
    out = resolve_isin_for_filings(filings, symbol_obs)
    assert (out["isin"] == "INE817H01014").all()  # OLD isin -- never the not-yet-existing NEW one


def test_forward_fallback_still_works_when_nothing_precedes_known_date():
    """A company's very first filing, disclosed before this warehouse's
    price history for it begins -- backward finds nothing, so forward must
    still be used rather than leaving the row unresolved."""
    symbol_obs = _symbol_obs([("NEWCO", "2024-06-01", "INE_FIRST_01")])
    filings = pd.DataFrame({
        "isin": ["INE_WRONG_01"], "symbol": ["NEWCO"], "known_date": [dt.date(2024, 1, 1)],
    })
    out = resolve_isin_for_filings(filings, symbol_obs)
    assert out.iloc[0]["isin"] == "INE_FIRST_01"
