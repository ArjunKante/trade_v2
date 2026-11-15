# Pre-Signal Frozen-Subset Eligibility vs. Forward-Endpoint Completeness — Methodology Reconciliation

**Date**: 2026-11-14
**Family**: Cross-Liquidity-Tier Return Propagation (lead-lag)
**Type**: Read-only methodology reconciliation. **No decision is made, resolved, or
reopened. No code is written. No roster is recalculated.** This report traces exact
governing text and reports exactly where it is complete, and exactly where it is not.

---

## 1. Executive conclusion

**CORRECTION NOTICE (2026-11-14, added by a documentation-correction task, same
day).** This section, as originally drafted, concluded that "Option 2 itself has not
been selected" and that Decision 19 "remains OPEN," relying on
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3C's own text in isolation.
**That conclusion was incomplete — it did not cross-check against
`PREREGISTRATION_LEAD_LAG_V1.md`'s AMENDMENT 3 LOG, item 3, which already records,
as a pre-existing human decision**: *"Option 2 (`basket_construction:option2_frozen_subset_fallback`)
was examined before registration and **subsequently selected as the
basket-construction methodology by human decision**. It is not a formal trial —
selection is not equivalent to a Phase 1 kill or to reaching a preregistered
predictive gate."* **Option 1 vs. Option 2 (Decision 19) — the basket-construction
*selection* — is therefore RESOLVED, not open.** This is an existing decision record,
not a new approval made by this correction. The original text is preserved below,
quoted, rather than deleted, so the record of the oversight is not lost.

**What is still correctly reported, and is NOT changed by this correction**: selecting
Option 2 as the governing construction does **not** resolve Option 2's own internal
parameters. The threshold *form* (count/fraction/both) and *value* remain OPEN
(`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3C's own text), and
**whether Decision 10's approved `70%` follower-breadth figure is the value intended
for Option 2's own step-4 threshold is NOT established by either document's text** —
Decision 10's own text (`PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 5 LOG Section 1) is
modeled on the leader-side per-minute `n_t_breadth` convention and never names "Option
2," "the frozen eligible subset," or this specific step. **This remains a genuine,
unresolved gap between an approved number and an unidentified parameter — narrower
than originally framed (the procedure itself is now known to be selected), but not
closed.**

*(Original text, preserved for provenance, superseded by the correction above)*:
"**The relationship between pre-signal eligibility and forward-endpoint completeness
is, itself, precisely and unambiguously specified** in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3C's 9-step "Option 2"
construction (quoted in full, Section 3 below). **But a load-bearing precondition for
that specification to govern anything is NOT yet satisfied: Option 2 itself has not
been selected.** The same document states explicitly, in the same section: *"Neither
Option 1 nor Option 2 is selected in this revision. Both remain OPEN (Decision 19)."*
This is still true as of this report — Decision 19 is not touched by any later
amendment read for this reconciliation.

A second, related finding: Decision 10's approved "70% follower-basket breadth
floor" ... [the remainder of the original "second finding" and "consequently"
paragraphs is superseded in substance by the corrected text above, which restates the
same underlying gap — the Decision-10-vs-Option-2-threshold identity question — without
the now-incorrect premise that Option 2's selection itself remains open]."

*(Original "Consequently, revised" paragraph, preserved for provenance, corrected by
the dated note immediately below — not deleted)*: "**Consequently, revised**:
`lead_lag/FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md`'s phrasing — *"the existing,
already-approved breadth floors"* — is **closer to accurate than this report
originally gave it credit for**, since Option 2 (the procedure those floors would be
checked under) is in fact the selected construction. That audit's residual
imprecision is narrower than this report originally claimed: it still did not
construct the Stage-A frozen eligible subset as its denominator (Section 6 below,
otherwise unchanged), and it still did not establish that Decision 10's `70%` is the
specific value Option 2's step 4 uses — but it did not overstate an unapproved
*procedure* the way this report's original Section 1 implied."

