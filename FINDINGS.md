# NSE Factor System: Findings, Studies 1-2

## 1. The question

Does 12-month momentum (skip most recent month, Jegadeesh-Titman
construction), long-only, top-decile, equal-weighted, rebalanced every 63
trading days, survive honest transaction costs on NSE equities?

Pre-registered in `PREREGISTRATION.md` before any holdout query, following
this project's own methodology lessons and `trade-info`'s (the prior
project's) discipline of never spending a sealed test on an untested
configuration.

## 2. The answer

**Yes, on a thin sample.**

| | pre-holdout backtest (2017-2024) | holdout (2025-2026) |
|---|---|---|
| Momentum CAGR (net) | 30.43% | 14.72% |
| Benchmark CAGR (net) | 18.11% | 10.85% |
| Margin | +12.32 pts | +3.87 pts |
| Sharpe (mom / bench) | 1.06 / 0.76 | 0.83 / 0.58 |
| MaxDD (mom / bench) | -35.95% / -49.82% | -6.48% / -10.45% |

All three pre-registered decision-rule conditions passed on the holdout:
(a) momentum CAGR > benchmark CAGR, (b) margin >= 3.0 points (actual: 3.87),
(c) MaxDD not more than 10 points worse than benchmark's (actual: 3.97
points *better*). Full period-by-period detail already reported in the
holdout evaluation; not repeated here.

**Do not extrapolate the backtest's 30.4%/18.1% level forward.** The
holdout's 14.72%/10.85% is far lower, consistent with 2017-2024 having been
an unusually strong run for Indian small/mid caps specifically, not with
the strategy degrading. The margin, not the absolute level, is the number
this study was designed to test, and the margin held.

## 3. The mechanism in the holdout: downside protection, not upside capture

This is the finding that matters more than the headline pass, and it is the
opposite of Section 4's failure mode.

| period | regime | momentum vs benchmark |
|---|---|---|
| 2025-04-11 | rising | -0.71 pts (loss) |
| 2025-07-14 | falling | +2.74 pts (win) |
| 2025-10-14 | falling | +1.43 pts (win) |
| 2026-01-14 | falling | +1.56 pts (win) |
| 2026-04-22 | rising | -1.77 pts (loss) |

Momentum beat the benchmark in 3 of 5 periods. **All three wins came in
falling markets; both losses came in rising markets, and both losses were
small** (-0.71, -1.77 points). The largest single-period margin was +2.74
points -- no one lucky quarter drove the aggregate result. MaxDD confirms
the same pattern at the portfolio level: -6.48% vs the benchmark's -10.45%.

The holdout's edge came from **losing less when the market fell**, not from
capturing more upside when it rose. That is a specific, falsifiable
mechanism, not a restatement of the headline CAGR gap.

## 4. The 2020 result: opportunity cost, not a wipeout

Distinct from Section 3's mechanism, and the reason "downside protection"
above cannot be read as "momentum is always defensive":

**Momentum returned +45.9% in 2020; the equal-weight benchmark returned
+65.7%.** A ~20-point relative underperformance in the crisis year -- real,
and concentrated in exactly the period a momentum strategy is theoretically
weakest (a sharp reversal invalidates "recent winners keep winning") -- but
**not an absolute loss**. 2020 was a V-shaped recovery: even the wrong side
of momentum was net positive. The cost of this specific tail risk is
foregone upside during a violent recovery, not capital destruction.

This is a genuinely different risk profile from "the strategy crashes when
momentum crashes." Section 3's holdout result does not contradict this; a
thin 5-period holdout with no violent reversal in it has simply not tested
this failure mode at all (see Section 8).

**This section's closing instruction ("stated this way... every time this
strategy is described going forward") is superseded by the amendment
immediately below and must not be repeated as originally worded.** Any
future summary of this strategy's known weaknesses must lead with the
corrected picture: the weakness is real but smaller and more
window-dependent than originally reported here, and momentum finished
AHEAD, not behind, over the full mechanically-defined drawdown episode
that contains 2020.

