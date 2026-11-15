# Decision 16 — Preregistration Exposure Log

Append-only historical exposure record for the lead-lag
("Cross-Liquidity-Tier Return Propagation") family's two
basket-construction configurations. This log is separate from, and does
not modify, `lead_lag/trial_ledger.json`.

**Cross-reference (2026-11-14, added, not a rewrite of the entries
below): `PREREGISTRATION_LEAD_LAG_V1.md` now carries an "AMENDMENT 3
LOG" section implementing the exact accounting treatment this log
records (formal trial count 7, multiplicity-family denominator 8,
future primary-gate alpha `0.05/8 = 0.00625`) into the operative
preregistration text (Sections 15, 17, 20, 23). That amendment is
drafted and uncommitted, same status as this log's own prospective
alpha note in Section 7 below. Neither Option 1 nor Option 2's
classification below changes as a result; this is a pointer, not a
revision.**

---

## 1. Purpose and scope

This file records the historical fact that two basket-construction
configurations were empirically examined **before** either was formally
registered in `lead_lag/trial_ledger.json`, and documents the Decision 16
accounting resolution that governs how that fact is treated going
forward.

This log is **not** a trial ledger. It does not register any
configuration, does not create a `trial_ledger.json` entry, and does not
constitute preregistration of either configuration. Its only purpose is
to make the registration-timing history visible and auditable, so that
no future reader of the preregistration, the proposal, or the ledger can
mistake informal pre-registration examination for formal registration.

This log covers exactly two configurations:

- `basket_construction:option1_full_completeness`
- `basket_construction:option2_frozen_subset_fallback`

---

## 2. Decision 16 approvals and accounting principles

The following are the user's settled Decision 16 approvals. This log
records them; it does not decide them.

- Both configurations above are included in the same multiplicity family
  as the six existing `trial_ledger.json` entries.
- The approved prospective multiplicity-family denominator is **8**.
- The proposed alpha for the future primary predictive gate is
  **`0.05/8`**. This is **not currently operative**. The committed
  `PREREGISTRATION_LEAD_LAG_V1.md` still states `alpha = 0.05/6`
  (Section 15), and that remains unchanged by this log.
- `0.05/8` becomes operative only once recorded in an appropriate
  preregistration amendment, committed **before** the primary predictive
  gate is run (Section 7 below).
- Neither configuration is retroactively registered by this log. Neither
  configuration was registered before its examination.
- The six existing `trial_ledger.json` entries are preserved exactly as
  they are; this log adds nothing to that file and changes nothing in it.

**Accounting principle — three separate numbers, not one:**

| Concept | Value | Basis |
|---|---|---|
| `trial_ledger.json` entries (unchanged) | 6 | The six pre-existing, formally registered configurations |
| Formal trial count, under the approved classification below | **7** | The six existing configurations plus Option 1 (approved classification: unregistered Phase 1 feasibility kill, counted as a formal trial despite the registration-timing deviation) |
| Approved multiplicity-family denominator | **8** | The six existing configurations plus Option 1 *and* Option 2 — a deliberately conservative policy choice that includes Option 2 even though Option 2 does not qualify as a formal trial under the current project trial definition |

These three numbers are intentionally different and must not be forced
to agree. See Section 5.

---

## 3. Option 1 — historical exposure and Phase 1 kill

- **Configuration key**: `basket_construction:option1_full_completeness`
- **Registration status at examination**: NOT REGISTERED. Absent from
  `lead_lag/trial_ledger.json` at the time of examination and remains
  absent from that file as of this log entry.
- **Examination date and timestamp precision**: 2026-11-10. No
  finer-grained timestamp (hour, minute) is available from any
  repository or conversation record. This date should be read as a
  calendar-day-level fact only.
- **Examination description and results**: examined via the exploratory
  Decision 10 follower-side completeness measurement. At the 100%
  completeness threshold, the measurement found **zero qualifying
  observations** across all four prediction horizons (5, 15, 30, and 60
  minutes) and all 120 months of the family's data window. The
  infeasibility was caused by structural intraday-archive coverage gaps
  — specifically, 41 follower-roster entities with no `bars_1min` history
  at all, each entity-level absence being sufficient on its own to make
  full-roster coverage impossible for every day of every month in which
  that entity sat in the follower roster.
- **Subsequent methodology decision**: none. Option 1 was **not
  selected**.