**DATED CORRECTION (2026-11-14, added by a second documentation-correction task, same
day).** The paragraph above, though it correctly flagged the two residual gaps
(denominator, and the `70%` identification), still read as a partial defense of the
audit's "already-approved breadth floors" phrasing — as if Option 2's selection
narrowed the gap between raw coverage and an eligibility verdict more than it
actually does. **It does not narrow that gap at all.** Stated precisely, distinguishing
every element the independent review asked to be kept separate:

1. **Decision 19 (Option 1 vs. Option 2 selection) is resolved** — Option 2 is the
   selected basket-construction methodology, per the existing human decision record
   in `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3. This is not reopened by
   this note.
2. **Option 2's own Stage-A threshold — its form (count/fraction/both), its
   numerical value, and its denominator convention — all remain OPEN.** Selecting
   Option 2 as the governing *procedure* says nothing about what number or
   denominator fills this blank.
3. **Decision 10's approved `70%` figure is not established as Option 2's own
   threshold.** It is an approved number on the follower side; whether it is *this*
   parameter is a separate, unresolved identification question.
4. **The leader-side `80%` per-minute rule (`PREREGISTRATION_LEAD_LAG_V1.md`
   Section 8) remains a separate mechanism** — different tier, different
   granularity, never to be merged with Option 2's follower-side, per-observation
   Stage-A threshold.
5. **`FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md`'s raw `15:29` coverage counts remain
   valid, unmodified, descriptive findings** — the 14-date and 20-date figures are
   not disputed, softened, or recalculated by this note.
6. **Those raw monthly-roster coverage figures do not establish Stage-A eligibility
   or Stage-B forward-endpoint completeness** — raw presence at a fixed clock time
   against the full original roster is not the same calculation as checking the
   actual frozen Stage-A subset's size against Option 2's (still-unspecified)
   threshold, nor the same as checking that subset against a real `t+h`.
7. **The audit's own comparison of the 14-date and 20-date groups against the
   `0.80`/`0.70` figures (its Section 7, "Reading 2") must not be treated as an
   established Option 2 eligibility result** — it is one candidate reading the audit
   itself declined to adopt as definitive, and Option 2's selection does not elevate
   it to one.
8. **Actual observation-level Stage-A and Stage-B outcomes require the real frozen
   subset (constructed from `t-35, t-5, t`) and the real horizon-specific `t+h`
   check** — neither has been calculated, here or in the audit, and this note does
   not calculate them.

**Option 2's selection changes which *procedure* is said to govern. It changes
nothing about whether raw full-roster coverage at one clock time can stand in for
that procedure's own checks — it cannot, and the original paragraph's framing ("closer
to accurate... since Option 2... is in fact the selected construction") risked
implying otherwise.** The severe archive-coverage warning in
`FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md` is retained in full as exactly that — a
warning — not as a settled eligibility verdict.

---

## 2. Exact governing source provisions and decision references

| Provision | Source | Status |
|---|---|---|
| Leader-tier roster construction (annual top-200, monthly turnover split) | `PREREGISTRATION_LEAD_LAG_V1.md` Section 6 | Committed, unchanged |
| Leader per-minute breadth floor `n_t_breadth >= 0.80 * leader-tier size` | `PREREGISTRATION_LEAD_LAG_V1.md` Section 8 | Committed, pre-existing, not part of the Option 1/2 debate |
| `n_t_breadth` vs. `n_t_return` distinction | `PREREGISTRATION_LEAD_LAG_V1.md` Section 8; AMENDMENT 2 LOG resolution 1 | Approved, 2026-11-14 |
| Follower-basket breadth floor **value**, `70%` | `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 5 LOG Section 1 (Decision 10) | **APPROVED, 2026-11-14 — a numeric value only** |
| Unified pre-signal eligibility (`t-35, t-5, t`), frozen subset, step-located breadth threshold, forward-endpoint gate — the full "Option 2" 9-step construction | `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3C | **Documented in full; SELECTED — `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3 ("subsequently selected as the basket-construction methodology by human decision"). CORRECTED, this reconciliation, same day: originally reported here as "NOT selected" — that was incomplete; see Section 1's correction notice.** |
| Choice between Option 1 (100% roster completeness) and Option 2 (frozen-subset construction) | `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3C, Section 11 decision item 19; resolving record: `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3 | **SELECTION RESOLVED (Option 2) — CORRECTED, same day; originally mis-reported as OPEN.** Option 2's own internal threshold form/value remains separately OPEN (next row). |
| Exact form/value of Option 2's own breadth threshold *as a parameter inside Option 2's own algorithm* | `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3C ("Which form, and what value, is left entirely OPEN, pending the Section 3D measurement work") | **OPEN — not explicitly identified with Decision 10's 70% figure anywhere in either document** |
| Decision 13 (exact endpoint-price convention) | `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 4 LOG | APPROVED, unaffected by this reconciliation |
| Decision 22 (`Momentum_F` same-session exclusion rule) | `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 5 LOG Section 3 | APPROVED (exclusion rule only); its own anchor arithmetic remains conditional on Decision 11 |
| Decision 11, 15, 17, 20, 21 | various | **OPEN where previously open — untouched by this reconciliation** |

`lead_lag/MASTER_SPEC_LEAD_LAG.md` was checked and contains no provision on this
topic (confirmed by direct grep: no reference to "Option 2," "frozen subset," or
breadth thresholds).

---

## 3. Stage A — pre-signal eligibility (quoted verbatim)

From `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3C, steps 1-6
(exact text, not paraphrased):

