# Decision 14 Follow-up — Lead-Lag Signal and Response Price-Scale Exposure Audit

**Date**: 2026-11-14
**Family**: Cross-Liquidity-Tier Return Propagation (lead-lag)
**Scope**: Whether `R_L(t)`, `R_F(t)`, `Y(t,h)`, and `Momentum_F(t)` are exposed to
the `bars_1min` mixed price-scale convention established in
`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`.
**Mode**: READ-ONLY. One `information_schema` query was issued in the prior
monthly-roster audit session; no new database query was needed for this audit
(all evidence reused from Decision 14 and documentation). No file was modified.
No strategy, regression, gate, or outcome analysis was run.

**HEAD before**: `9f71b65e006f937760e39a9f65035c69a1ef8df9`
**Git status before**: identical to the state at the start of the monthly-roster
audit (see Section 11) — one pre-existing modified file
(`PREREGISTRATION_LEAD_LAG_V1.md`, not touched by this audit) and a set of
untracked documentation files, none of which this audit modifies.

---

## 1. Executive conclusion

**No single overall classification applies cleanly, because the four
quantities do not all carry the same risk, and — critically — no committed,
executable implementation of any of the four exists in this repository to
verify against.** Per-calculation classification (Section 8 gives full
reasoning):

| Calculation | Classification |
|---|---|
| `R_L(t)` | **INDETERMINATE — INSUFFICIENT EVIDENCE** (no code; lowest design-level risk of the four) |
| `R_F(t)` | **INDETERMINATE — INSUFFICIENT EVIDENCE** (no code; lowest design-level risk of the four) |
| `Y(t,h)` | **INDETERMINATE — INSUFFICIENT EVIDENCE** (no code; safety depends entirely on one specific, named, unverified exclusion rule — and this is the primary 60-minute gating horizon) |
| `Momentum_F(t)` | **POTENTIALLY EXPOSED TO CROSS-SESSION SCALE CHANGES** (a concrete, unresolved arithmetic conflict was found in the governing design documents themselves, not merely an absence of code) |

**A second, equally material finding governs everything below**: the exact
formula the task specifies as "the approved return convention" —
`r_i(a,b) = P_i(b)/P_i(a) - 1`, applied uniformly to `R_L`, `R_F`, `Y`, and
`Momentum_F` — is **not** what the currently committed preregistration
(`PREREGISTRATION_LEAD_LAG_V1.md`, HEAD state) actually specifies for its
analogous constructs. The document that *does* define this exact convention
and these exact four symbols with this exact formula
(`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`) is an **untracked,
in-progress proposal whose own internal decision log marks this specific
convention "OPEN (technically recommended, not approved)" — Decision 13.**
This audit analyzes the convention exactly as the task specifies (Section 3
below gives the full reasoning under that convention), but this provenance
gap is reported prominently, not glossed over, in Section 6.

---

## 2. Scope and files inspected

**Documentation (read in full or by targeted section)**:
- `PREREGISTRATION_LEAD_LAG_V1.md` — the committed, HEAD-state preregistration (Sections 1, 2, 8, 9, 10, 11, 12 read in full; Amendment Log cross-referenced).
- `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` — untracked proposal; Sections 1, 3, 4, 5, 6 and the decision-log table read in full.
- `lead_lag/MASTER_SPEC_LEAD_LAG.md` — Sections 2–6 read.
- `lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` — Task 1 and Task 3 method descriptions read.
- `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md` — reused, not rerun.
- `lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md`, `lead_lag/DECISION_17_REPRODUCIBILITY_AUDIT.md` — spot-checked for endpoint-handling code references.
- `lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md` — this audit's immediate predecessor; its finding (roster/turnover never reads `bars_1min`) is assumed, not re-derived.

**Source code searched, repository-wide**:
```
Grep "S_leader|S_L\(|R_L\(|R_F\(|AR_follower|Momentum_F|def.*leader|def.*follower|signal_window" over src/   -> no matches
Grep "S_leader|S_L\(|R_L\(|R_F\(|AR_follower|Momentum_F" over scripts/                                       -> no matches
Grep "R_L\(t\)|R_F\(t\)|Y\(t,h\)|Momentum_F|S_L\(t\)" over the whole repository                              -> matches only in the four .md files listed above
Glob src/lead_lag/**                                                                                           -> no matches (no such directory)
Glob **/lead_lag*/**/*.py                                                                                      -> lead_lag/ledger.py, lead_lag/test_ledger.py only (trial-ledger bookkeeping, not signal/return code)
```

