"""Synthetic correctness tests for TTM computation and point-in-time shares
outstanding, run before real quarterly XBRL data is available (the full
extraction is a ~15 hour background job) so the logic itself is verified
independent of when that data lands.
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factors.fundamentals_factors import compute_ttm, pit_shares_outstanding_asof


def _quarterly(rows):
    df = pd.DataFrame(rows, columns=["isin", "period_end", "consolidated", "value", "known_date"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["known_date"] = pd.to_datetime(df["known_date"])
    return df


def test_ttm_sums_exactly_four_trailing_quarters():
    q = _quarterly([
        ("A", "2023-03-31", "Consolidated", 100, "2023-05-01"),
        ("A", "2023-06-30", "Consolidated", 110, "2023-08-01"),
        ("A", "2023-09-30", "Consolidated", 120, "2023-11-01"),
        ("A", "2023-12-31", "Consolidated", 130, "2024-02-01"),
        ("A", "2024-03-31", "Consolidated", 140, "2024-05-01"),
    ])
    as_of = pd.DataFrame({"isin": ["A"], "trade_date": [pd.Timestamp("2024-06-01")]})
    out = compute_ttm(q, as_of)
    row = out.iloc[0]
    assert row["n_quarters_summed"] == 4
    assert row["ttm_value"] == 110 + 120 + 130 + 140  # the 4 most recent KNOWN quarters, not the first 4


def test_ttm_reports_fewer_than_four_when_history_incomplete():
    q = _quarterly([
        ("A", "2023-09-30", "Consolidated", 100, "2023-11-01"),
        ("A", "2023-12-31", "Consolidated", 110, "2024-02-01"),
    ])
    as_of = pd.DataFrame({"isin": ["A"], "trade_date": [pd.Timestamp("2024-03-01")]})
    out = compute_ttm(q, as_of)
    row = out.iloc[0]
    assert row["n_quarters_summed"] == 2  # honestly reported, not padded or dropped


def test_ttm_never_uses_a_quarter_not_yet_known():
    """A quarter filed AFTER as_of must not appear in the TTM sum, even if
    its period_end is chronologically earlier than as_of."""
    q = _quarterly([
        ("A", "2023-03-31", "Consolidated", 100, "2023-05-01"),
        ("A", "2023-06-30", "Consolidated", 110, "2023-08-01"),
        ("A", "2023-09-30", "Consolidated", 120, "2023-11-01"),
        ("A", "2023-12-31", "Consolidated", 999, "2025-01-01"),  # filed 13 months late
    ])
    as_of = pd.DataFrame({"isin": ["A"], "trade_date": [pd.Timestamp("2024-01-15")]})
    out = compute_ttm(q, as_of)
    row = out.iloc[0]
    assert row["n_quarters_summed"] == 3  # the late one is correctly excluded
    assert 999 not in [row["ttm_value"]]
    assert row["ttm_value"] == 100 + 110 + 120


def test_ttm_prefers_consolidated_over_standalone_per_quarter():
    q = _quarterly([
        ("A", "2023-12-31", "Non-Consolidated", 50, "2024-02-01"),
        ("A", "2023-12-31", "Consolidated", 90, "2024-02-01"),
    ])
    as_of = pd.DataFrame({"isin": ["A"], "trade_date": [pd.Timestamp("2024-03-01")]})
    out = compute_ttm(q, as_of)
    assert out.iloc[0]["ttm_value"] == 90  # not 50, and not 140 (never summed across types)


def test_shares_outstanding_uses_most_recent_known_value_not_future():
    shares = pd.DataFrame({
        "isin": ["A", "A"],
        "period_end": pd.to_datetime(["2023-12-31", "2024-03-31"]),
        "known_date": pd.to_datetime(["2024-02-01", "2024-05-01"]),
        "shares_outstanding": [1000.0, 2000.0],
    })
    as_of = pd.DataFrame({"isin": ["A"], "trade_date": [pd.Timestamp("2024-04-01")]})
    out = pit_shares_outstanding_asof(shares, as_of)
    assert out.iloc[0]["shares_outstanding"] == 1000.0  # the 2024-03-31 count (known 2024-05-01) isn't visible yet