> 1. Start with the fixed monthly leader/follower roster (A above).
> 2. Determine constituent eligibility using **only** information computable by the
>    time the signal is actually computable ... covering **every** historical
>    endpoint any control in the primary model (Section 6) actually needs — for the
>    current specification, this means `t-35`, `t-5`, and `t` ... A name missing at
>    `t-35` but present at `t-5` and `t` is **not** partially includable for `R_F(t)`
>    only — it is excluded from the **whole** observation's eligible subset, so that
>    `R_F(t)`, `Y(t,h)`, and `Momentum_F(t)` are never computed over three different,
>    separately-filtered samples.
> 3. **Freeze** the eligible subset — membership and equal weights (`1/n_eligible`)
>    are fixed from this point; no further addition, removal, or substitution occurs
>    for this observation.
> 4. **Apply the minimum-breadth threshold to this frozen subset, here and nowhere
>    else in the construction** — i.e. after eligibility is determined and frozen
>    (steps 2-3), before anything is computed from it (step 6) and before the forward
>    check (step 7).
> 5. If the threshold is not met, mark the observation ineligible. **No substitution
>    of names occurs** — the observation is simply not used.
> 6. If the threshold is met, use the **same** frozen subset and weights, consistently,
>    for `R_F(t)`, `Y(t,h)`, and `Momentum_F(t)` — one common portfolio identity per
>    observation, not three.

**Direct answers to the task's exact questions**:

- **Which observations decide eligibility?** The bars at clock times `t-35`, `t-5`,
  and `t` — the union of every endpoint any control in the primary model needs, not
  only the signal window's own two endpoints.
- **Must all required pre-signal endpoints be present-valid?** Yes — step 2 excludes
  a name from the **whole** eligible subset if it fails at *any* of `t-35`, `t-5`, `t`.