**Amendment, after a descriptive (not a test, no study slot spent) drawdown
diagnostic run against a mechanical criterion fixed before any period was
inspected** (`scripts/run_drawdown_descriptive_diagnostic.py`): benchmark
peak-to-trough decline exceeding 15% finds exactly **one** episode in the
whole pre-holdout series -- peak 2017-11-15, trough 2020-03-05, recovery
2021-03-10 (benchmark -49.82% peak-to-trough). Over the full episode,
momentum finished net AHEAD, not behind: +42.23% vs the benchmark's +9.56%
(+32.68 points). Splitting the same episode at its actual trough (not at a
calendar-year boundary) into a decline leg and a recovery leg:

| leg | window | momentum | benchmark | diff |
|---|---|---|---|---|
| decline (peak->trough) | 2018-02-15 to 2020-03-05 | -35.95% | -49.82% | +13.87 pts |
| recovery (trough->recovery) | 2020-06-11 to 2021-03-10 | +122.07% | +118.35% | +3.73 pts |

**The recovery leg, mechanically defined from the actual trough, does not
show the ~20-point underperformance this section describes.** That number
is real and unchanged under the specific window it used (calendar-year
2020, Jan-Dec: momentum +45.9%, benchmark +65.7%, diff -19.8 points,
reconfirmed directly) -- but calendar-year 2020 is a different slice than
trough-to-recovery: it excludes the 2021 Q1 rebalance the mechanical
recovery leg includes, and it includes the 2020-03-05 rebalance (momentum
-12.6%, benchmark -6.4%) that the mechanical split instead assigns to the
decline leg, since that date is the series' actual trough. Most of the
calendar-year underperformance turns out to be concentrated in that
boundary-sensitive attribution, not spread evenly through "the recovery."
A second, smaller episode at a 10% threshold (2021-09-15 peak to
2022-03-17 trough, benchmark -14.71%) also shows momentum net ahead
(+6.38 points).

**What this does and does not change**: it does not overturn the
calendar-year-2020 number, which is correctly reported above and remains
true under that windowing. It does mean the "opportunity cost in a violent
recovery" framing is more window-dependent than Section 4 originally
stated, and that neither mechanically-defined drawdown episode in this
project's one pre-holdout series (n=2, an extremely thin sample --
descriptive only, no significance claim) actually shows momentum behind
the benchmark once the window is drawn from the market's own peak/trough
rather than from a calendar boundary. The underlying mechanism Section 3
describes (losing less on the way down) still replicates cleanly in the
decline leg here. Whether a "recovery-leg opportunity cost" specifically
survives a mechanical window is, on this one episode, genuinely unclear
rather than confirmed -- stated as a real limitation, not resolved by
this diagnostic, which cannot be: one episode is not enough data to
settle it either way.

**General lesson, stated plainly because this project got it wrong once
already**: a performance claim that depends on which calendar window you
slice it with is not a robust claim, even when every individual number
feeding it is correctly computed. Calendar-year 2020 is a natural,
convenient boundary -- twelve months, matches how markets and media talk
about "2020" -- but it is not a principled one; nothing about the
market's actual peak or trough respects a January 1st boundary. The
mechanical definition used here (peak-to-trough-to-recovery, fixed by a
threshold decided before any period was inspected) is the right default
for describing a drawdown's cost, specifically because it cannot be
unconsciously nudged toward whichever twelve-month window makes a
pre-existing narrative look strongest. This applies beyond this one
finding: any future characterization of this strategy's behavior in a
specific regime should default to a mechanically-defined window first,
and treat a calendar-year framing as a secondary, convenience-only view
to be reported alongside it, never in place of it.

## 5. Bugs found

Full mechanism and evidence in `BUGS.md`; summarized here because both
materially shaped this result.

