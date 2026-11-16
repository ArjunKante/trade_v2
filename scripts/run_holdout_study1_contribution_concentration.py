"""DESCRIPTIVE diagnostic on the ALREADY-SPENT Study 1 holdout (identical
selection/construction to run_holdout_study1.py, the primary recorded
result -- nothing about the strategy varied, no new hypothesis tested,
same discipline as the Bug #11 materiality checks). Decomposes the
momentum portfolio's own compounded GROSS return, across the 5 real
holdout rebalances, into each selected entity's dollar contribution, and
reports how concentrated that return is in the top 1/5/10 contributors.

WHY GROSS, NOT NET: the blended turnover cost is a small, portfolio-level
drag applied once per period, identical in spirit across names -- it
does not change which entities dominate contribution. Using gross
returns keeps the decomposition EXACT: each period's total dollar P&L
is exactly the equal-weighted sum of its selected entities' per-entity
dollar contributions (weight 1/n_selected each), so summing every
entity's contribution across all 5 periods reproduces the portfolio's
total gross compounded growth exactly, with nothing left over to
assign.

WHY "momentum portfolio return," not literally "share of margin": the
margin is momentum's return minus the benchmark's, and the benchmark is
an equal-weighted average over 1100-1300 names each period -- no single
name can contribute much to IT by construction. This decomposition is
therefore a close proxy for "share of the margin" (the benchmark side
is diffuse by construction, the momentum side is where concentration
would show up), not a literal attribution of the margin itself, which
would require decomposing both sides. Stated explicitly rather than
overclaiming precision.

Usage:
    python scripts/run_holdout_study1_contribution_concentration.py
"""
import datetime as dt
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer.db import get_read_connection
from data_layer.holdout import SEALED_HOLDOUT_START
from data_layer.entity_panel import read_full_entity_panel_authorized
from factors.momentum import compute_momentum_12_1
from factors.target import compute_forward_return, HORIZON_DAYS

ROOT = Path(__file__).resolve().parents[1]
REBALANCE_DAYS = 63
DECILE_FRAC = 0.10

LOG_PATH = ROOT / "data" / "holdout_access_log.txt"
with open(LOG_PATH, "a") as f:
    f.write(f"{dt.datetime.now().isoformat()} | scripts/run_holdout_study1_contribution_concentration.py | "
            f"authorize_holdout=True | DESCRIPTIVE diagnostic on the already-spent, already-recorded Study 1 "
            f"holdout (run_holdout_study1.py's own selections) -- per-entity contribution concentration, "
            f"no new hypothesis, nothing about the strategy varied, no modification follows from the result.\n")
print(f"Holdout access logged to {LOG_PATH}", file=sys.stderr, flush=True)

con = get_read_connection(ROOT / "data" / "warehouse.duckdb")
panel = read_full_entity_panel_authorized(con, authorize_holdout=True)
con.close()

# unexplained_jump_dates={}: this decomposes the ORIGINAL, published
# holdout result (run_holdout_study1.py's own construction, unguarded by
# the same precedent) -- "no new hypothesis, nothing about the strategy
# varied" per this script's own docstring; decomposing a different
# (corrected) result would not be decomposing the recorded one.
mom = compute_momentum_12_1(panel, unexplained_jump_dates={})
fwd_clean = compute_forward_return(panel, unexplained_jump_dates={})
clean = mom.merge(fwd_clean, on=["entity_id", "trade_date"]).dropna(subset=["value", "fwd_return"])

all_dates = sorted(clean["trade_date"].unique())
rebalance_dates_all = all_dates[::REBALANCE_DAYS]
rebalance_dates_all = [d for d in rebalance_dates_all if all_dates.index(d) + HORIZON_DAYS < len(all_dates)]

holdout_start_ts = pd.Timestamp(SEALED_HOLDOUT_START)
holdout_rebalance_dates = [d for d in rebalance_dates_all if d >= holdout_start_ts]
print(f"{len(holdout_rebalance_dates)} holdout rebalances: "
      f"{holdout_rebalance_dates[0].date()} to {holdout_rebalance_dates[-1].date()}")

contributions = {}
nav = 1.0
for d in holdout_rebalance_dates:
    pool = clean[clean["trade_date"] == d].rename(columns={"fwd_return": "realized_return"})
    cutoff = pool["value"].quantile(1 - DECILE_FRAC)
    mom_sel = pool[pool["value"] >= cutoff]
    n = len(mom_sel)
    period_gross = mom_sel["realized_return"].mean()
    for _, row in mom_sel.iterrows():
        dollar_contrib = (1.0 / n) * row["realized_return"] * nav
        contributions[row["entity_id"]] = contributions.get(row["entity_id"], 0.0) + dollar_contrib
    nav *= (1 + period_gross)

total_growth = nav - 1.0
contrib_df = pd.DataFrame(
    [{"entity_id": k, "contribution": v} for k, v in contributions.items()]
).sort_values("contribution", ascending=False).reset_index(drop=True)
contrib_df["share_of_total_growth"] = contrib_df["contribution"] / total_growth

print(f"\nTotal gross compounded growth over {len(holdout_rebalance_dates)} holdout rebalances: {total_growth*100:.2f}%")
print(f"Distinct entities ever selected: {len(contrib_df)}")
print(f"Sum of all contributions (should equal total growth, exact decomposition): "
      f"{contrib_df['contribution'].sum()*100:.4f}% vs {total_growth*100:.4f}%")

print("\nTop 10 contributors:")
print(contrib_df.head(10).to_string(index=False))

for top_n in (1, 5, 10):
    share = contrib_df.head(top_n)["share_of_total_growth"].sum()
    print(f"\nTop {top_n} contributor(s): {share*100:.1f}% of total gross compounded growth")

# resolve symbols for readability
symbols = con2 = None
con2 = get_read_connection(ROOT / "data" / "warehouse.duckdb")
sym_df = con2.execute(
    "SELECT DISTINCT entity_id, symbol FROM isin_lineage"
).fetchdf()
con2.close()
sym_map = dict(zip(sym_df["entity_id"], sym_df["symbol"]))
contrib_df["symbol"] = contrib_df["entity_id"].map(sym_map)
print("\nTop 10 with symbols:")
print(contrib_df.head(10)[["entity_id", "symbol", "contribution", "share_of_total_growth"]].to_string(index=False))

contrib_df.to_csv(ROOT / "data" / "holdout_study1_contribution_concentration.csv", index=False)
print(f"\nSaved to data/holdout_study1_contribution_concentration.csv")
