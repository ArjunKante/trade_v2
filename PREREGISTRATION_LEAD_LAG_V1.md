# Cross-Liquidity-Tier Return Propagation in NSE Equities, Study V1

## Provenance

**This is a brand-new research family. No prior trial exists in this
project under this name.** Phase 0 (`lead_lag/LEAD_LAG_RECONNAISSANCE.md`),
Phase 1 (`lead_lag/DATA_AUDIT_LEAD_LAG.md`), and Phase 2
(`lead_lag/LEAD_LAG_FEASIBILITY.md`) preceded the original version of this
document (committed alone, commit `e1418a661a769c9f134d750bbe95dc1a831b0305`,
2026-11-07), all read-only against the existing warehouse, no strategy
code written before that commit.

**Two binding scope decisions were made by the human user before the
original version was drafted:**

1. **Intraday scope is capped at the existing `data/fibo_intraday.duckdb`
   universe** -- 386 distinct entities, 2016-10-04 to 2026-09-18. No new
   Angel One fetch.
2. **Grouping is liquidity-tier-based, not sector-based.** `DATA_AUDIT_LEAD_LAG.md`
   found no point-in-time sectoral index series and no point-in-time
   sector/industry classification anywhere in this repository (the same
   defect shape as the already-documented Bug #12).

---

## AMENDMENT LOG (2026-11-08) -- read this before the rest of the document

This document was amended once, following an independent methodology
review of the original (`e1418a66`) version. **The amendment process
itself surfaced a more serious problem than the one the review set out to
check** -- recorded here first, in order of actual severity, not in the
order the review happened to ask about it.

### 1. CRITICAL, newly discovered during this amendment (not by the original review): the original Section 8/9 `S_leader(t)` was algebraically degenerate

While building the real data needed to answer the review's power-calculation
question, `lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Section 3.0
found that the original signal construction --
`AR_leader(i,k) = r(i,k) - B_leader(k)` where `B_leader(k)` excluded only
`i` from the **same leader group**, then `S_leader(t) = mean_i(S_i(t))`
averaged back across that **same leader group** -- is **identically zero
by construction**, for any data, always: a leave-one-out deviation from a
group's own mean, averaged back across that same group, telescopes to
exactly zero (the same identity that makes OLS residuals against a
constant sum to zero). Measured directly on real data: mean `-1.8e-21`,
sigma `4.2e-20` -- machine-epsilon noise, 16+ orders of magnitude below one
basis point, across 230 real trading days. This was never caught in
Phase 2 (`LEAD_LAG_FEASIBILITY.md`'s own MDE calculation used only the
**follower-side** forward-return sigma, never `S_leader(t)`'s own) or in
the original preregistration (Section 18 explicitly deferred computing
`S_leader`'s sigma to Phase 6 -- nobody had actually computed it before
this amendment).

**Fix adopted in this amendment**: Section 8/9 are rewritten so the
leader side is benchmarked against the **follower pool**, not against
other leaders. `AR_leader(i,k) = r(i,k) - B_follower_pool(k)`, where
`B_follower_pool(k)` is the plain equal-weighted mean return across that
month's **entire follower tier** (no leave-one-out needed here, since a
leader is never a member of the follower pool -- there is no
self-contamination risk to guard against on this side). This makes
`S_leader(t)` resolve to (a rescaling of) the cumulative 5-minute return
**spread between the leader portfolio and the follower portfolio** --
algebraically guaranteed non-degenerate (verified below, Section 8), and
arguably a more literal operationalization of the hypothesis ("leaders
moved and followers have not yet caught up") than the original
construction was.

### 2. Selection null redesigned (`matched random-leader-portfolio null` replaces the follower-permutation null)

The independent review found the original Section 16b (random follower
reassignment) was likely a **near no-op**: `S_leader(t)` is not
follower-specific, so permuting which follower label attaches to a given
row does not change the set of (signal, response) pairs the regression
actually sees. Replaced with a null that varies the thing that actually
matters -- which stocks constitute "leader" -- see Section 16b below.

### 3. MDE/power (Section 17) rewritten; no unconditional PASS re-claimed

The original MDE (1.4-4.2 bps) was computed from raw individual-stock
1-minute-bar variance and a naive day-count, not from the actual
dependence structure of the regression coefficient the estimand uses.
Combined with finding #1 above (the predictor itself didn't exist as
specified), **no version of this document before today's amendment had a
working power calculation at all.** Section 17 is rewritten to report
real, computed numbers where they exist and state plainly where they do
not. **This amendment does not claim a renewed feasibility PASS.** The
breadth correction (real ~40 leaders / ~160 followers per month,
replacing the stale 77/309 lifetime-turnover proxy) and the per-minute
breadth floor are solid, adopted outright. The dependence-aware SE/power
question is reported as **conditional and provisional**, pending a
Phase 4 re-run of the placebo diagnostic on the corrected signal from
fix #1 -- see Section 17.

### 4. Trial ledger made machine-enforced

`lead_lag/trial_ledger.json` + `lead_lag/ledger.py` (7 passing tests,
`lead_lag/test_ledger.py`) now hold the family's 6 registered trials as a
computed fact (`len(trials)`), not a hand-typed number in prose. Phase 4
code is required to call `ledger.assert_registered(config_key)` before
any gate and `ledger.record_gate_run(...)` after -- see Section 15.

### 5. Hypothesis reframed; title changed

Renamed to **"Cross-Liquidity-Tier Return Propagation in NSE Equities"**.
The original title and Section 1 text ("cross-stock lead-lag
propagation... information diffusion") overclaimed what a sector-agnostic,
liquidity-tier-only design can actually test -- see Section 1.

### 6. Monthly tier breadth computed from the real construction; per-minute breadth floor added

`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Tasks 1-2 computed the
actual Section 6 construction (not Phase 2's lifetime-turnover proxy) --
see Section 6 and Section 8.

### 7. Free parameters consolidated and frozen

See Section 23 (new).

### 8. Master spec committed

`lead_lag/MASTER_SPEC_LEAD_LAG.md` now holds the governing research
directive verbatim, with provenance. "Part X.Y" citations throughout this
document now resolve to a real, committed file.

### 9. Second pass: adversarial re-review of this amendment's own first draft found and fixed two further issues

Per the user's explicit procedure, this amendment's Section 16b and
Section 17 were sent to a fresh adversarial reviewer before commit. Two
concrete problems were found in the first draft and are fixed in the
version below, not merely caveated: (a) Section 16b's candidate pool
(top `2*n_leaders` by turnover) overlapped the true leader tier by ~50%
on average (a hypergeometric-draw consequence never checked in the first
draft), biasing the null conservative, while independently redrawing a
fresh random portfolio every month within a repetition narrowed the
null's spread, biasing it anti-conservative in the opposite direction --
fixed by making the candidate pool disjoint from the true tier and
requiring both a per-month-redraw (B1) and a fixed-selection-rule (B2)
variant to independently pass; (b) Section 17's Bonferroni MDE multiplier
was arithmetically wrong (3.1909, inherited uncorrected from the
supporting pilot document; the correct value is 3.47988), and Section
21's "comfortably below the economic floor" language was left as the one
undefined, outcome-adjacent judgment call in an otherwise strictly frozen
document -- both corrected, with a specific numeric margin rule (>=5x
proceed, 1-5x stop for guidance, <1x abandon) frozen into Section 23
before any real Phase 4 number exists.

**What this amendment does NOT do**: it does not run Phase 4. It does not
run any outcome analysis (no regression anywhere in the supporting
documents pairs a leader signal with a contemporaneous follower response
for the real, corrected signal -- the degeneracy check and the placebo
pilot are diagnostic only, per `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`'s
own explicit scope boundary). It does not claim the hypothesis has
passed, is well-powered beyond what is stated, or is ready for
implementation without the remaining open items below being resolved.
**Phase 4 still requires the user's explicit approval, after this
amendment itself is reviewed.**

This amendment is committed as a **new commit**, not an amendment to or
replacement of commit `e1418a66` -- that commit remains in git history
unchanged, per the requirement to preserve original provenance.

---

## AMENDMENT 2 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 10 calendar and leader-breadth resolution

**Status: prospective methodology clarification, prepared for human review
following explicit approval of four Decision 10 resolutions. Not yet
committed -- this edit exists only in the working tree, pending review.**
If approved as-is, this would become a new commit layered on top of
`9f71b65` (itself preserved unchanged, as `e1418a66` was preserved by
that amendment).

**Chronology, stated explicitly so this amendment is never read as
retroactive preregistration**: the calendar-coverage and leader-breadth
feasibility measurements this amendment resolves (`lead_lag/
DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md`,
`lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md`, and
the calendar/breadth audit reconciled in `lead_lag/
DECISION_10_RECONCILIATION_ADDENDUM.md`) were performed **before** the
four approvals below and **before** this amendment was drafted. This
amendment does not claim those measurements were preregistered under the
definitions it now states -- they were exploratory, unregistered
feasibility work, exactly as `lead_lag/
DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md` already records for the two
basket-construction configurations examined in that same chain. This
amendment is a **prospective** methodology clarification: the definitions
below govern going forward; they do not reach backward to characterize
measurements already taken as having been governed by them at the time.

**Four approved resolutions, recorded here**:

1. **Leader breadth eligibility** (Section 8): `n_t_breadth` counts
   present-valid bars only; a forward-fillable absent bar does not count
   toward the `0.80` breadth floor. `n_t_return`, the divisor actually
   used in `S_leader(t)`, remains governed by Decision 17's existing,
   unchanged return-construction rules. These are two distinct counts
   and must never be conflated.
2. **Retention/coverage denominator** (Section 12): the governing
   trading-session calendar is established jointly by
   `src/data_layer/nse_holidays.py`/`data/raw/nse_cm_holidays.pkl`
   (holiday classification) and explicit special-session verification --
   not by raw `bars_1min.trade_date` presence alone. The governing
   denominator is **2,457** verified trading-session dates, not the raw
   archive's 2,468.
3. **Weekend special sessions** (Section 12): four verified genuine
   weekend special-trading-session dates (`2020-02-01`, `2024-01-20`,
   `2025-02-01`, `2026-02-01`) remain included in the governing calendar,
   scheduled observations, retention denominators, and date/month/year
   coverage, despite falling on weekends. No blanket weekday-only filter
   is applied.
4. **Governing calendar source** (Section 12): `src/data_layer/
   nse_holidays.py` + `data/raw/nse_cm_holidays.pkl` are adopted as the
   starting authority for holiday classification in this family, combined
   with the special-session verification in resolution 3. Neither file is
   modified by this amendment. A date with ambiguous session status is
   flagged, not silently classified.

**What this amendment does NOT do**: it does not change the approved 70%
follower-breadth candidate (Decision 10's numerical threshold remains
open pending separate finalization). **[STATUS UPDATE, AMENDMENT 5 LOG,
2026-11-14: Decision 10's numerical threshold is no longer open -- it is
now APPROVED at 70%. This sentence is preserved unedited as an accurate
record of the threshold's status at the time AMENDMENT 2 was drafted.]**
It does not change the fixed
monthly roster, Option 2's frozen-subset construction, Decision 17's
return-construction rules, the day-level 50% leader floor, the approved
09:20 anchor (Decision 11 -- **this passing reference describes a
candidate anchor only; Decision 11 itself remains OPEN. An intermediate
edit in this working tree briefly claimed AMENDMENT 5 LOG, Section 2
confirmed this anchor; that claim was incorrect and has been corrected --
see AMENDMENT 5 LOG, Section 2, for the correction**), or any other previously approved decision. **[STATUS UPDATE, AMENDMENT 6 LOG, 2026-11-14 (later same day): Decision 11 has now been approved at `09:15`, by explicit user decision following a final targeted first-bar verification -- see AMENDMENT 6 LOG below. This passing reference to "the approved 09:20 anchor" turns out, in retrospect, to have been accurate -- but that is a coincidence of this later approval, not a resolution this amendment itself ever provided; at the time AMENDMENT 2 was drafted, and until AMENDMENT 6, the anchor was not settled.]** It
does not change the multiple-testing denominator, the trial ledger, or
alpha allocation **as part of this amendment's own scope** (Section 15,
Section 23's "Multiple-testing denominator" row, and
`lead_lag/trial_ledger.json` are all untouched by Amendment 2
specifically). **This statement describes Amendment 2's own scope only
and must not be read as meaning the denominator/alpha never changes --
Decision 16's separate multiplicity/alpha resolution is recorded in
AMENDMENT 3 LOG below, drafted the same day.** It does not
authorize Phase 4, a primary gate, or any outcome inspection. It does not
backdate registration of anything.

---

## AMENDMENT 3 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 16 multiplicity-family and future primary-gate alpha resolution

**Status: prospective methodology amendment, prepared for human review
following explicit human approval of the Decision 16 multiplicity
treatment. Not yet committed -- this edit exists only in the working
tree, pending review, layered on top of AMENDMENT 2 LOG (also not yet
committed) and `9f71b65` (committed, unchanged).** This is a separate
amendment from AMENDMENT 2 -- AMENDMENT 2 resolves Decision 10 (calendar
and leader-breadth questions) and explicitly does not touch multiplicity
or alpha; this amendment (3) resolves Decision 16 (multiplicity-family
membership and the future primary-gate alpha) and does not touch
anything AMENDMENT 2 resolved.

**Chronology, stated explicitly**: the empirical examinations underlying
this amendment (the Decision 10 completeness measurement that produced
Option 1's infeasibility finding and exercised Option 2's construction)
occurred before this amendment, and before Option 1/Option 2 were ever
formally registered. This amendment does not claim those measurements
were preregistered, and does not claim that Option 2's subsequent
selection as basket-construction methodology validates its predictive
performance in any way -- selection is a methodology choice, not a
primary-gate pass, and no predictive statistic was computed in reaching
it.

**Approved accounting treatment, recorded here**:

1. The six existing `lead_lag/trial_ledger.json` entries remain
   unchanged. The ledger is **not** edited by this amendment; `ledger.py`,
   its tests, and `assert_registered`/`record_gate_run` are not modified.
   Neither `basket_construction:option1_full_completeness` nor
   `basket_construction:option2_frozen_subset_fallback` is added to the
   ledger -- **neither configuration is retroactively registered**, and
   both therefore remain structurally ineligible for any future gate
   execution under the existing, unmodified `assert_registered`
   enforcement.
2. **Option 1** (`basket_construction:option1_full_completeness`) was
   examined before registration and is classified an **unregistered
   Phase 1 feasibility kill** -- it counts as **one formal trial** under
   the approved accounting treatment, notwithstanding the
   registration-timing deviation, which is disclosed here rather than
   concealed.
3. **Option 2** (`basket_construction:option2_frozen_subset_fallback`)
   was examined before registration and subsequently selected as the
   basket-construction methodology by human decision. It is **not a
   formal trial** -- selection is not equivalent to a Phase 1 kill or to
   reaching a preregistered predictive gate.
4. Both Option 1 and Option 2 are included in the same **multiplicity
   family** as the six existing configurations, as a deliberately
   conservative policy choice -- Option 2's inclusion is a
   multiplicity-control decision, not a reclassification as a formal
   trial.
5. **Formal trial count: 7** (6 ledger-registered + Option 1). **Operative
   multiplicity-family denominator: 8** (6 + Option 1 + Option 2). These
   are two different numbers answering two different questions and must
   not be conflated; see Section 23's three-row distinction.
6. **The future primary-gate significance level is prospectively changed
   to `alpha = 0.05/8 = 0.00625`, two-sided** -- see Sections 15, 17, 20,
   and 23 for the exact operative-text changes and the full recalculation
   of every alpha-dependent quantity this change touches. The historical
   `0.05/6 ~= 0.0083` figure, and every number derived from it, remains in
   this document, explicitly labeled historical/superseded, not deleted.
7. This amendment does not change the 20bps economic significance floor,
   the test sidedness, the statistical method, the bootstrap methodology,
   the sample/inference methodology, or any previously approved control
   or sensitivity specification -- only the multiplicity divisor and its
   direct numerical consequences change.
8. This amendment does not authorize Phase 4, a primary gate, or any
   outcome inspection, and does not imply that Option 1's or Option 2's
   examination, selection, or inclusion in the multiplicity family
   establishes anything about predictive validity, unbiasedness, or
   profitability for either configuration.

Full accounting detail: `lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md`.

---

## AMENDMENT 4 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 13 return-convention approval, and a proposed (not yet approved) Momentum_F same-session rule

**Status: one approved decision recorded, plus one new proposed decision
awaiting human review. Not yet committed -- this edit exists only in the
working tree, pending review, layered on top of AMENDMENT 2 LOG and
AMENDMENT 3 LOG (also not yet committed) and `9f71b65` (committed,
unchanged).** This amendment is a separate amendment from 2 and 3 -- it
touches neither the Decision 10 calendar/breadth questions nor the
Decision 16 multiplicity/alpha accounting; it resolves Decision 13 (the
return-convention question) and records a new, explicitly unapproved
proposal addressing a Momentum_F endpoint conflict discovered while
auditing Decision 13's consequences.

**Chronology, stated explicitly**: `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`
and `lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md` were completed before
this amendment and are unchanged by it. `lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md`
was completed after those two, and it is the document that first reported
(a) that `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` still carried
Decision 13 as "OPEN (technically recommended, not approved)" despite the
convention already governing that audit's own analysis, and (b) the
Momentum_F early-session arithmetic conflict resolved (as a proposal, not
yet an approval) below. That audit report is **preserved unchanged** --
its historical observation that Decision 13 was still open when it was
written was accurate at the time, and is not retroactively rewritten here.
This amendment, and the reconciliation it implements, is recorded
separately in `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`.

### 1. Decision 13 -- APPROVED, 2026-11-14 (user decision, not a methodology-review recommendation)

**The exact endpoint-price return convention is approved, by explicit user
decision on 2026-11-14:**

```
r_i(a,b) = P_i(b) / P_i(a) - 1                 [per frozen-eligible constituent i]
PortfolioReturn(a,b) = mean_i( r_i(a,b) )       [arithmetic mean across the frozen eligible constituents]
```

Applied consistently to `R_L(t)`, `R_F(t)`, `Y(t,h)`, and `Momentum_F(t)`
(all four defined with this construction in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Sections 4 and 6). This
is a **price return**, not a total return -- dividends are excluded, for
the reasons already stated in that proposal's Section 4A.

**This approval is prospective, not retroactive.** It governs Phase 4
implementation going forward. It does **not** mean this document's own
Section 8/9 construction -- `S_i(t) = sum_{k=t-4}^{t} AR_leader(i,k)`, a
sum of five 1-minute per-bar abnormal returns, fixing the original
degeneracy found in the 2026-11-08 amendment above -- was ever computed
using the exact-endpoint convention, or that any real-data measurement
already reported in this family's documents (e.g. the 3.92bps diagnostic
sigma cited in Section 8) used anything other than the sum-of-per-bar
construction it was actually computed with. **Section 8 and Section 9's
text, formulas, and worked measurements above are preserved exactly as
originally written and are not edited by this amendment.** They are now
labeled, here, as the **historical, registered construction**, superseded
*prospectively* by the Decision 13 convention for any Phase 4
implementation that has not yet been written. If Section 8/9's own
construction is ever formally retired rather than superseded, that would
require its own separate, explicit decision -- not implied by this one.

**What this resolves**: `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`'s
own decision-log item 13 and Section 4E ("RECOMMENDED, not APPROVED") are
updated to reflect this approval in that document directly (see that
file's own dated status-update note). This preregistration's Section 23
frozen-parameters table gains one new row recording the approved
convention (below).

### 2. Momentum_F(t) same-session endpoint conflict -- PROPOSED RULE, NOT YET APPROVED (Decision 22)

**This is a proposal awaiting explicit human approval. It is not approved
by this amendment and must not be read as settled.**

`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` Section 5.3
found a genuine arithmetic conflict in the governing design documents:
`Momentum_F(t)`'s two required endpoints are at clock times `t-35` and
`t-5` (the exact-endpoint convention needs only these two prices, not
every bar between them). The earliest documented signal-window anchor --
`t=09:19` if `09:15` is a valid regular-session bar, or `t=09:20` if
`09:16` is the first valid bar instead (Decision 11, itself still
genuinely unresolved -- see that decision's own open status, unchanged by
this amendment) -- requires a `Momentum_F` start endpoint at `t-35`, which
lands at approximately `08:45`/`08:46`: **before the regular session opens
at either candidate first-bar time.** No bar exists there. No document
read for this amendment specifies how an implementation should resolve
this.

**Proposed rule (Decision 22), for explicit human review -- not yet
approved**:

1. Both `Momentum_F(t)` endpoints (`P_j(t-35)` and `P_j(t-5)`, for every
   follower `j` in the frozen basket) must be valid observations belonging
   to the **same trading session and the same trade date**.
2. Both endpoints must separately satisfy the applicable Decision 17
   endpoint-validity rules (present-valid, or permitted forward-fill under
   Decision 17's existing `<180`-second rule -- not a new rule invented
   here).
3. **No cross-session endpoint pairing is permitted.**
4. **No previous-session fallback, nearest-available-bar substitution
   across a session boundary, clamping, padding, or silent endpoint
   replacement is permitted**, for either endpoint, under any
   circumstance.
5. If either required endpoint is unavailable or invalid under rules 1-2,
   `Momentum_F(t)` is **unavailable** for that observation.
6. An observation with an unavailable `Momentum_F(t)` is **excluded**
   under the frozen eligibility policy (the same unified-eligibility
   framework governing `t-35, t-5, t` elsewhere in this family's
   documents) -- **no imputed or substituted `Momentum_F` value is ever
   used.**
7. The same frozen follower basket and constituent-eligibility rules
   (Section 3 of the proposal, decision item 18 above) continue to apply
   unchanged -- this rule governs **endpoint validity**, not basket
   membership, and authorizes no future-informed constituent replacement
   or reweighting.

**Minimum-anchor arithmetic (conditional, not a guarantee of a complete
basket at that time)**:

- If `09:15` is the first valid regular-session bar: the start endpoint
  `t-35` must be at or after `09:15`, so `t >= 09:15 + 35 minutes = 09:50`.
  **Earliest possible anchor: `09:50`.**
- If `09:16` is the first valid regular-session bar instead: `t-35 >=
  09:16`, so `t >= 09:51`. **Earliest possible anchor: `09:51`.**

**These are conditional lower bounds on `t`, derived purely from the
`Momentum_F` endpoint requirement -- they do not by themselves resolve
Decision 11's own open anchor question (`09:15` vs. `09:16`,
`09:19`/`09:20` vs. `09:20`/`09:21`), and they do not guarantee a complete
basket, valid signal-window endpoints, or valid `Y(t,h)` forward endpoints
at those minutes.** They establish only that any observation requiring
`Momentum_F(t)` as a control cannot have `t` earlier than `09:50`/`09:51`
without violating rule 1 above -- i.e., the documented `09:19`/`09:20`
earliest-signal-anchor figures (Decision 11, Section 5 of the proposal)
describe the earliest anchor for the bare signal window only, and were
never checked against this requirement before now.

**What this proposed rule does NOT do**: it does not approve itself. It
does not change the approved 09:20 anchor language elsewhere in this
document (that reference, and Decision 11's own open status, are
unchanged and not reconciled by this amendment -- a separate,
pre-existing inconsistency between this document and several Decision 10/
17 documents over whether Decision 11's anchor is settled, noted but not
resolved here). It does not change the frozen monthly roster, Option 2's
construction, the existing Section 12 forward-window-crosses-15:30
exclusion for `Y(t,h)`, the 70% follower-breadth candidate, the trial
ledger, or the multiplicity/alpha accounting. It does not authorize Phase
4, a primary gate, or any outcome inspection. **It does not become
operative unless and until the user explicitly approves it.**

**[STATUS UPDATE, AMENDMENT 5 LOG, 2026-11-14: this proposed rule (Decision
22) is now APPROVED, with one wording refinement to rule 6 -- see
AMENDMENT 5 LOG, Section 3. Decision 11's "own open status" referenced
above is UNCHANGED and remains OPEN -- an intermediate edit in this
working tree briefly, incorrectly claimed Decision 11 was also resolved at
`09:15`; that claim was never approved by the user and has been corrected,
see AMENDMENT 5 LOG, Section 2. The pre-existing inconsistency this
paragraph flagged (between this document's passing "approved 09:20 anchor"
reference and several Decision 10/17 documents stating Decision 11 is
open) therefore remains unresolved, exactly as this paragraph originally
stated; the paragraph above is preserved unedited as an accurate record of
this amendment's own not-yet-approved status at the time it was
drafted.]**

**[FURTHER STATUS UPDATE, AMENDMENT 6 LOG, 2026-11-14 (later same day):
Decision 11 is now APPROVED at `09:15`, by explicit user decision -- see
AMENDMENT 6 LOG below. The conditional minimum-anchor arithmetic in this
section (`09:50` if `09:15`; `09:51` if `09:16`) therefore resolves to a
single, unconditional value: `t >= 09:50`. This is a fixed lower bound
only -- it does not by itself guarantee a complete basket or valid
endpoints at that minute, which remain governed by Decision 22's rules
1-6 above, unaffected by this update.]**

### 3. Section 23 update

A new row is added to Section 23's frozen-parameters table recording the
approved Decision 13 convention (below). No row is added for the proposed
Momentum_F rule, because Section 23 is a table of parameters already
frozen by approval -- an unapproved proposal does not belong there until
approved; it is instead recorded in full in this log and in
`lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`.

---

## AMENDMENT 5 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decisions 10 and 22 approved; Decision 11 CORRECTED back to OPEN; Decision 13 reaffirmed unchanged

**CORRECTION NOTICE (2026-11-14, same day, following a documentation-repair
task)**: this amendment, as originally drafted, incorrectly recorded
Decision 11 as approved at `09:15`. **That was a documentation error. The
user never approved Decision 11. Decision 11 remains OPEN** -- the
`09:15`-vs-`09:16` first-valid-regular-session-bar question is unresolved.
Section 2 below, and every consequence derived from the false approval
(the "unconditional" `Momentum_F` anchor in Section 3, and the Section 23
table rows), are corrected in place, with the erroneous original text
retained alongside each correction, not deleted, so the history of how the
error entered the document is not silently erased. **Decisions 10 and 22
remain correctly approved and are unaffected by this correction** -- they
are separate decisions from Decision 11.

**Status: two further decisions approved by explicit human user decision
on 2026-11-14 (Decision 10, Decision 22); Decision 11 was never approved
and is corrected back to OPEN below. Not yet committed -- this edit exists
only in the working tree, pending review, layered on top of AMENDMENT 2,
3, and 4 LOG (also not yet committed) and `9f71b65` (committed,
unchanged).** This amendment resolves Decision 10 (the follower-basket
breadth threshold numeric value, left open by AMENDMENT 2 LOG above) and
Decision 22 (the Momentum_F same-session rule proposed, not approved, in
AMENDMENT 4 LOG above). **Decision 11 (the first-bar anchor ambiguity) is
NOT resolved by this amendment and remains OPEN**, exactly as it was left
by every document that previously discussed it, including AMENDMENT 2's
and AMENDMENT 4's own passing references -- an earlier version of this
amendment incorrectly claimed otherwise; see the correction notice above
and Section 2 below. **Decision 13 is reaffirmed exactly as already
recorded in AMENDMENT 4 LOG -- it is not reopened, re-derived, or
duplicated here**, per the instruction to verify an existing reconciliation
before touching it rather than creating a redundant one: re-reading
AMENDMENT 4 LOG's Decision 13 section confirms it already states the
correct, consistent, approved formula and scope (`R_L(t)`, `R_F(t)`,
`Y(t,h)`, `Momentum_F(t)`), with no contradiction found.

**Chronology, stated explicitly**: Decision 10's 70% candidate and Decision
11's `09:15`-vs-`09:16` ambiguity were both already under discussion in
AMENDMENT 2 LOG and in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Sections 5 and 11 (decision items 10, 11) before this amendment; both were
explicitly left open at that time ("Decision 10's numerical threshold
remains open pending separate finalization," AMENDMENT 2 LOG; "hierarchy
approved; exact anchor not," proposal decision item 11). Decision 22 was
proposed, not approved, in AMENDMENT 4 LOG immediately above. This
amendment records the human user's approval of Decision 10 and Decision
22, received 2026-11-14, after AMENDMENT 4 LOG was drafted. **Decision 11
was not approved and an earlier version of this amendment incorrectly
stated that it was -- that statement is corrected in Section 2 below.** The
full reconciliation is recorded in
`lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`, updated by
this same task to reflect the corrected record.

### 1. Decision 10 -- APPROVED, 2026-11-14: follower-basket breadth floor frozen at 70%

**The minimum follower-basket breadth threshold is frozen at 70%, by
explicit user decision on 2026-11-14.** This supersedes the "candidate,
remains open" status recorded in AMENDMENT 2 LOG above (which is preserved
unchanged there, as a dated historical statement of that threshold's
status at the time AMENDMENT 2 was drafted -- not rewritten by this
amendment).

The approved definition, exactly as specified, reusing every existing
rule and convention already governing the analogous leader-side floor
(Section 8) and the governing calendar (Section 12), with nothing new
invented:

- **Present-valid observations only** count toward the 70% numerator and
  denominator -- the same `n_t_breadth`-style counting convention Section
  8 already applies on the leader side (Decision 10's earlier, calendar-
  focused resolution in AMENDMENT 2 LOG).
- **Forward-filled or absent bars are never counted as present** for this
  threshold, mirroring the leader-side rule exactly.
- **`n_t_return`, the divisor actually used in return construction, is
  governed by Decision 17's existing, unchanged endpoint-validity and
  return-construction rules** -- not a new or separate rule invented for
  the follower side. This preserves the same `n_t_breadth`-vs-`n_t_return`
  distinction Section 8 and AMENDMENT 2 LOG already established for the
  leader side, applied here to the follower side without alteration.
- **The governing trading-session calendar is the already-established
  2,457-date calendar** (AMENDMENT 2 LOG resolution 2-4, Section 12) --
  the 2,468 raw archive dates less the 11 verified non-regular-session
  dates, with the 4 genuine weekend special-trading-session dates
  (`2020-02-01`, `2024-01-20`, `2025-02-01`, `2026-02-01`) remaining
  included. **This amendment does not recompute, re-verify, or alter that
  calendar or its underlying classification in any way** -- it is reused
  exactly as already established.
- **The holiday-calendar verification methodology is unchanged**:
  `src/data_layer/nse_holidays.py` + `data/raw/nse_cm_holidays.pkl` plus
  explicit special-session verification, neither file modified, per
  AMENDMENT 2 LOG resolution 4, reused verbatim.

**What this amendment does NOT do**: it does not change the underlying
data, recompute any already-reported figure, or alter the calendar
methodology -- the 70% figure is a frozen threshold value applied to
already-established counting and calendar rules, not a new measurement.
It does not change the leader-side `0.80` breadth floor (Section 8),
which is a separate, already-frozen parameter for a different tier. It
does not authorize Phase 4, a primary gate, or any outcome inspection.

### 2. Decision 11 -- CORRECTION, 2026-11-14 (same day): remains OPEN, never approved

**This subsection, as originally drafted, incorrectly stated that `09:15`
was approved as the sole first-bar anchor by explicit user decision. That
statement was false. The user never approved Decision 11. It remains
OPEN.** `09:16` has not been ruled out as an alternative. The original,
erroneous text is quoted below, retained rather than deleted, so the
record of the error is not lost:

> *(Original, erroneous text, 2026-11-14 -- RETRACTED)*: "`09:15` is the
> sole first valid regular-session bar in `bars_1min`, by explicit user
> decision on 2026-11-14. `09:16` is not an alternative and is not treated
> as open." **This was incorrect. No such user decision was made.**

The ambiguity `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 5
described as "evidence found, not conclusively settled" **remains
unsettled**. The identical open status recorded in
`lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md`,
`lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md`, and
`lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md` is, and remains,
accurate -- not merely "historical," as the erroneous original text
implied.

**Consequence of this correction**: the two-branch arithmetic in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 5 remains fully
conditional, exactly as that section's own pre-existing text already
stated, and is restated here for clarity, not as a new derivation:

- **If** `09:15` is the first valid regular-session bar: the earliest
  possible signal window is bars `09:15, 09:16, 09:17, 09:18, 09:19` --
  signal-end minute `t = 09:19`, wall-clock anchor `09:20`.
- **If** `09:16` is the first valid regular-session bar instead: the
  earliest possible signal window starts at `09:16`, giving signal-end
  minute `t = 09:20`, wall-clock anchor `09:21`.

**Neither branch is chosen.** This preregistration's own passing reference
elsewhere to "the approved `09:20` anchor (Decision 11)" (AMENDMENT 2 LOG,
"what this amendment does NOT do") is a **pre-existing, historical
imprecision in that sentence's wording**, not a resolution of Decision 11
-- it is left unedited there as original historical text, per this
document's own preservation discipline, but must not be read as a
settled fact. Decision 11 requires its own, separate, explicit user
approval before either branch can be adopted.

**What this correction does NOT do**: it does not change the `h+5`
non-overlapping schedule derivation, the prediction horizons, or the
primary-gate designation (Section 10, unchanged). It does not change
Decision 10's or Decision 22's approval, both of which stand unaffected
(Sections 1 and 3). It does not itself authorize Phase 4, a primary gate,
or any outcome inspection.

**[SUPERSEDED, AMENDMENT 6 LOG, 2026-11-14 (later same day): Decision 11
has since been approved at `09:15` by explicit user decision, following
a final targeted first-bar verification report. See AMENDMENT 6 LOG
below for the full, current record. This Section 2 is preserved
unedited above as the accurate historical record of Decision 11's status
earlier on 2026-11-14 -- it was genuinely OPEN at the time this section
was drafted, and the correction it records (reverting an earlier,
erroneous "approved" claim back to OPEN) was accurate when written. It is
superseded, not retracted: unlike the erroneous claim this section itself
corrects, the approval recorded in AMENDMENT 6 LOG below is a real,
explicit user decision, made after independent evidentiary review.]**

### 3. Decision 22 -- APPROVED, 2026-11-14: Momentum_F(t) same-session rule, with a refined exclusion clarification

**The Momentum_F(t) same-session eligibility and minimum-anchor rule
proposed in AMENDMENT 4 LOG above is now APPROVED, by explicit user
decision on 2026-11-14.** The seven numbered requirements are approved
exactly as proposed, **with one wording refinement supplied by this
approval, not a substantive change**: rule 6 is restated to specify
*where* the exclusion applies, which the original proposal did not name
explicitly.

**Approved rule text (supersedes AMENDMENT 4 LOG's proposed text for rule
6 only; rules 1-5 and 7 are approved verbatim, unchanged)**:

1. Both `Momentum_F(t)` endpoints must be valid observations belonging to
   the same trading session and the same trade date.
2. Both endpoints must satisfy the applicable Decision 17 endpoint-validity
   rules.
3. No cross-session endpoint pairing is permitted.
4. No previous-session fallback, nearest-available-bar substitution across
   a session boundary, clamping, padding, or silent endpoint replacement
   is permitted.
5. If either endpoint is unavailable or invalid, `Momentum_F(t)` is
   unavailable for that observation.
6. **The corresponding observation is excluded from the primary regression
   sample. No null-control observation is retained in its place, and no
   value is imputed or substituted** -- this is the same exclusion
   AMENDMENT 4 LOG's rule 6 already specified ("excluded under the frozen
   eligibility policy... no imputed or substituted `Momentum_F` value is
   ever used"), stated here with the additional, explicit clarification
   that a null-control placeholder is not an acceptable alternative to
   exclusion either. This is a precision addition, not a reversal of
   AMENDMENT 4 LOG's original intent.
7. The same frozen follower basket and constituent-eligibility rules
   continue to apply. No future-informed constituent replacement or
   reweighting is permitted.

**Minimum-anchor arithmetic -- CORRECTED, 2026-11-14 (same day): remains
conditional on Decision 11, which is OPEN.** *(An earlier draft of this
subsection claimed the arithmetic was "now unconditional given Decision
11's resolution" and that `09:50` was "the operative one, not merely a
candidate." That claim was incorrect -- Decision 11 was never approved,
so no branch is operative. Both branches below remain live and
conditional, exactly as originally derived in AMENDMENT 4 LOG; the
erroneous "unconditional" framing is retracted.)*

- **If** `09:15` is the first valid regular-session bar: the `Momentum_F`
  start endpoint `t-35` must be at or after `09:15`, so `t >= 09:15 + 35
  minutes = 09:50`. **Conditional earliest anchor: `09:50`.**
- **If** `09:16` is the first valid regular-session bar instead: `t-35 >=
  09:16`, so `t >= 09:51`. **Conditional earliest anchor: `09:51`.**

**Neither branch is chosen.** This figure cannot be pinned to a single
value until Decision 11 is resolved by explicit user approval.

**This remains a lower time bound only, in either branch -- not a
guarantee that the follower basket or either endpoint is actually valid at
that minute for any specific observation.** If either endpoint fails the
validity requirements in rules 1-2 above, the observation is still
excluded under rule 6, regardless of `t`. **Decision 22's approval of the
exclusion rule itself (rules 1-7 above) is unaffected by this correction
and stands.**

**[SUPERSEDED, AMENDMENT 6 LOG, 2026-11-14 (later same day): Decision 11
is now APPROVED at `09:15` -- see AMENDMENT 6 LOG below. The two-branch
arithmetic above therefore resolves to a single value: the earliest
`Momentum_F(t)` anchor is `t >= 09:50`, unconditionally. This remains a
lower bound only -- it is not a guarantee that any specific basket or
endpoint is actually valid at that minute; rules 1-2 and 5-6 above continue
to govern validity and exclusion exactly as approved, unaffected by this
update.]**

**What this amendment does NOT do**: it does not create a separate,
alternative session anchor -- Decision 11 (Section 2 above) governs the
first-bar anchor; Decision 22 only derives a consequence of it for
`Momentum_F(t)` specifically. It does not change the frozen monthly
roster, Option 2's construction, the existing Section 12
forward-window-crosses-15:30 exclusion for `Y(t,h)`, the now-approved 70%
follower-breadth threshold (Section 1 above), the trial ledger, or the
multiplicity/alpha accounting. It does not authorize Phase 4, a primary
gate, or any outcome inspection.

### 4. Section 23 update -- CORRECTED, 2026-11-14 (same day)

One new row is added to Section 23's frozen-parameters table: the approved
70% follower-breadth floor (Decision 10). **The `Momentum_F(t)` minimum
anchor (Decision 22, approved) is also recorded, but as a conditional
two-branch figure (`09:50` or `09:51`), not a single value -- Decision 22's
exclusion rule is approved, but the anchor it implies still depends on
Decision 11, which is OPEN.** *(An earlier draft of this subsection added
rows for an "approved `09:15` first-bar fact" and a "now-unconditional
`09:20`" sampling anchor. Both rows are retracted -- Decision 11 was never
approved, no first-bar fact was confirmed, and the sampling anchor remains
conditional. See the corrected Section 23 table itself.)*

**[SUPERSEDED, AMENDMENT 6 LOG, 2026-11-14 (later same day): Decision 11
is now APPROVED at `09:15`. Section 23's table is updated accordingly --
the first regular-session bar, the non-overlapping sampling anchor
(`09:20`), and the `Momentum_F(t)` minimum anchor (`09:50`) are now
recorded as single, fixed, approved values rather than conditional
two-branch figures. See AMENDMENT 6 LOG below and the corrected Section 23
table.]**

---

## AMENDMENT 6 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 11 APPROVED at `09:15`, following a final targeted first-bar verification

**Status: Decision 11 (the first-valid-regular-session-bar question, left
OPEN by AMENDMENT 2 LOG, AMENDMENT 4 LOG, and corrected back to OPEN in
AMENDMENT 5 LOG Section 2 after an earlier erroneous approval claim in
this same working tree) is now genuinely APPROVED, by explicit user
decision on 2026-11-14, later the same day as AMENDMENT 5 LOG. Not yet
committed -- this edit exists only in the working tree, pending review,
layered on top of AMENDMENT 2, 3, 4, and 5 LOG (also not yet committed)
and `9f71b65` (committed, unchanged).**

**Chronology, stated explicitly, so this approval is not confused with the
earlier, retracted one**: AMENDMENT 5 LOG Section 2 correctly recorded
Decision 11 as OPEN after an earlier documentation error (an intermediate
edit that falsely claimed approval without any user decision) was found
and retracted. Following that correction, a separate, explicitly
authorized read-only task ("Final Targeted First-Bar Verification") ran a
direct, targeted query against `bars_1min` -- reusing the already-verified
governing trading-session calendar (2,457 dates, AMENDMENT 2 LOG) and the
already-approved Decision 17 structural-validity/PRESENT-VALID predicate,
inventing no new rule -- to measure `09:15` and `09:16` presence and
validity directly, rather than relying on the indirect Fibo-ORB usage
evidence `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 5
had previously described as "evidence found, not conclusively settled."
That verification is the evidentiary basis the user reviewed before
approving Decision 11 in this conversation on 2026-11-14. **This
amendment records that approval. It does not itself re-run, extend, or
re-derive the verification -- it is a documentation-only record of a
decision already made.**

### 1. Decision 11 -- APPROVED, 2026-11-14: `09:15` is the frozen first regular-session bar

**`09:15` is the first regular-session bar in `bars_1min`, by explicit user
decision on 2026-11-14.** `09:16` is not adopted as an alternative. This
supersedes the "OPEN" status recorded in AMENDMENT 5 LOG Section 2 (itself
a correction of an earlier erroneous approval claim), which is preserved
there unchanged as the accurate historical record of Decision 11's status
earlier that day -- not rewritten by this amendment.

**This is a global session-time convention, not a claim that every entity
has a valid bar at `09:15` on every date.** Missing or structurally
invalid entity-level `09:15` observations continue to be governed
entirely by the already-approved eligibility machinery -- Decision 17's
endpoint-validity rules, the entity-day archive-absence and <90%-present-
valid gates (Section 12), the leader/follower breadth floors (Section 8,
Decision 10) -- with **no new rule, substitution, forward-fill, or
previous-session fallback introduced by this amendment.** In particular:

- **No shift to `09:16` as the global convention** is made on account of
  any entity's missing `09:15` observation, on any date, including the
  identified `2020-11-23`-through-`2020-11-27` archive-coverage episode
  (a market/archive-wide, dated, identifiable gap affecting a stable
  subset of entities that week -- supporting evidence for why `09:15` is
  a real regular-session minute even where the archive under-captured it,
  not a reason to redefine the session boundary).
- **No substitution of a `09:16` bar for a missing `09:15` observation** is
  permitted for any entity-day.
- **No forward-fill, imputation, or previous-session bar** may stand in
  for a missing `09:15` observation. Existing Decision 17 forward-fill
  rules (the `<3`-consecutive-minute gap rule, Section 13) apply exactly
  as already approved and are not widened by this amendment.
- **The existing breadth, frozen-basket, and endpoint-completeness rules
  are unweakened.** This amendment fixes a session-time convention; it
  does not touch Section 8's leader floor, Decision 10's 70% follower
  floor, Option 2's frozen-subset construction, or Decision 17's
  endpoint-validity rules in any way.

### 2. Consequence -- first signal window and earliest signal anchor, now fixed

With `09:15` confirmed as the first regular-session bar, the two-branch
arithmetic recorded in AMENDMENT 5 LOG Section 2 (and in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 5) resolves to
a single value, with no new derivation -- this is the same arithmetic
already derived conditionally, now simply pinned to its `09:15` branch:

- **First signal window**: bars `09:15, 09:16, 09:17, 09:18, 09:19`
  (`t-4=09:15`, `t=09:19`).
- **Earliest non-overlapping sampling anchor**: `09:20` (the `t=09:19`
  bar's close becomes known at wall-clock `09:20`).

The `09:16`-first-valid branch (`t=09:20`, anchor `09:21`) is not adopted.

### 3. Consequence -- `Momentum_F(t)` minimum anchor, now fixed, subject to Decision 22

**Under approved Decision 22** (AMENDMENT 5 LOG Section 3, unchanged by
this amendment), both `Momentum_F(t)` endpoints must be valid, same-
session, same-trade-date observations. With `09:15` now the first
regular-session bar, the conditional minimum-anchor arithmetic resolves
to a single value:

- `t - 35 >= 09:15`, so **`t >= 09:50`**. **Earliest `Momentum_F` anchor:
  `09:50`, unconditionally.**

**This is a lower time bound only -- it is not a guarantee that the frozen
follower basket or either `Momentum_F` endpoint is actually valid at
`09:50` for any specific observation.** Decision 22's rules 1-6 (same-
session validity, no cross-session pairing, no fallback/substitution,
exclusion when an endpoint is unavailable or invalid) continue to govern
exactly as approved, unaffected by this amendment. The `09:16`-first-valid
branch (`t >= 09:51`) is not adopted.

### 4. Section 23 update

The frozen-parameters table is updated: the first regular-session bar,
non-overlapping sampling anchor, and `Momentum_F(t)` minimum anchor rows
are each changed from a conditional two-branch figure to a single,
approved value, with the prior conditional/OPEN text preserved as
historical record immediately above each updated row, per this
document's existing preservation discipline.

**What this amendment does NOT do**: it does not change Decision 10's
70% follower-breadth floor, Decision 13's return convention, Decision 17's
endpoint-validity rules, Decision 22's exclusion rule (rules 1-7, all
unchanged), the frozen monthly roster, Option 2's construction, the trial
ledger, or the multiplicity/alpha accounting. It does not resolve Decision
15 (the 20bps hurdle), Decision 20 (corporate-action handling), or
Decision 21 (special/irregular sessions) -- all remain OPEN, unaffected.
It does not authorize Phase 4, a primary gate, or any outcome inspection.
It does not itself verify that every entity-day has a valid `09:15`
observation -- the final targeted verification report found >99% archive-
wide presence and validity, with enumerable, already-governed exceptions
(the Nov 2020 cluster and three special/truncated-session dates), not
universal coverage, and this amendment does not overstate that finding.

