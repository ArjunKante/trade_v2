"""PHASE 0 -- feasibility and power only, for a potential post-earnings-drift
study. Read-only. Does NOT compute announcement-return vs forward-return.
Restricted to known_date < 2025-07-01 (the unsealed portion) throughout --
see EARNINGS_DRIFT_PHASE0.md Section 0 for the sealed-window declaration
this script respects. Runs no backfill; uses only data already resident in
data/warehouse.duckdb as of that declaration's commit.
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEAL_DATE = "2025-07-01"
HORIZON = 60  # trading days

con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)

filings = con.execute(f"""
    SELECT isin, known_date, broadcast_ts
    FROM fundamentals_filings
    WHERE known_date < DATE '{SEAL_DATE}'
""").fetchdf()
print(f"Events with known_date < {SEAL_DATE}: {len(filings):,} "
      f"(of 137,228 total ever loaded)")

# ---------------------------------------------------------------------------
# Section 2 (unmatched rows): isin_lineage match
# ---------------------------------------------------------------------------
lineage = con.execute("SELECT DISTINCT isin, entity_id FROM isin_lineage").fetchdf()
filings = filings.merge(lineage, on="isin", how="left")
unmatched = filings[filings["entity_id"].isna()]
matched = filings[filings["entity_id"].notna()].copy()
print(f"No isin_lineage match: {len(unmatched):,} of {len(filings):,}")
print(f"Matched: {len(matched):,}")

# ---------------------------------------------------------------------------
# Section 1: join attrition, restricted to matched rows
# ---------------------------------------------------------------------------
prices = con.execute("""
    SELECT entity_id, trade_date FROM entity_prices_daily ORDER BY entity_id, trade_date
""").fetchdf()
panel_max_date = prices["trade_date"].max()
panel_min_date = prices["trade_date"].min()
print(f"\nentity_prices_daily (point-in-time, split-adjusted) spans "
      f"{panel_min_date} to {panel_max_date}")

prices_by_entity = {eid: grp["trade_date"].sort_values().to_numpy()
                     for eid, grp in prices.groupby("entity_id")}

def classify(row):
    eid = row["entity_id"]
    kd = np.datetime64(row["known_date"])
    dates = prices_by_entity.get(eid)
    if dates is None or len(dates) == 0:
        return "no_price_rows_for_entity"
    # t0 = first trading day >= known_date
    idx = np.searchsorted(dates, kd, side="left")
    if idx >= len(dates):
        return "no_price_row_on_or_after_announcement"
    t0 = dates[idx]
    if (t0 - kd) / np.timedelta64(1, "D") > 10:
        return "nearest_trade_date_too_far_from_announcement(>10cal days)"
    if idx == 0:
        return "no_pre_announcement_row(entity_history_starts_at_or_after_t0)"
    pre = dates[idx - 1]
    if (t0 - pre) / np.timedelta64(1, "D") > 10:
        return "event_window_incomplete(gap_before_t0>10cal_days)"
    n_after = len(dates) - idx - 1
    if n_after < HORIZON:
        return f"incomplete_forward_window(<{HORIZON}_trading_days_after_t0;panel_ends_{panel_max_date})"
    return "survives"

matched["reason"] = matched.apply(classify, axis=1)
counts = matched["reason"].value_counts()
print("\nAttrition reasons (matched rows only):")
for reason, n in counts.items():
    print(f"  {reason:70s} {n:7,d}  ({n/len(matched)*100:5.1f}% of matched)")

survivors = matched[matched["reason"] == "survives"]
print(f"\nTotal events with known_date < {SEAL_DATE}: {len(filings):,}")
print(f"  -> no isin_lineage match:              {len(unmatched):,}")
print(f"  -> matched but join-incomplete:         {len(matched) - len(survivors):,}")
print(f"  -> SURVIVE (complete event+forward win): {len(survivors):,}  "
      f"({len(survivors)/len(filings)*100:.1f}% of all events in window)")

# ---------------------------------------------------------------------------
# Section 2: unmatched-row skew vs matched rows (turnover, listing status)
# market cap: no reliable warehouse-resident field (shares outstanding only
# obtainable by live XBRL scraping per scripts/sample_shares_outstanding_
# coverage_v2.py) -- substituting price level as a labelled proxy and
# stating this limitation plainly rather than computing a misleading number.
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("UNMATCHED-ROW SKEW CHECK")
print("=" * 78)

raw_prices = con.execute("""
    SELECT isin, trade_date, close, turnover FROM prices_eod
