"""Monthly leader/follower roster construction (Decisions 6, 7, 10, 18,
23, 24).

- Annual top-200 universe: reused unchanged from `fibo.universe`
  (Decision 23 §3.7 verified this step unaffected by every lead-lag-
  specific decision in this family).
- Ranking date: the first date of `fibo.lead_lag.calendar
  .first_session_of_month`'s governing/primary-sample calendar for that
  month (Decision 24) -- never raw `prices_eod` or `bars_1min` presence.
- Turnover source: `prices_eod.turnover` exclusively (Decision 23).
- Window: each entity's last 60 qualifying observations with
  `trade_date < ranking_date`, strictly -- the ranking date's own
  turnover is excluded (Decision 23).
- Split: top `ceil(0.2 * n_eligible)` by median turnover = leaders;
  remainder = followers (Section 6/7). Deterministic tie-break: median
  descending, then `entity_id` ascending.
- Fixed identity (Decision 18): this module computes membership once,
  for one ranking date; callers must not re-invoke it mid-month or
  filter its output by signal-time availability -- that would violate
  Decision 18 and is the caller's responsibility to avoid (see
  `tests/test_lead_lag_roster.py` for a regression test asserting this
  module's own output is independent of any signal-time input).
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import duckdb
import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fibo.universe import reconstitute_annually, effective_universe  # noqa: E402

from .calendar import is_exchange_session, HolidayCalendarMissing

LEAD_LAG_TOP_N = 200  # this family's own annual universe size -- NOT fibo.universe's module default (50)
TRAILING_WINDOW = 60
LEADER_FRACTION = 0.20
STUB_YEAR = 2016


class InvalidRankingDate(ValueError):
    """Raised when a caller passes a `ranking_date` that is not a
    genuine governing exchange session (Decision 24). Deliberately does
    not consult `bars_1min` or any archive-presence source -- only the
    pure calendar truth in `calendar.py`."""


def build_annual_universe(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """[year, entity_id, median_turnover_prior_year, rank] -- the
    lead-lag family's annual top-200 universe, reused unchanged from
    `fibo.universe`, explicitly overriding its own module default
    (top_n=50, the Fibonacci/ORB study's parameter)."""
    universe = reconstitute_annually(con, top_n=LEAD_LAG_TOP_N)
    return effective_universe(universe, stub_year=STUB_YEAR)


@dataclass(frozen=True)
class MonthlyRoster:
    ranking_date: dt.date
    entities: pd.DataFrame  # [entity_id, median_turnover, rank, tier]
    n_eligible: int
    n_leaders: int
    n_followers: int
    ineligible_entity_ids: tuple[str, ...]  # in annual universe, <60 qualifying obs


def build_monthly_roster(
    con: duckdb.DuckDBPyConnection,
    ranking_date: dt.date,
    universe_year_df: pd.DataFrame,
) -> MonthlyRoster:
    """Rank `universe_year_df`'s entities by trailing-60-qualifying-
    observation median `prices_eod.turnover`, using only observations
    with `trade_date < ranking_date` (Decision 23, strict exclusion of
    the ranking date's own turnover). Top `ceil(0.2*n_eligible)` =
    leaders; remainder = followers.

    `ranking_date` must be a genuine governing exchange session (Decision
    24) -- validated here via `calendar.is_exchange_session`, which is
    purely calendar-based and never consults `bars_1min`. A caller
    cannot silently construct a roster against an arbitrary date that is
    not actually a trading session; `InvalidRankingDate` is raised
    instead. An unresolvable holiday-calendar year (`HolidayCalendarMissing`)
    is re-raised as `InvalidRankingDate` with the original cause attached,
    rather than silently treating the date as valid or invalid."""
    try:
        valid = is_exchange_session(ranking_date)
    except HolidayCalendarMissing as exc:
        raise InvalidRankingDate(
            f"cannot validate ranking_date {ranking_date}: holiday calendar "
            f"does not cover its year"
        ) from exc
    if not valid:
        raise InvalidRankingDate(
            f"ranking_date {ranking_date} is not a governing exchange session"
        )

    entity_ids = tuple(universe_year_df["entity_id"].tolist())
    if not entity_ids:
        return MonthlyRoster(ranking_date, pd.DataFrame(columns=["entity_id", "median_turnover", "rank", "tier"]), 0, 0, 0, ())

    placeholders = ",".join(["?"] * len(entity_ids))
    q = f"""
        SELECT l.entity_id, p.trade_date, p.turnover
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        WHERE p.series = 'EQ' AND p.turnover IS NOT NULL AND p.turnover > 0
          AND p.trade_date < ?
          AND l.entity_id IN ({placeholders})
        QUALIFY ROW_NUMBER() OVER (PARTITION BY l.entity_id ORDER BY p.trade_date DESC) <= ?
    """
    df = con.execute(q, [ranking_date, *entity_ids, TRAILING_WINDOW]).fetchdf()
    counts = df.groupby("entity_id").size()
    eligible_ids = set(counts[counts >= TRAILING_WINDOW].index)
    ineligible_ids = tuple(sorted(set(entity_ids) - eligible_ids))

    elig_df = df[df["entity_id"].isin(eligible_ids)]
    medians = (
        elig_df.groupby("entity_id")["turnover"].median().reset_index()
        .rename(columns={"turnover": "median_turnover"})
    )
    medians = medians.sort_values(
        ["median_turnover", "entity_id"], ascending=[False, True]
    ).reset_index(drop=True)
    n_eligible = len(medians)
    n_leaders = math.ceil(LEADER_FRACTION * n_eligible) if n_eligible else 0
    medians["rank"] = medians.index + 1
    medians["tier"] = ["leader" if r <= n_leaders else "follower" for r in medians["rank"]]

    return MonthlyRoster(
        ranking_date=ranking_date,
        entities=medians,
        n_eligible=n_eligible,
        n_leaders=n_leaders,
        n_followers=n_eligible - n_leaders,
        ineligible_entity_ids=ineligible_ids,
    )


def roster_tier_size(roster: MonthlyRoster, tier: str) -> int:
    """Decision 19's threshold denominator: the ORIGINAL monthly
    roster-tier size (before any Stage A exclusion), not the frozen
    subset's own size."""
    if tier == "leader":
        return roster.n_leaders
    if tier == "follower":
        return roster.n_followers
    raise ValueError(f"unknown tier: {tier!r}")


def tier_entity_ids(roster: MonthlyRoster, tier: str) -> list[str]:
    return roster.entities.loc[roster.entities["tier"] == tier, "entity_id"].tolist()
