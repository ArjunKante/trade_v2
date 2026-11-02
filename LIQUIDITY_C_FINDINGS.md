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

## Status

**DEV complete, both sides. NO EDGE, both sides fail the gate (3 of 4
conditions) with the identical shape Studies A and B each already
showed.** The hypothesis's own stated test (half-target reach rate) also
fails on both sides, independent of the gate verdict. **Stopping here
for approval before TEST**, per the preregistration's own Section 12 --
TEST has not been read and `liquidity.c.guard_date_range` has not been
called with `authorize_test=True` anywhere in this study.
