# Portfolio construction on momentum_12_1 -- new family, trial 1

## Provenance

Every prior study in this project tested an ENTRY rule. None has tested
PORTFOLIO CONSTRUCTION -- concentration, weighting, rebalance frequency --
on the one signal that has ever passed a sealed test (`momentum_12_1`,
`PREREGISTRATION.md` Study 1, `FINDINGS.md` Section 2). This is that
study. New family, new module (`src/portfolio/`), first trial.

## THE HARD CONSTRAINT -- stated prominently, because it shapes everything below

**The historical holdout is RETIRED.** `FINDINGS.md` Section 7, in full:
the sealed 18-month window (`SEALED_HOLDOUT_START = 2025-03-19`) was
spent once by Study 1, read a second time by the swing project, and a
third time by the persistence monitor's own continuous read -- at which
point the project's own standing decision was that **no historical
holdout remains, for any hypothesis, from any project sharing this
warehouse.** "All future validation... is FORWARD-ONLY: on data arriving
after 2026-09-27."

**There is no sealed window available for this study.** Every number
this study produces comes from development data this researcher has
already seen in detail -- including, for the 2025-03-19 onward period
specifically, Study 1's own previously-reported realized result on
exactly that stretch. For that reason **this study's own development
window is capped at 2025-03-18**, the same boundary Study 1's own
pre-holdout backtest used (`entity_prices_daily`'s own physical
truncation, Section 1 below) -- not extended into the spent
2025-03-19→2026-09-27 window, which is not sealed anymore but is not
unseen either: its outcome is already known from Study 1, swing V1, and
the persistence monitor, and using it here would be hindsight dressed as
evaluation, not a second independent check.

**Consequently: everything in this study runs on development data only.
A positive result justifies FORWARD testing and nothing more. It is NOT
a validated improvement and must never be reported as one.** This makes
this study structurally WEAKER than the momentum sealed test it builds
on -- Study 1 at least had one genuinely unseen 18-month window; this
study has none. Every result below is read with that understood, not as
a footnote at the end.

## Section 0: reuse boundaries, read-only

Nothing in `src/factors/momentum.py`, `scripts/run_holdout_study1.py`, or
any closed study's own result is modified. Study 1's own sealed-test
pass/fail stands exactly as reported.

**Reused unchanged:**
- `factors.momentum.compute_momentum_12_1` -- the factor itself, no
  parameter touched.
- `factors.target.compute_forward_return(panel, horizon=...)` -- already
  parameterized by horizon; called with `horizon` set to each
  configuration's own rebalance length (21, 63, or 126), since the
  realized holding-period return must match the actual holding period,
  not always 63 days the way Study 1's own single-frequency script
  needed it to.
- `data_layer.entity_panel.read_entity_panel` -- reads the already-
  materialized, PHYSICALLY pre-holdout-truncated `entity_prices_daily`
  table (2016-01-01 to 2025-03-18, confirmed by direct query before
  writing this document -- 3,455,273 rows). This is used in preference
  to `read_full_entity_panel_authorized`, which requires either
  `authorize_holdout=True` (inappropriate -- there is no holdout left to
  spend) or raises `HoldoutViolationError` outright on any call reaching
  to "today" with `authorize_holdout=False`. `read_entity_panel` cannot
  leak a holdout-window date even by mistake, because the table itself
  was never materialized with one.
- `COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq":
  118.0}` and the rolling-20-day-median-turnover tercile construction
  (`p.groupby("entity_id")["turnover"].transform(...).rolling(20,
  min_periods=20).median()`, then `pd.qcut(..., 3, ...)` per date) --
  identical to `run_holdout_study1.py`'s own code.
- `DECILE_FRAC = 0.10` for the "full decile" concentration level.
- `data_layer.lineage_jump_guard.unexplained_jump_boundaries(con,
  before=None)` and `monitor.persistence.same_isin_jump_excluded_entities
  (con)` -- the Bug #1 and Bug #11 guards.

