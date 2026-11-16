# Pre-registration: Post-earnings announcement drift -- new family, trial 1

Frozen before the sealed window (earnings events, `known_date >= 2025-07-01`,
`EARNINGS_DRIFT_PHASE0.md` Section 0) is touched. Nothing below changes
after this document is committed except by an explicit, recorded
amendment. **No computation has been run for this document. It is drafted
from `EARNINGS_DRIFT_PHASE0.md`'s already-committed Phase 0 findings only,
per instruction, for review before anything runs.**

## Provenance

**Hypothesis source**: **Literature/external source** -- post-earnings
announcement drift (PEAD), a long-documented market anomaly (Bernard &
Thomas and the large literature following it). Named per the template's
own convention, with this project's standing caveat attached (see
Section 9 below): fluent familiarity with a literature-sourced strategy is
not evidence it works here.

**Provenance narrative**: This family did not come from browsing charts,
a diagnostic, or a derived finding in another study -- it came from a
decision to check whether a well-known anomaly survives this project's own
data and cost structure, same as every other literature-sourced family in
this repo (Darvas, ICT FVG) has been checked and closed. Phase 0
(`EARNINGS_DRIFT_PHASE0.md`), run before this document, found:

- 84.5% join-attrition survival on the unsealed 2016-01/2025-06 data.
- The 1,097 `isin_lineage`-unmatched rows are systematically skewed toward
  illiquid, low-priced, mostly-delisted names (survivorship-flavoured gap,
  excluded below, not silently dropped).
- 60% of announcements land post-market; day-0 cannot be defined by one
  rule without checking the real distribution first (checked; used below).