**Bug #1 (KAUSHALYA lineage/capital-reduction interaction).** ISIN lineage
correctly linked two ISINs as the same company (deterministic NSDL
structural match, independently verified). The corporate-actions parser,
by design, only extracts bonus/split events -- the same scope choice
`trade-info` made. The actual event connecting these two ISINs was a
capital reduction or scheme of arrangement, a real corporate action neither
parser attempts. Correct lineage + silently-absent adjustment fabricated a
~90x return. Found in 14 of 318 lineage transitions (4.4%). Confirmed to
leave rank IC essentially untouched (magnitude-robust) while corrupting the
mean-based cost-hurdle calculation materially (43.5% -> 34.3% x-sectional
std just from excluding these 14 entities) -- **this 43.5%/34.3% pair is
superseded; see the correction below.** It was measured before Bug #2's
gap-fix existed. On today's production code the uncorrected figure is
already 36.9% (Bug #2 independently NaNs all 14 boundary returns), and a
dedicated structural guard for this exact bug
(`src/data_layer/lineage_jump_guard.py`) was built, tested, and confirmed
to change nothing further on this dataset -- Bug #2 got there first, for
all 14 known cases. Built, currently redundant, retained deliberately: a
capital reduction or scheme of arrangement without a coincident trading
halt would slip past Bug #2's calendar-gap check but not this guard, and
this dataset's 14-for-14 pattern is not a guarantee that stays true going
forward. Full detail in `BUGS.md`'s Bug #1 entry.

**Bug #2 (stale-gap contamination in the LABEL, not just the features).**
Row-based `shift()` treated a multi-month trading halt as one ordinary
day's return, in three places: `trailing_vol_252`, `momentum_12_1`/`_6_1`,
and **the forward-return target itself**. The target is used to measure
every factor's IC -- a contaminated target corrupts every factor's IC
simultaneously, not just one. This is the worst place a bug like this can
live, because it doesn't show up as one factor looking wrong; it shows up
as all of them looking wrong in ways that could be individually rationalized.

**Found by chasing a decile/IC sign conflict, not by dropping the factor
that revealed it.** `trailing_vol_252`'s decile-mean table contradicted its
own negative IC -- structurally impossible for clean data. The instinct was
to read this as "vol is unreliable" and move on; the correct read, once
pushed on, was "the panel is still contaminated and vol happened to be the
factor sensitive enough to show it." Same root cause produced opposite
symptoms in the two factors it touched (vol's chained multiplicative
returns inverted the relationship; momentum's endpoint-comparison only
diluted it) -- that mechanistic asymmetry, not just the fixed numbers, is
what makes the fix credible rather than a convenient adjustment.

## 6. What was not tested

- **Value, Quality, Size**: blocked on missing infrastructure (no
  full-history fundamentals backfill, no balance-sheet extraction beyond
  one quarter's P&L snapshot, no shares-outstanding/market-cap history, no
  sector classification at the time factor work started). Not attempted --
  building this only becomes worthwhile once the price-layer methodology
  proved sound, which Study 1 was the test of.
- **`trailing_vol_252` and `beta_252`**: deliberately excluded from this
  holdout evaluation, pre-registered as out of scope. Testing all four
  factors against one holdout would have been four trials charged to a
  resource built to tolerate one. `trailing_vol_252` in particular still
  carries the diagnostic history in Section 5 and has not earned a holdout
  spend of its own.

## 7. Holdout status: spent

Study 1 of 3 complete. The sealed 18-month holdout for this dataset has
been read once, per `PREREGISTRATION.md`, and is now **spent**. Per this
project's own standing rule, it cannot be re-read, re-run on a modified
configuration, or appealed. Two further pre-registered studies remain
available against this dataset (Value/Quality/Size construction, or a
retest of `trailing_vol_252`/`beta_252` under their own pre-registration,
are both candidates -- not decided here).

## 8. What this is not

**Not a green light to trade.** Specifically:

- **Thin sample.** 5 holdout periods (fewer than the ~6-7 pre-registered),
  margin 3.87 points against a 3.0-point threshold -- a different period
  boundary could plausibly flip the pass/fail call. A pass at this sample
  size is weak evidence, exactly as `PREREGISTRATION.md` stated before the
  result existed, and that statement binds now that it passed, not only if
  it had failed.
- **Untested crash behavior.** Two mild drawdowns in the holdout is not a
  crash test. Section 4's 2020 episode remains the only evidence of how
  this strategy behaves in a violent reversal, and nothing in the holdout
  period tested that regime -- but Section 4's own amendment now applies
  here too: the originally-reported "-20 points relative" figure was a
  calendar-year-2020 artifact, not a mechanically-defined result. Measured
  from the market's own peak and trough instead of a calendar boundary,
  momentum finished the full 2017-2021 drawdown episode AHEAD of the
  benchmark by +32.68 points, and the recovery leg specifically shows
  +3.73 points, not -20. The weakness this bullet originally pointed to is
  real but smaller and far more window-dependent than stated here before;
  see Section 4 for the full reconciliation, not this bullet in isolation.
- **Low-liquidity cost: checked, not just flagged, and closed.** The
  ~118bps low-liquidity-tercile cost was uncalibrated Corwin-Schultz, with
  an unverified calibration argument (borrowing a T2T-name finding for a
  tercile assumed, not confirmed, to behave like T2T names). Both gaps are
  now closed by direct measurement, not left open: the tercile is 0% BE/BZ
  by construction (`entity_panel.py` filters `series='EQ'` unconditionally,
  so the T2T-calibration borrow never applied to begin with), and a cost
  sensitivity sweep across the full plausible range (118bps down to a
  fully-calibrated ~25bps) moves the momentum/benchmark margin by at most
  +0.30 points -- because low-liquidity names are only ~10.5% of top-decile
  momentum's mean composition. 118bps is retained as the working number: it
  is still not a live measurement, but it is now a known-uncertain input
  with directly measured, low leverage on this strategy's headline result,
  not an unresolved one. Closed; no live order-book verification is planned
  for it, since none could change this conclusion.
- **A sector-rotation pattern with no holdout precedent, but NOT a
  demonstrated risk factor.** Momentum's top decile is not sector-neutral
  and rotated hard into Healthcare in 2020 in both universes tested (see
  the diagnostic below) -- that rotation is real and replicated. Whether
  concentration itself predicts bad relative performance was tested
  directly (Section 11) and found to have no measured basis: no significant
  correlation, opposite signs across the two studies, and the individual
  highest-concentration periods split roughly evenly between gains and
  losses. Do not read "momentum concentrates in a narrow winner set" and
  "concentration causes underperformance" as the same claim -- only the
  first has evidence.

---

## Sector concentration diagnostic (does not spend a study slot)

Requested to speak directly to the 2020 risk in Section 4. Sector data:
NSE's Nifty Total Market constituent list (755 names, real "Industry"
classification, not the thematic sub-index names) joined to the top-decile
momentum holdings at every pre-holdout rebalance. **Coverage caveat, stated
upfront**: only 44.9% of top-decile holdings on average match a symbol in
this 755-name list -- the remainder are smaller names outside Nifty Total
Market's coverage and have no sector label here. The numbers below describe
the mapped ~45%, not the full portfolio.

