# Fibonacci/ORB Intraday Research (Hypothesis B): Findings

Full process record (phase-by-phase build, every intermediate number,
every correction): `FIBO.md`. Frozen rules and methodology:
`PREREGISTRATION_FIBO.md`, including Section 5b's cost-sensitivity
addition and Section 6b's sealed-test result. This document is the
conclusion, written last, in the main project's `FINDINGS.md` /
`SWING_FINDINGS.md` style.

## 1. The question

Does a fully mechanical, code-verified version of a discretionary
Fibonacci-retracement/opening-range-breakout intraday method have a
demonstrated edge, net of realistic transaction costs, on NSE equities?

## 2. The answer

**NO EDGE for these rules** -- against a pre-registered bar requiring four
criteria to hold under three cost scenarios simultaneously, one criterion
failed under one scenario. The failure is narrow, specific, and not what
"no edge" usually implies: the rule's DAY SELECTION is not in question.
Its EXECUTION, at the position size this rule risks, in the names it had
to trade to reach a usable sample size, is.

## 3. The sequence

**Development (top-50 universe, 2016-10-04 to 2022-12-31, descriptive
only, per `PREREGISTRATION_FIBO.md` Section 5a)**: 67 trades, 71.6% win
rate, mean net R +0.36 (lo-cost, t=3.22) / +0.27 (hi-cost, t=2.42).
**100.0th percentile vs the SELECTION null** but **8.9th percentile vs the
TIMING null** -- the confluence picks good days; the specific ORB-breakout
entry trigger looks weak on those same days.

**Two issues found before the test could run, both addressed before any
test-window data was read**: (1) the selection null needed a harder,
uptrend-restricted variant (null (b2)) to rule out that it was merely
rewarding being in an uptrend -- development scored **99.9th/100.0th
percentile** against it, the specific risk it existed to test, and it
held. (2) 67 trades over 6.25 years implied only ~40 test-window trades,
short of the 100-trade floor -- the universe was widened from top-50 to
top-200 by the same point-in-time turnover method, motivation trade-count
only, with the new names checked for DATA QUALITY ONLY on development data
(scale-probe UNRESOLVED 0.54-1.53% across bands, all within the 2%
threshold) before any strategy number was computed for them.

**Cost sensitivity, added as a mandatory condition of running the test**:
band 101-200's turnover is 18.0% of band 1-50's, against a cost model (a
flat 6.0-19.0bps spread/impact range) tuned on a different, more liquid
population. Three cost scenarios were frozen before the read: flat low,
flat high, and a pessimistic banded scenario (band 1-50 unchanged, band
51-100 at 2x the high bound, band 101-200 at 4x) -- TEST PASS redefined to
require all four original criteria under all three scenarios.

**The sealed test (top-200 universe, 2023-01-01 to 2026-09-18, read
once)**: 188 trades.

## 4. The shape of the result, precisely

**WHAT HELD**: both selection nulls (b) and (b2) at the **100th
percentile, in every one of the three cost scenarios including the
harshest**, on 188 sealed-window trades. The confluence beats random
day-selection, and beats random day-selection already restricted to
uptrend days, regardless of which cost assumption is applied. **Day
selection is not the problem.**

**WHAT FAILED**: mean net R collapses from +0.27 (t=4.57, flat high cost)
to +0.04 (t=0.65) once band 101-200's cost is stressed to 4x the high
bound. Band 101-200 is **58% of all trades** (109 of 188) and its own
pessimistic-scenario mean R is **-0.1021** -- a net loser -- while bands
1-50 and 51-100 stay solidly profitable even under their own (1x/2x)
stress multipliers.

**THE FINDING**: the signal appears real but was harvested predominantly
in names too thin to trade at this rule's fixed position size (floor(Rs
500 / R) shares). This is not a verdict on the underlying idea -- it is a
verdict on this fully mechanical, fixed-risk, liquidity-blind version of
it, trading names it had to include to reach a usable sample size.

## 5. Four things to record honestly

**(a) The 4x multiplier was an estimate, not a measurement, and the
result sits near the boundary it creates.** Recomputing criterion 2 at
intermediate multipliers for band 101-200 (holding bands 1-50/51-100 at
their own 1x/2x): mean net R and t fall monotonically as the multiplier
rises --

| band 101-200 multiplier | mean net R | t |
|---|---|---|
| 1x | 0.2547 | 4.230 |
| 2x | 0.1828 | **3.056 (would PASS)** |
| 3x | 0.1110 | **1.850 (would FAIL)** |
| 4x (as tested) | 0.0392 | 0.645 |

The pass/fail boundary for criterion 2 sits between 2x and 3x -- not at
some far, clearly-unrealistic extreme. The verdict therefore depends
materially on an assumption that was never measured for this project's
universe. **The correct next step for any future study in this direction
is to MEASURE band 101-200's actual spread/impact directly** (live
order-book sampling, the same method the swing project used for its own 5
names -- `ops/report_capacity_slippage_groundtruth.py`), not to stress-test
a turnover-ratio-derived guess further. This document does not know
whether a measured cost would land above or below the 2x-3x boundary --
that is precisely the open question a direct measurement would close.