**Finding, stated once here and relied on throughout**: **no file anywhere in
this repository implements `R_L(t)`, `R_F(t)`, `Y(t,h)`, or `Momentum_F(t)`.**
Phase 4 (and the Phase 3 implementation step that would precede it) has not
been built. The only executed code resembling any of these quantities is
described — not present as a committed file — in
`LEAD_LAG_POWER_AND_BREADTH_REVISION.md`'s Task 1–3 method sections, which
state their own scripts (`task1_monthly_tiers.py`, `task2_breadth.py`,
`task3_build_dataset.py`, `task3_placebo_bootstrap.py`) "live in throwaway
scripts in the session scratchpad (not committed)" (that document's own
header, lines 6–9). Those scripts are not present in this repository to read.

This is the dominant fact shaping this audit: **every claim below about
"the implementation" is necessarily a claim about documented design intent,
not verified executable code**, except where a committed, unrelated-but-
load-bearing module (none were found to be load-bearing for these four
quantities specifically — contrast with the monthly-roster audit, where
`src/fibo/universe.py` was committed and fully readable) can be cited.

---

## 3. Actual source-level call chains

**None exist.** This section reports that fact per quantity, then gives the
documented design each quantity would need to follow, with exact citations.

### `R_L(t)` / `R_F(t)` — documented design (no code)

Per `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` lines 252–253, 776:
```
R_i(a -> b)        = P_i(b) / P_i(a) - 1                      [per constituent]
PortfolioReturn(a->b) = mean_i( R_i(a -> b) )                  [equal-weighted, over the frozen basket]
R_L(t) = PortfolioReturn(t-5 -> t)   over the frozen leader basket
R_F(t) = PortfolioReturn(t-5 -> t)   over the frozen follower basket
```
`P_i(k)` is defined (same document, lines 946–968) as "the close of the bar
whose `ts` equals clock time `k`," sourced from `bars_1min.close`
(`src/fibo/intraday_db.py`'s schema, cited at the top of that proposal —
confirmed independently in Decision 14 Section 2.1: `bars_1min` columns
include `close`). **No query, function, or script implementing this exists.**

### `Y(t,h)` — documented design (no code)

Same document, lines 255, 1065; `PREREGISTRATION_LEAD_LAG_V1.md` line 388
gives the *committed* regression's dependent variable using a related but
not-identical name, `AR_follower(j, t->t+h)` (Section 2) — discussed in
Section 6 below. Per the proposal:
```
Y(t,h) = PortfolioReturn(t -> t+h)   over the frozen follower basket, "starting immediately after t"
Y(t,h) = alpha + beta*S_L(t) + gamma*R_F(t) + delta_1*TOD(t) + delta_2*Momentum_F(t) + epsilon(t,h)
```
No query, function, or script implementing `Y(t,h)`'s return construction
exists. The regression itself is explicitly **not run** anywhere in this
repository (consistent with Phase 4 being unbuilt).

### `Momentum_F(t)` — documented design (no code)

Same document, lines 1045–1051:
```
Momentum_F(t) = (1/n_followers) * sum_j [ P_j(t-5) / P_j(t-35) - 1 ]
```
over the disjoint window `[t-34, t-5]`, same frozen follower basket, same
exact-endpoint construction. No query, function, or script implementing this
exists. **`Momentum_F(t)` is not defined anywhere in the committed
`PREREGISTRATION_LEAD_LAG_V1.md` at all** — confirmed by an exhaustive grep
for `Momentum`/`momentum` in that file (Section 6 below gives the full
citation and discrepancy).

### Entity, session, and price-column identity — what every path would share

All four, per every document that defines them, read `bars_1min.close` for
one `entity_id` at a time, keyed by `(entity_id, ts)`, with the frozen
leader/follower basket membership fixed from the monthly roster (already
established, `lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`, to be built
from `prices_eod`, not `bars_1min` — i.e. the basket's **membership** is
roster-derived and scale-independent, but the **return values** of the
members are computed from `bars_1min`, which is where Decision 14's finding
applies).

---

## 4. Endpoint definitions for all four calculations

