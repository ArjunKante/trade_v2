"""Synthetic unit tests for src/liquidity/a.py's own new logic (confluence
clustering, scaled-exit resolution) -- pure-function scenarios with no DB
access, run BEFORE any real-data hand-trace, same discipline as poc.v5's
own 8-scenario synthetic test for resolve_multiday_exit_from_bars."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from liquidity.a import find_confluence_zone, resolve_scaled_exit_a

FAILS = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(label)
    print(f"[{status}] {label}")


# ---------------------------------------------------------------------
# Confluence zone
# ---------------------------------------------------------------------

# No cluster: all three levels far apart (ATR=1, tolerance=0.5)
z = find_confluence_zone(lo_3m_raw=100.0, lo_1w_raw=110.0, lo_1d_raw=120.0, atr_raw=1.0, prev_close_raw=125.0)
check("no_confluence when all three are far apart", z["status"] == "NO_CONFLUENCE")

# Pair clusters (1w, 1d close; 3m far)
z = find_confluence_zone(lo_3m_raw=100.0, lo_1w_raw=110.0, lo_1d_raw=110.3, atr_raw=1.0, prev_close_raw=125.0)
check("pair cluster (1w,1d)", z["status"] == "CONFLUENCE" and set(z["members"]) == {"1w", "1d"})
check("pair cluster zone_price is the mean", abs(z["zone_price"] - 110.15) < 1e-9)
check("pair cluster not flagged multi_cluster", z["multi_cluster"] is False)

# All three cluster (mutually within tolerance)
z = find_confluence_zone(lo_3m_raw=100.0, lo_1w_raw=100.2, lo_1d_raw=100.4, atr_raw=1.0, prev_close_raw=125.0)
check("all three cluster -> one zone of 3", z["status"] == "CONFLUENCE" and set(z["members"]) == {"3m", "1w", "1d"})
check("all-three zone_price is the mean of 3", abs(z["zone_price"] - 100.2) < 1e-9)

# Chain case: 3m close to 1w, 1w close to 1d, but 3m NOT close to 1d ->
# single connected component of size 3 via the shared 1w node
z = find_confluence_zone(lo_3m_raw=100.0, lo_1w_raw=100.4, lo_1d_raw=100.8, atr_raw=1.0, prev_close_raw=125.0)
check("chain via shared node forms one component of 3",
      z["status"] == "CONFLUENCE" and set(z["members"]) == {"3m", "1w", "1d"})


# ---------------------------------------------------------------------
# Scaled exit resolution -- synthetic 1-minute bars
# ---------------------------------------------------------------------

def bars(rows):
    """rows: list of (ts_str, open, high, low, close)."""
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def candles5_from_bars1(bars1):
    """Minimal 5-min aggregation good enough for the TIME_EXIT lookup --
    just needs a row at (or before) 15:15 with the right close."""
    return bars1.rename(columns={"ts": "ts"})


DAY = "2024-06-10"
ENTRY = 100.0
STOP = 95.0          # R = 5
HALF_T = 107.5        # entry + 1.5R
FULL_T = 115.0        # entry + 3.0R
QTY = 10


def ts(hhmm):
    return pd.Timestamp(f"{DAY} {hhmm}")


# Scenario 1: full 3R target, two separate bars (half then full)
b1 = bars([
    (f"{DAY} 09:46", 100, 101, 99, 100),
    (f"{DAY} 10:00", 101, 108, 100, 107),   # half target hit here (high>=107.5? no -- fix below)
])
# build more carefully: bar A hits HALF_T, later bar B hits FULL_T, no stop touch ever
b1 = bars([
    (f"{DAY} 09:46", 100, 102, 99.5, 101),
    (f"{DAY} 10:30", 101, 108, 100, 106),    # high 108 >= 107.5 -> half target this bar
    (f"{DAY} 11:30", 106, 116, 105, 110),    # high 116 >= 115 -> full target this bar
])
res = resolve_scaled_exit_a(b1, candles5_from_bars1(b1), ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 1: full 3R target reached, half+full across two bars",
      res["outcome"] == "FULL_EXIT" and res["half_exit_happened"] and len(res["legs"]) == 2
      and res["legs"][0]["price"] == HALF_T and res["legs"][1]["price"] == FULL_T)

# Scenario 2: stop hit before half exit ever happens
b2 = bars([
    (f"{DAY} 09:46", 100, 101, 99, 100),
    (f"{DAY} 10:00", 100, 101, 94, 95),      # low 94 <= stop 95 -- stop hit, no half exit
])
res = resolve_scaled_exit_a(b2, candles5_from_bars1(b2), ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 2: stop before half exit", res["outcome"] == "STOP_NO_HALF" and not res["half_exit_happened"]
      and len(res["legs"]) == 1 and res["legs"][0]["qty"] == QTY)

# Scenario 3: half exit happens, then remainder stops out
b3 = bars([
    (f"{DAY} 09:46", 100, 102, 99.5, 101),
    (f"{DAY} 10:30", 101, 108, 100, 106),     # half target hit
    (f"{DAY} 11:30", 106, 107, 94, 95),       # remainder: low <= stop -> stop
])
res = resolve_scaled_exit_a(b3, candles5_from_bars1(b3), ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 3: half exit then stop on remainder",
      res["outcome"] == "HALF_THEN_STOP" and res["half_exit_happened"]
      and len(res["legs"]) == 2 and res["legs"][1]["price"] == STOP)

# Scenario 4: 15:15 time exit with the second half still open (half hit, remainder never resolves)
b4_rows = [(f"{DAY} 09:46", 100, 102, 99.5, 101), (f"{DAY} 10:30", 101, 108, 100, 106)]
# fill out the rest of the day flat (no stop/target hit), ending with a 15:15 bar
for hh in range(11, 16):
    b4_rows.append((f"{DAY} {hh:02d}:00", 103, 104, 102, 103))
b4_rows.append((f"{DAY} 15:15", 103, 104, 102, 103.4))
b4 = bars(b4_rows)
res = resolve_scaled_exit_a(b4, candles5_from_bars1(b4), ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 4: half exit then 15:15 time exit on remainder",
      res["outcome"] == "HALF_THEN_TIME_EXIT" and res["half_exit_happened"]
      and len(res["legs"]) == 2 and res["legs"][1]["kind"] == "TIME_EXIT"
      and res["legs"][1]["price"] == 103.4)

# Scenario 5: NO_CONFLUENCE is exercised at the find_confluence_zone level
# already above; nothing further needed for resolution.

# Scenario 6: qty == 1 path, full target
b6 = bars([
    (f"{DAY} 09:46", 100, 102, 99.5, 101),
    (f"{DAY} 11:30", 106, 116, 100, 110),   # straight to full target, no half possible
])
res = resolve_scaled_exit_a(b6, candles5_from_bars1(b6), ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, 1)
check("scenario 6: qty=1 full target", res["outcome"] == "TARGET_QTY1" and res["qty1_path"]
      and not res["half_exit_happened"] and len(res["legs"]) == 1 and res["legs"][0]["qty"] == 1)

# Scenario 7: same-bar half+full (price jumps through both in one bar)
b7 = bars([
    (f"{DAY} 09:46", 100, 102, 99.5, 101),
    (f"{DAY} 10:30", 101, 120, 100, 118),    # high 120 clears both 107.5 and 115 in one bar
])
res = resolve_scaled_exit_a(b7, candles5_from_bars1(b7), ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 7: same-bar half-then-full", res["outcome"] == "FULL_EXIT_SAME_BAR"
      and res["half_exit_happened"] and res["legs"][0]["ts"] == res["legs"][1]["ts"])

# Scenario 8: nothing hit at all -> full position time exit
b8_rows = [(f"{DAY} 09:46", 100, 101, 99.5, 100)]
for hh in range(10, 16):
    b8_rows.append((f"{DAY} {hh:02d}:00", 100, 101, 99.6, 100.2))
b8_rows.append((f"{DAY} 15:15", 100, 101, 99.6, 100.5))
b8 = bars(b8_rows)
res = resolve_scaled_exit_a(b8, candles5_from_bars1(b8), ts("09:46"), ENTRY, STOP, HALF_T, FULL_T, QTY)
check("scenario 8: nothing hit -> full position time exit",
      res["outcome"] == "TIME_EXIT_FULL" and not res["half_exit_happened"]
      and len(res["legs"]) == 1 and res["legs"][0]["qty"] == QTY and res["legs"][0]["price"] == 100.5)

print()
if FAILS:
    print(f"=== {len(FAILS)} FAILURE(S): {FAILS} ===")
    sys.exit(1)
print("=== ALL SCENARIOS PASS ===")
