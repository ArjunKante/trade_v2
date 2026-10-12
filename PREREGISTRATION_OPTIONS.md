# Pre-registration: NIFTY ATM Straddle vs. Realised Move (Fair-Pricing Study)

Frozen before any ratio, mean, or t-statistic has been computed, per this
project's standing discipline (`PREREGISTRATION.md`,
`PREREGISTRATION_FIBO.md`, `PREREGISTRATION_SWING.md`,
`PREREGISTRATION_PER_STOCK.md`). Nothing below changes after this
document is written except by an explicit, recorded amendment.

**Amendment, 2026-10-13, BEFORE any ratio, mean, or t-statistic was
computed** (no analysis has run against real numbers at any point in
this document's history — the backfill finished, nothing downstream of
it has): four corrections to the original statistics plan (grouped as
three numbered requests plus the autocorrelation check), found by
inspection of the method, not by looking at a result.

1. **The log-ratio test is REPLACED.** The original plan tested
   mean(log(realised/straddle)) = 0 as a proxy for fair pricing. This is
   wrong, not just a style choice: a straddle's payoff is right-skewed
   under fair pricing (most months pay less than the premium, a few pay
   far more), and by Jensen's inequality `E[log(X)] < log(E[X])` for any
   non-degenerate X — so `E[log(payoff/price)]` is NEGATIVE even when
   `E[payoff/price] = 1` exactly (true fair pricing). The log test would
   report "overpricing" on fairly-priced options as a mathematical
   artifact of the transform, not a finding. It also breaks down near
   zero: a month where the realised move lands very close to zero
   produces a huge negative log value that can dominate the mean by
   itself. **New primary metric: R = payoff / straddle_price - 1** (the
   simple return from buying the straddle at the measurement point and
   holding to expiry; fair pricing ⟺ mean R = 0), tested via a
   **10,000-resample bootstrap confidence interval** rather than a
   t-test on a transformed variable, because R itself is also skewed and
   a bootstrap does not require assuming a distribution shape to get a
   valid interval. Median R is also reported, explicitly labelled
   descriptive, NOT the test — median and mean diverge substantially
   under this much skew, and conflating them would misstate what was
   actually tested.
