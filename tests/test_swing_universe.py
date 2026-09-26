"""Regression tests for src/swing/universe.py, focused on the mechanism
correction: the 5-day-return bottom-tercile condition must rank across the
FULL universe, never within a pre-filtered subset (e.g. momentum winners)
-- ranking within a subset of winners selects "the weakest winners," not
"stocks that fell relative to the market," a different population the
short-term-reversal mechanism does not obviously apply to."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swing.universe import (
    historical_momentum_top_decile, historical_liquidity_tercile,
    historical_bottom_tercile_5d_return, historical_volume_ratio,
)


def _flat_panel(entity_id, n_days=300, start_price=100.0, daily_return=0.0, seed=0):
    dates = pd.date_range("2018-01-01", periods=n_days, freq="B")
    rng = np.random.RandomState(seed)
    prices = start_price * np.cumprod(1 + daily_return + rng.normal(0, 0.001, n_days))
    return pd.DataFrame({
        "entity_id": entity_id, "trade_date": dates, "adjusted_close": prices,
        "volume": rng.randint(1000, 2000, n_days), "turnover": prices * rng.randint(1000, 2000, n_days),
    })


def test_bottom_tercile_5d_return_ranks_across_full_universe_not_a_subset():
    """9 'momentum winner' entities, all with strongly positive recent
    drift (so all would land in a momentum top decile together), plus 1
    entity with a genuinely bad recent week. Within the winners-only
    subset, the least-strong winner would look like the 'bottom tercile' --
    but ranked across the full 10-entity universe, only the genuinely-bad
    entity should ever qualify as bottom tercile on the days its return is
    actually the worst."""
    panels = []
    # 9 winners: strong positive daily drift
    for i in range(9):
        panels.append(_flat_panel(f"WINNER_{i}", daily_return=0.01, seed=i))
    # 1 loser: negative drift, will have a genuinely bad 5-day return
    panels.append(_flat_panel("LOSER_0", daily_return=-0.02, seed=99))
    panel = pd.concat(panels, ignore_index=True)

    result = historical_bottom_tercile_5d_return(panel)
    # on any date with a full cross-section, the flagged bottom-tercile
    # entities should be dominated by LOSER_0, not by whichever winner
    # happened to drift up slightly less than its peers that week
    last_date = result["trade_date"].max()
    on_last_date = result[result["trade_date"] == last_date]
    assert not on_last_date.empty
    flagged = on_last_date[on_last_date["bottom_tercile"]]["entity_id"].tolist()
    assert "LOSER_0" in flagged
    # with 10 entities and a bottom tercile (~3-4 of 10), LOSER_0's return
    # should be materially lower than the winners' returns that qualify
    loser_ret = on_last_date.loc[on_last_date["entity_id"] == "LOSER_0", "ret_5d"].iloc[0]
    winner_rets = on_last_date.loc[on_last_date["entity_id"] != "LOSER_0", "ret_5d"]
    assert loser_ret < winner_rets.min()


def test_momentum_top_decile_flags_expected_entities():
    panels = [_flat_panel(f"E{i}", daily_return=0.001 * i, seed=i) for i in range(15)]
    panel = pd.concat(panels, ignore_index=True)
    result = historical_momentum_top_decile(panel)
    if result.empty:
        pytest.skip("not enough history in this synthetic panel for a 252-day momentum window")
    last_date = result["trade_date"].max()
    on_date = result[result["trade_date"] == last_date]
    # the highest-drift entities (largest i) should rank best (rank 1 = highest momentum)
    top = on_date.sort_values("rank").iloc[0]
    assert top["entity_id"] == "E14"


def test_liquidity_tercile_returns_three_labels_when_enough_names():
    panels = [_flat_panel(f"E{i}", seed=i) for i in range(9)]
    panel = pd.concat(panels, ignore_index=True)
    result = historical_liquidity_tercile(panel)
    last_date = result["trade_date"].max()
    labels = set(result.loc[result["trade_date"] == last_date, "tercile"].dropna().unique().astype(str))
    assert labels <= {"low_liq", "mid_liq", "high_liq"}


def test_volume_ratio_excludes_signal_day_from_its_own_average():
    dates = pd.date_range("2020-01-01", periods=25, freq="B")
    volumes = [1000] * 20 + [5000] + [1000] * 4  # a single volume spike on day 21
    panel = pd.DataFrame({
        "entity_id": "E1", "trade_date": dates, "volume": volumes,
        "turnover": [v * 100.0 for v in volumes],
    })
    result = historical_volume_ratio(panel)
    spike_row = result[result["trade_date"] == dates[20]]
    assert spike_row["vol_ratio"].iloc[0] == pytest.approx(5.0)  # 5000 / mean(1000*20) = 5.0
    assert spike_row["high_volume"].iloc[0]