All endpoint definitions below are **as documented in
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`** (the only source that
defines all four with this exact formula), not as verified from executable
code, because none exists.

| Calculation | Start endpoint | End endpoint | Max span | Same-session guaranteed? | Same-scale guaranteed? |
|---|---|---|---|---|---|
| `R_L(t)` | `P_i(t-5)`, leader basket | `P_i(t)` | 5 min (clock span `[t-4, t+1)`, proposal lines 955-959) | **No code guarantee; strong design support** — earliest documented anchor is `09:19`/`09:20` (Section 5, lines 995-1008), so the window never reaches before session open in the documented design; no corporate-action-window overlap possible at this short a span except via the +/-1-trading-day exclusion (Section 12) | Contingent on same-session holding; if same-session, Decision 14 Section 7 found 0/208 within-session breaks empirically |
| `R_F(t)` | `P_j(t-5)`, follower basket | `P_j(t)` | 5 min | Same as `R_L(t)` | Same as `R_L(t)` |
| `Y(t,h)` | `P_j(t)`, follower basket | `P_j(t+h)` | up to 60 min (primary gate horizon, `PREREGISTRATION_LEAD_LAG_V1.md` line 678) | **Guaranteed only by one named design rule, not by arithmetic**: Section 12's "final-5-minutes-before-close signal-end minutes whose forward window would cross 15:30" exclusion (`PREREGISTRATION_LEAD_LAG_V1.md` lines 701-703) exists *precisely because*, without it, a 60-minute forward window from a late-session `t` would otherwise reach past market close into the next session's bars. The hazard is real; the patch is documented; whether it is ever actually coded is unverifiable here. | Contingent on the above rule being correctly implemented; if so, same reasoning as `R_L`/`R_F` applies |
| `Momentum_F(t)` | `P_j(t-35)`, follower basket | `P_j(t-5)` | 30 min, disjoint window `[t-34,t-5]` | **Not guaranteed — a concrete arithmetic conflict exists in the governing documents, detailed in Section 5.3** | Not guaranteed for the same reason |

---

## 5. Mathematical invariance, cross-session, and adjustment-boundary analysis

### 5.1 Mathematical invariance (question 1 of Section 6's framework) — holds unconditionally for the formula itself

For any pair of endpoints `a < b` sharing one common positive scale factor
`c` (i.e. `P_i^{observed}(a) = c * P_i^{true}(a)` and
`P_i^{observed}(b) = c * P_i^{true}(b)`):
```
R_i(a,b) = P_i(b)/P_i(a) - 1 = (c*P_true(b))/(c*P_true(a)) - 1 = P_true(b)/P_true(a) - 1
```
The factor cancels exactly. This holds identically for `R_L(t)`, `R_F(t)`,
`Y(t,h)`, and `Momentum_F(t)`, since all four reduce to `mean_i` of exactly
this per-constituent ratio form (Section 3). **This is a property of the
formula, established by algebra alone, true regardless of what `bars_1min`
actually contains.** It says nothing about whether the *condition*
("both endpoints share factor `c`") actually holds in the archive — that is
exactly questions 2 and 3, addressed next.

### 5.2 Implementation guarantee (question 2) — cannot be established; no code exists

Per Section 2–3, there is no committed code for any of the four quantities.
**No implementation-level guarantee can be verified for any of them.** This
is the single largest driver of this audit's classifications (Section 8).

### 5.3 The Momentum_F(t) early-session anchor conflict — a concrete, documented-but-unresolved design gap

This is a new finding, not previously flagged in Decision 14 or the
monthly-roster audit. Two sections of the same governing proposal document
specify requirements that are **arithmetically incompatible** at the start
of a trading session:

- **`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 5** (lines
  995–1008) derives the **earliest possible signal-window anchor** as
  `t = 09:19` (if `09:15` is a valid regular-session bar) or `t = 09:20`
  (if a pre-open exclusion applies at `09:15`). This derivation considers
  only the signal window `[t-4, t]` — it does not reference `Momentum_F`'s
  own endpoint requirement.
