"""Phase E factor computation from quarterly + annual XBRL facts.

Context convention, verified against real data before writing this (SEBI's
mandatory 6-column quarterly comparison table, `in-bse-fin` taxonomy):
context "OneD"/"OneI" = the CURRENT quarter/current instant (duration and
point-in-time facts respectively) -- "Two" preceding quarter, "Three"
corresponding quarter prior year, "Four"/"Five" year-to-date current/prior,
"Six" full prior year. Only One* is used here; using Four* by mistake would
silently sum cumulative YTD figures into a TTM calculation as if they were
one quarter, overstating every TTM figure. Confirmed via real VSTTILLERS
values (OneD revenue 2.19B vs FourD 6.93B for the same quarter, ~3.16x --
consistent with 1-quarter vs 9-month cumulative, not a coincidence).

TTM is computed by summing the CURRENT-QUARTER (One*) value across the
trailing 4 quarters by each company's own period_end sequence -- never by
calendar-quarter assumption, since 3.90% of companies use a non-March
fiscal year (Phase A finding).
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

QUARTERLY_SOURCE = "NSE_XBRL_QUARTERLY_FACTS"
ANNUAL_SOURCE = "NSE_XBRL_ANNUAL_BALANCE_SHEET"


def load_quarterly_tag(con: duckdb.DuckDBPyConnection, tag: str, instant: bool = False) -> pd.DataFrame:
    """One row per (isin, period_end): the CURRENT-quarter (One*) value for
    a single tag, numeric, deduped to the point-in-time-correct filing per
    fundamentals_pit's own logic (consolidated-preferred, latest restatement)."""
    ctx = "OneI" if instant else "OneD"
    sql = """
        SELECT f.isin, f.period_end, f.consolidated, f.seq_number,
               TRY_CAST(f.value AS DOUBLE) AS value, f.known_date
        FROM fundamentals_xbrl_facts f
        WHERE f.source = ? AND f.tag = ? AND f.context_ref = ?
    """
    df = con.execute(sql, [QUARTERLY_SOURCE, tag, ctx]).fetchdf()
    df = df.dropna(subset=["value"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["known_date"] = pd.to_datetime(df["known_date"])
    return df


def load_annual_tag(con: duckdb.DuckDBPyConnection, tag: str) -> pd.DataFrame:
    """Annual balance-sheet tags: no One*/Four* convention issue (annual
    filings report one period), value taken as-is."""
    sql = """
        SELECT isin, period_end, consolidated, seq_number,
               TRY_CAST(value AS DOUBLE) AS value, known_date
        FROM fundamentals_xbrl_facts
        WHERE source = ? AND tag = ?
    """
    df = con.execute(sql, [ANNUAL_SOURCE, tag]).fetchdf()
    df = df.dropna(subset=["value"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["known_date"] = pd.to_datetime(df["known_date"])
    return df


def _pick_pit_series(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse to one row per (isin, period_end): consolidated preferred
    (only falling back to standalone when no consolidated row exists for
    that quarter), then the latest known_date among rows of the winning
    type (restatement-aware). Two-step by construction, not a single sort
    + last() -- that shape silently picked the wrong preference in testing
    (last() surfaces the max of the sort key, which put non-consolidated
    last when preference was encoded ascending) and is exactly the kind of
    bug a synthetic test exists to catch before real data hides it."""
    df = df.copy()
    has_consolidated = (
        df[df["consolidated"] == "Consolidated"][["isin", "period_end"]]
        .drop_duplicates().assign(_has_cons=True)
    )
    df = df.merge(has_consolidated, on=["isin", "period_end"], how="left")
    df["_has_cons"] = df["_has_cons"].fillna(False)
    keep = ((df["_has_cons"]) & (df["consolidated"] == "Consolidated")) | (~df["_has_cons"])
    df = df[keep].drop(columns=["_has_cons"])

    df = df.sort_values(["isin", "period_end", "known_date"])
    return df.groupby(["isin", "period_end"], as_index=False).last()


def compute_ttm(quarterly_series: pd.DataFrame, as_of_dates: pd.DataFrame) -> pd.DataFrame:
    """quarterly_series: columns [isin, period_end, value, known_date], one
    row per (isin, period_end), already point-in-time-picked.
    as_of_dates: columns [isin, trade_date] -- the dates to compute TTM as of.

    Returns [isin, trade_date, ttm_value, n_quarters_summed, latest_period_end,
    latest_known_date] -- n_quarters_summed < 4 means TTM is not yet fully
    formed for that entity at that date (reported, not silently dropped).

    Vectorized via merge_asof rather than a per-(isin, as_of) Python loop --
    the original loop-based version is still the reference semantics (and
    still what tests/test_fundamentals_factors_ttm.py exercises); this
    computes the same result without one dataframe filter per combination,
    which at ~2,000 entities x ~24 dates x 7 tags did not finish in a
    reasonable time. merge_asof only finds the latest VISIBLE quarter by
    q_idx; it does NOT assume the 3 preceding quarters (by period_end order)
    are also visible -- each offset's own known_date is checked explicitly
    against as_of before being included, so a quarter filed out of period_end
    order (rare, but the whole reason a per-row check exists rather than an
    assumption) still can't leak early.
    """
    qs = _pick_pit_series(quarterly_series).sort_values(["isin", "period_end"]).reset_index(drop=True)
    if qs.empty or as_of_dates.empty:
        return pd.DataFrame(columns=["isin", "trade_date", "ttm_value", "n_quarters_summed",
                                      "latest_period_end", "latest_known_date"])
    qs["q_idx"] = qs.groupby("isin").cumcount()

    left = as_of_dates.sort_values("trade_date").reset_index(drop=True)
    right = qs[["isin", "known_date", "q_idx", "period_end"]].sort_values("known_date")
    latest = pd.merge_asof(left, right, left_on="trade_date", right_on="known_date",
                            by="isin", direction="backward")
    latest = latest.dropna(subset=["q_idx"])
    latest["q_idx"] = latest["q_idx"].astype(int)

    value_lookup = qs.set_index(["isin", "q_idx"])["value"]
    known_date_lookup = qs.set_index(["isin", "q_idx"])["known_date"]

    for offset in range(4):
        key = pd.MultiIndex.from_arrays([latest["isin"], latest["q_idx"] - offset])
        vals = value_lookup.reindex(key).values
        kds = known_date_lookup.reindex(key).values
        # explicit per-offset visibility check -- do not assume it from the latest quarter alone
        as_of_arr = latest["trade_date"].values
        visible_mask = pd.notna(kds) & (pd.to_datetime(kds) <= pd.to_datetime(as_of_arr))
        latest[f"_v{offset}"] = np.where(visible_mask, vals, np.nan)

    value_cols = [f"_v{o}" for o in range(4)]
    latest["ttm_value"] = latest[value_cols].sum(axis=1, skipna=True)
    latest["n_quarters_summed"] = latest[value_cols].notna().sum(axis=1)
    latest = latest[latest["n_quarters_summed"] > 0]
    latest["latest_period_end"] = latest["period_end"]
    latest["latest_known_date"] = latest["known_date"]
    return latest[["isin", "trade_date", "ttm_value", "n_quarters_summed",
                   "latest_period_end", "latest_known_date"]].reset_index(drop=True)


def compute_staleness_days(ttm_df: pd.DataFrame) -> pd.Series:
    return (pd.to_datetime(ttm_df["trade_date"]) - pd.to_datetime(ttm_df["latest_known_date"])).dt.days


def compute_shares_outstanding(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """shares = PaidUpValueOfEquityShareCapital / FaceValueOfEquityShareCapital,
    per (isin, period_end), point-in-time picked. Both tags come from the
    'OneD' context (they are duration-period disclosures in the SEBI format,
    confirmed present alongside P&L facts in the same filings)."""
    paidup = load_quarterly_tag(con, "PaidUpValueOfEquityShareCapital")
    faceval = load_quarterly_tag(con, "FaceValueOfEquityShareCapital")
    paidup_pit = _pick_pit_series(paidup)[["isin", "period_end", "value", "known_date"]].rename(columns={"value": "paidup"})
    faceval_pit = _pick_pit_series(faceval)[["isin", "period_end", "value"]].rename(columns={"value": "faceval"})
    merged = paidup_pit.merge(faceval_pit, on=["isin", "period_end"], how="inner")
    merged = merged[merged["faceval"] > 0]
    merged["shares_outstanding"] = merged["paidup"] / merged["faceval"]
    return merged[["isin", "period_end", "known_date", "shares_outstanding"]]


def pit_shares_outstanding_asof(shares_df: pd.DataFrame, as_of_dates: pd.DataFrame) -> pd.DataFrame:
    """Most recent known shares_outstanding per (isin, trade_date), never
    a future or current-day count applied backward.

    Vectorized via merge_asof -- see pit_latest_value_asof, which this now
    delegates to (same "latest known value as of date" shape as any other
    single-value point-in-time lookup)."""
    out = pit_latest_value_asof(
        shares_df.rename(columns={"shares_outstanding": "value"}), as_of_dates
    )
    return out.rename(columns={"value": "shares_outstanding", "known_date": "shares_known_date"})


def pit_latest_value_asof(value_df: pd.DataFrame, as_of_dates: pd.DataFrame) -> pd.DataFrame:
    """Generic point-in-time lookup: for each (isin, trade_date) in
    as_of_dates, the most recent row of value_df (columns [isin, known_date,
    value, ...]) with known_date <= trade_date. Replaces the per-(isin,
    as_of) nested-loop pattern that made the annual-tag lookups in
    scripts/run_phase_e_factors.py (7 calls: assets, equity, curL, curA,
    borrC, borrN, cfo) the single largest cost in the original Phase E run --
    each call was its own O(entities x dates) Python loop; merge_asof does
    the equivalent lookup as one sorted-merge per call.

    value_df may have extra columns (e.g. period_end) -- all are carried
    through via a plain merge_asof, since (unlike compute_ttm) there is no
    multi-quarter reconstruction here that could leak an out-of-order value:
    a single "latest visible row" is exactly what merge_asof(direction=
    'backward') computes directly, with no additional per-row check needed."""
    value_df = value_df.dropna(subset=["known_date"]).sort_values("known_date")
    left = as_of_dates.sort_values("trade_date").reset_index(drop=True)
    out = pd.merge_asof(left, value_df, left_on="trade_date", right_on="known_date",
                         by="isin", direction="backward")
    return out.dropna(subset=["known_date"]).reset_index(drop=True)
