"""Synthetic unit tests for src/liquidity/b.py's own new logic (HIGH-side
confluence clustering, short-side scaled-exit resolution) -- pure-function
scenarios, no DB access, run BEFORE any real-data hand-trace, same
discipline as liquidity_a_unit_test.py's own 14-scenario synthetic test."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from liquidity.b import find_confluence_zone_b, resolve_scaled_exit_b

FAILS = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(label)
    print(f"[{status}] {label}")


# ---------------------------------------------------------------------
# Confluence zone (HIGH levels)
# ---------------------------------------------------------------------

# No cluster: all three far apart (ATR=1, tolerance=0.5)
z = find_confluence_zone_b(hi_3m_raw=120.0, hi_1w_raw=110.0, hi_1d_raw=100.0, atr_raw=1.0, prev_close_raw=95.0)
check("no_confluence when all three are far apart", z["status"] == "NO_CONFLUENCE")

# Pair clusters (1w, 1d close; 3m far)
z = find_confluence_zone_b(hi_3m_raw=130.0, hi_1w_raw=110.3, hi_1d_raw=110.0, atr_raw=1.0, prev_close_raw=95.0)
check("pair cluster (1w,1d)", z["status"] == "CONFLUENCE" and set(z["members"]) == {"1w", "1d"})
check("pair cluster zone_price is the mean", abs(z["zone_price"] - 110.15) < 1e-9)
check("pair cluster not flagged multi_cluster", z["multi_cluster"] is False)

# All three cluster (mutually within tolerance)
z = find_confluence_zone_b(hi_3m_raw=100.4, hi_1w_raw=100.2, hi_1d_raw=100.0, atr_raw=1.0, prev_close_raw=95.0)
check("all three cluster -> one zone of 3", z["status"] == "CONFLUENCE" and set(z["members"]) == {"3m", "1w", "1d"})
check("all-three zone_price is the mean of 3", abs(z["zone_price"] - 100.2) < 1e-9)

# Chain case: 3m close to 1w, 1w close to 1d, but 3m NOT close to 1d ->
# single connected component of size 3 via the shared 1w node
z = find_confluence_zone_b(hi_3m_raw=100.8, hi_1w_raw=100.4, hi_1d_raw=100.0, atr_raw=1.0, prev_close_raw=95.0)
check("chain via shared node forms one component of 3",
      z["status"] == "CONFLUENCE" and set(z["members"]) == {"3m", "1w", "1d"})

# Tie-break direction check: two disjoint-looking groups is structurally
# unreachable with 3 nodes (same proof as Study A), so multi_cluster is
# never exercised here either -- not separately tested, per the prereg's
# own stated proof.


# ---------------------------------------------------------------------
# Scaled exit resolution -- synthetic 1-minute bars, SHORT geometry:
# stop ABOVE entry, targets BELOW entry
# ---------------------------------------------------------------------

def bars(rows):
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"])
    return df


DAY = "2024-06-10"
ENTRY = 100.0
STOP = 105.0          # R = 5 (stop ABOVE entry)
HALF_T = 92.5         # entry - 1.5R
FULL_T = 85.0         # entry - 3.0R
QTY = 10


def ts(hhmm):
    return pd.Timestamp(f"{DAY} {hhmm}")


# Scenario 1: full 3R target, two separate bars (half then full)
b1 = bars([
    (f"{DAY} 09:46", 100, 100.5, 99, 100),
    (f"{DAY} 10:30", 100, 101, 92, 94),      # low 92 <= 92.5 -> half target this bar
    (f"{DAY} 11:30", 94, 95, 84, 90),        # low 84 <= 85 -> full target this bar
])
res = resolve_scaled_exit_b(b1, b1, ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 1: full 3R target reached, half+full across two bars",
      res["outcome"] == "FULL_EXIT" and res["half_exit_happened"] and len(res["legs"]) == 2
      and res["legs"][0]["price"] == HALF_T and res["legs"][1]["price"] == FULL_T)

# Scenario 2: stop hit before half exit ever happens (price rises through stop)
b2 = bars([
    (f"{DAY} 09:46", 100, 101, 99, 100),
    (f"{DAY} 10:00", 100, 106, 99, 105),     # high 106 >= stop 105 -- stop hit, no half exit
])
res = resolve_scaled_exit_b(b2, b2, ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 2: stop before half exit", res["outcome"] == "STOP_NO_HALF" and not res["half_exit_happened"]
      and len(res["legs"]) == 1 and res["legs"][0]["qty"] == QTY)

# Scenario 3: half exit happens, then remainder stops out (price reverses back up)
b3 = bars([
    (f"{DAY} 09:46", 100, 100.5, 99, 100),
    (f"{DAY} 10:30", 100, 101, 92, 94),       # half target hit (low 92 <= 92.5)
    (f"{DAY} 11:30", 94, 106, 93, 105),       # remainder: high >= stop -> stop
])
res = resolve_scaled_exit_b(b3, b3, ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 3: half exit then stop on remainder",
      res["outcome"] == "HALF_THEN_STOP" and res["half_exit_happened"]
      and len(res["legs"]) == 2 and res["legs"][1]["price"] == STOP)

# Scenario 4: 15:15 time exit with the second half still open
b4_rows = [(f"{DAY} 09:46", 100, 100.5, 99, 100), (f"{DAY} 10:30", 100, 101, 92, 94)]
for hh in range(11, 16):
    b4_rows.append((f"{DAY} {hh:02d}:00", 97, 98, 96, 97))
b4_rows.append((f"{DAY} 15:15", 97, 98, 96, 96.6))
b4 = bars(b4_rows)
res = resolve_scaled_exit_b(b4, b4, ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 4: half exit then 15:15 time exit on remainder",
      res["outcome"] == "HALF_THEN_TIME_EXIT" and res["half_exit_happened"]
      and len(res["legs"]) == 2 and res["legs"][1]["kind"] == "TIME_EXIT"
      and res["legs"][1]["price"] == 96.6)

# Scenario 6: qty == 1 path, full target
b6 = bars([
    (f"{DAY} 09:46", 100, 100.5, 99, 100),
    (f"{DAY} 11:30", 94, 95, 84, 90),   # straight to full target, no half possible
])
res = resolve_scaled_exit_b(b6, b6, ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, 1)
check("scenario 6: qty=1 full target", res["outcome"] == "TARGET_QTY1" and res["qty1_path"]
      and not res["half_exit_happened"] and len(res["legs"]) == 1 and res["legs"][0]["qty"] == 1)

# Scenario 7: same-bar half+full (price drops through both in one bar)
b7 = bars([
    (f"{DAY} 09:46", 100, 100.5, 99, 100),
    (f"{DAY} 10:30", 100, 101, 80, 82),    # low 80 clears both 92.5 and 85 in one bar
])
res = resolve_scaled_exit_b(b7, b7, ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 7: same-bar half-then-full", res["outcome"] == "FULL_EXIT_SAME_BAR"
      and res["half_exit_happened"] and res["legs"][0]["ts"] == res["legs"][1]["ts"])

# Scenario 8: nothing hit at all -> full position time exit
b8_rows = [(f"{DAY} 09:46", 100, 100.5, 99.4, 100)]
for hh in range(10, 16):
    b8_rows.append((f"{DAY} {hh:02d}:00", 99.9, 100.4, 99.3, 99.8))
b8_rows.append((f"{DAY} 15:15", 99.9, 100.4, 99.3, 99.5))
b8 = bars(b8_rows)
res = resolve_scaled_exit_b(b8, b8, ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 8: nothing hit -> full position time exit",
      res["outcome"] == "TIME_EXIT_FULL" and not res["half_exit_happened"]
      and len(res["legs"]) == 1 and res["legs"][0]["qty"] == QTY and res["legs"][0]["price"] == 99.5)

print()
if FAILS:
    print(f"=== {len(FAILS)} FAILURE(S): {FAILS} ===")
    sys.exit(1)
print("=== ALL SCENARIOS PASS ===")
