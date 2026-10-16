# Standing operational lessons for long-running scripts

Not data-correctness bugs (see `BUGS.md`) -- engineering-practice lessons
about how this project's own tooling gets built, recorded because they
recur.

## Buffered stdout creates a stuck-vs-slow ambiguity (third occurrence)

Found live during the Phase B annual-XBRL extraction (12,308 documents,
multi-hour run): the log file sat at 0 bytes for the first several minutes
of real, correct progress, because (a) the initial status line lacked
`flush=True` and (b) the periodic progress line only fired every 500
documents -- an 8-10 minute blind window on a run this size. A person
watching the log at minute 4 cannot tell "working normally" from "hung"
without querying the database directly, which defeats the point of having
a log.

**This is the third time this exact ambiguity has shown up across these
projects.** Standing rule from here on, for every long-running script:

- Write progress to a log **file** with `flush=True` on **every** printed
  line, including the very first one -- not just periodic checkpoints.
  Python fully buffers stdout by default when it's redirected to a file
  (not a TTY); nothing appears until an explicit flush, a filled buffer, or
  process exit, regardless of how much real work has happened.
- Periodic checkpoints (e.g. "500 of 12,308 done") are still useful for a
  progress estimate, but are not a substitute for line-level flushing --
  they're too coarse to distinguish stuck from slow within their own
  window.
- Prefer a time-based heartbeat (one line every 30-60 seconds, regardless
  of how many items that represents) over a count-based checkpoint for
  anything expected to run more than a few minutes -- a heartbeat answers
  "is this alive" on a fixed cadence; a count-based checkpoint's answer
  time scales with however slow the run turns out to be, which is exactly
  the thing being diagnosed.

## Resume gap: permanently-failing items are retried forever, not just recovered

The annual-XBRL extraction's resumability (skip any `seq_number` already
present in `fundamentals_xbrl_facts`) is sound for the crash-recovery case
it was built for -- a crash loses at most one in-flight document, confirmed
by design (each document's facts are written and committed before moving
to the next). But it has no memory of a document that errored or came back
empty: those are recorded nowhere, so every future resume of the same job
retries them from scratch.

Safe (no data loss, no incorrect data), but inefficient against a document
that fails for a reason that will never change (permanently malformed
XBRL, a dead link, a genuinely empty filing) -- every resume pays the same
network round-trip for the same permanent failure. Noted, not fixed now;
the fix would be a small "known-bad" log (document id, reason, timestamp)
consulted before each fetch, separate from the fetch_log pattern used for
the price/corporate-actions backfills since this job's resumability
substrate is the fact table itself, not fetch_log (see the exchange that
prompted this note for why that distinction matters).

## A fix applied only where the bug was noticed, not everywhere the same pattern occurs (fourth occurrence)

