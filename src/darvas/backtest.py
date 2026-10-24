"""Orchestration layer, PREREGISTRATION_DARVAS.md Sections 0/4: builds the
point-in-time top-200-by-turnover universe (`fibo.universe`, unchanged),
fetches the entity-adjusted daily OHLC panel for every entity EVER a
member of that universe (`fibo.daily_ohlc`, unchanged, full history --
Section 1's own note on why box construction needs real pre-membership
warmup), applies the combined jump guard (`fibo.jump_guard`, unchanged),
slices to whichever window is currently authorized (`darvas.test_seal`),
runs `darvas.resolution.simulate_entity` per entity, and restricts the
resulting trade list to actual declared universe membership (by each
trade's own entry year) before returning -- the same filter-and-guard
pair (`restrict_to_universe` + `assert_universe_membership`) every other
study sharing `fibo.universe` already applies, per that module's own
BUGS.md Bug #11 note on why a backtest must never trade whatever the
archive happens to contain instead of what the specification declares.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from box_theory.costs import band_for_rank
from darvas import test_seal
from darvas.resolution import simulate_entity, sorted_complete_boxes
from fibo.daily_ohlc import build_daily_ohlc_panel
from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.universe import (
    assert_universe_membership, effective_universe, reconstitute_annually, restrict_to_universe,
)

TOP_N = 200
STUB_YEAR = 2016


def build_universe(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Point-in-time top-200-by-turnover, annually reconstituted, with the
    2016 stub year copied from 2017 -- identical to PREREGISTRATION_BOX.md
    Section 2a, same `top_n`."""
    universe = reconstitute_annually(con, top_n=TOP_N)
    return effective_universe(universe, stub_year=STUB_YEAR)


def run_backtest(con: duckdb.DuckDBPyConnection, window_start: dt.date, window_end: dt.date,
                  authorize_test: bool = False, entity_ids: list[str] | None = None,
                  return_context: bool = False) -> dict:
    """Returns {"trades": DataFrame, "boxes": DataFrame, "universe":
    DataFrame, "zero_qty_skips": int, "breakouts_skipped_in_position": int,
    "errors": list}. `trades` is already restricted to declared universe
    membership by (entry year, entity_id); `boxes` carries EVERY box this
    study's state machine ever produced for the entities it ran, including
    ones for years/entities later filtered out of `trades` -- kept
    unrestricted deliberately, since Section 7's report asks for box
    counts (trend-filter failures, never-broke-out, etc.) as a property of
    the price history itself, not gated by universe membership the way a
    TRADE must be.

    `return_context=True` additionally returns "entity_context": {entity_id
    -> {"dates", "opens", "closes", "n", "complete_boxes"}} -- the EXACT
    per-entity arrays and box lists this run's own `simulate_entity` calls
    used, keyed for `darvas.nulls`'s TIMING null (PREREGISTRATION_DARVAS.md
    "Nulls" section) to reuse verbatim via `darvas.resolution.run_position`,
    rather than re-fetching the panel and re-running box detection a second
    time for the same entities."""
    test_seal.guard_date_range(window_start, window_end, authorize_test=authorize_test,
                                caller="darvas.backtest.run_backtest", reason="windowed backtest run")

    universe = build_universe(con)
    all_members = entity_ids if entity_ids is not None else sorted(universe["entity_id"].unique())

    jump_dates = combined_unexplained_jump_dates(con)

    panel = build_daily_ohlc_panel(con, entity_ids=all_members)
    panel = panel[panel["trade_date"] <= pd.Timestamp(window_end)].copy()

    rank_lookup = {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}

    all_trades: list[dict] = []
    all_boxes: list[dict] = []
    zero_qty_total = 0
    skipped_in_position_total = 0
    errors: list[dict] = []
    entity_context: dict = {}

    for entity_id, g in panel.groupby("entity_id", sort=False):
        g = g.sort_values("trade_date").reset_index(drop=True)
        flagged = jump_dates.get(entity_id)
        if flagged:
            g = g[~g["trade_date"].isin(flagged)].reset_index(drop=True)
        try:
            result = simulate_entity(g, entity_id)
        except Exception as e:
            errors.append({"entity_id": entity_id, "error": str(e)})
            continue

        for b in result["boxes"]:
            b2 = dict(b)
            b2["entity_id"] = entity_id
            all_boxes.append(b2)

        for tr in result["trades"]:
            tr["year"] = int(tr["entry_date"].year)
            tr["rank"] = rank_lookup.get((tr["year"], entity_id))
            tr["band"] = band_for_rank(tr["rank"])
            all_trades.append(tr)

        zero_qty_total += result["zero_qty_skips"]
        skipped_in_position_total += result["breakouts_skipped_in_position"]

        if return_context:
            entity_context[entity_id] = {
                "dates": g["trade_date"].to_numpy(), "opens": g["adjusted_open"].to_numpy(),
                "closes": g["adjusted_close"].to_numpy(), "n": len(g),
                "complete_boxes": sorted_complete_boxes(result["boxes"]),
            }

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        before = len(trades_df)
        trades_df = restrict_to_universe(trades_df, universe)
        assert_universe_membership(trades_df, universe, label="darvas trades")
        dropped = before - len(trades_df)
    else:
        dropped = 0

    out = {
        "trades": trades_df, "boxes": pd.DataFrame(all_boxes), "universe": universe,
        "zero_qty_skips": zero_qty_total, "breakouts_skipped_in_position": skipped_in_position_total,
        "non_member_year_trades_dropped": dropped,
        "errors": errors,
    }
    if return_context:
        out["entity_context"] = entity_context
        out["panel"] = panel  # full (pre jump-row-drop) panel, for darvas.nulls' momentum lookup
        out["jump_dates"] = jump_dates
    return out
