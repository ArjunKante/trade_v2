# Decision 17 — Final Data-Validity Policy Recommendation

Read-only policy-synthesis memo. Run against the repo at commit
`9f71b65e006f937760e39a9f65035c69a1ef8df9` (HEAD throughout this memo's
entire drafting and revision history; **corrected** — an earlier version
of this header cited `c2a0d62`, which is a real, verified ancestor commit
of HEAD but reflects the repository state *before* the lead-lag
preregistration commits existed, not "working tree at time of writing" as
originally claimed; `c2a0d62` was evidently carried forward by copy-paste
from an earlier document in this review chain rather than re-checked).
Originally written 2026-11-09, updated 2026-11-09 to incorporate three
settled human decisions and a completed
empirical impact measurement. **This remains a recommendation for human
review, not a formal approval of the complete Decision 17 policy.**
Decision 17 as a whole stays OPEN — settling three of its sub-questions
(below) does not close the remaining ones (Decision 10, 11, 19, and
categories A/E's recommendation status, all still open; see Sections 7.3
and 8). No implementation is authorized by this document or by this
update.

**Three sub-questions are now SETTLED HUMAN DECISIONS, not recommendations
pending approval** (distinguished from this memo's own methodological
recommendations throughout — see the decision table in Section 6):

- **A1** — Zero-volume, OHLC-flat bars: **ACCEPT** as present-valid
  observations; use their own recorded close for return computation; do
  not classify them as missing merely because volume is zero.
- **B1** — Zero-volume, OHLC-non-flat bars: **FLAG / INELIGIBLE** pending
  resolution; never use their own OHLC values; never impute their own
  timestamp; treat as functionally absent for neighboring gap-span
  classification only.
- **C** — The Section 13 preregistration threshold is interpreted as
  **Interpretation E: exact elapsed timestamp duration** (`next_present_ts
  − prev_present_ts`, measured as true elapsed time, not a
  minute-boundary-crossing count), compared against 3 minutes
  (`<3 min` forward-fill; `>=3 min` exclude, not imputed). **This is the
  user's own new methodological decision, not a conclusion about the
  original 2026-11-07 preregistration author's intent** — a dedicated
  original-intent investigation (git-history and master-spec inspection)
  found the evidence inconclusive (strong indirect evidence leaning
  toward an elapsed-time framing, but nothing meeting the bar for a
  confirmed original intent). Decision C settles the question
  prospectively for this policy; it does not retroactively claim what the
  original author meant.

The empirical impact of decision C has been measured and independently
verified (Section 4.D below): the exact-elapsed-duration exclusion rate is
**23.4447% (follower)** and **51.8013% (leader)**, against a historical
`DATE_DIFF('minute')`-based approximation of 23.4450%/51.8013% and the
original absent-bar-count baseline (Interpretation M) of 9.31%/47.90%.

## 1. Scope and files inspected

This memo performs no new empirical measurement. It synthesizes a policy
recommendation from evidence already gathered by two prior documents, plus
the committed preregistration text that governs this question, re-read in
full for this task:

- `lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md` (the original
  investigation — read in full).
- `lead_lag/DECISION_17_REPRODUCIBILITY_AUDIT.md` (the independent audit —
  read in full; treated as a **separate audit record that qualifies, not
  automatically ratifies,** the original investigation's numbers and
  language).
- `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`, Sections 3 (basket
  construction, future-dependence mechanisms, Options 1/2), 4D (endpoint
  categories), 5 (timestamp convention, session structure), and 11
  (decision table rows 17–21) — re-read directly for this task.
- `PREREGISTRATION_LEAD_LAG_V1.md`, Sections 12 and 13, and the frozen
  parameter table (lines 510–530, 985–994) — re-read directly for this
  task; this is the **committed, frozen** rule this memo must clarify the
  scope of, not rewrite.
- Data-ingestion code (`src/fibo/intraday_db.py`, `src/fibo/download.py`,
  `scripts/fibo_download_intraday_top200.py`) — **not re-read** in this
  task; cited from the prior investigation's own file:line findings
  (Part 1 of `DECISION_17_ZERO_VOLUME_INVESTIGATION.md`), which already
  performed this inspection exhaustively and was independently spot-checked
  by the audit. Re-opening these files would not change any conclusion
  already established there, so this memo relies on that existing,
  verified record rather than repeating the inspection.

