"""Diagnostic (no study slot spent): is the low-liquidity tercile's 118bps
cost estimate justified?

The 118bps figure (PREREGISTRATION.md, run_momentum_backtest.py) uses raw
Corwin-Schultz, uncalibrated, on the argument that CS is accurate
(not overstated) on "thin/T2T-like names" -- borrowing a calibration finding
that was actually established on true trade-to-trade (BE/BZ series) names.

This script checks whether that borrowing is justified: what fraction of
the low-liquidity tercile is actually BE/BZ series, versus ordinary EQ
names that merely have low turnover. It also recomputes Corwin-Schultz
directly (no prior script computed and saved this -- the 62.7/97.7bps
figures existed only as a comment, not a reproducible artifact) and reports
a specific list of low-liq EQ names for live order-book verification.

Uses only the pre-holdout panel. Does not touch the sealed holdout window.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel

ROOT = Path(__file__).resolve().parents[1]
con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

# ---------------------------------------------------------------------------
# Part 1: is the low-liq tercile ever BE/BZ? (structural check, no query
# needed beyond the schema -- entity_panel.py's materialization SQL filters
# `series = 'EQ'` unconditionally, so nothing else can ever enter this
# panel.)
# ---------------------------------------------------------------------------
print("=" * 78)
print("PART 1: series composition of the panel this backtest's tercile is built from")
print("=" * 78)
series_counts = con.execute("SELECT series, COUNT(*) AS n FROM prices_eod GROUP BY series ORDER BY n DESC").fetchdf()
print(series_counts.to_string(index=False))
print(
    "\nentity_panel.materialize_entity_panel()'s SQL: `WHERE p.series = 'EQ'`.\n"
    "This filter is unconditional -- BE/BZ rows are never joined into\n"
    "entity_prices_daily, at any date, for any entity. Therefore the\n"
    "low-liquidity tercile (computed downstream from this panel, by\n"
    "run_momentum_backtest.py) is, BY CONSTRUCTION, 100% series='EQ' and 0%\n"
    "BE/BZ trade-to-trade -- not an empirical finding to be measured, a\n"
    "structural fact about how the panel is built. The 118bps calibration\n"
    "argument ('CS is accurate on thin/T2T-like names') is being applied to a\n"
    "population that is definitionally never actually T2T. The argument\n"
    "conflates 'thinly traded' with 'trade-to-trade (BE/BZ) market mechanism'\n"
    "-- these are different things. A low-turnover EQ stock still trades in\n"
    "continuous double-auction mode; BE/BZ names trade under periodic-call/\n"
    "trade-for-trade settlement, a structurally different microstructure.\n"
    "The calibration borrow is not obviously wrong, but it is unverified,\n"
    "exactly as PREREGISTRATION.md itself flags."
)

# ---------------------------------------------------------------------------
# Part 2: recompute the low-liq tercile and Corwin-Schultz directly,
# reproducibly (the 62.7/97.7bps figures were never saved as code).
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("PART 2: recomputing liquidity terciles and Corwin-Schultz spreads")
print("=" * 78)

panel = read_entity_panel(con)  # pre-holdout only, guarded at materialization
p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
p["_tercile"] = p.groupby("trade_date")["_liq"].transform(
    lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop")
    if s.notna().sum() >= 3 else pd.Series([np.nan] * len(s), index=s.index)
)

LAST_DATE = p["trade_date"].max()
print(f"Last pre-holdout panel date: {LAST_DATE.date()} (panel is truncated here; "
      f"sealed holdout begins 2025-03-19 and is not read by this script)")

snap = p[p["trade_date"] == LAST_DATE].dropna(subset=["_tercile"])
print(f"Entities with a tercile assignment on {LAST_DATE.date()}: {len(snap)}")
print(snap["_tercile"].value_counts())

low_liq_entities = snap.loc[snap["_tercile"] == "low_liq", "entity_id"].tolist()

# Pull symbol + raw high/low for Corwin-Schultz, over the trailing 60 trading
# days ending at LAST_DATE, for entities in the low_liq tercile on that date.
lookback_dates = sorted(p["trade_date"].unique())[-60:]
sql = f"""
    SELECT l.entity_id, p.trade_date, p.symbol, p.series, p.high, p.low
    FROM prices_eod p
    JOIN isin_lineage l ON p.isin = l.isin
    WHERE p.series = 'EQ' AND p.trade_date >= ? AND p.trade_date <= ?
      AND l.entity_id IN ({",".join("?" for _ in low_liq_entities)})
