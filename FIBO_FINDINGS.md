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
3's verdict (or Section 9's later amended re-test, or Section 13's second
amended re-test under a corrected scale method) comes out.

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

## 12. Section 9's 188 trades were stable by luck, not by enforcement (2026-10-11)

Full detail in `BUGS.md`'s Bug #14 entry -- recorded here as a direct
statement against Section 9's own verdict, not just a pointer, because it
is a fact about how that verdict was produced.

**`fibo_test_backtest.py` (the sealed-test script) never enforced the
top-200 universe it is specified on.** Its entity list was built from
whatever had been downloaded into `bars_1min`, not filtered against
`reconstitute_annually`'s declared membership -- the exact same
unenforced shape the development-window script had (Section 11 above),
which silently returned 278 trades instead of 67 once its own archive grew
beyond its top-50 specification. Checked directly for the sealed window:
zero of the 785 (year, entity) combinations actually evaluated in the
current 188-trade result fall outside the declared top-200 roster, and
zero trades carry the `"unranked"` tag the script's own code would apply
to an out-of-universe entity. **The 188 is correct, but it was correct
because the sealed window's intraday archive happened not to grow the
same way the dev window's did -- not because the script would have
refused to trade an out-of-universe name if one had appeared.** The
mechanism that corrupted the dev-window count was fully capable of
corrupting this one too; it simply didn't fire here.

**Section 9's amended verdict (+0.3673R, t=6.033) is unaffected by this
finding** -- it is a statement about how the number was produced, not a
revision of the number itself. A filter and an independent guard
(`src/fibo/universe.py`: `restrict_to_universe`, `assert_universe_membership`)
are now in place in all three Fibo backtest scripts, so this cannot recur
silently again; `src/fibo_live/watchlist.py` (the live system) already
enforced its universe correctly and needed no change. Not yet re-run as
of this entry -- reported before execution, per instruction.

## 13. SECOND AMENDED RE-TEST, CORRECTED SCALE (2026-11-03)

**The requested section number was 11; Sections 11 and 12 above already
exist and are left exactly as written. This is Section 13, not a
renumbering of anything above it.** Sections 3 (the original sealed
verdict, NO EDGE), 6b, 9 (the first amendment, cost-only, TEST PASS), and
12 all stand unedited above this section.

### 13a. Trigger: Bug #18

`BUGS.md`'s Bug #18 found that `fibo.backtest.evaluate_entity_day`
converted the golden zone/swing high to raw scale via the table-based
`adjustment_factors` method while converting that same day's own candles
via `fibo.scale_probe`'s empirically-validated method -- two different,
uncross-checked answers for the same day's scale, compared against each
other inside `zones_overlap`. A blast-radius measurement against the
already-published 188 TEST and 67 DEV trades found 9 and 5 trades
respectively where the two methods disagreed materially, all 9 and all 5
flipping `zones_overlap` from True to False under the correct scale --
i.e. 9 of 188 sealed-test trades were false positives that should not
have existed, and they were not neutral: their own mean net R (0.875)
sat far above the other 179 trades' (0.342), meaning they inflated the
sealed test's own headline mean.

### 13b. The scoping lesson: that first measurement only checked one direction

Recorded in full as a new standing rule in `OPERATIONS.md`, stated briefly
here because it is the reason this section's trade count is not simply
"188 minus 9." The blast-radius measurement in 13a only checked whether
already-selected trades would be REJECTED under the corrected scale. It
never checked the reverse -- whether days the ORIGINAL code rejected as
`SETUP_OFF` should have been accepted -- because that was not the
question the measurement was built to answer. A selection-stage bug, by
construction, has two failure modes, and a measurement that samples only
one side of the boundary cannot see the other.

**The reverse direction was 6x larger than the one originally checked.**
Fixing the scale method in `src/fibo/backtest.py` (one method,
`fibo.scale_probe`, used for both the candles and the golden zone/swing
conversion -- no other rule touched) and re-running the DEV window end to
end, FIRST, as a verification step before touching TEST: the 62 trades
unaffected by the mismatch reproduced byte-identical (one sub-0.01%
floating-point difference, immaterial), the 5 known-bad trades were
correctly gone -- and 58 previously-wrongly-rejected days flipped to
TRADE. DEV went from 67 to 120 trades, not 67 to 62.

### 13c. The TEST re-run: trade count, gains and losses broken out

One read, same frozen rules, same window (2023-01-01 to 2026-09-18,
top-200 universe), only the scale method changed.

| | count |
|---|---|
| Original (188) | 188 |
| LOSSES (correctly rejected under the fix) | 9 |
| GAINS (previously wrongly rejected, now correctly accepted) | 37 |
| **New total** | **216** |

