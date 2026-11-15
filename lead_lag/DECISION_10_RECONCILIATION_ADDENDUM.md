# Decision 10 — Reconciliation Addendum

Append-only reconciliation record. Run against the repo at commit
`9f71b65e006f937760e39a9f65035c69a1ef8df9` plus the uncommitted "AMENDMENT
2" edit to `PREREGISTRATION_LEAD_LAG_V1.md` prepared alongside this
addendum, 2026-11-14.

**This addendum does not overwrite, delete, or rewrite either original
measurement report.** `lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md`
and `lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md`
remain exactly as originally written, in full, as historical records of
the exploratory measurements that preceded the four approvals reconciled
here. This addendum reconciles their numbers against the newly-approved
methodology; it does not correct them in place.

**Chronology, stated once, plainly**: the measurements this addendum
reconciles were performed before the four Decision 10 approvals existed.
Nothing here implies those measurements were preregistered, registered,
or governed by definitions that did not yet exist when they were run.
This is a prospective reconciliation, not a retroactive one.

**Scope reminder**: this is a no-outcome documentation/reconciliation
task. No price, return, forward label, beta, correlation, IC, or
predictive statistic was read or computed in producing this addendum —
every number below is an availability/eligibility/date-coverage count,
reused or recomputed from the two original reports and the prior
calendar/breadth audit (whose own findings were independently
spot-checked, including direct confirmation that `src/data_layer/
nse_holidays.py` and `data/raw/nse_cm_holidays.pkl` exist with the stated
content, and that `2016-10-30` is a Sunday by direct date arithmetic).

---

## 1. Leader breadth reconciliation (Decision A)

### 1.1 What changed

The original combined report (`DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md:244-255`)
implemented the per-minute leader breadth count as **present-valid plus
absent-but-forward-fillable** bars ("Implementation A" in the audit). The
approved methodology (Decision A) requires **present-valid bars only**
("Implementation B" in the audit) for the breadth gate specifically,
while leaving Decision 17's forward-fill rule fully intact for leader
*return construction* (the `n_t_return` divisor in `S_leader(t)`,
preregistration Section 8, now explicitly distinguished from
`n_t_breadth` in the AMENDMENT 2 edit).

### 1.2 The three observations that change eligibility

| `trade_date` | `t` | horizon | `n_t` (A, present-valid+FF) | `n_t` (B, present-valid only) | `0.80 * NL` | Follower side | Combined status (A) | Combined status (B) |
|---|---|---|---|---|---|---|---|---|
| 2017-07-12 (Wed) | 11:19 | 5 min | 32 | 31 | 32 | passes (120/160) | **retained** | **excluded (leader-only)** |
| 2017-07-12 (Wed) | 11:19 | 15 min | 32 | 31 | 32 | passes (120/160) | **retained** | **excluded (leader-only)** |
| 2021-03-31 (Wed) | 14:34 | 30 min | 39 | 1 | 32 | passes (150/158) | **retained** | **excluded (leader-only)** |

All three pass the follower side under both breadth implementations and
at both the 70% and 75% follower candidates — they are not absorbed by
any follower-side exclusion. These are the only three observations in
the entire 2016-10-04–2026-09-18 archive where the present-valid-only and
present-valid-plus-forward-filled leader counts fall on opposite sides of
the `0.80` floor; `n_t_breadth` and `n_t_return` differ (non-decisively)
on 308 of 151,962 day-rule-surviving minutes overall.

### 1.3 Reconciled retained counts, approved (strict, present-valid-only) breadth

| Horizon | Retained, as originally reported (A) | Retained, approved methodology (B) | Δ |
|---|---|---|---|
| 5 min | 79,662 | **79,661** | −1 |
| 15 min | 38,633 | **38,632** | −1 |
| 30 min | 21,708 | **21,707** | −1 |
| 60 min | 9,639 | **9,639** | 0 |
| **Pooled** | **149,642** | **149,639** | **−3** |

At the 75% follower candidate (cited only as already-reported context,
not reopened): 144,716 → **144,713** (−3), same three observations.

Dates/months/years/first-last retained are **unchanged**: 2,446 distinct
dates, 120 months, 11 years, 2016-10-04 → 2026-09-18 — none of the three
affected observations is the sole retained observation for its date.

### 1.4 Correction to the "strict subset" claim

