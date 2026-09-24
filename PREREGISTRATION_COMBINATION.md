# Pre-registration: momentum_12_1 + earnings_yield combination (equal-weight rank average)

> **STATUS: WITHDRAWN before approval. Not run. The final study slot is
> HELD, not spent.** Power analysis (see below, done on both a
> portfolio-margin and a paired-rank-IC metric before any threshold was
> frozen) found this combination cannot be validated with this project's
> data at any practically reachable sample size -- the best case tested
> needs 8 years, the more realistic cases 18-72 years. Sections below
> written as an original design draft are kept for the permanent record of
> what was considered and why it was not pursued, per this project's
> standing practice (`LICENSE_ASSESSMENT.md`'s rejected sources, Phase D's
> dead ends) -- not as an active plan.
>
> **Post-hoc annotation (2026-09-24), historical draft text below left
> unedited**: the raw t=+2.86 cited in this draft for `earnings_yield` is
> now superseded -- a fundamentals-feed ISIN-resolution bug (BUGS.md Bug
> #7) had silently excluded 166 companies from every Phase E factor; fixed,
> the corrected figure is t=+2.75 (FUNDAMENTALS.md, FINDINGS.md Section
> 12). Still fails the same Bonferroni/BH threshold either way -- this
> withdrawal's conclusion is unaffected -- but the number itself should not
> be read forward from here as current.

Originally drafted to be written and frozen before any forward data exists
to evaluate it against, with nothing changing after approval. **This would
have used the final pre-registered study slot for this dataset** (Study 1:
momentum holdout, sealed-holdout spend, PASSED. Study 2: large-cap
replication, CV-only. This would have been study 3 of the hard cap of 3
established in `PREREGISTRATION.md`) -- the slot remains unspent instead.

---

## Why a combination, and why now

The Integrated Filing coverage report and the earnings_yield-vs-momentum
diagnostic (`FUNDAMENTALS.md`) found: (1) `earnings_yield`'s own rank IC
does not survive multiple-comparisons correction on its own (raw t=+2.86,
p~0.0085, fails Bonferroni/BH at m=8, threshold 0.00625) -- it is
suggestive, not established, standing alone; (2) `earnings_yield` and
`momentum_12_1` show near-zero cross-sectional rank correlation (mean
+0.0003, std 0.15) -- independent information, not a duplicate signal; (3)
`earnings_yield`'s IC holds outside momentum's own top decile (t=+3.09
there, a test of independence, not of EY "getting stronger") -- its signal
does not live inside names momentum already selects.

None of that is evidence a combination works. It is evidence a combination
is worth the cost of testing, which is a different and weaker claim,
recorded as such.

## Why this cannot be a CV-only or historical-backtest study

Fundamentals now exist for the sealed holdout window (2025-03-19 onward) --
the Integrated Filing fetcher recovers them, corrected in `FUNDAMENTALS.md`
from the earlier "hard ceiling" framing. **This does not mean the holdout
window is available for this study.** `momentum_12_1` was already evaluated
on that exact window in Study 1, and the result is known: holdout CAGR
14.72% vs benchmark 10.85%, margin +3.87 points, all three decision-rule
conditions passed (`FINDINGS.md`). A combination tested on that window would
have one of its two legs already observed to succeed there -- partial
contamination, regardless of whether the data needed to compute the other
leg physically exists. The data existing and the data being usable for a
clean test are different things, and only the second one governs what this
study is allowed to touch.

**Validation for this study is therefore FORWARD ONLY, starting from the
pre-registration date, on quarters that do not exist yet at the time this
document is written.** A CV backtest on the 2018-2024 pre-holdout window MAY
be run and reported, but strictly as context, explicitly labelled as such
-- it does not count as the test and does not inform the decision rule
below in any way.

## Strategy -- parameter-free by construction

- **Combination**: equal-weight average of the cross-sectional rank of
  `momentum_12_1` and the cross-sectional rank of `earnings_yield`, both
  ranks computed independently per rebalance date over the same eligible
  universe, then averaged with fixed 50/50 weights.
- **No fitted weights.** A fitted weight (e.g. an IC-optimal or
  regression-estimated blend) would be a search over a parameter space,
  and a search needs the same purged fold-based cross-validation this
  project uses whenever something is fitted (`factors.ic_eval.fold_level_ic_report`)
  -- deliberately avoided here so this study can use the simpler
  independent-dates significance test and a plain forward walk-forward
  check, with no fitting-driven leakage channel to guard against.
- **Construction**: long only. Top decile (top 10%) by the combined rank,
  cross-sectional, equal-weighted within the decile.
- **Rebalance**: every 63 trading days, matching both underlying factors'
  own horizon and this project's established convention.
- **Universe**: same eligibility rules as Study 1/2 (`series='EQ'`, ISIN
  prefix `INE`/`IN9`, entity-resolved via `isin_lineage`, gap-filtered at
  `STALE_GAP_DAYS=5`), further restricted to entities with both a
  computable `momentum_12_1` and a computable `earnings_yield` on a given
  rebalance date (coverage of the smaller of the two, reported as its own
  number when the study runs, not assumed).

## Benchmarks -- both required, both fixed now, answering two different questions

The decision rule needs the combination to beat two different things, for
two different reasons, and conflating them would hide which one actually
justifies building this:

1. **Momentum-alone**: the existing, already-validated `momentum_12_1`
   top-decile strategy, same universe, same rebalance, same cost model.
   This carries the real question: does adding `earnings_yield` improve on
   what momentum alone already achieves? If not, `earnings_yield` added
   complexity without adding return.
2. **Equal-weight benchmark**: the same naive universe benchmark used in
   Study 1/2. This is a floor, not a second bar to clear better than
   momentum-alone does -- it exists only to confirm the combined strategy
   still works at a basic level, not to re-litigate whether momentum
   itself is a good strategy (Study 1 already settled that). **Originally
   drafted at +5 points, requiring the combination to beat the naive
   benchmark by MORE than momentum's own holdout margin (+3.87 points) --
   corrected before approval.** That framing double-charged
   `earnings_yield`: it would have required EY to independently repeat a
   feat momentum alone already accomplished, on top of the separate
   momentum-alone condition already asking the real question. A result of
   (say) +4.5 points over benchmark and +2.5 points over momentum-alone
   would have FAILED the benchmark condition despite the combination
   having genuinely added value over momentum -- the wrong failure mode,
   caught before freezing rather than after. The benchmark condition is
   now **+3 points**, matching `PREREGISTRATION.md`'s own floor exactly
   (same reasoning: below this is within noise for a thin sample), rather
   than inventing a new number for this study.

## Costs

Same tercile-specific, turnover-weighted cost model as `PREREGISTRATION.md`
(~23bps high-liq, ~32.5bps mid-liq, ~118bps low-liq round-trip), applied
identically to all three legs (combination, momentum-alone, equal-weight
benchmark) so the comparison isolates the factor construction, not the
cost model.

## Power analysis -- computed BEFORE either threshold was frozen, using historical variance only

Per this project's standing discipline against post-hoc threshold
selection, this section reports a power calculation computed from the
2018-2024 pre-holdout window's **margin variance only** -- the historical
**mean** margin was never computed or examined while sizing this test
(`scripts/run_combination_power_analysis.py` never calls `.mean()` on
either margin series, by construction, not just by omission from its
printed output). Using variance to size a test's power is standard
practice; using the mean would be fitting the threshold to a result
already seen, which is exactly what this avoids.

Method: per rebalance date (26 dates, 2018-2024, restricted to entities
with both `momentum_12_1` and `earnings_yield` computable -- 21,533 obs),
computed the combination's top-decile return, momentum-alone's top-decile
return, and the restricted-universe equal-weight return (gross, no costs
-- a variance-magnitude estimate, not a CAGR estimate; costs are similar
enough across the three legs, sharing a rebalance cadence and a
momentum-tilted composition, that they are not expected to change the
conclusion below). Margin = combination return minus the comparison leg,
per period.

| | std of per-period margin | SE at n=8 | per-period margin needed for t>=2.0 | rough annualized-scale equivalent (x4, additive approx.) |
|---|---|---|---|---|
| vs momentum-alone | 4.657 pts | 1.646 pts | 3.293 pts | ~13.2 pts |
| vs equal-weight benchmark | 6.032 pts | 2.133 pts | 4.266 pts | ~17.1 pts |

**Finding, stated plainly: neither the +2-point nor the +3-point annualized
threshold is statistically distinguishable from noise at n=8.** A true
+2-point annualized effect (momentum-alone) corresponds to a per-period
margin of roughly 0.5 points, giving t ~ 0.5/1.646 ~ 0.30 -- far below even
a weak t~1.5 bar, let alone t>=2.0. The same holds for the +3-point
benchmark floor (t ~ 0.75/2.133 ~ 0.35). This is not a defect in the
chosen threshold values specifically -- solving for the margin that WOULD
reach t>=2.0 at n=8 gives ~13-17 annualized points, a magnitude far outside
what a modest second-factor addition could plausibly produce, and far
larger than momentum's own validated holdout margin (+3.87 points).

**Increasing n was considered and rejected as impractical.** Solving
`std/sqrt(n) = margin/2` for n at the momentum-alone case (std=4.657 pts,
target per-period margin ~0.5 pts for a true +2-point annualized effect)
gives n ~ (4.657/0.25)^2 ~ 347 quarters -- on the order of **87 years**. No
practical n fixes this; the noise in quarterly top-decile return
differences swamps a modest, economically plausible improvement, and that
is a property of the comparison itself (two heavily-overlapping,
momentum-tilted portfolios), not of the sample size chosen.

**Consequence, adopted rather than concealed**: this study's decision rule
is an **economic-magnitude threshold, not a statistical-significance
test**, exactly as `PREREGISTRATION.md`'s own +3-point floor for Study 1
implicitly was (that document's own words: "below that is within noise for
a ~6-7 period sample" -- the same limitation, now quantified precisely
rather than judged informally). n=8 (~2 years) is kept rather than extended,
because extending it to anywhere near a well-powered sample is not a
practical option, and this project's own precedent (Study 1) already
establishes that a thin, explicitly-weak-evidence sample is an accepted way
to run a forward check when a fully-powered one is unavailable. What
changes here versus Study 1 is that the weakness is now stated with an
exact number, not a qualitative "thin base" alone.

## Power analysis, part 2: IC-based metric, computed because the margin metric itself was the problem

The portfolio-margin power analysis above was correct in its arithmetic
but was answering with the wrong instrument: a top-decile portfolio return
collapses ~1,200 stocks into one number per quarter, discarding almost all
the cross-sectional information the factors actually carry. Rank IC uses
the entire cross-section every date. Recomputed on that basis, same
discipline (no mean IC computed or examined while sizing this test --
`scripts/run_combination_ic_power_analysis.py` never calls `.mean()` on
any IC or difference series), same 2018-2024 window, same 26-date,
21,533-obs restricted universe:

| | std | SE at n=8 |
|---|---|---|
| IC of combined rank | 0.1004 | 0.0355 |
| IC of momentum_12_1 alone | 0.1259 | 0.0445 |
| **paired difference** (IC_combo - IC_mom, same date) | **0.0848** | **0.0300** |

The paired difference is the right comparison, not the two ICs separately
-- it removes the common cross-sectional-dispersion component that moves
both ICs together on any given date, leaving only the part attributable to
`earnings_yield`'s actual contribution. It worked as intended: paired std
(0.0848) is noticeably tighter than either individual IC's std (0.1004,
0.1259), confirming real shared variance was removed.