The 9 losses are exactly the 9 identified in 13a (verified by key match,
not assumed). The 179 trades not touched by the fix are byte-identical to
their originals (8 of 179 show a sub-0.1%-relative floating-point
difference in `target` from `scale_probe` not being bit-identical to
`1/factor` even on non-mismatching days -- immaterial, no exit_reason
changed). The 37 gains are new; five were spot-checked by hand against
`scale_probe` directly and all five showed the identical signature as
13a's 9 losses (the table method defaulting to `factor=1.0` -- no
adjustment recorded at all -- against a real, non-unity `scale_probe`
measurement of 1.04-1.65), and three of the five sampled entities
(`INE155A01022`, `INE628A01036`, `INE397D01024`) are the same entities
independently flagged with matching stable ratios in the unrelated
Liquidity-family analysis that first surfaced Bug #18.

**Comparison against the 179-trade subtraction-only basis originally
scoped** (188 minus the 9 losses, gains not added -- i.e. the "half
correction"), to make the difference between the two visible:

| scenario | 179-trade (subtraction only) | 216-trade (full correction) |
|---|---|---|
| (i) flat low | mean +0.3361, t=5.446 | mean +0.2612, t=4.548 |
| (ii) flat high | mean +0.2499, t=4.096 | mean +0.1753, t=3.078 |
| (iii) pessimistic banded (refuted 4x) | mean **+0.0166**, t=0.270 | mean **-0.0443**, t=-0.774 |
| (iv) measured banded (Section 8c) | mean +0.3418, t=5.529 | mean +0.2679, t=4.661 |

The half-correction and the full correction disagree even on the SIGN of
scenario (iii)'s mean (marginally positive but not remotely significant,
vs. negative) -- both fail criterion 2 there, for different reasons, and
neither the 179-trade nor the 216-trade figure is "the" scale-corrected
result; only the full, two-directional re-run (216) is, per 13b.

### 13d. Which cost model was the re-run evaluated against -- resolved before writing a verdict

`fibo_test_backtest.py` computes `net_r_lo_cost`/`net_r_hi_cost` (flat
6/19bps) and `net_r_pessimistic` via the ORIGINAL 19bps x{1,2,4}
multiplier -- the same three scenarios Section 6b used, not the Section
8c/9 measured banded model (2.0/4.0/7.0bps by band). The corrected-scale
216-trade population was evaluated under all four, applying Section 8c's
frozen formula directly to the existing trades (no new data read):

**ALL FOUR CRITERIA, ALL FOUR COST SCENARIOS:**

| scenario | mean net R | t | vs null (b) | vs null (b2) | criterion 2 | criterion 3 | criterion 4 | verdict |
|---|---|---|---|---|---|---|---|---|
| (i) flat low | +0.2612 | 4.548 | 100.0th | 100.0th | PASS | PASS | PASS | **PASS** |
| (ii) flat high | +0.1753 | 3.078 | 100.0th | 100.0th | PASS | PASS | PASS | **PASS** |
| (iii) pessimistic banded (refuted 4x) | -0.0443 | -0.774 | 100.0th | 100.0th | **FAIL** | PASS | PASS | **FAIL** |
| (iv) measured banded (Section 8c, frozen) | +0.2679 | 4.661 | 100.0th | 100.0th | PASS | PASS | PASS | **PASS** |

Criterion 1 (>=100 trades): met, 216.

**Stated plainly, per instruction, rather than reported as a flat
failure: the corrected-scale re-test PASSES all four criteria under
every cost scenario tested EXCEPT the one scenario (iii) already
refuted on its own stated grounds in Section 5d/8c -- band 101-200
measured at ~3.2bps live against the 76bps that scenario's 4x
multiplier implies.** Scenario (iii) fails criterion 2 alone (mean <= 0);
criteria 3 and 4 would also have passed there, at the 100th percentile,
exactly as in every other scenario -- the entry mechanism's non-random
selection value is not in question in any scenario, including the
refuted one. Judged strictly against the ORIGINAL three-scenario frozen
rule (i, ii, iii only), this re-test still reads NO EDGE, since all three
original scenarios must pass and (iii) does not. Judged against the
measured, live-grounded cost model this project already adopted in
Section 9 to produce its own first amended PASS, this re-test is an
unambiguous, clean PASS -- a materially stronger result than Section 9's
own amendment, since here even the refuted multiplier's own FAILURE is
explained by a cost assumption already known to be wrong, not a genuine
finding about the strategy.

**AMENDED VERDICT: TEST PASS, under the measured cost model.** Section
3's original "NO EDGE" headline is left unedited above -- it remains the
accurate record of what the ORIGINAL sealed read, under its own original
three scenarios, returned. This section's verdict is a SEPARATE,
later statement about what the SAME window reads under a corrected
selection mechanism and the cost model this project has, since Section 9,
already established as the grounded one.

### 13e. By rank band

| band | n | win rate | mean gross R | mean net R (measured) | mean net R (refuted pessimistic) |
|---|---|---|---|---|---|
| 1-50 | 51 | 72.5% | 0.4869 | **+0.3514** | +0.2146 |
| 51-100 | 47 | 63.8% | 0.2859 | **+0.1569** | -0.0441 |
| 101-200 | 118 | 66.1% | 0.4325 | **+0.2761** | -0.1563 |

