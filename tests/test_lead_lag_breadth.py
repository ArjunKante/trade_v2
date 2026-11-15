"""Decision 10: follower-breadth diagnostic. Uses a SYNTHETIC in-memory
DuckDB table (not the real `bars_1min`) to verify the SQL present-valid
expression matches `validity.is_present_valid` exactly across every
bar category (D, A1, B1, E, null, inf), and that the breadth
aggregation/threshold logic is correct. No real database, no primary
regression, no S_L/R_F/Momentum_F/Y anywhere in this file."""
import datetime as dt
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lead_lag import breadth
from lead_lag.validity import is_present_valid

D = dt.date(2026, 6, 1)

# (open, high, low, close, volume, expected_category_label)
BAR_CASES = [
    (100.0, 101.0, 99.0, 100.5, 500.0, "D_positive_volume"),
    (100.0, 100.0, 100.0, 100.0, 0.0, "A1_zero_vol_flat"),
    (100.0, 101.0, 99.0, 100.5, 0.0, "B1_zero_vol_nonflat"),
    (-5.0, -5.0, -5.0, -5.0, 0.0, "E_negative_ohlc"),
    (None, 101.0, 99.0, 100.5, 500.0, "E_null_open"),
    (100.0, 101.0, 99.0, 100.5, None, "E_null_volume"),
    (100.0, 101.0, 99.0, 100.5, float("inf"), "E_inf_volume"),
    (100.0, 101.0, 99.0, 100.5, float("nan"), "E_nan_volume"),
    (100.0, 99.0, 101.0, 100.5, 500.0, "E_high_less_than_low"),
    (102.0, 101.0, 99.0, 100.5, 500.0, "E_open_outside_range"),
]


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE bars_1min (
            entity_id VARCHAR, trade_date DATE, ts TIMESTAMP,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE
        )
    """)
    yield c
    c.close()


def test_present_valid_sql_matches_python_validity_rule_for_every_category(con):
    for i, (o, h, l, cl, v, label) in enumerate(BAR_CASES):
        con.execute(
            "INSERT INTO bars_1min VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [f"E{i}", D, dt.datetime.combine(D, dt.time(9, 15)), o, h, l, cl, v],
        )
    df = con.execute(f"SELECT entity_id, CASE WHEN {breadth.PRESENT_VALID_SQL} THEN 1 ELSE 0 END AS pv FROM bars_1min ORDER BY entity_id").fetchdf()
    for i, (o, h, l, cl, v, label) in enumerate(BAR_CASES):
        expected = is_present_valid(o, h, l, cl, v)
        actual = bool(df.loc[df["entity_id"] == f"E{i}", "pv"].iloc[0])
        assert actual == expected, f"mismatch for case {label}: sql={actual} python={expected}"


def test_compute_follower_breadth_counts_present_valid_only(con):
    # minute 1: E0 present-valid (D), E1 present-valid (A1), E2 B1 (not valid)
    rows = [
        ("E0", D, dt.time(9, 15), 100.0, 101.0, 99.0, 100.5, 500.0),
        ("E1", D, dt.time(9, 15), 50.0, 50.0, 50.0, 50.0, 0.0),
        ("E2", D, dt.time(9, 15), 50.0, 51.0, 49.0, 50.5, 0.0),
    ]
    for entity_id, trade_date, t, o, h, l, cl, v in rows:
        con.execute("INSERT INTO bars_1min VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [entity_id, trade_date, dt.datetime.combine(trade_date, t), o, h, l, cl, v])
    df = breadth.compute_follower_breadth(con, ("E0", "E1", "E2"), D, D)
    assert len(df) == 1
    assert df.iloc[0]["n_present_valid"] == 2
    assert df.iloc[0]["n_follower_tier"] == 3
    assert df.iloc[0]["breadth"] == pytest.approx(2 / 3)


def test_compute_follower_breadth_empty_entity_list_returns_empty_df(con):
    df = breadth.compute_follower_breadth(con, (), D, D)
    assert df.empty
    assert list(df.columns) == ["trade_date", "ts", "n_present_valid", "n_follower_tier", "breadth"]


def test_compute_follower_breadth_date_range_is_respected(con):
    for day_offset, t in [(0, dt.time(9, 15)), (1, dt.time(9, 15))]:
        d = D + dt.timedelta(days=day_offset)
        con.execute("INSERT INTO bars_1min VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ["E0", d, dt.datetime.combine(d, t), 100.0, 101.0, 99.0, 100.5, 500.0])
    df = breadth.compute_follower_breadth(con, ("E0",), D, D)  # only day 0
    assert len(df) == 1
    assert pd.Timestamp(df.iloc[0]["trade_date"]).date() == D


def test_summarize_breadth_below_floor_counts():
    df = pd.DataFrame({
        "trade_date": [D] * 4, "ts": [1, 2, 3, 4],
        "n_present_valid": [160, 112, 111, 160],
        "n_follower_tier": [160, 160, 160, 160],
    })
    df["breadth"] = df["n_present_valid"] / df["n_follower_tier"]
    summary = breadth.summarize_breadth(df, floor=0.70)
    assert summary.n_minutes == 4
    assert summary.n_below_floor == 1  # only 111/160 = 0.69375 < 0.70
    assert summary.pct_below_floor == pytest.approx(25.0)
    assert summary.floor == 0.70


def test_summarize_breadth_handles_empty_dataframe():
    df = pd.DataFrame(columns=["trade_date", "ts", "n_present_valid", "n_follower_tier", "breadth"])
    summary = breadth.summarize_breadth(df)
    assert summary.n_minutes == 0
    assert summary.n_below_floor == 0


def test_this_module_never_computes_any_primary_regression_quantity():
    import inspect
    from lead_lag import breadth as breadth_module
    import lead_lag.regression as regression_module
    src = inspect.getsource(breadth_module)
    for forbidden in ("fit_ols", "fit_primary_regression", "import regression"):
        assert forbidden not in src
    assert not hasattr(breadth_module, "regression_module")
    assert regression_module.fit_ols.__module__ != breadth_module.__name__