---

## AMENDMENT 7 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 23 APPROVED: monthly roster turnover-ranking effective-time (Convention A, ranking-date excluded)

**Status: a new decision (Decision 23 -- the monthly leader/follower
roster's turnover-ranking effective-time and ranking-date inclusivity)
is APPROVED, by explicit user decision on 2026-11-14, following review of
`lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md`. Not yet committed --
this edit exists only in the working tree, pending review, layered on
top of AMENDMENT 2 through 6 LOG (also not yet committed) and `9f71b65`
(committed, unchanged).**

**Chronology, stated explicitly**: Section 6's existing text ("trailing-60
-trading-session median daily rupee turnover... point-in-time -- no bar
after the ranking date is used") was found, by a separate, explicitly
authorized read-only audit, to be genuinely silent on one specific point:
whether the ranking date's own turnover observation is included in or
excluded from that trailing-60-session window. That audit (i) confirmed
no committed code implements the monthly ranking step; (ii) found that a
prior, uncommitted scratchpad script from this family's own earlier work
had silently assumed ranking-date-inclusion, without flagging it as an
assumption; (iii) found that this project's own committed annual-
reconstitution code (`src/fibo/universe.py`) uses a full prior-calendar-
year exclusion with zero current-year lookback, a real precedent at a
different granularity; (iv) reconstructed both candidate conventions over
all 120 documented study months and found no change to leader/follower
counts, but entity-level tier reassignment in 47/120 months (103
reassignments, 58 entities), verified to be genuine rank-boundary median
shifts, not ties, missing data, or identity-resolution artifacts, and not
concentrated in any period; and (v) verified the annual top-200 universe
construction is unaffected by this question. **The user reviewed that
audit and approved Convention A. This amendment records that approval. It
does not itself re-run, extend, or re-derive the audit.**

### 1. Decision 23 -- APPROVED, 2026-11-14: monthly roster turnover ranking excludes the ranking date's own turnover

**The trailing-60-session median daily rupee turnover used to rank
entities for the monthly leader/follower split uses each entity's last 60
qualifying `prices_eod.turnover` observations with `trade_date <
ranking_date` -- the ranking date's own turnover observation is
excluded, by explicit user decision on 2026-11-14.** This clarifies,
rather than changes, Section 6's existing "no bar after the ranking date
is used" language: that language is preserved unedited below, now
understood as entailing strict exclusion of the ranking date itself, not
merely of dates after it.

- **The roster is frozen using data available as of the close of the
  trading session immediately preceding the ranking date** -- fully
  determined before the ranking date's market open.
- **The roster becomes effective from the first trading session of the
  ranking date itself** -- i.e., it governs that date's own `09:20`
  signal (Decision 11), with no availability gap and no deferral to the
  next trading session.
- **No imputation, forward-filling, or substitute turnover observation**
  is introduced by this decision, for any entity, on any date. The
  existing `>=60`-qualifying-session eligibility rule (Section 6,
  unchanged) continues to govern exactly as before; an entity short of 60
  qualifying prior-session observations remains excluded from that
  month's eligible pool, exactly as already specified.
- **The 47/120-month entity-level membership comparison is supporting
  audit evidence only, and is not the basis of this approval.** The
  approval rests on point-in-time validity: `prices_eod.turnover` is an
  end-of-day aggregate that does not exist until the ranking date's own
  session closes, so a ranking-date-inclusive convention cannot
  legitimately back that date's own `09:20` signal without a look-ahead.
  The membership-impact measurement is cited in
  `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` Section 5 as *not
  changing* this reasoning, not as the reasoning itself.

### 2. What this amendment does NOT do

- **It does not change the annual top-200 universe construction**
  (`src/fibo/universe.py`, `reconstitute_annually`, `effective_universe`)
  -- verified unaffected by the cited audit (Section 3.7 of that
  document); this amendment does not touch that code or its own
  calendar-year boundary in any way.
- **It does not resolve the separate `prices_eod`-vs-`bars_1min`
  first-trading-day calendar discrepancy** found as a byproduct of the
  cited audit's source-integrity checks (4 of 120 months differ,
  including 3 genuine weekend special sessions). **That discrepancy
  remains OPEN, folded into Decision 21's existing scope** (special/
  irregular trading sessions) -- it is not separately approved, resolved,
  or decided by this amendment. **[SUPERSEDED, AMENDMENT 11 LOG,
  2026-11-14 (later same day): this discrepancy has since been resolved
  as Decision 24 -- the governing exchange-session calendar, not raw
  presence in either table, determines ranking dates. See AMENDMENT 11
  LOG for the full record.]**
- **It does not resolve Option 2's own Stage-A threshold form, value, or
  denominator**, nor whether Decision 10's 70% figure is the value
  intended for that threshold -- both remain exactly as OPEN as recorded
  in Section 20/23 and the proposal's own row 19. This amendment is a
  **prerequisite clarification only**, as the auditing task itself
  stated; it does not itself finalize or touch that threshold.
- **It does not alter the Stage A/Stage B distinction or Stage B's
  zero-tolerance forward-endpoint rule** (the proposal's Section 3C,
  9-step construction) in any way.
- It does not change Decision 10's 70% follower-breadth floor, Decision
  11's `09:15` first-bar approval, Decision 13's return convention,
  Decision 17's endpoint-validity rules, or Decision 22's exclusion rule.
  It does not resolve Decision 15 (the 20bps hurdle) or Decision 20
  (corporate-action handling) -- both remained OPEN at the time this
  amendment (7) was drafted, unaffected by it. *(Decision 15 was
  subsequently approved, separately, by AMENDMENT 8 LOG, later the same
  day -- this sentence describes AMENDMENT 7's own scope only and is not
  a current-status claim; see AMENDMENT 8 LOG for Decision 15's current
  status. Decision 20 remains OPEN.)* It does
  not authorize Phase 4, a primary gate, or any outcome inspection.

### 3. Section 23 update

A new row is added to Section 23's frozen-parameters table recording the
approved ranking-date-exclusive turnover-window rule (Decision 23). No
other row in that table is touched by this amendment.

---

## AMENDMENT 8 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 15 APPROVED: signed effect-size-hurdle gate criterion

**Status: Decision 15 (whether, and how, the 20bps figure functions as an
approved primary-gate PASS/FAIL criterion -- left OPEN by the original
version and every amendment through AMENDMENT 7) is now APPROVED, by
explicit user decision on 2026-11-14. Not yet committed -- this edit
exists only in the working tree, pending review, layered on top of
AMENDMENT 2 through 7 LOG (also not yet committed) and `9f71b65`
(committed, unchanged).**

**Chronology, stated explicitly**: Section 18's and Section 20's own
prior "DECISION 15 STATUS NOTE"s (both dated 2026-11-14, drafted earlier
the same day by documentation-repair tasks) correctly recorded that
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 9/Section 11
decision item 15 only **recommended** a specific signed effect-size
construction (`beta > 0` required; negative `beta` never reinterpreted as
a pass via `|beta|`; the comparison an "effect-size hurdle," not a
validated cost or profitability claim) and that this recommendation had
**not** been approved. **The user has now reviewed and approved that
recommendation, exactly as it was stated, with one precision addition
not previously stated explicitly anywhere: the effect-size comparison is
strictly `>` 20bps -- equality does not pass.** This amendment records
that approval. It does not change the 20bps numeral, the two-sided
`alpha=0.00625` Bonferroni-adjusted significance level, day-clustered
standard errors, the 60-minute primary horizon, or any other gate
mechanic (conditions 0, 1's statistical machinery, 3-6 of Section 20).

### 1. Decision 15 -- APPROVED, 2026-11-14: signed effect-size-hurdle gate criterion

**The following rule is APPROVED as the governing interpretation of
Section 20's conditions 1 and 2, by explicit user decision on
2026-11-14:**

1. **Direction requirement**: `beta > 0` is mandatory for a primary-gate
   pass. A primary test that is statistically significant but shows
   `beta <= 0` does not pass condition 1, regardless of magnitude.
2. **Effect-size hurdle**: `beta * sigma(S_leader)` (equivalently
   `beta * sigma(S_L)`; `S_leader(t)` and `S_L(t)` denote the same
   quantity across this document and the proposal) **strictly exceeds**
   20 bps. **Equality (`beta * sigma(S_leader) = 20bps` exactly) does
   NOT pass.**
3. **Statistical significance -- unchanged**: the existing primary test
   (Section 20 condition 1) is unaffected in its statistical mechanics --
   two-sided Bonferroni-adjusted `alpha = 0.00625` (Decision 16,
   AMENDMENT 3 LOG), day-clustered standard errors, evaluated at the
   primary 60-minute horizon. This amendment adds the direction
   requirement (item 1 above) to that existing test; it does not alter
   the alpha, the clustering, the horizon, or any other inference
   mechanic.
4. **Negative beta**: a statistically significant negative `beta` is
   **contrary evidence** against the positive-propagation hypothesis.
   **`abs(beta)` (or any other magnitude-only reinterpretation) must
   never be used to convert a negative or non-positive `beta` into a
   pass**, under any circumstance.
5. **Interpretation, preserved exactly as already stated in the
   proposal's Section 9 and this document's own Section 18/20 status
   notes**: the 20bps effect-size hurdle is a model-implied effect size
   for a one-standard-deviation change in `S_leader(t)`/`S_L(t)`, under
   the fitted regression. **It is NOT a validated transaction-cost
   estimate, an achievable net profit figure, or evidence of
   tradability.** Any profitability claim requires a separate execution/
   turnover model, which does not exist in this document and is outside
   this study's scope (Section 19).

`sigma(S_leader)`/`sigma(S_L)` **retains its existing definition,
unchanged by this amendment**: the **observed** standard deviation of
the real, Section-8-corrected `S_leader(t)` series -- a variance-only
input, not a newly defined or re-derived quantity.

### 2. What this amendment does NOT do

It does not change the 20bps numeral (Section 18, unchanged, original
project convention). It does not change the two-sided Bonferroni alpha
(`0.00625`, Decision 16), the day-clustered standard-error methodology,
the 60-minute primary horizon, or any other condition in Section 20
(conditions 0, 3, 4, 5, 6 -- the signal non-degeneracy check, timing
null, selection null, market-factor null, and stage-count reconciliation
-- are all unchanged). It does not change any other decision row or
amendment's content (Decisions 10, 11, 13, 16, 17, 22, 23 are all
unaffected). It does not resolve Decision 20 (corporate-action handling)
or Decision 21 (special/irregular sessions) -- both remain OPEN,
unaffected. It does not authorize Phase 4, a primary gate, or any outcome
inspection -- this is a documentation-only record of an approved
interpretive rule, not an execution of the gate itself.

