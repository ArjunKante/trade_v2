"""Analysis/reporting pass over data/liquidity/mae_diagnostic_trades.pkl.
Pure read-only reporting, no new price data touched."""
import pickle

import numpy as np
import pandas as pd

with open("data/liquidity/mae_diagnostic_trades.pkl", "rb") as f:
    df = pickle.load(f)

df["direction_group"] = df["study"].map({"A": "LONG", "C_long": "LONG", "B": "SHORT", "C_short": "SHORT"})

PCTS = [50, 75, 90, 95, 99]


def pct_row(x):
    x = x.dropna()
    row = {f"p{p}": np.percentile(x, p) for p in PCTS}
    row["max"] = x.max()
    row["n"] = len(x)
    return row


print("=" * 100)
print("SECTION A: MAE distribution (%), within 10 days and within 30 days, by direction")
print("=" * 100)
for grp, sub in df.groupby("direction_group"):
    print(f"\n--- {grp} (n={len(sub)} stopped-out trades) ---")
    for col, label in [("mae_pct_10d", "MAE within 10d"), ("mae_pct_30d", "MAE within 30d")]:
        r = pct_row(sub[col])
        print(f"  {label}: " + "  ".join(f"{k}={v:.2f}" for k, v in r.items() if k != "n") + f"  (n={r['n']})")

print()
print("--- same, per individual study ---")
for study, sub in df.groupby("study"):
    print(f"\n{study} (n={len(sub)}):")
    for col, label in [("mae_pct_10d", "MAE 10d"), ("mae_pct_30d", "MAE 30d")]:
        r = pct_row(sub[col])
        print(f"  {label}: " + "  ".join(f"{k}={v:.2f}" for k, v in r.items() if k != "n"))

print()
print("=" * 100)
print("SECTION B: how many trades crossed 10% / 20% / 50% adverse (using 30-day MAE)")
print("=" * 100)
for grp, sub in df.groupby("direction_group"):
    n = len(sub)
    print(f"\n--- {grp} (n={n}) ---")
    for thresh in [10, 20, 50]:
        cnt = (sub["mae_pct_30d"] >= thresh).sum()
        print(f"  >= {thresh}% adverse (30d MAE): {cnt} ({cnt/n*100:.1f}%)")
    print("  [10-day MAE basis, for comparison]")
    for thresh in [10, 20, 50]:
        cnt = (sub["mae_pct_10d"] >= thresh).sum()
        print(f"  >= {thresh}% adverse (10d MAE): {cnt} ({cnt/n*100:.1f}%)")

print()
print("=" * 100)
print("SECTION C: of trades in each MAE bucket, recovery to 1.5R / 3R within 30 days")
print("=" * 100)
for grp, sub in df.groupby("direction_group"):
    print(f"\n--- {grp} ---")
    for thresh in [10, 20, 50]:
        bucket = sub[sub["mae_pct_30d"] >= thresh]
        n = len(bucket)
        if n == 0:
            print(f"  >= {thresh}%: n=0")
            continue
        r15 = bucket["r1_5_session"].notna()
        r3 = bucket["r3_session"].notna()
        print(f"  >= {thresh}% adverse: n={n}")
        print(f"    recovered to 1.5R within 30d: {r15.sum()} ({r15.mean()*100:.1f}%)"
              + (f"  median days={bucket.loc[r15,'r1_5_session'].median():.0f}" if r15.any() else ""))
        print(f"    recovered to 3R   within 30d: {r3.sum()} ({r3.mean()*100:.1f}%)"
              + (f"  median days={bucket.loc[r3,'r3_session'].median():.0f}" if r3.any() else ""))

print()
print("=" * 100)
print("SECTION D: full return distribution at day 10 and day 30, no stop at all")
print("=" * 100)
for grp, sub in df.groupby("direction_group"):
    print(f"\n--- {grp} (n={len(sub)}) ---")
    for col, label in [("day10_return", "day 10"), ("day30_return", "day 30")]:
        x = sub[col].dropna() * 100
        print(f"  {label}: mean={x.mean():.2f}%  median={x.median():.2f}%  "
              f"p10={np.percentile(x,10):.2f}%  p25={np.percentile(x,25):.2f}%  "
              f"p75={np.percentile(x,75):.2f}%  p90={np.percentile(x,90):.2f}%  "
              f"worst={x.min():.2f}%  best={x.max():.2f}%  (n={len(x)})")

print()
print("--- same, per individual study ---")
for study, sub in df.groupby("study"):
    print(f"\n{study} (n={len(sub)}):")
    for col, label in [("day10_return", "day 10"), ("day30_return", "day 30")]:
        x = sub[col].dropna() * 100
        print(f"  {label}: mean={x.mean():.2f}%  median={x.median():.2f}%  worst={x.min():.2f}%  best={x.max():.2f}%")

print()
print("=" * 100)
print("Data coverage check")
print("=" * 100)
print(df["n_future_days_available"].value_counts().sort_index())
print("no_intraday_data counts:", df["no_intraday_data"].sum(), "of", len(df))
