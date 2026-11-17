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

**RETRACTED, 2026-11-17** (superseding the paragraph below, not
deleting it -- see this section's own final entry for the full
retraction): ~~The holdout margin is stated as a range, permanently,
as of 2026-11-16... Primary 3.50 points; range 3.50-5.97 depending on
correction method...~~ **The margin has never been reproducibly
quantified. 3.50 was checked explicitly and shares the same defect as
the retracted 3.57-5.22 range -- it is not a safer number sitting
above it.** The verdict (holdout read once, pre-registered, all three
conditions passed) stands unaffected; the margin does not. Do not cite
a point estimate from this record. The 3.87 below is the ORIGINAL,
uncorrected, AS-READ figure -- the one number in this section that
*is* a fact about a specific read on a specific date, not a claim that
any later recomputation will confirm it.

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

**The sealed holdout spans 5 rebalance periods over ~13 months
(2025-04-11 to 2026-04-22), universe 1,131-1,292 names per period,
decile 114-130 names, 604 selection slots, 336 distinct entities. Five
periods is the effective sample for the CAGR margin, since holdings
within a period share the same market. The result was pre-registered
and all three conditions passed; this is stated so the sample size is
visible next to the margin rather than having to be derived.**

**Do not extrapolate the backtest's 30.4%/18.1% level forward.** The
holdout's 14.72%/10.85% is far lower, consistent with 2017-2024 having been
an unusually strong run for Indian small/mid caps specifically, not with
the strategy degrading. The margin, not the absolute level, is the number
this study was designed to test, and the margin held.

**Amendment, 2026-09-27: Bug #11 materiality check, closed.** This is the
only positive result across all three projects in this repository -- the
one number that must not rest on contamination. Some of the 78 same-ISIN-
jump entities BUGS.md Bug #11 found are plausible missed splits
(JSWSTEEL, GRASIM, TRENT -- zero `corporate_actions` coverage, ratios
close to common split factors); an uncorrected split fabricates an
artificial price jump that, if upward, inflates a trailing-12-month
return and could place a name in momentum's top decile on artifact alone.
The swing project checked this same contamination and found it immaterial
there, but swing selects on a 5-day dip, a different exposure to a
single-day jump than momentum's 12-month-return top-decile selection --
not assumed to generalize, checked directly instead
(`scripts/run_momentum_backtest_bug11_check.py`,
`scripts/run_holdout_study1_bug11_check.py`,
`scripts/run_study2_largecap_bug11_check.py`; the holdout reread is
permitted and logged to `data/holdout_access_log.txt` as a materiality
check on the now-retired window, Section 7, not a new spend).

| | pre-holdout backtest, ORIGINAL | pre-holdout, 78 EXCLUDED | holdout, ORIGINAL | holdout, 78 EXCLUDED | large-cap (Study 2), ORIGINAL | large-cap, 78 EXCLUDED |
|---|---|---|---|---|---|---|
| Momentum CAGR | 30.43% | 29.83% (-0.60pp) | 14.72% | 14.76% (+0.04pp) | 17.95% | 20.14% (+2.19pp) |
| Benchmark CAGR | 18.11% | 18.14% (+0.03pp) | 10.85% | 11.12% (+0.27pp) | 11.39% | 12.84% (+1.45pp) |
| Margin | +12.32pts | +11.70pts (-0.62) | +3.87pts | +3.64pts (-0.23) | +6.56pts | +7.30pts (+0.74) |
| Momentum MaxDD | -35.95% | -36.12% (-0.17pp) | -6.48% | -7.85% (-1.37pp) | -36.52% | -33.60% (+2.92pp) |
| Benchmark MaxDD | -49.82% | -50.01% (-0.19pp) | -10.45% | -10.45% (+0.00pp) | -44.51% | -39.80% (+4.71pp) |
| Decision rule | -- | all 3 PASS, no flip | -- | all 3 PASS, no flip | -- | all 3 PASS, no flip |

**No condition flipped anywhere. Margins moved modestly, in both
directions** (down 0.62pts and 0.23pts on the pre-holdout and holdout
comparisons, up 0.74pts on the large-cap one) -- not a one-directional
inflation. The holdout margin (3.64 vs. the 3.0-point threshold, AS OF
THIS 2026-09-27 CHECK ONLY -- see the 2026-11-16 update below: this is
a point reading of what is actually a 3.57-5.22 range across exclusion-
set versions, not a fixed value) is the closest to its bar of the
three, but still clears it with room, and
momentum's own holdout MaxDD actually got slightly WORSE excluding these
entities (-6.48% -> -7.85%) while its CAGR barely moved -- evidence
against these entities uniformly flattering the result, not for it.

