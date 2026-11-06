# Liquidity confluence, Study D (ascending lows): experiments log

Companion to `PREREGISTRATION_LIQUIDITY_D.md` (frozen rules, commit
`ddbfc22`). Liquidity family, trial 4. Records what was actually run and
found, per the preregistration's own Process section.

## Synthetic unit tests (Process Step 2 precursor)

`scripts/liquidity_d_unit_test.py` -- pure-function scenarios, no DB
access: `find_ascending_lows_long`/`find_ascending_highs_short` against
synthetic 5-minute candles covering a clean ascending pair/triple
(CONFIG 2LOW/3LOW), a qualifying local low/high above/below the zone
being ignored entirely (does not count, does not reset), a non-ascending
qualifying candidate resetting the running count rather than killing the
pattern, `PATTERN_BROKEN` (a new extreme beyond the original sweep), and
`PATTERN_INCOMPLETE` (day ends with the count short). **All 12 checks
passed.** Every sequence was constructed AND run against the real
function BEFORE being written down as an assertion -- not hand-traced
and trusted blind, the exact discipline `liquidity_c_unit_test.py`'s own
first draft lacked (caught there before any real-data trace, applied
here from the start instead of being re-learned).

## Hand-traced examples (Process Step 2), 5 per configuration, 20 total

All 20 required shapes -- `PATTERN_BROKEN`, `PATTERN_INCOMPLETE`,
`FULL_EXIT`, `STOP_NO_HALF`, `HALF_THEN_TIME_EXIT`, for each of
2LOW-long, 2LOW-short, 3LOW-long, 3LOW-short -- found by
`scripts/liquidity_d_handtrace.py` against the real DEV window, **all
twenty on the very first entity scanned** (`INE002A01018`) except
3LOW-long's own `FULL_EXIT` (found on the fourth entity scanned,
`INE012A01025` -- the only shape not reachable from the first entity's
own history, since a clean three-ascending-low win happened not to occur
there in the DEV window).

**Internal-consistency checks, worth recording explicitly, not just the
individual traces**:

- **`PATTERN_BROKEN` is byte-identical between 2LOW and 3LOW for both
  directions** (long: `INE002A01018` 2016-10-13, breach at idx 9; short:
  `INE002A01018` 2016-10-06, breach at idx 7) -- confirms by direct
  comparison, not just by reading the code, that breaking the pattern
  depends only on breaching the original sweep extreme, never on
  `n_required`, exactly as Section 2/3 specify.
- **The stop price is identical between 2LOW and 3LOW for the same
  underlying setup** (long `STOP_NO_HALF` example, `INE002A01018`
  2017-03-21: stop = 1267.5791 in both, despite 2LOW entering at
  confirm_idx=16/entry=1277.4111 and 3LOW entering at confirm_idx=31/
  entry=1276.8844, a materially later and different fill) -- confirms
  the stop is anchored to the sweep's own extreme, not to anything
  touched during the ascending-lows scan, exactly as Section 4 requires.
- **3LOW's own confirming candle is consistently later than 2LOW's for
  the same setup** (the same example: idx 16 vs idx 31, a 75-minute
  difference in `delay_minutes_from_sweep`, 50.0 vs 125.0) -- the
  mechanism is doing what it says: requiring a third ascending low
  structurally delays entry relative to requiring only a second.
- **3LOW's own `PATTERN_INCOMPLETE` example (`INE002A01018` 2017-02-13)
  shows `pattern_count=2` (one short of the 3 required)**, a
  meaningfully different near-miss shape than 2LOW's own
  `PATTERN_INCOMPLETE` example (`INE002A01018` 2017-06-06,
  `pattern_count=0`, no qualifying low ever confirmed at all) -- the
  hand-trace sample happened to surface both the "never got going" and
  the "one short" failure shapes without being asked to look for both
  specifically.
- **Realized net returns and cost figures are in the same range as
  every prior study in this family** (`STOP_NO_HALF` losses -0.77% to
  -1.02%, `HALF_THEN_TIME_EXIT`/`FULL_EXIT` gains +0.44% to +1.93%,
  total three-order costs 60-76 rupees on 23,000-25,000 rupee positions,
  ~0.25-0.3%) -- no sign of a scale, sizing, or cost-model defect
  specific to this study's own new code path.

**All twenty hand traces are internally consistent with the
preregistration exactly as written.** The ascending-lows sequencing (the
reset-on-non-ascending interpretation, the above/below-zone ignore rule,
both exercised live on real data, not only in the synthetic test), the
`PATTERN_BROKEN` breach check against the original sweep extreme (both
sides), the `PATTERN_INCOMPLETE` day-end timeout, the recomputed-R
target formulas off the later entry, and the unchanged exit mechanics
(`FULL_EXIT`, `STOP_NO_HALF`, `HALF_THEN_TIME_EXIT`, both directions,
both configurations) were each exercised and spot-checked by hand before
any aggregate number was computed.

## Status

Hand-traces complete, all 20 shapes found and cross-checked (including
direct comparisons between 2LOW and 3LOW on the same underlying setups,
confirming the stop and `PATTERN_BROKEN` logic are correctly
n_required-independent while entry timing and realized returns correctly
differ). Next: run DEV only, all four configurations, report, and
**stop for approval before TEST**.

## DEV run (Section 12 Step 3): 2LOW-long and 2LOW-short complete, 3LOW NOT RUN

