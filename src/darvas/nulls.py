"""The three nulls, PREREGISTRATION_DARVAS.md "Nulls" section.

All three reuse `darvas.resolution.run_position` for exit/trailing
mechanics (never a re-derived loop) and `darvas.costs`/`box_theory.
inference` for sizing/cost/bootstrap -- the same machinery the real
strategy itself uses.

Sub-rule 2's formula in Section 2 is `close[D] >= entry_box_top +
RUN_THRESHOLD_R * (entry_price - initial_stop)`. For all three nulls, a
synthetic entry has no real box, so there is no `entry_box_top` to speak
of -- the "Nulls" section's own stated reasoning for keeping Sub-rule 2 at
all ("which depends only on entry price and rho, both well-defined for a
null draw") already implies the natural substitution used throughout this
module: `entry_box_top := entry_price`. This is not a new amendment -- it
is the literal reading of that sentence, applied consistently to all
three nulls' own use of Sub-rule 2.
"""
from __future__ import annotations

import bisect

import numpy as np
import pandas as pd

from darvas.resolution import run_position

TIMING_NULL_WINDOW_DAYS = 20


# ======================================================================
# TIMING null
# ======================================================================

def build_timing_pool(trades: pd.DataFrame, entity_context: dict) -> list[dict]:
    """One entry per real trade: {entity_id, box (the REAL entry box,
    unchanged -- same bottom_price, same top_confirm_idx), ctx}. A trade
    whose entity has no context (should not happen -- entity_context is
    built for every entity simulate_entity ran) is dropped with a note,
    never silently skipped without counting."""
    pool = []
    missing = 0
    for _, tr in trades.iterrows():
        ctx = entity_context.get(tr["entity_id"])
        if ctx is None:
            missing += 1
            continue
        box = tr["stop_history"][0]["box"]  # the real entry box, Section 0's INITIAL stop_history row
        pool.append({"entity_id": tr["entity_id"], "box": box, "ctx": ctx})
    return pool, missing


def timing_null_seed_mean(pool: list[dict], rng: np.random.Generator) -> float:
    """PREREGISTRATION_DARVAS.md "Nulls"/TIMING: for each real trade,
    replace the entry date with a day drawn uniformly from the 20 trading
    days starting at that box's OWN top_confirm_idx -- NOT the real entry
    date, which can be much later once the bottom, then the breakout
    itself, are both waited out. Same real box's own bottom = initial
    stop (unchanged). Same exit mechanics as the real strategy
    (`use_new_box_rule=True`) -- Section 2's own trailing rules in full,
    run forward from this null's own random entry."""
    rs = []
    for item in pool:
        ctx, box = item["ctx"], item["box"]
        top_confirm_idx = box["top_confirm_idx"]
        offset = rng.integers(0, TIMING_NULL_WINDOW_DAYS)
        entry_idx = top_confirm_idx + offset
        if entry_idx >= ctx["n"] - 1:
            continue  # the random draw landed past the available data -- no trade this seed
        entry_price = float(ctx["opens"][entry_idx])
        initial_stop = float(box["bottom_price"])
        if entry_price <= initial_stop:
            continue
        complete_boxes = ctx["complete_boxes"]
        cb_ptr = bisect.bisect_right([cb["bottom_confirm_idx"] for cb in complete_boxes], entry_idx)
        trade = run_position(ctx["dates"], ctx["opens"], ctx["closes"], ctx["n"], item["entity_id"],
                              entry_idx, entry_price, initial_stop, float(box["top_price"]),
                              box, complete_boxes, cb_ptr, use_new_box_rule=True)
        if trade is not None:
            rs.append(trade["net_r"])
    return float(np.mean(rs)) if rs else float("nan")


# ======================================================================
# SELECTION null
# ======================================================================

def build_selection_pool_by_month(entity_context: dict, universe: pd.DataFrame) -> dict:
    """{(year, month) -> list of (entity_id, day_idx)}, restricted to
    actual declared universe members for that (entity, year) -- "random
    stock-days from the same universe-year population" (the Nulls
    section), independent of whether a real box ever existed there."""
    members = set(zip(universe["year"], universe["entity_id"]))
    pool: dict[tuple[int, int], list[tuple[str, int]]] = {}
    for entity_id, ctx in entity_context.items():
        dates = ctx["dates"]
        for i in range(ctx["n"]):
            d = pd.Timestamp(dates[i])
            if (d.year, entity_id) not in members:
                continue
            pool.setdefault((d.year, d.month), []).append((entity_id, i))
    return pool


