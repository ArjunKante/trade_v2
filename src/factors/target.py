"""Forward 63-trading-day return target, on entity-adjusted close, per
entity's own trading-day index (not calendar days)."""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZON_DAYS = 63

# Same gap-awareness issue as factors.momentum/factors.lowvol, applied to the
# TARGET this time: a row-based shift(-horizon) reaches forward however many
# calendar days the entity's next `horizon` trading rows actually span. If a
# stale trading gap falls inside that span, the "forward 63-day return" isn't
# a 63-trading-day return at all -- and because every factor's IC is measured
# against this same target, a contaminated target would corrupt every
# factor's IC simultaneously, not just one. Checked and fixed here rather
# than assumed clean.
STALE_GAP_DAYS = 5


def _max_gap_in_forward_window(panel: pd.DataFrame, horizon: int) -> pd.Series:
    """flag[t] = max(is_gap[t+1 .. t+horizon]) -- the gap flags at the rows
    the forward window from t actually passes through, never including row
    t's own incoming gap (irrelevant to a window starting AFTER t)."""
    p = panel.sort_values(["entity_id", "trade_date"])
    prev_date = p.groupby("entity_id")["trade_date"].shift(1)
    gap_days = (p["trade_date"] - prev_date).dt.days
    is_gap = (gap_days > STALE_GAP_DAYS).astype(int)
    is_gap_next = is_gap.groupby(p["entity_id"]).shift(-1)
    rev = is_gap_next[::-1]
    rolled = rev.groupby(p["entity_id"][::-1]).rolling(horizon, min_periods=1).max()
    return rolled.reset_index(level=0, drop=True)[::-1]


def compute_forward_return(panel: pd.DataFrame, horizon: int = HORIZON_DAYS) -> pd.DataFrame:
    """Returns [entity_id, trade_date (=prediction_time), eval_date
    (=evaluation_time, the real calendar date the target is realized on),
    fwd_return]. eval_date is what PurgedKFold needs as evaluation_times --
    it must be a REAL date, not prediction_time + a fixed calendar offset,
    since the horizon is defined in trading days.

    NaN'd out whenever a >STALE_GAP_DAYS gap falls inside the forward
    window -- see module docstring."""
    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    grp = p.groupby("entity_id", group_keys=False)
    p["future_close"] = grp["adjusted_close"].shift(-horizon)
    p["eval_date"] = grp["trade_date"].shift(-horizon)
    p["fwd_return"] = p["future_close"] / p["adjusted_close"] - 1

    gap_flag = _max_gap_in_forward_window(p, horizon)
    p.loc[gap_flag.values == 1, "fwd_return"] = np.nan

    return p[["entity_id", "trade_date", "eval_date", "fwd_return"]].dropna(subset=["fwd_return", "eval_date"])
