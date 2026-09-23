"""Reframed #1 (descriptive diagnostic ONLY, no study slot spent, NOT a
test): characterizes momentum's relative performance in every historical
drawdown episode, where "drawdown episode" is defined MECHANICALLY on the
BENCHMARK's NAV (equal-weight universe, same series used throughout this
project) -- benchmark peak-to-trough decline exceeding 15% -- never by
picking a period because of what is already known to have happened in it.

This does NOT validate anything and carries no decision rule. It exists
only to describe what the strategy actually did in every period meeting a
mechanical criterion, replacing the ad hoc "2020 specifically" example in
FINDINGS.md Section 4 with an exhaustive, criterion-first accounting.
Sample size is small (this project has one ~8-year pre-holdout series);
that limitation is stated, not hidden.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
DD_THRESHOLD = -0.15  # fixed before looking at any episode; not tuned to produce a particular count

nav = pd.read_csv(ROOT / "data" / "backtest_momentum_nav.csv", parse_dates=["date"])
rec = pd.read_csv(ROOT / "data" / "backtest_momentum_records.csv", parse_dates=["date"])
nav = nav.drop_duplicates(subset="date", keep="last").reset_index(drop=True)

bench = nav["benchmark_nav"].values
dates = nav["date"].values
running_peak = pd.Series(bench).cummax().values
dd = bench / running_peak - 1

# ---------------------------------------------------------------------------
# Mechanical episode detection: an episode starts at the peak index whose
# subsequent drawdown first breaches DD_THRESHOLD, and ends at the first
# later index where NAV recovers back to (or above) that same peak level --
# or at the series end if it never recovers. Peak-to-trough uses the actual
# minimum NAV reached within the episode, not just the breach point.
# ---------------------------------------------------------------------------
episodes = []
i = 0
n = len(bench)
while i < n:
    if dd[i] <= DD_THRESHOLD:
        # walk back to find this episode's peak: the most recent index <= i
        # where bench actually equals the running peak at i
        peak_val = running_peak[i]
        peak_idx = max(j for j in range(i + 1) if bench[j] == peak_val)
        # walk forward to trough (min NAV before recovery back to peak_val or series end)
        j = i
        trough_idx = i
        while j < n and bench[j] < peak_val:
            if bench[j] < bench[trough_idx]:
                trough_idx = j
            j += 1
        recovered_idx = j if j < n else None
        episodes.append((peak_idx, trough_idx, recovered_idx))
        i = j if j > i else i + 1
    else:
        i += 1

# dedupe overlapping detections (walk-forward above can re-trigger mid-episode)
dedup = []
for ep in episodes:
    if dedup and ep[0] <= dedup[-1][1]:
        continue
    dedup.append(ep)

print(f"Benchmark drawdown episodes exceeding {abs(DD_THRESHOLD)*100:.0f}% peak-to-trough "
      f"(mechanical threshold, fixed before inspection): {len(dedup)}")
print(f"Series: {pd.Timestamp(dates[0]).date()} to {pd.Timestamp(dates[-1]).date()}, "
      f"{n} rebalance-period NAV points\n")

rows = []
for peak_idx, trough_idx, recovered_idx in dedup:
    peak_date = pd.Timestamp(dates[peak_idx])
    trough_date = pd.Timestamp(dates[trough_idx])
    end_idx = recovered_idx if recovered_idx is not None else n - 1
    end_date = pd.Timestamp(dates[end_idx])
    bench_dd = bench[trough_idx] / bench[peak_idx] - 1

    window = rec[(rec["date"] > peak_date) & (rec["date"] <= end_date)]
    if window.empty:
        continue
    mom_compounded = (1 + window["mom_net"]).prod() - 1
    bench_compounded = (1 + window["bench_net"]).prod() - 1
    rows.append({
        "peak_date": peak_date.date(), "trough_date": trough_date.date(),
        "recovered": recovered_idx is not None, "end_date": end_date.date(),
        "n_periods": len(window), "bench_peak_to_trough": bench_dd * 100,
        "mom_net_over_episode": mom_compounded * 100, "bench_net_over_episode": bench_compounded * 100,
        "mom_minus_bench_pts": (mom_compounded - bench_compounded) * 100,
    })

ep_df = pd.DataFrame(rows)
print(ep_df.to_string(index=False, formatters={
    c: "{:.2f}".format for c in ["bench_peak_to_trough", "mom_net_over_episode", "bench_net_over_episode", "mom_minus_bench_pts"]
}))

if len(ep_df):
    wins = (ep_df["mom_minus_bench_pts"] > 0).sum()
    print(f"\nMomentum beat the benchmark (compounded, over the peak-to-recovery/end window) in "
          f"{wins} of {len(ep_df)} mechanically-defined drawdown episodes.")
    print(f"Mean relative return across episodes: {ep_df['mom_minus_bench_pts'].mean():+.2f} pts "
          f"(median: {ep_df['mom_minus_bench_pts'].median():+.2f} pts)")

print(
    "\nDESCRIPTIVE ONLY -- not a test. n is small (one pre-holdout series, "
    f"{len(ep_df)} episodes meeting a fixed mechanical threshold); no significance claim is "
    "made or implied, and none should be inferred from the win count above. This replaces "
    "FINDINGS.md Section 4's single hand-referenced 2020 example with an exhaustive account "
    "of every period meeting a criterion set before looking at outcomes -- it does not convert "
    "the qualitative 2020 finding into a validated one."
)

# ---------------------------------------------------------------------------
# The one episode found spans peak(2017-11) -> trough(2020-03) -> recovery
# (2021-03) -- a much longer window than "2020" alone. Split into its two
# mechanical legs (decline: peak->trough; recovery: trough->end) since
# FINDINGS.md Section 3 (downside protection) and Section 4 (recovery-leg
# opportunity cost) each describe one leg, not the whole episode -- this
# was decided as a follow-up split, not a second free choice of window.
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("Same episode, split into its two mechanical legs (decline vs recovery)")
print("=" * 78)
for peak_idx, trough_idx, recovered_idx in dedup:
    peak_date, trough_date = pd.Timestamp(dates[peak_idx]), pd.Timestamp(dates[trough_idx])
    end_idx = recovered_idx if recovered_idx is not None else n - 1
    end_date = pd.Timestamp(dates[end_idx])

    decline = rec[(rec["date"] > peak_date) & (rec["date"] <= trough_date)]
    recov = rec[(rec["date"] > trough_date) & (rec["date"] <= end_date)]
    for label, w in [("decline (peak->trough)", decline), ("recovery (trough->end)", recov)]:
        if w.empty:
            continue
        mc = (1 + w["mom_net"]).prod() - 1
        bc = (1 + w["bench_net"]).prod() - 1
        print(f"{label:28s} {str(w['date'].min().date())} to {str(w['date'].max().date()):12s} "
              f"n={len(w):2d}  mom={mc*100:+7.2f}%  bench={bc*100:+7.2f}%  diff={(mc-bc)*100:+7.2f}pts")

# ---------------------------------------------------------------------------
# Secondary mechanical threshold (10%), fixed here as the standard "correction"
# level rather than tuned to produce a specific episode count -- reported for
# completeness alongside the 15% result, not instead of it.
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("Secondary threshold check: 10% (standard 'correction' level, reported alongside 15%, not instead of it)")
print("=" * 78)
DD_THRESHOLD_2 = -0.10
dd2 = bench / running_peak - 1
episodes2 = []
i = 0
while i < n:
    if dd2[i] <= DD_THRESHOLD_2:
        peak_val = running_peak[i]
        peak_idx = max(j for j in range(i + 1) if bench[j] == peak_val)
        j = i
        trough_idx = i
        while j < n and bench[j] < peak_val:
            if bench[j] < bench[trough_idx]:
                trough_idx = j
            j += 1
        episodes2.append((peak_idx, trough_idx, j if j < n else None))
        i = j if j > i else i + 1
    else:
        i += 1
dedup2 = []
for ep in episodes2:
    if dedup2 and ep[0] <= dedup2[-1][1]:
        continue
    dedup2.append(ep)

rows2 = []
for peak_idx, trough_idx, recovered_idx in dedup2:
    peak_date, trough_date = pd.Timestamp(dates[peak_idx]), pd.Timestamp(dates[trough_idx])
    end_idx = recovered_idx if recovered_idx is not None else n - 1
    end_date = pd.Timestamp(dates[end_idx])
    bench_dd = bench[trough_idx] / bench[peak_idx] - 1
    window = rec[(rec["date"] > peak_date) & (rec["date"] <= end_date)]
    if window.empty:
        continue
    mc = (1 + window["mom_net"]).prod() - 1
    bc = (1 + window["bench_net"]).prod() - 1
    rows2.append({
        "peak_date": peak_date.date(), "trough_date": trough_date.date(), "end_date": end_date.date(),
        "n_periods": len(window), "bench_peak_to_trough": bench_dd * 100,
        "mom_minus_bench_pts": (mc - bc) * 100,
    })
ep_df2 = pd.DataFrame(rows2)
print(f"Episodes at 10% threshold: {len(ep_df2)}")
if len(ep_df2):
    print(ep_df2.to_string(index=False, formatters={c: "{:.2f}".format for c in ["bench_peak_to_trough", "mom_minus_bench_pts"]}))
    wins2 = (ep_df2["mom_minus_bench_pts"] > 0).sum()
    print(f"\nMomentum beat the benchmark in {wins2} of {len(ep_df2)} episodes at the 10% threshold.")
