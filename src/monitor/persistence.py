"""Momentum-persistence stability monitor -- DESCRIPTIVE ONLY.

======================================================================
WHAT THIS IS AND IS NOT (stated here, in the log header, and in the UI)
======================================================================
This module measures whether momentum_12_1 has recently been ranking
stocks in the same order their subsequent returns turned out. It does
NOT predict returns, does NOT change any position, does NOT emit a
buy/sell/reduce signal, and makes no claim that any regime will persist.
It is Hypothesis A-descriptive from NEW_RESEARCH_DIRECTION.md: a
monitoring log, never a decision rule. Nothing in this module, nor in the
CLI script or web UI built on it, is wired into the screener's filtering
or ranking, triggers any action, or should ever be used to select or tune
a strategy. If a future version ever crosses that line (A-actionable),
that is a DIFFERENT, separately-validated thing, not a change to this
module's scope.

======================================================================
THE STATISTIC (verbatim -- this is the single source of truth)
======================================================================
Per signal date: the cross-sectional Spearman rank correlation between
momentum_12_1 (12-month trailing return, skip most recent month --
factors.momentum.compute_momentum_12_1) and the SAME date's forward
63-trading-day return (factors.target.compute_forward_return), on the
same universe, both gap-guarded (STALE_GAP_DAYS, factors.momentum /
factors.target's own lineage-jump-guard convention). Dates with fewer
than MIN_CROSS_SECTION_N names in the merged cross-section are dropped.

This is EXACTLY the definition scripts/run_momentum_persistence_regime_
count.py already used and reported (3 mechanical regimes, 8 pre-holdout
years, cited in NEW_RESEARCH_DIRECTION.md) -- that script now imports its
computation from this module instead of duplicating it, so the two
cannot drift apart.

**Known discrepancy, flagged rather than silently resolved**: the
regime-count script (and this module, matching it exactly, per
instruction) applies factors.momentum/factors.target's own lineage-jump
guard (Bug #1's fix, ISIN-lineage-transition jumps) but does NOT exclude
the 78 same-ISIN-jump entities BUGS.md Bug #11 found (the MAJESCO-shape
defect) the way every OTHER rigorous computation in this project (the
swing decomposition, the swing V1 checks, the swing V1 holdout read)
does. This was true of the original regime-count script already and is
preserved here unchanged, because the instruction to build this module
was explicit and repeated: reuse that script's definition exactly, do
not redefine it. Whether the published 3-regime figure would change
under the same Bug #11 exclusion used elsewhere is an open question this
module does not resolve -- recorded here so it is visible, not buried.

======================================================================
THE LAG (must be visible everywhere this statistic is shown)
======================================================================
A persistence value for signal date D requires returns through D+63
trading days (factors.target.compute_forward_return's own `eval_date`
column is the real calendar date this realizes on -- never a fixed
calendar offset, since the horizon is defined in trading days). The most
recent measurable value is therefore always ~63 trading days (about a
quarter) behind the latest available price date, by construction, not
as an implementation shortcoming. Every reader of this module's output
(CLI, log, UI) must see BOTH the signal date and the measured-through
date, and the current-state readout states the lag in a plain sentence
(`current_readout()` below) -- never a bare number with no date attached.

======================================================================
POINT-IN-TIME INVARIANT
======================================================================
`compute_daily_persistence`'s optional `as_of` parameter enforces, by
filtering rows on their own `eval_date` BEFORE aggregation (not by
trusting the caller to pre-truncate the panel), that no persistence
value for a given `as_of` uses a return observation realized after
`as_of`. Tested directly in tests/test_monitor_persistence.py.

======================================================================
STUDY 3 FIREWALL -- checked, not assumed, before this module was written
======================================================================
Read directly, this session: `trade-info/STUDY_3_FRESH_DATA_MONITOR.md`,
`trade-info/PREREGISTRATION_FRESH_STUDY.md`, and
`trade-info/FRESH_DATA_CONTRACT.md` (Sections A-E).

**Finding 1, structural**: this module reads trade-new's OWN warehouse
(`data/warehouse.duckdb`, via `data_layer.entity_panel`) exclusively. It
never opens or queries `trade-info/data/nsepit.duckdb`, the database
Study 3's fresh window (`prices_raw`, 2026-01-01 onward) actually lives
in. The Study 3 firewall governs a table this module never reads --
structurally inapplicable, not merely unlikely to matter.

**Finding 2, on the firewall's own wording, checked in case a future
version of this module or a shared warehouse ever changes Finding 1**:
`FRESH_DATA_CONTRACT.md` Section D restricts its firewall to "a model or
strategy evaluated for a pass/fail verdict" -- and Section C explicitly
names "descriptive diagnostics (e.g. dispersion, regime-indicator
audits, placebo comparisons -- the kind of work E1, E1.5, and E2 did)"
as the category distinguished FROM "evidence of an actual tradeable
edge," i.e. explicitly NOT the thing the firewall/study-cap machinery
covers. This module is exactly a regime-indicator audit in that sense:
no pass/fail verdict, no threshold-triggered action, no model. Per the
task's own instruction ("if it covers only model inference, record that
reasoning... and proceed"): recorded here, and this module proceeds.

======================================================================
TRADE-NEW'S OWN HOLDOUT -- the closer, more directly relevant question
======================================================================
Not asked directly by the instruction, but surfaced here because it is
the more operative risk for THIS module's actual implementation: getting
a "measured through" date anywhere near the true latest available price
(rather than being permanently stuck at trade-new's own pre-holdout
boundary) requires reading through `SEALED_HOLDOUT_START` via
`data_layer.entity_panel.read_full_entity_panel_authorized(con,
authorize_holdout=True)` -- the SAME bypass mechanism already used twice
in this project (Study 1's momentum holdout evaluation, swing V1's
holdout evaluation; `FINDINGS.md` Section 7 records the ledger at 2 of 3
project-wide slots spent). This would be a THIRD use of that bypass.

Applying the SAME principle `trade-info`'s own contract states explicitly
(a descriptive, non-pass/fail statistic is not "an evaluation" and does
not increment a study-cap counter -- `FRESH_DATA_CONTRACT.md` Section
C/D, reasoned above by direct analogy since trade-new's own `FINDINGS.md`
has no equivalent written carve-out of its own): this module's read is a
descriptive regime-indicator audit, not an evaluation of any
pre-registered rule against a pass/fail threshold, so it is read here as
NOT charging the third and final project-wide holdout slot. **This is an
inference by analogy, not a rule this project has written down for
itself, flagged here exactly so a human can override it** -- every use
of `authorize_holdout=True` for this module's live/actionable reading is
logged to `data/holdout_access_log.txt` with a description distinguishing
it from the two real evaluative spends, so the distinction is auditable
later regardless of whether this reasoning is ultimately accepted.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return, HORIZON_DAYS

MIN_CROSS_SECTION_N = 20   # dates with fewer names than this are dropped -- matches the reference script exactly
ROLLING_PERIODS = 12       # trailing non-overlapping 63-day periods (~3 years) for the rolling mean/SE
REGIME_CI_Z = 1.96         # ~95% two-sided normal critical value for the "indistinguishable from zero" check


def compute_daily_persistence(panel: pd.DataFrame, jump_dates: dict | None = None,
                               as_of: "dt.date | pd.Timestamp | None" = None) -> pd.DataFrame:
    """[trade_date, persistence, n, max_eval_date] -- one row per signal
    date with >= MIN_CROSS_SECTION_N names in the merged cross-section.

    `as_of`, if given, enforces the point-in-time invariant: every row
    used in any date's correlation has its own `eval_date` <= as_of,
    filtered BEFORE aggregation. If omitted, every forward-return row
    `factors.target.compute_forward_return` itself was willing to return
    is used (which already excludes anything past the panel's own last
    available date, by construction of that function)."""
    mom = compute_momentum_12_1(panel, jump_dates).dropna(subset=["value"]).rename(columns={"value": "mom"})
    fwd = compute_forward_return(panel, unexplained_jump_dates=jump_dates)
    if as_of is not None:
        as_of_ts = pd.Timestamp(as_of)
        fwd = fwd[fwd["eval_date"] <= as_of_ts]

    merged = mom.merge(
        fwd[["entity_id", "trade_date", "eval_date", "fwd_return"]],
        on=["entity_id", "trade_date"], how="inner",
    )

    rows = []
    for d, g in merged.groupby("trade_date"):
        if len(g) < MIN_CROSS_SECTION_N:
            continue
        rho, _ = spearmanr(g["mom"], g["fwd_return"])
        rows.append({"trade_date": d, "persistence": rho, "n": len(g), "max_eval_date": g["eval_date"].max()})

    daily = pd.DataFrame(rows, columns=["trade_date", "persistence", "n", "max_eval_date"])
    if len(daily):
        daily = daily.sort_values("trade_date").reset_index(drop=True)
    return daily


def annual_mean_sign(daily: pd.DataFrame) -> pd.DataFrame:
    """[year, mean_persistence, sign] -- calendar-year mean of the daily
    statistic and its sign. Feeds mechanical_regimes(); this is the SAME
    per-year aggregation the reference script used, not a new one."""
    if daily.empty:
        return pd.DataFrame(columns=["year", "mean_persistence", "sign"])
    d = daily.copy()
    d["year"] = pd.to_datetime(d["trade_date"]).dt.year
    annual = d.groupby("year")["persistence"].mean().reset_index().rename(columns={"persistence": "mean_persistence"})
    annual["sign"] = np.sign(annual["mean_persistence"])
    return annual


def mechanical_regimes(annual: pd.DataFrame) -> list[tuple[int, int, float]]:
    """[(start_year, end_year, sign), ...] -- maximal contiguous runs of
    same-signed annual means. Rule fixed before this module (and the
    reference script it was ported from) was ever run against real data:
    a regime boundary is crossed exactly when consecutive years' annual
    means differ in sign. No magnitude threshold, no smoothing."""
    if annual.empty:
        return []
    years = annual["year"].tolist()
    signs = annual["sign"].tolist()
    regimes = []
    start_idx = 0
    for i in range(1, len(signs)):
        if signs[i] != signs[start_idx]:
            regimes.append((years[start_idx], years[i - 1], signs[start_idx]))
            start_idx = i
    regimes.append((years[start_idx], years[-1], signs[start_idx]))
    return regimes


def nonoverlapping_periods(daily: pd.DataFrame, period_days: int = HORIZON_DAYS) -> pd.DataFrame:
    """[period_index, period_start, period_end, mean_persistence, n_dates]
    -- COMPLETE non-overlapping `period_days`-trading-day blocks only (a
    trailing partial block is dropped, matching the sibling trade-info
    project's own non-overlapping-mature-period convention). The rolling
    mean/SE below reads only from these period-level points, never from
    overlapping daily values, per instruction."""
    cols = ["period_index", "period_start", "period_end", "mean_persistence", "n_dates"]
    if daily.empty:
        return pd.DataFrame(columns=cols)
    dates = daily["trade_date"].tolist()
    vals = daily["persistence"].tolist()
    rows = []
    idx = 0
    period_index = 0
    while idx + period_days <= len(dates):
        block_vals = vals[idx: idx + period_days]
        rows.append({
            "period_index": period_index,
            "period_start": dates[idx],
            "period_end": dates[idx + period_days - 1],
            "mean_persistence": float(np.mean(block_vals)),
            "n_dates": len(block_vals),
        })
        idx += period_days
        period_index += 1
    return pd.DataFrame(rows, columns=cols)


def rolling_mean_se(periods: pd.DataFrame, window: int = ROLLING_PERIODS) -> pd.DataFrame:
    """[period_index, period_end, rolling_mean, se, ci_lo, ci_hi] -- trailing
    mean and standard error over `window` non-overlapping periods, at
    every period index where a full trailing window exists. SE is the
    std of the window's own period-level means / sqrt(window) --
    computed exclusively from non-overlapping period points, never from
    daily (overlapping) values, per instruction."""
    cols = ["period_index", "period_end", "rolling_mean", "se", "ci_lo", "ci_hi"]
    if len(periods) < window:
        return pd.DataFrame(columns=cols)
    vals = periods["mean_persistence"].tolist()
    rows = []
    for i in range(window - 1, len(vals)):
        window_vals = vals[i - window + 1: i + 1]
        m = float(np.mean(window_vals))
        se = float(np.std(window_vals, ddof=1) / np.sqrt(window))
        rows.append({
            "period_index": int(periods["period_index"].iloc[i]),
            "period_end": periods["period_end"].iloc[i],
            "rolling_mean": m, "se": se,
            "ci_lo": m - REGIME_CI_Z * se, "ci_hi": m + REGIME_CI_Z * se,
        })
    return pd.DataFrame(rows, columns=cols)


def label_from_ci(ci_lo: float, ci_hi: float) -> str:
    """'positive' / 'negative' / 'indistinguishable from zero' -- the ONLY
    three labels this module ever produces. The third is not a hedge or a
    weaker synonym for zero: it is what is shown whenever the interval
    spans zero, exactly as often as that is what the data says, per
    instruction not to invent a threshold beyond the regime-count
    script's own (which never needed a CI at all, since it only reports
    a sign, never a confidence-qualified label)."""
    if ci_lo > 0:
        return "positive"
    if ci_hi < 0:
        return "negative"
    return "indistinguishable from zero"


def lag_sentence(signal_date: pd.Timestamp, measured_through: pd.Timestamp) -> str:
    return (
        f"Latest reading covers signals from {signal_date.date().isoformat()}, "
        f"measured through {measured_through.date().isoformat()}. It describes "
        f"the market roughly one quarter ago."
    )


def current_readout(daily: pd.DataFrame, periods: pd.DataFrame, rolling: pd.DataFrame) -> dict:
    """Assembles the plain-language current-state readout -- BOTH dates,
    the lag sentence, and the uncertainty-aware label -- as a dict, so the
    CLI script and the web UI render identical numbers without either one
    re-deriving anything independently."""
    if daily.empty:
        return {"available": False, "reason": "no persistence value computed yet"}

    latest = daily.iloc[-1]
    signal_date = pd.Timestamp(latest["trade_date"])
    measured_through = pd.Timestamp(latest["max_eval_date"])

    base = {
        "available": True,
        "latest_signal_date": signal_date.date().isoformat(),
        "measured_through": measured_through.date().isoformat(),
        "latest_value": float(latest["persistence"]),
        "lag_sentence": lag_sentence(signal_date, measured_through),
    }

    if rolling.empty:
        base.update({
            "rolling_mean": None, "se": None, "ci_lo": None, "ci_hi": None,
            "label": "insufficient history for a rolling read",
            "lag_sentence": base["lag_sentence"] + (
                f" Fewer than {ROLLING_PERIODS} complete 63-trading-day periods "
                f"exist yet for a rolling read."
            ),
        })
        return base

    r = rolling.iloc[-1]
    base.update({
        "rolling_mean": float(r["rolling_mean"]), "se": float(r["se"]),
        "ci_lo": float(r["ci_lo"]), "ci_hi": float(r["ci_hi"]),
        "label": label_from_ci(r["ci_lo"], r["ci_hi"]),
    })
    return base
