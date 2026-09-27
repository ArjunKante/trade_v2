# New Trading Research Direction: Hypothesis Design Only

Research-design document, per instruction. **No strategy implemented, no
parameter sweep run, no holdout touched.** Every number below is either
already published in an existing findings/design document (cited by file
and section) or a direct, read-only, non-holdout query run for this
document specifically (stated as such where it occurs). Phases below
follow the structure given in the authorizing instructions exactly.

## Validation constraint -- stated up front, because it bounds every hypothesis below

There is **no untouched historical validation window** left for a new
short-horizon hypothesis. `FINDINGS.md` Section 7 (this project) records
the shared project-wide holdout ledger at **2 of 3 spent**, and the
remaining slot is already recorded, in that same document, as not to be
used for another short-horizon variant. The sibling `trade-info` project's
own price-history holdout is separately **fully spent** (its `FINDINGS.md`
Section 8: "No further holdout exists for this dataset... any future study
run against this same price history is CV-only"). `trade-info`'s Study 3
fresh-data track is **frozen and immature**: as of the most recent monitor
run (`trade-info/STUDY_3_FRESH_DATA_MONITOR.md`, run #4, 2026-09-19),
431,945 fresh rows exist (2026-01-01 through 2026-09-18) but only **2 of
the required 4** non-overlapping 63-trading-day mature periods have
completed -- the monitor's own stated next action is to wait ~6 more
months. Its fresh data must not be touched by model inference before
then.

**Consequence, applied to every hypothesis in this document**: the only
clean test available for anything genuinely new is **forward** -- data
that does not exist yet. At 5-day horizons this generates roughly 550
trades/year (a real read within about a year); at the 63-day horizon
`momentum_12_1` already uses, it generates roughly 4 independent
rebalances/year (a real read taking years, stated honestly per hypothesis
below, not glossed over). Every candidate hypothesis states its own clean
validation path, or states plainly that none exists at reachable scale.

---

## Phase 1: Audit

Factual map of every named project, built by reading each project's own
findings/design documents directly (`trade-new/FINDINGS.md`,
`trade-new/SWING_FINDINGS.md`, `trade-new/PREREGISTRATION_SWING.md`,
`trade-new/PREREGISTRATION_SWING_V1.md`, `trade-info/FINDINGS.md`,
`trade-info/DESIGN.md`, `trade-info/STUDY_3_FRESH_EVALUATION_REPORT.md`,
`trade-info/STUDY_3_FRESH_DATA_MONITOR.md`), not invented or summarized
from memory.

### Project 1 -- ML on price/volume (`trade-info`, Studies 1 and 2)

| field | value |
|---|---|
| Hypothesis | A pooled LightGBM regressor on price/volume-derived features predicts cross-sectional forward 63-day return, net of retail costs. |
| Universe | Study 1: turnover-rank-buffered ~300-354 names (found, via Bug #7, to be the most-liquid band, not the intended mid-cap band -- a description bug, not a result bug). Study 2: plain turnover-rank band [200,600], no buffer, 401 names/year, T2T-excluded. |
| Features | Study 1: 25 (6 price, 5 volatility, 3 volume, 5 cross-sectional rank, 2 entity, `entity_id` categorical, 3 calendar). Study 2: same 25 + `delivery_percent` (26 total). Short-window (1d/5d) price features present in both sets. |
| Target | Forward 63-trading-day return, cross-sectionally z-scored per date. |
| Holding period / entry / exit | 63-day non-overlapping rebalance; implicit (portfolio-level, not per-trade entry/exit timing). |
| Validation design | `PurgedKFold`, purge=63D/embargo=5D, both studies; leakage suite (label shuffle, feature shift, regime split) before either ensemble was trusted. |
| Development window | Study 1/2 training: all data before `HOLDOUT_START=2024-07-01`. |
| Holdout window | `>=2024-07-01`, ~18 months, spent once (Study 2 only -- Study 1 failed at CV and never reached it). |
| Costs | Study 1: flat 42.2bps (informal). Study 2: ground-truth-measured 26.0-39.0bps (`trade-info/FINDINGS.md` Section 7 -- Corwin-Schultz/Roll overstate real NSE spreads 12-31x on normally-traded names). |
| Trial count | Study cap = 3 for this dataset (`trade-info/FINDINGS.md` Section 1/8); 2 used. |
| Final result | Study 1: CV IC 0.0281 vs. 0.03 threshold -- **failed at CV, holdout never spent.** Study 2: CV IC 0.0816 (passed all 3 gates) -> holdout IC **-0.0206**, t=-1.24 -- **sign reversed.** |
| Known failure mode | Momentum-family persistence statistic itself reversed sign between train and holdout (measured directly, placebo-checked: `trade-info/FINDINGS.md` Section 3). `entity_id` measured to leak 55.3%/48.9% of model gain and to defeat time-based purging (Section 6) -- a distinct, independently-documented defect, not the explanation for the sign reversal (ablating it raised CV IC to 0.099, so it was not "the" cause of the elevated CV number). |

**Matches the user's one-line summary exactly**: NO EDGE, holdout reversed sign. No discrepancy found.

### Project 2 -- 63-day momentum, and momentum+fundamentals (`trade-new`)

| field | value |
|---|---|
| Hypothesis | `momentum_12_1` (12-month trailing return, skip most recent month, Jegadeesh-Titman construction), long-only top decile, equal-weight, 63-day rebalance. |
| Universe | Study 1: whole-market microcap-heavy, no liquidity screen (`PREREGISTRATION.md`: "No additional liquidity screen. Whole market, including microcaps"). Study 2 (replication): top-200-by-turnover large-cap, annual reconstitution, realized ~177-190 names/rebalance. |
| Features / target | Single factor (momentum rank), no ML model; target is realized forward portfolio return. |
| Holding period | 63 trading days, non-overlapping rebalance. |
| Validation design | Pre-registered 3-condition decision rule (CAGR > benchmark, margin >= threshold, MaxDD not worse by more than a stated slack), fixed before the holdout was read. |
| Development window | 2017-2024 pre-holdout. |
| Holdout window | `SEALED_HOLDOUT_START=2025-03-19` through the latest ingested date, 18 months (`trade-new/src/data_layer/holdout.py`). |
| Costs | Tercile-based (high/mid/low liquidity), 23.0/32.5/118.0bps, ported from `trade-info`'s ground-truth measurement. |
| Trial count | Project-wide cap of 3 holdout reads on this dataset (`FINDINGS.md` Section 6/7); Study 1 = 1 of 3 (this project's own), now 2 of 3 after the swing V1 read (Section below). |
| Final result | Study 1: **PASS**, all 3 conditions (CAGR 14.72% vs 10.85%, margin +3.87pts, MaxDD 3.97pts *better*). Study 2 (large-cap, CV-only, no holdout spent): **replicates**, margin shrank as predicted (6.56pts vs 12.32pts), sign held on all 3 conditions. |
| Known failure mode / caveat | Mechanism is **downside protection, not upside capture** (`FINDINGS.md` Section 3: all 3 holdout wins came in falling markets, both losses in rising markets, both small). 2020 calendar-year showed a real ~20pt underperformance, later found to be a boundary-sensitive artifact of calendar-year framing rather than the mechanically-defined peak-to-trough episode (Section 4) -- momentum finished net ahead over the actual drawdown episode. Top-decile portfolio concentrates heavily into single sectors during crises (Healthcare, 2020, reproduced in **both** independently-constructed universes -- a real property, not a thin-universe artifact, though partly mechanically inflated by the large-cap portfolio's smaller holding count). |
| Momentum + `earnings_yield` combination | **Untestable at any reachable horizon** (`FINDINGS.md` Section 12): paired rank-IC-difference power analysis needs ~8 years for an optimistic 0.03 true effect, 18-72 years for a realistic 0.01-0.02 effect. General lesson: testing an incremental modification of an already-working strategy is bounded by the *variance of the difference*, not the size of the improvement -- this lesson is load-bearing for Phase 4/5 below. |

**Matches the user's summary exactly**: WORKS (holdout passed); combination UNTESTABLE (8-72 years). No discrepancy found.

### Project 3 -- Swing, V4 and V1 (`trade-new/src/swing/`)

| field | value |
|---|---|
| Hypothesis (V4, original) | Momentum-top-decile stocks in the bottom tercile of market-wide 5-day return ("established winners having a bad week"), with elevated volume (>1.5x 20d avg) and Nifty above its 50-day SMA, held 5 trading days. |
| Hypothesis (V1, decomposed) | Same dip condition, momentum/liquidity universe -- **volume and regime filters removed**, later concentrated to the top 10 candidates/day by dip depth for capital efficiency. |
| Universe | Momentum top decile (point-in-time, every date) ∩ liquidity tercile (high/mid, low excluded) ∩ series=EQ. Fundamentals-screener condition (item 5 of the original pre-registration) **specified but never applied** -- Bug #12 below. |
| Target / horizon | Open-to-open, entry t+1, exit t+6 (5 trading days held). |
| Validation design | Matched-random-entry-from-same-pool percentile test (1000 seeds), not a CV/ML split -- the population being tested is a hand-specified rule, not a fitted model. |
| Development window | Pre-holdout, 2016 through 2025-03-18 (~9 years). |
| Holdout window | Same `SEALED_HOLDOUT_START` as Project 2, 2025-03-19 through 2026-09-18. |
| Costs | Groww-specific DELIVERY cost model (`trade-new/src/swing/costs.py`): 30.6-43.6bps round-trip at the Rs 3L position floor. |
| Trial count | 6 computable decomposition variants (V1-V4, V7, V8; V5/V6 blocked, Bug #12), Bonferroni+BH corrected; V1 selected as best-of-6, then a further, **not itself Bonferroni-corrected**, exploration (Top-N concentration sweep, 2 capital/2025/year-by-year checks, 2 mechanism-search passes) before pre-registration (`PREREGISTRATION_SWING_V1.md` Section 0, stated explicitly there). |
| Final result | V4: 9.8th percentile vs. matched-random null -- **worse than random, in-sample.** V1: 100th percentile, p=0.001, n=65,219, Bonferroni+BH-cleared, in-sample -> **61.4th percentile, p=0.387, n=3,620, on the sealed holdout -- FAIL** (threshold was >=95). |
| Known failure mode | Two pre-holdout years (2021, 2024) already showed V1 losing to random selection with **no observable-in-advance cause** across nine measured variables (pool heat, cross-sectional dispersion, NIFTY return/vol, dip magnitude, trade count, candidates/day, unique entities, trades/entity) -- `PREREGISTRATION_SWING_V1.md` Section 3. Cost gate (Phase 1, before any signal existed): break-even at 5 days requires IC~=0.05 at Rs5L+, exceeding the strongest signal ever measured in either project at any horizon. |

**Matches the user's summary exactly.** No discrepancy found.

### Study 3 -- fresh-data momentum-model retest (`trade-info`)

| field | value |
|---|---|
| Hypothesis | Same 26-feature LightGBM construction as Study 2, retrained on all pre-2024-07-01 data, evaluated on **fresh** (never-historically-existing) data from 2026-01-01 forward, `entity_id` excluded. |
| Universe | Study 2's own rank[200,600] band, no F&O restriction (amended from an earlier F&O-restricted formulation -- `STUDY_3_FO_REMOVAL_AMENDMENT_IMPLEMENTATION.md`). |
| Decision gate | IC>=0.018 AND fold-t>=2.0 AND long-only net spread>0 at 39bps -- all three required, frozen spec hash `6c8b9a47...`, verified unchanged. |
| Minimum sample | >=4 non-overlapping mature 63-trading-day periods, >=10 names/date. |
| Status, as of this document (verified this session, read-only) | **2 of 4** periods mature (`STUDY_3_FRESH_DATA_MONITOR.md` run #4, 2026-09-19: period 1 `2026-01-01..2026-04-07` MATURE, period 2 `2026-04-08..2026-07-09` MATURE, period 3 `2026-07-10` onward INCOMPLETE at 50/63 days). Monitor's own stated next action: wait ~6 more months. |
| Firewall status | Confirmed intact as of the monitor's own last check: no IC/prediction/portfolio/evaluation artifact found under any plausible naming; fresh rows pass every PIT-integrity check run. |

**Matches the user's summary exactly** ("only 2 of the required 4 mature periods exist"). No discrepancy found -- confirmed directly against the monitor document, not assumed from the user's framing.

---

## Phase 2: What does 63-day momentum actually capture?

Using development data only (no new backtest run for this section; every
number below is already published).

**A. Time-scale.** Medium-horizon continuation, not short-horizon. The
factor's own construction is a 12-month trailing, skip-1-month formation
window, evaluated at a 63-trading-day forward horizon. Two independent
pieces of development evidence bound this from the short end: (1)
`trade-info`'s own combined model, which had short-window (1d/5d) price
features available alongside the momentum-family ones, measured those
short features at **0.0% of total model gain** (`trade-info/DESIGN.md`,
Study 2 diagnostic #4) -- in a model that DID find real signal in the
63d/252d-family features, the 1-5 day features contributed nothing. (2)
`trade-info`'s own horizon-selection table (`DESIGN.md`, "Horizon
selection") shows edge/cost rising monotonically with horizon at a fixed
IC: 5d 0.35x, 10d 0.50x, 21d 0.73x, 42d 1.04x, 63d 1.31x, 126d 1.97x (post
corporate-actions-bug-fix figures). Short horizons are structurally the
worst place this data has to offer for a cost-surviving edge, independent
of any specific model or universe -- this is the same conclusion `trade-new`'s
own swing Phase 1 reached independently, using a different cost model and
universe (`SWING.md`: break-even at 5 days needs IC~=0.05, exceeding every
factor either project has ever measured).

**B. Cross-sectional character.** Purely relative/rank-based. The target
is cross-sectionally z-scored every date (Project 1); the factor itself is
a per-date decile rank, evaluated against an equal-weight benchmark of the
SAME eligible universe, never an absolute-return threshold (Project 2). No
development evidence anywhere in either project supports an
absolute-return or market-relative-only (vs. sector- or size-relative)
construction outperforming the plain cross-sectional-rank one -- none was
tested, so this is silent, not negative, evidence.

**C. Concentration.** Real, and replicated. Momentum's top decile
concentrates into a narrow set of sectors during crisis regimes --
Healthcare dominant at 26.3-35.3% share across three consecutive 2020
rebalances, reproduced independently in **both** the microcap whole-market
universe (Study 1) and the differently-constructed large-cap top-200
universe (Study 2) (`FINDINGS.md`, sector-concentration section). Part of
the magnitude gap between the two universes' concentration statistics
(HHI 0.129 vs 0.179) is a stated, unresolved confound of holding-count
(20 vs ~110-130 names) rather than a real difference in rotation
intensity -- flagged as such in the source document, not resolved here.
**This is the strongest, most-replicated concentration finding available**,
and it is the mechanism Phase 4's Hypothesis C below targets directly.

**D. Trend quality.** Only one trend-quality-adjacent property has been
directly measured (not assumed) in either project's own data:
**downside protection, not upside capture** -- momentum's Study 1 holdout
beat its benchmark in all 3 falling-market periods and lost in both
rising-market periods, with losses smaller than wins (`FINDINGS.md`
Section 3). No development-data evidence exists in either project on
persistence-of-trend, rising-volume, stable-volatility, distance-from-
moving-average, or acceleration as SEPARATE trend-quality subcomponents --
none of these was directly tested. **Stated plainly, per instruction: this
part of Phase 2.D is not supported by development data, not invented.**

---

## Phase 3: What the reversal failure tells us

Using only already-documented development-data evidence (no new holdout
touch, no new V1 variant run against the V1 holdout).

**Regime dependency**: `PREREGISTRATION_SWING_V1.md` Section 3 already
tested this directly, before the holdout was read -- nine observables
(POOL_ML's own return, cross-sectional 5-day dispersion, NIFTY return and
realized volatility, V1's own average dip magnitude, trade count,
candidates/day, unique entities selected, trades/entity), checked
individually across the 9 pre-holdout years. **None separated the two
failing years (2021, 2024) from the other seven cleanly enough to survive
an individual-year check** -- the one aggregate-looking gap (POOL_ML's own
heat) was directly falsified by a counter-example (2023's hotter pool
still passed; 2024's cooler pool still failed). Regime, as measured by
these nine variables, is not a usable, observable-in-advance predictor of
when this reversal effect works.

**Pullback depth**: the Top-N concentration sweep (`swing_v1_checks`
CHECK 1) tested this directly. Concentrating to the deepest 5, 10, or 20
dips per day did **not** increase expectancy relative to the uncapped
population (worst-case expectancy: Top5 0.280%, Top10 0.262%, Top20
0.235%, uncapped 0.364% -- monotonically *higher*, not lower, as the
population widens to include shallower dips). **Deeper pullback carrying
more reversal edge is not supported by development data; if anything the
relationship runs the other way.**

**Market breadth**: the regime filter (Nifty above its 50-day SMA) is
this project's own operationalization of market breadth. Adding it to the
dip condition alone made selection **worse**, not better: V3
(dip+regime) scored the 58.2nd percentile vs. V1 (dip alone)'s 100th
(`swing_phase3_decomposition`). Conditioning reversal on broad-market
uptrend, as measured here, does not help.

**Structurally strong vs. weak names, and whether the failure is
reversal-itself or the wrong universe**: this is answerable directly from
the decomposition's own V1-vs-V8 comparison, without touching the holdout
again. **V8** (the same dip condition, ranked and applied across the
FULL liquid universe, with NO momentum-top-decile restriction at all) also
cleared the 100th percentile pre-holdout (p=0.001), though at much lower
absolute expectancy than V1 (0.040-0.170% vs. 0.364-0.494%). **The
pre-holdout reversal measurement was not an artifact of restricting to
momentum winners specifically -- it appeared, at the same extreme
percentile, in two structurally different universes.** This weakens
"wrong universe" as the explanation for the eventual holdout failure and
strengthens the alternative already recorded in `SWING_FINDINGS.md`
Section 4: the reversal-persistence measurement itself, across the whole
pre-holdout sample, was fragile/period-specific -- a conclusion that lines
up exactly with Project 1's own, independently-derived and
placebo-validated finding that a **different** momentum-family
persistence statistic reversed sign between two multi-year windows of the
same underlying NSE market. Two independent codebases, two different
horizons (63 days and 5 days), two different mechanisms (continuation and
reversal), and the same underlying finding: **a cross-sectional
persistence statistic measured over one multi-year development window is
not guaranteed to hold in the next one, and neither project's own
pre-holdout diagnostics (however extensive) detected this in advance.**

**Liquidity**: not independently tested. POOL_ML always restricts to
high/mid liquidity tercile; no split by tercile within that restricted set
was run. Open, not resolved by existing development data.

---

## Phase 4: Candidate hypotheses (at most 3)

Generated from Phase 2/3's evidence above, not named in advance. Each
targets a **different** causal story; none is a parameter variant of
another.

### Hypothesis A: Momentum-persistence stability monitor -- two versions, not one

The single most-replicated Phase 2/3 finding is that momentum-family
persistence statistics are themselves regime-unstable, and this
instability was invisible to both projects' own extensive pre-holdout
diagnostics. Rather than searching for a new statistic that predicts
RETURNS (the thing three attempts across two projects have now failed
at), this hypothesis proposes measuring and logging the STABILITY of the
statistic momentum_12_1 already depends on. **"No holdout ever needed" is
only true for as long as the monitor never changes a position** -- split
explicitly, per instruction, into two versions that are NOT
interchangeable:

- **A-descriptive**: reports the persistence statistic, drives no
  decision. Makes no claim beyond "here is what this number has been
  doing." Needs no validation, because it asserts nothing falsifiable
  about the future.
- **A-actionable**: uses the statistic to reduce or pause momentum
  exposure. This DOES assert something (that degradation is detectable
  usefully before or during a drawdown) and DOES need validation -- Phase
  5/7 below state the two specific problems this version faces before any
  claim about it is trusted.

### Hypothesis B: Loss-avoidance portfolio construction

Study 1's validated mechanism is downside protection (Phase 2.D), not
upside capture -- but the current implementation captures this only
indirectly, as a side effect of concentrating in a narrow top-decile
winner portfolio (Phase 2.C's documented crash-vulnerability). A
distinct causal story: if the mechanism is really "avoid recent losers"
rather than "own recent winners," a broadly diversified portfolio that
simply excludes the bottom momentum decile (holding everything else,
equal-weight) should capture most of the downside protection at lower
concentration risk than the current construction.

### Hypothesis C: Fundamentals as a concentration/crash-risk filter on momentum

Phase 2.C's crash-vulnerability finding (sector concentration, replicated
in two universes) is momentum's clearest documented weakness.
`fundamental_screener.py` already exists, already measures cash-flow
quality, and its own docstring already states it is untested as a
modifier of momentum in either direction. Distinct causal story:
financially fragile "story" momentum names are more exposed to a sudden,
correlated re-rating when risk appetite shifts; screening them out before
selection should reduce concentration/crash exposure, independent of
whether it changes the return level.

### Stop Condition 6 flag, applied to all three

None of A, B, or C is a parameter variant of V1 or V4. All three operate
on `momentum_12_1` (a different, already-holdout-passed base signal, at
its own already-validated 63-day horizon), not on the 5-day dip/reversal
construction that produced V4's 9.8th percentile. **Flagged explicitly so
this is checked, not assumed**: B and C do add a *condition* on top of an
existing signal, the same shape as V4's "signal plus filters" -- the
distinction stated plainly is that V4 compounded conditions onto a signal
that had never passed anything, while B and C propose a risk/construction
modification to a signal that has already passed a real, sealed holdout
once. That distinction is real, but it does not exempt B or C from needing
their own validation before any claim is trusted -- Phase 7 below is
explicit that neither has one, at the return-level, within reachable time.

No fourth hypothesis was generated or considered.

---

## Phase 5: Specification of each candidate

### Hypothesis A -- Momentum-persistence stability monitor

- **Economic mechanism**: momentum's edge depends on trailing-return-rank
  persisting into forward-return-rank; this persistence is not a constant
  -- `trade-info/FINDINGS.md` Section 3 measured it at +0.0814 (SE 0.0029)
  in training and -0.0158 (SE 0.0062) in an 18-month holdout, a shift 300x
  a same-metric train-vs-train placebo (0.0003).
- **Market mechanism**: momentum's persistence is attributed in the
  literature to underreaction/slow diffusion among less-sophisticated
  participants; its periodic reversal ("momentum crash") to a buildup of
  one-sided positioning unwinding sharply on a regime shift -- both
  already-known phenomena, not new claims. This hypothesis claims only
  that the REGIME STATE is a measurable, trackable quantity, not that a
  new mechanism exists.
- **Observable prediction (A-descriptive)**: a rolling, point-in-time (no
  lookahead) cross-sectional persistence statistic, logged every
  rebalance, describes the same regime-instability Phase 2/3 already
  documented, going forward. It asserts nothing about the future and
  cannot fail a falsification test -- it either shows the same kind of
  regime variation history already shows, or it doesn't, and either way
  is a reportable finding, not a pass/fail claim.
- **Observable prediction (A-actionable)**: the SAME statistic should show
  detectable degradation before or during momentum's own worst-performing
  periods, with enough lead time to act on.
- **Falsification condition (A-actionable only)**: if a
  prospectively-logged statistic shows no detectable degradation before
  or during a subsequent momentum drawdown (the statistic stays flat
  while realized returns still fall), the claim is false -- the
  instability is only visible in hindsight and has no operational use.
- **Two problems A-actionable specifically faces, checked directly rather
  than assumed away**:
  - **LAG**: persistence at a 63-day horizon is only measurable 63 days
    after the fact (the forward return has to realize before the
    correlation can be computed). The monitor therefore detects a regime
    roughly a quarter late by construction. Its value as an ACTIONABLE
    signal depends on regimes typically outlasting that lag -- itself
    untested, and not verifiable from the same three-regime history
    below (three regimes give at most two transition events to learn a
    typical regime LENGTH from, not enough to establish a reliable "does
    a quarter's lag still leave useful time to act" answer).
  - **SAMPLE**: the event being predicted is a regime shift, and the data
    contains few of them. Measured directly for this document (not
    assumed), on trade-new's own pre-holdout history
    (`scripts/run_momentum_persistence_regime_count.py`, same
    methodology as `trade-info`'s own regime diagnostic -- per-date
    cross-sectional Spearman rank correlation of momentum_12_1 against
    the same date's forward-63-day return, averaged per calendar year,
    with a regime defined mechanically, before running, as a maximal
    contiguous run of same-signed annual means): **3 distinct regimes in
    8 pre-holdout years** (2017-2019 positive, 2020 negative, 2021-2024
    positive) -- 2 sign-change events total. This is **under the ~5
    regimes that would be needed for a credible read**, exactly the
    threshold stated in advance. **A-actionable therefore cannot be
    validated on history, and faces the identical fundamental power
    problem `FINDINGS.md` Section 12 already proved fatal for an
    incremental-modification return claim -- not a different, avoided
    problem, the same one, restated: too few independent instances of the
    thing being measured to distinguish a real effect from chance, no
    matter how the metric is framed.** The only additional evidence
    available is Project 1's own, independently-derived holdout
    observation (persistence went negative in a materially different
    universe/codebase, 2024-07 through 2025-12) -- directionally
    consistent, but one more data point does not change a 2-transition
    sample into a validatable one.
- **Expected horizon and why**: momentum_12_1's own existing 63-day
  rebalance cadence -- this is not a new horizon, it is instrumentation
  layered on an existing one.
- **Expected costs and why the edge should survive**: A-descriptive
  generates no trades of its own, ever. A-actionable, if it were ever
  built despite the sample problem above, could only ever REDUCE trading
  relative to the base strategy (scale down, never add new positions), so
  it cannot make costs worse -- stated for completeness, not as a reason
  to build it now.
- **Universe and why**: identical to momentum_12_1's own validated
  universe(s) (Study 1 whole-market or Study 2 large-cap) -- reused, not
  redefined.
- **Entry/exit**: none of its own; A-actionable would modulate exposure to
  the existing strategy's own entries/exits, if built.
- **Position sizing**: N/A for A-descriptive. For A-actionable, were it
  ever pursued despite the sample problem: a pre-committed scaling rule
  keyed to the persistence statistic crossing a threshold fixed from its
  own DEVELOPMENT-period historical range -- never fit to the forward
  monitoring period's own results.
- **Required data**: none beyond what both projects already have
  (existing momentum_12_1/`ret_63d` panels in both codebases). Can be run
  in parallel on both independently-constructed universes as a built-in
  replication check.

### Hypothesis B -- Loss-avoidance portfolio construction

- **Economic mechanism**: if downside protection is driven by the bottom
  decile's own underperformance (distress, forced selling, downgrades)
  rather than the top decile's own outperformance, a broad-minus-bottom-
  decile construction should recover most of the protection with less
  concentration.
- **Market mechanism**: distressed/deteriorating names are sold by
  participants for reasons largely independent of price momentum itself
  (margin calls, index removal, credit downgrades) -- a different,
  plausibly more durable mechanism than crowd-driven continuation in the
  winners, which is exactly the mechanism Project 1 found to be
  regime-fragile.
- **Observable prediction**: a decile-level decomposition of momentum's
  own already-computed historical returns should show the bottom decile's
  underperformance versus the equal-weight benchmark exceeding the top
  decile's own outperformance.
- **Falsification condition**: if the top decile drives most of the
  historical margin (not the bottom decile), or a broad-minus-bottom-
  decile construction shows no concentration improvement over the current
  one, drop it -- decided at the development stage, no holdout needed.
- **Expected horizon and why**: momentum_12_1's own 63-day cadence --
  same factor, same horizon, different portfolio construction.
- **Expected costs**: broader (more names) but likely proportionally
  more total turnover per rebalance than the narrow top-decile
  construction -- net effect not assumed, to be measured directly at the
  development stage.
- **Universe and why**: identical to momentum_12_1's existing universe(s).
- **Entry/exit**: same 63-day rebalance mechanics; weights differ
  (broad ex-bottom-decile vs. top-decile-only).
- **Position sizing**: equal-weight across the broader set, mirroring the
  existing benchmark's own convention -- no new discretion introduced.
- **Required data**: entirely already available (existing decile return
  series from Study 1/2's own construction).

### Hypothesis C -- Fundamentals as a concentration/crash-risk filter on momentum

- **Economic mechanism**: financially fragile companies riding a
  momentum wave are a "story" trade, more exposed to a sudden re-rating
  than cash-flow-sound ones; screening them out before selection should
  reduce the crash/rotation exposure Phase 2.C documents, independent of
  return level.
- **Market mechanism**: a quality/momentum interaction already documented
  in the broader literature -- fragile-but-trending names are
  disproportionately liquidated in a risk-off shift, concentrating any
  momentum portfolio's crash exposure in exactly the names a cash-flow
  screen would remove.
- **Observable prediction**: applying `fundamental_screener.py`'s
  existing checks to momentum's own historical top-decile membership,
  at each historical rebalance, point-in-time, should reduce sector/HHI
  concentration relative to the unfiltered top decile, without requiring
  any return-level claim.
- **Falsification condition**: if applying the screener does not reduce
  concentration/HHI or does not reduce single-sector dominance in the
  2020-style episode, the risk-reduction story is not supported -- a
  cheap, development-only, holdout-free check.
- **Expected horizon/costs/universe/entry-exit/sizing**: identical to
  momentum_12_1's own already-validated construction, with the screener
  as an additional point-in-time exclusion filter before top-decile
  selection.
- **Required data, and what is missing**: `fundamental_screener.py`
  currently evaluates a CURRENT, as-of-today verdict only
  (`load_current_price_panel`, `compute_liquidity_tercile`) -- **the same
  point-in-time historical gap already flagged as BUGS.md Bug #12**,
  which blocked the swing decomposition's V5/V6 variants for the same
  reason. This hypothesis requires the same missing infrastructure: a
  point-in-time-correct historical version of the screener's checks,
  evaluable at every historical momentum-rebalance date across the
  sample -- not built, not started, flagged here for the second time.

---

## Phase 6: Multiple-testing control

No parameter is fixed at the numeric level in this document -- doing so
now, before any development-stage analysis exists to set it against, would
itself be the kind of post-hoc tuning this project's own discipline
exists to prevent. What is fixed here is the **rule** each future
parameter must be set by:

- Any threshold (e.g., A-actionable's persistence-degradation trigger, if
  it is ever built despite Phase 5/7's stated sample problem)
  must be derived from the DEVELOPMENT-period distribution of the
  statistic it applies to, computed before any forward or holdout data
  relevant to the decision exists, and stated in a frozen document before
  the parameter is used to make a decision -- the same discipline
  `PREREGISTRATION_SWING_V1.md` Section 6 already applied to its own power
  calculation (std measured, target and t-threshold fixed independently
  of it).
- Any structural (development-only) check -- Hypothesis B's decile
  decomposition, Hypothesis C's concentration-reduction check -- must be
  run and its outcome recorded BEFORE any return-level claim is made
  about the same hypothesis, exactly as Phase 5's falsification
  conditions state, so a negative structural result closes the hypothesis
  before it ever reaches a stage that could consume validation resources.
- If more than one hypothesis survives its own development-stage
  falsification check and is carried forward to a real validation attempt,
  that is a family of trials requiring its own multiple-comparisons
  correction, decided when and if it happens -- not assumed away now, the
  same standing note `PREREGISTRATION_SWING.md` Procedure item 4 already
  used.

---

## Phase 7: Development vs. validation, per candidate

| candidate | development-stage check (no holdout needed) | clean validation path for a return-level or risk-reduction claim |
|---|---|---|
| A-descriptive | Compute the persistence statistic historically (already done for this document: 3 mechanical regimes, 8 pre-holdout years). | **None needed.** It asserts nothing about the future, so there is nothing to validate -- reportable as understanding, never as a result. |
| A-actionable | Same computation, used to characterize whether degradation historically preceded drawdowns. | **Forward-only, and long.** Not a holdout-consuming claim at all -- it is a descriptive log, validated by whether it shows degradation before/during a FUTURE momentum drawdown. No existing holdout is spent. **But the sample problem is severe, not a minor caveat**: only 3 mechanical regimes exist in 8 pre-holdout years (2 transitions), under the ~5 needed for a credible read, fixed as the threshold before this was computed. This is the same fundamental power problem `FINDINGS.md` Section 12 already proved fatal for a different incremental claim, not a version of Hypothesis A that avoids it. Validating a rare-event leading indicator at this event rate may take a full further market cycle or more, not months. |
| B: loss-avoidance construction | Decile decomposition of already-existing historical returns (cheap, immediate, no holdout touch). | **No reachable clean validation path for a return-level claim.** This is an incremental modification of an already-working strategy -- `FINDINGS.md` Section 12's own power analysis (8-72 years for a comparable incremental claim) applies with full force here, for the identical statistical reason (the binding constraint is the variance of the difference, not the effect size). The only claim this hypothesis can honestly support is the STRUCTURAL one (concentration/HHI reduction), which is measurable immediately and does not require years of forward return data. Stated explicitly: if pursued past the development check, it is pursued as a risk-construction change, never presented as a validated return improvement. |
| C: fundamentals risk filter | Requires building the missing point-in-time historical screener first (real, scoped, not yet started -- Bug #12). Once built: concentration/HHI check on already-existing historical rebalance dates, no holdout touch. | Same constraint as B, for the same reason -- a return-level claim is not reachable at any practical horizon. The structural (concentration-reduction) claim is the only one with a clean, fast validation path, and only after the missing infrastructure is built. |

**No candidate here requires touching the V1 holdout beyond what is
already documented, requires a new V1 variant run against the V1 holdout,
requires touching Study 3's fresh data with model inference, or requires
consuming a holdout another experiment already used.** Stop Conditions
1-4 are clear on all three.

---

## Phase 8: What we are optimizing for

Robustness, economic plausibility, and stability across regimes --
explicitly not the parameter combination producing the highest historical
percentile. The single most direct evidence for why this ordering matters
is already in hand, not hypothetical: **V1 cleared a Bonferroni- and
BH-corrected 100th percentile on 65,219 pre-holdout trades and still
failed out of sample.** A large sample, a formally corrected significance
threshold, and a stated, plausible mechanism were all present, and none of
it substituted for genuine out-of-sample evidence (`SWING_FINDINGS.md`
Section 5). Every candidate above is deliberately structured so that its
FIRST checkpoint is a structural or mechanistic one (Phase 5's
falsification conditions), not a backtested return number -- a modest,
structurally-grounded result that survives its own falsification check is
worth more here than a high in-sample number with no such check.

---

## Phase 9: Architecture

**No evidence in the three documented failures supports splitting the
system into signal/setup/risk/portfolio/execution layers, so none is
proposed.** Checked directly against each failure, not assumed:

- **Project 1** (ML price/volume): failure was the core predictive
  statistic reversing sign out of sample -- a signal-generalization
  problem. The bugs found alongside it (`entity_id` leakage, cost-model
  overstatement, a decile-metrics computation error) were data/
  methodology defects, not failures of missing architectural separation.
- **Swing V4**: failure was that *compounding conditions onto the signal
  itself* made a better base signal worse. This is evidence about signal
  design, not about needing a formally separated "setup" layer -- the fix
  that worked was removing the added conditions, found by decomposition,
  not by consulting a layered system.
- **Swing V1**: failure was the selection signal's own out-of-sample
  non-replication. Position sizing (Top-10 concentration) and portfolio-
  level capital constraints were handled adequately with simple, ad hoc
  rules every time they were exercised (5.4x capital reduction at a
  measured 0.10-point expectancy cost) -- no evidence these needed a
  formal portfolio layer to work correctly. Entry/exit mechanics
  (next-day open, fixed hold) were never implicated in any failure.

**All three documented failures are signals that did not generalize, not
execution, sizing, or portfolio-construction problems.** A formal
signal/setup/risk/portfolio/execution architecture would not have
prevented any of them -- that split organizes implementation concerns, and
the concern that actually broke three times (does a measured cross-
sectional statistic hold beyond the window it was measured on) sits
outside all five of those layers. Not proposed; moving on, per instruction.

---

## Phase 10: Fundamentals

Not forced into return prediction, per instruction -- and this project's
own existing code already reflects that discipline independently: the
docstring of `fundamental_screener.py` states plainly it is "an untested
modification to momentum_12_1," never validated as a return predictor in
either direction, and structured from the start as a pass/fail exclusion,
never a ranking input (`PREREGISTRATION_SWING.md`'s own Universe item 5
used it the same way, though never actually applied -- Bug #12).
Hypothesis C above is the direct continuation of that existing,
already-correctly-scoped role: fundamentals as a quality/risk/distress
filter and universe constraint, evaluated on whether it reduces measured
concentration/crash exposure, never on whether it improves a return
number. No other fundamentals-based hypothesis is proposed here --
Phase 2's Section 12 finding (combination untestable, 8-72 years) already
rules out a *combination-with-momentum-for-return* framing on its own
terms, and nothing in this session's audit found a reason to revisit that
conclusion.

---

## Phase 11: Deliverable summary

### 1. Existing evidence

See Phase 1's audit table in full above. Three prior attempts (Project 1's
ML model, swing V4, swing V1) each cleared meaningful in-sample or
CV-stage bars and each failed the one test that mattered (a sealed
holdout, or a matched-random-null percentile test on genuinely
out-of-sample data). Two already-working results exist: `momentum_12_1`
(holdout-passed, replicated in two universes) and the ground-truth cost
measurement methodology both projects now share.

### 2. What we have learned

Momentum's real, validated mechanism is medium-horizon (63-252 day),
cross-sectional, rank-based downside protection -- not a short-horizon
signal and not upside capture. Short-horizon (1-5 day) price signals have
now failed, or shown zero standalone predictive value, in every
construction either project has tried. The single most important,
doubly-replicated finding is that momentum-family cross-sectional
persistence statistics are themselves regime-unstable in ways neither
project's own extensive pre-holdout diagnostics detected in advance --
this is the mechanism both Project 1's sign reversal and swing V1's
holdout failure share, at two different horizons, in two independent
codebases. Testing an incremental modification of an already-working
strategy is bounded by the variance of the difference, not the size of
the improvement, and this bound (8-72 years, `FINDINGS.md` Section 12) is
severe enough to rule out return-level validation for any of the
momentum-modification hypotheses this document proposes -- structural
(non-return) claims are the only ones left reachable.

### 3. What we must not do

- Retune V1, change any of its parameters, rerun any variant against the
  V1 holdout, or use its holdout performance to select a new strategy, or
  reinterpret its 61.4th-percentile result as a success.
- Touch Study 3's fresh data with model inference before its own 4-period
  maturity gate is met (currently 2 of 4).
- Treat a CV-stage or development-stage pass, on any future hypothesis,
  as a finding rather than a candidate -- both Project 1 and swing V1
  cleared strong-looking in-sample bars and both still failed
  out-of-sample.
- Claim a return-level improvement for Hypothesis B or C validated on any
  timeframe shorter than the decades `FINDINGS.md` Section 12 already
  measured as necessary for a comparable incremental claim.
- Spend the one remaining project-wide holdout slot on another
  short-horizon variant.

### 4. Candidate hypotheses

A (stability monitor), B (loss-avoidance construction), C (fundamentals
risk filter) -- full specification in Phase 5.

### 5. Recommended hypothesis

**Hypothesis A-descriptive, specifically -- not A-actionable.**
A-descriptive is recommended because it is the most directly justified by
the strongest, most-replicated finding in Phase 2/3 (regime-instability of
momentum-family persistence statistics, confirmed independently in two
codebases at two different horizons -- Phase 3's V1/V8 cross-universe
result remains the single strongest conclusion in this document: two
structurally different universes, V1 within momentum winners and V8
across the full market, both cleared the 100th percentile pre-holdout,
both failed to establish a real edge, pointing straight at the
persistence measurement itself rather than at either universe choice, and
matching Project 1's own placebo-validated sign-reversal finding
independently). A-descriptive **produces understanding, not returns** --
it asserts nothing about the future, so it needs no validation and cannot
fail one. It does not compete with Value/Quality/Size or the
`trailing_vol_252`/`beta_252` retest for the one remaining project-wide
holdout slot (it needs none, ever), and it can begin immediately on
already-available data with no new infrastructure.

**A-actionable is explicitly NOT recommended at this time.** Measured
directly for this document: only 3 mechanical persistence regimes exist
across 8 pre-holdout years (2 sign-change transitions), under the ~5
needed for a credible read. A-actionable's validation path, if pursued
anyway, has to be forward and long -- plausibly a full further market
cycle or more, since the thing being validated is the rate and lead-time
of rare regime transitions, and the data contains very few of them. This
is stated as the honest reason to build A-descriptive only for now, not
as a reason to abandon A-actionable permanently -- it becomes reachable
once more regime history (forward or, in principle, from a longer
historical panel) exists.

B and C are recorded as viable, lower-priority development-stage checks --
cheap, holdout-free, and worth running opportunistically -- but neither
currently has a reachable path to a validated return-level claim, stated
honestly rather than glossed over.

### 6. Exact specification for the chosen hypothesis

A-descriptive: compute a rolling, point-in-time cross-sectional
persistence statistic (trailing-return-rank vs. realized-forward-return-
rank, `trade-info`'s own already-built methodology, replicated for this
document in `scripts/run_momentum_persistence_regime_count.py`) on
momentum_12_1's own existing universe(s), every 63-day rebalance, logged
prospectively with no lookahead. **No trades, no exposure decision, no
threshold, no claim of any kind about the future.** It is a monitoring
log, full stop -- A-actionable's threshold-setting and exposure-scaling
design (Phase 5) is recorded for later, explicitly not specified as part
of this recommendation, since Section 5 above declines to pursue it now.

### 7. Data requirements, including what is missing

Nothing is missing for A-descriptive. Both projects already compute the
underlying momentum_12_1/`ret_63d` panels this hypothesis reads from, and
this document's own regime-count script is the reference implementation.
For A-actionable, what is missing is not data but SAMPLE: more distinct
persistence regimes than the 3 currently on record, reachable only by
waiting (forward) or, if ever revisited, by extending the historical
panel further back than either project's data currently allows.
(Hypotheses B and C's own missing-data items -- decile-level historical
returns already exist for B; a point-in-time historical fundamentals
screener does not yet exist for C, Bug #12 -- are recorded in Phase 5/7
for whenever either is picked up.)

### 8. Experiment design that contaminates no existing holdout

A-descriptive computes and logs a statistic on data both projects already
have unrestricted, non-holdout access to (the statistic's own
historical/development range, computed in full for this document) and,
going forward, on data that does not yet exist. It makes no claim
requiring a sealed holdout at any point in its design -- there is nothing
to contaminate. A-actionable is not being pursued now, so this question
does not arise for it yet.

### 9. Expected failure modes

For A-descriptive: none in the falsifiable sense -- it is a log, not a
claim. Its only failure mode is becoming a maintenance burden nobody
reads, which is an operational risk, not a research one.

For A-actionable, recorded for when the sample problem above is
revisited: the persistence statistic may degrade only in hindsight, with
no practically usable lead time before a momentum drawdown (the LAG
problem, Phase 5) -- in which case the hypothesis is falsified and
retired as an early-warning tool, though it would still stand as
confirmed, retrospective mechanism documentation. Separately, and
regardless of the lag question: with only 3 regimes on record, a
genuinely conclusive forward test requires observing enough further
transitions to reach a credible sample, which at the historical rate (2
transitions in 8 years) could take a decade or more -- stated as the
severe, not-glossed-over reason this version is not recommended now.

### 10. Explicit statement

V1 is untouched: no parameter changed, no variant rerun against its
holdout, its 61.4th-percentile result not reinterpreted. Project 1 and
Project 2 (momentum_12_1's own holdout pass) are untouched: no
retraining, no re-evaluation, no reuse of either project's spent holdout.
Study 3 is frozen, and its fresh data (2026-01-01 through 2026-09-18,
431,945 rows) has not been touched by model inference anywhere in this
document -- every number about it above was read directly from
`STUDY_3_FRESH_DATA_MONITOR.md`'s own already-published, read-only
monitor output, not recomputed.

---

## Stop conditions -- final check against this document

1. Needs V1 holdout performance beyond what is documented? No.
2. Needs a new V1 variant run on the V1 holdout? No.
3. Needs Study 3 fresh data touched by the model? No.
4. Needs consuming a holdout another experiment already used? No -- the
   recommended hypothesis needs none; B/C's structural checks need none;
   B/C's return-level claims are stated as unreachable, not attempted.
5. Repository lacks enough information for a clean development/validation
   split? No -- Phase 7's table states a path (or its absence) for each
   candidate explicitly.
6. An apparently new hypothesis is a renamed V1 or V4 parameter variant?
   No -- checked explicitly in Phase 4; all three operate on
   `momentum_12_1`, a different, already-holdout-passed base signal at
   its own already-validated horizon.

None triggered. This document is a design artifact only -- no code was
written to implement any hypothesis, no parameter sweep was run, no
holdout was touched.
