# Swing Trading (1-5 Day Horizon): Findings

Full process record (phase-by-phase build, every intermediate number,
every correction): `SWING.md`. Frozen rules and methodology:
`PREREGISTRATION_SWING.md` (the original V4 rule) and
`PREREGISTRATION_SWING_V1.md` (the decomposition's best candidate, V1
Top-10 concentrated, and the sealed-holdout test of it). This document is
the conclusion, written last, in the main project's `FINDINGS.md` style.

## 1. The question

Is there any 1-5 day horizon, universe, and condition set on NSE equities
where expected return exceeds realistic retail transaction costs?

## 2. The answer

**No.** Two rules were tested. Both failed -- one against the right
benchmark, in-sample; the other out-of-sample, on data neither rule's
design ever saw.

## 3. The sequence, because it is the useful part

**V4 (the original frozen rule: momentum-top-decile stocks in the bottom
tercile of 5-day return market-wide, with elevated volume AND the broader
market in an uptrend, held 5 trading days)** sat at the **9.8th percentile**
of a random-entry null distribution drawn from its own candidate pool,
matched trade count and timing, 1,000 seeds, on clean data -- worse than
~90% of random draws from the same population on the same days.

**Decomposition** (`scripts/run_swing_phase3_decomposition.py`, 6
pre-specified computable variants, Bonferroni- and Benjamini-Hochberg-
corrected) identified which of V4's own conditions caused this: the
volume filter and the regime filter, not the dip condition itself. Removing
both and keeping only the dip condition (**V1**) scored the **100th
percentile, p=0.0010**, on **65,219 pre-holdout trades**, clearing both
corrections across the 6-variant family -- the strongest result this
project's price-based work has ever produced, formally.

**V1 on the sealed holdout** (`scripts/run_swing_v1_holdout.py`,
`PREREGISTRATION_SWING_V1.md`'s frozen decision rule, Top-10-per-day
concentration by dip magnitude for capital efficiency): **61.4th
percentile, p=0.387, on 3,620 holdout trades**. Indistinguishable from
random selection from the same pool on the same days. Expectancy -0.019%
at worst-case cost (profit factor 0.99), 0.111% at optimistic cost
(profit factor 1.05) -- reported with the pool-contamination caveat
`PREREGISTRATION_SWING_V1.md` Section 5 attaches, not as a clean pass/fail
on its own. **FAIL against the pre-registered threshold (percentile >= 95).**

## 4. The honest reading: two possibilities the data cannot separate

Either the short-term-reversal-within-momentum-winners effect was real in
the pre-holdout years and decayed, or the 6-variant decomposition selected
the best of six candidates on a period where it happened to work, and the
Bonferroni/BH correction -- which controls for the 6 variants tested
simultaneously -- could not and did not control for the further,
undisclosed-family searching layered on top of that (the Top-10
concentration sweep, the capital checks, the year-by-year robustness
check, all run on the same pre-holdout data before the holdout was read;
`PREREGISTRATION_SWING_V1.md` Section 0 states this plainly). **This
document does not choose between those two readings -- the holdout result
is consistent with either.**

One piece of pre-holdout evidence now reads differently in light of the
holdout result than it did before the holdout was read. V1's own
pre-holdout year-by-year breakdown showed two failures with no
identifiable cause: the 1.1st percentile in 2021 and the 10.1st percentile
in 2024, against nine separately measured observables (POOL_ML's own
return, cross-sectional dispersion, NIFTY return and volatility, V1's own
average dip magnitude, trade count, candidates/day, unique entities
selected, trades per entity) -- none of which separated those two years
from the other seven cleanly enough to survive an individual-year check
(`PREREGISTRATION_SWING_V1.md` Section 3). At the time, this was recorded
as an isolated, unexplained limitation confined to 2 years out of 9. **In
light of the holdout also failing, with no new condition invoked and no
new mechanism found, 2021/2024 now look less like two anomalies inside an
otherwise-real effect, and more like an early, smaller-sample view of the
same thing the 18-month holdout shows at full scale: this configuration's
edge is not stable across time**, whether or not it was ever real to begin
with.

## 5. What an in-sample result at p=0.001 on 65,219 trades is worth

**This is the sharpest lesson of the project.** V1 was not a thin,
marginal, easily-dismissed result. It cleared a Bonferroni- and BH-
corrected significance threshold, across a pre-specified family, on a
sample two orders of magnitude larger than the original rule's (65,219
trades vs. V4's 4,146), with a mechanistically stated rationale
(`PREREGISTRATION_SWING.md`: established winners having a bad week is a
more specific, more plausible setup than an unconditional reversal
screen). Every ingredient that is normally treated as protection against
a false positive -- large sample, formal multiple-comparisons correction,
a story that makes sense before the number existed -- was present. **None
of it substituted for the holdout.** A result this strong in-sample
reverted to statistical noise (and a profit factor below 1 at worst-case
cost) the first time it faced data its own construction had never touched.
Sample size is not a substitute for out-of-sample evidence, at any p-value.

## 6. The cost gate, which preceded everything, and which both rules ultimately confirm

Phase 1 (before any rule was designed) found that break-even at a 5-day
horizon required roughly IC=0.05 at a Rs 5L+ position -- and even that one
cell failed the standing 3x hurdle. IC=0.05 exceeds the strongest signal
this project has ever measured at any horizon: `earnings_yield`'s IC
+0.0393 at a 63-day horizon (itself only "suggestive," failing
multiple-comparisons correction). This bar was stated explicitly before
either rule existed, specifically so a favorable-looking backtest number
could not later be mistaken for having cleared it.