The original combined report states that leader-side exclusions are
always a strict subset of follower-side failures (i.e. "excluded only by
leader-side rules" = 0). **This is corrected: it is not generally true
under the approved present-valid-only breadth definition.**

- Under Implementation A (as originally measured): excluded-only-by-leader = 0 — the claim held, but only because of which breadth implementation was in effect, not because of any structural guarantee.
- **Under Implementation B (approved)**: excluded-only-by-leader = **3** — exactly the three observations in §1.2, each of which independently passes the follower side.

The corrected statement, stated as plain counts rather than a combined
ratio (the prior phrasing incorrectly combined a leader-side *survivor*
count with a leader-side *failure* total and is withdrawn):

- **Total leader-side exclusions under approved Implementation B: 1,092.**
- Of these, **1,089 also fail the follower-side rules** (nested — these
  observations would have been excluded regardless of the leader-side
  rule).
- **Three observations fail the leader-side rule but pass the
  follower-side rules** (the three in §1.2) — these are excluded *only*
  because of the leader-side breadth floor.
- **Therefore: leader-side exclusions are NOT universally a subset of
  follower-side failures under the approved implementation.** `1,092 =
  1,089 + 3` reconciles exactly against the leader-side failure total
  reported in §1.3's underlying tabulation.

### 1.5 Breadth vs. return construction

No change to Decision 17's return-construction treatment occurred or is
implied by this reconciliation. A leader whose bar at `t` (or within the
`t-4..t` window) is forward-filled under the `<180`-second rule remains
eligible to contribute its `S_i(t)` to the `n_t_return`-divided average in
`S_leader(t)`, exactly as before — Decision A changes only whether that
same leader counts toward the `0.80` **gate**, not whether its return
contribution is used once the gate passes.

---

## 2. Calendar denominator reconciliation (Decisions B, C, D)

### 2.1 The audit's per-date classification, reused exactly

| Bucket | Dates | Classification |
|---|---|---|
| A | 2,451 | ordinary weekday, EOD-confirmed, ≥300 in-window minutes — genuine regular session |
| B | 2 | ordinary weekday, EOD-confirmed, partial in-window span — genuine regular session |
| C | 5 | ordinary weekday, EOD-confirmed, zero in-window bars (evening Muhurat session only) — **not** a regular session |
| D | 1 | weekday, NSE CM holiday, 1-hour special session only — **not** a regular session |
| E | 4 | weekend, full 375-minute in-window span — genuine special trading session, **included** |
| F | 3 | weekend, partial in-window span (incl. `2016-10-30`) — **not** a regular session |
| G | 2 | weekend, zero in-window bars — **not** a regular session |
| **Total** | **2,468** | |

Governing calendar (approved) = A + B + E = 2,451 + 2 + 4 = **2,457**.
Excluded = C + D + F + G = 5 + 1 + 3 + 2 = **11**.

No date is left unclassified by the audit's own evidence; none is marked
ambiguous by the available local evidence (weekday arithmetic, the NSE CM
holiday master, `prices_eod` EQ-row presence, and in-window intraday
span all independently agree for every one of the 2,468 dates).

### 2.2 Scheduled-observation denominators, reconciled

| Denominator | Dates | Scheduled (pooled) | h=5 | h=15 | h=30 | h=60 |
|---|---|---|---|---|---|---|
| D0 — raw archive (as originally published) | 2,468 | 153,016 | 81,444 | 39,488 | 22,212 | 9,872 |
| **D1 — governing (approved)** | **2,457** | **152,334** | **81,081** | **39,312** | **22,113** | **9,828** |
| D2 — strict NSE weekday (sensitivity only; drops bucket E too) | 2,458 | 152,396 | — | — | — | — |

D1 = D0 minus the 11 excluded dates' scheduled slots (11 × 33/16/9/4 =
363/176/99/44, summing to 682); none of the 11 excluded dates contributes
any retained observation under either breadth implementation (confirmed:
all 11 are members of the originally-reported 22 zero-retained-date set),
so **the retained numerator is identical whether D0 or D1 is used as the
denominator.**

### 2.3 Three retention percentages, reconciled against both breadth implementations

| Denominator | Numerator (Impl A, as originally measured) | % (A) | Numerator (Impl B, approved breadth) | % (B) |
|---|---|---|---|---|
| D0 — raw archive (historical comparison only) | 149,642 | 97.7950% | 149,639 | 97.7930% |
| **D1 — governing trading-session (approved)** | 149,642 | **98.2328%** | **149,639** | **98.2309%** |
| D2 — strict NSE weekday (sensitivity only) | 149,398 | 98.0328% | 149,395 | 98.0308% |