### 3. Section 18, Section 20, and Section 23 updates

Section 18's and Section 20's existing "DECISION 15 STATUS NOTE"s are
preserved unedited, each followed immediately by a new, dated status
update recording this approval -- per this document's existing
preservation discipline, the original OPEN-status text is not deleted or
rewritten. Section 20's conditions 1 and 2 are restated, immediately
below the existing numbered list, with the approved signed-threshold
language made explicit; the numbered list itself (conditions 0-6) is not
renumbered or restructured. A new row is added to Section 23's
frozen-parameters table recording the approved rule. No other row in
that table is touched by this amendment.

---

## AMENDMENT 9 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decisions 14, 19 (threshold), 20, and 21 APPROVED, following a consolidated methodology review

**Status: four decisions -- Decision 14 (`bars_1min` price-adjustment
convention), Decision 19's own Stage-A minimum-breadth threshold (the
"separately still OPEN" sub-question left unresolved when Decision 19's
*selection* of Option 2 was recorded), Decision 20 (corporate-action
handling), and Decision 21 (special/irregular sessions) -- are now
APPROVED, by explicit user decision on 2026-11-14, following review of a
single consolidated methodology report. Not yet committed -- this edit
exists only in the working tree, pending review, layered on top of
AMENDMENT 2 through 8 LOG (also not yet committed) and `9f71b65`
(committed, unchanged).**

**Chronology, stated explicitly**: each of these four questions was
individually audited in prior, separately authorized read-only work
(`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`,
`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md`,
`lead_lag/PRE_SIGNAL_VS_FORWARD_ENDPOINT_RECONCILIATION.md`,
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 4C,
`lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md`,
`lead_lag/FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md`). A single
consolidated review then reconciled all four against each other and
against every already-approved decision (10, 11, 13, 15, 16, 17, 22, 23),
found no genuine conflict, and presented one recommendation per decision
for explicit human approval. **The user approved all four, as
recommended, on 2026-11-14.** This amendment records that approval. It
does not itself re-run, extend, or re-derive any audit, and it does not
authorize Phase 4, a primary gate, or any outcome inspection.

### 1. Decision 14 -- APPROVED, 2026-11-14: `bars_1min` is MIXED CONVENTION

**`bars_1min` must not be treated as reliably raw.** By explicit user
decision, the following characterization is adopted:

- Angel One's intraday archive is **back-adjusted**, piecewise, for
  split/bonus corporate actions -- not raw, and not uniformly adjusted
  either. At **103 of 104** eligible split/bonus ex-dates in the tested
  population, the Angel-vs-bhavcopy price scale steps by exactly the
  recorded action ratio while the Angel series itself shows no
  discontinuity (`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md` SS6.1,
  SS9).
- **TATASTEEL 2022-07-28 is the documented exception**: its adjustment
  boundary is misplaced two trading sessions early, leaving two sessions
  in raw scale inside an otherwise-adjusted window (same document, SS5.4,
  SS9).
- The archive also contains **28 Angel-side scale breaks with no
  recorded corporate action** at that date (same document, SS6.3) --
  reported, not explained; these may reflect action types
  `corporate_actions` does not track (mergers, demergers, capital
  reductions) or an undetected adjustment-boundary error. **The vendor's
  exact adjustment mechanism remains unverified** -- the ~2-year trailing
  window is a measured empirical pattern, not confirmed Angel One
  documentation (same document, SS8 item 4).
- **Same-session returns may be used without reconstructing or
  rescaling vendor history**, because every located scale boundary in
  the tested population (143 Angel-vs-bhavcopy breaks, SS6.3) falls
  **between** sessions, never inside one -- confirmed directly by a
  208-session, 77,654-bar within-session scan (same document, SS7):
  **zero** sustained multiplicative shifts at either an 8% or a 15%
  threshold. **This is a tested-population finding, not a universal
  guarantee** -- it does not establish that all possible intraday scale
  defects are impossible, only that none were found in the 208 sessions
  actually scanned.
- **Phase 4 must explicitly assert, in code, that both endpoints of
  every computed return (`R_L(t)`, `R_F(t)`, `Y(t,h)`, `Momentum_F(t)`)
  belong to the same `trade_date`** -- this is a new, approved
  implementation requirement, not yet satisfied by anything committed
  (no `src/lead_lag/` code exists). The within-session safety finding is
  **conditional** on this assertion actually holding; it is not a
  substitute for it.
- **Limitations, preserved exactly as audited, not weakened**: the
  104-event population covers only recorded bonus/split actions on
  entities with intraday coverage (75 of 386 archive entities); 504 of
  659 in-window corporate-action events have no intraday coverage at
  all; pre-2016 actions are invisible to this check; whether other
  entities carry an undetected misplaced boundary analogous to
  TATASTEEL's is explicitly unresolved (`DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`
  SS8, items 1, 3, 4, 5).

**No new adjustment algorithm is introduced. No source data, ingestion
code, or read path is modified by this amendment.**

### 2. Decision 19 -- APPROVED, 2026-11-14: Option 2's Stage-A minimum-breadth threshold

**The Option 2 Stage-A minimum-breadth threshold (left as a separately
OPEN sub-question when Option 2's *selection* was recorded,
`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3) is now APPROVED,
by explicit user decision, as the following rule:**

```
     |frozen_subset(t, side)|
    --------------------------   >=  0.70
      n_roster_tier(month, side)
```

applied **separately** for `side in {leader, follower}`, where:

- **Numerator**: the count of that side's roster names surviving Stage A
  eligibility (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
  Section 3C step 2 -- present-valid, jointly, at `t-35`, `t-5`, **and**
  `t`) and included in the frozen subset for observation `(t, side)`.
- **Denominator**: that calendar month's **original roster-tier size**
  for that side (`n_leaders` or `n_followers`, as assigned at roster
  construction, Sections 6/7, Decision 23) -- **the size before any
  Stage A exclusion is applied**, not the frozen subset's own size and
  not the annual top-200 universe.
- **Applied at step 4**, exactly where `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
  Section 3C's 9-step construction places it: **after** eligibility is
  determined and the subset is frozen (steps 2-3), **before** anything is
  computed from it (step 6), and **before** the forward check (step 7,
  Stage B).

**This 70% value and this original-roster-tier denominator are both
newly approved methodological choices for this specific purpose.** They
are **not** described as, and must not be read as, already established
by Decision 10's prior approval. Decision 10's 70% follower-breadth
figure is a **conceptually distinct, pre-existing mechanism** -- a
per-minute floor modeled on the leader-side `n_t_breadth` convention
(Section 8), gating whether a portfolio-level statistic is computed *at
a given minute at all*. Option 2's Stage-A threshold gates whether one
specific `(t, side)` **observation's frozen subset** is large enough to
trust, at the point in the 9-step procedure where that subset already
exists. **Choosing the identical number (70%) for both is a deliberate
parsimony/consistency decision made explicitly today, not an inference,
transfer, or reuse of Decision 10's earlier approval.** The leader-side
`0.80` per-minute floor (Section 8) remains a third, separate mechanism,
unaffected and unconflated with either of the above.

**Everything else about Stage A and Stage B is unchanged**:

- Stage A's pre-signal endpoint checks at `t-35`, `t-5`, and `t` (step 2)
  are preserved exactly, including the all-or-nothing-per-name joint
  requirement.
- This threshold is applied **before** the subset and its weights are
  frozen for use -- more precisely, step 4 is evaluated on the subset
  **already frozen** at step 3, and the subsequent computation (step 6)
  only proceeds if step 4 passes; no computation ever uses an
  unfrozen or partially-determined subset.
- Stage B (steps 7-9) is preserved **exactly, with zero tolerance**: if
  any frozen-subset member fails its `t+h` endpoint, the **entire**
  observation is discarded -- no reweighting, no replacement, no partial
  return, no imputation, for any horizon.

**Option 2 remains the selected construction. Option 1 is not reopened
or reconsidered by this amendment.**

### 3. Decision 20 -- APPROVED, 2026-11-14: corporate-action eligibility folded into Stage A

**The existing single-entity `+/-1`-trading-day corporate-action
exclusion (Section 12, `known_date = ex_date`) is retained, unchanged in
its own definition, and is now APPROVED to be applied as follows:**

- **Applied as a separate eligibility condition during Stage A, before
  the eligible subset and weights are frozen** -- i.e. inside step 2's
  existing per-name, per-endpoint check, not as a later, separate pass
  over an already-frozen subset.
- **A constituent inside its own `+/-1`-day corporate-action window at a
  required Stage A endpoint (`t-35`, `t-5`, or `t`) is ineligible for
  that observation** -- excluded from the frozen subset at Stage A,
  through the same mechanism that already excludes names for any other
  endpoint-validity failure (missing bar, structurally invalid bar).
- **This does not redefine structural bar validity or the existing
  Decision 17 PRESENT-VALID definition.** A bar can be structurally
  valid, present, and PRESENT-VALID, and still fail corporate-action
  eligibility -- these are two separate conditions, both checked at Stage
  A, neither subsuming the other.
- **No second, parallel, whole-day exclusion mechanism is introduced.**
  The existing rule is relocated to operate inside the single, unified
  Stage A eligibility check (per the proposal's own "no separate
  per-name filtering mechanism" principle, Section 3) -- it is not
  duplicated, and it does not run as a standalone filter alongside
  roster/completeness logic.
- **Stage B's existing zero-tolerance forward-endpoint rule is
  preserved exactly**, unaffected by this amendment.

**Evidentiary basis and its explicit limits**: this approval relies on
`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md` Section 7's direct,
empirical finding of zero within-session mixed-scale defects across the
104-event/208-session tested population -- **not** on any confirmed
exchange-side adjustment-timing mechanism, which remains unverified
(`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 4C, category
2). **This amendment does not claim the Decision 14 audit proves all
corporate-action-related scale risks are absent.** Its tested scope is
limited to recorded bonus/split events on entities with intraday
coverage; unrecorded action types (mergers, demergers, capital
reductions) and entities outside the archive's covered universe are not,
and cannot be, addressed by this audit or this amendment.

### 4. Decision 21 -- APPROVED, 2026-11-14: special sessions included; `2021-02-24` conservatively excluded; primary-sample calendar = 2,456 dates

**The governing trading-session calendar (Section 12, 2,457 dates, A+B+E
buckets) is unchanged and remains the authoritative verified-calendar
figure, reused by every historical measurement that already used it
(Decision 10's breadth tables, the frozen-roster audits, and all other
work predating this amendment). This amendment does not retroactively
describe any of that prior work as having used a different denominator.**

**A new, narrower figure is introduced for the primary analysis sample
specifically, by explicit user decision**:

- **The four verified weekend special sessions are included**: `2020-02-01`,
  `2024-01-20`, `2025-02-01`, `2026-02-01`. **The existing session
  convention applies to these four dates exactly as to any other
  included session** -- first regular-session bar `09:15` (Decision 11),
  earliest signal anchor `09:20`, final bar-start convention `15:29`
  (Section 12), subject to the same ordinary endpoint-validity and
  eligibility checks as any other date, including Decision 20's
  corporate-action condition above. No special-session-specific rule is
  introduced for these four dates; they are governed by the ordinary
  rule because `lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md` Section 7
  independently verified each one as a structurally normal, near-complete
  375-minute session.
- **`2021-02-24` is conservatively excluded from the primary sample.**
  Its own session identity was already flagged unresolved
  (`lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md`, "2021-02-24's
  identity unresolved") and the consolidated review found that
  `lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md` itself contains **mutually
  inconsistent statements about this date's own in-window coverage**
  (Section 3/4.1 of that document record `n_min=295`, 189 active
  entities, and 14,401 post-`15:29` rows for `2021-02-24`, while Section
  7 of the same document states "0 entities have any bar in the
  `09:15-15:29` window at all" for the same date) -- a genuine,
  previously unnoticed internal inconsistency, not invented here and not
  resolved here. Given this, and the date's already-documented unresolved
  identity, the conservative treatment is exclusion from the primary
  sample. **`REGULAR_SESSION_FINAL_BAR_AUDIT.md` itself is not edited by
  this amendment** -- its internal inconsistency is recorded here as the
  reason for this exclusion, flagged for separate, future correction of
  that document, not silently fixed by assumption.
- **The primary-sample calendar therefore contains 2,456 dates**: the
  governing 2,457-date calendar, less `2021-02-24`.
- **The 11 already-verified non-session dates remain excluded**,
  unchanged (5 Muhurat-evening-only weekdays, 1 holiday-special-1-hour
  weekday, 2 weekend dates with no in-window session, 3 weekend dates
  with only a partial/single-artifact-bar footprint -- Section 12,
  unchanged).
- **No substitution of `15:28` for a missing `15:29` endpoint, no
  forward-fill of any missing endpoint, and no inference of session
  status from incidental archive rows is authorized** -- all unchanged
  from the existing Decision 17 and Section 12/13 rules.

**The distinction between genuine special sessions (the 4 E-bucket
dates, included), non-session archive artifacts (the 11 C/D/F/G-bucket
dates, excluded), and unresolved dates (`2021-02-24`, now excluded from
the primary sample specifically because its own classification evidence
is internally inconsistent) is preserved exactly as the consolidated
review stated it -- none of these three categories is conflated with
another.**

### 5. What this amendment does NOT do

It does not change Decision 10's 70% follower-breadth floor or Section
8's 80% leader floor (both remain separate, unconflated mechanisms). It
does not change Decision 11's `09:15`/`09:20` anchors, Decision 13's
return convention, Decision 15's signed effect-size-hurdle rule, Decision
16's multiplicity accounting, Decision 17's endpoint-validity rules,
Decision 22's `Momentum_F` same-session rule, or Decision 23's roster
effective-time convention -- all nine are unaffected. It does not reopen
Option 1 or Decision 19's own selection (both already resolved,
unchanged). It does not rewrite, correct, or silently resolve the
internal inconsistency found in `REGULAR_SESSION_FINAL_BAR_AUDIT.md` --
that document is not edited by this amendment. It does not modify
`lead_lag/trial_ledger.json`, any source code, the master spec, or any
other strategy family. It does not authorize Phase 4, a primary gate, or
any outcome inspection.

---

## AMENDMENT 10 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 17 APPROVED: the full bar-validity, gap-handling, and Stage A/Stage B precedence policy

**Status: Decision 17 (missing-data / stale-price / structural-validity
compatibility across every endpoint this family's eligibility checks
need) is now APPROVED, by explicit user decision on 2026-11-14. Not yet
committed -- this edit exists only in the working tree, pending review,
layered on top of AMENDMENT 2 through 9 LOG (also not yet committed) and
`9f71b65` (committed, unchanged).**

**Chronology, and an inconsistency found while drafting this amendment,
stated explicitly**: `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md`
recorded three sub-decisions -- **A1** (zero-volume, OHLC-flat bars:
accept), **B1** (zero-volume, OHLC-non-flat bars: flag/ineligible), and
**C** (the Section 13 gap threshold's unit is exact elapsed timestamp
duration, not a minute-truncated approximation) -- as **already settled
human decisions**, predating this amendment. That same document's own
remaining two categories (positive-volume structurally-valid bars, and
structurally invalid bars) and the Stage A/Stage B precedence framing
were left as **recommendations pending approval**, explicitly distinct
from A1/B1/C (Section 7 of that document: *"A1, B1, and C are SETTLED
HUMAN DECISIONS... excluded from 7.1-7.3's categorization... Whether to
approve the remainder of this policy -- categories A and E's
recommendation status (still pending approval, not settled by A1/B1/C)
... genuinely require a human decision."*). **Despite this, numerous
passages throughout this document's own prior amendments referred to
"Decision 17's existing, already-approved" rules, and to a "PRESENT-VALID"
definition, as if settled -- while this document never formally defined
PRESENT-VALID anywhere, and the governing decision-table row (proposal
Section 11, row 17) remained OPEN throughout.** This is a genuine
documentation inconsistency, found while preparing this amendment, not
invented: this document had been informally treating Decision 17 as
settled in cross-references while its own formal governance record said
otherwise. **This amendment resolves that inconsistency**: it formally
defines PRESENT-VALID for the first time in this document, approves the
remainder of the policy (categories A and E, renamed D and E below for
this amendment's own exposition, plus Stage A/Stage B precedence), and
closes the decision-table row. **A1, B1, and C are not reopened, re-
examined, or re-approved here -- they are restated below exactly as
already settled, for completeness, with their own prior settlement dates
unchanged.**

### 1. Previously settled sub-decisions, restated unchanged (not reopened)

**A1 -- zero-volume, OHLC-flat bars (SETTLED, predates this amendment):
ACCEPT.** Treated as a present, valid observation; the bar's own close
is used directly; not classified as missing merely because volume is
zero. No forward-fill machinery is invoked, since there is no gap to
fill (`lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md` Section
4.B).

**B1 -- zero-volume, OHLC-non-flat bars (SETTLED, predates this
amendment): FLAG / INELIGIBLE.** The bar's own reported OHLC values are
never used. Its own timestamp is never imputed. Its timestamp still
counts when measuring the duration of a neighboring genuine gap (same
document, Section 4.C).

**C -- genuine missing-timestamp gaps (SETTLED, predates this
amendment): exact elapsed duration.** The gap threshold is measured as
`EPOCH(next_present_ts) - EPOCH(prev_present_ts)` -- true elapsed
duration, not a minute-truncated approximation. **If this duration is
strictly less than 180 seconds, the existing Section 13 short-gap
forward-fill rule may apply.** **If this duration is 180 seconds or
greater, the gap is excluded, not imputed.** The 180-second boundary is
exact: **180 seconds itself falls on the excluded side, not the
forward-filled side** (`<180` forward-filled; `>=180` excluded). **This
exact-seconds interpretation is recorded as a prospective methodological
choice made by explicit human decision, not as a finding about what the
original preregistration author intended** -- that original intent was
investigated and found inconclusive (same document, Section 4.D, Section
7). This is stated explicitly because the original preregistration never
specified the boundary's exact unit, and this document does not
retroactively claim it did.

### 2. Newly approved: category D -- positive-volume, structurally valid bars

**ACCEPT**, including numerically extreme positive-volume values. No
arbitrary positive-volume exclusion threshold is introduced -- none is
derivable from available evidence, and inventing one would itself be an
unjustified, outcome-adjacent choice. Extreme values **may be flagged
for reporting or diagnostic purposes**, but are not excluded or specially
treated. **Positive volume is not, and is not claimed to be, conclusive
proof of a genuine trade** -- no trade-count field exists anywhere in
this family's schema to confirm this, and vendor-level trade
confirmation is unavailable. This limitation is not resolved by this
approval and is not claimed to be.

### 3. Newly approved: category E -- structurally invalid bars

**EXCLUDE outright, under any circumstance.** A bar is structurally
invalid, and therefore excluded, if **any** of the following holds:

- `high < low`
- `open` outside `[low, high]`
- `close` outside `[low, high]`
- any of `open`/`high`/`low`/`close` is null, non-finite, or `<= 0`
- `volume < 0`

For a structurally invalid bar: **its own OHLC values are never used.
Its own timestamp is never repaired or forward-filled, regardless of
gap length.** Its timestamp still counts when measuring the duration of
a neighboring genuine gap (the same "counts toward span length, never a
target for imputation" treatment already settled for category B1 above).
**Extreme positive volume alone is never treated as structural
invalidity** -- a numerically extreme but otherwise structurally valid
positive-volume bar belongs in category D above, not here.

### 4. PRESENT-VALID -- formally defined for the first time in this document

**A bar is PRESENT-VALID if it is positive-volume and structurally valid
(category D), or zero-volume with `open=high=low=close` (category A1).**
Its own OHLC close is used directly as the endpoint price; no
forward-fill step is invoked for a PRESENT-VALID bar, since there is
nothing missing to fill.

**[PRECISION CORRECTION, 2026-11-14 (same day, same amendment -- not yet
committed): the paragraph above, as originally drafted, left the A1
(zero-volume, flat-OHLC) branch under-specified in a way that could be
read as conflicting with category E below.** This is a precision
correction to the wording, not a new methodological decision and not a
change to any approved rule's substance -- A1, B1, D, and E are all
unaffected in what they approve; only the stated precedence between A1
and E is made explicit, since the original wording did not say which
governs when both might appear to apply to the same bar.

**The A1 (zero-volume, OHLC-flat) branch of PRESENT-VALID requires all
of the following, jointly**:
- `volume = 0`
- `open = high = low = close`
- all four OHLC values are finite and strictly positive (`> 0`)

**The positive-volume branch (category D) is unchanged**: positive
volume and structurally valid, including numerically extreme
positive-volume values, with no arbitrary cutoff.

**Category E structural invalidity takes precedence over the A1 branch.
A structurally invalid bar is never PRESENT-VALID, even if its OHLC
values happen to be equal to one another.** Concretely: a bar with
`volume = 0` and `open = high = low = close = 0` (or any non-finite or
`<= 0` value in that flat quadruple) satisfies category E's own
"any OHLC value null, non-finite, or `<= 0`" exclusion criterion
(Section 3 above) and is therefore structurally invalid -- it does
**not** qualify for the A1 branch merely because its four prices are
equal to each other. Category E is evaluated first, or equivalently
(the result is identical either way): A1 only ever applies to a bar that
is also not structurally invalid.

**This correction does not alter the approved scope of A1, B1, D, or E**:
A1 (zero-volume, OHLC-flat bars, now explicitly finite-and-positive) is
still accepted; B1 (zero-volume, OHLC-non-flat bars) are still
functionally absent with their own timestamp never imputed; D
(structurally valid positive-volume bars, including extreme values) are
still accepted with no invented cutoff; E (structurally invalid bars)
are still excluded outright. The FUNCTIONALLY ABSENT and imputation-
eligibility text below this paragraph is unaffected and is not restated
here.]**

**A bar is FUNCTIONALLY ABSENT**, for the sole purpose of classifying the
length of a surrounding genuine gap (including Section 12's 90%
entity-day-completeness count), if it is a true absent expected
timestamp, or zero-volume with non-flat OHLC (category B1), or
structurally invalid (category E). A functionally-absent bar does not
split an otherwise-contiguous absence run into two separately-measured
shorter runs.

**Only a true absent expected timestamp -- never a category-B1 or
category-E bar's own timestamp -- is eligible to receive an imputed
value under Section 13's forward-fill mechanism.** If an endpoint
computation needs exactly a category-B1 or category-E timestamp, that
endpoint is excluded outright, regardless of how the surrounding
combined span is classified. Treating a bar as functionally absent for
span-length classification does not, by itself, authorize imputing a
value at its own timestamp -- these are two separable operations, and
this document does not conflate them.

### 5. Stage A / Stage B precedence -- the two stages do not share identical imputation rules

**This distinction is stated explicitly because the two stages must
never be read as applying the same rule interchangeably:**

**Stage A -- pre-signal eligibility** (the unified eligibility check at
`t-35`, `t-5`, and `t`, `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 3C step 2):

- The approved bar-validity rules above (PRESENT-VALID / A1 / B1 / D / E)
  apply identically at all three endpoints.
- The existing Section 13 short-gap rule **may** forward-fill a
  genuinely absent timestamp, **only** when the exact elapsed gap
  (category C, above) is strictly less than 180 seconds.
- This eligibility determination happens **before** the eligible subset
  and its weights are frozen (step 3) -- not after, and not
  retroactively revised once frozen.
- **A structurally invalid bar (E) or a zero-volume, OHLC-non-flat bar
  (B1) can never have its own timestamp imputed, at any of the three
  Stage A endpoints, regardless of surrounding gap length.**

**Stage B -- forward endpoint at `t+h`** (the zero-tolerance forward
check, same proposal section, steps 7-9):

- **The existing strict zero-tolerance rule is preserved exactly,
  unchanged by this amendment.** Every member of the frozen pre-signal
  subset must have a valid forward endpoint at `t+h`.
- **If even one frozen-subset member lacks a valid forward endpoint, the
  entire observation is discarded.** No forward-endpoint imputation,
  substitution, reweighting, replacement, partial return, or
  missing-value treatment of any kind is permitted, for any horizon,
  under any circumstance.
- **Stage B takes precedence over the general Stage A short-gap rule.**
  The Stage A short-gap forward-fill rule (category C, `<180` seconds)
  applies **only** to Stage A's own pre-signal endpoints (`t-35`, `t-5`,
  `t`) -- it must **never** be applied to a Stage B forward endpoint
  (`t+h`). A `t+h` endpoint that would qualify for Stage A's short-gap
  forward-fill, were it a pre-signal endpoint, is **not** forward-filled
  at Stage B -- it is evaluated only as PRESENT-VALID or not, with any
  failure triggering whole-observation discard under Stage B's own rule.

### 6. Session scope -- reused unchanged, not reopened

**All endpoint, gap, and run-validity logic above applies only within
verified regular trading sessions.** This reuses, without modification,
the Decision 21 governing calendar and its exclusions (AMENDMENT 9 LOG,
Section 4; Section 12) -- the approved 2,457-date governing calendar and
the 2,456-date primary-sample calendar, the 4 included weekend specials,
the 11 excluded non-session dates, and the conservative exclusion of
`2021-02-24`. **Off-session rows are excluded from all endpoint and gap
logic, for any date, regardless of cause** -- a row outside the regular
session window is never treated as adjacent to a regular-session row for
gap-length or run-length purposes. **Session identity is never inferred
from incidental archive rows.** **This amendment does not modify
Decision 21's calendar, reopen any of its sub-questions, or alter which
dates are included or excluded.**

### 7. What this amendment does NOT do

It does not claim this approval resolves the underlying vendor-semantics
uncertainty for zero-volume bars, or proves that any positive-volume bar
reflects a genuine trade -- both remain permanently unverifiable
limitations, stated as such in
`lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md` Sections 4.A-4.C
and preserved unedited there. It does not recalculate, re-measure, or
modify any empirical finding in that document (the exact-duration
exclusion rates, the structural-violation counts, the zero-volume
clustering pattern) -- all are reused exactly as measured. It does not
reopen Decisions 14, 19, 20, 21, 22, or 23. It does not modify
`lead_lag/trial_ledger.json`, any source code, SQL, data, the master
spec, or any other strategy family. It does not authorize Phase 4, a
primary gate, regression, diagnostic, or any outcome inspection.

---

## AMENDMENT 11 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 24 APPROVED: governing exchange-session calendar determines monthly roster ranking dates

**Status: a new decision -- Decision 24, which calendar source
determines the first trading session of each calendar month for monthly
roster ranking purposes -- is now APPROVED, by explicit user decision on
2026-11-14. Not yet committed -- this edit exists only in the working
tree, pending review, layered on top of AMENDMENT 2 through 10 LOG (also
not yet committed) and `9f71b65` (committed, unchanged).**

**Chronology, stated explicitly**: `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md`
Section 4.1, cited and preserved unchanged by AMENDMENT 7 LOG's own "does
NOT do" paragraph (above -- see the dated note appended there, Section 4
below), found that `prices_eod`'s own `series='EQ'` calendar and
`bars_1min`'s own archive-presence calendar disagree on "first trading
day of month" in 4 of 120 documented months: `2016-10`, `2020-02`,
`2025-02`, and `2026-02`. That finding was left explicitly open,
"folded into Decision 21's existing scope," by both AMENDMENT 7 LOG and
AMENDMENT 9 LOG -- neither amendment resolved it. **This amendment
resolves it now, by explicit user decision, without re-running or
extending that audit's own measurement.**

