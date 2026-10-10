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

## 2. The lesson that matters, independent of the verdict

This is placed here, ahead of the verdict below, deliberately -- it is
the finding that should survive in memory regardless of which way Section
3's verdict (or Section 9's later amended re-test) comes out.

> The original pre-registration was rigorous in structure -- frozen
> rules, sealed window, pre-committed criteria -- and still carried an
> unvalidated number at its core. The 19bps base and the 4x multiplier
> were never checked against turnover or position-size data that was
> already in the warehouse. Nobody looked until the number decided a
> verdict. That is the real lesson of this episode, independent of
> whether the amended re-test passes or fails.

Concretely: Section 4's 6.0-19.0bps flat spread range was ported from a
DIFFERENT project's DIFFERENT universe, and the pessimistic scenario's
2x/4x multipliers were, by their own stated text at the time, "ROUND
NUMBERS... not a precise re-measurement," with "no fresh spread data
collected for this test." Both caveats were written down correctly when
the test was frozen -- and neither one triggered an actual measurement
before the number was used to decide a 188-trade, 44.5-month verdict. The
turnover data that eventually refuted the multiplier's stated grounds
(Section 6d below) and the live spread data that quantified the actual
error both existed, or were cheap to obtain, BEFORE the sealed test's one
authorized read, not after.

**The structural disciplines this project enforces -- frozen rules,
sealed windows, pre-committed pass criteria, one authorized read --
protect against p-hacking and lookahead. They do not, by themselves,
validate every number fed into the criteria those disciplines are built
to protect.** A flagged-but-unmeasured input can sit at the center of a
frozen, sealed, disciplined test and still be wrong by an order of
magnitude. Section 9 below reports what happened once that specific input
was finally measured and the same sealed trade list was re-costed under
it -- read it alongside Section 9i's citation requirements, not as a
clean second test.

## 3. The answer

**NO EDGE for these rules** -- against a pre-registered bar requiring four
criteria to hold under three cost scenarios simultaneously, one criterion
failed under one scenario. The failure is narrow, specific, and not what
"no edge" usually implies: the rule's DAY SELECTION is not in question.
Its EXECUTION, at the position size this rule risks, in the names it had
to trade to reach a usable sample size, is.

## 4. The sequence

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

## 5. The shape of the result, precisely

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

## 6. Four things to record honestly

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
produced the recorded verdict in Sections 3 and 5 above -- that verdict
stands, unchanged, as recorded. What changes is confidence in ONE INPUT
to that bar: the 4x multiplier, already flagged in (a) as an estimate
rather than a measurement, now has its stated reasoning checked against
data and found wanting. Whether this justifies a corrected-cost
re-evaluation of the sealed window, or whether that would amount to
re-reading a spent window, is a decision explicitly deferred -- pending
a live bid-ask spread measurement on a sample of band 101-200 names, the
one open input left.

**Live measurement, 2026-10-05 ~11:31 IST, Groww market depth, six
band-101-200 names** (HAVELLS, LENSKART, IGL, JSWSTEEL, GODREJPROP,
PERSISTENT): quoted spreads 3.1-5.7 bps, mean 4.3 bps. Depth at best bid
is tens of thousands of shares against this rule's ~26-share position --
impact is zero, consistent with the turnover-ratio argument in (d) above.
Versus the two frozen assumptions: flat-high (19 bps) is **~4x too
high**; the pessimistic banded scenario's 4x-stressed figure (76 bps) is
**~17x too high**. Same caveat as the swing project's September reading:
this is a single session, six names -- it cannot capture spread variation
across the trading day, across volatile sessions, or during 2023-2024,
part of the actual sealed-test window, when conditions may have differed.
Whether this measurement justifies a corrected-cost re-evaluation of the
sealed window remains the decision deferred above -- not resolved by
recording this number.

## 7. Engineering note: computing the sealed-test nulls under repeated external kills

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

## 8. What this does and does not conclude

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
6.c) are all untested, separately pre-registerable directions this
document does not rule out. What it does rule out, cleanly, is this exact
rule set as specified and frozen in `PREREGISTRATION_FIBO.md` Section 3.

