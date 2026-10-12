# Pre-registration: NIFTY ATM Straddle vs. Realised Move (Fair-Pricing Study)

Frozen before any ratio, mean, or t-statistic has been computed, per this
project's standing discipline (`PREREGISTRATION.md`,
`PREREGISTRATION_FIBO.md`, `PREREGISTRATION_SWING.md`,
`PREREGISTRATION_PER_STOCK.md`). Nothing below changes after this
document is written except by an explicit, recorded amendment.

**NEW, SEPARATE MODULE** (`src/options_history/`): reads NIFTY's own
index closing prices from `data/warehouse.duckdb`'s `index_eod` table
(read-only — the same raw exchange index levels `scripts/
backfill_nifty_index.py` already populated; not a Fibo/momentum result,
and nothing there is modified). Everything else — the NIFTY-options EOD
data itself — lives in this module's own `data/options_history/
options_history.duckdb`, never `data/warehouse.duckdb`. Fibo, momentum,
swing, per_stock, and the live options-depth collector are untouched.

**DATA-ONLY STATUS**: this document governs analysis of data whose
feasibility was separately established (`OPTIONS_HISTORICAL_FEASIBILITY.md`)
and which is being downloaded now (`scripts/backfill_nifty_options.py`).
**No ratio has been computed. No result exists yet.** This document is
being written and will be shown to the user BEFORE the download even
finishes, specifically so the measure and the statistics plan cannot be
shaped by having seen a result.

## 0. The question

Does the NIFTY at-the-money straddle price systematically exceed the
subsequently realised move to expiry? I.e., does the market price more
movement into an option than actually occurs, on average, over the
2016-2026 history available?

**This measures fair pricing, not tradeability.** See Section 5 — the
data behind this study has no bid/ask at any date (`OPTIONS_HISTORICAL_
FEASIBILITY.md` Section 3), so nothing here can say whether a strategy
built on this finding (if any) would survive real transaction costs. A
systematic gap between straddle price and realised move, even if found,
is a statement about CLOSING-PRICE fairness, not about an executable
edge.

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
just the one crash."

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
3. **ATM strike**: at the measurement point's own `trade_date`, the
   strike among that expiry's listed NIFTY option strikes closest to
   NIFTY's own closing level that day (`index_eod.close`, read-only,
   warehouse-shared raw index data).
4. **Straddle price** = that strike's CE closing price + PE closing
   price, both on the measurement date.
5. **Realised move** = `|NIFTY_close(expiry_date) - NIFTY_close(measurement_date)|`,
   both read from `index_eod`.
6. **Reported metric: ratio = realised / straddle**, one value per
   monthly expiry. (Ratio < 1: realised move was smaller than the
   straddle priced in. Ratio > 1: realised move exceeded the straddle.
   Stated for orientation only — no claim about which way this study's
   own result will land.)

**Statistical test uses log(ratio), descriptive reporting uses the raw
ratio** — a methodological choice, not specified by the user, flagged
here rather than silently applied: a ratio is bounded below by 0 and
right-skewed, so a one-sample t-test on the raw ratio (testing mean = 1)
would violate that test's own normality-of-the-mean assumption more than
necessary; log(ratio) (testing mean = 0) is symmetric and better-behaved
for exactly the same underlying question. The ratio itself, per
instruction, is what gets reported.

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
measurement/expiry pair is independent of every other month's by
construction (disjoint date ranges), so no purging/embargo scheme is
needed the way an overlapping-window study would require.

**Designed sample size (calendar-implied maximum, before the liquidity
filter can drop any month)**:
- Development (2016-01 to 2022-12): **84 months → up to 84 observations.**
- Test (2023-01 to 2026-09): **45 months → up to 45 observations.**

The ACTUAL achieved count in each window (after Section 4's filter drops
any month with an illiquid leg) is not yet known — it will be reported
alongside the result, not predicted here.

**Minimum detectable standardized effect at t ≥ 2** (one-sample t-test
on log(ratio), `d_min = t / sqrt(n)`, the standard power relationship —
computed from sample size alone, independent of any data):
- Development (n ≤ 84): **d_min ≈ 0.218** standard deviations of
  log(ratio) away from zero.
- Test (n ≤ 45): **d_min ≈ 0.298** standard deviations of log(ratio)
  away from zero.

(Smaller n in the test window means a somewhat larger true effect is
needed there to reach the same t ≥ 2 bar — stated now, before the actual
dispersion of log(ratio) is known, so the comparison is available
up front rather than discovered as a surprise after the fact.)

## 6. Limitation, stated per instruction

**Closing prices, no bid/ask, anywhere, in this dataset, at any date**
(`OPTIONS_HISTORICAL_FEASIBILITY.md` Section 3). This measures whether
NIFTY options are FAIRLY PRICED relative to what subsequently happened —
it does NOT measure, and cannot be extended by more analysis of this
same data to measure, whether a strategy acting on any finding here
would be PROFITABLE after real transaction costs. Those are two
different questions; this study answers only the first one.

## Status

**>>> STOPPING HERE, per instruction.** No ratio, mean, standard
deviation, or t-statistic has been computed for either window. The
2016-2026 backfill (`scripts/backfill_nifty_options.py`) may still be
running when this document is read — downloading data is not analysis,
and this document was written without waiting for it to finish, so that
no part of the measure or the statistics plan above could have been
shaped by a result. The user approves this pre-registration before
anything in Section 2/5 is actually run against real numbers.