"""
raw = con.execute(sql, [lookback_dates[0], LAST_DATE] + low_liq_entities).fetchdf()
raw["trade_date"] = pd.to_datetime(raw["trade_date"])
raw = raw.sort_values(["entity_id", "trade_date"])


def corwin_schultz(high: pd.Series, low: pd.Series) -> pd.Series:
    """Standard 2-day Corwin-Schultz (2012) high-low spread estimator.
    Returns a per-day spread estimate (fraction of price); negative alpha
    (the known small-sample artifact) is floored to a zero spread for that
    day, per the original paper's own recommendation."""
    h, l = high.values, low.values
    beta = np.full(len(h), np.nan)
    for i in range(1, len(h)):
        beta[i] = np.log(h[i] / l[i]) ** 2 + np.log(h[i - 1] / l[i - 1]) ** 2
    h2 = np.maximum(h[1:], h[:-1])
    l2 = np.minimum(l[1:], l[:-1])
    gamma = np.log(h2 / l2) ** 2
    gamma = np.concatenate([[np.nan], gamma])
    k = 3 - 2 * np.sqrt(2)
    with np.errstate(invalid="ignore"):
        alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    spread = np.where(spread < 0, 0.0, spread)
    return pd.Series(spread, index=high.index)


rows = []
for eid, g in raw.groupby("entity_id"):
    g = g[(g["high"] > 0) & (g["low"] > 0) & (g["high"] >= g["low"])]
    if len(g) < 10:
        continue
    sp = corwin_schultz(g["high"], g["low"])
    symbol = g["symbol"].iloc[-1]
    series_set = sorted(g["series"].unique())
    rows.append({
        "entity_id": eid,
        "symbol": symbol,
        "series_observed_last_60d": ",".join(series_set),
        "median_cs_spread_bps": np.nanmedian(sp) * 10000,
        "mean_cs_spread_bps": np.nanmean(sp) * 10000,
        "n_days": len(g),
    })

res = pd.DataFrame(rows).sort_values("median_cs_spread_bps")
print(f"\nLow-liq entities with sufficient recent history: {len(res)} of {len(low_liq_entities)}")
print(f"\nPanel-wide low-liq tercile Corwin-Schultz (median across {len(res)} names, "
      f"trailing 60d ending {LAST_DATE.date()}):")
print(f"  median of medians: {res['median_cs_spread_bps'].median():.1f} bps")
print(f"  mean of medians:   {res['median_cs_spread_bps'].mean():.1f} bps")
print(f"  (comment in run_momentum_backtest.py cites 97.7bps raw for this tercile)")

print("\n--- 8 names spanning the low-liq tercile's CS distribution (for live "
      "order-book verification) ---")
n = len(res)
idx = sorted(set(int(round(x)) for x in np.linspace(0, n - 1, min(8, n))))
sample = res.iloc[idx][["symbol", "series_observed_last_60d", "median_cs_spread_bps", "n_days"]]
print(sample.to_string(index=False))

print(
    "\nNOTE ON STALENESS: these names and their tercile membership reflect the "
    "last PRE-HOLDOUT panel date "
    f"({LAST_DATE.date()}), not today (2026-09-23), because computing a truly "
    "current low-liq tercile would require reading dates >= 2025-03-19 -- the "
    "sealed holdout window. This project's own standing rule "
    "(src/data_layer/holdout.py) is that authorize_holdout=True is 'never set "
    "in a diagnostic.' Whether that rule should be read to cover a pure "
    "market-microstructure lookup (which touches no return, no IC, no "
    "strategy decision) the same way it covers a factor/strategy evaluation "
    "is not this script's call to make silently -- flagged back to the user "
    "rather than decided either way."
)
con.close()