- **How is Option 2's own threshold calculated? CORRECTED (2026-11-14, same day,
  documentation-correction task) — see below for what changed.** Per step 4,
  *whatever* Option 2's own minimum-breadth threshold turns out to be (its form and
  value are **OPEN**, not established by this reconciliation or any source document),
  it is applied to the **already-frozen eligible subset** (the survivors of step
  2-3), **not** to the original monthly roster. This is stated as "the precise
  location of the threshold in the algorithm" — a statement about *where in the
  procedure* the check happens, not a statement of *what number* it uses.
  **No numeric value — not `70%`, not `80%`, not any other figure — is established
  as Option 2's own threshold by this passage or anywhere in the governing proposal
  text.** The two existing approved/documented numbers in this family must not be
  read into this blank:
  - **`0.80` (leader-side, `PREREGISTRATION_LEAD_LAG_V1.md` Section 8)** is a
    **separate, pre-existing, per-minute** mechanism (`n_t_breadth >= 0.80 *
    leader-tier size`), deciding whether `S_leader(t)` is computed *at a given
    minute* — not an Option-2 Stage-A, per-observation, follower-side threshold.
    The proposal's own text is explicit: "the threshold specified here is a
    different quantity, on a different tier, at a different granularity ... The
    two numbers must not be assumed equal, confused, or merged."
  - **`0.70` (follower-basket breadth floor, Decision 10,
    `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 5 LOG Section 1)** is an **approved
    numeric value**, but Decision 10's own text models it on the leader's
    per-minute convention and never names "Option 2," "the frozen eligible
    subset," or this step-4 threshold. **Whether `0.70` is the value Option 2's
    own threshold uses remains OPEN** — approving a number is not the same as
    identifying which parameter it fills.
- **Applied to the original roster or another denominator?** **Option 2's own
  threshold is applied to the frozen eligible subset — explicitly not the raw
  roster — per step 4's own wording.** This establishes *where* the check sits in
  the procedure. It does **not** establish, and this reconciliation does not claim,
  any particular denominator convention (count, fraction of the frozen subset,
  fraction of the original roster, or both) for whatever threshold value is
  eventually chosen — the proposal's own Section 3C lists count, fraction, and
  "both jointly" as open candidate forms, and that openness is preserved here
  unresolved.
- **Once per observation or once per session/month?** Once per **observation**
  (i.e., per follower-row, per signal-minute `t`) — the roster itself (Section 3A) is
  frozen once per month, but the **eligibility subset** inside that roster is
  determined fresh for each `(entity-set, t)` observation, per step 2's own framing.
- **At what point does the subset/weights freeze?** Immediately after step 2-3,
  **before** the breadth threshold is even checked (step 4) and **before** anything
  is computed (step 6).

**The key question, answered directly (reworded, same day, to avoid naming specific
numbers Option 2's own threshold has not been shown to use)**: *"Does Option 2's own
breadth threshold determine which constituents enter the frozen subset, or does it
also permit missing constituents at later forward endpoints?"* — **Neither,
precisely.** The threshold is checked **after** the frozen subset already exists
(steps 2-3 determine membership; step 4 is a pass/fail gate on the *already-fixed*
subset's size, not a membership rule itself). It does **not** permit missing
constituents at `t+h` — forward completeness (Stage B) is a **wholly separate,
later, unconditional** check, described next. **This structural answer holds
regardless of what Option 2's threshold value or form eventually is** — it follows
from the procedure's step ordering, not from `70%`, `80%`, or any other figure.

---

## 4. Stage B — forward-endpoint completeness (quoted verbatim)

From the same section, steps 7-9:

> 7. Check `t+h` completeness against this already-frozen subset, **only now**, as a
>    whole-observation pass/fail gate.
> 8. If any frozen-subset member fails at `t+h`, discard the **entire** observation —
>    never reweight, replace, or reselect constituents.
> 9. Step 8 is still a form of future-dependent observation inclusion (mechanism 2
>    above), even though no future-dependent constituent selection (mechanism 1)
>    occurs anywhere in steps 1-6.

**Direct answers**:

- **Must every frozen-subset constituent have a valid `t+h` endpoint?** Yes —
  unconditionally, no threshold, no tolerance.
- **Does one missing/invalid endpoint invalidate the whole observation?** Yes,
  explicitly ("if **any** frozen-subset member fails... discard the **entire**
  observation").
- **Are the 80%/70% thresholds reapplied at `t+h`?** **No.** The breadth threshold is
  located exclusively at step 4 (pre-signal, Stage A). Step 7 is a **separate,
  zero-tolerance** gate with no threshold parameter at all.
- **Can constituents be removed, replaced, reweighted, or renormalized after the
  signal?** No — explicitly prohibited ("never reweight, replace, or reselect
  constituents"; separately, Section 3C's preceding discussion: "No replacement of an
  unavailable constituent after observing `t+h`, and no future-informed weighting or
  imputation, is proposed anywhere in this document").
- **Are partial portfolio returns permitted?** No (Section 3's "Required diagnostic"
  passage: "Option 2 never computes a partial forward portfolio return after a
  frozen-subset member fails the forward check").
- **Is forward-fill, zero-substitution, nearest-bar substitution, or imputation
  permitted at `t+h`?** No, none of these — explicitly and repeatedly ruled out.

**The pre-signal-exclusion case vs. the frozen-but-fails-forward case, kept distinct**
(Section 3C's own "Four exclusion categories" passage, reproduced in substance): a
name excluded at Stage A (step 2, fails pre-signal eligibility) **never enters the
frozen subset at all** — the observation may be unobservable in a different sense (the
whole `R_F(t)`/`Momentum_F(t)` construction may not even be computable, "not merely
unobserved"). A name that **is** in the frozen subset but fails at `t+h` causes the
**entire already-defined observation** to be discarded at Stage B — a different
failure mode, occurring strictly later, after a valid pre-signal quantity already
existed. The document itself states these must not be conflated; this reconciliation
preserves that distinction rather than collapsing it.

---

## 5. Comparison table — the two stages

| | **Stage A — pre-signal eligibility** | **Stage B — forward-endpoint completeness** |
|---|---|---|
| Endpoints checked | `t-35`, `t-5`, `t` | `t+h` (per horizon) |
| Governs | Whether a name enters the **frozen subset** at all | Whether the **already-frozen** observation is kept or discarded |
| Threshold | **Yes — Option 2's own minimum-breadth floor. Form and value both OPEN** (not `0.70`, not `0.80`, not any other figure established as this threshold by any source document). **CORRECTED, same day**: see the three bullets below, replacing an earlier version of this cell that listed `0.70`/`0.80` beside the threshold in a way that could be read as supplying it. | **None** — zero-tolerance, any single failure discards the whole observation |
| *(sub-note, Stage A column only, added same day)* | • Option 2's own Stage-A threshold: form (count/fraction/both) and value both OPEN.<br>• Leader-side `0.80` per-minute floor (Section 8): a **separate** mechanism, different tier, different granularity — not this threshold.<br>• Decision 10's approved follower `70%`: an approved **number**, but whether it is *this* threshold's value is **OPEN**, not established by either document. | *(not applicable — Stage B has no threshold of any kind, see row above)* |
| Tolerance for missing names | Up to the threshold's own slack (e.g., some names may fail Stage A and simply not enter the subset — the *remaining* subset can still pass if large enough) | **Zero** — no missing names tolerated among subset members at this stage |
| What happens on failure | Observation marked ineligible; "no substitution of names occurs" | Entire observation discarded; "never reweight, replace, or reselect" |
| Applies once, or per horizon | Once per observation (shared across `R_F`, `Y`, `Momentum_F` per step 6) | **Separately per horizon** — `t+h` differs by horizon, so Stage B must be re-checked for each `h` even though Stage A's frozen subset is shared |
| Governing decision status | **Option 2 is the SELECTED construction (Decision 19 resolved, `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3) — CORRECTED, same day; this stage's own procedure is governing.** Its threshold's own form/value remains separately OPEN. | Same selection applies — Stage B is part of the same selected Option 2 procedure |

