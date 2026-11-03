# Liquidity confluence, Study C (retest confirmation): experiments log

Companion to `PREREGISTRATION_LIQUIDITY_C.md` (frozen rules, commit
`ffaa7ca`). Liquidity family, trial 3. Records what was actually run and
found, per the preregistration's own Process section.

## Synthetic unit tests (Process Step 2 precursor)

`scripts/liquidity_c_unit_test.py` -- pure-function scenarios, no DB
access: `find_retest_long`/`find_retest_short` against synthetic 5-minute
candles covering the two-candle retest, the same-candle (single-bar
touch-and-close) retest, `RETEST_FAILED` (a breach of the original sweep
extreme before any valid retest), and `NO_RETEST` (both "never returns
to the zone" and "returns but never recloses") for each direction. **All
9 checks passed** (one round of test-data correction was needed first --
the initial scenario data set reclaim/pullback prices so close to the
zone that a pullback candle's own close was already trivially above the
zone price, confirming nothing about the sequencing logic; caught by
re-deriving the expected result by hand before trusting the test, not
after, and fixed before any real-data trace).

## Hand-traced examples (Process Step 2), 5 per side, 10 total

All 10 required shapes -- `NO_RETEST`, `RETEST_FAILED`, `FULL_EXIT`,
`STOP_NO_HALF`, `HALF_THEN_TIME_EXIT`, for LONG and for SHORT each --
found by `scripts/liquidity_c_handtrace.py` against the real DEV window,
**all ten on the very first entity scanned** (`INE002A01018`), the same
entity every one of Study A's and Study B's own hand-traces also used.

**One direct cross-check against Study A's own already-verified
numbers, worth recording explicitly**: Study C's own `STOP_NO_HALF`
(long) example is `INE002A01018`, 2017-05-18 -- the EXACT SAME entity,
date, zone (`zone_price=1340.6250`, members `('1d','1w')`), sweep
(`sweep_idx=8`), and reclaim (`reclaim_idx=10`) as `LIQUIDITY_A_
FINDINGS.md`'s own `STOP_NO_HALF` hand-trace. This is expected, not a
coincidence to investigate -- Study C reuses Study A's own unchanged
sweep/reclaim detection, so the same day necessarily produces the same
setup up to that point. What differs, and was checked by hand: Study C's
own retest candle (idx 11, 10:10) pulls the fill one 5-minute bar later
than Study A's own (10:05 vs. Study A's 10:05 reclaim-based fill -- the
retest adds exactly one candle's delay here), landing at **entry =
1340.7050** (vs. Study A's own 1340.9886) while the **stop is identical,
1332.6486** -- confirming by direct comparison, not just by reading the
code, that Study C's own stop correctly uses the ORIGINAL sweep extreme
(`final_sweep_low = 1335.5191`, matching Study A's own hand-traced value
exactly) and not any level touched during the retest. Both studies'
version of this trade resolve the same way here (`STOP_NO_HALF`), since
the stop is unchanged and price moved against the position regardless of
the few extra minutes' delay.

**All ten hand traces are internally consistent with the preregistration
exactly as written.** The retest sequencing (two-candle and same-candle
confirmation, each exercised live, not only in the synthetic test), the
`RETEST_FAILED` breach check against the ORIGINAL sweep extreme (both
sides), the `NO_RETEST` timeout, the recomputed-R target formulas off
the later entry, and the unchanged exit mechanics (`FULL_EXIT`,
`STOP_NO_HALF`, `HALF_THEN_TIME_EXIT`, all three shapes, both
directions) were each exercised and spot-checked by hand before any
aggregate number was computed.

## DEV result: FAILS, both sides -- no edge, same shape as A and B

**A units bug found and corrected before trusting one derived figure,
stated here rather than silently fixed**: `scripts/liquidity_c_dev_run.
py`'s own `filtered_out_trades.vs_actual_c_mean` field subtracted a raw
fraction (`fout_mean`, e.g. `-0.008856`) from a percentage (`mean_net_r
* 100`, e.g. `-0.2694`) -- a factor-of-100 units mismatch that produced
a number (`+0.2606`) that happened to look plausible at a glance but was
not the real gap. **Not used by any gate decision** (the gate never
reads this field) -- caught re-deriving it by hand before writing this
section, not after. The corrected figures below are computed directly
from the two correctly-scaled percentage means, not from that field.

### Gate, both sides -- 3 of 4 fail, identical shape to A and B

| Condition | LONG | SHORT |
|---|---|---|
| Mean > 0, CI excludes zero | mean -0.2694%, CI `[-0.3413%, -0.1877%]` -- FAIL | mean -0.1096%, CI `[-0.1505%, -0.0673%]` -- FAIL |
| >= 95th pctile vs. BOTH nulls | TIMING 100.0, SELECTION 100.0 -- **PASS** | TIMING 100.0, SELECTION 100.0 -- **PASS** |
| Positive after dropping best year | -0.2951% (2020 excluded) -- FAIL | -0.1239% (2020 excluded) -- FAIL |
| Positive within bands 1-100 | -0.2148% -- FAIL | -0.1138% -- FAIL |

**Both sides: NO EDGE, DEV FAILS.** The gate requires all four; 3
failures on each side regardless of the one pass. TEST is not read.

### Finding 1: the family's own signature pattern recurs a THIRD time, now even with a confirmation filter added

Both nulls pass at the **100th percentile** on both sides (500 seeds
each) while the mean stays negative -- the exact shape Study A and
Study B each already showed, and POC V4 before either of them. Adding a
second, stricter entry condition on top of an entry mechanism that
already demonstrably selects better-than-random stock-days did not
change the shape of the result: real, non-random selection value,
insufficient to clear costs. The counter-evidence recorded in the
preregistration (both nulls already maxed out; POC's own entry-filter
attempts across V2-V5 all failed; entry filtering has not rescued this
general family before) is now confirmed a third time, not merely
plausible in advance.

### Finding 2: THE HYPOTHESIS'S OWN TEST FAILS -- half-target reach rate FELL on both sides, not rose

| | Study A/B (no retest) | Study C (retest) |
|---|---|---|
| LONG half-target reach rate | 21.6% | **19.6%** |
| SHORT half-target reach rate | 26.5% | **23.4%** |

**The retest requirement was proposed specifically to raise this number
-- "requiring a second hold... raising the mean without raising the win
count" was the stated mechanism.** It did the opposite on both sides.
This is reported as its own finding, independent of the gate verdict,
per the preregistration's own explicit instruction: the filter did not
do what it was proposed to do. `full_target_rate_of_half_reached` moved
the same direction on the long side (21.8% vs. A's 23.1%); the short
side's own figure (19.3%) has no directly-stated B figure to compare
against in the preregistration, so is reported without a delta.

**A delay-cost explanation was pre-committed and is NOT what happened,
checked directly**: the mean "give-up" from waiting for the retest is
tiny -- **0.072% of entry price (long), 0.080% (short)**, with the
MEDIAN delay only 5 minutes on both sides (one extra 5-minute candle
past the original reclaim, the most common case by far) and a long
right tail (max 265 min long, 240 min short). This number is roughly an
order of magnitude too small to explain a ~2-3 percentage point
reach-rate drop on its own. The reach rate fell for a different reason
than "the later entry starts too far from the target" -- see Finding 3.

### Finding 3: the premise -- that filtered-out trades were worse -- is TRUE in aggregate, but the aggregate hides an uneven split

| | n | mean net return (counterfactual, immediate A/B-style entry) |
|---|---|---|
| LONG, filtered out (`no_retest` + `retest_failed`) | 1,017 | **-0.8856%** |
| LONG, survived (Study C's own actual trades) | 6,994 | -0.2694% |
| SHORT, filtered out | 1,001 | **-0.8150%** |
| SHORT, survived | 8,168 | -0.1096% |

**Filtered-out trades really were worse, by a wide margin, on both
sides** -- 0.62 percentage points worse (long), 0.71 points worse
(short) than what actually survived. This directly supports the stated
premise. **But broken down by WHICH filter removed them, the picture
splits**:

```
LONG:  retest_failed (n=950)  mean -1.019%   -- clearly bad trades, correctly removed
       no_retest     (n=67)   mean +1.005%   -- would have been GOOD trades, removed anyway
SHORT: retest_failed (n=935)  mean -0.954%   -- clearly bad trades, correctly removed
       no_retest     (n=66)   mean +1.151%   -- would have been GOOD trades, removed anyway
```

`retest_failed` (price breaching the original sweep extreme before ever
confirming a retest -- a clean signal the setup was actually dead) is
the large bucket and is genuinely doing useful work: these counterfactual
trades were bad, and removing them is exactly what the hypothesis
predicted. **`no_retest` (price never came back to the zone at all --
usually because it kept running in the trade's own favor) is doing the
opposite of what was intended: these are the smaller bucket, but their
own counterfactual mean is POSITIVE on both sides.** A trade that runs
away in its own favor without ever offering a second chance to confirm
is exactly the kind of trade this mechanism was supposed to keep, not
lose. The net effect across both buckets together is still "filtered-
out worse than survived" -- but it is not a clean "the filter removes
bad trades" story; it is "the filter removes mostly-bad trades and a
smaller number of trades that were actually good," and the first group
is simply larger.

### Finding 4: trade count fell by 11-14%, not "half or more" as predicted

| | Study A/B | Study C | drop |
|---|---|---|---|
| LONG | 8,131 | 6,994 | -14.0% |
| SHORT | 9,222 | 8,168 | -11.4% |

Attrition at the two new skip reasons: LONG `no_retest`=544,
`retest_failed`=1,155 (1,699 total, against ~8,693 setups that reached
the retest stage at all -- a 19.5% loss at this stage specifically,
partly offset by the fact that not every one of A's own 8,131 trades
maps one-to-one onto this same 8,693-setup population, since a handful
of downstream guards -- `stop_too_tight`/`stop_too_wide`/`zero_qty` --
also shift slightly under the later, recomputed-R entry price). SHORT:
`no_retest`=536, `retest_failed`=1,149 (1,685 of ~9,853 reaching
retest, 17.1%). The drop is real and in the predicted direction, just
roughly a third to a half the predicted MAGNITUDE.

### Why the mean barely moved despite removing clearly-worse-on-average trades

Arithmetically, removing a subset averaging -0.89%/-0.82% (Finding 3)
from a population should pull the survivors' own mean UP by more than
it actually moved: Study A's own -0.2841% became Study C long's
-0.2694%, a shift of only **+0.015 percentage points** -- not the much
larger shift simple arithmetic on the filtered-out mean alone would
suggest (the two populations are not a clean strict subset of each
other, since Study C's own downstream guards operate on the later,
recomputed entry price -- but the shift is still far smaller than the
filtering benefit on its own implies). The most consistent explanation,
combining Findings 2 and 3: the retest filter removes a population that
is worse on average (true), but what SURVIVES is itself pulled down
somewhat by the mechanism too (the reach-rate drop, Finding 2) -- the
two effects substantially offset each other, leaving the headline mean
close to unchanged on both sides. Not a null effect from "the filter
doesn't matter" -- a near-cancellation of two real, opposing effects.

### Base rate, updated, and Claude's prediction

**Fifteen prior strategies in this project have now closed with no edge
(the fourteen named in Study B's own updated count, plus this one) --
or, counting trial-by-trial within this family, Liquidity now stands at
3 trials, 3 failures.** Study C adds a fourth: entry filtering has now
failed to rescue this general sweep-and-reclaim-style mechanism across
SIX attempts total in this project (POC V2-V5, four; Liquidity A and B
implicitly by not needing a filter to begin with; Study C explicitly).

**Claude's own prediction, scored plainly**: right that both sides would
fail (verdict). Wrong that the trade count would fall by half or more
(it fell 11-14%). Wrong that the half-target reach rate would rise
modestly (it fell on both sides). Right that the mean would stay
negative, but for a different reason than stated (the predicted
mechanism -- "the later entry gives up part of the move" -- measures at
only ~0.07-0.08% and is not the dominant force; the real story is
Findings 2 and 3 substantially offsetting each other). **This is the
third consecutive study in this family where the verdict prediction was
right and the mechanism prediction was wrong** (Study A: predicted
cost, found follow-through; Study B: predicted similar-or-worse
follow-through, found better; Study C: predicted a sharper trade-count
drop and a rising reach rate from a small give-up cost, found a modest
drop, a FALLING reach rate, and a near-cancellation of two offsetting
effects neither single predicted mechanism captured). Recorded as a
pattern, per the preregistration's own instruction, not dismissed as
three independent coincidences.

## CLOSED -- DEV failed both sides, TEST stays sealed, no retry

**Confirmed by the user.** DEV failed on both sides (3 of 4 gate
conditions each). TEST was never read and will not be. No retry of this
configuration. **Liquidity family: 3 trials, 3 failures** (A, B, C, all
closed, all the same shape: both nulls pass at the 100th percentile
while the mean stays negative).

### Central finding: the hypothesis was tested directly and REFUTED

**The hypothesis was that filtering non-followers raises the mean
without raising the win count.** It was tested directly, against the
hypothesis's own stated criterion, not a proxy for it: the half-target
reach rate.

**It FELL on both sides** -- 21.6% -> **19.6%** (long), 26.5% ->
**23.4%** (short). Not flat, not a rounding-level wobble -- a fall, on
both sides, in the one number the hypothesis itself nominated as its
test.

**The mechanism is visible directly in the skip breakdown, not inferred
after the fact**:

```
LONG:  retest_failed (n=950)  mean -1.019%   -- correctly filtered
       no_retest     (n=67)   mean +1.005%   -- incorrectly filtered
SHORT: retest_failed (n=935)  mean -0.954%   -- correctly filtered
       no_retest     (n=66)   mean +1.151%   -- incorrectly filtered
```

`retest_failed` trades (price breached the original sweep extreme
before ever confirming a retest) really were bad, and removing them is
exactly what the hypothesis predicted. But `no_retest` trades -- price
ran away in the trade's own favor and never came back to offer a
confirmation -- were themselves the best trades in the filtered-out
population, on both sides. **The retest removed the best trades along
with the worst.**

**General lesson, stated for reuse beyond this study**: a confirmation
filter that requires price to come back necessarily excludes the moves
that do not come back -- and those are disproportionately the winners,
because the strongest moves are the ones least likely to pull back far
enough to retest before running. A filter built on "wait for
confirmation" trades win rate for win *rate among survivors*, and the
trade-off is not automatically favorable: it depends on whether the
excluded "ran without confirming" population is better or worse than
the excluded "genuinely failed" population. Here the two were roughly
comparable in size-weighted impact on the excluded group's own mean
pulling in opposite directions, and in Study C's measured reach rate
specifically, the loss of the best non-confirming trades dominated.
This is a general caution against any retest/confirmation filter
applied on top of a sweep-and-reclaim-style mechanism without first
checking, as done here, what the "never came back" population actually
looked like -- it is not safe to assume it is disproportionately bad.

### Units bug, restated for the closure record

`scripts/liquidity_c_dev_run.py`'s own `filtered_out_trades.
vs_actual_c_mean` field is wrong (subtracts a raw fraction from a
percentage, a factor-of-100 error) and was flagged, not silently fixed,
before this document relied on any derived figure from it. **It never
touched the gate decision** -- the gate reads `mean_net_return_pct`,
`ci_low`/`ci_high`, the two null percentiles, the ex-best-year mean, and
the bands-1-100 mean, none of which pass through the buggy field. The
corrected figures (-0.62pp long, -0.71pp short) used throughout this
document were computed by hand directly from the two correctly-scaled
percentage means, not from the buggy stored field.

### Calibration note: three for three, verdict right / mechanism wrong

**Within this family, the verdict prediction was right all three times
(A, B, C) and the mechanism prediction was wrong all three times.**
Study A: predicted cost would be the binding constraint, found instead
that follow-through was the issue. Study B: predicted similar-or-worse
follow-through on the short side, found it was better. Study C:
predicted a sharp trade-count collapse and a rising reach rate driven
by a small delay cost, found a modest trade-count drop, a *falling*
reach rate, and a cancellation between two effects (correctly-filtered
losers vs. incorrectly-filtered winners) that neither single predicted
mechanism captured.

**Worth stating as a general calibration note about predictions made in
this project, not just about this family**: the verdict ("will this
configuration show an edge") has been forecastable from priors and
counter-evidence recorded in advance. The mechanism ("why, specifically,
will it fail or succeed") has not been -- three for three wrong, each
time for a different, concrete, checkable reason rather than a vague
miss. This suggests pre-committed verdict predictions in this project
are worth continuing to make and record (they carry real information),
while pre-committed mechanism predictions should be treated as a
lower-confidence guess even when the verdict prediction is sound --
worth checking directly against the data, as done here, rather than
assumed to follow once the verdict is confirmed.

## POST-CLOSURE DIAGNOSTIC: what did price actually do over the next 10 days, regardless of the strategy's own exits?

**Not a new study. No new strategy, no gate, no verdict change.** All
three studies (A, B, C) stay closed exactly as recorded above. This is
a measurement over the already-closed trade population, run after the
fact and reported here because it spans all three studies' trades.
Cross-referenced from `LIQUIDITY_A_FINDINGS.md` and
`LIQUIDITY_B_FINDINGS.md`.

**Question**: for every one of the 32,515 trades actually taken across
A (8,131), B (9,222), C-long (6,994), and C-short (8,168), starting from
the real entry price, what did price do over the following 10 trading
days -- regardless of what the strategy's own stop, half-target,
full-target, or 15:15 time-exit actually did? Specifically: when (same
day via 1-minute bars, or which of the next 10 trading days) was each
of the strategy's own stop, 1.5R, 3R, and -- to see whether moves ran
further than the strategy ever aimed for -- 5R and 10R, first touched.

**Method, and why it is not literally "daily bars" as first specified**:
a pre-flight check (see Bug #18, `BUGS.md`) found that `prices_eod`
disagrees with the bars_1min-derived raw scale on 13-15% of days, with
the disagreement traced to the same unreconciled-corporate-action
pattern `fibo.scale_probe` already exists to fix. Rather than import
that noise into a new measurement, every session here -- the entry day
(1-minute resolution) and all 10 forward days (daily-aggregated from
the same 1-minute source) -- is priced from `bars_1min` alone, converted
via `fibo.scale_probe`'s empirically-validated per-day scale: the exact
same method, and for the entry day the exact same scale value, that
`box_theory.context.eligible_day_context` already uses for the candles
A/B/C's own entry and exit logic runs on. `prices_eod` is used only as
`scale_probe`'s own required input (the previous day's high/low) and as
the trading-day calendar, never compared against `entry_price`/
`stop_price` directly. Validated directly against a known hand-trace
before running at scale: for Study A's own 2017-05-18 `STOP_NO_HALF`
trade (`INE002A01018`), this diagnostic independently recovers the exact
same stop touch -- same day, 13:17:00 -- as the trade's own recorded
`final_exit_ts`. A day scale_probe cannot resolve (unresolved match,
ex-date, or gap-guard skip) is recorded as data-unavailable for that
session, not silently treated as "not touched"; coverage was effectively
complete (31,091 of 32,515 trades, 95.6%, had the full 10 forward
trading days resolved; the remainder mostly ran short of the DEV window's
own end rather than hitting a data gap).

**CAVEATS, stated up front, per instruction**:
- **Shorts (B, C-short) cannot legally be held overnight in Indian cash
  equities at retail.** A 10-day hold is not an executable strategy for
  these two studies' trades -- the numbers below for B and C-short are a
  measurement of price behaviour only, not a description of anything
  that could actually be traded.
- This measurement uses the ORIGINAL entry price and the ORIGINAL stop
  level, and prices only the move itself -- it does not model delivery
  margin/costs, overnight gap risk, or the capital a real multi-day hold
  would tie up. POC V5 already tested an actual 10-day hold directly
  (not a hypothetical lookahead) and found it WORSE than the intraday
  version (-0.63% vs -0.29%), substantially for exactly these reasons.
  Nothing below should be read as contradicting that finding.
- **This is hindsight on a closed population.** If anything below
  suggests a better exit rule, that is a hypothesis for a new,
  separately pre-registered trial -- not a result, and not evidence for
  or against any of A/B/C's own closed verdicts.

### Section 1: first-touch timing, cumulative % reached by checkpoint, per level

Percent of trades where each level was touched by same-day, by day 1,
2, 3, 5, 10, or never within the 10-day window (bands do not sum to
100% beyond "never" since each row is its own cumulative-by-checkpoint
series):

**LONG (A + C-long combined, n=15,125)**

| level | same day | by day 1 | by day 2 | by day 3 | by day 5 | by day 10 | never |
|---|---|---|---|---|---|---|---|
| stop | 41.4% | 63.5% | 70.6% | 74.8% | 79.5% | 84.5% | 15.5% |
| 1.5R | 24.3% | 50.4% | 60.7% | 66.4% | 73.2% | 80.9% | 19.1% |
| 3R | 5.8% | 21.6% | 32.5% | 40.3% | 50.0% | 62.7% | 37.3% |
| 5R | 1.0% | 6.6% | 13.1% | 19.4% | 28.5% | 43.1% | 56.9% |
| 10R | 0.0% | 0.6% | 1.6% | 3.4% | 7.0% | 16.0% | 84.0% |

**SHORT (B + C-short combined, n=17,390)** -- caveat above applies

| level | same day | by day 1 | by day 2 | by day 3 | by day 5 | by day 10 | never |
|---|---|---|---|---|---|---|---|
| stop | 35.8% | 60.2% | 69.7% | 74.5% | 79.9% | 85.8% | 14.2% |
| 1.5R | 28.9% | 52.6% | 61.9% | 67.2% | 73.2% | 80.2% | 19.8% |
| 3R | 6.3% | 21.5% | 32.3% | 39.6% | 49.1% | 61.5% | 38.5% |
| 5R | 1.1% | 6.1% | 12.4% | 18.0% | 27.0% | 41.4% | 58.6% |
| 10R | 0.0% | 0.5% | 1.4% | 2.7% | 5.8% | 14.0% | 86.0% |

All four studies individually (A, B, C-long, C-short) show the same
shape as their direction's combined row above, within 1-6 points per
cell -- the pattern is not specific to any one study. One structural
fact worth stating plainly: **the strategy's own stop is touched at some
point within 10 days on 84-86% of ALL trades** (same-day stop alone is
34-44%) -- the stop is a frequently-revisited level, not a rare tail
event, regardless of what eventually happens afterward. 3R (the
strategy's own full target) is reached within 10 days on only 61-63% of
trades even with no stop/time-exit in the way at all -- confirming the
strategy's own ~20-27% full-target-after-half reach rate (Study A/B's
own published figures) is not primarily a "ran out of time" artifact;
most of the shortfall is simply moves that don't go that far within 10
days, stop or no stop. 5R and 10R are reached within 10 days on only
39-44% and 13-17% of trades respectively -- confirming the strategy is
not systematically leaving large multiples on the table industry-wide,
though a minority of trades clearly do run much further than 3R.

### Section 2: of trades that hit the stop SAME DAY, how many went on to reach 1.5R or 3R anyway within 10 days?

| | n same-day stop | % of all trades | -> reached 1.5R | -> reached 3R |
|---|---|---|---|---|
| LONG | 6,267 | 41.4% | 4,560 (72.8%) | 3,502 (55.9%) |
| SHORT | 6,219 | 35.8% | 4,248 (68.3%) | 3,233 (52.0%) |
| A | 3,533 | 43.5% | 2,577 (72.9%) | 2,013 (57.0%) |
| B | 3,482 | 37.8% | 2,413 (69.3%) | 1,852 (53.2%) |
| C-long | 2,734 | 39.1% | 1,983 (72.5%) | 1,489 (54.5%) |
| C-short | 2,737 | 33.5% | 1,835 (67.0%) | 1,381 (50.5%) |

**On roughly 7 of 10 same-day stop-outs, the idea was directionally
right and the stop (or the one-day horizon) was what was wrong, not the
setup itself** -- price went on to reach 1.5R within 10 days regardless
of having first breached the stop. Just over half even reached the full
3R target. This is consistent across all four studies, long and short
alike (67-73% for 1.5R, 51-57% for 3R). Read together with Section 1's
own finding that the stop is touched on 84-86% of ALL trades (not just
same-day ones) -- a setup breaching its own stop at some point is close
to the norm, not the exception, for this entry mechanism; what varies is
whether price comes back afterward.

### Section 3: of trades that exited via 15:15 time-exit without ever reaching the half target (TIME_EXIT_FULL), where did price end up by day 10?

| | n | % of all | mean day-10 return | median | % favourable |
|---|---|---|---|---|---|
| LONG | 5,968 | 39.5% | +0.346% | +0.424% | 52.7% |
| SHORT | 7,116 | 40.9% | -0.309% | -0.123% | 49.0% |
| A | 2,994 | 36.8% | +0.324% | +0.408% | 52.4% |
| B | 3,465 | 37.6% | -0.320% | -0.127% | 49.0% |
| C-long | 2,974 | 42.5% | +0.368% | +0.450% | 53.1% |
| C-short | 3,651 | 44.7% | -0.299% | -0.117% | 48.9% |

(`day10_return` is signed so positive always means "favourable for the
position actually taken" -- for SHORT trades this means price fell.)

**Longs that timed out without reaching the half target kept drifting
favourably afterward on average (median +0.42%, 53% net favourable by
day 10); shorts that timed out drifted unfavourably on average (median
-0.12% to -0.13%, only 49% favourable)** -- a small but real directional
asymmetry, in the same direction as Study B's own already-published
finding that shorts underperform longs despite better raw metrics
(Study B outperformed A with no trend filter, yet the family's own
counter-evidence already flagged shorts as structurally weaker
follow-through). Separately: of these same TIME_EXIT_FULL trades,
78-80% went on to reach 1.5R and 57-59% went on to reach 3R within the
full 10-day window anyway (both directions, all four studies) -- the
single 15:15 cutoff is, by a wide margin, the single biggest source of
"target not reached" in this entire population, well ahead of the stop.

### Section 4: when BOTH the stop and a target were reached within 10 days, which came first?

**Target = 1.5R**

| | n both reached | stop first | target first | same session (order unknown) |
|---|---|---|---|---|
| LONG | 9,919 (65.6%) | 5,448 (54.9%) | 3,358 (33.9%) | 1,113 (11.2%) |
| SHORT | 11,490 (66.1%) | 5,382 (46.8%) | 4,757 (41.4%) | 1,351 (11.8%) |

**Target = 3R**

| | n both reached | stop first | target first | same session (order unknown) |
|---|---|---|---|---|
| LONG | 7,250 (47.9%) | 5,314 (73.3%) | 1,597 (22.0%) | 339 (4.7%) |
| SHORT | 8,333 (47.9%) | 5,679 (68.2%) | 2,210 (26.5%) | 444 (5.3%) |

Median gap when orderable: 2 trading sessions for 1.5R, 3 for 3R, both
directions (means 3.1-3.9, pulled up by a long right tail). Of the
"same session" cases that were specifically same-DAY (both touched
intraday, session 0): zero exact-same-minute ties on either target or
either direction; the stop preceded the target intraday roughly 2.3-2.4x
as often as the reverse (LONG 1.5R: 398 stop-first vs. 168 target-first
within the day; SHORT 1.5R: 452 vs. 196) -- consistent with the stop
typically sitting closer to entry than 1.5R, so a volatile day that
clears both tends to clear the nearer one first.

**For 3R specifically, the stop comes first roughly 2.6-3.3x as often as
the target does, in both directions** -- when a trade is eventually
going to reach the full target AND also touch the stop at some point
within 10 days, it overwhelmingly touches the stop FIRST. This is the
most direct evidence in this diagnostic that the strategy's stop
placement is, more often than not, positioned such that a genuinely
winning move still "shakes out" the position on the way -- not proof
that the stop is wrong (a tighter stop also changes position sizing and
the win population itself, and this is hindsight on a closed
population, not a trial), but a concrete, measured fact a future
pre-registered trial on stop placement would need to explain.

### What this does and does not change

**No verdict changes.** A, B, and C stay closed exactly as recorded
above -- DEV failed, TEST stays sealed, no retry, 3 trials/3 failures.
Nothing here is a backtest of an alternative exit rule (no costs, no
position-sizing change, no re-entry logic, no slippage past the
original fill); it is a measurement of what price did, on the
population these three closed studies actually traded, after their own
exits are set aside. The clearest hypotheses it raises for a future,
separately pre-registered trial -- a wider stop, or a longer hold past
15:15 for longs specifically given the asymmetric day-10 drift in
Section 3 -- are exactly that: hypotheses, generated from hindsight on a
population that already failed its own gate, not findings that this
population would have passed under a different rule. POC V5's own
direct test of a longer hold (not a lookahead measurement) already
found that an actual extended hold made its own family's result WORSE,
which is the relevant prior for how much weight any hindsight-only
signal here should carry on its own.

## POST-CLOSURE DIAGNOSTIC 2: maximum adverse excursion on stopped-out trades

**Not a study. No new strategy, no gate, no verdict change.** All three
studies stay closed exactly as recorded above. Measures, for every trade
across A/B/C-long/C-short whose REAL, ACTUAL outcome was a stop-out
(`final_exit_kind == 'STOP'` -- 12,035 of the 32,515 real trades), what
price did afterward if no stop had existed, using the ORIGINAL entry
price and tracking daily bars forward 30 trading days. Same
`fibo.scale_probe` method as the first post-closure diagnostic above,
extended from 10 to 30 forward days and from "first touch of 5 preset
levels" to the full daily high/low path, so maximum adverse excursion
(MAE) can be measured at any horizon. 88.2% of trades (10,621/12,035)
had the full 30-day window available; coverage gaps are mostly partial
windows near the DEV/TEST boundary, never a data error.

**CAVEAT, stated up front, per instruction**: shorts (B, C-short) cannot
legally be held overnight in Indian cash equities at retail. The SHORT
numbers below describe price behaviour only -- they are not a
description of anything executable. **This is hindsight on a closed
population.** No verdict changes as a result of anything below.

### Section A: MAE distribution, within 10 days and within 30 days

Percentage adverse move from entry, worst point reached (for long:
entry minus the lowest low reached, over entry; for short: the highest
high reached minus entry, over entry):

| | n | p50 | p75 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|
| LONG, MAE within 10d | 6,060 | 5.53% | 9.49% | 14.58% | 19.28% | 35.67% | 84.86% |
| LONG, MAE within 30d | 6,060 | 8.62% | 14.74% | 23.59% | 32.23% | 55.17% | 88.56% |
| SHORT, MAE within 10d | 5,975 | 5.66% | 9.65% | 15.38% | 19.84% | 37.21% | 99.82% |
| SHORT, MAE within 30d | 5,975 | 9.61% | 16.50% | 25.81% | 33.36% | 58.52% | 165.26% |

All four studies individually track their direction's combined row
within 0.1-1 point per cell. **The median stopped-out trade, tracked
without a stop, still moves against entry by 8.6-9.6% within 30 days**
-- roughly 14x the stop's own typical distance (stop_distance_pct was
~0.6-0.9% in the original closed studies). The stop is not a narrow miss
on a trade that was about to turn around; the median path keeps going
hard in the adverse direction for a while, consistent with Finding 3's
earlier observation that `retest_failed` (clean breach) trades really
were bad. SHORT's tail is heavier than LONG's at every percentile and
dramatically so at the max (165.26% vs 88.56%) -- a 165% adverse move on
a short is a position that, unhedged, would have wiped out the account
multiple times over by the time it happened; this is exactly why the
caveat above matters, not a rounding curiosity.

### Section B: how many trades crossed 10% / 20% / 50% adverse

Using 30-day MAE (10-day shown for comparison):

| | n | >=10% (30d) | >=20% (30d) | >=50% (30d) | >=10% (10d) | >=20% (10d) | >=50% (10d) |
|---|---|---|---|---|---|---|---|
| LONG | 6,060 | 2,610 (43.1%) | 860 (14.2%) | 101 (1.7%) | 1,392 (23.0%) | 279 (4.6%) | 16 (0.3%) |
| SHORT | 5,975 | 2,863 (47.9%) | 1,067 (17.9%) | 97 (1.6%) | 1,396 (23.4%) | 286 (4.8%) | 22 (0.4%) |

Roughly 4 in 10 stopped-out trades would have moved 10%+ against entry
within 30 days if held without a stop; roughly 1 in 6-7 would have moved
20%+; 50%+ is rare but not zero (97-101 trades, ~1.6-1.7%) on both sides.
Nearly double the 10-day count is reached by day 30 at the 10% and 20%
thresholds (e.g. LONG 10%: 23.0% -> 43.1%), meaning most of this
additional adverse movement accrues AFTER day 10, not before it.

### Section C: of trades in each MAE bucket, recovery to 1.5R / 3R within 30 days

| | n | -> 1.5R (rate, median days) | -> 3R (rate, median days) |
|---|---|---|---|
| LONG >=10% adverse | 2,610 | 1,678 (64.3%), 2 days | 1,218 (46.7%), 5 days |
| LONG >=20% adverse | 860 | 465 (54.1%), 2 days | 307 (35.7%), 3 days |
| LONG >=50% adverse | 101 | 57 (56.4%), 1 day | 40 (39.6%), 2 days |
| SHORT >=10% adverse | 2,863 | 1,868 (65.2%), 3 days | 1,357 (47.4%), 6 days |
| SHORT >=20% adverse | 1,067 | 531 (49.8%), 2 days | 331 (31.0%), 5 days |
| SHORT >=50% adverse | 97 | 31 (32.0%), 1 day | 21 (21.6%), 2 days |

**Recovery rate does not fall monotonically with how far a trade first
went against entry.** Trades that went 50%+ against entry recover to
1.5R about as often as (LONG) or notably less often than (SHORT) trades
that only went 10%+ -- the severity of the adverse excursion is not a
clean predictor of whether the trade eventually comes back. The median
time-to-recovery when it happens is short (1-6 days) across every
bucket, meaning recoveries that occur, occur quickly -- there is no
large population of trades grinding back slowly over weeks. **SHORT's
recovery rate degrades much more sharply in the >=50% bucket than
LONG's** (32.0% vs 56.4% for 1.5R) -- the heavier adverse tail in
Section A is not merely cosmetic; the worst short trades are also
disproportionately the ones that do not come back.

### Section D: full return distribution at day 10 and day 30, no stop at all

| | n | day-10 mean | day-10 median | day-10 worst | day-10 best | day-30 mean | day-30 median | day-30 worst | day-30 best |
|---|---|---|---|---|---|---|---|---|---|
| LONG | 6,060 | -0.93% | -0.83% | -84.43% | +52.87% | -0.17% | -0.36% | -87.40% | +105.34% |
| SHORT | 5,975 | -1.60% | -1.30% | -68.34% | +89.74% | -1.83% | -1.64% | -155.17% | +90.00% |

(Return is signed so positive always means favourable for the position
actually taken; for SHORT this means price fell.)

**Without a stop, the stopped-out population's own mean return stays
negative at both horizons for both directions** -- consistent with the
earlier finding that the stop, on average, is not making a bad trade
worse by itself (SHORT's mean actually gets WORSE from day 10 to day 30,
-1.60% to -1.83%, while LONG's improves slightly, -0.93% to -0.17%, the
same long/short asymmetry already recorded in the first post-closure
diagnostic's Section 3). **The worst-case tail is severe and asymmetric**:
LONG's floor is bounded near -87% to -88% at both horizons (a long
position cannot lose more than 100% of entry); SHORT's day-30 worst case
is -155.17% -- a short position has no such floor, and this number is
the direct, measured illustration of why the caveat above is not
boilerplate. The best-case tail is large on both sides (+52.87% to
+105.34% LONG, +89.74% to +90.00% SHORT) -- a reminder that the same
population contains both the worst single losses and some of the
largest favourable moves in the whole post-closure analysis, consistent
with Section C's finding that even badly-adverse trades recover at a
non-trivial rate.

### What this does and does not change

**No verdict changes.** A, B, and C stay closed exactly as recorded
above. This is hindsight on a closed population using the ORIGINAL entry
price and the ORIGINAL R-levels -- it does not model an executable
alternative (no re-sizing, no re-entry, no delivery costs or margin for
a multi-day hold, and for SHORT specifically, no model of the overnight
risk a real multi-day short could not legally carry in the first place).
Any exit-rule hypothesis this suggests -- a wider stop sized to the
10-30%+ adverse moves many trades experience before recovering, at the
cost of the capital and risk a wider stop implies -- is exactly that: a
hypothesis for a future, separately pre-registered trial, not a finding
that this population would have passed under a different rule. The same
prior from the first post-closure diagnostic applies here with more
force, not less: POC V5's own direct test of an actual extended hold
(not a lookahead measurement) already found it made that family's result
WORSE, and this diagnostic's own SHORT worst-case (-155.17%) is a
concrete illustration of why "the trade recovers eventually" is not the
same question as "a wider stop is a good idea."

## Status

**CLOSED.** DEV failed both sides. TEST was never read and stays
sealed. No retry. Liquidity family stands at 3 trials, 3 failures.