**How many of the 78 ever entered the top decile, and clustering**: 44 of
78 entered Study 1's (whole-market) top decile at some point pre-holdout
(138 entity-rebalance hits, spread across every year 2017-2024 -- 9, 10,
24, 25, 25, 13, 13, 19 -- no single-period concentration), and 14 of 78
entered during the 5-rebalance holdout window (29 hits, spread across all
5 dates, 4-7 names per date). 0 of 78 ever entered Study 2's large-cap
top decile, but **29 of 78 were in the large-cap UNIVERSE (the
top-200-by-turnover benchmark) at some point** -- present in every year
2018-2026, 15-20 names each year -- including large, liquid names
(JSWSTEEL, GRASIM, TRENT among them, confirmed by symbol lookup, not just
thin illiquid ones); the large-cap margin moved because excluding these
29 changed the BENCHMARK's own composition, not because any of the 78
were ever a top-decile pick.

**Closed, per this check's own pre-committed rule**: all three condition
sets passed, on all three comparisons, with modest bidirectional margin
movement -- the momentum holdout pass does not rest on this
contamination. Not re-run further; the six other scripts sharing this
same gap (BUGS.md Bug #11's update) remain recorded, not fixed.

**UPDATE, 2026-11-16: the record stays anchored to the read date; a
separate sensitivity diagnostic was run alongside it, and is NOT a
replacement for the record.**

**THE RECORD**: margin 3.87 -> 3.64 at the exclusion set's state on
**2026-09-27** (78 entities, the holdout read date), still clearing the
3.0 threshold. This is the pre-registered result and does not change.

**THE DIAGNOSTIC** (descriptive, run on the already-retired window,
nothing about the strategy varied, not to be re-run as a recurring
"update"): `same_isin_jump_excluded_entities()` reads the full
warehouse at call time with no point-in-time cutoff, so the SAME
mechanism applied at later snapshot dates -- dates that did not exist
on 2026-09-27, using information not available at read time -- produces
a different number each time it is asked. That is what the table below
measures: not a newer, better value, but how sensitive the mechanism
itself is. Window held fixed (the original 5 rebalances, through
2026-04-22) so only the exclusion-set snapshot varies:

| snapshot date (not the holdout window) | excluded | margin |
|---|---|---|
| ORIGINAL (no exclusion applied at all) | 0 | 3.87 |
| **2026-09-27 (the record, read date)** | **78** | **3.64** |
| 2026-09-27, reconstructed* | 79 | 3.99 |
| 2026-09-28 | 80 | 5.22 |
| 2026-10-10 | 81 | 3.57 |
| 2026-11-16 | 82 | 4.00 |

*Reconstructed by filtering today's flagged-jump table on `jump_date <=
checkpoint` -- no snapshot of the exact original 78 was ever saved, off
by one entity, immaterial to the conclusion. Script:
`scripts/run_holdout_study1_bug11_check_versioned.py`. Logged to
`data/holdout_access_log.txt` as a materiality check on the retired
window, same discipline as the original.

**State the diagnostic against the threshold, not just as a range**: a
single entity has been observed moving the margin by **1.65 points**
(MOLDTKPAC, `INE893J01011`, snapshot 2026-10-10) while the buffer above
the 3.0 threshold across these snapshots is only **0.57 to 1.00
points**. A single further adverse addition of a size already seen
would exceed that buffer. The result is not robust to the exclusion
mechanism's own instability, even though the record itself (3.64, dated
2026-09-27) stands and is not changed by this.

**Which entities drive it, not an even four-way split**: AASTHA
(`INE2FMX01012`, flagged 2026-09-28) moved the margin +1.23pts (3.99 ->
5.22). MOLDTKPAC (`INE893J01011`, flagged 2026-10-09) moved it -1.65pts
(5.22 -> 3.57) -- the single largest swing, and on its own would have
left only a 0.57pt buffer had it landed alone rather than alongside
AASTHA's offsetting move. CONCORDBIO (`INE338H01029`, flagged
2026-11-04) moved it +0.43pts (3.57 -> 4.00). Two large, nearly-
canceling single-name swings, not four entities contributing a little
each.

**This and the contribution-concentration diagnostic below are the SAME
fact, not two independent observations -- stated explicitly so a future
reader does not take them as corroborating each other.** A margin in
which the top 10 of 336 entities carry 63% of compounded return is
*necessarily* a margin a single entity's removal can move by points:
concentration and single-name sensitivity are the same property of the
same distribution, read two ways. The exclusion-set sweep found this
empirically, from the outside, by watching what happened when specific
entities entered an unrelated (same-ISIN-jump) exclusion list; the
contribution decomposition below finds the identical property directly,
from the inside, by ranking the real selections by their own return.
Neither corroborates the other independently -- they are one
right-skewed distribution, observed twice.

**UPDATE, 2026-11-16, second diagnostic: contribution concentration of
the RECORDED holdout result itself** (descriptive only, on the
already-spent window, same discipline as above -- momentum being
winner-driven is expected, this is the number on record rather than an
inference). Decomposed the primary, unexcluded holdout's own
compounded gross return (12.88% over the 5 rebalances) by entity,
exact (every entity's dollar contribution sums to the total, nothing
left over): **top 1 contributor = 9.3% of total growth, top 5 = 38.3%,
top 10 = 63.0%**, out of 336 distinct entities ever selected across the
5 rebalances. The single largest contributor was GABRIEL
(`INE524A01029`, 9.3%), followed by POWERINDIA (`INE07Y701011`, 8.7%)
and LAURUSLABS (`INE947Q01010`, 7.7%). "Share of the margin" is
approximated by share of the momentum side's own return, not a full
two-sided attribution -- the benchmark side is an equal-weighted
average over 1100-1300 names each period, so no single name can move
it much by construction; concentration is a momentum-side property.
Script: `scripts/run_holdout_study1_contribution_concentration.py`,
output in `data/holdout_study1_contribution_concentration.csv`. **Same
fact as the exclusion-set sensitivity above, not separate
corroborating evidence** -- see that paragraph's note.

**Reconciliation, checked rather than assumed (336 distinct entities
out of how many slots)**: the HOLDOUT window itself has only **5
rebalance periods** (2025-04-11 through 2026-04-22, ~13 months at the
63-day cadence) -- not the ~8-year, ~32-period PRE-HOLDOUT development
window this could be confused with. Eligible universe per period:
1131-1292 names (whole-market, Study 1's own construction); decile
(10%): 114-130 names/period; **total selection slots: 604**, not
~5,900. Median number of periods a selected name appears in: **1**
(mean 1.80; 170 names appeared exactly once, 94 twice, 47 three times,
20 four times, 5 in all five). This reconciles cleanly with the
`mom_turnover` already recorded per period in `data/
holdout_study1_records.csv` (46-55% of the decile turns over every
rebalance) -- roughly half the names change each period, so across
only 5 periods, 336 distinct out of 604 slots is the arithmetic that
turnover predicts, not a discrepancy.

**PRE-COMMITTED INTERPRETATION, recorded 2026-11-16, before the
2026-10-26 live basket's outcome is known:**

> The 2026-10-26 basket's 63-day outcome will be high variance and
> dominated by a small number of holdings. Historically the top 1
> entity accounted for 9.3% of compounded return, the top 5 for 38.3%
> and the top 10 for 63.0%, out of 336 distinct entities ever selected.
> A single basket is therefore an extremely weak test: a good outcome
> may reflect one or two names running, and a poor outcome may reflect
> their absence, with neither saying much about the strategy. Recorded
> 2026-11-16, before the outcome is known, so that it cannot be offered
> afterwards as an explanation for whichever result arrives.
>
> One forward basket is one fifth of the holdout's sample. Roughly five
> baskets — about 315 trading days, or 15 months — would carry
> comparable weight to the sealed test. The January 2027 check-in is
> therefore a single weak observation by construction, whichever way
> it lands, and should be recorded as one data point rather than read
> as confirmation or refutation.

**PRE-COMMITTED, 2026-11-16, before the Bug #26 lineage-contamination
check below is run:**

**WHAT THIS IS**: a contamination check on a recorded result, in the
same category as the exclusion-set reproducibility check above. It is
NOT a re-test and NOT a new hypothesis. Nothing about the strategy may
vary -- same rules, same windows, same universe construction. The only
change is removing data now known to be defective (`BUGS.md` Bug #26's
own follow-up 3: 40 entities with an unexplained, zero-gap lineage-
transition jump, never previously excluded from this holdout).

**Method -- both reported, they answer different questions:**
(a) WINDOW-LEVEL, the precise correction: exclude any momentum or
forward-return window that SPANS a flagged lineage transition, keeping
that entity's clean windows. This is the correct granularity, per the
finding that the transition sits between endpoints, not at one.
(b) ENTITY-LEVEL, the conservative one: exclude all 40 entities
outright, matching the 78-entity precedent. If (a) and (b) disagree
materially, that itself is informative and will be stated as such.

**Both directions, before the number exists:**

If the margin stays above 3.0 under both corrections: the result
stands, and the margin is restated to include this exclusion alongside
the same-ISIN one. It does not become "more robust" -- it becomes
correctly stated.

If the margin falls below 3.0 under either correction: the recorded
pass was produced partly by contaminated data. That does not mean
momentum fails; it means THIS TEST did not establish it, the holdout is
spent, and it cannot be re-established. The project would then have
ZERO clean passes, and `PROJECT_CONTEXT.md` Section 4 must say so in
its first line. No re-litigating, no appeal to the original check
having passed, no third correction.

**RESULT, computed after the above was committed**
(`scripts/run_holdout_study1_lineage_check.py`). Window held fixed to
the original 5 rebalances (through 2026-04-22, same convention as the
exclusion-set sensitivity table above); same-ISIN exclusion pinned to
the 2026-09-27 read date (79 entities, reproducing 3.63 against the
recorded 3.64 -- the same one-entity reconstruction difference already
noted above, immaterial):

| variant | margin | pass? |
|---|---:|---|
| ORIGINAL (no exclusion at all) | 3.87 | -- |
| RECORDED (78 same-ISIN excluded, 2026-09-27) | 3.64 | -- |
| Reproduced baseline, this check (79 same-ISIN excluded) | 3.63 | PASS |
| **(a) WINDOW-LEVEL** (78/79 + the 40 lineage entities' transition windows masked) | **3.50** | **PASS** |
| **(b) ENTITY-LEVEL** (78/79 + the 40 lineage entities excluded outright) | **5.97** | **PASS** |

**(a) and (b) disagree materially (-2.47pts), as anticipated above --
stated, not smoothed over.** Window-level and entity-level correct the
same contamination at different granularity and get different answers;
neither is wrong, they answer different questions (what the data
actually shows once only the bad windows are removed, vs. the more
conservative whole-entity removal). Window-level is the more precise
correction, per this project's own finding that the transition sits
strictly between a window's two endpoints, not at either.

**Selected-decile positions affected, baseline (pre-correction)**: of
the 40 entities, 18 entity-rebalance hits into the top decile across
the 5 holdout rebalances (1, 3, 4, 7, 3 per rebalance) -- no single
rebalance drove this; 2026-01-14 (7 hits) is the most concentrated.
Window-level correction removes 2 of those 18 hits (2026-01-14 drops
from 7 to 5, as the specific entities whose lookback window spans their
own transition at that date are correctly excluded from that one
rebalance's ranking, while remaining eligible at other rebalances where
their window is clean); entity-level removes all 18 by construction.

**VERDICT, per the pre-commitment above: the margin stays above 3.0
under both corrections. The result stands. The margin is restated,
not "made more robust"**: **3.87 (original) -> 3.64 (78 same-ISIN
excluded, 2026-09-27) -> 3.50 (also window-level-correcting the 40
lineage entities, the precise form; 5.97 under the conservative
entity-level form)**. `PROJECT_CONTEXT.md` Section 4 is NOT amended to
state zero clean passes -- this branch of the pre-commitment does not
apply.

**THE MARGIN IS NOW STATED AS A RANGE, PERMANENTLY, AND NO FURTHER
POINT ESTIMATE SHOULD BE PRODUCED, 2026-11-16.** Six measured values
exist on record (3.87, 3.64, 3.63, 3.50, 5.97, and the separate
3.57-5.22 exclusion-set-sensitivity diagnostic) -- every one defensible
under its own stated method at the time it was computed, none of them
"the number." **Primary: 3.50** (window-level correction for both known
contaminations -- the most precise analysis choice, and, as it happens,
the lowest measured value, which is itself worth noting rather than
treating as suspicious: the more careful the correction, the smaller
the margin got, consistently, across every correction applied so far).
Full range: **3.50-5.97**, plus the 3.57-5.22 diagnostic layered on top
of the pre-lineage-correction state. `PROJECT_CONTEXT.md` Section 4
carries the same range. **The next person to recompute this will get
yet another number -- `same_isin_jump_excluded_entities()` still reads
the live warehouse with no pinned version, and any further contamination
class found would add another correction method with its own defensible
granularity choice. That is a property of the measurement, not news,
and is not grounds for another re-run.**

---

**RETRACTION, 2026-11-17: the paragraph immediately above treated 3.50
as a clean primary figure above an unmeasured-sensitivity range. It
was wrong to do so. Annotated, not deleted.**

Instructed to check this explicitly, before anything else, since it is
the headline number: **does the 3.50 figure share the defect that made
the 3.57-5.22 range unreliable?** Checked by reading the code, not by
analogy. `scripts/run_holdout_study1_lineage_check.py` builds its
40-entity correction via `lineage_jump_guard.find_unexplained_jumps(con)`
-- called with no `before=` cutoff. Inside that function
(`src/data_layer/lineage_jump_guard.py:67`):

```python
actions = con.execute("SELECT symbol, ex_date FROM corporate_actions").fetchdf()
```

An unfiltered, current-state read -- no `known_date`/`fetched_at`
point-in-time predicate at all. `has_nearby_ca_record`, the flag that
decides whether a transition enters the 40-entity set, is evaluated
against TODAY's `corporate_actions` table for every transition,
including ones dated years ago. **This is the identical mechanism**
`BUGS.md` Bug #27 already found unstable on the same-ISIN side. Opened
as its own entry, `BUGS.md` Bug #28 -- the same bug in a second place,
the ninth instance of "fixed where noticed, not everywhere the pattern
recurs" (`PROJECT_CONTEXT.md` Section 7 finding #4).

**Answer: yes. 3.50 is exposed identically.** No earlier run of this
script exists to show an observed drift (unlike the same-ISIN side,
where multiple historical runs already disagree), but the mechanism
is the same and already proven unstable in the sibling case. 3.50 is
not a safer number sitting above the retracted range -- it is the same
kind of number.

**The corrected record, replacing the paragraph above:**

The verdict stands, unaffected: the holdout was read once, on a
pre-registered design, and all three conditions passed.

The margin does not stand the same way. Computed at **+3.87** at read
time against the 3.0 threshold. Subsequent corrections gave 3.64, 3.50,
and 5.97, each clearing 3.0 when run. **None of these four numbers is
reproducible.** ~~All four depend on `corporate_actions` state at the
moment the computation ran.~~ **CORRECTED, 2026-11-17**: `corporate_
actions` has been frozen since 2026-09-19 and cannot be the moving part
-- the dependency is on `prices_eod`/`adjustment_factors` state (which
grow continuously) feeding the detectors' own ratio/boundary
computation, not on the corporate-actions match. See `BUGS.md`'s
resolution-path entry, corrected the same day, for the full redirection.
The margin has never been reproducibly
quantified; its sensitivity to warehouse state is unmeasured; and
whether the pass depended on contaminated entities is therefore **OPEN**
-- not "resolved at 3.50," not "bounded by a 3.50-5.97 range."

**Do not cite a point estimate from this record. Do not recompute
expecting to confirm one.** A new run produces a new number, and that
is a property of the measurement. Large-cap replication +6.56 ->
reported 7.30 (the table above) is **also unreproduced**: re-running
`run_study2_largecap_bug11_check.py` today, pinned, gives **8.04**,
cause undiagnosed (`BUGS.md` Bug #27). Lower stakes -- Study 2 was
CV-only, no holdout spent -- but it does not sit in this record as
verified either.

**ADDENDUM, 2026-11-17 -- structural stability of 3.50 specifically,
not a reopening.** Checked whether the drift mechanism above can
actually reach the holdout window [2025-04-11, 2026-04-22]: of 45
unexplained lineage transitions, 14 fall inside it; of 82 canonical
same-ISIN entities, 13 do: all already inside the exclusion lists that
produced 3.50, none new. Of the 3 entities added to the same-ISIN set
since the pinned 79-entity snapshot, zero have jump dates inside the
window. Because `prices_eod` is confirmed forward-growth-only (no row
with a `trade_date` before the window's close has ever been written
with a `fetched_at` after it), a closed historical window cannot
acquire a new in-window jump from future ingestion. **Property:** under
window-level correction, 3.50's inputs cannot move from same-ISIN
drift as currently observed, and will keep not moving unless a future
run reports a NEW unexplained jump/transition dated inside the window
itself -- the one failure mode not ruled out here. This does not make
3.50 reproducible from first principles, and does not un-OPEN the
margin -- it establishes that the specific drift mechanism already
observed elsewhere does not, in fact, reach this particular number.
Full transition/entity lists and the forward-growth evidence are in
`BUGS.md`'s "Holdout-window drift-reachability check" and "Exclusion-
set growth source" entries, both 2026-11-17.

**FINAL RESTATEMENT, 2026-11-17 -- absent new information. Rests
entirely on the measurements already made above; nothing below
required a new computation.**

**VERDICT**: the holdout was read once against a design fixed in
advance; all three pre-registered conditions passed. Unchanged.

**MARGIN UNDER WINDOW-LEVEL LINEAGE CORRECTION: 3.50, against a 3.0
threshold. REPRODUCIBLE**, for two independent reasons: its exclusion
list is persisted (`results/exclusions/
run_holdout_study1_lineage_check.window_level.json`) and reproduces the
figure end-to-end by loading, not recomputing; and recomputing the list
from scratch yields the same margin, because all entities added since
the pinned snapshot have out-of-window jump dates while price
ingestion is forward-only (the ADDENDUM immediately above).

**Did detected contamination drive the pass? No.** Removing it costs
0.37 points (3.87 -> 3.50) and the result still clears the 3.0
threshold. This was the question the corrections existed to answer,
and it is now answered -- for DETECTED contamination. Undetected
contamination is unfalsifiable and always will be.

**Conditions under which 3.50 would move -- both stated, not just the
likelier one:**
(a) price ingestion ceasing to be forward-only, i.e. historical
backfill producing a newly-detected jump dated inside the window;
(b) `corporate_actions` resuming updates, which could EXPLAIN one of
the 14 currently-unexplained in-window transitions, remove it from the
exclusion set, and move the margin in the OPPOSITE direction. That
table is frozen by accident, not design, making (b) the more likely of
the two.

**Tripwire**: both conditions are checked, not just written down, by
`src/data_layer/margin_tripwire.py` (`assert_no_in_window_price_
revision` for (a), `assert_corporate_actions_and_lineage_still_frozen`
for (b)) -- the natural location since it sits alongside `data_layer.
staleness`, the module every price-panel consumer already calls before
computing anything, per `BUGS.md` Bug #13. ~~Not yet wired into any
entry point~~ **WIRED, 2026-11-17**: `tests/test_margin_tripwire.py`'s
`test_live_*` functions, data-gated (skip on CI, run for real in the
Saturday weekly full-suite job per `OPERATIONS.md`'s "Weekly full-suite
run against real data" section) -- verified live end-to-end, including
a real "DOWN" email on a forced failure. If either raises --
`FrozenTableResumedError` or `HoldoutWindowPriceRevisionError` -- 3.50
must be recomputed and this section revisited before the number is
cited again.

**Still open, unchanged**: the older figures (3.87, 3.64, Study 2's
7.30) remain unreproducible, with no exclusion list ever saved for any
of them; the sensitivity of the margin to exclusion-set VERSION (as
opposed to whether the window-level set is currently stable) remains
unmeasured and needs the as-of work on the price/lineage path (`BUGS.
md`'s resolution-path entry, corrected 2026-11-17).

**ADDENDUM, 2026-11-18 -- the 3.0pp threshold itself was never
calibrated.** Traced its provenance in `PREREGISTRATION.md`: stated as
"within noise for a ~6-7 period sample," with no standard-error or MDE
calculation shown anywhere backing the number 3.0 -- marked UNVERIFIED.
Since it is asserted, not derived, ran the calibration it never got: a
5,000-seed random-decile null over the identical already-spent holdout
window (same universe, same costs, same benchmark, `scripts/run_
holdout_study1_random_decile_null.py`). **The recorded +3.50pp margin
sits at the 92.6th percentile of random, momentum-blind decile
selections -- below the 95th-percentile bar this project uses
everywhere else, and 8.9% of random deciles clear 3.0pp outright on
this same window.** The verdict is unaffected -- conditions (a) and (c)
don't depend on this, and the pre-registration already called a pass
"weak evidence... on a thin sample" before the holdout was read. What
changes: the margin clears a bar whose stringency was never
established, not a calibrated one. Full numbers and the provenance
trace are in `PREREGISTRATION.md`'s own 2026-11-18 post-hoc annotation.

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

## 7. Holdout status: RETIRED -- no historical holdout remains

**Historical record, before the retirement decision below**: Study 1 of 3
complete. The sealed 18-month holdout for this dataset was read once, per
`PREREGISTRATION.md`, and was **spent**. Per this project's own standing
rule, it could not be re-read, re-run on a modified configuration, or
appealed.

**Second read, 2026-09-27**: the sibling swing project's own
`PREREGISTRATION_SWING_V1.md` (V1, dip-in-momentum-winners, Top-10
concentrated by dip magnitude) charged its holdout evaluation against
this same resource, per the user's explicit decision recorded there --
`scripts/run_swing_v1_holdout.py`, logged to
`data/holdout_access_log.txt`, result in
`data/swing_logs/swing_v1_holdout_20260927T162530.txt`. **Primary gate:
FAIL** (percentile 61.4 vs. the required >=95, against a matched-random
null drawn from POOL_ML restricted to the same holdout window). This is
an unrelated rule (a 5-day-horizon dip-reversal signal within momentum
winners) on an overlapping but not identical universe (POOL_ML requires a
liquidity-tercile screen this Study did not apply) -- reported here only
so the shared resource's ledger stayed accurate, not as a finding about
`momentum_12_1` itself.

**Third read, 2026-09-27, the one that changes the ledger's own status**:
`src/monitor/persistence.py` (Hypothesis A-descriptive,
`NEW_RESEARCH_DIRECTION.md`) was built to compute a descriptive,
non-evaluative statistic on data through the latest available price,
requiring the same `authorize_holdout=True` bypass a third time. Read at
first, by analogy to the sibling `trade-info` project's own
`FRESH_DATA_CONTRACT.md` (which exempts "regime-indicator audits" from
its pass/fail-verdict firewall), as NOT charging this third slot.

**That reasoning is now superseded, per explicit decision, and the
ledger's status changes as a result -- not the count, the STATUS.** A
one-time descriptive read might plausibly not spend a sealed window, but
`src/monitor/persistence.py` reads it on EVERY run, permanently going
forward: a window continuously displayed is not sealed in any meaningful
sense, regardless of how the individual read is characterized. It had
also already been read twice by actual pre-registered strategies (this
Study 1, swing V1) before the monitor ever existed. **Therefore: the
historical holdout (`SEALED_HOLDOUT_START = 2025-03-19` onward) is
CLOSED.** The ledger is not "2 of 3 spent, 1 remaining" but **RETIRED --
no historical holdout remains, for any hypothesis, from any project
sharing this warehouse.** The third pre-registered study slot named after
Study 1 (Value/Quality/Size construction, or a `trailing_vol_252`/
`beta_252` retest) is not fundable against a historical holdout any
longer, because there is no historical holdout left to evaluate it
against.

**All future validation, for any hypothesis in this repository, is
FORWARD-ONLY: on data arriving after 2026-09-27**, the date of this
decision. `data/holdout_access_log.txt` continues to log every read
through the now-retired window, for the audit trail -- those entries no
longer represent a resource being preserved, only a record of when data
was read.

**A second sealed momentum window, declared 2026-11-16, in its own
commit, before anything else and before any further run on current
data.**

**Everything from 2026-04-23 onward (the day after the first holdout's
last rebalance, 2026-04-22) is sealed for the momentum family.** Not to
be read for evaluation until it has accumulated at least 5 rebalance
periods -- roughly mid-2027 at the 63-trading-day cadence -- then read
ONCE, under a preregistration written before that read, the same
discipline as the first holdout.

**Rationale.** The first holdout was 5 rebalances over ~13 months,
essentially one regime (`FINDINGS.md` Section 3: all three momentum
wins came in falling markets, both losses in rising ones -- one regime
shape, not a tested cross-regime claim). A second window of comparable
size, in whatever regime arrives next, is worth far more than any
further re-analysis of the first -- it is new evidence, not a different
cut of the same evidence. It costs nothing to seal now and cannot be
created retroactively; every day this window goes undeclared is a day
closer to someone reading it informally without having decided to.

**This is distinct from the live forward basket recorded 2026-10-26**
(`PROJECT_CONTEXT.md`'s own live-state table, January 2027 check-in
pre-committed above). That is one basket, real holdings, a single
observation by construction. This is an independent historical check,
evaluated once a full comparable sample accumulates. Both are useful;
neither substitutes for the other.

**Disclosure, not a clean confirmation -- checked precisely, not
assumed.** Asked whether anything in the Bug #26 lineage check
(immediately above) read past 2026-04-22: **the final, reported
margins (3.63/3.50/5.97) did not** -- `ORIGINAL_HOLDOUT_LAST_DATE =
2026-04-22` is enforced on the `in_holdout` filter used for every
reported figure. **But an earlier run in this same session did.**
Before that pin was added, a first (buggy) version of `scripts/
run_holdout_study1_lineage_check.py` iterated the live panel's own
rebalance schedule, which has grown a 6th rebalance (2026-07-23) since
the first holdout was recorded -- that run computed and printed
2026-07-23's own momentum top-decile composition (22 total entity-
rebalance hits from the 40 lineage entities across all 6 dates, 4 of
them at 2026-07-23 specifically) and folded its realized 63-day forward
return into a 6-rebalance margin (7.31/7.22/9.24 across the three
variants) before the bug was caught and fixed. **That output already
exists in this session's own transcript** -- it is disclosed here
rather than treated as if it didn't happen. This is a small, partial,
accidental pre-seal exposure of ONE rebalance's composition and
return, not an evaluation and not a conclusion drawn from it -- the
same "partial, not zero" honesty standard `EARNINGS_DRIFT_PHASE0.md`
Section 0 used for its own seal. Whether the eventual 2027
preregistration should discount or exclude 2026-07-23 specifically on
this basis is a decision for whoever writes that preregistration, not
resolved here.

Recorded in `data/holdout_access_log.txt` alongside the retired window
and the earnings-drift seal.

**RE-DECLARED, 2026-11-17, excluding the contaminated rebalance --
superseding the start date above, not editing it.** The 2026-11-16
declaration sealed `>= 2026-04-23` without excluding 2026-07-23 by
name. Since then, that rebalance was read a SECOND time, independently,
by a different route:

- **First leak (already disclosed above):** the lineage-check script's
  own pre-fix run printed 2026-07-23's composition directly.
- **Second leak, found while pinning the Bug #11 check scripts
  (Section-7-adjacent work, same day):** `scripts/run_holdout_study1_
  bug11_check.py`, unpinned, silently absorbed 2026-07-23 into its own
  "reproduction" of the recorded holdout margin, returning **7.31**
  against the recorded **3.64** -- a gap only explainable by that one
  rebalance's own return. The same unpinned-window defect existed in
  three sibling scripts.

**The actual figures that were seen, recorded here so a later
re-derivation is recognized as a repeat, not mistaken for fresh data.
Marked CONTAMINATED -- seen twice before any seal excluded them,
carrying NO evidential weight, never to be cited as a result:**

| source | config | 2026-07-23 (or 6-period aggregate) figures |
|---|---|---|
| `run_holdout_study1_lineage_check.py`, pre-fix run | 78 same-ISIN + 40 lineage entities excluded, unpinned (6 rebalances) | Aggregate margin 7.31 (raw) / 7.22 (window-level) / 9.24 (entity-level); 2026-07-23 alone: 4 of the 40 lineage entities in the top decile (baseline), 2 (window-level) |
| `run_holdout_study1_bug11_check.py`, re-run while verifying the guard-default fix | 78/79 same-ISIN excluded only, unpinned (6 rebalances) | 2026-07-23 period-level: momentum net **-4.21%**, benchmark net **-8.61%** -- momentum beat benchmark by **+4.39pts** in this one period (both negative in absolute terms; a relative win, the same "loses less when the market falls" shape as Section 3's own finding). 6-period aggregate margin **7.31** |

**This confirms the rebalance was strongly positive -- in the relative,
margin sense, not necessarily in absolute return** -- consistent with,
not contradicting, the downside-protection mechanism already documented
in Section 3. This is reported as a contaminated observation, not as
evidence that mechanism continues to hold; one period proves nothing
either way.

**The seal is moved to the first rebalance AFTER the contaminated one,
confirmed against the live panel, not assumed: `MOMENTUM_WINDOW_2_START
= 2026-10-23`** (63-trading-day cadence from 2026-07-23). 2026-07-23
itself is permanently EXCLUDED from the second momentum window -- not
sealed, not evidential, never to be read again as if it were unseen.

**Made mechanical, not a note**: `src/data_layer/holdout.py` now
defines `MOMENTUM_WINDOW_2_START`, `MOMENTUM_WINDOW_2_CONTAMINATED_
REBALANCE`, `guard_momentum_rebalance_dates()` (raises
`MomentumWindow2ViolationError` on any rebalance date `>=
2026-10-23` unless `authorize_momentum_window_2=True` is passed
explicitly, the same convention `guard_date_range`/`authorize_holdout`
already use), and `clip_momentum_rebalance_dates()` (narrows a
rebalance-date list to exclude both the contaminated date and the
sealed window, never needs authorization). Wired into the four
Bug #11 check scripts as a second, independent layer underneath their
own manual window pin (below).

**Confirmed, not assumed, that nothing computed this session reaches
the corrected seal.** Checked directly against the live panel: the
rebalance schedule's next position after 2026-07-23 is 2026-10-23,
which sits at index 2394 of 2396 total dates in the momentum-factor
pipeline's own date list -- only 1 date exists after it, nowhere near
the 63 trading days `HORIZON_DAYS` completeness requires. Every script
run this session (including the unpinned ones that leaked 2026-07-23)
filters `rebalance_dates_all` to dates with a complete forward window
before doing anything else, which mechanically excludes 2026-10-23 --
confirmed by index arithmetic, not inferred from behavior. **Currently
exactly one rebalance (2026-10-23) exists inside the corrected seal,
it is not yet forward-complete, and nothing in this session touched
it.**

## 8. What this is not

**Not a green light to trade.** Specifically:

- **Thin sample.** 5 holdout periods (fewer than the ~6-7 pre-registered;
  universe 1,131-1,292 names/period, decile 114-130, 604 selection slots,
  336 distinct entities -- Section 2's own span statement), margin
  **3.50-5.97 points** (Section 2's own permanent range, primary 3.50)
  against a 3.0-point threshold -- a different period
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
raw standalone IC t=+2.75 (corrected from the originally-reported +2.86
after fixing a fundamentals-feed ISIN-resolution bug that had silently
excluded ~30-43 companies per rebalance date -- BUGS.md Bug #7; a
remeasurement of the same result, not a new one) that fails multiple-
comparisons correction at m=8 (Bonferroni/BH threshold 0.00625) --
suggestive, not established. None of that changed. **This finding is
about testability, not about the factor**: even a real, economically
meaningful combination effect could
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
