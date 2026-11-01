"""Synthetic unit tests for src/liquidity/c.py's own new logic (retest
detection, both directions) -- pure-function scenarios, no DB access,
run before any real-data hand-trace, same discipline as liquidity_a_
unit_test.py's own synthetic test."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from liquidity.c import find_retest_long, find_retest_short

FAILS = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(label)
    print(f"[{status}] {label}")


def bars(rows):
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"])
    return df


DAY = "2024-06-10"
ZONE = 100.0
ATR = 10.0  # tol = 0.2*10 = 2.0 -> "within tol of zone" band is [98.0, 102.0]
SWEEP_LOW = 95.0   # long: the original sweep's own final extreme
SWEEP_HIGH = 105.0  # short mirror

# candles5 passed to find_retest_long/short includes the reclaim candle
# at index 0 (must match the "reclaim_idx" argument); scanning starts at
# index 1 (strictly after reclaim_idx).

# ---------------------------------------------------------------------
# LONG side -- after reclaim, price is above the zone (100) and must
# pull back DOWN toward it, then close back above it again.
# ---------------------------------------------------------------------

# Scenario 1: two-candle retest -- pullback candle touches but closes
# BELOW zone (not yet); a later candle closes back ABOVE zone (RETEST).
b1 = bars([
    (f"{DAY} 09:50", 101, 103, 101, 103),      # reclaim candle (idx 0), well above zone
    (f"{DAY} 09:55", 103, 103, 99.0, 99.5),    # low 99 within tol (|99-100|=1<=2) -> touched; close 99.5 < zone: not yet
    (f"{DAY} 10:00", 99.5, 101, 99.2, 100.5),  # low 99.2 still within tol; close 100.5 > zone -> RETEST here (idx 2)
])
r1 = find_retest_long(b1, 0, SWEEP_LOW, ZONE, ATR)
check("long: two-candle retest confirms at the close-above candle (idx 2)",
      r1["status"] == "RETEST" and r1["idx"] == 2)

# Scenario 2: same-candle retest -- low dips within tol AND closes above
# zone in the SAME candle (a sharp V).
b2 = bars([
    (f"{DAY} 09:50", 101, 103, 101, 103),      # reclaim candle (idx 0)
    (f"{DAY} 09:55", 103, 103, 99.0, 100.5),   # low 99 within tol (touched) AND close 100.5 > zone -> RETEST, idx 1
])
r2 = find_retest_long(b2, 0, SWEEP_LOW, ZONE, ATR)
check("long: retest can confirm on a single candle (touch+close together)",
      r2["status"] == "RETEST" and r2["idx"] == 1)

# Scenario 3: RETEST_FAILED -- a candle's low breaches the original
# SWEEP_LOW before any valid retest completes.
b3 = bars([
    (f"{DAY} 09:50", 101, 103, 101, 103),      # reclaim candle (idx 0)
    (f"{DAY} 09:55", 103, 103, 99.0, 99.5),    # touched (low 99 within tol), close 99.5 < zone: not yet
    (f"{DAY} 10:00", 99.5, 100, 94.0, 94.5),   # low 94 < SWEEP_LOW=95 -> RETEST_FAILED, idx 2
])
r3 = find_retest_long(b3, 0, SWEEP_LOW, ZONE, ATR)
check("long: breach of the original sweep low -> RETEST_FAILED",
      r3["status"] == "RETEST_FAILED" and r3["breach_idx"] == 2)

# Scenario 4: NO_RETEST -- price never comes back within 0.2xATR of the
# zone at all (stays well above it all day).
b4 = bars([
    (f"{DAY} 09:50", 101, 103, 101, 103),
    (f"{DAY} 09:55", 103, 106, 103, 105),
    (f"{DAY} 10:00", 105, 107, 104, 106),
])
r4 = find_retest_long(b4, 0, SWEEP_LOW, ZONE, ATR)
check("long: price never returns to the zone -> NO_RETEST", r4["status"] == "NO_RETEST")

# Scenario 5: NO_RETEST -- touches the zone but never closes back above it.
b5 = bars([
    (f"{DAY} 09:50", 101, 103, 101, 103),
    (f"{DAY} 09:55", 103, 103, 99.0, 98.5),    # touch, close 98.5 stays below zone
    (f"{DAY} 10:00", 98.5, 99, 97.0, 97.5),    # still below zone; low 97 > SWEEP_LOW=95 (no breach)
])
r5 = find_retest_long(b5, 0, SWEEP_LOW, ZONE, ATR)
check("long: touches but never closes back above zone -> NO_RETEST", r5["status"] == "NO_RETEST")


# ---------------------------------------------------------------------
# SHORT side -- exact mirror: after reclaim, price is below the zone and
# must pull back UP toward it, then close back below it again.
# ---------------------------------------------------------------------

b6 = bars([
    (f"{DAY} 09:50", 99, 99, 97, 97),          # reclaim candle (idx 0), well below zone
    (f"{DAY} 09:55", 97, 101.0, 97, 100.5),    # high 101 within tol (|101-100|=1<=2) -> touched; close 100.5 > zone: not yet
    (f"{DAY} 10:00", 100.5, 100.8, 99, 99.5),  # high 100.8 still within tol; close 99.5 < zone -> RETEST, idx 2
])
r6 = find_retest_short(b6, 0, SWEEP_HIGH, ZONE, ATR)
check("short: two-candle retest confirms at the close-below candle (idx 2)",
      r6["status"] == "RETEST" and r6["idx"] == 2)

# Same-candle short retest.
b6b = bars([
    (f"{DAY} 09:50", 99, 99, 97, 97),
    (f"{DAY} 09:55", 97, 101.0, 97, 99.5),     # high 101 within tol (touched) AND close 99.5 < zone -> RETEST, idx 1
])
r6b = find_retest_short(b6b, 0, SWEEP_HIGH, ZONE, ATR)
check("short: retest can confirm on a single candle (touch+close together)",
      r6b["status"] == "RETEST" and r6b["idx"] == 1)

b7 = bars([
    (f"{DAY} 09:50", 99, 99, 97, 97),
    (f"{DAY} 09:55", 97, 106.0, 97, 97.5),     # high 106 > SWEEP_HIGH=105 -> RETEST_FAILED
])
r7 = find_retest_short(b7, 0, SWEEP_HIGH, ZONE, ATR)
check("short: breach of the original sweep high -> RETEST_FAILED",
      r7["status"] == "RETEST_FAILED" and r7["breach_idx"] == 1)

b8 = bars([
    (f"{DAY} 09:50", 99, 99, 97, 97),
    (f"{DAY} 09:55", 96, 97, 94, 95),
    (f"{DAY} 10:00", 95, 96, 93, 94),
])
r8 = find_retest_short(b8, 0, SWEEP_HIGH, ZONE, ATR)
check("short: price never returns to the zone -> NO_RETEST", r8["status"] == "NO_RETEST")

print()
if FAILS:
    print(f"=== {len(FAILS)} FAILURE(S): {FAILS} ===")
    sys.exit(1)
print("=== ALL SCENARIOS PASS ===")