- **`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 6** (lines
  1045–1051) requires `Momentum_F(t)` to read `P_j(t-34)` through `P_j(t-5)`
  — i.e. a bar at clock time `t-34`.

**The conflict**: for the earliest documented anchor `t=09:19`, `t-34 =
08:45`; for `t=09:20`, `t-34 = 08:46`. Both are **before the 09:15 session
open**, under either candidate convention. No bar exists there in a regular
trading session. Section 5's anchor derivation and Section 6's window
definition were each worked out in isolation and **never cross-checked
against each other anywhere in the document** — confirmed by re-reading
Section 5 in full (it discusses only the 5-minute signal window) and Section
6 in full (it discusses only the momentum window, "adopted as given in the
task, not selected by comparing alternative windows," line 1056, with no
reference back to Section 5's anchor timing).

**Why this matters for scale exposure, specifically**: `bars_1min` has no
rows before `09:15` on a regular session (per the Fibo-ORB usage-pattern
evidence cited at proposal lines 972-977, and per the general regular-session
convention `09:15-15:29` used throughout Decision 14 and this family's other
documents). An endpoint lookup for `P_j(t-34)` at a would-be `08:45`/`08:46`
timestamp therefore has exactly three possible resolutions if ever coded,
and **the documents do not say which**:

1. **Correctly return "no valid bar," and exclude the observation** — safe,
   consistent with the "unified eligibility check... applies uniformly to all
   three endpoints `t-35, t-5, t`" principle stated elsewhere in the same
   proposal (lines 925-934) for the *signal*-side endpoints, though that
   passage does not explicitly extend to `Momentum_F`'s own `t-35`-relative
   endpoints by name.
2. **Silently resolve to the nearest available bar, which would be on the
   *previous trading session*** (e.g. the prior day's `15:29` close, if an
   implementation used a simple time-ordered lookup — `LAG(n)` by row order,
   or a `<=` timestamp match — without a `trade_date` guard). This is
   **exactly the cross-session, differently-scaled endpoint pairing**
   Section 3.B of the task asks to be investigated, and it is the one
   concrete, named pathway this audit found by which it could occur, as
   opposed to a purely hypothetical one.
3. **Some other, unspecified clamping/padding behavior** not discussed in
   any document read for this audit.

**This is classified as a methodology/documentation gap, not a code defect**
(Section 6 explains why: there is no code to contain a defect). It is a real,
citable internal inconsistency in the design specification itself, elevating
`Momentum_F(t)`'s classification above the other three (Section 8).

### 5.4 Cross-session analysis for `R_L`, `R_F`, and `Y(t,h)` — no analogous conflict found

- **`R_L`/`R_F`**: the 5-minute window's earliest anchor (`09:19`/`09:20`)
  requires only `P_i(t-5)` at `09:14`/`09:15` — both within or at the exact
  edge of the documented session open, with no symmetric conflict of the
  `Momentum_F` kind found. (`09:15` itself being a valid bar is the one
  **separately flagged, unresolved** question the proposal's own Section 5
  states "is not conclusively settled" — lines 970-985 — but this affects
  which exact minute the window starts, not whether it reaches outside the
  session.)
- **`Y(t,h)`**: Section 12's "forward window would cross 15:30" exclusion
  (quoted in Section 4 above) is the document's own explicit acknowledgment
  that, absent this rule, a forward horizon **would** routinely reach into
  the next session for late-day `t`. The rule's existence is evidence the
  hazard was recognized and a mitigation was designed; whether the
  mitigation is ever coded is the unresolved implementation-guarantee
  question (Section 5.2), not a design gap of the `Momentum_F` kind.
- No special-session, monthly-roster-boundary, or missing-bar-fallback
  mechanism was found, in any document read, that would route an `R_L`,
  `R_F`, or `Y(t,h)` endpoint lookup across a session boundary. The
  monthly-roster boundary specifically cannot introduce a cross-session
  price endpoint, because roster membership (which entities are in the
  basket) and endpoint price lookup (which bar a given entity's return is
  computed from) are architecturally separate steps — the roster audit
  already established the former never touches `bars_1min` at all.

### 5.5 Piecewise adjustment boundaries (question C) — reusing, not rerunning, Decision 14

Decision 14 Section 6.3 (reused verbatim, not recomputed): across a
full-history scan of the 75 entities carrying the 104 eligible corporate-
action events, **143 Angel-vs-bhavcopy scale breaks > 5%** were found, of
which **103 sit exactly on a recorded ex-date and 40 do not**. Decision 14
Section 7 (also reused): across the **208 event-adjacent sessions /
77,654 bars** actually scanned for within-session breaks, **zero** sustained
multiplicative mid-session shifts were found at either an 8% or 15%
threshold. **Every one of the 143 located boundaries, in the tested
population, falls at a session-to-session transition — none mid-session.**

Applying this reused evidence to the endpoint spans in Section 4: **a return
construction whose two endpoints are both guaranteed to fall within one
trading session cannot, by this evidence, straddle any of the 143 located
boundaries** — because none of them falls inside a session, only between
sessions. This directly supports `R_L(t)`, `R_F(t)`, and a correctly-gated
`Y(t,h)` (per the 15:30 rule) being safe **conditional on** the
same-session guarantee actually holding in whatever code eventually
implements them — a conditional this audit cannot discharge (Section 5.2).

For `Momentum_F(t)`'s early-session hazard specifically (Section 5.3): **if**
an implementation ever resolved a missing `t-34` bar by rolling to the
previous session (resolution 2 above), the resulting endpoint pair would by
construction be a genuine cross-session pair, and Decision 14's own evidence
is that **103 of 104** such session-to-session boundaries in the tested
population carry a real scale discontinuity (the back-adjustment signature).
This would not be a remote or theoretical risk in that scenario — it would
land on almost exactly the population Decision 14 already showed is
discontinuous.

---

## 6. Separating mathematical invariance from empirical evidence (per Section 6 of the task)

| Question | Answer | Basis |
|---|---|---|
| 1. Does the formula cancel a shared multiplicative factor? | **Yes, for all four quantities** | Algebra (Section 5.1), unconditional |
| 2. Does the actual code guarantee both endpoints share that factor? | **Cannot be established — no code exists for any of the four quantities** | Section 2, 3 |
| 3. Does the archive contain observed/suspected scale boundaries between actual endpoints? | **Zero observed within-session boundaries in the 208-session tested population (Decision 14, reused); 143 observed between-session boundaries exist in the broader archive; whether any real endpoint pair ever lands on one depends entirely on the unresolved implementation guarantee (question 2), except for `Momentum_F`'s early-session case, where a concrete pathway to a cross-session pair was found in the design documents themselves (Section 5.3)** | Decision 14 Sections 6.3/7 (reused), this audit's Section 5.3 (new) |

**A positive answer to question 1 does not establish positive answers to
questions 2 or 3 — stated explicitly because that is exactly the error this
audit's instructions warn against, and because it would be easy to read
Section 5.1's clean algebra as settling the matter when it settles only the
formula, not the archive or the (nonexistent) code.**

---

## 7. Documentation consistency — the convention this audit was asked to test is not the one currently registered

**Central finding.** The task states: *"The approved return convention is:
`r_i(a,b) = P_i(b)/P_i(a) - 1`... This exact endpoint-price convention
applies consistently to `R_L(t)`, `R_F(t)`, `Y(t,h)`, `Momentum_F(t)`."*
Tracing this through the repository's own artifacts finds:

1. **The committed, HEAD-state preregistration does not use this
   convention for its own signal construction.** `PREREGISTRATION_LEAD_LAG_V1.md`
   Section 8 (lines 523-627, "CORRECTED — fixes the degeneracy") defines:
   ```
   S_i(t) = sum_{k=t-4}^{t} AR_leader(i,k)      [a SUM of five 1-minute per-bar returns]
   ```
   not a single exact-endpoint ratio `P_i(t)/P_i(t-5)-1`. This is a
   materially different construction — not algebraically identical to the
   exact-endpoint convention (a sum of per-bar log-ish returns differs from
   the single compounded ratio by a Jensen's-gap term, explicitly the
   motivation cited for proposing the alternative — see point 2 below).
   Preregistration Section 2 (line 388) likewise defines the dependent
   variable as `AR_follower(j, t->t+h)`, a **per-follower-entity**
   leave-one-out abnormal return, not a **portfolio-level**
   `Y(t,h) = PortfolioReturn(t->t+h)` over a frozen basket.
2. **The exact-endpoint, portfolio-level convention the task describes
   lives only in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`**, an
   untracked file. That document's own decision-log table states, verbatim
   (line 1646): *"Return convention adoption (exact endpoint-price method)
   | **OPEN** (technically recommended, not approved) | Section 4
   construction, applied consistently to `R_L`, `R_F`, `Y`, `Momentum_F` |
   Keep original sum-of-per-bar convention for the leader side only
   (rejected -- internal inconsistency) | Exactness; avoids Jensen's-gap
   error | Yes -- amends the committed Section 8 formula | Before data
   analysis."* The same document's Section 4E states: *"Adoption status:
   Unchanged: RECOMMENDED, not APPROVED (Decision 13)"* (line 938). The
   broader shift to a portfolio-level estimand ("Option A") is marked
   **APPROVED** elsewhere in the same decision log (line 1634) — so the
   *aggregation level* (portfolio vs. per-follower) and the *endpoint
   method* (exact-ratio vs. sum-of-bars) are two separable decisions, and
   only the first has been approved; the second — the one this audit was
   asked to test — has not.
