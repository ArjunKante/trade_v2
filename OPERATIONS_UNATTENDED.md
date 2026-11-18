# Unattended operation runbook

A focused recovery doc for failures that can silently stop the Fibo
evening job from producing a watchlist while nobody is watching --
distinct from OPERATIONS.md (the full operational history/decision log)
and BUGS.md (the full bug catalogue). This file exists to be read FAST,
at 2am, by whoever is covering, without having to reconstruct context
from either of those. Add an entry here any time a new unattended
failure mode is found; keep each entry self-contained (what it means,
what to inspect, the exact command).

**How to tell something needs this doc at all**: the evening job's own
`notify_evening_skipped(...)` call (and the resulting log line, always
prefixed `REFUSING TO COMPUTE:`) names the reason. Match that reason
string against the section headers below.

---

## `LineageWouldChangeError` ("isin_lineage would change after backfill")

### What it means

The evening job found a missing trading day, filled it into `prices_eod`
(and already rebuilt `adjustment_factors`/`entity_prices_daily` on top of
it), then checked whether rebuilding `isin_lineage` from that newly-
filled data would produce a DIFFERENT result than what is currently
persisted. It would. This is BUGS.md Bug #33's confirmed real mechanism:
an ordinary backfilled day can shift a successor ISIN's transition date,
or flip a clean predecessor/successor link into an unresolved overlap,
silently splitting one entity's continuous history into two if applied
without review.

**The price fill already happened and is NOT reverted.** `isin_lineage`
itself was never written -- the job computed what it WOULD be, found it
differs, and stopped there rather than persist a different link
silently. `isin_lineage` is exactly as it was before this run.

### Blast radius: the WHOLE evening job, for one run -- does not recur on its own, but does not self-correct either

- **No watchlist is produced for the target trading day.** This error is
  raised before `build_watchlist`/the `watchlist`/`watchlist_run` events
  in `scripts/fibo_evening.py`'s `main()` -- the function returns right
  after logging and calling `notify_evening_skipped`. The morning job's
  own freshness guard (`assert_watchlist_current`) will then also refuse
  the next morning, the same "REFUSED -- No watchlist_run event targets
  <date>" shape already seen for Bug #19's outage.
- **It will NOT fire again tomorrow for the SAME gap**, because the raw
  price fill already happened and is not reverted -- `find_missing_
  trading_days` will no longer see that date as missing on the next run.
  If no new gap appears, the evening job resumes producing watchlists
  normally the very next night, with no human action.
- **It will NOT self-correct the actual problem.** `isin_lineage` stays
  stale relative to what `prices_eod` now actually supports, silently,
  forever, until a human runs the ACCEPT procedure below. Nothing
  re-checks this later on its own. If you only notice "the watchlist
  came back the next night" and conclude the problem resolved itself,
  you are wrong -- it went silent, not away.
