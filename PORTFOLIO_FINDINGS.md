# Momentum portfolio construction: experiments log

Companion to `PREREGISTRATION_PORTFOLIO.md` (frozen rules, commit
`585e690`). New family, trial 1. Records what was actually run and
found, per the preregistration's own Process section.

## Synthetic unit tests (pre-Step-2, same discipline as every prior study)

`scripts/portfolio_unit_test.py` -- pure-function scenarios, no DB
access: `select_portfolio` (fixed-count selection, decile selection,
equal weight, the rank-weight linear tilt and its own ordering, empty-
pool handling, invalid-weighting rejection) and `turnover_and_cost`
(confirmed to reduce EXACTLY to `scripts/run_holdout_study1.py`'s own
`turnover_frac = len(entered)/len(mom_set)` formula in both the
one-name-swap case and the steady-state complete-replacement case; a
first-ever buy-in correctly gives turnover 0.5, not 1.0, since it has
only one trading leg -- Study 1's own `turnover_frac=1.0` special case
for its first period is a COST-formula convenience, and this module's
own cost figure for that same period was checked separately and matches
it exactly, via each entering name's own tercile rate rather than an
averaged one). **All 17 checks passed on the first run** (one initial
test assertion was wrong -- expected 1.0 for the first-rebalance
turnover rather than the correct 0.5 -- caught and fixed before trusting
the result, not after).

## Section 7 power calculation (Process Step 2)