## 9. Amended re-test under corrected cost inputs (2026-10-08)

Section 3's verdict above (NO EDGE, sealed test, 2026-10-02 read) stands,
unchanged. This section records a LATER event: a live bid-ask spread
measurement (Section 6d below; full detail in `PREREGISTRATION_FIBO.md`
Section 8) refuted the sealed test's 19bps/4x cost assumption, and the
SAME sealed 188-trade list and the SAME 1000-seed null draws were
re-costed under the corrected figure -- not re-read, not re-decided. Full
mechanism, replay verification, and tables: `PREREGISTRATION_FIBO.md`
Section 9.

**AMENDED VERDICT: TEST PASS.** Mean net R +0.3673 (t=6.033), vs both
selection nulls at the 100.0th percentile, on all 188 trades, all four
pre-registered criteria. Band 101-200 -- 58% of trades, the band whose
pessimistic-scenario mean R was -0.1021 under the original (unmeasured)
cost assumption -- is solidly profitable (+0.3478) under the measured
one.

**How this must be cited -- it is weaker evidence than a clean sealed-test
pass, for three reasons that must travel with the +0.3673 / t=6.033
figure wherever it is quoted:**

1. **The window was already read.** This is a re-costing of a trade list
   the sealed test already read once and returned NO EDGE on -- not an
   independent test on new or held-out data.
2. **The correction was made after seeing the failure.** The 19bps/4x
   inputs were refuted by data already in the warehouse, and the error
   applied uniformly to all three bands including the two that already
   passed -- but nobody looked until the number decided a verdict
   (Section 2 above). The sequence was: see the failure, then measure the
   input that caused it.
3. **The cost model rests on a thin measurement.** 5 snapshots across 3
   trading days in one calendar week of October 2026, standing in for the
   entire 2023-2026 sealed window, with only one genuinely volatile
   session represented.

Report this result as *"the sealed trade list is profitable under a
directly measured, rather than assumed, cost model"* -- not as *"the
strategy passed the sealed test."* The second framing drops all three
qualifications above.

**What the three-scenario collapse demonstrates**: under the corrected
model, the original flat-low, flat-high, and pessimistic-banded scenarios
all land on the identical figure. They were never three different costs
-- they were three guesses bracketing one small, now-measured quantity,
and the 0.32R spread between the lowest and highest original scenario was
driven entirely by how wrong those guesses were, not by real uncertainty
in the trade economics. **The sealed test's entire cost-scenario
structure was built on a quantity that, once measured, barely affects the
outcome.**

**By year, stated plainly, not smoothed over**: 2026 is the weakest year
by a wide margin -- +0.0731R on 50 trades, against +0.5888 (2024) and
+0.5770 (2025). The strongest years are the two MIDDLE years of the
window, not the most recent one; 2026 sits closer to 2023 (+0.2699) than
to either 2024 or 2025. At n=50, against 47-48 trades in each other year,
this could be ordinary single-year noise -- or it could be decay in the
most recent period. This document does not have enough information to
tell those apart, and does not adjust the headline figure for it.

**Caveat on this result, added 2026-10-10 (diagnostic on the existing
Section 9 verdict, not a new finding; not a study, no slot spent, no rule
changed):** is 2026's weakness (+0.0731R, n=50) noise or decay, against
+0.5888 (2024) and +0.5770 (2025)?

**Lead with the caveat this diagnostic raised against itself: a bootstrap
comparing 2026's 50 trades to the pooled 2023-2025 138 trades treats every
trade as an independent draw. Trades cluster by stock (the same name can
appear more than once in a year) and by market-wide day (multiple band-
101-200 names can trigger off the same broad move) -- the true variance of
a 50-trade annual MEAN is therefore wider than the 0.1212 this calculation
used, and the bootstrap's p=0.0006 is too small.** The direction of the
finding (2026 sits outside the range ordinary per-trade noise would produce
at this sample size) is probably right; the exact magnitude (how far
outside) is not established by this calculation and should not be quoted
as if it were.

Three things ARE established, independent of that caveat:

- **Setups did not change.** move/ATR (4.89 vs 5.10/5.13/4.59), ORB-width/
  ATR (0.58 vs 0.50/0.52/0.61), trend strength at entry (1.40 vs 1.62/1.22/
  1.27), and rank-band mix all put 2026 inside the range 2023-2025 already
  spans. Band 101-200's share in 2026 (52%) is LOWER than in 2023 (60%) or
  2025 (66%) -- the thin-liquidity band is not more dominant in the weak
  year. Signal generation looks stable; whatever changed, changed in
  outcomes, not in which setups qualify.
- **Both exit mechanisms moved together, not one cleanly.** 2026 has the
  lowest TARGET rate of all four years (8.0%, vs 12.5%/23.3%/19.1%), the
  highest STOP rate (10.0%, vs 8.3%/4.7%/2.1%), AND its TIME_EXIT cohort's
  own mean fell to +0.108 from +0.384 (2024) / +0.361 (2025). Fewer trades
  reach target, more get stopped, and the ones that just ride to 15:15
  make less along the way -- simultaneously, not via one isolated cause.
- **2018 (development) and 2026 (sealed) share a signature.** 2018 is the
  only losing development year (net R hi-cost -0.579, n=5 -- too small for
  any statistical weight of its own). Its exit mix: STOP 40%, TARGET 0%,
  TIME_EXIT mean -0.118 -- stop rate up, target rate down, TIME_EXIT
  cohort negative, same three things moving together as 2026. Recorded as
  a qualitative resemblance between this project's only two weak years,
  not as a replicated statistical finding -- two observations carry no
  weight on their own.

**Operational consequence, stated plainly, not pre-judged**: the forward
paper test now has a second question to answer, not just one. Not only
"does the edge replicate going forward" but "was 2026's weakness ordinary
noise, or the start of decay." The live log settles that on its own
timeline, from new trades the sealed window never saw -- not from more
analysis of the same 188 trades. Nothing here pre-judges which answer the
live log will give.

**How long that takes, computed, since it bounds the wait**: at this
population's per-trade SD of 0.8567, distinguishing a true mean of +0.47
from a true mean of +0.07 (the two candidates this diagnostic is actually
choosing between) at |t|>=2 needs n >= (2 x 0.8567 / 0.40)^2 = **~19
forward trades** with that per-trade variance. At the sealed test's own
historical pace (188 trades / ~44.5 months = ~4.2/month), that is **roughly
4.5 months** of live paper trading -- not years. This is the number that
tells the live log when it can actually speak to this question, not a
reason to wait on it before reading anything else the log produces.

Logged as a diagnostic (not a study, no slot spent, no rule changed) in
`experiments_fibo.csv`.

## 10. Diagnostic: when does the strategy's return arrive, 09:30 vs 11:30 vs 15:15 (2026-10-10, not a study, nothing built)

Two comparisons, fixed in advance (not a minute-by-minute scan): return
09:30 close to 11:30 close, and 09:30 close to 15:15 close, on the 188
sealed-test trades, the 67 development trades (separate), and a control of
every stock-day in that year's top-200 roster. Plus a decomposition of the
strategy's own gross R into the portion realized by 11:30 vs after.

**Lead with the caveat, not the headline: the 09:30-anchored comparison is
largely CIRCULAR and must not be cited as evidence of edge.** Entry
requires a 15-minute candle to close above the opening-range high, so by
construction a trade cannot exist unless the stock already moved up between
09:30 and entry. Measuring a return FROM 09:30 on the traded sample
therefore partly re-measures the entry condition itself, not a result of
the trade. The raw contrast (sealed trades +1.21% by 11:30 / +1.79% by
15:15, vs the top-200 control -0.02% / -0.04% over the same years, both
t-stats enormous given n) is recorded here for completeness but is not
evidence of anything beyond the entry rule doing what it was built to do.

**The honest number is entry-anchored, not clock-anchored**: of the
sealed test's mean gross +0.5150R, computed from each trade's own entry
price (not 09:30, since entries land anywhere in 09:30-11:30):

