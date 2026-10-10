"""Evening computation: for every top-200 universe member, the frozen
daily-side rule (PREREGISTRATION_FIBO.md Section 3a-3c) evaluated as of the
day's close -- Alligator uptrend, most recent confirmed swing + 2xATR
filter, golden zone -- plus the scale factor needed to place that zone
against TOMORROW's raw intraday prints.

QUALIFIES, defined here (not stated verbatim in the frozen rule, which only
defines uptrend/swing/zone individually): a stock "qualifies" for tomorrow's
actionable watchlist iff uptrend is True AND a confirmed swing exists AND
it passes the 2xATR filter AND tomorrow's scale factor is known (no ex-date
in the lookahead window). Every top-200 member is logged regardless --
uptrend=False or no-valid-swing rows are kept with null swing/zone fields,
not dropped, so the evening log is a complete, auditable record of the
whole universe each night, not just the names that happened to qualify.
`qualifies=False` rows are never shown by the morning job.

Bug #1/#11 propagation fix (2026-10-11): `most_recent_confirmed_swing`'s
ATR(14) is now computed with `src/fibo/jump_guard.py`'s combined
lineage-jump/same-isin-jump exclusion -- previously unguarded here,
the same gap this fix closed in the backtest scripts. See BUGS.md and
FIBO_FINDINGS.md's propagation-fix note for the blast-radius check that
preceded this change.

TOMORROW'S SCALE FACTOR: adjustment_factors is only piecewise-constant
across ex-dates, so tomorrow's factor equals today's UNLESS a corporate
action's ex_date falls in (today, today + EX_DATE_LOOKAHEAD_DAYS] -- in
that case the factor could change overnight and is reported as unknown
(scale_factor=None, qualifies=False) rather than guessed. This is the same
ex-date-skip convention src/fibo/scale_probe.py already uses, moved one
layer up to the daily factor instead of the intraday archive scale.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from data_layer.staleness import assert_data_current
from fibo.daily_ohlc import build_daily_ohlc_panel
from fibo.indicators import alligator, alligator_uptrend, most_recent_confirmed_swing, golden_zone
from fibo.jump_guard import combined_unexplained_jump_dates
from fibo.price_scale import get_adjustment_factor
from fibo.universe import reconstitute_annually
from fibo_live.config import EX_DATE_LOOKAHEAD_DAYS, TOP_N


def _latest_symbols(con: duckdb.DuckDBPyConnection, entity_ids: list[str]) -> dict[str, str]:
    if not entity_ids:
        return {}
    placeholders = ", ".join(["?"] * len(entity_ids))
    df = con.execute(
        f"""
        SELECT l.entity_id, p.symbol, MAX(p.trade_date) AS last_seen
        FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
        WHERE l.entity_id IN ({placeholders}) AND p.series = 'EQ'
        GROUP BY l.entity_id, p.symbol
        """,
        entity_ids,
    ).fetchdf()
    df = df.sort_values("last_seen").drop_duplicates("entity_id", keep="last")
    return dict(zip(df["entity_id"], df["symbol"]))


def _upcoming_ex_date(con: duckdb.DuckDBPyConnection, entity_id: str, as_of: dt.date, lookahead_days: int) -> bool:
    row = con.execute(
        """
        SELECT 1 FROM corporate_actions ca JOIN isin_lineage l ON ca.isin = l.isin
        WHERE l.entity_id = ? AND ca.ex_date > ? AND ca.ex_date <= ? LIMIT 1
        """,
        [entity_id, as_of, as_of + dt.timedelta(days=lookahead_days)],
    ).fetchone()
    return row is not None


def build_watchlist(con: duckdb.DuckDBPyConnection, as_of_date: dt.date, top_n: int = TOP_N) -> pd.DataFrame:
    """One row per top-`top_n` universe member, as of `as_of_date`'s close.
    Columns: entity_id, symbol, year, rank, uptrend, has_swing, passes_atr_filter,
    swing_high, swing_low, atr, golden_zone_low, golden_zone_high,
    scale_factor, ex_date_flag, qualifies."""
    assert_data_current(con)  # BUGS.md Bug #13 -- refuse rather than compute on a stale/gapped panel
    universe = reconstitute_annually(con, top_n=top_n)
    year = as_of_date.year
    members = universe[universe["year"] == year]
    entity_ids = members["entity_id"].tolist()
    if not entity_ids:
        return pd.DataFrame(columns=[
            "entity_id", "symbol", "year", "rank", "uptrend", "has_swing", "passes_atr_filter",
            "swing_high", "swing_low", "atr", "golden_zone_low", "golden_zone_high",
            "scale_factor", "ex_date_flag", "qualifies",
        ])
    rank_lookup = dict(zip(members["entity_id"], members["rank"]))
    symbols = _latest_symbols(con, entity_ids)

    panel = build_daily_ohlc_panel(con, entity_ids=entity_ids)
    panel = panel[panel["trade_date"] <= pd.Timestamp(as_of_date)]

    alligator_df = alligator(panel)
    uptrend_df = alligator_uptrend(panel, alligator_df)
    uptrend_today = uptrend_df[uptrend_df["trade_date"] == pd.Timestamp(as_of_date)]
    uptrend_lookup = dict(zip(uptrend_today["entity_id"], uptrend_today["uptrend"]))

    jump_dates = combined_unexplained_jump_dates(con)
    swing_df = most_recent_confirmed_swing(panel, as_of_date=as_of_date, unexplained_jump_dates=jump_dates)
    swing_lookup = {r["entity_id"]: r for _, r in swing_df.iterrows()}

    rows = []
    for entity_id in entity_ids:
        uptrend = bool(uptrend_lookup.get(entity_id, False))
        swing = swing_lookup.get(entity_id)
        has_swing = swing is not None
        passes_atr = bool(swing["passes_filter"]) if has_swing else False

        swing_high = swing_low = atr = zone_low = zone_high = None
        if has_swing and passes_atr:
            swing_high = float(swing["swing_high_price"])
            swing_low = float(swing["swing_low_price"])
            atr = float(swing["atr_at_swing_high"])
            zone_low, zone_high = golden_zone(swing_low, swing_high)

        ex_flag = _upcoming_ex_date(con, entity_id, as_of_date, EX_DATE_LOOKAHEAD_DAYS)
        scale_factor = None
        if not ex_flag:
            try:
                scale_factor = get_adjustment_factor(con, entity_id, as_of_date)
            except ValueError:
                scale_factor = None

        qualifies = uptrend and has_swing and passes_atr and (scale_factor is not None)

        rows.append({
            "entity_id": entity_id, "symbol": symbols.get(entity_id), "year": year,
            "rank": int(rank_lookup[entity_id]), "uptrend": uptrend, "has_swing": has_swing,
            "passes_atr_filter": passes_atr, "swing_high": swing_high, "swing_low": swing_low,
            "atr": atr, "golden_zone_low": zone_low, "golden_zone_high": zone_high,
            "scale_factor": scale_factor, "ex_date_flag": ex_flag, "qualifies": qualifies,
        })

    return pd.DataFrame(rows)