2. **Payoff is now measured from the strike, not from the measurement
   point.** `payoff = |NIFTY_close(expiry) - K|`, K = the chosen ATM
   strike — this is literally what a straddle pays at expiry (call pays
   `max(S_T-K, 0)`, put pays `max(K-S_T, 0)`, sum = `|S_T-K|`, always,
   by construction, not an approximation). The original
   `|NIFTY(expiry) - NIFTY(measurement)|` is close to this but not
   identical, since K is a discrete, rounded strike and NIFTY's own
   close at the measurement point is continuous — using the actual
   payoff removes that discrepancy from the test entirely. The original
   quantity is kept, demoted to a secondary descriptive figure only
   (Section 2, step 5) — intuitively meaningful ("how far did the index
   move") even though it is not the number the straddle actually paid.
3. **A decision rule is added** (Section 5) — fixed now, before DEV is
   computed, let alone TEST: what result in each window does and does
   not support "options are systematically overpriced," stated as an
   explicit rule rather than left to be judged informally after seeing
   both numbers. Also: DEV's mean R will be reported a second time,
   **excluding 2020**, so how much of any effect rests on the one crash
   year is visible rather than buried inside a single pooled number.
4. **Lag-1 autocorrelation of the R series is added to the statistics
   plan.** Volatility clusters in time; 84 (DEV) / 45 (TEST) disjoint
   monthly windows are independent BY CONSTRUCTION (non-overlapping date
   ranges), but that does not guarantee the resulting R values are
   independent draws — a volatile stretch of months could correlate with
   each other through shared market conditions even though their
   measurement windows never overlap. If lag-1 autocorrelation turns out
   to be material, the plain (iid) bootstrap in point 1 understates the
   true uncertainty, and a block bootstrap (resampling contiguous runs
   of months, not single months, to preserve whatever short-range
   dependence exists) is used instead.

This document's Sections 2 and 5 below are rewritten to reflect all
four points directly, rather than kept as originally written with a
patch bolted on — a reader should not have to cross-reference the
amendment note against stale section text to know what the actual plan
is.

**NEW, SEPARATE MODULE** (`src/options_history/`): reads NIFTY's own
index closing prices from `data/warehouse.duckdb`'s `index_eod` table
(read-only — the same raw exchange index levels `scripts/
backfill_nifty_index.py` already populated; not a Fibo/momentum result,
and nothing there is modified). Everything else — the NIFTY-options EOD
data itself — lives in this module's own `data/options_history/
options_history.duckdb`, never `data/warehouse.duckdb`. Fibo, momentum,
swing, per_stock, and the live options-depth collector are untouched.

**DATA-ONLY STATUS**: the 2016-2026 backfill (`scripts/
backfill_nifty_options.py`) has since completed (5,635,823 rows, 2,652
trading days, one unresolvable NSE-archive gap on 2021-03-30 — see
OPERATIONS.md/BUGS.md). **No ratio, mean, or R value has been computed
from it.** This amendment was written and is being shown to the user
before any such computation runs, specifically so the corrected measure
and statistics plan cannot be shaped by having seen a result.

## 0. The question

Does the NIFTY at-the-money straddle price systematically exceed the
subsequently realised move to expiry? I.e., does the market price more
movement into an option than actually occurs, on average, over the
2016-2026 history available?

**This measures fair pricing, not tradeability.** See Section 6 — the
data behind this study has no bid/ask at any date (`OPTIONS_HISTORICAL_
FEASIBILITY.md` Section 3), so nothing here can say whether a strategy
built on this finding (if any) would survive real transaction costs. A
systematic gap between straddle price and realised payoff, even if
found, is a statement about CLOSING-PRICE fairness, not about an
executable edge.

## 1. Sealed development/test windows

`src/options_history/test_seal.py`, same mechanism as Fibo/momentum's
own `src/data_layer/holdout.py::HoldoutViolationError` (an exception that
raises unless explicitly authorized, not a comment saying "don't query
past X"):

- **Development: 2016-01 to 2022-12** (84 calendar months). Includes the
  2020-03 COVID crash — NIFTY's largest realised move of this entire
  history sits here.
- **Test (sealed): 2023-01 to 2026-09** (45 calendar months).

**Stated limitation, not glossed over**: the test window contains no
crash of 2020's scale. Whatever this study finds about crash-era pricing
can only ever come from the development window — the sealed test cannot
confirm or refute a crash-specific finding, because it does not contain
a comparable event. A result that holds in both windows is evidence the
finding is not solely a 2020-crash artifact; a result that only holds in
development is NOT distinguishable, by this design, from "it was really
just the one crash." (Section 5's decision rule and the DEV-excluding-
2020 figure both exist to make this visible rather than implicit.)

## 2. Measure

For each **monthly** NIFTY option expiry (Section 3 for why monthly
only):

1. **Measurement point: 20 trading days before that expiry**, counted
   backward along NIFTY's own trading-day calendar (`index_eod`), not
   calendar days. Chosen (not specified by the user verbatim — stated as
   a filled gap) to land comfortably inside the contract's liquid life,
   past the newly-listed noise at the start of its 2-3 month runway and
   clear of the final days' gamma/theta distortion right before expiry,
   while still carrying close to a full month of remaining time value —
   roughly the point the "current month" contract becomes the most
   actively quoted series.
2. **Monthly expiry date itself, operationally defined from the data,
   not assumed from a fixed weekday rule** (NSE has changed index-option
   expiry weekdays more than once over 2016-2026): for calendar month M,
   the monthly expiry = the LATEST distinct `expiry_date` among all
   NIFTY option rows whose expiry falls within month M. This is correct
   whether or not weekly contracts also existed that month (weeklies,
   present from 2019 onward, always expire before the month's final
   week; the monthly contract's own expiry is always the last one in
   its month, by construction of how NSE lists "near/next/far month"
   contracts).
3. **ATM strike (K)**: at the measurement point's own `trade_date`, the
   strike among that expiry's listed NIFTY option strikes closest to
   NIFTY's own closing level that day (`index_eod.close`, read-only,
   warehouse-shared raw index data).
4. **Straddle price** = that strike's CE closing price + PE closing
   price, both on the measurement date.
5. **Payoff** (PRIMARY, amendment 2) = `|NIFTY_close(expiry_date) - K|`
   — the straddle's actual payoff at expiry, both prices read from
   `index_eod`/the chosen strike. **Realised move** (SECONDARY,
   descriptive only) = `|NIFTY_close(expiry_date) - NIFTY_close(measurement_date)|`
   — close to the payoff but not identical (K is a discrete strike,
   NIFTY's own close is continuous); reported alongside the payoff
   because "how far did the index move" is independently meaningful, but
   it is not what feeds the test below.
6. **R = payoff / straddle_price - 1**, one value per monthly expiry —
   the PRIMARY reported and tested metric (amendment 1). R < 0: the
   straddle's payoff fell short of its own price (fair pricing's null is
   mean R = 0; a systematically negative mean R is the "overpriced"
   direction). R > 0: payoff exceeded price. The ratio `payoff /
   straddle_price` itself (= R + 1) is not separately tracked — it
   carries the same information as R, shifted by one.

## 3. Monthly expiries only — and why

**Primary measure uses monthly NIFTY option expiries only.** Weekly
NIFTY options did not exist for the whole 2016-2026 period (introduced
2019) — including them would silently change the sample's composition
partway through the window (pre-2019: monthly-only henceforth available
granularity; post-2019: monthly AND weekly both exist), which would make
"2016" and "2026" observations structurally different kinds of events,
not just different dates of the same kind. Restricting to monthly
expiries throughout keeps one consistent instrument definition across
the entire 2016-2026 history in both the development and test windows.

## 4. Liquidity filter

**Exclude any contract (one option leg: a specific strike + CE/PE +
date) with zero traded volume that day.** Applied independently to BOTH
legs of a given month's straddle — if either the CE or the PE leg at the
chosen ATM strike has zero volume on the measurement date, that ENTIRE
month's observation is dropped (not estimated, not substituted with a
neighboring strike), since a leg with no trade that day has no price
this study trusts enough to use (the same reasoning
`OPTIONS_HISTORICAL_FEASIBILITY.md` Section 5 already illustrated with a
real example of a zero-volume row carrying a non-zero exchange-model
settlement price anyway).

## 5. Statistics plan

**One observation per monthly expiry, non-overlapping** — each
measurement/expiry pair is independent of every other month's BY
CONSTRUCTION (disjoint date ranges), so no purging/embargo scheme is
needed the way an overlapping-window study would require. Section 5e
below checks whether "disjoint" actually implies "independent" here,
since volatility clustering could make that assumption fail in practice
even though the date ranges never overlap.

**(a) Designed sample size** (calendar-implied maximum, before the
liquidity filter can drop any month):
- Development (2016-01 to 2022-12): **84 months → up to 84 observations.**
- Test (2023-01 to 2026-09): **45 months → up to 45 observations.**

The ACTUAL achieved count in each window (after Section 4's filter drops
any month with an illiquid leg) is not yet known — it will be reported
alongside the result, not predicted here.

**(b) Primary test (amendment 1)**: mean R, development window, with a
**95% confidence interval from a 10,000-resample bootstrap** (resample
the window's own R values with replacement 10,000 times, take each
resample's mean, report the 2.5th/97.5th percentile of that
distribution). **Median R is reported alongside, explicitly labelled
descriptive, not the test** — informative about the typical month
without being distorted the way a skewed mean can be, but the mean is
what "systematically overpriced" is actually a claim about (the average
cost of buying the straddle every month, not the typical month's cost).

**Rough guide to detectable effect, stated with its own limits**: for a
plain-vanilla CLT-based interval, a 95%-CI-excludes-zero result needs a
standardized effect (mean R / std R) of roughly `1.96/sqrt(n)` —
**≈0.214 for DEV (n≤84), ≈0.292 for TEST (n≤45)**. A bootstrap CI
converges to this same approximation for large, well-behaved samples,
but its actual width in a small, skewed sample like this one depends on
R's real dispersion, which is not known until the data exists. Treat the
two numbers above as a rough sense of scale, not a guarantee the way an
exact-formula power calculation would be.

**(c) DEV excluding 2020 (amendment 3)**: mean R recomputed over the
development window with every monthly expiry falling in calendar year
2020 removed (12 months), reported alongside the full DEV figure — not
instead of it. Shows directly how much of any development-window effect
is carried by the one crash year versus the other six years of
development data.

**(d) Test window**: run ONCE, identical construction to development,
no changes made to the measure, the filter, or the test based on
anything seen in development. Mean R with the same 95%/10,000-resample
bootstrap CI; median R, same descriptive labelling.

**(e) Lag-1 autocorrelation (amendment 4)**: computed on the
chronologically-ordered R series, DEV and TEST separately. **Material**
is defined here, before the value is known, as `|lag-1 autocorrelation|
> 2/sqrt(n)` — the usual rule-of-thumb bound for a single autocorrelation
coefficient being distinguishable from zero under an i.i.d. null (≈0.22
for DEV's n≤84, ≈0.30 for TEST's n≤45). If material, (b) and (d)'s
bootstrap is replaced with a **block bootstrap** (contiguous runs of
months resampled as units, not individual months) for that window, and
this substitution is itself reported, not silently swapped in.

**(f) Decision rule (amendment 3), fixed now**:

"Options are systematically overpriced" requires **BOTH**:
- DEV mean R < 0 **with its bootstrap CI excluding 0**, AND
- TEST mean R < 0 (same sign as DEV — **its CI is NOT required to
  exclude 0**, stated now rather than discovered as a convenient excuse
  later: TEST's n≤45 may simply not have the power to reach a
  CI-excludes-zero result even if the same real effect is present, and
  demanding that bar in both windows would quietly make the test window
  pointless by design).

Every other outcome is read as follows, fixed now:
- **DEV significant, TEST opposite sign** → NOT established (the
  finding did not replicate directionally; treated as likely noise or a
  development-window-specific artifact, not as a confirmed result).
- **Neither window shows a significant (CI-excluding-zero) mean R** → NO
  DETECTABLE MISPRICING AT THIS SAMPLE SIZE (an absence-of-evidence
  statement, not a claim that options are proven fairly priced).

## 6. Limitation, stated per instruction

**Closing prices, no bid/ask, anywhere, in this dataset, at any date**
(`OPTIONS_HISTORICAL_FEASIBILITY.md` Section 3). This measures whether
NIFTY options are FAIRLY PRICED relative to what subsequently happened —
it does NOT measure, and cannot be extended by more analysis of this
same data to measure, whether a strategy acting on any finding here
would be PROFITABLE after real transaction costs. Those are two
different questions; this study answers only the first one.

## Status

**>>> STOPPING HERE, per instruction.** No R value, mean, median,
bootstrap CI, or autocorrelation has been computed for either window.
The amendments above were made by inspecting the method against what it
claims to test, not by looking at any number this data could produce —
the backfill finished and nothing downstream of it has run. The user
approves this amended pre-registration before anything in Section 2/5 is
actually run against real numbers.
