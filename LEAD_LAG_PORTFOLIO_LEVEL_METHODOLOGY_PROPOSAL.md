# Cross-Liquidity-Tier Return Propagation: Portfolio-Level Methodology Proposal

**STATUS: DRAFT -- OPTION A DIRECTION APPROVED -- FINAL METHODOLOGY NOT YET APPROVED -- NOT COMMITTED.**

**Revision 6** of this proposal is the current, latest substantive
methodology revision: drafted 2026-11-08, revised through five prior
rounds, with Revision 6 (reviewed and accepted) correcting three
documentation/definition issues -- see "What changed in Revision 6,
concisely, by part" below. A subsequent documentation-maintenance pass
(metadata and revision-history cleanup only, no methodology change) was
applied after Revision 6; it did not introduce a new substantive
revision number. This remains a **draft** for human review, not a
replacement preregistration. The amended preregistration at commit
`9f71b65`, `lead_lag/trial_ledger.json`, and `lead_lag/MASTER_SPEC_LEAD_LAG.md`
remain unchanged. No Phase 4 code, breadth measurement, power
calculation, regression, bootstrap, null simulation, or outcome
inspection has been authorized or performed. Nothing is committed.

**SUPERSESSION NOTE (2026-11-14): Decision 16 approved.** Section 10
below and this document's "Report" sections describe
multiplicity-family membership for the two basket-construction
configurations as "explicitly OPEN" and state that alpha "remains
`0.05/6`." **Those statements were accurate when written and are not
rewritten here, but Decision 16 has since been approved and closes this
question**: multiplicity-family membership is now **CLOSED/approved**
(an 8-exposure family: the 6 existing configurations plus both basket
options); the **formal trial count is 7**, not 8 (Option 1 counts as an
unregistered Phase 1 feasibility kill; Option 2 does not count as a
formal trial despite being in the multiplicity family); the six-entry
`lead_lag/trial_ledger.json` is unchanged; and the future primary-gate
alpha is **`0.05/8 = 0.00625`**, recorded prospectively in
`PREREGISTRATION_LEAD_LAG_V1.md`'s AMENDMENT 3 LOG (drafted 2026-11-14,
not yet committed). Full accounting:
`lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md`. This single note
supersedes every "OPEN"/"`0.05/6` unchanged" statement below for
multiplicity-family-membership purposes specifically; the historical
narrative in Section 10 and the Report sections is otherwise left as
written, since it was correct at the time and remains useful evidence of
how the decision was reached.

## Verified before this revision (read directly, not inferred from filenames or prior summaries)

- `pwd`: `/c/projects/trade-new`.
- `git log -1`: HEAD is `9f71b65e006f937760e39a9f65035c69a1ef8df9` --
  unchanged.
- `git status --short`: three untracked files only (this proposal, the
  earlier working-draft proposal, the original methodology review). No
  tracked file modified; `git diff --stat` empty.
- `PREREGISTRATION_LEAD_LAG_V1.md`, `lead_lag/trial_ledger.json`,
  `lead_lag/MASTER_SPEC_LEAD_LAG.md`: unchanged since `9f71b65`.
- `PREREGISTRATION_LEAD_LAG_V1.md` Section 12/13 re-read directly: exact
  text quoted in Sections 4 and 5 below.
- `lead_lag/trial_ledger.json` and `lead_lag/ledger.py` re-read in full
  for Section 10.
- `PROJECT_CONTEXT.md` lines 138-142 re-read directly: the exact trial
  definition quoted in Section 10.
