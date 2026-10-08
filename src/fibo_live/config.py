"""Frozen constants for the live paper-trading system. Changing any rule
constant here (universe size, swing/ATR/zone parameters -- all actually
defined in src/fibo/indicators.py and imported, never duplicated here) is
exactly the kind of mid-run rule change the DO-NOT list forbids. The only
thing that is allowed to change is VERSION, and only by starting a new
version with a new, empty log -- never by rewriting this one's.

VERSIONING: PAPER_VERSION names the current rule version's log directory
(data/fibo_live/<version>/). A rule change is a new PAPER_VERSION string,
which starts a brand new, empty events log -- the old version's log is
left exactly as it is, forever, as the evidence for that version's run.
Do not bump this to reinterpret old data; bump it only when a rule
actually changes and a fresh forward test under the new rule is wanted.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"  # unused here (live path never touches the historical archive)
RAW_PRICES_DIR = ROOT / "data" / "raw" / "prices"

PAPER_VERSION = "v1"
LIVE_DIR = ROOT / "data" / "fibo_live" / PAPER_VERSION
EVENTS_LOG = LIVE_DIR / "events.jsonl"

TOP_N = 200  # same top-200 universe as the sealed test (PREREGISTRATION_FIBO.md Section 1 amendment)

# a corporate action with ex_date inside this many calendar days of the
# evening run is treated as "scale factor unknown for tomorrow" -- NOT a
# precise trading-calendar lookup (deliberately conservative: covers a
# weekend plus up to 2 holidays so the actual next trading day is never
# missed), see src/fibo_live/watchlist.py
EX_DATE_LOOKAHEAD_DAYS = 5

# the evaluation gate (DO-NOT list: never show performance before 100
# trades) and the one number the gate compares against once it opens --
# the amended re-test's own mean net R, PREREGISTRATION_FIBO.md Section 9d /
# FIBO_FINDINGS.md Section 9. Cited, not re-derived: if that figure is ever
# revised, update it here to match, never the other way around.
EVAL_MIN_TRADES = 100
SEALED_AMENDED_MEAN_NET_R = 0.3673