| year | mean top-sector concentration | dominant sector |
|---|---|---|
| 2017 | ~20% | Metals & Mining / Financial Services / Capital Goods |
| 2018 | ~18% | Capital Goods, then Information Technology |
| 2019 | ~21% | Information Technology, then Financial Services |
| **2020** | **~30%, peaking at 37.3%** | **Healthcare (Pharma)** |
| 2021 | ~19% | Healthcare, then Information Technology / Capital Goods |
| 2022-2024 | ~29% | Capital Goods (persistently) |

**2020-09-08 shows the single highest sector concentration in the entire
pre-holdout series: 37.3% of the mapped top-decile portfolio in Healthcare.**
This is not a coincidence -- pharma/healthcare names were the mechanical
"recent winners" of the COVID period (vaccine, PPE, and hospital-demand
plays), and a momentum strategy chasing recent winners rotated hard into
exactly that sector precisely when the market's own composition of winners
had become unusually narrow. Healthcare stayed the dominant sector through
2020-12-09 (32.1%) before fading in 2021.

**Amendment, after Section 11's diagnostic: the sentence that used to stand
here claimed this concentration was a mechanism for 2020's
underperformance. That causal claim was tested directly and did not
survive testing** -- 2020-09-08 (rank 1 of 30 by concentration) did return
-5.88% relative that period, but concentration itself shows no measured
relationship to subsequent relative return across either universe tested
(Section 11), and the single most concentrated period in Study 2's entire
series (2020-01-21, 57.9% in one sector) returned **+2.37%**, not a loss.
What survives is narrower and still real: **momentum rotated into
Healthcare in 2020 in both the microcap and large-cap universes tested** --
a genuine, replicated observation about how this factor responds to an
unusually narrow market-wide winner set. That the rotation also predicts
worse performance is a separate claim this project does not have evidence
for.

