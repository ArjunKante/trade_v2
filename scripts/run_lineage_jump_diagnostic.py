"""Bug #1 follow-up (diagnostic, no study slot spent): extend the
corporate-actions parser to capital reductions / schemes of arrangement, or
if the feed genuinely can't be parsed into a ratio for these, detect the
jump structurally and NaN only the affected boundary return -- not the
whole entity.

Reproduces Bug #1's finding (14 of 318 lineage transitions show an
unexplained >1.5x/<0.67x adjusted-price jump), then for each one: (a)
checks the cached raw corporate-actions feed for ANY record on that
symbol within +-10 days of the transition, not just bonus/split matches,
to see whether a capital-reduction/scheme subject exists but was silently
dropped by the current bonus/split-only regex; (b) reports which of the 14
get a plausible explanation this way vs remain genuinely unexplained.
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection

ROOT = Path(__file__).resolve().parents[1]
con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

# ---------------------------------------------------------------------------
# Reproduce Bug #1: find every lineage transition's adjusted-price boundary
# ratio (last close under predecessor_isin -> first close under isin).
# ---------------------------------------------------------------------------
lineage = con.execute(
    "SELECT isin, entity_id, predecessor_isin, known_date AS transition_date "
    "FROM isin_lineage WHERE predecessor_isin IS NOT NULL"
).fetchdf()
print(f"Total lineage transitions: {len(lineage)}")

prices = con.execute(
    "SELECT p.isin, p.symbol, p.trade_date, p.close, af.factor, p.close * af.factor AS adj_close "
    "FROM prices_eod p "
    "JOIN isin_lineage l ON l.isin = p.isin "
    "JOIN adjustment_factors af ON af.trade_date = p.trade_date AND af.entity_id = l.entity_id "
    "WHERE p.series = 'EQ' AND (p.isin IN (SELECT predecessor_isin FROM isin_lineage WHERE predecessor_isin IS NOT NULL) "
    "OR p.isin IN (SELECT isin FROM isin_lineage WHERE predecessor_isin IS NOT NULL))"
).fetchdf()
prices["trade_date"] = pd.to_datetime(prices["trade_date"])

rows = []
for _, r in lineage.iterrows():
    pred = prices[prices["isin"] == r["predecessor_isin"]].sort_values("trade_date")
    cur = prices[prices["isin"] == r["isin"]].sort_values("trade_date")
    if pred.empty or cur.empty:
        continue
    last_pred = pred.iloc[-1]
    first_cur = cur.iloc[0]
    if last_pred["adj_close"] <= 0 or pd.isna(last_pred["adj_close"]) or pd.isna(first_cur["adj_close"]):
        continue
    ratio = first_cur["adj_close"] / last_pred["adj_close"]
    rows.append({
        "entity_id": r["entity_id"], "symbol": first_cur["symbol"],
        "predecessor_isin": r["predecessor_isin"], "isin": r["isin"],
        "transition_date": r["transition_date"],
        "pred_last_date": last_pred["trade_date"], "pred_last_adj_close": last_pred["adj_close"],
        "cur_first_date": first_cur["trade_date"], "cur_first_adj_close": first_cur["adj_close"],
        "boundary_ratio": ratio,
    })

jr = pd.DataFrame(rows)

SEALED_HOLDOUT_START = pd.Timestamp(2025, 3, 19)
jr_pre = jr[pd.to_datetime(jr["transition_date"]) < SEALED_HOLDOUT_START].copy()
jr_post = jr[pd.to_datetime(jr["transition_date"]) >= SEALED_HOLDOUT_START].copy()
print(f"Transitions before sealed holdout start (2025-03-19): {len(jr_pre)}  "
      f"(Bug #1 originally reported 318 at an earlier data snapshot)")
print(f"Transitions inside/after the sealed window (not used for the headline count below, "
      f"more raw data has landed since the seal was set): {len(jr_post)}")

unexplained = jr_pre[(jr_pre["boundary_ratio"] > 1.5) | (jr_pre["boundary_ratio"] < 0.67)].copy()
print(f"Unexplained (>1.5x or <0.67x) boundary jumps, PRE-HOLDOUT ONLY: {len(unexplained)} of {len(jr_pre)} "
      f"(Bug #1 originally reported 14 of 318)")

# ---------------------------------------------------------------------------
# Check the cached raw feed (22,514 records, not filtered by the bonus/split
# regex) for ANY subject on these symbols near the transition date.
# ---------------------------------------------------------------------------
with open(ROOT / "data" / "raw" / "nse_corporate_actions_2016_2025.json", encoding="utf-8") as f:
    raw = json.load(f)
raw_df = pd.DataFrame(raw)
raw_df["ex_date"] = pd.to_datetime(raw_df["exDate"], format="%d-%b-%Y", errors="coerce")

BONUS_RE = re.compile(r"Bonus\s+(\d+)\s*:\s*(\d+)", re.IGNORECASE)
SPLIT_RE = re.compile(
    r"From\s+(?:Rs|Re)\.?\s*([\d.]+)\s*/?-?\s*Per\s+Share\s+To\s+(?:Rs|Re)\.?\s*([\d.]+)\s*/?-?\s*Per\s+Share",
    re.IGNORECASE,
)
CAPRED_RE = re.compile(r"capital\s+reduction|scheme\s+of\s+arrangement|reduction\s+of\s+capital|"
                        r"amalgamation|demerger|merger", re.IGNORECASE)

print("\n" + "=" * 100)
print("Per-transition: any raw feed record at all (window +-10 calendar days), and is it a bonus/split?")
print("=" * 100)

recovered, still_unexplained = [], []
for _, u in unexplained.iterrows():
    window_lo = u["transition_date"] - dt.timedelta(days=10)
    window_hi = u["transition_date"] + dt.timedelta(days=10)
    cand = raw_df[(raw_df["symbol"] == u["symbol"]) & (raw_df["ex_date"] >= window_lo) & (raw_df["ex_date"] <= window_hi)]
    matched_type = "NONE"
    matched_subject = ""
    for _, c in cand.iterrows():
        subj = c["subject"] or ""
        if BONUS_RE.search(subj) or SPLIT_RE.search(subj):
            matched_type = "bonus_or_split_ALREADY_PARSED"
            matched_subject = subj.strip()
            break
        if CAPRED_RE.search(subj):
            matched_type = "capital_reduction_or_scheme_FOUND_UNPARSED"
            matched_subject = subj.strip()
            break
    if matched_type == "NONE" and not cand.empty:
        matched_type = "OTHER_ACTION_NO_RATIO"
        matched_subject = "; ".join((c["subject"] or "").strip() for _, c in cand.iterrows())

    row = {
        "symbol": u["symbol"], "transition_date": u["transition_date"].date() if hasattr(u["transition_date"], "date") else u["transition_date"],
        "boundary_ratio": round(u["boundary_ratio"], 3), "feed_match": matched_type,
        "subject": matched_subject[:80],
    }
    if matched_type == "capital_reduction_or_scheme_FOUND_UNPARSED":
        recovered.append(row)
    else:
        still_unexplained.append(row)
    print(f"{u['symbol']:15s} {str(row['transition_date']):12s} ratio={row['boundary_ratio']:8.3f}  "
          f"{matched_type:35s} {matched_subject[:60]}")

print(f"\n{'=' * 100}")
print(f"RESULT: {len(recovered)} of {len(unexplained)} recovered (a capital-reduction/scheme/merger "
      f"subject exists in the feed but was never parsed for a ratio)")
print(f"        {len(still_unexplained)} of {len(unexplained)} still genuinely unexplained "
      f"(no matching record in the feed at all, or an event type with no numeric ratio derivable from subject text)")
con.close()
