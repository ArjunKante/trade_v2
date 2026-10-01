"""Regression tests for src/fibo/download.py: chunking, the
truncation-detect-and-retry logic (the actual mechanism protecting the
Step 3 download from Step 1's silent-truncation pitfall), and the
download-plan builder."""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.download import (
    chunk_date_ranges, is_truncated, fetch_chunk_with_retry, build_download_plan,
    looks_rate_limited, looks_token_expired,
)


def test_looks_rate_limited_matches_documented_403_phrasing():
    assert looks_rate_limited("Access denied because of exceeding rate limit")
    assert looks_rate_limited("Too many requests")
    assert not looks_rate_limited("Invalid Token")
    assert not looks_rate_limited("SUCCESS")


def test_looks_token_expired_matches_the_real_error_seen_live():
    # "Invalid Token" is the EXACT message Angel One returned when this
    # project's own session expired mid-download (scripts/
    # fibo_download_intraday.py's module docstring) -- this is a
    # regression test for that specific real string, not just the general shape.
    assert looks_token_expired("Invalid Token")
    assert looks_token_expired("Session Expired")
    assert not looks_token_expired("Access denied because of exceeding rate limit")
    assert not looks_token_expired("SUCCESS")


def test_rate_limit_and_token_expiry_keyword_sets_do_not_overlap():
    """These two failure shapes get handled completely differently (stop
    vs. re-login-and-retry) -- a message that matched both would be
    ambiguous. Sanity-checks the two keyword lists share no word that
    could double-fire on the same real message."""
    from fibo.download import RATE_LIMIT_KEYWORDS, TOKEN_EXPIRY_KEYWORDS
    assert not set(RATE_LIMIT_KEYWORDS) & set(TOKEN_EXPIRY_KEYWORDS)


def test_chunk_date_ranges_splits_inclusive_nonoverlapping():
    ranges = chunk_date_ranges(dt.date(2020, 1, 1), dt.date(2020, 1, 10), chunk_days=4)
    assert ranges == [
        (dt.date(2020, 1, 1), dt.date(2020, 1, 4)),
        (dt.date(2020, 1, 5), dt.date(2020, 1, 8)),
        (dt.date(2020, 1, 9), dt.date(2020, 1, 10)),
    ]


def test_chunk_date_ranges_exact_multiple():
    ranges = chunk_date_ranges(dt.date(2020, 1, 1), dt.date(2020, 1, 8), chunk_days=4)
    assert ranges == [(dt.date(2020, 1, 1), dt.date(2020, 1, 4)), (dt.date(2020, 1, 5), dt.date(2020, 1, 8))]


def test_is_truncated_true_when_first_candle_far_later_than_requested_start():
    assert is_truncated(dt.date(2020, 1, 1), dt.date(2020, 6, 1))


def test_is_truncated_false_within_slack_for_weekend_start():
    # requested start on a Saturday; first real trading candle two days later -- not truncation
    assert not is_truncated(dt.date(2020, 1, 4), dt.date(2020, 1, 6))


def _candle(date_str):
    return [f"{date_str}T09:15:00+05:30", 1.0, 1.0, 1.0, 1.0, 100]


def test_fetch_chunk_with_retry_returns_data_untouched_when_not_truncated():
    def call_fn(start, end):
        return [_candle(str(start)), _candle(str(end))], None

    data, note = fetch_chunk_with_retry(call_fn, dt.date(2020, 1, 1), dt.date(2020, 1, 25))
    assert note is None
    assert len(data) == 2


