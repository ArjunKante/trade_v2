"""Per-stock weekly study's universe: the current top-50-by-turnover
entities (point-in-time, annually reconstituted) that ALSO currently pass
the existing fundamental screener.

Both halves of this filter are REUSED, read-only, from code this module
never modifies:
  - `src/fibo/universe.py::reconstitute_annually` -- the same point-in-time,
    annually-reconstituted top-N-by-turnover construction the Fibo study
    already uses (membership for year Y = top N by median daily turnover
    over calendar year Y-1, held fixed for all of year Y). This module
    just takes the LATEST reconstituted year's membership -- "current
    point-in-time membership" -- instead of Fibo's whole multi-year panel.
  - `src/reports/fundamental_screener.py::evaluate_company` (plus its
    tercile/sector/company-name helpers) -- the exact same cash-flow-
    quality-primarily screen already used ahead of the momentum universe,
    applied here to this study's own top-50 list instead of the momentum
    top decile. A stock "passes" iff its verdict is PASS or
    FINANCIALS-PARTIAL, the same definition `run_screener` uses for its
    own survivors.

LOOKAHEAD CAVEAT, stated plainly (per instruction): the fundamental
screener is CURRENT-STATE ONLY -- BUGS.md Bug #12 notes it has no
point-in-time history, so it cannot be asked "would this company have
passed the screen back in 2017." Applying today's screener verdict to
gate a universe that will then be backtested over 2016-2026 is a mild
lookahead: a stock could have failed this screen for most of its history
and only clear it recently (or vice versa), and this selection would not
know that. This is accepted here because the screener's role is to pick
WHICH 50 stocks are worth testing a per-stock rule on GOING FORWARD, not
to certify that each one would have passed a fundamentals gate at every
historical point the backtest reads -- the backtest itself still reads
each stock's own real historical prices unconditionally, it is only the
MEMBERSHIP LIST (which 50 names qualify to be tested at all) that carries
this mild current-state bias. Not a correctness bug in the backtest;
a stated limitation of the selection step.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from fibo.universe import reconstitute_annually
from reports.fundamental_screener import (
    evaluate_company, compute_liquidity_tercile, load_company_names, resolve_isin_entities,
)
from reports.fundamental_snapshot import load_sector_map

TOP_N = 50


def _latest_symbols(con: duckdb.DuckDBPyConnection, entity_ids: list[str]) -> dict[str, str]:
    """Same convention as fibo_live.watchlist._latest_symbols -- the most
    recently traded symbol for each entity, since a symbol can be recycled
    or renamed across an entity's own lineage."""
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


def current_top_n_by_turnover(con: duckdb.DuckDBPyConnection, top_n: int = TOP_N) -> pd.DataFrame:
    """[entity_id, symbol, rank, median_turnover_prior_year, year] -- the
    LATEST reconstituted year's top-`top_n` membership from
    fibo.universe.reconstitute_annually. `year` is kept so a caller can
    see exactly which year this membership was ranked for (year Y, off
    year Y-1's turnover) -- current point-in-time, not today's literal
    turnover ranking (which would need a partial-year proxy; this reuses
    the already-decided annual convention instead of inventing a second
    one)."""
    uni = reconstitute_annually(con, top_n=top_n)
    latest_year = uni["year"].max()
    top = uni[uni["year"] == latest_year].sort_values("rank").reset_index(drop=True)
    symbols = _latest_symbols(con, top["entity_id"].tolist())
    top["symbol"] = top["entity_id"].map(symbols)
    return top


def screener_gate(con: duckdb.DuckDBPyConnection, candidates: pd.DataFrame) -> pd.DataFrame:
    """`candidates`: a DataFrame with entity_id, symbol, rank (as returned
    by current_top_n_by_turnover). Returns the same frame with an added
    `screener_verdict` column (PASS / FINANCIALS-PARTIAL / FAIL /
    INSUFFICIENT DATA) and a `screener_pass` bool (True iff PASS or
    FINANCIALS-PARTIAL -- the same definition run_screener's own
    `survivors` uses). Runs `evaluate_company` per candidate, with a
    placeholder (NaN) momentum_12_1 -- this universe was never ranked by
    momentum, and evaluate_company's checks never read that field, only
    report it."""
    sector_map = load_sector_map()
    tercile_df = compute_liquidity_tercile(con)

    all_isins = []
    for eid in candidates["entity_id"]:
        all_isins.extend(r[0] for r in con.execute("SELECT isin FROM isin_lineage WHERE entity_id = ?", [eid]).fetchall())
    name_by_isin = load_company_names(con, all_isins)
    isin_entity = resolve_isin_entities(con, all_isins)
    isin_entity["company_name"] = isin_entity["isin"].map(name_by_isin)
    company_names = (
        isin_entity.dropna(subset=["company_name"]).drop_duplicates("entity_id")
        .set_index("entity_id")["company_name"].to_dict()
    )

    verdicts, passes = [], []
    for _, row in candidates.iterrows():
        mom_row = pd.Series({
            "entity_id": row["entity_id"], "symbol": row["symbol"],
            "rank": row["rank"], "momentum_12_1": float("nan"),
        })
        result = evaluate_company(con, mom_row, sector_map, tercile_df, company_names)
        verdicts.append(result["verdict"])
        passes.append(result["verdict"] in ("PASS", "FINANCIALS-PARTIAL"))

    out = candidates.copy()
    out["screener_verdict"] = verdicts
    out["screener_pass"] = passes
    return out


def build_study_universe(con: duckdb.DuckDBPyConnection, top_n: int = TOP_N) -> pd.DataFrame:
    """The full pipeline: current top-`top_n`-by-turnover, screener-gated.
    Returns ALL `top_n` candidates with their verdict (not just survivors)
    so the caller can report how many passed, same transparency convention
    fundamental_screener.py itself uses (nothing dropped silently)."""
    candidates = current_top_n_by_turnover(con, top_n=top_n)
    return screener_gate(con, candidates)
