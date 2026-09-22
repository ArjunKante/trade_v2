"""Phase C step 1: does NOT commit to a full extraction. Stratified real
sample (50 documents/year) of quarterly XBRL, checking for
PaidUpValueOfEquityShareCapital + FaceValueOfEquityShareCapital presence
and a sane computed share count. Coverage-by-year gate before building
anything, per instruction.
"""
import re
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

N_PER_YEAR = 50
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

con = duckdb.connect("data/warehouse.duckdb", read_only=True)
sample = con.execute(f"""
    SELECT symbol, isin, period_end, xbrl_url, EXTRACT(year FROM period_end) AS yr
    FROM fundamentals_filings
    WHERE reporting_quarter != 'Annual' AND xbrl_url IS NOT NULL AND xbrl_url NOT LIKE '%xbrl/-'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY EXTRACT(year FROM period_end) ORDER BY random()) <= {N_PER_YEAR}
""").fetchdf()
con.close()

print(f"Sampling {len(sample)} documents across {sample['yr'].nunique()} years")

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
        shares = None
        sane = None
        if has_both:
            paidup = float(paidup_m.group(1))
            faceval = float(faceval_m.group(1))
            if faceval > 0:
                shares = paidup / faceval
                sane = 1000 <= shares <= 5e10  # loose sanity band
        results.append({"yr": row["yr"], "symbol": row["symbol"], "has_both": has_both,
                         "shares": shares, "sane": sane, "http": r.status_code})
    except Exception as e:
        results.append({"yr": row["yr"], "symbol": row["symbol"], "has_both": False,
                         "shares": None, "sane": None, "http": "ERR"})

    if (i + 1) % 100 == 0:
        print(f"  ... {i+1}/{len(sample)} done", flush=True)

res = pd.DataFrame(results)
print("\n=== COVERAGE BY YEAR (sampled, {} per year) ===".format(N_PER_YEAR))
cov = res.groupby("yr").agg(n=("has_both", "size"), n_has_tags=("has_both", "sum"), n_sane=("sane", "sum"))
cov["pct_has_tags"] = cov["n_has_tags"] / cov["n"] * 100
cov["pct_sane"] = cov["n_sane"] / cov["n"] * 100
print(cov.to_string())
res.to_csv("data/shares_outstanding_coverage_sample.csv", index=False)