""").fetchdf()
raw_prices_sorted = raw_prices.sort_values(["isin", "trade_date"])
last_by_isin = raw_prices_sorted.groupby("isin").last()
turnover_by_isin = raw_prices_sorted.groupby("isin")["turnover"].median()
raw_max_date = raw_prices["trade_date"].max()

def isin_profile(isins):
    isins = pd.Index(isins).unique()
    sub_last = last_by_isin.reindex(isins)
    sub_turn = turnover_by_isin.reindex(isins)
    still_trading = (sub_last["trade_date"] >= (raw_max_date - pd.Timedelta(days=90))).mean()
    return {
        "n_isin": len(isins),
        "median_daily_turnover (last obs, proxy for liquidity)": sub_turn.median(),
        "median_last_close (price-level proxy, NOT market cap -- see note)": sub_last["close"].median(),
        "pct_still_trading_within_90cal_days_of_raw_panel_end": still_trading * 100,
    }

unmatched_isins = unmatched["isin"].unique()
matched_isins = matched["isin"].unique()
prof_unmatched = isin_profile(unmatched_isins)
prof_matched = isin_profile(matched_isins)

print(f"raw prices_eod panel ends {raw_max_date} (used here only for last-seen / turnover, not returns)")
print(f"\n{'metric':65s} {'unmatched':>15s} {'matched':>15s}")
for k in prof_unmatched:
    print(f"{k:65s} {prof_unmatched[k]:>15,.2f} {prof_matched[k]:>15,.2f}")

con2 = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)

# ---------------------------------------------------------------------------
# Section 3: announcement timing distribution (known_date < SEAL_DATE)
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("ANNOUNCEMENT TIMING DISTRIBUTION")
print("=" * 78)
ts = filings["broadcast_ts"].dropna()
tod = pd.to_datetime(ts).dt.time
n_tot = len(tod)
before_open = sum(1 for t in tod if t < pd.Timestamp("09:15:00").time())
in_hours = sum(1 for t in tod if pd.Timestamp("09:15:00").time() <= t <= pd.Timestamp("15:30:00").time())
after_close = n_tot - before_open - in_hours
print(f"n = {n_tot:,} (all have non-null broadcast_ts, per prior coverage check)")
print(f"  before 09:15:            {before_open:7,d}  ({before_open/n_tot*100:5.1f}%)")
print(f"  09:15 - 15:30 (in hours): {in_hours:7,d}  ({in_hours/n_tot*100:5.1f}%)")
print(f"  after 15:30:             {after_close:7,d}  ({after_close/n_tot*100:5.1f}%)")

# ---------------------------------------------------------------------------
# Section 4: clustering
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("CLUSTERING")
print("=" * 78)
filings["year"] = pd.to_datetime(filings["known_date"]).dt.year
filings["quarter"] = pd.to_datetime(filings["known_date"]).dt.to_period("Q")
filings["date_only"] = pd.to_datetime(filings["known_date"]).dt.date

per_year = filings.groupby("year")
print(f"{'year':>6s} {'distinct dates':>15s} {'events':>8s} {'top-20-day share':>18s}")
for yr, grp in per_year:
    n_dates = grp["date_only"].nunique()
    daily_counts = grp.groupby("date_only").size().sort_values(ascending=False)
    top20_share = daily_counts.head(20).sum() / len(grp) * 100
    print(f"{yr:>6d} {n_dates:>15d} {len(grp):>8d} {top20_share:>17.1f}%")

g_day = filings["date_only"].nunique()
g_quarter = filings["quarter"].nunique()
print(f"\nTotal distinct announcement DATES, full {filings['date_only'].min()} to "
      f"{filings['date_only'].max()} window: {g_day:,}  (day-clusters)")
print(f"Total distinct QUARTERS in the same window: {g_quarter:,}  (quarter-clusters)")

# ---------------------------------------------------------------------------
# Section 5: MDE both ways
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("MDE, COMPUTED BOTH WAYS")
print("=" * 78)

surv_ids = survivors[["isin", "entity_id", "known_date"]].copy()
surv_ids["known_date"] = pd.to_datetime(surv_ids["known_date"])

def fwd_return(row):
    eid = row["entity_id"]
    kd = np.datetime64(row["known_date"])
    dates = prices_by_entity[eid]
    idx = np.searchsorted(dates, kd, side="left")
    t0 = dates[idx]
    t_fwd = dates[idx + HORIZON]
    return t0, t_fwd

px = con2.execute("SELECT entity_id, trade_date, adjusted_close FROM entity_prices_daily").fetchdf()
px = px.set_index(["entity_id", "trade_date"])["adjusted_close"]

rets = []
for _, row in surv_ids.iterrows():
    eid = row["entity_id"]
    t0, t_fwd = fwd_return(row)
    try:
        p0 = px.loc[(eid, pd.Timestamp(t0))]
        p1 = px.loc[(eid, pd.Timestamp(t_fwd))]
        rets.append(p1 / p0 - 1)
    except KeyError:
        continue

rets = pd.Series(rets)
sigma = rets.std()
print(f"60-trading-day forward return, survivors (n={len(rets):,}): "
      f"mean={rets.mean()*100:.2f}% (NOT used for sizing), sd={sigma*100:.2f}%")

from scipy import stats as _stats

ALPHA = 0.05
POWER = 0.80

def mde_two_sample(sigma, n_eff, decile_frac=0.10, alpha=ALPHA, power=POWER):
    n1 = max(2, n_eff * decile_frac)
    n0 = max(2, n_eff * (1 - decile_frac))
    df = n1 + n0 - 2
    t_a = _stats.t.ppf(1 - alpha / 2, df)
    t_b = _stats.t.ppf(power, df)
    se = sigma * np.sqrt(1 / n1 + 1 / n0)
    return (t_a + t_b) * se, df

mde_day, df_day = mde_two_sample(sigma, g_day)
mde_qtr, df_qtr = mde_two_sample(sigma, g_quarter)

print(f"\nEffective clusters (day-clustered):     {g_day:,}  -> df={df_day:.0f}  "
      f"MDE (80% power, top-decile-vs-rest) = {mde_day*100:.2f}%")
print(f"Effective clusters (quarter-clustered): {g_quarter:,}  -> df={df_qtr:.0f}  "
      f"MDE (80% power, top-decile-vs-rest) = {mde_qtr*100:.2f}%")
print(f"\nRound-trip cost band for comparison: 0.20% - 0.30%")
print(f"Day-clustered MDE {'<=' if mde_day*100 <= 0.30 else '>'} cost band")
print(f"Quarter-clustered MDE {'<=' if mde_qtr*100 <= 0.30 else '>'} cost band")

con2.close()
con.close()

