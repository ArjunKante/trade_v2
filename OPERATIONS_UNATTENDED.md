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

**Since 2026-11-19, one more signal type exists that is NOT a refusal**:
an email subject starting `FIBO EVENING: HOLIDAY CALENDAR DEGRADED` or
`FIBO MORNING: HOLIDAY CALENDAR DEGRADED` -- the job completed normally
(heartbeat reached, no `REFUSED` session_status), but ran with the
holiday calendar unable to confirm a date. See "Holiday-calendar guard
now degrades instead of refusing" below for what this means and the
one-command fix.

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

---

## 2026-12: load next year's NSE holiday calendar before it's needed

### What it means

`data_layer.nse_holidays`' two sources (`data/raw/nse_cm_holidays.pkl`,
the laptop's own full copy; `data/raw/nse_cm_holidays_fallback.json`,
the committed copy a GitHub Actions runner's fresh checkout relies on)
cover 2016-2026 only, as of 2026-11-19. NSE typically publishes the
following year's trading-holiday circular in December. **Check monthly
starting December 2026** -- the exact command below both checks and
loads in one step, so there is nothing to do by hand beyond running it.

### The exact command

```
python scripts/fetch_nse_holiday_calendar.py --year 2027
```

- If NSE has not published 2027 yet, this refuses loudly and writes
  nothing (`HolidayCalendarNotPublished`, exit code 1) -- safe to
  re-run on the same schedule next month.
- If it has, this fetches the real CM-segment circular, writes both
  `nse_cm_holidays.pkl` and `nse_cm_holidays_fallback.json`, and prints
  the exact `git add`/`git commit` for the fallback file (the one path
  this project's `.gitignore` carves out). **Commit it** -- an
  uncommitted fallback file still leaves a GitHub Actions runner's
  fresh checkout uncovered for 2027.
- `--dry-run` fetches and reports without writing anything; this is how
  the script was verified against the already-trusted 2026 calendar
  before being trusted for 2027 (`python scripts/fetch_nse_holiday_
  calendar.py --year 2026 --dry-run` reproduced NSE's real, live 20-date
  2026 CM calendar byte-for-byte against the stored one, 2026-11-19).

### Why this script didn't exist until 2026-11-19

The original 2016-2026 calendar was "fetched directly from NSE in an
earlier phase of this project" (`data_layer/nse_holidays.py`'s own
docstring) by a one-off, uncommitted script. Every month since, the
monthly-recheck note existed only as a documented intention -- exactly
the pattern `PROJECT_CONTEXT.md` Section 7 finding #15 names (a flag
nobody is forced to act on dies). This script is the fix: a single,
tested, re-runnable command, so the January outage this whole section
exists to prevent takes one command to resolve, by anyone, not a fresh
investigation into how the original calendar was ever built.

---

## Holiday-calendar guard now degrades instead of refusing (2026-11-19) -- a deliberate reversal of 2026-11-15

### What changed

From 2026-11-15 to 2026-11-19, `fibo_evening.py`'s `next_trading_day`
and `fibo_morning.py`'s `previous_trading_day` let `HolidayCalendarMissing`
propagate uncaught the moment a candidate date's year wasn't covered by
either calendar source -- the evening job emailed `notify_evening_
skipped` and stopped before the heartbeat; the morning job logged a
`REFUSED` session_status and stopped before `login()`. **Reversed
2026-11-19**: both functions now catch `HolidayCalendarMissing`
themselves, log a WARNING, treat the unconfirmable candidate as an
ORDINARY TRADING DAY (weekend-only from there), and return a `degraded`
flag. The caller no longer stops the run on this condition -- it sends
a loud, independent email (`notify_holiday_calendar_degraded`, new in
both scripts, kept at FULL VOLUME, same `send_email`/dedup mechanism
every other alert here already uses) and continues.

### Why: the operating context changed, not the underlying judgment