- **Formal trial classification**: **UNREGISTERED PHASE 1 FEASIBILITY
  KILL**, counted as a **formal trial** under the approved interpretation
  of the project's trial definition (`PROJECT_CONTEXT.md` lines 138–142),
  notwithstanding the registration-timing deviation (the configuration
  was examined, and killed by that examination, before it was formally
  registered). This classification is an explicit, approved accounting
  decision for this configuration specifically — it does not reinterpret
  the general project trial definition, and it does not by itself resolve
  how an analogous unregistered examination would be classified for any
  other configuration in any other family.
- **Multiplicity-family membership**: INCLUDED, per Decision 16, in the
  8-member prospective family.
- **Prospective alpha status**: covered by the proposed `0.05/8`,
  prospective and not yet operative (Section 2).
- **Registration action taken**: NONE. This log entry does not create a
  `trial_ledger.json` record and does not register this configuration.
- **Mandatory future disclosure**: any future preregistration amendment
  or `trial_ledger.json` registration touching this family must disclose
  that this configuration was examined, and found infeasible, before it
  was formally registered — i.e., that its classification as a formal
  trial rests on a registration-timing deviation, not on a
  prospectively-registered Phase 1 check conducted in the ordinary
  sequence.

---

## 4. Option 2 — historical exposure and subsequent methodology selection

- **Configuration key**: `basket_construction:option2_frozen_subset_fallback`
- **Registration status at examination**: NOT REGISTERED. Absent from
  `lead_lag/trial_ledger.json` at the time of examination and remains
  absent from that file as of this log entry.
- **Examination date and timestamp precision**: 2026-11-10. No
  finer-grained timestamp is available. Calendar-day-level fact only.