---

## 9. Data constraint: survivorship-bias-free US equity data is not free

Attempted before Study 2, as a cross-market replication test. Assessed
against the same licensing standard applied to NSE/BSE/Screener.in in
Phase 1.

**Every source that is genuinely free (yfinance, Stooq, the Nasdaq.com/NYSE
retail website) fails at least one of two required bars, and most fail
both:**

- **yfinance**: Yahoo's own terms explicitly prohibit automated/robotic
  data collection; the data is stated "for personal use only." Separately,
  and independent of the licensing question, delisted tickers routinely
  return "no data found" -- confirmed via multiple upstream GitHub issues.
  A backtest built on it would have been survivorship-contaminated even if
  the licensing question were waived.
- **Stooq.com**: terms of use were not fetchable in this research pass.
  Treated as unverified, not as permitted -- the same standard this project
  applied to every other source, rather than assuming a popular free source
  is safe by default.
- **Nasdaq.com / NYSE retail site**: explicit "personal, non-commercial
  use" only, explicit no-robots clause. The free lookup tool is built
  around live listings with roughly a 10-year cap; delisted-ticker history
  is not retrievable through it at all.

**The sources that are actually advertised as survivorship-bias-free
(Sharadar via Nasdaq Data Link, EODHD, Norgate Data, and the academic
gold-standard CRSP) are all paid**, ranging from roughly $20-70/month for
the commercial options up to institutional-only licensing for CRSP. EODHD
at $19.99/month was the best-fitting option found (ToS-permitted for
research, delisted coverage since 2000, point-in-time index constituents
available for constructing a period-correct benchmark).

**Decision: do not pay. Pivot to a second Indian population instead
(Study 2, below).** Worth recording as a general observation, not just a
project-specific one: a meaningful fraction of retail momentum/factor
backtesting in the public domain likely runs on exactly the three sources
ruled out here, which means a nontrivial fraction of that published work is
probably survivorship-contaminated, licensing questions aside.

---

## 10. Study 2 -- large-cap replication (CV-only, no holdout)

**This section is CV-only evidence on data this project has already seen
in full (the pre-holdout partition). It is weaker evidence than Study 1's
holdout test and must not be read as equivalent.** No holdout exists for
this study; none was spent.

### Question

