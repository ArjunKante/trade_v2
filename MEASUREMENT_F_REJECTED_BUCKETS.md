# Measurement: Liquidity F rejected buckets

**This is a MEASUREMENT, not a trading study.** It asserts nothing
tradeable, has no gate, no nulls, no verdict rule, and no sealed
window. Nothing here authorizes building a strategy. This page is
committed before any number in it exists.

## What will be measured

On the Study F Phase 1 sample already in hand — 12 entities, 84
entity-years, 15,176 eligible entity-days, the identical sample used
for Study F's own Phase 1 count estimate, **not expanded** — every row
that fell into the `NOT_RECLAIMED` bucket, the `SWEEP_EXTENDED` bucket,
and (for direct comparison) the `RECLAIMED` bucket, long and short
separately, will have its exit resolved under Study A's/B's own exit
rules: scaled exit at 1.5R and 3.0R, stop at the sweep extreme ± 0.1x
ATR, the same three-order intraday cost model. Mean net return per
trade will be reported with a day-clustered bootstrap CI, for each of
the six (bucket × side) groups.

## What will NOT be done

- **No scaling to universe level.** The sample's own 16.67x
  count-extrapolation factor was built for counting setups, not for
  estimating a mean return — a sample unrepresentative in composition
  (even if representative in count) would corrupt a scaled return
  estimate in a way it does not corrupt a count.
- No nulls, no gate, no verdict rule.
- No sealed TEST window is touched — DEV-only sample, as Phase 1
  already was.

## Reference points, reported alongside, not reproduced

Study C's `no_retest` bucket: **+1.0%**. Study D's `PATTERN_INCOMPLETE`
bucket: **+0.87% to +0.91%**.

## Pre-committed now, before the numbers exist

**A positive mean in `NOT_RECLAIMED` or `SWEEP_EXTENDED` does NOT
license a Study G that trades them.** If that happens, it is a third
replication of `PROJECT_CONTEXT.md` §7 finding #6 ("Confirmation
filters discard the winners") and nothing more — not a new discovery.
Any strategy derived from this measurement is **trial 7** in the
Liquidity family, needs its own preregistration under the full gate,
and inherits the calibration notes' own chart-observation prior (four
observations tested from browsing charts, four nulls — §9).

## Runtime

No null stages. Estimated well under the 3-hour threshold (per-trade
exit resolution only, on a bucket population in the low thousands, not
a full-universe scan) — if that estimate turns out wrong once measured,
reported before the full run, not after.

---

## APPENDED 2026-11-07: the first result set failed an arithmetic
## reconciliation against Phase 1 and is withdrawn. Do not cite it.

The first measurement (reported in chat, never written into this file)
gave `not_reclaimed`/`sweep_extended` sample sizes roughly **15x
smaller** than Phase 1's own raw counts for those same buckets (e.g.
long `not_reclaimed`: 1,065 in Phase 1 vs. 68 resolved) while
`reclaimed` reconciled cleanly (909 vs. Phase 1's 934 fill-in-window).
Investigated per instruction, not assumed.

**Cause, found and confirmed with counts, not guessed**: the
measurement script's own counterfactual function for the rejected
buckets called `find_entry_a`/`find_entry_b` — the FULL Study A/B entry
pipeline, which **independently re-detects its own 5-minute sweep from
scratch** via `poc.v4.find_sweep`, rather than reusing Study F's own
already-found hourly sweep extreme. This is a different construction
from Study C's/D's own precedent (`_original_entry_long/short`,
`_original_ab_entry_long/short`), which feed the SAME originating sweep
into A's/B's reclaim+fill+guard logic and never re-detect a sweep
independently. A rerun capturing every dropped row's exact
`find_entry_a`/`find_entry_b` status found:

| | total rows | A/B's own NOT_RECLAIMED | ENTERED (resolved) | NO_FILL_BAR | FILL_OUTSIDE_WINDOW | STOP_TOO_TIGHT | other |
|---|---|---|---|---|---|---|---|
| long/not_reclaimed | 1,065 | 959 (90.0%) | 68 (6.4%) | 18 | 13 | 4 | 3 |
| long/sweep_extended | 593 | 533 (89.9%) | 41 (6.9%) | 0 | 12 | 6 | 1 |
| short/not_reclaimed | 1,156 | 1,052 (91.0%) | 64 (5.5%) | 22 | 9 | 7 | 2 |
| short/sweep_extended | 619 | 559 (90.3%) | 45 (7.3%) | 0 | 11 | 4 | 0 |

**Classification: SELECTIVE, on this evidence, not on plausibility.**
~90% of every dropped row shares one specific reason: A's/B's own,
completely independently-detected 5-minute sweep *also* failed to
reclaim under A's/B's own native (non-killing) reclaim rule. That is
not an unrelated coin-flip — it is the same underlying adverse
price-continuation that produced Study F's own `NOT_RECLAIMED`/
`SWEEP_EXTENDED` classification in the first place, recurring under a
different detection path. The surviving ~6-7% subsample is therefore
conditioned on "A's/B's own unrelated mechanism also found a tradeable
setup that day" — a condition correlated with the day's own price
behavior, not independent of the outcome being measured.

**Blast radius, both directions**:
- *Wrongly included*: none found. The 68/41/64/45 `ENTERED` rows that
  were measured are legitimate A/B-style resolutions; they are simply
  drawn from a biased subpopulation, not individually wrong.
- *Wrongly excluded*: all of the 997/552/1,092/574 dropped rows
  (90.0-95.0% of each bucket). Each one is a real Study F
  `NOT_RECLAIMED`/`SWEEP_EXTENDED` setup that could have had a
  well-defined counterfactual under the Study C/D-style construction
  (reuse F's own sweep extreme, run A's/B's own reclaim+fill+guard
  logic from there) but was excluded because the script instead
  required A's/B's own independent sweep detection to also succeed — a
  stronger, different, and outcome-correlated condition.

**Disposition: SELECTIVE loss. Not rerun, per instruction.** A
counterfactual built this way cannot answer the question on a
representative subsample; patching the construction and rerunning
would be a different measurement, not a fix of this one, and was not
done here.

**Not a BUGS.md-worthy code defect.** The error lives entirely in this
measurement's own throwaway script (never committed, never part of
`src/liquidity/`), not in any production code. Checked, per instruction,
whether the same shape exists in Studies A-D's own bucket reporting: it
does not — Study C's `_original_entry_long/short` and Study D's
`_original_ab_entry_long/short` both correctly reuse the SAME
originating sweep already found, rather than re-detecting one
independently. Their own `no_retest`/`PATTERN_INCOMPLETE` figures
(+1.0%, +0.87-0.91%) are unaffected by this mistake.

**No corrected number is reported here.** A properly-constructed
counterfactual (reusing Study F's own sweep extreme) was not built or
run in this pass -- doing so would be a new measurement requiring its
own fresh pre-statement, not a patch to this one.