3. **`Momentum_F(t)` does not appear anywhere in the committed
   preregistration at all.** Exhaustive grep for `Momentum`/`momentum` in
   `PREREGISTRATION_LEAD_LAG_V1.md` finds only generic prose references to
   "the follower's own recent momentum" as a control *concept* (lines
   338, 667) — no formula, no window, no endpoint convention. The exact
   `[t-34,t-5]` window and its exact-endpoint formula exist only in the
   unapproved proposal.
4. **Carried forward from the two prior audits**: both
   `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` (lines 805-808) and
   `MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`'s own Section 6 finding
   independently confirm this same proposal document still carries the
   pre-Decision-14 "likely raw" framing for `bars_1min`, unresolved.

**This audit does not resolve any of these four points** — per its own
instructions, it reports them. The practical consequence for this audit's
technical analysis (Sections 3-5): it was conducted **on the convention the
task specified**, because that is the assignment, while flagging that this
convention is, at the time of this audit, a recommended-but-unapproved
alternative to what the project's own committed registration document
actually specifies.

**One further, brief note on the registered (Section 8/9) convention's own
scale-exposure profile**, since it is the convention actually in force: a
sum of five 1-minute bar returns `sum_{k=t-4}^{t} r(i,k)` is invariant to a
constant scale factor under the **same** condition as the exact-endpoint
convention — every consecutive bar pair `(k-1,k)` contributing to the sum
must share one scale. If a scale-regime boundary fell between two specific
consecutive bars inside the window, the registered convention would show the
distortion concentrated in **one** anomalous 1-minute term rather than
spread across the whole 5-minute ratio — a different failure *shape*, not a
different failure *condition*. Decision 14's within-session evidence
(Section 5.5 above) applies equally to this convention: zero such mid-session
boundaries were found in the 208 tested sessions.