If `momentum_12_1` is a real effect and not an artifact of the
microcap-heavy whole-market universe Study 1 used, does it show a positive
margin over equal-weight in Indian large-caps too? Momentum is documented
globally to be weaker in large caps -- the sign was expected to hold, the
margin was expected to shrink, and a lower decision threshold (2.0 points
vs Study 1's 3.0) was fixed in advance for that reason.

### Universe

Top 200 entities by trailing 252-day median turnover, reconstituted
annually (membership for year Y decided from year Y-1's year-end data only
-- no lookahead), plain rank band, no buffer. Same entity-resolved,
gap-filtered (`STALE_GAP_DAYS=5`) panel as Study 1. Realized universe size
per rebalance: 177-190 entities (mean ~181) out of the 200-name annual
cohort -- the shortfall is names that drop out of a given rebalance due to
gap-exclusion, matching the same benign-exclusion pattern quantified in the
survivorship check.

### Configuration

Identical to Study 1: `momentum_12_1`, long-only, top decile, equal
weight, 63-day rebalance. Not retuned. Cost: flat 23bps round-trip (the
high-liquidity tercile rate, not blended) -- large-cap by construction, and
the most reliable of the three tercile estimates since it is anchored to
the prior project's live order-book measurement rather than a calibrated
or uncalibrated Corwin-Schultz proxy.

### Results

| | momentum | equal-weight benchmark |
|---|---|---|
| CAGR (net) | 17.95% | 11.39% |
| Sharpe | 0.77 | 0.58 |
| MaxDD | -36.52% | -44.51% |

**Decision rule, all three evaluated separately:**
- (a) CAGR exceeds benchmark: 17.95% vs 11.39% -> **PASS**
- (b) margin >= 2.0 points: margin = **6.56 points** -> **PASS**
- (c) MaxDD not >10 points worse than benchmark's: momentum's MaxDD is
  *7.99 points better*, not worse -> **PASS**

**OVERALL: REPLICATES.**

As predicted, the margin shrank relative to Study 1's pre-holdout backtest
(6.56 points here vs 12.32 points there) -- consistent with momentum being
weaker, though still clearly present, in a large-cap population. The sign
held in every one of the three conditions.

27 individual period returns recorded in
`data/study2_largecap_records.csv`; not reproduced in full here.

### Sector concentration -- the hypothesis this was meant to test, and the answer it gave

The stated hypothesis was: *"large-caps should concentrate less than
microcaps; if concentration is similar, the 2020 failure mode is a property
of momentum itself rather than of thin universes."*

| | Study 1 (microcap, ~1000-1300 name universe, ~110-130 holdings/decile) | Study 2 (large-cap, ~180 name universe, ~20 holdings/decile) |
|---|---|---|
| mean top-sector concentration | 24.35% | **29.61%** |
| mean HHI | 0.129 | **0.179** |
| sector-data coverage | 44.9% | 83.6% (better -- large-caps match the Nifty Total Market list far more completely) |

**Concentration in the large-cap top decile is not lower than the
microcap universe's -- it is higher on both measures.** This does not
confirm the stated hypothesis's directional prediction, but it does answer
the underlying question the hypothesis was built to test: concentration is
not a thin-microcap-universe artifact, since it appears at least as
strongly in a large-cap population.

**One confound stated plainly, not glossed over**: the large-cap top
decile holds roughly 20 names against the microcap universe's ~110-130.
Concentration statistics (HHI, top-sector share) are mechanically higher
for smaller portfolios independent of any real sector-rotation behavior --
fewer holdings simply have fewer ways to spread across sectors even under
a uniform random allocation. Part of the large-cap/microcap gap in this
table is very likely this arithmetic effect, not a stronger rotation
tendency. No null-distribution simulation was run to separate the two
effects; that would be needed before treating the raw magnitude comparison
(29.6% vs 24.4%) as itself meaningful.

**What survives the confound, because it is not a magnitude comparison**:
**Healthcare is the dominant sector in the large-cap top decile through
2020-04-27, 2020-07-27, and 2020-10-23** (26.3%, 35.3%, 29.4%), the same
sector and the same year found dominant in Study 1's microcap universe.
The same regime-driven rotation into the same sector, in the same crisis
year, in a population an order of magnitude more liquid and differently
constructed. That is real evidence the rotation-into-a-narrow-winner-set
finding is a property of the momentum effect itself, not an artifact of
Study 1's specific thin, microcap-heavy universe. **This is a claim about
the rotation existing and replicating, not about it predicting
performance** -- Section 11 tests the performance-prediction claim directly
across both studies and finds no measured basis for it.

### Study counter

Study 2 of 3 complete for this dataset. One pre-registered study remains
available. Study 2 used no holdout and spends none of the one that remains
sealed.

---

## 11. Diagnostic: does concentration predict subsequent relative performance? (not a study, no slot spent)

Descriptive measurement on data already seen (both studies' pre-holdout
partitions). No strategy, no decision rule. Purpose: decide whether a
sector cap or a concentration-based risk indicator is worth pre-registering
as Study 3, before spending the last slot on it.

**Result: null, and clean.** Concentration at selection time does not
measurably predict the strategy's relative return over the following
period, in either universe.

| | Study 1 microcap (n=30) | Study 2 large-cap (n=27) |
|---|---|---|
| top_sector_pct vs relative_return | rho = **-0.236**, p = 0.210, 95% CI [-0.549, +0.136] | rho = **+0.063**, p = 0.754, 95% CI [-0.325, +0.433] |
| hhi vs relative_return | rho = -0.179, p = 0.344 | rho = +0.013, p = 0.951 |
| partial (controlling for n_holdings) | rho = -0.314, p = 0.097 | rho = +0.035, p = 0.865 |

**The two studies disagree in sign.** A real risk factor would show a
negative correlation (higher concentration -> worse relative performance)
in both populations. Study 1 leans that direction (not significantly);
Study 2 leans the opposite way. Neither reaches significance in either
direction.

**The individual points are more decisive than the correlation coefficients:**

- Study 2's single worst period in the entire series, 2020-04-27 at
  -17.11% relative return, had concentration rank 17 of 27 -- below
  median, unremarkable.
- Study 2's single highest concentration ever measured, 2020-01-21 at
  57.9% in one sector (more than double the next-highest reading), returned
  **+2.37%** -- positive.
- Study 2's second-highest concentration, 2023-11-13 at 50.0%, returned
  **+5.27%** -- also positive.
- Study 1's top five most concentrated periods split 2 losses / 3 gains --
  a coin flip, not a pattern.

**Power constraint, stated plainly**: at n=30 and n=27, a Spearman
correlation needs |rho| >= 0.36-0.38 to clear p<0.05. This rules out a
*strong* concentration-performance relationship in either universe. **It
does not rule out a weak one** -- an effect with |rho| around 0.15-0.25
could exist and remain undetectable at this sample size, and Study 1's
own point estimate (-0.236) sits inside that undetectable band. Absence of
significance here is absence of enough data to see a strong effect, not
proof of zero effect.

**What this does and does not settle, stated as two separate claims:**

- **Momentum rotates hard into a narrow winner-set sector under stress,
  and this replicates across two differently-constructed Indian
  universes.** Real, evidenced twice (Section 10; Healthcare, 2020, both
  studies).
- **That rotation predicts subsequent relative underperformance.** Not
  evidenced. Tested directly here, in both universes, with a null result
  that agrees in neither sign nor significance. Section 4 and the sector
  diagnostic's original text (Section "Sector concentration diagnostic")
  presented the causal version of this claim before it was tested; both
  have been amended to state only the first claim.

**Consequence for Study 3**: a sector cap or a concentration-based
de-risking rule would fix a mechanism with no measured performance benefit,
validated against data already seen. Not pre-registered. The third and
final study slot for this dataset remains unspent.

Logged as a diagnostic (not a study) in `experiments.csv`.

---

## 12. The combination study that couldn't be run -- a result about testability, not about the factor

This section exists because the finding below is real, useful independent
of any factor's fate, and arguably the most transferable methodological
output of the entire fundamentals-layer effort (Phase A through the
Integrated Filing fetcher, `FUNDAMENTALS.md`). It belongs in a findings
document, not buried in a withdrawn pre-registration draft.

### The question

Given `momentum_12_1` (established, Section 2) and `earnings_yield`
(suggestive, near-zero correlation with momentum -- see `FUNDAMENTALS.md`'s
diagnostic), does an equal-weight rank combination of the two add
measurable value over momentum alone? A pre-registration
(`PREREGISTRATION_COMBINATION.md`) was drafted to answer this using the
project's final study slot.

### The finding: the combination's incremental value cannot be validated on this data, at any reachable horizon

Not because the effect is known to be absent -- because the measurement is
too noisy relative to the effect size a second factor could plausibly
contribute. Two metrics were tried, computed on the 2018-2024 window where
both factors exist (26 rebalance dates, 21,533 obs):

| metric | std of the relevant difference | n (or years) needed to detect a plausible true effect at t>=2.0 |
|---|---|---|
| top-decile portfolio margin (combination vs momentum-alone) | 4.657 pts/quarter | ~347 quarters (~87 years) for a true +2-point annualized effect |
| **paired rank-IC difference** (combination vs momentum-alone, same date) | **0.0848** | ~32 quarters (~8 years) for a true 0.03 IC difference; ~72-288 quarters (~18-72 years) for the more realistic 0.01-0.02 range |

**Paired IC difference is the more efficient of the two metrics, and by a
wide margin** -- it uses the full cross-section every date instead of
collapsing ~1,200 stocks into one top-decile portfolio return, and pairing
by date removes the common cross-sectional-dispersion component that
inflates each factor's IC variance separately (confirmed directly: paired
std 0.0848 is tighter than either individual IC's own std, 0.1004 and
0.1259). It is still not enough. Even its best case (a 0.03 true
difference, a generous assumption given `earnings_yield`'s own modest
standalone IC) needs eight years; the more realistic 0.01-0.02 range needs
18 to 72 years. No metric change and no practically reachable increase in
sample size rescues this.