**The figure named in the approval instruction, 98.233%, is the D1/
Implementation-A combination** — i.e. the governing calendar denominator
applied to the *original* (not-yet-breadth-corrected) numerator:
`149,642 / 152,334 = 98.23283049%`, reported as **98.2328%** (98.233%
rounded to three decimal places). Once Decision A's approved
present-valid-only breadth is also applied (as it must be, since both are
approved in the same set of decisions), **the fully reconciled governing
figure is `149,639 / 152,334 = 98.23086113%`, reported as `98.2309%`
(98.231% rounded to three decimal places).** This is a genuine arithmetic
reconciliation this addendum surfaces explicitly, per the instruction to
report arithmetic precisely rather than accept a cited figure uncompared
against the other approved decision. The difference (0.00196936
percentage points, approximately 0.0020 percentage points when rounded
to four decimal places; 3 observations) is immaterial to any qualitative
conclusion but
is not zero, and 98.2328%/98.233% should not be re-cited as the final
figure without this correction -- the approved figure is `98.2309%`
(`98.231%`).

**Labels, as required**:
- **Raw archive-date denominator (D0): historical comparison only.** Not the authoritative figure.
- **Verified actual-session denominator (D1): the governing metric.** `149,639 / 152,334 = 98.2309%` (`98.231%` rounded), previously cited as `98.2328%` (`98.233%` rounded) before Decision A's breadth correction was applied.
- **Strict-weekday denominator (D2): sensitivity only.** 98.031% (reconciled). Provided for context; not governing.

### 2.4 Date/month/year coverage, reconciled

| Denominator | Retained dates | Retained months | Retained years | First → last |
|---|---|---|---|---|
| D0 (as published) | 2,446 of 2,468 | 120 of 120 | 11 of 11 | 2016-10-04 → 2026-09-18 |
| **D1 (governing)** | **2,446 of 2,457** | **120 of 120** | **11 of 11** | **2016-10-04 → 2026-09-18** |
| D2 (sensitivity) | 2,442 of 2,458 | 120 of 120 | 11 of 11 | 2016-10-04 → 2026-09-18 |

The retained-date *numerator* (2,446) is unchanged across D0/D1 — the 11
dates D1 removes from the denominator never contributed a retained
observation. D2's numerator drops to 2,442 because it additionally
excludes the 4 genuine weekend special-session dates, each of which does
contribute retained observations (244 pooled) — this is exactly why
Decision C requires their inclusion in the governing calendar rather than
applying a blanket weekday-only filter.

**Observations excluded because their dates are not genuine sessions**:
the 11 dates excluded under D1 contribute 0 retained observations in
either breadth implementation — their exclusion from the *denominator*
changes no retained observation's status. This is stated separately, as
required: no observation was removed from the retained *numerator* by
this reconciliation; only the denominator's composition changed.

---

## 3. The `2016-10-30` loose-sensitivity result (correction)

**Established facts, reused from the audit, independently re-confirmed**
(day-of-week via direct date arithmetic: `2016-10-30` is a Sunday; also
an NSE CM holiday per `data/raw/nse_cm_holidays.pkl`):

- The "loose sensitivity count of 35" is **arithmetically correct** —
  35 leader-tier entities each have exactly one present-valid row inside
  the `09:15`–`15:29` clock window that day.
- Every one of those 35 rows is stamped **exactly `15:29:00`**.
- **Zero** bars exist anywhere in the preceding 374 minutes of the
  window for this date.
- A separate, correctly-excluded cluster of off-session rows (4
  entities, `18:29`–`19:29`) exists for the same date and does not
  overlap the 35.

**Correction**: the count of 35 must not be described as evidence of
meaningful regular-session leader coverage on this date. It is the
arithmetic result of a broad clock-window query landing on a single,
isolated, end-of-window artifact bar per entity, on a date that is both a
Sunday and an NSE holiday and that the governing calendar (§2) correctly
excludes. The query's arithmetic result (35) and genuine session
eligibility (none) are two different things; this addendum states both
without altering either the original report's text or the number 35
itself — nothing is removed or falsified, only re-described.

Under the governing D1 calendar, `2016-10-30` is one of the 11 excluded
dates and contributes 0 retained observations under any breadth
implementation, consistent with its treatment in the original combined
report's zero-retained-date list.

---

## 4. Preserved findings — explicitly unchanged

The following are **not** altered by this reconciliation or by the
AMENDMENT 2 preregistration edit:

- The approved 70% follower-breadth candidate (still open pending separate finalization; not reopened here).
- The fixed monthly roster (Decision 18) and Option 2 frozen-subset construction (Decision 19).
- Decision 17's existing bar-validity and return-construction rules (only the leader *breadth gate* changed; return construction is explicitly untouched, §1.5).
- The existing whole-day leader-tier rule (`n_day >= 0.50 * NL`) is unchanged. Its wording defect (the literal "<50%...lacks a valid bar" inversion, flagged by the prior audit) has since been corrected in Section 12 of the accompanying preregistration -- the correction is to the sentence's wording only; the underlying rule, its implementation, and its 0.50 threshold remain exactly as they were.
- The approved 09:20 anchor (Decision 11) — not reopened.
- The already-known 2026-08-03-onward `15:19` archive truncation — preserved as a known limitation, not re-presented as new; independently reconfirmed that it contributes 0 to the 3-observation leader-breadth delta in §1 (all 34 affected observations are excluded under both breadth implementations and independently by the follower-side rule).
- `lead_lag/trial_ledger.json`, the multiple-testing denominator (6), and alpha allocation (`0.05/6`, Section 15) — untouched **by this addendum's own scope (Decision 10: calendar, breadth, return construction)**. This statement describes this addendum's scope only and should not be read as meaning these values never change — Decision 16's separate multiplicity/alpha resolution (formal trial count 7, multiplicity-family denominator 8, future primary-gate alpha `0.05/8 = 0.00625`) is recorded in `PREREGISTRATION_LEAD_LAG_V1.md`'s AMENDMENT 3 LOG, drafted the same day as this clarification, and is outside this addendum's own subject matter.
- `lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md` — unaffected, untouched by this addendum.

---

## 5. Validation checks performed

| # | Check | Result |
|---|---|---|
| 1 | Amendment's breadth predicate matches approved present-valid-only rule | **Pass** — `n_t_breadth`, Section 8, counts present-valid bars only |
| 2 | Amendment does not change Decision 17 return construction | **Pass** — `n_t_return` explicitly left governed by Decision 17's existing rules; no edit to any Decision 17 document |
| 3 | Amendment's calendar source matches actual repository implementation | **Pass** — `src/data_layer/nse_holidays.py` and `data/raw/nse_cm_holidays.pkl` independently confirmed to exist with the stated purpose |
| 4 | Special sessions not accidentally removed by a weekday-only filter | **Pass** — the 4 weekend special sessions (bucket E) remain in the governing D1 denominator and numerator |
| 5 | Non-session archive dates not counted as genuine sessions | **Pass** — buckets C/D/F/G (11 dates) excluded from D1 |
| 6 | 98.233%/98.231% figure reconciles exactly to its numerator/denominator | **Pass, with correction** — 149,642/152,334 = 98.23283049%, reported as 98.2328% (original, pre-breadth-correction); 149,639/152,334 = 98.23086113%, reported as 98.2309% (fully reconciled, approved) |
| 7 | Three changed breadth observations recorded consistently | **Pass** — identical identifiers (2017-07-12 ×2 horizons, 2021-03-31 ×1 horizon) used in the preregistration edit and this addendum |
| 8 | Strict-subset claim corrected everywhere in new documentation | **Pass** — corrected in this addendum (§1.4); the original combined report's text is left as a historical record and not edited |
| 9 | 2016-10-30 loose-sensitivity count described accurately | **Pass** — §3, arithmetic vs. substance distinguished |
| 10 | Historical reports remain preserved and identifiable | **Pass** — neither original report was modified; confirmed via file read-back and git status |
| 11 | New amendment does not imply retroactive preregistration | **Pass** — chronology stated explicitly in both the preregistration edit and this addendum's header |
| 12 | No unrelated methodology or multiplicity decision changed | **Pass** — §4 enumerates what is explicitly unchanged |

**No figure in this addendum is marked unresolved** — every reconciliation
in §1–§3 closed exactly, with the one genuine correction (98.233% →
98.231% once both approved decisions are combined) stated explicitly
rather than silently absorbed.

---

## 6. Status

**READY FOR HUMAN REVIEW.** This addendum and the accompanying
uncommitted edit to `PREREGISTRATION_LEAD_LAG_V1.md` ("AMENDMENT 2 LOG")
are prepared for review. Neither has been committed. No primary gate, no
outcome inspection, and no change to the 70% follower-breadth candidate,
the trial ledger, or alpha allocation occurred in producing them.
