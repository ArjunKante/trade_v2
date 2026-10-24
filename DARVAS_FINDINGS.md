# Darvas Box theory, faithful version: experiments log

Companion to `PREREGISTRATION_DARVAS.md` (frozen rules, commit `0373d00`,
amended twice before any number existed -- `5523bb4` named the missing
6th box outcome, `600fbc2` defined Sub-rule 1's "later box" precisely).
Records what was actually run and found, per that document's Process
section.

**Bottom line, stated first per this project's "bad results first"
discipline: DEV FAILS, decisively, on every gate condition. Darvas's own
breakout trigger and trailing stop both subtracted value rather than
adding it.** The real strategy's mean net R sits at the very bottom of
all three null distributions: **0.0th percentile against TIMING, 0.3th
against SELECTION, 0.3th against MOMENTUM** (the primary null). A
uniformly random entry timed off the exact same box signal beat the real
entry-and-trail rule in essentially all 1,000 draws. This is not "Darvas
is a more complicated way of measuring momentum" -- the momentum null
result alone would say that. **It is worse than doing nothing clever at
all with the same boxes.** The sealed TEST window is never read.

## Universe-membership verification (done before trusting the DEV number)

Before the real run, 509 of 1,266 pre-restriction trades (40.2%) were
being dropped for not belonging to a declared top-200-by-turnover
universe member in their own entry year -- high enough to check
specifically for a date-alignment bug before accepting it:

- **No year-boundary clustering.** Drop counts by calendar month of
  entry are flat (28-64 per month across all twelve); only 21/509 (4.1%)
  fall within 5 calendar days of a Jan1/Dec31 boundary, close to the
  ~2.7% base rate pure chance would produce.
- **Sample dropped cases resolve to an economically coherent story, not
  an artifact.** E.g. `INE006I01046`/`INE010V01017`: real companies,
  real Darvas signals in 2017-2021, but turnover-universe membership
  only starting 2022-2024 -- their price action moved before their
  turnover rank caught up. Across all distinct dropped (entity, year)
  pairs, 24.9% become a member the very next year, consistent with the
  point-in-time rule's one-year turnover lag, not a bug in it.
- **0 of 175** distinct dropped entities are "never a universe member in
  any year" -- rules out a mismatch between the fetched panel and the
  declared universe.
- **Independent cross-check, bypassing `fibo.universe`'s own
  arithmetic**: pulled `INE008A01015`'s own 2020 median turnover
  straight from `prices_eod` (Rs 57,358,262) against 2021's actual
  rank-200 cutoff (Rs 191,863,231) -- confirms the exclusion by raw
  turnover, not by trusting the module that produced the drop to also
  grade itself.

Clean. This was a real risk of a wrong headline number (either direction
-- a date-alignment bug could as easily have inflated the trade count as
deflated it), and it is recorded here because it was checked, not
assumed.

## DEV result

757 trades, 501 distinct entry days, 2016-01-01 to 2022-12-31, full
top-200-by-turnover universe (428 entities ever members), 1000 seeds
each for TIMING and SELECTION (the 20-seed timed probe projected well
under the ~1-hour budget for both, so neither fell back to 500), a
single deterministic MOMENTUM alternate set (712 of 757 real trades
matched to a same-day top-`momentum_12_1` universe member -- 45 had no
exact-date price for their matched stock and are excluded from that
null only). Runtime 2.3 minutes total, peak ~450MB.

| | |
|---|---|
| Trades / distinct entry days | 757 / 501 |
| Win rate | **34.5%** |
| Mean net R (97.5% CI) | 0.0363 [-0.0839, 0.1682] |
| Median net R (descriptive) | **-0.3282** |
| MDE | 0.1280 |
| TIMING null percentile | **0.0** (1000 seeds) |
| SELECTION null percentile | **0.3** (1000 seeds) |
| MOMENTUM null percentile (primary) | **0.3** (deterministic, 712/757 matched) |
| Ex-best-year mean (drops 2017) | **-0.0283** |
| Exit mix | STOP 751 / FORCED_WINDOW_CLOSE 6 |
| Forced-window-close contribution | +2.0151 (6 trades) |
| Peak concurrent positions / capital | 55 / Rs 301,471 |
| **DEV_PASS** | **False** |

**By year (net R)**: 2016 +0.095 (11), **2017 +0.229 (190, the best
year, excluded for the ex-best-year check)**, 2018 -0.242 (73), 2019
-0.255 (74), 2020 +0.049 (104), 2021 +0.091 (241), 2022 -0.118 (64).
Dropping 2017 alone flips the whole DEV sample negative -- the entire
positive headline mean is a single calendar year's contribution.

**By band (net R)**: 1-50 **-0.051** (207), 51-100 **-0.101** (215),
101-200 **+0.179** (335). Whatever apparent edge exists sits entirely in
the thinnest, least-liquid band; both liquid bands (1-100 combined) are
negative. This is the identical thin-names dependency
`PREREGISTRATION_BOX.md` Section 7 built its own "bands 1-100" check to
catch in that unrelated family -- recorded here as the same failure
shape recurring in a different study, not copied from it.

**Holding period**: mean 29.8 trading days, median 20, max 252
(open-ended by construction -- no time limit, no profit target).

**Box construction**: 2,165 complete breakouts, 2,407 complete
breakdowns, 584 broke out before their own bottom ever confirmed
(untradeable -- no defined stop), 119 trend-filter failures, 48
unresolved at window end, 8 top-never-confirmed, 5 bottom-never-confirmed
(the amended 6th outcome -- rare, as expected for a boundary case).
**Same-day top-and-bottom confirmation: 891 of 4,620 complete boxes
(19.3%)** -- the book's claim that this is common holds up on real data.
**"Never broke out" (breakdown + unresolved): 2,455** complete boxes
that formed and then either failed downward or simply ran out of data.

## Win rate, median, and mean: the classic trend-following shape, and the mean is not real

**34.5% win rate, median net R -0.328, mean net R +0.036.** A small
number of large winners (the kind Trace 2's hand-trace of the long-
running KOTAKBANK position showed, net R +3.03 over 252 trading days)
are carrying a population where the typical trade loses close to a third
of its risked capital. This is the textbook trend-following payoff
shape -- frequent small losses, rare large wins -- and by itself that
shape is not disqualifying; many genuinely profitable systems look
exactly like this. **What is disqualifying is that the mean, the one
number that shape depends on being real, has a 97.5% CI that comfortably
straddles zero, and sits at the bottom of all three null distributions.**
The shape is present; the edge inside the shape is not demonstrated.

## The no-pyramiding simplification's cost

**828 breakout signals were skipped because a position was already
open** in that entity -- more than the 757 trades actually taken.
`PREREGISTRATION_DARVAS.md`'s own Discipline section recorded this
tradeoff before any number existed: Darvas's book attributes much of his
own return to concentrating capital into winners by adding to them as
new boxes formed, and this version deliberately does not implement that,
to keep per-trade statistics comparable to every other study in this
project. **Stated plainly, as a limitation of what was tested, not as an
excuse for the result above**: it is possible a pyramiding version
behaves differently, and this study does not test that version. What it
does test -- one position per entity, breakout entry, box-trailing exit
-- failed on its own terms, independent of this simplification. The
828-skip count is reported so the simplification's scale is visible, not
to suggest it explains the failure.

## What the three null results actually say, taken together

The MOMENTUM null is the one that matters most here, per instruction,
and it is unambiguous: the SAME universe-year, on the SAME entry dates,
buying whichever stock simply had the highest trailing `momentum_12_1`
-- a signal that has already cleared a genuinely sealed, first-exposure
holdout in this project (`PREREGISTRATION.md`/`FINDINGS.md` Study 1) --
beat Darvas's own box-and-breakout stock selection in 99.7% of the
resampled comparison. But the TIMING null result is the more pointed
one: it does not change the STOCK or the STOP at all, only the DAY of
entry, within 20 trading days of the exact box this study's own engine
detected -- and it beat the real rule in 100% of 1,000 draws. **That
means the box construction's own timing signal -- the breakout trigger
itself, the specific day price closes above the top -- carries negative
information, not merely zero.** Combined with the SELECTION null's
near-identical 0.3rd-percentile result (a random stock-day with a
matched stop distance, no box required at all), the conclusion is not
"this needs a better entry filter" -- it is that this specific
breakout-and-trail construction, as frozen before any of these numbers
existed, has no demonstrated edge over several cheaper alternatives,
including one that ignores the box entirely.

**Status: closed.** Per `PREREGISTRATION_DARVAS.md` Section 6 and
Section 9's Discipline, this result is not rescued by retrying the
200-day lookback, the 3-day confirmation, the 50-day trend filter, or
`RUN_THRESHOLD_R` at other values -- all four are FIXED by that document
and stay fixed. The sealed TEST window (2023-01-01 to 2026-09-30) is
never read and remains sealed.

**Family tally**: Darvas Box theory is a NEW family, independent of the
unrelated `box_theory`/`box_theory_v2` family (previous-session-low
reversal, intraday) that this document's own preamble distinguishes
itself from. **Trial count for this family: 1. Closed at DEV, trial 1 of
1.** No second configuration was pre-registered, so there is no
Bonferroni-adjacent bookkeeping to carry forward the way
`box_theory`/FVG's 2-configuration families required -- this family
simply ends here.
