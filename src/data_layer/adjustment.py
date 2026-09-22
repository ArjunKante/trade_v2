"""Forward-only price adjustment factors, entity-aware, materialized.

prices_eod is never modified. adjustment_factors is a separate, derived
table: adjusted(d) = raw(d) * factor(d), where

    factor(d) = product over corporate actions (for this entity's full ISIN
                chain, not just one bare ISIN) with ex_date > d, of (1 / ratio)

Entity-aware, not ISIN-aware, because a split recorded against ISIN B must
also adjust prices recorded under ISIN A if A and B are the same company's
earlier and later ISINs (isin_lineage.entity_id) -- otherwise a split at an
ISIN changeover boundary only adjusts half the price series.

Two independent implementations (SQL aggregation, pure Python) are provided
and must be checked against each other by a test -- a single implementation
can validate its own internal consistency but can't catch a shared
conceptual mistake in the formula itself. This mirrors the prior project's
own practice for the same reason it states: "a single implementation cannot
verify itself."

Materialization is an explicit, separately-run step (scripts/materialize_
adjustment_factors.py). Nothing in this module is called from a read path.
The prior project shipped adjustment_factors as uniformly factor=1.0 for
months because corporate actions were never ingested, and no test caught
it -- see test_adjustment_factors.py::test_factor_table_has_more_than_one_
distinct_value for the regression test that would have caught it on day one.
"""
from __future__ import annotations

import bisect
import datetime as dt

import duckdb
import numpy as np
import pandas as pd

SOURCE_NAME = "ADJUSTMENT_FACTORS_MATERIALIZED"


def compute_factors_sql(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Implementation 1: set-based SQL aggregation using the
    product-via-log-sum-exp identity (product(x_i) = exp(sum(ln(x_i))),
    valid here since every ratio is strictly positive)."""
    sql = """
    WITH actions_by_entity AS (
        SELECT l.entity_id, ca.ex_date, ca.ratio
        FROM corporate_actions ca
        JOIN isin_lineage l ON ca.isin = l.isin
    ),
    combined_actions AS (
        SELECT entity_id, ex_date, EXP(SUM(LN(ratio))) AS combined_ratio
        FROM actions_by_entity
        GROUP BY entity_id, ex_date
    ),
    entity_dates AS (
        SELECT DISTINCT l.entity_id, p.trade_date
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
    )
    SELECT
        ed.entity_id,
        ed.trade_date,
        COALESCE(EXP(SUM(LN(1.0 / ca.combined_ratio))), 1.0) AS factor
    FROM entity_dates ed
    LEFT JOIN combined_actions ca
      ON ed.entity_id = ca.entity_id AND ca.ex_date > ed.trade_date
    GROUP BY ed.entity_id, ed.trade_date
    """
    return con.execute(sql).fetchdf()


def compute_factors_python(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Implementation 2: pure Python/pandas, no SQL aggregation, no log-sum-exp
    trick -- a genuinely different computation path, not a restatement of the
    same SQL in another syntax."""
    actions = con.execute(
        """
        SELECT l.entity_id, ca.ex_date, ca.ratio
        FROM corporate_actions ca JOIN isin_lineage l ON ca.isin = l.isin
        """
    ).fetchdf()
    entity_dates = con.execute(
        """
        SELECT DISTINCT l.entity_id, p.trade_date
        FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
        """
    ).fetchdf()

    actions["ex_date"] = pd.to_datetime(actions["ex_date"])
    entity_dates["trade_date"] = pd.to_datetime(entity_dates["trade_date"])

    # combine same-day multi-component actions (e.g. bonus+split same ex_date) by direct multiplication
    combined = actions.groupby(["entity_id", "ex_date"], as_index=False)["ratio"].prod()

    # per entity: sorted ex_dates and a suffix product of (1/ratio), so factor(d) for
    # any d is "the suffix product starting at the first ex_date strictly after d"
    suffix_by_entity: dict[str, tuple[list, list]] = {}
    for entity_id, grp in combined.groupby("entity_id"):
        grp = grp.sort_values("ex_date")
        ex_dates = grp["ex_date"].tolist()
        inv_ratios = (1.0 / grp["ratio"]).tolist()
        suffix = [1.0] * (len(inv_ratios) + 1)
        for i in range(len(inv_ratios) - 1, -1, -1):
            suffix[i] = suffix[i + 1] * inv_ratios[i]
        suffix_by_entity[entity_id] = (ex_dates, suffix)

    factors = []
    for entity_id, grp in entity_dates.groupby("entity_id"):
        ex_dates, suffix = suffix_by_entity.get(entity_id, ([], [1.0]))
        for d in grp["trade_date"]:
            idx = bisect.bisect_right(ex_dates, d)  # first index with ex_date > d
            factors.append((entity_id, d, suffix[idx]))

    out = pd.DataFrame(factors, columns=["entity_id", "trade_date", "factor"])
    return out


def materialize_adjustment_factors(con: duckdb.DuckDBPyConnection, impl: str = "sql") -> int:
    """The one explicit write path. Never call this from a read function."""
    df = compute_factors_sql(con) if impl == "sql" else compute_factors_python(con)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["known_date"] = df["trade_date"]
    df["fetched_at"] = dt.datetime.now()
    df["source"] = SOURCE_NAME
    df["revision_seq"] = 1

    con.execute("DELETE FROM adjustment_factors")  # fully-recomputed derived table, not append-only facts
    con.register("factors_new", df[["entity_id", "trade_date", "factor", "known_date", "fetched_at", "source", "revision_seq"]])
    con.execute("INSERT INTO adjustment_factors SELECT * FROM factors_new")
    con.unregister("factors_new")
    return len(df)


def read_adjusted_prices(con: duckdb.DuckDBPyConnection, entity_id: str) -> pd.DataFrame:
    """Read path ONLY -- joins prices_eod (via isin_lineage to the entity's
    full ISIN chain) against the already-materialized adjustment_factors.
    Never materializes anything itself; if adjustment_factors is empty or
    stale, that is this function's caller's problem to notice (e.g. via the
    'more than one distinct factor value' test), not something this
    function silently fixes by writing."""
    sql = """
        SELECT p.isin, p.trade_date, p.close AS raw_close, af.factor,
               p.close * af.factor AS adjusted_close
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        JOIN adjustment_factors af ON af.entity_id = l.entity_id AND af.trade_date = p.trade_date
        WHERE l.entity_id = ? AND p.series = 'EQ'
        ORDER BY p.trade_date
    """
    return con.execute(sql, [entity_id]).fetchdf()
