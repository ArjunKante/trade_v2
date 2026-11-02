"""Analysis/reporting pass over data/liquidity/horizon_diagnostic_trades.pkl
(produced by liquidity_abc_horizon_diagnostic.py). Pure read-only reporting,
no new price data touched."""
import pickle
import pandas as pd

with open("data/liquidity/horizon_diagnostic_trades.pkl", "rb") as f:
    df = pickle.load(f)

df["direction_group"] = df["study"].map({"A": "LONG", "C_long": "LONG", "B": "SHORT", "C_short": "SHORT"})

LEVELS = ["stop", "r1_5", "r3", "r5", "r10"]


def cum_reach_pct(sub, level):
    sess = sub[f"{level}_session"]
    n = len(sub)
    out = {"same_day": (sess == 0).sum() / n * 100}
    for chk in [1, 2, 3, 5, 10]:
        out[f"by_day_{chk}"] = (sess <= chk).sum() / n * 100
    out["never"] = sess.isna().sum() / n * 100
    return out


print("=" * 100)
print("SECTION 1: first-touch cumulative-reach distribution per level, per study")
print("=" * 100)
for study, sub in df.groupby("study"):
    print(f"\n--- {study} (n={len(sub)}) ---")
    rows = [{"level": level, **cum_reach_pct(sub, level)} for level in LEVELS]
    print(pd.DataFrame(rows).set_index("level").round(1).to_string())

print()
print("=" * 100)
print("SECTION 1b: same, combined by direction (LONG = A+C_long, SHORT = B+C_short)")
print("=" * 100)
for grp, sub in df.groupby("direction_group"):
    print(f"\n--- {grp} (n={len(sub)}) ---")
    rows = [{"level": level, **cum_reach_pct(sub, level)} for level in LEVELS]
    print(pd.DataFrame(rows).set_index("level").round(1).to_string())

print()
print("=" * 100)
print("SECTION 2: of trades that hit stop SAME DAY, how many went on to reach 1.5R / 3R within 10 days?")
print("=" * 100)
for grp, sub in df.groupby("direction_group"):
    same_day_stop = sub[sub["stop_session"] == 0]
    n = len(same_day_stop)
    reached_15 = same_day_stop["r1_5_session"].notna().sum()
    reached_3 = same_day_stop["r3_session"].notna().sum()
    reached_either = (same_day_stop["r1_5_session"].notna() | same_day_stop["r3_session"].notna()).sum()
    print(f"{grp}: n_same_day_stop={n} ({n/len(sub)*100:.1f}% of all {grp} trades)")
    print(f"  -> also reached 1.5R within 10d: {reached_15} ({reached_15/n*100:.1f}%)")
    print(f"  -> also reached 3R   within 10d: {reached_3} ({reached_3/n*100:.1f}%)")
    print(f"  -> reached EITHER level: {reached_either} ({reached_either/n*100:.1f}%)")

print()
print("--- same breakdown per individual study ---")
for study, sub in df.groupby("study"):
    same_day_stop = sub[sub["stop_session"] == 0]
    n = len(same_day_stop)
    reached_15 = same_day_stop["r1_5_session"].notna().sum()
    reached_3 = same_day_stop["r3_session"].notna().sum()
    print(f"{study}: n_same_day_stop={n} ({n/len(sub)*100:.1f}%)  "
          f"->1.5R:{reached_15}({reached_15/n*100:.1f}%)  ->3R:{reached_3}({reached_3/n*100:.1f}%)")

print()
print("=" * 100)
print("SECTION 3: TIME_EXIT_FULL trades (never reached half target) -- where did price end up by day 10?")
print("=" * 100)
for grp, sub in df.groupby("direction_group"):
    time_exit = sub[sub["outcome"] == "TIME_EXIT_FULL"]
    n = len(time_exit)
    r = time_exit["day10_return"].dropna()
    pct_positive = (r > 0).mean() * 100
    reached_15_later = time_exit["r1_5_session"].notna().sum()
    reached_3_later = time_exit["r3_session"].notna().sum()
    print(f"{grp}: n_TIME_EXIT_FULL={n} ({n/len(sub)*100:.1f}% of all {grp} trades)")
    print(f"  day10_return: mean={r.mean()*100:.3f}%  median={r.median()*100:.3f}%  pct_positive={pct_positive:.1f}%")
    print(f"  of these, later reached 1.5R within 10d anyway: {reached_15_later} ({reached_15_later/n*100:.1f}%)")
    print(f"  of these, later reached 3R   within 10d anyway: {reached_3_later} ({reached_3_later/n*100:.1f}%)")

print()
print("--- same breakdown per individual study ---")
for study, sub in df.groupby("study"):
    time_exit = sub[sub["outcome"] == "TIME_EXIT_FULL"]
    n = len(time_exit)
    r = time_exit["day10_return"].dropna()
    print(f"{study}: n={n} ({n/len(sub)*100:.1f}%)  mean_day10_ret={r.mean()*100:.3f}%  "
          f"median={r.median()*100:.3f}%  pct_pos={(r>0).mean()*100:.1f}%")

print()
print("=" * 100)
print("SECTION 4: of trades where BOTH stop AND a target were reached within 10 days, which came first?")
print("=" * 100)
for target_level, target_name in [("r1_5", "1.5R"), ("r3", "3R")]:
    print(f"\n--- target = {target_name} ---")
    for grp, sub in df.groupby("direction_group"):
        both = sub[sub["stop_session"].notna() & sub[f"{target_level}_session"].notna()]
        n = len(both)
        stop_sess = both["stop_session"]
        targ_sess = both[f"{target_level}_session"]
        stop_first = (stop_sess < targ_sess).sum()
        targ_first = (targ_sess < stop_sess).sum()
        same_session = (stop_sess == targ_sess).sum()
        print(f"{grp}: n_both_reached={n} ({n/len(sub)*100:.1f}% of all {grp})")
        print(f"   stop first: {stop_first} ({stop_first/n*100:.1f}%)  target first: {targ_first} "
              f"({targ_first/n*100:.1f}%)  same session (ambiguous order): {same_session} ({same_session/n*100:.1f}%)")
        diff_sess = both[stop_sess != targ_sess]
        gap = (diff_sess[f"{target_level}_session"] - diff_sess["stop_session"]).abs()
        print(f"   median session gap (when orderable): {gap.median():.1f} sessions, mean {gap.mean():.2f}")
        same0 = both[(stop_sess == 0) & (targ_sess == 0)]
        if len(same0):
            targ_ts = pd.to_datetime(same0[f"{target_level}_when"])
            stop_ts = pd.to_datetime(same0["stop_when"])
            dt_min = (targ_ts - stop_ts).dt.total_seconds() / 60.0
            n_exact_tie = (dt_min == 0).sum()
            print(f"   of the same-session-0 cases (n={len(same0)}): exact-same-minute ties={n_exact_tie}, "
                  f"target-before-stop={(dt_min<0).sum()}, stop-before-target={(dt_min>0).sum()}")
