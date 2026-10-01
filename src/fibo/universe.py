"""Point-in-time top-50-by-turnover universe for the Fibonacci/ORB intraday
study, annually reconstituted -- NOT today's Nifty 50 (survivorship bias:
today's index membership reflects which companies grew/survived to be in
it today, so applying it to 2017 would silently drop every large name that
later failed or fell out and only keep past winners).

RECONSTITUTION RULE, stated explicitly because the instruction ("top 50 by
trailing median turnover ... reconstituted annually, point-in-time") does
not fully pin down the window boundaries:
    Membership for calendar year Y = the top 50 entities by MEDIAN DAILY
    TURNOVER over calendar year Y-1 (series='EQ' only), ranked descending,
    ties broken by entity_id ascending (deterministic, stated rather than
    silent). That membership is held FIXED for every trading date in year Y
    and reconstituted again at the next Jan 1.
This is "trailing median turnover, reconstituted annually" read as a full
prior-calendar-year lookback (like an index committee reweighting off the
preceding year's traded value) rather than a trailing N-trading-day rolling
window recomputed continuously (that convention already exists elsewhere in
this project -- src/swing/universe.py's historical_liquidity_tercile -- and
serves a different purpose: a continuously-rolling tercile for a 5-day-
horizon rule, not a stable annual membership list for an intraday study that
needs to know its tradeable universe for a whole year at a time before
downloading a year of 1-minute bars for it). If a trailing-N-trading-day
window anchored at each Jan 1 was intended instead, this is a one-line
change (replace the calendar-year groupby with a fixed trading-day lookback).

TURNOVER, not adjusted price, is the ranking quantity -- deliberately read
straight from prices_eod (RAW close x volume, in rupees), not through
entity_panel/adjustment_factors. Turnover in rupee terms is invariant to a
split (a 1:5 split multiplies volume by 5 and divides price by 5; the
rupee value traded that day is unchanged), so no split adjustment applies
here at all, unlike every price-level computation in this project.

NO GUARD from data_layer.holdout is applied: FINDINGS.md Section 7 retired
the sealed historical holdout (2025-03-19 onward) for every hypothesis
sharing this warehouse, so reading the full turnover history through the
present is not a leak. The Fibo study's OWN forward-only dev/test boundary
(a new, unrelated concept) is decided separately, in Step 1/5 of this
module's build, once intraday data depth is known.

FIRST YEAR GAP: the warehouse starts 2016-01-01, so calendar year 2016 has
no preceding year to rank against -- 2016 is dropped from the reconstituted
universe rather than backfilled with a partial-year proxy. Flagged, not
silently worked around.

LAST YEAR GAP, same shape, other end: a prior_year whose own data does not
reach November is treated as still IN PROGRESS, not a complete year, and is
excluded from ranking -- otherwise the warehouse's current partial year
(e.g. data through September) would get ranked as if it were a full year
and used to mint a membership list for a year that has not started yet.
Found live: an early version of this function produced a 2027 membership
list off 2026's Jan-Sep data alone.
"""
from __future__ import annotations

import duckdb
import pandas as pd

TOP_N = 50


def _entity_daily_turnover(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """[entity_id, trade_date, turnover] -- every EQ-series trading day,
    entity-aware (spans ISIN lineage chains the same way every other
    entity-level read in this project does), raw turnover, no adjustment."""
    df = con.execute(
        """
        SELECT l.entity_id, p.trade_date, p.turnover
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        WHERE p.series = 'EQ' AND p.turnover IS NOT NULL AND p.turnover > 0
        """
    ).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def reconstitute_annually(con: duckdb.DuckDBPyConnection, top_n: int = TOP_N) -> pd.DataFrame:
    """[year, entity_id, median_turnover_prior_year, rank] -- one row per
    (year, member) for every calendar year that has a preceding year of
    data. `year` is the year the membership APPLIES to (Y), ranked off
    calendar year Y-1's median daily turnover."""
    turnover = _entity_daily_turnover(con)
    turnover["cal_year"] = turnover["trade_date"].dt.year
    median_by_entity_year = (
        turnover.groupby(["entity_id", "cal_year"])["turnover"].median().reset_index()
        .rename(columns={"turnover": "median_turnover", "cal_year": "prior_year"})
    )

    # a year only counts as a valid ranking base once its own data reaches
    # November -- otherwise the warehouse's current in-progress year would
    # mint a membership list for a year that has not started yet
    max_date_by_year = turnover.groupby("cal_year")["trade_date"].max()
    complete_years = {y for y, last in max_date_by_year.items() if last.month >= 11}

    years_present = sorted(y for y in turnover["cal_year"].unique() if y in complete_years)
    rows = []
    for prior_year in years_present:
        year = prior_year + 1
        candidates = median_by_entity_year[median_by_entity_year["prior_year"] == prior_year].copy()
        if candidates.empty:
            continue
        candidates = candidates.sort_values(
            ["median_turnover", "entity_id"], ascending=[False, True]
        ).reset_index(drop=True)
        candidates["rank"] = candidates.index + 1
        top = candidates.head(top_n).copy()
        top["year"] = year
        rows.append(top[["year", "entity_id", "median_turnover", "rank"]].rename(
            columns={"median_turnover": "median_turnover_prior_year"}))
    if not rows:
        return pd.DataFrame(columns=["year", "entity_id", "median_turnover_prior_year", "rank"])
    return pd.concat(rows, ignore_index=True)


def membership_report(universe: pd.DataFrame) -> pd.DataFrame:
    """[year, n_members, n_added, n_dropped] -- member count per year and
    how many names changed vs. the prior year's list (added = in this year,
    not in the previous; dropped = the reverse). First reconstituted year
    has n_added = n_members, n_dropped = 0 by construction (no prior list)."""
    years = sorted(universe["year"].unique())
    rows = []
    prev_set: set[str] = set()
    for y in years:
        cur_set = set(universe.loc[universe["year"] == y, "entity_id"])
        added = len(cur_set - prev_set)
        dropped = len(prev_set - cur_set) if prev_set else 0
        rows.append({"year": y, "n_members": len(cur_set), "n_added": added, "n_dropped": dropped})
        prev_set = cur_set
    return pd.DataFrame(rows)


def is_member(universe: pd.DataFrame, entity_id: str, trade_date) -> bool:
    """Point-in-time membership check for one entity on one date: was it in
    that date's calendar-year membership list."""
    year = pd.Timestamp(trade_date).year
    return not universe[(universe["year"] == year) & (universe["entity_id"] == entity_id)].empty
