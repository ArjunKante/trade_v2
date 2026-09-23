"""Targeted synthetic tests for the fundamental-snapshot research tool
(src/reports/fundamental_snapshot.py) -- a reading tool, not a study, so
this covers the pieces most likely to silently mislead a reader rather than
every metric exhaustively: CAGR/TTM arithmetic, the negative-equity ROE
sign trap, and graceful NOT-AVAILABLE behavior when a tag is entirely
missing (e.g. a bank without RevenueFromOperations).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reports.fundamental_snapshot import (
    growth_metrics, profitability_metrics, returns_metrics, _asof_ttm_value, _rolling_ttm,
)


def _quarters(values, start="2020-03-31"):
    dates = pd.date_range(start, periods=len(values), freq="QE")
    known = dates + pd.Timedelta(days=15)
    return pd.DataFrame({"period_end": dates, "known_date": known, "value": values})


def test_rolling_ttm_sums_trailing_four_and_nans_when_incomplete():
    df = _quarters([100, 110, 120, 130, 140, 150])
    out = _rolling_ttm(df)
    assert pd.isna(out["ttm"].iloc[2])  # only 3 quarters behind it (itself + 2)
    assert out["ttm"].iloc[3] == 100 + 110 + 120 + 130
    assert out["ttm"].iloc[5] == 120 + 130 + 140 + 150


def _pl_with_growth(n_years, growth_rate, start_revenue=1000):
    """n_years of quarterly revenue/ni growing at growth_rate annually,
    flat EBIT/fc/da so TTM math is exercised without extra noise."""
    n_q = n_years * 4
    revenue = [start_revenue * (1 + growth_rate) ** (i / 4) for i in range(n_q)]
    dates = pd.date_range("2018-03-31", periods=n_q, freq="QE")
    known = dates + pd.Timedelta(days=20)
    df = pd.DataFrame({
        "period_end": dates, "known_date": known,
        "revenue": revenue, "ni": [r * 0.1 for r in revenue],
        "pbt": [r * 0.12 for r in revenue], "fc": [r * 0.01 for r in revenue], "da": [r * 0.05 for r in revenue],
    })
    df["ebit"] = df["pbt"] + df["fc"]
    df["ebitda"] = df["ebit"] + df["da"]
    for col in ["revenue", "ni", "ebit", "ebitda", "fc"]:
        df[f"{col}_ttm"] = df[col].rolling(4, min_periods=4).sum()
    df["n_q_ttm"] = df["revenue"].rolling(4, min_periods=1).count().astype(int)
    return df


def test_growth_metrics_recovers_known_cagr():
    pl = _pl_with_growth(n_years=6, growth_rate=0.20)  # 20%/yr for 6 years
    shares = pd.DataFrame({"period_end": pl["period_end"], "known_date": pl["known_date"], "shares": [1000] * len(pl)})
    g = growth_metrics(pl, shares)
    assert g["available"]
    assert g["revenue_cagr_3y"] == pytest.approx(0.20, abs=0.01)
    assert g["revenue_cagr_5y"] == pytest.approx(0.20, abs=0.01)
    assert g["revenue_yoy"] == pytest.approx(0.20, abs=0.01)
    # EPS grows at the same rate here since shares is flat
    assert g["eps_cagr_3y"] == pytest.approx(0.20, abs=0.01)


def test_growth_metrics_reports_unavailable_on_empty_pl():
    g = growth_metrics(pd.DataFrame(), pd.DataFrame())
    assert g["available"] is False
    assert "reason" in g


def test_profitability_margins_computed_from_ttm():
    pl = _pl_with_growth(n_years=2, growth_rate=0.0)
    p = profitability_metrics(pl)
    assert p["available"]
    # constant ratios by construction: ebit=0.12+0.01=0.13 of revenue, ebitda=0.13+0.05=0.18, net=0.10
    assert p["ebit_margin"] == pytest.approx(0.13, abs=1e-6)
    assert p["ebitda_margin"] == pytest.approx(0.18, abs=1e-6)
    assert p["net_margin"] == pytest.approx(0.10, abs=1e-6)


def test_asof_ttm_value_handles_empty_frame_without_keyerror():
    # This is the exact shape that crashed on banks (no RevenueFromOperations
    # tag -> build_quarterly_pl returns pd.DataFrame() with no columns at all).
    value, source_pe = _asof_ttm_value(pd.DataFrame(), "ni_ttm", pd.Timestamp("2024-03-31"))
    assert value is None and source_pe is None


def test_returns_metrics_flags_negative_equity_instead_of_a_misleading_positive_roe():
    pl = _pl_with_growth(n_years=2, growth_rate=0.0)
    pl.loc[pl.index[-1], "ni_ttm"] = -400  # trailing loss
    annual = pd.DataFrame({
        "period_end": [pl["period_end"].iloc[-1]],
        "known_date": [pl["known_date"].iloc[-1]],
        "equity": [-1000.0],   # negative net worth
        "assets": [5000.0], "curL": [1000.0],
    })
    ret = returns_metrics(annual, pl)
    row = ret["by_year"].iloc[0]
    assert bool(row["roe_negative_equity"]) is True
    assert pd.isna(row["roe"])  # NOT a deceptive positive number from loss/negative-equity


def test_returns_metrics_reports_roe_normally_with_positive_equity():
    pl = _pl_with_growth(n_years=2, growth_rate=0.0)
    annual = pd.DataFrame({
        "period_end": [pl["period_end"].iloc[-1]],
        "known_date": [pl["known_date"].iloc[-1]],
        "equity": [2000.0], "assets": [5000.0], "curL": [1000.0],
    })
    ret = returns_metrics(annual, pl)
    row = ret["by_year"].iloc[0]
    assert bool(row["roe_negative_equity"]) is False
    assert row["roe"] == pytest.approx(row["roe"])  # a real number, not NaN
    assert not pd.isna(row["roe"])