### The general lesson

**The binding constraint on testing an incremental improvement is usually
the variance of the difference, not the size of the effect.** A second
factor's marginal contribution to an already-working strategy is, almost
by construction, smaller than the first factor's own effect -- and the
*noise* in measuring that marginal contribution does not shrink to match.
Most retail backtesting never computes this before declaring a strategy
"improved": a single backtest run showing a better number is treated as
confirmation, when the honest question -- could this comparison's own
noise level have produced a number this size by chance alone, at this
sample size? -- is never asked. This project's own numbers above make the
scale of the problem concrete: an 87-year requirement on the intuitive
metric, an 8-to-72-year requirement even on the more efficient one. A
single-run "improvement" reported without this check could not possibly
distinguish a real gain from noise, and there is no reason to expect this
combination's case is unusual among published or informally-reported
"improved" strategies more broadly.

### The discipline that makes this credible, not convenient

The power analysis was run on **variance only**. Both analysis scripts
(`scripts/run_combination_power_analysis.py`,
`scripts/run_combination_ic_power_analysis.py`) were written so they never
call `.mean()` on any margin, IC, or difference series -- enforced
structurally in the code, not merely omitted from the printed output. This
matters because using the historical mean to size a test's power would be
fitting the threshold to a result already seen -- exactly the kind of
post-hoc reasoning this project's whole discipline exists to prevent. A
power analysis that peeked at the mean while choosing a threshold could
always be tuned to make some threshold look reachable; one that only ever
sees the variance cannot be gamed that way, which is what makes its
negative conclusion trustworthy rather than merely convenient.

