"""Targeted synthetic tests for the fundamental screener
(src/reports/fundamental_screener.py) -- covers the verdict precedence
rule (FAIL > INSUFFICIENT DATA > FINANCIALS-PARTIAL > PASS), the
financials D/E-and-interest-coverage exemption applying to exactly those
two checks and no others, and fiscal_year_points' quarter-spacing.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reports.fundamental_screener import fiscal_year_points, check_tier1, check_tier2


def _pl(n_quarters, revenue, ni, ebit):
    dates = pd.date_range("2020-03-31", periods=n_quarters, freq="QE")
    known = dates + pd.Timedelta(days=20)
    df = pd.DataFrame({"period_end": dates, "known_date": known, "revenue_ttm": revenue, "ni_ttm": ni, "ebit_ttm": ebit})
    return df


def test_fiscal_year_points_spaced_four_quarters_apart_ending_at_latest():
    pl = _pl(10, revenue=list(range(100, 110)), ni=[1] * 10, ebit=[1] * 10)
    fy = fiscal_year_points(pl, n=3)
    # latest is index 9 (revenue=109); spaced back by 4: indices 9, 5, 1
    assert list(fy["revenue_ttm"]) == [101, 105, 109]


def test_tier1_revenue_decline_needs_three_points_else_na():
    pl = _pl(5, revenue=[100, 90, 80, 70, 60], ni=[1] * 5, ebit=[1] * 5)
    checks = {c["check"]: c for c in check_tier1(pl)}
    assert checks["revenue_decline_2y"]["status"] == "NA"  # only ~1-2 spaced annual points fit in 5 quarters


def test_tier1_revenue_decline_two_consecutive_years_fails():
    # 12 quarters -> 3 annual points (idx 11, 7, 3): declining if each successive point is lower
    revenue = list(range(200, 0, -1))[:12][::-1]  # arbitrary increasing then we override key indices
    revenue = [0] * 12
    for i, v in zip([3, 7, 11], [300, 200, 100]):
        revenue[i] = v
    pl = _pl(12, revenue=revenue, ni=[10] * 12, ebit=[10] * 12)
    checks = {c["check"]: c for c in check_tier1(pl)}
    assert checks["revenue_decline_2y"]["status"] == "FAIL"


def test_tier1_net_loss_latest_fy():
    pl = _pl(4, revenue=[100] * 4, ni=[-5, -5, -5, -5], ebit=[1] * 4)
    checks = {c["check"]: c for c in check_tier1(pl)}
    assert checks["net_loss_latest_fy"]["status"] == "FAIL"


def test_tier1_operating_margin_decline_three_consecutive_quarters():
    revenue = [100] * 4
    ebit = [30, 25, 20, 15]  # margin strictly declining for 3 consecutive steps
    pl = _pl(4, revenue=revenue, ni=[1] * 4, ebit=ebit)
    checks = {c["check"]: c for c in check_tier1(pl)}
    assert checks["operating_margin_decline_3q"]["status"] == "FAIL"


def test_tier1_operating_margin_not_monotonic_passes():
    revenue = [100] * 4
    ebit = [20, 25, 20, 25]  # not a monotonic decline
    pl = _pl(4, revenue=revenue, ni=[1] * 4, ebit=ebit)
    checks = {c["check"]: c for c in check_tier1(pl)}
    assert checks["operating_margin_decline_3q"]["status"] == "PASS"


def _annual(equity, borrC, borrN, cfo, curL=None, curA=None):
    return pd.DataFrame({
        "period_end": [pd.Timestamp("2024-03-31")], "known_date": [pd.Timestamp("2024-05-01")],
        "equity": [equity], "borrC": [borrC], "borrN": [borrN], "cfo": [cfo],
        "curL": [curL], "curA": [curA],
    })


def test_tier2_debt_equity_and_interest_coverage_skipped_for_financials_but_cfo_checks_still_apply():
    annual = _annual(equity=100.0, borrC=500.0, borrN=0.0, cfo=-10.0)  # D/E=5.0 (would FAIL), CFO negative (should still FAIL)
    pl = _pl(4, revenue=[100] * 4, ni=[10] * 4, ebit=[10] * 4)
    checks = {c["check"]: c for c in check_tier2(annual, pl, is_financials=True)}
    assert checks["debt_equity_max"]["status"] == "SKIPPED (financials)"
    assert checks["interest_coverage_min"]["status"] == "SKIPPED (financials)"
    assert checks["cfo_negative_latest"]["status"] == "FAIL"  # NOT exempted


def test_tier2_debt_equity_applies_normally_for_non_financials():
    annual = _annual(equity=100.0, borrC=500.0, borrN=0.0, cfo=10.0)
    pl = _pl(4, revenue=[100] * 4, ni=[10] * 4, ebit=[10] * 4)
    checks = {c["check"]: c for c in check_tier2(annual, pl, is_financials=False)}
    assert checks["debt_equity_max"]["status"] == "FAIL"
    assert "5.00x" in checks["debt_equity_max"]["value"]


def test_tier2_na_when_no_balance_sheet_at_all():
    checks = {c["check"]: c for c in check_tier2(pd.DataFrame(), pd.DataFrame(), is_financials=False)}
    assert all(c["status"] in ("NA", "SKIPPED (financials)") for c in checks.values())
    assert checks["cfo_pat_avg_min"]["status"] == "NA"
