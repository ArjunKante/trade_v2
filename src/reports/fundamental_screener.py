"""Fundamental screener: filters the momentum top decile down to a
shortlist. A research tool, not a study -- no slot spent, no
pre-registration.

THIS FILTER IS AN UNTESTED MODIFICATION TO momentum_12_1. The tested,
holdout-passed result (FINDINGS.md) is on the UNFILTERED top decile. This
project has already established (FINDINGS.md Section 12) that testing an
incremental modification's effect needs 8-72 years of data at realistic
effect sizes -- this screener has not been tested at all, in either
direction. It may help or hurt subsequent returns. It is applied here for
its own stated, accepted purpose (reading down a shortlist for further
research), not because it has been shown to improve anything.

KNOWN AND ACCEPTED TRADE-OFF: these filters will remove turnaround
stories -- companies with a recent loss, declining revenue, or a weak
balance sheet that are nonetheless newly showing strong price momentum.
Some of the best individual momentum performers historically are exactly
this shape (a fundamentally weak company where sentiment/fundamentals are
inflecting positively before the accounting catches up). Filtering them
out is a deliberate choice to trade some of momentum's own edge for a
fundamentally-cleaner shortlist, not a free improvement.

METHODOLOGY NOTES, stated once here rather than scattered:
- "Fiscal year" P&L points (for the revenue-decline and net-loss checks)
  are trailing-twelve-month figures at quarters spaced exactly 4 quarters
  apart, walking back from the latest available quarter -- NOT calendar
  fiscal years. This project's P&L data is quarterly-only (no separate
  annual P&L filing exists in this warehouse); this is the same convention
  fundamental_snapshot.py's growth_metrics already uses for CAGR.
- "Declining" (revenue 2+ years, operating margin 3+ quarters) means a
  streak ending AT THE LATEST available point -- a currently-ongoing
  decline, not a decline anywhere in history.
- Same data-vintage caveat as fundamental_snapshot.py: quarterly P&L tops
  out ~late 2024, annual balance sheet ~FY2024, in this warehouse. Every
  check's own known_date/staleness is reported so this is never hidden.
- A check that cannot be computed (missing data or insufficient history)
  is reported as its own status, never silently treated as a pass.

VERDICT PRECEDENCE (fixed, applied uniformly, never overridden per-company):
  1. Any check evaluates to FAIL -> verdict = FAIL.
  2. Else, any required check could not be evaluated -> verdict = INSUFFICIENT DATA.
  3. Else, sector is financials (leverage checks skipped) -> verdict = FINANCIALS-PARTIAL.
  4. Else -> verdict = PASS.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from reports.fundamental_snapshot import (
    resolve_identifier, load_current_price_panel, compute_momentum_universe,
    build_quarterly_pl, build_annual_frame, _shares_series, staleness_days,
    load_sector_map, NOT_AVAILABLE, BS_START,
)

FINANCIALS_SECTOR = "Financial Services"

THRESHOLDS = {
    "debt_equity_max": 2.0,
    "interest_coverage_min": 2.0,
    "cfo_pat_avg_min": 0.5,
}


# ---------------------------------------------------------------------------
# Fiscal-year P&L points (trailing-12m at quarters spaced 4 apart)
# ---------------------------------------------------------------------------

def fiscal_year_points(pl: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    if pl.empty:
        return pd.DataFrame(columns=["period_end", "known_date", "revenue_ttm", "ni_ttm"])
    valid = pl[pl["revenue_ttm"].notna()].reset_index(drop=True)
    if valid.empty:
        return pd.DataFrame(columns=["period_end", "known_date", "revenue_ttm", "ni_ttm"])
    idx = list(range(len(valid) - 1, -1, -4))[:n]
    idx = sorted(idx)
    return valid.iloc[idx][["period_end", "known_date", "revenue_ttm", "ni_ttm"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Tier 1: P&L, full history
# ---------------------------------------------------------------------------

def check_tier1(pl: pd.DataFrame) -> list[dict]:
    checks = []
    fy = fiscal_year_points(pl, n=5)

    if len(fy) < 3:
        checks.append({"tier": 1, "check": "revenue_decline_2y", "status": "NA",
                        "reason": f"only {len(fy)} annual point(s) available, need 3"})
    else:
        r = fy["revenue_ttm"].values
        decline1 = r[-1] < r[-2]
        decline2 = r[-2] < r[-3]
        status = "FAIL" if (decline1 and decline2) else "PASS"
        checks.append({"tier": 1, "check": "revenue_decline_2y", "status": status,
                        "value": f"{r[-3]:,.0f} -> {r[-2]:,.0f} -> {r[-1]:,.0f}",
                        "known_date": fy["known_date"].iloc[-1]})

    if len(fy) < 1:
        checks.append({"tier": 1, "check": "net_loss_latest_fy", "status": "NA", "reason": "no annual point available"})
    else:
        ni = fy["ni_ttm"].iloc[-1]
        status = "FAIL" if ni < 0 else "PASS"
        checks.append({"tier": 1, "check": "net_loss_latest_fy", "status": status,
                        "value": f"{ni:,.0f}", "known_date": fy["known_date"].iloc[-1]})

    if pl.empty:
        checks.append({"tier": 1, "check": "operating_margin_decline_3q", "status": "NA", "reason": "no quarterly P&L"})
    else:
        valid = pl[pl["revenue_ttm"].notna() & (pl["revenue_ttm"] != 0) & pl["ebit_ttm"].notna()].copy()
        valid["op_margin"] = valid["ebit_ttm"] / valid["revenue_ttm"]
        if len(valid) < 4:
            checks.append({"tier": 1, "check": "operating_margin_decline_3q", "status": "NA",
                            "reason": f"only {len(valid)} margin quarter(s) available, need 4"})
        else:
            m = valid["op_margin"].values[-4:]
            declining = m[0] > m[1] > m[2] > m[3]
            status = "FAIL" if declining else "PASS"
            checks.append({"tier": 1, "check": "operating_margin_decline_3q", "status": status,
                            "value": f"{m[0]*100:.1f}% -> {m[1]*100:.1f}% -> {m[2]*100:.1f}% -> {m[3]*100:.1f}%",
                            "known_date": valid["known_date"].iloc[-1]})
    return checks


# ---------------------------------------------------------------------------
# Tier 2: balance sheet, FY2023+
# ---------------------------------------------------------------------------

def check_tier2(annual: pd.DataFrame, pl: pd.DataFrame, is_financials: bool) -> list[dict]:
    checks = []
    if annual.empty:
        reason = "no FY2023+ balance-sheet data at all"
        checks.append({"tier": 2, "check": "debt_equity_max", "status": "SKIPPED (financials)" if is_financials else "NA", "reason": reason})
        checks.append({"tier": 2, "check": "interest_coverage_min", "status": "SKIPPED (financials)" if is_financials else "NA", "reason": reason})
        checks.append({"tier": 2, "check": "cfo_pat_avg_min", "status": "NA", "reason": reason})
        checks.append({"tier": 2, "check": "cfo_negative_latest", "status": "NA", "reason": reason})
        return checks

    last = annual.iloc[-1]

    if is_financials:
        checks.append({"tier": 2, "check": "debt_equity_max", "status": "SKIPPED (financials)",
                        "reason": "sector=Financial Services -- leverage checks not applied"})
        checks.append({"tier": 2, "check": "interest_coverage_min", "status": "SKIPPED (financials)",
                        "reason": "sector=Financial Services -- leverage checks not applied"})
    else:
        borrC, borrN, equity = last.get("borrC"), last.get("borrN"), last.get("equity")
        total_debt = (borrC or 0) + (borrN or 0) if (pd.notna(borrC) or pd.notna(borrN)) else None
        if total_debt is None or pd.isna(equity) or equity == 0:
            checks.append({"tier": 2, "check": "debt_equity_max", "status": "NA", "reason": "debt or equity not disclosed"})
        else:
            de = total_debt / equity
            status = "FAIL" if de > THRESHOLDS["debt_equity_max"] else "PASS"
            checks.append({"tier": 2, "check": "debt_equity_max", "status": status,
                            "value": f"{de:.2f}x (threshold {THRESHOLDS['debt_equity_max']}x)", "known_date": last["known_date"]})

        ebit_ttm, _ = _asof_ttm(pl, "ebit_ttm", last["period_end"])
        fc_ttm, _ = _asof_ttm(pl, "fc_ttm", last["period_end"])
        if ebit_ttm is None or fc_ttm in (None, 0):
            checks.append({"tier": 2, "check": "interest_coverage_min", "status": "NA", "reason": "EBIT or finance costs not available"})
        else:
            ic = ebit_ttm / fc_ttm
            status = "FAIL" if ic < THRESHOLDS["interest_coverage_min"] else "PASS"
            checks.append({"tier": 2, "check": "interest_coverage_min", "status": status,
                            "value": f"{ic:.2f}x (threshold {THRESHOLDS['interest_coverage_min']}x)", "known_date": last["known_date"]})

    if "cfo" not in annual.columns or annual["cfo"].notna().sum() == 0:
        checks.append({"tier": 2, "check": "cfo_pat_avg_min", "status": "NA", "reason": "no CFO disclosed for any FY2023+ year"})
        checks.append({"tier": 2, "check": "cfo_negative_latest", "status": "NA", "reason": "no CFO disclosed for any FY2023+ year"})
    else:
        ratios = []
        for _, r in annual.iterrows():
            cfo = r.get("cfo")
            if pd.isna(cfo):
                continue
            ni_ttm, _ = _asof_ttm(pl, "ni_ttm", r["period_end"])
            if ni_ttm not in (None, 0):
                ratios.append(cfo / ni_ttm)
        if not ratios:
            checks.append({"tier": 2, "check": "cfo_pat_avg_min", "status": "NA", "reason": "CFO present but no matching TTM PAT to ratio against"})
        else:
            avg_ratio = float(np.mean(ratios))
            status = "FAIL" if avg_ratio < THRESHOLDS["cfo_pat_avg_min"] else "PASS"
            checks.append({"tier": 2, "check": "cfo_pat_avg_min", "status": status,
                            "value": f"{avg_ratio:.2f}x avg over {len(ratios)} year(s) (threshold {THRESHOLDS['cfo_pat_avg_min']}x)",
                            "known_date": annual["known_date"].iloc[-1]})

        last_cfo = last.get("cfo")
        if pd.isna(last_cfo):
            checks.append({"tier": 2, "check": "cfo_negative_latest", "status": "NA", "reason": "CFO not disclosed for the latest FY2023+ year"})
        else:
            status = "FAIL" if last_cfo < 0 else "PASS"
            checks.append({"tier": 2, "check": "cfo_negative_latest", "status": status,
                            "value": f"{last_cfo:,.0f}", "known_date": last["known_date"]})
    return checks


def _asof_ttm(pl: pd.DataFrame, col: str, period_end: pd.Timestamp):
    if pl.empty or "period_end" not in pl.columns or col not in pl.columns:
        return None, None
    sub = pl[pl["period_end"] <= period_end]
    if sub.empty or pd.isna(sub[col].iloc[-1]):
        return None, None
    return sub[col].iloc[-1], sub["period_end"].iloc[-1]


# ---------------------------------------------------------------------------
# Tier 3: practical (liquidity tercile, series)
# ---------------------------------------------------------------------------

def compute_liquidity_tercile(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """entity_id -> tercile ('low_liq'/'mid_liq'/'high_liq') at each entity's
    own latest date, same construction as run_momentum_backtest.py (20-day
    rolling median turnover, cross-sectional tercile per trade_date)."""
    panel, as_of = load_current_price_panel(con)
    p = panel.sort_values(["entity_id", "trade_date"]).copy()
    p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
    p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
        lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
        if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index)
    )
    last_date = p.groupby("entity_id")["trade_date"].transform("max")
    latest = p[p["trade_date"] == last_date][["entity_id", "trade_date", "_tercile"]]
    return latest.rename(columns={"trade_date": "as_of_date", "_tercile": "tercile"})


def current_series(con: duckdb.DuckDBPyConnection, isins: list[str]) -> tuple:
    """The series of the single most recent prices_eod row for this entity,
    across ANY series (not just EQ) -- if a name has recently moved to BE/BZ
    surveillance, that would not show up in the EQ-filtered momentum panel
    at all, so this checks the raw table directly."""
    row = con.execute(
        f"SELECT series, trade_date FROM prices_eod WHERE isin IN ({','.join('?' for _ in isins)}) "
        "ORDER BY trade_date DESC LIMIT 1",
        isins,
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def check_tier3(con: duckdb.DuckDBPyConnection, entity_id: str, isins: list[str],
                tercile_df: pd.DataFrame) -> list[dict]:
    checks = []
    trow = tercile_df[tercile_df["entity_id"] == entity_id]
    if trow.empty or pd.isna(trow["tercile"].iloc[0]):
        checks.append({"tier": 3, "check": "bottom_liquidity_tercile", "status": "NA",
                        "reason": "insufficient turnover history for a tercile assignment"})
    else:
        tercile = trow["tercile"].iloc[0]
        status = "FAIL" if tercile == "low_liq" else "PASS"
        checks.append({"tier": 3, "check": "bottom_liquidity_tercile", "status": status,
                        "value": str(tercile)})

    series, series_date = current_series(con, isins)
    if series is None:
        checks.append({"tier": 3, "check": "series_be_bz", "status": "NA", "reason": "no price row found"})
    else:
        status = "FAIL" if series in ("BE", "BZ") else "PASS"
        checks.append({"tier": 3, "check": "series_be_bz", "status": status,
                        "value": f"series={series} as of {series_date}"})
    return checks


# ---------------------------------------------------------------------------
# Per-company evaluation
# ---------------------------------------------------------------------------

def evaluate_company(con: duckdb.DuckDBPyConnection, mom_row: pd.Series, sector_map: pd.DataFrame,
                      tercile_df: pd.DataFrame, company_names: dict) -> dict:
    entity_id, symbol = mom_row["entity_id"], mom_row["symbol"]
    isins = [r[0] for r in con.execute("SELECT isin FROM isin_lineage WHERE entity_id = ?", [entity_id]).fetchall()]
    sector_row = sector_map[sector_map["symbol"] == symbol]
    sector_name = sector_row["sector"].iloc[0] if not sector_row.empty else None
    sector_known = sector_name is not None
    is_financials = sector_name == FINANCIALS_SECTOR

    pl = build_quarterly_pl(con, isins)
    annual = build_annual_frame(con, isins)

    checks = check_tier1(pl) + check_tier2(annual, pl, is_financials) + check_tier3(con, entity_id, isins, tercile_df)

    fails = [c for c in checks if c["status"] == "FAIL"]
    nas = [c for c in checks if c["status"] == "NA"]

    if fails:
        verdict = "FAIL"
    elif nas:
        verdict = "INSUFFICIENT DATA"
    elif is_financials:
        verdict = "FINANCIALS-PARTIAL"
    else:
        verdict = "PASS"

    return {
        "symbol": symbol, "name": company_names.get(entity_id, NOT_AVAILABLE),
        "entity_id": entity_id, "momentum_rank": int(mom_row["rank"]), "momentum_value": mom_row["momentum_12_1"],
        "sector": sector_name, "sector_known": sector_known,
        "verdict": verdict, "checks": checks, "fails": fails, "nas": nas,
    }


def load_company_names(con: duckdb.DuckDBPyConnection, isins: list[str]) -> dict:
    """isin -> most-recent company_name, then reduced to entity_id via the
    caller's own isin->entity_id map (kept separate to avoid re-querying
    isin_lineage per name)."""
    if not isins:
        return {}
    df = con.execute(
        f"SELECT isin, company_name, known_date FROM fundamentals_filings "
        f"WHERE isin IN ({','.join('?' for _ in isins)}) AND company_name IS NOT NULL "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY isin ORDER BY known_date DESC) = 1",
        isins,
    ).fetchdf()
    return dict(zip(df["isin"], df["company_name"]))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_screener(con: duckdb.DuckDBPyConnection) -> dict:
    universe = compute_momentum_universe(con)
    top_decile = universe[universe["in_top_decile"]].sort_values("rank").reset_index(drop=True)
    as_of = universe["as_of_date"].max()

    sector_map = load_sector_map()
    tercile_df = compute_liquidity_tercile(con)

    all_isins = []
    for eid in top_decile["entity_id"]:
        all_isins.extend(r[0] for r in con.execute("SELECT isin FROM isin_lineage WHERE entity_id = ?", [eid]).fetchall())
    name_by_isin = load_company_names(con, all_isins)
    isin_entity = con.execute(
        f"SELECT isin, entity_id FROM isin_lineage WHERE isin IN ({','.join('?' for _ in all_isins)})", all_isins
    ).fetchdf()
    isin_entity["company_name"] = isin_entity["isin"].map(name_by_isin)
    company_names = isin_entity.dropna(subset=["company_name"]).drop_duplicates("entity_id").set_index("entity_id")["company_name"].to_dict()

    results = [evaluate_company(con, row, sector_map, tercile_df, company_names) for _, row in top_decile.iterrows()]

    n_start = len(results)
    after_t1 = sum(1 for r in results if not any(c["tier"] == 1 and c["status"] == "FAIL" for c in r["checks"]))
    after_t2 = sum(1 for r in results if not any(c["tier"] in (1, 2) and c["status"] == "FAIL" for c in r["checks"]))
    after_t3 = sum(1 for r in results if r["verdict"] in ("PASS", "FINANCIALS-PARTIAL"))
    survivors = [r for r in results if r["verdict"] in ("PASS", "FINANCIALS-PARTIAL")]
    insufficient = [r for r in results if r["verdict"] == "INSUFFICIENT DATA"]
    failed = [r for r in results if r["verdict"] == "FAIL"]

    return {
        "as_of": as_of, "n_universe": int(universe["n_universe"].iloc[0]), "results": results,
        "funnel": {"start": n_start, "after_tier1": after_t1, "after_tier2": after_t2, "after_tier3": after_t3},
        "survivors": survivors, "insufficient": insufficient, "failed": failed,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

HEADER = """\
================================================================================================
FUNDAMENTAL SCREENER -- RESEARCH TOOL, NOT A STUDY. No slot spent, no pre-registration.

