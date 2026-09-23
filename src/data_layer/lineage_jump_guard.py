"""Structural detector for Bug #1 (BUGS.md): an ISIN lineage transition
whose adjusted-price boundary shows a large, unexplained jump -- correct
lineage link, no corporate action on record to justify the discontinuity
(capital reduction, scheme of arrangement, or similar restructuring the
corporate-actions feed does not carry via this endpoint at all, confirmed
directly: 0 of 14 originally-identified cases have ANY record, of any
type, in the raw feed within +-10 days of the transition -- not a parsing
gap in corporate_actions.py's regex, a feed coverage gap).

Because the feed carries nothing to parse, extending the bonus/split
regex cannot recover these events. The fallback this module implements
instead: flag the boundary structurally (ratio outside a fixed band with
no matching corporate action nearby) so factor code can NaN out only the
single return that spans the boundary -- not the whole entity's history,
which Bug #1's original write-up left as an undecided, blunter option.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

RATIO_HIGH = 1.5
RATIO_LOW = 1 / RATIO_HIGH
EXPLANATION_WINDOW_DAYS = 10


def find_unexplained_jumps(
    con: duckdb.DuckDBPyConnection,
    before: dt.date | None = None,
    ratio_high: float = RATIO_HIGH,
) -> pd.DataFrame:
    """One row per lineage transition whose adjusted-price boundary ratio
    (first adjusted close under the new isin / last adjusted close under
    the predecessor isin) falls outside [1/ratio_high, ratio_high], with no
    corporate_actions record for that symbol within +-EXPLANATION_WINDOW_DAYS
    of the transition date.

    `before`: if given, restricts to transitions with transition_date <
    this cutoff -- pass SEALED_HOLDOUT_START to keep this diagnostic
    compliant with the project's holdout rule when run against the live
    warehouse (lineage/adjustment tables themselves are not holdout-guarded,
    since they are structural/data-quality layers, not factor or return
    computations -- but a caller doing pre-holdout-only work should still
    scope its own read this way rather than relying on that distinction).
    """
    lineage_sql = "SELECT isin, entity_id, predecessor_isin, known_date AS transition_date FROM isin_lineage WHERE predecessor_isin IS NOT NULL"
    if before is not None:
        lineage_sql += " AND known_date < ?"
        lineage = con.execute(lineage_sql, [before]).fetchdf()
    else:
        lineage = con.execute(lineage_sql).fetchdf()

    if lineage.empty:
        return pd.DataFrame(columns=["entity_id", "symbol", "predecessor_isin", "isin",
                                      "transition_date", "boundary_ratio", "has_nearby_ca_record"])

    isins = list(pd.unique(lineage[["isin", "predecessor_isin"]].values.ravel()))
    prices = con.execute(
        "SELECT p.isin, p.symbol, p.trade_date, p.close * af.factor AS adj_close "
        "FROM prices_eod p "
        "JOIN isin_lineage l ON l.isin = p.isin "
        "JOIN adjustment_factors af ON af.trade_date = p.trade_date AND af.entity_id = l.entity_id "
        f"WHERE p.series = 'EQ' AND p.isin IN ({','.join('?' for _ in isins)})",
        isins,
    ).fetchdf()
    prices["trade_date"] = pd.to_datetime(prices["trade_date"])

    actions = con.execute("SELECT symbol, ex_date FROM corporate_actions").fetchdf()
    actions["ex_date"] = pd.to_datetime(actions["ex_date"])

    rows = []
    for _, r in lineage.iterrows():
        pred = prices[prices["isin"] == r["predecessor_isin"]].sort_values("trade_date")
        cur = prices[prices["isin"] == r["isin"]].sort_values("trade_date")
        if pred.empty or cur.empty:
            continue
        last_pred, first_cur = pred.iloc[-1], cur.iloc[0]
        if not (last_pred["adj_close"] > 0) or pd.isna(first_cur["adj_close"]):
            continue
        ratio = first_cur["adj_close"] / last_pred["adj_close"]
        if ratio <= ratio_high and ratio >= 1 / ratio_high:
            continue

        transition_date = pd.Timestamp(r["transition_date"])
        window_lo = transition_date - pd.Timedelta(days=EXPLANATION_WINDOW_DAYS)
        window_hi = transition_date + pd.Timedelta(days=EXPLANATION_WINDOW_DAYS)
        nearby = actions[
            (actions["symbol"] == first_cur["symbol"])
            & (actions["ex_date"] >= window_lo) & (actions["ex_date"] <= window_hi)
        ]
        rows.append({
            "entity_id": r["entity_id"], "symbol": first_cur["symbol"],
            "predecessor_isin": r["predecessor_isin"], "isin": r["isin"],
            "transition_date": transition_date, "boundary_ratio": ratio,
            "has_nearby_ca_record": len(nearby) > 0,
        })
    return pd.DataFrame(rows)


def unexplained_jump_boundaries(con: duckdb.DuckDBPyConnection, before: dt.date | None = None) -> dict[str, set]:
    """entity_id -> set of transition dates that are unexplained jumps with
    NO corporate-actions record nearby (the only case where NaN-ing the
    boundary return, rather than correcting it, is the right response --
    a jump WITH a nearby record deserves parser attention instead, not a
    NaN)."""
    df = find_unexplained_jumps(con, before=before)
    df = df[~df["has_nearby_ca_record"]]
    out: dict[str, set] = {}
    for eid, dates in df.groupby("entity_id")["transition_date"]:
        out[eid] = set(dates)
    return out