---

## 6. Assessment of `FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md`

**Direct answers to the task's four questions**:

1. **Does raw full-roster coverage at `15:29` establish whether the pre-signal
   eligible subset passes its breadth threshold?** **No.** The pre-signal eligible
   subset (Stage A) is defined by joint validity at `t-35`, `t-5`, and `t` for a
   *specific* signal-minute `t` — not by presence at the single fixed clock-time
   `15:29`. The prior report measured coverage at `15:29` directly against the **raw**
   160/40-member monthly roster, not against any reconstructed Stage-A eligible
   subset. These are two different denominators, and the report did not construct the
   smaller one.
2. **Does raw full-roster coverage establish whether a frozen subset has complete
   forward endpoints?** **Only conditionally** — this would be literally true if (a)
   `15:29` is in fact the `t+h` forward endpoint for some well-defined observation,
   which depends on knowing `t` and `h`, which in turn depends on the still-OPEN
   Decision 11 (first-bar anchor) and the derived signal/anchor schedule, neither of
   which the prior report computed or assumed; and (b) the subset being checked is the
   **frozen Stage-A subset**, not the raw roster. The prior report used the raw
   roster. Its finding is a legitimate, severe **date-level** coverage signal, not a
   literal implementation of Stage B.
3. **Can the 14 dates be declared entirely unusable from the existing report alone?**
   **No.** **CORRECTED, same day** (the passage below replaces an earlier version
   that invoked "either Option 1 or Option 2" as if the choice between them were
   still live — it is not, Section 1 — and that came closer to treating the raw
   percentages as a proxy verdict than this reconciliation should): the raw `15:29`
   coverage collapse (2.5-5% leader, ~17% follower presence) is a **severe,
   well-evidenced, date-level feasibility warning** about archive coverage
   degradation on those 14 dates, and it is retained in full as exactly that — it is
   not softened or discarded here. **But it does not, by itself, establish
   observation-level failure under Option 2's own Stage A or Stage B**, because (i)
   it was measured against the raw monthly roster, not the actual Stage-A eligible
   subset constructed from `(t-35, t-5, t)`; (ii) Option 2's own threshold form and
   value are not fixed, so "fails the breadth floor" cannot yet be evaluated as a
   pass/fail fact; and (iii) `15:29`'s role as an actual `t+h` forward endpoint for
   any specific, well-defined observation is not established (Decision 11 is open).
   **The exact observation-level impact of this collapse cannot be established
   without constructing the real Stage-A subset and checking it against the real
   Stage-B endpoint for each horizon — neither of which this reconciliation, or the
   audit it discusses, performs.**