**(b) The sample-size tension is a structural finding, independent of the
cost-assumption question above.** Bands 1-50 and 51-100 alone produced 79
trades (~21/year) over the test window and stayed profitable under their
own stress multipliers -- but 79 trades over 3.75 years could never have
cleared the 100-trade pre-registered floor on their own; the universe
widening that was REQUIRED to reach statistical power is exactly what
introduced the band 101-200 trades whose cost assumption the result now
hinges on. At this rule's trade frequency (per-name signal is rare: one
uptrend AND one confirmed swing AND one ORB/golden-zone overlap AND one
15-minute breakout, on the same day), **a universe liquid enough to trade
at this position size cannot generate enough trades to test with
confidence, and a universe wide enough to generate enough trades
necessarily reaches into names where the position-sizing assumption
(fixed Rs 500 risk, liquidity-blind) becomes the binding constraint.**
This tension is not specific to the 4x choice in (a) -- it would recur at
any version of this rule that sizes positions without reference to the
name's own liquidity.

**(c) The TIMING null replicated out of sample.** Development: 8.9th
percentile. Sealed test: 2.3rd percentile, on entirely different trades
from an entirely different (and sealed) window. The specific ORB-breakout
entry trigger underperforms a random entry time on the exact same
qualifying days, consistently, in both samples. This is a replicated
finding, not a one-off artifact, and is arguably the most reusable result
to come out of this study -- **recorded here as a candidate for a future,
separately pre-registered study** (e.g. testing entry at a random or fixed
time within the golden-zone-overlap window instead of an ORB breakout),
not as a fix applied retroactively to this rule. Per Section 5a/5b, no
rule was changed to act on it.

**(d) The 4x multiplier's stated justification is refuted by this
project's own data (checked 2026-10-02, before any live spread
measurement).** The multiplier was an estimate, not a measurement (per
(a) above) -- supplied by the user, resting on two stated grounds: that
band 101-200 is a thin population, and that the flat high-bound
spread/impact assumption understates true cost there. Both grounds fail
against data already sitting in this project's own warehouse:

- **"Thin population"**: measured median daily turnover for band
  101-200, 2023-01-01 to 2026-09-18, is **Rs 108 crore** (p10 Rs 35
  crore, p90 Rs 336 crore). Not thin by any ordinary standard. The 67
  entities that actually produced the 109 band-101-200 sealed-test
  trades have an almost identical turnover distribution to the band as a
  whole (same Rs 108 crore median) -- the trades are not concentrated in
  some unusually thin tail that a band-wide median could be hiding.
- **"Impact understated"**: this rule's Rs 500 fixed risk produces
  position sizes that are a median **0.0027%** of that stock's own daily
  turnover in band 101-200 (max **0.054%**, across all 188 sealed-test
  trades, every band). At that size, market impact should be negligible
  under any standard liquidity model -- the position is not large enough,
  relative to the day's traded value, to move the price.

Neither of the two stated reasons for a 4x stress multiplier survives
contact with data this project already had. **The only cost question
this leaves open is the QUOTED SPREAD itself** -- not impact, not a
thin-market discount -- which a live measurement, not a turnover-ratio-
derived guess, can actually settle.

**This is a finding about the TEST DESIGN, not a re-reading of the
sealed-test result.** The sealed test ran on rules frozen in advance,
including the 4x multiplier as one input to the pass/fail bar, and
produced the recorded verdict in Sections 2 and 4 above -- that verdict
stands, unchanged, as recorded. What changes is confidence in ONE INPUT
to that bar: the 4x multiplier, already flagged in (a) as an estimate
rather than a measurement, now has its stated reasoning checked against
data and found wanting. Whether this justifies a corrected-cost
re-evaluation of the sealed window, or whether that would amount to
re-reading a spent window, is a decision explicitly deferred -- pending
a live bid-ask spread measurement on a sample of band 101-200 names, the
one open input left.

## 6. Engineering note: computing the sealed-test nulls under repeated external kills

The 1000-seed TIMING/SELECTION(b)/SELECTION(b2) null computation on the
sealed test window was interrupted by this environment's own external
process kills roughly 15 times in direct succession during this run --
far more frequently than any prior long-running script in this project
experienced (Step 3's original download, by contrast, was killed only a
handful of times over many hours). The script initially had no
checkpointing; each of the first few kills cost an entire in-progress null
type's accumulated seeds. Fixed live, mid-run, by adding a
per-null-type, per-N-seed pickled checkpoint (`scripts/fibo_test_nulls.py`,
atomic-swap write), tightened from every 50 seeds to every 10 once kills
began arriving faster than a 50-seed checkpoint could complete. With
checkpointing in place, the full 3000 seeds (1000 each for three null
types) completed across the remaining relaunches with no single kill
costing more than 10 seeds of work, and **no trade, no rule, and no
already-computed seed's result was ever redone** -- this was infrastructure
resilience against an environment fault, not a second analytical pass
over the sealed data.

## 7. What this does and does not conclude

**Concludes**: this specific, fully mechanical, fixed-risk version of the
Fibonacci/ORB confluence does not clear a pre-registered, four-criteria,
three-cost-scenario bar on the sealed 2023-2026 test window. The failure
is isolated to execution cost at the thinner names needed to reach a
testable sample size, not to the day-selection mechanism itself, which
held decisively (100th percentile) under every cost assumption tried,
including the harshest. The ORB-breakout entry trigger specifically
underperformed random entry in both the development and sealed-test
windows -- a replicated, separate finding.

**Does not conclude**: that the underlying idea -- Fibonacci retracement
confluence with an opening-range breakout -- has no edge under any
position-sizing, universe, or entry-timing variant. A liquidity-aware
position size, a universe restricted to names where the cost assumption
is not the binding constraint, or a different entry mechanism (Section
5.c) are all untested, separately pre-registerable directions this
document does not rule out. What it does rule out, cleanly, is this exact
rule set as specified and frozen in `PREREGISTRATION_FIBO.md` Section 3.