### 1. Decision 24 -- APPROVED, 2026-11-14: the governing exchange-session calendar determines ranking dates

**The first trading session of each calendar month, for monthly
leader/follower roster ranking purposes, is determined by the governing
exchange-session calendar -- the same calendar already established for
Decision 10 (AMENDMENT 2 LOG, resolutions 3-4: `src/data_layer/nse_holidays.py`
+ `data/raw/nse_cm_holidays.pkl` plus explicit special-session
verification) and reused unchanged for Decision 21 (AMENDMENT 9 LOG,
Section 4) -- not by raw presence in `prices_eod`, and not by raw
presence in `bars_1min`.** Applying Decision 21's own treatment exactly,
with no new calendar logic invented:

- **The four verified weekend special sessions -- `2020-02-01`,
  `2024-01-20`, `2025-02-01`, `2026-02-01` -- are included** as genuine
  governing-calendar trading sessions. Where one of these falls on or
  before the first weekday of its calendar month (`2020-02-01`,
  `2025-02-01`, and `2026-02-01` are each the 1st of February), **it is
  the governing first trading session of that month for ranking
  purposes** -- not the following weekday, even though `prices_eod` has
  no `series='EQ'` row for that date (`MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md`
  Section 4.1). `2024-01-20` is not near a month boundary and does not
  affect any ranking-date selection; it is included in the governing
  calendar for the same reason, for completeness and consistency.
- **`2021-02-24` is excluded from the primary sample**, per Decision 21
  (AMENDMENT 9 LOG, Section 4) -- its session identity remains
  unresolved, and the internal inconsistency found in
  `REGULAR_SESSION_FINAL_BAR_AUDIT.md` is unchanged and not revisited
  here. This date is not near a month boundary and was not found to
  affect any ranking-date selection; it is excluded for consistency with
  the already-approved treatment, not because a specific ranking-date
  conflict was found.
- **Missing `bars_1min` archive coverage does not redefine an exchange
  trading session.** The archive's own presence or absence of rows for
  a given date is a data-availability fact about one specific table, not
  evidence about whether the exchange actually held a session that day.
  The governing calendar (nse_holidays.py plus verification) is the sole
  authority for session identity; neither `prices_eod` nor `bars_1min`'s
  own raw presence overrides it.
- **The `2016-10-03`-versus-`2016-10-04` discrepancy is the known
  intraday-archive-start artifact, not a calendar disagreement.**
  `bars_1min` begins at `2016-10-04`
  (`lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md` Section 2); `2016-10-03`
  is `prices_eod`'s own first `2016-10` EQ row and is, per the governing
  exchange-session calendar, a genuine trading day (an ordinary Monday,
  not an NSE holiday). The archive's absence of `bars_1min` rows for
  `2016-10-03` reflects when the intraday archive itself begins
  collecting data, not a dispute about whether `2016-10-03` was a real
  trading session. This document does not characterize this as a
  calendar-source disagreement.

### 2. Three distinct concepts, kept explicitly separate

This amendment introduces no new mechanism beyond clarifying which of
three already-distinct concepts governs ranking-date identification:

- **The governing exchange-session calendar** (nse_holidays.py plus
  explicit special-session verification, Decision 10/21) -- determines
  **which calendar dates are genuine trading sessions**, including which
  one is the first session of a given month. This is the calendar this
  amendment adopts for ranking-date determination.
- **`prices_eod.turnover`** -- the exclusive source of the turnover
  values themselves, used to rank entities within the trailing-60-session
  window (Decision 23, AMENDMENT 7 LOG, unchanged by this amendment). This
  table's own `series='EQ'` row presence is relevant only to whether a
  turnover observation exists for a given entity on a given date within
  that window -- it is not used to determine which date is the "first
  trading day of the month."
- **`bars_1min`** -- the source of intraday observation availability for
  the signal-side eligibility checks (Stage A/B, Decisions 11, 17, 22)
  that determine whether the roster can actually be *used* at a given
  signal-minute. This table's own row presence is likewise not used to
  determine ranking dates.

**These three concepts are not interchangeable, and none of the other
two is used as a substitute calendar source for the first.**

### 3. Decision 23's existing rules -- preserved exactly, not altered

**None of the following, already approved under Decision 23 (AMENDMENT
7 LOG), is changed by this amendment:**

- Turnover source remains exclusively `prices_eod.turnover` -- never
  `bars_1min`, never close-times-volume, never an adjusted-price
  derivation.
- The trailing-60-session window still uses each entity's last 60
  qualifying observations with `trade_date < ranking_date`, strictly.
- The ranking date's own turnover remains excluded.
- The roster is still frozen using only information available as of the
  close of the trading session immediately preceding the ranking date.
- The roster still becomes effective from the ranking date's own first
  trading session.
- The annual top-200 universe construction (`src/fibo/universe.py`,
  `reconstitute_annually`, `effective_universe`) is unchanged and remains
  a separate, upstream step, unaffected by which calendar identifies a
  given month's ranking date.

**This amendment changes only which calendar is consulted to identify
*which date* is "the ranking date" -- it does not touch what happens
once that date is identified.**

### 4. What this amendment does NOT do

It does not alter `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md`'s
own measured findings or wording -- that document's 4-of-120-month
mismatch finding, its reconstruction methodology, and its own stated
conclusions are reused exactly as measured and are not retroactively
characterized as having already assumed this amendment's resolution at
the time that audit was conducted; that document is not edited by this
amendment. It does not reopen Decision 10's or Decision 21's own
governing-calendar definitions (both reused unchanged, not re-derived).
It does not reopen any other part of Decision 23. It does not modify
`lead_lag/trial_ledger.json`, any source code, data, roster artifact, the
master spec, or any other strategy family. It does not authorize Phase
4, a primary gate, diagnostic, or any outcome inspection. It does not
perform or require any new empirical reconstruction -- the governing
calendar's own dates were already established by Decision 10/21's prior
work and are reused here, not recomputed.

---

## AMENDMENT 12 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decisions 7, 8, and 9 APPROVED: final control set, fixed-effects specification, and prior-day NIFTY50 regime control

**Status: three decisions -- Decision 7 (final control set), Decision 8
(fixed-effects specification), and Decision 9 (prior-day NIFTY50 regime
control) -- are now APPROVED together, by explicit user decision on
2026-11-14. Not yet committed -- this edit exists only in the working
tree, pending review, layered on top of AMENDMENT 2 through 11 LOG (also
not yet committed) and `9f71b65` (committed, unchanged).**

**A structural documentation gap found while drafting this amendment,
stated explicitly, not silently worked around**: this document's own
"Section 11: controls (X)" has never been updated for the portfolio-level
Option A estimand -- it still describes the **original, pre-amendment
per-follower control set** (follower's own trailing-5-minute raw return,
`B_follower_LOO`, trailing 30-day realized volatility, time-of-day
bucket, trailing-60-session turnover rank), not `R_F(t)`, `TOD(t)`, or
`Momentum_F(t)`, and this document contains no copy of the primary
regression equation at all -- that equation exists only in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
("Control evaluation and final proposed regression equation," Section
6). **This amendment does not rewrite Section 11** -- its original text
is preserved, per this document's own preservation discipline, as the
accurate historical record of the original per-follower design -- but
appends a dated note there pointing to this amendment as the actual,
current, operative control-set record for the approved portfolio-level
estimand.

### 1. Decision 7 -- APPROVED, 2026-11-14: final control set

**Primary regression controls** (as specified in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 6's existing
equation, unchanged by this amendment -- see Section 2 of this log):

- `R_F(t)` -- contemporaneous follower-portfolio return. **Required as
  part of the base estimand**, not a discretionary addition.
- `TOD(t)` -- categorical time-of-day control, using the existing
  opening-30 / midday / closing-30 buckets.
- `Momentum_F(t)` -- follower-portfolio return over the disjoint earlier
  window, using the already-approved exact-endpoint construction
  (Decision 13).

**Other variables, approved as sensitivity-only or diagnostic-only,
never primary controls**:

- **Trailing realized volatility** (leader and/or follower): not a
  default regression control; sensitivity-only, included only if a
  specific purpose is separately justified -- none is asserted by
  default.
- **Coarse trading activity**: a diagnostic comparison of excluded vs.
  included days. **Not a regression control.**
- **Prior-day NIFTY50**: governed separately by Decision 9 below;
  sensitivity-only, never a primary control.

**The existing primary regression equation and its variable definitions
are unchanged by this amendment** -- this approval adopts the control
set the equation in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 6 already specifies; it does not alter that equation or any
variable's definition.

### 2. Decision 8 -- APPROVED, 2026-11-14: fixed-effects specification

- **Primary specification: no fixed effects.**
- **Sensitivity specification: year fixed effects.**
- **No quarter fixed effects** -- not adopted at either the primary or
  sensitivity level.
- **Year fixed effects must remain a sensitivity analysis and must not
  replace the no-fixed-effects primary specification**, under any
  circumstance.

### 3. Decision 9 -- APPROVED, 2026-11-14: prior-day NIFTY50 regime control

- **Prior-day NIFTY50 is omitted from the primary regression.**
- **It may be included as a sensitivity control**, explicitly labeled a
  **coarse daily-regime proxy** -- never described as an intraday
  benchmark, an independent intraday market factor, or a market-adjusted
  control.
- **Only the prior trading day's close-to-close return may be used.**
  **The same day's closing return must never be used** -- it is not
  knowable intraday and using it would be a look-ahead.
- **This approval does not resolve, and does not claim to resolve, the
  existing structural limitation already stated in this document**
  (Section 9 of the original construction, reproduced at this
  document's own "What this construction can and cannot rule out"
  passage): **no independent intraday market or sector index exists** in
  the data available to this family. That limitation is preserved
  exactly as already stated and is not weakened, strengthened, or
  resolved by approving a coarse daily-regime proxy as a sensitivity-only
  control.

### 4. What this amendment does NOT do

It does not change the existing primary regression equation or any
variable's definition (all remain exactly as specified in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 6). It does
not rewrite Section 11's own legacy per-follower control-set text --
that text is preserved unedited as historical record, with a dated note
appended pointing here. It does not change Decisions 10, 11, 12, 13, 14,
15, 16, 17, 19, 20, 21, 22, 23, or 24 -- Decision 12 (the bootstrap
block-length/run-length sub-parameters) remains the one OPEN row this
amendment does not touch. It does not modify
`lead_lag/trial_ledger.json`, any source code, data, the master spec, or
any other strategy family. It does not authorize Phase 4, a primary
gate, diagnostic, or any outcome inspection.

---

## AMENDMENT 13 LOG (2026-11-14, DRAFTED, NOT YET COMMITTED) -- Decision 18 APPROVED: fixed monthly roster identity, no dynamic availability-based reconstitution

**Status: Decision 18 (fixed monthly roster identity -- whether roster
membership may ever be altered mid-month based on signal-time
availability) is now APPROVED, by explicit user decision on 2026-11-14,
immediately prior to Phase 4 implementation authorization. Not yet
committed -- this edit exists only in the working tree, pending review,
layered on top of AMENDMENT 2 through 12 LOG (also not yet committed) and
`9f71b65` (committed, unchanged).**

**Chronology**: `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 3A and decision-table row 18 have described this rule as
RECOMMENDED since this family's 2026-11-08 revision -- it was never
formally approved as a decision-table row, even though it was
consistently treated as the operative assumption throughout every
subsequent audit and amendment in this family (Decisions 10, 17, 19,
20's Stage A/B constructions all presuppose a fixed roster; none of them
separately re-derived or re-justified it). **This amendment closes that
gap.**

### 1. Decision 18 -- APPROVED, 2026-11-14: fixed monthly roster identity

- **Leader and follower roster identities remain fixed for each monthly
  roster period** -- membership does not change within a month once the
  roster is constructed (Section 6/7, Decision 23/24's ranking-date and
  calendar-source conventions).
- **Membership is determined solely by the monthly liquidity-tier
  assignment** (trailing-60-session turnover rank, top ~20% = leaders,
  remainder = followers, per Section 6/7) -- never by signal-time price
  availability.
- **No signal-time availability-based additions, removals, or
  replacements.** A name's own bar-level availability at any particular
  `t`, `t-35`, `t-5`, or `t+h` governs only that single observation's
  Stage A/Stage B eligibility (Decisions 17, 19, 20) -- it never alters
  the roster's own membership for that month, for any other observation,
  or for any other name.
- **No dynamically filtered or reconstituted basket during the month.**
  The roster is not re-ranked, re-filtered, or re-selected mid-month
  under any circumstance.

**This is the same rule `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 3A already describes and decision-table row 18 already
recommended -- this amendment approves it exactly as stated, changing no
substance.**

### 2. What this amendment does NOT do

It does not change Option 2's own per-observation Stage A/Stage B
construction (Decisions 17, 19, 20, 22) -- those operate entirely within
a single, already-fixed roster and are unaffected. It does not change
Decisions 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, or 24 --
Decision 12 remains the one OPEN row. It does not modify
`lead_lag/trial_ledger.json`, any source code, data, the master spec, or
any other strategy family. It does not itself authorize Phase 4
implementation -- that authorization is recorded separately, in the
project's own task history, not by this documentation amendment.

---

## AMENDMENT 14 LOG (2026-11-15, DRAFTED, NOT YET COMMITTED) -- Decision 12 APPROVED: bootstrap block-length sub-parameters, derived L=6

**Status: Decision 12 (the bootstrap block-length `L`'s three open
sub-parameters -- the minimum `n_k` for a lag to be evaluable, the
minimum consecutive qualifying run length `R`, and the minimum usable-
block count) is now APPROVED, by explicit user decision on 2026-11-15.
This closes the last remaining OPEN row referenced throughout AMENDMENT
2 through 13 LOG above (each preserved unedited as an accurate
historical record of Decision 12's status at the time it was written).
Not yet committed -- this edit exists only in the working tree, pending
review, layered on top of AMENDMENT 2 through 13 LOG and `9f71b65`
(committed, unchanged).**

**Chronology**: `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 7B fully specified the block-length *procedure* (fixed initial
lag range 1-10, the `+/-2/sqrt(n_k)` decay band, the deterministic
run-length/extension/maximum-lag-20 rule, taking the larger of the
signed- and squared-residual series' own `L`) while leaving three
numerical sub-parameters open, "to be set by reference to standard
time-series-diagnostic/block-bootstrap practice once the real,
post-exclusion day counts are known." Phase 5 built the real, full-
history (2016-10-04 to 2026-09-18) controls-only baseline-model
residual series (`Y` regressed on `R_F`, `TOD`, `Momentum_F` --
`S_L` deliberately excluded, per Section 7B.0's own hypothesis-
predictor-free construction) and ran the unchanged procedure under two
candidate sub-parameter sets, before any approval, to see whether the
result was sensitive to the choice:

| Parameter set | `min_n_k` | `R` | `min_usable_blocks` | `L` (signed) | `L` (squared) | `L` | usable blocks |
|---|---:|---:|---:|---:|---:|---:|---:|
| Conservative | 30 | 2 | 20 | 1 | 6 | **6** | 310 |
| Stricter | 50 | 3 | 30 | 1 | 6 | **6** | 310 |

Both candidate sets agree on `L=6` against the real data (1,861 usable
days). The user reviewed this evidence and approved the conservative
set's exact values, not a different set chosen because it produced a
more favorable number -- both sets produced the identical `L`, so there
was nothing to choose between on that basis.

### 1. Decision 12 -- APPROVED, 2026-11-15: bootstrap block-length sub-parameters

- **`min_n_k = 30`** -- the minimum number of valid pairwise-complete
  day-pairs for a lag to be evaluable at all (below this, a lag is
  reported indeterminate, per Section 7B.3 -- unchanged).
- **`R = 2`** -- the minimum consecutive qualifying run length (the
  construction floor established by Section 7B.4's own isolated-
  terminal-lag correction; no stricter value was found necessary).
- **`min_usable_blocks = 20`** -- the minimum number of usable blocks
  (`n_usable_days // L`) for the resulting `L` to support reliable
  block-bootstrap inference (Section 7B.4's final contingency check).
- **Derived block length: `L = 6`** -- the larger of the signed-residual
  series' own result (`L=1`, found within the initial 1-10 lag range)
  and the squared-residual series' own result (`L=6`, also found within
  the initial 1-10 lag range; mild, short-lived volatility-clustering-
  type dependence, unsurprising for financial returns and fully
  consistent with ordinary market behavior, not a defect).
- **Evidentiary basis**: the real, full-history (2016-10-04 to
  2026-09-18) controls-only baseline-model residual series, 1,861 usable
  days, computed by `src/lead_lag/block_length.py` (the unchanged
  Section 7B procedure) via `src/lead_lag/regression.fit_ols` against
  `R_F`, `TOD_opening_30`, `TOD_closing_30`, `Momentum_F` only --
  `S_L` was never a regressor in this computation, so no `beta`,
  p-value, or effect size for the propagation hypothesis exists anywhere
  in the evidence this decision rests on.
- **Resulting usable-block count: 310** at `L=6`, comfortably above
  `min_usable_blocks=20` under either tested parameter set.
- **Not tuned to outcome**: the two candidate parameter sets were
  compared to each other, never to any `beta`, p-value, significance
  level, or the real `S_L`-`Y` relationship, which this computation
  never touches.

### 2. What this amendment does NOT do

It does not change the block-length *algorithm* (Section 7B's
procedure, `block_length.py`, is unmodified) or substitute a different
candidate value for `L`. It does not change Decisions 7, 8, 9, 10, 11,
13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, or 24. It does not run the
primary (`S_L`-including) regression, compute or reveal any real `beta`,
p-value, or effect size, or inspect the `S_L`-`Y` relationship in any
way. It does not modify `lead_lag/trial_ledger.json`, any other source
code, data, the master spec, or any other strategy family. It does not
authorize the primary empirical evaluation -- that remains a separate,
explicit authorization, not granted by this documentation amendment.

---

## AMENDMENT 15 LOG (2026-11-15, DRAFTED, NOT YET COMMITTED) -- Decision 25 APPROVED: null-imposed inference methodology, split-bootstrap design, draw-count convention; real structural preflight findings recorded

**Status: Decision 25 (the complete primary-coefficient inference
methodology -- block-bootstrap hierarchy, residual alignment, the
null-imposed p-value procedure, the split between unrestricted CI/SE
and null-imposed significance testing, and the bootstrap draw-count
convention) is now APPROVED, by explicit user decision on 2026-11-15.
This closes the inference-machinery gap identified at the end of
Phase 5 (Section 7C's own "subject to final human approval" hierarchy,
and Section 14's original, less specific "day-clustered... 1,000-draw
block bootstrap as a cross-check" language). Not yet committed -- this
edit exists only in the working tree, pending review, layered on top
of AMENDMENT 2 through 14 LOG and `9f71b65` (committed, unchanged).**

**Chronology**: following Decision 12's approval (AMENDMENT 14 LOG),
a focused engineering and verification cycle (i) implemented a
vectorized null-imposed, anchor-matched residual block bootstrap in
`src/lead_lag/inference.py`; (ii) synthetically calibrated it across
3 day-level dependence strengths x 2 match-rate levels (4,000 outer
repetitions, 10,000 inner draws each -- 40 million total inner fits)
plus a focused 2,000-repetition extension on the two scenarios that
showed zero rejections in the first pass; (iii) synthetically verified
power near the 20bps effect-size boundary (8 scenarios straddling
10/19/21/40bps, both signs, 300 repetitions each); (iv) verified the
h=60 schedule's structurally-zero-column property against both
`lstsq` and normal-equations solvers; (v) ran a real-data, strictly
outcome-blind structural preflight (never importing `lead_lag.returns`,
never reading a price/outcome value) reconstructing the real retained-
observation index fresh, independently reproducing Phase 5's own 3,761-
observation count with zero outcome access. All evidence is summarized
below; none of it constitutes, or is derived from, a real primary beta,
p-value, or S_L-Y relationship.

### 1. Decision 25 -- APPROVED, 2026-11-15: null-imposed inference methodology

**(a) Primary and sensitivity block-bootstrap hierarchy.**

- **Primary**: consecutive multi-day block bootstrap, block length
  `L=6` (Decision 12's own derived value, AMENDMENT 14 LOG) -- construct
  every contiguous window of 6 trading-session positions in the
  governing calendar's own ordered date sequence; draw
  `ceil(n_session_positions / 6)` such blocks with replacement per
  resample.
- **Sensitivity**: independent single-day-cluster bootstrap, block
  length `L=1` -- the identical procedure and formula, changing only
  the block length (Section 7C's own framing: one mechanism at two
  block lengths, not two separate implementations).
- Implemented as `src/lead_lag/inference.py::null_imposed_block_bootstrap`
  (general function), `primary_null_imposed_bootstrap` (`L=6`) and
  `sensitivity_null_imposed_bootstrap` (`L=1`) (thin wrappers).

**(b) Residual alignment (anchor-keyed matching).**

- Donor and target observations are matched using their **identical
  scheduled anchor** (`t`), derived from the approved
  `schedule.non_overlapping_schedule(horizon)` function -- never
  hardcoded, never row-order-based.
- A donor day's **complete residual structure is preserved**: all of
  that day's own matched anchors move together as one unit to whichever
  target position drew that donor.
- An observation is **excluded**, never recycled/interpolated/
  substituted, if the drawn donor day lacks that same anchor.
- **Repeated donor-block draws remain independent bootstrap
  occurrences** -- a donor day drawn at two different positions in the
  same or different resamples contributes independently at each
  position; its residuals are read, never consumed.

**(c) Null-imposed pseudo-outcome construction.**

Fit the controls-only null model once:

```
Y ~ R_F + TOD_opening_30 + TOD_closing_30 + Momentum_F
```

(`S_L` excluded -- the same reduced-control set Decision 12's own ACF
diagnostic already used). For each bootstrap replicate:

1. Real target observations and their complete predictor values
   (including `S_L`) are held fixed.
2. Donor-day blocks are drawn per (a) above.
3. Residuals are matched to targets by anchor, per (b).
4. `Y_star = null_fitted(target) + matched_donor_residual`.
5. The **complete, unmodified primary regression** (including `S_L`)
   is refit on `(real X, Y_star)`.
6. The `S_L` coefficient (`beta_star`) is extracted.

**No additional residual centering is applied** beyond the null
model's own OLS residuals (which already have exact zero mean over the
full estimation sample by the normal equations; a resampled subset's
realized mean need not be exactly zero, which is expected bootstrap
behavior, not a defect).

**(d) Two-sided, finite-sample-corrected null-imposed p-value.**

```
p = (1 + count(|beta_star| >= |beta_hat|)) / (1 + n_valid)
```

where `beta_hat` is the real, un-resampled point estimate and `n_valid`
is the count of resamples that produced a usable refit. **This
null-imposed bootstrap p-value is the sole source of the primary
hypothesis-test p-value** -- never the unrestricted bootstrap's own
sign-count statistic, and never an IID or other unapproved analytic
approximation.

**(e) Rank-deficiency handling.** A resample is excluded (counted, not
substituted) if its matched-row count is below the number of
parameters, or if its weighted design's rank falls **strictly below**
the real, full design's own baseline rank (`k_eff`, computed once from
the unresampled data) -- never merely for matching that baseline. This
distinguishes a genuine, bootstrap-specific loss of identification from
the h=60 schedule's own permanent structural property (Section 4
below), which every resample necessarily inherits and must not be
treated as a failure on that account alone.

### 2. Split-bootstrap design -- a new methodological decision, approved as part of Decision 25

**Two methodologically distinct, independently-computed bootstrap
procedures, sharing the same approved block structure, are never
combined:**

- **Unrestricted case-resampling block bootstrap**
  (`block_bootstrap_beta`/`primary_block_bootstrap`/
  `sensitivity_single_day_cluster_bootstrap`, pre-existing, unchanged):
  each resample redraws whole days' real rows (with real `Y`), refits
  the complete primary regression, and the resulting `beta` distribution
  supplies the **coefficient standard error and confidence interval**
  (raw `[alpha/2, 1-alpha/2]` percentiles).
- **Null-imposed, anchor-matched residual block bootstrap** (Section 1
  above): supplies **only** the two-sided hypothesis-test p-value.

**Why separate**: the null-imposed `beta_star` distribution is centered
at/near zero *by construction* (the null is imposed on every
replicate) -- it is not a valid basis for a confidence interval around
the real, unrestricted `beta_hat`, which is centered near `beta_hat`
itself. Conversely, the unrestricted bootstrap's own sign-count
statistic is a CI-duality test, not a null-imposed test, and is not
used as the primary significance decision. **The primary gate's
statistical-significance criterion is evaluated using only the
null-imposed p-value, at the operative alpha (Decision 16,
`0.05/8 = 0.00625`)**; the unrestricted CI/SE is reported for effect-
size and direction context, never substituted for the significance
decision. Neither procedure uses an IID or other analytic standard
error anywhere.

### 3. Bootstrap draw-count convention

- **Requested null-imposed bootstrap draws: 10,500**, for both the
  primary (`L=6`) and sensitivity (`L=1`) procedures, applied
  identically and reported separately for each.
- **Minimum successful valid draws required: 10,000.**
- Failed draws (`n_failed_total = n_failed_empty_or_unmatched +
  n_failed_rank_deficient`) are always counted and reported, never
  silently substituted or omitted; `n_valid + n_failed_total ==
  n_resamples_requested` holds by construction (verified by test).
- **If fewer than 10,000 valid draws are obtained for either
  procedure, the primary evaluation must stop and report insufficient
  valid draws** -- the required minimum is never silently lowered, and
  a shortfall is never silently patched by drawing additional resamples
  under a different seed or procedure.
- This 10,500-requested/10,000-minimum-valid check is a **protocol-
  level requirement applied by whoever executes the real evaluation**,
  using the `n_valid` field `null_imposed_block_bootstrap` already
  exposes -- it is not, and does not need to be, a hard-coded exception
  inside the bootstrap function itself, which already reports every
  quantity the check requires.

### 4. Real-data structural preflight findings (outcome-blind; no S_L/Y/beta/p-value/significance was computed or accessed)

- **Historical period**: 2016-10 through 2026-09. **Trading days with
  at least one retained observation: 1,861.** **Independently
  reconstructed retained observations: 3,761** -- exactly reproducing
  Phase 5's original count via a fresh recomputation that never
  imported `lead_lag.returns` and never read a price/outcome value.
