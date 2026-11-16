# Pre-registration: [study name] -- [new family, trial N] / [variant of existing family]

Frozen before [the sealed holdout / the next read / whatever resource this
study will consume] is touched. Nothing below changes after this document
is written except by an explicit, recorded amendment -- the same
discipline every prior preregistration in this project uses.

This is a TEMPLATE, not a finished document -- every bracketed placeholder
must be filled in, and any section that does not apply to this study
should say so explicitly (never silently deleted; see `PREREGISTRATION_
SWING_V1.md`'s own Section 7, "What is NOT being tested," for the
convention). Copy this file, rename it, then fill it in -- do not edit
this template itself to fit one study.

## Provenance

**Hypothesis source** (pick one, state plainly -- this is a new field,
2026-11-16, added because the project's own trial-counting record is
only as good as what each study discloses about where it came from):

- [ ] **Structural/decomposition** of an already-run study or variant
  (e.g. decomposing why a failed configuration failed, the way Swing V1
  came from decomposing V4).
- [ ] **Literature/external source** (a named book, paper, or published
  methodology -- e.g. Darvas boxes, ICT Fair Value Gap). Name the source.
- [ ] **A measured finding in a DIFFERENT, already-closed study**
  suggesting this one (e.g. Portfolio construction, proposed because
  `momentum_12_1` passed its own sealed test and nothing had yet tested
  portfolio construction on it). Name the study and finding.
- [ ] **A diagnostic or bug investigation** surfacing this as a candidate
  structurally (e.g. a blast-radius check revealing an unguarded case
  worth its own test). Name the diagnostic/bug.
- [ ] **Suggested by browsing closed-study trades in the research app**
  (`scripts/research_app.py`) -- i.e. a chart-level observation while
  looking at an already-closed study's (or, for Fibo, the sealed TEST
  window's) individual trades. If this is the source, say which study/
  view, which chart(s) prompted it, and what was seen. This is the
  option the project's own banners and standing rules exist to make
  honest, not to prevent -- recording it here is what makes the trial
  count visible, not the act of looking itself.
- [ ] **Other** (state what, plainly -- do not leave this blank and do
  not retrofit a cleaner-sounding origin after the fact).

Then, as every prior preregistration already does, write the fuller
PROVENANCE NARRATIVE below this field -- what was tried before, what
failed, why this configuration, what family (if any) it belongs to, and
what correction (Bonferroni/BH or otherwise) that family needs. The field
above is a quick, greppable record for later trial-counting audits
(`PROJECT_CONTEXT.md` Section 7); the narrative below is the actual
account a reader needs to evaluate this study on its own terms. Neither
replaces the other.

[Full provenance narrative here.]

## Section 0: reuse boundaries, read-only

[What existing, already-validated code/data/methodology this study reuses
unmodified -- e.g. a cost model, a universe construction, a prior study's
own pure functions. State what is reused and from where; state what is
new.]

## Section 1: configuration frozen (universe, strategy, costs)

[Universe, point-in-time construction, the exact rule being tested, cost
model -- everything that must be fixed before any holdout/sealed window is
touched, or before the next forward-only read if there is no holdout left
to spend.]

## Section 2: historical result (pre-holdout/exploratory -- NOT the test)

[What this configuration showed on development data. Explicit that this
is NOT the validation -- development-stage evidence only.]

## Section 3: known, permanent limitations

[Anything already known to weaken this result, stated now, not discovered
convenient to mention only if the read fails.]

## Section 4: the validation path -- what resource this consumes, and why

[A sealed holdout read? A forward-only read because none is left
(`FINDINGS.md` Section 7's retirement)? A development-only structural
check needing no holdout at all? State which, and why that is the right
validation path for this specific claim -- per `NEW_RESEARCH_DIRECTION.md`
Phase 6's own rule, a threshold/claim here must be derived from this
study's own measured distribution, never borrowed from a different
comparison by analogy (`PROJECT_CONTEXT.md` Section 7 finding #16).]

## Section 5: decision rule, fixed now, before the read

[Every condition required for PASS, fixed before any holdout/forward data
relevant to the decision exists.]

## Section 6: power calculation, from historical variance only, never the mean

[Computed from the DEVELOPMENT-period distribution's own variance -- see
`FINDINGS.md` Section 12's own discipline (never call `.mean()` on the
series being sized) and the correction recorded after the 8-72-year
figure there was found reused by analogy for other studies without this
step.]

## Section 7: what is NOT being tested, and what is NOT decided here

[State explicitly, so a later reader does not assume silence means
untested rather than out of scope.]

## Section 8: multiple-testing correction, if this is part of a family

[If more than one variant/configuration is being run together, or this
study follows others in a named family, state the correction and which
family it is corrected against. If this is a lone trial, say so.]

## Section 9: Claude's pre-committed prediction

[State a prediction before the read, per this project's own convention
(`PREREGISTRATION_PORTFOLIO.md` Section 10, `PREREGISTRATION_LIQUIDITY_D.md`
Section 11) -- so a later reader can check calibration, not just the
result.]

## Section 10: procedure

[The exact steps, in order, that will be run once this document is
frozen. No step here may be reordered or skipped once the read begins.]
