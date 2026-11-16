# Post-earnings-drift: Phase 0 (feasibility and power only)

**This is NOT a preregistration and NOT a study.** No relationship between
announcement return and forward return is computed anywhere in this
document. That computation is the study itself, and per this project's own
rule (`PROJECT_CONTEXT.md` Section 3, "Pre-registration"), it needs a frozen,
committed preregistration before any such number exists. This document is
counting and power arithmetic only, on the unsealed portion of the data, to
decide whether a preregistration is even worth writing.

---

## 0. Sealed-window declaration (committed before anything else below)

**Earnings events with `known_date`/`broadcast_ts` on or after 2025-07-01
are SEALED for the post-earnings-drift hypothesis family, effective this
commit.**

Declared now, in its own commit, before any backfill script runs and before
any of the Phase 0 analyses below are computed — following this project's
own standing discipline (`PROJECT_CONTEXT.md` Section 3, "Sealed windows":
read once, after DEV passes and the human approves; declared before touched,
not after).

**Honest statement of contamination — partial, not zero:**

The *price* data for 2025-07-01 onward is not unknown. Daily and intraday
bars for this period were already loaded and used in the momentum holdout
evaluation (`FINDINGS.md` Section 7) and in the live Fibo/momentum forward
systems. Market conditions in this window — levels, volatility, the general
shape of the tape — have been seen, repeatedly, by other work in this
project.

What has genuinely never been loaded or examined, by any script, study, or
person, in this project, is the **earnings-event data itself**: which
companies filed on which dates, the `broadcast_ts`/`known_date` timestamps,
the financial content of those filings, or anything derived from joining
those events to subsequent price action. `fundamentals_filings` and
`fundamentals_xbrl_facts` rows with `known_date >= 2025-07-01` have not been
queried, joined, or aggregated anywhere before this document.

So: the environment the events sit in is known; the events themselves are
not. That is a weaker seal than the original historical holdout had (which
sealed both price and event data together), and this document says so
plainly rather than claiming an unseen window where only a partial one
exists.

**This is the only unseen data available to this hypothesis family, and it
stops being claimable as unseen the moment the fundamentals backfill is next
run and it pulls in rows past this date, or the moment any script queries
`fundamentals_filings`/`fundamentals_xbrl_facts` with `known_date >=
2025-07-01`.** Everything in this document (Sections 1-5 below) is computed
only against `known_date < 2025-07-01` (equivalently, the window 2016-01
through 2025-06), using data already resident in `data/warehouse.duckdb` as
of this commit. No backfill is run as part of this document.

Recorded in `data/holdout_access_log.txt` alongside the retired windows
(see entry timestamped at this commit).

---

## 1-5. Feasibility and power analyses (2016-01 through 2025-06 only)

[Filled in below, in the same commit sequence, after the sealing
declaration above has landed on its own.]
