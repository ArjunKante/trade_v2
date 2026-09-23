"""Per-company fundamental snapshot: a research/reading tool, not a study.

No pre-registration, no study slot, no holdout at stake -- this computes no
forward return and no IC, so none of the sealed-holdout machinery in
data_layer.holdout applies to it. It DOES deliberately read price data up to
today (2026-09), not the truncated pre-holdout entity_panel, because a
"current fundamental snapshot" that shows an 18-month-stale price would defeat
its own purpose. This is a live-monitoring display, categorically different
from a backtest evaluation, and does not reuse entity_panel.py's guarded read
path or the authorize_holdout flag (that flag stays reserved, per its own
docstring, for the one sanctioned end-of-project strategy evaluation).

DATA VINTAGE, stated plainly rather than left to be discovered from
per-field staleness numbers: this tool uses ONLY the two tested, verified
XBRL sources (NSE_XBRL_QUARTERLY_FACTS with the confirmed OneD/OneI "current
period" context convention, and NSE_XBRL_ANNUAL_BALANCE_SHEET). It does NOT
read NSE_INTEGRATED_FILING_FINANCIALS (the SEBI Integrated Filing source that
superseded the legacy quarterly feed from ~April 2025) -- that source uses a
different, project-unverified context-ref convention, and guessing at it here
would repeat exactly the OneD/FourD mistake this project has already been
burned by once (fundamentals_factors.py's own docstring). Practical
consequence, confirmed directly against the warehouse: quarterly P&L tops
out around period_end 2024-12-31 and annual balance-sheet data tops out
around FY2024 (period_end 2024-03-31) for nearly all companies -- "latest"
in this report means latest available in this warehouse, not latest filed
in the real world. Every figure's known_date and staleness make this
concrete per-field; this is the same fact stated once, globally, so it is
not missed.

NO COMPOSITE SCORE OR CROSS-METRIC RANKING is computed anywhere in this
module. Per-metric percentile-within-sector (one valuation ratio compared to
its own peers) is shown because it was explicitly requested and is not a
composite; nothing here combines metrics into a single number or overall
rank. This project has already established (FINDINGS.md Section 12) that an
untested factor combination cannot be validated on this data -- a composite
score is exactly that, uninvited.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from factors.fundamentals_factors import _pick_pit_series, compute_ttm, pit_latest_value_asof
from factors.momentum import compute_momentum_12_1
from data_layer.lineage_jump_guard import unexplained_jump_boundaries

ROOT = Path(__file__).resolve().parents[2]
SECTOR_MAP_CSV = ROOT / "data" / "raw" / "sector" / "symbol_industry_map.csv"

QUARTERLY_SOURCE = "NSE_XBRL_QUARTERLY_FACTS"
ANNUAL_SOURCE = "NSE_XBRL_ANNUAL_BALANCE_SHEET"

PRICE_LOOKBACK_DAYS = 500       # comfortably more than momentum's 273-trading-day need
ACTIVE_WINDOW_DAYS = 10         # an entity must have traded within this many days of the panel's max date to count as "current"
BS_START = pd.Timestamp("2023-01-01")  # FY2023+, per FUNDAMENTALS.md's own coverage finding
NOT_AVAILABLE = "NOT AVAILABLE"


# ---------------------------------------------------------------------------
# Entity resolution
# ---------------------------------------------------------------------------

def resolve_identifier(con: duckdb.DuckDBPyConnection, identifier: str) -> dict:
    """symbol or ISIN -> {entity_id, isins, symbol}. Raises ValueError if
    nothing matches -- never silently returns a guess."""
    identifier = identifier.strip().upper()
    is_isin_shaped = len(identifier) == 12 and identifier[:3] in ("INE", "IN9", "INF")

    if is_isin_shaped:
        row = con.execute("SELECT entity_id FROM isin_lineage WHERE isin = ?", [identifier]).fetchone()
        if row is None:
            raise ValueError(f"ISIN {identifier} not found in isin_lineage.")
        entity_id = row[0]
    else:
        row = con.execute(
            "SELECT l.entity_id FROM prices_eod p JOIN isin_lineage l ON l.isin = p.isin "
            "WHERE p.symbol = ? AND p.series = 'EQ' ORDER BY p.trade_date DESC LIMIT 1",
            [identifier],
        ).fetchone()
        if row is None:
            raise ValueError(f"Symbol {identifier} not found in prices_eod (series='EQ').")
        entity_id = row[0]

    isins = [r[0] for r in con.execute("SELECT isin FROM isin_lineage WHERE entity_id = ?", [entity_id]).fetchall()]
    sym_row = con.execute(
        "SELECT p.symbol FROM prices_eod p WHERE p.isin IN "
        f"({','.join('?' for _ in isins)}) AND p.series = 'EQ' ORDER BY p.trade_date DESC LIMIT 1",
        isins,
    ).fetchone()
    symbol = sym_row[0] if sym_row else identifier
    return {"entity_id": entity_id, "isins": isins, "symbol": symbol}


# ---------------------------------------------------------------------------
# Current price panel + momentum universe (unguarded -- see module docstring)
# ---------------------------------------------------------------------------

def load_current_price_panel(con: duckdb.DuckDBPyConnection, lookback_days: int = PRICE_LOOKBACK_DAYS) -> pd.DataFrame:
    """entity_id, trade_date, symbol, adjusted_close, turnover -- for every
    EQ entity, restricted to a recent window (momentum only needs ~273
    trading days; this leaves comfortable margin). Reads directly from
    prices_eod/isin_lineage/adjustment_factors, NOT entity_panel (which is
    truncated at the sealed holdout boundary by design -- see module
    docstring for why that truncation does not apply to this tool)."""
    as_of = con.execute("SELECT MAX(trade_date) FROM prices_eod").fetchone()[0]
    start = pd.Timestamp(as_of) - pd.Timedelta(days=lookback_days)
    sql = """
        SELECT l.entity_id, p.trade_date, p.symbol, p.close * af.factor AS adjusted_close, p.turnover
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        JOIN adjustment_factors af ON af.entity_id = l.entity_id AND af.trade_date = p.trade_date
        WHERE p.series = 'EQ' AND p.trade_date >= ?
    """
    df = con.execute(sql, [start.date()]).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df, pd.Timestamp(as_of)


def compute_momentum_universe(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One row per currently-active entity (traded within ACTIVE_WINDOW_DAYS
    of the panel's max date): entity_id, symbol, as_of_date, latest_price,
    momentum_12_1, rank (1 = highest), pct_rank, in_top_decile, n_universe.

    Uses the same gap-aware momentum computation as the backtest
    (factors.momentum.compute_momentum_12_1), including the Bug #1
    structural jump guard (lineage_jump_guard) -- both apply exactly the
    same way to current data as to historical data, since neither depends
    on the sealed-holdout boundary."""
    panel, as_of = load_current_price_panel(con)
    jump_dates = unexplained_jump_boundaries(con)  # full history, no `before` cutoff -- this is not a pre-holdout-only read
    mom = compute_momentum_12_1(panel, unexplained_jump_dates=jump_dates)
    merged = mom.merge(panel[["entity_id", "trade_date", "symbol", "adjusted_close"]],
                        on=["entity_id", "trade_date"], how="left")

    last_date_by_entity = merged.groupby("entity_id")["trade_date"].max().rename("last_date")
    merged = merged.merge(last_date_by_entity, on="entity_id")
    latest_rows = merged[merged["trade_date"] == merged["last_date"]].copy()
    active_cutoff = as_of - pd.Timedelta(days=ACTIVE_WINDOW_DAYS)
    active = latest_rows[latest_rows["last_date"] >= active_cutoff].dropna(subset=["value"]).copy()

    active = active.rename(columns={"trade_date": "as_of_date", "adjusted_close": "latest_price", "value": "momentum_12_1"})
    active["rank"] = active["momentum_12_1"].rank(ascending=False, method="min").astype(int)
    n = len(active)
    active["pct_rank"] = 1 - (active["rank"] - 1) / n
    decile_cutoff = active["momentum_12_1"].quantile(0.90)
    active["in_top_decile"] = active["momentum_12_1"] >= decile_cutoff
    active["n_universe"] = n
    return active[["entity_id", "symbol", "as_of_date", "latest_price", "momentum_12_1",
                   "rank", "pct_rank", "in_top_decile", "n_universe"]].sort_values("rank").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Fundamentals loading, entity-scoped (isin-list filtered, spans lineage chain)
