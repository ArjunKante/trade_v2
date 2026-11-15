# Lead-Lag Documentation Reconciliation — Decision 13 Approval and Momentum_F Session-Boundary Rule

**Date**: 2026-11-14 (originally written); **updated twice, same day**. A
second task approved Decisions 10, 10, and (incorrectly) claimed Decision
11 was approved (Sections 1, 6, 7, 8, and 13 carried that update — see
Section 13). **A third, documentation-repair task then found that Decision
11 was never actually approved by the user and corrected the record**
(Sections 1, 7, 8, 13.2, 13.3, 13.6, and new Section 15 carry this
correction — see Section 15 for the complete, dated record). **Current,
authoritative status, as of the most recent correction**: Decision 10 —
APPROVED (70%); Decision 11 — **OPEN** (never approved; the second
update's claim otherwise was a documentation error, now corrected);
Decision 13 — APPROVED; Decision 22 — APPROVED, with its minimum-anchor
arithmetic conditional on Decision 11 (not unconditional).
**Family**: Cross-Liquidity-Tier Return Propagation (lead-lag)
**Type**: Documentation-only reconciliation. No Phase 4 code was written. No
strategy, regression, gate, backtest, or outcome analysis was run. No new
data was fetched. `lead_lag/trial_ledger.json` was not modified. Neither
Decision-14 audit report nor the monthly-roster audit report was modified.

---

## 1. Executive summary

Two objectives, both completed:

1. **Decision 13 (the exact endpoint-price return convention) is now
   recorded as APPROVED, 2026-11-14**, consistently across
   `PREREGISTRATION_LEAD_LAG_V1.md` (new AMENDMENT 4 LOG + a new Section 23
   row) and `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` (Section 4E
   status update + decision-table row 13 status update). The historical
   preregistration text (Section 8/9's sum-of-per-bar construction and its
   worked measurements) is **unchanged and preserved** as the historical
   record of what was actually computed; the new convention is recorded as
   governing **prospectively**, for Phase 4 implementation not yet written.
2. **The Momentum_F(t) early-session endpoint conflict is resolved with an
   explicit, enforceable same-session eligibility rule.** It was first
   recorded as a proposal (decision item 22 in the proposal's decision
   table; a new subsection of the preregistration's AMENDMENT 4 LOG), and
   is **now APPROVED, 2026-11-14**, with one wording refinement to its
   exclusion clause (Section 6 below).

**Update, same day, 2026-11-14 (Section 13 below has the full record)**:
one further decision was approved after the above was first written --
**Decision 10** (follower-basket breadth floor frozen at 70%).

**Correction, same day, 2026-11-14 (Section 15 below has the full
record)**: Section 13 below, as originally drafted, also claimed
**Decision 11** (`09:15` confirmed as the sole first-bar anchor) had been
approved, and that this made Decision 22's minimum-anchor figure
unconditional at `09:50`. **Both claims were incorrect. The user never
approved Decision 11. It remains OPEN, and Decision 22's minimum-anchor
figure remains the original two-branch conditional (`09:50` if `09:15`;
`09:51` if `09:16`), not a single unconditional value.** Decision 22's
approval of the same-session exclusion rule itself is unaffected and
stands.

No Phase 4 implementation, strategy calculation, data analysis, or gate was
performed. This is a documentation reconciliation only.

---

## 2. Exact user approval evidence and date for Decision 13

The task instruction that initiated this reconciliation states, verbatim:
*"The user explicitly approved the exact endpoint-price return convention
on 2026-11-14... The approval is a settled user decision. It must not be
treated as OPEN or presented for approval again."* This is the evidence
this reconciliation acts on. The exact approved formula, as given:

```
r_i(a,b) = P_i(b) / P_i(a) - 1          [per frozen-eligible constituent]
```
then the arithmetic mean across the frozen eligible constituents, applied
consistently to `R_L(t)`, `R_F(t)`, `Y(t,h)`, and `Momentum_F(t)`. A price
return, not a total return; dividends excluded. This reconciliation did not
independently re-derive or re-justify this approval — it records it, per
the task's own instruction that it "must not be treated as OPEN."

---

## 3. Before/after documentation status for Decision 13

| Document | Before | After |
|---|---|---|
| `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 4E | "Unchanged: RECOMMENDED, not APPROVED (Decision 13)." | **STATUS UPDATE (2026-11-14): APPROVED.** Original wording preserved below, labeled historical. |
| `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 11, row 13 | Status cell: `**OPEN** (technically recommended, not approved)` | Status cell: `**APPROVED, 2026-11-14**` with the original wording preserved parenthetically in the same cell; "Approval required?" column changed from "Yes" to "No -- already approved"; "Freeze point" changed from "Before data analysis" to "Prospective, Phase 4 implementation" |
| `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`, decision-table tally sentence | "6 APPROVED..., 1 RECOMMENDED..., 14 OPEN..., 21 rows total." | New tally added above it (7 APPROVED including row 13, 1 CLOSED/APPROVED [row 16], 1 RECOMMENDED, 13 OPEN including new row 22, 22 rows total); **the original tally sentence is preserved immediately below, explicitly labeled historical and no longer current — not deleted.** |
| `PREREGISTRATION_LEAD_LAG_V1.md` | No mention of Decision 13 anywhere; Section 8/9 described only the historical sum-of-per-bar construction | New AMENDMENT 4 LOG section records Decision 13 as APPROVED, with exact formula, date, and scope (applies to all four quantities); new Section 23 row records the approved convention as a frozen parameter; Status section gains a new "Amendment 4 drafted..." paragraph |
| `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md` | States Decision 13's convention is "untouched" by that audit | **Not modified by this reconciliation**, per the task's explicit boundary. Its own historical references to Decision 13 remain exactly as written — they were accurate observations about Decision 13's status in the audit's own scope (the price-level raw/adjusted question), not about the return-convention approval question, and are not affected by this reconciliation either way. |
| `lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` | States Decision 13 is "OPEN (technically recommended, not approved)" as of that audit's writing, and recommends resolving it | **Not modified**, per the task's explicit boundary. This was an accurate historical observation at the time that audit was written — it is not retroactively rewritten. This reconciliation report is the "separate, dated supersession note" the audit's own Section 7 and Section 11 anticipated might be needed. |

---

## 4. Historical versus prospective return-convention description

**Historical, registered, unchanged**: `PREREGISTRATION_LEAD_LAG_V1.md`
Section 8 (as amended 2026-11-08, fixing the original degeneracy) defines:
```
S_i(t) = sum_{k=t-4}^{t} AR_leader(i,k)      [sum of five 1-minute per-bar abnormal returns]
AR_leader(i,k) = r(i,k) - B_follower_pool(k)
S_leader(t) = (1/n_t_return) * sum_i S_i(t)
```
This text, its surrounding derivation, and its one reported real-data
measurement (diagnostic substitute sigma = 3.92 bps, Section 8) are **not
edited by this reconciliation**. They remain the accurate record of what
this family's documents actually specified and what was actually measured
before 2026-11-14.

**Prospective, approved 2026-11-14, governs Phase 4 going forward**:
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Sections 4 and 6 define
`R_L(t)`, `R_F(t)`, `Y(t,h)`, and `Momentum_F(t)` using the exact
endpoint-price convention (Section 2 above). This is now the approved
convention for any Phase 4 implementation not yet written. **No code
implementing either convention exists anywhere in this repository** —
confirmed by the repository-wide search already performed in
`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` Section 2,
not re-run here. This reconciliation does not change that fact; it
clarifies which convention Phase 4 code should implement when written.

**What is explicitly not claimed**: that the historical construction was
"wrong," that it is retired, or that any already-reported real-data number
should be recomputed. Only a prospective governing choice is recorded.

---

## 5. Exact Momentum_F(t) endpoint arithmetic

Per `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 6:
```
Momentum_F(t) = (1/n_followers) * sum_j [ P_j(t-5) / P_j(t-35) - 1 ]
```
Under the Decision 13 exact-endpoint convention, this requires exactly two
price observations per constituent `j`: one at clock time `t-35` (start
endpoint) and one at clock time `t-5` (end endpoint) — not a cumulative sum
over the 30 intervening bars, despite the proposal's own prose describing
the window as "30 one-minute bars" (a phrasing inherited from this
construction's framing as a disjoint window, not from the exact-endpoint
arithmetic itself; flagged, not silently corrected, in the proposal's own
Section 6 via a new status-update note — see Section 9 below).

**The conflict**: the earliest documented signal-window anchor is
`t = 09:19` (if `09:15` is the first valid regular-session bar) or
`t = 09:20` (if `09:16` is first valid instead) — `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 5. For either candidate, the required `Momentum_F` start endpoint
at `t-35` lands at approximately `08:45` or `08:46` — **before the regular
session opens under either candidate first-bar convention.** No bar exists
there. Neither document that defines the anchor (Section 5) or the
momentum window (Section 6) cross-references the other's requirement; this
is a genuine specification gap, not a coding question.

---

## 6. Same-session eligibility and exclusion rule — APPROVED, 2026-11-14 (Decision 22)

First recorded as a proposal (matching the task's own specification) as
new decision item **22** in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 11, and as a new subsection of `PREREGISTRATION_LEAD_LAG_V1.md`'s
AMENDMENT 4 LOG. **Now approved**, by explicit user decision on
2026-11-14, with rule 6 restated for precision (Section 13 below has the
full before/after):

1. Both `Momentum_F(t)` endpoints must be valid observations belonging to
   the same trading session and the same trade date.
2. Both endpoints must satisfy the applicable Decision 17 endpoint-validity
   rules.
3. No cross-session endpoint pairing is permitted.
4. No previous-session fallback, nearest-available-bar substitution across
   a session boundary, clamping, padding, or silent endpoint replacement is
   permitted.
5. If either required endpoint is unavailable or invalid, `Momentum_F(t)`
   is unavailable for that observation.
6. **The observation is excluded from the primary regression sample. No
   null-control observation is retained in its place, and no value is
   imputed or substituted.** *(Restated for precision at approval -- the
   original proposed wording, "excluded under the frozen eligibility
   policy — no imputation or substitution," is preserved here as the
   historical text this restatement refines, not reverses.)*
7. The same frozen follower basket and constituent-eligibility rules
   continue to apply; no future-informed constituent replacement or
   reweighting is authorized by this rule.

**Approval status: APPROVED, 2026-11-14 — Decision 22.** This is a settled
user decision and is not presented for approval again. *(Historical,
preserved: this rule's status at the time this section was first written
was "OPEN, PROPOSED 2026-11-14 — NOT YET APPROVED.")*

---

## 7. Conditional earliest-anchor derivation

Derived from the endpoint requirement alone (`t-35` must be at or after
the first valid regular-session bar), exactly as instructed:

- **If `09:15` is the first valid regular-session bar**: `t - 35 >= 09:15`,
  so `t >= 09:15 + 35 minutes = 09:50`. **Earliest possible anchor: `09:50`.**
- **If `09:16` is the first valid regular-session bar instead**:
  `t - 35 >= 09:16`, so `t >= 09:51`. **Earliest possible anchor: `09:51`.**

These matched the figures given in the original task instruction exactly;
no discrepancy was found between that instructed arithmetic and a direct
re-derivation from the endpoint definitions in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 6.

**CORRECTED, 2026-11-14 (same day, Section 15 below has the full record)**:
an intermediate version of this section stated "Decision 11 is now
APPROVED at `09:15`" and declared the first branch above operative and
unconditional. **That was incorrect. The user never approved Decision 11.
It remains OPEN.** Both branches above remain live and conditional:
**`09:50`** if `09:15` is the first valid regular-session bar, **`09:51`**
if `09:16` is first valid instead. Neither is chosen. The pre-existing
inconsistency this section originally flagged -- between
`PREREGISTRATION_LEAD_LAG_V1.md`'s passing "approved `09:20` anchor"
reference and several Decision 10/17 documents stating Decision 11
remained open -- is **not resolved** and remains exactly as originally
described here; the intermediate claim that it had been resolved is
retracted.

**`09:50` (or `09:51`) is a conditional lower bound on `t` only, in either
branch** — it does not guarantee a complete follower basket, valid
signal-window endpoints, or a valid `Y(t,h)` forward endpoint at that
minute; it establishes only the earliest time at which the `Momentum_F`
endpoint requirement *can* be satisfied, in whichever branch is eventually
approved. If either endpoint fails validity, the observation is still
excluded (Section 6, rule 6) regardless of which branch applies.

---

## 8. Decisions still requiring user approval

**UPDATE, 2026-11-14 (same day)**: Decisions 10 and 22, listed as open in
this section when it was first written, are **now APPROVED** -- see
Section 13 below for the record. **CORRECTION, 2026-11-14 (same day,
Section 15 below has the full record)**: an intermediate version of this
update also listed Decision 11 as now approved. **That was incorrect.
Decision 11 was never approved by the user and remains OPEN** -- it is
restored to this list below, exactly as this section originally (and
correctly) stated.

Explicit current list, so none is mistaken for already-settled:

1. **Decision 11 (exact session anchor, `09:15` vs. `09:16`, and the
   resulting `09:19`/`09:20` vs. `09:20`/`09:21` signal anchor; and, by
   consequence, Decision 22's `09:50`/`09:51` `Momentum_F` minimum anchor)
   — remains OPEN**, and still inconsistently described across repository
   documents in the sense that one pre-existing passing reference in
   `PREREGISTRATION_LEAD_LAG_V1.md` calls the `09:20` anchor "approved" --
   that pre-existing imprecision is noted, not resolved, by this
   reconciliation or its correction.
2. Every decision item already marked OPEN in
   `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 11 that this
   reconciliation did not touch (items 7, 8, 9, 12, 14, 15, 17, 19, 20,
   21) — **unaffected and unchanged** by this reconciliation. (Item 15,
   the effect-size-hurdle/sign-rule decision, remains OPEN and is
   explicitly out of this reconciliation's scope — a later
   documentation-repair task addressed its treatment in the
   preregistration separately.)
3. Decision 14's own standing recommendation that
   `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`'s stale pre-Decision-14
   "likely raw" framing (Section 4B) be corrected — **out of this
   reconciliation's scope and not touched here.**

**Already approved, not reopened**: Decision 13 (Section 3-4 above);
Decision 10 (Section 13 below); Decision 22 (Section 6 above, Section 13
below -- exclusion rule only; its anchor arithmetic remains conditional on
the still-open Decision 11, item 1 above); Option A portfolio-level
estimand (decision item 1 of the proposal's table, unaffected); Decision
16's multiplicity/alpha accounting (unaffected).

*(Historical, preserved: this section's original list, as first written,
read: "1. Decision 22 (Momentum_F same-session rule, Section 6 above) —
OPEN, proposed, awaiting approval. Not approved by this reconciliation. 2.
Decision 11 (exact session anchor, `09:15` vs. `09:16`...) — remains OPEN,
unchanged by this reconciliation, and still inconsistently described
across repository documents (noted, not resolved)." Decision 22 has since
been approved (Section 13); Decision 11's original statement above was, in
fact, correct all along, and is restored as current, not merely
historical.)*

---

## 9. Files modified and why

| File | Change | Why |
|---|---|---|
| `PREREGISTRATION_LEAD_LAG_V1.md` | New "AMENDMENT 4 LOG" section (after AMENDMENT 3 LOG, before Section 0); one new row in Section 23's frozen-parameters table; one new paragraph in the closing "Status" section | Record Decision 13's approval and Decision 22's proposal in the governing preregistration, following the document's own established amendment-log pattern (Amendments 2 and 3) |
| `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` | Section 4E: added a dated status-update note (original text preserved below it); Section 6 (Momentum_F): added a dated status-update note clarifying the two-endpoint convention and flagging the conflict; Section 11: updated row 13's status cell, added new row 22, added an updated tally with the original tally preserved as historical | Correct the stale Decision 13 status everywhere it appeared in this document, and record the new Momentum_F proposal in the same decision-table structure the document already uses |
| `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md` | New file (this report) | Required deliverable |

**Not modified, per the task's explicit boundaries**: `lead_lag/MASTER_SPEC_LEAD_LAG.md`
(checked — contains no reference to Decision 13 or `Momentum_F`, so nothing
to reconcile there); `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`;
`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md`;
`lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`; `lead_lag/trial_ledger.json`;
`lead_lag/ledger.py`; any source code; any other strategy family's files.

---

## 10. Consistency-check results

Checked, after editing, for contradictory statuses/formulas/wording across
the preregistration, proposal, and master specification:

- **Decision 13 status**: now reads APPROVED, 2026-11-14 consistently in
  both live governing documents (preregistration AMENDMENT 4 LOG + Section
  23; proposal Section 4E + Section 11 row 13). No remaining document
  describes it as "merely recommended," "pending approval," or
  "technically recommended but unapproved" — **except** the two
  Decision-14-family audit reports, which are explicitly exempted from
  editing and whose historical statements remain accurate for the point in
  time they describe.
- **Exact endpoint-price return formula**: stated identically in both live
  documents (`r_i(a,b) = P_i(b)/P_i(a) - 1`, mean across frozen
  constituents, price return, dividends excluded).
- **Sum-of-per-bar return (historical)**: preserved, unedited, in
  `PREREGISTRATION_LEAD_LAG_V1.md` Section 8/9, now explicitly labeled
  historical/superseded-prospectively in the new AMENDMENT 4 LOG and the
  new Section 23 row. No contradiction — both are present, each correctly
  labeled with its own temporal scope.
- **`R_L(t)`, `R_F(t)`, `Y(t,h)`, `Momentum_F(t)`**: all four are named
  consistently in the Decision 13 approval text in both documents.
  `Momentum_F(t)`'s own window and endpoint description in the proposal's
  Section 6 is annotated (not changed) to clarify the two-endpoint reading
  under the now-approved convention.
- **`09:19`/`09:20`**: unchanged wherever it appears; now explicitly
  cross-referenced from the new Momentum_F material as "the bare
  signal-window anchor, not sufficient for `Momentum_F`."
- **`09:50`/`09:51`**: newly introduced, consistently in both documents and
  this report, with identical conditional derivation in all three places.
- **Same-session endpoint requirements**: newly stated, consistently, as
  decision item 22 (proposal) and the AMENDMENT 4 LOG's proposed-rule
  subsection (preregistration) — both unapproved, both identical in
  substance.
- **15:30 forward-window exclusion (`Y(t,h)`)**: **not modified**, per the
  task's explicit instruction. Its existing wording in
  `PREREGISTRATION_LEAD_LAG_V1.md` Section 12 is accurate as far as it
  goes ("final-5-minutes-before-close signal-end minutes whose forward
  window would cross 15:30") but does not explicitly state, in so many
  words, that the forward endpoint must remain within the *same regular
  trading session* or that no next-session fallback is permitted — it is
  phrased as a minute-exclusion rule, not an endpoint-pairing rule. **A
  narrowly scoped wording clarification is proposed here, in this report
  only, not applied to the source document**: *"...signal-end minutes
  whose forward window would cross 15:30 — equivalently, the forward
  endpoint `P(t+h)` must be a same-regular-session observation; no
  next-session fallback or cross-session endpoint pairing is permitted for
  any horizon `h`."* This is a wording-precision suggestion only; the
  anchor, horizons, and primary-gate designation are unchanged, and no
  edit was made to Section 12 itself, per the task's explicit boundary.
- **No other contradictions found** between the preregistration, the
  proposal, and `lead_lag/MASTER_SPEC_LEAD_LAG.md` (which contains no
  reference to Decision 13 or `Momentum_F` at all, confirmed by direct
  grep, so there was nothing there to reconcile).

---

## 11. Remaining implementation requirements for Phase 4

Not implemented here; recorded for whoever eventually writes Phase 4 code.
**[UPDATED, 2026-11-14, twice, same day: item 1 below is superseded --
Decision 22 is now approved, per Section 13.3/15. Item 2 was briefly
thought superseded by the same update, then found to still apply --
Decision 11 was never actually approved and remains genuinely open; see
Section 15.]**

1. ~~Decision 22 (Section 6/8 above) must be explicitly approved or
   rejected before Phase 4 code implements `Momentum_F(t)`'s endpoint
   lookup.~~ **Resolved: Decision 22 is approved (Section 13.3/15).** Its
   minimum-anchor arithmetic is still conditional on item 2 below.
2. **Decision 11 (exact session anchor) must be resolved — independently
   of this reconciliation — before any anchor-dependent code (signal
   window, `Momentum_F`, or the forward horizon schedule) can be written
   with certainty about its earliest valid observation. This remains true
   and unresolved as of the most recent correction (Section 15).**
3. No code exists anywhere in this repository implementing `R_L(t)`,
   `R_F(t)`, `Y(t,h)`, or `Momentum_F(t)` under either the historical or
   the newly approved convention (reconfirmed, not re-run, from
   `lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` Section
   2). Whatever convention and whichever rule set governs by the time
   Phase 4 is written, it must be implemented from scratch and verified
   against this reconciliation's recorded formulas and rules, not assumed
   correct by virtue of this document existing.
4. Every other OPEN decision item in
   `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 11 (control
   set, fixed-effects specification, NIFTY regime control, follower-side
   completeness threshold, bootstrap block-length parameters, effect-size
   sign rule, missing-data compatibility rule, Option 1-vs-2 basket
   choice, corporate-action handling, special-session verification) remains
   open and is unaffected by this reconciliation.

---

## 12. Final verification

**HEAD before**: `9f71b65e006f937760e39a9f65035c69a1ef8df9`

**Working-tree status before** (identical to the end state of the prior
Decision-14-follow-up audit):
```
 M PREREGISTRATION_LEAD_LAG_V1.md
?? LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md
?? lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md
?? lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md
?? lead_lag/DECISION_10_RECONCILIATION_ADDENDUM.md
?? lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md
?? lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md
?? lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md
?? lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md
?? lead_lag/DECISION_17_REPRODUCIBILITY_AUDIT.md
?? lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md
?? lead_lag/METHODOLOGY_PROPOSAL_2026-11-08_PORTFOLIO_LEVEL_ESTIMAND.md
?? lead_lag/METHODOLOGY_REVIEW_2026-11-08_ESTIMAND_AND_NULL.md
?? lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md
```

**Files modified by this reconciliation**: `PREREGISTRATION_LEAD_LAG_V1.md`
(already modified in the working tree before this task began, per the
status above — this reconciliation adds further edits to the same
pre-existing modified file) and `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
(already untracked/new in the working tree before this task began — this
reconciliation edits that same file in place, it does not newly create
it).

**Files newly created by this reconciliation**: exactly one —
`lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`.

**No unrelated file was changed.** `lead_lag/MASTER_SPEC_LEAD_LAG.md`,
`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`,
`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md`,
`lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`, `lead_lag/trial_ledger.json`,
`lead_lag/ledger.py`, and all other files were read only or not touched at
all.

**No code or data analysis executed**: no database connection was opened;
no strategy, regression, gate, backtest, predictive-performance, beta, or
significance computation was run; no trial was registered or counted.

**Git verification, run immediately after writing this report**: see the
command output quoted in the final response to the user (HEAD after,
`git status --short` after, `git diff --check`). No staging, commit,
branch, or push occurred.

---

## 13. Update, 2026-11-14 (same day) — Decisions 10, 11, and 22 approved

A second task, received the same day as the original version of this
report, carried three further explicit user approvals. This section is
the authoritative record of that update; Sections 1, 6, 7, and 8 above
were each edited (not silently) to point here and to stop asserting that
Decision 11 or Decision 22 was still open.

### 13.1 Decision 10 — APPROVED: follower-basket breadth floor frozen at 70%

Definition, exactly as approved: present-valid observations only count
(forward-filled/absent bars never count as present); `n_t_return` for
actual return construction remains governed, unchanged, by Decision 17's
existing endpoint-validity rules; the governing trading-session calendar
is the already-established 2,457-date calendar (the 2,468 raw archive
dates less the 11 verified non-regular-session dates, with the 4 genuine
weekend special-trading-session dates remaining included); the existing
holiday-calendar verification methodology
(`src/data_layer/nse_holidays.py` + `data/raw/nse_cm_holidays.pkl`, plus
explicit special-session verification) is unmodified and reused exactly.
No underlying data was recomputed and no calendar methodology was altered
to produce this approval -- it freezes a numeric threshold onto rules and
a calendar that already existed.

This was never a decision item in this report's original Sections 1-12
(it only appeared obliquely, via the preregistration's own "70%
follower-breadth candidate... remains open" language, not as a named
section here). It is recorded here for the first time in this report.

### 13.2 Decision 11 — RETRACTED CLAIM: was never approved; remains OPEN

**This subsection originally claimed `09:15` was confirmed as the sole
first valid regular-session bar, approved by the user. That claim was
false and is retracted — see Section 15 for the full correction.** No
such user decision was ever made. `09:16` has not been ruled out. The
non-overlapping sampling anchor therefore remains the pre-existing
two-branch conditional (`09:20`/`t=09:19` if `09:15`; `09:21`/`t=09:20` if
`09:16`) in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 5,
neither branch chosen.

The inconsistency Section 7 above originally flagged -- between
`PREREGISTRATION_LEAD_LAG_V1.md`'s passing "approved `09:20` anchor"
reference and several Decision 10/17 documents stating Decision 11
remained open -- is **not resolved** by this report and was never
genuinely resolved by the erroneous claim this subsection previously made.
The Decision 10/17 documents that state Decision 11 is open
(`lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md`,
`lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md`,
`lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md`) are **not modified
by this reconciliation** -- they were, and remain, accurate.

### 13.3 Decision 22 — APPROVED, with the rule-6 exclusion clarification; anchor remains conditional

Approved exactly as proposed in Section 6 above, with one wording
refinement to rule 6: the exclusion is now specified as removal **from
the primary regression sample**, with an explicit statement that **no
null-control observation may be retained** in its place (in addition to
the original rule's prohibition on imputation or substitution). This is
a precision addition to the proposed text, not a reversal of its intent
— the original proposal already required exclusion with no imputation or
substitution; this refinement only names where the exclusion applies and
forecloses one specific alternative (null-control retention) the original
wording did not explicitly address. **This exclusion-rule approval is
unaffected by the Section 13.2 correction and stands.**

**CORRECTED (2026-11-14, same day, Section 15 below has the full
record)**: this subsection previously claimed that, "given Decision 11's
approval," the minimum-anchor arithmetic became unconditional at
`t >= 09:50`. **Decision 11 was never approved, so that claim is
retracted.** The minimum-anchor arithmetic remains the original two-branch
conditional: `t >= 09:50` if `09:15` is the first valid regular-session
bar; `t >= 09:51` if `09:16` is first valid instead. Neither branch is
chosen. This remains a lower time bound only, in either branch, never a
guarantee of basket or endpoint validity at that minute -- an invalid or
unavailable endpoint still excludes the observation under rule 6,
regardless of `t`.

### 13.4 Decision 13 — reaffirmed, not reopened or duplicated

Per the task's own instruction to verify the existing reconciliation
before making changes: Sections 2-4 above (Decision 13's approval,
formula, and scope) were re-read in full before this update. **No
contradiction or omission was found.** Decision 13 is not re-derived,
re-approved, or duplicated by this update -- it stands exactly as
recorded in the original version of this report.

### 13.5 Files touched by this update

- `PREREGISTRATION_LEAD_LAG_V1.md`: new "AMENDMENT 5 LOG" section (Decisions
  10, 11, 22 approvals, Decision 13 reaffirmed); four new rows in Section
  23's frozen-parameters table (70% follower-breadth floor; `09:15`
  first-bar fact; `09:20` derived anchor; `09:50` `Momentum_F` minimum
  anchor); dated status-update notes added inline at the three locations
  that previously described Decision 10 as open/candidate and at the two
  locations describing Decision 11/22 as open (AMENDMENT 2 LOG and
  AMENDMENT 4 LOG's own closing paragraphs, and the Status section); a new
  "Amendment 5 drafted..." closing-status paragraph. **No historical
  sentence was deleted or rewritten** -- each received an adjacent, dated
  bracketed status-update note instead.
- `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`: Section 5 (anchor
  derivation) annotated with dated status-update notes at three points,
  original hedged text preserved; Section 6 (Momentum_F) given a further
  dated status-update note; Section 11's decision table rows 10, 11, and
  22 updated to APPROVED (each cell preserving its original status text
  parenthetically); a second, superseding tally added (the first tally
  update and the original Revision-6 tally are both preserved below it,
  unedited); the Section-11 preamble note and the separate closing
  "Updated APPROVED / RECOMMENDED / OPEN tally" checklist item (item 13 in
  that list) were each given a dated status-update note; the "remaining
  unresolved methodological issue" checklist (item 14 in that same list)
  was given a dated status-update note identifying which two of its items
  are now resolved.
- `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md` (this
  file): updated in place -- Sections 1, 6, 7, and 8 restated to stop
  describing Decision 11/22 as open; this Section 13 added as the
  authoritative record of the update; Section 9 and Section 12 (below)
  updated to list this round's edits.

**Not modified**: `lead_lag/MASTER_SPEC_LEAD_LAG.md` (re-checked; still
contains no reference to Decision 10, 11, 13, 22, or `Momentum_F` -- there
is nothing in it to reconcile, and per the task's own instruction, a
master-spec edit is not made without stopping to report why first; no such
necessity was found); `lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md`,
`lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md`,
`lead_lag/DECISION_10_RECONCILIATION_ADDENDUM.md`,
`lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md`,
`lead_lag/DECISION_17_REPRODUCIBILITY_AUDIT.md`,
`lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md` (all historical
audit/feasibility artifacts; a dated supersession note in the governing
documents and this report is preferred over rewriting their conclusions,
per the task's own instruction, and none of them is a governing document
whose contradiction would otherwise force an edit); `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`;
`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md`;
`lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`; `lead_lag/trial_ledger.json`;
`lead_lag/ledger.py`; any source code; any other strategy family's files.

### 13.6 Consistency re-check after this update — SUPERSEDED, see Section 15

**This subsection's claims below were invalidated by the Decision 11
correction recorded in Section 15. Preserved unedited for provenance, not
deleted; do not rely on this version — see Section 15.6 for the corrected
re-check.**

*(Original, now-superseded text)*: "Every governing reference to the
first-bar anchor now identifies `09:15` as the sole anchor... `Momentum_F(t)`'s
same-session rule and its now-unconditional `09:50` minimum anchor are
stated consistently... No contradictory status was found remaining in the
preregistration, the proposal, or this report after this update..." **This
was incorrect**: governing references did not, in fact, consistently
identify `09:15` as approved (because it never was), and the "unconditional
`09:50`" claim was itself one of the contradictions, not an absence of
one.

---

## 14. Final verification for this update (2026-11-14, same day)

**HEAD before this update**: `9f71b65e006f937760e39a9f65035c69a1ef8df9`
(unchanged from Section 12 above).

**Files modified by this update**: `PREREGISTRATION_LEAD_LAG_V1.md`,
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`, and this file
(`lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md`) -- all three
already existed and were already modified/untracked before this update
began; no new file was created by this update.

**No other file was touched.** See Section 13.5's explicit "Not modified"
list.

**No code or data analysis executed** in this update: no database
connection was opened; no strategy, regression, gate, backtest,
predictive-performance, beta, or significance computation was run; no
trial was registered, counted, or added to `lead_lag/trial_ledger.json`.

**Git verification, run immediately after this update**: see the command
output quoted in the final response to the user for this task (HEAD
after, complete `git status`, `git diff --check` summary). No staging,
commit, branch, or push occurred.

---

## 15. Correction, 2026-11-14 (same day) — Decision 11 was never approved; corrected back to OPEN

A third task, a documentation-integrity repair, found that Section 13
above (and the places it updated in the two governing documents)
incorrectly recorded Decision 11 as approved at `09:15`. **The user never
approved Decision 11. This section is the authoritative record of the
correction.**

### 15.1 What was wrong

Section 13.2 above stated `09:15` was "confirmed as the sole first valid
regular-session bar... by explicit user decision." **No such decision was
made.** This false claim propagated into: Section 1 (executive summary),
Section 7 (anchor derivation, claimed "unconditional"), Section 8
(decisions-requiring-approval list, dropped Decision 11), Section 11
(implementation requirements, implied Decision 11 was resolved),
Section 13.3 (Decision 22's minimum anchor, claimed "unconditional
`t>=09:50`"), and Section 13.6 (consistency re-check, asserted no
contradiction existed). Each of these is corrected above, in place, with
the erroneous text preserved and marked retracted rather than deleted.

The same false claim was independently introduced into both governing
documents during the same second task, and is separately corrected there:

- `PREREGISTRATION_LEAD_LAG_V1.md`: AMENDMENT 5 LOG's title, opening
  status paragraph, and chronology; Section 2 ("Decision 11 -- APPROVED");
  Section 3 ("now unconditional" `Momentum_F` anchor); Section 4 (Section
  23 update description); the Section 23 table's "First valid
  regular-session bar" and "Non-overlapping sampling anchor" rows; the
  inline bracketed annotations added to AMENDMENT 2 LOG and AMENDMENT 4
  LOG's "what this does NOT do" paragraphs; and the Status section's
  Amendment 4 and Amendment 5 closing paragraphs. All corrected in place,
  original erroneous text preserved and marked retracted, per the same
  "do not silently erase the history of the mistake" instruction this
  report itself follows.
- `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`: two "STATUS UPDATE"
  notes in Section 5 (anchor derivation) and one in the "How the schedule
  interacts with session structure" subsection; the "FURTHER STATUS
  UPDATE" in Section 6 (Momentum_F); decision-table row 11 (reverted to
  OPEN) and row 22 (kept APPROVED, anchor text reverted to conditional);
  the "FURTHER UPDATE" paragraph above Section 11's table; the "Second
  tally" (corrected into a new "Third tally," with the erroneous one
  preserved as historical); and the closing checklist's two status-update
  notes (items 13 and 14). All corrected in place, same preservation
  discipline.

### 15.2 What is restored, exactly

| Decision | Status before this correction (wrong) | Status after this correction (right) |
|---|---|---|
| 10 | APPROVED, 70% | **Unaffected — still APPROVED, 70%** |
| 11 | APPROVED, `09:15` sole anchor | **OPEN — never approved; `09:15` vs. `09:16` unresolved** |
| 13 | APPROVED | **Unaffected — still APPROVED** |
| 22 (exclusion rule) | APPROVED | **Unaffected — still APPROVED** |
| 22 (minimum anchor) | Unconditional, `t>=09:50` | **Conditional: `t>=09:50` if `09:15`; `t>=09:51` if `09:16`** |
| Non-overlapping sampling anchor (`Y`/signal window) | Unconditional, `09:20` | **Conditional: `09:20` if `09:15`; `09:21` if `09:16`** |

### 15.3 Files touched by this correction

- `PREREGISTRATION_LEAD_LAG_V1.md`: all locations listed in Section 15.1
  above, corrected in place with retraction notices; no historical
  sentence deleted.
- `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`: all locations listed
  in Section 15.1 above, corrected in place with retraction notices; no
  historical sentence deleted.
- `lead_lag/DECISION_13_AND_MOMENTUM_ANCHOR_RECONCILIATION.md` (this
  file): Sections 1, 7, 8, 11, 13.2, 13.3, 13.6 corrected in place; this
  Section 15 added as the authoritative correction record.

**Not modified**: everything listed as "Not modified" in Section 9 and
Section 13.5 above remains not modified by this correction either --
`lead_lag/MASTER_SPEC_LEAD_LAG.md`, every Decision 10/14/17/roster audit
report, `lead_lag/trial_ledger.json`, `lead_lag/ledger.py`, source code,
and other strategy families.

### 15.4 Decision 15 (effect-size hurdle / sign rule) — also addressed by this task, kept OPEN

This same documentation-repair task also added status-clarification notes
to `PREREGISTRATION_LEAD_LAG_V1.md` Sections 18, 20, and 23, making
explicit that Decision 15 (the `beta>0` sign rule and "effect-size hurdle"
interpretation of the 20bps floor) is **recommended by the proposal
(Section 11, decision item 15) but not approved by the user, and remains
OPEN.** The preregistration's Section 20 gate conditions 1-2 must not be
read as having already adopted the proposal's specific sign-rule
interpretation. The 20bps **number** itself is unaffected (original,
frozen project convention, not in question). Decision Table row 15 in
the proposal was not touched -- it already correctly read OPEN.

### 15.5 Forward-window session-boundary wording — clarified, no rule changed

`PREREGISTRATION_LEAD_LAG_V1.md` Section 12's existing forward-window
exclusion rule was annotated (not changed in substance) to state explicitly,
for any horizon `h`: a signal-end minute `t` is excluded if `t+h` would
require a bar at or after `15:30`; no next-session fallback or
cross-session endpoint pairing is permitted, mirroring Decision 22's
identical prohibition. One implementation clarification is flagged as
still required, not guessed at: whether `15:29` is confirmed as the actual
last regular-session bar on every date in the governing calendar has not
been independently verified (the close-side mirror of Decision 11's own
open first-bar question).

### 15.6 Consistency re-check, corrected (supersedes Section 13.6)

- Every governing reference to the first-bar anchor now identifies
  Decision 11 as **OPEN** -- confirmed by direct grep of both governing
  documents for "Decision 11" after editing; every remaining match is
  either the original correct "unresolved"/"OPEN" text, or a retraction
  notice pointing to this correction.
- `Momentum_F(t)`'s same-session exclusion rule (Decision 22) remains
  APPROVED everywhere it is stated; its minimum anchor is stated as
  **conditional** (`09:50`/`09:51`) everywhere it is stated, with no
  remaining "unconditional" claim found in either governing document
  after this correction.
- The non-overlapping sampling anchor for the bare signal window
  (`R_L`/`R_F`/`Y`) is likewise stated as conditional (`09:20`/`09:21`)
  everywhere it is stated.
- Decision 10, 13, and 22's exclusion-rule approvals are unaffected and
  remain consistent across both governing documents and this report.
- Decision 15 is explicitly OPEN in the preregistration's Sections 18, 20,
  and 23, and was already OPEN in the proposal's decision-table row 15,
  untouched.
- **Two incidental, non-asserting cross-references in the proposal**
  (pointing descriptively to "Section 5's `09:20`/`09:21` treatment,"
  without themselves claiming a status) were left unedited, exactly as
  noted in the now-superseded Section 13.6 -- they remain harmless for
  the same reason given there: Section 5 itself now carries the correct,
  conditional statement.

### 15.7 Final verification for this correction

**HEAD before this correction**: `9f71b65e006f937760e39a9f65035c69a1ef8df9`
(unchanged from Sections 12 and 14 above).

**No code or data analysis executed**: no database connection was opened;
no strategy, regression, gate, backtest, predictive-performance, beta, or
significance computation was run; no trial was registered, counted, or
added to `lead_lag/trial_ledger.json`; no master specification, source
code, or other strategy family's file was touched.

**Git verification, run immediately after this correction**: see the
command output quoted in the final response to the user for this task
(HEAD after, complete `git status`, `git diff --check` and `git diff
--stat`). No staging, commit, branch, or push occurred.
