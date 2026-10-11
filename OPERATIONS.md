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

**Kept current automatically**: `scripts/fibo_evening.py` calls
`fibo_live.git_sync.sync_events_log_to_git` once at the very end of every
run (after `run_unattended`, so it fires whether that run produced a new
watchlist, skipped idempotently, refused on stale data, or crashed with an
unhandled exception -- whatever got appended before any of those outcomes
still gets backed up). It stages the file, commits only if something
actually changed, and pushes. Every step is best-effort: a failed `git
add`/`commit`/`push` (no network, no upstream, a hook rejecting the
commit, git itself missing) is logged and the job still exits normally --
this sync must never be the reason a scheduled run is reported as failed,
and a missed push just means the laptop is carrying one more unpushed
commit for next time, not lost data (the file itself is still safe on
disk; only the off-laptop backup is delayed).