# ---------------------------------------------------------------------------

def _load_tag(con: duckdb.DuckDBPyConnection, source: str, tag: str, isins: list[str],
              context_ref: str | None = None) -> pd.DataFrame:
    if not isins:
        return pd.DataFrame(columns=["isin", "period_end", "consolidated", "value", "known_date"])
    ctx_clause = "AND context_ref = ?" if context_ref else ""
    params = [source, tag] + isins + ([context_ref] if context_ref else [])
    sql = f"""
        SELECT isin, period_end, consolidated, TRY_CAST(value AS DOUBLE) AS value, known_date
        FROM fundamentals_xbrl_facts
        WHERE source = ? AND tag = ? AND isin IN ({','.join('?' for _ in isins)}) {ctx_clause}
    """
    df = con.execute(sql, params).fetchdf()
    df = df.dropna(subset=["value"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["known_date"] = pd.to_datetime(df["known_date"])
    return df


def _quarterly(con, tag, isins, instant=False):
    return _load_tag(con, QUARTERLY_SOURCE, tag, isins, context_ref="OneI" if instant else "OneD")


def _annual(con, tag, isins):
    return _load_tag(con, ANNUAL_SOURCE, tag, isins)


def _pit_entity_series(df: pd.DataFrame) -> pd.DataFrame:
    """PIT-pick (consolidated-preferred, latest-restatement) across a
    single entity's full lineage chain, then sort by period_end. Reuses
    fundamentals_factors._pick_pit_series unmodified -- it groups by
    (isin, period_end), which is still correct here because a lineage
    chain's ISINs never share a period_end (a clean handover, by
    isin_lineage's own construction)."""
    if df.empty:
        return df
    return _pick_pit_series(df).sort_values("period_end").reset_index(drop=True)


def _rolling_ttm(picked: pd.DataFrame) -> pd.DataFrame:
    """One row per quarter: trailing-4-quarter sum ending at that quarter,
    by POSITION in this entity's own quarter sequence (never a calendar
    assumption -- matches compute_ttm's own convention for non-March-FY
    companies). NaN (not zero, not padded) when fewer than 4 quarters are
    behind it."""
    df = picked.sort_values("period_end").reset_index(drop=True).copy()
    df["ttm"] = df["value"].rolling(4, min_periods=4).sum()
    df["n_q"] = df["value"].rolling(4, min_periods=1).count().astype(int)
    return df


def _shares_series(con, isins) -> pd.DataFrame:
    paidup = _pit_entity_series(_quarterly(con, "PaidUpValueOfEquityShareCapital", isins))
    faceval = _pit_entity_series(_quarterly(con, "FaceValueOfEquityShareCapital", isins))
    if paidup.empty or faceval.empty:
        return pd.DataFrame(columns=["period_end", "known_date", "shares"])
    m = paidup[["period_end", "known_date", "value"]].rename(columns={"value": "paidup"}).merge(
        faceval[["period_end", "value"]].rename(columns={"value": "faceval"}), on="period_end", how="inner")
    m = m[m["faceval"] > 0]
    m["shares"] = m["paidup"] / m["faceval"]
    return m[["period_end", "known_date", "shares"]].sort_values("period_end").reset_index(drop=True)


def _shares_as_of(shares_df: pd.DataFrame, known_dates: pd.Series) -> pd.Series:
    """Latest known share count as of each given known_date -- never a
    future count applied backward."""
    if shares_df.empty:
        return pd.Series([np.nan] * len(known_dates), index=known_dates.index)
    s = shares_df.sort_values("known_date")
    idx = np.searchsorted(s["known_date"].values, known_dates.values, side="right") - 1
    out = np.where(idx >= 0, s["shares"].values[np.clip(idx, 0, len(s) - 1)], np.nan)
    return pd.Series(out, index=known_dates.index)


def staleness_days(as_of: pd.Timestamp, known_date) -> object:
    if pd.isna(known_date):
        return None
    return (as_of - pd.Timestamp(known_date)).days


# ---------------------------------------------------------------------------
# Single-company P&L assembly (quarterly, full history)
# ---------------------------------------------------------------------------

def build_quarterly_pl(con: duckdb.DuckDBPyConnection, isins: list[str]) -> pd.DataFrame:
    """One row per quarter (period_end), full history: revenue, PAT
    (ProfitLossForPeriod), EBIT (=PBT+FinanceCosts), EBITDA (=EBIT+D&A),
    finance costs, each PIT-picked across the entity's full lineage chain
    -- plus their trailing-4-quarter (TTM) sums. known_date is revenue's own
    (revenue is present whenever a quarter is filed at all; a company
    missing revenue for a quarter has no usable filing for it either way)."""
    revenue = _pit_entity_series(_quarterly(con, "RevenueFromOperations", isins))
    ni = _pit_entity_series(_quarterly(con, "ProfitLossForPeriod", isins))
    pbt = _pit_entity_series(_quarterly(con, "ProfitBeforeExceptionalItemsAndTax", isins))
    fc = _pit_entity_series(_quarterly(con, "FinanceCosts", isins))
    da = _pit_entity_series(_quarterly(con, "DepreciationDepletionAndAmortisationExpense", isins))

    if revenue.empty:
        return pd.DataFrame()

    m = revenue[["period_end", "known_date", "value"]].rename(columns={"value": "revenue"})
    for df, col in [(ni, "ni"), (pbt, "pbt"), (fc, "fc"), (da, "da")]:
        if df.empty:
            m[col] = np.nan
        else:
            m = m.merge(df[["period_end", "value"]].rename(columns={"value": col}), on="period_end", how="left")

    m["ebit"] = m["pbt"] + m["fc"]
    m["ebitda"] = m["ebit"] + m["da"]
    m = m.sort_values("period_end").reset_index(drop=True)

    for col in ["revenue", "ni", "ebit", "ebitda", "fc"]:
        m[f"{col}_ttm"] = m[col].rolling(4, min_periods=4).sum()
    m["n_q_ttm"] = m["revenue"].rolling(4, min_periods=1).count().astype(int)
    return m


def growth_metrics(pl: pd.DataFrame, shares: pd.DataFrame) -> dict:
    """CAGR/YoY on TTM revenue and TTM EPS. shares_at_quarter uses only
    known-by-then share counts (no lookahead) -- computed once here rather
    than at report-render time so both the single-company and batch paths
    share one code path."""
    out = {}
    if pl.empty or pl["revenue_ttm"].notna().sum() == 0:
        return {"available": False, "reason": "no quarterly revenue history"}

    valid = pl[pl["revenue_ttm"].notna()].reset_index(drop=True)
    shares_at_q = _shares_as_of(shares, valid["known_date"])
    valid = valid.assign(shares=shares_at_q.values)
    valid["eps_ttm"] = np.where(valid["shares"] > 0, valid["ni_ttm"] / valid["shares"], np.nan)

    def _cagr(series, back):
        if len(series) <= back:
            return None
        latest, prior = series.iloc[-1], series.iloc[-1 - back]
        if pd.isna(latest) or pd.isna(prior) or prior <= 0:
            return None
        years = back / 4
        return (latest / prior) ** (1 / years) - 1

    def _yoy(series):
        return _cagr(series, 4)

    out["available"] = True
    out["latest_period_end"] = valid["period_end"].iloc[-1]
    out["latest_known_date"] = valid["known_date"].iloc[-1]
    out["revenue_cagr_3y"] = _cagr(valid["revenue_ttm"], 12)
    out["revenue_cagr_5y"] = _cagr(valid["revenue_ttm"], 20)
    out["revenue_yoy"] = _yoy(valid["revenue_ttm"])
    out["eps_cagr_3y"] = _cagr(valid["eps_ttm"], 12)
    out["eps_cagr_5y"] = _cagr(valid["eps_ttm"], 20)
    out["eps_yoy"] = _yoy(valid["eps_ttm"])
    out["last_8_quarters"] = pl.tail(8)[["period_end", "known_date", "revenue", "ni"]].copy()
    return out


def profitability_metrics(pl: pd.DataFrame) -> dict:
    if pl.empty:
        return {"available": False}
    valid = pl[pl["revenue_ttm"].notna() & (pl["revenue_ttm"] > 0)].copy()
    if valid.empty:
        return {"available": False}
    valid["ebitda_margin"] = valid["ebitda_ttm"] / valid["revenue_ttm"]
    valid["ebit_margin"] = valid["ebit_ttm"] / valid["revenue_ttm"]
    valid["net_margin"] = valid["ni_ttm"] / valid["revenue_ttm"]
    latest = valid.iloc[-1]
    trend = valid.tail(12)[["period_end", "known_date", "ebitda_margin", "ebit_margin", "net_margin"]]
    return {
        "available": True,
        "latest_known_date": latest["known_date"],
        "ebitda_margin": latest["ebitda_margin"],
        "ebit_margin": latest["ebit_margin"],
        "net_margin": latest["net_margin"],
        "trend_12q": trend,
    }


# ---------------------------------------------------------------------------
# Annual balance sheet / cash flow / returns / efficiency (FY2023+ only)
# ---------------------------------------------------------------------------

ANNUAL_TAGS = {
    "assets": "Assets", "equity": "Equity", "curL": "CurrentLiabilities", "curA": "CurrentAssets",
    "borrC": "BorrowingsCurrent", "borrN": "BorrowingsNoncurrent", "cash": "CashAndCashEquivalents",
    "cfo": "CashFlowsFromUsedInOperatingActivities",
    "capex": "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
}


def build_annual_frame(con: duckdb.DuckDBPyConnection, isins: list[str]) -> pd.DataFrame:
    """One row per fiscal year (period_end >= BS_START only, per this
    project's own coverage finding -- FUNDAMENTALS.md: real balance-sheet
    coverage is near-zero before FY2023). Each tag PIT-picked independently
    then outer-joined on period_end, so a company missing one tag (e.g. no
    disclosed CurrentLiabilities) still shows the tags it does have, rather
    than losing the whole year."""
    frames = {}
    for col, tag in ANNUAL_TAGS.items():
        picked = _pit_entity_series(_annual(con, tag, isins))
        frames[col] = picked[["period_end", "known_date", "value"]].rename(columns={"value": col}) if not picked.empty else None

    base = None
    for col, df in frames.items():
        if df is None:
            continue
        d = df.rename(columns={"known_date": f"kd_{col}"})
        base = d if base is None else base.merge(d, on="period_end", how="outer")
    if base is None:
        return pd.DataFrame()
    base = base[base["period_end"] >= BS_START].sort_values("period_end").reset_index(drop=True)
    # a single representative known_date per year: the latest among whichever tags are present (never earlier than any tag actually used)
    kd_cols = [c for c in base.columns if c.startswith("kd_")]
    base["known_date"] = base[kd_cols].max(axis=1)
    return base


def _asof_ttm_value(pl: pd.DataFrame, col: str, period_end: pd.Timestamp) -> tuple:
    """Nearest TTM value at or before a given period_end (for matching a
    fiscal year's balance-sheet snapshot to its contemporaneous P&L TTM --
    exact match for standard March-FY companies, nearest-prior otherwise).
    Returns (value, source_period_end) or (None, None)."""
    if pl.empty or "period_end" not in pl.columns or col not in pl.columns:
        return None, None
    sub = pl[pl["period_end"] <= period_end]
    if sub.empty or pd.isna(sub[col].iloc[-1]):
        return None, None
    return sub[col].iloc[-1], sub["period_end"].iloc[-1]


def returns_metrics(annual: pd.DataFrame, pl: pd.DataFrame) -> dict:
    """ROE, ROCE -- FY2023+ only, years available stated explicitly, never
    extrapolated to a year without both a balance-sheet AND a matching P&L
    TTM figure."""
    if annual.empty:
        return {"available": False}
    rows = []
    for _, r in annual.iterrows():
        ni_ttm, _ = _asof_ttm_value(pl, "ni_ttm", r["period_end"])
        ebit_ttm, _ = _asof_ttm_value(pl, "ebit_ttm", r["period_end"])
        equity = r.get("equity")
        assets = r.get("assets")
        curL = r.get("curL")
        capital_employed = assets - curL if (pd.notna(assets) and pd.notna(curL)) else None
        # Negative equity or negative capital employed makes the ratio's SIGN misleading
        # (negative/negative reads as a healthy positive) -- flagged, not silently computed.
        roe = ni_ttm / equity if (ni_ttm is not None and pd.notna(equity) and equity > 0) else None
        roe_negative_equity = pd.notna(equity) and equity <= 0
        roce = (ebit_ttm / capital_employed) if (ebit_ttm is not None and capital_employed is not None and capital_employed > 0) else None
        roce_negative_capital_employed = capital_employed is not None and capital_employed <= 0
        rows.append({
            "period_end": r["period_end"], "known_date": r["known_date"], "roe": roe, "roce": roce,
            "roe_negative_equity": roe_negative_equity, "roce_negative_capital_employed": roce_negative_capital_employed,
        })
    df = pd.DataFrame(rows)
    return {"available": df[["roe", "roce"]].notna().any().any(), "by_year": df}


def balance_sheet_metrics(annual: pd.DataFrame, pl: pd.DataFrame) -> dict:
    if annual.empty:
        return {"available": False}
    rows = []
    for _, r in annual.iterrows():
        borrC, borrN = r.get("borrC"), r.get("borrN")
        total_debt = (borrC or 0) + (borrN or 0) if (pd.notna(borrC) or pd.notna(borrN)) else None
        equity = r.get("equity")
        de = total_debt / equity if (total_debt is not None and pd.notna(equity) and equity != 0) else None
        ebitda_ttm, _ = _asof_ttm_value(pl, "ebitda_ttm", r["period_end"])
        cash = r.get("cash")
        net_debt = (total_debt - cash) if (total_debt is not None and pd.notna(cash)) else None
        net_debt_ebitda = net_debt / ebitda_ttm if (net_debt is not None and ebitda_ttm not in (None, 0)) else None
        curA, curL = r.get("curA"), r.get("curL")
        current_ratio = curA / curL if (pd.notna(curA) and pd.notna(curL) and curL != 0) else None
        ebit_ttm, _ = _asof_ttm_value(pl, "ebit_ttm", r["period_end"])
        fc_ttm, _ = _asof_ttm_value(pl, "fc_ttm", r["period_end"])
        interest_coverage = ebit_ttm / fc_ttm if (ebit_ttm is not None and fc_ttm not in (None, 0)) else None
        rows.append({
            "period_end": r["period_end"], "known_date": r["known_date"],
            "debt_equity": de, "net_debt_ebitda": net_debt_ebitda,
            "current_ratio": current_ratio, "interest_coverage": interest_coverage,
        })
    df = pd.DataFrame(rows)
    return {"available": True, "by_year": df}


def cash_flow_metrics(annual: pd.DataFrame, pl: pd.DataFrame) -> dict:
    if annual.empty or "cfo" not in annual.columns:
        return {"available": False}
    rows = []
    for _, r in annual.iterrows():
        cfo = r.get("cfo")
        capex = r.get("capex")
        fcf = (cfo - abs(capex)) if (pd.notna(cfo) and pd.notna(capex)) else None
        ni_ttm, _ = _asof_ttm_value(pl, "ni_ttm", r["period_end"])
        cfo_pat = cfo / ni_ttm if (pd.notna(cfo) and ni_ttm not in (None, 0)) else None
        rows.append({
            "period_end": r["period_end"], "known_date": r["known_date"],
            "cfo": cfo, "fcf": fcf, "cfo_pat_ratio": cfo_pat,
        })
    df = pd.DataFrame(rows)
    return {"available": df["cfo"].notna().any(), "by_year": df}


# ---------------------------------------------------------------------------
# Valuation (current price + fundamentals), single company
# ---------------------------------------------------------------------------

def compute_current_valuation(pl: pd.DataFrame, annual: pd.DataFrame, shares: pd.DataFrame,
                               latest_price: float) -> dict:
    """Uses the LATEST available TTM P&L row and the LATEST available
    annual balance-sheet row -- these are not necessarily the same vintage
    (P&L tops out ~Dec 2024, balance sheet ~FY2024 in this warehouse; see
    module docstring) -- each figure's own known_date is carried through so
    the mismatch is visible, not hidden."""
    out = {"available": False}
    if pl.empty or shares.empty:
        return out
    pl_valid = pl[pl["revenue_ttm"].notna()]
    if pl_valid.empty:
        return out
    latest_pl = pl_valid.iloc[-1]
    latest_shares_row = shares.iloc[-1]
    shares_n = latest_shares_row["shares"]
    if pd.isna(shares_n) or shares_n <= 0 or pd.isna(latest_price):
        return out

    market_cap = latest_price * shares_n
    out["available"] = True
    out["market_cap"] = market_cap
    out["shares_known_date"] = latest_shares_row["known_date"]
    out["pl_known_date"] = latest_pl["known_date"]

    ni_ttm, rev_ttm, ebit_ttm, ebitda_ttm = latest_pl["ni_ttm"], latest_pl["revenue_ttm"], latest_pl["ebit_ttm"], latest_pl["ebitda_ttm"]
    out["pe"] = market_cap / ni_ttm if ni_ttm and ni_ttm > 0 else None
    out["pe_na_reason"] = None if (ni_ttm and ni_ttm > 0) else "negative or zero trailing earnings"
    out["ps"] = market_cap / rev_ttm if rev_ttm else None
    out["earnings_yield"] = ebit_ttm / market_cap if ebit_ttm is not None else None

    if not annual.empty:
        last_a = annual.iloc[-1]
        equity, borrC, borrN, cash = last_a.get("equity"), last_a.get("borrC"), last_a.get("borrN"), last_a.get("cash")
        total_debt = (borrC or 0) + (borrN or 0) if (pd.notna(borrC) or pd.notna(borrN)) else None
        out["pb"] = market_cap / equity if pd.notna(equity) and equity else None
        out["pb_known_date"] = last_a["known_date"] if pd.notna(equity) else None
        if total_debt is not None and pd.notna(cash) and ebitda_ttm:
            out["ev_ebitda"] = (market_cap + total_debt - cash) / ebitda_ttm
        else:
            out["ev_ebitda"] = None
        out["bs_known_date"] = last_a["known_date"]
    else:
        out["pb"] = out["ev_ebitda"] = None
        out["bs_known_date"] = None

    fcf_row = None
    if not annual.empty and "cfo" in annual.columns and "capex" in annual.columns:
        fa = annual.dropna(subset=["cfo", "capex"])
        if not fa.empty:
            fcf_row = fa.iloc[-1]
    if fcf_row is not None:
        fcf = fcf_row["cfo"] - abs(fcf_row["capex"])
        out["fcf_yield"] = fcf / market_cap
        out["fcf_known_date"] = fcf_row["known_date"]
    else:
        out["fcf_yield"] = None
        out["fcf_known_date"] = None
    return out


# ---------------------------------------------------------------------------
# Sector universe snapshot (bulk, vectorized) -- for per-metric percentile only
# ---------------------------------------------------------------------------

def load_sector_map() -> pd.DataFrame:
    df = pd.read_csv(SECTOR_MAP_CSV)
    df.columns = [c.strip() for c in df.columns]
    return df.rename(columns={"Symbol": "symbol", "Industry": "sector"})


def compute_sector_valuation_snapshot(con: duckdb.DuckDBPyConnection, as_of: pd.Timestamp) -> pd.DataFrame:
    """Bulk, vectorized valuation snapshot (current PE/PS/EV-EBITDA/PB/
    FCF-yield/earnings-yield) for every symbol in the Nifty Total Market
    sector map, computed ONCE at a single as-of date -- reuses
    factors.fundamentals_factors' tested TTM/point-in-time machinery
    (compute_ttm, pit_latest_value_asof) exactly as run_phase_e_factors.py
    does across many historical dates, just at one current date here, so
    this is cheap by comparison. Rows with insufficient data are simply
    absent, not zero-filled -- percentile lookups skip them naturally."""
    sector = load_sector_map()
    sym_isin = con.execute(
        "SELECT DISTINCT ON (p.symbol) p.symbol, l.entity_id "
        "FROM prices_eod p JOIN isin_lineage l ON l.isin = p.isin "
        "WHERE p.series = 'EQ' AND p.symbol IN "
        f"({','.join('?' for _ in sector['symbol'])}) "
        "ORDER BY p.symbol, p.trade_date DESC",
        sector["symbol"].tolist(),
    ).fetchdf()
    sector = sector.merge(sym_isin, on="symbol", how="inner")
    entity_ids = sector["entity_id"].unique().tolist()
    if not entity_ids:
        return pd.DataFrame()

    isin_to_entity = con.execute(
        f"SELECT isin, entity_id FROM isin_lineage WHERE entity_id IN ({','.join('?' for _ in entity_ids)})",
        entity_ids,
    ).fetchdf()

    def _load_relabeled(source, tag, context_ref=None):
        ctx = f"AND context_ref = '{context_ref}'" if context_ref else ""
        df = con.execute(
            f"SELECT isin, period_end, consolidated, TRY_CAST(value AS DOUBLE) AS value, known_date "
            f"FROM fundamentals_xbrl_facts WHERE source = ? AND tag = ? {ctx}",
            [source, tag],
        ).fetchdf()
        df = df.dropna(subset=["value"]).merge(isin_to_entity, on="isin", how="inner")
        df = df.drop(columns=["isin"]).rename(columns={"entity_id": "isin"})  # relabel: entity_id plays "isin" role for _pick_pit_series/compute_ttm
        df["period_end"] = pd.to_datetime(df["period_end"])
        df["known_date"] = pd.to_datetime(df["known_date"])
        return df

    as_of_df = pd.DataFrame({"isin": entity_ids, "trade_date": as_of})

    revenue_q = _load_relabeled(QUARTERLY_SOURCE, "RevenueFromOperations", "OneD")
    ni_q = _load_relabeled(QUARTERLY_SOURCE, "ProfitLossForPeriod", "OneD")
    pbt_q = _load_relabeled(QUARTERLY_SOURCE, "ProfitBeforeExceptionalItemsAndTax", "OneD")
    fc_q = _load_relabeled(QUARTERLY_SOURCE, "FinanceCosts", "OneD")
    da_q = _load_relabeled(QUARTERLY_SOURCE, "DepreciationDepletionAndAmortisationExpense", "OneD")

    pbt_pit = _pick_pit_series(pbt_q)[["isin", "period_end", "value", "known_date"]].rename(columns={"value": "pbt"})
    fc_pit = _pick_pit_series(fc_q)[["isin", "period_end", "value"]].rename(columns={"value": "fc"})
    ebit_q = pbt_pit.merge(fc_pit, on=["isin", "period_end"], how="inner")
    ebit_q["value"] = ebit_q["pbt"] + ebit_q["fc"]
    ebit_q["consolidated"] = "Consolidated"
    ebit_q = ebit_q[["isin", "period_end", "consolidated", "value", "known_date"]]

    da_pit = _pick_pit_series(da_q)[["isin", "period_end", "value"]].rename(columns={"value": "da"})
    ebitda_q = ebit_q.merge(da_pit, on=["isin", "period_end"], how="inner")
    ebitda_q["value"] = ebitda_q["value"] + ebitda_q["da"]
    ebitda_q = ebitda_q[["isin", "period_end", "consolidated", "value", "known_date"]]

    ttm_rev = compute_ttm(revenue_q, as_of_df).rename(columns={"ttm_value": "revenue_ttm"})
    ttm_ni = compute_ttm(ni_q, as_of_df).rename(columns={"ttm_value": "ni_ttm"})
    ttm_ebit = compute_ttm(ebit_q, as_of_df).rename(columns={"ttm_value": "ebit_ttm"})
    ttm_ebitda = compute_ttm(ebitda_q, as_of_df).rename(columns={"ttm_value": "ebitda_ttm"})

    paidup = _load_relabeled(QUARTERLY_SOURCE, "PaidUpValueOfEquityShareCapital", "OneD")
    faceval = _load_relabeled(QUARTERLY_SOURCE, "FaceValueOfEquityShareCapital", "OneD")
    paidup_pit = _pick_pit_series(paidup)[["isin", "period_end", "value", "known_date"]].rename(columns={"value": "paidup"})
    faceval_pit = _pick_pit_series(faceval)[["isin", "period_end", "value"]].rename(columns={"value": "faceval"})
    shares_m = paidup_pit.merge(faceval_pit, on=["isin", "period_end"], how="inner")
    shares_m = shares_m[shares_m["faceval"] > 0]
    shares_m["value"] = shares_m["paidup"] / shares_m["faceval"]
    shares_pit = pit_latest_value_asof(shares_m[["isin", "known_date", "value"]], as_of_df).rename(columns={"value": "shares"})

    equity_a = _load_relabeled(ANNUAL_SOURCE, "Equity")
    borrC_a = _load_relabeled(ANNUAL_SOURCE, "BorrowingsCurrent")
    borrN_a = _load_relabeled(ANNUAL_SOURCE, "BorrowingsNoncurrent")
    cash_a = _load_relabeled(ANNUAL_SOURCE, "CashAndCashEquivalents")
    cfo_a = _load_relabeled(ANNUAL_SOURCE, "CashFlowsFromUsedInOperatingActivities")
    capex_a = _load_relabeled(ANNUAL_SOURCE, "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities")

    def _annual_asof(tag_df, name):
        if tag_df.empty:
            return pd.DataFrame(columns=["isin", "trade_date", name])
        picked = _pick_pit_series(tag_df)[["isin", "known_date", "value"]]
        out = pit_latest_value_asof(picked, as_of_df)
        return out.rename(columns={"value": name})[["isin", "trade_date", name]]

    equity_pit = _annual_asof(equity_a, "equity")
    borrC_pit = _annual_asof(borrC_a, "borrC")
    borrN_pit = _annual_asof(borrN_a, "borrN")
    cash_pit = _annual_asof(cash_a, "cash")
    cfo_pit = _annual_asof(cfo_a, "cfo")
    capex_pit = _annual_asof(capex_a, "capex")

    m = pd.DataFrame({"entity_id": entity_ids})
    m = m.merge(ttm_rev[["isin", "revenue_ttm"]].rename(columns={"isin": "entity_id"}), on="entity_id", how="left")
    m = m.merge(ttm_ni[["isin", "ni_ttm"]].rename(columns={"isin": "entity_id"}), on="entity_id", how="left")
    m = m.merge(ttm_ebit[["isin", "ebit_ttm"]].rename(columns={"isin": "entity_id"}), on="entity_id", how="left")
    m = m.merge(ttm_ebitda[["isin", "ebitda_ttm"]].rename(columns={"isin": "entity_id"}), on="entity_id", how="left")
    m = m.merge(shares_pit[["isin", "shares"]].rename(columns={"isin": "entity_id"}), on="entity_id", how="left")
    for pit_df, name in [(equity_pit, "equity"), (borrC_pit, "borrC"), (borrN_pit, "borrN"),
                          (cash_pit, "cash"), (cfo_pit, "cfo"), (capex_pit, "capex")]:
        m = m.merge(pit_df[["isin", name]].rename(columns={"isin": "entity_id"}), on="entity_id", how="left")

    price_row = con.execute(
        f"SELECT l.entity_id, p.close * af.factor AS price FROM prices_eod p "
        f"JOIN isin_lineage l ON l.isin = p.isin "
        f"JOIN adjustment_factors af ON af.entity_id = l.entity_id AND af.trade_date = p.trade_date "
        f"WHERE p.series = 'EQ' AND l.entity_id IN ({','.join('?' for _ in entity_ids)}) "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY l.entity_id ORDER BY p.trade_date DESC) = 1",
        entity_ids,
    ).fetchdf()
    m = m.merge(price_row, on="entity_id", how="left")

    m["market_cap"] = m["price"] * m["shares"]
    m["pe"] = np.where(m["ni_ttm"] > 0, m["market_cap"] / m["ni_ttm"], np.nan)
    m["ps"] = m["market_cap"] / m["revenue_ttm"]
    m["earnings_yield"] = m["ebit_ttm"] / m["market_cap"]
    total_debt = m["borrC"].fillna(0) + m["borrN"].fillna(0)
    m["ev_ebitda"] = np.where(m["ebitda_ttm"].notna() & (m["ebitda_ttm"] != 0),
                               (m["market_cap"] + total_debt - m["cash"].fillna(0)) / m["ebitda_ttm"], np.nan)
    m["pb"] = m["market_cap"] / m["equity"]
    fcf = m["cfo"] - m["capex"].abs()
    m["fcf_yield"] = fcf / m["market_cap"]

    m = sector.merge(m, on="entity_id", how="left")
    return m[["entity_id", "symbol", "sector", "pe", "ps", "ev_ebitda", "pb", "fcf_yield", "earnings_yield"]]


def sector_percentile(sector_df: pd.DataFrame, sector_name: str, metric: str, value) -> object:
    """Fraction of same-sector peers with a strictly lower value on this
    one metric (0-100). None if sector unknown or too few peers with data."""
    if sector_name is None or value is None or pd.isna(value):
        return None
    peers = sector_df[(sector_df["sector"] == sector_name) & sector_df[metric].notna()]
    if len(peers) < 3:
        return None
    return float((peers[metric] < value).mean() * 100)


def efficiency_metrics(annual: pd.DataFrame, pl: pd.DataFrame) -> dict:
    if annual.empty:
        return {"available": False}
    rows = []
    for _, r in annual.iterrows():
        revenue_ttm, _ = _asof_ttm_value(pl, "revenue_ttm", r["period_end"])
        assets = r.get("assets")
        asset_turnover = revenue_ttm / assets if (revenue_ttm is not None and pd.notna(assets) and assets != 0) else None
        curA, curL = r.get("curA"), r.get("curL")
        wc_pct_revenue = ((curA - curL) / revenue_ttm * 100) if (
            pd.notna(curA) and pd.notna(curL) and revenue_ttm not in (None, 0)) else None
        rows.append({
            "period_end": r["period_end"], "known_date": r["known_date"],
            "asset_turnover": asset_turnover, "working_capital_pct_revenue": wc_pct_revenue,
        })
    df = pd.DataFrame(rows)
    return {"available": True, "by_year": df}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def build_company_report(con: duckdb.DuckDBPyConnection, identifier: str,
                          momentum_universe: pd.DataFrame | None = None,
                          sector_snapshot: pd.DataFrame | None = None) -> dict:
    """Assembles every section for one company. Pass momentum_universe /
    sector_snapshot in when calling this repeatedly (batch mode) so each is
    computed exactly once rather than once per company."""
    info = resolve_identifier(con, identifier)
    entity_id, isins, symbol = info["entity_id"], info["isins"], info["symbol"]

    if momentum_universe is None:
        momentum_universe = compute_momentum_universe(con)
    as_of = momentum_universe["as_of_date"].max() if not momentum_universe.empty else pd.Timestamp(
        con.execute("SELECT MAX(trade_date) FROM prices_eod").fetchone()[0])

    mom_row = momentum_universe[momentum_universe["entity_id"] == entity_id]
    if mom_row.empty:
        price_row = con.execute(
            "SELECT p.close * af.factor FROM prices_eod p JOIN adjustment_factors af "
            "ON af.entity_id = ? AND af.trade_date = p.trade_date "
            f"WHERE p.isin IN ({','.join('?' for _ in isins)}) AND p.series='EQ' "
            "ORDER BY p.trade_date DESC LIMIT 1",
            [entity_id] + isins,
        ).fetchone()
        latest_price = price_row[0] if price_row else None
        momentum_section = {"available": False, "reason": "not in the currently-active universe "
                             f"(no trade within {ACTIVE_WINDOW_DAYS} days of {as_of.date()})"}
    else:
        r = mom_row.iloc[0]
        latest_price = r["latest_price"]
        momentum_section = {
            "available": True, "as_of_date": r["as_of_date"], "value": r["momentum_12_1"],
            "rank": int(r["rank"]), "n_universe": int(r["n_universe"]), "pct_rank": r["pct_rank"],
            "in_top_decile": bool(r["in_top_decile"]),
        }

    pl = build_quarterly_pl(con, isins)
    shares = _shares_series(con, isins)
    annual = build_annual_frame(con, isins)

    sector_map = load_sector_map()
    sector_row = sector_map[sector_map["symbol"] == symbol]
    sector_name = sector_row["sector"].iloc[0] if not sector_row.empty else None

    valuation = compute_current_valuation(pl, annual, shares, latest_price)
    if sector_snapshot is not None and valuation.get("available"):
        valuation["percentiles"] = {
            metric: sector_percentile(sector_snapshot, sector_name, metric, valuation.get(metric))
            for metric in ["pe", "ps", "ev_ebitda", "pb", "fcf_yield", "earnings_yield"]
        }
    else:
        valuation["percentiles"] = {}

    return {
        "identifier": identifier, "symbol": symbol, "entity_id": entity_id, "sector": sector_name,
        "as_of": as_of, "latest_price": latest_price,
        "momentum": momentum_section,
        "growth": growth_metrics(pl, shares),
        "profitability": profitability_metrics(pl),
        "returns": returns_metrics(annual, pl),
        "balance_sheet": balance_sheet_metrics(annual, pl),
        "cash_flow": cash_flow_metrics(annual, pl),
        "efficiency": efficiency_metrics(annual, pl),
        "valuation": valuation,
    }


# ---------------------------------------------------------------------------
# Rendering -- single-company report and batch table
# ---------------------------------------------------------------------------

def _pct(x, dp=1):
    return f"{x*100:.{dp}f}%" if x is not None and pd.notna(x) else NOT_AVAILABLE


def _ratio(x, dp=2):
    return f"{x:.{dp}f}x" if x is not None and pd.notna(x) else NOT_AVAILABLE


def _num(x, dp=0):
    return f"{x:,.{dp}f}" if x is not None and pd.notna(x) else NOT_AVAILABLE


def _dt(x):
    return pd.Timestamp(x).date().isoformat() if x is not None and pd.notna(x) else NOT_AVAILABLE


def _stale(as_of, known_date):
    d = staleness_days(as_of, known_date)
    return f"{d}d" if d is not None else NOT_AVAILABLE


def render_report(r: dict) -> str:
    as_of = r["as_of"]
    lines = []
    A = lines.append
    A("=" * 88)
    A("RESEARCH TOOL -- NOT A VALIDATED STRATEGY. No composite score, no ranking across metrics.")
    A("This project's own factor studies (FINDINGS.md) apply to momentum_12_1 alone, evaluated")
    A("via a sealed holdout. Nothing on this page has been tested that way. Read, don't select.")
    A("=" * 88)
    A(f"{r['symbol']}  ({r['identifier']})   entity_id={r['entity_id']}   sector={r['sector'] or 'unknown (not in Nifty Total Market list)'}")
    A(f"As of {as_of.date()}   latest price: {_num(r['latest_price'], 2)}")
    A(
        "DATA VINTAGE NOTE: quarterly P&L in this warehouse currently tops out around late 2024 and\n"
        "annual balance-sheet data around FY2024 -- a known, documented gap (SEBI's Integrated Filing\n"
        "transition moved later quarters to a differently-structured feed this tool deliberately does\n"
        "not guess at; see this module's docstring). Every 'latest' figure below is latest AVAILABLE,\n"
        "not latest FILED -- check the staleness numbers, they will often be large."
    )

    A("\n--- MOMENTUM CONTEXT ---")
    m = r["momentum"]
    if m["available"]:
        A(f"momentum_12_1 = {m['value']:+.4f}   rank {m['rank']} of {m['n_universe']} "
          f"(pct_rank {m['pct_rank']*100:.1f})   in top decile: {m['in_top_decile']}")
        A(f"(as of {m['as_of_date'].date()}, currently-active universe only)")
    else:
        A(f"{NOT_AVAILABLE} -- {m['reason']}")

    A("\n--- GROWTH (P&L, full history) ---")
    g = r["growth"]
    if not g.get("available"):
        A(f"{NOT_AVAILABLE} -- {g.get('reason', 'no data')}")
    else:
        A(f"revenue CAGR 3y: {_pct(g['revenue_cagr_3y'])}    revenue CAGR 5y: {_pct(g['revenue_cagr_5y'])}    latest YoY revenue: {_pct(g['revenue_yoy'])}")
        A(f"EPS CAGR 3y:     {_pct(g['eps_cagr_3y'])}    EPS CAGR 5y:     {_pct(g['eps_cagr_5y'])}    latest YoY EPS:     {_pct(g['eps_yoy'])}")
        A(f"(latest quarter known_date {_dt(g['latest_known_date'])}, staleness {_stale(as_of, g['latest_known_date'])})")
        A("\nLast 8 quarters (revenue, PAT, known_date, staleness):")
        q8 = g["last_8_quarters"]
        for _, row in q8.iterrows():
            A(f"  {row['period_end'].date()}  revenue={_num(row['revenue'])}  PAT={_num(row['ni'])}  "
              f"known_date={_dt(row['known_date'])}  staleness={_stale(as_of, row['known_date'])}")

    A("\n--- PROFITABILITY (P&L) ---")
    p = r["profitability"]
    if not p.get("available"):
        A(NOT_AVAILABLE)
    else:
        A(f"EBITDA margin: {_pct(p['ebitda_margin'])}   EBIT margin: {_pct(p['ebit_margin'])}   net margin: {_pct(p['net_margin'])}")
        A(f"(known_date {_dt(p['latest_known_date'])}, staleness {_stale(as_of, p['latest_known_date'])})")
        A("3-year trend (TTM margins by quarter-end):")
        for _, row in p["trend_12q"].iterrows():
            A(f"  {row['period_end'].date()}  EBITDA={_pct(row['ebitda_margin'])}  EBIT={_pct(row['ebit_margin'])}  net={_pct(row['net_margin'])}")

    A("\n--- RETURNS (needs balance sheet, FY2023+ only) ---")
    ret = r["returns"]
    if not ret.get("available"):
        A(f"{NOT_AVAILABLE} -- balance sheet data starts FY2023")
    else:
        by = ret["by_year"]
        A(f"Years available: {', '.join(str(y.date()) for y in by['period_end'])}")
        for _, row in by.iterrows():
            roe_str = f"{NOT_AVAILABLE} -- negative equity, ratio sign not meaningful" if row.get("roe_negative_equity") else _pct(row["roe"])
            roce_str = f"{NOT_AVAILABLE} -- negative capital employed, ratio sign not meaningful" if row.get("roce_negative_capital_employed") else _pct(row["roce"])
            A(f"  FY ending {row['period_end'].date()}: ROE={roe_str}  ROCE={roce_str}  "
              f"known_date={_dt(row['known_date'])}  staleness={_stale(as_of, row['known_date'])}")

    A("\n--- BALANCE SHEET (FY2023+ only) ---")
    bs = r["balance_sheet"]
    if not bs.get("available"):
        A(f"{NOT_AVAILABLE} -- balance sheet data starts FY2023")
    else:
        for _, row in bs["by_year"].iterrows():
            A(f"  FY ending {row['period_end'].date()}: D/E={_ratio(row['debt_equity'])}  "
              f"net debt/EBITDA={_ratio(row['net_debt_ebitda'])}  current ratio={_ratio(row['current_ratio'])}  "
              f"interest coverage={_ratio(row['interest_coverage'])}  known_date={_dt(row['known_date'])}  "
              f"staleness={_stale(as_of, row['known_date'])}")

    A("\n--- CASH FLOW (FY2023+ only) ---")
    cf = r["cash_flow"]
    if not cf.get("available"):
        A(f"{NOT_AVAILABLE} -- cash flow statement data starts FY2023 (annual filings only)")
    else:
        for _, row in cf["by_year"].iterrows():
            A(f"  FY ending {row['period_end'].date()}: CFO={_num(row['cfo'])}  FCF={_num(row['fcf'])}  "
              f"CFO/PAT={_ratio(row['cfo_pat_ratio'])}  known_date={_dt(row['known_date'])}  "
              f"staleness={_stale(as_of, row['known_date'])}")

    A("\n--- EFFICIENCY (FY2023+ only) ---")
    eff = r["efficiency"]
    if not eff.get("available"):
        A(f"{NOT_AVAILABLE} -- balance sheet data starts FY2023")
    else:
        for _, row in eff["by_year"].iterrows():
            A(f"  FY ending {row['period_end'].date()}: asset turnover={_ratio(row['asset_turnover'])}  "
              f"working capital % revenue={_pct(row['working_capital_pct_revenue']/100) if pd.notna(row['working_capital_pct_revenue']) else None}  "
              f"known_date={_dt(row['known_date'])}  staleness={_stale(as_of, row['known_date'])}")

    A("\n--- VALUATION (current price + fundamentals) ---")
    v = r["valuation"]
    if not v.get("available"):
        A(f"{NOT_AVAILABLE} -- insufficient price, shares, or TTM earnings/revenue data")
    else:
        pct = v.get("percentiles", {})

        def _pctile(name):
            p_ = pct.get(name)
            return f"(sector percentile: {p_:.0f})" if p_ is not None else "(sector percentile: unknown -- sector unmapped or too few peers)"

        A(f"market cap: {_num(v['market_cap'])}")
        pe_line = _ratio(v["pe"]) if v["pe"] is not None else f"{NOT_AVAILABLE} -- {v['pe_na_reason']}"
        A(f"P/E:  {pe_line}  {_pctile('pe')}")
        A(f"P/S:  {_ratio(v['ps'])}  {_pctile('ps')}")
        A(f"EV/EBITDA: {_ratio(v['ev_ebitda'])}  {_pctile('ev_ebitda')}"
          + ("" if v["ev_ebitda"] is not None else "  -- needs FY2023+ debt/cash data"))
        A(f"P/B: {_ratio(v['pb'])}  {_pctile('pb')}" + ("" if v["pb"] is not None else "  -- needs FY2023+ equity data"))
        A(f"FCF yield: {_pct(v['fcf_yield'])}  {_pctile('fcf_yield')}"
          + ("" if v["fcf_yield"] is not None else "  -- needs FY2023+ CFO/capex data"))
        A(f"Earnings yield (EBIT/mktcap): {_pct(v['earnings_yield'])}  {_pctile('earnings_yield')}")
        A(f"(P&L known_date {_dt(v.get('pl_known_date'))}, staleness {_stale(as_of, v.get('pl_known_date'))}; "
          f"balance-sheet known_date {_dt(v.get('bs_known_date'))}, staleness {_stale(as_of, v.get('bs_known_date'))})")

    A("=" * 88)
    return "\n".join(lines)


def render_batch_row(r: dict) -> dict:
    """One condensed row for the batch/scan table -- a subset of the full
    report's fields, still individual metrics, still no composite."""
    m, g, p, ret, bs, v = r["momentum"], r["growth"], r["profitability"], r["returns"], r["balance_sheet"], r["valuation"]
    latest_roe = ret["by_year"]["roe"].iloc[-1] if ret.get("available") else None
    latest_de = bs["by_year"]["debt_equity"].iloc[-1] if bs.get("available") else None
    return {
        "symbol": r["symbol"],
        "sector": r["sector"] or "unknown",
        "mom_rank": m["rank"] if m["available"] else None,
        "mom_value": m["value"] if m["available"] else None,
        "revenue_yoy": g.get("revenue_yoy") if g.get("available") else None,
        "eps_yoy": g.get("eps_yoy") if g.get("available") else None,
        "net_margin": p.get("net_margin") if p.get("available") else None,
        "roe": latest_roe,
        "debt_equity": latest_de,
        "pe": v.get("pe") if v.get("available") else None,
        "pb": v.get("pb") if v.get("available") else None,
        "ev_ebitda": v.get("ev_ebitda") if v.get("available") else None,
    }


def render_batch_table(rows: list[dict]) -> str:
    df = pd.DataFrame(rows)
    fmt = df.copy()
    for col in ["revenue_yoy", "eps_yoy", "net_margin", "roe"]:
        fmt[col] = df[col].apply(lambda x: _pct(x) if x is not None else NOT_AVAILABLE)
    for col in ["mom_value"]:
        fmt[col] = df[col].apply(lambda x: f"{x:+.4f}" if x is not None and pd.notna(x) else NOT_AVAILABLE)
    for col in ["debt_equity", "pe", "pb", "ev_ebitda"]:
        fmt[col] = df[col].apply(lambda x: _ratio(x) if x is not None else NOT_AVAILABLE)
    fmt = fmt.sort_values("mom_rank", key=lambda s: s.fillna(10**9))
    header = ("RESEARCH TOOL -- NOT A VALIDATED STRATEGY. Individual metrics only, no composite/rank across "
               "columns. Sorted by momentum rank for scanning convenience only.")
    return header + "\n" + fmt.to_string(index=False)