THIS FILTER IS AN UNTESTED MODIFICATION TO momentum_12_1. The tested, holdout-passed result
(FINDINGS.md) is on the UNFILTERED momentum top decile. This project has established that
testing an incremental modification's effect needs 8-72 years of data at realistic effect
sizes (FINDINGS.md Section 12) -- this screener has not been tested in either direction. It
may help or hurt subsequent returns.

KNOWN AND ACCEPTED TRADE-OFF: these filters will remove turnaround stories -- some of
momentum's historically best individual performers are fundamentally weak companies newly
showing strong price momentum, before the accounting catches up. Filtering them out trades
some of momentum's own edge for a fundamentally-cleaner shortlist. This is not a free
improvement, and is not claimed to be one.

Thresholds were fixed before this run examined which companies they would remove. No
threshold has been adjusted based on this run's output.
================================================================================================"""


def _fmt_check(c: dict) -> str:
    if c["status"] == "FAIL":
        return f"[FAIL] tier{c['tier']}.{c['check']} = {c.get('value', '?')}"
    if c["status"] == "NA":
        return f"[N/A]  tier{c['tier']}.{c['check']} -- {c.get('reason', 'not computable')}"
    if c["status"].startswith("SKIPPED"):
        return f"[SKIP] tier{c['tier']}.{c['check']} -- {c.get('reason', c['status'])}"
    return f"[pass] tier{c['tier']}.{c['check']}" + (f" = {c['value']}" if "value" in c else "")


def render_per_company_line(r: dict) -> str:
    sector_note = ""
    if not r["sector_known"]:
        sector_note = "  [sector unknown -- leverage checks applied without financials exemption]"
    line = f"#{r['momentum_rank']:>4}  {r['symbol']:<12} {r['name'][:40]:<40} verdict={r['verdict']}{sector_note}"
    if r["verdict"] == "FAIL":
        for c in r["fails"]:
            line += "\n         " + _fmt_check(c)
    elif r["verdict"] == "INSUFFICIENT DATA":
        for c in r["nas"]:
            line += "\n         " + _fmt_check(c)
    return line


def render_full_report(result: dict) -> str:
    lines = [HEADER, ""]
    lines.append(f"As of {result['as_of'].date()}   momentum universe size: {result['n_universe']}   "
                 f"top decile evaluated: {result['funnel']['start']}")
    lines.append("")
    lines.append("--- PER-COMPANY VERDICTS (all {} names, none dropped silently) ---".format(result["funnel"]["start"]))
    for r in result["results"]:
        lines.append(render_per_company_line(r))
    lines.append("")

    f = result["funnel"]
    lines.append("--- FUNNEL ---")
    lines.append(f"start (momentum top decile):     {f['start']}")
    lines.append(f"after Tier 1 (P&L):               {f['after_tier1']}")
    lines.append(f"after Tier 2 (balance sheet):     {f['after_tier2']}")
    lines.append(f"after Tier 3 (liquidity/series):  {f['after_tier3']}")
    lines.append(f"  survivors (PASS + FINANCIALS-PARTIAL): {len(result['survivors'])}")
    lines.append(f"  INSUFFICIENT DATA:                     {len(result['insufficient'])}")
    lines.append(f"  FAIL:                                   {len(result['failed'])}")
    lines.append("")

    lines.append("--- SURVIVORS (key metrics, known_date, staleness) ---")
    as_of = result["as_of"]
    for r in result["survivors"]:
        lines.append(f"\n{r['symbol']}  ({r['name']})  momentum_rank={r['momentum_rank']}  "
                     f"momentum_12_1={r['momentum_value']:+.4f}  sector={r['sector'] or 'unknown'}  verdict={r['verdict']}")
        for c in r["checks"]:
            kd = c.get("known_date")
            stale = f", staleness={staleness_days(as_of, kd)}d" if kd is not None else ""
            val = c.get("value", c.get("reason", ""))
            lines.append(f"    tier{c['tier']}.{c['check']}: {c['status']} {val}"
                         + (f"  (known_date={pd.Timestamp(kd).date()}{stale})" if kd is not None else ""))

    lines.append("")
    lines.append("--- INSUFFICIENT DATA (not counted as PASS) ---")
    for r in result["insufficient"]:
        na_str = "; ".join(f"tier{c['tier']}.{c['check']} ({c.get('reason','?')})" for c in r["nas"])
        lines.append(f"{r['symbol']} ({r['name']}) rank={r['momentum_rank']}: {na_str}")

    lines.append("")
    lines.append("--- FAILED (for later cost-of-filter measurement -- no modelling, just a record) ---")
    for r in result["failed"]:
        fail_str = "; ".join(f"tier{c['tier']}.{c['check']}={c.get('value','?')}" for c in r["fails"])
        lines.append(f"{r['symbol']} ({r['name']}) rank={r['momentum_rank']} momentum_12_1={r['momentum_value']:+.4f}: {fail_str}")

    lines.append("")
    lines.append("=" * 96)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diagnostics on a completed run -- descriptive only, no threshold changes,
# no verdict changes. Answers "what is the filter actually doing", not
# "should the filter change."
# ---------------------------------------------------------------------------

ALL_CHECK_NAMES = [
    ("tier1", "revenue_decline_2y"), ("tier1", "net_loss_latest_fy"), ("tier1", "operating_margin_decline_3q"),
    ("tier2", "debt_equity_max"), ("tier2", "interest_coverage_min"), ("tier2", "cfo_pat_avg_min"), ("tier2", "cfo_negative_latest"),
    ("tier3", "bottom_liquidity_tercile"), ("tier3", "series_be_bz"),
]


def fail_breakdown(result: dict) -> dict:
    """Per-metric FAIL counts (a company failing 3 checks counts once
    toward EACH of those 3 metrics -- these are not mutually exclusive),
    plus the distribution of how many checks each failed company failed on
    (1 vs 2+ is a materially different signal, per the request)."""
    per_metric = {f"{t}.{c}": [] for t, c in ALL_CHECK_NAMES}
    n_fails_per_company = []
    for r in result["failed"]:
        n_fails_per_company.append(len(r["fails"]))
        for c in r["fails"]:
            key = f"tier{c['tier']}.{c['check']}"
            per_metric.setdefault(key, []).append(r["symbol"])

    dist = pd.Series(n_fails_per_company).value_counts().sort_index() if n_fails_per_company else pd.Series(dtype=int)
    return {
        "n_failed": len(result["failed"]),
        "per_metric_counts": {k: len(v) for k, v in per_metric.items()},
        "per_metric_symbols": per_metric,
        "n_checks_failed_distribution": dist.to_dict(),
    }


def render_fail_breakdown(fb: dict) -> str:
    lines = ["--- DIAGNOSTIC 1: FAIL BREAKDOWN BY REASON ---",
             f"({fb['n_failed']} total FAILs; counts below are NOT mutually exclusive -- a company "
             "failing 3 checks is counted once in each of those 3 metrics' totals)", ""]
    for tier_label, checks in [("Tier 1 (P&L)", ["tier1.revenue_decline_2y", "tier1.net_loss_latest_fy", "tier1.operating_margin_decline_3q"]),
                                ("Tier 2 (balance sheet)", ["tier2.debt_equity_max", "tier2.interest_coverage_min",
                                                             "tier2.cfo_pat_avg_min", "tier2.cfo_negative_latest"]),
                                ("Tier 3 (practical)", ["tier3.bottom_liquidity_tercile", "tier3.series_be_bz"])]:
        lines.append(tier_label + ":")
        for key in checks:
            n = fb["per_metric_counts"].get(key, 0)
            pct = f" ({n/fb['n_failed']*100:.0f}% of all FAILs)" if fb["n_failed"] else ""
            lines.append(f"  {key:<32} {n:>3}{pct}")
        lines.append("")

    lines.append("Number of checks failed per company (1 = a single borderline metric; 2+ = multiple independent problems):")
    for n_checks, count in sorted(fb["n_checks_failed_distribution"].items()):
        lines.append(f"  failed on exactly {n_checks} check(s): {count} companies")
    multi = sum(c for n, c in fb["n_checks_failed_distribution"].items() if n >= 2)
    single = fb["n_checks_failed_distribution"].get(1, 0)
    lines.append(f"  -> {single} companies failed on a single metric; {multi} failed on 2 or more.")
    lines.append("")

    max_key = max(fb["per_metric_counts"], key=fb["per_metric_counts"].get) if fb["per_metric_counts"] else None
    if max_key:
        max_n = fb["per_metric_counts"][max_key]
        lines.append(f"Single largest contributor: {max_key} ({max_n} of {fb['n_failed']} FAILs, "
                     f"{max_n/fb['n_failed']*100:.0f}% -- {'this metric alone accounts for a large majority of FAILs' if max_n/fb['n_failed'] > 0.5 else 'no single metric dominates'}).")
    return "\n".join(lines)


def insufficient_breakdown(con: duckdb.DuckDBPyConnection, result: dict) -> dict:
    """Splits the INSUFFICIENT DATA group by cause: (a) under 18 months of
    price history, (b) 18+ months but no FY2023+ balance sheet at all,
    (c) has some filings but a specific field/check is missing, (d) other.
    Priority order matches the request's framing: a genuinely-too-new
    listing is classified as (a) regardless of what else is also true for
    it (short history plausibly explains every other gap simultaneously)."""
    as_of = result["as_of"]
    rows = []
    for r in result["insufficient"]:
        isins = [x[0] for x in con.execute("SELECT isin FROM isin_lineage WHERE entity_id = ?", [r["entity_id"]]).fetchall()]
        first_date = con.execute(
            f"SELECT MIN(trade_date) FROM prices_eod WHERE isin IN ({','.join('?' for _ in isins)}) AND series='EQ'",
            isins,
        ).fetchone()[0]
        months = (as_of - pd.Timestamp(first_date)).days / 30.44 if first_date else None

        annual_missing = any(c["check"].startswith(("debt_equity", "interest_coverage", "cfo_")) and
                              c.get("reason", "").startswith("no FY2023+ balance-sheet data at all") for c in r["nas"])

        if months is not None and months < 18:
            category = "a"
        elif annual_missing:
            category = "b"
        elif r["nas"]:
            category = "c"
        else:
            category = "d"  # should not occur given check design; kept as an honest catch-all

        rows.append({
            "symbol": r["symbol"], "name": r["name"], "momentum_rank": r["momentum_rank"],
            "category": category, "listing_date": first_date, "history_months": months,
            "na_reasons": [f"tier{c['tier']}.{c['check']} -- {c.get('reason', '?')}" for c in r["nas"]],
        })

    df = pd.DataFrame(rows)
    return {"rows": df}


def render_insufficient_breakdown(ib: dict) -> str:
    df = ib["rows"]
    lines = ["--- DIAGNOSTIC 2: INSUFFICIENT DATA GROUP, SPLIT BY CAUSE ---",
             f"({len(df)} total INSUFFICIENT DATA. Priority: (a) short history overrides (b)/(c) even if also true.)", ""]

    counts = df["category"].value_counts()
    labels = {"a": "(a) under 18 months of price history -- genuinely too new to rule on",
              "b": "(b) 18+ months of price history but no FY2023+ balance-sheet filing at all",
              "c": "(c) has some filings, but a specific required field/check is missing",
              "d": "(d) other (did not fit a or b or c)"}
    for cat in ["a", "b", "c", "d"]:
        lines.append(f"  {labels[cat]}: {int(counts.get(cat, 0))}")
    lines.append("")

    lines.append("Group (a) detail -- price-history length and listing date (first EQ trade in this warehouse):")
    a_rows = df[df["category"] == "a"].sort_values("history_months")
    for _, row in a_rows.iterrows():
        ld = row["listing_date"].isoformat() if row["listing_date"] is not None else NOT_AVAILABLE
        hm = f"{row['history_months']:.1f}mo" if row["history_months"] is not None else NOT_AVAILABLE
        lines.append(f"  {row['symbol']:<12} rank={row['momentum_rank']:>4}  history={hm:>8}  listing_date~={ld}")
    lines.append("")

    lines.append("Group (b) detail -- mature by price history, balance sheet simply not filed/extracted yet:")
    for _, row in df[df["category"] == "b"].iterrows():
        lines.append(f"  {row['symbol']:<12} rank={row['momentum_rank']:>4}  history={row['history_months']:.1f}mo")
    lines.append("")

    lines.append("Group (c) detail -- specific missing field/check named per company:")
    for _, row in df[df["category"] == "c"].iterrows():
        lines.append(f"  {row['symbol']:<12} rank={row['momentum_rank']:>4}:")
        for reason in row["na_reasons"]:
            lines.append(f"      {reason}")

    if (df["category"] == "d").any():
        lines.append("")
        lines.append("Group (d) detail:")
        for _, row in df[df["category"] == "d"].iterrows():
            lines.append(f"  {row['symbol']:<12} rank={row['momentum_rank']:>4}: {'; '.join(row['na_reasons'])}")
    return "\n".join(lines)


def render_diagnostics(fb: dict, ib: dict, source_run_label: str) -> str:
    header = (
        "================================================================================================\n"
        f"DIAGNOSTICS on run: {source_run_label}\n"
        "Descriptive only -- NO thresholds changed, NO verdicts reclassified as a result of this report.\n"
        "================================================================================================\n"
    )
    return header + "\n" + render_fail_breakdown(fb) + "\n\n" + render_insufficient_breakdown(ib) + "\n"


def write_diagnostics_log(text: str, root: Path) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = root / "data" / "screener_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"fundamental_screener_diagnostics_{ts}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def write_log(report_text: str, root: Path) -> Path:
    """Writes exactly the text already rendered/printed -- never a
    separately-recomputed version -- so the log is provably what was shown,
    not a second, possibly-divergent render."""
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = root / "data" / "screener_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"fundamental_screener_{ts}.txt"
    path.write_text(report_text, encoding="utf-8")
    return path
