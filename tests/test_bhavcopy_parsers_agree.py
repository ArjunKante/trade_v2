"""The dual-format overlap window (2024-01-01 to 2024-07-05, both legacy and
UDiFF genuinely published) is a free correctness check: parse the same real
trading day through both parsers and the ISIN-matched rows must agree. This
is exactly the check the prior project's DESIGN.md flagged as something
"most people never notice exists" -- it catches a column-mapping mistake in
either parser that unit tests on synthetic fixtures would never surface.

Network test: fetches real files. Skipped if the network call fails so the
regular test suite doesn't depend on internet access.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.prices_nse import fetch_raw_zip, parse_bhavcopy_zip, SOURCE_LEGACY, SOURCE_UDIFF

OVERLAP_DAY = dt.date(2024, 7, 5)  # inside the verified overlap window, a real Friday trading day
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "prices" / "_overlap_check"


@pytest.fixture(scope="module")
def both_parses():
    try:
        legacy_path, _ = fetch_raw_zip(OVERLAP_DAY, RAW_DIR, source=SOURCE_LEGACY)
        udiff_path, _ = fetch_raw_zip(OVERLAP_DAY, RAW_DIR, source=SOURCE_UDIFF)
    except Exception as e:
        pytest.skip(f"network fetch failed, skipping overlap cross-check: {e}")
    legacy_df = parse_bhavcopy_zip(legacy_path, SOURCE_LEGACY, OVERLAP_DAY, series_include=["EQ"])
    udiff_df = parse_bhavcopy_zip(udiff_path, SOURCE_UDIFF, OVERLAP_DAY, series_include=["EQ"])
    return legacy_df, udiff_df


def test_same_isins_present_in_both_formats(both_parses):
    legacy_df, udiff_df = both_parses
    legacy_isins = set(legacy_df["isin"])
    udiff_isins = set(udiff_df["isin"])
    # allow a small tolerance for edge-of-universe listing/delisting timing differences
    overlap = legacy_isins & udiff_isins
    assert len(overlap) / max(len(legacy_isins), 1) > 0.98


def test_ohlcv_identical_for_isin_matched_rows(both_parses):
    legacy_df, udiff_df = both_parses
    merged = legacy_df.merge(udiff_df, on="isin", suffixes=("_legacy", "_udiff"))
    assert len(merged) > 1000  # sanity: the merge actually matched real rows, not an empty join

    for col in ["open", "high", "low", "close", "prev_close"]:
        diff = (merged[f"{col}_legacy"] - merged[f"{col}_udiff"]).abs()
        assert diff.max() < 0.01, f"{col} mismatch between legacy and UDiFF parse of {OVERLAP_DAY}"

    vol_diff = (merged["volume_legacy"] - merged["volume_udiff"]).abs()
    assert vol_diff.max() == 0, "volume mismatch between legacy and UDiFF parse"