- **It CAN recur with a different isin** if a different gap later lands
  near a different entity's own first/last observed trading day -- bounded
  by how often that coincidence happens (BUGS.md Bug #33: "not rare in
  kind, only in how often a given gap happens to land on an ISIN's
  first/last observed day"), not a permanent block.

### What to inspect

```
python scripts/inspect_lineage_drift.py
```

Read-only, safe to run any time, any number of times (it diffs a FRESH
`build_lineage()` against whatever is currently persisted -- unaffected
by how much time has passed since the failure). Prints every isin that
would change, OLD vs NEW (`entity_id`, `predecessor_isin`, `link_method`,
`known_date`) side by side. Also check the evening job's own log line for
that run (or the `notify_evening_skipped` message) -- it names up to the
first 10 affected isins directly, which is usually enough to start with.

For each changed isin, decide by hand: is the NEW resolution actually
correct (a real ISIN reissue the structural rule now resolves correctly
given the completed data), or does it look wrong (e.g. an overlap that
shouldn't exist, suggesting the UNDERLYING filled data itself needs a
second look before touching lineage at all)?

### Recovery: accept the lineage change (the common case)

Only once you've reviewed the diff above and the NEW resolution looks
correct:

```
python scripts/build_isin_lineage.py
```

This rebuilds and PERSISTS `isin_lineage` from scratch (prints the
BAJFINANCE sanity check at the end -- confirm it still looks right).

**Required follow-up, do not skip:** `margin_tripwire.py`'s
`assert_corporate_actions_and_lineage_still_frozen` asserts `isin_
lineage`'s row count and `MAX(fetched_at)` are UNCHANGED since
2026-09-19. After accepting a real lineage change, that assertion will
now correctly fail on every subsequent evening run (`FrozenTableResumedError`)
-- not a new bug, the tripwire doing its job -- until the frozen baseline
itself is updated to the new reality:

1. Note the new row count and `fetched_at` printed by
   `build_isin_lineage.py` (or query `SELECT COUNT(*), MAX(fetched_at)
   FROM isin_lineage`).
2. Edit `src/data_layer/margin_tripwire.py`: update
   `ISIN_LINEAGE_FROZEN_ROWS` and `ISIN_LINEAGE_FROZEN_AT` to those
   values.
3. Re-run the margin materiality check (`python scripts/run_holdout_
   study1_lineage_check.py`) to confirm the holdout margin is still what
   FINDINGS.md Section 2 reports -- **check BUGS.md Bug #34 first**: as
   of 2026-11-19 this number was already NOT reproducing (5.81, not
   3.50) for a separate, unidentified reason, independent of lineage.
   Don't attribute a mismatch here to the lineage change you just made
   without first ruling out Bug #34's own open cause.
4. Commit the `margin_tripwire.py` constant update and whatever
   FINDINGS.md Section 2 revision follows from step 3, together, with a
   clear message naming which gap triggered the lineage change.

### Recovery: reject the lineage change / handle the gap manually

There is no automatic rollback for the raw price fill -- it already
happened. "Manual" here means: don't run `build_isin_lineage.py` at all
(leave `isin_lineage` exactly as it is), and instead investigate the
FILLED DATA itself by hand if the diff from `inspect_lineage_drift.py`
looks wrong (e.g. a bhavcopy row for the gap date looks suspicious, or
the entity boundary it landed on suggests a real corporate event the
auto-fill had no business treating as "an ordinary missed day" at all).
Correcting `prices_eod` directly is a manual DuckDB operation outside any
existing script's scope -- treat it the same caution-level as any other
direct price-table edit in this project (append-only, higher
`revision_seq`, never UPDATE/DELETE), and re-run `inspect_lineage_drift.py`
afterward to confirm the diff is now empty or has changed to something
you're prepared to accept.

### What NOT to do

- Do not comment out or bypass the `LineageWouldChangeError` raise to
  "get the watchlist running again" -- that is exactly the silent-drift
  risk Bug #33 exists to prevent.
- Do not run `build_isin_lineage.py` without reading
  `inspect_lineage_drift.py`'s output first.
- Do not forget the `margin_tripwire.py` constant update after accepting
  a change -- skipping it does not make the job healthier, it just
  converts tonight's clear, specific error into tomorrow's
  `FrozenTableResumedError` on the UNRELATED next evening run.

---

## Sibling exceptions caught in the same `try`/`except` block (fibo_evening.py)

If the log doesn't say "isin_lineage would change," check which of these
it actually says instead -- they look similar (`REFUSING TO COMPUTE:`,
`notify_evening_skipped`, no watchlist produced) but need different
recovery:

- **`GapRequiresHumanDecisionError`** ("price gap needs review"): a
  missing trading day is too old (>30 days) or sits inside a sealed
  window with a recorded result. Not a lineage issue at all -- see
  `src/data_layer/gap_backfill.py`'s own module docstring for the
  AUTO_FILL/ALERT_STOP policy.
- **`TripwireFailedAfterBackfillError`** ("margin tripwire failed after
  backfill"): the backfill itself revised a price inside the first
  sealed holdout window, or resumed a frozen feed
  (`corporate_actions`/`isin_lineage` gained a row some OTHER way than
  this project's own `build_isin_lineage.py`). Investigate which of
  `margin_tripwire.py`'s two conditions fired before touching anything.
