# Liquidity confluence, Study C (retest confirmation): experiments log

Companion to `PREREGISTRATION_LIQUIDITY_C.md` (frozen rules, commit
`ffaa7ca`). Liquidity family, trial 3. Records what was actually run and
found, per the preregistration's own Process section.

## Synthetic unit tests (Process Step 2 precursor)

`scripts/liquidity_c_unit_test.py` -- pure-function scenarios, no DB
access: `find_retest_long`/`find_retest_short` against synthetic 5-minute
candles covering the two-candle retest, the same-candle (single-bar
touch-and-close) retest, `RETEST_FAILED` (a breach of the original sweep
extreme before any valid retest), and `NO_RETEST` (both "never returns
to the zone" and "returns but never recloses") for each direction. **All
9 checks passed** (one round of test-data correction was needed first --
the initial scenario data set reclaim/pullback prices so close to the
zone that a pullback candle's own close was already trivially above the
zone price, confirming nothing about the sequencing logic; caught by
re-deriving the expected result by hand before trusting the test, not
after, and fixed before any real-data trace).

## Hand-traced examples (Process Step 2), 5 per side, 10 total

All 10 required shapes -- `NO_RETEST`, `RETEST_FAILED`, `FULL_EXIT`,
`STOP_NO_HALF`, `HALF_THEN_TIME_EXIT`, for LONG and for SHORT each --
found by `scripts/liquidity_c_handtrace.py` against the real DEV window,
**all ten on the very first entity scanned** (`INE002A01018`), the same
entity every one of Study A's and Study B's own hand-traces also used.

**One direct cross-check against Study A's own already-verified
numbers, worth recording explicitly**: Study C's own `STOP_NO_HALF`
(long) example is `INE002A01018`, 2017-05-18 -- the EXACT SAME entity,
date, zone (`zone_price=1340.6250`, members `('1d','1w')`), sweep
(`sweep_idx=8`), and reclaim (`reclaim_idx=10`) as `LIQUIDITY_A_
FINDINGS.md`'s own `STOP_NO_HALF` hand-trace. This is expected, not a
coincidence to investigate -- Study C reuses Study A's own unchanged
sweep/reclaim detection, so the same day necessarily produces the same
setup up to that point. What differs, and was checked by hand: Study C's
own retest candle (idx 11, 10:10) pulls the fill one 5-minute bar later
than Study A's own (10:05 vs. Study A's 10:05 reclaim-based fill -- the
retest adds exactly one candle's delay here), landing at **entry =
1340.7050** (vs. Study A's own 1340.9886) while the **stop is identical,
1332.6486** -- confirming by direct comparison, not just by reading the
code, that Study C's own stop correctly uses the ORIGINAL sweep extreme
(`final_sweep_low = 1335.5191`, matching Study A's own hand-traced value
exactly) and not any level touched during the retest. Both studies'
version of this trade resolve the same way here (`STOP_NO_HALF`), since
the stop is unchanged and price moved against the position regardless of
the few extra minutes' delay.

**All ten hand traces are internally consistent with the preregistration
exactly as written.** The retest sequencing (two-candle and same-candle
confirmation, each exercised live, not only in the synthetic test), the
`RETEST_FAILED` breach check against the ORIGINAL sweep extreme (both
sides), the `NO_RETEST` timeout, the recomputed-R target formulas off
the later entry, and the unchanged exit mechanics (`FULL_EXIT`,
`STOP_NO_HALF`, `HALF_THEN_TIME_EXIT`, all three shapes, both
directions) were each exercised and spot-checked by hand before any
aggregate number was computed.

## Status

Hand-traces complete, all 10 shapes found and cross-checked (including
direct verification against Study A's own previously-verified numbers
for the shared sweep/reclaim portion of one trade). Next: run DEV only,
both sides (Process Step 3), report, and **stop for approval before
TEST**.