Refusing outright was the right trade on 2026-11-15, for the problem
that existed then: a single evening/morning run hitting an uncovered
year, with a human checking in daily, able to reload the calendar the
same day. The *same* mechanism is the wrong trade for the problem that
exists now: the 2026-12/2027-01 unattended window above, where nobody
may check in for weeks. In that setting, "refuse" doesn't mean "caught
safely" -- it means the forward test silently stops producing
watchlists every single night (evening) or every single morning
(morning) until someone happens to notice and runs the reload command.
A documented alert nobody reads in time is operationally identical to
no alert at all; a correctly-firing degrade-and-continue is not.

The two failure modes were weighed directly, not assumed:
- **Weekend-only degradation is mild, and already covered.** If a real,
  uncovered-year holiday slips through as an assumed trading day, the
  evening job's bhavcopy fetch simply finds nothing published that day
  (exactly like any other day with no data yet), and the EXISTING
  staleness/no-bhavcopy handling (`assert_data_current`, the backward-
  walk fetch loop) already deals with that case correctly -- it is not
  a new failure mode, it's the ordinary "nothing published yet" path
  this job runs every single day regardless.
- **Refusing outright, for three unattended months, is not mild.** It
  is the forward test going dark, discovered only when a human
  eventually goes looking -- the exact outcome `PROJECT_CONTEXT.md`
  Section 2's "momentum basket check-in ~2027-01-27, calendar-uncertain"
  entry was already worried about for a DIFFERENT, adjacent reason.

### What did NOT change

- `data_layer.nse_holidays.is_nse_holiday` itself is untouched -- it
  still raises `HolidayCalendarMissing` for an uncovered year, by
  design (that module's own docstring: the choice of what to do about
  it belongs to each caller, not to it). Only the two Fibo call sites'
  own degrade-vs-refuse choice reversed.
- `fibo_morning.py`'s separate, pre-existing `is_non_trading_day` check
  already silently treated an uncovered year as "not confirmed a
  holiday" (returns `False` on `HolidayCalendarMissing`) -- that is a
  different, older code path, untouched by this change, and it never
  sends an alert either way. Only the two newly-degrading functions
  (`next_trading_day`, `previous_trading_day`) now alert.
- The loudest fix remains loading the real calendar (the section above)
  -- degrading gracefully is a safety net for the gap between "the
  calendar ran out" and "someone reloads it," not a reason to stop
  reloading it.

### Verified by test

`tests/test_holiday_week_oct2026.py` and `tests/test_fibo_morning_
watchlist_freshness.py`: both `next_trading_day`/`previous_trading_day`
return `(date, degraded)` instead of raising; `assert_watchlist_current`
propagates the flag instead of raising; both `main()`s complete
normally (heartbeat reached / no holiday-calendar `REFUSED` event) and
each sends exactly one `HOLIDAY CALENDAR DEGRADED` email. Full `fibo`/
`holiday` selection (211 tests) passes.

---

## Fibo morning job: the 10:45/11:00/11:15 candles aren't examined until the 15:20 run

cron-job.org dispatches at 09:35/10:00/11:00 leave the 10:45, 11:00 and
11:15 candle-starts unexamined until the 15:20 run — 17.1% of backtest
trades (37 of 216) enter in that slice. Detecting them only at 15:20
means the signal and its outcome are committed at the same moment, after
the result is knowable, which defeats the pre-outcome timestamp the
forward test's credibility rests on. Fix: add a dispatch at 11:35 (the
last in-window candle closes 11:30). Found 2026-11-19, code trace not
yet observed live — zero triggers logged to date.

**The first thing to verify once a real trigger in this slice (entry_ts
10:59, 11:14, or 11:29) actually occurs**: check that slice's trigger's
own logged `ts` (`events.jsonl`) against its `entry_ts` -- if `ts` lands
near 15:20 rather than near the candle's own close, this gap is
confirmed live, not just a code trace, and the 11:35 dispatch fix above
is no longer optional.