**Paired IC difference needed for t>=2.0 at n=8: 0.060.**

**n needed for t>=2.0 to detect a given true paired IC difference:**

| true difference | n needed | in years |
|---|---|---|
| 0.01 | 287.7 quarters | ~71.9 years |
| 0.02 | 71.9 quarters | ~18.0 years |
| 0.03 | 32.0 quarters | ~8.0 years |

**This is a real improvement over the portfolio-margin metric** (which
needed ~87 years for a comparable-magnitude effect) -- pairing on IC
recovers meaningfully more power per unit of sample size, exactly as
expected from using the full cross-section instead of one decile cut.
**It is not enough.** Even the most favorable case tested (a true 0.03
paired IC difference, arguably a generous assumption given
`earnings_yield`'s own modest standalone IC) needs 8 years -- four times
the original 2-year design, not "n=8 or a modest multiple" by any
reasonable reading of that phrase. The more conservative, arguably more
realistic differences (0.01-0.02) need 18 to 72 years. No metric change
rescues this at a practical n.

## Conclusion: this combination cannot be validated with the data available at any practically reachable sample size

Per the pre-committed logic this power analysis exists to serve: since
IC-based testing (the better of the two metrics tried) is also hopeless at
any reachable n, the honest conclusion is that this combination cannot be
validated here, not that a further metric or threshold change would fix
it. **The final pre-registered study slot for this dataset is NOT spent on
this test.** The slot is held, not burned on a multi-year wait that would
produce an uninterpretable number regardless of outcome.

This is not a verdict on `earnings_yield` itself. The diagnostic findings
already on record in `FUNDAMENTALS.md` stand exactly as reported: near-zero
correlation with momentum, IC holding outside momentum's top decile,
standalone IC suggestive but not surviving multiple-comparisons correction.
What this conclusion adds is narrower and specific: **there is no
statistically interpretable way to test whether combining the two adds
value, given this project's data size and the noise level of both the
portfolio-return and rank-IC metrics at this universe size.** A different
dataset (a larger cross-section, a longer history, or both) could in
principle have enough power; this one does not, and pre-registering a test
that cannot pass would spend the project's last slot on a result nobody
could interpret.

**Status: WITHDRAWN before approval, not run, study slot held.** This
document is kept as the permanent record of what was considered and why it
was correctly not pursued, per this project's own standing practice of
recording paths not taken (Phase D's sector-classification dead ends,
`LICENSE_ASSESSMENT.md`'s rejected sources) rather than deleting them.

## Everything below this line is the ORIGINAL DESIGN DRAFT -- superseded by the conclusion above, kept for the record only, none of it is an active plan

## Decision rule -- as originally drafted, NOT adopted

Evaluated **only after 8 forward quarters have completed** (see the timing
section below for why 8 and what "completed" means). The combination is
read as **justified** only if BOTH hold:

**(a) Margin over momentum-alone, net of costs, of at least 2 percentage
points annualized CAGR**, measured over the same 8-quarter forward window,
same cost model. This is the real question -- does `earnings_yield` add
anything over the already-validated single-factor strategy.

**(b) Margin over the equal-weight benchmark, net of costs, of at least 3
percentage points annualized CAGR** over the same window -- a floor
confirming the combined strategy still works at a basic level, matching
`PREREGISTRATION.md`'s own floor exactly, not a bar requiring the
combination to out-do momentum's own historical achievement.

**Both numbers are economic-magnitude floors, not statistically powered
thresholds** -- per the power analysis above, neither would reliably
separate a true small effect from noise at n=8, and no practical increase
in n changes that. A pass here is read as "the magnitude looks right and
nothing is obviously broken," not "this is statistically established" --
consistent with, and no stronger a claim than, how Study 1's own holdout
pass was read.

Failing either condition means the combination is not adopted. Both
conditions were fixed before any forward data exists to compute either
number, per this project's standing discipline against post-hoc threshold
selection.

## Partial outcomes -- pre-committed readings, not a judgment call at quarter 8

Both conditions are required for the combination to be adopted, but each
partial outcome gets its own pre-committed reading rather than being
collapsed into a single "failed" with no further comment:

**Passes momentum-alone (a), fails benchmark floor (b)**: mechanically
unlikely -- momentum alone already clears the +3-point benchmark floor by
a wide historical margin (+3.87 points on the holdout), so a combination
that beats momentum-alone by +2 points would need momentum-alone itself to
have badly underperformed the benchmark in this specific forward window
for the combination to still miss the floor. If it happens anyway: read as
evidence that momentum itself entered an unusual regime during this
forward window (matching the already-documented 2020 regime-risk finding
that momentum can underperform in some conditions), not as a validation or
an indictment of the combination. Not adopted. Momentum-alone's own
separate, already-established validity is unaffected -- this reading
exists precisely so a bad quarter for momentum isn't mistaken for a
finding about `earnings_yield`.

**Fails momentum-alone (a), passes benchmark floor (b)**: the scenario the
correction above exists to handle correctly. Read as: the combination
works at a basic level (clears the naive floor) but `earnings_yield` did
not add measurable value over momentum alone in this window. Not adopted
over pure momentum-alone -- but explicitly **not** read as evidence against
`earnings_yield`'s underlying diagnostic findings (near-zero correlation
with momentum, IC holding outside momentum's top decile), which remain
what they are: suggestive, not established, per the multiple-comparisons
correction already on record. One failed forward check at n=8 does not
retroactively strengthen or weaken a correction that was about a different
sample (2018-2024 CV) and a different question (standalone significance).

**Fails both**: not adopted, reported plainly, no further reading needed
beyond the sample-size caveat already stated.

**Passes both**: read per the "Interpretation, pre-committed" section
below -- value added, on a thin, explicitly underpowered sample, stated as
such and not overclaimed.

## Timing -- stated as a calendar mechanism, not a vague "later"

Pre-registration date: the date this document is approved (recorded at
approval, not backdated). **8 forward quarters** at a 63-trading-day
rebalance is approximately 2 years of live/prospective data -- collected
going forward from approval, not sourced from any window this project has
already observed prices or returns for. The verdict date is therefore
**approximately 2 years after approval**, computed exactly once the
approval date is fixed and stated in this document's approval record.

## Explicit rule: no interim judgment before quarter 8

Interim quarters (1 through 7) are **logged, not judged**. Each completed
quarter's combination return, momentum-alone return, and benchmark return
are recorded as they occur, in a running log, exactly as measured -- no
partial verdict, no "trending toward pass/fail" commentary, no early
stopping in either direction. A combination that looks spectacular after 3
quarters is not adopted early; a combination that looks poor after 3
quarters is not abandoned early. This mirrors Study 1's own discipline
against reading a thin sample as more informative than it is, applied here
to prevent the opposite failure mode -- optional stopping on a live,
still-accumulating result, which inflates false-positive and false-negative
rates alike if the stopping point is chosen after seeing the data rather
than fixed in advance.

## Sample size, stated upfront

8 non-overlapping quarters is a thin base, on the same order as Study 1's
own ~6-7 period holdout sample -- and, per the power analysis above,
explicitly too thin to statistically distinguish either decision-rule
threshold from noise, not merely "thin" in a qualitative sense. Recorded
now, before any forward data exists: **a pass at this sample size is weak
evidence the combination adds value, and a fail is equally weak evidence
that it doesn't** -- consistent with how Study 1's result was interpreted,
not a stronger claim licensed by this being the final study slot.

## What is NOT being tested

Only the equal-weight `momentum_12_1` + `earnings_yield` rank combination,
exactly as specified above. Not tested here: any other weighting scheme,
any other factor pairing (e.g. `margin_trend`, which showed a borderline
raw t=+2.26 but also failed multiple-comparisons correction), any fitted or
optimized blend, any use of the untestable balance-sheet factors (`pb`,
`roce`, `roe`, `de`, `interest_coverage`) which remain UNTESTED per
`FUNDAMENTALS.md`, not weak or inconclusive. A future pre-registered study
would be required for any of these, and none is available -- this is the
final slot for this dataset.

## Interpretation, pre-committed

**If both conditions pass**: the combination is read as adding real value
over both a naive benchmark and the already-validated single-factor
strategy, on a thin, explicitly underpowered sample (see the power
analysis above -- a pass here is a magnitude check clearing an
economically-motivated floor, not a statistically established result). The
report states this alongside the sample-size and power caveats above, not
after them, and alongside the fundamentals data-quality caveats already on
record (Integrated Filing coverage 79.4% of the actively-traded universe,
ISIN-parsed per-document, restatement rate 11.4% in the new format).

**If either condition fails**: the combination is not adopted. Reported
plainly, with both margins shown regardless of which condition failed. No
appeals, no re-weighting, no re-running on a different rebalance cadence,
no partial credit for beating one benchmark but not the other. Momentum-
alone's own validated result (Study 1) is unaffected either way.

## Procedure

- Combined rank computed via `factors.momentum.compute_momentum_12_1` and
  `factors.fundamentals_factors` earnings_yield construction, exactly as
  already coded -- no re-derivation, no re-tuning between now and the
  first forward observation.
- Forward returns computed via `factors.target.compute_forward_return`,
  same gap-awareness, applied prospectively as each quarter's data becomes
  available -- never backfilled from data that predates this document's
  approval date.
- Interim log maintained in a dedicated, append-only record (not this
  document, which stays frozen) -- one row per completed quarter: combination
  return, momentum-alone return, benchmark return, all net of costs.
- Verdict computed **exactly once**, at quarter 8, applying both fixed
  conditions above in the stated order, reported alongside both margins
  regardless of outcome.
- Executed with no access to, and no computation touching, the sealed
  price holdout's already-observed window (2025-03-19 through the
  pre-registration approval date) for anything other than universe
  construction and factor definitions already frozen before this document
  -- the forward window begins strictly after the approval date.

---

**This document was never frozen and none of the procedure above was run.**
See the STATUS note at the top and the "Conclusion" section: the power
analysis found this combination cannot be validated with this project's
data at any practically reachable sample size, on either metric tried. The
final study slot for this dataset remains held, not spent.
