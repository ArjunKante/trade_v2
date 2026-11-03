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