### What this does NOT conclude

**`earnings_yield`'s diagnostic findings are unaffected and stand exactly
as reported in `FUNDAMENTALS.md`**: near-zero cross-sectional correlation
with momentum (mean +0.0003, std 0.15), IC holding outside momentum's own
top decile (a test of independence, not of the factor "getting stronger"),
raw standalone IC t=+2.86 that fails multiple-comparisons correction at
m=8 (Bonferroni/BH threshold 0.00625) -- suggestive, not established. None
of that changed. **This finding is about testability, not about the
factor**: even a real, economically meaningful combination effect could
not be distinguished from noise with this project's data, and that is a
statement about the measurement's power, not a statement that no such
effect exists.

### Decision

The final pre-registered study slot for this dataset was **not spent**.
`PREREGISTRATION_COMBINATION.md` is marked withdrawn before approval, kept
as the permanent record of what was considered and why, per this project's
standing practice of recording paths not taken rather than deleting them
(`LICENSE_ASSESSMENT.md`'s rejected sources, Phase D's sector-classification
dead ends). Holding an unusable slot was judged better than spending it on
a multi-year wait for a number nobody could interpret.

## 13. Final state of this project's factor work

| component | status |
|---|---|
| `momentum_12_1` | **Established.** Replicated in two differently-constructed Indian universes (microcap whole-market, Study 1; large-cap top-200, Study 2). Sealed holdout evaluated once and passed (Section 2). |
| `earnings_yield` | **Suggestive, not established.** Independent of momentum (near-zero correlation, signal holds outside momentum's top decile). Fails multiple-comparisons correction on its own. |
| momentum + earnings_yield combination | **Untestable on this data, at any reachable horizon** (Section 12) -- not evaluated as true or false, evaluated as unmeasurable given this project's cross-section size and history length. |
| sealed price holdout | **Spent** (Study 1, `PREREGISTRATION.md`). Cannot be re-read, re-run, or appealed. |
| final pre-registered study slot | **Held, unspent.** Available for a future study against this dataset if one is designed with adequate power from the outset. |