4. **What additional calculation is necessary?** **CORRECTED, same day**: item (b)
   below originally read "resolve Decision 19" as if the Option 1-vs-2 choice were
   still open; it is not (Section 1's correction notice) — Option 2 already governs.
   The remaining steps are: (a) resolve Decision 11 (fixes the anchor and hence the
   real signal-minute schedule); (b) confirm whether Decision 10's approved `70%`
   figure is in fact the value Option 2's own step 4 uses (not established by either
   document's own text — this is now the operative open question, not "which option
   governs"); (c) implement the Stage-A unified `(t-35,t-5,t)` eligibility check in
   actual code (none exists) to produce the real frozen subset per observation; (d)
   only then evaluate Stage B at the real `t+h` for each horizon. **None of this
   exists. This reconciliation does not perform it.**

**This is reported as a correction to the earlier report's framing, not an edit to
it.** `lead_lag/FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md` is unmodified; its Section 7
already hedged with "two readings" and did not claim a single definitive verdict, but
its Section 1 executive language ("already-approved breadth floors," stated plainly)
is, in light of the present reconciliation, **more confident than the underlying
decision record supports**, specifically regarding the word "approved" as applied to
the *procedure*, not the *number*.

---

## 7. Exact observation-level specification (pseudocode, no new rule invented)

Transcribed directly from Section 3C's own ordering; no threshold value, anchor, or
new rule is introduced:

```
# Per calendar month: (unchanged, Section 6/7 of 9f71b65 -- not reconstructed here)
roster_leaders, roster_followers = fixed_monthly_roster(month)

# Per candidate observation (one per signal-minute t, shared across R_L, R_F, Y, Momentum_F):
for t in candidate_signal_minutes:          # schedule itself depends on OPEN Decision 11
    for side, roster in [("leader", roster_leaders), ("follower", roster_followers)]:

        # ---- STAGE A: pre-signal eligibility (steps 1-6) ----
        eligible = []
        for name in roster:
            if is_present_valid(name, t-35) and is_present_valid(name, t-5) and is_present_valid(name, t):
                eligible.append(name)          # step 2: joint check, all-or-nothing per name
            # else: name excluded from the WHOLE eligible subset for this observation

        frozen_subset, frozen_weights = freeze(eligible, weight=1/len(eligible))   # step 3

        # step 4 -- Option 2's own Stage-A threshold. Deliberately abstract:
        #   - form (minimum count, fraction, or both) is OPEN
        #   - numerical value is OPEN
        #   - denominator convention (frozen subset size? original roster size?
        #     something else?) is OPEN
        #   - whether Decision 10's approved 70% follower figure supplies this
        #     threshold is OPEN, not established by any source document
        # No denominator, count, fraction, or value is encoded below -- passing
        # len(frozen_subset) or len(roster) here would silently assert a
        # denominator convention this reconciliation does not establish.
        if not option2_stage_a_threshold_met(frozen_subset):                      # step 4
            mark_observation_ineligible(t, side)                                   # step 5
            continue   # NO substitution; observation simply not used

        # compute R_L(t) / R_F(t) / Y-signal-side inputs / Momentum_F(t)
        # from frozen_subset + frozen_weights, consistently (step 6)

        # ---- STAGE B: forward-endpoint completeness (steps 7-9), PER HORIZON h ----
        for h in horizons:                      # 5, 15, 30, 60 minutes -- each checked separately
            if all(is_present_valid(name, t+h) for name in frozen_subset):        # step 7
                include_observation(t, h, side)   # Y(t,h) computed from frozen_subset, frozen_weights
            else:
                discard_observation(t, h, side)    # step 8: ENTIRE observation discarded
                # never: reweight, substitute, forward-fill, impute, or report a partial return
```

**Is the frozen subset shared across horizons?** Yes for Stage A (one freeze per
`(t, side)` observation, reused for every horizon's signal-side inputs) — but Stage B
(`t+h` completeness) is evaluated **separately for each horizon `h`**, since `t+h`
differs by horizon; an observation can pass Stage B at `h=5` and fail it at `h=60`
using the exact same frozen subset. No threshold, breadth value, denominator, or
eligibility rule above is invented — every element is a direct transcription of
Section 3C's numbered steps, or an explicit "OPEN, not specified" placeholder
(`option2_stage_a_threshold_met`'s form, value, and denominator convention are all
unresolved — the function takes only `frozen_subset` as an argument, deliberately
omitting any roster size or count that would imply a denominator this reconciliation
does not establish). **CORRECTED, same day**: an earlier version of this pseudocode
passed `len(roster)` into this check, which inadvertently encoded a specific
denominator convention (the original roster's size) as if it were settled. That was
an error, not a finding, and is corrected here.

---

## 8. Monthly roster effective-time finding (kept separate from Stages A/B)

**Question**: is same-day (ranking-date) turnover legitimately available when
determining that day's roster membership, or does the roster become effective only
after the ranking date's own close?

**Exact governing text, `PREREGISTRATION_LEAD_LAG_V1.md` Section 6**: *"on the first
trading day of each calendar month, rank eligible entities by trailing-60-trading-
session median daily rupee turnover (raw, from `prices_eod`, point-in-time -- **no
bar after the ranking date is used**)."*

**This text constrains only one side of the boundary** (no *future* bar relative to
the ranking date) — it does not state whether the ranking date's **own** turnover
(which, as a daily bhavcopy figure, is not published until after that day's session
closes) is included in or excluded from the trailing-60-session window. Checked
against every other source that discusses this construction:
- `lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1's method description (the
  one place this construction was actually executed) states only "ranked by
  trailing-60-trading-session median daily rupee turnover," with no inclusive/exclusive
  boundary specified either.
- `lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md` (this family's prior roster audit)
  likewise does not address this boundary.
- No document specifies whether the roster is "effective" *before* the ranking
  date's own session opens (which would require the decision to be made using only
  data through the **prior** session, since the ranking date's own bhavcopy does not
  exist yet at the open) or whether same-day knowledge is implicitly assumed
  available by the point in the day the roster is "used."

**Classification: UNRESOLVED.** This is a genuine documentation gap, independent of
the pre-signal-vs-forward-endpoint question addressed in Sections 3-7. It is not
resolved, not assumed, and not silently decided by this reconciliation. (For
reference and full transparency only, not as a resolution: the prior
`FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md` used `trade_date <= ranking_date` —
i.e., included the ranking date's own turnover — as one specific, disclosed
implementation choice for that audit's own reconstruction; that choice is not
endorsed, ratified, or extended by this reconciliation, and the ambiguity it
represents remains open.)

---

## 9. Unresolved questions requiring explicit user approval

1. ~~Decision 19 — Option 1 vs. Option 2.~~ **RESOLVED, not an open question** —
   corrected, same day (Section 1). `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG
   item 3 already records Option 2's selection by human decision. Retained here,
   struck through, so the correction itself is visible, not silently removed.
2. **Whether Decision 10's approved `70%` value is the number intended for Option
   2's own step-4 threshold**, or a differently-scoped figure. Neither document's text
   makes this identification explicitly. **This is now the primary, operative open
   question for Option 2's threshold** (sharpened by Option 2's selection no longer
   being in doubt). Not resolved here.
3. **The exact *form* of Option 2's breadth threshold** (count, fraction, or both) —
   explicitly left OPEN by the proposal's own Section 3C, independent of point 2
   above.
4. **Decision 11** (first-bar anchor) — unaffected, still OPEN; blocks reconstructing
   the real signal-minute schedule needed for any genuine Stage A/B observation-level
   evaluation.
5. **The monthly roster effective-time question (Section 8)** — unresolved,
   independent of points 1-4.
6. **Decisions 15, 17 (as applied beyond what is already settled), 20, 21** —
   unaffected, not newly implicated by this reconciliation beyond what prior reports
   already recorded.

---

## 10. Final statement of what is, and is not, established

**Established, directly from committed/approved text**:
- The exact 9-step Option 2 procedure, in full, including precisely where its breadth
  threshold sits (Stage A, step 4) and the zero-tolerance nature of its forward check
  (Stage B, steps 7-8).
- That Stage A and Stage B are categorically different mechanisms (a threshold-gated
  pre-signal filter vs. an unconditional post-freeze forward gate), never to be
  conflated, per the governing document's own repeated instruction.
- That Decision 10 approved a **number** (`70%`), explicitly modeled on the leader
  per-minute convention, with no textual tie to Option 2's own threshold parameter.
- **That Option 1 vs. Option 2 (Decision 19) is RESOLVED — Option 2 is the selected
  basket-construction methodology**, per the pre-existing human decision record in
  `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3. **CORRECTED, same day**:
  this report originally stated the opposite (Decision 19 "explicitly, currently
  OPEN"); that was incomplete and is retracted — see Section 1's correction notice.

**Not established, and not invented here**:
- Whether Decision 10's `70%` is the value Option 2's own step-4 threshold uses — this
  is the operative open question, now that *which* option governs is no longer in
  doubt.
- The exact form (count/fraction/both) of Option 2's own threshold.
- The real signal-minute/anchor schedule (blocked on Decision 11).
- Any observation-level inclusion/exclusion count for the 14 dates examined in
  `FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md`, or for any other date.
- Whether same-day ranking-date turnover is legitimately available for that day's
  roster (Section 8).

This reconciliation is **fully supported by approved/committed text for everything it
states as established**, and **explicitly exposes, rather than resolves, a genuine
unresolved ambiguity** everywhere it says so. No prior decision was reopened, no
number was changed, and no new rule was introduced.