def test_fetch_chunk_with_retry_splits_and_reassembles_on_truncation():
    """Simulates Angel's real behavior: a big request silently returns only
    a recent slice. The retry logic must detect this, split the range, and
    end up with candles covering the WHOLE originally-requested span.

    This scenario genuinely requires TWO levels of splitting (a 31-day
    range splits into two ~15-16 day halves, each of which is STILL over
    the fake truncation threshold and must split again) -- found live
    during Step 3's real download: an earlier version of
    fetch_chunk_with_retry checked `if lerr is not None` on a recursive
    call's SECOND return value to decide failure, but a successful nested
    split also returns a non-None second value (its own informational
    note) -- so a successful two-level split was wrongly reported as a
    failure and its real candles silently discarded. `data is not None`
    and the earliest-date check below are the assertions that catch that
    exact regression; the original version of this test only checked the
    note text and would NOT have caught it."""
    calls = []

    def call_fn(start, end):
        calls.append((start, end))
        span = (end - start).days + 1
        if span > 10:
            # truncate: pretend only the last 5 days came back
            fake_start = end - dt.timedelta(days=4)
            return [_candle(str(fake_start)), _candle(str(end))], None
        return [_candle(str(start)), _candle(str(end))], None

    data, note = fetch_chunk_with_retry(call_fn, dt.date(2020, 1, 1), dt.date(2020, 1, 31), min_chunk_days=3)
    assert data is not None, "a successful (possibly multi-level) split must never be reported as a failure"
    assert len(calls) > 3, "this scenario must actually exercise more than one level of splitting"
    dates = sorted(dt.date.fromisoformat(c[0][:10]) for c in data)
    assert dates[0] == dt.date(2020, 1, 1), "the earliest requested date must survive reassembly, not be silently dropped"
    assert note is not None and "split" in note


def test_fetch_chunk_with_retry_nested_split_success_not_mistaken_for_parent_error():
    """Minimal, direct reproduction of the bug above: the LEFT half's own
    recursive call must itself split (and thus return a non-None note) for
    this to exercise the regression -- the parent must not mistake that
    note for an error and discard the left half's real data."""
    def call_fn(start, end):
        span = (end - start).days + 1
        if span > 8:
            return [_candle(str(end - dt.timedelta(days=3))), _candle(str(end))], None
        return [_candle(str(start)), _candle(str(end))], None

    # 20-day range: splits into two 10-day halves, each of which is STILL >8
    # and must split again -- so both children return (data, note-not-None)
    data, note = fetch_chunk_with_retry(call_fn, dt.date(2021, 1, 1), dt.date(2021, 1, 20), min_chunk_days=3)
    assert data is not None
    dates = sorted(dt.date.fromisoformat(c[0][:10]) for c in data)
    assert dates[0] == dt.date(2021, 1, 1)


def test_fetch_chunk_with_retry_raises_if_truncation_persists_at_min_size():
    # first candle is always WAY beyond the requested start (100 days), so
    # is_truncated fires at every recursion depth, all the way down to
    # min_chunk_days -- unlike a fixed end-anchored fake, this can't
    # coincidentally fall within the slack tolerance once chunks get small.
    def always_truncated(start, end):
        return [_candle(str(start + dt.timedelta(days=100)))], None

    with pytest.raises(RuntimeError):
        fetch_chunk_with_retry(always_truncated, dt.date(2020, 1, 1), dt.date(2020, 1, 10), min_chunk_days=3)


def test_fetch_chunk_with_retry_propagates_real_errors():
    def erroring(start, end):
        return None, "some real API error"

    data, err = fetch_chunk_with_retry(erroring, dt.date(2020, 1, 1), dt.date(2020, 1, 5))
    assert data is None
    assert err == "some real API error"


def test_build_download_plan_uses_next_years_list_for_the_stub_period():
    universe = pd.DataFrame({
        "year": [2017, 2017], "entity_id": ["A", "B"],
        "median_turnover_prior_year": [1.0, 1.0], "rank": [1, 2],
    })
    entity_to_token = {"A": "111", "B": "222"}
    plan = build_download_plan(universe, entity_to_token, dev_start=dt.date(2016, 10, 4), full_end=dt.date(2017, 12, 31))
    stub_rows = plan[plan.year == 2016]
    assert set(stub_rows.entity_id) == {"A", "B"}
    assert (stub_rows["start"] == dt.date(2016, 10, 4)).all()
    assert (stub_rows["end"] == dt.date(2016, 12, 31)).all()
    full_2017 = plan[plan.year == 2017]
    assert set(full_2017.entity_id) == {"A", "B"}


def test_build_download_plan_excludes_entities_without_a_token():
    universe = pd.DataFrame({
        "year": [2020, 2020], "entity_id": ["HAS_TOKEN", "NO_TOKEN"],
        "median_turnover_prior_year": [1.0, 1.0], "rank": [1, 2],
    })
    entity_to_token = {"HAS_TOKEN": "999"}
    plan = build_download_plan(universe, entity_to_token, dev_start=dt.date(2020, 1, 1), full_end=dt.date(2020, 12, 31))
    assert set(plan.entity_id) == {"HAS_TOKEN"}
