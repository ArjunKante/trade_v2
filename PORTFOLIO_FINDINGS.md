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

## Status

**STOPPED per `PREREGISTRATION_PORTFOLIO.md` Section 11 Step 2.** Only
the baseline configuration has been run, at all three rebalance
frequencies; none of the other 23 grid configurations has been touched.
Waiting for the user's explicit approval before running the full grid,
given the power calculation's own finding that it is unlikely to
resolve anything at the committed significance level.