The DEV run started 2026-11-03, was interrupted before 3LOW could run,
and was not resumed. 2LOW-long and 2LOW-short each completed in full
(backtest, both nulls at the full seed count, gate evaluation). 3LOW-long
reached only 50/321 entities of its own backtest stage before the
interruption; 3LOW-short never started. The decision below is to close
the study on the 2LOW results alone and NOT run 3LOW -- a deliberate
stop, not an accident of the interruption (see "Why 3LOW was not run,"
below).

### 2LOW-long: FAIL, worse than unfiltered

Mean net return **-0.2926%** (5,387 trades, CI(Bonf4) [-0.3872%,
-0.1895%], excludes zero on the negative side), vs **Study A's -0.2841%**
(8,131 trades). Both nulls at the 100th percentile. `DEV_PASS: false`.

The ascending-lows requirement cut the trade count from 8,131 to 5,387
(roughly a third of A's trades removed) and the survivors performed
**worse** than A's unfiltered population (-0.2926% vs -0.2841%), not
better.

### 2LOW-short: FAIL, worse than unfiltered

Mean net return **-0.1383%** (6,070 trades, CI(Bonf4) [-0.1936%,
-0.0839%], excludes zero on the negative side), vs **Study B's -0.1212%**
(9,222 trades). Both nulls at the 100th percentile. `DEV_PASS: false`.

Same pattern as the long side: trade count cut from 9,222 to 6,070
(again roughly a third removed), and the survivors performed worse than
B's unfiltered population (-0.1383% vs -0.1212%).

### The hypothesis's own test: half-target reach rate

The hypothesis was that requiring ascending lows selects trades that
follow through -- sellers losing strength, not just one more touch. The
half-target reach rate is that hypothesis's own test, and it **fell** on
both sides:

- 2LOW-long: **17.8%** reach rate (942/5,287 scaled-eligible trades) vs
  **Study A's 21.6%**.
- 2LOW-short: **21.5%** reach rate (1,285/5,987 scaled-eligible trades)
  vs **Study B's 26.5%**.

The filter did not do what was proposed. This is the same direction of
failure Study C's own retest requirement produced against the same A/B
baselines (21.6% -> 19.6% long, 26.5% -> 23.4% short) -- a second,
differently-constructed waiting rule in this family, and a second time
the reach rate fell instead of rising.

### PATTERN_INCOMPLETE: repeats Study C's NO_RETEST finding

For every trade the ascending-lows requirement filtered out, the
counterfactual A/B-style (immediate-entry) trade was also computed.
Split by skip reason:

- 2LOW-long `PATTERN_INCOMPLETE` (1,893 trades): mean counterfactual
  **+0.906%**. `PATTERN_BROKEN` (4,144 trades): mean counterfactual
  **-0.765%**.
- 2LOW-short `PATTERN_INCOMPLETE` (2,675 trades): mean counterfactual
  **+0.871%**. `PATTERN_BROKEN` (4,460 trades): mean counterfactual
  **-0.646%**.

`PATTERN_INCOMPLETE` repeats Study C's `NO_RETEST` finding exactly: the
trades discarded because the pattern never finished were, on average,
**winners** (+0.87% to +0.91%, in the same range as `NO_RETEST`'s own
+1.0% to +1.15%). A waiting rule that requires more structure before
entry is, for a third time in this family (Study C's retest, Study D's
ascending-lows), disproportionately discarding the strongest moves --
the ones least likely to pause long enough to produce the additional
structure the rule demands. `PATTERN_BROKEN`'s own counterfactual mean is
negative, so that half of the filter is working as intended; it is the
`PATTERN_INCOMPLETE` half that is working against the hypothesis, same
as `NO_RETEST` did.

### Why 3LOW was not run

2LOW already failed in both directions and already performed worse than
the unfiltered baseline in both directions. 3LOW is the identical filter
applied more strictly (a third ascending low required instead of a
second) -- the same lever, pushed further in the same direction that
already failed. Running 3LOW now would have answered a question this
study no longer needed answered. This is recorded as a **deliberate stop
on an already-decided question**, not as an incomplete study left
dangling.

The partial 3LOW-long checkpoint (50/321 entities, no completed
backtest, no nulls) is **discarded, not reported** -- it contains no
result of any kind, only an interrupted intermediate state.

### Liquidity family tally

**Four trials, four failures.** Study A (long, NO EDGE), Study B (short,
NO EDGE), Study C (retest, NO EDGE both sides), Study D (ascending lows,
NO EDGE both sides, 3LOW deliberately not run). **TEST has never been
read in any of the four.**

### Operational lesson

This DEV run was estimated in hours and needed roughly 20: two
configurations (2LOW-long, 2LOW-short) alone consumed about 10 hours of
wall-clock time, and 3LOW-long/3LOW-short were not reached. Future
multi-configuration studies in this family should either budget
wall-clock time for the full configuration count up front (roughly 5x
the single-configuration estimate here, not a flat multiple assumed from
one config's own quick run), or run each configuration as a separate
job/process so that an interruption strands at most one half-finished
configuration rather than leaving the remainder unstarted.

## Status

**CLOSED.** 2LOW-long and 2LOW-short both FAIL at DEV and both perform
worse than their unfiltered baselines (Studies A and B); the
hypothesis's own half-target-reach-rate test fell on both sides; the
`PATTERN_INCOMPLETE` filtered-out trades were, on average, winners,
repeating Study C's `NO_RETEST` finding. 3LOW was deliberately not run
(see above) -- its partial checkpoint is discarded. Study D is closed
**partially completed**: a decision was reached and the study is done,
even though two of its four pre-registered configurations never
executed. TEST not read. Liquidity family: 4 trials, 4 failures.
