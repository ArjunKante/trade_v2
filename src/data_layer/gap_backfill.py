"""Automated backfill policy for BUGS.md Bug #30's structural fix: decides
which missing trading days `price_gap_detector` finds get filled
automatically, and which require a human -- then rebuilds every table
this project currently materializes from `prices_eod` and re-runs the
margin tripwire, so a backfill can never again leave the appearance of
health (raw data present) without the substance (derived tables current).

TWO INDEPENDENT REASONS stop a gap from auto-filling -- either one alone
is enough (BUGS.md Bug #30's closing update, user instructions
2026-11-18):

  1. AGE: older than RECENT_GAP_MAX_AGE_DAYS (30, "~30 days" per that
     instruction). An old, previously-undiscovered gap is not an
     ordinary operational miss -- it has been silently affecting
     computations for a while and deserves a human looking at what it
     already touched, not a silent fix.

  2. SEALED WINDOW WITH A RECORDED RESULT: the rule is "a window blocks
     once a result has been recorded against it," not a fixed list of
     dates -- see SealedWindow/SEALED_WINDOWS below. margin_tripwire.py's
     realized holdout ([HOLDOUT_WINDOW_START, HOLDOUT_WINDOW_END]) blocks
     because 3.50 is recorded against it (FINDINGS.md Section 2). The
     second momentum window (holdout.MOMENTUM_WINDOW_2_START onward) does
     NOT currently block: it is open-ended and nothing has been evaluated
     against it yet (holdout.py's own MOMENTUM_WINDOW_2_MIN_REBALANCES
     has not been met) -- filling a missed day inside it is the same kind
     of action as the ordinary, unconditional daily ingestion this
     project already runs into that same window every evening, not a
     revision of a recorded result. The day a number IS recorded against
     it, flip that ONE window's `result_recorded_at` field below (mirror
     how margin_tripwire.MARGIN_LAST_VERIFIED_AT already carries window
     1's) -- classify_gap's own logic does not change; it is a generic
     loop over SEALED_WINDOWS, not an if/elif naming each window.

     An earlier version of this module used holdout.MOMENTUM_WINDOW_2_
     START directly, open-ended, as its own blocking boundary. Rejected
     after testing against real dates: that window has no end, so EVERY
     date from 2026-10-23 onward is permanently "inside" it -- which
     would make every future gap ALERT_STOP forever, starting the day
     this was built, making the auto-fill path unreachable from then on.
     That is the opposite of what was asked.

Everything else -- a gap inside no window with a recorded result, no
older than RECENT_GAP_MAX_AGE_DAYS -- is an ordinary operational miss (a
transient fetch failure, a DuckDB lock collision, a crashed run, same
shape as the real 10-day incident this module was built to close) and
gets filled.

PROVENANCE INSIDE AN OPEN (not-yet-recorded) WINDOW: a fill landing
inside MOMENTUM_WINDOW_2's span (or any future window with no recorded
result yet) does not block, but is appended to WINDOW_FILL_AUDIT_LOG --
outside the sealed data itself, same discipline as the project's
persisted exclusion lists and holdout_access_log.txt. Whoever evaluates
that window later needs to know which dates inside it were mechanically
backfilled and when; a window silently patched is a window whose
provenance can't be stated. The audit entry records only the trade_date
and row count -- never a price or any entity-level value (see next
paragraph).

WHAT GETS REPORTED, FOR ANY SEALED-DATE GAP: dates and row counts only.
Filling data is not the same as looking at it, but an alert or log line
that printed what it filled would be. Nothing in this module ever reads
back or logs an actual price, return, or entity-level value for a gap
date -- not for an ALERT_STOP date (never fetched at all) and not for an
audit-logged fill inside an open window (only the row count is recorded).

DOWNSTREAM CHAIN rebuilt after any auto-fill (BUGS.md Bug #30, item 2):
  - adjustment_factors (data_layer.adjustment.materialize_adjustment_
    factors) -- always. A new prices_eod row has no adjusted_close
    anywhere until this runs; this is the exact mechanism that kept
    compute_momentum_universe() empty even after Bug #30's raw backfill.
  - entity_prices_daily (data_layer.entity_panel.materialize_entity_
    panel) -- always, though it is physically truncated at
    SEALED_HOLDOUT_START, so it only actually changes if a filled date
    happens to be pre-holdout (never true for an AUTO_FILL date in
    practice) -- included anyway for completeness; cheap and idempotent.
  - The margin tripwire (both checks) -- always, right after the two
    materializations above. A failure here means the backfill itself
    revised something inside the first sealed window or resumed a frozen
    feed; propagates as TripwireFailedAfterBackfillError.

LINEAGE, CLOSED 2026-11-18 (BUGS.md Bug #33): the "narrow edge case, not
verified" exclusion of isin_lineage from this rebuild chain was wrong --
confirmed, not narrow. Two synthetic-warehouse reproductions showed an
ordinary backfilled day can shift a successor ISIN's known_date, or flip
a clean predecessor/successor link to overlapping_date_ranges_not_a_
clean_handover, silently splitting one entity's continuous history into
two. isin_lineage is NOT rebuilt-and-persisted unconditionally the way
adjustment_factors/entity_panel are, for a concrete reason, not caution:
margin_tripwire.assert_corporate_actions_and_lineage_still_frozen asserts
isin_lineage's row count AND MAX(fetched_at) are UNCHANGED since
2026-09-19 -- and isin_lineage.build_lineage always stamps fetched_at=
now(). Persisting a fresh build unconditionally, even one with identical
content, would bump fetched_at and trip that tripwire on every single
autofill, forever -- the same "automatic path becomes unreachable" trap
this module's docstring already names for an earlier, rejected design
(the open-ended MOMENTUM_WINDOW_2 boundary, above).

Instead: build_lineage is run TWICE -- once before this run's fill
touches prices_eod at all, once after -- and the two fresh computations
are diffed against EACH OTHER, content only (isin, entity_id,
predecessor_isin, link_method, known_date -- never fetched_at/
revision_seq, which always differ on every call). Deliberately NOT
diffed against what is currently PERSISTED in isin_lineage: that table
was intentionally frozen 2026-09-19 for margin_tripwire's own purposes
and has legitimately drifted from "what build_lineage() would produce
today" ever since, for reasons with nothing to do with any one gap fill
(prices_eod has grown for two months of ordinary trading days). Diffing
against that stale snapshot would find a large, pre-existing mismatch on
EVERY run regardless of what this fill touched -- the same "automatic
path becomes unreachable forever" trap this module's docstring already
names twice above, reintroduced a third time if not caught. The
before/after comparison isolates exactly what THIS fill changed, nothing
else. Either way, isin_lineage itself is never written here -- if
nothing changed, there is nothing to persist that isn't already true;
if something changed, it must not be persisted silently (an automatic
rebuild must never apply a different link without review) and
LineageWouldChangeError is raised instead -- the fill's raw prices_eod
rows and the two materializations above are NOT reverted (same
precedent as TripwireFailedAfterBackfillError: surfaced loudly, not
rolled back), but the run ends in a required human decision rather than
a quiet success. This is Bug #33's own candidate fix, built: "re-run
build_lineage and diff ... refusing on any changed/dropped link" --
diffing before-vs-after rather than before-vs-persisted, for the reason
above.

NOT rebuilt, and why:
  - lineage_jump_guard.find_unexplained_jumps / same_isin_jump_guard's
    equivalent / compute_momentum_universe's own unexplained_jump_
    boundaries: none of these are materialized tables. Every call reads
    prices_eod/isin_lineage fresh -- there is nothing to rematerialize;
    they self-heal the instant the underlying rows are correct.
  - index_eod: populated by a wholly separate source (NSE_INDEX_CLOSE_
    ALL, data_layer.index_nse) that does not read prices_eod at all;
    there is no table in this codebase derived from BOTH prices_eod and
    index_eod. Nothing to rebuild.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import duckdb
import pandas as pd

from data_layer.adjustment import materialize_adjustment_factors
from data_layer.entity_panel import materialize_entity_panel
from data_layer.holdout import MOMENTUM_WINDOW_2_START
from data_layer.isin_lineage import build_lineage
from data_layer.margin_tripwire import (
    FrozenTableResumedError,
    HOLDOUT_WINDOW_END,
    HOLDOUT_WINDOW_START,
    HoldoutWindowPriceRevisionError,
    MARGIN_LAST_VERIFIED_AT,
    assert_corporate_actions_and_lineage_still_frozen,
    assert_no_in_window_price_revision,
)
from data_layer.price_gap_detector import find_missing_trading_days
from data_layer.prices_nse import load_bhavcopy_to_duckdb

ROOT = Path(__file__).resolve().parents[2]
WINDOW_FILL_AUDIT_LOG = ROOT / "data" / "window_fill_audit_log.txt"

RECENT_GAP_MAX_AGE_DAYS = 30  # user instruction, 2026-11-18 -- "~30 days"

ACTION_AUTO_FILL = "AUTO_FILL"
ACTION_ALERT_STOP = "ALERT_STOP"

REASON_TOO_OLD = "older than the auto-fill window"
REASON_RECENT_OPERATIONAL = "recent operational miss"


@dataclass(frozen=True)
class SealedWindow:
    name: str
    start: dt.date
    end: dt.date | None  # None = still open, no realized end date yet
    result_recorded_at: dt.datetime | None  # None = nothing has been evaluated against this window yet

    def contains(self, d: dt.date) -> bool:
        if d < self.start:
            return False
        return self.end is None or d <= self.end

    def blocks(self, d: dt.date) -> bool:
        """A window only blocks a raw-data backfill once a result has
        actually been recorded against it. An open window nobody has
        evaluated yet is filled by the same ordinary, unconditional
        daily ingestion this project already runs every evening -- there
        is no recorded number for a fill to disturb."""
        return self.result_recorded_at is not None and self.contains(d)


# The blocking set is DERIVED from each window's own recorded-result
# status, not hardcoded per-window logic -- see module docstring. Adding
# a future window, or flipping an open one to blocking once it gets a
# recorded result, means editing ONE record here; classify_gap's own
# loop below never changes.
SEALED_WINDOWS: list[SealedWindow] = [
    SealedWindow(
        name="first sealed holdout (margin_tripwire.py; FINDINGS.md Section 2)",
        start=HOLDOUT_WINDOW_START,
        end=HOLDOUT_WINDOW_END,
        result_recorded_at=MARGIN_LAST_VERIFIED_AT,  # 3.50 is recorded against this window
    ),
    SealedWindow(
        name="second sealed momentum window (holdout.py)",
        start=MOMENTUM_WINDOW_2_START,
        end=None,  # still open -- holdout.MOMENTUM_WINDOW_2_MIN_REBALANCES not yet met
        result_recorded_at=None,  # flip this the day a number is recorded against this window
    ),
]


class GapRequiresHumanDecisionError(Exception):
    """Raised when find_missing_trading_days finds a gap that is too old
    or sits inside a window a result has been recorded against -- the
    caller must not fill it automatically. Any gap found in the SAME
    scan that is NOT one of these is still filled before this is raised
    (see run_gap_check_and_autofill) -- an old or sealed gap elsewhere in
    history should not hold an unrelated, ordinary operational miss
    hostage. Message carries only dates and reasons, never price data."""


class TripwireFailedAfterBackfillError(Exception):
    """Raised when the margin tripwire fails immediately after an
    auto-fill -- the backfill itself touched the first sealed window or
    resumed a frozen feed. Wraps the original tripwire exception so the
    caller can refuse exactly like any other data-integrity failure."""


class LineageWouldChangeError(Exception):
    """Raised when recomputing isin_lineage after an auto-fill would
    produce different content than what is currently persisted (BUGS.md
    Bug #33) -- the new lineage is NOT written. Message carries only
    isins and dates, never price data, same discipline as
    GapRequiresHumanDecisionError. The raw prices_eod fill and the
    adjustment_factors/entity_panel rematerializations that already ran
    are NOT reverted -- same precedent as TripwireFailedAfterBackfillError."""


_LINEAGE_CONTENT_COLS = ["entity_id", "predecessor_isin", "link_method", "known_date"]


def _lineage_content_diff(old_df: pd.DataFrame, new_df: pd.DataFrame) -> list[str]:
    """isins whose (entity_id, predecessor_isin, link_method, known_date)
    differs between two build_lineage() outputs, or that exist on only
    one side -- empty list means the two computations agree completely.
    Pure dataframe diff, no connection -- callers pass a BEFORE-fill and
    an AFTER-fill build_lineage() result (module docstring explains why
    this must be before-vs-after, never before-vs-currently-persisted).
    Never compares fetched_at/source/revision_seq, which legitimately
    differ on every build_lineage() call regardless of content."""
    old = old_df[["isin"] + _LINEAGE_CONTENT_COLS].copy()
    new = new_df[["isin"] + _LINEAGE_CONTENT_COLS].copy()

    for df in (old, new):
        df["predecessor_isin"] = df["predecessor_isin"].fillna("<NONE>")
        df["known_date"] = pd.to_datetime(df["known_date"]).dt.date

    merged = old.merge(new, on="isin", how="outer", suffixes=("_old", "_new"), indicator=True)
    changed_isins: set[str] = set(merged.loc[merged["_merge"] != "both", "isin"])
    both = merged[merged["_merge"] == "both"]
    for col in _LINEAGE_CONTENT_COLS:
        mismatched = both.loc[both[f"{col}_old"] != both[f"{col}_new"], "isin"]
        changed_isins.update(mismatched)
    return sorted(changed_isins)


@dataclass(frozen=True)
class GapDecision:
    trade_date: dt.date
    action: str  # ACTION_AUTO_FILL / ACTION_ALERT_STOP
    why: str


def _blocking_window(d: dt.date) -> SealedWindow | None:
    for w in SEALED_WINDOWS:
        if w.blocks(d):
            return w
    return None


def _open_window_containing(d: dt.date) -> SealedWindow | None:
    """Like _blocking_window, but matches a window regardless of whether
    it currently blocks -- used only to decide whether a successful
    AUTO_FILL needs an audit-trail entry (module docstring, 'PROVENANCE
    INSIDE AN OPEN WINDOW')."""
    for w in SEALED_WINDOWS:
        if w.contains(d):
            return w
    return None


def classify_gap(trade_date: dt.date, as_of: dt.date) -> GapDecision:
    """Window membership is checked before age -- a gap that happens to
    be both inside a blocking window AND recent is still ALERT_STOP;
    window membership always wins."""
    window = _blocking_window(trade_date)
    if window is not None:
        return GapDecision(trade_date, ACTION_ALERT_STOP, window.name)
    age_days = (as_of - trade_date).days
    if age_days > RECENT_GAP_MAX_AGE_DAYS:
        return GapDecision(trade_date, ACTION_ALERT_STOP, REASON_TOO_OLD)
    return GapDecision(trade_date, ACTION_AUTO_FILL, REASON_RECENT_OPERATIONAL)


def _record_fill_inside_open_window(window: SealedWindow, trade_date: dt.date, rows: int) -> None:
    """Dates and row counts only -- never a price or entity-level value
    (module docstring)."""
    WINDOW_FILL_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(WINDOW_FILL_AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(
            f"{dt.datetime.now().isoformat()} | AUTO-FILLED {trade_date.isoformat()} ({rows} rows) -- "
            f"inside open window '{window.name}' [{window.start} .. {window.end or 'open'}], "
            f"no result recorded against it yet. See BUGS.md Bug #30.\n"
        )


def run_gap_check_and_autofill(
    con: duckdb.DuckDBPyConnection,
    raw_dir: Path,
    as_of: dt.date,
    log: Callable[[str], None],
    series_include: list[str] | None = None,
) -> dict:
    """Finds every gap in prices_eod's full history, classifies each,
    fills the auto-fillable ones, rebuilds the downstream chain (see
    module docstring), and re-runs the margin tripwire. Raises
    GapRequiresHumanDecisionError if any gap is too old or inside a
    window a result has been recorded against -- after filling
    everything else first, not instead of it. Raises
    LineageWouldChangeError if recomputing isin_lineage after the fill
    would change any isin's resolution (BUGS.md Bug #33) -- checked
    before the margin tripwire, which would otherwise mask it. Raises
    TripwireFailedAfterBackfillError if the tripwire fails immediately
    after an auto-fill."""
    missing = find_missing_trading_days(con)
    result: dict = {"auto_filled": [], "alert": [], "rows_loaded": 0}
    if not missing:
        return result

    decisions = [classify_gap(m.trade_date, as_of) for m in missing]
    auto = [d for d in decisions if d.action == ACTION_AUTO_FILL]
    alert = [d for d in decisions if d.action == ACTION_ALERT_STOP]

    if auto:
        log(f"price gap check: {len(auto)} recent, non-sealed missing trading day(s) -- "
            f"auto-filling: {[d.trade_date.isoformat() for d in auto]}")
        # Captured BEFORE prices_eod is touched -- the baseline this fill's
        # own effect on isin_lineage is measured against. Must not be the
        # currently-persisted isin_lineage table (module docstring: that
        # snapshot is frozen as of 2026-09-19 and has already drifted from
        # "what build_lineage() produces today" for unrelated reasons).
        pre_lineage_df, _ = build_lineage(con)
        for d in auto:
            n = load_bhavcopy_to_duckdb(con, d.trade_date, raw_dir, series_include=series_include)
            result["rows_loaded"] += n
            open_window = _open_window_containing(d.trade_date)
            if open_window is not None:
                _record_fill_inside_open_window(open_window, d.trade_date, n)
                log(f"  {d.trade_date}: inside open window '{open_window.name}' -- audit-logged "
                    f"to {WINDOW_FILL_AUDIT_LOG.name}.")
        log("price gap check: rebuilding downstream chain (adjustment_factors, entity panel)...")
        materialize_adjustment_factors(con)
        materialize_entity_panel(con)

        log("price gap check: verifying isin_lineage is unaffected by this fill (BUGS.md Bug #33)...")
        post_lineage_df, _ = build_lineage(con)
        changed = _lineage_content_diff(pre_lineage_df, post_lineage_df)
        if changed:
            raise LineageWouldChangeError(
                "auto-filling {} would change isin_lineage's resolution for {} isin(s): {} -- "
                "NOT persisted. The price fill and adjustment_factors/entity_panel rebuilds above "
                "already happened and are not reverted; a human must review the lineage change "
                "before isin_lineage itself is touched. See BUGS.md Bug #33.".format(
                    [d.trade_date.isoformat() for d in auto], len(changed), changed[:10],
                )
            )
        log("price gap check: isin_lineage unaffected -- not rewritten (its own freeze invariant "
            "stays intact; see margin_tripwire.assert_corporate_actions_and_lineage_still_frozen).")

        log("price gap check: running margin tripwire after backfill...")
        try:
            assert_no_in_window_price_revision(con)
            assert_corporate_actions_and_lineage_still_frozen(con)
        except (HoldoutWindowPriceRevisionError, FrozenTableResumedError) as e:
            raise TripwireFailedAfterBackfillError(
                f"margin tripwire failed immediately after auto-filling "
                f"{[d.trade_date.isoformat() for d in auto]}: {e}"
            ) from e
        log("price gap check: margin tripwire passed.")
        result["auto_filled"] = [d.trade_date for d in auto]

    if alert:
        result["alert"] = alert
        raise GapRequiresHumanDecisionError(
            "{} missing trading day(s) require a human decision before they can be filled: {}".format(
                len(alert), "; ".join(f"{d.trade_date} ({d.why})" for d in alert),
            )
        )
    return result