**On the jump guards specifically, stated as a deliberate choice, not
silently decided**: `run_holdout_study1.py` itself, written before
Bug #11 was found, does NOT apply either guard. This study applies both,
matching the convention every momentum-pipeline script written SINCE
Bug #11 uses (`scripts/run_momentum_persistence_monitor.py`,
`scripts/run_momentum_basket_snapshot.py`) -- "the momentum backtest
machinery" is read here as this project's own current, corrected
understanding of that machinery, not a frozen snapshot of a script that
predates a confirmed bug. This means this study's own BASELINE
configuration (Section 2) may differ very slightly from Study 1's own
originally-reported pre-holdout CAGR -- expected, small, and explained
by this one guard difference, not a new discrepancy to chase.

**New code, lives entirely in `src/portfolio/`**: concentration/
weighting portfolio construction (Section 4), the parameterized
backtest loop generalizing `run_holdout_study1.py`'s single-frequency,
equal-weight-only loop to 24 configurations (Section 3), weight-based
turnover and cost generalization (Section 5), and the statistics module
(Section 6).

## Section 1: universe and development window

Identical to `PREREGISTRATION.md`'s own Universe section: NSE equities,
`series='EQ'` only, ISIN prefix INE/IN9, entity-resolved via
`isin_lineage`, entity-adjusted close, `STALE_GAP_DAYS=5` gap-filtering,
no additional liquidity screen (whole market, including microcaps).

**Development window: 2016-01-01 to 2025-03-18.** Not a point-in-time
annually-reconstituted top-N universe the way the box_theory/POC/
darvas/fvg family uses (`fibo.universe.reconstitute_annually`) -- Study
1 never used that construction, and this study doesn't introduce it.
The eligible cross-section is determined FRESH at each rebalance date:
whichever entities have a non-NaN `momentum_12_1` value AND a resolvable
liquidity tercile on that specific date, exactly as `run_holdout_
study1.py`'s own `day_full`/`pool` filtering already does. Mean eligible
cross-section size: approximately 1,000-1,300 entities (`PREREGISTRATION.
md`'s own figure, confirmed unchanged since the universe query itself is
unchanged).

## Section 2: the baseline, and what "beating it" means

**BASELINE = equal weight, full top decile, 63-trading-day rebalance --
the exact configuration that passed the sealed test.** This is not an
arbitrary member of the grid; it happens to also be one of the 24 cells
(concentration=decile x weighting=equal x rebalance=63), and is reported
both on its own and inside the full 24-row table, where it will
trivially show zero difference against itself -- noted plainly when the
table is built, not treated as a bug.

**The question this study answers is NOT "which of the 24 configurations
is best."** It is: does any configuration beat THIS ONE baseline by a
margin that survives correction for having asked the question 24 times?
Every comparison in Section 6 forward is framed against the baseline's
own realized return series, never against a zero-return null and never
by ranking the 24 against each other.

## Section 3: the grid -- 24 configurations, all run, all reported

| Dimension | Levels |
|---|---|
| Concentration | top 10, top 25, top 50, full decile (~120, `DECILE_FRAC=0.10` applied to the eligible cross-section) |
| Weighting | equal weight, weight proportional to momentum rank |
| Rebalance | 21, 63, or 126 trading days |

4 x 2 x 3 = 24. **All 24 are run and reported in Section 8's table,
including the worst** -- reporting only the best configuration found is
exactly the failure mode Section 6's own Bonferroni correction exists to
prevent, and selectively reporting here would silently reintroduce it at
the reporting stage even with correct math underneath.