**Both rules confirm it, by two different routes.** V4 never reached the
cost question at all -- it could not even beat random selection from its
own pool, so whether it cleared costs was moot. V1 was the candidate that
looked, briefly, like it might be the exceptional signal Phase 1 said
would be required: positive expectancy, a 100th-percentile selection
result, a plausible mechanism. On the one test designed to check whether
it truly was exceptional, it was not -- expectancy at worst-case cost went
slightly negative, and the percentile fell to statistical noise. Three
attempts now (V4 pre-holdout, V1 pre-holdout, V1 holdout) have each
independently landed on the same conclusion Phase 1 predicted before any
of them were built: this cost structure, at this horizon, needs an edge
stronger than anything this project has produced, and nothing tested has
been that edge.

## 7. Bug #12: the fundamentals screener was specified but never applied

`PREREGISTRATION_SWING.md`'s Universe section froze a fundamentals-
screener risk filter (`fundamental_screener.py` verdict != FAIL) as
condition 5. It was never applied in any candidate-count check or
backtest this project ran -- confirmed by reading
`run_swing_phase2_candidate_counts.py` and both Phase 3 backtest scripts
directly, none of which reference the screener at all. Root cause:
`fundamental_screener.py` only evaluates a CURRENT, as-of-today verdict;
no point-in-time historical series exists across the years these
backtests span. **V5 and V6** (the two decomposition variants that would
have added this screener on top of the dip condition, with and without
the regime filter) **were therefore never computable** -- reported as
NOT COMPUTABLE rather than silently dropped, and logged as `BUGS.md` Bug
#12, the same class of defect as Bug #7 (a spec written assuming a
capability the actual code did not have at the point it was invoked).
Building a point-in-time historical screener remains a separate,
un-started undertaking.

## 8. Capital: the binding practical constraint, independent of either verdict

**V4** (clean data): peak concurrent positions 81, peak capital Rs 2.43
crore at the Rs 3L floor -- ~7.6x the original back-of-envelope estimate
(2.2 entries/day x 5-day hold), because entries cluster in bursts rather
than spreading evenly. **V1, uncapped**: peak concurrent positions 348,
peak capital Rs 10.44 crore -- concentrating to the Top-10-per-day
configuration (the version actually pre-registered and holdout-tested)
brought this down to 64 positions / Rs 1.92 crore pre-holdout, and 55
positions / Rs 1.65 crore in the holdout itself, at a cost of roughly 0.10
percentage points of worst-case expectancy relative to the uncapped
version. Concentration solved the capital problem; it did not solve the
edge problem -- the holdout result in Section 3 is for this same
capital-efficient, Top-10 configuration.

## 9. Bug #11: a real, independent finding, regardless of either rule's fate

Found while sanity-checking V4's single worst trade (a -98.6% "return" on
MAJESCO that was actually the real December 2020 Majesco demerger, never
corrected by `adjustment_factors`): **a same-ISIN uncorrected corporate
action is unguarded anywhere in this codebase.** `lineage_jump_guard`
(Bug #1's fix) only checks the boundary between an ISIN and its lineage
successor; a jump within one ISIN's own continuous row sequence is
structurally invisible to it. A new detector
(`src/data_layer/same_isin_jump_guard.py`, 4 tests) scanned the full
warehouse: 288 rows across 78 entities carry this exact,
previously-unguarded shape. Excluding them moved V4's headline percentile
from 9.0 to 9.8 -- immaterial to that conclusion, but the gap itself is
real and plausibly affects the main momentum project's own price-based
factors for any entity with this shape of event, unchecked there. Checked
against the sibling `trade-info` project before writing anything there:
it already has a pipeline-wired detector for this exact shape
(`src/nsepit/quality.py`'s `PriceDiscontinuity`); no entry was added
there.

## 10. Holdout ledger

`FINDINGS.md` Section 7: **2 of 3 project-wide holdout reads now spent, 1
remaining.** The first (Study 1, momentum_12_1) belongs to the main
project. The second belongs to this project -- V1's Top-10 configuration,
charged and logged per `PREREGISTRATION_SWING_V1.md`'s explicit decision
to treat the swing project's read as one of the two slots the main
project's Study 1 left available, not a separate allocation.

**Stated plainly, per instruction: the one remaining slot should not be
spent on another short-horizon (1-5 day) variant.** Three independent
attempts -- V4 pre-holdout, V1 pre-holdout, and V1 on the actual sealed
holdout -- have now each landed on the same conclusion Phase 1's cost
gate predicted before any of them existed: this horizon's cost structure
requires an exceptional signal, and nothing produced by this project's
methodology, including the strongest in-sample result it has ever
generated (Section 5), has been that signal. A fourth short-horizon
attempt would be re-litigating a question three independent tests have
already answered, at the cost of this project's last shared holdout read.
If the remaining slot is spent, Section 6's own named candidates
(Value/Quality/Size construction, or a `trailing_vol_252`/`beta_252`
retest) are the ones still open -- not decided here.

## 11. What this does and does not conclude

**Concludes**: at the 1-5 day horizon, on the momentum-top-decile/
liquidity-screened universe this project constructed, no rule tested --
including the one that cleared a Bonferroni- and BH-corrected 100th-
percentile in-sample result on 65,219 trades -- has a demonstrated,
out-of-sample edge over the cost structure this horizon imposes. The cost
gate identified before any signal existed (Section 6) is the finding both
rules ultimately confirm, not a footnote to either of them.

**Does not conclude**: that no 1-5 day edge exists on NSE equities under
any conceivable rule, universe, or mechanism. Two rule families, one
universe construction, sharing one candidate pool, were tested. A
genuinely different mechanism or universe remains untested in principle
-- but Section 10's ledger constraint means this project is not the one
positioned to test it with what remains of the shared holdout resource.
