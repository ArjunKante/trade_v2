"""DIAGNOSTIC, not a study -- no strategy, no decision rule, no slot spent.
Does top-decile sector concentration AT SELECTION TIME predict the
strategy's subsequent relative return over that period? Descriptive
measurement on data already seen (Study 1 microcap + Study 2 large-cap).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]


def fisher_se(r, n):
    """SE of a correlation coefficient via the Fisher z-transform."""
    z_se = 1 / np.sqrt(n - 3)
    return z_se  # SE in z-space; convert bounds separately if needed


def report_correlation(x, y, n, label):
    rho, p = stats.spearmanr(x, y)
    z_se = 1 / np.sqrt(n - 3)
    z = np.arctanh(rho)
    lo, hi = np.tanh(z - 1.96 * z_se), np.tanh(z + 1.96 * z_se)
    print(f"  {label}: Spearman rho = {rho:+.3f}, p = {p:.3f}, 95% CI [{lo:+.3f}, {hi:+.3f}] (n={n})")
    return rho, p


def partial_spearman(x, y, z, n):
    """Partial Spearman correlation of x,y controlling for z (Pearson
    formula applied to Spearman correlations, standard practice)."""
    rxy, _ = stats.spearmanr(x, y)
    rxz, _ = stats.spearmanr(x, z)
    ryz, _ = stats.spearmanr(y, z)
    num = rxy - rxz * ryz
    den = np.sqrt((1 - rxz**2) * (1 - ryz**2))
    r_partial = num / den if den != 0 else np.nan
    # approximate t-test for partial correlation, df = n-3
    df = n - 3
    if abs(r_partial) < 1:
        t_stat = r_partial * np.sqrt(df / (1 - r_partial**2))
        p = 2 * (1 - stats.t.cdf(abs(t_stat), df))
    else:
        p = np.nan
    return r_partial, p, rxz, ryz


def critical_r_for_p05(n):
    """|r| needed for p<0.05 two-tailed, Spearman approx via t-distribution, df=n-2."""
    df = n - 2
    t_crit = stats.t.ppf(1 - 0.025, df)
    r_crit = t_crit / np.sqrt(df + t_crit**2)
    return r_crit


def run_study(name, backtest_csv, sector_csv, n_report_2020):
    print("\n" + "=" * 80)
    print(f"STUDY: {name}")
    print("=" * 80)

    bt = pd.read_csv(backtest_csv, parse_dates=["date"])
    sec = pd.read_csv(sector_csv, parse_dates=["date"])
    sec_dedup = sec.drop(columns=[c for c in ["n_holdings"] if c in sec.columns and c in bt.columns])
    df = bt.merge(sec_dedup, on="date", how="inner")
    df["relative_return"] = df["mom_net"] - df["bench_net"]
    n = len(df)
    print(f"Merged n = {n} (backtest had {len(bt)}, sector audit had {len(sec)})")

    n_holdings_col = "n_holdings" if "n_holdings" in df.columns else "mom_n"

    print("\n--- Power problem, stated upfront ---")
    r_crit = critical_r_for_p05(n)
    print(f"At n={n}, |Spearman rho| >= {r_crit:.3f} is needed for p<0.05 (two-tailed).")

    print("\n--- Correlation: concentration vs subsequent relative return ---")
    rho_conc, p_conc = report_correlation(df["top_sector_pct"], df["relative_return"], n, "top_sector_pct vs relative_return")
    rho_hhi, p_hhi = report_correlation(df["hhi"], df["relative_return"], n, "hhi vs relative_return")

    print("\n--- Mechanical confound: holding count vs concentration ---")
    rho_n_conc, p_n_conc = report_correlation(df[n_holdings_col], df["top_sector_pct"], n, "n_holdings vs top_sector_pct")
    rho_n_hhi, p_n_hhi = report_correlation(df[n_holdings_col], df["hhi"], n, "n_holdings vs hhi")

    print("\n--- Partial correlations, controlling for n_holdings ---")
    rp_conc, pp_conc, _, _ = partial_spearman(df["top_sector_pct"], df["relative_return"], df[n_holdings_col], n)
    print(f"  top_sector_pct vs relative_return | n_holdings: partial rho = {rp_conc:+.3f}, p = {pp_conc:.3f}")
    rp_hhi, pp_hhi, _, _ = partial_spearman(df["hhi"], df["relative_return"], df[n_holdings_col], n)
    print(f"  hhi vs relative_return | n_holdings: partial rho = {rp_hhi:+.3f}, p = {pp_hhi:.3f}")

    print("\n--- Median split: concentration (top_sector_pct) ---")
    med = df["top_sector_pct"].median()
    high = df[df["top_sector_pct"] >= med]["relative_return"]
    low = df[df["top_sector_pct"] < med]["relative_return"]
    diff = high.mean() - low.mean()
    se_diff = np.sqrt(high.var(ddof=1) / len(high) + low.var(ddof=1) / len(low))
    print(f"  median top_sector_pct = {med:.2f}%")
    print(f"  high-concentration half (n={len(high)}): mean relative return = {high.mean()*100:+.3f}%, SD={high.std()*100:.3f}%")
    print(f"  low-concentration half  (n={len(low)}): mean relative return = {low.mean()*100:+.3f}%, SD={low.std()*100:.3f}%")
    print(f"  difference (high - low) = {diff*100:+.3f} pts, SE = {se_diff*100:.3f} pts, t = {diff/se_diff if se_diff else float('nan'):.2f}")

    print("\n--- Median split: HHI ---")
    medh = df["hhi"].median()
    highh = df[df["hhi"] >= medh]["relative_return"]
    lowh = df[df["hhi"] < medh]["relative_return"]
    diffh = highh.mean() - lowh.mean()
    se_diffh = np.sqrt(highh.var(ddof=1) / len(highh) + lowh.var(ddof=1) / len(lowh))
    print(f"  median hhi = {medh:.4f}")
    print(f"  high-HHI half (n={len(highh)}): mean relative return = {highh.mean()*100:+.3f}%, SD={highh.std()*100:.3f}%")
    print(f"  low-HHI half  (n={len(lowh)}): mean relative return = {lowh.mean()*100:+.3f}%, SD={lowh.std()*100:.3f}%")
    print(f"  difference (high - low) = {diffh*100:+.3f} pts, SE = {se_diffh*100:.3f} pts, t = {diffh/se_diffh if se_diffh else float('nan'):.2f}")

    print("\n--- All individual points (date, n_holdings, top_sector_pct, hhi, relative_return) ---")
    df["conc_rank"] = df["top_sector_pct"].rank(ascending=False).astype(int)
    df["hhi_rank"] = df["hhi"].rank(ascending=False).astype(int)
    out = df[["date", n_holdings_col, "top_sector_pct", "conc_rank", "hhi", "hhi_rank", "relative_return"]].copy()
    out["relative_return"] = out["relative_return"] * 100
    print(out.to_string(index=False))

    print("\n--- 2020 rebalances specifically ---")
    y2020 = df[pd.to_datetime(df["date"]).dt.year == 2020]
    if len(y2020):
        for _, row in y2020.iterrows():
            print(f"  {row['date'].date()}: top_sector_pct={row['top_sector_pct']:.2f}% (rank {int(row['conc_rank'])} of {n} by concentration), "
                  f"hhi={row['hhi']:.4f} (rank {int(row['hhi_rank'])} of {n} by HHI), relative_return={row['relative_return']*100:+.3f}%")
    else:
        print("  no 2020 rebalances in this study's sample")

    df.to_csv(ROOT / "data" / f"concentration_diagnostic_{name.replace(' ', '_').lower()}.csv", index=False)
    return df


df1 = run_study("Study 1 microcap", ROOT / "data" / "backtest_original_records_v2.csv",
                 ROOT / "data" / "sector_concentration_audit.csv", 3)
df2 = run_study("Study 2 largecap", ROOT / "data" / "study2_largecap_records.csv",
                 ROOT / "data" / "study2_sector_concentration.csv", 3)
