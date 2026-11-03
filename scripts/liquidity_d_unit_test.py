"""Synthetic unit tests for src/liquidity/d.py's own new logic
(ascending-lows/highs detection, both directions, both n_required
values) -- pure-function scenarios, no DB access, run before any
real-data hand-trace, same discipline as liquidity_c_unit_test.py's own
synthetic test.

Every sequence below was constructed AND VERIFIED by running the real
function against it before being written down here as an assertion --
not hand-traced and trusted blind. liquidity_c_unit_test.py's own first
draft had exactly this failure mode (test data that didn't actually
distinguish the state it claimed to), caught before any real-data trace;
this file was built the other way around from the start specifically to
avoid repeating it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from liquidity.d import find_ascending_lows_long, find_ascending_highs_short

FAILS = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(label)
    print(f"[{status}] {label}")


def candles(lows_highs):
    """lows_highs: list of (low, high) tuples, one per 5-min candle;
    index 0 = sweep candle (sweep_idx=0 in every test here)."""
    rows = []
    t0 = pd.Timestamp("2024-06-10 09:45:00")
    for i, (lo, hi) in enumerate(lows_highs):
        mid = (lo + hi) / 2
        rows.append({"ts": t0 + pd.Timedelta(minutes=5 * i), "open": mid, "high": hi, "low": lo, "close": mid})
    return pd.DataFrame(rows)


ZONE = 100.0
SWEEP_LOW = 90.0
SWEEP_LOW_WIDE = 80.0  # used only where the test needs headroom below zone for an above-zone local low
SWEEP_HIGH = 110.0

# ---------------------------------------------------------------------
# LONG, n_required=2: clean ascending pair
# ---------------------------------------------------------------------
r = find_ascending_lows_long(
    candles([(90, 92), (99, 101), (97, 99), (99, 101), (98.5, 100.5), (99.5, 101.5)]),
    sweep_idx=0, sweep_low=SWEEP_LOW, zone_price=ZONE, n_required=2,
)
check("2LOW: clean ascending pair confirms, count=2", r["status"] == "PATTERN_CONFIRMED" and r["count"] == 2)
check("2LOW: confirms at the correct candle (idx5)", r.get("confirm_idx") == 5)

# ---------------------------------------------------------------------
# LONG, n_required=2: a local low ABOVE the zone is ignored entirely --
# does not count, does not reset the running sequence
# ---------------------------------------------------------------------
r = find_ascending_lows_long(
    candles([
        (80, 82), (95, 97), (90, 92), (95, 97), (112, 114), (108, 110), (115, 117), (96, 98), (98, 100),
    ]),
    sweep_idx=0, sweep_low=SWEEP_LOW_WIDE, zone_price=ZONE, n_required=2,
)
check("2LOW: above-zone local low (108, between the two qualifying lows) ignored, not a reset",
      r["status"] == "PATTERN_CONFIRMED" and r["count"] == 2 and r["confirm_idx"] == 8)
check("2LOW: final qualifying low correctly recorded as 96, not reset by the ignored 108",
      r.get("final_low") == 96.0)

# ---------------------------------------------------------------------
# LONG, n_required=2: a non-ascending qualifying low RESETS the running
# count (becomes the new baseline) rather than killing the pattern
# ---------------------------------------------------------------------
r = find_ascending_lows_long(
    candles([(90, 92), (96, 98), (94, 96), (97, 99), (92, 94), (95, 97), (93, 95), (96, 98)]),
    sweep_idx=0, sweep_low=SWEEP_LOW, zone_price=ZONE, n_required=2,
)
check("2LOW: a lower (non-ascending) qualifying low resets the count instead of breaking the pattern",
      r["status"] == "PATTERN_CONFIRMED" and r["count"] == 2 and r["confirm_idx"] == 7)
check("2LOW: the confirming low (93) is compared against the RESET baseline (92), not the discarded one (94)",
      r.get("final_low") == 93.0)

# ---------------------------------------------------------------------
# LONG: PATTERN_BROKEN -- a new low below SWEEP_LOW ends the setup
# immediately, regardless of local-low state
# ---------------------------------------------------------------------
r = find_ascending_lows_long(
    candles([(90, 92), (97, 99), (99, 101), (85, 87)]),
    sweep_idx=0, sweep_low=SWEEP_LOW, zone_price=ZONE, n_required=2,
)
check("LONG: a new low below SWEEP_LOW breaks the pattern at the breaching candle",
      r["status"] == "PATTERN_BROKEN" and r["broken_idx"] == 3)

# ---------------------------------------------------------------------
# LONG: PATTERN_INCOMPLETE -- only one qualifying low ever confirms
# before the day's candles run out
# ---------------------------------------------------------------------
r = find_ascending_lows_long(
    candles([(90, 92), (99, 101), (97, 99), (99, 101)]),
    sweep_idx=0, sweep_low=SWEEP_LOW, zone_price=ZONE, n_required=2,
)
check("LONG: day ends with count < n_required -> PATTERN_INCOMPLETE",
      r["status"] == "PATTERN_INCOMPLETE" and r["count"] == 1)

# ---------------------------------------------------------------------
# LONG, n_required=3: three strictly-ascending qualifying lows required
# ---------------------------------------------------------------------
r = find_ascending_lows_long(
    candles([
        (90, 92), (99, 101), (97, 99), (99, 101), (98.5, 100.5), (99.5, 101.5), (99, 101), (100.5, 102.5),
    ]),
    sweep_idx=0, sweep_low=SWEEP_LOW, zone_price=ZONE, n_required=3,
)
check("3LOW: three ascending qualifying lows confirm",
      r["status"] == "PATTERN_CONFIRMED" and r["count"] == 3 and r["confirm_idx"] == 7)

# ---------------------------------------------------------------------
# SHORT mirror: exact mirror of the 2LOW clean-confirm case
# ---------------------------------------------------------------------
r = find_ascending_highs_short(
    candles([(108, 110), (99, 101), (101, 103), (99, 101), (99.5, 101.5), (98.5, 100.5)]),
    sweep_idx=0, sweep_high=SWEEP_HIGH, zone_price=ZONE, n_required=2,
)
check("SHORT 2-equiv: two descending (toward zone) qualifying highs confirm",
      r["status"] == "PATTERN_CONFIRMED" and r["count"] == 2 and r["confirm_idx"] == 5)

# ---------------------------------------------------------------------
# SHORT: PATTERN_BROKEN -- a new high above SWEEP_HIGH ends the setup
# ---------------------------------------------------------------------
r = find_ascending_highs_short(
    candles([(108, 110), (99, 101), (101, 103), (99, 101), (109, 112)]),
    sweep_idx=0, sweep_high=SWEEP_HIGH, zone_price=ZONE, n_required=2,
)
check("SHORT: a new high above SWEEP_HIGH breaks the pattern",
      r["status"] == "PATTERN_BROKEN" and r["broken_idx"] == 4)

# ---------------------------------------------------------------------
# SHORT: PATTERN_INCOMPLETE -- only one qualifying high ever confirms
# ---------------------------------------------------------------------
r = find_ascending_highs_short(
    candles([(108, 110), (99, 101), (101, 103), (99, 101)]),
    sweep_idx=0, sweep_high=SWEEP_HIGH, zone_price=ZONE, n_required=2,
)
check("SHORT: day ends with count < n_required -> PATTERN_INCOMPLETE",
      r["status"] == "PATTERN_INCOMPLETE" and r["count"] == 1)

print()
if FAILS:
    print(f"{len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("ALL PASSED")
