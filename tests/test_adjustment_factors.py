"""Adjustment factors: two independent implementations must agree, the
factor table must have more than one distinct value (the regression test
for the prior project's silent factor=1.0-everywhere bug), and adjusted
prices must be continuous across a real ISIN-change-plus-split boundary.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_connection
from data_layer.adjustment import compute_factors_sql, compute_factors_python, read_adjusted_prices

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"


@pytest.fixture(scope="module")
def con():
    if not WAREHOUSE.exists():
        pytest.skip("real warehouse not present")
    return get_connection(WAREHOUSE)


def test_sql_and_python_implementations_agree_on_bajfinance(con):
    """Full-warehouse comparison (4.69M rows) is run manually, not on every
    test invocation (13s pure-Python pass); this restricts to the one entity
    with the most complex chain (3 ISINs, 2 transitions) as a fast regression
    check that still exercises the real disagreement-prone case."""
    sql_full = compute_factors_sql(con)
    py_full = compute_factors_python(con)

    sql_sub = sql_full[sql_full["entity_id"] == "INE296A01016"]
    py_sub = py_full[py_full["entity_id"] == "INE296A01016"]
    merged = sql_sub.merge(py_sub, on=["entity_id", "trade_date"], suffixes=("_sql", "_py"))
    assert len(merged) == len(sql_sub) == len(py_sub)
    assert (merged["factor_sql"] - merged["factor_py"]).abs().max() < 1e-9


def test_factor_table_has_more_than_one_distinct_value(con):
    """The prior project's regression test, ported directly: adjustment_
    factors being uniformly 1.0 means corporate actions were never wired in,
    and nothing else catches that silently."""
    n_distinct = con.execute("SELECT COUNT(DISTINCT factor) FROM adjustment_factors").fetchone()[0]
    assert n_distinct > 1


def test_adjusted_close_continuous_across_isin_change_plus_split(con):
    """The exact case this whole layer exists to fix: BAJFINANCE's raw close
    drops ~90% at the 2025-06-13 -> 2025-06-16 ISIN change (a real 10x split/
    bonus), but the entity-adjusted close must move smoothly."""
    df = read_adjusted_prices(con, "INE296A01016")
    window = df[(df["trade_date"] >= "2025-06-10") & (df["trade_date"] <= "2025-06-20")].sort_values("trade_date")
    assert window["isin"].nunique() == 2  # genuinely spans the ISIN boundary

    day_returns = window["adjusted_close"].pct_change().dropna()
    assert day_returns.abs().max() < 0.05  # no day exceeds a 5% move; the raw series has a ~90% one

    raw_day_returns = window["raw_close"].pct_change().dropna()
    assert raw_day_returns.abs().max() > 0.8  # confirm the raw series DOES have the fake crash we're fixing


def test_adjusted_close_continuous_across_2016_boundary_too(con):
    df = read_adjusted_prices(con, "INE296A01016")
    window = df[(df["trade_date"] >= "2016-09-05") & (df["trade_date"] <= "2016-09-13")].sort_values("trade_date")
    day_returns = window["adjusted_close"].pct_change().dropna()
    # real trading noise around the ex_date, not a clean lab fixture -- bound loose enough to
    # accommodate genuine one-day volatility while still clearly distinguishing from a fake ~90% crash
    assert day_returns.abs().max() < 0.10

    raw_day_returns = window["raw_close"].pct_change().dropna()
    assert raw_day_returns.abs().max() > 0.8  # confirm the raw series has the fake crash being fixed


def test_factor_is_forward_only_never_applies_before_ex_date_wrongly():
    """factor(d) must use STRICT inequality (ex_date > d): the action's own
    ex_date already carries the post-action raw price (confirmed against
    real BAJFINANCE data), so it must not be adjusted a second time."""
    import pandas as pd
    from unittest.mock import MagicMock
    from data_layer.adjustment import compute_factors_python

    fake_con = MagicMock()

    def fake_execute(sql, *args, **kwargs):
        result = MagicMock()
        if "corporate_actions" in sql:
            result.fetchdf.return_value = pd.DataFrame([
                {"entity_id": "E1", "ex_date": pd.Timestamp("2020-06-16"), "ratio": 10.0},
            ])
        else:
            result.fetchdf.return_value = pd.DataFrame([
                {"entity_id": "E1", "trade_date": pd.Timestamp("2020-06-15")},  # day before ex_date
                {"entity_id": "E1", "trade_date": pd.Timestamp("2020-06-16")},  # ex_date itself
                {"entity_id": "E1", "trade_date": pd.Timestamp("2020-06-17")},  # day after
            ])
        return result

    fake_con.execute.side_effect = fake_execute
    out = compute_factors_python(fake_con).set_index("trade_date")["factor"]
    assert out.loc[pd.Timestamp("2020-06-15")] == pytest.approx(0.1)   # before ex_date: adjusted down
    assert out.loc[pd.Timestamp("2020-06-16")] == pytest.approx(1.0)   # ex_date itself: NOT adjusted (already post-action)
    assert out.loc[pd.Timestamp("2020-06-17")] == pytest.approx(1.0)   # after ex_date: not adjusted
