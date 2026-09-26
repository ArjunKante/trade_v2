"""Phase 3: the frozen rule's backtest, plus benchmarks. See
PREREGISTRATION_SWING.md for the frozen thresholds; this module does not
change any of them.

TRADE CONSTRUCTION: entry at the open of the trading day immediately after
the signal date (the entity's OWN next trading row, not calendar-next-day),
exit at the open 5 trading days after entry (the entity's own row+5) --
built by reusing factors.target.compute_forward_return (already tested,
already STALE_GAP_DAYS-guarded) on an adjusted-OPEN series instead of
close. This is the same mechanism, same gap discipline, just applied to
the exact open-to-open construction this rule specifies instead of
close-to-close.

CAPITAL: this backtest assumes UNLIMITED capital -- every qualifying
signal is taken, regardless of how much capital that would require
concurrently. Per PREREGISTRATION_SWING.md's "What is NOT being tested"
section, portfolio-level capital-constraint modeling is explicitly out of
scope; peak concurrent capital is measured and reported as a downstream
finding, never enforced as a limit here.

EQUITY CURVE: daily bhavcopy data has no intraday marks, so each trade's
P&L is booked in full on its EXIT date (a lump-sum realized-P&L curve),
not smoothed across the holding days -- the standard simplification for a
trade-list backtest without intraday marks. Because every trade uses the
SAME fixed position size (Rs 3L or Rs 5L, never compounded into a growing
base), summing per-trade fractional returns is proportional to summing
rupee P&L directly -- reported in both units at report time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factors.target import compute_forward_return

HOLD_DAYS = 5


def build_open_close_panel(con, before) -> pd.DataFrame:
    """[entity_id, trade_date, isin, adjusted_open, adjusted_close, volume,
    turnover], strictly before `before` -- same JOIN pattern as
    data_layer.entity_panel.materialize_entity_panel (prices_eod +
    isin_lineage + adjustment_factors), extended with the open column
    (read_entity_panel/entity_prices_daily does not carry it). Read-only
    against the existing data layer; no schema or table change."""
    sql = """
        SELECT l.entity_id, p.trade_date, p.isin, p.open * af.factor AS adjusted_open,
               p.close * af.factor AS adjusted_close, p.volume, p.turnover
        FROM prices_eod p
        JOIN isin_lineage l ON p.isin = l.isin
        JOIN adjustment_factors af ON af.entity_id = l.entity_id AND af.trade_date = p.trade_date
        WHERE p.series = 'EQ' AND p.trade_date < ? AND p.open > 0 AND p.close > 0
    """
    df = con.execute(sql, [before]).fetchdf()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.sort_values(["entity_id", "trade_date"]).reset_index(drop=True)


def entry_exit_returns(panel: pd.DataFrame, unexplained_jump_dates: dict | None = None) -> pd.DataFrame:
    """[entity_id, trade_date(=ENTRY date), eval_date(=EXIT date),
    fwd_return(=gross entry-to-exit open-to-open return)] -- for EVERY
    row, not just signal rows (cheap to precompute once, then looked up
    per signal set). Reuses factors.target.compute_forward_return on the
    adjusted_open series (renamed to satisfy its interface), horizon=5:
    exactly entry -> 5 trading days later, gap-guarded identically to
    every other forward return in this project."""
    # drop adjusted_close BEFORE renaming adjusted_open -> adjusted_close, or a panel that
    # carries both columns (as build_open_close_panel's does) ends up with two columns of
    # the same name -- silently turns every groupby-column selection into a DataFrame
    # instead of a Series, which breaks compute_forward_return's internal shift() assignment.
    open_panel = panel[["entity_id", "trade_date", "adjusted_open"]].rename(
        columns={"adjusted_open": "adjusted_close"})
    return compute_forward_return(open_panel, horizon=HOLD_DAYS, unexplained_jump_dates=unexplained_jump_dates)


def attach_trades_to_signals(signals: pd.DataFrame, panel: pd.DataFrame, entry_exit: pd.DataFrame) -> pd.DataFrame:
    """signals: [entity_id, trade_date(=SIGNAL date)]. Maps each signal to
    its entry date (the entity's own next trading row) and looks up that
    entry's precomputed gross open-to-open 5-day return. Signals whose
    entity has no next trading row, or whose entry falls inside a
    stale-gap window (already NaN'd out by entry_exit_returns), are
    dropped -- no trade, same as every other gap-guarded computation in
    this project."""
    p = panel.sort_values(["entity_id", "trade_date"])[["entity_id", "trade_date"]].copy()
    p["entry_date"] = p.groupby("entity_id")["trade_date"].shift(-1)
    sig = signals.merge(p, on=["entity_id", "trade_date"], how="left").dropna(subset=["entry_date"])
    trades = sig.merge(
        entry_exit.rename(columns={"trade_date": "entry_date", "eval_date": "exit_date", "fwd_return": "gross_return"}),
        on=["entity_id", "entry_date"], how="inner",
    )
    return trades[["entity_id", "trade_date", "entry_date", "exit_date", "gross_return"]].rename(
        columns={"trade_date": "signal_date"}).reset_index(drop=True)


def concurrent_positions(trades: pd.DataFrame, all_dates: pd.Index) -> pd.Series:
    """Event-sweep over the full trading calendar: +1 on a trade's entry
    date, -1 on its exit date (a position is open from entry up to but not
    including exit, since it is SOLD at the exit date's open)."""
    entries = trades["entry_date"].value_counts()
    exits = trades["exit_date"].value_counts()
    delta = pd.Series(0.0, index=all_dates)
    delta = delta.add(entries.reindex(all_dates, fill_value=0), fill_value=0)
    delta = delta.subtract(exits.reindex(all_dates, fill_value=0), fill_value=0)
    return delta.cumsum()


def trade_stats(trades: pd.DataFrame, cost_bps: float, trades_per_year: float) -> dict:
    """Standard trade-list stats on net-of-cost returns (fractional, one
    unit = one position's own cost basis). Call once per cost_bps end
    (lo, hi) -- never blended into a single midpoint cost."""
    net = trades["gross_return"] - cost_bps / 10_000
    wins = net[net > 0]
    losses = net[net <= 0]
    n = len(net)
    win_rate = len(wins) / n if n else float("nan")
    avg_win = wins.mean() if len(wins) else float("nan")
    avg_loss = losses.mean() if len(losses) else float("nan")
    expectancy = net.mean() if n else float("nan")
    loss_sum = losses.sum()
    profit_factor = (wins.sum() / abs(loss_sum)) if loss_sum != 0 else float("inf")
    sharpe = (net.mean() / net.std() * np.sqrt(trades_per_year)) if n > 1 and net.std() > 0 else float("nan")

    return {
        "n_trades": n, "win_rate": win_rate, "avg_win": avg_win, "avg_loss": avg_loss,
        "expectancy": expectancy, "profit_factor": profit_factor, "sharpe_annualized": sharpe,
    }


def equity_curve_drawdown(trades: pd.DataFrame, cost_bps: float, position_size: float,
                           starting_capital: float) -> dict:
    """Max drawdown on an actual RUPEE equity curve, not a dimensionless
    sum-of-fractional-returns (which is uninterpretable once trades
    overlap -- see the correction this replaces). starting_capital is a
    STATED input, not computed here: the caller should state where it
    came from (e.g. the measured peak concurrent capital this exact trade
    set required, so the curve never needs more capital than it started
    with -- an unlimited-capital backtest's own peak, not an arbitrary
    number).

    Equity is realized-P&L-only: each trade's rupee P&L (net return x
    position_size) is booked in full on its exit date, since daily
    bhavcopy data has no intraday marks to smooth it across the holding
    period -- the curve is a step function at each exit, not a
    day-by-day mark-to-market."""
    net = trades["gross_return"] - cost_bps / 10_000
    pnl_rs = net * position_size
    ordered = trades.assign(pnl_rs=pnl_rs).sort_values("exit_date")
    equity = starting_capital + ordered["pnl_rs"].cumsum()
    running_max = equity.cummax()
    drawdown_rs = equity - running_max
    max_dd_rs = drawdown_rs.min() if len(drawdown_rs) else float("nan")
    max_dd_pct = (max_dd_rs / running_max.loc[drawdown_rs.idxmin()]) if len(drawdown_rs) and pd.notna(max_dd_rs) else float("nan")
    return {
        "starting_capital": starting_capital, "ending_equity": equity.iloc[-1] if len(equity) else starting_capital,
        "max_drawdown_rs": max_dd_rs, "max_drawdown_pct_of_peak": max_dd_pct,
    }


def random_entry_benchmark(strategy_trades: pd.DataFrame, eligible_trades: pd.DataFrame,
                            n_seeds: int = 1000, seed0: int = 0) -> pd.DataFrame:
    """For each signal_date the STRATEGY actually traded, draw the SAME
    number of entities at random from `eligible_trades` (a PRECOMPUTED
    trade set for the whole stage-1 candidate universe -- e.g. the
    buy-and-hold benchmark's own trades, reused here rather than
    recomputed) instead of the strategy's own selections -- matched trade
    count and timing, per instruction. Repeated n_seeds times.

    Deliberately does all its work in plain numpy arrays, not pandas
    merges, inside the seed loop -- an earlier version merged against a
    multi-million-row table once per seed and took >8 minutes for 1000
    seeds; this version precomputes one (entities, returns) numpy pair
    per day ONCE, then only does numpy indexing per seed."""
    counts_per_day = strategy_trades.groupby("signal_date").size()
    by_day = {day: (g["entity_id"].to_numpy(), g["gross_return"].to_numpy())
              for day, g in eligible_trades.groupby("signal_date")}

    rows = []
    for seed in range(seed0, seed0 + n_seeds):
        rng = np.random.default_rng(seed)
        picked = []
        for day, k in counts_per_day.items():
            pair = by_day.get(day)
            if pair is None:
                continue
            entities, returns = pair
            if len(entities) == 0:
                continue
            k = min(k, len(entities))
            idx = rng.choice(len(entities), size=k, replace=False)
            picked.append(returns[idx])
        if not picked:
            continue
        arr = np.concatenate(picked)
        rows.append({"seed": seed, "n_trades": len(arr), "mean_gross_return": arr.mean(),
                     "std_gross_return": arr.std()})
    return pd.DataFrame(rows)


def coin_flip_benchmark(strategy_trades: pd.DataFrame, n_seeds: int = 1000, seed0: int = 0) -> pd.DataFrame:
    """Same trades (same entities, same dates) as the real strategy, but
    each trade's sign is randomized 50/50 (long vs. short) per seed --
    tests whether merely being present on these specific (entity, date)
    pairs carries a directionless bias (survivorship, look-ahead) rather
    than testing a trading rule."""
    gross = strategy_trades["gross_return"].to_numpy()
    rows = []
    for seed in range(seed0, seed0 + n_seeds):
        rng = np.random.default_rng(seed)
        sign = rng.choice([-1.0, 1.0], size=len(gross))
        flipped = gross * sign
        rows.append({"seed": seed, "n_trades": len(flipped), "mean_gross_return": flipped.mean(),
                     "std_gross_return": flipped.std()})
    return pd.DataFrame(rows)
