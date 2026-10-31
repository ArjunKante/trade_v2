"""Synthetic unit tests for src/portfolio/'s own new logic -- pure-
function scenarios, no DB access, run before any real-data backtest,
same discipline as liquidity_a_unit_test.py's own synthetic test."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from portfolio.construction import select_portfolio
from portfolio.costs import turnover_and_cost

FAILS = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(label)
    print(f"[{status}] {label}")


# ---------------------------------------------------------------------
# select_portfolio
# ---------------------------------------------------------------------

pool = pd.DataFrame({"entity_id": [f"E{i}" for i in range(1, 11)], "value": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]})

sel = select_portfolio(pool, 3, "equal")
check("top-3 fixed count selects the 3 highest values",
      set(sel["entity_id"]) == {"E1", "E2", "E3"} and len(sel) == 3)
check("equal weight sums to 1", abs(sel["weight"].sum() - 1.0) < 1e-9)
check("equal weight is uniform across the 3 selected names", (sel["weight"] == sel["weight"].iloc[0]).all())

sel_rank = select_portfolio(pool, 3, "rank")
check("rank weight sums to 1", abs(sel_rank["weight"].sum() - 1.0) < 1e-9)
w = dict(zip(sel_rank["entity_id"], sel_rank["weight"]))
check("rank weight: strongest momentum (E1) gets the largest weight (3/6)", abs(w["E1"] - 0.5) < 1e-9)
check("rank weight: weakest selected (E3) gets the smallest weight (1/6)", abs(w["E3"] - (1 / 6)) < 1e-9)
check("rank weight: E1 > E2 > E3", w["E1"] > w["E2"] > w["E3"])

pool_big = pd.DataFrame({"entity_id": [f"E{i}" for i in range(1, 101)], "value": list(range(100, 0, -1))})
sel_decile = select_portfolio(pool_big, "decile", "equal")
check("decile selects ~10% of a 100-name pool", 9 <= len(sel_decile) <= 11)

empty = select_portfolio(pd.DataFrame(columns=["entity_id", "value"]), 10, "equal")
check("empty pool returns empty selection, not padded", empty.empty)

try:
    select_portfolio(pool, 3, "bogus")
    check("unknown weighting raises", False)
except ValueError:
    check("unknown weighting raises", True)


# ---------------------------------------------------------------------
# turnover_and_cost -- must reduce EXACTLY to run_holdout_study1.py's own
# turnover_frac = len(entered)/len(mom_set) formula at equal weight
# ---------------------------------------------------------------------

# One-name swap at N=5, equal weight: E1..E4 stay, E5 exits, E6 enters.
N = 5
prev = {f"E{i}": 1 / N for i in range(1, N + 1)}
new = {f"E{i}": 1 / N for i in range(1, N)}
new["E6"] = 1 / N
tercile = {f"E{i}": "high_liq" for i in range(1, 7)}

turnover, cost = turnover_and_cost(prev, new, tercile)
expected_turnover_frac = 1 / N  # Study 1's own turnover_frac for a 1-name swap out of N
check("one-name swap, equal weight: turnover matches Study 1's own turnover_frac exactly",
      abs(turnover - expected_turnover_frac) < 1e-9)
expected_cost = expected_turnover_frac * (23.0 / 10000.0)  # Study 1: turnover_frac * avg_cost (entering tercile only)
check("one-name swap, equal weight: cost matches Study 1's own formula exactly",
      abs(cost - expected_cost) < 1e-9)

# No change at all: turnover and cost both zero.
t2, c2 = turnover_and_cost(prev, dict(prev), tercile)
check("no change: turnover=0, cost=0", t2 == 0.0 and c2 == 0.0)

# First rebalance (prev empty): full turnover, cost on every entering name's own tercile.
tercile_mixed = {"E1": "high_liq", "E2": "mid_liq"}
t3, c3 = turnover_and_cost({}, {"E1": 0.5, "E2": 0.5}, tercile_mixed)
# A first-ever buy-in has only ONE leg (entering; there is no prior
# portfolio to exit), so under the standard one-way turnover definition
# (0.5 * sum|delta|) it is correctly 0.5, not 1.0 -- unlike a STEADY-
# STATE complete replacement (old names exiting AND new names entering),
# which has two legs and correctly gives 1.0 (verified separately
# below). Cost is unaffected either way: it is charged directly per
# entering name's own full weight at its own tercile rate, matching
# Study 1's own effective first-period cost exactly (checked next).
check("first rebalance (one leg only): turnover = 0.5", abs(t3 - 0.5) < 1e-9)
check("first rebalance: cost uses each entering name's own tercile",
      abs(c3 - (0.5 * 23.0 / 10000.0 + 0.5 * 32.5 / 10000.0)) < 1e-9)

# Weight increase on a RETAINED name (rank-weight case) still charged, weight
# decrease on another retained name is NOT separately charged (matches the
# stated "entering flow only" convention).
prev_w = {"E1": 0.6, "E2": 0.4}
new_w = {"E1": 0.4, "E2": 0.6}
t4, c4 = turnover_and_cost(prev_w, new_w, {"E1": "high_liq", "E2": "mid_liq"})
check("retained-name reweight: turnover = 0.2 (half of total |delta|=0.4)", abs(t4 - 0.2) < 1e-9)
check("retained-name reweight: cost charged only on E2's own increase (0.2 @ mid_liq)",
      abs(c4 - (0.2 * 32.5 / 10000.0)) < 1e-9)

# Steady-state COMPLETE replacement (every name exits, every name is
# new) genuinely has two legs and should give turnover = 1.0.
prev_full = {f"E{i}": 1 / 5 for i in range(1, 6)}
new_full = {f"F{i}": 1 / 5 for i in range(1, 6)}
tercile_full = {**{f"E{i}": "high_liq" for i in range(1, 6)}, **{f"F{i}": "high_liq" for i in range(1, 6)}}
t5, _ = turnover_and_cost(prev_full, new_full, tercile_full)
check("steady-state complete replacement (two legs): turnover = 1.0", abs(t5 - 1.0) < 1e-9)

print()
if FAILS:
    print(f"=== {len(FAILS)} FAILURE(S): {FAILS} ===")
    sys.exit(1)
print("=== ALL SCENARIOS PASS ===")
