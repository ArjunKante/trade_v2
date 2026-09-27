# Pre-registration: V1 (dip-in-momentum-winners, Top-10 concentrated), the swing project's holdout test

Frozen before the sealed holdout is touched. Nothing below changes after
this document is written except by an explicit, recorded amendment, the
same discipline `PREREGISTRATION.md` and `PREREGISTRATION_SWING.md`
already established. **This document supersedes `PREREGISTRATION_SWING.md`'s
frozen rule** (momentum ∩ liquidity ∩ dip ∩ volume ∩ regime, the original
V4) -- that rule failed its own historical screen (9.8th percentile, clean
data). This document freezes a DIFFERENT configuration (V1, Top-10
concentrated), arrived at by decomposing why V4 failed, not by tuning V4.

## 0. Provenance -- stated plainly, per instruction

**V1 is the best of 6 decomposition variants, not a first-principles
design.** `scripts/run_swing_phase3_decomposition.py`
(`data/swing_logs/swing_phase3_decomposition_20260927T152209.txt`) tested
one pre-specified family of 6 computable variants (V5/V6, the
fundamentals-screener variants, could not be run -- see Section 1 and
BUGS.md Bug #12) against their own matched-random nulls, Bonferroni- and
Benjamini-Hochberg-corrected:

| variant | percentile | p-value | Bonferroni (α/6) | BH |
|---|---|---|---|---|
| **V1 (dip only)** | **100.0** | **0.0010** | **CLEARS** | **CLEARS** |
| V2 (dip+volume) | 76.1 | 0.2398 | no | no |
| V3 (dip+regime) | 58.2 | 0.4186 | no | no |
| V4 (dip+volume+regime, original rule) | 9.8 | 0.9021 | no | no |
| V7 (momentum+liquidity only, no dip) | 28.5 (degenerate null) | n/a | n/a | n/a |
| V8 (dip, full universe, no momentum) | 100.0 | 0.0010 | CLEARS | CLEARS (but expectancy 0.040-0.170% vs V1's 0.364-0.494%) |

V1 is the only variant that (a) clears both corrections and (b) carries
the strongest absolute expectancy among the variants that clear. It was
then, in a further round of the SAME pre-holdout exploration (not a
separate pre-registered study, not itself Bonferroni-corrected against a
named family): (1) concentrated to the top 10 candidates/day by dip
magnitude, checked against 5/10/20-candidate caps
(`data/swing_logs/swing_v1_checks_20260927T154446.txt`, CHECK 1); (2)
checked for 2025-window sensitivity (CHECK 2) and year-by-year robustness
(CHECK 3); and (3) investigated for what separates its two worst years
(`data/swing_logs/swing_v1_regime_check_20260927T155639.txt`).

**Bonferroni was applied to the 6-variant family and V1 clears it. That
correction does not extend to the further concentration sweep, the
capital check, or the year-by-year breakdown -- all of that was additional
searching on the same pre-holdout data, informal and undisclosed-family,
even though none of it changed a threshold post-hoc (see Section 3: every
number that went into the frozen configuration below was decided from
this exploration, not fit to a target).** V1 has never faced data it was
not, in some part of this exploration, selected or shaped by. The sealed
holdout, read once under this document's decision rule, is the first
genuinely out-of-sample look at this exact configuration.

## 1. Configuration frozen

**Universe** (point-in-time at every signal date, unchanged from
`PREREGISTRATION_SWING.md` except item 5, dropped -- see below):

1. Momentum top decile: `factors.momentum`'s `momentum_12_1`
   (gap-guarded), ranked and deciled as of each candidate date.
2. ∩ liquidity: high_liq + mid_liq turnover terciles, low_liq excluded
   (`src/swing/universe.py`'s `historical_liquidity_tercile`).
3. ∩ `series = 'EQ'` only.
4. ∩ ASM/GSM surveillance names excluded where point-in-time-obtainable.
   **Same unresolved limitation as the original document**: no confirmed
   point-in-time-correct historical source exists yet. Historical
   backtest numbers above are run without it; flagged, not silently
   treated as equivalent.
5. ~~∩ fundamentals screener verdict != FAIL~~ **DROPPED.** BUGS.md Bug
   #12: `fundamental_screener.py` has never been evaluated at a historical
   point in time -- every number in this document (the 6-variant
   decomposition, V1's own historical figures, the Top-10 concentration)
   was produced WITHOUT this condition, exactly as the original
   `PREREGISTRATION_SWING.md` intended it and exactly as it actually ran.
   Adding it now would be freezing an UNTESTED fifth condition, the
   opposite of pre-registering something already screened. If a
   point-in-time historical screener is ever built, testing it against
   this rule is a new trial, requiring its own pre-registration and its
   own charge against the holdout budget (Section 4) -- not assumed here.

Conditions 1-4 above, intersected, are referred to as **POOL_ML** below --
the same population every matched-random null in this document draws
from.

**The rule, frozen:**

**(a) Dip filter**, unchanged from the original: trailing 5-trading-day
return (close-to-close, gap-guarded), bottom tercile of the **FULL EQ
universe** (not ranked within POOL_ML -- the mechanism correction
`PREREGISTRATION_SWING.md` already recorded), intersected with POOL_ML.

**(b) Concentration, NEW**: of the names passing (a), keep only the
**top 10 per day by dip depth** (most negative 5-day return first). Ties
broken by `pandas.DataFrame.rank(method="first")` -- row order within
that day's group as the panel is sorted (`entity_id`, `trade_date`), an
arbitrary but fixed and deterministic tie-break, stated here so it is not
a silent implementation detail. On days with fewer than 10 names passing
(a) (9.3% of days, per the concentration sweep), all of them are taken --
the cap only ever removes names, never adds.

**(c) NO volume filter, NO regime filter.** This is the decomposition's
finding, not an oversight: V2 (dip+volume, 76.1st percentile), V3
(dip+regime, 58.2nd), and V4 (both, 9.8th) all under-performed V1. Adding
either back is not pre-registered by this document; testing them again
would be a new trial.

**Entry**: next trading day's open (t+1). **Exit**: open of trading day
t+6 (5 full trading days held). Unchanged from the original rule -- no
stop loss, no partial exit, daily bhavcopy data only.

**Position size**: Rs 3,00,000. **Order type**: DELIVERY. **Cost model**:
`src/swing/costs.py`, unchanged, both cost-bound ends (30.6-43.6bps
round-trip at Rs 3L) reported, never blended.

## 2. Historical result (pre-holdout, exploratory -- NOT the test)

Top-10 configuration, pre-holdout (2016-2025-03-18, 78-entity BUGS.md
Bug #11 exclusion applied, same as every number in this project's swing
work): n=19,745 trades, mean gross return 0.698%, std (gross) 8.214%,
expectancy 0.262% (worst-case cost) / 0.392% (optimistic cost), win rate
48.4%, profit factor 1.10, **100th percentile vs. matched-random null
from POOL_ML** (1000 seeds, same day-count/timing). Peak concurrent
positions 64, peak deployed capital Rs 1.92 crore at the Rs 3L floor --
compares to the uncapped V1's 348 positions / Rs 10.44 crore for the same
100th-percentile result, at a cost of ~0.10 percentage points of
worst-case expectancy (0.364% uncapped -> 0.262% capped). **This capital
efficiency is why Top-10, not uncapped V1, is the frozen configuration.**

**Stated as exploratory per Section 0, not as evidence carried into the
decision rule below** -- the holdout is the test, not a confirmation of
this number.

## 3. Known, permanent limitation: 2 of 9 pre-holdout years failed, unpredictably

V1 (uncapped; the per-year breakdown was not re-run for the Top-10 cap
specifically, and is not expected to change materially since the cap
mechanically selects a subset of the same signal population) scored at
or above the 93.5th percentile in 7 of 9 pre-holdout years, but at the
**1.1st percentile in 2021** and the **10.1st percentile in 2024** --
worse than or statistically indistinguishable from random selection from
POOL_ML in those two years, despite positive absolute expectancy in both.

**Investigated in full before this document was approved, per instruction
-- settled now, not left as an assumption**
(`swing_v1_regime_check_20260927T155639.txt`, first pass;
`swing_v1_regime_check2_20260927T161355.txt`, full re-run adding V1's own
trade count and candidate-set structure, since the first pass omitted
both):

| observable | flagged (2021, 2024) | other seven | separates cleanly? |
|---|---|---|---|
| POOL_ML mean 5d fwd return | **1.052%** | **0.062%** | NO -- see below |
| cross-sectional 5d dispersion | 6.661% | 6.436% | no (statistically indistinguishable) |
| NIFTY return | 16.27% | 11.06% | no (non-monotonic, see below) |
| NIFTY realized vol (annualized) | 14.89% | 15.27% | no (flagged years are LOWER, not higher) |
| V1 avg dip magnitude selected | -5.133% | -5.697% | no (wrong direction, see below) |
| V1 trade count | 8,440 | 6,906 | no (modest, not exceptional) |
| V1 candidates/day (mean) | 34.6 | 33.5 | no (negligible) |
| V1 unique entities selected | 365 | 320 | no (modest) |
| V1 trades per unique entity | 23.05 | 20.88 | no (modest) |

**Correction to the first pass's NIFTY-vol figure**: the first pass
reported "23.38% vs 19.93%" for this row: a computation artifact --
computing a single pooled daily-return series across the non-flagged
years with the flagged years excised mid-timeline, then taking
`pct_change()` across the resulting date-discontinuity, fabricates a
large fake one-day "return" at each seam. Recomputed properly here
(per-year volatility, then averaged): flagged years are actually **lower**
vol (14.89%) than the other seven (15.27%), reversing the earlier
(wrong) direction. Recorded so the earlier number is not left standing
uncorrected.

**The one aggregate-level gap that looks real -- POOL_ML's own mean
return, 1.052% (flagged) vs 0.062% (other seven) -- does not survive
inspection at the individual-year level**, which is where a usable
threshold would have to hold: 2023's POOL_ML mean (1.290%) exceeds
**both** flagged years individually (2021: 1.395%, barely above 2023;
2024: 0.709%, clearly below 2023) -- yet 2023 scored the 98.6th
percentile (a pass) while 2024, with a COOLER pool than 2023, scored the
10.1st (a failure). A rule of the form "POOL_ML mean above threshold X
predicts V1 failure" cannot be drawn through these three points without
misclassifying one of them -- 2023 vs 2024 is not a case of insufficient
evidence for the "pool ran hot" hypothesis, it is a directly falsifying
counter-example (a cooler pool-year failed while a hotter one passed),
so this refutes that hypothesis rather than merely failing to confirm it.
The same non-monotonicity appears in NIFTY
return: 2017's return (28.75%) exceeds 2021's (23.79%) and still scored a
pass (93.5th percentile), while 2024's return (8.75%) is unremarkable --
lower than five of the other seven years -- and still failed.

**Verdict, stated plainly per instruction: the two years share nothing
measurable that forms a usable, observable-in-advance risk condition.**
Nine candidate observables were checked across two independent
investigation passes (four in the first pass, five more --  including
trade count and candidate-set structure -- in the full re-run). None
separates 2021/2024 from the other seven cleanly enough to survive an
individual-year check, including the one that looked most promising in
aggregate. **The existing limitation wording stands as written**: this
rule has no known observable condition that predicts when it stops
working. Even a holdout pass should be read with the expectation that the
edge can vanish, or invert, unpredictably, in roughly 2 years out of 9 by
this record. No condition has been added to V1's configuration (Section
1) as a result of this investigation, per instruction -- this section
exists to make the limitation statement accurate and to record, for any
future variant's own pre-registration, that POOL_ML's own heat is the
only lead worth re-examining with a larger sample, not a validated rule.

## 4. THE HOLDOUT: what it is, and the correction to how it was first framed

`src/data_layer/holdout.py`: `SEALED_HOLDOUT_START = 2025-03-19`,
`SEALED_AT = 2026-09-19`, an 18-month sealed window. Every phase 1-4
swing script to date has used the pre-holdout panel only
(`authorize_holdout` never passed as `True` anywhere in `src/swing/` or
its scripts) -- confirmed, not assumed.

**Correction, made before this document went further**: an earlier
framing of this section stated the swing holdout as unspent and available
to spend exactly once. That is not accurate for the underlying resource.
`FINDINGS.md` Section 7 ("Holdout status: spent") and its summary table
("sealed price holdout | **Spent** (Study 1, `PREREGISTRATION.md`).
Cannot be re-read, re-run, or appealed.") record that this EXACT window
was already read once, by the main momentum project's Study 1
(`scripts/run_holdout_study1.py`, `authorize_holdout=True`), before this
document was written. It is the same physical resource, not a separate
swing-specific allocation. `FINDINGS.md` Section 6 records that **two
further pre-registered studies remain available against this dataset**
(Value/Quality/Size construction, or a `trailing_vol_252`/`beta_252`
retest, were the named candidates there -- not decided as exclusive).

**Decision, made by the user, recorded here**: this V1 holdout read is
charged as **one of those two remaining project-wide slots**. When the
actual read happens (the future script that passes
`authorize_holdout=True` for this purpose), `FINDINGS.md`'s holdout-status
table and Section 6/7 narrative must be updated in that same change, so
the project's own ledger stays accurate and nobody double-spends the
remaining slot later. Not done in this document, since nothing has been
read yet.

**What is, and is not, contaminated by Study 1 having already read this
window**:

- Study 1 measured the **momentum top-decile portfolio with NO liquidity
  screen** (`PREREGISTRATION.md`: "No additional liquidity screen. Whole
  market, including microcaps.") -- a related but NOT identical
  population to POOL_ML, which additionally requires high/mid liquidity
  tercile. Its holdout result: 14.72% CAGR vs. a 10.85% benchmark CAGR in
  this exact window (`FINDINGS.md` Section 2). **This is directional
  context, not a re-measurement of POOL_ML itself** -- POOL_ML has never
  been evaluated in this window by any prior study. The inference that
  POOL_ML likely also ran hot in this window (same underlying momentum
  mechanism, overlapping but not identical universe) is plausible, not
  confirmed.
- **Consequence for the decision rule**: an absolute "positive expectancy
  net of costs" condition would be close to uninformative here. If the
  momentum-tilted population ran hot in this window (as the related,
  already-published measurement suggests), then close to any selection
  rule drawn from POOL_ML would show positive expectancy, regardless of
  whether V1's own selection (dip-within-winners, Top-10 concentrated)
  adds anything beyond the pool's own drift. **Demoted from a gate to a
  reported figure, per instruction** -- see Section 5.
- **What is NOT contaminated**: the percentile-vs-matched-random test.
  Both V1's actual trades and the random-draw null are sampled from the
  SAME POOL_ML population, on the SAME calendar days, in the SAME window
  -- the pool's own hot-or-cold performance in this window cancels out of
  the comparison by construction. A rule with no real selection power
  would still center near the 50th percentile against its own pool's
  null, hot pool or not. **This is why it remains the primary gate.**
- **Also recorded**: V1's entire design -- the decomposition that selected
  it over 5 alternatives, the Top-10 concentration choice, the tie-break
  rule, both checks, and the year-by-year investigation -- was derived
  **strictly from the pre-holdout panel** (`build_open_close_panel(con,
  SEALED_HOLDOUT_START)`, truncated before 2025-03-19 throughout). No
  swing-specific parameter, threshold, or the choice of V1 itself over
  V2-V8, was set with any visibility into what the holdout window
  contains. This is what makes the percentile test meaningful despite
  sharing a window with Study 1's unrelated momentum measurement: nothing
  about V1's construction responds to what is in the holdout.

## 5. Decision rule, fixed now, before the read

**PRIMARY GATE**: compute V1 (Top-10 concentrated)'s trades over the
sealed holdout window (2025-03-19 through the end of the sealed 18-month
window). Compute its mean gross return's percentile against a
matched-random-entry null drawn from POOL_ML **restricted to the same
holdout window**, same day-by-day trade count and timing as V1's own
holdout trades, 1000 seeds -- the identical construction used throughout
this document's pre-holdout numbers, applied once, here, for real.

- **PASS**: percentile >= 95 (equivalently, one-sided permutation
  p <= 0.05 against the 1000-seed null).
- **FAIL**: percentile < 95.
- No middle category. A pass means "this configuration held up on data it
  was never shaped by," not "live-viable" -- Section 3's limitation
  applies regardless, and execution/capital feasibility was already
  answered affirmatively by Section 2's Rs 1.92 crore figure, a separate
  question from statistical significance.

**REPORTED, NOT GATING**: expectancy net of both cost-bound ends at Rs
3L, over the same holdout window. Reported with this note attached every
time, per instruction: **"POOL_ML's own performance in this window is
already known, directionally, to have been strong (Study 1's related
momentum measurement, 14.72% vs 10.85% CAGR) before this figure was
computed. This number reflects the pool's own drift as much as V1's own
selection, and carries little information on its own -- it is not a
pass/fail condition."**

**SECONDARY, DESCRIPTIVE ONLY**: win rate, avg win, avg loss, profit
factor, peak concurrent positions, peak deployed capital, trade count,
max drawdown -- reported for the record, not gating anything.

## 6. Power calculation, from historical variance only, never the mean

Same formula and discipline as `PREREGISTRATION_SWING.md`: n = (t_threshold
x std / effect)^2, t_threshold=2.0 and effect=0.5% both fixed now, neither
fit to a result. **Only the std input is measured**, from Top-10's own
pre-holdout per-trade gross-return distribution (Section 2): std=8.214%.

    n = (2.0 x 0.08214 / 0.005)^2 ~= 1,080 trades

**This 1,080 figure governs when the primary gate may be read at all --
no interim percentile is evaluated before this many holdout trades exist**,
same discipline as the original document. Top-10's own historical rate
(19,745 trades / 9.21 pre-holdout years ~= 2,144 trades/year, cap binding
on 90-100% of days per the concentration sweep) suggests the full 18-month
sealed window would contain roughly 3,200 trades if the historical rate
holds -- comfortably above 1,080 -- but this is an estimate from historical
conditions, not a guarantee; if the actual holdout window produces fewer
than 1,080 Top-10 trades, the primary gate is not evaluated at all, and
that -- not a forced early read -- is the recorded outcome.

## 7. What is NOT being tested, and what is NOT decided here

- No stop-loss, no partial exits, no position scaling beyond the fixed
  Top-10/day cap, no portfolio-level capital-constraint modeling beyond
  the measured Rs 1.92 crore peak.
- No claim that V1 is "the" short-term-reversal effect -- this project's
  own specific, frozen version, tested on its own terms.
- No forward (live, not-yet-existing) data is invoked here. Per the
  user's explicit decision, superseding `SWING.md`'s original framing
  ("forward paper trading... is this project's primary validation"), the
  ALREADY-SEALED 18-month historical holdout is the test, not a live log
  starting today. If the primary gate fails or cannot be evaluated
  (Section 6), whether a live forward log is still worth running is a
  separate decision, not made here.
- Whether V2-V8, or the fundamentals-screener variants once a
  point-in-time historical screener exists, are worth their own future
  pre-registration and their own holdout charge is not decided here.
- This document does not authorize the holdout read. It fixes the rule
  and the decision thresholds so that when a future script does pass
  `authorize_holdout=True` for this purpose, nothing about the rule or
  the threshold can be adjusted in response to what that read shows.