- Events cluster heavily (35-53% of a year's events on 20 days); 38
  quarter-clusters is the honest effective sample size, not 2,218 days or
  137,110 events.
- **The MDE was computed wrong once, then corrected.** The original
  computation used the variance of the 60-day return *level*; the study
  tests a *difference* (top decile minus the rest), and quarter-level
  shocks cancel in a difference far more than in a level.
  `PROJECT_CONTEXT.md`'s own finding #3 ("variance of the difference, not
  effect size, is the binding constraint") already named this exact
  failure mode, and it was catchable against that finding before anything
  was run. Corrected: winsorized quarter-clustered MDE **0.67%** (range
  0.44%-0.93% across 200 random-assignment draws) versus raw **1.78%**
  (range 1.06%-7.26%, too unstable to use). Winsorized sits *below* the
  1%-3% plausible PEAD band -- the opposite of the original, wrong-variance
  conclusion. This reversal is why this document exists at all; it is
  recorded here, in full, not softened, because the choice between 0.67%
  and 1.78% was made in advance (Section 6) and is consequential (Section
  2 restates both).

This is **trial 1** of a new family. Phase 0's two MDE computations
(original and corrected) are feasibility work, not trials, per explicit
instruction when that correction was recorded.

---

## Amendment 1 (2026-11-16, before any computation)

Three changes, recorded explicitly rather than edited in silently:

1. **Entry moved from open to close.** Flag 1 below is resolved: entry is
   now the CLOSE of the first session after the 3-day event window closes,
   using `adjusted_close` from `entity_prices_daily` -- never the raw
   unadjusted table. Forced by the panel having no `open` field at all;
   conservative (gives up the open-to-close gap any announcement reaction
   would have moved through); and it means this design tests **drift**,
   not the announcement **reaction** -- the reaction itself, if any,
   happens inside the 3-day event window and before entry, and is never
   captured as part of this study's own return.
2. **NIFTY50 replaced as the market-adjustment benchmark.** Flag 3 below
   is resolved: the benchmark is now the equal-weight return of this
   study's own event universe (Section 1) over the same session dates as
   each event's own 3-day window, not any index. NIFTY50 is cap-weighted
   and large-cap; this universe has a long small-cap tail (Phase 0 Section
   2's turnover profile). Adjusting against a large-cap index would leave
   systematic small-cap-wide movement sitting inside the "abnormal"
   return, uncancelled, rather than genuinely idiosyncratic drift.
3. **A limitations entry added, before any result exists**: the
   liquid-bands gate condition (Section 5, condition 4) is the single
   most likely failure mode. PEAD is expected, in the literature this
   family is sourced from, to be strongest in thinly covered, illiquid
   names -- which is exactly where this project's cost model charges the
   most (`COST_BY_TERCILE`'s own `low_liq` tier) and exactly what the
   gate excludes to test whether the effect survives in the tradable
   part of the universe. If the effect lives only in the names the gate
   excludes, the study fails, and that failure is the gate working as
   designed, not an oversight to fix after the fact.

Sections 0, 1, 3, 7, and 10 below reflect these three changes directly;
nothing else in this document changed.

---

## Flags: specification does not fit the data as given -- not resolved here

Per instruction, these are surfaced, not worked around. Each is a place
where the Rules as specified cannot be implemented against the data
exactly as stated, or rest on an unimplemented mechanism. None are fixed
in this document.

1. **No `open` price in the point-in-time panel.** **RESOLVED by
   Amendment 1 above.** `entity_prices_daily` (the entity-resolved,
   split-adjusted panel this project standardizes on --
   `read_entity_panel()`, same as the momentum study) carries
   `raw_close`/`adjusted_close` only, no `open`. "Entry at the open of the
   first full session after the event window closes" could not be
   implemented against that panel as written, and the raw `prices_eod`
   table's `open` is ISIN-keyed, not entity-resolved, and not
   corporate-action-adjusted -- using it directly would have reintroduced
   exactly the same-ISIN-jump and lineage-transition risk this project
   has already been burned by three times (Bug #1, Bug #11, Bug #18).
   Resolved: entry is now at the CLOSE of the first full session after
   the event window, using `adjusted_close` only. See Section 1 and
   Section 3.
2. **The same-ISIN exclusion set's `as_of` predicate is not implemented.**
   `BUGS.md` records this directly: `same_isin_jump_excluded_entities()`
   always reads the live, full warehouse; the underlying detector
   (`same_isin_jump_guard.unexplained_same_isin_jump_entities`) accepts a
   `before` cutoff but nothing threads it through. Per instruction, this
   document pins to the existing named snapshot already used for this
   project's one positive result (`FINDINGS.md` Section 2's Bug #11
   record): **the exclusion set's state on 2026-09-27 (78 entities)**. If
   `as_of` threading is implemented later, this document's universe does
   NOT silently follow it -- the pin stated here would need its own
   recorded amendment.
3. **Only one index series exists for market-adjustment.** **RESOLVED by
   Amendment 1 above.** `index_eod` has NIFTY50 only (2016-01-01 to
   2026-11-05) -- no broader small/mid-cap index -- and NIFTY50 is a
   known-imperfect benchmark for this universe: Phase 0 Section 2 already
   found the matched universe's median turnover (₹10.3M) sits well below
   large-cap liquidity, and NIFTY50 tracks the 50 largest names
   specifically. Resolved: no index is used at all; the benchmark is now
   the equal-weight return of this study's own event universe over each
   event's own window dates. See Section 1 and Section 0.
4. **The Gate's "net of costs, stated per rebalance" wording assumes a
   periodic-rebalance strategy; this is event-driven.** There is no fixed
   rebalance date -- events arrive continuously. Interpreted below as "per
   event entry" (one round-trip cost per position taken), the natural unit
   for this design. Stated as an interpretive choice, not implied by the
   template.

---

## Section 0: reuse boundaries, read-only

**Reused unmodified:**
- `read_entity_panel()` / `entity_prices_daily` -- the point-in-time,
  split-adjusted entity panel, same reconstitution convention as
  `scripts/run_holdout_study1.py`'s momentum universe.
- `same_isin_jump_guard.unexplained_same_isin_jump_entities(con,
  before=date(2026, 9, 28))` -- the 78-entity snapshot, pinned (Flag 2
  above), the same mechanism and snapshot `FINDINGS.md` Section 2 already
  uses for Bug #11.
- Turnover-tercile liquidity-band construction (20-day rolling median
  turnover, per-day tercile cut), same as
  `scripts/run_survivorship_quantification.py`'s `_liq`/`_tercile`.
- One-sample MDE machinery, `src/portfolio/power.py::
  minimum_detectable_difference` -- already used for Section 6 below.
- Random-decile-assignment null construction --
  `scripts/earnings_drift_phase0_mde_correction.py`'s `one_draw()` logic,
  reused for the SELECTION null (Section 4) rather than rewritten.
- Compounding convention: sessions/periods compound, `(1+x)^n - 1`, never
  summed or linearly approximated.

**New in this study, not yet written:** the event-return construction
(market-adjusted 3-session return, benchmarked against this study's own
equal-weight event-universe return per Amendment 1 -- not NIFTY50), the
close-based entry-rule implementation (frozen by Amendment 1, not yet
coded), the per-quarter real-spread aggregation, the quarter-clustered
bootstrap CI, the TIMING null construction, and the cost application.
None of this exists yet; Section 10 lists the order it would be built
and run in, once this document is approved.

## Section 1: configuration frozen (universe, strategy, costs)

**Universe**: `entity_prices_daily` via `read_entity_panel()`, restricted
to `known_date < 2025-07-01` (DEV window, Section 0 sealed-window
declaration). Excludes:
- The 1,097 `isin_lineage`-unmatched rows (Phase 0 Section 2) -- stated
  explicitly as excluded, not silently dropped; they are confirmed
  survivorship-skewed (median turnover ~1,000x lower, ~90% no longer
  trading).
- The 78-entity same-ISIN exclusion set, pinned as of 2026-09-27 (Flag 2).

**Event return (ranking signal)**: market-adjusted return across 3
trading sessions -- day 0, day 0+1, day 0+2 -- each session's raw return
computed close-to-close, adjusted by subtracting the **equal-weight
return of this study's own event universe (Section 1's universe, after
exclusions) over those same 3 session dates** -- not any index (Amendment
1). The three sessions compound (not sum). The focal entity is itself a
member of the universe its own window is benchmarked against; with
~2,441 constituent entities this is a ~0.04% self-weight, noted rather
than corrected.

**Day 0 definition** (pinned from Phase 0 Section 3's real distribution,
not improvised): if `broadcast_ts` is before 15:30 on a trading day, day 0
= that trading day (covers the 1.4% pre-market + 38.7% in-hours cases,
40.1% of events). If `broadcast_ts` is at/after 15:30 (60.0% of events,
post-market) or falls on a non-trading day, day 0 = the next trading day.
One rule, branching on the real distribution, applied uniformly -- no
subset gets a different rule applied after the fact.

**Entry**: the **close** of the first full trading session after day 0+2
closes (i.e., day 0+3's `adjusted_close`, if a normal session) --
**amended from open to close** (Amendment 1): `entity_prices_daily` has
no `open` field, and the raw unadjusted table is not used. Conservative
(gives up any open-to-close move the announcement reaction itself might
still be working through on day 0+3) and deliberate: this design tests
**drift after the reaction window**, not the reaction itself.

**Ranking and grouping**: rank by event return **within each quarter**
(the same grouping Phase 0's corrected MDE used for its null spread) --
not globally across the full DEV window. This is required for internal
consistency: the Gate's "top decile versus the rest" must be the same
quantity Section 6's power calculation was computed on, and that
calculation grouped by quarter. A global ranking would compare a
different statistic than the one Phase 0 sized.

**Position**: top decile (by within-quarter event-return rank), equal
weight across the decile's constituents for that quarter.

**Holding period**: 60 trading days from entry. No stop.

**Comparison**: top-decile mean 60-day return minus the mean 60-day
return of the rest of that quarter's event population (same construction
as the null). Not versus NIFTY50 or any index -- no index is used
anywhere in this document after Amendment 1; the event-return
market-adjustment step above uses this study's own event-universe
equal-weight return instead.

**Costs**: round-trip cost of 0.20%-0.30% of notional, charged once per
position (one entry, one exit) against the top-decile leg only -- the
"rest" leg is a statistical comparison population, never a funded
position, so no cost is charged against it (Flag 4's interpretive
choice). Turnover assumption: 100% per position (full size at entry, full
size at exit, no partial fills, no overlap control across quarters).

## Section 2: historical result (pre-holdout/exploratory -- NOT the test)

None exists. This document is drafted without running the strategy at
all, per instruction. Phase 0's two MDE figures (wrong-variance 1.78%/raw
vs. corrected winsorized 0.67%) are power inputs, not a historical
backtest result, and are not a preview of this study's own outcome.

## Section 3: known, permanent limitations

- **Entry is at close, not open (Amendment 1), forced by
  `entity_prices_daily` carrying no `open` field.** This is conservative
  -- it gives up the open-to-close move of the first post-window session,
  which could still carry residual announcement reaction -- and it means
  this design tests **drift that persists after the 3-day event window**,
  not the announcement's own initial reaction. A study that could use
  intraday or raw adjusted opens might find a different, larger effect in
  the reaction itself; this one, by construction, cannot see that effect
  and is not claiming to.
- **The liquid-bands gate condition (Section 5, condition 4) is the most
  likely failure mode, stated before any result exists.** PEAD is
  expected, in the literature this family is sourced from, to be
  strongest in thinly covered, illiquid names -- exactly where this
  project's cost model charges the most (`low_liq` tier,
  `COST_BY_TERCILE`) and exactly what this condition excludes. If the
  effect lives only in the names the gate excludes, the study fails, and
  that is the gate working as intended, not an oversight to patch later.
- **The event-universe equal-weight benchmark (Amendment 1) includes the
  focal entity in its own benchmark** (~0.04% self-weight at ~2,441
  constituents) -- negligible at this N, noted rather than corrected.
- The 78-entity exclusion pin (Flag 2) will go stale the moment the live
  same-ISIN jump guard flags another entity (it already moved from 78 to
  82 once during this project's own history, per `BUGS.md`) -- this
  document's result, whenever computed, is anchored to 78, stated
  plainly rather than silently re-run against whatever the live count is
  by then.
- Winsorization (Section 6) changes the primary verdict's basis
  materially (0.67% vs. 1.78% MDE) -- this is disclosed, not hidden, but
  it is still a modeling choice made before seeing a result, and a critic
  is entitled to prefer the raw number.
- This project's own calibration record (`PROJECT_CONTEXT.md` Section 9)
  is 0-for-5 on predicted MECHANISM across the Liquidity family, even
  when the verdict was right. No reason exists to expect better calibration
  here.

## Section 4: the validation path -- what resource this consumes, and why

**DEV** (2016-01 through 2025-06, unsealed): structural checks, the Gate
(Section 5), and both nulls (below) -- consumes nothing sealed.

**SEALED** read (`known_date >= 2025-07-01`): read **once**, only after
DEV passes **and** the human approves, per this project's own "Sealed
windows" rule (`PROJECT_CONTEXT.md` Section 3). A DEV failure closes the
study automatically -- no approval step is reached, and no sealed data is
touched.

**SELECTION null**: random decile assignment within each quarter, same
construction as Phase 0's corrected MDE null (`scripts/
earnings_drift_phase0_mde_correction.py::one_draw`). Tests whether the
within-quarter decile assignment by true event return adds anything over
a random split of the same population.

**TIMING null**: the same selected events (same entities, same years),
each held for 60 trading days from a random trading day elsewhere in the
same calendar year, instead of from the real post-announcement entry.
Tests whether the announcement's timing matters, or only which
stock/year combinations were selected.

## Section 5: decision rule, fixed now, before the read

**All of the following must hold, on DEV, before the sealed window is
ever touched:**

1. Mean top-decile-minus-rest spread (within-quarter, Section 1) > 0,
   with a **quarter-clustered** bootstrap CI (resample the 36 quarters
   with replacement, not individual events) excluding zero.
2. >= 95th percentile against **both** the SELECTION null and the TIMING
   null (Section 4).
3. Still positive after dropping the single best calendar year.
4. Positive within the liquid bands alone (high_liq + mid_liq turnover
   terciles, Section 0's reused construction; low_liq excluded for this
   check only).
5. Net of 0.20%-0.30% round-trip costs (Section 1), stated at **both**
   ends of the band -- must be positive at 0.30%, the worse end, not only
   at 0.20%.

If condition 1 fails decisively, the run is killed outright -- the nulls
do not get a chance to rescue it, per this project's standing Gate rule.

## Section 6: power calculation, from historical variance only, never the mean

Already computed in `EARNINGS_DRIFT_PHASE0.md` (the "Correction to
Section 5's MDE" section), reproduced here per instruction so a reader
sees the choice was made in advance, not after:

| | SD of quarterly null spread | MDE (80% power, quarter-clustered, df=35) |
|---|---|---|
| Raw | mean 3.71% (range 2.20%-15.11%) | mean 1.78% (range 1.06%-7.26%) |
| **Winsorized (primary)** | mean 1.39% (range 0.92%-1.93%) | **mean 0.67% (range 0.44%-0.93%)** |

**Winsorization rule, frozen here, before any result**: clip the 60-day
forward return at the **1st/99th percentile, computed within each
quarter** (not pooled across the full DEV window), before computing any
decile mean. Justified on grounds that do not reference any outcome of
this study: (a) it is the same level and the same within-quarter
granularity already used for Phase 0's power calculation, so the power
estimate and the eventual test statistic are computed under the same
treatment of the data, not two different ones; (b) a 1%/99% clip removes
only the most extreme ~2% of observations per quarter, which Phase 0
Section 5 already identified as dominated by corporate-action-scale
artifacts (e.g., +18,939% on repeated rows for a single entity) rather
than tradable price action; (c) within-quarter (not pooled) clipping
avoids one unusually volatile quarter setting the clip level for every
other quarter.

**Both winsorized and raw are reported, always, in every result this
study produces -- winsorized is the pre-declared primary, raw is never
omitted alongside it**, so a reader can see both and judge the
sensitivity themselves.

**Plausible PEAD effect band: 1%-3% over 60 days** (stated as a
literature-informed band, not derived from this project's own data).
**Round-trip cost band: 0.20%-0.30%.** The winsorized MDE (0.67%) sits
below the entire plausible band; the raw MDE (1.78%) sits inside the
lower half of it but is unstable across draws (Section 6 of
`EARNINGS_DRIFT_PHASE0.md`) and is not used as the basis for this study's
feasibility.

## Section 7: what is NOT being tested, and what is NOT decided here

- Whether PEAD exists in US or other developed markets -- not tested;
  assumed only as the literature source for this hypothesis, per Section
  9's own caveat about fluency not being evidence.
- Any announcement-return-vs-forward-return relationship -- not computed
  anywhere in this document or in Phase 0. That computation begins only
  if this document is approved and DEV is run.
- Whether a different entry rule (open-based, if a data source existed),
  a different benchmark, or a different exclusion-set vintage (Flag 2)
  would change the result -- not tested; one configuration is specified
  and frozen here, per instruction ("ONE corrected computation, not a
  search" applied to this document's own design, not just to the MDE
  correction it follows).
- Intraday reaction within the 3-session event window, or the
  open-to-close reaction on the entry session itself -- not modeled; only
  close-to-close session returns are used (Amendment 1), and entry is at
  close, not open.
- The announcement **reaction** (the price move during the 3-day event
  window) -- not this study's subject at all; this design tests only
  what happens **after** that window, i.e. drift, by construction
  (Amendment 1, Section 3).

## Section 8: multiple-testing correction, if this is part of a family

Lone trial -- trial 1 of a new family. No correction applied, none
needed at n=1. If any alternative configuration (open-based entry if a
data source were found, a different winsorization level, a different
holding period) is run before or after this one, the family's trial count
increases and a correction must be applied retroactively to both,
per `PROJECT_CONTEXT.md`'s own trial-counting convention (a configuration
counts once it reaches this Gate or is killed at a Phase-1-equivalent
check -- Phase 0, already run, did not kill this family, so this is the
first trial to actually reach the Gate).

## Section 9: Claude's pre-committed prediction

**Prediction, before any computation**: DEV will show a positive,
plausible-looking winsorized spread, roughly in the lower half of the
1%-3% literature band -- PEAD is well-enough documented that some
version of it showing up in a first pass would not be surprising. But I
predict the study **fails at least one Gate condition**, most likely
condition 4 (liquid bands alone), because published PEAD effects are
frequently concentrated in exactly the smaller, less liquid names this
project's own Liquidity family (4 of 4 DEV failures) has already found
evaporate once liquidity constraints are applied -- and Phase 0 Section 2
already confirmed this universe's matched population skews toward
lower-turnover names generally. Per this project's own calibration record
(Section 9 of `PROJECT_CONTEXT.md`: 5-for-5 wrong on mechanism even when
the verdict was right), I hold this mechanism loosely -- if the study
fails, I would not be surprised if it fails for a different reason than
the one stated here.

## Section 10: procedure

Not run. The order, once approved:

1. Build the event universe (Section 1 exclusions, join-attrition logic
   from `scripts/earnings_drift_phase0.py`, reused).
2. Build the event-universe equal-weight daily return series (Amendment
   1) -- new, not yet written.
3. Compute the market-adjusted 3-session event return (benchmarked
   against step 2's series, Section 1) for every surviving event.
4. Rank within each quarter; assign top decile and the rest.
5. Compute per-quarter top-decile-minus-rest spread, both raw and
   winsorized (Section 6's frozen rule), using close-based entry
   (Amendment 1) for the 60-day holding return.
6. Quarter-clustered bootstrap CI on the mean spread (resample quarters).
7. Run the SELECTION null (random decile assignment, many draws) and the
   TIMING null (random same-year entry window); compute percentiles.
8. Drop the best calendar year; recheck positivity.
9. Restrict to liquid bands only (Section 0's tercile construction);
   recheck positivity.
10. Apply round-trip costs at both 0.20% and 0.30% to the top-decile leg;
    recheck positivity at the worse end.
11. Evaluate Section 5's Gate in full. If any condition fails, the study
    closes automatically -- no sealed read, no human decision needed.
12. If all conditions hold, present the DEV result for human approval
    before touching `known_date >= 2025-07-01`.