| window | mean R | pct of gross |
|---|---|---|
| by 11:30 | +0.1830 | 35.5% |
| 11:30 to exit/15:15 | +0.3320 | 64.5% |

**Two-thirds of the strategy's gross return arrives in the back half of the
holding window, after 11:30.** (188/188 trades decomposed; for the 9
already exited by 11:30, realization is 100% "by 11:30" by definition; for
the remaining 179, price at 11:30 was converted to the trade's own raw
price scale via the entry bar's own empirical scale factor -- exact by
construction, since scale is constant within a day -- then expressed in
R-units via that trade's stop distance. Sum of the two halves matches
gross R exactly on every trade, to floating-point precision.)

**Practical consequence, recorded as an observation, not a rule change**:
shortening the exit time would cut away the majority of the edge. The
15:15 exit is doing real work. No rule changes as a result of this
diagnostic, per Section 5a/5b's own discipline -- same treatment as the
TIMING null in Section 6c above.

**Power constraint, n=188**: observed SD 1.130% (09:30 to 11:30) and 1.790%
(09:30 to 15:15) imply a mean return of only 0.165% / 0.261% would already
clear |t|>=2 at this sample size -- this particular sample is not
underpowered for the (circular) clock-anchored contrast above; it is simply
not the right comparison to draw a conclusion from.

**Added mid-run, descriptive only**: exit-time-of-day for the 29 TARGET and
12 STOP exits among the 188 (bucketed 09:30-10:30 / 10:30-11:30 /
11:30-13:00 / 13:00-15:15): TARGET skews late (6.9% / 13.8% / 31.0% /
48.3%), STOP skews slightly less late (0.0% / 25.0% / 33.3% / 41.7%). n=29
and n=12 -- a shape, not a tested claim.

**Standing caution, now twice observed**: an earlier diagnostic (09:27 vs
09:29 entry-time comparison, per the user's own prior read, not re-derived
here) found the opposite sign to what had been eyeballed, in both
populations tested, with no stable sign by year. This diagnostic's own
starting intuition -- that a breakout strategy's gains should show up
early, by 11:30 -- was also reversed by the data (65% of gross R arrives
AFTER 11:30, not before). Twice now, in this project, an eyeballed
intraday pattern has pointed the opposite way from what a decade of
1-minute bars actually shows. Recorded as a standing caution against
reasoning about intraday timing from intuition rather than measurement,
independent of either individual result.

Diagnostic only. Not a study -- no pre-registration, no sealed window read,
no rule changed. Logged in `experiments_fibo.csv`.

## 11. Propagation fix: Bug #1/#2/#11 guards applied to src/fibo/ (2026-10-11)

Full detail in `BUGS.md`'s Bug #11 entry (UPDATE, 2026-10-11) -- recorded
here only as a pointer, since it changes no verdict. `src/fibo/` had none
of this project's lineage-jump, same-isin-jump, or gap-aware-ATR guards
anywhere; a blast-radius check found 0 of the 188 sealed + 67 dev trades'
own signal-computation windows touch a presently-known instance (that
check's own limits -- [0.667, 1.5] ratio band, >5-calendar-day gaps only --
are stated in BUGS.md, not repeated here). Fixed and re-verified: the
sealed 188-trade list is byte-identical; the live evening watchlist for
2026-10-08 reproduces its exact 6 qualifying stocks. **Section 9's amended
verdict (+0.3673R, t=6.033) stands, unchanged, confirmed not contaminated
by this fix.**

One separate thing surfaced during verification, unrelated to the fix
itself: re-running the development-window backtest today returns 278
trades, not the 67 described in Section 4, because the intraday archive
underlying that window grew after the original 2026-09-29 run (confirmed
via a controlled with/without-fix comparison on today's archive: 278
trades either way, zero difference from the fix). **Section 4's "67
trades, 71.6% win rate" is not reproducible from today's warehouse state
for a reason that has nothing to do with this fix** -- flagged, not
investigated or resolved here. The 67-trade pickle was restored rather
than left at 278 so this document's own numbers stay matched to what is
actually saved on disk.
