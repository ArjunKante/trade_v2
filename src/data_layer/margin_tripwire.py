"""Tripwire for FINDINGS.md Section 2's 3.50 holdout margin.

The 3.50 figure is recorded as reproducible under window-level lineage
correction for two reasons (FINDINGS.md Section 2, final restatement,
2026-11-17): its exclusion list is persisted (`results/exclusions/
run_holdout_study1_lineage_check.window_level.json`), and recomputing
that list from scratch gives the same in-window entity set because (a)
`prices_eod` has only ever grown forward (no row inside the sealed
holdout window [2025-04-11, 2026-04-22] has been touched since this was
verified) and (b) `corporate_actions`/`isin_lineage` have been frozen,
unchanged, since 2026-09-19.

Both of those are facts about the warehouse TODAY, not permanent
properties. This module is the mechanized version of the tripwire
FINDINGS.md Section 2 states in prose -- checked here, not just
written down, so a resumed ingest or a backfill does not have to be
remembered by someone reading an old markdown file. Not yet wired into
any entry point (unlike `staleness.assert_data_current`, which every
price-panel consumer already calls) -- that wiring is additional,
unscoped work, left for whoever next touches the ingestion path for
either table.
"""
from __future__ import annotations

import datetime as dt

import duckdb

HOLDOUT_WINDOW_START = dt.date(2025, 4, 11)
HOLDOUT_WINDOW_END = dt.date(2026, 4, 22)

# Confirmed by direct query, BUGS.md Bug #27's correction, 2026-11-17.
CORPORATE_ACTIONS_FROZEN_ROWS = 727
CORPORATE_ACTIONS_FROZEN_AT = dt.datetime(2026, 9, 19, 23, 9, 3, 854044)
ISIN_LINEAGE_FROZEN_ROWS = 3357
ISIN_LINEAGE_FROZEN_AT = dt.datetime(2026, 9, 19, 23, 19, 29, 582651)

# The timestamp this module's checks were last confirmed to pass against
# (results/exclusions/run_holdout_study1_lineage_check.window_level.json
# generated_at). A caller checking for in-window price revision should
# pass the moment the margin was last verified reproducible, not an
# arbitrary "now" -- this default is that moment.
MARGIN_LAST_VERIFIED_AT = dt.datetime(2026, 11, 17, 3, 43, 12, 854859)


class FrozenTableResumedError(Exception):
    """corporate_actions or isin_lineage gained a row, or a fetched_at
    value newer than its recorded frozen snapshot -- condition (b) of
    FINDINGS.md Section 2's tripwire. A resumed corporate_actions feed
    could newly EXPLAIN one of the 14 currently-unexplained in-window
    lineage transitions, removing it from the exclusion set and moving
    the 3.50 margin. Recompute and revisit FINDINGS.md Section 2 before
    trusting 3.50 again."""


class HoldoutWindowPriceRevisionError(Exception):
    """A prices_eod row with trade_date inside the sealed holdout window
    [2025-04-11, 2026-04-22] has a fetched_at after the margin was last
    verified -- condition (a) of FINDINGS.md Section 2's tripwire: price
    ingestion is no longer forward-only, and a newly-detected in-window
    jump is possible. Recompute and revisit FINDINGS.md Section 2 before
    trusting 3.50 again."""


def assert_corporate_actions_and_lineage_still_frozen(
    con: duckdb.DuckDBPyConnection,
) -> None:
    ca_count, ca_max = con.execute(
        "SELECT COUNT(*), MAX(fetched_at) FROM corporate_actions"
    ).fetchone()
    if ca_count != CORPORATE_ACTIONS_FROZEN_ROWS or (
        ca_max is not None and ca_max > CORPORATE_ACTIONS_FROZEN_AT
    ):
        raise FrozenTableResumedError(
            f"corporate_actions has {ca_count} rows (max fetched_at {ca_max}), "
            f"not the frozen {CORPORATE_ACTIONS_FROZEN_ROWS} rows as of "
            f"{CORPORATE_ACTIONS_FROZEN_AT} -- the feed has resumed. "
            f"See FINDINGS.md Section 2, condition (b)."
        )

    lin_count, lin_max = con.execute(
        "SELECT COUNT(*), MAX(fetched_at) FROM isin_lineage"
    ).fetchone()
    if lin_count != ISIN_LINEAGE_FROZEN_ROWS or (
        lin_max is not None and lin_max > ISIN_LINEAGE_FROZEN_AT
    ):
        raise FrozenTableResumedError(
            f"isin_lineage has {lin_count} rows (max fetched_at {lin_max}), "
            f"not the frozen {ISIN_LINEAGE_FROZEN_ROWS} rows as of "
            f"{ISIN_LINEAGE_FROZEN_AT} -- the feed has resumed. "
            f"See FINDINGS.md Section 2, condition (b)."
        )


def assert_no_in_window_price_revision(
    con: duckdb.DuckDBPyConnection,
    baseline_fetched_at: dt.datetime = MARGIN_LAST_VERIFIED_AT,
) -> None:
    row = con.execute(
        "SELECT COUNT(*) FROM prices_eod "
        "WHERE trade_date BETWEEN ? AND ? AND fetched_at > ?",
        [HOLDOUT_WINDOW_START, HOLDOUT_WINDOW_END, baseline_fetched_at],
    ).fetchone()
    if row[0] > 0:
        raise HoldoutWindowPriceRevisionError(
            f"{row[0]} prices_eod row(s) inside the sealed holdout window "
            f"[{HOLDOUT_WINDOW_START}, {HOLDOUT_WINDOW_END}] have fetched_at "
            f"after {baseline_fetched_at} -- price ingestion has touched "
            f"already-closed history. See FINDINGS.md Section 2, condition (a)."
        )