No database was queried in this task (see Section 7, "Access and
restrictions," below). **This update additionally incorporates** two
further completed, read-only measurement tasks not reflected in the
original version of this memo: an Interpretation-E impact measurement
(M-vs-E exclusion rates, boundary-case analysis, and the B1/invalid-bar
bounding-row interaction diagnostic) and a follow-up exact-duration
precision verification (confirming `DATE_DIFF('minute')` is not an exact
proxy for elapsed duration, and quantifying the resulting correction).
Both were delivered as in-conversation findings, not as separate files
(per this update's own instruction not to create a second memo); their
figures are incorporated directly into Sections 2, 4.D, 6, 7, and 8 below,
with the same care to distinguish settled decisions from this memo's own
remaining recommendations.

## 2. Evidence summary, with the audit's qualifications applied

### 2.1 What the evidence establishes (corrected terminology used throughout below)

- `bars_1min.volume` is Angel One's raw per-minute candle value, inserted
  unmodified; no project-side synthesis exists; no trade-count field exists
  to distinguish a genuine print from anything else.
- Zero-volume rows: 7,018 table-wide; 82% OHLC-flat, 18% (1,259) **not**
  flat despite zero reported volume; 60% of all zero-volume rows table-wide
  sit at exactly 15:28 or 15:29.
- Follower-tier and leader-tier zero-volume rates are **numerically
  similar in this measured population; no inferential test of their
  difference was performed** (corrected from the original memo's
  unsupported "statistically indistinguishable" language, per the audit).
- **Absent expected timestamps** (not "missing rows," and not confirmed
  feed failures) are far more common than zero-volume rows and
  tier-differentiated (follower ≈1.15%, leader ≈0.095% of expected
  interior minutes). The cause is unresolved: vendor no-trade suppression,
  incomplete vendor data, and other undocumented API behavior all remain
  open, competing explanations, per the audit's Part 2.
- Applying the committed **under-3-minutes / 3-minutes-or-longer** split
  (using this neutral phrasing, not "valid"/"invalid," since no validity
  policy had, at the time this evidence was first gathered, been approved
  for this category) to the two phenomena gives very different results:
  zero-volume runs are almost entirely under 3 minutes (≈99%, and in any
  case moot under settled decision A1 — see Section 4.D); absent-timestamp
  gaps are not. This figure (9.3% follower, ≈48% leader) was measured
  under **Interpretation M** (count of absent expected bars) as a
  historical baseline; under the now-**settled decision C** (Interpretation
  E, exact elapsed duration), the measured rate is materially higher —
  **23.4447% follower, 51.8013% leader** (Section 4.D).
- Structural anomalies: 0 `high<low`; 1 `close` outside `[low,high]`; 54
  `open` outside `[low,high]` (one single-date/single-bar-of-day cluster,
  2023-03-03 09:15:00, mechanism unconfirmed); 560 negative-volume rows (3
  dates, 189 entities); a cluster of numerically extreme but
  **structurally valid** positive-volume rows at the session's first bar
  (mechanism unconfirmed, not asserted as an error).
- Eight off-session row clusters exist; 7 of 8 are now positively sourced
  to confirmed NSE/BSE Muhurat Trading dates (per the audit's web-sourced
  cross-check — see the explicit boundary note in Section 7 below on why
  that step sits outside this task's own restrictions). **2021-02-24
  remains unconfirmed as either a Muhurat session or a disaster-recovery
  test; neither is asserted as fact.**
- No code anywhere in the repo implements Section 13's rule, or any
  volume-based bar classification, for this or any prior study.

### 2.2 The five audit qualifications, applied explicitly

1. **bars_1min present-row totals differ slightly (~0.002%–0.8%) between
   the original memo and the audit; the exact join-level cause is
   unidentified.** This residual is small relative to every rate and
   percentage cited above and does not change any qualitative conclusion
   this memo relies on. It is **not** resolved here and is **not** a
   precondition for the policy below — the policy is a categorical rule,
   not a number sensitive to a sub-1%-scale count discrepancy.
2. **The leader-gap under-3-minute share is 52.10% (audit) vs. 52.45%
   (original memo) — not exact reproduction.** This is the single
   noisiest figure in the evidence base (smallest denominator, 3,664
   events) and is treated as such below: it supports the qualitative
   finding that roughly half of leader-tier absent-timestamp gaps are
   3 minutes or longer, not a precise point estimate.
3. **The 2017 follower zero-volume rate differs slightly between the two
   documents** (0.0025% audit vs. 0.0026% original) — immaterial to the
   policy; both show the same qualitative pattern (near-zero before 2023,
   rising sharply in 2024/2026).
4. **The top-10-largest-volume ranking finds 10/10, not 8/10, at or
   adjacent to the session open.** This strengthens, not weakens, the
   descriptive observation that extreme positive-volume rows cluster at
   the session's first bar. It does not change the recommendation in
   Section 3.A below (no cutoff is proposed either way).
5. **Interior-gap rates exclude entity-days with no present rows at all;
   that rate was never separately measured.** This matters less than it
   might appear, because — as established in Section 3.4 below — any
   entity-day failing a *much broader*, already-frozen 90%-bar-completeness
   threshold (`PREREGISTRATION_LEAD_LAG_V1.md` Section 12) is excluded in
   its entirety before Section 13's gap-level rule is ever reached. A
   zero-present-row day trivially fails that 90% threshold. The unmeasured
   gap this qualification points to therefore does not block the policy
   below; it is noted as a residual unresolved fact in Section 5.

## 3. Evidence re-read directly: two existing, frozen rules this policy must nest inside, not replace

Before evaluating each data condition, two already-**committed, frozen**
rules from `PREREGISTRATION_LEAD_LAG_V1.md` Section 12 bound this entire
exercise and must not be re-derived or restated as open:

- **Entity-day completeness exclusion: any entity-day with less than 90%
  of its expected bars present is excluded in its entirety** (Section 12,
  original, unchanged). This already removes the extreme case of a
  wholesale missing day, independent of anything decided below.
- **Pre-open/opening-auction bars and the final-5-minutes-before-close
  signal-end minutes (whose forward window would cross 15:30) are already
  excluded** (Section 12, original, unchanged).
- **Section 13's gap-fill rule itself is frozen, per its own text
  ("Frozen, per Section 23")**: `<3`-consecutive-minute gaps
  forward-filled; `>=3`-minute gaps excluded, not imputed. **This memo does
  not propose changing this threshold's value.** (A genuine ambiguity in
  what unit this frozen threshold counts — elapsed timestamp duration, or
  the count of absent expected one-minute bars — was identified; it is
  now **RESOLVED by settled human decision C**, below: elapsed timestamp
  duration, measured exactly, is the operative unit. This is a new,
  prospective methodological decision, not a finding about the original
  2026-11-07 preregistration author's intent, which a dedicated
  investigation found inconclusive — see Section 4.D.) Decision 17's actual open
  question — confirmed by its own decision-table wording — is narrower:
  **which bar categories count as "present" (and therefore feed the 90%
  completeness count and never trigger Section 13's gap logic at all) vs.
  "absent" (and therefore are governed by Section 12/13's already-frozen
  machinery)**, since Section 13's text, read literally, addresses gaps
  between present rows and says nothing about zero-volume or
  structurally-invalid rows that are themselves present.

This reframes the whole task precisely: **the policy below decides bar
classification, not gap-length thresholds.** The thresholds are already
set; what was never decided is which rows are "present, valid," which are
"present, untrustworthy," and which are "absent."

## 4. Evaluation of each data condition

### A. Positive-volume, structurally valid bars

**Recommendation: ACCEPT.** Positive volume alone does not prove a genuine
trade — no trade-count field exists anywhere in the schema to confirm
this, a limitation this memo does not pretend is resolved. But absent any
specific evidence of corruption for this category (the known corruption
classes — OHLC-range violations, negative volume — are separately
identified, structurally detectable anomalies, not a property of
positive-volume rows generally), requiring proof of genuineness beyond
structural self-consistency would be an unjustified, unmeasurable bar.
**Required structural checks, all already measured and all currently
passing except where noted**: `high >= low`; `low <= open <= high`;
`low <= close <= high`; all four price fields non-null, finite, and
positive; `volume >= 0` (not negative). A row failing any of these is not
in this category at all — it moves to category E below.

**Numerically extreme but structurally valid positive-volume rows** (the
session-open cluster, including the single largest value in the table,
confirmed at 10 of the top 10 rows per the audit) **remain in this
category.** No numerical outlier cutoff is proposed, per the task's
explicit instruction and because no principled value is derivable from
the evidence gathered — inventing one here would be exactly the kind of
unjustified threshold this project's methodology is built to avoid. This
is flagged as an open monitoring item (its mechanism is unconfirmed, and
it shares a bar-of-day pattern with the unrelated 54 open-violations and
the negative-volume rows), not excluded or specially treated.

### B. Zero-volume, OHLC-flat bars (82% of zero-volume rows, 5,759/7,018)

**SETTLED HUMAN DECISION A1: ACCEPT.** The user has explicitly adopted
option 1 below as policy — these bars are treated as valid present
observations; their own recorded close is used for return computation;
they are not classified as missing merely because volume is zero. This is
no longer a recommendation pending approval for this specific category;
the three-option analysis is retained below as the evidentiary record
supporting the decision, not as an open choice.

Three defensible choices were considered, with their consequences:

1. **Accept as a present, valid observation.** Consequence: maximizes
   sample retention (the rate is tiny regardless, ≈0.004% of rows either
   way); risk is that the price field may reflect a closing-auction
   clearing mechanism rather than a clean last trade at the specific
   minutes where these cluster (15:28/15:29), a risk that is low-incidence
   given the overall rate but not zero, and is **not resolved** by this
   choice.
2. **Treat as unresolved/ineligible**, i.e. functionally absent despite
   being a present row. Consequence: maximally conservative with respect
   to the unknown vendor semantics, but buys little actual safety here —
   excluding the row does not resolve what `volume=0` means, and discards
   self-consistent, internally-valid data at a rate too small to matter
   for the exclusion-rate question this is ultimately feeding (Decision
   19), while *not* being the row that generates the ambiguity most worth
   worrying about (that is category C).
3. **A separately justified, time-of-day-conditional rule** (e.g. treat
   these differently specifically at 15:28/15:29). Rejected here, not
   because it is unreasonable, but because choosing a rule that varies by
   exactly the minutes where this phenomenon concentrates is one step away
   from outcome-adjacent, post-hoc tuning of a bar-validity rule using the
   very pattern this investigation found — a risk this project's
   methodology is specifically designed to avoid, even though this is a
   data-mechanics question, not a returns question.

**Decision A1 adopts option 1.** The row is present and internally
self-consistent (open=high=low=close); its own close price is used
directly as the bar's price — this requires no invocation of Section 13's
forward-fill machinery at all, since there is no gap to fill. This
decision does not resolve what `volume=0` means — it only settles how to
treat the already-present price field pending that still-unresolved
question (Section 8).

### C. Zero-volume, OHLC-non-flat bars (18%, 1,259/7,018)

These bars report real intra-bar price movement despite zero recorded
volume — a logical inconsistency with the standard "no trade this minute"
reading, concentrated at the same closing-auction-adjacent minutes
(15:28/15:29) as category B. **What can be inferred**: the row is present,
and (unlike category E) passes the structural OHLC/volume self-consistency
checks in Section A above — a non-flat OHLC range is not itself a
structural violation. **What cannot be inferred**: whether the price field
reflects a genuine, usable price (e.g. an auction-derived close Angel's
aggregator populated without an associated volume figure) or a vendor-side
defect that happens not to trip any structural check. The investigation
and audit both leave this mechanism explicitly unconfirmed.

**SETTLED HUMAN DECISION B1: FLAG / INELIGIBLE PENDING RESOLUTION — its
own, fourth category, merged with neither B (zero-volume-flat) nor E
(structurally invalid).** The user has explicitly adopted this treatment
as policy, including both of its components: never use this category's
own OHLC values, and never impute its own timestamp. It is not accepted
as a trustworthy present observation
(unlike B, this bar's own price field is not merely a flat carry-forward —
it asserts a specific price move with no supporting volume, which is a
materially different and more active claim to distrust), and it is not
reclassified into "structurally invalid" (unlike E, it violates no OHLC or
sign constraint; calling it "corrupted" would overstate what is actually
known). For any downstream counting (completeness percentage, gap-length
measurement), this category is treated as **functionally absent** — i.e.
it does not count toward Section 12's 90% present-bar threshold and does
not break an otherwise-contiguous absence run into two shorter ones — pending
resolution, since its price cannot currently be trusted as a valid
observation. This is a conservative, explicitly-labeled METHODOLOGICAL
RECOMMENDATION, not a forced conclusion.

**Two distinct operations, not to be conflated (see Section 4.E below for
the identical distinction applied to structurally invalid bars)**: (1)
rejecting this category's own reported price as a usable observation —
settled by decision B1, FLAG/INELIGIBLE; and (2) whether a replacement
price may instead be **imputed** at this bar's exact timestamp via
Section 13's short-gap forward-fill mechanism, treating the timestamp as
if it were a genuine absence. **Decision B1 explicitly settles operation
(2) as well: never.** The timestamp is **excluded outright** wherever a
computation needs it, never imputed — this is now a settled decision, not
merely this memo's conservative default pending approval. (No explicitly
supported rule authorizing imputation for this category exists anywhere
in this document, the prior investigation, or the prior audit; decision
B1 confirms that absence of a rule means "never," rather than leaving it
open.) Treating a bar as functionally absent for gap-length classification
does not, by itself, authorize imputing a value at its own timestamp —
decision B1 settles this explicitly rather than leaving it as an inference
from the counting treatment.

### D. Absent expected timestamps

Kept categorically separate from present zero-volume bars throughout (per
the task's instruction and Section 3 above).

**Exact frozen text governing this threshold** (`PREREGISTRATION_LEAD_LAG_V1.md`,
Section 13, frozen per Section 23): *"Unchanged from the original version:
<3-consecutive-minute gaps forward-filled for return computation;
>=3-minute gaps excluded, not imputed."* This memo does not re-derive or
change this threshold's value.

**Correction to a prior version of this memo**: an earlier draft of this
section incorrectly claimed that elapsed-clock-time and the count of
absent expected one-minute bars are numerically identical for this data.
**They are not.** For two present rows bounding a gap,
`absent expected bars = elapsed timestamp minutes - 1` — e.g. present
rows at 09:15 and 09:18 are 3 minutes apart by elapsed clock time, but
only 2 one-minute bars (09:16, 09:17) are actually absent between them.
That false equivalence is withdrawn.

**The ambiguity, and how it was resolved.** Section 13's text —
"<3-consecutive-minute gaps" — does not state which of two quantities it
counts, and no other part of the preregistration (including the
Section 23 frozen-parameter table, which repeats the identical phrase
with no further elaboration) disambiguates it:

- **Reading (i), elapsed timestamp duration**: gap length = true elapsed
  time between the two bounding present rows (09:15→09:18 = 3 minutes →
  classified >=3, excluded).
- **Reading (ii), count of absent expected bars**: gap length = number of
  absent minute-slots strictly between the two bounding present rows
  (09:15→09:18 = 2 absent bars → classified <3, forward-filled).

These two readings disagree exactly at the boundary the threshold is
meant to discriminate — a real, classification-relevant disagreement, not
a rounding-scale one. **A dedicated original-intent investigation**
(inspecting git history, the first preregistration commit's fuller
original Section 13 text, and the verbatim master-spec prompt) **found
the evidence inconclusive** — a strong indirect lean toward the
elapsed-time framing ("the gap *since* the last valid bar," and the
master spec's general "do not use candle counts as substitutes for
elapsed time" principle), but nothing meeting the bar for a confirmed
original intent. **SETTLED HUMAN DECISION C**: rather than leave this
open indefinitely, the user has made a new, prospective methodological
decision — **adopt reading (i), elapsed timestamp duration, measured
exactly** (true duration via timestamp subtraction, not a
minute-truncated approximation — see the precision note below). This is
a decision about what the policy *will* do going forward, explicitly not
a claim about what the original 2026-11-07 preregistration author
intended.

**Precision note, itself independently verified**: an initial measurement
of decision C used `DATE_DIFF('minute', prev_ts, ts)` as a proxy for
elapsed duration. This is **not exact** — DuckDB's `DATE_DIFF('minute',...)`
counts minute-*boundary crossings*, not true elapsed seconds, and the two
diverge whenever a bounding timestamp carries a nonzero-seconds offset
(408,297 of 169,935,257 `bars_1min` rows, 0.24%, table-wide). A follow-up
exact-duration verification (direct `EPOCH()`-based timestamp subtraction,
compared against exactly 180 seconds) found: only **167 of 974,499**
identified gaps (0.0171%) even have a non-`:00`-aligned bounding
endpoint — all 167 traced to one entity (`INE628A01036`) — and of those,
only **3 gap classifications actually changed** (all follower-tier, all
in the direction DATE_DIFF-wrongly-excluded → exact-duration-correctly-
forward-filled, all real 2017 observations), with **zero** leader-tier
changes. The figures below are the **exact-duration** measurements (the
authoritative ones); the `DATE_DIFF`-based figures are retained
parenthetically as an intermediate, now-superseded approximation, not as
a competing result.

**D1 — Gaps classified under the 3-minute threshold (decision C: exact
elapsed duration).** Section 13's committed rule: forward-filled for
return computation, from the nearest preceding present-valid bar
(Sections 4.A/4.B).

**D2 — Gaps classified at or above the 3-minute threshold (decision C:
exact elapsed duration).** Section 13's committed rule: excluded, not
imputed.

**Measured exclusion rates, both tiers, three ways (M historical baseline
/ `DATE_DIFF`-based E, superseded / exact-duration E, authoritative)**:

| Tier | M (absent-bar count, historical) | `DATE_DIFF`-based E (superseded intermediate) | **Exact-duration E (authoritative)** | Denominator |
|---|---|---|---|---|
| Follower | 9.3066% (90,352/970,835) | 23.4450% (227,612/970,835) | **23.4447% (227,609/970,835)** | 970,835 identified interior gaps, tier-assigned entities, regular session, unchanged bounding-row scope |
| Leader | 47.8985% (1,755/3,664) | 51.8013% (1,898/3,664) | **51.8013% (1,898/3,664)** | 3,664 identified interior gaps, same scope |

The headline move is the **M → E threshold-interpretation change itself**
(decision C): +14.14 percentage points for followers, +3.90 for leaders —
this is the substantive effect of adopting elapsed duration over
absent-bar count. The subsequent `DATE_DIFF`-approximation → exact-duration
precision correction moved the follower rate by **−0.0003 percentage
points** and the leader rate by **0.0000** — three orders of magnitude
smaller, confined to 3 gaps / 1 entity. **This evidence is not sensitive
to which E figure (DATE_DIFF-approximate or exact) is cited** — both are
reported above for full traceability, but the exact-duration figures are
the ones this policy adopts.

**The 137,403-gap "boundary set" (137,260 follower, 143 leader, 316
distinct entities), first identified when comparing M against the
`DATE_DIFF`-based E approximation, is the set of gaps with exactly 2
absent bars (equivalently, `DATE_DIFF('minute',...)=3`)** — i.e. the set
whose classification flips between M and `DATE_DIFF`-based E. **This
137,403 figure must not be read as 137,403 independently-confirmed
exact-duration flips.** It is the correct count of the M→`DATE_DIFF`-E
boundary under that intermediate approximation; the subsequent
exact-duration verification found that, of this same underlying gap
population, only 3 gaps' classifications actually change once true
elapsed duration (not minute-boundary-crossing count) is used, because
only 167 of all 974,499 gaps have any non-`:00`-aligned endpoint at all
(see the precision note above). The 137,403 figure remains the correct
description of the M-vs-E *threshold-interpretation* effect; it is not,
and was never claimed to be, a description of the separate `DATE_DIFF`-
precision question.

**Secondary diagnostic — interaction with B1 and structurally-invalid
bars (kept separate from the headline D1/D2 figures above, per Section
4.C/4.E's bounding-row treatment).** A separate measurement recomputed the
gap set using a bounding-row definition that excludes B1 (category-C) and
structurally-invalid (category-E) rows from counting as valid bounding
points (they still extend a surrounding absence span without being
imputed themselves, per Sections 4.C/4.E). This measurement was run under
the `DATE_DIFF`-based E approximation, **not** re-verified under
exact-duration E (given the exact-duration correction's measured effect
is three orders of magnitude smaller than the M→E effect and is confined
to a different entity than the B1/invalid-bar interaction's affected
entities, a materially different result is not expected, but **this has
not been directly measured and is not asserted as confirmed**). Result,
reported as its own diagnostic with its own denominator — **not** folded
into the headline D1/D2 rates above:

| Tier | Gap count (redefined bounding rows) | `DATE_DIFF`-E exclusion rate (this diagnostic) | Headline `DATE_DIFF`-E rate (unchanged bounding rows) | Difference |
|---|---|---|---|---|
| Follower | 971,149 (+314) | 23.44% (227,679/971,149) | 23.4450% | −0.005pp — driven by the **larger denominator** (971,149 vs. 970,835), reflecting 314 additional/merged gap events once B1/invalid rows stop counting as bounds, not by any change to the 3-minute test itself |
| Leader | 3,692 (+28) | 51.49% (1,901/3,692) | 51.8013% | **−0.31pp** — this is not negligible relative to its own cause: it is driven entirely by the **denominator growing from 3,664 to 3,692** (28 additional/merged gap events among a small, already-noisy leader-tier gap population), i.e. by the bounding-row-redefinition policy layer (Sections 4.C/4.E), not by decision C's threshold-interpretation choice or by the `DATE_DIFF`-vs-exact-duration precision question |

This secondary layer affects **627 specific merge events across 261
entity-months** (194 distinct entities) — a small, concrete, traceable
set, not a population-wide effect. **This memo does not assert a final,
single adjusted rate combining both layers** (decision C's
threshold-interpretation effect, and the B1/invalid bounding-row
redefinition effect) — the evidence available does not permit an
unambiguous composition without a dedicated exact-duration remeasurement
of this specific secondary gap set, which was not performed. The
**headline, authoritative rates for decision C are the exact-duration
D1/D2 figures above (23.4447% follower, 51.8013% leader)**, computed under
the unchanged, original bounding-row scope; the B1/invalid-bar interaction
is reported here as a separate, smaller-magnitude diagnostic finding, not
as a replacement headline number.

**D3 — Session-edge and whole-entity-day absence.** Unaffected by decision
C (this is a scope question, not a length-classification question).
Already substantially addressed by Section 12's pre-existing, frozen
90%-entity-day-completeness exclusion and pre-open/final-5-minute
exclusions (Section 3 above) — an entity-day with zero or near-zero
present rows never reaches Section 13's gap-level logic at all; it is
excluded wholesale first. The residual, narrower question — a single
absent timestamp sitting exactly at a session boundary within an
otherwise-qualifying entity-day — is addressed by the session-boundary
requirement in Section 5 below, not by a new numeric threshold.

**Observed leader/follower asymmetry and time-of-day concentration**
(leader gaps far fatter-tailed than follower; invalid gaps concentrated at
midday for followers, close-of-session for leaders) are real, measured
facts, now re-confirmed under decision C's exact-duration measurement,
that change **how much** of each tier's data D2 ultimately excludes —
directly relevant input to Decision 19's exclusion-rate measurement — but
do not change **the rule itself**, which is tier- and time-of-day-agnostic
by design.

**Does decision C affect the cause of absence, or anything else about
zero-volume runs?** No. Decision C is purely about how to measure and
classify the *length* of an already-identified absent-timestamp gap.
**Zero-volume run length is mathematically unaffected by the M-vs-E
(or `DATE_DIFF`-vs-exact-duration) distinction** — a zero-volume run's
continuation test is exact 1-minute adjacency between consecutive
*present* rows, with no absent row inside it at all, so there is no
quantity for M-vs-E to disagree about. This was independently confirmed by
re-inspecting the run-length SQL, not merely asserted. Separately, and
more fundamentally: **under settled decision A1, accepted flat
zero-volume bars never invoke Section 13's gap-handling machinery in the
first place** — the earlier exploratory "<3/>=3 applied to zero-volume
runs" analysis (Section 2.1 above) was a diagnostic for an
already-superseded policy option, not an operative part of this policy.

**D3 — Session-edge and whole-entity-day absence.** Already substantially
addressed by Section 12's pre-existing, frozen 90%-entity-day-completeness
exclusion and pre-open/final-5-minute exclusions (Section 3 above) — an
entity-day with zero or near-zero present rows never reaches Section 13's
gap-level logic at all; it is excluded wholesale first. The residual,
narrower question — a single absent timestamp sitting exactly at a session
boundary within an otherwise-qualifying entity-day — is addressed by the
session-boundary requirement in Section 5 below, not by a new numeric
threshold.

**Observed leader/follower asymmetry and time-of-day concentration**
(leader gaps far fatter-tailed than follower; invalid gaps concentrated at
midday for followers, close-of-session for leaders) are real, measured
facts that change **how much** of each tier's data D2 ultimately excludes
— directly relevant input to Decision 19's exclusion-rate measurement —
but do not change **the rule itself**, which is tier- and
time-of-day-agnostic by design (Section 13's text draws no such
distinction, and this memo does not propose one, for the same
post-hoc-tuning-avoidance reason given in category B).

**Should the rule use elapsed time or a count of absent expected minute
bars?** Settled by decision C: elapsed time, measured exactly. What this
memo additionally fixes, for implementation clarity, is the *scope* of
what counts as a bounding "present" row for that measurement: only
present-valid rows per Sections 4.A/4.B, for the same
`(entity_id, trade_date)`, restricted to the regular session (Section 5
below) — a category-C or category-E row does **not** count as a bounding
present row (Sections 4.C, 4.E), and gap measurement never crosses a
session boundary regardless of `trade_date` grouping (Section 5). The
headline D1/D2 figures above use the *original*, unchanged bounding-row
scope (matching the existing audit); the effect of additionally applying
this category-C/E bounding-row exclusion is reported separately, as a
secondary diagnostic, above — it is not yet folded into the headline
figures (see that diagnostic's own caveats).

### E. Structurally invalid bars

**Recommendation: EXCLUDE outright. Never repaired, never forward-filled,
regardless of gap length.** This is the one category in this memo with no
genuine alternative considered — a self-contradictory row cannot be a
valid endpoint under any reading of the schema's own stated constraints,
independent of what caused it. Exact rule: a bar is structurally invalid,
and therefore excluded, if any of the following holds: `high < low`;
`open` outside `[low, high]`; `close` outside `[low, high]`; any of
`open`/`high`/`low`/`close` null, non-finite, or `<= 0`; `volume < 0`.
Measured incidence table-wide: 0 / 1 / 54 / 0 / 560 respectively (the open-
and close-violation sets do not overlap). **Extreme-but-positive volume is
explicitly excluded from this category** — it belongs in category A,
flagged, not excluded, per the task's instruction and Section A above.

**Two distinct operations must not be conflated here**: (1) rejecting the
invalid row's own reported OHLC values — never used, under any
circumstance; and (2) whether a replacement price may instead be
**imputed** at that exact timestamp from a preceding valid close, via
Section 13's short-gap forward-fill mechanism, by treating the row as
equivalent to a genuine absence. **Section 13's frozen text authorizes
operation (2) only for genuinely absent rows** — timestamps where no row
exists at all. It says nothing about a present-but-structurally-invalid
row, and does not settle whether such a row may be treated as eligible
for the same forward-fill treatment. **Treating a row as functionally
absent for counting purposes does not, by itself, authorize imputing a
replacement price at its own timestamp** — these are separable questions,
and this memo does not assume the first settles the second.

**Resolution adopted here, as a conservative methodological choice
requiring explicit human approval — not as something Section 13's frozen
text already settles:**

- For the purpose of classifying the length of *neighboring* genuine
  absences (deciding whether a run of real absent timestamps on either
  side of an invalid row is, combined, under or at/over the Section 13
  threshold), an invalid row's timestamp counts toward the span rather
  than breaking it — it provides no trustworthy information, so it should
  not silently reset the gap counter.
- **The invalid row's own timestamp, however, is never itself the target
  of an imputed value.** If an endpoint computation needs exactly that
  timestamp (`t-35`, `t-5`, `t`, or `t+h`), that endpoint is excluded
  outright, never forward-filled, regardless of how short the surrounding
  combined span is classified. This preserves the "never repaired, never
  forward-filled" rule stated at the top of this section without
  contradicting the counting treatment just described.

This resolution is **not forced by Section 13's frozen text, which is
silent on this interaction** — it is this memo's recommended default,
requiring the same human approval as every other methodological choice in
this document, not an automatic consequence of "functionally absent"
classification. The identical two-operation distinction is applied to
category C above.

## 5. How these rules apply across `t-35`, `t-5`, `t`, and `t+h`

The same bar-category rule (A/B/C/E above, plus the D1/D2 gap logic) is
applied **identically** at every endpoint the unified eligibility check
needs — `t-35`, `t-5`, `t` for the pre-signal/control side, and `t+h` for
the forward side — per the following principles, each directly
implementing an already-approved or already-recommended piece of the
proposal's own Section 3 construction, not a new design:

1. **Pre-signal eligibility uses only information available by signal
   time** (wall-clock `t+1`, per the proposal's verified bar-start
   convention, Section 5) — the bar-category rule is applied using the
   data as it stood at that moment, never using anything from `t+h`.
2. **The eligible subset and its weights are frozen before `t+h` is
   examined.** This memo adds nothing here beyond restating the existing,
   already-specified Option 2 steps 2–3 and Option 1's full-roster
   requirement — both already satisfy this principle by construction.
3. **A `t+h` endpoint failure (per the identical bar-category rule) is
   checked only after freezing, as a separate, subsequent,
   whole-observation gate, and never retroactively changes the frozen
   pre-signal subset's composition.** This is already how Option 2's steps
   7–8 are written; this memo confirms the same bar-category rule — not a
   looser or stricter one — governs that later check.
4. **No partial forward portfolio return, future-informed reweighting,
   replacement, or imputation of a missing or excluded endpoint**, at any
   of the four time points, under either basket option. This is already
   stated in the proposal's Section 3 and is not weakened or strengthened
   here.
5. **A missing or excluded endpoint must not be silently converted into a
   zero return.** An observation whose `t+h` endpoint is excluded (absent
   per D2, or structurally invalid per E, or still-unresolved per C, for
   any required constituent) is **discarded** (coded as missing/`NaN`,
   dropped from that horizon's sample) — never coded as a zero or
   otherwise substituted value. This is a direct, necessary consequence of
   principle 4 and of Option 2's own step 8 ("discard the entire
   observation"); it is stated explicitly here because the proposal itself
   does not spell out the zero-return failure mode by name.
6. **Whether an excluded bar invalidates only that entity's eligibility or
   the entire portfolio observation depends on which basket option is
   eventually chosen (Decision 19) — this is a genuine dependency, not
   assumed away:**
   - **Under Option 1** (100% roster completeness): there is no
     smaller "frozen subset" than the full ~160-name roster, at any of the
     four endpoints. A single entity's bar failing the category rule at
     *any* of `t-35`, `t-5`, `t`, or `t+h` is sufficient to disqualify the
     **entire observation** — Option 1 is, by construction, stricter and
     more easily triggered at this step than Option 2 (already noted in
     the proposal's own Section 3, "Option 1 ... its own future-dependence
     revisited").
   - **Under Option 2**: a pre-signal (`t-35`/`t-5`/`t`) bar failure is
     **entity-level** at step 2 — that single entity is dropped from the
     eligible subset; the observation survives if the remaining subset
     still clears the (separately OPEN, Decision 10) breadth threshold. A
     `t+h` bar failure, however, is **always whole-observation** under
     Option 2 as well (step 7–8: any frozen-subset member failing at `t+h`
     discards the entire observation) — so the entity-level/whole-observation
     distinction applies only to the *pre-signal* side; the *forward* side
     is whole-observation-level under both options.

### Session-boundary requirement (not a new session classification)

The investigation found that partitioning only by `trade_date` is
insufficient: eight dates carry a second, multi-hour same-day cluster of
rows well after the regular session's close (seven confirmed Muhurat
Trading dates; 2021-02-24 unresolved), and any gap/run detection keyed on
raw `ts` difference or on `trade_date` alone, without also bounding the
regular-session clock-time window, would silently bridge the several-hour
gap between the regular close and that second cluster as if it were one
ordinary absence. **This memo does not propose classifying which
off-session cluster is a genuine Muhurat session and which (if any) is
something else** — that remains Decision 21's unresolved question, and
2021-02-24's identity is not asserted here. The requirement is narrower
and does not depend on resolving that question: **all bar-category and
gap-length logic described in Section 4 must be scoped to the regular
session clock-time window only** (candidate `09:15`–`15:29`, pending the
still-open exact-anchor confirmation, Decision 11) **and must never treat
a row outside that window, for any date, as adjacent to a regular-session
row for gap-length or run-length purposes — regardless of why that
off-session row exists.** This is exactly the scoping choice the
investigation itself already applied as a measurement convenience; this
memo elevates it to a stated implementation requirement for Decision 17's
policy, not a new session-boundary classification.

## 6. Decision table

| Data condition | Recommended treatment | Evidence supporting it | Remaining uncertainty | Decision type |
|---|---|---|---|---|
| A. Positive volume, structurally valid (incl. numerically extreme) | **ACCEPT** | Full-table structural checks (0 OHLC violations, 0 negative volume among this subset by definition); no trade-count field exists to require more | Whether `volume>0` always means a genuine trade is unresolved (no vendor confirmation); extreme-value mechanism unconfirmed | Methodological choice (conservative default, not forced) |
| B. Zero-volume, OHLC-flat | **SETTLED DECISION A1 — ACCEPT** (as a present, valid price observation; uses its own close directly) | 82% of zero-volume rows; self-consistent OHLC; tiny overall rate (≈0.004%); 60% of all zero-volume rows cluster at 15:28/15:29, consistent with a closing-auction mechanism | What `volume=0` represents at the vendor level remains unresolved (the decision settles treatment, not vendor semantics) | Settled human decision (A1) |
| C. Zero-volume, OHLC-non-flat | **SETTLED DECISION B1 — FLAG / INELIGIBLE PENDING RESOLUTION** — own reported price never used; counts toward neighboring gap-length classification; own timestamp never imputed (Section 4.C) | 18% (1,259/7,018) of zero-volume rows; logically inconsistent with "no trade"; concentrated at the same two closing minutes | Mechanism entirely unconfirmed; cannot be resolved without vendor documentation or live API access (the decision settles treatment, not the underlying mechanism) | Settled human decision (B1) |
| D1. Absent timestamp, interior gap classified under the 3-minute threshold (decision C: exact elapsed duration) | **ACCEPT** (forward-filled, per already-frozen Section 13 text) | Section 13 (committed, frozen); measured exact-duration rate: follower 76.5553%, leader 48.1987% under threshold (Section 4.D) | Cause of absence unresolved; original-author intent for the threshold's unit was investigated and found inconclusive — decision C settles it prospectively, not retroactively | Threshold value: already-approved (preregistration-frozen). Unit interpretation: **settled human decision (C)** |
| D2. Absent timestamp, interior gap classified at/above the 3-minute threshold (decision C: exact elapsed duration) | **EXCLUDE** (per already-frozen Section 13 text) | Section 13 (committed, frozen); measured exact-duration exclusion rate: **23.4447% follower, 51.8013% leader** (vs. historical M baseline 9.31%/47.90%; vs. an intermediate `DATE_DIFF`-based approximation of 23.4450%/51.8013%, superseded) | Whether the threshold's *value* (3 minutes) is the economically correct cutoff is not established; the *unit* question is now settled (C), not open | Threshold value: already-approved (preregistration-frozen). Unit interpretation: **settled human decision (C)**; underlying economic-cutoff question remains open |
| D3. Session-edge / whole entity-day absence | **EXCLUDE** (already handled by Section 12's frozen 90%-entity-day-completeness rule, upstream of this policy) | Section 12 (committed, frozen) | Fully-missing-day rate was never separately measured (audit qualification 5); does not block this policy | Already-approved (preregistration-frozen) |
| E. Structurally invalid (OHLC violation, negative volume, null/non-finite/non-positive price) | **EXCLUDE** — own reported values never used, never repaired or forward-filled at its own timestamp; counts toward neighboring gap-length classification only (Section 4.E) | Full-table reproduction: 0/1/54/0/560 by sub-type; zero overlap between violation sets | Root cause of the 54-row cluster and the 560 negative-volume rows is unconfirmed (plausible shared vendor artifact, not proven); whether functionally-absent classification may ever extend to authorizing imputation at its own timestamp is unresolved by Section 13's frozen text — resolved here conservatively (never), pending human approval | Measured + methodological choice (the exclusion itself has no real alternative; the imputation question and the root-cause question are both separate and unresolved) |
| Off-session rows (regular-session scoping requirement) | **EXCLUDE from all gap/run/endpoint logic**, regardless of cause | 8 dates, ≈93,400 rows; 7/8 now sourced to confirmed Muhurat dates; 2021-02-24 unresolved | 2021-02-24's identity unresolved; exact session anchor (`09:15` vs `09:16` start) unresolved (Decision 11) | Methodological choice (scoping requirement) + requires human decision (exact anchor) |

## 7. Recommended final Decision 17 policy, in precise operational language

> **A bar is PRESENT-VALID** if it is positive-volume and structurally
> valid (Section 4.A), or zero-volume with `open=high=low=close`
> (Section 4.B); its own OHLC close is used directly as the endpoint
> price, with no forward-fill step invoked.
>
> **A bar is FUNCTIONALLY ABSENT**, for the purpose of classifying the
> length of a surrounding gap (including the Section 12 90%
> entity-day-completeness count), if it is a true absent expected
> timestamp, OR zero-volume with `open≠high` or `low≠high` (non-flat;
> Section 4.C, pending resolution), OR structurally invalid by any of the
> five criteria in Section 4.E. A functionally-absent bar does not
> interrupt an otherwise-contiguous absence run into two
> separately-measured shorter runs.
>
> **Only a true absent expected timestamp — never a category-C or
> category-E bar's own timestamp — is eligible to receive an imputed
> value under Section 13's forward-fill mechanism.** If an endpoint
> computation needs exactly a category-C or category-E timestamp, that
> endpoint is excluded outright, regardless of how the surrounding
> combined span is classified (Sections 4.C, 4.E). Treating a bar as
> functionally absent for span-length classification does not, by itself,
> authorize imputing a value at its own timestamp.
>
> **Section 13's exact frozen text** — *"<3-consecutive-minute gaps
> forward-filled for return computation; >=3-minute gaps excluded, not
> imputed"* — **then applies to spans of true absent expected
> timestamps**, restricted to the regular session window only (Section
> 5's session-boundary requirement) and never bridging a session boundary
> regardless of `trade_date` grouping. **Per SETTLED HUMAN DECISION C**,
> the threshold's unit is **elapsed timestamp duration between the
> bounding present-valid rows, measured exactly** (true duration via
> timestamp subtraction — e.g. `EPOCH(ts) - EPOCH(prev_ts)` — not a
> minute-truncated approximation such as `DATE_DIFF('minute', ...)`,
> which was verified to diverge from true duration whenever a bounding
> timestamp carries a nonzero-seconds offset). Spans with a duration under
> 3 minutes (180 seconds) are forward-filled from the nearest preceding
> present-valid bar; spans of 3 minutes (180 seconds) or more are
> excluded, not imputed. This is a new, prospective methodological
> decision by the user — not a finding about the original preregistration
> author's intent, which was investigated and found inconclusive.
>
> **This identical rule is applied at `t-35`, `t-5`, `t`, and `t+h`**,
> with pre-signal eligibility frozen before any `t+h` check (Section 5,
> principles 1–3), no partial/reweighted/imputed/zero-substituted forward
> return under any circumstance (Section 5, principles 4–5), and the
> entity-level-vs-whole-observation consequence of a failure determined by
> whichever basket option (Decision 19) is eventually approved (Section 5,
> principle 6).

**A1, B1, and C are SETTLED HUMAN DECISIONS, not entries in the
measurement/choice/open-question taxonomy below.** They are listed
separately here for clarity, then excluded from 7.1–7.3's categorization
of this memo's own remaining recommendations and open questions:

- **A1**: zero-volume, OHLC-flat bars — ACCEPT.
- **B1**: zero-volume, OHLC-non-flat bars — FLAG/INELIGIBLE, own values
  never used, own timestamp never imputed.
- **C**: Section 13 threshold unit — Interpretation E, exact elapsed
  timestamp duration (not `DATE_DIFF('minute')`-truncated, verified).

### 7.1 Which parts are directly supported by measurement

- The exact counts and rates for every bar category (A–E) and for the
  off-session clusters.
- That the committed 3-minute threshold, applied literally (under either
  M or E), has almost no practical effect on zero-volume runs — and in any
  case decision A1 means it is never invoked for that category at all —
  but a material effect on absent-timestamp gaps, now quantified
  precisely under decision C: **23.4447% follower / 51.8013% leader**
  exclusion, versus the historical M baseline of 9.31%/47.90%.
- That the `DATE_DIFF('minute')`-vs-exact-duration precision question
  (raised independently of the M-vs-E threshold-interpretation question)
  has a measured, negligible effect: 3 flipped gap classifications out of
  974,499, confined to one entity.
- That zero-volume and absent-timestamp phenomena have materially
  different length distributions, time-of-day concentrations, and
  tier-sensitivities.
- That 7 of 8 off-session clusters are genuine, sourced Muhurat Trading
  dates.

### 7.2 Which parts are conservative methodological choices, not empirical conclusions

- Treating structurally invalid and category-C bars as non-interrupting
  for gap-run *classification* purposes, while never imputing a value at
  their own timestamp (Sections 4.C, 4.E) — the two are kept separate so
  that "functionally absent" is not read as automatically authorizing
  imputation. (For category C specifically, the "never impute" half is
  now settled by decision B1; the "non-interrupting for classification"
  half, and the identical treatment for category E, remain this memo's
  own conservative recommendation, not yet elevated to a settled
  decision.)
- Not inventing a numerical cutoff for extreme-but-positive volume.
- Scoping all gap/run logic to the regular session regardless of
  off-session-cluster cause.
- Not composing the B1/invalid-bar bounding-row diagnostic into the
  headline exact-duration D1/D2 rates (Section 4.D) absent a direct
  measurement of that specific combination.

### 7.3 Which questions genuinely require a human decision

- Whether to approve the **remainder** of this policy — categories A and
  E's recommendation status (still pending approval, not settled by
  A1/B1/C), and the overall Decision 17 policy as a whole. (A1, B1, and C
  themselves are settled and are not reopened by this list.)
- The exact session anchor (`09:15` vs. `09:16` as the first valid
  regular-session bar — Decision 11, unresolved by this memo).
- Which basket option (1 or 2) governs the entity-level-vs-whole-observation
  consequence described in Section 5, principle 6 (Decision 19, explicitly
  out of scope for this memo).
- The follower-side breadth threshold value and form (Decision 10,
  unrelated numeric question, explicitly out of scope here).
- Whether category C's pending resolution is ever actually resolvable
  without vendor documentation or live API access this project does not
  currently have (this is about the underlying vendor-semantics mechanism,
  not about decision B1's already-settled treatment of category C).
- **Whether a category-E (structurally invalid) bar's own timestamp may
  ever be eligible for imputation under some future, separately-approved
  rule.** This memo's default is never, pending such a rule (Section 4.E).
  (The equivalent question for category C is already settled by decision
  B1: never.)
- **Whether, and how, to compose the B1/invalid-bar bounding-row
  diagnostic (Section 4.D) into a single adjusted exclusion rate.** The
  evidence available does not permit an unambiguous composition without a
  dedicated exact-duration remeasurement of that specific combined gap
  set, which has not been performed.

### 7.4 Whether any additional measurement is strictly necessary before this policy can be finalized

**No, with one narrow exception already identified.** The policy above is
a categorical bar-classification rule; none of
its five categories (A–E) or the off-session scoping requirement depends
on a number this memo lacks. The genuinely open items (category C's root
cause, the 54-row and 560-row anomaly mechanisms, 2021-02-24's identity)
are not resolvable by any further **internal, read-only measurement** —
they require vendor documentation or live API access, which is outside
this investigation's access and outside this task's restrictions. The one
measurement that remains useful and necessary is the **exclusion rate**
this policy, once approved, would produce under each basket option — but
that is explicitly Decision 19's own measurement, explicitly prohibited in
this task, and is not a precondition for approving the classification
policy itself (the policy must exist first so that the exclusion-rate
measurement has a definition to measure against). **The one narrow
exception**: if the B1/invalid-bar bounding-row diagnostic (Section 4.D)
is ever needed as a precise, composed adjustment to the headline
exact-duration D1/D2 rates (rather than as a separate, smaller-magnitude
diagnostic, which is sufficient for this memo's current purposes), a
targeted re-measurement of that specific gap set under exact-duration E
would be needed — not performed here, and not required to adopt or act on
decisions A1/B1/C as stated.

## 8. Remaining uncertainties (full list)

- What `volume=0` represents at the vendor level (no-trade suppression vs.
  something else) — unresolved, not resolvable internally.
- What causes an absent expected timestamp — three competing explanations
  remain open, not resolvable internally.
- The mechanism behind the 54 open-violation rows, the 560 negative-volume
  rows, and the extreme-maximum-volume clustering — all plausibly related
  vendor-side artifacts, none confirmed.
- 2021-02-24's identity (Muhurat-adjacent anomaly vs. disaster-recovery
  test vs. something else) — unconfirmed; not a Diwali date under any
  calendar reading.
- The exact regular-session anchor (`09:15` vs. `09:16`) — Decision 11,
  unresolved.
- The fully-missing-entity-day rate was never separately measured (audit
  qualification 5) — does not block this policy, per Section 2.2 above.
- Whether category C should ultimately be resolved toward B-like
  acceptance or E-like exclusion once (if ever) more vendor evidence
  becomes available — this memo recommends neither permanently, only
  "pending."
- **RESOLVED by settled decision C**, not by original-intent discovery:
  which of two readings Section 13's frozen `<3`/`>=3`-minute threshold
  counts is now a settled prospective policy choice (elapsed timestamp
  duration, measured exactly) — but the question of what the original
  2026-11-07 preregistration author actually intended remains, and will
  remain, genuinely inconclusive (a dedicated investigation found only
  strong indirect evidence, not a confirmed answer). Retained here as a
  historical note, not an open item blocking anything.
- Whether a category-E bar's own timestamp may ever be eligible for an
  imputed replacement value under a future, separately-approved rule.
  This memo's default, pending such a rule, is never (Section 4.E) —
  "functionally absent for gap-length classification" is explicitly not
  treated as automatically authorizing imputation. (The equivalent
  question for category C is settled by decision B1: never.)
- Whether, and how, the B1/invalid-bar bounding-row diagnostic (Section
  4.D: follower 23.44% vs. headline 23.4447%; leader 51.49% vs. headline
  51.8013%) should ultimately be composed into a single adjusted rate,
  and whether that composition should be re-verified under exact-duration
  E specifically (it was measured only under the superseded
  `DATE_DIFF`-based E approximation). Not resolved by this memo.

## 9. Explicit statement of what did not occur in this task (or in this update)

No Decision 19 exclusion-rate or distortion measurement, no Section 3D
missingness-emulation or sample-adequacy measurement, no strategy-outcome
inspection, no return/signal/correlation/predictive-statistic computation,
no Phase 4 work, no trial registration or ledger change, and no edit to
the preregistration, the methodology proposal, any source code, or either
existing Decision 17 investigation/audit document occurred in this task
or in this update. This update made no new database query of its own —
every figure it incorporates was produced and independently verified by
four separate, already-completed, read-only measurement tasks (the
original investigation, the reproducibility audit, the Interpretation-E
impact measurement, and the exact-duration precision verification), each
of which confirmed `git status`/`git diff` showed no repository change.

## 10. Files touched, access, and restriction compliance

- **Files created or modified by this update**:
  `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md` (this file) —
  edited in place to incorporate settled decisions A1/B1/C and the
  verified Interpretation-E measurement. **No other file was created or
  modified.**
- **Git status before this update**: six untracked files (this document
  itself, plus its predecessors from earlier in this review chain —
  `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`,
  `lead_lag/DECISION_17_REPRODUCIBILITY_AUDIT.md`,
  `lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md`,
  `lead_lag/METHODOLOGY_PROPOSAL_2026-11-08_PORTFOLIO_LEVEL_ESTIMAND.md`,
  `lead_lag/METHODOLOGY_REVIEW_2026-11-08_ESTIMAND_AND_NULL.md`); HEAD at
  `9f71b65e006f937760e39a9f65035c69a1ef8df9`; tracked-file diff empty;
  working tree otherwise clean.
- **Git status after this update**: identical set of untracked files
  (same six, this document re-edited in place, not renamed or
  duplicated); HEAD unchanged; tracked-file diff still empty. Nothing
  staged, committed, amended, or pushed.
- **Precisely what this does and does not establish**: `git diff --stat`
  reporting empty output proves only that no **tracked** file changed
  relative to HEAD — it says nothing about untracked files, since git does
  not diff untracked content against any baseline at all. For **this
  file** (the memo itself), unchanged-ness of the untouched portions is
  established by a stronger, independent form of evidence: every edit in
  this task was made via an exact-match old-string/new-string replacement
  tool, which would have failed had the targeted text not matched
  precisely, and only the text shown in the diff below was altered. For
  the **other five untracked files**, **no reliable pre-task baseline
  (hash or saved copy) was ever recorded anywhere in this conversation**,
  so their content stability cannot be independently verified by this or
  any prior task in this chain — the only available assurance is
  procedural: no tool call in this task (or, per each prior task's own
  reported tool use, in any prior task in this chain) read-wrote or
  otherwise targeted those five files. As a weak, non-definitive
  corroborating signal (not a content hash, not proof), their filesystem
  modification timestamps were checked and are all dated 2026-11-08 or
  2026-11-09, prior to this task's start, with no timestamp falling
  inside this task's execution window — consistent with, but not proof
  of, those five files being unchanged. No pre-existing untracked file
  was deleted in this task.
- **Database access in this update**: none. This editing task performed
  no new query against `data/fibo_intraday.duckdb` or
  `data/warehouse.duckdb`; every number incorporated above was produced
  and verified by prior, separate, read-only measurement tasks.
- **External source access in this update**: none. (The Muhurat-date
  web-sourcing cited in Section 2.1 was performed by an earlier
  reproducibility-audit task, not this one or any task in this update
  chain.)
- **Prohibited-work confirmation**: no strategy return, signal,
  correlation, or predictive statistic was computed or inspected in this
  update; no Decision 19 or Section 3D measurement was performed; no
  Phase 4 work, trial registration, or ledger change occurred; no
  preregistration, methodology-proposal, master-specification, or
  source-code file was edited; nothing was committed, amended, staged, or
  pushed; no implementation of the policy (A1, B1, C, or any other
  category) occurred.

**Decision 17 is not approved by this document.** A1, B1, and C are
settled human decisions; the remainder of the policy (categories A and E's
recommendation status, and Decisions 10, 11, 19, and 21) remains open.
This is a recommendation for your continued review, not a formal approval
of the complete policy, and not an authorization to implement anything.
