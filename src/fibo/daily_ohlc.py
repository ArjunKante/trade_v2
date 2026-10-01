"""Entity-adjusted daily OHLC panel for the Fibo module's daily-side rules
(Alligator, fractal swings, ATR, golden zone) -- all four need daily HIGH
and LOW, which entity_prices_daily (src/data_layer/entity_panel.py) does not
carry (close only). Same JOIN pattern as src/swing/backtest.py's
build_open_close_panel (prices_eod + isin_lineage + adjustment_factors),
extended to all four OHLC columns instead of open+close.

No data_layer.holdout guard: FINDINGS.md Section 7 retired the sealed
historical holdout for every hypothesis sharing this warehouse, so reading
the full daily history through the present is not a leak. This module's
own study has a separate, forward-only dev/test boundary, decided once
intraday data depth is known (Step 1 of this module's build) -- unrelated
to the retired historical window.
"""
from __future__ import annotations

import duckdb
import pandas as pd


def build_daily_ohlc_panel(con: duckdb.DuckDBPyConnection, entity_ids: list[str] | None = None) -> pd.DataFrame:
    """[entity_id, trade_date, isin, adjusted_open, adjusted_high,
    adjusted_low, adjusted_close, volume, turnover], full history, entity-
    adjusted (raw * adjustment_factors.factor for that entity/date, same
    factor applied uniformly across O/H/L/C so intra-day ranges are
    preserved under adjustment). `entity_ids`, if given, restricts the
    query (avoids materializing the whole 2967-entity warehouse just to
    look at 2-3 stocks)."""
    placeholders = ", ".join(["?"] * len(entity_ids)) if entity_ids else ""
    where_entity = f"AND l.entity_id IN ({placeholders})" if entity_ids else ""
    sql = f"""
        SELECT l.entity_id, p.trade_date, p.isin,
               p.open  * af.factor AS adjusted_open,
               p.high  * af.factor AS adjusted_high,
               p.low   * af.factor AS adjusted_low,
               p.close * af.factor AS adjusted_close,
               p.volume, p.turnover
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        JOIN adjustment_factors af ON af.entity_id = l.entity_id AND af.trade_date = p.trade_date
        WHERE p.series = 'EQ' AND p.open > 0 AND p.high > 0 AND p.low > 0 AND p.close > 0
        {where_entity}
    """
    params = list(entity_ids) if entity_ids else []
    df = con.execute(sql, params).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.sort_values(["entity_id", "trade_date"]).reset_index(drop=True)