- **New this revision**: `src/fibo/intraday_db.py`'s `bars_1min` schema
  re-read directly, specifically the `ts` column comment: `"ts
  TIMESTAMP NOT NULL, -- bar START time, Asia/Kolkata, naive
  (exchange-local, no tz math needed)"`. **`bars_1min.ts` labels the bar's
  START, not its end** -- this was previously flagged as unverified in
  the committed preregistration itself (Section 8 of `9f71b65`: "its
  exact timestamp convention... is still to be verified empirically").
  It is now verified directly from the schema comment, not inferred from
  market convention. Consequences worked out in Section 5 below.
- **New this revision**: `grep -n "09:15" src/fibo/backtest.py` shows
  Fibo's own ORB logic uses **"the 09:15-09:30 1-minute bars"** directly
  as its opening-range window -- i.e. existing, already-running code in
  this project treats the `09:15` bar as valid, ordinary regular-session
  data, not as a pre-open/auction artifact requiring exclusion. This is
  real evidence, not an assumption, but it is evidence from a *different*
  study's usage pattern, not a direct query of `bars_1min`'s own earliest
  timestamp per day -- its limits are stated precisely in Section 5.
- **New this revision**: `src/data_layer/corporate_actions.py`'s own
  docstring re-read directly: scope is **"deliberately narrow: only
  bonus and face-value-split events... Dividends, buybacks, AGMs, rights
  issues... are not reliably machine-parseable from this feed... out of
  scope here."** `known_date` is set equal to `ex_date` ("`caBroadcastDate`
  is always null on this feed; `ex_date` is unambiguously public").
  **Corrected in Revision 6**: this establishes only that the existing
  corporate-actions pipeline excludes dividends from its supported feed
  -- it does not establish that no dividend data exists anywhere else in
  the project, and no project-wide dividend-source inventory has been
  performed (used in Section 4A/4C, narrowed accordingly). It also
  confirms split/bonus events are indexed by `ex_date`, a whole trading
  day, not an intraday timestamp (used in Section 4C's re-analysis).

If any of the above had differed from the expected state, this task
would have stopped before editing. None did. (This revision also
re-verified `lead_lag/trial_ledger.json` directly for Part 4 below --
six entries, unchanged content, matching every prior revision's own
reading.)

**Revision 5's own Part 0 check, performed fresh at the start of this
round**: `pwd` = `/c/projects/trade-new`; HEAD =
`9f71b65e006f937760e39a9f65035c69a1ef8df9`, matching the expected commit
exactly; `git status --short` showed the same three untracked files as
every prior round; `git diff --stat` was empty; all four protected files
(`PREREGISTRATION_LEAD_LAG_V1.md`, `lead_lag/trial_ledger.json`,
`lead_lag/MASTER_SPEC_LEAD_LAG.md`, `PROJECT_CONTEXT.md`) were confirmed
present via direct listing. No discrepancy found; editing proceeded.

**Revision 6's and the subsequent documentation-maintenance pass's own
Part 0 checks, each performed fresh at the start of their respective
rounds**: identical result each time -- HEAD `9f71b65e006f937760e39a9f65035c69a1ef8df9`,
the same three untracked files, empty `git diff --stat`, all four
protected files present. No discrepancy found in either round; editing
proceeded in both.

## What changed in Revision 6, concisely, by part

**Revision 6 made three documentation/definition corrections to
Revision 5's own text -- it did not resolve any open methodological
question, and none of the three is an empirical finding.** Full detail
in Section 3D-A, Section 10, and Section 12's "Revision 6's three
corrections" subsection.

1. **Dividend evidence**: the opening evidence-verification summary (just
   above) had retained an unsupported project-wide claim ("dividends are
   not tracked at all by any existing mechanism") even after Section 4A's
   body text was already narrowed in Revision 5. Corrected so the summary
   and Section 4A agree: the existing corporate-actions pipeline excludes
   dividends from its supported feed; this says nothing about whether
   dividend data exists elsewhere in the project, and no project-wide
   inventory has been performed.
2. **Missingness-emulation ground truth**: Section 3D-A's ground-truth
   definition required full-roster validity only at the three pre-signal
   endpoints (`t-35`, `t-5`, `t`), while its own later steps compared
   `Y(t,h)` -- a forward quantity needing the full roster to also be valid
   at `t+h`. Corrected to require horizon-specific full-roster validity
   at `t-35`, `t-5`, `t`, **and** `t+h` before an observation qualifies as
   ground truth for that horizon; insufficient-coverage handling made
   explicit (report as a finding, never relax the requirement or
   substitute a partial return).
3. **Trial accounting**: "denominator becomes 8" could be read as
   asserting eight is the current actual trial count. Corrected to
   distinguish the current recorded ledger count (**six**, unchanged)
   from the two proposed/prospective basket-construction configurations
   (not registered, not examined) and the conditional prospective total
   (**eight**, contingent on approval, registration, and each
   configuration subsequently qualifying under the existing trial
   definition). Multiplicity-family membership remains explicitly OPEN;
   the committed `alpha = 0.05/6` is unchanged.

**None of the above changed any formula, endpoint, horizon, threshold,
return definition, regression specification, bootstrap rule, ACF rule,
decision-table status, or protected file.**

## What changed in Revision 5, concisely, by part

1. **Part 1**: a real loophole in the ACF lag-decay rule is closed -- the
   prior rule could accept a single isolated terminal lag as evidence of
   decay. A minimum consecutive run length `R` (`>=2` by construction,
   exact value left OPEN) is now required, with precise handling of
   indeterminate lags within a candidate run (Section 7B.4).
2. **Part 2**: project trial count, multiplicity-adjustment family
   membership, and alpha allocation are now explicitly separated (Section
   10). Trial count remains recommended at 8; **multiplicity-family
   membership for the two basket-construction configurations is left
   genuinely OPEN**, with reasoning on both sides; the existing committed
   `alpha = 0.05/6` is explicitly confirmed unchanged, never silently
   replaced with `0.05/8`.
3. **Part 3**: the missingness-emulation diagnostic (Section 3D) is split
   into two endpoint-specific components -- (A) pre-signal eligibility-mask
   emulation, preserving which endpoint failed and re-running the exact
   eligibility determination; (B) a forward-endpoint/observation-inclusion
   diagnostic that explicitly never computes a partial forward return,
   since Option 2 never does so operationally.
4. **Part 4**: the dividend-data claim is narrowed from "no dividend data
   exists anywhere in this project" to "the existing corporate-actions
   pipeline does not provide it" -- the broader claim was never
   established by a project-wide audit (Section 4A).
5. **Part 5**: corporate-action evidence is split into three explicit
   categories (project-code / exchange-mechanism / intraday-data,
   Section 4C). The prior revision's assertion that "NSE's own standard
   mechanism... overnight" is established fact is walked back -- no
   authoritative source was ever verified; it is now stated as a
   commonly understood but unverified premise.
6. **Part 6**: a terminology note is added at the top of Section 3
   distinguishing the nominal signal label `t` from the wall-clock time
   (`t+1`) at which the bar labelled `t`'s close actually becomes
   available, closing a prose-level risk that "at or before `t`" could be
   misread as "at wall-clock `t`." No arithmetic or anchor changed.
7. **Part 7**: the included-vs-excluded diagnostic (Section 3C) no longer
   claims `S_L(t)`/`R_F(t)`/`Momentum_F(t)` are unconditionally observable
   for excluded observations -- four exclusion categories are distinguished,
   each with its own variable-availability statement, and diagnostic-only
   partial-subset values are explicitly forbidden from being labelled as
   the primary construction's own quantities.
8. Decision table (rows 10, 12, 16, 20) and adversarial review updated to
   match; no new rows; no previously APPROVED or RECOMMENDED row's status
   changed.

## What changed in the prior revision (Revision 4), for reference

1. **Part 1**: a real gap in the previous "Option 2 avoids future-dependent
   selection" claim is corrected. **Constituent-selection bias** (future
   data choosing *which names* enter the basket) and **observation-selection
   / informative-censoring bias** (future data availability determining
   *whether an already-defined observation is kept at all*) are now
   explicitly distinguished. The corrected Option 2 (and Option 1)
   eliminate only the first. Concrete mechanisms by which future
   missingness can be informative (halts, illiquidity, extreme moves,
   feed failures) are named; a diagnostic comparing included vs. excluded
   observations on legitimately observable grounds is specified, with an
   explicit statement that matching on observables does not prove
   non-informative missingness.
2. **Part 2**: the return-distortion diagnostic is strengthened. The
   prior "compare a missing name's own nearby returns" check is retained
   but **demoted to a supplementary, descriptive-only diagnostic** --
   it cannot reveal the actual missing return on the exact observation
   where a name was unavailable. A new **missingness-emulation**
   diagnostic is specified: apply realistic missingness masks (drawn from
   observed patterns, never from `t+h` outcomes) to observations where
   the full-roster return is actually known, and measure the resulting
   mechanical distortion directly.
3. **Part 3**: a real overstatement is corrected. The controls-only
   baseline-residual series (excluding `S_L(t)`) is **hypothesis-predictor-free**,
   not "outcome-independent" or "fully firewalled" -- it still contains
   `Y(t,h)`. The ACF-based block-length procedure is now fully specified:
   lag measured in true trading-session positions; pairwise-valid `n_k`
   per lag (not one shared day-count); a deterministic decay/extension/maximum-lag
   rule; and an explicit statement of which two numerical sub-parameters
   remain genuinely open pending measurement, rather than invented.
4. **Part 4**: the prior revision's three-entry, denominator-9
   recommendation is re-examined and found to **double-count the
   estimand** -- `estimand:portfolio_level_response` cannot itself reach
   a gate or be killed independent of a basket-construction choice, so it
   is not an independently countable configuration under this project's
   own definition. **Revised recommendation: two entries (the two basket
   constructions only), denominator 8**, with a residual interpretive
   question named rather than hidden.
5. **Part 5**: the exact location of Option 2's minimum-breadth threshold
   within the construction is now specified precisely (applied to the
   already-frozen, at-or-before-`t` eligible subset, before any
   computation and before the `t+h` check) -- an ordered, 9-step
   algorithm. The threshold's **form** (count, fraction, or both) is
   distinguished from its **value** (still open); both are explicitly
   distinguished from the unrelated, already-committed leader-side
   per-minute breadth floor.
6. **Part 6**: decision table (rows 10, 12, 16, 19) and adversarial review
   updated to reflect all of the above; no new rows added, no previously
   APPROVED row's status changed.

---

## 1. Adopting Option A as the primary estimand [APPROVED direction]

Unchanged from the prior revision:

```
R_L(t)   = leader-portfolio return over the 5-minute signal window ending at t
R_F(t)   = follower-portfolio return over the SAME window
S_L(t)   = R_L(t) - R_F(t)
Y(t,h)   = follower-portfolio forward return over horizon h, starting immediately after t

Y(t,h) = alpha + beta*S_L(t) + gamma*R_F(t) + delta.X(t) + epsilon(t,h)
```

One observation per `(trading day, signal minute t)`. `beta` measures the
incremental predictive association between the leader portfolio's recent
return and the follower portfolio's subsequent return, conditional on the
follower portfolio's own contemporaneous return -- not causal information
diffusion, not a market-adjusted or abnormal return (no independent
intraday benchmark exists; Section 4B).

The old per-follower, leave-one-out-demeaned dependent variable is
dropped from this study [APPROVED]. Not re-litigated here.

---

## 3. The basket-composition problem -- Option 2 corrected, bound types separated

### Terminology clarified this round: nominal `t` vs. wall-clock availability

**Every "at or before `t`" / "`t`-or-earlier information" statement in
this section means the same precise thing, stated once here rather than
left to be inferred from context each time**, to close a real
look-ahead risk the prior wording could invite:

- **Nominal signal endpoint label `t`**: the integer index used
  throughout this document's notation (`R_F(t)`, `S_L(t)`, etc.) -- a
  label, not itself a wall-clock time.
- **The bar labelled `t`**: the `bars_1min` row whose `ts` (bar-start
  timestamp, Section 5) equals clock time `t`.
- **The wall-clock time that bar's close becomes available**:
  approximately `t+1` (Section 5 -- the bar labelled `t` has not finished
  until one minute after it starts).
- **The time a quantity is actually computable**: a quantity that needs
  `P_i(t)` (the close of the bar labelled `t`) is not computable until
  wall-clock `t+1`, not at wall-clock `t`.

**Eligibility (Section 3C below) uses information available by the time
the relevant quantity is actually computable -- i.e. the close of the bar
labelled `t`, available at approximately wall-clock `t+1` -- not
information available at the nominal label `t` taken literally as a
wall-clock time.** An implementation that treated "`t`" as the decision
timestamp and used the bar labelled `t`'s close *at* wall-clock `t` would
introduce a one-minute look-ahead; this document's own return-window
arithmetic (Section 4, Section 5) already waits for the correct,
later wall-clock moment, and this is now stated explicitly so a future
implementation does not reintroduce the error through notation alone.
**This clarification changes no arithmetic and no anchor recommendation**
-- `09:20`/`09:21` (Section 5) and the `h+5` spacing (Section 5) are
unchanged; it only tightens the prose so "at or before `t`" cannot be
misread as "at wall-clock `t`."

### A. Monthly roster -- fixed, identity-only, never availability-filtered

Unchanged from the prior revision: the roster is the full set of entities
assigned to the leader or follower tier that month by the existing
point-in-time construction (Section 6/7 of `9f71b65`). Signal-time price
availability never removes a name from the roster; there is no
substitution of any kind, for any reason (short gap, long gap, or
corporate action -- Section 4C).

**STATUS UPDATE (2026-11-14)**: "the existing point-in-time construction"
had a genuine, previously unexamined ambiguity -- whether the monthly
ranking date's own turnover observation is included in or excluded from
the trailing-60-session median used to rank entities. This is now
**RESOLVED, by explicit user decision, as decision item 23 in Section 11**
(`lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md`): the ranking date's
own turnover is **excluded** (Convention A, prior-session cutoff); the
roster is frozen before, and becomes effective from, the ranking date's
own market open. This clarifies, but does not change, "the existing
point-in-time construction" described above -- no new eligibility rule,
substitution, or availability filter is introduced by this resolution.

**FURTHER STATUS UPDATE (2026-11-14, later the same day)**: a separate
sub-question -- *which calendar* identifies "the ranking date" (the
first trading day of the month) -- was left open by the resolution
above: `prices_eod`'s own `series='EQ'` calendar and `bars_1min`'s own
archive-presence calendar disagree in 4 of 120 documented months
(`lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` Section 4.1). This is
now **RESOLVED, by explicit user decision, as decision item 24 in
Section 11**: the governing exchange-session calendar (the same
calendar already used for Decisions 10 and 21 -- `nse_holidays.py` plus
explicit special-session verification) determines ranking dates, not
raw presence in either `prices_eod` or `bars_1min`. The 4 verified
weekend special sessions are included (3 of them, on the 1st of
February, can be that month's governing ranking date); `2021-02-24` is
excluded, per Decision 21; `2016-10-03` vs. `2016-10-04` is the known
intraday-archive-start artifact, not a calendar disagreement. This does
not alter any other part of the resolution above.

**FURTHER STATUS UPDATE (2026-11-14, immediately prior to Phase 4
implementation authorization)**: the fixed-roster-identity rule this
subsection's heading and opening paragraph describe is now **APPROVED,
by explicit user decision, as Decision 18** (decision-table row 18) --
exactly as already stated above, with no substantive change: roster
membership is fixed for the month, determined solely by the monthly
liquidity-tier assignment, with no signal-time availability-based
additions, removals, or replacements, and no dynamic mid-month
reconstitution. See `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 13 LOG
for the full record.

### B. Observation-level completeness -- a gate, never a per-name filter, unified across every control the observation needs

Unchanged in principle, **extended in scope**: the completeness gate must
account for **every** endpoint any part of the observation's own model
actually needs -- not only the signal window (`t-5, t`) but also, if
`Momentum_F(t)` remains a control (Section 6), its own endpoints
(`t-35, t-5`). This is addressed precisely in the revised Option 2
construction below (C), which unifies all of these into a single
eligibility determination rather than letting each control filter its
own, separately-selected sample (the specific risk the momentum-consistency
instruction warns against).

Forward completeness (at `t+h`, per horizon) remains a separate,
subsequent check on the same frozen subset, gating the whole observation,
never reweighting survivors.

**No numerical threshold is chosen here** -- deferred to the
already-approved breadth/feasibility work (Section 3D).

### Applying the same construction to the leader roster

Unchanged: identical logic applies to `R_L(t)`.

### C. Fixed weights -- three distinct bound types, and a corrected Option 2

**The prior revision's claim is withdrawn as incorrect, not merely
imprecise.** It stated that, under a `95%` completeness threshold, "any
single kept observation's realized basket differs from the full roster by
at most 5% of its members" and treated this as if it bounded the
resulting economic distortion. **It does not.** Three different things
were being conflated:

1. **Bound on missing-constituent count** -- directly set by the
   completeness threshold (e.g. `<=5%` of the roster missing). This is
   the only thing a completeness threshold actually bounds by itself.
2. **Bound on constituent-weight deviation** -- under equal-weight
   renormalization among the available subset, each remaining name's
   weight shifts from `1/n` to `1/n_available`; this shift is also
   directly computable from the missing-count, and is small whenever the
   missing-count is small.
3. **Bound on portfolio-return deviation** -- **does not follow from (1)
   or (2) at all.** Dropping one name `k` from an `n`-name equal-weight
   average changes the computed return by `|R_true - R_k| / (n-1)`
   (exact algebra: `R_partial = (n*R_true - R_k)/(n-1)`). This depends on
   `R_k`, the **missing name's own return** -- which, by definition, is
   not observed for that observation. If missingness is **not** random
   with respect to return magnitude (plausible: the same illiquidity or
   halt that causes a stale/missing bar may also coincide with an
   unusually large true move), a small number of missing names can
   produce a portfolio-return deviation **far larger** than their count
   share would suggest. **This document no longer claims the third bound
   follows from the first two.**

### Two distinct future-dependence mechanisms -- not to be conflated [new this revision]

Every construction below must be evaluated against **two separate**
mechanisms by which future (`t+h`) information could bias this design,
not one:

1. **Constituent-selection bias**: future information changes **which
   names populate the basket itself**. This is the mechanism the
   freeze-then-check design (fixed two revisions ago) and the per-observation
   eligibility unification (B above) were built to eliminate -- and do
   eliminate, for both Option 1 and the corrected Option 2 below.
2. **Observation-selection / informative-censoring bias**: even with
   constituent membership fully frozen using only `t`-or-earlier
   information, **whether a given, already-defined observation is kept
   or discarded at all still depends on `t+h` endpoint availability.** If
   the *reason* an observation gets excluded correlates with the outcome
   being measured, the surviving sample is a non-random, outcome-correlated
   subset of all candidate signal times -- a different mechanism from
   (1), and one that whole-observation exclusion does **not** remove.

**Eliminating (1) does not eliminate (2), and this document does not
claim otherwise anywhere below.**

**Why future endpoint missingness may be informative, not incidental**
-- concrete mechanisms, not a generic caveat:

- **Trading halts/suspensions**, often triggered *by* extreme price moves
  (e.g. circuit-breaker halts) -- the halt is a direct consequence of the
  very outcome this design measures, so excluding halted-and-therefore-incomplete
  observations removes exactly the tail of the return distribution,
  possibly the region where any real propagation effect would be
  strongest (or weakest).
- **Illiquidity or stale-price conditions** -- chronic staleness (a name
  that is routinely thin) is partly addressed by Option 1's roster-wide
  requirement; *acute* staleness (a name that goes quiet immediately
  following a specific event) is forward-looking-informative in a way
  chronic staleness is not.
- **Extreme price movements themselves** -- a stock hitting an exchange
  circuit limit stops trading for the remainder of the window, so the
  most extreme realized moves are mechanically the ones most likely to
  produce a missing or zero-volume bar.
- **Data-feed or market-event failures** -- plausibly closer to
  missing-completely-at-random, named here for balance: not every
  missingness mechanism need be informative, and this document does not
  assume any one mechanism dominates without evidence.
- **Other mechanisms correlated with subsequent returns** -- e.g.
  corporate actions (Section 4C) often coincide with unusual trading
  patterns independent of the scale-discontinuity question addressed
  there.

**This document does not claim that whole-observation exclusion makes
the retained sample unbiased.** It only avoids compounding mechanism (2)
with a *second*, construction-level distortion (reweighting among
survivors) -- which is why that alternative remains rejected. **No
replacement of an unavailable constituent after observing `t+h`, and no
future-informed weighting or imputation, is proposed anywhere in this
document.** If such a correction (e.g. an inverse-probability-weighting-style
adjustment for informative censoring) were ever considered, it would need
to be its own, separately described and separately approved methodology
-- not a silent patch to either option below.

### Option 1 -- unchanged in construction; its own future-dependence revisited

100% roster completeness; no composition ambiguity when kept; exclusion
rate unmeasured, possibly severe; measured, not assumed, in Section 3D.

**Option 1 fully solves mechanism (1) above and leaves no composition
ambiguity at all when an observation is kept -- but it does not solve
mechanism (2), and may trigger it more severely than Option 2**: because
Option 1 requires *every one* of ~160 roster members to have valid `t+h`
data simultaneously, a single halted or stale name anywhere in the
roster is enough to discard the observation -- a stricter, more easily
triggered forward-dependency than Option 2's own gate, which only
requires the already-smaller, pre-filtered frozen subset to clear `t+h`,
not the full original roster. **Compositional purity and vulnerability to
informative censoring are two separate properties; Option 1 improves the
first and may worsen the second.**

### Option 2 -- exact ordered construction, with the breadth threshold located precisely

**The previous Option 2 (a vague "high threshold, reweight among
survivors" description) is replaced with the specific, ordered candidate
below**, which **must never use `t+h` data to decide basket membership**:

1. Start with the fixed monthly leader/follower roster (A above).
2. Determine constituent eligibility using **only** information
   computable by the time the signal is actually computable (per the
   terminology clarified at the top of this section -- the close of the
   bar labelled `t`, available at approximately wall-clock `t+1`, not at
   wall-clock `t` itself), covering **every** historical endpoint any control
   in the primary model (Section 6) actually needs -- for the current
   specification, this means `t-35`, `t-5`, and `t` (the momentum
   window's two endpoints and the signal window's second endpoint; `t-5`
   is shared between them). A name missing at `t-35` but present at `t-5`
   and `t` is **not** partially includable for `R_F(t)` only -- it is
   excluded from the **whole** observation's eligible subset, so that
   `R_F(t)`, `Y(t,h)`, and `Momentum_F(t)` are never computed over three
   different, separately-filtered samples.
3. **Freeze** the eligible subset -- membership and equal weights
   (`1/n_eligible`) are fixed from this point; no further addition,
   removal, or substitution occurs for this observation.
4. **Apply the minimum-breadth threshold to this frozen subset, here and
   nowhere else in the construction** -- i.e. after eligibility is
   determined and frozen (steps 2-3), before anything is computed from it
   (step 6) and before the forward check (step 7). **This is the precise
   location of the threshold in the algorithm**, resolving the ambiguity
   the prior revision left unaddressed.
5. If the threshold is not met, mark the observation ineligible. **No
   substitution of names occurs** -- the observation is simply not used.
6. If the threshold is met, use the **same** frozen subset and weights,
   consistently, for `R_F(t)`, `Y(t,h)`, and `Momentum_F(t)` -- one common
   portfolio identity per observation, not three.
7. Check `t+h` completeness against this already-frozen subset, **only
   now**, as a whole-observation pass/fail gate.
8. If any frozen-subset member fails at `t+h`, discard the **entire**
   observation -- never reweight, replace, or reselect constituents.
9. **Step 8 is still a form of future-dependent observation inclusion
   (mechanism 2 above), even though no future-dependent constituent
   selection (mechanism 1) occurs anywhere in steps 1-6.** This revision
   states this explicitly rather than implying the construction is fully
   future-dependence-free.

**What the minimum-breadth threshold is, and is not, expressed as --
no numerical value is chosen here.** Candidate forms, left open:

- A minimum **count** of eligible constituents (e.g. "at least `N`
  names"), which does not automatically scale with the roster's own size
  (documented to vary from ~144 to ~160 across months, Section 6 of
  `9f71b65`) -- a fixed count could be a near-100% requirement in a thin
  month and a loose one in a full month.
- A minimum **fraction** of that month's roster (e.g. "at least `X%`"),
  which scales naturally with roster size but could, at the extreme, pass
  a very small absolute count in an unusually thin month.
- **Both** jointly (a fraction floor and an absolute-count floor), which
  avoids the degenerate small-absolute-count case above at the cost of a
  second free parameter.

**Which form, and what value, is left entirely OPEN**, pending the
Section 3D measurement work -- the missingness-emulation diagnostic (D
below) is the right tool for choosing a value that is actually about
return-distortion risk, not merely about constituent count.

**Explicitly distinguished from the leader-side breadth requirement
already in this family's preregistration** (Section 8 of `9f71b65`:
`n_t >= 0.80 * leader-tier size`, a **per-minute** floor on how many
leaders have a valid bar at a given instant, deciding whether
`S_leader(t)`/`S_L(t)` is computed at all that minute): **the threshold
specified here is a different quantity, on a different tier, at a
different granularity** -- a **per-observation** floor on how many
followers survive the unified `(t-35, t-5, t)` eligibility check,
deciding whether the follower-side portfolio construction (`R_F`/`Y`/`Momentum_F`)
is trusted for that observation. **The two numbers must not be assumed
equal, confused, or merged** -- the existing `0.80` leader-side figure is
not inherited here, and the follower-side figure is determined by its own,
separate measurement.

**Evaluation of coherence, restated precisely**: this construction is
mathematically and operationally coherent and fully eliminates
**constituent-selection** (mechanism 1) bias. It does **not** eliminate
**observation-selection/informative-censoring** (mechanism 2) bias, which
both Option 1 and corrected Option 2 retain by necessity. **Neither
Option 1 nor Option 2 is selected in this revision.** Both remain OPEN
(Decision 19), now with the two-mechanism distinction and the
breadth-threshold location both made explicit.

**DATED SUPERSESSION NOTE (2026-11-14, added by a documentation-correction
task).** The paragraph above accurately described this decision's status
*at the time this section was drafted*. **It no longer describes the
current status.** `PREREGISTRATION_LEAD_LAG_V1.md`, AMENDMENT 3 LOG, item
3, records: *"Option 2 (`basket_construction:option2_frozen_subset_fallback`)
was examined before registration and **subsequently selected as the
basket-construction methodology by human decision**. It is **not a
formal trial** — selection is not equivalent to a Phase 1 kill or to
reaching a preregistered predictive gate."* **Option 2 — the exact 9-step
construction above — is therefore the selected basket-construction
methodology. Option 1 was not selected.** This is an existing human
decision record, already present in the preregistration's own working-tree
AMENDMENT 3 LOG (drafted 2026-11-14, not yet committed to git, but an
existing decision record nonetheless) — it is not a new approval made by
this note, and this note does not ask for one.

**What remains open, and is not resolved by the selection above
(important distinction, preserved, not weakened)**: selecting Option 2
as *which construction governs* does **not** by itself fix Option 2's own
internal parameters. Still explicitly OPEN, exactly as the paragraphs
above already state and as this note does not alter:
- The exact **form** of Option 2's own minimum-breadth threshold (count,
  fraction, or both) — see "What the minimum-breadth threshold is, and is
  not, expressed as" above.
- The exact **value** of that threshold.
- **Whether Decision 10's separately-approved `70%` follower-breadth
  figure is the value intended for this threshold** — Decision 10's own
  text (`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 5 LOG Section 1) is
  modeled on the leader-side *per-minute* `n_t_breadth` convention and
  never names "Option 2," "the frozen eligible subset," or this step-4
  threshold specifically. **The two are not automatically the same
  parameter merely because selection has occurred**, and this note does
  not equate them.

The informative-censoring/observation-selection-bias discussion above
(mechanism 2, retained by both options "by necessity") is **unaffected
by the selection** and is preserved in full, unedited, as the accurate
and still-relevant rationale for why Option 2's own residual limitation
is understood and disclosed, not newly discovered or newly resolved.

**FURTHER STATUS UPDATE (2026-11-14, later the same day, following a
consolidated methodology review)**: the form, value, and denominator
question posed immediately above is now **APPROVED**: step 4's minimum-
breadth threshold is `|frozen_subset(t,side)| / n_roster_tier(month,side)
>= 0.70`, a **fraction** of that side's **original monthly roster-tier
size** (not the frozen subset's own size), applied **separately** for
`side in {leader, follower}`, evaluated exactly at step 4 as already
described above. **The `0.70` value is a fresh decision for this specific
purpose, not an inheritance of Decision 10's separate per-minute follower
floor** -- the two remain the distinct mechanisms the paragraph two above
already describes, now simply sharing a number by deliberate choice. See
`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 9 LOG, Section 2, and
decision-table row 19 for the full record. The mechanism-2
(observation-selection) limitation discussed above remains, unaffected --
this approval resolves only the Stage-A threshold, not Stage B's own
informative-censoring exposure.

### Required diagnostic -- comparing included and excluded observations, variable availability now conditioned on exclusion category [corrected this round]

**The prior wording claimed `S_L(t)`, `R_F(t)`, and `Momentum_F(t)` are
observable for both included and excluded observations, unconditionally.
That is not true for every exclusion reason, and this round corrects it.**
If an observation is excluded because its own pre-signal eligible subset
never cleared the breadth threshold in the first place, `R_F(t)` (and
possibly `S_L(t)`, if the leader side is similarly affected) may not be
computable **at all** for that observation -- there is no reliable
quantity to report, not merely an unobserved one.

**Four exclusion categories, with variable availability stated
separately for each**:

1. **Failure to meet the pre-signal eligibility/breadth requirement**
   (Section 3C step 4: the frozen follower-side subset is too small).
   `R_F(t)` and `Momentum_F(t)` are **not reliably computable** -- they
   would have to be computed from a subset too small to trust by the
   proposal's own breadth logic, which is precisely why the observation
   is excluded. If computed anyway for diagnostic curiosity, such a value
   must be labelled explicitly as a **diagnostic-only partial-subset
   figure** (e.g. `R_F_diagnostic_partial(t)`) and never equated with the
   primary construction's `R_F(t)`. `S_L(t)` is unaffected **only if** the
   leader side independently cleared its own, separate breadth floor
   (Section 8 of `9f71b65`) -- the two sides must be checked
   independently, not assumed to succeed or fail together.
2. **Failure at the forward `t+h` endpoint check specifically** (the
   pre-signal side cleared its breadth threshold; some frozen-subset
   member fails only at `t+h`). Here `S_L(t)`, `R_F(t)`, and
   `Momentum_F(t)` **are** genuinely computable and observable -- the
   frozen subset passed its own breadth check, so these at-or-before-`t`
   quantities are well-defined. Only `Y(t,h)` itself is unobservable in
   this category.
3. **Failure due to a missing or invalid signal endpoint on the leader
   side** -- a distinct failure mode from category 1 (which concerns the
   follower-side frozen subset): if the leader-tier breadth floor
   (Section 8 of `9f71b65`) fails at `t`, `S_L(t)` is not computable,
   **even if the follower side is otherwise fine and `R_F(t)` is
   computable**. This category must not be merged with category 1 --
   they affect different tiers and can occur independently.
4. **Any other explicitly supported exclusion reason** (e.g. a
   corporate-action-driven exclusion, if candidate policy (ii) from
   Section 4C is eventually adopted) -- variable-specific availability
   depends on the specific policy chosen and is not stated in advance of
   that choice.

**Observable for both included and excluded observations, but only in
categories 2 and (partially) 3-4 above, never unconditionally**: time of
day; a market-regime proxy computed only from `t`-or-earlier data;
whichever of `S_L(t)`/`R_F(t)`/`Momentum_F(t)` the specific category
leaves computable.

**Observable for excluded observations only in a restricted,
non-operational sense** (unchanged from the prior revision): price/volume
behavior in the stock(s) that caused the exclusion, in the minutes
*between* `t` and the point of failure -- informative diagnostically, but
**not usable inside the actual construction itself**, since using it
operationally would reintroduce exactly the future-dependence Option 2 is
built to avoid.

**Not observable for excluded observations at all, in any category**:
the true, full-roster forward return `Y(t,h)` itself.

**Possibly not available from existing data at all**: a direct
classification of *why* a given bar is missing (halt vs. feed gap vs.
generic staleness) -- `bars_1min`'s schema carries no explicit reason
code; whether any classification is derivable from `angel_token`,
`source`, or other existing fields is unresolved. **If the actual
exclusion reason cannot be identified from existing fields for a given
observation, this must be reported as unknown, never fabricated into a
specific category.**

**This document does not claim that matching on the observable
characteristics above proves missingness is non-informative, and does
not claim any unavailable variable is secretly observable.** Selection on
observed characteristics can never rule out selection on unobserved ones
-- at best, close agreement on every observable dimension, within the
category where it is genuinely available, is *reassuring*, not
*dispositive*.

### D. Required diagnostics -- missingness emulation added as the primary return-distortion check

Unchanged from the prior revision: roster size per month (known);
signal-time and per-horizon forward valid-count/fraction; whole-observation
exclusion rate under Option 1 and corrected Option 2; exclusion-rate
breakdown by time-of-day/liquidity-rank/regime; sufficiency of remaining
independent trading days; the included-vs-excluded diagnostic above.

**The "nearby-return comparison" check named in the prior revision
(comparing a missing name's own realized returns, on days it is present,
against the group average) is retained, but demoted explicitly to a
descriptive, supplementary diagnostic.** It speaks only to that name's
*general* behavior pattern, not to its actual (unobserved) return on the
*specific* observation where it went missing -- it cannot, by itself,
establish the magnitude of return distortion bound-type-3 (C above)
describes.

**The diagnostic is split into two distinct components this round,
because pre-signal endpoint missingness and forward (`t+h`) endpoint
missingness are not the same masking operation and must not be treated
as interchangeable** -- the former affects which names are eligible for
the frozen basket at all (Section 3C's mechanism 1 territory, resolved by
construction), the latter determines whether an already-frozen
observation is used at all (mechanism 2, never resolved). Conflating them
would blur exactly the distinction Section 3C exists to keep separate.

### A. Pre-signal eligibility-mask emulation (none of it run here)

Applies to missingness at the endpoints that determine the frozen
eligible subset: `t-35`, `t-5`, `t`.

**Ground-truth definition corrected this round -- a real gap closed.**
Revision 5's step 1 required full-roster validity only at the three
pre-signal endpoints (`t-35`, `t-5`, `t`) before treating an observation
as "ground truth." **This is insufficient**: the diagnostic's own step 7
goes on to recompute and compare `Y(t,h)`, which needs the full roster to
also be valid at the **forward** endpoint `t+h` -- pre-signal validity
alone says nothing about whether the forward outcome is actually
observable for the full roster. Without this, the "known full-roster
reference" the comparison relies on may not exist. Corrected procedure:

1. **Ground-truth eligibility is defined separately for each horizon
   `h`** (5/15/30/60 minutes) -- an observation's eligibility as a clean
   reference is not a single fact independent of which horizon is being
   diagnosed, since `t+h` differs by horizon.
2. For a given horizon `h`, an observation qualifies as a **full-roster
   ground-truth observation** only if the full fixed roster has valid
   required price endpoints for **every** quantity the comparison in
   step 9 below will use: the pre-signal endpoints `t-35`, `t-5`, `t`
   **and** the forward endpoint `t+h` for that specific horizon, **and**
   any other endpoint the actual frozen construction of `R_F(t)`,
   `Momentum_F(t)`, or `Y(t,h)` requires. **Pre-signal validity alone does
   not qualify an observation as ground truth for any horizon.**
3. All reference quantities for a qualifying observation (`R_F(t)`,
   `Momentum_F(t)`, `Y(t,h)` for that `h`) are computed using the exact
   same frozen return definitions and endpoint conventions (Section 4)
   that the proposed primary construction uses -- no separate or relaxed
   definition for the ground-truth reference itself.
4. **Only after** a clean, horizon-specific, full-roster reference
   observation is established (steps 1-3) are the pre-signal missingness
   masks applied, at `t-35`, `t-5`, and/or `t`, **preserving which
   specific endpoint(s) were missing for each affected name** -- not
   merely how many names were missing in total.
5. **Re-run the exact Option 2 eligibility determination** (Section 3C
   step 2) on the masked data, including its frozen-subset (step 3) and
   breadth-threshold (step 4) logic in full -- do not shortcut this with
   a simplified count-only mask that ignores which endpoint failed.
6. **Recompute only the quantities the masked construction actually
   defines.** If the masked eligible subset fails the breadth threshold,
   the masked construction does not define `R_F(t)`/`Y(t,h)`/`Momentum_F(t)`
   for that trial at all -- this is an exclusion outcome (reported per
   step 9), not a return-distortion data point, and must never be
   papered over by substituting a partial return.
7. Where the masked construction does define a quantity, compare it
   against the corresponding, already-validated full-roster reference
   quantity for the **same** underlying observation and horizon.
8. Preserve the exact weighting and return arithmetic the real candidate
   construction would use throughout -- no shortcuts.
9. **Report the number of eligible ground-truth observations separately
   by horizon** (a different full-roster-at-`t+h` requirement per
   horizon will generally yield a different count), together with:
   return distortion (mean signed, median/upper-tail absolute, for
   trials where a comparison was defined); frequency of sign changes;
   the realized eligible-constituent count after masking; and the rate
   at which masked trials failed the breadth threshold outright (an
   exclusion outcome, reported separately from return distortion), with
   reasons where the data supports classifying them.
10. **The masking patterns come from the observed *structure* of
    missingness, never from `t+h` outcomes or from how the comparison
    turns out** -- no mask is chosen or adjusted after seeing the
    resulting distortion figures.

**Insufficient ground-truth coverage, handled explicitly, not patched
around**: if the clean, horizon-specific, full-roster ground-truth sample
is too small or unrepresentative for a given horizon, **report
insufficient ground-truth coverage for that horizon as a finding.** Do
**not** relax the full-roster endpoint requirement (including the `t+h`
requirement just added) to manufacture more "clean" observations; do
**not** substitute a partial forward return for the missing full-roster
reference; do not silently change the roster or return construction to
make more observations qualify; do not claim the diagnostic establishes
missing-at-random regardless of coverage. **The adequacy threshold for
"too small to be meaningful," and any resulting decision rule, are left
explicitly OPEN** -- no already-approved rule in this family directly
governs this specific diagnostic's minimum sample size, and inventing one
here would be exactly the kind of unjustified numerical choice this
family's standing discipline exists to prevent.

### B. Forward-endpoint missingness and observation-inclusion diagnostic (none of it run here)

Applies to missingness at `t+h`. **Option 2 never computes a partial
forward portfolio return after a frozen-subset member fails the forward
check -- it discards the entire observation (Section 3C step 8).
Accordingly, this diagnostic never simulates a "what the forward return
would have been" calculation, since that would represent a quantity the
real construction never produces.**

1. **Do not** calculate a partial forward portfolio return under any
   forward-missingness mask -- this is the specific shortcut this
   component explicitly prohibits.
2. Apply realistic forward-missingness patterns (observed elsewhere) to
   otherwise-clean observations **only to determine how often the actual
   whole-observation discard rule (step 8) would have triggered** -- a
   count/frequency exercise, not a return-recomputation exercise.
3. Report the induced observation-exclusion rate and its variation by
   time of day, by liquidity strata, by missingness pattern, and by any
   other supported pre-signal characteristic (Section 3C's
   included-vs-excluded diagnostic, Part 7 of this round).
4. Compare retained and excluded observations only on variables genuinely
   available for both groups (per the exclusion-category-specific
   availability matrix, Section 3C, Part 7 of this round) -- never on the
   forward return itself.
5. **State the limitation explicitly, every time this diagnostic is
   reported**: the actual forward return of a discarded observation
   remains unobserved. This diagnostic measures how often and under what
   conditions discarding happens, not what was discarded.

### Shared constraints across both components

- **Neither component proves missing-at-random.** Component A measures
  mechanical return-distortion sensitivity to a realistic pattern;
  component B measures the frequency and correlates of observation
  exclusion. Neither establishes that the real missingness mechanism is
  unrelated to the outcome.
- **No mask is chosen or modified based on `t+h` outcomes, or because a
  given mask produces a more favorable diagnostic result**, in either
  component.
- **If the available missingness patterns cannot be reconstructed
  reliably** (too few clean ground-truth observations for A; too few
  representative forward-missingness examples for B) **that must be
  reported as a limitation, not resolved by inventing patterns or
  loosening the procedure after seeing a disappointing result.**

**None of this is run in this task.**

---

## 4. Portfolio return arithmetic -- dividends, adjustment, and corporate actions re-examined

### A. Return definition -- unchanged, citation strengthened

`R_i(a -> b) = P_i(b)/P_i(a) - 1`; `PortfolioReturn(a -> b) = mean_i(R_i(a -> b))`
over the frozen subset (Section 3). **Price return, not total return,
dividends excluded.**

**Claim narrowed this round -- the prior wording overreached.** What is
actually established, precisely: `src/data_layer/corporate_actions.py`'s
own docstring states dividends are **out of scope for that pipeline
specifically** ("not reliably machine-parseable from this feed... out of
scope here"). **This establishes only that the existing corporate-actions
pipeline does not provide dividend data -- it does not establish that no
dividend information exists anywhere else in this project.** No
project-wide inventory of every data source has been performed in this
task (or any prior revision), and this document does not claim one has.
**The proposal therefore adopts a price-return convention with dividends
excluded as a methodology choice, consistent with and motivated by the
one data source (`bars_1min`) this family actually reads from, not
because a comprehensive audit has proven dividend data is unavailable
project-wide.** If a separately authorized, sufficiently comprehensive
repository audit later found dividend data elsewhere, that would not by
itself change this methodology choice (the convention is adopted because
`bars_1min` -- the actual source used -- has no such data and no
adjustment path for it), but it would mean the broader "no dividend data
anywhere" claim should not be relied upon until such an audit exists.
**The distinction between price return and total return is unchanged**:
every return in this proposal remains a price return, uniformly, for the
reasons above.

### B. Price adjustment status of `bars_1min` -- unchanged conclusion

Unchanged: strong circumstantial evidence of raw, unadjusted prices (no
adjustment column or code anywhere in `bars_1min`'s schema or read path);
not a positive confirmation; a targeted historical-split verification is
recommended as later, separately authorized work (Decision 14).

**STATUS UPDATE (2026-11-14)**: that targeted verification was performed
(`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`) and found the opposite
of the circumstantial inference above: `bars_1min` is **MIXED
CONVENTION**, back-adjusted for split/bonus actions at 103/104 tested
events, piecewise (~2-year trailing windows), with between-session-only
scale boundaries. **Decision 14 is now APPROVED** on this basis -- see
decision-table row 14 and `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 9
LOG, Section 1, for the full record and its explicit limitations (vendor
mechanism unverified; 104-event tested population only). The paragraph
above is preserved unedited as the accurate historical record of this
section's conclusion before that verification ran.

### C. Corporate actions -- re-examined mechanistically, not assumed sufficient OR assumed excessive

**The prior revision's framing (treat any nearby corporate action as an
invalid endpoint, folded into the completeness count) is replaced with a
more precise analysis**, per instruction, distinguishing cases that do
and do not actually threaten an intraday, single-session return. **This
round further corrects an overreach in that analysis**: the earlier text
asserted "NSE's own standard mechanism recalculates the previous close...
overnight" as if it were an established fact. **It was not established
-- it was a common understanding of exchange convention, never traced to
an authoritative source verified within this proposal's own materials.**
The three evidence categories below separate what is actually known from
what is merely assumed.

**1. Project-code evidence** -- what is actually established by reading
this project's own code:

- `corporate_actions.py` records split/bonus events keyed by `ex_date`,
  a whole **trading date**, with `known_date` set equal to `ex_date`.
- The pipeline's scope is deliberately narrow: only bonus and
  face-value-split events are parsed; dividends, buybacks, AGMs, and
  rights issues are explicitly out of scope (Section 4A).
- **What the project code does not record**: any intraday timestamp for
  when, within the ex-date's session, an adjustment takes effect; any
  direct statement about whether intraday prices on or after the ex-date
  are adjusted or raw; any confirmation of exchange-side mechanics
  (circuit-limit recalculation, reference-price reset) at all -- the
  pipeline's data model is silent on all of this, by design, since it
  only needs the ex-date for the **daily** adjustment-factor pipeline it
  actually serves.

**2. Exchange-mechanism evidence** -- **no authoritative NSE source for
split/bonus effective timing or reference-price adjustment mechanics has
been verified within this proposal's own materials.** The claim that
splits/bonuses take effect "overnight, before the session opens" reflects
a commonly understood convention, not a citation this task can stand
behind. **This document does not invent or assert such a citation.** The
exchange mechanism itself -- specifically, whether intraday trading on an
ex-date (or any date near one) is internally scale-consistent as a
consequence of how NSE actually applies the adjustment -- **remains to be
independently verified**, not assumed true because it is commonly
believed.

**3. Intraday-data evidence** -- **unverified**, unchanged from the prior
revision: whether `bars_1min` is internally scale-consistent around actual
historical split/bonus events has not been checked against real data.
This remains a targeted, separately authorized check for later work, not
performed here.

**Four distinct cases, restated against this corrected evidence
hierarchy**:

1. **An action whose adjustment, IF the commonly understood (but
   unverified, per category 2 above) exchange mechanism holds, takes
   effect *before* the trading session** -- `corporate_actions.py`'s
   `known_date = ex_date` convention (category 1) is *consistent with*,
   but does not *prove*, this mechanism. **If** it holds, an intraday
   return computed entirely within one session should not see a scale
   discontinuity, since every bar within a single session would already
   be on one consistent scale. All of this family's constructs are, by
   the existing, unchanged Section 12 rule, already confined to a single
   session. **This entire case is conditional on an unverified premise
   and is stated as such, not as an established fact.**
2. **An action effective *during* a relevant return interval** -- would
   require either a genuinely atypical, intraday-timed adjustment (contrary
   to the commonly understood, but unverified, day-level norm) or an
   observation spanning two sessions (excluded by the existing rule,
   assuming that rule is airtight). **Not ruled out with certainty.**
3. **Incorrectly adjusted or mixed-scale historical prices** -- the
   `Bug #18`-class risk, previously found in the **daily** pipeline.
   Whether an analogous defect could exist *within* `bars_1min` itself is
   category-3 evidence territory: **unverified, not addressed by anything
   read for this proposal.**
4. **Ex-dividend effects under the price-return convention** -- not a
   corporate action this project's pipeline tracks at all (Section 4A);
   a known, accepted property of any price-return convention, not a
   defect requiring exclusion.

**Necessity of the existing rule -- explicitly not decided either way.**
**This document does not claim the existing single-entity `+/-1`-trading-day
exclusion rule is either necessary or unnecessary** for this family's
intraday constructs. The reasoning in case 1 above, even if the
underlying exchange mechanism is eventually confirmed, would only support
"unnecessary for this specific risk" -- it says nothing about whether the
rule guards against some other risk (e.g. category-3-style mixed-scale
defects, which case 1's reasoning does not touch at all). **Both
"necessary" and "unnecessary" require the category 2 and category 3
verifications above, neither of which has been performed.**

**Required factual verification before selecting a rule** (not performed
in this task, proposed as later, separately authorized work): (a)
identify or confirm an authoritative source for NSE's actual split/bonus
adjustment-timing mechanism (category 2); (b) directly inspect
`bars_1min`'s actual intraday price behavior around one or more known
historical split/bonus ex-dates (category 3), to check both whether case
1's premise holds in practice and whether any case-3-style mixed-scale
artifact appears within a single session.

**Two named candidate policies, both OPEN (Decision 20) -- neither
removed**:

- **(i) No special intraday corporate-action exclusion** for
  observations confined to a single session (motivated by case 1's
  reasoning), checked later via the verification above.
- **(ii) Retain a conservative exclusion**, but -- consistent with
  Section 3's "no separate per-name filtering mechanism" principle --
  fold a corporate-action-affected name's endpoint into the **same**
  completeness-counting framework (Section 3B/C) rather than a
  standalone, entity-level, whole-day rule, so it never operates as a
  second, parallel filtering mechanism alongside the roster/completeness
  logic.

**Neither is adopted here.** The policy remains OPEN until the
verification above is performed.

**STATUS UPDATE (2026-11-14)**: the category-3 verification named above
("directly inspect `bars_1min`'s actual intraday price behavior around
one or more known historical split/bonus ex-dates") was subsequently
performed by `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md` Section 7
(zero within-session mixed-scale defects, 104 events / 208 sessions /
77,654 bars). **Decision 20 is now APPROVED**: policy (ii) is adopted --
the existing `+/-1`-day exclusion is retained, folded into Stage A's
eligibility check (step 2 above) at `t-35`, `t-5`, `t`, rather than
operating as a standalone whole-day filter. **Category 2 (the
exchange-mechanism question) remains unverified** -- this approval does
not rest on it, only on the category-3 result now available; this
approval does not claim all corporate-action-related scale risk is
eliminated, only that none was found in the tested population. See
decision-table row 20 and `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 9
LOG, Section 3, for the full record. The paragraphs above are preserved
unedited as the accurate historical record of this section's analysis
before that verification was available.

### D. Endpoint and gap-handling compatibility -- unchanged four categories, now cross-referenced to the unified eligibility step

Unchanged from the prior revision: the four categories (genuinely traded;
zero-volume-stale-close; permitted forward-filled; invalid/corrupted
endpoint) and the open question of whether the existing Section 13 text
actually distinguishes the second from the fourth. **Cross-reference,
new in this revision**: these same four categories now apply uniformly
to **all three** endpoints the unified Section 3C eligibility check
needs (`t-35, t-5, t`), not only to the signal window's two -- consistent
with the single-frozen-subset design.

**STATUS UPDATE (2026-11-14)**: the ambiguity this subsection flagged is
now **APPROVED** as Decision 17 -- see decision-table row 17 and
`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 10 LOG for the full policy:
PRESENT-VALID is formally defined (positive-volume structurally-valid,
or zero-volume OHLC-flat); FUNCTIONALLY ABSENT is defined separately for
gap-length classification only (true absent timestamp, zero-volume
OHLC-non-flat, or structurally invalid); the exact-duration `<180`s/
`>=180`s gap threshold is restated; and Stage A's short-gap rule is
explicitly barred from ever applying to Stage B's `t+h` zero-tolerance
check. **This approval does not resolve the underlying vendor-semantics
uncertainty for zero-volume bars or prove any positive-volume bar
reflects a genuine trade** -- both remain permanently unverifiable
limitations, unchanged by this approval. The paragraph above is
preserved unedited as the accurate historical record of this
subsection's open question before 2026-11-14.

### E. Adoption status

**STATUS UPDATE (2026-11-14): APPROVED.** The exact endpoint-price return
convention described in Section 4A above (`R_i(a,b) = P_i(b)/P_i(a) - 1`,
price return, dividends excluded, applied consistently to `R_L(t)`,
`R_F(t)`, `Y(t,h)`, and `Momentum_F(t)`) is approved by explicit user
decision on 2026-11-14 -- Decision 13. This is a settled approval, not
reopened for review. It is prospective: it governs Phase 4 implementation
going forward and does not retroactively characterize any
already-completed measurement (e.g. this family's registered Section 8/9
sum-of-per-bar construction, or any real-data figure computed with it) as
having used this convention. See `PREREGISTRATION_LEAD_LAG_V1.md`'s
AMENDMENT 4 LOG and `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`
for the full reconciliation record.

*(Historical, preserved for provenance -- this was the status at the time
this section was originally drafted, before the 2026-11-14 approval
above)*: "Unchanged: RECOMMENDED, not APPROVED (Decision 13)."

---

## 5. Non-overlapping observation spacing -- anchor mechanics re-grounded in the verified timestamp convention

### Timestamp convention -- verified, with consequences worked out

**Directly confirmed** (`src/fibo/intraday_db.py` schema comment,
quoted at the top of this document): `bars_1min.ts` labels a bar's
**start**, not its end. Given this, and given OHLCV semantics generally
(a bar's `close` is, by definition, the price at the end of that bar's
own interval, independent of how the bar's timestamp is labeled): **the
price this proposal calls `P_i(k)` -- "the close of the bar whose `ts`
equals clock time `k`" -- represents the price at approximately clock
time `k+1` minute**, i.e. the moment that one-minute interval has fully
elapsed. This has a direct, previously unstated consequence: the
signal-window formula `R_i(t-5 -> t)` uses `P_i(t-5)` (≈ price at clock
`t-4`, the window's start) and `P_i(t)` (≈ price at clock `t+1`, the
window's end) -- so the window **as labeled by bar-start timestamps
`t-4` through `t`** genuinely spans clock time `[t-4, t+1)`, a clean
5-minute interval, with no off-by-one error in the *span* -- but the
information needed to compute `P_i(t)` (bar `t`'s close) is itself not
knowable until bar `t` has fully elapsed, i.e. until **wall-clock time
`t+1`**. **The response window's own first required price, `P_i(t)`, is
therefore the same quantity that becomes available at exactly the moment
the signal itself becomes usable** -- an internally consistent, no-gap,
no-duplicate-minute design, but one where "nominal signal-completion time
`t`" and "the wall-clock moment the signal is actually known" differ by
one minute. This is stated explicitly here so a later implementation
does not conflate the two.

### Whether `09:15` is a valid, included regular-session bar -- RESOLVED, 2026-11-14 (see status update below); evidentiary history preserved as originally drafted

**New evidence, not an assumption**: `src/fibo/backtest.py` uses "the
09:15-09:30 1-minute bars" directly as Fibo's own opening-range window --
i.e. an already-running study in this project treats `09:15` as ordinary,
usable regular-session data. NSE's own standard session structure (pre-open
auction concludes before continuous trading begins) is also consistent
with `09:15` being the first regular-session minute, not a pre-open
artifact. **This is evidence from a different study's *usage pattern*,
not a direct query of `bars_1min`'s own `MIN(ts)` per trading day** --
this task's own boundary (no broad bar-data query) does not permit
settling the question with certainty here. **The prior revision's Section
12-citing claim that "the existing exclusion already removes the
pre-open/auction bar(s) and the very first completed bar" is therefore
weakened to: evidence suggests this may not be necessary at `09:15`
specifically, but this is not confirmed.**

**STATUS UPDATE (2026-11-14), then CORRECTED (2026-11-14, same day)**:
an earlier edit in this working tree stated "APPROVED -- Decision 11" here,
claiming `09:15` had been confirmed by explicit user decision as the sole
first valid regular-session bar. **That claim was incorrect and is
retracted. Decision 11 was never approved by the user and remains OPEN.**
The `09:15`-vs-`09:16` question is unresolved; `09:16` has not been ruled
out as an alternative. This correction note is left in place, rather than
silently removed, specifically so the history of the erroneous claim is not
erased -- see `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`
for the full corrected record. The paragraph above (the evidentiary
discussion) is accurate as far as it goes and is unaffected by either the
erroneous claim or this correction -- it was, and remains, "evidence found,
not conclusively settled," exactly as its own heading says.

**FINAL STATUS UPDATE (2026-11-14, later the same day, following a
separate, explicitly authorized targeted verification task)**: Decision
11 is now **APPROVED at `09:15`**, by explicit user decision, after
review of a direct, targeted `bars_1min` query (not the indirect Fibo-ORB
usage evidence described above) that measured `09:15`/`09:16` presence
and structural validity across the governing calendar, confirmed a
specific `2020-11-23`-to-`2020-11-27` archive-coverage episode and three
special/truncated-session dates, and attributed both to the existing,
already-approved eligibility machinery rather than to any ambiguity in
the session-boundary definition itself. `09:16` is not adopted. See
`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 6 LOG for the full record.
**This supersedes every "OPEN"/"not conclusively settled" statement in
this subsection and in Section 11's decision table row 11 below** -- those
statements are preserved unedited above/below as the accurate historical
record of this question's status before 2026-11-14, not restated as
current.

### Required design -- unchanged in structure, anchor re-derived precisely

1-5. Unchanged: one fixed clock-time anchor per horizon, independent of
any day's data; schedule generated from the derived spacing (65/35
minutes); anchor chosen before any outcome is examined and never moved;
failed scheduled slots are skipped, never shifted; the anchor is not
selected by comparing sample-size, significance, beta, or power.

**Candidate anchor, re-derived** [RECOMMENDED, OPEN]: **if** `09:15` is
indeed the dataset's first valid regular-session bar (evidence above,
not fully confirmed), the earliest possible signal window is bars
`09:15, 09:16, 09:17, 09:18, 09:19` (`t-4=09:15, t=09:19`), whose final
bar (`t=09:19`) closes -- becomes known -- at wall-clock `09:20`. **This
is the same `09:20` candidate as before, now derived from the verified
`ts`=bar-start convention plus the Fibo-ORB evidence, rather than from a
generic "mechanically possible" argument alone.** **If** a genuine
pre-open-bar exclusion turns out to apply at `09:15` after all (not
confirmed either way), the earliest valid signal window would instead
start at `09:16`, giving `t=09:20` and an anchor of **`09:21`**. **Both
figures are reported; neither is chosen with certainty**, pending the
`MIN(ts)`-per-day check named as required, later, separately authorized
verification (Decision 11).

**CORRECTED STATUS (2026-11-14, same day)**: an earlier edit here claimed
"Decision 11 is now APPROVED at `09:15`" and declared the first branch
operative. **That claim was incorrect and is retracted -- Decision 11 was
never approved and remains OPEN.** Both branches above remain live and
conditional:

- **If `09:15` is the first valid regular-session bar**: signal-end minute
  `t=09:19`, non-overlapping sampling anchor `09:20`.
- **If `09:16` is the first valid regular-session bar instead**:
  signal-end minute `t=09:20`, non-overlapping sampling anchor `09:21`.

Neither branch is chosen. This is a restatement of the paragraph above's
own original, correct conditional, not a new derivation -- it is repeated
here only to make unmistakable that the erroneous "APPROVED" claim that
previously appeared at this location is retracted, and the figures it
asserted as settled are once again explicitly conditional on Decision 11,
which remains OPEN.

**FINAL STATUS UPDATE (2026-11-14, later the same day)**: Decision 11 is
now genuinely APPROVED at `09:15` -- see the status update earlier in
this section and `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 6 LOG. The
first branch above is the one that obtains: **signal-end minute `t=09:19`,
non-overlapping sampling anchor `09:20`, unconditionally.** The `09:16`/
`09:21` branch is not adopted. This differs from the earlier, retracted
"APPROVED" claim this subsection corrects in one essential way: that claim
was false when made (no user decision existed); this one records a real
decision made after the correction, on separate evidentiary grounds.

### How the schedule interacts with session structure

Unchanged in substance (market open/close; incomplete windows per Section
3's gate; corporate-action exclusions per Section 4C, now OPEN between
two named policies rather than a single assumed rule; invalid scheduled
observations skipped, never shifted), **except**: "pre-open/auction"
handling is now stated as **conditional on which anchor is ultimately
confirmed** (09:20 vs. 09:21), not asserted as already resolved by
construction. **CORRECTED STATUS (2026-11-14, same day)**: an earlier edit
here claimed the anchor was "confirmed as `09:20` (Decision 11, approved)."
**That claim was incorrect and is retracted.** The sentence immediately
above this note -- "conditional on which anchor is ultimately confirmed
(09:20 vs. 09:21), not asserted as already resolved by construction" --
was the accurate statement at the time this correction was written:
Decision 11 was OPEN and neither anchor was confirmed.

**FURTHER STATUS UPDATE (2026-11-14, later the same day)**: Decision 11
has since been genuinely approved at `09:15` -- see the status updates
earlier in this section. The anchor is now confirmed as `09:20`,
unconditionally, by a real approval, not by the earlier, retracted claim
this note corrects.

**Special trading sessions**: unchanged -- unverified, flagged (Decision
21). **STATUS UPDATE (2026-11-14)**: Decision 21 is now **APPROVED** --
the 4 verified weekend special sessions are included under the
unmodified session convention; `2021-02-24` is conservatively excluded;
the primary-sample calendar is 2,456 dates. See decision-table row 21
and `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 9 LOG, Section 4.

### Interval terminology -- unchanged

The three-way distinction (non-overlapping return increments; shared
endpoint price observations; overlap of the complete signal-plus-forward
interval) and the `h+5` spacing derivation are both retained exactly as
in the prior revision, re-verified again by the same worked example
(`t=10, h=60`: interval `[6,70]`; next valid `t'=75`: interval `[71,135]`;
no overlap).

---

## 6. Controls -- unchanged from the prior revision; reproduced here in full so this document remains self-contained

No changes requested in this round.

### Contemporaneous return vs. recent momentum: checked for overlap, as instructed

`R_F(t)` is defined over the 5-minute signal window `[t-4,t]` (prices at
bars `t-5` and `t`). If "recent momentum" were defined over that same
window, it would be `R_F(t)` restated, and exactly (not merely
mechanically) collinear with it. **Momentum is therefore defined over a
disjoint, strictly earlier window**, at the task's own proposed
boundaries, `[t-34, t-5]` (30 one-minute bars, ending exactly where the
signal window begins, sharing the single boundary price `P(t-5)` but no
bars):

```
Momentum_F(t) = (1/n_followers) * sum_j [ P_j(t-5) / P_j(t-35) - 1 ]
```

using the frozen follower basket (Section 3, now a single eligibility
determination shared with `R_F`/`Y`, per this revision's Part 1 fix), the
same exact-endpoint-price construction as Section 4. **This window is
adopted as given in the task, not selected by comparing alternative
windows against `Y` or `beta`** -- the methodological justification is
frequency separation (30 minutes is an order of magnitude longer than the
5-minute signal window, giving a genuinely slower-moving own-trend
measure), not fit quality.

**STATUS UPDATE (2026-11-14)**: under the now-approved Decision 13
exact-endpoint convention, `Momentum_F(t)` requires exactly two price
observations, at clock times `t-35` and `t-5` -- not every one of the "30
one-minute bars" the paragraph above describes; that phrasing reflects
this window's origin as a cumulative-sum description and is retained
unchanged above, but the approved construction uses only the two named
endpoints. A genuine conflict was found between this window's start
endpoint and the earliest documented signal anchor: see decision item 22
in Section 11 below and `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`.

**FURTHER STATUS UPDATE (2026-11-14): Decision 22 is now APPROVED** (it
was still only a proposal when the note immediately above was written).
**Decision 22's approval stands and is unchanged by the correction below.**

**CORRECTION (2026-11-14, same day)**: this note previously went on to
claim that "Decision 11 also now approved at `09:15`" collapsed the
minimum-anchor arithmetic to a single unconditional figure, `09:50`. **That
claim about Decision 11 was incorrect and is retracted -- Decision 11 was
never approved and remains OPEN.** The minimum-anchor arithmetic therefore
remains **conditional, exactly as originally derived**:

- If `09:15` is the first valid regular-session bar: `t-35 >= 09:15`, so
  **`t >= 09:50`**.
- If `09:16` is the first valid regular-session bar instead: `t-35 >=
  09:16`, so **`t >= 09:51`**.

Neither branch is chosen; this is a conditional lower bound only, in
either branch, never a guarantee of basket or endpoint validity. If either
`Momentum_F` endpoint is invalid or unavailable, the observation is
excluded from the primary regression sample (no null-control retention,
imputation, or substitution) -- this exclusion rule itself, decision item
22's approved text below, is unaffected by this correction and remains
approved.

**FINAL STATUS UPDATE (2026-11-14, later the same day)**: Decision 11 is
now genuinely APPROVED at `09:15` -- see `PREREGISTRATION_LEAD_LAG_V1.md`
AMENDMENT 6 LOG. The minimum-anchor arithmetic therefore resolves,
unconditionally, to **`t >= 09:50`**. This remains a lower bound only --
it does not guarantee basket or endpoint validity, which continues to be
governed, unchanged, by Decision 22's approved exclusion rule (rules 1-6,
decision item 22 below).

### Control evaluation and final proposed regression equation

```
Y(t,h) = alpha + beta*S_L(t) + gamma*R_F(t) + delta_1*TOD(t) + delta_2*Momentum_F(t) + epsilon(t,h)
```

where:

- `S_L(t) = R_L(t) - R_F(t)` (Section 4).
- `R_F(t)`: follower-portfolio contemporaneous return (Section 4) --
  required, part of the base estimand, not a discretionary addition.
- `TOD(t)`: categorical time-of-day bucket (opening-30 / midday /
  closing-30), unchanged from the existing per-follower design.
- `Momentum_F(t)`: follower-portfolio return over the disjoint `[t-34,t-5]`
  window, defined above.

**Reported as sensitivity specifications alongside the primary model
above, not folded into it** [RECOMMENDED]:

- **Year fixed effects** (not quarter -- simpler, fewer parameters
  relative to the ~2,468-day sample while still leaving adequate
  within-year identification). **Purpose**: absorb slow, multi-year
  drift common to `S_L(t)` and `Y(t,h)` that is unrelated to short-horizon
  propagation, so `beta` in the fixed-effects specification is identified
  from within-year co-movement only. Reported alongside, not replacing,
  the no-fixed-effects primary, specifically so a genuinely slow-moving
  real effect is not invisibly absorbed by the fixed effects if included
  as the sole specification.
- **Prior trading day's NIFTY50 close-to-close return**, if included at
  all [OPEN -- Decision 9]: explicitly labeled a coarse daily-regime
  proxy, never an intraday or market-adjusted control; must use the
  **prior** day's close only (same-day close is not known intraday, so
  using it would be look-ahead).
- **Trailing realized volatility** (leader and/or follower portfolio):
  sensitivity-only, included if and only if a specific primary purpose is
  separately justified -- none is asserted by default here.
- **Coarse trading-activity measure** (total traded value, full eligible
  universe, that day): **not** added as a separate regression control by
  default, to avoid duplicating whatever breadth/completeness exclusion
  rule Section 3's measurement work establishes -- a day with
  systemically thin trading is likely to already fail those completeness
  checks. Recommended use: a **diagnostic** comparison of excluded vs.
  included days, not a regression term [RECOMMENDED, OPEN whether to add
  as a formal control instead].

**No independent intraday market or sector index exists** (confirmed,
Section 4B / `lead_lag/DATA_AUDIT_LEAD_LAG.md` Section 2); none is
invented here.

**STATUS UPDATE (2026-11-14)**: the primary control set above (`R_F(t)`,
`TOD(t)`, `Momentum_F(t)`) is now **APPROVED as Decision 7**, exactly as
specified in the equation and bullet list above -- **unchanged by this
approval**. The fixed-effects treatment is now **APPROVED as Decision
8**: no fixed effects in the primary specification; year fixed effects
sensitivity-only, exactly as described above (not quarter, and never
replacing the no-FE primary). The prior-day NIFTY50 treatment is now
**APPROVED as Decision 9**: omitted from the primary regression;
included only as a sensitivity control, explicitly labeled a coarse
daily-regime proxy; prior trading day's close-to-close return only, never
the same-day close. Trailing realized volatility and the coarse
trading-activity diagnostic remain exactly as described above --
sensitivity/diagnostic-only, never primary controls, not newly settled
by this approval beyond their existing RECOMMENDED status. **The
limitation that no independent intraday market or sector index exists is
unchanged and is not resolved by approving the NIFTY50 sensitivity
control.** See decision-table rows 7, 8, and 9 and
`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 12 LOG for the full record.
The bracketed `[RECOMMENDED]` / `[OPEN -- Decision 9]` / `[RECOMMENDED,
OPEN...]` labels above are preserved unedited as the accurate historical
record of this subsection's status before 2026-11-14.

---

## 7. Inference and bootstrap -- dependence diagnostic strengthened, calendar spacing corrected

### A. Freezing the selection principle -- unchanged

The block length `L` is chosen using only a measured property of the
data's own dependence structure, before and independently of fitting the
`S_L`/`Y` regression or examining any of its results. Explicitly
forbidden: choosing `L` from the smallest p-value, the largest beta, the
narrowest confidence interval, the most favorable standard error, or
whether a choice clears the (now renamed, Section 9) effect-size hurdle.

### B. A concrete, reproducible diagnostic -- terminology corrected, fully specified, none of it run here

**0. Terminology correction, this round.** The controls-only baseline-model
residual series (excluding `S_L(t)`) is **hypothesis-predictor-free, not
outcome-independent and not "fully firewalled" from the outcome.** The
prior revision's language overstated this. **The residuals still contain
`Y(t,h)`, the dependent variable itself** (`residual = Y(t,h) - fitted
value`) -- the diagnostic is blind to the hypothesis-specific result
(there is no `beta`, no p-value for the propagation hypothesis, and no
effect-size-hurdle comparison derivable from a model that excludes
`S_L(t)` entirely), but it is **not** blind to the outcome series' own
statistical properties in general. Both facts are stated together,
precisely, from this point on -- excluding `S_L(t)` reduces direct
hypothesis-result peeking; it does not make the diagnostic outcome-free.

**1. Series examined -- unchanged in substance, terminology corrected.**
Examine **two** series, both hypothesis-predictor-free in the sense just
defined:

- **(a) The controls-only baseline-model residual series** (signed): fit
  `Y(t,h) = alpha + gamma*R_F(t) + delta_1*TOD(t) + delta_2*Momentum_F(t) + epsilon`
  -- the full control set excluding `S_L(t)` -- and use this baseline
  model's day-level aggregated residuals.
- **(b) The same baseline residuals, squared (or absolute)**: to detect
  volatility-clustering-type dependence that a linear check on signed
  residuals would miss, a well-documented phenomenon in financial returns
  generally, not a speculative one.
- **No third series is proposed.** Any future addition would need its
  own, separately stated justification, fixed before measurement, not
  introduced ad hoc.

**2. Aggregation to day level**: the simple mean of that day's realized,
non-overlapping baseline-model residuals (or their squares, for series
(b)).

**3. Exact ACF calculation.**

- Lag is measured in **true trading-session positions**: every actual
  NSE trading day occupies its real sequential position in the calendar,
  whether or not it has a valid diagnostic value (unchanged correction
  from the prior revision -- restated precisely here, since Part 3 of
  this round re-emphasizes it must not be reversed again).
- For lag `k`, the sample autocorrelation is computed using the subset of
  `(i, i+k)` day-pairs where **both** days have a valid value --
  **pairwise-complete-case** correlation, never compressing excluded days
  out of the sequence. A missing observation must never make two distant
  trading days appear adjacent.
- `n_k`, the number of valid pairs **at that specific lag**, is reported
  alongside each lag's correlation estimate. **The reference band uses
  `n_k`, not a single fixed day-count shared by every lag** -- a
  refinement on the prior revision's wording, which implied one `n_days`
  served every lag; once pairwise-complete handling with real exclusions
  is applied, different lags will generally have different valid-pair
  counts.
- **Reference band**: `+/- 2/sqrt(n_k)`, the standard large-sample
  white-noise band, assuming approximate stationarity and asymptotic
  normality of the sample ACF under a true-white-noise null -- a
  pre-existing statistical convention, stated here as an assumption the
  diagnostic relies on, not a proven property of this data.
- **Insufficient valid pairs at a given lag**: if `n_k` is too small for
  the asymptotic band to be a reasonable approximation, that lag is
  reported as **indeterminate**, not silently treated as satisfying (or
  failing) the decay criterion by default. **The exact minimum `n_k` for
  a lag to be evaluable at all is left OPEN**, to be set by reference to
  standard time-series-diagnostic practice once the real, post-exclusion
  day counts are known -- not invented here as an arbitrary number.

**4. Deterministic lag-selection rule -- corrected this round to close an
isolated-terminal-lag loophole.**

**The problem with the prior rule, stated precisely**: "the smallest `L`
such that every lag from `L` through the current maximum qualifies" can
be satisfied by a run of length **one** -- e.g. if lags 1-9 all fail the
decay criterion and only lag 10 (the current maximum) qualifies, the
prior rule's own wording accepts `L=10` as "every lag from 10 through 10
qualifies." **A single qualifying lag at the edge of the examined range
is not evidence of decay; it could be noise.** The rule is rewritten
below to require a genuine run, not an isolated point.

- Fixed initial lag range: 1 through 10 trading-session positions
  (unchanged).
- Decay criterion for a lag `k` to **qualify**: `|ACF(k)| <= 2/sqrt(n_k)`
  (unchanged).
- **Minimum consecutive qualifying run, `R`**: a candidate `L` is only
  accepted if **every** lag from `L` through the current maximum examined
  lag qualifies **and** this run has length at least `R` trading-session
  positions (`current_max - L + 1 >= R`). **`R` must be at least 2 by
  construction** -- `R=1` would silently reproduce the exact
  isolated-terminal-lag loophole this correction exists to close. **The
  exact value of `R` beyond this minimal floor is left explicitly OPEN**
  -- no established, citable statistical convention pins down a single
  "correct" minimum run length for this specific application the way
  `+/-2/sqrt(n)` does for the per-lag band, and inventing a specific
  number (3? 5?) here merely to appear complete would violate the
  instruction not to do so. `R` must be set by reference to standard
  time-series persistence-testing practice once real data exists, not
  guessed now.
- **How an indeterminate lag within a candidate run is treated**: an
  indeterminate lag (Section 7B.3 -- `n_k` too small to evaluate)
  **breaks** a candidate run. It is never treated as if it qualified
  (that would be assuming unknown dependence is absent, an unjustified
  presumption) and never silently skipped over (that would let an
  unevaluated lag count toward satisfying `R` without actually having
  been checked). If an indeterminate lag falls inside the range that
  would otherwise be the candidate run, no run is established through
  that point, and the procedure must look to a longer, still-unbroken
  run reaching the current maximum, or conclude none exists within the
  examined range.
- **Deterministic extension rule**: if no qualifying run of length `>= R`
  reaching the current maximum exists within lags 1-10, extend the
  examined range to 1-20 and reapply the identical criterion (decay band,
  run-length `R`, indeterminate-lag handling) over the new range.
- **Maximum permitted lag: 20.** Extension stops there -- the range is
  not pushed to 30, 40, or beyond.
- **Explicit failure/INCONCLUSIVE condition**: if no qualifying run of
  length `>= R` reaching lag 20 is found, **or** if the implied number of
  usable blocks (total usable trading days divided by the resulting `L`)
  is too small for reliable block-bootstrap inference, report the study
  as power-INCONCLUSIVE. **The exact minimum usable-block count is also
  left OPEN** -- standard block-bootstrap methodological guidance, not an
  arbitrary number invented for this study, should set it once the real
  day-count and candidate `L` are known. **Neither contingency is
  resolved by shrinking `L` or `R` to manufacture a usable result.**
- **Take the larger of the two `L` values** obtained from series (a) and
  (b) as the single predeclared block length.
- **None of this rule is applied to actual data, and `R` is not chosen,
  in this task** -- the rule's structure is fully specified; its two
  pre-existing open sub-parameters (minimum `n_k` per lag, minimum usable
  block count) and this round's new third open sub-parameter (`R`) are
  all left for measurement time, not invented here, and `R`'s value is
  not selected by looking at the actual ACF (which has not been
  computed).

**5. Forbidden selection criteria, restated explicitly**: `L` is never
chosen based on the lead-lag coefficient `beta`, its p-value, its
significance, its effect size, or whichever block length happens to
produce a more favorable inference. Nothing about `beta`, `S_L(t)`, or the
effect-size hurdle is computed, or needs to be computed, before `L` is
fixed by the procedure above.

**6. On leaving three parameters open rather than inventing numbers.**
The decay band formula, the requirement that a run reach the current
maximum examined lag, the indeterminate-lag-breaks-a-run rule, the
extension rule, and the maximum lag (20) are all fully deterministic and
grounded in standard, pre-existing statistical convention or direct
logical necessity (Part 1 of this round's own correction). **Three
numerical sub-parameters are left genuinely OPEN**: the minimum `n_k` for
a lag to be evaluable; the minimum consecutive run length `R` (`>= 2` by
construction, exact value otherwise unset); and the minimum usable-block
count for reliable inference. Setting any of these now, before the real
post-exclusion day counts and candidate `L` are known, would require
either an arbitrary invented number or tuning against data this task is
not authorized to examine. All three must be set, with reference to
standard practice, at measurement time, before `L` is actually computed
-- not before, and not here.

### C. Inference hierarchy -- unchanged

Primary (once `L` is frozen by the procedure above): consecutive multi-day
block bootstrap. Sensitivity comparison: independent single-day-cluster
bootstrap. Supplementary only: continuous/overlapping sample. **The
choice between the block-bootstrap and single-day-cluster methods, as
primary vs. sensitivity, is not revisited after comparing which produces
a more favorable inference** -- the hierarchy (block-primary-once-frozen)
is fixed by this document now, subject to final human approval.

**Clearly distinguished**: the methodological direction (measure
hypothesis-predictor-free dependence first, from a controls-only baseline
and its square, over the true trading-day calendar, require a genuine
consecutive run before declaring decay, freeze `L` from that alone) is
this document's recommendation. **The numerical value of `L`, and the
three open sub-parameters named in B.6 (`n_k` minimum, run length `R`,
minimum block count), are not and cannot be determined here.**

---

## 8. Selection-null correction -- adopted [APPROVED]

Unchanged in substance from the prior revision; reproduced here in full
so this document remains self-contained. No changes requested in this
round.

**Correction**: for both B1 (per-month independent redraw) and B2 (fixed
rank-position rule), exclude the **entire drawn pseudo-leader set** for
that repetition and month from the benchmark used to construct that
repetition's own `S_L_random(t)`:

```
B_follower_pool_minus_pseudo(k) = (1/(n_F - n_leaders)) * sum_{j in real follower tier, j NOT in this repetition's drawn pseudo-leader set} r(j,k)
```

No other change to the existing B1/B2 randomization design is proposed
-- the disjoint candidate-pool fix already committed in `9f71b65`, the
1,000-repetition count, and the 95th-percentile two-sided comparison
convention are all unchanged, since no further incompatibility with
this correction has been identified.

**The approximate 15% benchmark-noise increase (`sqrt(160/120) ~= 1.15`)
is kept explicitly labeled as an unverified hypothesis, not a fact** --
it rests on an assumption of comparable idiosyncratic variance across the
drawn-pseudo-leader-adjacent names (ranks 41-120) and the deeper follower
names (ranks 121-200), which has not been checked.

**Empirical diagnostics required to compare real and randomized signal
construction** (none run here):

1. Compare the **realized variance** of the real `S_L(t)` series against
   the realized variance of `S_L_random(t)` (both B1 and B2), reporting
   the ratio directly, rather than relying on the `sqrt(n)` approximation.
2. Compare the **realized benchmark-pool sizes** actually used per
   month/repetition once real eligibility filtering (completeness gates,
   Section 3) is applied -- the idealized 160/120 figures may not hold
   exactly in practice.
3. Compare summary statistics (mean, sigma, within-day autocorrelation)
   of the real vs. null signal series side by side, as a basic
   comparability sanity check, **before** either is used in any gate
   decision.

**Comparability**: both the real signal and the corrected null signal are,
after this fix, the same *shape* of construction -- a group's portfolio
return minus a fully disjoint group's portfolio return, same window, same
procedure -- differing only in which names populate each side and the
benchmark-pool-size gap described above. This gap cannot be removed
without changing what the null tests. **No change beyond this specific,
targeted exclusion fix is proposed.**

**No null was run to produce this section.**

---

## 9. Economic threshold -- renamed an effect-size hurdle, not a cost or profitability claim

### Renamed, per this round's instruction

**The quantity `beta * sigma(S_L)` is a model-implied effect size for a
one-standard-deviation change in the signal, under the fitted regression
-- it is renamed an "effect-size hurdle" throughout this document,
replacing the prior "economic threshold"/"economic magnitude" language,
specifically because there is no trading rule, entry/exit model, position
sizing, turnover calculation, or execution model anywhere in this
proposal that would let it be interpreted as an achievable strategy
return.** `sigma(S_L)` remains the **observed** standard deviation of the
real `S_L(t)` series (a variance-only input).

### Positive-beta primary success rule -- unchanged, restated under the new name

The research hypothesis is a positive-propagation hypothesis. Adopted
accordingly [RECOMMENDED, human approval required]:

1. **The primary success condition requires `beta > 0`.**
2. **The effect-size-hurdle comparison (`beta * sigma(S_L)` against 20bps)
   is evaluated only when `beta` is positive.**
3. **A statistically significant negative `beta` is reported as contrary
   evidence against the propagation hypothesis, not as a successful
   result under a different label.**
4. **Absolute magnitude is never used to convert a negative effect into
   a pass.**
5. **The 20bps value is retained provisionally, but is explicitly not a
   validated transaction-cost estimate and does not establish net
   profitability or tradability.** Any later trading-cost comparison
   requires a **separate** execution/turnover model (basket-level fills,
   slippage, market impact across simultaneously-held positions) that
   does not exist anywhere in this proposal and is not authorized or
   attempted here.

**Human approval status unchanged**: RECOMMENDED, not approved (Decision
15, now reflecting the renamed terminology).

**STATUS UPDATE (2026-11-14)**: Decision 15 is now **APPROVED**, by
explicit user decision, exactly as recommended in items 1-5 above, with
one precision addition not previously stated explicitly: item 2's
comparison (`beta * sigma(S_L)` against 20bps) is **strictly greater
than** 20bps -- equality does not pass. Items 1, 3, 4, and 5 above are
approved verbatim, unchanged. See
`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 8 LOG for the full record and
decision-table row 15 below for the current, consolidated statement of
the rule. The "RECOMMENDED, not approved" sentence immediately above is
preserved unedited as the accurate historical record of this section's
status before 2026-11-14.

---

## 10. Trial ledger and multiplicity -- configuration count re-examined: three found to double-count the estimand, revised to two

### Re-reading the ledger and the trial definition for this round

`PROJECT_CONTEXT.md` lines 138-142, quoted exactly (re-read again):

> **Trial, defined**: any configuration that reached a pre-registered
> gate OR was killed at a Phase 1 feasibility check. Both carry selection
> pressure. A configuration blocked before either (never run, no gate
> reached, not Phase-1-killed -- e.g. Swing's own V5/V6, blocked by Bug
> #12) is not a trial under this definition.

`lead_lag/trial_ledger.json` re-read again: six entries. **The existing
precedent most relevant to this round's question is the family's own
`grouping:liquidity_tier` / `grouping:statistical_cluster` pair**: two
*genuinely alternative*, both-empirically-examined grouping mechanisms
received **two separate entries**, even though only one was adopted --
contrasted with the **five correlation-threshold cuts** examined within
the statistical-cluster mechanism, which received **zero additional
entries**, because they were "one configuration sliced five ways for
description," never independently gated or independently adopted/rejected.

### Applying this precedent to the questions this round asks

- **Are Option 1 and Option 2 (Part 1/Section 3) distinct configurations?**
  **Yes.** They are two genuinely alternative, both-to-be-empirically-examined
  basket-construction methodologies, directly analogous to the
  grouping-mechanism pair -- not a single configuration with a tunable
  parameter. **Recommendation: two separate entries.**
- **Are different completeness-threshold *values* within Option 2 (e.g.
  90% vs. 95% vs. 99%, explored to visualize an exclusion-rate tradeoff
  curve) separate configurations?** **No**, by the correlation-threshold-cuts
  precedent -- provided they are examined descriptively, to inform
  **one** final choice of threshold, and are not each independently
  gated or independently adopted as a final methodology. If, contrary to
  that, a specific threshold value were separately carried all the way to
  its own adoption decision, it would need its own entry at that point --
  but the exploratory sweep itself does not.
- **Are different horizon-specific completeness policies separate
  configurations?** **No**, by the same logic -- calibrating a threshold
  separately per horizon, feeding the **already-registered** horizon
  entries (#3-6), is a measurement/calibration detail of those existing
  trials, not a new trial in its own right.
- **Does a diagnostic-only measurement that cannot independently pass or
  kill a configuration count as a trial?** **No** -- the definition's own
  language ("killed at a Phase 1 feasibility check") implies the check
  must be *capable* of killing the configuration to carry selection
  pressure. A purely descriptive measurement with no attached decision
  rule would not qualify. **The proposed Section 3D/Section 7 work is
  not purely descriptive** -- it has an explicit decision rule attached
  (the margin-ratio rule from the prior preregistration amendment:
  `>=5x` proceed, `1-5x` inconclusive, `<1x` abandon), so it **does**
  carry real selection pressure and does qualify.

### Re-examining whether the estimand itself is a separately gateable configuration [this round's correction]

**Can `estimand:portfolio_level_response`, standing alone, ever itself
"reach a pre-registered gate" or be "killed at a Phase 1 feasibility
check," independent of a basket-construction choice? No.** The estimand
(`Y(t,h) = alpha + beta*S_L(t) + ...`) cannot be computed, let alone
gated or killed, without first fixing some basket construction (Option 1
or Option 2) to actually produce `R_F(t)`, `Y(t,h)`, and `S_L(t)` from
real data. There is no "bare" examination of the estimand that does not
pass through one of the two basket constructions.

**This means the prior revision's three-entry recommendation
double-counted the estimand.** It is accurately described as "an
estimand definition shared by multiple configurations" -- a category this
project's own trial definition does not independently count -- not itself
"a genuinely alternative basket construction," which *is* independently
countable, per the grouping-mechanism precedent. The distinction the task
draws (estimand shared by multiple configurations / genuinely alternative
basket construction / descriptive measurement / threshold-or-horizon
parameter variation / a configuration that independently reaches a gate
or is killed) places the shared estimand in the **first** category, not
the fourth.

### Current recorded ledger count vs. proposed configurations -- distinguished explicitly this round

**A real conflation in the prior wording is corrected here.** "Denominator
becomes 8" could be read as asserting 8 is already the project's actual
trial count. **It is not.** Three different things, kept separate from
this point on:

- **Current recorded ledger count**: **six**, exactly as reported from
  `lead_lag/trial_ledger.json` (re-read directly for this revision,
  unchanged content). **No claim anywhere in this document asserts the
  two basket-construction configurations are already recorded trials --
  they are not.** Neither has been registered, examined, or shown to
  have reached a gate or a Phase 1 kill.
- **Proposed configurations (prospective, not yet registered or
  examined)**:
  1. `basket_construction:option1_full_completeness` -- Section 3C's
     Option 1.
  2. `basket_construction:option2_frozen_subset_fallback` -- Section 3C's
     corrected Option 2.
  Both are **proposals written down in this document**, nothing more at
  this stage. Writing a configuration down does not make it a trial.
  **If the human reviewer approves this step**, both must be registered
  in `lead_lag/trial_ledger.json` **before** the first qualifying
  empirical examination (Section 3D, Section 7) -- not after, and not
  merely because this document names them.
- **Conditional prospective total**: **eight** is the anticipated total
  **only if** both proposed configurations are subsequently approved,
  registered, and then actually satisfy the project's existing trial
  definition (reach a preregistered gate, or are killed at a Phase 1
  feasibility check -- unchanged, not loosened). **Eight is not described
  anywhere in this document as the current actual trial count.** It is a
  forward-looking, conditional figure, contingent on steps that have not
  happened.

**Residual ambiguity, stated rather than hidden**: even granting the
conditional total of eight, this reasoning treats "the portfolio-level
estimand" as a shared parent definition and "which basket construction
computes it" as the actual unit that would reach a gate. This is
consistent with the project's own stated trial definition and its own
grouping-mechanism precedent, but it is **this document's own
interpretation** for a case not phrased identically anywhere in
`PROJECT_CONTEXT.md` or the ledger itself. **If the human reviewer judges
that the shift from the old, degenerate per-follower estimand to the new
portfolio-level estimand warrants its own historical ledger marker** (not
a counted trial, a documentation anchor), **that is an additional,
separate decision this document does not make.**

### The four distinct stages, restated

1. **The old algebraic design-review catch** -- not a trial (Swing
   V5/V6 / Bug #12 precedent). No ledger entry.
2. **The two proposed basket-construction configurations** -- exist now
   only as proposed specifications in this document, not registered, not
   examined. (The shared estimand itself is not a third stage-2 entity,
   per the re-examination above.)
3. **The first empirical feasibility examination** (Section 3D, Section
   7) -- not yet run. **Registration of both proposed configurations, if
   approved, must happen before this step begins** -- registration is
   itself a prerequisite for a configuration to even become examinable,
   let alone qualify as a trial.
4. **The first primary gate** -- further downstream, contingent on stage
   3.

### Trial count, multiplicity family, and alpha allocation are three separate concepts

**The conditional "eight" above answers only the first of three distinct
questions, and this document does not conflate them.**

**A. Project trial count** -- **currently six**, per the recorded ledger;
**conditionally eight** if both proposed configurations are approved,
registered, and subsequently qualify under the existing definition
(reached a gate, or killed at Phase 1) -- not merely because they have
been written down in this proposal. This is a counting exercise, not a
statement about how significance is corrected.

**B. Multiplicity-adjustment family** -- the set of configurations whose
results are *jointly* protected by one shared family-wise error
allocation. **This is a separate question from A, and this document does
not assume every project trial automatically belongs to the same
multiplicity family.** A genuine case for treating the two
basket-construction configurations as **outside** the family that
protects the actual propagation-hypothesis tests (the existing 6: 2
grouping mechanisms + 4 horizons) can be made: unlike the grouping-mechanism choice (which represents two competing
*economic* hypotheses about what "leader" means, each independently
capable of showing or failing to show real propagation), Option 1 and
Option 2 are not competing scientific hypotheses about propagation at
all -- both attempt to compute the *same* `S_L(t)`/`Y(t,h)` as faithfully
as possible under real-world data limitations. Under this reading, the
basket-construction decision is a **data-construction methodology choice
resolved before the propagation hypothesis is tested at all** (on
grounds of exclusion rate and measured return-distortion risk, Section
3D -- not on any p-value or significance criterion), analogous to other
pre-hypothesis choices in this family (the exact gap-fill rule, the exact
completeness-threshold value) that were never themselves given their own
alpha allocation. **A competing, equally defensible reading** is that
because both configurations are independently gateable "trials" under the
project's own definition (category A), they should join the same family
as the existing 6 by the letter of this family's own grouping-mechanism
precedent, regardless of whether they represent competing economic
hypotheses or competing data-handling methodologies.

**Neither reading is adopted here. `PROJECT_CONTEXT.md` and
`lead_lag/trial_ledger.json`, re-read for this round, do not settle which
reading governs a case shaped like this one** (an estimand with two
competing *lower-level construction* methodologies, as opposed to two
competing *groupings*) -- **multiplicity-family membership for the two
basket-construction configurations is therefore left explicitly OPEN.**

**C. Alpha allocation** -- the actual alpha assigned to the primary gate,
derived from B once B is resolved. **The existing, committed `alpha =
0.05/6` (Section 15 of `9f71b65`) is unchanged by this proposal and is
not silently replaced with `0.05/8` anywhere in this document.** If
reading B's second option (basket construction joins the main family)
is eventually adopted, the operative alpha for the propagation-hypothesis
test becomes `0.05/8`; if the first option (basket construction sits
outside the family) is adopted, it remains `0.05/6`. **This document
does not declare either operative** -- that is a human decision, not
resolved by project documentation alone.

**What must be decided before any primary gate is run**: (i) whether the
two basket-construction configurations join the propagation-hypothesis
multiplicity family or sit outside it as a resolved pre-hypothesis
methodology choice; (ii) the resulting operative alpha (`0.05/6` or
`0.05/8`) for the primary gate; (iii) this decision, once made, must be
recorded in whatever eventual preregistration amendment adopts this
proposal, so it cannot be silently revisited after an outcome is known.

**No edit to `trial_ledger.json` was made. The existing `alpha` value
(`0.05/6`) was not changed anywhere in this document. The two proposed
configurations were not registered.** This remains a human decision
(Decision 16, revised again in Revision 6 to distinguish the current
recorded count (6) from the proposed configurations (2) and the
conditional prospective total (8)). **Do not retroactively register
configurations, and do not count the shared estimand as an independent
trial without the reasoning given above.**

**SUPERSEDED (2026-11-14): this OPEN position is historical, not
current.** Everything above, from "A. Project trial count" through this
point, describes Decision 16 as it stood at Revision 6 -- genuinely
unresolved at the time, and not rewritten here as though it had already
been settled. **Decision 16 has since been approved**: Option 1 is a
formal trial (an unregistered Phase 1 feasibility kill); Option 2 is not
a formal trial; both are included in the multiplicity family. **Formal
trial count: 7. Multiplicity-family denominator: 8. Prospective
primary-gate alpha: `0.05/8 = 0.00625`** (not yet operative -- it becomes
operative only once the drafted, uncommitted AMENDMENT 3 LOG in
`PREREGISTRATION_LEAD_LAG_V1.md` is committed). The six-entry
`lead_lag/trial_ledger.json` is unchanged; neither configuration was
retroactively registered. See the opening supersession note and
`lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md` for the full
accounting. This paragraph is the only part of Section 10 that reflects
current status; the reasoning above it remains as an accurate record of
how that status was reached.

---

## 11. Revised human decision table

All 21 prior rows preserved; no new rows added this round (every issue
raised fits inside an existing row, per instruction not to duplicate).

**UPDATE (2026-11-14)**: row 13's status is updated to **APPROVED** (user
decision, not a this-round methodology-review change), and **one new row,
22, is added** recording a proposed, not-yet-approved `Momentum_F(t)`
same-session rule found while auditing Decision 13's consequences. See
`lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md` for the full
record. The sentence above describes the state of the table before this
update and is retained for provenance, not corrected.

**FURTHER UPDATE (2026-11-14, same day, following this update)**: rows 10
and 22 are each updated from OPEN to **APPROVED** by further explicit user
decision -- 70% follower-breadth floor (row 10), and the `Momentum_F(t)`
same-session rule (row 22), the latter with a refined exclusion wording
specifying exclusion from the primary regression sample.

**CORRECTION (2026-11-14, same day, following the update immediately
above)**: this update originally also claimed row 11 (`09:15` as the sole
first-bar anchor, Decision 11) moved to APPROVED. **That claim was
incorrect and is retracted -- Decision 11 was never approved by the user
and remains OPEN.** Row 11 is restored to its original status below. See
`lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md` (updated by
this same task) for the full corrected record.

**FURTHER UPDATE (2026-11-14, same day, documentation-correction task)**:
row 19 (Option 1 vs. Option 2 basket-construction selection) is updated
from OPEN to **SELECTION RESOLVED** -- this is not a new approval made
here; it is the existing human decision record already present in
`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3 (Option 2
"examined before registration and subsequently selected... by human
decision"), which this proposal's own Section 3C text had not yet been
updated to reflect. **This does not resolve Option 2's own internal
threshold form/value, nor whether Decision 10's `70%` figure is the
value intended for it -- both remain separately OPEN.** See Section 3C's
own dated supersession note for the full record.

| # | Decision | Status | Recommended option | Alternatives | Reasoning | Approval required? | Freeze point |
|---|---|---|---|---|---|---|---|
| 1 | Option A (portfolio-level estimand) as primary | **APPROVED** | `Y(t,h)`/`S_L(t)`/`R_F(t)`, Sections 1,4 | Old per-follower spec | Section 1's derivation | Already approved | Before data analysis |
| 2 | Drop old individual-follower specification from this study | **APPROVED** | Yes, future study if pursued | Run alongside (rejected) | No executed trial to preserve | Already approved | Before data analysis |
| 3 | Correct B1/B2 pseudo-leader benchmark self-inclusion | **APPROVED** | Group-exclusion fix, Section 8 | Leave uncorrected (rejected) | Mechanical self-inclusion demonstrated | Already approved | Before data analysis |
| 4 | Non-overlapping as primary inference sample | **APPROVED** | Section 5's `h+5` schedule | Continuous as sole/co-primary (rejected) | Ambiguous-dual-primary risk removed | Already approved | Before data analysis |
| 5 | Continuous/overlapping as supplementary | **APPROVED** | Cross-check only | Omit; co-primary (both rejected) | Still useful as robustness | Already approved | Before data analysis |
| 6 | Follower-side breadth + fresh power work before the primary gate | **APPROVED** | Required, Sections 3D, 7 | Skip (rejected) | Repeats this family's own established discipline | Already approved | Before the primary gate |
| 7 | Final control set | **APPROVED, 2026-11-14** (historical status at drafting, preserved: "OPEN") | `R_F(t)` + `TOD(t)` + `Momentum_F(t)` primary (required, part of the base estimand); trailing realized volatility, coarse trading activity (diagnostic only), and prior-day NIFTY50 (governed by Decision 9) are sensitivity/diagnostic-only, never primary | Any other subset (superseded -- this subset adopted) | Redundancy check done; no independent market factor exists | No -- already approved | Prospective, Phase 4 implementation |
| 8 | Exact fixed-effects specification | **APPROVED, 2026-11-14** (historical status at drafting, preserved: "OPEN") | Primary: **no fixed effects**. Sensitivity: **year FE** only. No quarter FE. Year FE must never replace the no-FE primary | Quarter FE (rejected); year FE as sole primary (rejected -- would risk invisibly absorbing a genuinely slow real effect) | Fewer parameters; avoids absorbing a real slow effect if sole primary | No -- already approved | Prospective, Phase 4 implementation |
| 9 | Prior-day NIFTY50 regime control: include? | **APPROVED, 2026-11-14** (historical status at drafting, preserved: "OPEN") | **Omitted from the primary regression.** May be included as a **sensitivity-only** control, explicitly labeled a coarse daily-regime proxy; prior trading day's close-to-close return only -- never the same-day close | Treating it as an intraday benchmark, independent intraday market factor, or market-adjusted control (rejected); using the same-day close (rejected -- look-ahead) | No intraday index exists -- this limitation is unchanged and not resolved by this approval | No -- already approved | Prospective, Phase 4 implementation |
| 10 | Follower-side completeness **threshold value and form** | **APPROVED, 2026-11-14 -- frozen at 70%** (historical status at drafting, preserved: "OPEN") | **70%** of the follower tier, present-valid observations only (forward-filled/absent bars excluded, mirroring the leader-side `n_t_breadth` convention); `n_t_return` for actual return construction governed unchanged by Decision 17; calendar denominator is the existing 2,457-date governing calendar, holiday-verification methodology unmodified | Count-based form; any other percentage (both superseded by this approval) | User decision, 2026-11-14; see `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 5 LOG Section 1 | No -- already approved | Prospective, Phase 4 implementation |
| 11 | Non-overlapping sampling **anchor and schedule** | **APPROVED, 2026-11-14 (later same day) -- Decision 11 resolved to `09:15`**, by explicit user decision following a final targeted first-bar verification report (`>99%` archive-wide presence/validity at `09:15`, a dated `2020-11-23`-to-`2020-11-27` archive-coverage episode and three special/truncated dates found and attributed to existing eligibility machinery, not session-definition ambiguity). See `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 6 LOG for the full record. **This genuine approval must not be confused with the earlier, retracted claim it supersedes, preserved here unchanged as historical record**: *(historical, preserved)* "**OPEN** (hierarchy approved; exact anchor not) -- **CORRECTED, 2026-11-14, same day**: this row was briefly, incorrectly marked 'APPROVED -- `09:15` confirmed' earlier in this working tree; that was never approved by the user and is retracted. Decision 11 remains genuinely OPEN." | **`09:20`** (signal-end minute `t=09:19`), unconditionally -- `09:15` confirmed as the first valid regular-session bar; `09:16`/`09:21` not adopted. *(Historical, preserved: "`09:20` if `09:15` is a valid regular-session bar (evidenced, not confirmed); `09:21` otherwise -- confirm via a targeted `MIN(ts)` check.")* | Any other deterministic clock-time anchor; separate anchors per horizon (both superseded by this approval) | Session-boundary mechanics plus the now-verified `ts`=bar-start convention, confirmed by the final targeted first-bar verification report -- not outcome-based | No -- already approved | Prospective, Phase 4 implementation |
| 12 | Bootstrap block length `L`, run-length `R`, series, and switch-over rule | **OPEN** (deterministic lag-decay/consecutive-run/extension/max-lag rule now fully specified; `L`, `R`, and two further numerical sub-parameters remain open) | Measure ACF of **hypothesis-predictor-free** (not outcome-independent -- residuals still contain `Y(t,h)`) controls-only baseline residuals AND their squares, using pairwise-valid `n_k` at each true trading-session lag; require a genuine consecutive qualifying run of length `>=R` reaching the current maximum lag (not an isolated terminal lag) before declaring decay; predeclare `L` as the larger of the two series' smallest such run (Section 7B) | Single-day clustering only, unchecked (rejected); raw-return-only ACF (rejected); describing the diagnostic as outcome-independent (rejected -- corrected terminology); one fixed `n_days` band for every lag (rejected); compressed-sequence lag counting (rejected); accepting an isolated terminal qualifying lag as evidence of decay (rejected this round as a real flaw) | Residuals still contain `Y(t,h)`; a single qualifying lag at the edge of the examined range is not evidence of decay; `R>=2` by construction, exact value left to standard practice | Yes | Before the primary gate |
| 13 | Return convention adoption (exact endpoint-price method) | **APPROVED, 2026-11-14** (historical status at drafting, preserved: "OPEN -- technically recommended, not approved") | Section 4 construction, applied consistently to `R_L`, `R_F`, `Y`, `Momentum_F` | Keep original sum-of-per-bar convention for the leader side only (rejected -- internal inconsistency) | Exactness; avoids Jensen's-gap error | No -- already approved | Prospective, Phase 4 implementation |
| 14 | `bars_1min` adjustment status (raw vs. adjusted) | **APPROVED, 2026-11-14 -- MIXED CONVENTION** (historical status at drafting, preserved: "OPEN (schema-level evidence found, not a full confirmation)") | `bars_1min` is back-adjusted for split/bonus actions, piecewise, at 103/104 tested events; `prices_eod` remains raw; 28 action-less Angel-side breaks and the TATASTEEL 2022-07-28 misplaced boundary are documented, not explained; vendor mechanism unverified; same-session returns usable without reconstruction, conditional on Phase 4 asserting the same-`trade_date` guarantee in code; zero within-session mixed-scale defects found across 208 tested sessions/77,654 bars (a tested-population finding, not a universal guarantee) | Assume raw and proceed without checking (superseded -- refuted by 103/104 exact-ratio agreement); assume fully/uniformly adjusted (rejected -- 28 action-less breaks and 1 misplaced boundary show incompleteness) | `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md` Sections 6-9 (the resolving decision record); `lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` SS5.5 | No -- already approved | Prospective, Phase 4 implementation |
| 15 | 20bps **effect-size hurdle** interpretation and sign rule | **APPROVED, 2026-11-14**, by explicit user decision (historical status at drafting, preserved: "OPEN (specific rule recommended, Section 9)") | `beta > 0` required for a pass; `beta * sigma(S_L) > 20bps` **strictly** (equality does not pass -- precision added at approval, not previously stated explicitly); negative or non-positive `beta` = contrary evidence, never flipped via `\|beta\|`/`abs(beta)`; renamed "effect-size hurdle," explicitly not a validated transaction-cost or profitability claim; statistical significance test unchanged (two-sided `alpha=0.00625`, day-clustered SE, 60-minute primary horizon, Decision 16) | Magnitude-only rule regardless of sign (rejected); calling it a validated cost hurdle (rejected this round as unsupported); equality at 20bps counting as a pass (rejected at approval -- strict inequality only) | Matches the stated positive-propagation hypothesis; no execution/turnover model exists to support a profitability claim; `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 8 LOG (the resolving decision record) | No -- already approved | Prospective, Phase 4 implementation |
| 16 | Trial-ledger entries: current count, formal trial count, multiplicity-family denominator, and alpha allocation | **CLOSED / APPROVED (2026-11-14, Decision 16)** -- superseding the Revision 6 `OPEN` status recorded in the "Recommended option" column, which is preserved below as historical record, not restated as current | **Historical (Revision 6, preserved)**: *current recorded count: 6, per `lead_lag/trial_ledger.json`, re-verified, unchanged -- the 2 basket-construction configurations are **not** already recorded trials. Proposed configurations: `basket_construction:option1_full_completeness` and `basket_construction:option2_frozen_subset_fallback`, to be registered before the Section 3D/7 work begins, if approved. Conditional prospective total: 8, only if both are approved, registered, and subsequently satisfy the existing trial definition -- not merely because they are written down. Multiplicity family (OPEN): whether the 2 proposed configurations, if they become trials, join the same family as the existing 6 (operative alpha `0.05/8`) or sit outside it (operative alpha stays `0.05/6`) is not settled by project documentation. Alpha (unchanged): the committed `0.05/6` is not altered anywhere in this document.* **Current, post-Decision-16 (2026-11-14)**: six-entry ledger unchanged; **Option 1 is a formal trial** (unregistered Phase 1 feasibility kill); **Option 2 is not a formal trial**; both are included in the multiplicity family. **Formal trial count: 7. Multiplicity-family denominator: 8. Prospective primary-gate alpha: `0.05/8 = 0.00625`** (not yet operative -- becomes operative only once the drafted, uncommitted AMENDMENT 3 LOG in `PREREGISTRATION_LEAD_LAG_V1.md` is committed). No retroactive ledger registration occurred; `trial_ledger.json` still has exactly 6 entries. See `lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md` for full accounting. | Describing 8 as the current ledger-registered trial count (still rejected -- the ledger itself remains at 6; 8 is the multiplicity-family denominator, 7 is the formal trial count, and neither equals the ledger's own count); registering either configuration retroactively (not done; not authorized) | Section 10 (historical reasoning, annotated, not rewritten); current count, formal trial count, multiplicity-family denominator, and alpha allocation are four concepts that must not be conflated | No -- approved | Amendment 3 (multiplicity/alpha) drafted 2026-11-14, **not yet committed**; must be committed before the primary gate runs. This row's approval does **not** itself authorize the primary gate. |
| 17 | Missing-data / stale-price compatibility | **APPROVED, 2026-11-14** (historical status at drafting, preserved: "OPEN (ambiguity sharpened, not resolved)") | **PRESENT-VALID** = positive-volume structurally-valid (D) OR zero-volume OHLC-flat (A1, settled). **FUNCTIONALLY ABSENT** (for gap-length classification only) = true absent timestamp, OR zero-volume OHLC-non-flat (B1, settled), OR structurally invalid (E). Exact-duration gap threshold (C, settled): `<180`s forward-filled, `>=180`s excluded. D (positive-volume valid, incl. extreme values, no invented cutoff) and E (structurally invalid: `high<low`; `open`/`close` outside `[low,high]`; any OHLC null/non-finite/`<=0`; `volume<0` -- own values never used, own timestamp never repaired/forward-filled) newly approved. Applied identically at `t-35,t-5,t`; Stage A's short-gap rule never applies to Stage B's `t+h` zero-tolerance check | Assume the existing rule already covers all four cases (superseded -- now explicitly distinguished and resolved); inventing a positive-volume outlier cutoff (rejected -- unjustified, no principled value derivable); allowing Stage A's short-gap rule to apply at `t+h` (rejected -- would weaken Stage B's zero-tolerance rule) | Section 4D; `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md` Sections 4-7 (the resolving decision record); `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 10 LOG | No -- already approved | Prospective, Phase 4 implementation |
| 18 | Fixed monthly roster identity (no dynamic add/remove/replace) | **APPROVED, 2026-11-14** (historical status at drafting, preserved: "RECOMMENDED") | Roster membership determined solely by tier assignment, never by signal-time price availability; no additions, removals, or replacements based on signal-time availability; no dynamically filtered or reconstituted basket during the month | Availability-filtered basket per observation (rejected) | Section 3A; availability-dependent composition is a selection effect, not a measurement choice | No -- already approved | Prospective, Phase 4 implementation |
| 19 | Option 1 (100% completeness) vs. corrected Option 2 (frozen-subset-with-residual-variability fallback) | **SELECTION RESOLVED, 2026-11-14** — Option 2 selected; Option 1 not selected. Per `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3: Option 2 "was examined before registration and subsequently selected as the basket-construction methodology by human decision" (not a predictive-gate pass, not a formal trial). (Historical status at drafting, preserved: "**OPEN** (this round adds the constituent-selection-vs-observation-inclusion distinction and the exact breadth-threshold location)".) **FURTHER STATUS UPDATE, 2026-11-14 (later, same day, following a consolidated methodology review)**: the threshold sub-question this row previously left separately OPEN is now **APPROVED**: `|frozen_subset(t,side)| / n_roster_tier(month,side) >= 0.70`, applied separately per side, at step 4 (after freezing, before computation, before Stage B). **The `0.70` value and the original-roster-tier denominator are newly approved choices for this specific purpose -- not inherited from, or justified by, Decision 10's separate per-minute follower-breadth approval.** *(Historical, preserved: "Separately and explicitly still OPEN, not resolved by this selection: Option 2's own minimum-breadth threshold form (count/fraction/both), its value, and whether Decision 10's 70% figure is the value intended for it.")* See `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 9 LOG, Section 2, and `lead_lag/PRE_SIGNAL_VS_FORWARD_ENDPOINT_RECONCILIATION.md` for the full record. | Option 2 (Section 3C, 9-step ordered construction with the breadth threshold applied at a precisely specified step) is now the selected construction, not a fallback. **Both Option 1 and Option 2 retain observation-inclusion (informative-censoring) dependence on `t+h`; Option 2's selection does not remove this** | The prior, vaguer "reweight among survivors" Option 2 (withdrawn); believing either option eliminates all future-dependent sample selection (rejected -- only constituent-selection bias is eliminated, not observation-inclusion bias); believing selection of Option 2 also fixes its threshold form/value (rejected -- a separate, still-open question) | Section 3C; `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3 (the resolving decision record); AMENDMENT 9 LOG, Section 2 (the threshold's own resolving decision record) | No — selection already resolved (existing human decision record). **No -- threshold form/value also now approved** (historical: "Yes, still required for Option 2's own threshold form/value") | Selection: already in effect. Threshold form/value: **also already approved** (historical: "before data analysis") -- prospective, Phase 4 implementation |
| 20 | Corporate-action handling under portfolio aggregation | **APPROVED, 2026-11-14** (historical status at drafting, preserved: "OPEN (this round separates project-code, exchange-mechanism, and intraday-data evidence; the exchange-mechanism claim is walked back from asserted to unverified)") | **(ii) adopted**: the existing single-entity `+/-1`-day exclusion is retained unchanged, applied as a Stage A eligibility condition at `t-35`, `t-5`, `t`, before freezing -- folded into the unified completeness framework, not a standalone whole-day filter. Approved on the strength of Decision 14's direct empirical finding (zero within-session mixed-scale defects, 208 tested sessions) -- **not** on any confirmed exchange mechanism, which remains unverified | (i) no special intraday exclusion at all (rejected -- discards a cheap safeguard against unrecorded-action/non-tested-population risk for no benefit); asserting NSE's adjustment-timing mechanism as established fact without a verified authoritative source (rejected -- walked back, unchanged by this approval) | Section 4C; `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md` Section 7 (the category-3 verification Section 4C called for); no authoritative NSE source verified -- category 2 remains open as a permanent limitation, not a blocker | No -- already approved | Prospective, Phase 4 implementation |
| 21 | Special/irregular trading sessions (early close, Muhurat, etc.) | **APPROVED, 2026-11-14** (historical status at drafting, preserved: "OPEN, unverified") | The 4 verified weekend special sessions (`2020-02-01`, `2024-01-20`, `2025-02-01`, `2026-02-01`) are **included**, under the unmodified `09:15`/`09:20`/`15:29` session convention; the 11 already-verified non-session dates remain **excluded**, unchanged; `2021-02-24` is **conservatively excluded** from the primary sample (unresolved identity plus a newly found internal inconsistency in `lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md`'s own in-window-coverage statements for that date). **Primary-sample calendar: 2,456 dates** (the governing 2,457-date calendar, unchanged and still authoritative for prior measurements, less `2021-02-24`) | Assume already handled (superseded -- now explicitly verified and handled); force `2021-02-24` into "normal" (rejected -- its own source document disagrees with itself); exclude all weekend specials as a blanket precaution (rejected -- all 4 independently verified as structurally normal) | `lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md` Sections 3, 4.1, 7 (the resolving evidence, including the internal-inconsistency finding); `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 9 LOG, Section 4 | No -- already approved | Prospective, Phase 4 implementation |
| 22 | `Momentum_F(t)` same-session endpoint eligibility and minimum anchor (row added 2026-11-14, found while auditing Decision 13's consequences) | **APPROVED, 2026-11-14** (historical status at proposal, preserved: "OPEN, PROPOSED 2026-11-14 -- NOT YET APPROVED"). **The same-session exclusion rule itself (columns to the right) remains approved and unchanged.** *(Historical correction, preserved)*: "CORRECTED, same day: this cell previously claimed the minimum anchor was 'now unconditional given Decision 11's approval at `09:15`.' Decision 11 was never approved and remains OPEN -- that claim is retracted; the anchor is conditional, as restored below." **FURTHER STATUS UPDATE, 2026-11-14 (later same day)**: Decision 11 has since been genuinely approved at `09:15` -- see `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 6 LOG. The minimum anchor is therefore now **unconditionally `t>=09:50`**, by a real approval (unlike the earlier, retracted claim this cell corrects, which asserted the same conclusion without any actual user decision) | Both `Momentum_F(t)` endpoints (`t-35`, `t-5`) must be valid, same-trading-session, same-trade-date observations, each satisfying Decision 17's endpoint-validity rules; no cross-session pairing; no previous-session fallback, nearest-bar substitution, clamping, or padding; if either endpoint is unavailable/invalid, `Momentum_F(t)` is unavailable and the observation is **excluded from the primary regression sample -- no null-control observation retained, no imputation, no substitution** (refined exclusion wording, approved 2026-11-14). **Minimum anchor: `t>=09:50`, unconditionally** -- `09:15` confirmed as the first valid regular-session bar (Decision 11, APPROVED). *(Historical, preserved: "conditional on Decision 11 (OPEN, not resolved): `t>=09:50` if `09:15` is the first valid regular-session bar (`t-35>=09:15`); `t>=09:51` if `09:16` is first valid instead (`t-35>=09:16`) -- lower bounds only in either branch, never a guarantee of a complete basket at that time, and neither branch is chosen until Decision 11 is resolved.")* This remains a lower bound only -- never a guarantee of a complete basket at that time; validity and exclusion continue to be governed by rules 1-2 and 5-6 (this cell, columns to the left) | Silent fallback to the previous session's nearest available bar (rejected -- would pair a `Momentum_F` endpoint across a session boundary); treating the existing `09:19`/`09:20` signal-only anchor as also sufficient for `Momentum_F` (rejected -- arithmetically incompatible); retaining a null-control placeholder instead of exclusion (rejected -- explicit refinement added at approval) | `lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` Section 5.3 found the documented earliest signal anchor requires a `Momentum_F` start endpoint before session open, which does not exist in `bars_1min`; this row adopts an exclusion-based resolution, not a substitution-based one | No -- already approved (the exclusion rule); Decision 11 is now also approved (row 11 above), fixing the anchor unconditionally | Prospective, Phase 4 implementation |
| 23 | Monthly roster turnover-ranking effective-time / ranking-date inclusivity (row added 2026-11-14, found while auditing Option 2's Stage-A threshold prerequisites) | **APPROVED, 2026-11-14**, by explicit user decision following review of `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` | **Convention A (prior-session cutoff)**: each entity's trailing-60-session median `prices_eod.turnover` uses only observations with `trade_date < ranking_date`; the ranking date's own turnover is excluded; no imputation, forward-filling, or substitute observation of any kind. The roster is frozen using data available as of the close of the trading session immediately preceding the ranking date, and becomes effective from the first trading session of the ranking date itself -- available before that date's `09:20` signal (Decision 11) | **Convention B (ranking-date-inclusive cutoff)** -- rejected: requires the ranking date's own end-of-day turnover, which does not exist until that date's session closes; using it at that date's own `09:20` signal would be a look-ahead. A same-session-excluded variant of Convention B (roster effective only from the next trading session) would be point-in-time valid but is a materially different rule from "formed on the first trading day of each month" and was not what was approved | `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md`, Sections 1-5; the 47/120-month (39.2%) entity-level tier-reassignment comparison between conventions is **supporting evidence only, not the basis of this approval** -- the approval rests on point-in-time validity (Section 2 of that audit: `prices_eod.turnover` is an end-of-day aggregate, unavailable at the ranking date's own open), not on the magnitude of the membership difference. **This decision does not change the annual top-200 universe construction** (`src/fibo/universe.py`, verified unaffected in the cited audit, Section 3.7) **and does not resolve the separate `prices_eod`-vs-`bars_1min` first-trading-day calendar discrepancy found in the same audit (Section 4.1) -- that remains open, folded into Decision 21's existing scope, not separately approved or resolved here.** *(SUPERSEDED IN PART, 2026-11-14, later same day: this calendar discrepancy has since been resolved as decision item 24 below -- the governing exchange-session calendar, not raw presence in either table, determines ranking dates. This sentence is preserved unedited as the accurate historical record of this row's status before that resolution.)* It also does not touch Option 2's own Stage-A threshold form, value, or denominator, nor its relationship to Decision 10's 70% figure -- both remain separately OPEN (row 19) -- and does not alter the Stage-A/Stage-B distinction or Stage-B's zero-tolerance forward-endpoint rule (Section 3C) in any way | No -- already approved | Prospective, Phase 4 implementation |
| 24 | Monthly roster ranking-date calendar source (row added 2026-11-14, found as a byproduct of Decision 23's own audit) | **APPROVED, 2026-11-14**, by explicit user decision following review of `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` Section 4.1 | **The governing exchange-session calendar** (the same calendar already approved for Decision 10/21: `nse_holidays.py` plus explicit special-session verification) **determines each month's first trading session for ranking purposes** -- never raw presence in `prices_eod`, never raw presence in `bars_1min`. The 4 verified weekend special sessions are included (`2020-02-01`, `2024-01-20`, `2025-02-01`, `2026-02-01`); 3 of them (on the 1st of February) can be that month's governing ranking date even though `prices_eod` has no `series='EQ'` row that day. `2021-02-24` is excluded, per Decision 21. `2016-10-03` vs. `2016-10-04` is the known intraday-archive-start artifact, not a calendar disagreement | Using `prices_eod`'s own calendar (rejected -- misses 3 genuine weekend special sessions as ranking-date candidates); using `bars_1min`'s own raw presence (rejected -- conflates data availability with session identity; also wrong for `2016-10-03`, which the archive does not cover at all); treating the 4/120-month mismatch as unresolvable without new data collection (rejected -- resolved by adopting the already-established governing calendar, no new measurement needed) | `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` Section 4.1 (the finding); `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 11 LOG (the resolving decision record) | No -- already approved | Prospective, Phase 4 implementation |

**Twelfth tally, 2026-11-14 (immediately prior to Phase 4 implementation
authorization), superseding the "Eleventh tally" immediately below for
row 18's approval** (see `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 13
LOG for the full record): **22 APPROVED/RESOLVED** (rows 1-6, 7, 8, 9,
10, 11, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24), **1 CLOSED/APPROVED
with historical detail preserved** (row 16, Decision 16), **0
RECOMMENDED**, **1 OPEN** (row 12). **24 rows total.** Row 18 (fixed
monthly roster identity) moves from RECOMMENDED to **APPROVED**, by
explicit user decision, exactly as already described in Section 3A and
this row -- no substantive change. **This does not change row 12
(remains OPEN, unaffected), and does not touch any of rows 1-6, 10, 11,
13, 14, 15, 16, 17, 19, 20, 21, 22, 23, or 24.** No other row's status
changed from the "Eleventh tally" below. **Every row in this table is
now APPROVED/RESOLVED or CLOSED/APPROVED except row 12, which remains
OPEN and is explicitly deferred past Phase 4's primary-gate pre-work
(Decision 12's own numerical bootstrap sub-parameters) -- not resolved,
approximated, or silently assumed by this tally.**

*(Eleventh tally, 2026-11-14, preserved -- no longer current, retained
for provenance)*: "**Eleventh tally, 2026-11-14 (later the same day),
superseding the "Tenth tally" immediately below for rows 7, 8, and 9's
approval**... **21 APPROVED/RESOLVED** (rows 1-6, 7, 8, 9, 10, 11, 13,
14, 15, 17, 19, 20, 21, 22, 23, 24), **1 CLOSED/APPROVED with historical
detail preserved** (row 16, Decision 16), **1 RECOMMENDED** (row 18),
**1 OPEN** (row 12). **24 rows total.** Rows 7 (final control set), 8
(fixed-effects specification), and 9 (prior-day NIFTY50 regime control)
move from OPEN to APPROVED, together, by explicit user decision. This
does not change row 12 (remains OPEN, unaffected), and does not touch
any of rows 1-6, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, or
24. No other row's status changed from the "Tenth tally" below."

*(Tenth tally, 2026-11-14, preserved -- no longer current, retained for
provenance)*: "**Tenth tally, 2026-11-14 (later the same day), superseding
the "Ninth tally" immediately below for new row 24's approval**... **18
APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 14, 15, 17, 19, 20, 21, 22, 23,
24), **1 CLOSED/APPROVED with historical detail preserved** (row 16,
Decision 16), **1 RECOMMENDED** (row 18), **4 OPEN** (rows 7, 8, 9, 12).
**24 rows total.** New row 24 (monthly roster ranking-date calendar
source) is added as APPROVED, by explicit user decision: the governing
exchange-session calendar (Decision 10/21) determines ranking dates,
resolving the `prices_eod`-vs-`bars_1min` first-trading-day mismatch row
23 itself left open. This does not change rows 7, 8, 9, or 12 (all
remain OPEN, unaffected), does not reopen Decision 23's other rules or
the annual top-200 universe construction, and does not touch any of rows
1-6, 10, 11, 13, 15, 16, 17, 18, 19, 20, 21, 22, or 23. No other row's
status changed from the "Ninth tally" below."

*(Ninth tally, 2026-11-14, preserved -- no longer current, retained for
provenance)*: "**Ninth tally, 2026-11-14 (later the same day), superseding
the "Eighth tally" immediately below for row 17's approval**... **17
APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 14, 15, 17, 19, 20, 21, 22,
23), **1 CLOSED/APPROVED with historical detail preserved** (row 16,
Decision 16), **1 RECOMMENDED** (row 18), **4 OPEN** (rows 7, 8, 9, 12).
**23 rows total.** Row 17 moves from OPEN to APPROVED, by explicit user
decision: PRESENT-VALID formally defined; categories A1/B1/C restated as
previously settled, unchanged; categories D and E newly approved; Stage
A/Stage B precedence stated explicitly. This does not change rows 7, 8,
9, or 12 (all remain OPEN, unaffected), does not reopen Decisions 14, 19,
20, 21, 22, or 23, and does not touch any of rows 1-6, 10, 11, 13, 15,
16, 18, 22, or 23. No other row's status changed from the "Eighth tally"
below."

*(Eighth tally, 2026-11-14, preserved -- no longer current, retained for
provenance)*: "**Eighth tally, 2026-11-14 (later the same day),
superseding the "Seventh tally" immediately below for rows 14, 19, 20,
and 21's approval**... **16 APPROVED/RESOLVED** (rows 1-6, 10, 11, 13,
14, 15, 19, 20, 21, 22, 23), **1 CLOSED/APPROVED with historical detail
preserved** (row 16, Decision 16), **1 RECOMMENDED** (row 18), **5 OPEN**
(rows 7, 8, 9, 12, 17). **23 rows total.** Rows 14, 20, and 21 move from
OPEN to APPROVED; row 19's own previously-separate threshold sub-question
also moves to APPROVED within its own cell (row 19 itself was already
counted APPROVED/RESOLVED for its selection, so this does not change the
tally count for row 19) -- all four by explicit user decision, following
a single consolidated methodology review. This does not change rows 7,
8, 9, 12, or 17 (all remain OPEN, unaffected), does not reopen Option 1,
and does not touch any of rows 1-6, 10, 11, 13, 15, 16, 18, 22, or 23. No
other row's status changed from the "Seventh tally" below."

*(Seventh tally, 2026-11-14, preserved -- no longer current, retained for
provenance)*: "**Seventh tally, 2026-11-14 (later the same day),
superseding the "Sixth tally" immediately below for row 15's approval**
... **13 APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 15, 19, 22, 23), **1
CLOSED/APPROVED with historical detail preserved** (row 16, Decision 16),
**1 RECOMMENDED** (row 18), **8 OPEN** (rows 7, 8, 9, 12, 14, 17, 20, 21).
**23 rows total.** Row 15 (20bps effect-size-hurdle interpretation and
sign rule) moves from OPEN to **APPROVED** here, by explicit user
decision, exactly as recommended in Section 9 with one added precision
(strict inequality, `>20bps`, not `>=`). This does not change the
20bps numeral, the two-sided `alpha=0.00625` significance level, the
day-clustered SE methodology, or the 60-minute primary horizon, and does
not touch row 7, 8, 9, 12, 14, 17, 20, or 21 (all remain OPEN,
unaffected). No other row's status changed from the "Sixth tally"
below."

*(Sixth tally, 2026-11-14, preserved -- no longer current, retained for
provenance)*: "**Sixth tally, 2026-11-14 (later the same day), superseding
the "Fifth tally" immediately below for new row 23's approval**... **12
APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 19, 22, 23), **1
CLOSED/APPROVED with historical detail preserved** (row 16, Decision 16),
**1 RECOMMENDED** (row 18), **9 OPEN** (rows 7, 8, 9, 12, 14, 15, 17, 20,
21). **23 rows total.** New row 23 (monthly roster turnover-ranking
effective-time, Convention A -- prior-session cutoff) is added as
**APPROVED**, by explicit user decision on 2026-11-14 following review of
the cited audit. This does not change row 19's own still-OPEN
threshold-form/value sub-question, does not touch row 20 or row 21 (both
remain OPEN, unaffected), and does not alter the annual top-200 universe
construction, Option 2's Stage-A/Stage-B distinction, or Stage-B's
zero-tolerance forward-endpoint rule. No other row's status changed from
the "Fifth tally" below."

*(Fifth tally, 2026-11-14, preserved -- no longer current, retained for
provenance)*: "**Fifth tally, 2026-11-14 (later the same day), superseding
the "Fourth tally" immediately below for row 11's approval**... **11
APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 19, 22), **1 CLOSED/APPROVED
with historical detail preserved** (row 16, Decision 16), **1
RECOMMENDED** (row 18), **9 OPEN** (rows 7, 8, 9, 12, 14, 15, 17, 20, 21).
**22 rows total.** Row 11 moves from OPEN to **APPROVED** here, reflecting
the user's explicit decision following a final targeted first-bar
verification report -- `09:15` is the frozen first regular-session bar;
row 22's `Momentum_F(t)` minimum anchor is a consequence, now also
unconditional (`t>=09:50`). No other row's status changed from the
"Fourth tally" below."

*(Fourth tally, 2026-11-14, preserved -- no longer current, retained for
provenance)*: "**Fourth tally, 2026-11-14 (same day), superseding the
"Third tally" immediately below for row 19's selection-resolved status**
... **10 APPROVED/RESOLVED** (rows 1-6, 10, 13, 19, 22), **1
CLOSED/APPROVED with historical detail preserved** (row 16, Decision 16),
**1 RECOMMENDED** (row 18), **10 OPEN** (rows 7, 8, 9, 11, 12, 14, 15, 17,
20, 21). **22 rows total.** Row 19 moves from OPEN to **SELECTION
RESOLVED** here, reflecting the pre-existing `PREREGISTRATION_LEAD_LAG_V1.md`
AMENDMENT 3 LOG item 3 decision record -- this is not a new approval. Row
19's own internal threshold form/value sub-question is **not** resolved by
this move and remains counted as open within that row's own cell detail,
not as a separate tally row. No other row's status changed from the
"Third tally" below."

*(Third tally, 2026-11-14, preserved -- no longer current, retained for
provenance)*: "**Third tally, 2026-11-14 (same day), superseding the
"Second tally" immediately below for the Decision 11 correction**... **9
APPROVED** (rows 1-6, 10, 13, 22), **1 CLOSED/APPROVED with historical
detail preserved** (row 16, Decision 16), **1 RECOMMENDED** (row 18), **11
OPEN** (rows 7, 8, 9, 11, 12, 14, 15, 17, 19, 20, 21). **22 rows total.**
Row 11 is restored to OPEN here (the "Second tally" below incorrectly
counted it as APPROVED) -- Decision 11 was never approved by the user. No
other row's status changed from the "Second tally" below."

*(Second tally, 2026-11-14, preserved -- no longer current, retained for
provenance of the error and its correction)*: "**Second tally update,
2026-11-14, superseding the one immediately below it for Decisions 10, 11,
and 22's approval**... **10 APPROVED** (rows 1-6, 10, 11, 13, 22), **1
CLOSED/APPROVED with historical detail preserved** (row 16, Decision 16),
**1 RECOMMENDED** (row 18), **10 OPEN** (rows 7, 8, 9, 12, 14, 15, 17, 19,
20, 21). **22 rows total.** Rows 10, 11, and 22 moved from OPEN to
APPROVED in this update; no other row's status changed from the tally
immediately below."

*(First tally update, 2026-11-14, preserved -- no longer current, retained
for provenance)*: "**Tally, counted directly from the table above, updated
2026-11-14 for Decision 13's approval and the addition of row 22**... **7
APPROVED** (rows 1-6, 13), **1 CLOSED/APPROVED with
historical detail preserved** (row 16, Decision 16 -- labeled separately
because its cell retains both the historical Revision-6 OPEN text and the
current approved accounting, not a plain APPROVED), **1 RECOMMENDED**
(row 18), **13 OPEN** (rows 7-12, 14-15, 17, 19-22, of which row 22 is
newly added and explicitly a proposal awaiting approval, not yet
approved). **22 rows total.** This updates, rather than silently
preserves, the prior revision's tally sentence below, which is retained
immediately after this one for historical provenance and is no longer
current:"

*(Historical, prior revision's tally, preserved -- no longer current)*:
"**Tally, counted directly from the table above**: 6 APPROVED (rows 1-6),
1 RECOMMENDED (row 18), 14 OPEN (rows 7-17, 19-21). 21 rows total.
Unchanged from the prior revision's tally -- this round's edits (rows 10,
12, 16, 19) changed row *content*, not row *status*; no row's
APPROVED/RECOMMENDED/OPEN label changed.

**This was Revision 6's tally and is not the current one.** Decision 16
(row 16) was approved 2026-11-14, after this revision -- it was not
wrong when counted above, it has since changed. **Current tally: 7
APPROVED/CLOSED (rows 1-6, 16), 1 RECOMMENDED (row 18), 13 OPEN (rows
7-15, 17, 19-21).** No other row's status has changed.

---

## 12. Adversarial self-review, redone against this round's revised content

### Revision 6's three corrections, stated first and precisely

- **Dividend evidence, corrected.** The opening evidence-verification
  summary at the top of this document had retained an unsupported
  project-wide claim ("directly confirms dividends are not tracked at
  all by any existing mechanism") even after Section 4A's own body text
  was narrowed in Revision 5. **This was an inconsistency within the
  document, not merely an isolated overreach** -- the correction only
  works if every restatement of the finding agrees. The opening summary
  now states only that the existing corporate-actions pipeline excludes
  dividends from its supported feed, which establishes the scope of that
  pipeline and nothing about the rest of the project. **Not described as
  empirically resolved**: no project-wide dividend-source inventory has
  been performed, and this document does not claim one has.
- **Missingness-emulation ground truth, corrected.** The Section 3D-A
  diagnostic's ground-truth definition required full-roster validity only
  at the three pre-signal endpoints (`t-35`, `t-5`, `t`), while its own
  later steps recomputed and compared `Y(t,h)` -- a forward quantity
  needing the full roster to also be valid at `t+h`. **This was an
  internal gap, not a cosmetic one**: without the forward-endpoint
  requirement, the "known full-roster reference" the whole comparison
  depends on might not actually exist. The corrected definition requires
  horizon-specific full-roster validity at `t+h` (and every other
  endpoint the frozen construction needs) before an observation qualifies
  as ground truth for that horizon, and requires reporting insufficient
  ground-truth coverage explicitly rather than relaxing the requirement,
  substituting partial returns, or claiming missing-at-random regardless
  of coverage. **Not described as empirically resolved**: the adequacy
  threshold for insufficient coverage is left OPEN, and no data, mask, or
  comparison has actually been run.
- **Trial accounting, corrected.** "Denominator becomes 8" in the prior
  revision could be read as asserting eight is the current actual trial
  count. **It is not, and this document no longer leaves that reading
  available.** The current recorded ledger count is six, verified
  directly from `lead_lag/trial_ledger.json`, unchanged. The two
  basket-construction configurations are proposed and prospective only --
  neither has been registered or empirically examined. Eight is a
  conditional, forward-looking total, contingent on both approval and
  registration (a human decision not made here) and on each
  configuration subsequently satisfying the project's existing trial
  definition (not merely existing as a written proposal). **Multiplicity-family
  membership and the operative alpha remain explicitly OPEN**; the
  committed `0.05/6` is unchanged.

**None of the three corrections above resolves any previously open risk
-- they repair internal inconsistencies and a definitional gap in how
this document itself was written. The underlying methodological
questions (ground-truth adequacy, basket-construction choice,
multiplicity-family membership, and every other item in Section 11's
table) remain exactly as open as before this round.** **Historical
status (2026-11-14): true of Revision 6; multiplicity-family membership
specifically was subsequently closed by Decision 16 (formal trial count
7, multiplicity-family denominator 8, prospective alpha `0.05/8`,
ledger unchanged at 6) -- ground-truth adequacy, basket-construction
choice, and the other Section 11 items remain open as this round left
them.**

### Carried forward from prior revisions (historical record, superseded claims marked as such, not restated as current)

- **Future-dependent constituent selection**: still fixed -- unchanged
  this round, re-verified intact.
- **Future-dependent observation inclusion**: unchanged from the prior
  revision's correction -- neither option eliminates it; not re-targeted
  this round, but now also cross-referenced from the corrected Section
  3D-B diagnostic (observation exclusion is measured by frequency, never
  by computing the forward return it would have had).
- **Return distortion from missing constituents -- made endpoint-specific
  this round.** The missingness-emulation diagnostic is now split into
  two components: (A) pre-signal eligibility-mask emulation, which
  preserves *which endpoint* (`t-35`, `t-5`, or `t`) was missing for each
  masked name and re-runs the exact eligibility determination, rather
  than a simplified count-only mask; (B) a forward-endpoint diagnostic
  that explicitly **never** computes a partial forward return under
  Option 2 (the real construction never does this operationally), only
  the frequency and correlates of whole-observation exclusion. **This
  closes a real gap**: the prior single diagnostic conflated two
  different missingness mechanisms (constituent-selection-adjacent vs.
  observation-inclusion-adjacent) into one masking operation. **Still not
  run or measured.**
- **Predictor/dependent-variable basket consistency**: unchanged, intact.
- **Momentum-control eligibility**: unchanged, intact.
- **Corporate-action discontinuities -- re-examined this round, a real
  overreach corrected.** The prior revision asserted "NSE's own standard
  mechanism... overnight" as established fact. **It was not established**
  -- no authoritative NSE source was ever verified within this proposal's
  materials. The evidence is now split into three explicit categories
  (project-code / exchange-mechanism / intraday-data), with the
  exchange-mechanism claim walked back to "commonly understood, not
  verified." **Neither candidate policy is removed; Decision 20 remains
  OPEN, now on a more honest evidentiary footing.**
- **Price adjustment status**: unchanged -- circumstantial, not proven.
- **Zero-volume stale bars / corrupted-but-present bars**: unchanged.
- **Timestamp conventions -- sharpened this round.** `ts` = bar start
  remains directly verified (unchanged fact), but the *prose* describing
  eligibility ("at or before `t`") is now precisely distinguished from
  wall-clock availability (`t+1`) via an explicit terminology note at the
  top of Section 3, closing a risk that an implementation could
  misread the nominal label `t` as the actual decision timestamp and
  introduce a one-minute look-ahead. **No arithmetic or anchor
  recommendation changed** -- this is a prose-precision fix, confirmed
  not to contradict Section 5's existing `09:20`/`09:21` treatment.
- **Special sessions**: unchanged -- unverified, flagged.
- **Non-overlapping intervals**: unchanged -- `h+5` spacing holds.
- **Cross-day dependence / ACF rule -- a real loophole closed this
  round.** The previous rule ("every lag from `L` through the current
  maximum qualifies") could accept a single isolated terminal lag as
  evidence of decay. **Corrected**: a qualifying run must now have length
  at least `R` (`>=2` by construction, exact value left open, not
  invented), and an indeterminate lag breaks rather than gets skipped
  over in a candidate run. The hypothesis-predictor-free (not
  outcome-independent) terminology from the prior round is preserved.
  **Still not run or measured.**
- **Block-length selection influenced by outcome**: re-checked against
  both the terminology correction and the new run-length requirement --
  neither introduces any path by which `beta`, its p-value, or the
  effect-size hurdle could influence the choice of `R` or `L`; `R` is
  stated to be set from standard practice, not from the actual ACF
  (which has not been computed).
- **Power**: still genuinely open and unmeasured.
- **Multiplicity and trial counting -- further corrected this round.**
  Beyond the prior round's estimand-double-counting fix, this round adds
  a three-way distinction the prior round elided: project trial count (A,
  recommended at 8), multiplicity-adjustment family membership (B,
  **explicitly left OPEN** -- a genuine, reasoned case exists for
  treating the two basket-construction configurations as outside the
  main propagation-hypothesis family, since neither represents a
  competing economic hypothesis), and alpha allocation (C, **the existing
  committed `0.05/6` is explicitly confirmed unchanged**, never silently
  replaced with `0.05/8`). **This is the clearest instance in this
  document of declining to force a conclusion where precedent genuinely
  does not settle the question.** **Historical-status clarification
  (2026-11-14)**: this bullet describes the position at Revision 6.
  Decision 16 subsequently closed the family-membership and
  alpha-allocation question (B and C above): Option 1 counts as a formal
  trial, Option 2 does not, both join the multiplicity family, formal
  trial count is 7, multiplicity-family denominator is 8, and the
  prospective primary alpha is `0.05/8` (not yet operative). The
  six-entry ledger is unchanged. This does not retroactively mean
  Revision 6 was wrong to leave it open -- it genuinely was, at the time.
- **Positive-beta success rule**: unchanged -- not targeted this round.
- **Effect-size versus profitability claims**: unchanged -- not targeted
  this round.
- **Included-vs-excluded diagnostic availability -- corrected this
  round.** The prior claim that `S_L(t)`/`R_F(t)`/`Momentum_F(t)` are
  observable for both included and excluded observations,
  unconditionally, was false for at least one real exclusion category
  (pre-signal breadth failure, where these quantities may not be
  reliably computable at all). Four exclusion categories are now
  distinguished, each with its own variable-availability statement, and
  a diagnostic-only partial-subset value is explicitly forbidden from
  being labelled as the primary construction's `R_F(t)` or `S_L(t)`.
- **Dividend-data claim -- corrected this round.** "There is no dividend
  data anywhere in this project" overstated what the cited docstring
  actually establishes (only that the existing corporate-actions
  *pipeline* doesn't provide it). **Narrowed** to a pipeline-specific
  claim, with the price-return convention now stated as a methodology
  choice motivated by the actual data source used, not as a conclusion
  from a project-wide audit that was never performed.

**This revision does not claim the design is valid merely because its
construction is now more precise or because more issues have been named
or corrected.** The two most consequential open risks remain exactly what
they have been throughout every revision of this proposal: whether the
design is adequately powered once actually measured, and the
stale-pricing/non-synchronous-trading identification ambiguity.
Observation-selection/informative-censoring bias (Section 3C) remains a
third risk of comparable importance, now with a two-part diagnostic
proposed (Section 3D) but not run. **A fourth, newly surfaced open
question this round** is whether the two basket-construction
configurations share a multiplicity-adjustment family with the existing
six trials -- a question this document can state precisely but cannot
answer from existing project documentation alone.

---

## Report (Revision 5)

1. **Exact file path revised**: `C:\projects\trade-new\LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`,
   in place; no second file created.

2. **Starting and ending HEAD**: `9f71b65e006f937760e39a9f65035c69a1ef8df9`
   at the start of this task and unchanged at the end -- this task never
   touched git state.

3. **Starting and ending `git status --short` / `git diff --stat`**:
   identical at both points -- `git status --short` showed the same three
   untracked files (this proposal, the earlier working-draft proposal,
   the original methodology review) before and after; `git diff --stat`
   was empty before and after.

4. **Exact changes by section, Revision 5**: Section 3 (a terminology
   note distinguishing nominal `t` from wall-clock `t+1` availability
   added at the top; Option 2 step 2's wording tightened to match; the
   included-vs-excluded diagnostic rewritten with four exclusion
   categories and category-specific variable availability, replacing an
   unconditional claim false for at least one category; the
   missingness-emulation diagnostic split into endpoint-specific
   components A and B); Section 4 (dividend claim narrowed from
   project-wide to pipeline-specific, Section 4A; corporate-action
   analysis restructured into project-code/exchange-mechanism/intraday-data
   evidence categories, exchange-mechanism claim walked back to
   unverified, Section 4C); Section 7 (ACF lag-decay rule corrected to
   require a minimum consecutive qualifying run `R>=2`, not an isolated
   terminal lag, with indeterminate-lag handling specified; "two open
   sub-parameters" becomes "three"); Section 10 (trial count,
   multiplicity-family membership, and alpha allocation explicitly
   separated into three concepts; family membership left OPEN with
   reasoning on both sides; the existing `0.05/6` alpha explicitly
   confirmed unchanged); Section 11 (rows 10, 12, 16, 20 updated; no new
   rows; no status changes); Section 12 (adversarial review rewritten
   against this round's seven corrections).

5. **ACF lag-decay rule, final form, with every open parameter named**:
   fixed initial range 1-10 trading-session positions; per-lag decay
   criterion `|ACF(k)| <= 2/sqrt(n_k)`; a candidate `L` requires every lag
   from `L` through the current maximum to qualify **and** that run to
   have length `>= R` (`R >= 2` by construction); an indeterminate lag
   breaks a candidate run rather than being skipped or assumed to
   qualify; deterministic extension to range 1-20 if no such run is
   found; maximum permitted lag 20; INCONCLUSIVE if no qualifying run is
   found by lag 20 or if the resulting block count is too small. **Open**:
   the exact value of `R`; the minimum `n_k` for a lag to be evaluable;
   the minimum usable-block count; and `L` itself. None chosen by looking
   at an actual ACF, which was not computed.

6. **Project trial count, multiplicity family, and alpha allocation,
   distinguished**: (A) project trial count -- recommended at **8** (6
   existing + 2 basket-construction configurations), answerable from this
   family's own grouping-mechanism precedent. (B) multiplicity-adjustment
   family -- **left explicitly OPEN**; a reasoned case exists for
   excluding the 2 basket-construction configurations from the
   propagation-hypothesis family (a data-construction methodology choice,
   not a competing economic hypothesis), but this is not settled by
   `PROJECT_CONTEXT.md` or the ledger for a case shaped like this one. (C)
   alpha allocation -- **the committed `0.05/6` is unchanged**; never
   silently replaced with `0.05/8`.

7. **Whether denominator 8 remains the recommended trial count, and
   whether the multiplicity denominator remains OPEN**: yes to both -- 8
   is the recommended **trial count**; the **operative multiplicity
   denominator** remains OPEN pending the family-membership decision in
   point 6.

8. **The revised, endpoint-specific missingness-emulation procedure**:
   (A) pre-signal eligibility-mask emulation -- apply masks that preserve
   *which* endpoint (`t-35`, `t-5`, or `t`) failed, re-run the exact
   Option 2 eligibility determination, freeze, apply the breadth
   threshold, recompute `R_F(t)`/`Y(t,h)`/`Momentum_F(t)`, compare against
   the known full-roster truth. (B) forward-endpoint diagnostic --
   **never** computes a partial forward return; measures only how often
   and under what conditions the real whole-observation discard rule
   would trigger under realistic forward-missingness patterns. Neither
   component uses `t+h` outcomes to choose or tune a mask; neither proves
   missing-at-random.

9. **The corrected dividend-data statement**: narrowed from "no dividend
   data exists anywhere in this project" to "the existing
   corporate-actions pipeline does not provide dividend data; this does
   not establish that no source anywhere in the project contains it; no
   project-wide inventory has been performed; price-return,
   dividends-excluded is adopted as a methodology choice motivated by the
   actual data source used, not a proven absence claim."

10. **The revised corporate-action evidence hierarchy**: (1) project-code
    evidence -- `known_date = ex_date`, dividends out of scope, no
    intraday timestamp recorded for any action. (2) exchange-mechanism
    evidence -- **no authoritative NSE source verified**; the
    "overnight, before the session" claim is now stated as commonly
    understood, not proven. (3) intraday-data evidence -- unverified,
    unchanged, a targeted check proposed for later work. Both candidate
    policies remain open; neither declared necessary or unnecessary.

11. **The clarified nominal signal time vs. actual signal-availability
    time**: `t` labels the bar whose `ts` equals clock time `t`; that
    bar's close becomes available at approximately wall-clock `t+1`, not
    at wall-clock `t`. Eligibility uses information computable by the
    time it is actually available, never information nominally labelled
    `t` taken literally as a wall-clock moment. No arithmetic or anchor
    recommendation changed -- this corrects prose precision only.

12. **The revised included-vs-excluded diagnostic availability matrix**:
    four exclusion categories -- (1) pre-signal follower-side breadth
    failure: `R_F(t)`/`Momentum_F(t)` not reliably computable; (2)
    forward `t+h` failure only: `S_L(t)`/`R_F(t)`/`Momentum_F(t)` all
    genuinely observable, only `Y(t,h)` unobservable; (3) leader-side
    signal-endpoint failure: `S_L(t)` not computable even if the follower
    side is fine; (4) any other supported reason, availability dependent
    on the policy chosen. A diagnostic-only partial-subset value must
    never be labelled as the primary construction's own quantities.
    Unknown exclusion reasons are reported as unknown.

13. **Updated APPROVED / RECOMMENDED / OPEN tally**: 6 APPROVED (rows
    1-6), 1 RECOMMENDED (row 18), 14 OPEN (rows 7-17, 19-21). 21 rows
    total -- unchanged from every prior revision's tally, since this
    round changed row content (10, 12, 16, 20) but no row's status.
    Counted directly from the finished table in Section 11.
    **[STATUS UPDATE, 2026-11-14, CORRECTED TWICE same day: this count is
    historical and no longer current. An intermediate version of this note
    stated Section 11's table showed row 11 as APPROVED -- that was
    incorrect; Decision 11 was never approved by the user and remains
    OPEN. A further update: row 19 (Option 1 vs. Option 2 selection) has
    since moved to SELECTION RESOLVED, per the pre-existing
    `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3 decision
    record (Option 2 selected) -- this is not a new approval, and does
    not resolve Option 2's own internal threshold form/value, which
    remains open within row 19's own cell. Section 11's table now shows
    10 APPROVED/RESOLVED (rows 1-6, 10, 13, 19, 22), 1 CLOSED/APPROVED
    (row 16), 1 RECOMMENDED (row 18), 10 OPEN (rows 7, 8, 9, 11, 12, 14,
    15, 17, 20, 21), 22 rows total -- see Section 11's own tally for the
    authoritative current count.]**

    **[FURTHER STATUS UPDATE, 2026-11-14 (later the same day)**: row 11
    (the first-bar anchor, Decision 11) has since moved from OPEN to
    **APPROVED**, by explicit user decision following a final targeted
    first-bar verification report -- `09:15` is the frozen first
    regular-session bar. Section 11's table now shows **11
    APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 19, 22), 1 CLOSED/APPROVED
    (row 16), 1 RECOMMENDED (row 18), **9 OPEN** (rows 7, 8, 9, 12, 14,
    15, 17, 20, 21), 22 rows total -- see Section 11's own "Fifth tally"
    for the authoritative current count.]**

    **[FURTHER STATUS UPDATE, 2026-11-14 (later still, same day)**: a new
    row 23 (monthly roster turnover-ranking effective-time / ranking-date
    inclusivity) has been added and is **APPROVED** -- Convention A
    (prior-session cutoff), by explicit user decision following review of
    `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md`. Section 11's table
    now shows **12 APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 19, 22, 23),
    1 CLOSED/APPROVED (row 16), 1 RECOMMENDED (row 18), **9 OPEN** (rows
    7, 8, 9, 12, 14, 15, 17, 20, 21), **23 rows total** -- see Section 11's
    own "Sixth tally" for the authoritative current count. This does not
    resolve row 19's own threshold form/value sub-question, row 20, or
    row 21, and does not change the annual top-200 universe construction
    or Option 2's Stage-A/Stage-B distinction.]**

    **[FURTHER STATUS UPDATE, 2026-11-14 (later still, same day)**: row 15
    (the 20bps effect-size-hurdle interpretation and sign rule) has moved
    from OPEN to **APPROVED** -- `beta > 0` required; `beta * sigma(S_L) >
    20bps` strictly (equality does not pass); by explicit user decision,
    following review of Section 9's recommendation
    (`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 8 LOG). Section 11's table
    now shows **13 APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 15, 19, 22,
    23), 1 CLOSED/APPROVED (row 16), 1 RECOMMENDED (row 18), **8 OPEN**
    (rows 7, 8, 9, 12, 14, 17, 20, 21), **23 rows total** -- see Section
    11's own "Seventh tally" for the authoritative current count. The
    20bps numeral, the two-sided `alpha=0.00625` significance level, the
    day-clustered SE methodology, and the 60-minute primary horizon are
    unchanged.]**

    **[FURTHER STATUS UPDATE, 2026-11-14 (later still, same day,
    following a consolidated methodology review)**: rows 14, 20, and 21
    move from OPEN to **APPROVED**; row 19's own previously-open
    threshold sub-question also moves to APPROVED within its own cell.
    Section 11's table now shows **16 APPROVED/RESOLVED** (rows 1-6, 10,
    11, 13, 14, 15, 19, 20, 21, 22, 23), 1 CLOSED/APPROVED (row 16), 1
    RECOMMENDED (row 18), **5 OPEN** (rows 7, 8, 9, 12, 17), **23 rows
    total** -- see Section 11's own "Eighth tally" for the authoritative
    current count. `bars_1min` is MIXED CONVENTION (Decision 14); Option
    2's Stage-A threshold is `0.70` of the original roster-tier size
    (Decision 19); the existing CA exclusion is folded into Stage A
    (Decision 20); the primary-sample calendar is 2,456 dates, with
    `2021-02-24` conservatively excluded (Decision 21). See
    `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 9 LOG for the full
    record.]**

    **[FURTHER STATUS UPDATE, 2026-11-14 (later still, same day,
    following approval of Decision 17)**: row 17 moves from OPEN to
    **APPROVED**. Section 11's table now shows **17 APPROVED/RESOLVED**
    (rows 1-6, 10, 11, 13, 14, 15, 17, 19, 20, 21, 22, 23), 1
    CLOSED/APPROVED (row 16), 1 RECOMMENDED (row 18), **4 OPEN** (rows 7,
    8, 9, 12), **23 rows total** -- see Section 11's own "Ninth tally" for
    the authoritative current count. PRESENT-VALID is formally defined;
    categories A1/B1/C (settled) and D/E (newly approved) are all
    recorded; Stage A's short-gap rule is barred from Stage B. See
    `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 10 LOG for the full
    record.]**

    **[FURTHER STATUS UPDATE, 2026-11-14 (later still, same day,
    following approval of Decision 24)**: a new row 24 (monthly roster
    ranking-date calendar source) is added and is **APPROVED**: the
    governing exchange-session calendar (Decision 10/21) determines
    ranking dates, resolving the `prices_eod`-vs-`bars_1min`
    first-trading-day mismatch row 23 itself left open. Section 11's
    table now shows **18 APPROVED/RESOLVED** (rows 1-6, 10, 11, 13, 14,
    15, 17, 19, 20, 21, 22, 23, 24), 1 CLOSED/APPROVED (row 16), 1
    RECOMMENDED (row 18), **4 OPEN** (rows 7, 8, 9, 12), **24 rows
    total** -- see Section 11's own "Tenth tally" for the authoritative
    current count. See `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 11 LOG
    for the full record.]**

    **[FURTHER STATUS UPDATE, 2026-11-14 (later still, same day,
    following approval of Decisions 7, 8, and 9 together)**: rows 7
    (final control set), 8 (fixed-effects specification), and 9
    (prior-day NIFTY50 regime control) move from OPEN to **APPROVED**.
    Section 11's table now shows **21 APPROVED/RESOLVED** (rows 1-6, 7,
    8, 9, 10, 11, 13, 14, 15, 17, 19, 20, 21, 22, 23, 24), 1
    CLOSED/APPROVED (row 16), 1 RECOMMENDED (row 18), **1 OPEN** (row
    12), **24 rows total** -- see Section 11's own "Eleventh tally" for
    the authoritative current count. The primary regression equation and
    all variable definitions (this document's own Section 6, above) are
    unchanged. See `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 12 LOG for
    the full record.]**

    **[FURTHER STATUS UPDATE, 2026-11-14 (immediately prior to Phase 4
    implementation authorization)**: row 18 (fixed monthly roster
    identity) moves from RECOMMENDED to **APPROVED**. Section 11's table
    now shows **22 APPROVED/RESOLVED** (rows 1-6, 7, 8, 9, 10, 11, 13,
    14, 15, 17, 18, 19, 20, 21, 22, 23, 24), 1 CLOSED/APPROVED (row 16),
    **0 RECOMMENDED**, **1 OPEN** (row 12), **24 rows total** -- see
    Section 11's own "Twelfth tally" for the authoritative current
    count. Every row is now APPROVED/RESOLVED or CLOSED/APPROVED except
    row 12 (Decision 12's bootstrap sub-parameters), explicitly deferred
    past Phase 4's pre-primary-gate work, not resolved here. See
    `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 13 LOG for the full
    record.]**

14. **Every remaining unresolved methodological issue**: the exact value
    of `R` and the two other open ACF sub-parameters; the numerical block
    length `L`; whether the two basket-construction configurations share
    a multiplicity family with the existing six (and the resulting
    operative alpha); whether observation-selection/informative-censoring
    bias is small enough to ignore; whether the missingness-emulation
    diagnostics will have enough representative ground-truth data;
    Option 1 vs. Option 2 and the breadth-threshold form/value; whether
    `bars_1min` holds raw or adjusted prices; whether an authoritative
    NSE source confirms the split/bonus timing mechanism; whether
    same-session returns are scale-consistent around corporate actions;
    whether `09:15` is a valid bar; whether special/irregular sessions
    exist; whether dividend data exists outside the corporate-actions
    pipeline (unaudited); whether the design is adequately powered at
    all; the residual estimand-pivot ledger-marker question.

    **STATUS UPDATE (2026-11-14), CORRECTED TWICE, same day**: of this
    list, the **"Option 1 vs. Option 2"** portion of this item is now
    resolved by the existing human decision record in
    `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3 (Option 2
    selected, Option 1 not selected -- see Section 3C's own dated
    supersession note and decision-table row 19). **The "and the
    breadth-threshold form/value" portion of this SAME list item is a
    separate, still-OPEN question and is NOT resolved by that selection.**

    *(Second correction, same day)*: an earlier version of this note
    additionally claimed "the breadth-threshold form/value" was itself
    "frozen at 70%, Decision 10." **That was incorrect and is retracted.**
    Decision 10 approved a numeric follower-breadth value modeled on the
    leader-side per-minute `n_t_breadth` convention (Section 8) -- its own
    text never names "Option 2," "the frozen eligible subset," or this
    list item's threshold. **Whether Decision 10's `70%` is the value
    Option 2's own step-4 threshold uses remains an open question**,
    separate from, and not settled by, either Decision 10's approval or
    Option 2's selection. The exact endpoint-price return convention
    (Decision 13) and the `Momentum_F(t)` same-session rule (Decision 22)
    are also now approved, though neither was itself named in this
    particular list at the time it was written. **"Whether `09:15` is a
    valid bar" was briefly, incorrectly marked resolved by an intermediate
    edit in this working tree -- that was never approved by the user and
    this item remained OPEN, exactly as the list above states, at the
    time this note was written.** Every other item in this list remains
    open, unaffected by this update. See
    `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md` and
    `lead_lag/PRE_SIGNAL_VS_FORWARD_ENDPOINT_RECONCILIATION.md` for the
    full record. The list above is preserved unedited.

    **[FINAL STATUS UPDATE, 2026-11-14 (later the same day)**: "whether
    `09:15` is a valid bar" is now **RESOLVED** -- `09:15` is APPROVED as
    the frozen first regular-session bar, by explicit user decision
    following a final targeted first-bar verification report. This is a
    genuine approval, unlike the earlier, retracted claim corrected
    immediately above: it followed an actual user decision made after
    reviewing direct `bars_1min` evidence, not an undocumented assumption.
    See `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 6 LOG. Every other item
    in the numbered list above remains open, unaffected by this update.]**

    **[FURTHER FINAL STATUS UPDATE, 2026-11-14 (later still, same day,
    following a consolidated methodology review)**: four more items on
    this list are now resolved. **"Whether `bars_1min` holds raw or
    adjusted prices"** -- resolved, MIXED CONVENTION (Decision 14).
    **"Whether same-session returns are scale-consistent around
    corporate actions"** -- the tested population (104 events, 208
    sessions) shows zero within-session mixed-scale defects; the existing
    CA exclusion is folded into Stage A on this basis (Decision 20);
    untested entities/action-types remain a documented, permanent
    limitation, not resolved further. **"Whether special/irregular
    sessions exist"** -- resolved: yes, the 4 weekend specials exist and
    are included; the 11 non-session dates and `2021-02-24` are excluded
    (Decision 21). **"Option 1 vs. Option 2 and the breadth-threshold
    form/value"** -- the selection was already resolved; the
    breadth-threshold form/value portion is now also resolved (`0.70` of
    the original roster-tier size, Decision 19). Every other item in the
    numbered list above (the ACF sub-parameters, block length `L`,
    multiplicity-family sharing, missingness-emulation data sufficiency,
    authoritative NSE source for split/bonus timing [still unverified --
    not the same question as the above], dividend data, power adequacy,
    the estimand-pivot ledger marker) remains open, unaffected by this
    update. See `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 9 LOG for the
    full record.]**

15. **Confirmation that all protected files remained untouched**:
    `PREREGISTRATION_LEAD_LAG_V1.md`, `lead_lag/trial_ledger.json`,
    `lead_lag/MASTER_SPEC_LEAD_LAG.md`, and `PROJECT_CONTEXT.md` were
    confirmed present and read-only throughout; the existing `alpha`
    value in the committed preregistration was not changed.

16. **Explicit confirmation that no measurement, outcome inspection, data
    fetch, Phase 4 work, trial registration, commit, or push occurred**:
    none occurred. No breadth measurement, power calculation, regression,
    ACF/residual diagnostic, bootstrap, null simulation, missingness
    emulation, project-wide dividend audit, historical corporate-action
    bar check, `MIN(ts)`-per-day query, or broad historical data query
    was run. No new data was fetched. No existing strategy or other
    research family was changed. No trial was registered and no alpha
    value was changed. Nothing was committed or pushed. No second,
    competing proposal file was created.

---

## Report (Revision 6)

1. **Exact file path revised**: `C:\projects\trade-new\LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`,
   in place; no second file created.

2. **Starting and ending HEAD**: `9f71b65e006f937760e39a9f65035c69a1ef8df9`
   both before and after this task -- unchanged throughout.

3. **Starting and ending `git status --short` / `git diff --stat`**:
   identical -- the same three untracked files (this proposal, the
   earlier working-draft proposal, the original methodology review)
   before and after; `git diff --stat` empty before and after.

4. **Exact sections changed**: the opening "Verified before this
   revision" evidence summary (the stale "not tracked at all" bullet
   corrected); Section 3D-A (ground-truth definition corrected to require
   horizon-specific full-roster validity at `t+h`, not only the
   pre-signal endpoints; insufficient-coverage handling made explicit);
   Section 4A (no further change needed -- already narrowed correctly in
   Revision 5; verified consistent with the opening-summary fix); Section
   10 (current recorded ledger count, proposed configurations, and
   conditional prospective total explicitly separated, replacing
   language that could be read as asserting eight as a current count);
   Section 11 (rows 10 and 16 updated; rows 19 and 20 reviewed and found
   already consistent with this round's requirements, left unchanged);
   Section 12 (three Revision 6 corrections stated precisely at the top,
   prior revisions' content preserved below as explicitly marked
   historical record); this Report (new section appended).

5. **Exact corrected dividend statement, and confirmation no live
   project-wide absence claim remains**: the opening summary now reads
   that the corporate-actions pipeline's docstring "establishes only that
   the existing corporate-actions pipeline excludes dividends from its
   supported feed -- it does not establish that no dividend data exists
   anywhere else in the project, and no project-wide dividend-source
   inventory has been performed." A full-document search for "not
   tracked at all," "no dividend data anywhere," and "no existing
   mechanism" found and corrected the one remaining live instance (the
   opening summary); no other live instance remains -- all other
   "project-wide" references in the document correctly state that no
   such audit has been performed, not that absence has been established.

6. **Exact ground-truth eligibility requirements, including
   horizon-specific forward-endpoint completeness**: for a given horizon
   `h`, an observation qualifies as a full-roster ground-truth reference
   only if the full roster has valid required endpoints at `t-35`,
   `t-5`, `t`, **and** `t+h` for that specific horizon, and any other
   endpoint the frozen construction of `R_F(t)`/`Momentum_F(t)`/`Y(t,h)`
   requires -- pre-signal validity alone no longer qualifies an
   observation as ground truth for any horizon. Ground truth is defined
   separately per horizon, since `t+h` differs by horizon.

7. **How insufficient ground-truth coverage is handled**: reported as a
   finding, for the specific horizon affected; the full-roster endpoint
   requirement (including `t+h`) is never relaxed to manufacture more
   qualifying observations; no partial forward return is substituted; the
   roster or return construction is not silently changed; missing-at-random
   is never claimed regardless of coverage; the adequacy threshold for
   "too small to be meaningful" is left explicitly OPEN, since no
   already-approved rule in this family governs this specific
   diagnostic's minimum sample size.

8. **Confirmation that Section 3D-B remains frequency-only**: unchanged
   from Revision 5, re-verified this round -- Section 3D-B explicitly
   prohibits calculating a partial forward portfolio return under any
   forward-missingness mask, and measures only how often and under what
   conditions the real whole-observation discard rule would trigger.
   Section 3D-A and 3D-B remain separate components, not merged, since
   they address different mechanisms (constituent-eligibility-adjacent
   vs. observation-inclusion-adjacent missingness).

9. **Current recorded ledger count, proposed configuration count, and
   conditional prospective total**: current recorded count is **6**
   (`lead_lag/trial_ledger.json`, re-verified, unchanged). Proposed
   configurations: **2** (`basket_construction:option1_full_completeness`,
   `basket_construction:option2_frozen_subset_fallback`), neither
   registered nor empirically examined. Conditional prospective total:
   **8**, contingent on approval, registration, and each configuration
   subsequently satisfying the existing trial definition -- never
   described anywhere in this document as the current actual count.

10. **Confirmation that multiplicity-family membership remains OPEN and
    committed alpha remains `0.05/6`**: confirmed. Section 10 states
    explicitly that neither of the two readings of family membership (the
    two basket-construction configurations inside vs. outside the
    propagation-hypothesis family) is adopted, and that the existing
    `alpha = 0.05/6` (Section 15 of `9f71b65`) is unchanged and not
    silently replaced with `0.05/8` anywhere in this document.

11. **Updated decision-table tally**: 6 APPROVED (rows 1-6), 1
    RECOMMENDED (row 18), 14 OPEN (rows 7-17, 19-21). 21 rows total --
    **unchanged from every prior revision**, since this round changed row
    *content* (rows 10, 16) but authorized no status change, per the
    governing constraint.

12. **Confirmation that all 21 rows and all status labels remain
    intact**: confirmed by direct inspection of the finished table --
    row count is 21; no row's APPROVED/RECOMMENDED/OPEN label differs
    from the prior revision.

13. **Confirmation that protected files were not edited**:
    `PREREGISTRATION_LEAD_LAG_V1.md`, `lead_lag/trial_ledger.json`,
    `lead_lag/MASTER_SPEC_LEAD_LAG.md`, and `PROJECT_CONTEXT.md` were
    confirmed present at the start of this task and were read-only
    throughout; none was written to; the committed `alpha` value was not
    changed.

14. **Explicit confirmation that no measurement, query, data fetch,
    emulation, outcome inspection, registration, Phase 4 work, commit, or
    push occurred**: none occurred. No missingness emulation, ACF or
    bootstrap calculation, power calculation, corporate-action bar
    inspection, project-wide dividend inventory, `MIN(ts)` query, or any
    other historical data query was run. No trial was registered. No
    alpha value was changed. Nothing was committed or pushed. No second,
    competing proposal file was created -- this document was revised and
    appended to in place.

**Stopping here. Waiting for explicit human review before any further
action. This is not authorization to begin feasibility work, trial
registration, or Phase 4.**