The same mechanism Section 9e already documented recurs here: band
101-200 (118 of 216 trades, 55%) is the band whose refuted-pessimistic
mean is negative, and it is solidly profitable under the measured cost.
Band 51-100 is newly negative under the refuted scenario here (it was not
in Section 6b/9, at a smaller n) -- a detail of the already-refuted
scenario, not of the measured one, where all three bands are positive.

### 13f. By year

| year | n | win rate | mean gross R | mean net R (measured) |
|---|---|---|---|---|
| 2023 | 61 | 60.7% | 0.3635 | +0.2032 |
| 2024 | 61 | 63.9% | 0.4111 | +0.2658 |
| 2025 | 44 | 81.8% | 0.7159 | +0.5821 |
| 2026 | 50 | 66.0% | 0.2109 | +0.0731 |

2026 remains the weakest year (n unchanged at 50 -- none of this year's
trades were touched by the scale fix in either direction), reproducing
Section 9f's own figure for 2026 exactly. All four years individually
net-positive under the measured model, same as Section 9.

### 13g. Exit-reason breakdown

| reason | count | % |
|---|---|---|
| TIME_EXIT | 169 | 78.2% |
| TARGET | 29 | 13.4% |
| STOP | 18 | 8.3% |

Same shape as Sections 6b/9 (most of the result is intraday drift held to
the close, not bounces off the golden zone); STOP's share rose slightly
(8.3% vs 6.4%) -- consistent with 37 new, previously-unseen trades
entering the population.

### 13h. TIMING null (descriptive only, not a TEST PASS criterion)

Strategy at the **0.0th percentile**, every cost measure (gross, lo, hi,
pessimistic, measured) -- MORE extreme than Section 6b's original 2.3rd
percentile and Section 9's 2.2nd. The specific ORB-breakout entry trigger
underperforms a random entry time on the same good days even more
starkly in the corrected-scale population than in the original. Unchanged
conclusion from Section 6b/9: a candidate for a future, separately
pre-registered study on entry timing, not acted on here.

### 13i. HOW THIS RESULT MUST BE CITED -- four caveats, expanded from Section 9i

**Wherever the +0.2679R / t=4.661 figure (or the 216-trade count) is
cited, all four of the following must be cited alongside it:**

| # | reason | why it weakens the result |
|---|---|---|
| 1 | **The window was already read -- twice before this.** | The original sealed test (Section 6b) and the first amended re-test (Section 9) both already read this window. This is a THIRD read of the same window, not independent data. |
| 2 | **The scale correction was made after seeing a failure.** | Bug #18 was found while building an unrelated post-hoc diagnostic over closed Liquidity trades, not while auditing Fibo. But the decision to recompute TEST under the corrected scale was made knowing Section 6b had already failed and Section 9 had already amended once -- the same "see the failure, then go measure the input" sequence Section 9h already named as the real lesson of this project's prior amendment. |
| 3 | **The cost model this re-test passes under rests on a thin measurement.** | Section 8c/9's measured banded model (2.0/4.0/7.0bps) is 5 valid snapshots across 3 trading days in one calendar week (2026-10-05/07/08). That limitation is inherited here in full, unchanged, unresolved by this section. |
| 4 | **The trade list itself was wrong until now, and wrong in the direction that flattered the result.** | 9 of the original 188 trades were false positives averaging 0.875R against the population's 0.342R (the other 179) -- the uncorrected sealed test's own headline mean was inflated by a selection-stage bug, not just mis-costed. The correction that fixes this also adds 37 previously-missed trades (13c) -- the trade list changed substantially in BOTH directions, not merely trimmed. |

**This verdict should be reported as: "the sealed trade list, re-selected
under a corrected scale method, is profitable under a directly measured,
rather than assumed, cost model, in a window that has now been read three
times" -- not as "the strategy passed the sealed test."** A result
requiring two separate amendments (one to the cost model, one to the
selection mechanism) to a twice-already-read window is weak evidence
regardless of what the corrected number says. If the figure in 13d had
come back failing under the measured model too, that would have been
reported as a failure in the first sentence of this section; it did not,
and that is reported here with exactly the same directness.

### 13j. Status

**PASS under the measured cost model; FAIL under the already-refuted
pessimistic multiplier; NO EDGE under the strict original three-scenario
rule taken literally.** All three readings are reported because they are
all true simultaneously of the same number -- which one is "the" verdict
depends on which cost model is trusted, and Section 9 already settled
that question in favor of the measured one for this same reason, before
this section existed. **This PASS should be read as grounds to continue
the forward paper test (`fibo_evening.py`/`fibo_morning.py`), not as
grounds to believe the backtest.** Not yet propagated to the live system
-- Bug #18 was found not to affect `fibo_morning.py`'s own zone
conversion structurally (today's own `adjustment_factors.factor` is 1.0
by construction, verified directly across all 175 live watchlist rows
logged since 2026-10-08), so no live-system change is implied by this
section.