---

## 8. Per-calculation classification and overall risk assessment

### `R_L(t)` — INDETERMINATE — INSUFFICIENT EVIDENCE

No code exists. Design-level support for same-session endpoints is strong
(short 5-minute window; earliest documented anchor `09:19`/`09:20` leaves no
room for the window to reach before session open under either candidate
convention; no identified design gap analogous to `Momentum_F`'s). Cannot be
upgraded past INDETERMINATE without either (a) committed code to read, or
(b) actual observation-level data to check — neither exists.

### `R_F(t)` — INDETERMINATE — INSUFFICIENT EVIDENCE

Identical reasoning and identical classification to `R_L(t)`.

### `Y(t,h)` — INDETERMINATE — INSUFFICIENT EVIDENCE

No code exists. Unlike `R_L`/`R_F`, same-session-ness here depends on one
specific, explicitly named design rule (Section 12's "forward window would
cross 15:30" exclusion) rather than on the window simply being too short to
reach a boundary — i.e., **without that rule being correctly applied,
cross-session exposure for this quantity would not be a remote edge case, it
would be the routine outcome for any `t` in roughly the last `h` minutes of
the session.** This makes `Y(t,h)` the single highest-priority quantity to
verify once Phase 4 code exists, especially because `h=60` minutes is the
preregistration's own **primary gating horizon** (`PREREGISTRATION_LEAD_LAG_V1.md`
line 678).

### `Momentum_F(t)` — POTENTIALLY EXPOSED TO CROSS-SESSION SCALE CHANGES

This is the one calculation elevated above INDETERMINATE, because a concrete,
citable mechanism for cross-session exposure was found directly in the
governing design documents (Section 5.3) — not merely the general absence of
code that affects all four. The earliest documented session anchor is
arithmetically incompatible with this quantity's own 30-minute lookback
requirement, and no document specifies how that incompatibility is meant to
be resolved. Until a named resolution rule exists (analogous to `Y(t,h)`'s
15:30 rule) and is verified in code, this is the one quantity with an
identified, undischarged pathway to a genuinely cross-session, potentially
different-scale endpoint pair — not merely a hypothetical one.

### Overall assessment

- **Are all approved lead-lag return calculations safe under the Decision
  14 findings?** This cannot be affirmed. Three of four are
  indeterminate purely for lack of an implementation to check; the fourth
  (`Momentum_F`) has an identified, concrete exposure pathway in the design
  itself, independent of any code question.
- **Is the risk limited to a specific calculation or endpoint path?**
  Yes, materially so: `Momentum_F(t)`'s early-session anchor is the one
  concrete finding; `Y(t,h)` is the one quantity whose safety depends on a
  single, specific, as-yet-unverified rule rather than on the window simply
  being too short to reach a boundary; `R_L`/`R_F` carry the lowest
  identified design-level risk of the four.
- **Methodology ambiguity, code defect, data limitation, or a combination?**
  **Methodology ambiguity and data limitation, not a code defect** — there
  is no code to contain a defect. The methodology ambiguity is twofold:
  (a) the exact-endpoint, portfolio-level convention this audit was asked to
  test is a recommended-but-unapproved alternative to the committed
  preregistration's own sum-of-per-bar, per-follower construction (Section
  7), and (b) `Momentum_F(t)`'s window and the earliest signal anchor were
  specified in two places that were never cross-checked against each other
  (Section 5.3). The data limitation is Decision 14's own, carried forward
  unchanged: its within-session clean-negative finding covers 208 sessions
  for 75 entities carrying a *recorded* corporate action — whether an
  unrecorded, mid-session scale artifact could exist elsewhere in the
  386-entity archive was explicitly flagged as unresolved there
  (Decision 14 Section 8, limitation 5) and is not re-tested here.
