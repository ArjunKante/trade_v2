"""Corrected: stratify the share-capital-tag sample by ANNOUNCEMENT year
(known_date), matching Phase A's own point-in-time convention, not
period_end -- the two disagree on which year a filing belongs to often
enough to matter, as the first pass of this check found out.
"""
import re
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import requests

N_PER_YEAR = 40
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

con = duckdb.connect("data/warehouse.duckdb", read_only=True)
sample = con.execute(f"""
    SELECT symbol, isin, period_end, known_date, xbrl_url, EXTRACT(year FROM known_date) AS announce_yr
    FROM fundamentals_filings
    WHERE reporting_quarter != 'Annual' AND xbrl_url IS NOT NULL AND xbrl_url NOT LIKE '%xbrl/-'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY EXTRACT(year FROM known_date) ORDER BY random()) <= {N_PER_YEAR}
""").fetchdf()
con.close()

print(f"Sampling {len(sample)} documents across {sample['announce_yr'].nunique()} announcement-years")

PAIDUP_RE = re.compile(r"PaidUpValueOfEquityShareCapital[^>]*>([\d.]+)<")
FACEVAL_RE = re.compile(r"FaceValueOfEquityShareCapital[^>]*>([\d.]+)<")

results = []
for i, row in sample.iterrows():
    try:
        r = requests.get(row["xbrl_url"], headers={"User-Agent": USER_AGENT}, timeout=15)
        time.sleep(0.5)
        paidup_m = PAIDUP_RE.search(r.text)
        faceval_m = FACEVAL_RE.search(r.text)
        has_both = bool(paidup_m and faceval_m)
        sane = None
        if has_both:
            paidup = float(paidup_m.group(1))
            faceval = float(faceval_m.group(1))
            sane = faceval > 0 and 1000 <= (paidup / faceval) <= 5e10
        results.append({"announce_yr": row["announce_yr"], "has_both": has_both, "sane": sane})
    except Exception:
        results.append({"announce_yr": row["announce_yr"], "has_both": False, "sane": None})
    if (i + 1) % 100 == 0:
        print(f"  ... {i+1}/{len(sample)} done", flush=True)

res = pd.DataFrame(results)
print(f"\n=== COVERAGE BY ANNOUNCEMENT YEAR (sampled, up to {N_PER_YEAR}/year, among real-XBRL filings only) ===")
cov = res.groupby("announce_yr").agg(n=("has_both", "size"), n_has_tags=("has_both", "sum"), n_sane=("sane", "sum"))
cov["pct_has_tags"] = cov["n_has_tags"] / cov["n"] * 100
print(cov.to_string())
res.to_csv("data/shares_outstanding_coverage_sample_v2.csv", index=False)