`corporate_actions.py` established, and tested, that NSE's corporate-
actions feed's `isin` field cannot be trusted for company identification
(`resolve_isin_for_actions`, matching by symbol against this project's own
price observations instead). That fix was never checked against the OTHER
NSE feed built around the same `isin` field -- `corporates-financial-
results`, i.e. every fundamentals fact in this warehouse -- which had the
identical defect. It did: 166 of 2,487 companies' fundamentals were
silently orphaned from every join through `isin_lineage`, and every Phase
E factor had been measured on a universe missing them, for months, before
anyone thought to check (BUGS.md Bug #7).

**This is the fourth occurrence of this exact meta-pattern across this
project and its predecessor.** It is not carelessness -- each individual
fix was careful, tested, and correct for the case that motivated it. The
failure is that nobody thinks to ask, at the moment a fix is found and
verified, "where else does this exact shape of bug live?" A fix's own
correctness gives no signal that a sibling instance exists elsewhere;
finding one requires a deliberate, separate step that the relief of having
just fixed something makes easy to skip.

**Standing rule from here on: when a bug is fixed, grep the codebase for
the same shape before closing it out.** Concretely, before considering any
bug resolved:
- Name the general shape of the defect in one sentence (here: "a feed's
  own identifier field cannot be trusted and must be re-resolved against
  this project's own observations"), not just the specific instance fixed.
- Grep/search for every other place that shape could plausibly recur --
  every other ingestion path touching a similar external identifier, every
  other module with a structurally similar assumption -- before marking
  the bug closed, not after something else breaks and reveals a sibling.
- If a sibling is found, it is the SAME bug for logging purposes (same
  BUGS.md entry, or an explicit cross-reference), not a coincidentally
  similar new one -- treating it as new hides the fact that the first fix
  should have been searched for siblings and wasn't.

## Angel One rate limiting: the documented limits are not the real constraint

Every module that calls Angel One SmartAPI has independently rediscovered
throttling settings. This section is the one place to check or update them,
so the next module doesn't re-derive this from scratch.

**Published limits** (confirmed live against
`https://smartapi.angelone.in/docs/RateLimit` and `.../docs/Historical`):
`getCandleData` = 3 req/sec, 150 req/min, 5000 req/hour. No documented daily
cap exists for this or any other endpoint used here.

**What we have actually hit is tighter than the documented caps, twice:**
- **2026-10-09**: a rate-limit-shaped error after only ~6 requests in a few
  seconds -- nowhere near 3/sec, 150/min, or 5000/hour.
- **2026-09-30** (`scripts/fibo_download_intraday_top200.py`): the download
  stopped on a rate-limit-shaped error after 502 successful requests in
  roughly 10 minutes -- again well inside every published ceiling.

Neither incident is explained by the documented per-second/minute/hour
numbers. Two readings are both consistent with the evidence and neither is
ruled out: either Angel enforces an undocumented burst limit (tripped by a
short run of requests closer together than the published per-second cap
would suggest), or there is an undocumented cumulative/daily quota that
2026-09-30's ~502-request stop and 2026-10-09's ~6-request stop both sit
under. **Treat the published numbers as an upper bound on what Angel allows,
never as a floor on what will actually succeed.**

**The rule, regardless of which reading is correct:** on a rate-limit error,
back off and retry the *same* request. Never record a failed fetch as a
result -- a chunk/candle/quote that was never actually fetched must come
back as a distinct non-terminal failure (e.g. `FETCH_FAILED`), not as "no
data" or "off," so a later run retries it instead of silently treating a
gap as a checked-and-empty result.

**Current settings** (the reference values -- update here first, then
propagate):
- 0.4s between requests (flat throttle, independent of any rolling-window
  check).
- On a rate-limit-shaped error specifically (`fibo.download.looks_rate_limited`
  -- not on any other error, and not on a token-expiry-shaped error, which
  needs a re-login instead, not a wait): exponential backoff starting at 2s,
  doubling, capped at 30s, up to 5 retries before giving up on that request
  for this run.
- The Angel One instrument/scrip master (`OpenAPIScripMaster.json`, tens of
  MB, does not change intraday) is downloaded at most once per IST calendar
  date and cached to disk; every call that date reuses the cached copy.

**Audit of every module that calls Angel One, against these settings:**

| module | throttle | rate-limit handling | scrip master |
|---|---|---|---|
| `scripts/fibo_morning.py` (`fetch_candle_with_retry`) | 0.4s | matches: exponential backoff 2s->30s, 5 retries, `FETCH_FAILED` on exhaustion, never `SETUP_OFF`/checked | does **not** cache -- calls `fibo.download.resolve_entity_tokens`, which re-downloads the full master on every call (up to 3x in one run: once each from `phase1_setups`, `watch_for_triggers`, `resolve_outcomes`, whenever any setup is active) |
| `scripts/fibo_evening.py` | n/a | n/a | n/a -- never imports or calls Angel One; the daily bar comes from NSE bhavcopy |
| `scripts/snapshot_spreads.py` (spread monitor) | n/a -- one `getMarketData` call per invocation | **does not retry** on a rate-limit error; fails the run and returns a non-zero exit without writing any row, so it does not violate "never record a failed fetch as a result," but it also doesn't back off and retry within the same run the way the stated rule intends | matches: uses `spread_monitor.tokens.resolve_tokens`, cached per IST date |
| `scripts/fibo_download_intraday.py`, `scripts/fibo_download_intraday_top200.py` (bulk historical backfill) | 0.4s, plus a rolling-window self-throttle (140/min, 4500/hour) | **deliberately different, not a bug**: STOPS IMMEDIATELY on the first rate-limit-shaped error rather than backing off and retrying -- a one-shot resumable backfill where stopping costs nothing (the next run picks up every chunk not already logged `ok`), so the chosen tradeoff is "never risk hammering a limited key further" over "retry in place." Still correctly never logs a stopped chunk as done. | does **not** cache -- same `resolve_entity_tokens` call as the morning job, once per run |

**Two things to fix to bring every module into line with the stated
settings:** (1) `fibo.download.resolve_entity_tokens` should cache the
scrip master to disk per IST date, the same way `spread_monitor.tokens`
already does, instead of re-downloading the full master file on every call;
(2) `snapshot_spreads.py`'s single `getMarketData` call has no backoff/retry
at all on a rate-limit error -- it simply fails the run. Neither has been
changed yet; recorded here so the fix is deliberate rather than
rediscovered mid-incident.

## `getMarketData` hard-limits at 50 tokens per call -- undocumented anywhere in this project before now

Confirmed LIVE, 2026-10-12, binary search against the real API while
building `src/options_depth/`: `getMarketData` returns error **`AB4029`
"Tokens max limit exceeded"** for 51 tokens in one call (any mix of
exchanges in the request dict), and succeeds at exactly 50. Not a rate
limit (no backoff fixes it, no `looks_rate_limited`-shaped error) -- a
hard per-call cap, distinct from every throttle/backoff setting in the
section above. `scripts/snapshot_options_depth.py` is the one caller that
chunks for this (`CHUNK_SIZE = 50`, confirmed against the live boundary,
not guessed).

**Audit of every other `getMarketData` call site in this project** (found
by grepping for the literal call, not inferred):

| call site | tokens in that call | margin to 50 |
|---|---|---|
| `scripts/fibo_morning.py` (`confirm_trading_day`) | 1 (Nifty 50 index only) | **48/50 free -- no exposure.** Nothing about this call ever grows with the watchlist; it only ever checks the index. |
| `scripts/snapshot_spreads.py` | `len(token_map) + 1` -- currently 20 symbols (`config/spread_monitor_symbols.txt`) + the Nifty index = **21** | **29 tokens of headroom, UNGUARDED.** Nothing in `snapshot_spreads.py` or `spread_monitor.tokens.resolve_tokens` chunks, checks, or even warns if the config file's symbol count grows past 29 more entries (50 total). At 50+ tokens the ENTIRE call fails with `AB4029` and the run records zero rows, silently, for every symbol -- not a partial failure, a total one, and nothing currently watches for it. Not fixed here (not asked for, and the current 20-symbol research list is a deliberately curated, individually-commented sample, not something likely to silently grow past 29 more entries by accident) -- but flagged with its exact margin so whoever next edits that config file does so knowing the ceiling exists. |
| `scripts/snapshot_options_depth.py` | chunked at 50, by design | n/a -- the one caller built with this limit already in mind. |

## `data/fibo_live/v1/events.jsonl` is tracked in git -- the one deliberate exception to the data/ ignore rule

Every other file under `data/` is gitignored, for a licensing reason: most
of it is NSE market data (bhavcopy, index closes, fundamentals), and this
project does not redistribute that. `events.jsonl` is different in kind,
not just in size -- it is the Fibo live paper-trading system's entire
evidence trail (every evening watchlist, every morning setup/trigger/
outcome, `src/fibo_live/eventlog.py`), which is:

- **this laptop's own paper-trading decisions**, plus a small number of
  prices derived from them for display -- not a redistribution of NSE's
  datasets. The licensing rationale for ignoring the rest of `data/` does
  not apply to it.
- **the forward test itself**, with exactly one copy, on one laptop that
  has already crashed twice in a single week. Losing this file does not
  just lose data -- a forward test that has to be re-logged from scratch
  after a crash is not the same test anymore; a re-logged signal after the
  fact proves nothing about whether it was known before its outcome.
- **made credible by git's own commit timestamps**: a forward test's whole
  claim to being forward (not hindsight re-labeled as foresight) rests on
  the signal having been recorded before the outcome existed. A git commit
  is independent, third-party-timestamped evidence of exactly that, the
  same way the event log's own `ts` field is (`eventlog.py`'s docstring),
  but backed by something other than this one laptop's clock.

**Mechanics**: `.gitignore` un-ignores this one path with a chain of
negation patterns walking back down through every parent directory
(`/data/*` -> `!/data/fibo_live` -> `/data/fibo_live/*` -> `!/data/fibo_live/v1`
-> `/data/fibo_live/v1/*` -> `!/data/fibo_live/v1/events.jsonl`) -- per
gitignore(5), a single negated pattern on a file inside an otherwise-
ignored directory does not work; every ancestor directory has to be
un-ignored and re-ignored in turn. Nothing else under `data/` is affected;
confirmed with `git status` after staging only this one path.

**Kept current automatically, from BOTH jobs, not just the evening one**:
`scripts/fibo_evening.py` AND `scripts/fibo_morning.py` each call
`fibo_live.git_sync.sync_events_log_to_git` once at the very end of their
own run (after `run_unattended`, so it fires whether that run produced new
events, skipped idempotently, refused early, or crashed with an unhandled
exception -- whatever got appended before any of those outcomes still
gets backed up).

Syncing only from the evening job would defeat the whole timestamp
argument above for anything the MORNING job writes -- setup, trigger, and
outcome events. The evening job runs once, after close; the morning job is
what logs a stock going SETUP ON around 09:30 and a trigger firing some
minutes after that, all DURING market hours, with that trade's own outcome
not yet known. If the only sync point were 18:30 that evening, the first
git commit touching that setup event would already postdate its outcome
(resolved by 15:15 the same day) -- at that point git's timestamp proves
nothing a human claiming to have logged it after the fact couldn't also
claim. Committing right after each morning run, instead, gives that setup
a commit timestamp from while the trade was still live -- independent
evidence it really was recorded before the outcome existed, which is the
specific thing a forward test needs and the only reason this sync exists.

Each call stages the file, commits only if something actually changed,
and pushes. Every step is best-effort: a failed `git add`/`commit`/`push`
(no network, no upstream, a hook rejecting the commit, git itself
missing) is logged and the job still exits normally -- this sync must
never be the reason a scheduled run is reported as failed, and a missed
push just means the laptop is carrying one more unpushed commit for next
time, not lost data (the file itself is still safe on
disk; only the off-laptop backup is delayed).

## An ETA built from the throttle sleep alone, not a measured per-item cost -- BUGS.md Bug #4's exact mistake, recurring

**The estimate**: the NIFTY-options backfill (`scripts/backfill_nifty_options.py`)
was projected at ~73 minutes for ~2,676 trading days, built from 12
isolated sample fetches (OPTIONS_HISTORICAL_FEASIBILITY.md) averaging
~0.84s/request, plus the standard 0.8s politeness sleep -- call it
~1.6s/file.

**What actually happened, measured from the real run's own heartbeat
log** (`data/options_history/backfill.log`): a sustained ~9-10s/day
across several consecutive 50-day intervals, no errors, nothing
anomalous -- just slower, by roughly 6x, for the whole run. Projected
total: **~6.5 hours, not 73 minutes.**

**Same mechanism BUGS.md's Bug #4 already named**: "the original ETA had
implicitly assumed the throttle sleep WAS the per-document cost, with no
allowance for real request latency at all." The 12 samples here were
each a single, isolated, spaced-out request (with this assistant's own
processing time as an unplanned extra gap between them) -- not a
measurement of what the SAME archive does to a few thousand back-to-back
requests from the same IP in one sustained run. An isolated-request
timing is not evidence about sustained-throughput timing; Bug #4 already
established this and it recurred anyway because the ETA was built before
re-reading that entry.

**Unconfirmed but worth testing before the next similar job**: Bug #4's
own fix had two parts, and only the throttle-vs-real-cost half of the
lesson was applied here. The other half -- `src/data_layer/prices_nse.py`'s
own equity fetcher (and this new F&O fetcher, `src/options_history/
fetch.py`, which copies its shape) both call bare `requests.get()` per
request, never a reused `requests.Session()`. Bug #4 measured a 6.4x
speedup from exactly that swap, on a different host. This was NOT
re-measured here -- deliberately, to avoid adding a second burst of
parallel load against NSE while the real backfill was already mid-run
against it -- so it is a plausible contributing cause, not a confirmed
one. Worth an isolated measurement (same-host, back-to-back, with vs.
without a shared Session) before the next bhavcopy-scale backfill's ETA
is quoted, rather than assumed fixed or assumed irrelevant.

**The fix for THIS kind of estimate, going forward**: time a real
SUSTAINED sample first -- several dozen consecutive requests against the
actual target, back to back, at the actual intended throttle -- before
quoting an ETA for anything in the hundreds-to-thousands of requests.
A handful of isolated single-shot timings is what produced both this
miss and Bug #4's.

## The Fibo evening job missed its 18:30 run -- NOT a lock conflict with the options backfill, there is no scheduled trigger for it at all

**Hypothesis going in** (the user's own, reasonable given the backfill was
running the entire evening): the options backfill holds a write lock on
the same DuckDB file the evening job needs, so the 18:30 run either
failed or was blocked. **Checked, ruled out**: the backfill writes only
to `data/options_history/options_history.duckdb`
(`src/options_history/db.py::DB_PATH`) -- confirmed live, twice, by
successfully opening `data/warehouse.duckdb` in a separate connection
while the backfill was actively running. No lock contention is possible
between these two files; DuckDB locks per-file, not per-process.

**What actually happened**: `data/fibo_live/scheduler.log` has no entry
at all between the 09:32:34 morning-job run and this incident -- not a
refusal, not an error, nothing. `Get-ScheduledTask` confirms why: **no
Task Scheduler entry exists for `fibo_evening.py` or `fibo_morning.py`,
and never has.** Every run of either script, this entire project, has
been triggered manually. 18:30 did not fail -- nothing was listening
for 18:30 in the first place, and nobody happened to run it by hand that
evening because attention was on the backfill.

**This is BUGS.md Bug #13's exact meta-pattern recurring one layer up**:
Bug #13 found this project has no scheduled ingestion runner of any kind
and that a silent 13-day gap went unnoticed for exactly that reason. The
evening/morning jobs have the identical gap -- they only run when a
human remembers to run them -- and it took exactly one evening of
divided attention to prove it. `scripts/snapshot_options_depth.py` (this
same session) is the one script in this project that actually has a
real Task Scheduler entry; `fibo_evening.py`/`fibo_morning.py` do not,
despite both having the unattended-logging/never-crash machinery
(`scheduler_support.py`) that ASSUMES something external is triggering
them on a schedule.

**Compounding effect, found while fixing it**: by the time this was run
(just after midnight, now the next calendar day), the gap between real
wall-clock "today" and the warehouse's last-ingested date had grown past
`assert_data_current`'s 3-day tolerance, so Bug #13's own staleness
guard correctly refused to run at all -- a second, independent
consequence of the same missed run, not a new bug. Unblocking it needed
a manual bhavcopy ingestion for the missed day before the evening job
would proceed. A scheduled 18:30 trigger would never have let this gap
open far enough to hit that guard in the first place.

**UPDATE, 2026-10-13: fixed for the evening job.** `FiboEvening` now
exists (weekdays 18:30, runs on battery, does not wake the machine, runs
only when logged on, starts in `C:\projects\trade-new`) -- created with
`schtasks /create /tn FiboEvening /xml scripts/_fibo_evening_task.xml`
and verified against its own registered settings with
`schtasks /query /tn FiboEvening /xml`, not just the creation command's
exit status. Full detail: BUGS.md Bug #17 (this gap) and Bug #16 (the
staleness-guard-ordering bug it exposed as a second, independent
consequence). **The morning job still has no scheduled task** -- not
asked for yet, flagged in Bug #17.