- **Does the evidence justify keeping the current return convention, or is
  a separate methodology decision required?** A separate methodology
  decision is required — but it is narrower than "fix the return
  convention." See Section 11.

---

## 9. Targeted data-check methodology and results

**No new database query was run for this audit.** Per the task's own
instruction not to rerun Decision 14 unnecessarily, and because no
implementation exists to generate actual `(entity, t, t+h)` observation
rows to check, a literal "endpoint-pair" check (in the sense of pairing real
signal/response observations against known boundaries) is **not possible**
from current repository evidence — there are no observations to pair.

What **is** reused, verbatim, from Decision 14 (not rerun):

- **Population tested** (Decision 14 Sections 3-4, 7): 104 eligible
  split/bonus events across 75 entities; 208 event-adjacent sessions;
  77,654 regular-session bars.
- **Selection logic** (Decision 14 Section 4, rules R1-R7): predeclared,
  deterministic, eligibility based on intraday coverage around each
  recorded ex-date, not on observed price movement.
- **Endpoint pairs checked, in Decision 14's own sense (within-session
  consecutive/extreme bar pairs, not this family's signal/response
  pairs)**: 77,654 bars across 208 sessions.
- **Number crossing sessions**: not applicable to Decision 14's own
  within-session scan (it was designed not to cross sessions); separately,
  Decision 14's full-history scan located 143 between-session boundaries
  across the 75 entities' complete archives (Section 6.3 there).
- **Number intersecting known or suspected scale boundaries**: 0 of 77,654
  bars showed a within-session break (Decision 14 Section 7); 143 of the
  75 entities' full-history session transitions showed a between-session
  break (Decision 14 Section 6.3).
- **Exclusions**: identical to Decision 14's own (504 corporate-action
  events excluded for no intraday coverage at all; 31/12/8 excluded for
  one-sided or gapped coverage — Decision 14 Section 3.4). Not re-derived
  here.

**This finite, reused check does not prove all historical observations of
`R_L`, `R_F`, `Y`, or `Momentum_F` are safe.** It establishes only that, in
the specific 208-session population Decision 14 tested, zero within-session
scale breaks were found, and that every located scale-regime boundary in
that population's broader entity histories falls between sessions. Applying
this to the four quantities audited here requires the additional,
**unverified** premise that their actual (nonexistent) implementation
confines every endpoint pair to a single session — which is exactly the
implementation-guarantee gap Section 5.2 and Section 8 describe.

---

## 10. Limitations and unresolved questions

1. **No executable implementation of any of the four quantities exists.**
   This is the limitation underlying every INDETERMINATE classification in
   Section 8. It is not a gap this audit can close by further reading —
   the code does not exist.
2. **The task's "approved" convention does not match the committed
   preregistration's own Section 8/9 construction**, and the document that
   does define it marks it explicitly unapproved (Section 7). Which
   convention actually governs Phase 4, if and when it is built, is
   presently unresolved.
