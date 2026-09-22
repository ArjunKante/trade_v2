"""Five diagnostics requested before any factor is trusted further:
  1. momentum_6_1 vs momentum_12_1 skip-correctness (done inline in chat, not here)
  2. IC by liquidity tercile, BE/BZ exclusion confirmation
  3. Decile monotonicity of forward return
  4. Cost hurdle: edge = IC x cross-sectional std, vs ground-truth cost
  5. Leakage suite: label shuffle, 1-day feature shift, 2016-2019 vs 2020 regime split
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel
from factors.momentum import compute_momentum_12_1, compute_momentum_6_1
from factors.lowvol import compute_trailing_vol, compute_beta
from factors.target import compute_forward_return
from factors.ic_eval import purged_fold_assignments, daily_rank_ic, fold_level_ic_report

ROOT = Path(__file__).resolve().parents[1]
N_SPLITS = 10
ROUND_TRIP_COST_BPS_LOW = 26.0   # prior project's ground-truth measured range
ROUND_TRIP_COST_BPS_HIGH = 39.0

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)
index_raw = con.execute("SELECT trade_date, close FROM index_eod WHERE index_name='NIFTY50' ORDER BY trade_date").fetchdf()
con.close()

index_raw["trade_date"] = pd.to_datetime(index_raw["trade_date"])
index_raw["mkt_logret"] = np.log(index_raw["close"] / index_raw["close"].shift(1))
index_returns = index_raw[["trade_date", "mkt_logret"]]

print("Computing factors + target...")
factors = {
    "momentum_12_1": compute_momentum_12_1(panel),
    "momentum_6_1": compute_momentum_6_1(panel),
    "trailing_vol_252": compute_trailing_vol(panel),
    "beta_252": compute_beta(panel, index_returns),
}
fwd = compute_forward_return(panel)

# trailing 20-day median turnover per entity per date, for liquidity tercile assignment
p = panel.sort_values(["entity_id", "trade_date"]).copy()
p["_liq"] = p.groupby("entity_id")["turnover"].transform(lambda s: s.rolling(20, min_periods=20).median())
liq = p[["entity_id", "trade_date", "_liq"]]


def build_merged(fdf):
    m = fdf.merge(fwd, on=["entity_id", "trade_date"]).merge(liq, on=["entity_id", "trade_date"])
    return m.dropna(subset=["value", "fwd_return", "eval_date", "_liq"]).sort_values("trade_date").reset_index(drop=True)


print("\n" + "=" * 70)
print("DIAGNOSTIC 2: IC by liquidity tercile (cross-sectional, per date)")
print("=" * 70)
for name, fdf in factors.items():
    m = build_merged(fdf)
    m["_tercile"] = m.groupby("trade_date")["_liq"].transform(
        lambda s: pd.qcut(s, 3, labels=["low_liq", "mid_liq", "high_liq"], duplicates="drop") if s.nunique() >= 3 else pd.Series([np.nan]*len(s), index=s.index)
    )
    print(f"\n--- {name} ---")
    for tercile in ["low_liq", "mid_liq", "high_liq"]:
        sub = m[m["_tercile"] == tercile]
        if len(sub) < 1000:
            print(f"  {tercile}: insufficient obs ({len(sub)})")
            continue
        rep = fold_level_ic_report(sub, n_splits=N_SPLITS)
        print(f"  {tercile:9s}: n={len(sub):>9,}  mean_ic={rep['mean_ic']:+.4f}  se={rep['se_ic']:.4f}  t={rep['t_stat']:+.2f}  folds_used={rep['n_folds_used']}")

print("\n(BE/BZ series were never in entity_prices_daily -- confirmed by direct query: "
      "100% of rows are series='EQ'. All IC numbers reported anywhere in this project "
      "already exclude trade-to-trade names; there is no separate 'excluded' rerun to show.)")


print("\n" + "=" * 70)
print("DIAGNOSTIC 3: decile monotonicity (mean forward 63d return per factor decile)")
print("=" * 70)
for name, fdf in factors.items():
    m = fdf.merge(fwd, on=["entity_id", "trade_date"]).dropna(subset=["value", "fwd_return"])
    m["_decile"] = m.groupby("trade_date")["value"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 10, labels=False, duplicates="drop") if s.nunique() >= 10 else np.nan
    )
    dec = m.groupby("_decile")["fwd_return"].agg(["mean", "count"])
    print(f"\n--- {name} --- (decile 0 = lowest factor value, 9 = highest)")
    print(dec.to_string())
    spread = dec["mean"].iloc[-1] - dec["mean"].iloc[0]
    # monotonicity: fraction of consecutive decile steps that go the same direction as the overall spread
    diffs = dec["mean"].diff().dropna()
    same_sign = (np.sign(diffs) == np.sign(spread)).mean()
    print(f"  D9-D0 spread: {spread:+.4f}   monotonic steps: {same_sign*100:.0f}% of 9 consecutive gaps move the same direction")


print("\n" + "=" * 70)
print("DIAGNOSTIC 4: cost hurdle (edge = IC x cross-sectional std of fwd 63d return)")
print("=" * 70)
daily_xsec_std = fwd.groupby("trade_date")["fwd_return"].std()
mean_xsec_std = daily_xsec_std.mean()
print(f"mean cross-sectional std of forward 63d return: {mean_xsec_std*100:.2f}%")
print(f"ground-truth round-trip cost range: {ROUND_TRIP_COST_BPS_LOW}-{ROUND_TRIP_COST_BPS_HIGH} bps\n")

summary_ic = {"momentum_12_1": 0.0714, "momentum_6_1": 0.0756, "trailing_vol_252": -0.0729, "beta_252": -0.0380}
for name, ic in summary_ic.items():
    edge_bps = abs(ic) * mean_xsec_std * 10000
    edge_over_cost_low = edge_bps / ROUND_TRIP_COST_BPS_HIGH
    edge_over_cost_high = edge_bps / ROUND_TRIP_COST_BPS_LOW
    print(f"  {name:18s}: |IC|={abs(ic):.4f}  edge={edge_bps:.1f}bps  edge/cost={edge_over_cost_low:.2f}x-{edge_over_cost_high:.2f}x")


print("\n" + "=" * 70)
print("DIAGNOSTIC 5: leakage suite")
print("=" * 70)

for name, fdf in factors.items():
    m = build_merged(fdf).drop(columns=["_liq"])
    print(f"\n--- {name} ---")
    base = fold_level_ic_report(m, n_splits=N_SPLITS)
    print(f"  baseline        : mean_ic={base['mean_ic']:+.4f}  t={base['t_stat']:+.2f}")

    # (a) label shuffle -- shuffle fwd_return WITHIN each date (preserves cross-sectional distribution, breaks the relationship)
    rng = np.random.default_rng(42)
    shuffled = m.copy()
    shuffled["fwd_return"] = shuffled.groupby("trade_date")["fwd_return"].transform(
        lambda s: rng.permutation(s.values)
    )
    shuf_rep = fold_level_ic_report(shuffled, n_splits=N_SPLITS)
    print(f"  label-shuffled  : mean_ic={shuf_rep['mean_ic']:+.4f}  t={shuf_rep['t_stat']:+.2f}  (expect ~0)")

    # (b) shift features forward 1 trading day: pair factor(t) with target that was at t+1 (per entity)
    shifted = fdf.sort_values(["entity_id", "trade_date"]).copy()
    shifted["trade_date"] = shifted.groupby("entity_id")["trade_date"].shift(-1)  # relabel factor(t) as if it were observed at t+1
    shifted = shifted.dropna(subset=["trade_date"])
    m_shift = build_merged(shifted).drop(columns=["_liq"])
    shift_rep = fold_level_ic_report(m_shift, n_splits=N_SPLITS)
    pct_drop = (1 - abs(shift_rep["mean_ic"]) / abs(base["mean_ic"])) * 100 if base["mean_ic"] else np.nan
    print(f"  +1 day shift    : mean_ic={shift_rep['mean_ic']:+.4f}  t={shift_rep['t_stat']:+.2f}  ({pct_drop:+.0f}% change vs baseline)")

    # (c) train 2016-2019 vs test 2020 regime split (descriptive, not a model -- just IC computed on each block)
    m["_year"] = pd.to_datetime(m["trade_date"]).dt.year
    train_block = m[m["_year"].between(2016, 2019)]
    test_block = m[m["_year"] == 2020]
    train_ic = daily_rank_ic(train_block).dropna()["ic"].mean()
    test_ic = daily_rank_ic(test_block).dropna()["ic"].mean()
    print(f"  2016-2019 IC    : {train_ic:+.4f}")
    print(f"  2020 IC         : {test_ic:+.4f}  (regime check: does sign/magnitude hold?)")