- **Five scheduled h=60 anchors**: `09:19, 10:24, 11:29, 12:34, 13:39`.
- **Zero retained observations at `09:19`**, for a deterministic,
  structural reason verified independently of any data: that anchor's
  own `t-35 = 08:44` precedes the `09:15` session open, so Decision 22's
  Momentum_F minimum-anchor requirement (`t-35 >= 09:15`) can never be
  satisfied there, for any day, by construction.
- **Consequence**: `TOD_opening_30` is structurally zero across the
  entire real historical dataset (not merely a synthetic-test
  artifact), **in addition to** `TOD_closing_30`'s own permanent,
  schedule-derived zero-column property (established without any data
  access at all: no h=60 anchor falls in the `15:00-15:29` closing
  window). **Effective real primary design rank: `k_eff = 4`** (of 6
  parameters: intercept, `S_L`, `R_F`, `TOD_opening_30`,
  `TOD_closing_30`, `Momentum_F`).
- **Both zero-variance regressors are handled correctly by the
  existing, unmodified implementation** -- verified directly: feeding
  the exact real `(trade_date, t)` structural pattern (with fabricated
  placeholder numeric values, never real outcomes) into
  `primary_null_imposed_bootstrap` produces `k_eff=4`,
  `zero_variance_regressors=('TOD_opening_30','TOD_closing_30')`, and
  zero failures across 2,000 resamples -- no code change was required;
  the rank-baseline mechanism (Section 1(e)) generalizes correctly to
  more than one structurally-degenerate column.
- **Mean structural anchor-match rate** (presence-only simulation, no
  outcome values, 2,000 resamples each): **`L=6`: ~36.89%**; **`L=1`:
  ~36.80%** -- both block lengths give materially the same rate, as
  expected (match rate is governed by cross-day anchor-presence
  overlap, not block length). The distribution is stable and narrow
  (observed range ~31.7%-42.2%), with no evidence of occasional
  near-zero-coverage resamples.
- **No calendar or anchor-alignment inconsistencies were found**: zero
  retained `trade_date`s fall outside the governing primary-sample
  calendar; zero retained `t` values fall outside the approved 5-anchor
  schedule.
- **No additional minimum-coverage threshold is adopted** -- the
  observed match-rate distribution does not justify one, and none is
  invented.
- **Relation to synthetic calibration**: the real structural match
  rate (~37%) sits in the same range as, or below, the synthetic
  `drop_prob=0.4` calibration scenario, which an extended 2,600-
  repetition run found to be **measurably conservative** (empirical
  Type I error 0.04%-0.12%, materially below the nominal 0.625% target,
  with 95% Clopper-Pearson intervals excluding the nominal rate). **The
  conservative-bias regime found in synthetic calibration is therefore
  the operative regime for this real study, not an edge case.**
  Conservative bias is the safe direction (it only costs power; it
  never inflates false positives) -- a real result clearing
  `alpha=0.00625` under this regime is, if anything, stronger evidence
  against the null than the nominal level alone would suggest. **This
  finding is reported as a real, confirmed property of the synthetic
  calibration exercise and the real data's own structural shape; it is
  not, and does not substitute for, a claim that synthetic calibration
  establishes the real run's own exact Type I error.**
- **Structural findings are categorically distinct from empirical
  return/predictive findings.** No primary outcome (`Y`, `S_L`, `R_F`,
  `Momentum_F`), no regression coefficient, and no p-value was computed
  or inspected at any point during the structural preflight.

### 5. What this amendment does NOT do

It does not change the primary regression specification
(`Y ~ S_L + R_F + TOD_opening_30 + TOD_closing_30 + Momentum_F`), the
portfolio-level estimand, the primary horizon (60 minutes), the sample,
or the controls. It does not change the preregistered success criteria
(`beta > 0`; `beta * sigma(S_L) > 20bps` strictly; two-sided
null-imposed bootstrap `p < 0.00625`; all three required). It does not
change the existing multiplicity accounting (formal trial count 7,
operative denominator 8, `alpha = 0.05/8 = 0.00625`) -- no inconsistency
was found in this accounting during this amendment's review, so none
was changed. It does not change Decisions 1-24, the trial ledger, the
master spec, or any other strategy family. It does not authorize the
primary empirical evaluation, inspection of any real outcome, or any
real-data regression fit -- those remain separate, explicit
authorizations not granted by this documentation amendment.

---

## Section 0: reuse boundaries, read-only

Unchanged from the original version. No existing strategy file is
touched. See the original Section 0 reuse list (`entity_panel`,
`isin_lineage`, `corporate_actions`, `adjustment`, `fibo.universe`,
`fibo.intraday_db`, `factors.target`, `factors.ic_eval`,
`box_theory.inference.day_clustered_bootstrap`, `data_layer.holdout`),
plus, new in this amendment: `lead_lag/ledger.py` (trial-ledger
enforcement, governance tooling, not strategy logic) and
`lead_lag/MASTER_SPEC_LEAD_LAG.md` (reference document). No existing
family's module is modified anywhere in this amendment.

---

## Section 1: research hypothesis (REFRAMED)

**Original framing (overclaimed)**: "cross-stock lead-lag propagation...
information diffusion, common-factor transmission, or asynchronous
repricing across related securities."

**Corrected framing**: within the existing point-in-time
top-200-by-turnover universe, do abnormal 5-minute cumulative return
spreads between the most liquid stocks ("leaders," top ~20% by trailing
turnover) and the least liquid stocks ("followers," remaining ~80%)
predict the followers' subsequent abnormal returns, over a fixed forward
horizon, after controlling for the followers' own recent momentum and
contemporaneous follower-pool co-movement?

**This design, as specified, cannot distinguish between at least four
candidate mechanisms, and does not claim to**:

1. **Genuine delayed repricing** -- leaders possess or process
   firm-specific or market-wide information faster, and that information
   genuinely propagates to followers with a lag (the mechanism implied by
   the original "information diffusion" framing).
2. **Common market-factor reactions at different speeds** -- both tiers
   are reacting to the same observable or unobservable shock, with
   liquid names simply repricing faster because they trade more
   frequently, with no information flowing from specific leaders to
   specific followers at all.
3. **Non-synchronous trading** -- a classical market-microstructure
   effect (Lo-MacKinlay-style): illiquid names trade and update prices
   less frequently by construction, so their *observed* returns
   mechanically lag liquid names' *observed* returns, even when the
   *true* (unobserved, continuously-updating) prices of both groups move
   together with no lag at all.
4. **Stale-price effects** -- a related but distinct artifact of
   infrequent trading in the follower tier producing bars whose closing
   price has not been refreshed by a recent trade, independent of any
   genuine predictive relationship.

**OHLCV data alone cannot conclusively distinguish these four
mechanisms.** Doing so would require order-book-level data, trade-by-trade
timestamps, or an identified natural experiment -- none of which this
project has. The market-factor null (Section 16c) and the reverse-direction
diagnostic (Section 16d) narrow the space of plausible explanations but do
not resolve it; this is stated here explicitly so a PASS verdict (Section
20) is never read as having isolated mechanism (1) specifically. A PASS
means "a liquidity-tiered return-propagation pattern exists and survives
the stated controls and nulls" -- not "information diffuses between
specific leader and follower companies."

This is a **measurement** question, not a trading-strategy proposal. A
statistically detectable coefficient does not by itself authorize a
trading simulation -- see Section 20.

---

## Section 2: primary estimand

**MODEL-LEVEL STATUS NOTE (2026-11-14, added by a documentation-repair
task -- read this before the formula below).** Everything in this section
is the **historical, per-follower, leave-one-out-demeaned specification**,
exactly as it read before any of the Decision 10/11/13/22 approvals above.
**It is not the model that currently governs this study.** The user has
separately approved a **portfolio-level estimand ("Option A")** as
primary, documented in full in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` (Section 11, decision
item 1: "Option A (portfolio-level estimand) as primary | **APPROVED**";
decision item 2: "Drop old individual-follower specification from this
study | **APPROVED**"). Under Option A, the operative model is:

```
Y(t,h) = alpha + beta * S_L(t) + gamma * R_F(t) + delta . X(t) + epsilon(t,h)
```

where `S_L(t) = R_L(t) - R_F(t)`; `R_L(t)` is the leader-portfolio
contemporaneous return; `R_F(t)` is the follower-portfolio contemporaneous
return; `Y(t,h)` is the follower-*portfolio* forward return (not a
per-entity `AR_follower(j,t->t+h)` as below); and the primary controls are
`R_F(t)`, `TOD(t)`, and `Momentum_F(t)` (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 6). This is **the currently governing model.** `R_L(t)`, `R_F(t)`,
`Y(t,h)`, and `Momentum_F(t)` are all constructed under the Decision
13-approved exact-endpoint-price convention (AMENDMENT 4 LOG above) --
**prospectively, for Phase 4 implementation not yet written**; no code
implementing either the historical or the portfolio-level model exists
anywhere in this repository (confirmed by
`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` Section 2's
repository-wide search, not re-run here).

**This note does not change the mathematical model, introduce a new
control, or alter the formula below.** The per-follower specification
immediately below is preserved exactly as originally written -- it is the
accurate historical record of what this section specified before Option A
was approved, and remains a correct description of Section 8/9's own,
separately-preserved historical construction (Sections 8-9 below are
likewise unedited). It must simply not be read, going forward, as the
specification Phase 4 will implement.

**Three distinct things, now explicitly separated, so a reader is never
left to guess which one governs**:
1. **Historical methodology and historical calculations** -- this
   section's `AR_follower(j, t->t+h)` formula below, and Section 8/9's
   `S_leader(t)`/`B_follower_pool`/`B_follower_LOO` constructions. Accurate
   record of what was specified and measured before the Option A
   approval; not deleted, not retroactively rewritten.
2. **The approved portfolio-level estimand** -- `Y(t,h)`, `S_L(t)`,
   `R_L(t)`, `R_F(t)` as defined above and in
   `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Sections 1 and 4;
   this is the model Phase 4 is to implement, mathematically unchanged
   from what the proposal specifies.
3. **The prospective Phase 4 implementation convention** -- Decision
   13's exact endpoint-price return construction (`r_i(a,b) =
   P_i(b)/P_i(a) - 1`, AMENDMENT 4 LOG above), which supplies the endpoint
   arithmetic for `R_L`, `R_F`, `Y`, and `Momentum_F` under the Option A
   model; it does not retroactively describe how `S_leader(t)` (item 1)
   was actually computed.

---

### Historical formula (per-follower, leave-one-out-demeaned -- superseded by Option A above, preserved unedited below)

Unchanged in form from the original version; the error term's dependence
structure and the predictor's own construction are both addressed more
carefully below (Sections 8, 9, 17) following the degeneracy fix.

```
AR_follower(j, t -> t+h) = alpha + beta * S_leader(t) + gamma . X(j,t) + epsilon(j,t,h)
```

- `j` indexes a follower-tier entity, `t` indexes a completed 1-minute bar
  (the signal-end minute), `h` is the forward horizon (Section 10).
- One row = one (follower entity j, trading day, signal-minute t)
  observation. `S_leader(t)` is **not** follower-specific -- it is one
  pooled value shared by every follower row at a given (day, minute).
  This is stated explicitly because it is exactly the property that made
  the original Section 16b selection null ineffective (Amendment Log
  item 2) and is load-bearing for the corrected null's design (Section
  16b below).
- `AR_follower(j, t->t+h)` is entity j's forward h-minute abnormal
  (leave-one-out-benchmark-adjusted) return, Section 9.
- `S_leader(t)` is the equal-weighted leader-portfolio signal, Section 8
  (corrected construction).
- `X(j,t)` is the predetermined control vector, Section 11.
- Pooled across all eligible (follower, trading-day, signal-minute)
  observations; inference uses day-clustered standard errors (Section 14).

Reported alongside beta (not a bare p-value): standard error, 95% CI,
implied economic magnitude at +/-1 observed sigma of `S_leader`,
incremental R-squared over the controls-only model, stability across
years and across the liquidity-tier boundary.

---

## Section 3: data sources

Unchanged from the original version. No new data fetch of any kind is
required. No existing fact table is written to. (See the original
Section 3 table: `bars_1min` in `data/fibo_intraday.duckdb`; `prices_eod`
in `data/warehouse.duckdb` via `read_full_entity_panel_authorized`;
`isin_lineage`, `corporate_actions`/`adjustment_factors`;
`fibo.universe.reconstitute_annually`; `index_eod` -- NIFTY50 only, not
used as the intraday benchmark since no intraday index series exists;
sector/industry files -- explicitly not used.)

**Operational note added in this amendment**: `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
found `read_full_entity_panel_authorized(...)` raised a `MemoryError` on
its first call in the environment used for that analysis (succeeded on
retry). Phase 4 implementation should use the lighter direct
`prices_eod` + `isin_lineage` join for turnover-ranking purposes
specifically (turnover is split-invariant, so adjustment factors are not
needed for that one purpose), reserving the full adjusted panel for where
split/bonus-adjusted prices are actually required (return computation on
intraday bars, which uses `bars_1min` directly, not `entity_panel` at
all).

---

## Section 4: universe definition

Unchanged from the original version: `fibo.universe.reconstitute_annually`,
annual top-200-by-turnover, point-in-time, capped to the existing
`fibo_intraday.duckdb` date range (2016-10-04 to 2026-09-18). Known,
inherited survivorship-bias limitation, not re-solved here (see original
Section 4).

---

## Section 5: historical sector grouping

**None. Not used anywhere in this design.** Unchanged from the original
version. See Section 1's reframing above for why this changes what the
study can and cannot claim.

---

## Section 6: leader definition, WITH REAL MONTHLY BREADTH (corrected)

**Construction, unchanged from the original version**: within each
year's point-in-time top-200-by-turnover annual universe (Section 4), on
the first trading day of each calendar month, rank eligible entities by
trailing-60-trading-session median daily rupee turnover (raw, from
`prices_eod`, point-in-time -- no bar after the ranking date is used).
Top 20% of that month's eligible pool = leaders; held fixed for the
month. An entity with fewer than 60 trailing sessions of history as of
the ranking date is excluded from that month's eligible pool.

**[DECISION 23 -- APPROVED, 2026-11-14, AMENDMENT 7 LOG: "no bar after
the ranking date is used" is clarified, not changed, by explicit user
decision -- the trailing-60-session window excludes the ranking date's
own turnover observation (`trade_date < ranking_date`, strictly), not
merely dates after it. The roster is frozen as of the close of the prior
trading session and becomes effective from the ranking date's own first
trading session. See AMENDMENT 7 LOG for the full record and
`lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` for the underlying
audit. This paragraph's original wording is preserved unedited above, per
this document's existing preservation discipline -- the clarification
does not alter the `>=60`-session eligibility rule, the 20% split, or any
tie-breaking convention.]**