3. **`Momentum_F(t)`'s early-session anchor conflict (Section 5.3) is
   identified but not resolved here**, per the task's own boundary against
   implementing fixes. Whether this is intended to be handled by exclusion,
   by a later minimum anchor, or by some other rule is not stated in any
   document read.
4. **Whether `09:15` is a valid regular-session `bars_1min` bar is itself
   unresolved** (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` lines
   970-985, "evidence found, not conclusively settled") — this shifts the
   exact earliest anchor by one minute either way but does not change this
   audit's findings materially.
5. **Decision 14's own limitation #5** (possible further misplaced
   adjustment-regime boundaries beyond the 104-event tested population) is
   carried forward unchanged and directly bounds how far this audit's reuse
   of that evidence (Section 5.5, Section 9) can be trusted to generalize.
6. **Whether the 1-minute per-bar returns underlying the registered
   Section 8/9 convention (`r(i,k)`) are themselves computed as exact
   adjacent-bar ratios or by some other method is not specified in
   `PREREGISTRATION_LEAD_LAG_V1.md`** — the document uses `r(i,k)` without
   a defining formula in the sections read; this is noted, not resolved.
7. **This audit did not examine `B_follower_pool(k)`, `B_follower_LOO(j,k)`,
   or the leave-one-out construction's own scale-exposure profile** in
   detail beyond noting (Section 7) that it is built from the same
   per-constituent return primitives as everything else — a dedicated pass
   on the benchmark construction specifically was judged out of scope for
   the four named quantities this audit was asked to test.

---

## 11. Recommended next decision

**Not implemented here, per the task's boundaries.** The smallest decision
that actually needs to be made, stated narrowly:

1. **Resolve Decision 13** (the exact-endpoint-price convention's adoption
   status) before any Phase 4 code is written — not because either
   convention is unsafe with respect to Decision 14's findings (Section 7
   shows both share the same core same-session requirement), but because
   two different, non-identical formulas are currently both "live" in the
   repository's own documents, and Phase 4 code written against one would
   not match a preregistration still describing the other.
2. **Add a named, explicit minimum-anchor (or equivalent) rule for
   `Momentum_F(t)`**, analogous in kind to Section 12's existing "forward
   window would cross 15:30" rule, so that the first eligible anchor of
   each session is defined with its 30-minute lookback requirement
   accounted for — before, not after, any implementation is written. This
   is a documentation/specification completion step, not a data analysis,
   and does not require new data, a new trial, or running any gate.

Both are decisions about what the specification should say, not findings
that require new data collection or a new empirical test.

---

## 12. Final verification

**New files created**: exactly one —
`lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md`.

**Existing files modified**: none. `PREREGISTRATION_LEAD_LAG_V1.md`,
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`,
`lead_lag/MASTER_SPEC_LEAD_LAG.md`,
`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md`,
`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`,
`lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`, `lead_lag/trial_ledger.json`,
and all source code were read only.

**Database access**: no new database connection was opened for this audit;
all data evidence is reused from the already-completed, read-only Decision
14 audit. No `INSERT`/`UPDATE`/`DELETE`/`CREATE`/`DROP`/`ATTACH` was issued.

**New data fetched**: none.

**Prohibited analysis**: no strategy, regression, gate, backtest, predictive-
performance, beta, or significance analysis was run or inspected. No trial
was registered or counted. No fix was implemented.

**Git HEAD before**: `9f71b65e006f937760e39a9f65035c69a1ef8df9`

**Git status before** (identical to the end of the prior monthly-roster
audit):
```
 M PREREGISTRATION_LEAD_LAG_V1.md
?? LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md
?? lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md
?? lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md
?? lead_lag/DECISION_10_RECONCILIATION_ADDENDUM.md
?? lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md
?? lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md
?? lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md
?? lead_lag/DECISION_17_REPRODUCIBILITY_AUDIT.md
?? lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md
?? lead_lag/METHODOLOGY_PROPOSAL_2026-11-08_PORTFOLIO_LEVEL_ESTIMAND.md
?? lead_lag/METHODOLOGY_REVIEW_2026-11-08_ESTIMAND_AND_NULL.md
?? lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md
```

(to be confirmed identical, plus this one new file, after writing this
report — see the closing verification run immediately after this file is
saved.)