- **Examination description and results**: examined in the same Decision
  10 measurement task as Option 1. Its 9-step frozen-subset-then-
  forward-check construction (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_
  PROPOSAL.md` Section 3C) was exercised across five completeness
  thresholds (80%, 85%, 90%, 95%, 100%) and four horizons. The
  measurement produced retained-observation counts and forward-endpoint
  exclusion rates ranging from 0.47% to 1.16%.
- **Subsequent methodology decision**: the user subsequently **approved
  Option 2 as the selected basket-construction methodology**. This was a
  human methodology decision informed by the measurements above. **It
  was not a predictive-gate pass, not a successful strategy result, and
  not evidence that Option 2 produces unbiased returns, adequate
  predictive power, or a profitable strategy.** No predictive hypothesis
  was tested by this examination or by the subsequent selection.
- **Formal trial classification**: **NOT A FORMAL TRIAL**, under the
  current project trial definition. Option 2 was neither killed at a
  Phase 1 feasibility check (it was exercised and then selected, not
  killed) nor did it reach a preregistered predictive gate (methodology
  selection is not a predictive-gate pass under
  `PREREGISTRATION_LEAD_LAG_V1.md`'s Section 20 verdict-rules sense of
  "gate"). Its empirical exposure and its subsequent selection are both
  real, documented historical facts — recorded in full in this entry —
  but neither fact, individually or together, satisfies the project's
  formal trial definition as currently written.
- **Multiplicity-family membership**: INCLUDED, per Decision 16, in the
  8-member prospective family — **despite** not qualifying as a formal
  trial. This is a deliberate, conservative multiplicity policy choice,
  not a reclassification of Option 2 as a formal trial.
- **Prospective alpha status**: covered by the proposed `0.05/8`,
  prospective and not yet operative (Section 2).
- **Registration action taken**: NONE. This log entry does not create a
  `trial_ledger.json` record and does not register this configuration.
- **Mandatory future disclosure**: any future preregistration amendment
  or registration record touching this family must disclose (a) that
  this configuration was examined before formal registration, and (b)
  that it was separately selected as the basket-construction methodology
  via a human decision, not via a predictive gate — and must not describe
  that selection as evidence of predictive validity.

---

## 5. Formal trial count versus multiplicity-family denominator

These two numbers are **deliberately different** and must not be
reconciled into one figure:

- **Formal trial count, under the approved classification**: **7** — the
  six existing `trial_ledger.json` entries, plus Option 1 (classified as
  an unregistered Phase 1 feasibility kill, counted as a formal trial per
  Section 3). Option 2 does **not** add to this count, because it is not
  classified as a formal trial (Section 4).
- **Approved multiplicity-family denominator**: **8** — the six existing
  entries, plus Option 1, plus Option 2. The user has explicitly chosen
  to include Option 2 in the multiplicity-correction family as a
  conservative policy decision, even though Option 2 does not meet the
  formal trial definition. Family membership is a multiplicity-control
  policy choice; formal trial classification is a separate, definitional
  question. They answer different questions and are not required to
  produce the same number.
- **`trial_ledger.json`'s own machine-computed count (`denominator()`)
  remains 6**, because this log does not add any entry to that file's
  `trials` array. Neither the "7" nor the "8" above is, or should be,
  read out of `trial_ledger.json` directly — both are accounting facts
  recorded in this separate log, pending whatever future registration
  action (if any) is taken for Option 1 and/or Option 2.

---

## 6. Registration-timing deviation and mandatory future disclosure

Both configurations were empirically examined **before** either was
formally registered. Neither was preregistered before its examination.
This log does not imply otherwise anywhere above, and must not be edited
to imply otherwise in the future.

Any future preregistration amendment, or any future `trial_ledger.json`
registration, that touches this family must disclose:

1. Option 1's unregistered empirical examination and its classification
   as a Phase 1 feasibility kill, including the registration-timing
   deviation underlying that classification (Section 3).
2. Option 2's unregistered empirical examination and its subsequent
   selection as methodology via human decision — not via a predictive
   gate — including the explicit caveat that this selection is not
   evidence of predictive validity (Section 4).
3. The fact that both configurations were included in the 8-member
   multiplicity family despite carrying different formal trial
   classifications (Section 5).

This log itself does **not** constitute preregistration of either
configuration, and does not substitute for whatever registration action
is eventually taken.

---

## 7. Preregistration amendment dependency

The proposed `alpha = 0.05/8` is **not operative**. The currently
committed `PREREGISTRATION_LEAD_LAG_V1.md` states `alpha = 0.05/6`
(Section 15), unchanged by this log. `0.05/8` becomes the operative alpha
for the primary predictive gate only once:

- a preregistration amendment recording the 8-member multiplicity family
  and the `0.05/8` alpha is drafted and committed, and
- that amendment is committed **before** the primary predictive gate is
  run — not after, and not concurrently with it.

No such amendment has been drafted or committed as of this log entry.
This log does not draft, propose text for, or otherwise begin that
amendment — it only records the dependency.

**Dated clarification (2026-11-14), added adjacent to the original
statement above rather than replacing it**: the preceding sentence
records the status as of this log's initial preparation and is preserved
as historical evidence, not deleted or rewritten. **An "AMENDMENT 3 LOG"
was subsequently drafted in `PREREGISTRATION_LEAD_LAG_V1.md` on
2026-11-14**, implementing the accounting treatment this log describes
(formal trial count 7, multiplicity-family denominator 8, prospective
primary-gate alpha `0.05/8 = 0.00625`) into the operative preregistration
text. **It remains uncommitted.** No commit, staging, or push is
authorized by this clarification or by the task that added it.

---

## 8. Append-only maintenance rule

This artifact is an **append-only historical exposure log**:

- Existing entries (Sections 3 and 4, and any later entries) must never
  be overwritten or erased.
- Any later examination of either configuration, or of any future
  configuration with a comparable registration-timing history, must be
  recorded as a **new, separately dated entry** — not as an edit to an
  existing entry.
- Any correction to a previously recorded fact must be documented
  transparently as a new, dated correction entry that states what was
  wrong and what the corrected fact is — never as a silent replacement of
  the original text.
- This log does not substitute for formal prospective registration in
  `lead_lag/trial_ledger.json`. If either configuration is ever formally
  registered, that registration happens in `trial_ledger.json` itself,
  via the normal hand-edit-and-commit process described in
  `lead_lag/ledger.py`'s module docstring — not by editing this log.

---

## 9. Git and implementation audit

- This file was created as the **only** file touched by the task that
  produced it. No other file in the repository was read-modified,
  created, staged, or committed as part of that task.
- No entry was added to `lead_lag/trial_ledger.json`. No alpha value was
  changed in any existing file. No configuration was registered. No
  empirical measurement, database query, backtest, feasibility check, or
  predictive gate was run in the course of creating this file.
- This log is uncommitted at the time of its creation, consistent with
  every other document in this family's current review chain.
