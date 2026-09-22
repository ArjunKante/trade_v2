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
