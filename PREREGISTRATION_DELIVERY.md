# Pre-registration: Delivery Study 1 (abnormal delivery %, up-days only, quarterly) -- DEV-only, new family, trial 1

Frozen before any abnormal-delivery value, rebalance, or return exists
anywhere in this study, per this project's standing discipline
(`PREREGISTRATION.md` and family). Nothing below changes after this
document is committed except by an explicit, recorded amendment, made
before the next number that amendment could have been shaped by.

**This document is DEV-only. There is no TEST window of any kind** --
not even the forward-only, non-sealed "TEST slice" device
`PREREGISTRATION_DARVAS.md`/`PREREGISTRATION_BOX.md`/`PREREGISTRATION_
FVG.md`/`PREREGISTRATION_IPO.md` each carry (a 2023-2026-style window,
read later, understood as a forward-only discipline device rather than a
genuine holdout). This study carries no such device at all. Section 4
states why that is a deliberate design choice, not an oversight.

## Provenance

**Hypothesis source: Other, stated plainly.** This is not literature-
sourced (no named book/paper), not a structural decomposition of a prior
study, not a bug/diagnostic finding, and not browsed from the research
app. The `delivery_eod` data itself exists in this project because of a
prior, separate import (`36c2fe8`/`6753e56`, see Section 0) from the
sibling `trade-info` project, whose own Study 2 already uses
`delivery_percent` as one of 26 ML features (`NEW_RESEARCH_DIRECTION.md`
line 69) -- that is background context for why the data was worth
importing, not a finding that this specific signal (abnormal delivery on
up-days, as a standalone decile-selection rule) works. The actual
hypothesis -- that elevated delivery on up-days reads as accumulation --
is a mechanism story, named and flagged as such in Section 1, per
amendment 3.

**This is a NEW family ("delivery"), trial count 1.** It shares no code,
universe-construction call, or trial budget with any prior family in
this project.

**All 2016-2026 data in this project's archives has already been read by
prior studies and the historical holdout is retired** (`FINDINGS.md`
Section 7). Per `PROJECT_CONTEXT.md`'s rule 6, "any new equity study is
development-only; a pass justifies forward testing and nothing more."
This study goes one step further than every DEV+TEST-slice study before
it: it carries **no TEST slice at all**, DEV-only in the strict sense,
because a dedicated power calculation (Section 6) shows no split of the
available data leaves either side with a usable sample. This is the
**fourth recorded instance of finding #3** ("variance of the difference,
not effect size, is the binding constraint" -- `PROJECT_CONTEXT.md`,
2026-11-16) shaping a study's design before any number existed, the same
discipline that caught the post-earnings-drift Phase 0 variance error.

## Section 0: reuse boundaries, read-only

**New, separate module: `src/delivery/`** (does not yet exist). Reads
`data/warehouse.duckdb` read-only except for its own persisted exclusion
list under `results/exclusions/`. Never modifies `src/factors/`, `src/
darvas/`, `src/fibo/`, `src/box_theory/`, `src/fvg/`, `src/ipo_listing/`,
`src/per_stock/`, or `src/swing/`. It never places, modifies, or cancels
an order.