def selection_null_seed_mean(pool_by_month: dict, trades_by_month: dict, rho_pool: np.ndarray,
                              entity_context: dict, rng: np.random.Generator) -> float:
    """PREREGISTRATION_DARVAS.md "Nulls"/SELECTION: for each (year, month)
    with real trades, draw the SAME count of random (entity, day) pairs
    from that month's own pool; stop distance drawn (with replacement)
    from the real sample's own pooled rho distribution; Sub-rule 2 only
    (module docstring)."""
    rs = []
    for ym, count in trades_by_month.items():
        candidates = pool_by_month.get(ym)
        if not candidates or count == 0:
            continue
        idx = rng.integers(0, len(candidates), size=count)
        rhos = rho_pool[rng.integers(0, len(rho_pool), size=count)]
        for k in range(count):
            entity_id, day_idx = candidates[idx[k]]
            ctx = entity_context[entity_id]
            entry_idx = day_idx
            if entry_idx >= ctx["n"] - 1:
                continue
            entry_price = float(ctx["opens"][entry_idx])
            rho = float(rhos[k])
            initial_stop = entry_price * (1 - rho)
            if entry_price <= initial_stop:
                continue
            trade = run_position(ctx["dates"], ctx["opens"], ctx["closes"], ctx["n"], entity_id,
                                  entry_idx, entry_price, initial_stop, entry_price,  # entry_box_top := entry_price
                                  None, [], 0, use_new_box_rule=False)
            if trade is not None:
                rs.append(trade["net_r"])
    return float(np.mean(rs)) if rs else float("nan")


# ======================================================================
# MOMENTUM null -- THE PRIMARY ONE
# ======================================================================

def build_momentum_lookup(panel: pd.DataFrame, unexplained_jump_dates: dict) -> pd.DataFrame:
    """[trade_date, entity_id, momentum] -- `factors.momentum.
    compute_momentum_12_1`, unchanged, called on the FULL (pre jump-row-
    drop) panel, since that function's own NaN-based exclusion (not a row
    drop) expects the row-based shift() to see every calendar row in
    place (PREREGISTRATION_DARVAS.md Section 0's own reuse note). Indexed
    by trade_date for a fast per-date slice."""
    from factors.momentum import compute_momentum_12_1
    mom = compute_momentum_12_1(panel[["entity_id", "trade_date", "adjusted_close"]],
                                 unexplained_jump_dates=unexplained_jump_dates)
    mom = mom.rename(columns={"value": "momentum"}).dropna(subset=["momentum"])
    return mom.set_index("trade_date").sort_index()


def top_momentum_entity(mom_by_date: pd.DataFrame, date: pd.Timestamp, year: int,
                         universe: pd.DataFrame, exclude_entity: str | None = None) -> str | None:
    """The universe-year member with the highest momentum_12_1 as of
    `date` -- point-in-time, no lookahead (compute_momentum_12_1 itself
    only ever looks backward). The real Darvas stock is NOT excluded by
    default (Nulls section: "the real Darvas stock is not excluded...
    since no exclusion was specified") -- `exclude_entity` exists only so
    a caller COULD exclude it, never used that way by the DEV-run script
    itself, kept for completeness/testing."""
    if date not in mom_by_date.index:
        return None
    day_rows = mom_by_date.loc[[date]]  # list form: always a DataFrame, even for a single match
    members = set(universe.loc[universe["year"] == year, "entity_id"])
    day_rows = day_rows[day_rows["entity_id"].isin(members)]
    if exclude_entity is not None:
        day_rows = day_rows[day_rows["entity_id"] != exclude_entity]
    if day_rows.empty:
        return None
    # positional argmax, not .loc[idxmax()] -- day_rows' index is the
    # (duplicated) date itself, so a label-based lookup would return
    # every row sharing that date instead of the single best one
    best = day_rows["momentum"].to_numpy().argmax()
    return str(day_rows["entity_id"].iloc[best])


def momentum_null_trades(trades: pd.DataFrame, mom_by_date: pd.DataFrame, universe: pd.DataFrame,
                          entity_context: dict) -> pd.DataFrame:
    """PREREGISTRATION_DARVAS.md "Nulls"/MOMENTUM: one alternate trade per
    real trade, entering the SAME date's top-momentum universe-year
    member instead of the real Darvas stock. Same rho (hence same sizing
    formula), Sub-rule 2 only. A SINGLE deterministic alternate set (no
    seeds), run through `box_theory.inference.day_clustered_bootstrap`
    by the caller -- same non-random-alternate shape PREREGISTRATION_
    IPO.md Section 8's own SELECTION null already uses."""
    rows = []
    for _, tr in trades.iterrows():
        entry_date, year, rho = tr["entry_date"], int(tr["year"]), float(tr["rho"])
        alt_entity = top_momentum_entity(mom_by_date, entry_date, year, universe)
        if alt_entity is None:
            continue
        ctx = entity_context.get(alt_entity)
        if ctx is None:
            continue
        idx = int(np.searchsorted(ctx["dates"], entry_date.to_numpy()))
        if idx >= ctx["n"] or pd.Timestamp(ctx["dates"][idx]) != entry_date:
            continue  # the top-momentum stock didn't trade exactly this date -- no alternate for this real trade
        entry_price = float(ctx["opens"][idx])
        initial_stop = entry_price * (1 - rho)
        if entry_price <= initial_stop or idx >= ctx["n"] - 1:
            continue
        trade = run_position(ctx["dates"], ctx["opens"], ctx["closes"], ctx["n"], alt_entity,
                              idx, entry_price, initial_stop, entry_price,  # entry_box_top := entry_price
                              None, [], 0, use_new_box_rule=False)
        if trade is not None:
            trade["real_entity_id"] = tr["entity_id"]
            rows.append(trade)
    return pd.DataFrame(rows)
