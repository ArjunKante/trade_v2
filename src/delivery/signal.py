"""Abnormal delivery % signal (up-days only), quarterly, DEV-only --
`PREREGISTRATION_DELIVERY.md` Section 1. This module implements that
specification exactly; no parameter here is independently tunable
(amendment 4 -- one spec, no retries).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MEASUREMENT_DAYS = 21
BASELINE_DAYS = 60
MIN_UP_DAYS = 5
DECILE_FRAC = 0.10  # same as factors.momentum's own top-decile cut, PREREGISTRATION.md

# Same threshold factors.target/factors.momentum use for their own
# gap-awareness, applied here to the 21/60-day windows instead of the
# 252-day lookback -- PREREGISTRATION_DELIVERY.md Section 1,
# "Gap-awareness, OUR extension of an existing convention".
STALE_GAP_DAYS = 5


def _is_unexplained_jump_row(p: pd.DataFrame, unexplained_jump_dates: dict | None) -> pd.Series:
    """Duplicated from factors.target._is_unexplained_jump_row -- same
    Bug #1/#11 guard, same self-contained-module convention every factor
    module in this project already follows."""
    if not unexplained_jump_dates:
        return pd.Series(False, index=p.index)
    flag = pd.Series(False, index=p.index)
    for eid, dates in unexplained_jump_dates.items():
        mask = (p["entity_id"] == eid) & (p["trade_date"].isin(dates))
        flag |= mask
    return flag


def build_up_day_panel(panel: pd.DataFrame, delivery: pd.DataFrame, *,
                        unexplained_jump_dates: dict) -> pd.DataFrame:
    """`panel`: entity_id, trade_date, adjusted_close -- one row per
    entity-day it actually traded (NOT reindexed to a master calendar;
    `PREREGISTRATION_DELIVERY.md` Section 1 windows are defined on each
    entity's own trading-day index). `delivery`: entity_id, trade_date,
    delivery_percent, already resolved via isin_lineage (Section 0).

    A flagged (entity, date) row is DROPPED before any rolling
    computation touches it -- the same convention Darvas/Box/FVG apply
    (`combined_unexplained_jump_dates`'s own docstring) -- so a fabricated
    price jump cannot manufacture a false up-day and cannot silently
    reappear later as an unflagged neighbor of a dropped day.

    Returns panel + `is_up_day` (True/False/NaN -- NaN where the prior
    row is unavailable, too far back in calendar time, or either row was
    dropped above) + `usable` (bool, same condition) + `delivery_percent`
    (left-joined, NaN where no delivery row exists for that entity-day).
    """
    p = panel.sort_values(["entity_id", "trade_date"]).reset_index(drop=True).copy()
    flagged = _is_unexplained_jump_row(p, unexplained_jump_dates)
    p = p[~flagged].reset_index(drop=True)

    grp = p.groupby("entity_id", group_keys=False)
    prev_close = grp["adjusted_close"].shift(1)
    prev_date = grp["trade_date"].shift(1)
    gap_days = (p["trade_date"] - prev_date).dt.days
    usable = prev_close.notna() & (gap_days <= STALE_GAP_DAYS)
    p["is_up_day"] = np.where(usable, p["adjusted_close"] > prev_close, np.nan)
    p["usable"] = usable

    p = p.merge(delivery[["entity_id", "trade_date", "delivery_percent"]],
                on=["entity_id", "trade_date"], how="left")
    return p


def abnormal_delivery_at(up_day_panel: pd.DataFrame, rebalance_date: pd.Timestamp) -> pd.DataFrame:
    """One row per entity with ANY history before `rebalance_date`.
    Measurement window = that entity's own trailing `MEASUREMENT_DAYS`
    rows strictly before `rebalance_date`; baseline window = the
    `BASELINE_DAYS` rows immediately before THAT -- non-overlapping by
    construction (amendment 2). `abnormal_delivery` = mean delivery_percent
    on up-days with a delivery_percent value in the measurement window,
    minus the same in the baseline window. NaN (`eligible=False`) unless
    BOTH windows have at least `MIN_UP_DAYS` such days -- never silently
    zero, never silently imputed."""
    before = up_day_panel[up_day_panel["trade_date"] < rebalance_date]
    rows = []
    for entity_id, g in before.groupby("entity_id", sort=False):
        g = g.sort_values("trade_date")
        measurement = g.tail(MEASUREMENT_DAYS)
        remaining = g.iloc[: max(len(g) - MEASUREMENT_DAYS, 0)]
        baseline = remaining.tail(BASELINE_DAYS)

        m_up = measurement[(measurement["is_up_day"] == True) & measurement["delivery_percent"].notna()]  # noqa: E712
        b_up = baseline[(baseline["is_up_day"] == True) & baseline["delivery_percent"].notna()]  # noqa: E712

        n_m, n_b = len(m_up), len(b_up)
        eligible = n_m >= MIN_UP_DAYS and n_b >= MIN_UP_DAYS
        abnormal = (m_up["delivery_percent"].mean() - b_up["delivery_percent"].mean()) if eligible else np.nan
        rows.append({
            "entity_id": entity_id,
            "rebalance_date": rebalance_date,
            "n_measurement_rows": len(measurement),
            "n_baseline_rows": len(baseline),
            "n_up_measurement": n_m,
            "n_up_baseline": n_b,
            "abnormal_delivery": abnormal,
            "eligible": bool(eligible),
        })
    return pd.DataFrame(rows)


def select_top_decile(signal_at_date: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Same inclusive `>= quantile(1 - DECILE_FRAC)` cut
    `scripts/run_holdout_study1_lineage_check.py` uses for momentum's own
    top decile (ties at the cutoff are ALL included, not broken --
    reused verbatim, not independently decided, per `PREREGISTRATION_
    DELIVERY.md`'s 'same universe/strategy as momentum')."""
    pool = signal_at_date[signal_at_date["eligible"]]
    if pool.empty:
        return pool, float("nan")
    cutoff = pool["abnormal_delivery"].quantile(1 - DECILE_FRAC)
    sel = pool[pool["abnormal_delivery"] >= cutoff]
    return sel, cutoff


def rebalance_dates(all_trade_dates: list, horizon_days: int, *, delivery_max_date=None) -> list:
    """Quarterly, non-overlapping: every 63rd trading day of the full
    available index (`all_dates[::63]`, the identical construction
    momentum's own holdout script uses), kept only if it has enough prior
    history for both windows (>= MEASUREMENT_DAYS + BASELINE_DAYS trading
    days) and enough forward data remaining (>= horizon_days) --
    PREREGISTRATION_DELIVERY.md Section 1, 'Rebalance dates'.

    BUG FIXED (found running Section 10 step 4, before any aggregate
    number was reported as the DEV result): this function originally
    strided over the FULL price panel's own date range, which extends
    past `delivery_eod`'s own 2016-2025 coverage into 2026 (price data
    continues; delivery data does not). That produced two degenerate
    rebalance dates (2026-03-18, 2026-06-23) whose entire 21-day
    measurement window falls past delivery coverage, with pools of 12
    and 1 eligible entities respectively -- a data-coverage artifact, not
    a real reading. `delivery_max_date` (required by every caller in this
    study, no default) clips the candidate dates to delivery_eod's own
    max date BEFORE striding, exactly as `PREREGISTRATION_DELIVERY.md`
    Section 1 already specified in words ("the full trading-day index
    intersected with delivery_eod's own coverage") -- the prose was
    correct; this function's first implementation did not match it."""
    dates = sorted(all_trade_dates)
    strided = dates[::63]
    out = []
    for d in strided:
        if delivery_max_date is not None and d > pd.Timestamp(delivery_max_date):
            continue  # clipped against delivery_eod's own coverage, not the (longer) price panel's
        idx = dates.index(d)
        if idx >= MEASUREMENT_DAYS + BASELINE_DAYS and idx + horizon_days < len(dates):
            out.append(d)
    return out
