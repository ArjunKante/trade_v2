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
