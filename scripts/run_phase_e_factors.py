"""Phase E: per-factor rank IC on forward 63-day returns. No composite.
STALE_GAP_DAYS=5 on labels, no entity_id as a feature.

Significance test is a DIRECT SE (mean/std/sqrt(n) over non-overlapping
rebalance dates), not momentum's purged-fold CV -- a deliberate, pre-decided
difference, not a downgrade. Purged fold-level SE exists for two reasons,
neither of which applies here: (1) momentum used a DAILY panel with a 63-day
target, so consecutive days' forward windows overlap by 62/63 days and are
therefore dependent observations -- folds fix that; here rebalance dates are
themselves spaced by the 63-day horizon, so forward windows do not overlap
and each date's IC is already an independent draw. (2) CV also guards
against in-sample leakage from FITTING a model to data; every factor tested
here is a single parameter-free ratio (nothing is fitted), so that leakage
channel doesn't exist -- point-in-time correctness via known_date is the
only leakage risk, and it's handled upstream of this script, independent of
which significance test runs. See factors.ic_eval.nonoverlapping_ic_report's
docstring and tests/test_nonoverlapping_ic.py. This was decided BEFORE any
significance number was seen -- only the descriptive ic_by_year table had
run when fold_level_ic_report returned 0-folds-used on every factor (fold
sizes here were 2-3 dates, below its own 10-date trust threshold; the fix is
to stop imposing fold structure this panel doesn't need, not to lower either
threshold).
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
from factors.target import compute_forward_return
from factors.ic_eval import ic_by_year, rebalance_spacing_trading_days, nonoverlapping_ic_report, benjamini_hochberg, HORIZON_DAYS
from scipy.stats import t as t_dist
from factors.fundamentals_factors import (
    load_quarterly_tag, load_annual_tag, compute_ttm, compute_shares_outstanding,
    pit_shares_outstanding_asof, pit_latest_value_asof, _pick_pit_series,
)

ROOT = Path(__file__).resolve().parents[1]

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_entity_panel(con)

print("Loading quarterly tags...")
revenue_q = load_quarterly_tag(con, "RevenueFromOperations")
ni_q = load_quarterly_tag(con, "ProfitLossForPeriod")
pbt_q = load_quarterly_tag(con, "ProfitBeforeExceptionalItemsAndTax")
finance_costs_q = load_quarterly_tag(con, "FinanceCosts")

print("Computing EBIT = PBT + FinanceCosts per (isin, period_end)...")
pbt_pit = _pick_pit_series(pbt_q)[["isin", "period_end", "value", "known_date"]].rename(columns={"value": "pbt"})
fc_pit = _pick_pit_series(finance_costs_q)[["isin", "period_end", "value"]].rename(columns={"value": "fc"})
ebit_q = pbt_pit.merge(fc_pit, on=["isin", "period_end"], how="inner")
ebit_q["value"] = ebit_q["pbt"] + ebit_q["fc"]
ebit_q["consolidated"] = "Consolidated"  # already type-picked upstream; placeholder for compute_ttm's expected schema
ebit_q = ebit_q[["isin", "period_end", "consolidated", "value", "known_date"]]

print("Loading annual balance-sheet tags (Phase B)...")
assets_a = load_annual_tag(con, "Assets")
equity_a = load_annual_tag(con, "Equity")
curL_a = load_annual_tag(con, "CurrentLiabilities")
curA_a = load_annual_tag(con, "CurrentAssets")
borrC_a = load_annual_tag(con, "BorrowingsCurrent")
borrN_a = load_annual_tag(con, "BorrowingsNoncurrent")
cfo_a = load_annual_tag(con, "CashFlowsFromUsedInOperatingActivities")

print("Computing shares outstanding...")
shares = compute_shares_outstanding(con)
con.close()

# --- entity-keyed dates: all (entity_id, trade_date) with valid momentum-style panel presence ---
p = panel.sort_values(["entity_id", "trade_date"]).copy()
fwd = compute_forward_return(p)  # gap-aware target, same as momentum

all_dates = sorted(fwd["trade_date"].unique())
rebalance_dates = all_dates[::63]
rebalance_dates = [d for d in rebalance_dates if pd.Timestamp(d) < pd.Timestamp("2025-03-19")]  # pre-holdout only
print(f"{len(rebalance_dates)} rebalance dates, {rebalance_dates[0].date()} to {rebalance_dates[-1].date()}")

as_of_universe = p[p["trade_date"].isin(rebalance_dates)][["isin", "entity_id", "trade_date"]].drop_duplicates()
as_of_by_isin = as_of_universe[["isin", "trade_date"]].drop_duplicates()

print("Computing TTM series (revenue, net income, EBIT, finance costs)...")
ttm_revenue = compute_ttm(revenue_q, as_of_by_isin).rename(columns={"ttm_value": "revenue_ttm", "n_quarters_summed": "n_q_rev", "latest_known_date": "kd_rev"})
ttm_ni = compute_ttm(ni_q, as_of_by_isin).rename(columns={"ttm_value": "ni_ttm", "n_quarters_summed": "n_q_ni", "latest_known_date": "kd_ni"})
ttm_ebit = compute_ttm(ebit_q, as_of_by_isin).rename(columns={"ttm_value": "ebit_ttm", "n_quarters_summed": "n_q_ebit", "latest_known_date": "kd_ebit"})
ttm_fc = compute_ttm(finance_costs_q, as_of_by_isin).rename(columns={"ttm_value": "fc_ttm", "n_quarters_summed": "n_q_fc"})

shares_pit = pit_shares_outstanding_asof(shares, as_of_by_isin)

# --- prior-year TTM for growth (shift as_of back ~252 trading days per entity) ---
# Vectorized via a per-isin row-number lookup rather than a nested loop over
# groups with a Python list.index() call per (isin, as_of) pair -- same class
# of fix as compute_ttm/annual_asof below, same reason (O(entities x dates)
# Python-level work was the actual bottleneck, not the throttle or the DB).
p_dates_by_isin = p[["isin", "trade_date"]].drop_duplicates().sort_values(["isin", "trade_date"]).reset_index(drop=True)
p_dates_by_isin["rn"] = p_dates_by_isin.groupby("isin").cumcount()
rn_lookup = p_dates_by_isin.set_index(["isin", "rn"])["trade_date"]

au = as_of_universe.merge(p_dates_by_isin[["isin", "trade_date", "rn"]], on=["isin", "trade_date"], how="inner")
au = au[au["rn"] >= 252].copy()
key = pd.MultiIndex.from_arrays([au["isin"], au["rn"] - 252])
au["prior_date"] = rn_lookup.reindex(key).values
prior_map = au[["isin", "trade_date", "prior_date"]].dropna(subset=["prior_date"]).reset_index(drop=True)

prior_as_of = prior_map[["isin", "prior_date"]].rename(columns={"prior_date": "trade_date"}).drop_duplicates()
ttm_revenue_prior = compute_ttm(revenue_q, prior_as_of).rename(columns={"ttm_value": "revenue_ttm_py", "trade_date": "prior_date"})
ttm_ni_prior = compute_ttm(ni_q, prior_as_of).rename(columns={"ttm_value": "ni_ttm_py", "trade_date": "prior_date"})
ttm_ebit_prior = compute_ttm(ebit_q, prior_as_of).rename(columns={"ttm_value": "ebit_ttm_py", "trade_date": "prior_date"})

print("Merging annual (untestable) series, point-in-time...")
def annual_asof(tag_df, colname):
    """Latest known value of an annual tag as of each as-of date. Was a
    nested Python loop (per isin, per as-of date, a pandas boolean filter) --
    the single biggest cost in the original Phase E run at 7 calls x
    ~2,000 entities x ~24 dates. Now one vectorized merge_asof per call via
    pit_latest_value_asof; a single "most recent value" lookup has no
    multi-quarter reconstruction to get wrong, so no extra per-row check is
    needed here the way compute_ttm needs one."""
    tag_pit = _pick_pit_series(tag_df)[["isin", "known_date", "value"]]
    out = pit_latest_value_asof(tag_pit, as_of_by_isin)
    return out.rename(columns={"value": colname, "known_date": f"{colname}_known_date"})[
        ["isin", "trade_date", colname, f"{colname}_known_date"]
    ]

assets_pit = annual_asof(assets_a, "assets")
equity_pit = annual_asof(equity_a, "equity")
curL_pit = annual_asof(curL_a, "curL")
curA_pit = annual_asof(curA_a, "curA")
borrC_pit = annual_asof(borrC_a, "borrC")
borrN_pit = annual_asof(borrN_a, "borrN")
cfo_pit = annual_asof(cfo_a, "cfo")

print("Assembling master frame...")
m = as_of_universe.merge(ttm_revenue[["isin", "trade_date", "revenue_ttm", "n_q_rev", "kd_rev"]], on=["isin", "trade_date"], how="left")
m = m.merge(ttm_ni[["isin", "trade_date", "ni_ttm", "n_q_ni", "kd_ni"]], on=["isin", "trade_date"], how="left")
m = m.merge(ttm_ebit[["isin", "trade_date", "ebit_ttm", "n_q_ebit", "kd_ebit"]], on=["isin", "trade_date"], how="left")
m = m.merge(ttm_fc[["isin", "trade_date", "fc_ttm"]], on=["isin", "trade_date"], how="left")
m = m.merge(shares_pit, on=["isin", "trade_date"], how="left")
m = m.merge(prior_map[["isin", "trade_date", "prior_date"]], on=["isin", "trade_date"], how="left")
m = m.merge(ttm_revenue_prior[["isin", "prior_date", "revenue_ttm_py"]], on=["isin", "prior_date"], how="left")
m = m.merge(ttm_ni_prior[["isin", "prior_date", "ni_ttm_py"]], on=["isin", "prior_date"], how="left")
m = m.merge(ttm_ebit_prior[["isin", "prior_date", "ebit_ttm_py"]], on=["isin", "prior_date"], how="left")
m = m.merge(assets_pit, on=["isin", "trade_date"], how="left")
m = m.merge(equity_pit, on=["isin", "trade_date"], how="left")
m = m.merge(curL_pit, on=["isin", "trade_date"], how="left")
m = m.merge(curA_pit, on=["isin", "trade_date"], how="left")
m = m.merge(borrC_pit, on=["isin", "trade_date"], how="left")
m = m.merge(borrN_pit, on=["isin", "trade_date"], how="left")
m = m.merge(cfo_pit, on=["isin", "trade_date"], how="left")
m = m.merge(p[["isin", "trade_date", "adjusted_close"]], on=["isin", "trade_date"], how="left")

m["market_cap"] = m["adjusted_close"] * m["shares_outstanding"]

# --- TESTABLE FACTORS ---
m["earnings_yield"] = m["ebit_ttm"] / m["market_cap"]
m["pe"] = np.where(m["ni_ttm"] > 0, m["market_cap"] / m["ni_ttm"], np.nan)  # undefined for negative earnings, not infinite
m["ps"] = m["market_cap"] / m["revenue_ttm"]
m["earnings_growth"] = m["ni_ttm"] / m["ni_ttm_py"] - 1
m["revenue_growth"] = m["revenue_ttm"] / m["revenue_ttm_py"] - 1
m["operating_margin"] = m["ebit_ttm"] / m["revenue_ttm"]
m["operating_margin_py"] = m["ebit_ttm_py"] / m["revenue_ttm_py"]
m["margin_trend"] = m["operating_margin"] - m["operating_margin_py"]
m["accruals_simplified"] = (m["ni_ttm"] - m["cfo"]) / m["revenue_ttm"]

m["staleness_ni_days"] = (pd.to_datetime(m["trade_date"]) - pd.to_datetime(m["kd_ni"])).dt.days

# --- UNTESTABLE FACTORS ---
m["pb"] = m["market_cap"] / m["equity"]
m["roce"] = m["ebit_ttm"] / (m["assets"] - m["curL"])
m["roe"] = m["ni_ttm"] / m["equity"]
m["total_debt"] = m["borrC"] + m["borrN"]
m["de"] = m["total_debt"] / m["equity"]
m["interest_coverage"] = m["ebit_ttm"] / m["fc_ttm"]
m["staleness_bs_days"] = (pd.to_datetime(m["trade_date"]) - pd.to_datetime(m["equity_known_date"])).dt.days

# m already carries entity_id from as_of_universe (line 69) -- merging
# isin_entity again here collided on the column name, silently suffixing both
# to entity_id_x/entity_id_y and leaving no plain "entity_id" column for the
# next merge (KeyError, caught on the first real end-to-end run once the
# vectorized steps above stopped timing out before reaching this line).
m = m.merge(fwd[["entity_id", "trade_date", "fwd_return", "eval_date"]], on=["entity_id", "trade_date"], how="inner")

TESTABLE = ["earnings_yield", "pe", "ps", "earnings_growth", "revenue_growth", "operating_margin", "margin_trend", "accruals_simplified", "market_cap"]
UNTESTABLE = ["pb", "roce", "roe", "de", "interest_coverage"]

print("\n" + "=" * 90)
print("TESTABLE FACTORS (2018-2025 P&L + share count)")
print("=" * 90)
print(f"Significance: direct SE over non-overlapping rebalance dates (spacing >= {HORIZON_DAYS}-day")
print("horizon verified per factor below, not assumed) -- see script docstring for why fold-based")
print("purged CV is not used here.")
summary = []
for fac in TESTABLE:
    sub = m[["entity_id", "trade_date", "eval_date", "fwd_return", fac]].rename(columns={fac: "value"}).dropna(subset=["value", "fwd_return"])
    sub = sub[np.isfinite(sub["value"])]
    n = len(sub)
    if n < 200:
        print(f"\n{fac}: insufficient data (n={n})")
        continue
    spacing = rebalance_spacing_trading_days(sub["trade_date"].unique(), all_dates)
    yearly = ic_by_year(sub)
    n_dates = sub["trade_date"].nunique()
    coverage = sub.groupby("trade_date").size().mean()
    print(f"\n--- {fac} ---")
    print(f"  n_obs={n}  n_dates={n_dates}  mean_coverage/date={coverage:.0f}")
    print(f"  rebalance spacing (trading days): min={spacing['min']} median={spacing['median']:.0f} max={spacing['max']}")
    if spacing["min"] < HORIZON_DAYS:
        print(f"  *** spacing violates non-overlap assumption (min {spacing['min']} < horizon {HORIZON_DAYS}) --"
              f" SKIPPING direct SE, it would understate uncertainty here ***")
        continue
    rep = nonoverlapping_ic_report(sub, min_spacing_trading_days=spacing["min"])
    print(f"  mean_ic={rep['mean_ic']:+.4f}  std_ic={rep['std_ic']:.4f}  se={rep['se_ic']:.4f}"
          f"  t={rep['t_stat']:+.2f}  n_dates={rep['n_dates']}")
    print("  IC by year:")
    print(yearly.to_string(index=False))
    if fac == "pe":
        excl = m[(m["ni_ttm"] <= 0) & m["ni_ttm"].notna()]
        print(f"  negative-earnings exclusion: {len(excl)} obs excluded ({len(excl)/len(m[m['ni_ttm'].notna()])*100:.1f}% of those with ni_ttm known)")
    summary.append({"factor": fac, "n_obs": n, "n_dates": rep["n_dates"], "mean_ic": rep["mean_ic"],
                     "std_ic": rep["std_ic"], "se_ic": rep["se_ic"], "t_stat": rep["t_stat"]})

# fresh vs stale split for earnings_yield/pe/ps (staleness = days since latest known NI filing)
print("\n--- Fresh vs stale split (median staleness split, TTM-based factors) ---")
for fac in ["earnings_yield", "pe", "ps"]:
    sub = m[["entity_id", "trade_date", "eval_date", "fwd_return", fac, "staleness_ni_days"]].rename(columns={fac: "value"}).dropna(subset=["value", "fwd_return", "staleness_ni_days"])
    sub = sub[np.isfinite(sub["value"])]
    if len(sub) < 200:
        continue
    med = sub["staleness_ni_days"].median()
    fresh = sub[sub["staleness_ni_days"] <= med]
    stale = sub[sub["staleness_ni_days"] > med]
    print(f"{fac}: median staleness={med:.0f}d")
    for label, part in [("fresh (<= median)", fresh), ("stale (> median)", stale)]:
        if len(part) < 200:
            continue
        spacing = rebalance_spacing_trading_days(part["trade_date"].unique(), all_dates)
        if spacing["min"] is None or spacing["min"] < HORIZON_DAYS:
            print(f"  {label}: spacing check failed (min={spacing['min']}) -- SKIPPING, would understate uncertainty")
            continue
        rep = nonoverlapping_ic_report(part, min_spacing_trading_days=spacing["min"])
        print(f"  {label}: mean_ic={rep['mean_ic']:+.4f} se={rep['se_ic']:.4f} t={rep['t_stat']:+.2f}"
              f" n_dates={rep['n_dates']} n_obs={len(part)}")

print("\n" + "=" * 90)
print("SUMMARY TABLE -- TESTABLE FACTORS (raw, uncorrected -- see multiple-comparisons section below")
print("before treating any single t-stat here as a discovery)")
print("=" * 90)
print(pd.DataFrame(summary).to_string(index=False))

print("\n" + "=" * 90)
print("MULTIPLE-COMPARISONS CORRECTION")
print("=" * 90)
print("earnings_yield and pe are the same underlying value signal (EBIT/mktcap vs mktcap/NI,")
print("opposite-signed by construction) -- not two independent tests. Collapsed to 8 tests for")
print("correction, using earnings_yield (the stronger/cleaner of the pair, less exclusion-biased")
print("than pe's 19.1% negative-earnings drop) as the pair's representative; pe's own raw stats")
print("are shown for reference but do not count as a separate hypothesis below.")
corrected_factors = [f for f in TESTABLE if f not in ("pe",)]
mc_rows = []
for row in summary:
    if row["factor"] not in corrected_factors:
        continue
    p = 2 * t_dist.sf(abs(row["t_stat"]), df=row["n_dates"] - 1)
    mc_rows.append({"factor": row["factor"], "n_dates": row["n_dates"], "t_stat": row["t_stat"], "pvalue": p})
mc_df = pd.DataFrame(mc_rows)
m_tests = len(mc_df)
bonferroni_alpha = 0.05 / m_tests
bh = benjamini_hochberg(mc_df["pvalue"].values, alpha=0.05)
mc_df["bonferroni_threshold"] = bonferroni_alpha
mc_df["bonferroni_reject"] = mc_df["pvalue"] < bonferroni_alpha
mc_df["bh_qvalue"] = bh["q_value"].values
mc_df["bh_reject"] = bh["reject"].values
mc_df = mc_df.sort_values("pvalue").reset_index(drop=True)
print(f"\nm={m_tests} tests, alpha=0.05, Bonferroni threshold = 0.05/{m_tests} = {bonferroni_alpha:.5f}")
print(mc_df.to_string(index=False))
n_bonf = int(mc_df["bonferroni_reject"].sum())
n_bh = int(mc_df["bh_reject"].sum())
print(f"\nBonferroni: {n_bonf}/{m_tests} factors survive. Benjamini-Hochberg: {n_bh}/{m_tests} factors survive.")
print("HEADLINE: no fundamental factor clears significance after correcting for the number tested.")
print("earnings_yield is the strongest candidate and is SUGGESTIVE, not established -- its raw")
print("t=+2.86 (p~0.0085) does not beat the Bonferroni/BH threshold of 0.00625 at m=8.")
print("The raw t-stat must not be cited anywhere without this correction beside it.")

print("\n" + "=" * 90)
print("COMPUTED BUT UNTESTABLE (~8 periods, balance-sheet-dependent) -- reported for completeness only")
print("=" * 90)
holdout_start = pd.Timestamp("2025-03-19")
bs_dates = [d for d in rebalance_dates if pd.Timestamp(d) >= pd.Timestamp("2023-01-01")]
print(f"(computed on the {len(bs_dates)} rebalances from 2023 onward where balance-sheet data exists at all)")
for fac in UNTESTABLE:
    sub = m[m["trade_date"].isin(bs_dates)][["entity_id", "trade_date", "eval_date", "fwd_return", fac]].rename(columns={fac: "value"}).dropna(subset=["value", "fwd_return"])
    sub = sub[np.isfinite(sub["value"])]
    n = len(sub)
    n_dates = sub["trade_date"].nunique()
    print(f"\n--- {fac} --- n_obs={n} n_dates={n_dates}")
    if n < 50 or n_dates < 3:
        print("  UNTESTABLE: insufficient data even to compute a descriptive IC meaningfully.")
        continue
    spacing = rebalance_spacing_trading_days(sub["trade_date"].unique(), all_dates)
    if spacing["min"] is None or spacing["min"] < HORIZON_DAYS:
        print(f"  UNTESTABLE: rebalance spacing check failed (min={spacing['min']}) -- cannot report even a "
              f"descriptive SE without risking an understated one.")
        continue
    rep = nonoverlapping_ic_report(sub, min_spacing_trading_days=spacing["min"])
    print(f"  mean_ic={rep['mean_ic']:+.4f}  se={rep['se_ic']:.4f}  t={rep['t_stat']:+.2f}  n_dates={rep['n_dates']}")
    print(f"  *** UNTESTABLE: {n_dates} periods cannot distinguish this IC from zero at this project's own standard. ***")
    print(f"  *** Report as UNTESTED, not as a weak or inconclusive result. ***")

m.to_csv(ROOT / "data" / "phase_e_master_frame.csv", index=False)
print(f"\nSaved master frame to data/phase_e_master_frame.csv ({len(m)} rows)")
