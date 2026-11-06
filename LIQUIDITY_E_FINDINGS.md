# Liquidity confluence, Study E (timeframe comparison): experiments log

No companion preregistration document exists for this study -- the
preregistration was never written, by explicit instruction, because
Phase 1's own feasibility check closed the study first. This file is
the complete record of what was specified, what Phase 1 found, and why
the study was abandoned before any DEV trade was ever computed.

## Provenance, stated plainly

**Study A (long, 5-min)**: mean net return **-0.2841%**, 8,131 trades,
both nulls **100th percentile**. Closed at DEV, NO EDGE, TEST not read.

**Study B (short, 5-min)**: mean net return **-0.1212%**, 9,222 trades,
both nulls **100th percentile**. Closed at DEV, NO EDGE, TEST not read.

**Study C (retest confirmation)**: **-0.2694%** (long) / **-0.1096%**
(short), both failed DEV, both nulls 100th percentile both sides.

**Study D (ascending lows)**: **-0.2926%** (2LOW-long) / **-0.1383%**
(2LOW-short), both failed DEV, worse than their own unfiltered A/B
baselines, and the half-target reach rate -- the hypothesis's own test
in both C and D -- FELL rather than rose.

**All four closed at DEV with NO EDGE. Study E was proposed as a fifth
revision after four consecutive failures in the same mechanism -- severe
selection pressure, recorded here exactly as it was recorded before
Study D's own trial**: swing V1 reached the **100th percentile on
65,219 development trades at p=0.001**, cleared both Bonferroni and
Benjamini-Hochberg correction, and scored only the **61.4th percentile**
on its own sealed holdout. An extreme, multiply-corrected in-sample
result is not a guarantee of anything once new data is read -- recorded
here as the same standing caution it was for Study D, not reached in
Study E's own case because Study E never produced a DEV result at all.

**THE HYPOTHESIS, as proposed**: the sweep-and-reclaim mechanism may
work at a different confirmation timeframe than the 5-minute candles A
and B used -- specifically, 1-hour sweep-and-reclaim candles, compared
directly against a 5-minute arm re-derived through the identical code
path (so the comparison would be strictly like-for-like, not code
written twice).

**THE COUNTER-EVIDENCE, recorded with equal weight before any trade
existed**: both C and D found that waiting longer for confirmation
discards the winners -- the trades filtered out for not producing the
required additional pattern averaged **+0.87% to +1.15%** across both
studies. An hourly confirmation is a slower form of waiting, and was
expected to inherit that same risk directly.

## PHASE 1 -- feasibility estimate, sample-based, before any full run

Per the study's own process (feasibility first, STOP for approval
before the preregistration is even written), a sample of 12 entities
with full 7-year DEV coverage (84 of the universe's 1,400 entity-years,
a 6% sample, scale factor 16.67x) was run through the REAL, unmodified
`poc.v4.find_sweep`/`find_reclaim` and `liquidity.b.find_sweep_short`/
`find_reclaim_short` against both 5-minute candles and
`fvg.bars.aggregate_to_1hour` output, for every eligible entity-day
(15,176 of them in the sample). No preregistration was written, no
`src/liquidity/e.py` was created, and nothing from this phase was
committed -- a disposable sample script only.

**The 5-minute arm reproduced A and B closely**, confirming the
reused-code-path approach was sound: scaled estimate 8,267 trades vs
A's actual 8,131 (1.7% off); 9,633 vs B's actual 9,222 (4.5% off). Both
within normal sampling noise for this sample size.

### THE CONFOUND -- fatal, found before any full run

**"Reclaim within 3 candles" means 15 minutes on the 5-minute arm and 3
hours on the hourly arm -- a 12x difference in real-time window.** The
rule was expressed in CANDLES (`poc.v4.RECLAIM_WINDOW_CANDLES = 3`,
reused unchanged, exactly as the design called for), and candle size was
the one variable the study intended to test -- so the reclaim window's
own real-time generosity changed silently along with it. The two arms
would therefore have differed in BOTH confirmation granularity AND
reclaim patience at once. Any difference observed between them could
not have been attributed to timeframe alone -- it would have been
impossible to say whether an effect came from "hourly confirmation is a
better/worse signal" or from "a 3-hour-patient setup behaves differently
from a 15-minute-patient one," two genuinely different mechanisms
conflated into one comparison. **That is not a controlled comparison.
It is two changes at once, dressed as one.**

This is NOT a minor wrinkle -- it directly produced the single largest,
most surprising result of Phase 1:

| Config | scaled reclaimed | scaled fill-in-window | scaled lost to 14:30 cutoff |
|---|---|---|---|
| 5-min long | 10,100 | 8,267 | 1,500 |
| 5-min short | 11,117 | 9,633 | 1,033 |
| 1-hour long | 14,767 | **11,233** | 2,000 |
| 1-hour short | 17,300 | **14,417** | 1,733 |

