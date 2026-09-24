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