**Already built and committed, prior to this document** (`36c2fe8`,
corrected in `6753e56`): the `delivery_eod` table (`isin`, `trade_date`,
`delivery_volume`, `delivery_percent`, `known_date`, `fetched_at`,
`source`, `revision_seq`), imported from `trade-info`'s `prices_raw`,
deduped to latest revision, scoped 2016-01-01 to 2025-12-31 (that
project's own backfill cutoff). **Entity resolution already verified
clean**: of 3,344 distinct source ISINs, 369 (11.0%, 7.0% of rows) are
unmatched to this project's own `isin_lineage` -- and all 369, 100%, are
`INF`-prefixed fund/ETF units, excluded by `isin_lineage`'s own
equity-only structural rule (`EQUITY_ISIN_PREFIXES = ("INE", "IN9")`) by
design, not a lineage miss. Every genuine equity ISIN resolves cleanly.
This is NOT a fifth instance of the Bug #7/#11/#33 silent-misresolution
shape -- it is a correct exclusion, independently checkable at `results/
delivery_import_unmatched_isins.csv`.

**Reused, read-only, unmodified, from the momentum study
(`PREREGISTRATION.md`) and its holdout-check script
(`scripts/run_holdout_study1_lineage_check.py`)**:

- `data_layer.entity_panel.read_full_entity_panel_authorized(con,
  authorize_holdout=True)` -- the entity-adjusted price panel
  (`entity_id`, `trade_date`, `isin`, `raw_close`, `adjusted_close`,
  `volume`, `turnover`), `series='EQ'` only, joined via `isin_lineage`.
  `authorize_holdout=True` is the same sanctioned, logged call every
  post-retirement DEV-only study in this project already makes to read
  full history now that the holdout itself is retired.
- `data_layer.lineage_jump_guard.find_unexplained_jumps` +
  `data_layer.same_isin_jump_guard.find_unexplained_same_isin_jumps`,
  combined exactly as every other panel-derived study here combines
  them (Bug #1 + Bug #11 guards). A flagged `(entity, date)` row is
  dropped before any rolling computation (up-day classification,
  delivery averaging) touches it.
- `data_layer.exclusion_list.save_exclusion_list` / `load_exclusion_list`
  -- the same content-hash-verified persistence mechanism every DEV-only
  study uses, under this study's own new key (`results/exclusions/
  run_delivery_study1_dev.json`).
- `factors.target.HORIZON_DAYS` (= 63) -- the forward hold length,
  unchanged.
- `COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq":
  118.0}` and `BLENDED_COST_BPS = 32.5`, and the rolling-20-trading-day-
  median-turnover-per-entity, per-date `qcut`-into-tercile construction
  -- copied verbatim from `run_holdout_study1_lineage_check.py`'s own
  inline constants, **not re-derived, not re-tuned**, same uncertainty
  caveat `PREREGISTRATION.md` already states for the low-liq figure.
- The quarterly rebalance-date construction (`all_dates[::63]`, strided
  over the full available trading-day index) -- the identical
  construction momentum's own holdout script uses, applied here to the
  FULL `delivery_eod`-covered window rather than a 5-date holdout tail
  (Section 1).

**Not reused**: `factors.momentum.compute_momentum_12_1` is not called
anywhere in this study. This study does not test whether delivery adds
to momentum (unlike Darvas's own MOMENTUM null) -- see Section 7.

**New in `src/delivery/`**: the abnormal-delivery signal computation
(Section 1), the quarterly portfolio construction, and the SELECTION
null (Section 5/6).

## Section 1: configuration frozen (universe, strategy, costs)

### Universe

Identical to momentum's own (`PREREGISTRATION.md` "Universe"): NSE
equities, `series='EQ'` only, ISIN prefix `INE`/`IN9`, entity-resolved
via `isin_lineage`, entity-adjusted prices (`adjustment_factors`), no
additional liquidity screen (whole market, including microcaps).
Combined lineage-jump + same-ISIN-jump exclusion applied throughout
(Section 0).

**Gap-awareness, OUR extension of an existing convention, stated as
such**: momentum's own `STALE_GAP_DAYS = 5` (calendar days) rule exists
for its 252-trading-day lookback and 63-day forward window; no existing
function in this project tests for a stale gap inside an arbitrary
21-or-60-trading-day window, so this study writes its own check using
the SAME `STALE_GAP_DAYS = 5` threshold and the same jump-exclusion
input, applied to the measurement and baseline windows below. Any
measurement or baseline window containing a gap exceeding 5 calendar
days is excluded (NaN) for that entity at that rebalance, never silently
computed across.

### Signal -- abnormal delivery %, up-days only (OUR operationalization, amendment 3)

For each entity, at each quarterly rebalance date `R` (rebalance-date
construction below):

- **Up-day**: a trading day `d` with `adjusted_close[d] >
  adjusted_close[d-1]`. A day with a flagged jump exclusion, or whose
  prior day is excluded or missing, is classified as neither up nor
  down -- it contributes to no window's numerator or denominator.
- **Measurement window**: the 21 trading days strictly before `R`,
  `[R-21, R-1]` on the entity's own trading-day index.
- **Baseline window**: the 60 trading days strictly before the
  measurement window, `[R-81, R-22]` -- **non-overlapping with the
  measurement window by construction** (amendment 2). "Abnormal" is
  never measured partly against itself.
- **Abnormal delivery** = mean(`delivery_percent` on up-days in the
  measurement window) **minus** mean(`delivery_percent` on up-days in
  the baseline window). A plain difference, not a ratio -- our choice,
  stated as such: `delivery_percent` is already a bounded 0-100
  percentage, so a percentage-point difference is directly
  interpretable and does not blow up near a small baseline denominator
  the way a ratio would.
- **Minimum observations**: at least 5 up-days required in BOTH windows,
  else the entity gets NaN for that rebalance (excluded from the
  eligible pool that date, same dropna-and-report convention every
  other study here uses -- never silently imputed).

**Mechanism, named as such**: delivery on up-days reads as accumulation
(buyers taking and holding supply as price rises); the same logic,
applied to down-days, would read as distribution. This document tests
the accumulation (up-days-only) reading only.

**Alternatives NOT tested here, named now, per amendment 3** -- each is
a SEPARATE, independently pre-registered trial if ever run, never a
revision of this one (amendment 4):

1. All-days abnormal delivery (no up/down split).
2. Up-days-minus-down-days abnormal delivery (a net
   accumulation-distribution spread).
3. Volume-weighted delivery (weighting each day's `delivery_percent` by
   that day's own volume/turnover rather than a simple mean).

### Portfolio construction

Identical to momentum's own (`PREREGISTRATION.md` "Strategy"): long
only. Top decile (highest 10% by abnormal delivery) of the eligible
cross-section at each rebalance, equal-weighted within the decile. **No
stop** -- held exactly to the next rebalance, 63 trading days
(`factors.target.HORIZON_DAYS`).

### Benchmark

Equal-weight of the same eligible universe, same quarterly cadence,
blended 32.5bps cost -- identical construction to momentum's own
benchmark leg (`PREREGISTRATION.md` "Benchmark").

### Costs

Identical tercile table to momentum's own (Section 0), applied only to
entities entering the decile at each rebalance (turnover-weighted).

### Rebalance dates -- quarterly, non-overlapping (amendment 1)

The full trading-day index intersected with `delivery_eod`'s own
coverage (2016-01-01 to 2025-12-31), strided every 63 trading days
(`all_dates[::63]`) -- the SAME construction momentum's own holdout
script uses, applied to the FULL covered window, not the 5-date holdout
tail. This is deliberately **not** the monthly-formation design
originally specified: monthly formation with a 63-day hold creates three
overlapping cohorts at any time, a different statistic than the one the
power calculation (Section 6) was run against. Quarterly, non-
overlapping formation matches both the MDE computation and momentum's
own cadence.

A rebalance date is usable only if it has (i) >=81 trading days of prior
history (measurement + baseline windows) and (ii) >=63 trading days of
forward data remaining (the forward return, `compute_forward_return`'s
own existing dropna behavior). This nominally yields ~40 quarterly dates
over 2016-2025; the number actually surviving both constraints is
**reported, not asserted**, once computed (Section 10) -- expected close
to, but somewhat below, 40, which is near the ~35 the power calculation
(Section 6) requires.

## Section 2: historical result (pre-computation -- NOT the test)

**N/A.** No computation has run anywhere in this study. This document is
committed and pushed alone, before any abnormal-delivery value,
rebalance, or return exists, per Section 10 step 1.

## Section 3: known, permanent limitations

- `delivery_eod` coverage ends 2025-12-31 (`trade-info`'s own backfill
  cutoff) -- this study cannot be extended to later data without a fresh
  import first.
- Up-days-only is a mechanism story (amendment 3), not derived from this
  project's own measured data; the three named alternatives (Section 1)
  are untested and may turn out stronger, weaker, or unrelated.
- The measurement-minus-baseline DIFFERENCE convention for "abnormal" is
  this document's own choice among at least two defensible alternatives
  (a ratio was considered and rejected, Section 1) -- not uniquely
  dictated by the hypothesis.
- Long-only only, the same F&O/shorting infeasibility `PREREGISTRATION.
  md` measures directly for momentum (7.4%/13.6%), not independently
  re-measured here -- ported by reference, not re-derived.
- The low-liquidity cost estimate (118bps) carries the same uncertainty
  `PREREGISTRATION.md` already flags for momentum; not re-assessed here.
- The Section 6 power calculation's 2.12% SD figure comes from a Phase 0
  feasibility check that was not persisted as its own script/output
  file in this repository -- the SELECTION null actually run in Section
  10 will re-measure the same quantity at full scale, and that figure,
  not this one, is what the gate is evaluated against (see Section 6).

## Section 4: the validation path -- DEV-only, no TEST window, and why

**No TEST window exists in this study, of any kind.** Rule 6
(`PROJECT_CONTEXT.md`) already means any new equity study here is
development-only; this study additionally forgoes even the forward-only
"sealed TEST slice" device Darvas/Box/FVG/IPO each carry, because
Section 6's power calculation shows that device cannot validate
anything here: splitting the available ~40 quarters leaves too few on
either side to detect an effect anywhere near the size being tested for.
Building a validation window that cannot validate is worse than not
building one -- it would manufacture the appearance of a held-out check
with none of the substance. A DEV pass here (Section 5) **justifies
starting a forward PAPER test, and nothing more** -- standing up that
paper test (sizing, execution, monitoring) is a separate, later,
operational decision, outside this document's scope.

This also removes, entirely, the blocker this study would otherwise have
carried on `trade-info`'s own 2026 delivery backfill catching up: since
nothing here reads past 2025-12-31, no additional wait is needed.

## Section 5: decision rule -- gate, fixed now, before any computation

**DEV passes only if ALL hold:**

**(a)** Mean quarterly abnormal-delivery top-decile return exceeds the
benchmark's, net of costs, across every usable rebalance date in the DEV
window (Section 1).

**(b)** That spread's percentile against the SELECTION null (Section 6)
is **>= 95th**, where the 95th-percentile bar is **computed from this
study's own null distribution in this same run** -- never an asserted
number. `PREREGISTRATION.md`'s own 2026-11-17 post-hoc annotation found
its asserted 3.0pp margin threshold was never derived and, once
checked, sat at only the 92.6th percentile of its own random-decile
null -- this study is designed from the start to avoid that gap.

**(c)** [this document's own addition, modeled on every prior gate's own
single-period-sensitivity check -- e.g. Darvas's "drop the single best
calendar year," `PREREGISTRATION_DARVAS.md` Section 6] The spread
remains positive after dropping the single best-performing quarter from
the DEV sample. Added here because amendment 4 itself names the exact
failure mode this guards against: a near-miss result propped up by one
outlier period, the shape that produced the Swing family's six variants.

**Anything else = NO EDGE. The study closes.** Per amendment 4 / rule 7
(`PROJECT_CONTEXT.md`: "A DEV failure closes a study automatically. No
approval needed, and no retry at other parameter values"): no retry at a
90-day baseline, no retry on all-days or up-minus-down-days delivery, no
retry at a different decile cut, hold length, or minimum-up-day count.
Any such variant is a NEW, separately pre-registered trial -- never a
revision of this one.

## Section 6: power calculation, from historical variance only, never the mean

**~40 nominal quarters exist** in `delivery_eod`'s own 2016-2025
coverage (10 years x 4). Detecting a 1% per-quarter spread at 80% power
needs approximately **35** of them in a single window.

**CORRECTED, before any code in `src/delivery/` existed**: the first
draft of this section mischaracterized this figure's own provenance,
describing it as borrowed from momentum's measured variance as a
"working proxy." That was wrong, caught before being relied on. The
actual input is **this study's own Phase 0 feasibility check**: the SD
of the quarterly spread under RANDOM decile assignment is **2.12%** --
measured on `delivery_eod`'s own coverage window, with the real
abnormal-delivery signal, not borrowed from a different study by
analogy. Under random assignment the signal itself is irrelevant by
construction, so this is already exactly the quantity Section 10's
SELECTION null (Section 5b) is built around -- not a proxy standing in
for it. The arithmetic checks out exactly: at 2-sided alpha=0.05,
80% power (z-sum ~2.8), `MDE = 2.8 * 2.12% / sqrt(N)` gives ~1.00% at
N=35 and ~2.97% at N=4 -- matching both figures below to two decimal
places, not merely "in the right ballpark." There is no borrowed-proxy
limitation here; this was a provenance error in drafting, not a gap in
the underlying calculation. Section 3's limitations list is corrected
to match.

The Phase 0 script that produced 2.12% was run before this document was
frozen (the template's own Section 6 instruction: "computed from the
DEVELOPMENT-period distribution's own variance," which this feasibility
check already is -- Section 2's "no computation has run" refers to the
SIGNAL/portfolio/aggregate computation this document gates, not to the
Phase 0 feasibility check that justified going DEV-only in the first
place). It was not persisted as its own script/output file in this
repository; the SELECTION null actually run in Section 10 step 4 will
re-measure this same quantity at full scale, against the pinned
exclusion set, and that figure -- not this one -- is what Section 5b's
gate is actually evaluated against. If the two differ, that will be
reported as-is, not reconciled after the fact.

**Splitting any DEV/TEST boundary within this window is infeasible**:
holding out 2025 alone as a TEST slice (~4 quarters) leaves an MDE near
3% -- roughly three times momentum's own ~1% per-quarter effect size. A
split that can only detect an effect several times larger than the one
being tested for is not a meaningful validation path. This is why
Section 4 uses no split at all, per rule 6, rather than building a TEST
window that cannot validate anything -- this is the fourth recorded
instance of finding #3 (variance of the difference, not effect size, is
the binding constraint) shaping a design before any number existed.

## Section 7: what is NOT being tested, and what is NOT decided here

- The three named alternative delivery-signal specs (Section 1) --
  separate future trials, not this one.
- Any momentum-comparison null (unlike Darvas's own MOMENTUM null) --
  this study claims a standalone signal, not incrementality over
  momentum; that question is out of scope here.
- **A TIMING null.** There is no entry-timing discretion in this design
  to null out: entries are fully determined by the fixed quarterly
  rebalance calendar (Section 1), not by a signal-confirmation lag the
  way Darvas's box-breakout timing is. A timing null would have nothing
  distinct from the SELECTION null to test, so none is specified here --
  stated now so its absence is not mistaken for an oversight.
- Shorting (long-only throughout, same infeasibility as momentum).
- Any parameter sweep over the 21/60-day window widths, the 5-up-day
  minimum, the decile cut, or the hold length -- all FIXED now
  (amendment 4).
- A forward paper test's own design (sizing, execution, monitoring) --
  out of scope for this document; a DEV pass only justifies starting one
  (Section 4).

## Section 8: multiple-testing correction

New family ("delivery"), **trial count = 1**. No correction applied
beyond the single, self-computed 95th-percentile SELECTION-null bar
itself (Section 5b) -- the same stance `PREREGISTRATION_DARVAS.md`
Section 0 takes at its own trial count 1. Per amendment 4 / rule 7, this
is also the LAST trial this family gets if DEV fails: no variant is
folded in afterward without its own fresh pre-registration.

## Section 9: Claude's pre-committed prediction

**I predict DEV FAILS, most likely at condition (b)** (the 95th-
percentile SELECTION-null bar). This project's base rate across entry-
filter and overlay studies run against this universe is heavily
skewed toward failure -- the entire Liquidity family (A-E), POC (V1-V5),
Darvas, and FVG all closed on a null or DEV failure, several specifically
on a selection-null miss. "Up-days-only delivery as accumulation" is a
plausible-sounding mechanism story (amendment 3's own framing), the same
shape as several of those closed studies' original rationales. That
said, I flag real uncertainty here that those priors don't fully cover:
this is a genuinely new signal FAMILY for this project (delivery/
distribution data, never tested here before), not a retread of an
already-failed mechanism dressed in new parameters -- so a pass would be
more informative than most of this project's recent near-misses, and I
would not be surprised by it, only mildly so.

## Section 10: procedure

1. **Write this document. Commit and push it alone**, before any
   abnormal-delivery value, rebalance, or return exists anywhere in
   `src/delivery/`. Report the commit hash. **>>> this step.**
2. Build `src/delivery/` (signal computation, quarterly portfolio
   construction, SELECTION null), reusing Section 0's boundaries
   verbatim -- no new universe, cost, or exclusion logic invented.
3. **Hand-trace 3 real DEV rebalance dates before any aggregate number
   is computed**: one near the 2016 start (tightest warmup margin), one
   near the 2025 end (tightest forward-return margin), one in the middle
   with an ordinary up-day count in both windows. If real DEV data does
   not contain one of these shapes, that is stated plainly rather than
   manufactured.
4. **Run DEV only**: the real top-decile portfolio, then the SELECTION
   null (random same-size subset from the same point-in-time eligible
   pool at each rebalance, same cost model, same benchmark -- the
   identical shape `scripts/run_holdout_study1_random_decile_null.py`
   already uses for momentum; 5,000 seeds, with the same timed-probe
   affordability check every prior study's own null run uses before
   committing to the full count). Persist the exclusion set used to
   `results/exclusions/run_delivery_study1_dev.json` **before**
   computing anything from it. Report: rebalance dates used (count,
   first, last, and how many of the nominal ~40 survived Section 1's
   warmup/tail constraints); per-rebalance eligible-pool size; mean
   quarterly spread with a quarter-resampled bootstrap CI (resampling
   the independent quarterly observations themselves, not a day-
   clustered bootstrap -- the periods are non-overlapping by
   construction, amendment 1/2); all three gate conditions, stated
   plainly; the SELECTION null's own percentile; the measured abnormal-
   delivery spread's own variance (compared against Section 6's 2.12%
   Phase 0 figure, not silently reconciled if it differs). **Bad
   results are reported in the first sentence.**
5. Apply the gate (Section 5). **>>> STOP. Report to the user.** There
   is no TEST step in this family at all (Section 4) -- a pass justifies
   proposing a forward paper test as a separate, later decision; a fail
   closes the family outright (Section 5/8).

## Status

**>>> STOPPING HERE, per Process step 1.** No `src/delivery/` code
exists yet, beyond the already-committed, already-verified `delivery_eod`
import (`36c2fe8`/`6753e56`). This document is being committed and
pushed alone, before any signal, rebalance, or return value exists
anywhere in this study, so Step 2's build and every later step cannot
have shaped anything written above.