**The hourly arm produced MORE trades than the 5-minute arm, not
fewer** -- sweep events were actually somewhat less frequent per
candle on the hourly arm (fewer, wider candles), but reclaim succeeded
far more often once a sweep was found, because the reclaim window was,
in real time, 12x longer. The 14:30-cutoff loss rate was similar across
both arms (~10-15% of reclaimed setups either way) -- most late-day
hourly setups failed upstream as `NOT_RECLAIMED` (running past the
day's last candle) rather than registering as a cutoff loss.

**CLAUDE'S PRE-COMMITTED PREDICTION WAS WRONG, and wrong specifically
because this mechanism was missed.** The prediction (stated before
Phase 1 ran) was "far fewer trades, possibly under 2,000 combined" for
the hourly arm, reasoning from "an hourly confirmation is a slower form
of waiting" by analogy to C's and D's own slower-waiting filters. That
analogy held for the FILTER studies (C, D), where additional structure
had to be found WITHIN a fixed real-time entry window before it closed.
It did not hold here, because Study E's own design did not hold the
reclaim window's real time constant across arms -- the thing that would
have made "slower confirmation discards winners" a fair comparison was
never actually constant between the two arms being compared. The
prediction's own reasoning was sound for the wrong study design.

### Runtime estimate

Stage-1 (backtest) scan cost extrapolates to ~33-40 minutes per
configuration, closely cross-validating against Study D's own actual
Stage-1 times (34-38 minutes) -- good confidence in the sample's scaling
methodology. The null stages are the dominant cost and scale with trade
count. Using Study D's own observed null-stage/trade-count ratio (~3.5
seconds/trade -- one historical data point, flagged as uncertain, not a
precise model): 5-minute arms ≈ 8.5-10 hours each, hourly arms ≈
11.5-15 hours each. **Roughly 45-50 hours total if run sequentially --
more than double Study D's own ~20-hour run, which itself left two of
four configurations unfinished.** Study E's trade counts are larger than
Study D's filtered counts in every configuration, so this is not an
improvement on Study D's own operational problem -- it is a worse
version of it.

### Two smaller findings, recorded for reuse in any future hourly-candle study

- **Partial-bucket convention, reused from POC V3's own precedent**:
  the day's last hourly bucket (15:15-15:30, 15 minutes rather than 60)
  is eligible to serve as a sweep or confirmation candle like any other
  -- `find_entry_v3` (`src/poc/v3.py`) already established this, using
  the bucket's own actual `bucket_end` for the close timestamp rather
  than an assumed fixed offset. Phase 1's sample script followed the
  same convention.
- **The first hourly bucket (09:15-10:15) is excluded from sweep
  eligibility**, a real asymmetry inherent to reusing `find_sweep`
  unchanged: that function filters candles to `ts >= ENTRY_WINDOW_START`
  (09:45) using each candle's own START time, and the first hourly
  bucket starts at 09:15 -- before the window opens -- so the entire
  first hour is unavailable for a sweep on the hourly arm, with no
  equivalent loss on the 5-minute arm (whose first in-window candle
  starts exactly at 09:45).

## Liquidity family tally

**Five trials specified. Four failures (A, B, C, D) -- all closed at
DEV with NO EDGE, TEST never read in any of them. Study E is neither a
failure nor an untested idea: it was fully specified, evaluated at the
feasibility stage, found to be a confounded comparison at an infeasible
cost, and deliberately abandoned before any DEV trade was computed.**
Recorded as its own category -- SPECIFIED AND ABANDONED AT PHASE 1 --
distinct from a DEV failure (which requires a completed DEV run) and
from an idea that was never evaluated at all (Study E was evaluated;
the evaluation is exactly what closed it).

## Status

**CLOSED AT PHASE 1 -- NOT RUN.** No preregistration was written, no
`src/liquidity/e.py` was created, no DEV backtest exists. Closed for
two independent reasons, either alone sufficient: (1) the design as
specified was confounded -- candle width and reclaim-window real time
varied together, not independently, so no result could have been
attributed to timeframe alone; (2) the estimated cost (~45-50 hours
sequential across four configurations) exceeded Study D's own already-
problematic ~20-hour, two-of-four-configurations-unfinished precedent.
The reusable lesson (candle-expressed rules silently change real-time
meaning when candle size is the variable under test) is recorded as a
standing rule in `OPERATIONS.md`.

**No committed Bonferroni gate threshold exists for this study.** A
"four configurations, p < 0.0125" framing was discussed before this
study was closed, but that framing was never written into this
document or into any other committed file -- it exists only in chat.
Any figure for this study's own Bonferroni correction circulating
outside this repository was never committed and should not be treated
as a project fact (`OPERATIONS.md`'s own standing rule on this).