## The morning job is moving to GitHub Actions -- ONE owner only, never both

**In progress, 2026-10-13/14.** `scripts/fibo_morning.py` is moving to a
scheduled GitHub Actions workflow (`.github/workflows/`) instead of a
local Task Scheduler entry, so it runs even when the laptop is closed.
This required three prerequisite fixes, all landed:

1. **Explicit IST everywhere on the morning path.** `detect_run_mode`,
   the morning job's own trigger/outcome time-window checks, and
   `append_event`'s `ts` stamp all used to default to the HOST machine's
   local clock (`dt.datetime.now()`/`dt.date.today()`), correct only by
   coincidence because the laptop's OS clock happens to be IST. A GitHub
   Actions runner's clock is UTC. Fixed to compute IST explicitly
   everywhere on this path, verified by a test that fakes a UTC-clock
   host and checks the decisions are still IST-correct (see
   `tests/test_fibo_live_clock.py`, `tests/test_staleness.py`).
2. **No warehouse dependency.** The morning job used to open
   `data/warehouse.duckdb` for two things: a staleness check, and
   resolving each stock's Angel token via `isin_lineage`/`prices_eod`.
   Both are gone -- replaced by `assert_watchlist_current` (did the
   evening job log a `watchlist_run` targeting today, in `events.jsonl`,
   recently enough to trust) and `spread_monitor.tokens.resolve_tokens`
   (resolves straight from the `symbol` already on the watchlist event,
   against Angel's own instrument master -- no DB connection at all).
   NSE price data and the warehouse file itself never need to reach any
   machine running this job that isn't the laptop.
3. **`git pull --ff-only` as the first thing the evening job's `main()`
   does**, before any `append_event` call (`fibo_live/git_sync.py`'s
   `pull_before_appending`) -- so a day the GitHub-Actions-run morning
   job has already pushed commits, the laptop's evening run starts from
   that state before appending its own lines, keeping every push a
   clean fast-forward. Unlike the existing push (best-effort, swallowed
   on failure), this one raises and aborts the run on failure.

Probe workflow (`.github/workflows/probe_github_actions.yml`,
workflow_dispatch only) confirmed, 2026-10-13: Angel One login OK from a
GitHub Actions runner, the IST clock computation correct, outbound email
OK, scrip-master download ~5.5s (no caching needed).

**ONE OWNER RULE, once the real schedule is enabled: `fibo_morning.py`
must never be run on the laptop again.** Both the morning job's own
idempotency (skips anything already logged for today) and the evening
job's pre-run pull assume there is exactly one place committing
`setup`/`trigger`/`outcome`/`notification` events during market hours.
Running it from both the laptop and GitHub Actions on the same morning
does not corrupt anything outright (idempotent skips still apply by
entity+trade_date), but it reintroduces the exact non-fast-forward-push
risk item 3 above exists to eliminate, for no benefit. If the morning
job is ever run manually for debugging, do it with `--date` against a
past date and do NOT let its git_sync push run (or push manually and
reconcile) -- never as a stand-in for a day the schedule already covers.

## The morning job schedule went LIVE 2026-10-16

The manual `workflow_dispatch` run on 2026-10-14 confirmed the job
behaves correctly on a GitHub Actions runner (LIVE mode, watchlist
freshness check OK, 16 stocks fetched, git sync pushed, zero setups).
The `schedule:` trigger itself, though, was never uncommented until
2026-10-16 -- so **2026-10-15 and 2026-10-16 are known gaps**: nothing
ran the morning check on either day. Recorded honestly as two
`session_status`/`MISSED` events in `events.jsonl` (appended, not
backfilled as `SETUP_OFF` for any stock -- a stock whose ORB was never
checked must never be recorded as if it had been). If either morning is
ever replayed from stored 1-minute data, that is a separate run with
`run_mode=REPLAY`, reported as replay evidence, never live evidence.

Three fixes landed before the schedule was uncommented:

1. **Skip-resolved idempotency confirmed, and tested.** `phase1_setups`
   already split resolved rows (a terminal `SETUP_ON`/`SETUP_OFF` already
   logged today) from rows needing a fetch *before* calling
   `resolve_tokens_for_rows` -- a fully-resolved run now makes no Angel
   One call of any kind in that function, not just skips the candle
   fetch. `watch_for_triggers`/`resolve_outcomes` already restricted
   themselves to `setup_on == True` rows and skipped anything with an
   existing trigger/outcome event. `tests/test_fibo_morning_idempotency.py`
   covers all of this, including the actual 16-stock-all-`SETUP_OFF`
   shape of the 2026-10-14 run, with a client stub that raises if
   `getCandleData` is ever called.
2. **ORB fetch throttle raised to 0.8s** (`ORB_THROTTLE_SECONDS`,
   `scripts/fibo_morning.py`) -- the 2026-10-14 run hit rate limits on
   most of 16 stocks (LAURUSLABS exhausted all 5 retries), because every
   ORB fetch happens back-to-back in one burst at the start of the run.
   The trigger-watch and outcome-resolution passes keep the original
   0.4s (`THROTTLE_SECONDS`) -- they are naturally spread across re-runs,
   not one burst. 16 stocks at 0.8s throttle alone is ~12.8s; this is a
   calculated lower bound on the ORB pass's duration, not a measured one
   (no live market session was available to re-run this against) -- see
   this file's own "ETA built from the throttle sleep alone" entry for
   why a throttle-only number is a floor, not an estimate, of real
   per-request latency. Confirm the real figure the next time this job
   actually runs against a live market with several stocks queued.
3. **Git sync commit message now names the job.** `sync_events_log_to_git`
   took a hardcoded "Fibo evening events" message regardless of which job
   called it; it now takes a `job_label` parameter, and the morning job
   passes `"Fibo morning events"` so its own commits are distinguishable
   from the evening job's in `git log`.

## Watchlist freshness was judged by elapsed hours, not by what actually matters

Found before it ever caused a real incident, checking the schedule
ahead of 2026-10-19: `assert_watchlist_current` refused to run unless a
`watchlist_run` targeting today had been logged within the last **36
hours**. A Friday-evening run targeting the following Monday is,
correctly, about **63 hours old** by 09:30 Monday -- the evening job
runs once per trading night by design, so this check would have
refused **every single Monday**, including the real one already queued
up in `events.jsonl` for 2026-10-19.

Fixed by judging the relationship that actually matters instead of
elapsed time: a `watchlist_run` exists whose `target_trade_date` is
today AND whose `as_of_date` is today's own previous trading day
(`previous_trading_day`, `scripts/fibo_morning.py`) -- weekend- and
NSE-holiday-aware, via `data_layer.nse_holidays.is_nse_holiday`. This
still catches the real failure mode the 36-hour check was built for
(BUGS.md Bug #13's meta-pattern -- a multi-day gap in the evening job,
where the logged `as_of_date` is genuinely stale data, not just an
old-looking timestamp), without being fooled by an ordinary weekend.
Verified against the real `events.jsonl`: the already-logged Friday run
for 2026-10-19 (`as_of_date=2026-10-16`) now passes; the old rule would
have refused it. 10 tests, `tests/test_fibo_morning_watchlist_freshness.py`.

**One residual, explicitly flagged gap, not fixed by this change
alone** (closed separately below): `previous_trading_day` falls back to
weekend-only skipping when the NSE holiday calendar can't be confirmed
(`HolidayCalendarMissing`). On a GitHub Actions runner that never had
any holiday calendar at all, a weekday holiday the Friday before a
Monday would have been mistaken for an ordinary trading day, and the
Monday run would have wrongly refused a genuinely fresh watchlist built
from Thursday's data instead. See "Holiday calendar now reaches the
runner" immediately below.

## Durable refusal logging: a refusal is now recorded in events.jsonl, not just printed

**The gap**: every refusal (`assert_watchlist_current` raising, a login
failure, `confirm_trading_day` finding today unconfirmed as a trading
day) was logged only via `log()` -- stdout, plus
`data/fibo_live/scheduler.log`. On a laptop that file persists; on a
GitHub Actions runner it lives only on that ephemeral runner and is
never committed, so the only durable trace of a refusal was that one
run's own entry in GitHub's Actions log (retained for a limited window,
not pushed anywhere, not visible from `git log` or `events.jsonl`). This
is the exact ambiguity that made the 2026-10-15/2026-10-16 gap (above)
need a manual, after-the-fact backfill: nothing in the committed
evidence trail distinguished "the evening job never ran" from "the
morning job ran and refused" from "the morning job ran and found a
quiet, zero-setup morning."

**The fix**: every refusal path in `main()` now funnels through
`log_refusal` (`scripts/fibo_morning.py`), which still logs to
scheduler.log/stdout as before AND appends a `session_status` event
(`src/fibo_live/session_status.py`) to `events.jsonl` -- committed and
pushed by the same `sync_events_log_to_git` call that already runs
after every run, refusal or not. Fields: `trade_date`, `session`
(`"morning"`), `status`, `reason`, `run_mode`.

`status` is `NON_TRADING_DAY` when `trade_date` is confirmed not a
trading day (a weekend, or an NSE holiday confirmed by
`is_nse_holiday`) and `REFUSED` otherwise -- so a holiday reads
differently, at a glance, from a genuinely missed or broken evening
job. An unverifiable day (`HolidayCalendarMissing`) is never assumed to
be a holiday, so it logs `REFUSED`, not `NON_TRADING_DAY` -- consistent
with `nse_holidays.py`'s own fail-safe stance.

Deduplicated on `(trade_date, session, reason)`: the `*/15` cron fires
every 15 minutes all morning, and a schedule re-hitting the identical
refusal must log it once, not nine times. 16 tests across
`tests/test_fibo_live_session_status.py` (the dedup/record logic in
isolation) and `tests/test_fibo_morning_refusal_logging.py` (including
`main()` itself refusing on an ordinary weekday with no watchlist at
all -- the actual Monday-with-no-watchlist shape -- and on a weekend,
and twice in a row to prove the dedup holds end-to-end).

## Holiday calendar now reaches the runner

**The gap**: `data_layer.nse_holidays.is_nse_holiday`'s only data
source, `data/raw/nse_cm_holidays.pkl`, is deliberately not committed
to git -- each environment keeps its own copy. A GitHub Actions
runner's fresh checkout never has one, so every call raised
`HolidayCalendarMissing` there, and every caller that degrades
gracefully on that (`previous_trading_day`, `is_non_trading_day`) was
silently running in weekend-only mode in production, the whole time.

**The fix**: `data/raw/nse_cm_holidays_fallback.json` -- a trimmed copy
of the same source, dates only (the pkl carries no holiday names
either, so none were lost by trimming) -- is now committed (`.gitignore`
carves out this one path the same way it already does for
`data/fibo_live/v1/events.jsonl`). `nse_holidays.py`'s `_load` prefers
the full pkl when present (more years, the laptop's own source of
truth) and falls back to this JSON otherwise.

**Known limitation, stated plainly**: the source pkl only covers
2016-2026 -- there is no 2027 data anywhere in this project to trim
from, so the committed fallback covers **2026 only**. A holiday check
for any 2027 date will raise `HolidayCalendarMissing` on a runner
without the pkl (degrading to weekend-only, same as before) until
someone extends the fallback file with real 2027 NSE holiday dates
before 2027 starts mattering to this schedule. Flagged here rather than
quietly left for next December to discover. **Update, 2026-10-16**: the
2027 NSE holiday calendar is not yet in the fallback file -- `next_trading_day`
logs a warning and falls back to reactive detection for 2027 dates; to be
added from NSE's own holiday circular before January 2027. 6 tests,
`tests/test_nse_holidays.py`, including the fallback resolving
2026-10-20 (a real, confirmed-live NSE holiday) correctly with no pkl
present at all -- the actual runner path.

## What to check on the first fully automatic Monday (2026-10-19)

1. **The cron actually fired.** Check the Actions tab for "Fibo morning
   job" runs between 04:00-06:00 UTC and again at 09:45/10:00 UTC on
   2026-10-19 -- a schedule that silently never fires (GitHub disables
   scheduled workflows on a repo with no activity for 60 days, not a risk
   here, but worth the first-time check) would recreate exactly the gap
   this section just closed.
2. **The runner image is actually `ubuntu-24.04`**, not whatever
   `ubuntu-latest` would have become on this exact date (GitHub's Ubuntu
   26 migration lands 2026-10-19) -- check the run log's "Set up job"
   step reports `24.04`.
3. **Watchlist freshness check passes** against Friday night's evening
   run (confirm the evening job's `watchlist_run` event for 2026-10-19
   has `as_of_date=2026-10-16` -- see "Watchlist freshness was judged by
   elapsed hours, not by what actually matters" below for why this is no
   longer an hours-based check).
4. **At least one `setup` event gets logged** for 2026-10-19, and its
   `status` is `SETUP_ON`, `SETUP_OFF`, or `FETCH_FAILED` -- never a
   missing row for a watchlist stock (that would mean the run refused
   early or crashed silently).
5. **No `FETCH_FAILED` survives past the last scheduled run of the
   morning** -- the 0.8s ORB throttle should mean most stocks succeed on
   the first attempt now; if several still exhaust all 5 retries, the
   rate limit is tighter than 0.8s/request handles and needs another
   look (see this file's "Angel One rate limiting" section).
6. **`git log` shows a "Fibo morning events" commit** (not "Fibo evening
   events") pushed during market hours, and the evening job's own commit
   that night still fast-forwards cleanly on top of it.
7. **No duplicate/overlapping run**: confirm nobody also ran
   `scripts/fibo_morning.py` on the laptop that morning -- the ONE OWNER
   RULE above.
8. **Tuesday 2026-10-20 should refuse with `NON_TRADING_DAY`, not
   `SETUP_OFF`/`SETUP_ON`.** Confirmed live against the holiday
   calendar while building this: 2026-10-20 is an NSE holiday. The
   schedule still fires that morning (cron doesn't know about holidays,
   only weekday-vs-weekend); the job should log a `session_status`
   event with `status=NON_TRADING_DAY` and exit without any per-stock
   events, not a stale-watchlist `REFUSED` and not a quiet `SETUP_OFF`
   morning. If it instead shows `REFUSED`, the holiday calendar isn't
   being consulted correctly on that runner -- check whether
   `data/raw/nse_cm_holidays_fallback.json` was actually in the checkout
   for that run.
9. **Every `session_status` event that does appear in `events.jsonl`
   this week should have `session=morning` and a `reason` that matches
   what the run log says** -- durable refusal logging (below) means a
   refusal is no longer only visible in a GitHub Actions run log that
   expires; spot-check that the git-committed copy and the Actions run's
   own stdout agree.
