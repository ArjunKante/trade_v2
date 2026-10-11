"""Orchestrates one full run of the per-stock weekly study: ties universe,
weekly/sigma, rules, and stats together into the full stock x rule trial
table PER_STOCK.md's report is rendered from. No result from this module
is final until `apply_bonferroni_and_conflicts` has run across ALL trials
(Bonferroni needs the total trial count, and the "both rules qualify ->
drop both" rule needs every rule's verdict for the same stock) -- a single
trial's own numbers are never a complete verdict on their own.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from fibo.daily_ohlc import build_daily_ohlc_panel
from per_stock.rules import RULES, generate_trades, precompute_week_days
from per_stock.stats import (
    FIT_T_MIN, MIN_CHECK_TRADES, NULL_BEAT_PERCENTILE,
    bonferroni_alpha, null_percentile, random_entry_null, split_fit_check, t_test_mean_gt_zero,
)
from per_stock.weekly import build_weekly_panel_with_sigma

EMPTY_STATS = {"n": 0, "mean": float("nan"), "std": float("nan"), "t_stat": float("nan"), "p_value": float("nan")}


def evaluate_trial(weekly: pd.DataFrame, week_days: dict, entity_id: str, symbol: str, rule: str) -> dict:
    """One (stock, rule) trial's full set of numbers -- every condition
    reported individually (never collapsed into just a final bool) so a
    rejected trial's report row shows WHICH condition(s) it failed.
    `week_days`: per_stock.rules.precompute_week_days's cache for this
    entity, built once and reused across both rules and every null seed."""
    trades = generate_trades(weekly, week_days, entity_id, rule)
    fit, check = split_fit_check(trades)

    fit_stats = t_test_mean_gt_zero(fit["net_return"]) if not fit.empty else dict(EMPTY_STATS)
    check_stats = t_test_mean_gt_zero(check["net_return"]) if not check.empty else dict(EMPTY_STATS)

    fit_pass_mean = (not pd.isna(fit_stats["mean"])) and fit_stats["mean"] > 0
    fit_pass_t = (not pd.isna(fit_stats["t_stat"])) and fit_stats["t_stat"] >= FIT_T_MIN
    check_pass_mean = (not pd.isna(check_stats["mean"])) and check_stats["mean"] > 0
    check_pass_n = check_stats["n"] >= MIN_CHECK_TRADES

    n_check = check_stats["n"]
    if check_pass_n:
        null_means = random_entry_null(weekly, week_days, entity_id, n_check)
    else:
        null_means = np.array([])
    pctl = null_percentile(check_stats["mean"], null_means) if null_means.size else float("nan")
    beats_null = (not pd.isna(pctl)) and pctl >= NULL_BEAT_PERCENTILE

    return {
        "entity_id": entity_id, "symbol": symbol, "rule": rule,
        "fit_n": fit_stats["n"], "fit_mean": fit_stats["mean"], "fit_std": fit_stats["std"],
        "fit_t": fit_stats["t_stat"], "fit_p": fit_stats["p_value"],
        "check_n": check_stats["n"], "check_mean": check_stats["mean"], "check_std": check_stats["std"],
        "check_t": check_stats["t_stat"], "check_p": check_stats["p_value"],
        "fit_pass_mean": fit_pass_mean, "fit_pass_t": fit_pass_t,
        "check_pass_mean": check_pass_mean, "check_pass_n": check_pass_n,
        "null_percentile": pctl, "beats_null": beats_null, "n_null_draws": int(null_means.size),
        "n_all_trades": len(trades),
    }


def run_all_trials(con: duckdb.DuckDBPyConnection, universe: pd.DataFrame) -> pd.DataFrame:
    """`universe`: entity_id/symbol rows that already passed the screener
    gate (per_stock.universe.build_study_universe, filtered to
    screener_pass). One row per (stock, rule) -- up to 2 x len(universe)."""
    entity_ids = universe["entity_id"].tolist()
    weekly = build_weekly_panel_with_sigma(con, entity_ids)
    daily = build_daily_ohlc_panel(con, entity_ids=entity_ids)

    rows = []
    for _, u in universe.iterrows():
        week_days = precompute_week_days(daily, u["entity_id"])
        for rule in RULES:
            rows.append(evaluate_trial(weekly, week_days, u["entity_id"], u["symbol"], rule))
    return pd.DataFrame(rows)


def apply_bonferroni_and_conflicts(trials: pd.DataFrame) -> pd.DataFrame:
    """Adds `n_trials_run` (trials with a computable FIT p-value --
    Bonferroni's denominator), `bonferroni_alpha`, `bonferroni_pass`, the
    combined `qualifies` (every pre-registered condition true), and
    `kept` -- `qualifies` UNLESS the stock's OTHER rule also qualifies, in
    which case BOTH are set to kept=False (conflicting evidence, per
    spec: "if both rules qualify for a stock, keep neither")."""
    out = trials.copy()
    n_trials_run = int(out["fit_p"].notna().sum())
    alpha_adj = bonferroni_alpha(n_trials_run) if n_trials_run else float("nan")
    out["n_trials_run"] = n_trials_run
    out["bonferroni_alpha"] = alpha_adj
    out["bonferroni_pass"] = out["fit_p"].notna() & (out["fit_p"] <= alpha_adj)

    out["qualifies"] = (
        out["fit_pass_mean"] & out["fit_pass_t"] & out["check_pass_mean"] & out["check_pass_n"]
        & out["bonferroni_pass"] & out["beats_null"]
    )

    qualify_counts = out.groupby("entity_id")["qualifies"].sum()
    conflicted = set(qualify_counts[qualify_counts > 1].index)
    out["conflicted_stock"] = out["entity_id"].isin(conflicted)
    out["kept"] = out["qualifies"] & ~out["conflicted_stock"]
    return out