For each of the three rebalance frequencies, the eligible-date list is
`all_dates[::rebalance_days]`, trimmed at the tail wherever the forward-
return window would run past 2025-03-18 (identical trimming rule to
`run_holdout_study1.py`'s own `[d for d in ... if all_dates.index(d) +
HORIZON_DAYS < len(all_dates)]`, with `HORIZON_DAYS` replaced by that
configuration's own `rebalance_days`). This produces three DIFFERENT
rebalance-date calendars; the 8 configurations sharing a given rebalance
frequency share that frequency's own calendar, the forward-return
computation at that horizon, and the resulting period count.

## Section 4: portfolio construction

**Concentration**: at each rebalance date, rank the eligible cross-
section by `momentum_12_1` value, descending. "Top 10/25/50" selects
that many entities by rank, a fixed count. "Full decile" selects every
entity at or above the `1 - DECILE_FRAC` quantile cutoff, the same
variable-count construction Study 1 uses (~120 names on a ~1,150-name
mean cross-section, but varying with the actual eligible count that
day).

**Weighting**:
- **Equal weight**: `weight_i = 1/N` for each of the N selected names --
  Study 1's own convention, unchanged.
- **Rank-proportional weight (new, this study's own construction,
  stated explicitly since no prior script in this project has ever
  needed it)**: a linear rank tilt. For N selected names with momentum
  rank `r_i` (`r=1` is the single highest `momentum_12_1` value in the
  selection), `weight_i = (N - r_i + 1) / sum_{j=1}^{N} (N - r_j + 1)`.
  The strongest-momentum name receives the largest weight (`N` "shares"
  out of a total of `N(N+1)/2`); the weakest name in the selection
  receives the smallest (`1` share). Chosen as the simplest unambiguous
  construction that ties weight monotonically to momentum strength
  without introducing a second free parameter (e.g. an exponential
  tilt's own decay rate) this study was not asked to tune.

## Section 5: costs and turnover -- generalized to weighted portfolios

Same tercile round-trip rates as Study 1 (`COST_BY_TERCILE`), applied to
realized turnover, not the whole holding -- but generalized from Study
1's own name-count fraction (which only happens to be correct because
equal weight makes every name's own weight change identical in
magnitude) to a genuine WEIGHT-based turnover, needed because the
rank-weighted dimension means a RETAINED name can still change weight
between rebalances, which is a real trading cost Study 1's own formula
was never asked to capture:

```
turnover_rs_equivalent = 0.5 * sum_over_union(|w_new_i - w_old_i|)
cost_this_period = sum_over_union(|w_new_i - w_old_i| * tercile_cost_bps[i] / 10000)
```
(`w_old_i = 0` for a name not previously held, `w_new_i = 0` for a name
exiting; `tercile_cost_bps[i]` is the ENTERING name's own tercile for an
increase, the EXITING/REDUCED name's own tercile for a decrease -- the
same per-entity tercile lookup Study 1 already does, just applied
per-unit-of-weight-change instead of per-whole-name.) For every EQUAL-
WEIGHT configuration this reduces identically to Study 1's own
`turnover_frac = len(entered)/len(mom_set)` formula, confirmed
algebraically (every name changes by the same `1/N` or `0`) and will be
spot-checked against it in the hand-trace step.

`total_cost_drag` (Section 8's own required figure) is the sum of
`cost_this_period` across every rebalance in a configuration's own
window, reported both in the per-period average and as a cumulative
NAV drag.

## Section 6: statistics

**Primary test: Bonferroni-corrected two-sided threshold, p < 0.002**
(`0.05 / 24`). A configuration's own annualized-return advantage over
baseline must clear this bar to be called a finding, not the
uncorrected 0.05. Stated as arithmetic, not just asserted: **at an
uncorrected 5% bar, the probability of at least one false positive
across 24 independent tests is `1 - 0.95^24 ≈ 71%`** -- nearly a coin
flip's worse, which is exactly why a per-comparison 0.05 bar cannot be
used to call any single cell in this grid a finding.

**Secondary, clearly labelled as secondary and less conservative:
Benjamini-Hochberg** (controls false discovery rate, not family-wise
error) across the same 24 p-values -- implemented directly (sort
p-values ascending, find the largest `k` with `p_(k) <= (k/24) * 0.05`,
reject all `p_(1..k)`), not via `statsmodels` (listed in `requirements.
txt` but not actually installed in this environment, confirmed before
writing this document -- flagged rather than silently adding a new
dependency or silently failing at runtime).

**Test construction, per configuration, against the one fixed
baseline**:
- **Same-frequency configurations (the 8 at 63-day rebalance, sharing
  baseline's own rebalance calendar exactly)**: a PAIRED two-sided
  t-test on the per-period difference (`config_net_return -
  baseline_net_return`, date-matched, N = the 63-day period count).
  Preferred over an unpaired test here because it removes common
  market-wide variance both series share, and is strictly more
  powerful when the pairing is valid -- which it is, since both
  portfolios are drawn from the identical eligible cross-section on
  the identical dates.
- **Different-frequency configurations (the 16 at 21-day or 126-day
  rebalance, whose own rebalance dates do not align with baseline's
  63-day calendar)**: an unpaired, unequal-variance (Welch) two-sided
  t-test comparing that configuration's own annualized-equivalent
  period returns against baseline's own period returns. No date-
  matching is attempted across different rebalance calendars; Welch's
  test does not require it and correctly handles the resulting unequal
  N and unequal variance between the two series.

Both test types are evaluated at the same p < 0.002 primary bar and
contribute to the same 24-entry Benjamini-Hochberg secondary list.

## Section 7: power calculation -- run FIRST, before any configuration is evaluated

**Required before the grid runs at all, per instruction.** Computed
directly from the BASELINE configuration's own realized return series
at each of the three rebalance frequencies (equal weight, full decile,
rebalanced at 21, 63, and 126 days respectively) -- not assumed, not
scaled analytically from one frequency to the others, since this
project's own backtest code is being built regardless and running the
one baseline configuration three times (not the other 23 cells) is
little additional cost for a materially more honest number than a
sqrt(time)-scaling guess would give.

**For each frequency f in {21, 63, 126}, reported before any other
configuration is touched:**
1. `N_f` -- the actual count of non-overlapping, fully-realizable
   rebalance periods in the DEV window at that frequency (the real
   trimmed count, not an estimate from `(days in window) / f`).
2. The observed mean and standard deviation of baseline's own realized
   per-period NET return at that frequency.
3. **Minimum detectable difference in annualized return**, both:
   - a **detection threshold** (critical value only, `z_{1-0.001} ≈
     3.09` from the normal approximation, no power/beta term) -- the
     smallest effect that would register as significant if observed
     exactly, with no guarantee of reliably observing it, and
   - a **minimum detectable EFFECT at 80% power** (the standard target,
     stated explicitly as a modeling choice, not a given): `MDE_period =
     (t_{1-0.001, df} + t_{0.80, df}) * (sigma_f / sqrt(N_f))` using the
     t-distribution (not normal) given the small sample sizes involved,
     `df = N_f - 1`, converted to an annualized figure via proper
     compounding (`(1 + MDE_period)^(252/f) - 1`, not a linear
     approximation).
   Both figures reported, clearly distinguished, for every frequency.
4. **Whether that minimum is plausibly achievable**, discussed plainly
   against realistic momentum-strategy effect sizes -- not just the
   number alone. Concentration is expected to raise both return AND
   variance (stated in the grid's own motivation), which means the
   TRUE variance for a top-10, rank-weighted configuration is likely
   HIGHER than baseline's own full-decile, equal-weight variance used
   here as the anchor -- so this power calculation, anchored on
   baseline's own (lower) variance, is **optimistic for the
   concentrated configurations specifically**, not a uniform bound
   across the grid. Stated here, before the grid runs, so a later
   under-powered result for a concentrated cell is read as expected,
   not a surprise.

**`>>> STOP after this section is computed and reported.`** If the
minimum detectable difference is implausibly large relative to what a
portfolio-construction change could plausibly deliver, that is reported
plainly and the grid is not run without the user's explicit go-ahead to
spend the compute anyway.

## Section 8: report, per configuration and across the grid

**Per configuration (all 24 rows, one table)**: annualized return,
annualized volatility, Sharpe ratio, maximum drawdown and its duration
(peak date to trough date, in trading days), number of rebalances,
mean per-period turnover, total cost drag (Section 5), difference vs.
baseline (annualized pp), uncorrected p-value, and Bonferroni-corrected
pass/fail at p < 0.002.

**Across the grid**:
- Whether any single dimension (concentration, weighting, rebalance)
  shows a monotonic effect on return, tested directly (e.g. does mean
  return across the four concentration levels, holding weighting/
  rebalance fixed, rise or fall steadily, or is the ordering noisy/
  non-monotonic) -- same numerical-monotonicity-check discipline this
  project already applies elsewhere (e.g. the Liquidity-family turnover-
  quintile diagnostic), not eyeballed.
- The concentration/variance tradeoff stated explicitly: does top-10
  beat full-decile on gross return, and by how many points does its
  MaxDD worsen in exchange.
- How much of any apparent gross improvement is consumed by turnover
  cost specifically (gross-vs-net gap, broken out per configuration, not
  just an aggregate number) -- a 21-day rebalance trades roughly 3x as
  often as 63-day; this is reported as its own line, not folded silently
  into the net figure.

## Section 9: verdict rule, fixed now

**If no configuration beats the baseline at p < 0.002 (Bonferroni-
corrected)**: the finding is that portfolio construction does not
materially improve this signal at a detectable level in this sample,
and the baseline (equal weight, full decile, 63-day rebalance) stands
as this project's own best-evidenced construction for `momentum_12_1`.

**If one or more configurations clear p < 0.002**: the finding is that
configuration MERITS FORWARD TESTING. Stated explicitly, every time this
sentence is used: **this does not mean it works.** There is no sealed
window left to confirm it, per the hard constraint at the top of this
document. A pass here is an invitation to collect forward evidence, not
a validated improvement, and must never be described as the latter in
this document, `OPERATIONS.md`, or anywhere else this result is cited.

## Section 10: Claude's pre-committed prediction

I expect no configuration to clear p < 0.002. I expect concentration to
raise gross returns and raise drawdowns roughly proportionally (a
noisier, less diversified book), not for free. I expect the 21-day
rebalance to look worse net than gross specifically because of turnover
cost, more so than the 63- or 126-day configurations. I expect the power
calculation itself (Section 7) to show a minimum detectable difference
that is large relative to plausible portfolio-construction effect sizes,
particularly at the 126-day frequency where the period count is
smallest.

## Section 11: process

1. Write this document. Commit and push ALONE. Report the hash.
2. Run the power calculation (Section 7) only -- the baseline
   configuration at all three rebalance frequencies, nothing else.
   Report it in full. **STOP for approval before running the other 23
   configurations.**
3. Run the full grid, all 24 configurations, reported in full per
   Section 8, only after that approval.

## Section 12: discipline

All parameters fixed now: the four concentration levels, the two
weighting schemes, the three rebalance frequencies, the tercile cost
model, the Bonferroni threshold, the paired/Welch test assignment. If
the grid's result is null, these exact 24 configurations are not
retried at other values, other concentration counts, or other weighting
formulas -- a different grid would be a new, separately pre-registered
trial of this same family, not a rerun of this one. This governs
portfolio-construction testing on `momentum_12_1` only; it does not
reopen Study 1's own sealed-test result, which stands exactly as
reported regardless of this study's own outcome.

## Status

Preregistration complete. Not yet committed. Next: commit alone, report
hash, then build `src/portfolio/` and run the Section 7 power
calculation only.
