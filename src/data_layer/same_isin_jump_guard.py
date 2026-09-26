"""Structural detector for a NEW bug shape, distinct from Bug #1/
`lineage_jump_guard.py`: a large, unexplained adjusted-price jump between
two CONSECUTIVE trading rows of the SAME isin (no ISIN-lineage transition
at all -- `lineage_jump_guard` cannot see this, since it only examines the
boundary between a predecessor isin and its successor).

Found live (swing project, Phase 3 backtest, 2026-09-26): MAJESCO
(INE898S01029) collapsed from ~985 to ~12.2 between 2020-12-22 and
2020-12-23 -- the December 2020 Majesco demerger, a real corporate event.
`adjustment_factors.factor` stays flat 1.0 across the collapse and
`corporate_actions` has zero rows for this isin -- the same underlying
mechanism as Bug #1 (a capital reduction / scheme of arrangement the
bonus/split-only corporate-actions parser does not capture), but Bug #1's
fix (`lineage_jump_guard`) only guards ISIN-lineage-transition boundaries.
A same-isin event is currently unguarded anywhere in this codebase.

Same ratio/explanation-window convention as `lineage_jump_guard.py`
(RATIO_HIGH=1.5, EXPLANATION_WINDOW_DAYS=10) for consistency with the
already-established Bug #1 threshold -- not re-derived here.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

RATIO_HIGH = 1.5
EXPLANATION_WINDOW_DAYS = 10


def find_unexplained_same_isin_jumps(
    con: duckdb.DuckDBPyConnection,
    before: dt.date | None = None,
    ratio_high: float = RATIO_HIGH,
) -> pd.DataFrame:
    """One row per (isin, consecutive-trading-row pair) whose adjusted-close
    ratio falls outside [1/ratio_high, ratio_high], with no
    `corporate_actions` record for that symbol within
    +-EXPLANATION_WINDOW_DAYS of the jump date. `gap_days` is reported (the
    calendar gap between the two rows) so a same-day-adjacent collapse
    (the Majesco shape) can be told apart from a jump straddling a long
    trading halt -- both are flagged, neither is silently treated as more
    or less real; the caller decides what to do with the distinction.

    `before`: optional cutoff, same convention as
    `lineage_jump_guard.find_unexplained_jumps` -- restricts to jump dates
    strictly before this date. Omit to scan the full warehouse (the right
    default for a blast-radius assessment; a caller doing pre-holdout-only
    downstream work should pass SEALED_HOLDOUT_START explicitly)."""
    sql = """
        SELECT p.isin, p.symbol, p.trade_date, p.close * af.factor AS adj_close
        FROM prices_eod p
        JOIN isin_lineage l ON l.isin = p.isin
        JOIN adjustment_factors af ON af.trade_date = p.trade_date AND af.entity_id = l.entity_id
        WHERE p.series = 'EQ'
    """
    params = []
    if before is not None:
        sql += " AND p.trade_date < ?"
        params.append(before)
    prices = con.execute(sql, params).fetchdf()
    if prices.empty:
        return pd.DataFrame(columns=["isin", "symbol", "prev_date", "jump_date", "ratio",
                                      "gap_days", "has_nearby_ca_record"])
    prices["trade_date"] = pd.to_datetime(prices["trade_date"])
    prices = prices.sort_values(["isin", "trade_date"])

    prev_close = prices.groupby("isin")["adj_close"].shift(1)
    prev_date = prices.groupby("isin")["trade_date"].shift(1)
    ratio = prices["adj_close"] / prev_close
    is_jump = (prev_close > 0) & ratio.notna() & ((ratio > ratio_high) | (ratio < 1 / ratio_high))

    jumps = prices[is_jump].copy()
    jumps["ratio"] = ratio[is_jump]
    jumps["prev_date"] = prev_date[is_jump]
    jumps["gap_days"] = (jumps["trade_date"] - jumps["prev_date"]).dt.days
    jumps = jumps.rename(columns={"trade_date": "jump_date"})
    if jumps.empty:
        return pd.DataFrame(columns=["isin", "symbol", "prev_date", "jump_date", "ratio",
                                      "gap_days", "has_nearby_ca_record"])

    actions = con.execute("SELECT symbol, ex_date FROM corporate_actions").fetchdf()
    actions["ex_date"] = pd.to_datetime(actions["ex_date"])

    has_nearby = []
    for _, r in jumps.iterrows():
        window_lo = r["jump_date"] - pd.Timedelta(days=EXPLANATION_WINDOW_DAYS)
        window_hi = r["jump_date"] + pd.Timedelta(days=EXPLANATION_WINDOW_DAYS)
        nearby = actions[(actions["symbol"] == r["symbol"]) &
                          (actions["ex_date"] >= window_lo) & (actions["ex_date"] <= window_hi)]
        has_nearby.append(len(nearby) > 0)
    jumps["has_nearby_ca_record"] = has_nearby

    return jumps[["isin", "symbol", "prev_date", "jump_date", "ratio", "gap_days",
                  "has_nearby_ca_record"]].reset_index(drop=True)


def unexplained_same_isin_jump_entities(con: duckdb.DuckDBPyConnection, before: dt.date | None = None) -> pd.DataFrame:
    """entity_id -> the isins/jump_dates behind each unexplained same-isin
    jump (has_nearby_ca_record == False only), resolved through
    isin_lineage so a caller can exclude affected ENTITIES (not just
    isins) from a downstream analysis."""
    jumps = find_unexplained_same_isin_jumps(con, before=before)
    jumps = jumps[~jumps["has_nearby_ca_record"]]
    if jumps.empty:
        return pd.DataFrame(columns=["entity_id", "isin", "symbol", "jump_date", "ratio", "gap_days"])
    isins = jumps["isin"].unique().tolist()
    lineage = con.execute(
        f"SELECT isin, entity_id FROM isin_lineage WHERE isin IN ({','.join('?' for _ in isins)})", isins
    ).fetchdf()
    return jumps.merge(lineage, on="isin", how="left")[
        ["entity_id", "isin", "symbol", "jump_date", "ratio", "gap_days"]]