**Real monthly breadth, computed for the first time in this amendment**
(`LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1, read-only, against the
real construction above -- not Phase 2's lifetime-turnover proxy):

| Year | eligible min/med/max | leaders min/med/max | followers min/med/max |
|---|---|---|---|
| 2016 (stub, Oct-Dec) | 193/194/195 | 39/39/39 | 154/155/156 |
| 2017 | 196/200/200 | 40/40/40 | 156/160/160 |
| 2018 | 198/200/200 | 40/40/40 | 158/160/160 |
| 2019 | 200/200/200 | 40/40/40 | 160/160/160 |
| 2020 | 196/200/200 | 40/40/40 | 156/160/160 |
| 2021 | 194/200/200 | 39/40/40 | 155/160/160 |
| 2022 | 189/200/200 | 38/40/40 | 151/160/160 |
| 2023 | 198/200/200 | 40/40/40 | 158/160/160 |
| 2024 | 189/200/200 | 38/40/40 | 151/160/160 |
| 2025 | 181/200/200 | 37/40/40 | 144/160/160 |
| 2026 (through Sep) | 187/200/200 | 38/40/40 | 149/160/160 |

**Headline correction: the real construction gives ~40 leaders / ~160
followers per month (91 of 120 months, 76%, sit exactly at 40/160), not
the 77/309 lifetime-turnover-proxy figure that appeared in
`LEAD_LAG_FEASIBILITY.md` Section 1a and was carried into this document's
original Section 6 commentary.** The proxy used lifetime total turnover
across all 386 entities ever observed in the full 10-year archive (top
20% of 386 = 77); the real construction ranks within each year's current
~200-name annual universe (top 20% of ~196-200 = ~39-40) -- roughly half
the breadth. This does not change the qualitative feasibility conclusion
(40/160 is still an operationally ample candidate set, zero new
infrastructure required), but 40/160 replaces 77/309 as the number this
family's documents should cite going forward.

**2017-2019 are NOT materially thinner than later years** (contrary to
what the original amendment-planning hypothesis expected, based on a
different, unrelated thinness finding in `LEAD_LAG_FEASIBILITY.md`
Section 1b about a 252-day correlation-window check that does not apply
to this construction). The only recurring pattern is a **post-reconstitution
dip every January-March** (and the three 2016 stub months): new entrants
to that year's top-200 annual universe have not yet accumulated 60
trading sessions of history by the time the Jan/Feb/Mar ranking date
arrives. The pool recovers to the full ~200 by April every year without
exception. Worst month in the full 10-year range: **2025-01, 181
eligible / 37 leaders / 144 followers** -- still an ample sample, no
feasibility concern.

---

## Section 7: follower (laggard) definition

Unchanged from the original version: all entities eligible that month
(Section 4) not in that month's leader tier (Section 6) -- the bottom
~80% by trailing turnover (~160/month, per Section 6's corrected count).
Additional per-observation eligibility filters per Section 12.

---

## Section 8: leader signal construction (CORRECTED -- fixes the degeneracy)

**This section is historical methodology, per Section 2's model-level
status note above -- it describes the per-follower specification's own
`S_leader(t)`, not the approved portfolio-level `R_L(t)`/`S_L(t)`.**
Preserved unedited; not the model Phase 4 implements.

**The original construction in this section was algebraically degenerate
and is replaced below.** See Amendment Log item 1 for the full discovery
and derivation.

For each leader-tier entity `i` and each completed 1-minute bar `k`:

```
B_follower_pool(k)  = equal-weighted mean of r(j,k) over ALL followers j in that month's follower tier
AR_leader(i,k)      = r(i,k) - B_follower_pool(k)
S_i(t)              = sum_{k=t-4}^{t} AR_leader(i,k)      [5-minute trailing cumulative, fixed in real minutes]
S_leader(t)         = (1/n_t_return) * sum_i S_i(t)       [equal-weighted across leader-tier entities with a computable S_i(t) under Decision 17's return-construction rules, subject to the n_t_breadth gate below]
```

**Critical difference from the original**: the leader's own abnormal
return is now benchmarked against the **follower pool**, not against
other leaders. No leave-one-out exclusion is applied on this side,
because a leader is never itself a member of the follower pool -- there
is no self-contamination risk here, unlike the follower side (Section 9),
where a follower IS a member of the group its own benchmark is drawn
from and leave-one-out remains necessary there.

**Why this is non-degenerate (the algebra the original construction
failed)**:

```
S_leader(t) = (1/n_t) * sum_i sum_k [r(i,k) - B_follower_pool(k)]
            = [mean cumulative leader-portfolio return over the window]
              - [cumulative follower-pool return over the same window]
```

This is the cumulative 5-minute **return spread between the leader
portfolio and the follower portfolio** -- two different, non-identical
groups of stocks, so there is no algebraic reason for this quantity to be
zero, and empirically it is not (a diagnostic substitute of this same
form, `mean_leaders - mean_universe`, measured sigma = 3.92 bps over a
~230-day, 11-month pilot sample -- `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
Section 3.1; the exact `mean_leaders - mean_followers` form specified here
has not yet been measured on real data and must be the first thing Phase
4 verifies, per Section 21 below).

Equal weighting, not turnover-weighting, per the original design's
explicit instruction (master spec Part 4.3, now `lead_lag/MASTER_SPEC_LEAD_LAG.md`
Part 4.3 -- "do not choose weights after observing results").

**Minimum per-minute breadth floor** (`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
Task 2): `S_leader(t)` is **not computed** for a given minute unless
`n_t_breadth >= 0.80 * (that month's leader-tier size)`. Evidence: pooled across
an 11-month, 1-per-year sample (86,250 leader-tier minute-observations,
post-open-auction-exclusion per Section 12), the frac-of-tier-present
distribution is 0.825/0.875/0.875/0.95 at the 1st/10th/25th/50th
percentiles -- leader-tier breadth is virtually always complete
(pooled zero-volume-bar fraction across the sample: 3.1e-7). A 0.80
floor excludes only the single genuine outlier minute found in the full
sample (`2020-06-11 14:21:00`, 13/40 = 32.5% breadth) -- roughly 0.001%
of minutes -- while a stricter floor (0.90+) would needlessly discard
~35.7% of minutes that are in fact fine (a handful of leaders missing a
bar by routine, non-systemic chance). This floor is frozen now, per
Section 23, not tuned after Phase 4 output exists.

**Breadth count vs. return-construction count, explicitly distinguished
(Decision 10 amendment, 2026-11-14, following the calendar/breadth
feasibility audit)**: two separate counts exist at minute `t`, and must
not be conflated:

- **`n_t_breadth`** -- counts **present-valid bars only** (Decision 17's
  category 1: positive-volume structurally valid, or zero-volume-flat).
  An absent bar that Decision 17 permits forward-filling (`<180` seconds
  from the nearest preceding present-valid bar) does **NOT** count toward
  `n_t_breadth`. This is the count tested against the `0.80` floor above,
  and it is the count the cited evidence base
  (`LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 2) actually measured --
  its own method counted "valid-bar leader entities" at each `(trade_date,
  ts)` directly from present rows, with no forward-fill step, so the
  0.825/0.875/0.875/0.95 percentile evidence above was always
  present-valid-only and remains unchanged by this clarification.
- **`n_t_return`** -- the divisor actually used in the `S_leader(t)`
  formula above: the (possibly larger) set of leader-tier entities with a
  **computable** `S_i(t)` under Decision 17's existing, unchanged
  return-construction rules, which may include an entity whose bar at `t`
  (or at an earlier bar within the `t-4..t` window) was forward-filled
  under the `<180`-second rule. **Permission to forward-fill an endpoint
  for return computation does not imply permission to count that
  forward-filled value as a contemporaneously observed leader for
  breadth-eligibility purposes.** Decision 17's forward-fill rule is, and
  remains, a return-construction mechanism only; it is not extended to the
  breadth gate.

Measured over the full 2016-10-04 to 2026-09-18 archive, `n_t_breadth` and
`n_t_return` differ on 308 of 151,962 day-rule-surviving minutes (mean
difference 0.0023 leaders, max 38), and the two counts cross the `0.80`
floor differently on exactly **3** scheduled observations: `2017-07-12`
(`t=11:19`, horizons 5 and 15 minutes) and `2021-03-31` (`t=14:34`,
horizon 30 minutes). Under this amendment's approved `n_t_breadth`
definition, these 3 observations are correctly excluded (they pass the
floor only if forward-filled leaders are miscounted as present). Full
observation-level accounting: `lead_lag/DECISION_10_RECONCILIATION_ADDENDUM.md`.

`S_leader(t)` is only computed, and only usable as a predictor, after bar
`t` has fully closed. Its timestamp convention (bar-start vs bar-end) is
still to be verified empirically in Phase 4 hand-tracing (Section 21)
before any aggregate result is trusted -- unchanged requirement from the
original version.

---

## Section 9: benchmark construction (clarified following the Section 8 fix)

**This section is historical methodology, per Section 2's model-level
status note above.** Preserved unedited; not the model Phase 4 implements.

Two distinct follower-pool quantities are now in play, and this amendment
names them separately to avoid the ambiguity that contributed to the
original degeneracy going unnoticed:

```
B_follower_pool(k)     = equal-weighted mean of r(j,k) over ALL followers that month
                         [used ONLY in Section 8's leader-signal construction -- no exclusion, since no leader is ever a follower]

B_follower_LOO(j,k)    = equal-weighted mean of r(j',k) over OTHER followers j' != j, that month
                         [used for follower j's OWN abnormal return AND as a control for follower j -- leave-one-out IS required here, because j is itself a member of the group forming its own benchmark]

AR_follower(j,k)        = r(j,k) - B_follower_LOO(j,k)
```

`B_follower_pool(k)` and `B_follower_LOO(j,k)` differ only by whether `j`
itself is excluded from the average over a ~160-name pool -- numerically
almost indistinguishable for any single `j`, but conceptually distinct
and kept separately labeled, because conflating them is exactly the kind
of "collapse a leave-one-out quantity back into its own group" mistake
that produced Section 8's original degeneracy.

**No leader ever enters any follower's benchmark, in either direction**
-- `B_follower_pool` and `B_follower_LOO` are both built exclusively from
followers. This preserves the original intent behind Part 4.1's
leave-one-out requirement ("a leader's own movement must not mechanically
contaminate the laggard's benchmark") exactly, while fixing the
degeneracy by making the **leader's own signal** (not the follower's
benchmark) draw on a disjoint pool (followers) instead of a
self-referential one (other leaders).

**What this construction can and cannot rule out, stated explicitly per
the independent review's finding**: no intraday NIFTY or any other index
series exists (Section 3), so there is no benchmark external to this
two-tier split itself. The market-factor null (Section 16c) tests whether
`S_leader(t)` adds predictive power beyond `B_follower_LOO` and the
follower's own momentum -- this tests "is this more than a contemporaneous
bivariate correlation," but it **cannot** distinguish a genuine
leader-to-follower information flow from both tiers reacting to one
shared, unobserved factor at different speeds (Section 1's mechanisms 1
vs 2 vs 3). This limitation is structural, not a gap this study can close
with the data available, and is not resolved by the Section 8 fix.

---

## Section 10: prediction horizons

Unchanged from the original version. Primary horizon: 60 minutes.
Secondary/robustness: 30 minutes. Exploratory, non-gating: 5 and 15
minutes. All expressed in real trading minutes. Selection was variance-only
(Phase 2), not outcome-dependent -- reaffirmed, with the caveat noted in
Section 17 that since every horizon's original MDE cleared the (now
superseded) cost-floor comparison by a wide margin, the horizon choice was
always more of an economic bet ("more room for a real effect to clear
costs") than a power-maximizing choice, and should be read as such.

---

## Section 11: controls (X)

Unchanged from the original version (follower's own trailing-5-minute raw
return; `B_follower_LOO` over the same window; follower's trailing
30-day realized volatility; time-of-day bucket; follower's trailing-60-session
turnover rank within the follower pool). No control added or removed in
this amendment.

**[DECISIONS 7, 8, 9 -- APPROVED, 2026-11-14, AMENDMENT 12 LOG.** This
section describes the **original, pre-amendment per-follower control
set** and has never been updated for the approved portfolio-level
Option A estimand -- it is preserved above unedited as the accurate
historical record of the original design, not as the current operative
control set. **The current, approved primary controls for the
portfolio-level estimand are `R_F(t)`, `TOD(t)`, and `Momentum_F(t)`**,
exactly as specified in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 6's existing,
unchanged primary regression equation; trailing realized volatility,
coarse trading activity, and prior-day NIFTY50 are sensitivity/
diagnostic-only, never primary. The primary specification uses no fixed
effects; year fixed effects are sensitivity-only; quarter fixed effects
are not adopted. See AMENDMENT 12 LOG for the full record.]**

---

## Section 12: exclusions

Unchanged from the original version (pre-open/opening-auction bars;
final-5-minutes-before-close signal-end minutes whose forward window
would cross 15:30; <90%-bar-completeness entity-days; +/-1-trading-day
corporate-action windows **[DECISION 20 -- APPROVED, 2026-11-14,
AMENDMENT 9 LOG, Section 3: this existing window is applied as a Stage A
eligibility condition at `t-35`, `t-5`, and `t` -- a constituent inside
its own window at a required endpoint is ineligible for that observation,
excluded before the frozen subset is formed, through the same mechanism
as any other endpoint-validity failure. Not a second, parallel, whole-day
filter. See AMENDMENT 9 LOG for the full record.]**; whole-day exclusion -- **exclude the entire
[SESSION-BOUNDARY WORDING CLARIFICATION, 2026-11-14, added by a
documentation-repair task -- precision only, no new rule, no changed
horizons or schedule]: "final-5-minutes-before-close" is sized for the
smallest horizon (`h=5`) and must not be misread as a fixed, horizon-independent
5-minute cutoff -- the actual, general rule, which the phrase "whose
forward window would cross 15:30" already states and which this note only
makes explicit, is: **for prediction horizon `h`, a signal-end minute `t`
is excluded if `t+h` would require a bar at or after `15:30`** -- i.e. the
last eligible `t` for horizon `h` is the last regular-session minute such
that `t+h` still falls on or before the session's final regular bar. **No
next-session fallback, nearest-available-bar substitution, or any other
form of carrying a forward endpoint into the next trading session is
permitted for any horizon, under any circumstance** -- this mirrors
Decision 22's identical prohibition for `Momentum_F(t)` (AMENDMENT 5 LOG,
Section 3) and is stated here explicitly so a future implementation cannot
accidentally reach across the session boundary for `Y(t,h)`.
**Implementation clarification still required, not resolved here, and not
guessed at**: this document does not independently verify, from a direct
query of `bars_1min`, that `15:29` is in fact the last regular-session bar
on every trading day in the governing calendar (the close-side mirror of
Decision 11's question about the first regular-session bar) --
if the last bar ever differs from `15:29` on some date, the exact final
eligible minute for a given horizon on that date would shift accordingly,
and that has not been checked.]** **[STATUS UPDATE, AMENDMENT 6 LOG,
2026-11-14: Decision 11 (the first-bar question) is now APPROVED at
`09:15`. This close-side question about `15:29` is a separate, independent
question, not resolved or touched by that approval -- it remains
unconfirmed by direct query here, and is addressed separately, on a
read-only, non-binding basis, in `lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md`
and `lead_lag/FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md`, which found `15:29`
coverage collapses on a specific, identified set of dates. Neither audit
changes this document's governing rules; both are cited here only to avoid
implying the close-side question is unexamined anywhere.]** -- exclude the entire
trading day if fewer than 50% of that month's leader tier has a valid
bar; equivalently, retain the day iff `n_day >= 0.50 * leader-tier size`**
(corrected wording, Decision 10 amendment, 2026-11-14 -- the original
text here read "...if <50%...lacks a valid bar," which inverts the
intended predicate; the rule itself, its 0.50 threshold, and its
implementation are unchanged, and this correction agrees exactly with
Section 23's own, always-correct statement of this same rule, ">=50% of
tier has a valid bar")). Section 8's per-minute breadth floor
(`n_t_breadth >= 0.80 * leader-tier size`) is an additional, minute-level
exclusion layered on top of the existing day-level 50% floor -- the two
operate at different granularities and both apply.

**Governing trading-session calendar (Decision 10 amendment, 2026-11-14,
following the calendar/breadth feasibility audit).** Raw distinct
`bars_1min.trade_date` presence is **not, by itself, sufficient proof of
a genuine trading session** -- the archive contains dates that are
weekends or NSE holidays with incidental rows, and weekday dates whose
only rows are an evening special session (no regular-hours trading at
all). The governing session calendar for this family is established
jointly by:

1. **`src/data_layer/nse_holidays.py` + `data/raw/nse_cm_holidays.pkl`**
   (project-internal NSE CM-segment holiday source, covering 2016-2026,
   built specifically to distinguish genuine holidays from failed or
   premature data fetches) -- used for holiday classification. This
   source is a holiday list, not a complete trading-session calendar by
   itself, and is not modified by this amendment.
2. **Explicit special-session verification** -- a date that the holiday
   source marks as a weekend or holiday is nonetheless included in the
   governing calendar if the archive shows a genuine full-length
   regular-hours session on it (in this family's audited history: four
   such dates, `2020-02-01`, `2024-01-20`, `2025-02-01`, `2026-02-01`,
   each with all 375 regular-session minutes populated across 180-198
   entities and independently corroborated as real special trading
   sessions). A weekend/holiday date with only a partial or absent
   in-window session (e.g. an evening-Muhurat-only cluster, or a single
   end-of-window artifact bar) is **not** included merely because
   `bars_1min` has some row for it that day.
3. **Dates with ambiguous session status are flagged, not silently
   classified either way.** Within the already-audited 2016-10-04 to
   2026-09-18 archive window, this has already been done exhaustively:
   `lead_lag/DECISION_10_RECONCILIATION_ADDENDUM.md` classifies all 2,468
   raw archive dates with no date left unresolved (every date's
   regular/non-regular/special-session status is established from
   weekday arithmetic, the NSE CM holiday master, `prices_eod` presence,
   and in-window intraday coverage, all in agreement) -- **no date in
   this audited set remains ambiguous.** This flagging principle governs
   **future or newly-encountered dates only** (e.g. if the archive is
   ever extended past 2026-09-18): any such date must be resolved using
   the same calendar evidence and special-session verification procedure
   before it is included in any denominator, not silently classified
   either way by default.

The **raw archive-date count (2,468, all distinct `bars_1min.trade_date`
values) remains available for historical reconciliation only** and must
not be presented as the authoritative trading-session denominator. The
**governing trading-session denominator is 2,457 dates** -- the 2,468
raw archive dates, less the 11 verified to have no genuine regular
session (5 ordinary weekdays with evening-Muhurat-only data; 1 weekday
NSE holiday with only a 1-hour special session; 2 weekend dates with no
in-window session at all; and 3 weekend dates, including `2016-10-30`,
with only a partial or single-artifact-bar in-window footprint). **The 4
genuine weekend special-trading-session dates are weekends and therefore
part of this subtraction's complement, not an addition to it -- they
remain included in the 2,457 throughout, per point 2 above.** See the
reconciliation addendum for the exact per-date classification and
arithmetic.

**[DECISION 21 -- APPROVED, 2026-11-14, AMENDMENT 9 LOG, Section 4.** The
governing 2,457-date calendar above is unchanged and remains the
authoritative figure for every historical measurement that already used
it -- this note does not retroactively alter any prior count. **A new,
narrower primary-sample figure is approved for analysis going forward:
2,456 dates -- the governing 2,457-date calendar, less `2021-02-24`**,
excluded conservatively because its session identity was already
flagged unresolved and because `lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md`
itself was found to contain mutually inconsistent statements about this
date's own in-window coverage (that document is not edited by this
note). The 4 genuine weekend special sessions remain included in both
the 2,457 governing figure and the 2,456 primary-sample figure, under
the unmodified session convention. See AMENDMENT 9 LOG, Section 4, for
the full record.]**

---

## Section 13: missing-data handling

Unchanged from the original version: <3-consecutive-minute gaps
forward-filled for return computation; >=3-minute gaps excluded, not
imputed. Frozen, per Section 23.

**[DECISION 17 -- APPROVED, 2026-11-14, AMENDMENT 10 LOG.** This
section's "3-minute"/"<3-consecutive-minute" wording is clarified, not
changed: the unit is **exact elapsed timestamp duration** between the
bounding present-valid rows (`EPOCH(next) - EPOCH(prev)`), not a
minute-truncated approximation. **The boundary is exact at 180 seconds:
strictly less than 180 seconds forward-fills; 180 seconds or more
excludes** -- 180 seconds itself is on the excluded side. **This exact-
unit interpretation is a prospective methodological choice made by
explicit human decision on 2026-11-14, not a claim about the original
preregistration author's intent**, which was investigated and found
inconclusive. This rule applies only to genuine absent-timestamp gaps
within the regular session (Decision 21's calendar, reused unchanged) --
it is never applied to a Stage B forward endpoint (`t+h`), which remains
governed by its own zero-tolerance rule regardless of gap length. See
AMENDMENT 10 LOG for the full policy, including the formal PRESENT-VALID
definition and the Stage A/Stage B precedence statement.]**

---

## Section 14: statistical methodology

Unchanged from the original version: day-clustered OLS standard errors
(cluster = `trade_date`); 1,000-draw day-level block bootstrap as a
cross-check, fixed seed 20261107; non-overlapping-sample robustness check
(one observation per follower per day); no individual-minute-level
resampling anywhere.

---

## Section 15: registered-configuration ledger and multiple-testing correction

**The registered-configuration ledger is `lead_lag/trial_ledger.json`,
validated by `lead_lag/ledger.py` (7 passing tests,
`lead_lag/test_ledger.py`), rather than a hand-maintained table in this
document.** It contains **six** registered configurations.
`ledger.denominator()` returns `len(trials)` = **6** -- this is the
**registered-configuration count**, not the operative multiplicity-family
denominator. **Do not use `ledger.denominator()` as the Bonferroni
divisor for the future primary gate.** Under Decision 16 (AMENDMENT 3 LOG
above), the operative multiplicity-family denominator is **8** (the six
registered configurations plus Option 1 and Option 2), giving a
prospective two-sided primary-gate alpha of **`0.05/8 = 0.00625`**. The
ledger remains unchanged at six entries; neither basket-construction
configuration is retroactively registered. See AMENDMENT 3 LOG and
Section 23 for the full distinction between six ledger entries, seven
formal trials (six ledger entries plus Option 1, an unregistered Phase 1
feasibility kill), and eight multiplicity-family exposures.

| # | `config_key` | Configuration | Status |
|---|---|---|---|
| 1 | `grouping:liquidity_tier` | Liquidity-tier grouping | Adopted primary |
| 2 | `grouping:statistical_cluster` | Statistical-cluster grouping (5 descriptive threshold cuts, 1 configuration) | Examined, not adopted |
| 3 | `horizon:5min` | 5-minute horizon | Exploratory, non-gating |
| 4 | `horizon:15min` | 15-minute horizon | Exploratory, non-gating |
| 5 | `horizon:30min` | 30-minute horizon | Secondary/robustness |
| 6 | `horizon:60min` | 60-minute horizon | **Primary gate** |

**New, structural enforcement requirement for Phase 4**: before any
configuration reaches a statistical gate (a regression fit that will be
interpreted against Section 20, a null draw, a horizon's DEV result),
Phase 4 code **must** call `ledger.assert_registered(config_key)` --
which raises `UnregisteredConfigurationError` for anything not already in
`trial_ledger.json` -- and **must** call `ledger.record_gate_run(config_key,
run_metadata)` immediately after, which appends an automatic,
timestamped record to the ledger file itself and raises if the
configuration was never registered. This directly addresses the
independent review's finding that this exact project's POC family let
its Bonferroni denominator stay pinned at 2 across three preregistrations
while its real trial count reached 5 (`PROJECT_CONTEXT.md` Section 3,
finding #15) -- a demonstrated failure of prose-only discipline that this
mechanism is built to prevent recurring here. Adding a new configuration
requires hand-editing `trial_ledger.json` and committing that change --
there is no runtime path to grow the trial count silently.

**Primary gate test**: `beta` at h=60 minutes, tested at Bonferroni
alpha = 0.05 / 8 = 0.00625, two-sided, day-clustered SE (**per Decision
16, AMENDMENT 3 LOG -- this supersedes the original `0.05/6 ~= 0.0083`
figure for future primary-gate purposes; the `0.05/6` figure remains
historically accurate as the value computed when only the original six
configurations existed, and is not deleted, only superseded**).
Secondary/exploratory
horizons reported at the same corrected threshold, non-gating. Secondary
BH report via `factors.ic_eval.benjamini_hochberg`, never substituted for
the primary correction. The five null/diagnostic checks in Section 16 are
not counted as additional trials (necessary conditions on one trial's
interpretation, not a separate multiple-comparisons problem), unchanged
reasoning from the original version.

---

## Section 16: null hypotheses

**(a) Timing null (circular time-shift)**: unchanged from the original
version. Per-day circular shift of the follower's forward-return series,
leader-signal series keeps its real timestamps, 1,000 draws, fixed seed
20261107, real `|beta|` must exceed the 95th percentile of the null-draw
distribution.

**(b) Selection null -- REDESIGNED: matched random-leader-portfolio null**

The original design (random follower reassignment against a
follower-agnostic signal) is replaced, per the independent review's
finding that it did not vary the quantity the regression actually tests.

**New construction, REVISED following adversarial re-review** -- the
first draft of this redesign (sent to re-review before any commit, per
the user's explicit procedure) was itself found to have two concrete,
opposite-direction flaws, fixed below rather than caveated around.

**Flaw found in the first draft, fixed here**: the first draft's
candidate pool was "top `2*n_leaders` by turnover" -- but the true
leader tier (top `n_leaders`) is, by that same ranking, exactly the top
half of that pool. A uniform without-replacement draw of `n_leaders` from
a `2*n_leaders` pool containing the true tier as a fixed subset is a
hypergeometric draw with expected overlap `n_leaders / 2` -- **on
average, about half of every "random" portfolio was literally the real
leader tier**, diluting the null's reference distribution toward the
real one (biasing the test conservative -- too hard to pass). Separately,
drawing a **fresh, independent** random portfolio every calendar month
*within* a single repetition pools 120 independent monthly sub-draws into
one `beta_random,r` -- any composition-specific association averages away
across those 120 independent draws, which systematically *narrows* the
between-repetition spread of `beta_random,r` relative to holding one
coherent counterfactual selection rule fixed across the whole sample
(biasing the test anti-conservative -- too easy to pass). These two
biases point in opposite directions and neither was acknowledged in the
first draft; both are fixed below rather than left to cancel by
assumption.

1. **The real follower-side data is held fixed across every repetition**
   -- the same (follower, day, minute) rows, the same `AR_follower`
   values, the same controls `X(j,t)`, exactly as used in the primary
   test. This is "preserve the actual follower portfolio," per the
   redesign requirement, and is standard permutation-test practice
   (condition on the real outcome data, vary only the randomized
   predictor) -- unchanged from the first draft, not itself a flaw.
2. **Candidate pool, now disjoint from the true leader tier (fix for
   Flaw 1)**: that month's candidate pool is ranks `n_leaders+1` through
   `3*n_leaders` by the same trailing-60-session turnover rank used for
   real tiering (i.e., the next two liquidity bands immediately below the
   true leaders -- e.g. ranks 41-120 when `n_leaders=40`) -- **zero
   overlap with the true leader tier by construction**, while still
   liquidity-comparable (the band immediately adjacent to the real tier,
   not an arbitrary or illiquid draw).
3. **Two null variants, both required (fix for Flaw 2)**, rather than
   one:
   - **Null B1 (per-month independent redraw)**: for each repetition
     `r = 1..1000`, draw `n_leaders` entities uniformly at random, without
     replacement, from that month's disjoint candidate pool,
     **independently for each calendar month**.
   - **Null B2 (fixed selection rule per repetition)**: for each
     repetition `r = 1..1000`, draw **one** random subset of
     `n_leaders` **rank-positions** (not entity identities) within the
     disjoint band once, and apply that same rank-position rule to every
     month's actual roster at those positions for the rest of that
     repetition -- entity identities still vary month to month as universe
     membership and ranks shift, but which rank-positions are selected
     does not, so a single repetition reflects one coherent
     counterfactual selection rule held across the full sample, not an
     average over 120 independent monthly draws.
   A fresh draw (B1) or a fresh rank-position rule (B2) is made for every
   repetition; neither is reused across repetitions.
4. Using **the exact Section 8 signal-construction procedure, unchanged**
   -- same 5-minute window, same `B_follower_pool(k)` benchmark, same
   equal weighting, same per-minute breadth floor -- build
   `S_leader_random,r(t)` (separately for B1 and B2) from the
   randomly-drawn portfolio, on the **same real trading days and the same
   real signal-minutes** as the true `S_leader(t)`. Only the identity of
   which stocks populate "leader" changes; nothing about when or how the
   signal is computed changes.
5. Refit the primary regression (Section 2's equation, same controls,
   same horizon) with `S_leader_random,r(t)` in place of the real
   `S_leader(t)`, holding the real follower-side data fixed (step 1), once
   for B1 and once for B2. Collect `beta_random,r` across all 1,000
   repetitions, separately for each variant.
6. **Comparison**: the real `beta` (from the true, top-20%-by-turnover
   leader tier) must exceed the 95th percentile of `|beta_random|`
   (two-sided) **for both B1 and B2 independently** to pass this null
   (Section 20's gate condition 4 is updated accordingly). Requiring both
   is deliberate: B1 and B2 are sensitive to different, opposite-direction
   biases, so a result that only clears one of them is not trusted as a
   clean pass.

**Why this is not another near-no-op**: unlike the original follower-permutation
null, this construction varies `S_leader(t)`'s own realized time series
across repetitions (different stock composition on the same days produces
different realized 5-minute cumulative returns, since individual stocks'
returns are not identical even within a liquidity band) -- it does not
merely relabel rows while leaving the regressor's values untouched. This
was the specific, identified failure mode of the original design. The
revised construction additionally does not share the two further flaws
the adversarial re-review found in this redesign's own first draft
(contaminated candidate pool, narrowed-by-redraw null spread) --
acknowledged here explicitly rather than only rebutting the one failure
mode the independent review happened to name first, per that same
re-review's finding that the first draft's defense paragraph was
one-sided.

**Minor, non-blocking caveat carried forward**: the empirical 95th
percentile of 1,000 draws has its own estimation uncertainty (order
roughly +/-1.3 percentage points under a normal approximation) for a
single pass/fail threshold with no reported confidence interval. Phase 4
should re-run at 5,000 draws as a stability check and confirm the
pass/fail conclusion does not flip before relying on the 1,000-draw
result alone.

**This null must be run on the real, Section-8-corrected `S_leader(t)`,
not on the diagnostic substitute used in `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`'s
pilot** -- the pilot's placebo diagnostic (below) is a different check
answering a different question (sampling noise under zero true effect),
and does not substitute for actually running this redesigned selection
null once Phase 4 code exists.

**(c) Market-factor null**: unchanged in form from the original version
-- nested-model comparison (`X(j,t)` only vs. full model). See Section 9
for the explicit statement of what this can and cannot rule out.

**(d) Reverse-direction diagnostic**: unchanged from the original
version. Diagnostic only, both directions reported regardless of result.

**(e) Placebo diagnostic -- construction detail now pinned down**

`LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Section 3.3 found the original
text ("pair... against `S_leader` drawn from a different... trading day")
was ambiguous between two readings that produced bootstrap SE estimates
differing by more than 10x: an independent random placebo-day draw **per
follower-row**, versus one random placebo-day draw **shared by every
follower on the same real day** (matching how the real `S_leader(t)`
actually works -- one pooled value per day, broadcast to every follower
that day).

**Resolved in this amendment: the per-real-day-shared reading is
correct**, because it is the one that actually matches Section 2's model
(`S_leader(t)` is not follower-specific) -- the per-row-independent
reading implicitly treats the signal as if it varied by follower, which
it does not, and so does not faithfully reconstruct what is being tested.
**All Phase 4 implementations of this diagnostic must draw exactly one
random placebo day per real response day, shared across every follower
row on that day**, with the placebo day at least 20 trading days from the
real day, same intraday minute-of-day. This resolution is frozen now, per
Section 23, not chosen after seeing which reading looks better in a
future run (the pilot's own finding that the two readings disagree by
>10x, with the correct one giving the *smaller* estimate, is recorded
honestly here rather than defaulting to whichever was more conservative).

---

## Section 17: power and minimum detectable effect (MDE) -- REWRITTEN, NO UNCONDITIONAL PASS CLAIMED

**The original version's MDE (1.39-4.22 bps) is withdrawn as a power
statement for this estimand.** It was computed from individual-stock raw
1-minute-bar return variance and a naive day-count, not from the
day-clustered regression coefficient's actual sampling distribution, and
-- independent of that problem -- the predictor it would have applied to
did not exist as specified (Amendment Log item 1). Neither error is
cosmetic; both are acknowledged plainly rather than patched over.

**What is now known, following `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
Task 3**:

1. **The corrected `S_leader(t)` (Section 8) has not yet been measured on
   real data.** Its own empirical sigma -- the quantity Section 2's
   estimand actually needs -- remains unmeasured; this amendment commits
   to measuring it as the first step of Phase 4, before any gate is run
   (Section 21).
2. **A diagnostic substitute signal** (`mean_leaders - mean_universe`
   trailing-5-minute return, a close but not identical proxy for the
   corrected Section 8 construction, which uses `mean_leaders -
   mean_followers` specifically) was used to pilot the dependence-aware
   SE methodology on an 11-month, 230-trading-day, single-fixed-signal-minute
   (10:15) sample, via the Section 16e placebo construction (never
   fitting a contemporaneous, real signal-to-response relationship):
   - Day-clustered block bootstrap (resampling the 230 real response
     days with replacement, redrawing a fresh placebo pairing every
     replicate), 500/500 replicates achieved in 2.2-2.4 seconds -- the
     bootstrap itself is computationally cheap and tractable at this
     scope; full-scale (**2,457 verified trading sessions** -- the
     governing calendar, Section 12, Decision 10 amendment; not the raw
     2,468-date archive count) cost was not measured and should not be
     assumed comparable without checking.
   - Using the methodologically correct (per-real-day-shared, Section
     16e) pairing convention: `SE_boot = 0.0347` (coefficient units),
     giving a design effect of 0.089 relative to a naive non-clustered
     SE (i.e., the day-clustered SE is *smaller* than the naive one in
     this pilot -- a plausible, not yet fully explained, consequence of
     the leave-one-out follower benchmark already stripping out common
     same-day comovement that clustering would otherwise need to
     correct for). **This is a deliberate choice of the smaller,
     non-conservative of the two SE readings found in Task 3.3** (the
     per-row-independent reading gave `SE_boot = 0.1120`, over 3x larger)
     -- used here because it is the one that actually matches Section
     2's model (`S_leader(t)` is one pooled value per day, not
     follower-specific), not because it is favorable; this is stated
     explicitly, since the number happening to be smaller than the
     alternative could otherwise look like cherry-picking.
   - Resulting MDE, **corrected following adversarial re-review of this
     amendment's own first draft** (the first draft used an arithmetically
     wrong Bonferroni critical value, 3.1909; the correct value for a
     two-sided test at alpha=0.05/6 is `z_{1-alpha/2} + z_{power} =
     z_{0.995833} + z_{0.80} = 2.63826 + 0.84162 = 3.47988`) -- **this
     0.05/6-based derivation is HISTORICAL, superseded for future
     primary-gate purposes by Decision 16 (AMENDMENT 3 LOG); retained
     here, not deleted, as the value actually used by this amendment's own
     original 11-month pilot illustration**:
     `0.0347 * 2.80158 ~= 0.0972` (uncorrected, alpha=0.05, power=0.80,
     unaffected by the multiplicity denominator and therefore unchanged by
     Decision 16) to
     `0.0347 * 3.47988 ~= 0.1208` (Bonferroni, alpha=0.05/6, historical)
     coefficient units. Converted via the *proxy's own* sigma (3.92 bps)
     purely for illustration: approximately **0.38-0.47 bps** (historical)
     -- **explicitly not a reliable number**, since it depends on a proxy
     signal, not the real, corrected Section 8 construction.

     **Operative recalculation under Decision 16 (alpha=0.05/8), using the
     identical pilot inputs and the identical formula, for direct
     comparison only** -- not a new measurement, not a new assumption,
     only the multiplicity divisor changed: two-sided critical value
     `z_{1-0.05/16} + z_{0.80} = z_{0.996875} + 0.84162 = 2.73437 + 0.84162
     = 3.57599` (new, replacing 3.47988); coefficient-units MDE `0.0347 *
     3.57599 ~= 0.1241` (new, replacing 0.1208); illustrative bps figure
     (same proxy-sigma conversion, same caveats) `0.1241 * 3.92 ~= 0.49
     bps` (new, replacing 0.47; the uncorrected 0.0972/0.38bps endpoint of
     the range is unaffected by the multiplicity denominator and does not
     change). **Updated illustrative range: approximately 0.38-0.49 bps.**
     **This recalculation updates only the alpha/multiplier used in the
     pilot illustration above -- the resulting ~0.1241 coefficient-units
     figure (and the ~0.49bps illustrative conversion) is, exactly as its
     historical ~0.1208 predecessor was, a pilot-scale illustration on an
     11-month proxy sample, not an operative full-scale MDE. The
     full-scale MDE remains uncomputed, pending the actual full-scale
     signal standard error (`SE_boot` measured on the real, corrected
     `S_leader(t)` at full scale, Section 21 steps 1-2) -- nothing here
     implies the full-scale power gate has passed, or that this pilot
     estimate substitutes for it.** This recalculation carries every
     caveat the historical one carried
     (proxy signal, not the real Section 8 construction; not a power
     statement; superseded at Phase 4 once the real signal's sigma is
     measured, per Section 21 step 1-2) -- it does not newly validate
     anything about Option 1, Option 2, or the propagation hypothesis
     itself. (Algebraic note on how close a
     placeholder this proxy actually is: since the proxy is
     `mean_leaders - mean_universe` and, with stable tier sizes
     `n_L~=40, n_F~=160`, `mean_universe` is a turnover-weighted blend of
     both tiers, `mean_leaders - mean_universe ~= (n_F/(n_L+n_F)) *
     (mean_leaders - mean_followers) ~= 0.8 *` the real Section 8 signal
     -- i.e., the proxy is approximately a fixed linear rescaling of the
     real signal, not an unrelated quantity, which leaves t-stats and the
     bps-at-+/-1-sigma economic magnitude largely invariant to the
     substitution; the two residual, uncompensated gaps are that the 0.8
     ratio is not perfectly constant month to month (observed 0.796-0.80),
     and the real signal's own per-minute breadth floor, Section 8,
     excludes slightly different minutes than this proxy did.)
3. **Power at the project's economic-significance thresholds (10/20/30
   bps, Section 18) is not usefully reportable from this pilot** -- the
   proxy's small sigma relative to `SE_boot` makes power trivially >0.999
   at every threshold tested, which is an artifact of the proxy, not
   informative about the real signal.

**Explicit statement, per this family's own standing instruction not to
claim an unconditional PASS where one cannot be supported**: **this
amendment does not claim the study is adequately powered.** The evidence
available is consistent with "not alarming" (the bootstrap achieved full
target scale easily; the design effect is not large; the breadth
correction, Section 6, remains ample) but this is a materially weaker
statement than the original version's "5-20x margin," which was never
actually computed on anything that matches the real estimand. **The power
question is deferred to Phase 4's first analysis step** (Section 21):
measure the real, corrected `S_leader(t)`'s own sigma; re-run the
day-clustered placebo bootstrap (per-real-day-shared pairing, Section
16e) on the real signal at full scale; only then compute a trustworthy
MDE and compare it against Section 18's economic floor, before running
any primary-gate regression.

---

## Section 18: economic significance threshold

Unchanged from the original version: 20 bps (stricter bound of the
project's established 20-30bps round-trip cost figure, `PROJECT_CONTEXT.md`
Section 8), compared against the model-implied effect at +/-1 observed
sigma of the real (Section 8-corrected) `S_leader(t)` -- which Section 17
notes has not yet been measured. The spread/impact component of the
20-30bps figure remains unvalidated (`SPREAD_ESTIMATOR_VALIDATION.md`:
zero days of live collection as of this writing); this caveat is
unchanged and not newly introduced by this amendment.

**DECISION 15 STATUS NOTE (2026-11-14, added by a documentation-repair
task; corrected 2026-11-14, same day, by a second documentation-repair
task -- see the superseded wording quoted below).** Two separate things
must not be conflated, and the correction below exists specifically
because an earlier version of this note risked conflating them:

1. **The bare numeral "20 bps."** This figure is original, long-standing
   project convention, inherited from `PROJECT_CONTEXT.md`'s 20-30bps
   round-trip cost figure, and predates every amendment in this document.
   **This numeral is unchanged by any amendment and is not altered here.**
2. **Whether, and how, that numeral functions as an approved
   primary-gate PASS/FAIL success criterion.** This -- not merely the
   sign-direction question -- is Decision 15, and **Decision 15 is OPEN.
   The user has not approved any rule for using 20bps as a gate
   criterion.** `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section
   11, decision item 15, **recommends**, but does not itself approve, a
   specific construction: `beta > 0` required for a pass (not a
   magnitude-only `|beta|` comparison); negative `beta` is contrary
   evidence, **never silently flipped or reinterpreted under an
   unapproved rule**; the comparison labeled an "effect-size hurdle,"
   explicitly **not** a claim that 20bps represents validated trading
   costs or net profitability. **This remains a recommendation only.
   No primary-gate interpretation of Section 20 may treat this
   recommendation, or any other specific hurdle construction, as settled
   until the user explicitly approves one.**

*(Superseded wording, preserved for provenance, not deleted -- this
phrasing is what the correction above exists to clarify)*: "The **20bps
number itself** is original, long-standing project convention... and is
**not in question here**." That sentence remains literally true of the
bare numeral (item 1 above) but is retracted as the note's lead framing
because, read in isolation, it risks being misread as settling item 2 --
whether the hurdle itself is an approved gate criterion -- which it does
not and never did.
**This section does not itself state a sign rule** -- it compares "the
model-implied effect at `+/-1` observed sigma" against the floor, which
is silent on whether a large-magnitude negative `beta` would count as
clearing this threshold. **Decision 15 must be resolved by explicit user
approval before Section 20's gate (below) is run or interpreted as having
a settled success criterion.** This status note does not itself approve,
reject, or change the 20bps value or the sign rule -- it records that a
decision is required and has not yet been made.

**[DECISION 15 -- APPROVED, 2026-11-14, AMENDMENT 8 LOG, later the same
day.** The decision this status note describes as required has now been
made, by explicit user decision: `beta > 0` is mandatory for a pass;
`beta * sigma(S_leader)` must **strictly exceed** 20bps (equality does
not pass); a statistically significant negative `beta` is contrary
evidence, never reinterpreted via `|beta|`; the 20bps figure remains
explicitly not a validated transaction-cost estimate or profitability
claim. **The bare 20bps numeral (item 1 above) is unchanged.** See
AMENDMENT 8 LOG for the full record. This status note's own text above
is preserved unedited as the accurate historical record of Decision 15's
status earlier that day.]**

---

## Section 19: execution-cost assumptions (for any future trading simulation)

Unchanged from the original version: not specified here, deferred entirely
to a separate Phase 7 preregistration, per the master spec's explicit
prohibition on folding execution mechanics into the primary measurement
(`lead_lag/MASTER_SPEC_LEAD_LAG.md` Part 9).

---

## Section 20: verdict rules

**Unchanged in structure from the original version, with one addition**:
a seventh, prior condition is added, since it is now a precondition for
the other six to even be meaningful.

**PASS requires ALL of the following; any single failure is a FAIL,
closing the measurement study automatically:**

0. **(New) Signal non-degeneracy check**: the real, corrected `S_leader(t)`
   (Section 8) has measurable, non-trivial variance on real data (i.e.,
   Phase 4's first analysis step, Section 21, confirms sigma is of a
   sane economic order of magnitude, not machine-epsilon noise). This is
   checked **before** any of the following six, since Amendment Log item
   1 demonstrates it cannot be assumed.
1. **Primary test**: `beta` at h=60 minutes is statistically significant
   at the Bonferroni-corrected alpha (0.00625, two-sided, per Decision 16
   -- supersedes the original 0.0083 figure, which remains historically
   accurate for the original six-configuration family and is recorded,
   not deleted, in Section 23), day-clustered
   SE, economically interpretable sign.
2. **Economic magnitude**: the Section 18 implied effect at +/-1 sigma of
   the real `S_leader` exceeds the 20bps floor.
3. **Timing null**: real `|beta|` exceeds the 95th percentile of the
   circular-shift null distribution (Section 16a).
4. **Selection null (redesigned)**: real `|beta|` exceeds the 95th
   percentile of the matched-random-leader-portfolio null distribution
   **for both the B1 (per-month redraw) and B2 (fixed selection rule)
   variants independently** (Section 16b) -- passing only one is not a
   pass of this gate.
5. **Market-factor null**: the leader-signal term's incremental
   contribution (Section 16c) is statistically distinguishable from zero
   and not reducible to the controls alone.
6. **Stage-count reconciliation**: leader-tier construction -> signal
   construction -> follower-eligibility filtering -> final regression
   sample row counts reconcile against each prior stage, with no
   unexplained discrepancy.

**[CONDITIONS 1 AND 2 -- PRECISE RESTATEMENT, APPROVED 2026-11-14,
AMENDMENT 8 LOG.** Conditions 1 and 2 above are preserved unedited; this
restates them with the now-approved signed-threshold interpretation made
explicit, resolving the ambiguity the DECISION 15 STATUS NOTE below
describes:

1'. **Primary test, restated**: `beta` at `h=60` minutes is **positive**
    (`beta > 0`) AND statistically significant at the Bonferroni-corrected
    alpha (`0.00625`, two-sided, per Decision 16), day-clustered SE. A
    statistically significant `beta <= 0` does not satisfy this condition,
    regardless of magnitude -- it is reported as contrary evidence
    (Section 18/20 Decision 15 notes), not as a pass under a different
    label.
2'. **Economic magnitude, restated**: `beta * sigma(S_leader)` **strictly
    exceeds** 20bps (`beta * sigma(S_leader) > 20bps`; equality does
    **not** pass). This condition is only meaningful, and is only
    evaluated, when condition 1' is satisfied (`beta > 0`) -- a negative
    `beta`'s magnitude is never substituted into this comparison.

The alpha, the day-clustered SE methodology, the 60-minute primary
horizon, and conditions 0, 3, 4, 5, and 6 are **unchanged** by this
restatement.]**

**DECISION 15 STATUS NOTE (2026-11-14, added by a documentation-repair
task).** Conditions 1 and 2 above are written at the level of generality
this document has always used ("economically interpretable sign";
"implied effect... exceeds the 20bps floor") and **do not, by themselves,
specify** whether condition 2 is a signed or an absolute-magnitude
comparison, or whether a large-magnitude `beta` of the wrong sign
could satisfy it. `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 11, decision item 15, **recommends** a specific resolution
(`beta > 0` required; negative `beta` is contrary evidence, never
flipped via `|beta|`; the comparison is an "effect-size hurdle," not a
validated cost or profitability claim) -- **but that decision table
explicitly marks item 15 OPEN, and the user has not approved it.** **No
primary-gate PASS/FAIL verdict under this section may be interpreted
using the proposal's specific sign rule, or treated as if that
interpretation were already settled, before Decision 15 receives explicit
user approval.** If, when Phase 4 is actually run, conditions 1 and 2 as
literally worded above cannot be evaluated without first choosing between
the proposal's recommended sign rule and some other interpretation (e.g.,
a pure `|beta|` magnitude test), **that conflict must be reported to the
user and left OPEN, not resolved by this document or silently decided by
whichever interpretation the implementer finds convenient.** This note
does not change conditions 0-6, the alpha, the horizon, or any other gate
mechanic -- it only flags that one specific interpretive question
(Decision 15) is unresolved and must not be treated as settled. **Clarified
by a second documentation-repair task, 2026-11-14, same day (Section 18's
note has the full correction)**: the unresolved question is not only the
sign-direction choice -- it is whether the 20bps "effect-size hurdle"
construction, as a primary-gate criterion at all, has been approved. It has
not. Decision 15 remains OPEN in its entirety, not merely on the
sign-direction detail.

**[FURTHER STATUS UPDATE -- DECISION 15 APPROVED, 2026-11-14, AMENDMENT 8
LOG, later the same day.** The conflict this note describes is resolved:
the proposal's recommended sign rule (`beta > 0` required; negative
`beta` never flipped via `|beta|`) is now APPROVED, by explicit user
decision, with the added precision that condition 2's comparison is
strictly `>` 20bps, not `>=`. **Conditions 1' and 2' above (the precise
restatement) are the governing text going forward.** This note's own
text above, and the sign-rule-recommendation-vs-approval distinction it
drew, is preserved unedited as the accurate historical record of
Decision 15's status earlier that day -- it was, and remains, an
accurate description of what was true before this approval.]**

**A PASS here means**: a statistically and economically significant,
null-surviving, incrementally-informative liquidity-tiered return
relationship was found at the preregistered primary horizon -- per
Section 1's reframing, this does not establish which of the four named
mechanisms (genuine information diffusion, common-factor differential
speed, non-synchronous trading, stale pricing) is responsible, and does
not by itself authorize a trading simulation.

**A PASS here does NOT mean**: that a live, tradeable edge exists, that
execution costs have been fully accounted for, that any historical
holdout-style validation has occurred, or that the specific mechanism of
"information propagation between related securities" (the original,
pre-amendment hypothesis framing) has been confirmed.

---

## Section 21: failure conditions and required Phase 4 first steps

**Beyond the headline gate, in addition to the original version's four
failure conditions (sign instability, non-overlapping-sample check,
signal sparsity, 10bps robustness), this amendment adds the following as
mandatory, ordered FIRST STEPS of Phase 4, to be completed and reported
before any primary-gate regression is run:**

1. **Measure the real, Section-8-corrected `S_leader(t)`'s own mean and
   sigma on real data** (all months, full date range). Confirm it is not
   degenerate (Section 20, check 0) before proceeding. If it is found to
   be degenerate or near-degenerate in some other, not-yet-anticipated
   way, **stop and report this honestly rather than patching the
   construction ad hoc** -- the same discipline this amendment itself
   followed when the original construction failed this exact check.
2. **Re-run the Section 16e placebo bootstrap on the real, corrected
   signal**, at full scale (**the governing 2,457 verified trading
   sessions, Section 12** -- not the raw 2,468-date archive count, and
   not the 11-month pilot sample), using the per-real-day-shared pairing convention
   (Section 16e, resolved). Report the resulting `SE_boot`, MDE, and
   power at the Section 18 economic thresholds. Compare this against
   Section 18's floor **before** running the primary-gate regression,
   using the following frozen decision rule (margin ratio = Section 18's
   20bps floor divided by the full-scale corrected MDE, both expressed in
   bps via the real signal's own measured sigma, per step 1 above --
   **frozen now, per the adversarial re-review's finding that
   "comfortably below" was the one undefined, outcome-adjacent judgment
   call left in this document, inconsistent with Section 23's otherwise
   strict freezing discipline**):
   - margin ratio `>= 5`: proceed to the primary-gate regression.
   - margin ratio `>= 1` and `< 5`: **stop, report INCONCLUSIVE, and
     return to the user for explicit guidance before proceeding** -- do
     not auto-proceed on a borderline margin.
   - margin ratio `< 1` (MDE exceeds the floor): **stop and report
     ABANDONED** -- the sample cannot resolve an economically meaningful
     effect at all.
   The `>= 5` threshold is anchored to, but more conservative than, the
   original (withdrawn) version's "5-20x margin" language -- chosen now,
   before any real Phase 4 number exists, specifically so it cannot be
   adjusted after seeing whether a given run clears it.
3. **Run the redesigned selection null (Section 16b)** on the real signal
   and confirm it is genuinely discriminating in practice (i.e., the
   1,000 `beta_random` draws show real variation, not another
   unanticipated collapse) before relying on it as part of Section 20's
   gate.
4. Only after 1-3 above are complete and reported, proceed to the primary
   h=60-minute regression and the remaining Section 20 checks.

---

## Section 22: reproducibility requirements

Unchanged from the original version (read-only connections only; fixed
seed 20261107 for every null/bootstrap draw; 1,000 draws per randomized
procedure; chunking by calendar year with per-chunk checkpointing for the
full DEV run, per the Phase 2 OOM lesson; five-observation hand-tracing
before aggregate results are accepted), **plus**: every statistical gate
run in Phase 4 must call `lead_lag/ledger.assert_registered(config_key)`
before running and `lead_lag/ledger.record_gate_run(config_key,
run_metadata)` immediately after (Section 15), and the per-real-day-shared
placebo-pairing convention (Section 16e) must be used verbatim, not
re-chosen.

---

## Section 23: frozen free parameters (new, consolidated)

Every parameter identified across this family's documents that could
affect sample selection or results, in one place, so none can be
silently retuned after Phase 4 output exists:

| Parameter | Value | Source |
|---|---|---|
| Leader-tier cutoff | top 20% by trailing turnover | Section 6, master spec Part 3.3 default |
| Trailing turnover window | 60 trading sessions | Section 6, master spec Part 3.3 default |
| Tier reconstitution cadence | monthly, first trading day | Section 6 |
| Signal window width | 5 minutes, fixed | Section 8, master spec Part 4.2 |
| Per-minute leader breadth floor | `n_t_breadth >= 0.80 * tier size`, present-valid bars only (forward-filled bars excluded from this count) | Section 8, Decision 10 amendment (2026-11-14), evidence-based (excludes ~0.001% of minutes) |
| Leader return-construction count (`n_t_return`), distinct from `n_t_breadth` | Decision 17's existing return-construction rules (may include forward-filled endpoints); divisor of `S_leader(t)` | Section 8, Decision 10 amendment (2026-11-14) |
| Day-level leader breadth floor | >=50% of tier has a valid bar | Section 12 (original) |
| Governing trading-session calendar | `src/data_layer/nse_holidays.py` + `data/raw/nse_cm_holidays.pkl` (holiday classification) plus explicit special-session verification; raw `bars_1min.trade_date` is not sufficient by itself | Section 12, Decision 10 amendment (2026-11-14) |
| Governing trading-session denominator | 2,457 dates (2,468 raw archive dates, less 11 verified non-regular-session dates; 4 genuine weekend special sessions remain included) | Section 12, Decision 10 amendment (2026-11-14) |
| Entity-day completeness exclusion | <90% of expected bars | Section 12 (original) |
| Gap-fill forward-fill threshold | <3 consecutive minutes | Section 13 (original). **Operative interpretation, APPROVED 2026-11-14 -- Decision 17, AMENDMENT 10 LOG, Section 1**: exact elapsed timestamp duration between the bounding present-valid rows, `EPOCH(next) - EPOCH(prev)`, strictly `<180` seconds. This exact-seconds unit is a prospective methodological clarification made by explicit human decision, not a claim that the original preregistration specified this unit -- that original intent was investigated and found inconclusive. The original "<3 consecutive minutes" wording above is preserved unedited as the historical text being clarified. |
| Gap exclusion threshold | >=3 consecutive minutes | Section 13 (original). **Operative interpretation, APPROVED 2026-11-14 -- Decision 17, AMENDMENT 10 LOG, Section 1**: exact elapsed timestamp duration `>=180` seconds, exclude, not imputed -- **180 seconds itself is on the excluded side**. Same provenance note as the row above: a prospective clarification, not an original-intent finding. This threshold governs Stage A's pre-signal endpoints only; it does not apply to, and is never substituted for, Stage B's existing zero-tolerance forward-endpoint rule at `t+h` (AMENDMENT 10 LOG, Section 5), which is unchanged by this row. |
| Corporate-action exclusion window | +/-1 trading day | Section 12 (original) |
| Prediction horizons | 5, 15, 30, 60 minutes | Section 10 |
| Primary horizon | 60 minutes | Section 10, chosen variance-only |
| *(OPEN, 2026-11-14 -- see APPROVED row below)* Economic significance floor | 20 bps (stricter of 20-30bps) -- the bare **numeral** is unchanged, original project convention, inherited from `PROJECT_CONTEXT.md`. **Whether, and how, this numeral functions as an approved primary-gate PASS/FAIL criterion is Decision 15 -- OPEN, not approved** (not merely the sign-direction detail; the entire "effect-size hurdle" construction, including the proposal's recommended `beta>0` rule, remains an unapproved recommendation). **No primary-gate verdict may treat this row as describing a settled success condition.** See Section 18's and Section 20's status notes. *(Corrected 2026-11-14: an earlier version of this row said "the number is frozen," which risked being read as implying the hurdle itself was settled; retracted in favor of this wording.)* **Superseded, AMENDMENT 8 LOG, 2026-11-14 (later same day) -- see the APPROVED row directly below.** Row preserved unedited as the accurate historical record of this decision's status earlier that day. | Section 18 |
| **Decision 15 -- effect-size-hurdle gate criterion (signed)** | **`beta > 0` AND `beta * sigma(S_leader) > 20bps`, strictly** (equality does not pass); negative or non-positive `beta` is contrary evidence, never reinterpreted via `abs(beta)`; the bare 20bps numeral is unchanged; statistical significance test unchanged (two-sided `alpha=0.00625`, day-clustered SE, 60-minute primary horizon, Decision 16); not a validated transaction-cost or profitability claim | **APPROVED, 2026-11-14 -- Decision 15**, AMENDMENT 8 LOG, following explicit user decision reviewing `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 9's recommendation. Supersedes the OPEN row above, preserved there unchanged as historical record. See Section 18 and Section 20 (conditions 1'/2') |
| Significance level | alpha=0.05, two-sided (unaffected by Decision 16 -- this is the unadjusted level, not the multiplicity-corrected one) | Section 15 |
| Power target | 0.80 | Section 17 |
| Ledger-registered configurations | 6 (`lead_lag/trial_ledger.json`, `ledger.denominator()` -- unchanged by Decision 16; the ledger is deliberately not edited) | Section 15 |
| Formal trial count (project trial definition) | 7 (6 ledger-registered + Option 1, an unregistered Phase 1 feasibility kill) | Section 15, Decision 16 amendment (2026-11-14), `lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md` |
| Operative multiplicity-family denominator (future primary gate) | **8** (6 ledger-registered + Option 1 + Option 2; Option 2 is included for multiplicity-control purposes despite NOT being a formal trial) | Section 15, Decision 16 amendment (2026-11-14) |
| Future primary-gate Bonferroni alpha | **0.05/8 = 0.00625**, two-sided -- operative; supersedes the historical `0.05/6` row below for gate purposes | Section 15, 20, Decision 16 amendment (2026-11-14) |
| *(historical, superseded)* Pre-Decision-16 multiplicity-family denominator | 6 (`lead_lag/trial_ledger.json`) -- accurate description of the multiplicity-family denominator as of the original 2026-11-08 amendment, before Options 1/2 existed and before Decision 16 added them to the family; the ledger's own registered-configuration count also remains 6 today, but that is now a separate fact from the operative multiplicity-family denominator (8, see the row above) | Section 15 (original wording, retained) |
| Null/bootstrap draw count | 1,000 (timing, selection); 500 achieved in pilot (placebo bootstrap, Phase 4 to confirm at full scale) | Section 14, 16 |
| Random seed | 20261107 | Section 22 |
| Placebo day-pairing granularity | one shared random day per real response day (not per follower-row) | Section 16e, resolved in this amendment |
| Placebo minimum day separation | >=20 trading days | Section 16e (original) |
| Matched-random-leader candidate pool | ranks `n_leaders+1` to `3*n_leaders` by trailing turnover (disjoint from the true leader tier) | Section 16b, revised following adversarial re-review (first draft's top-40%/2x-size pool overlapped the true tier by ~50% and is superseded) |
| Selection-null variants required | both B1 (per-month independent redraw) and B2 (fixed selection rule per repetition) must independently pass | Section 16b, Section 20 condition 4, revised following adversarial re-review |
| Selection-null repetitions | 1,000 (per variant) | Section 16b |
| **Future primary-gate Bonferroni two-sided z-critical (alpha=0.05/8)** | **2.73437** (giving MDE multiplier **3.57599** with z_power=0.84162, unchanged) | Section 17, Decision 16 amendment (2026-11-14); `z_{1-0.05/16}`, identical formula/convention as the historical row below, only the denominator changed |
| *(historical, superseded)* Bonferroni two-sided z-critical (alpha=0.05/6) | 2.63826 (giving MDE multiplier 3.47988 with z_power=0.84162) | Section 17, corrected following adversarial re-review (first draft used 3.1909 in error); accurate for the original six-configuration family |
| Full-scale MDE-vs-floor decision margin | `>=5x`: proceed; `1x-5x`: INCONCLUSIVE, stop for guidance; `<1x`: ABANDONED | Section 21, frozen following adversarial re-review (first draft left "comfortably below" undefined) |
| **Return convention (exact endpoint-price)** | `r_i(a,b) = P_i(b)/P_i(a) - 1` per frozen-eligible constituent, arithmetic mean across constituents; price return, dividends excluded; applied consistently to `R_L(t)`, `R_F(t)`, `Y(t,h)`, `Momentum_F(t)` | **APPROVED, 2026-11-14 -- Decision 13**, AMENDMENT 4 LOG above; supersedes the historical Section 8/9 sum-of-per-bar construction *prospectively* for Phase 4 implementation only -- Section 8/9's own text and worked measurements are unchanged and remain the accurate historical record of what was actually computed before this approval |
| **Follower-basket breadth floor** | **70%** of the follower tier, present-valid observations only (forward-filled/absent bars excluded from the count, mirroring the leader-side `n_t_breadth` convention); `n_t_return` for actual return construction governed unchanged by Decision 17; calendar denominator is the existing 2,457-date governing calendar | **APPROVED, 2026-11-14 -- Decision 10**, AMENDMENT 5 LOG, Section 1; supersedes the "candidate, remains open" status recorded in AMENDMENT 2 LOG, which is preserved there unchanged as historical record |
| *(RETRACTED, 2026-11-14, same day -- see corrected rows below)* First valid regular-session bar | `09:15` | Originally entered here as "APPROVED, 2026-11-14 -- Decision 11." **That was incorrect; no such approval was given at that time. Decision 11 was OPEN.** Row retained, struck from governing status, so the error is not silently erased. **[NOTE, AMENDMENT 6 LOG, 2026-11-14, later same day: this retracted row's *value* (`09:15`) has since turned out to match the genuine approval recorded below -- a coincidence of timing, not a retroactive validation of the erroneous approval claim this row documents. The error being retracted here was the false claim of an approval that had not happened, not the value itself.]** |
| *(OPEN, 2026-11-14 -- see corrected row below)* **Decision 11 -- first valid regular-session bar** | **`09:15` OR `09:16` -- NOT YET DETERMINED** | **OPEN**, as of this entry. `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 5 ("evidence found, not conclusively settled"); unresolved per `lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md`, `lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md`, `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md`. **Superseded, AMENDMENT 6 LOG, 2026-11-14 (later same day) -- see the APPROVED row directly below.** Row preserved unedited as the accurate historical record of this decision's status earlier that day. |
| **Decision 11 -- first valid regular-session bar** | **`09:15`** | **APPROVED, 2026-11-14 -- Decision 11**, AMENDMENT 6 LOG, following a final targeted first-bar verification report (`>99%` archive-wide presence and structural validity at `09:15`, under both the 2,457-date governing calendar and the full 2,468-date raw archive; a dated, identifiable `2020-11-23`-through-`2020-11-27` archive-coverage episode and three special/truncated-session dates (`2016-10-30`, `2017-07-10`, `2025-10-21`) found and attributed to existing, already-approved eligibility machinery, not to session-definition ambiguity). `09:16` is not adopted. Supersedes the OPEN row above, preserved there unchanged as historical record. |
| **Non-overlapping sampling anchor** | **`09:20`** (signal-end minute `t=09:19`) | **APPROVED, 2026-11-14 -- consequence of Decision 11's approval**, AMENDMENT 6 LOG, Section 2. Supersedes the conditional `09:20`/`09:21` row below, preserved unchanged as historical record. *(An earlier draft of this row asserted a single, unconditional `09:20` value prematurely, before Decision 11 was actually approved; that earlier draft was retracted at the time -- this row's current `09:20` value is independently, correctly derived from the now-genuine approval, not a revival of that earlier error.)* |
| *(CONDITIONAL, superseded 2026-11-14)* Non-overlapping sampling anchor | **Conditional**: `09:20` (signal-end minute `t=09:19`) if `09:15` is first valid; `09:21` (signal-end minute `t=09:20`) if `09:16` is first valid instead | Section 5 of `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`; conditional on Decision 11, OPEN at the time this row was written. **Superseded, AMENDMENT 6 LOG, 2026-11-14 -- see the APPROVED row above.** Row preserved unchanged as historical record. |
| **`Momentum_F(t)` minimum anchor** | **`09:50`** | **APPROVED, 2026-11-14 -- consequence of Decision 11's approval**, AMENDMENT 6 LOG, Section 3; lower bound only, never a guarantee of basket/endpoint validity, which remains governed unchanged by Decision 22's rules 1-6 (AMENDMENT 5 LOG, Section 3). The exclusion rule itself was already APPROVED, 2026-11-14 -- Decision 22, AMENDMENT 5 LOG, Section 3; this row fixes the anchor value that rule's arithmetic implies. Supersedes the conditional row below, preserved unchanged as historical record. |
| *(CONDITIONAL, superseded 2026-11-14)* `Momentum_F(t)` minimum anchor | **Conditional**: `09:50` if `09:15` is first valid; `09:51` if `09:16` is first valid instead -- lower bound only in either branch, never a guarantee of basket/endpoint validity | **The exclusion rule itself is APPROVED, 2026-11-14 -- Decision 22**, AMENDMENT 5 LOG, Section 3. **The anchor value was conditional on Decision 11 (OPEN at the time)** -- an earlier draft of this row asserted a single, unconditional `09:50` value prematurely; retracted at the time. **Superseded, AMENDMENT 6 LOG, 2026-11-14 -- see the APPROVED row above**; that row's `09:50` value is independently, correctly derived from the now-genuine Decision 11 approval. |
| **Monthly roster turnover-ranking window (ranking-date inclusivity)** | **Ranking date excluded**: trailing-60-session median `prices_eod.turnover` uses `trade_date < ranking_date`, strictly; roster frozen as of the prior session's close, effective from the ranking date's own first trading session | **APPROVED, 2026-11-14 -- Decision 23**, AMENDMENT 7 LOG; clarifies, does not change, Section 6's existing "no bar after the ranking date is used" language (preserved unedited there). Does not alter the `>=60`-session eligibility rule, the 20% leader/follower split, or the annual top-200 universe construction. **Option 2's Stage-A threshold is now also approved -- see the row below, AMENDMENT 9 LOG (superseding the "separately OPEN" cross-reference this row originally carried).** See `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` for the underlying audit. |
| **Monthly roster ranking-date calendar source** | The **governing exchange-session calendar** (Decision 10/21: `nse_holidays.py` plus explicit special-session verification) identifies each month's first trading session -- never raw presence in `prices_eod` or `bars_1min`. The 4 weekend specials are included (3 of them, on the 1st of February, can be that month's governing ranking date); `2021-02-24` excluded, per Decision 21; `2016-10-03` vs. `2016-10-04` is the known intraday-archive-start artifact, not a calendar disagreement | **APPROVED, 2026-11-14 -- Decision 24**, AMENDMENT 11 LOG. Resolves the `prices_eod`-vs-`bars_1min` first-trading-day mismatch (4/120 months) left open by AMENDMENT 7 LOG and AMENDMENT 9 LOG. Does not alter any other Decision 23 rule (turnover source, 60-session window, freeze/effective timing) or the annual top-200 universe construction. See `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` Section 4.1 for the underlying finding, preserved unchanged. |
| **Final control set (primary regression)** | `R_F(t)` + `TOD(t)` + `Momentum_F(t)`, primary; trailing realized volatility, coarse trading activity, and prior-day NIFTY50 are sensitivity/diagnostic-only, never primary | **APPROVED, 2026-11-14 -- Decision 7**, AMENDMENT 12 LOG, Section 1. Adopts the control set already specified in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 6's existing, unchanged primary regression equation; does not alter that equation or any variable's definition. |
| **Fixed-effects specification** | Primary: no fixed effects. Sensitivity: year fixed effects. No quarter fixed effects. Year FE must never replace the no-FE primary | **APPROVED, 2026-11-14 -- Decision 8**, AMENDMENT 12 LOG, Section 2. |
| **Prior-day NIFTY50 regime control** | Omitted from the primary regression; sensitivity-only, explicitly labeled a coarse daily-regime proxy; prior trading day's close-to-close return only, never the same-day close | **APPROVED, 2026-11-14 -- Decision 9**, AMENDMENT 12 LOG, Section 3. Does not resolve the existing, separately-stated limitation that no independent intraday market or sector index exists (Section 1, "What this construction can and cannot rule out"), preserved unchanged. |
| **Fixed monthly roster identity** | Membership fixed for the month, determined solely by the monthly liquidity-tier assignment; no signal-time availability-based additions, removals, or replacements; no dynamic mid-month reconstitution | **APPROVED, 2026-11-14 -- Decision 18**, AMENDMENT 13 LOG. Same rule `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3A/row 18 already described as RECOMMENDED; approved here exactly as stated, no substantive change. |
| **`bars_1min` price-adjustment convention** | **MIXED CONVENTION**: back-adjusted for split/bonus actions, piecewise, between-session boundaries only; `prices_eod` remains raw; same-session returns usable without vendor-history reconstruction, conditional on Phase 4 asserting the same-`trade_date` guarantee in code | **APPROVED, 2026-11-14 -- Decision 14**, AMENDMENT 9 LOG, Section 1. Vendor mechanism unverified; tested population limited to 104 recorded split/bonus events on 75 archive-covered entities. See `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`. |
| **Option 2 Stage-A minimum-breadth threshold** | `\|frozen_subset(t,side)\| / n_roster_tier(month,side) >= 0.70`, applied separately per side, at step 4 (after freezing, before computation and before Stage B) | **APPROVED, 2026-11-14 -- Decision 19 (threshold sub-question)**, AMENDMENT 9 LOG, Section 2. The `0.70` value and the original-roster-tier denominator are both newly approved for this purpose, not inherited from Decision 10's separate per-minute follower floor. See `lead_lag/PRE_SIGNAL_VS_FORWARD_ENDPOINT_RECONCILIATION.md`. |
| **Corporate-action eligibility, applied at Stage A** | The existing `+/-1`-trading-day exclusion (unchanged) is checked at `t-35`, `t-5`, `t` as a Stage A eligibility condition, before freezing; not a second whole-day filter | **APPROVED, 2026-11-14 -- Decision 20**, AMENDMENT 9 LOG, Section 3. Exchange-mechanism category (NSE adjustment timing) remains unverified; tested scope limited to the Decision 14 population. |
| **Primary-sample governing calendar** | **2,456 dates** (the governing 2,457-date calendar, Section 12, less `2021-02-24`); 4 weekend specials included under the unmodified session convention; 11 non-session dates excluded, unchanged | **APPROVED, 2026-11-14 -- Decision 21**, AMENDMENT 9 LOG, Section 4. The 2,457-date governing figure is unchanged and remains authoritative for all prior historical measurements; 2,456 applies to the primary sample specifically. `2021-02-24` excluded conservatively; see AMENDMENT 9 LOG for the internal-inconsistency finding that prompted this. |
| **PRESENT-VALID bar definition** | Positive-volume and structurally valid (category D), OR zero-volume with `open=high=low=close`, **all four finite and strictly positive** (category A1, settled); own close used directly, no forward-fill invoked. **Category E structural invalidity takes precedence -- a structurally invalid bar is never PRESENT-VALID, even if flat.** | **APPROVED, 2026-11-14 -- Decision 17**, AMENDMENT 10 LOG, Section 4. Formally defined in this document for the first time by this amendment; previously referenced informally in prior amendments without a formal definition. **PRECISION CORRECTION, 2026-11-14, same day**: this row's A1 wording is updated to match AMENDMENT 10 LOG, Section 4's precision correction (finite-and-positive requirement; E's precedence over A1) -- a wording clarification, not a change to any approved rule's scope. |
| **Structural-invalidity criteria (category E)** | Exclude if any of: `high<low`; `open` outside `[low,high]`; `close` outside `[low,high]`; any OHLC value null/non-finite/`<=0`; `volume<0`. Own values never used; own timestamp never repaired/forward-filled; timestamp still counts for neighboring gap-length classification | **APPROVED, 2026-11-14 -- Decision 17**, AMENDMENT 10 LOG, Section 3. Extreme positive volume alone is never structural invalidity (see category D, same amendment, Section 2). |
| **Exact-duration gap threshold (category C)** | `EPOCH(next_present_ts) - EPOCH(prev_present_ts)`, strictly `<180` seconds forward-filled; `>=180` seconds excluded (180 itself excluded) | **SETTLED, predating this amendment (Decision 17, sub-decision C)**, restated and formally cross-referenced to Section 13 by AMENDMENT 10 LOG, Section 1. A prospective methodological choice, not a claim about original preregistration intent. |
| **Stage A / Stage B imputation precedence** | Stage A (`t-35,t-5,t`): short-gap forward-fill may apply, `<180`s only; B1/E bars never imputed. Stage B (`t+h`): zero-tolerance, unchanged; Stage A's short-gap rule never applied to `t+h`; any failure discards the entire observation | **APPROVED, 2026-11-14 -- Decision 17**, AMENDMENT 10 LOG, Section 5. Stage B's existing zero-tolerance rule (Decision 19, AMENDMENT 9 LOG) is unaffected and takes precedence. |
| **Decision 12 -- bootstrap block-length sub-parameters and derived `L`** | `min_n_k=30`; `R=2`; `min_usable_blocks=20`; derived **`L=6`** (max of signed-series `L=1` and squared-series `L=6`, both found within the initial 1-10 lag range); evidentiary basis: real full-history (2016-10-04 to 2026-09-18) controls-only baseline residuals, 1,861 usable days, 310 usable blocks at `L=6` | **APPROVED, 2026-11-15 -- Decision 12**, AMENDMENT 14 LOG. Two candidate sub-parameter sets were compared before approval and both independently produced `L=6`; neither was chosen by reference to `beta`, p-value, significance, or the real `S_L`-`Y` relationship, which this computation never touches. |
| **Decision 25 -- null-imposed inference methodology and split-bootstrap design** | Primary: consecutive multi-day block bootstrap, `L=6`, `ceil(n/L)` blocks with replacement. Sensitivity: identical procedure, `L=1`. Residuals matched by identical scheduled anchor; unmatched observations excluded, never recycled/interpolated. Null model `Y~R_F+TOD_opening_30+TOD_closing_30+Momentum_F`; pseudo-`Y=null_fitted+matched_donor_residual`; complete primary regression (incl. `S_L`) refit per replicate. Two-sided p-value `(1+count(\|beta_star\|>=\|beta_hat\|))/(1+n_valid)` is the **sole** source of the primary significance decision. Unrestricted case-resampling bootstrap (unchanged, pre-existing) supplies CI/SE only -- the two distributions are never combined. | **APPROVED, 2026-11-15 -- Decision 25**, AMENDMENT 15 LOG, Sections 1-2. Implemented in `src/lead_lag/inference.py`; synthetically calibrated (4,000+2,600 outer repetitions, 10,000 inner draws each) and power-verified near the 20bps boundary before approval. |
| **Bootstrap draw-count convention** | Requested: 10,500 (primary and sensitivity, each). Minimum valid required: 10,000. Failed draws always counted (`n_valid+n_failed_total==n_resamples_requested`), never substituted. Shortfall below 10,000 valid draws: evaluation must stop and report, never silently lowered or patched. | **APPROVED, 2026-11-15 -- Decision 25**, AMENDMENT 15 LOG, Section 3. A protocol-level check applied by the evaluator using the bootstrap's own exposed `n_valid` field, not a hard-coded exception inside the function. |
| **Real structural preflight findings (h=60 design)** | Effective real primary design rank `k_eff=4` (of 6): `TOD_closing_30` permanently zero (schedule-derived, no h=60 anchor in the 15:00-15:29 window); `TOD_opening_30` also zero in the real data (09:19's own `t-35=08:44` precedes session open, so Decision 22's Momentum_F floor can never be met there) -- 0/3,761 retained observations at `t=09:19`. Both handled correctly by the existing `k_eff`/`zero_variance_regressors` mechanism, no code change required. Mean structural anchor-match rate ~36.9% (`L=6`) / ~36.8% (`L=1`), stable, no calendar/anchor-alignment issues found. | **RECORDED, 2026-11-15**, AMENDMENT 15 LOG, Section 4. Outcome-blind: no `Y`/`S_L`/`R_F`/`Momentum_F`/beta/p-value was computed or accessed to produce this row. |

None of these were chosen after observing any outcome. Any future change
to a value in this table requires a new, explicitly versioned amendment
(or a V2 preregistration), with its own entry in `lead_lag/trial_ledger.json`
if the change constitutes a new configuration.

---

## Status

**Original version committed 2026-11-07**, commit `e1418a661a769c9f134d750bbe95dc1a831b0305`.

**This amendment drafted 2026-11-08**, following an independent
methodology review and the subsequent discovery (during this amendment's
own supporting analysis) that the original Section 8/9 signal construction
was algebraically degenerate. Supporting documents:
`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` (real breadth, per-minute
floor, placebo pilot), `lead_lag/MASTER_SPEC_LEAD_LAG.md` (governing
directive, now committed), `lead_lag/trial_ledger.json` +
`lead_lag/ledger.py` + `lead_lag/test_ledger.py` (machine-enforced trial
accounting, 7 passing tests).

**Adversarial re-review completed.** Two concrete issues were found in
this amendment's own first draft (Section 16b's candidate-pool overlap
and redraw-narrowing biases; Section 17's arithmetic error and
Section 21's undefined margin) and are fixed in the version now in this
file -- see Amendment Log item 9. The reviewer's other findings (the
Section 8 degeneracy fix itself, the breadth numbers, the ledger
mechanism, Sections 1/2/6/9/15/20/21/23 generally) held up under
adversarial reading and are unchanged.

**No `src/lead_lag/` code exists yet. Phase 4 implementation still
requires the user's explicit approval, now that this amendment has been
reviewed and is being committed.** This amendment does not claim the
hypothesis has passed, and does not claim an unconditional power PASS --
see Sections 17 and 20.

Amendment commit hash: _to be filled in immediately after this file is
committed._

**Amendment 2 drafted 2026-11-14, NOT YET COMMITTED.** Resolves four
Decision 10 methodology questions (leader-breadth present-valid-only
gating, the governing trading-session calendar and denominator, inclusion
of verified weekend special sessions, and adoption of
`nse_holidays.py`/`nse_cm_holidays.pkl` as the governing calendar source)
following an explicit calendar/breadth feasibility audit. See the
"AMENDMENT 2 LOG" section near the top of this document for the full
record, and `lead_lag/DECISION_10_RECONCILIATION_ADDENDUM.md` for the
measurement reconciliation. **This edit exists only in the working tree
pending human review and is not yet a commit.** The 70% follower-breadth
candidate is unchanged and remains open; no primary gate is authorized by
this amendment. **[Superseded by Amendment 5 below, 2026-11-14: the 70%
threshold is now APPROVED. This paragraph is preserved unedited as the
accurate record of Amendment 2's own scope at the time it was drafted.]**

**Amendment 3 drafted 2026-11-14, NOT YET COMMITTED.** A separate
amendment from Amendment 2 -- resolves Decision 16 (multiplicity-family
membership for the two basket-construction configurations and the future
primary-gate alpha). Formal trial count becomes 7; the operative
multiplicity-family denominator becomes 8; the future primary-gate alpha
becomes `0.05/8 = 0.00625`, two-sided. The six-entry `trial_ledger.json`
is unchanged; neither basket configuration is retroactively registered.
See the "AMENDMENT 3 LOG" section for the full record, and
`lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md` for the
accounting detail this amendment implements. **This edit exists only in
the working tree pending human review and is not yet a commit.** No
primary gate is authorized by this amendment; the historical `0.05/6`
derivation and every value computed from it remain in this document,
labeled historical/superseded, not deleted.

**Amendment 4 drafted 2026-11-14, NOT YET COMMITTED.** Records Decision 13
(exact endpoint-price return convention, applied to `R_L(t)`, `R_F(t)`,
`Y(t,h)`, `Momentum_F(t)`) as **APPROVED by explicit user decision on
2026-11-14** -- a settled approval, not reopened for review. Separately
records a **new, explicitly unapproved proposal (Decision 22)** addressing
a Momentum_F(t) early-session endpoint conflict found while auditing
Decision 13's consequences (`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md`
Section 5.3): the documented `09:19`/`09:20` earliest signal anchor is
arithmetically incompatible with `Momentum_F(t)`'s own `t-35` endpoint
requirement, which needs a bar at or after the session open, giving a
conditional earliest anchor of `09:50`/`09:51` depending on Decision 11's
still-unresolved `09:15`-vs-`09:16` question. The proposed rule requires
strict same-session, non-substituted endpoints and observation exclusion
(never imputation) when an endpoint is unavailable. **Decision 22 is a
proposal only and remains OPEN pending explicit human approval -- it is
not approved by this amendment.** See the "AMENDMENT 4 LOG" section for
the full record and `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`
for the complete reconciliation. **This edit exists only in the working
tree pending human review and is not yet a commit.** No primary gate,
Phase 4 implementation, or outcome inspection is authorized by this
amendment. Section 8/9's historical sum-of-per-bar construction and its
worked measurements remain unchanged in this document and are not
retroactively characterized as having used the newly approved convention.
**[Superseded by Amendment 5 below, 2026-11-14: Decision 22 is now
APPROVED (not open), with its exclusion rule fixed; its minimum anchor
remains conditional (`09:50` or `09:51`) pending Decision 11, which was
never approved and remains OPEN -- an intermediate edit briefly claimed
otherwise and has been corrected (see Amendment 5 LOG, Section 2). This
paragraph is preserved unedited as the accurate record of Amendment 4's
own scope at the time it was drafted.]**

**Amendment 5 drafted 2026-11-14, NOT YET COMMITTED. CORRECTED, same day,
following a documentation-repair task.** Records two further approvals:
**Decision 10** (follower-basket breadth floor frozen at **70%**,
present-valid-only counting, `n_t_return` governed unchanged by Decision
17, reusing the existing 2,457-date governing calendar and its unmodified
holiday-verification methodology); and **Decision 22** (the Momentum_F(t)
same-session rule proposed in Amendment 4 is now APPROVED, with rule 6
restated to clarify that no null-control observation may be retained in
place of exclusion). **Decision 22's minimum anchor remains conditional**
(`09:50` if `09:15` is the first valid bar; `09:51` if `09:16` is first
valid instead) **because Decision 11 was never approved and remains
OPEN.** This amendment, as originally drafted, incorrectly stated that
Decision 11 was also approved at `09:15` and that the minimum anchor was
therefore fixed, unconditionally, at `09:50` -- **that was a documentation
error, corrected in Section 2 above; no such user approval was ever
given.** **Decision 13 is reaffirmed exactly as recorded in Amendment 4 --
not reopened or duplicated.** See the "AMENDMENT 5 LOG" section for the
full, corrected record and
`lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md` (updated by
this same task) for the complete reconciliation. **This edit exists only
in the working tree pending human review and is not yet a commit.** No
primary gate, Phase 4 implementation, or outcome inspection is authorized
by this amendment. All historical text describing Decision 10 or Decision
22 as open, candidate, or unresolved is preserved unedited elsewhere in
this document, each now accompanied by a dated status-update note rather
than rewritten -- and Decision 11's own historical "open" text is, and
remains, accurate, not merely historical. **[SUPERSEDED, AMENDMENT 6 LOG,
2026-11-14 (later same day): Decision 11 has since been approved at
`09:15`. This closing sentence was an accurate statement of Decision 11's
status at the time Amendment 5 was drafted -- it is no longer the current
status, and is preserved here unedited as historical record, not as a
description of where Decision 11 stands today. See Amendment 6 below.]**

**Amendment 6 drafted 2026-11-14, NOT YET COMMITTED, later the same day
as Amendment 5.** Records **Decision 11 as APPROVED**: `09:15` is the
frozen first regular-session bar, by explicit user decision, following
review of a final targeted first-bar verification report (direct
`bars_1min` query, reusing the existing governing calendar and Decision
17's validity predicate, no new rule invented). Consequences, both fixed
as single values rather than conditional two-branch figures: the earliest
non-overlapping sampling anchor is `09:20`; the earliest `Momentum_F(t)`
minimum anchor (subject to Decision 22's unchanged validity/exclusion
rules) is `09:50`. `09:16` is not adopted. See the "AMENDMENT 6 LOG"
section for the full record. **This edit exists only in the working tree
pending human review and is not yet a commit.** No primary gate, Phase 4
implementation, or outcome inspection is authorized by this amendment.
Decision 10's, Decision 13's, Decision 17's, and Decision 22's own rules
are unchanged. Decisions 15, 20, and 21 remain OPEN, unaffected. All
historical text describing Decision 11 as open, or describing the earlier,
erroneous approval claim and its correction, is preserved unedited
elsewhere in this document, each accompanied by a dated status-update or
supersession note rather than rewritten.

**Amendment 7 drafted 2026-11-14, NOT YET COMMITTED, later the same day
as Amendment 6.** Records **Decision 23 as APPROVED**: the monthly
leader/follower roster's trailing-60-session turnover ranking excludes
the ranking date's own turnover observation (`trade_date < ranking_date`,
strictly); the roster is frozen as of the close of the trading session
immediately preceding the ranking date and becomes effective from the
ranking date's own first trading session, by explicit user decision
following review of `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md`.
This clarifies, not changes, Section 6's existing "no bar after the
ranking date is used" language, preserved unedited there. See the
"AMENDMENT 7 LOG" section for the full record. **This edit exists only
in the working tree pending human review and is not yet a commit.** This
amendment does not change the annual top-200 universe construction, does
not resolve the separate `prices_eod`-vs-`bars_1min` first-trading-day
calendar discrepancy (folded into Decision 21's existing open scope, not
separately resolved), does not resolve Option 2's own Stage-A threshold
form/value/denominator or its relationship to Decision 10's 70% figure
(both remain OPEN), and does not alter the Stage A/Stage B distinction or
Stage B's zero-tolerance forward-endpoint rule. Decisions 15, 20, and 21
remain OPEN, unaffected. No primary gate, Phase 4 implementation, or
outcome inspection is authorized by this amendment.

**[SUPERSEDED IN PART, AMENDMENT 11 LOG, 2026-11-14 (later same day): the
`prices_eod`-vs-`bars_1min` calendar discrepancy this paragraph describes
as unresolved has since been resolved as Decision 24 (the governing
exchange-session calendar determines ranking dates, not raw presence in
either table). Decisions 15, 20, and 21 have also since been approved
(Amendments 8 and 9). This paragraph is preserved unedited above as the
accurate historical record of Amendment 7's own scope at the time it was
drafted.]**

**[SUPERSEDED, AMENDMENT 8 LOG, 2026-11-14 (later the same day): Decision
15 has since been approved -- see Amendment 8 below. This paragraph's
"Decisions 15, 20, and 21 remain OPEN" statement was accurate as a
description of Amendment 7's own scope at the time it was drafted and is
preserved unedited above; Decision 20 and Decision 21 remain OPEN.]**

**Amendment 8 drafted 2026-11-14, NOT YET COMMITTED, later the same day
as Amendment 7.** Records **Decision 15 as APPROVED**: the signed
effect-size-hurdle gate criterion -- `beta > 0` mandatory for a pass;
`beta * sigma(S_leader) > 20bps`, strictly (equality does not pass); a
statistically significant negative or non-positive `beta` is contrary
evidence, never reinterpreted via `abs(beta)`; the 20bps figure remains
explicitly not a validated transaction-cost or profitability estimate --
by explicit user decision, following review of
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 9's
recommendation. See the "AMENDMENT 8 LOG" section for the full record.
**This edit exists only in the working tree pending human review and is
not yet a commit.** The bare 20bps numeral, the two-sided `alpha=0.00625`
Bonferroni-adjusted significance level (Decision 16), day-clustered
standard errors, the 60-minute primary horizon, and every other Section
20 condition (0, 3, 4, 5, 6) are unchanged. Decision 20 and Decision 21
remain OPEN, unaffected. No primary gate, Phase 4 implementation, or
outcome inspection is authorized by this amendment. All historical text
describing Decision 15 as open or merely recommended is preserved
unedited elsewhere in this document, each accompanied by a dated
status-update note rather than rewritten.

**[SUPERSEDED, AMENDMENT 9 LOG, 2026-11-14 (later the same day): Decision
20 and Decision 21 have since been approved -- see Amendment 9 below.
This paragraph's "Decision 20 and Decision 21 remain OPEN" statement was
accurate as a description of Amendment 8's own scope at the time it was
drafted and is preserved unedited above.]**

**Amendment 9 drafted 2026-11-14, NOT YET COMMITTED, later the same day
as Amendment 8.** Records **Decisions 14, 19 (Stage-A threshold), 20, and
21 as APPROVED**, following a single consolidated methodology review:
`bars_1min` is MIXED CONVENTION (Decision 14); Option 2's Stage-A
threshold is `|frozen_subset|/n_roster_tier >= 0.70` per side, applied at
step 4 (Decision 19); the existing `+/-1`-day corporate-action exclusion
is applied as a Stage A eligibility condition, not a standalone filter
(Decision 20); the 4 weekend special sessions are included and
`2021-02-24` is conservatively excluded, giving a 2,456-date primary
sample while the 2,457-date governing calendar remains unchanged
(Decision 21) -- all by explicit user decision. See the "AMENDMENT 9
LOG" section for the full record. **This edit exists only in the working
tree pending human review and is not yet a commit.** Decisions 10, 11,
13, 15, 16, 17, 22, and 23 are unaffected. Option 1 is not reopened. No
primary gate, Phase 4 implementation, or outcome inspection is authorized
by this amendment. All historical text describing these four decisions
as open is preserved unedited elsewhere in this document, each
accompanied by a dated status-update note rather than rewritten.

**Amendment 10 drafted 2026-11-14, NOT YET COMMITTED, later the same day
as Amendment 9.** Records **Decision 17 as APPROVED**: the full bar-
validity, gap-handling, and Stage A/Stage B precedence policy. Restates,
unchanged, the three previously-settled sub-decisions (A1 -- zero-volume
OHLC-flat bars accepted; B1 -- zero-volume OHLC-non-flat bars flagged
ineligible; C -- the Section 13 gap threshold's unit is exact elapsed
timestamp duration, `<180`s forward-filled, `>=180`s excluded). Newly
approves category D (positive-volume structurally-valid bars, including
numerically extreme values, accepted without an invented cutoff) and
category E (structurally invalid bars, excluded outright, never
repaired or forward-filled at their own timestamp). Formally defines
PRESENT-VALID in this document for the first time, and states explicitly
that Stage A's short-gap forward-fill rule may never be applied to a
Stage B forward endpoint. See the "AMENDMENT 10 LOG" section for the
full record, including a documentation inconsistency found while
drafting it (numerous prior passages referred to Decision 17 as already
settled while its own decision-table row remained OPEN). **This edit
exists only in the working tree pending human review and is not yet a
commit.** This amendment does not reopen Decisions 14, 19, 20, 21, 22, or
23, does not modify `lead_lag/trial_ledger.json`, any source code, or the
master spec, and does not authorize Phase 4, a primary gate, or any
outcome inspection. All historical text describing Decision 17 as open
or partially settled is preserved unedited elsewhere in this document.

**Amendment 11 drafted 2026-11-14, NOT YET COMMITTED, later the same day
as Amendment 10.** Records **Decision 24 as APPROVED**: the governing
exchange-session calendar (the same Decision 10/21 calendar: `nse_holidays.py`
plus explicit special-session verification) determines each month's
first trading session for monthly roster ranking purposes -- not raw
`prices_eod` or `bars_1min` presence. Resolves the `prices_eod`-vs-
`bars_1min` first-trading-day mismatch (4/120 months) that AMENDMENT 7
LOG and AMENDMENT 9 LOG both left open, "folded into Decision 21's
scope." The 4 weekend specials are included (3 of them can be a
February's governing ranking date); `2021-02-24` excluded, per Decision
21; the `2016-10-03`/`2016-10-04` difference is the known intraday-
archive-start artifact, not a calendar disagreement. See the "AMENDMENT
11 LOG" section for the full record. **This edit exists only in the
working tree pending human review and is not yet a commit.** This
amendment does not alter any other Decision 23 rule (turnover source,
60-session window, ranking-date exclusion, freeze/effective timing), the
annual top-200 universe construction, or Decision 10's/21's own governing-
calendar definitions. It does not modify
`lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` (its findings and
wording are reused exactly as measured, not restated as having already
assumed this resolution), `lead_lag/trial_ledger.json`, any source code,
data, roster artifact, or the master spec. It does not authorize Phase 4,
a primary gate, or any outcome inspection. All historical text describing
this calendar question as open is preserved unedited elsewhere in this
document, each accompanied by a dated supersession note rather than
rewritten.

**Amendment 12 drafted 2026-11-14, NOT YET COMMITTED, later the same day
as Amendment 11.** Records **Decisions 7, 8, and 9 as APPROVED
together**: the final primary control set (`R_F(t)` + `TOD(t)` +
`Momentum_F(t)`; trailing realized volatility, coarse trading activity,
and prior-day NIFTY50 sensitivity/diagnostic-only); the fixed-effects
specification (no FE primary, year-FE sensitivity, no quarter FE); and
the prior-day NIFTY50 regime control (omitted from the primary
regression, sensitivity-only as a coarse daily-regime proxy, prior-day
close-to-close only). See the "AMENDMENT 12 LOG" section for the full
record, including a documentation gap found while drafting it (Section
11's own control-set text was never updated for the portfolio-level
Option A estimand; a dated note was appended there rather than rewriting
it). **This edit exists only in the working tree pending human review
and is not yet a commit.** The existing primary regression equation and
all variable definitions (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 6) are unchanged. This amendment does not change Decisions 10,
11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, or 24 -- Decision 12
remains the one OPEN row untouched. It does not modify
`lead_lag/trial_ledger.json`, any source code, data, the master spec, or
any other strategy family. It does not authorize Phase 4, a primary
gate, or any outcome inspection.

**Amendment 13 drafted 2026-11-14, NOT YET COMMITTED, immediately prior
to Phase 4 implementation authorization.** Records **Decision 18 as
APPROVED**: leader and follower roster identities remain fixed for each
monthly roster period; membership is determined solely by the monthly
liquidity-tier assignment; no signal-time availability-based additions,
removals, or replacements; no dynamically filtered or reconstituted
basket during the month. This is the same rule
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3A and
decision-table row 18 already described as RECOMMENDED since this
family's 2026-11-08 revision; this amendment approves it exactly as
stated. See the "AMENDMENT 13 LOG" section for the full record. **This
edit exists only in the working tree pending human review and is not
yet a commit.** This amendment does not change Decisions 10-17 or 19-24
-- Decision 12 remains the one OPEN row. It does not modify
`lead_lag/trial_ledger.json`, any source code, data, the master spec, or
any other strategy family.
