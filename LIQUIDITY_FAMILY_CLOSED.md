# Liquidity confluence family: CLOSED

## Final tally

**4 DEV failures** — Studies A, B, C, D, each reached a pre-registered
gate and failed it, each passing both nulls at the 100th percentile.

**2 Phase 1 abandonments** — Study E (timeframe comparison), closed
before preregistration: the reclaim window's real-time width varied
silently with the sweep timeframe, so no outcome could be attributed to
timeframe alone — confounded. Study F (hourly structure, 5-minute
confirmation), closed before preregistration: fixing the window's width
left its start uncontrolled, so the comparison was not merely confounded
but unidentifiable — no amount of data could have resolved it.

**1 withdrawn measurement** — the Study F rejected-buckets measurement
(`MEASUREMENT_F_REJECTED_BUCKETS.md`), which failed its own arithmetic
reconciliation against Phase 1 and was withdrawn as a selective-sampling
artifact, not retried.

No seventh trial is open. This file is the closure record.

## Why the family closes here, not just this trial

**Every configuration's selected trades landed in the same -0.1% to
-0.3% band as the eleven other intraday strategies tried in this
project** (`PROJECT_CONTEXT.md` §8's own structural finding) — Darvas
boxes, Fibonacci zones, volume profile, fair value gaps, IPO openings,
liquidity sweeps, all different logic, all landing in the same place.
That consistency was never eleven bad ideas; it is one constant seen
through eleven lenses, and the liquidity family's own four completed
trials are four more lenses on the identical constant, not four
independent chances at a different one.

**All four DEV failures passed both nulls at the 100th percentile.**
The entry mechanism carries real, non-random selection value in every
one of them — this was never a case of a strategy with no signal at
all. The problem was never "can this mechanism find anything," it was
"is what it finds worth more than it costs," and the answer was no,
repeatedly, at the 100th percentile of confidence that something real
was being selected.

**An exit fix was already ruled out, not merely untried.** Across
32,515 Liquidity trades (`PROJECT_CONTEXT.md` §8): the strategy's own
stop is touched within 10 days on 84-86% of all trades; of same-day
stop-outs, 69-73% eventually reach 1.5R; but when both the stop and the
3R target are eventually reached, the stop arrives first 2.6-3.3x as
often. Direction was frequently right — the path made it unharvestable.
Held with no stop at all, the mean return stays negative at both 10 and
30 days, with worst-case single trades of -87% (long) and -155%
(short). There is no exit rule hiding in this data that rescues the
entry; the one measurement built to check for it came back negative in
every direction tried.

**A horizon fix was already ruled out, not merely untried.** POC V5
held 10 days instead of intraday and did worse, not better
(-0.6302%, worse than every intraday POC variant) — delivery costs are
higher than intraday costs, and overnight gaps bypass stops entirely.
The liquidity family's own entry mechanism is exit- and horizon-
identical to POC V4, which already carries this result by construction.

**Selection, exit, and horizon have each been attacked separately in
this project, by different studies, and the distribution did not
move.** Study C and Study D each attacked selection directly (requiring
more confirmation before entry) and each made the entry's own follow-
through worse, not better, while discarding trades that were -- on
average -- winners. POC V5 attacked horizon and made it worse. The
±10/30-day stop-touch measurement attacked exit and found no slack.
Three different levers, three different studies, one result each time.

## No Study G

**A seventh trial in this family needs a new mechanism, not another
filter.** Every filter tried in this family (retest, ascending lows,
timeframe) narrowed WHICH trades the same underlying sweep-and-reclaim
mechanism selects. None of them changed what that mechanism is. The
family's own four completed trials and two abandonments have now
exhausted the reasonable filter space around one mechanism without
finding edge; narrowing further is not expected, on this project's own
calibration record, to behave differently than the last four attempts
did. The family is closed.
