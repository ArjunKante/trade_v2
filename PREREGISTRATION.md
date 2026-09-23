# Pre-registration: Study 1 (momentum_12_1, long-only, top-decile)

Written and frozen before any query touches the sealed holdout. Nothing in
this document changes after approval. If the holdout is evaluated and
anything here is subsequently found to need changing, the holdout is burned
and that is reported, not silently re-run.

**Study counter for this project: 1 of a hard cap of 3.** After the third
pre-registered study against this dataset, the holdout is spent or sealed
permanently, regardless of outcome, matching the discipline `trade-info`
established for its own dataset.

---

## Why now, not sooner

Everything through the diagnostics, gap-awareness fix, cost pressure-test,
and survivorship check was exploratory work on the pre-holdout partition
only (2016-01-01 to 2025-03-18). That work earned the right to spend the
holdout by surviving its own scrutiny, not by producing a favorable number:

- The vol/momentum/target gap-awareness bug (`BUGS.md` Bug #2) was found by
  chasing a decile/IC sign conflict rather than dropping the factor that
  showed it, and its fix moved the two factors in mechanistically opposite,
  independently-explicable directions (vol's spurious signal inverted;
  momentum's true signal strengthened) — that asymmetry is what makes the
  fix credible rather than a tuning choice.
- The survivorship-bias hypothesis (that the eligibility filter
  disproportionately removes distressed names from the benchmark, inflating
  momentum's apparent edge) was **tested directly, not assumed away, and
  refuted**: excluded entities' mean momentum decile was 4.44 against a
  uniform-random expectation of 4.5; 99.8% of excluded entities resumed
  trading; their median return across the halt was +1.8%. The backtest gap
  (+12.3 points CAGR) survives even the deliberately unrealistic
  pessimistic bound (every excluded entity forced to -100%), falling only
  to +9.9 points. The hypothesis was a real, correctly-motivated challenge
  to the result, and it did not survive contact with the data — that is
  what makes the result worth spending the holdout on, not the fact that it
  came out favorable.
- A methodological bug in the backtest script itself (the final rebalance
  date's 100% "exclusion" rate, caused by the sealed-holdout boundary
  correctly refusing to materialize data past it, not by any business
  outcome) was caught before it could be misread as a finding.

None of this guarantees the holdout will pass. It establishes that the
pre-holdout result is not an artifact of the specific bugs and hypotheses
that were actually checked.

---

## Universe

- NSE equities, `series = 'EQ'` only (BE/BZ trade-to-trade names excluded
  throughout — confirmed by direct query, never re-included).
- ISIN prefix `INE` or `IN9` (ordinary equity + DVR share classes; `INF`
  fund/ETF units excluded).
- Entity-resolved via `isin_lineage` (NSDL structural rule: issuer code +
  security type match, serial strictly increasing, non-overlapping date
  ranges). Zero ambiguous cases among real equity ISINs in this dataset.
- Prices are entity-adjusted (`adjustment_factors`, forward-only, spans the
  full lineage chain) — never raw close.
- Gap-filtered: any return, momentum, or forward-return computation whose
  relevant window contains a trading gap exceeding `STALE_GAP_DAYS = 5`
  calendar days is excluded (NaN) rather than silently computed across it.
- No additional liquidity screen. Whole market, including microcaps.
- **Entity count**: 2,464 distinct entities in the full pre-holdout panel
  (2016-01-01 to 2025-03-18). Per-rebalance eligible cross-section
  (momentum + liquidity tercile both available): approximately 1,000-1,300
  entities, mean ~1,150.

## Strategy

- **Factor**: `momentum_12_1` — 12-month return, skipping the most recent
  month (Jegadeesh-Titman construction: `skip=21` trading days,
  `window=252` trading days), computed on entity-adjusted close.
- **Construction**: long only. Top decile (top 10%) by `momentum_12_1`
  value, cross-sectional, equal-weighted within the decile.
- **No shorting**: F&O eligibility measured directly at 7.4% for the bottom
  decile (13.6% for the whole sample, using the current 210-symbol F&O
  list as a ceiling, not a historical measure) — shorting this universe is
  not implementable, not a design preference.
- **Rebalance**: every 63 trading days.
- **Benchmark**: equal-weight of the same eligible universe, same
  rebalance cadence, same cost treatment (blended cost, not
  tercile-specific, since it holds the whole market rather than a
  liquidity-tilted subset).

## Costs

Tercile-specific, turnover-weighted, applied only to entities *entering*
the portfolio at each rebalance (not the whole holding, matching realized
turnover):

| tercile | round-trip cost | basis |
|---|---|---|
| high-liq | ~23 bps | Corwin-Schultz spread (62.7bps raw) calibrated by the prior project's own measured ~21x overstatement factor for normally-traded names, + ~20bps statutory/brokerage floor |
| mid-liq | ~32.5 bps | prior project's direct ground-truth measurement (26-39bps, live order book, rank 300-600, 2026-09-15), midpoint |
| low-liq | ~118 bps | Corwin-Schultz spread (97.7bps raw) used **uncalibrated**, since the prior project found CS is accurate (not overstated) on thin/T2T-like names, + ~20bps floor |

**The low-liquidity figure is the least certain input in this whole
pre-registration.** It is not a live-market re-measurement; it is a
Corwin-Schultz estimate combined with a calibration argument borrowed from
a different (though related) measurement exercise. If the holdout result
is sensitive to this specific number, that sensitivity will be reported,
not hidden behind a single point estimate.

Benchmark leg uses the blended 32.5bps rate on its own turnover throughout.

## Decision rule — all three required, fixed now

The holdout is read as a **pass** only if ALL THREE hold. Any one failing
means momentum does not replicate, and the project reports that plainly.

**(a) Holdout CAGR, net of costs, exceeds the equal-weight benchmark's
CAGR, net of costs** — same universe, same period, same cost model.

**(b) The margin is at least 3 percentage points annualized.** Below that
is within noise for a ~6-7 period sample (see below) and would not be
distinguishable from chance at this sample size.

**(c) Momentum's max drawdown is not materially worse than the
benchmark's, operationalized as: momentum's MaxDD does not exceed the
benchmark's own MaxDD by more than 10 percentage points.** This specific
number is fixed here, before the holdout is read, so it cannot be adjusted
after seeing the result.

## Sample size — stated upfront, not discovered afterward

The sealed holdout (`SEALED_HOLDOUT_START = 2025-03-19` through the most
recent available data) is approximately 18 months, which at a 63-trading-day
rebalance is **approximately 6-7 non-overlapping periods** (exact count
depends on the trading calendar and how much of the holdout's tail has a
complete 63-day-forward window at evaluation time).

**This is a thin base.** A single unusual quarter can flip the verdict in
either direction. Recorded now, before the result exists: **a pass at this
sample size is weak evidence that momentum replicated, and a fail is
equally weak evidence that it didn't** — this is a consistency check
against the pre-holdout finding, not a definitive test with real
statistical power. Neither outcome licenses a stronger claim than that
afterward.

## What is NOT being tested

Only `momentum_12_1` is pre-registered for this holdout spend.
`trailing_vol_252` and `beta_252` are explicitly excluded from this
evaluation — testing all four factors against one holdout would be four
trials charged to a resource that only tolerates one, and `trailing_vol_252`
in particular still carries the unresolved decile-conflict history from
this project's diagnostics. Neither factor gets a holdout evaluation in
this study. A future pre-registered study (within the 3-study cap) would be
required to test them.

## Interpretation, pre-committed

**If it passes**: momentum replicated out of sample, on a thin sample. The
report states this alongside, not after: the 2020 regime-risk finding
(momentum can materially underperform, though not necessarily lose money
outright, in a V-shaped-recovery regime), the ~199% annualized turnover,
the long-only constraint (shorting unavailable), and the low-liquidity cost
estimate's uncertainty. **This is not a green light to trade** — it is one
consistency check clearing, on a small sample, with real costs and real
constraints still attached.

**If it fails**: momentum did not replicate. Reported plainly. No appeals,
no reruns on a different configuration, no "but without the gap filter it
would have passed." The pre-holdout backtest and diagnostics remain exactly
as reported — a failed holdout does not erase them, it means they did not
generalize to the next 18 months, which is itself the honest, useful
result a holdout exists to produce.

## Procedure

Run once, on the frozen configuration above, no tuning between the
pre-holdout backtest and this run:

- Same factor computation (`factors.momentum.compute_momentum_12_1`, same
  `SKIP_DAYS`/`WINDOW_12M`, same `STALE_GAP_DAYS` gap-awareness).
- Same forward-return computation (`factors.target.compute_forward_return`,
  same gap-awareness), applied to the holdout window this time.
- Same decile construction (top 10%, equal-weight), same 63-trading-day
  rebalance cadence.
- Same tercile-cost model and turnover-weighting as coded in this
  project's existing backtest script — not re-derived, not re-tuned.
- Excluded-entity handling follows the **original** convention (dropped,
  not the -100% pessimistic bound) — the pessimistic bound was a stress
  test of the pre-holdout result, not a proposed live methodology, and the
  survivorship check found the exclusion filter is not decile-biased.
- Executed in exactly one dedicated script that sets
  `authorize_holdout=True` explicitly — never a default, never set
  anywhere else.
- All three decision-rule conditions reported separately, plainly, in the
  order given above, alongside the actual CAGR/Sharpe/MaxDD numbers for
  both legs.

---

**Waiting for approval before any holdout query is written or run.**

---

## Post-hoc annotation (2026-09-23) -- does not alter the locked
pre-registration above or reopen the spent holdout

The low-liquidity cost line's calibration argument ("CS is accurate on
thin/T2T-like names") was suggested during this project's later cost-review
work by extending the mid-liq tercile's live-order-book T2T finding
(2026-09-15) to the low-liq tercile as well. That extension was checked
directly and does not hold: the low-liq tercile is **0% BE/BZ (trade-to-
trade) by construction** -- `entity_panel.py` filters `series='EQ'`
unconditionally at materialization, so no BE/BZ name is ever eligible for
this tercile at any date. The calibration argument was borrowed from a
context where it held (true T2T names, live-measured) and applied to one
where it structurally cannot (an EQ-only tercile that is merely
low-turnover, a different market microstructure from T2T entirely).

This does not, on its own, mean 118bps is wrong -- only that the specific
argument offered for using it uncalibrated was invalid. A follow-up cost
sensitivity sweep (`scripts/run_lowliq_cost_sensitivity.py`) settled the
practical question instead of the calibration argument: across the full
plausible range from 118bps down to a fully-calibrated ~25bps (the same
~21x correction the high-liq tercile already gets), the momentum/benchmark
CAGR margin moves by at most +0.30 points, because low-liquidity names are
only ~10.5% of top-decile momentum's mean composition. This does not change
Study 1's holdout pass/fail outcome and would not have under any tested
value in this range. 118bps is retained as the working number: a
known-uncertain input with directly measured, low leverage on the
strategy's headline result -- closed on that basis, not on a live
re-measurement, which was deliberately not pursued because it could not
change this conclusion either way.