`scripts/run_portfolio_power_calc.py` -- baseline only (equal weight,
full decile), at each of the three rebalance frequencies, on
development data (2016-01-01 to 2025-03-18, `entity_prices_daily`'s own
physical pre-holdout truncation; 81 same-ISIN-jump entities excluded per
Bug #11; 2,386 entities, 3,318,929 rows, 2,274 distinct trading days).

**Bonferroni threshold: alpha = 0.05 / 24 = 0.002083.** At an
uncorrected 5% bar, P(at least one false positive across 24 trials) =
**70.8%** -- confirms the arithmetic the preregistration states.

| Frequency (days) | N periods | Baseline annualized return | Period return std | MDE, 80% power (annualized) | Bare detection threshold (annualized) |
|---|---|---|---|---|---|
| 21 | 95 | 29.46% | 7.677% | **+45.25 pp** | +34.39 pp |
| 63 | 31 | 27.56% | 15.117% | **+54.38 pp** | +41.93 pp |
| 126 | 15 | 27.53% | 26.971% | **+74.97 pp** | +59.34 pp |

N at 63 days (31) matches the preregistration's own stated estimate
("roughly 32") almost exactly. N at 21 days (95) and 126 days (15) match
the stated ~3x/~0.5x relationship to the 63-day count exactly as
predicted (95/31=3.06, matching 63/21=3; 31/15=2.07, matching 126/63=2).

**Whether the minimum is plausibly achievable: no.** A minimum
detectable EFFECT of 45-75 percentage points of ANNUALIZED return is not
a plausible magnitude for a portfolio-construction change (concentration,
weighting, rebalance cadence) to produce -- realistic effects from these
levers, in the literature and in this project's own prior work, run to
at most low double digits of annualized return, not tens of points. Even
the single BEST case here (21-day rebalance, the highest N and lowest
per-period variance of the three) requires a 45-point swing to register
as significant at the required threshold with 80% power, or 34 points
even at the loosest bare-detection reading with no power guarantee at
all. **126-day rebalance is especially hopeless**: N=15 and the largest
per-period variance combine to require a 75-point swing.

This is stated plainly, per the preregistration's own instruction, not
glossed over: **the grid as designed cannot resolve any realistic
portfolio-construction effect at the Bonferroni-corrected significance
level this study committed to.** This was Claude's own pre-committed
prediction (Section 10: "I expect the power calculation itself to show
a minimum detectable difference that is large relative to plausible
portfolio-construction effect sizes") -- confirmed, not merely close.

**Two structural reasons the variance is this large, worth recording
since they explain WHY the grid is underpowered, not just that it is**:
the development-window baseline's own annualized return (~27-29%,
consistent across all three frequencies) is itself a very large,
high-variance momentum premium -- the same regime this project's own
`PREREGISTRATION.md` "Why now, not sooner" section already flagged
(pre-holdout backtest gap of +12.3 points CAGR vs. benchmark, later
compressed sharply in the sealed holdout to a 3-7pp margin over only
6-7 periods). A signal this volatile at the WHOLE-PORTFOLIO level, over
a sample this small, leaves very little room to resolve a SECOND,
smaller construction effect layered on top of it, at a correction level
as strict as 24-trial Bonferroni.

## Verdict: UNDERPOWERED BY DESIGN -- the grid was not run

**Decision, per explicit instruction**: the study closes on the power
calculation alone. The other 23 configurations are not run. Running
them would not have produced a usable answer -- it would have produced
24 numbers from a comparison that cannot resolve a real effect from
noise at the significance level this study committed to, which is a
worse outcome than not running it at all (a null result from an
underpowered test invites exactly the "well it still mostly didn't
beat baseline" misreading a properly-labelled non-result avoids).

### The finding, stated as the MDE table itself

| Frequency (days) | N periods | MDE, 80% power (annualized) |
|---|---|---|
| 21 | 95 | **45.25 pp** |
| 63 | 31 | **54.38 pp** |
| 126 | 15 | **74.97 pp** |

all under 24-trial Bonferroni (p < 0.002). **Plausible portfolio-
construction effects -- what concentration, weighting, or rebalance
cadence could realistically move annualized return by -- are low single
digits of annualized return.** The grid, as designed, cannot resolve an
effect of that size from noise. It would need an effect **10-20x
larger** than anything concentration/weighting/rebalance plausibly
produces, at every one of the three frequencies, to register as
significant. This is not "the grid is a little underpowered" -- it is
underpowered by roughly two orders of magnitude.

### The cause

The development-window momentum premium itself is a volatile ~27-29%
CAGR (Section 7 above, consistent across all three baseline-frequency
runs). A portfolio-construction effect is, by construction, smaller than
the underlying signal it is layered on top of -- and a signal this large
and this volatile, measured over only 31 quarterly observations (95 at
21-day, 15 at 126-day), leaves a standard error too wide to separate a
plausible construction effect from the noise already present in the
signal itself. This is a property of the DATA (how volatile momentum's
own realized return was in this development window, over this sample
size), not of anything specific to the 24 configurations chosen.

### The baseline stands -- by default, not by having won a contest

**Equal weight, full top decile, 63-trading-day rebalance remains this
project's own best-evidenced construction for `momentum_12_1`.** Stated
plainly, because the distinction matters: **this is not because the
other 23 configurations were tested and lost. It is because they cannot
be tested here, at all, at any significance level this study was willing
to accept.** "The baseline stands" and "the baseline won" are different
claims, and only the first one is true of this result. No configuration
is recommended, preferred, or ruled out by this study -- the honest
state is "unknown, and unknowable from this dataset at this sample
size," not "equivalent" or "no better."

### The transferable lesson -- the second time this exact thing has happened

**This is the second time the binding constraint on a comparison study
in this project has been the variance of the difference, not the size
of the effect being looked for.** `FINDINGS.md` Section 12 (the
momentum + earnings-yield combination study) found the same shape: a
plausible combination effect (IC difference 0.01-0.03) would have needed
**8 to 72 years** of data to distinguish from noise at the paired-IC
metric, its own most efficient measure, let alone the cruder top-decile-
margin metric's own ~87-year requirement. This study finds portfolio
construction needs effects **10-20x larger than any that plausibly
exist** to clear the same kind of bar. Different mechanism (a second
factor's marginal IC contribution there; a construction choice's
marginal return contribution here), same shape of failure: **a
comparison study, fully specified down to its decision rule, run into a
sample whose own noise floor was never checked against the effect size
being looked for.**

**The standing lesson, recorded here for reuse, not just for this
study**: before designing a comparison study -- any study whose verdict
rests on configuration A beating configuration B by some margin -- compute
the minimum detectable difference FIRST, from the data's own observed
variance, before finalizing which configurations to even include. Both
times in this project, the full grid or combination design was specified
down to every parameter before anyone checked whether the data could
answer the question being asked. The check is cheap (one baseline
run's worth of variance, in this study's own case); the alternative is
discovering it only after the comparison has already been run, or not
discovering it at all and reporting an underpowered null as if it meant
something.

### Claude's prediction was correct about the mechanism, not just the verdict

Worth recording plainly, since most of this project's prior predictions
(Study A's own cost-mechanism miss, Study B's own follow-through-
direction miss) got the VERDICT right while being wrong about WHY.
Section 10's own pre-committed prediction stated: "I expect the power
calculation itself to show a minimum detectable difference that is
large relative to plausible portfolio-construction effect sizes." That
is exactly what happened, not merely a correct top-line guess -- the
mechanism (variance of the baseline signal swamping any resolvable
construction effect) was anticipated before the numbers existed, one of
the few predictions in this project's own history to be right about the
mechanism and not just the outcome.

## Status

**CLOSED. Verdict: UNDERPOWERED BY DESIGN.** The grid (23 remaining
configurations) was never run, by explicit decision, not by omission.
**TEST was never relevant to this study** -- per `PREREGISTRATION_
PORTFOLIO.md`'s own hard constraint, there is no sealed window for
portfolio-construction testing (`FINDINGS.md` Section 7, retired); this
closure has nothing to do with any TEST/holdout evaluation, sealed or
otherwise, because none exists for this study to reach.

**Portfolio family: 1 trial, closed underpowered.** Project-wide tally:
seventeen studies.
