# Pre-registration: Box Theory V2, strength-filtered previous-session reversal

Frozen before any touch is counted, any trade is simulated, or any R value
exists, per this project's standing discipline (`PREREGISTRATION.md` and
family, including `PREREGISTRATION_BOX.md`, V1's own frozen document).
Nothing below changes after this document is committed except by an
explicit, recorded amendment, made before the next result that amendment
could have been shaped by.

## Provenance -- stated plainly, as instructed

**V1 closed at DEV with NO EDGE** (`BOX_FINDINGS.md` Step 3, `PREREGISTRATION_
BOX.md` Section 7): both FAST and SLOW failed decisively -- mean net R
around -0.138 (FAST) and -0.126 (SLOW), every calendar year negative for
both configurations, and **0th percentile against the SELECTION null for
both** (random-day entry on the same universe-year population beat the
touch-and-reversal signal in all 500 resampled draws, every time). Per
V1's own Section 7, that closure is final for the rules frozen there; it
is not reopened, re-read, or re-costed by anything below.

**V2 is a REVISION proposed by the user AFTER seeing V1's failure.** It
therefore carries selection pressure that V1 itself did not: the four
changes below were chosen with knowledge of what V1's result looked like,
even though no number from V2 itself exists yet. This is development
evidence only, to a greater degree than V1 was -- a DEV pass here
justifies forward paper trading at most, never a validity claim, and the
gap between "passes this gate" and "has genuine predictive edge" is wider
for a post-hoc revision than for an a-priori rule.

**The family trial count for box theory is now 3**: V1 FAST, V1 SLOW,
and V2. This is not re-litigated here -- V1's own two trials are already
spent and closed; V2 is the third and, per the discipline below, carries
its own one-shot discipline exactly as V1's two configurations did.

**Why V2 is not just a V1 variant, stated once, not left implicit**: V1's
confirmation threshold was "any green candle" -- a condition so loose that
nearly every touch-day satisfied it (only 7,167 of 277,128 + however many
actually-touched days failed to find ANY green candle at all, out of V1's
full diagnostic counts -- see `BOX_FINDINGS.md`). V1's SELECTION-null
failure is consistent with a story where the entry trigger carries no
information: almost any day that touches the previous low eventually
shows a green candle, so "touch + any green candle" is barely
distinguishable from "touch," which V1's own SELECTION null (built from
the same touch-eligible population, including non-touch days) already
showed loses. V2 asks a different, narrower question: among days that
touch the previous low, does a STRONG reversal -- a candle with
materially more range and volume than what came immediately before, with
materially more room to the previous high, and confirmed within a tight
two-candle window -- behave differently? That is not a retuned threshold
on the same mechanism; it is a different selection criterion over the
same touch population, which is exactly what V1's failure leaves open
(see V1's own `BOX_THEORY.md`/`PREREGISTRATION_BOX.md` Section 0 "does
not conclude" framing, by analogy with Fibo's own closing language).

## 0. Scope and reuse boundaries

**New code lives in `src/box_theory/v2.py` only.** `src/box_theory/`'s
existing modules (`context.py`, `resolution.py`, `bars.py`, `holiday.py`,
`costs.py`, `inference.py`, `nulls.py`, `backtest.py`, `test_seal.py`,
`universe_data.py`) are imported and reused **read-only, unmodified** --
V1's closed result must stay reproducible exactly as recorded, which
means nothing V1 depends on may change underneath it. Specifically reused:

- `box_theory.context.eligible_day_context` / `group_by_day` -- the
  identical Section 2b eligibility pipeline (jump guard, ex-date,
  previous-session validity, scale resolution), unchanged, because V2's
  box definition, universe, guards, and scale handling are identical to
  V1's.
- `box_theory.resolution.resolve_exit` / `resolve_exit_arrays` --
  unchanged. V2's stop, arming, exit, and time-exit rules are byte-
  identical to V1's FAST configuration (Section 3 below); V2 calls these
  with `config="FAST"` literally, not a relabeling -- that string
  selects the single-red-candle exit branch these functions already
  implement, which is exactly the exit rule V2 uses.
- `box_theory.resolution.find_touch_idx`, `fill_bar_after_candle_close`,
  `position_size_shares` -- unchanged; V2's touch detection, fill
  mechanics, and position sizing are identical to V1's.
- `box_theory.costs.band_for_rank` / `round_trip_cost_rs` -- unchanged;
  same Section 8c banded model, same `swing.costs` INTRADAY formulas.
- `box_theory.backtest.build_universe` -- unchanged; same point-in-time
  top-200 annually-reconstituted universe, same stub-year handling.
- `box_theory.inference.day_clustered_bootstrap` / `percentile_vs_null`
  / `excludes_zero` -- unchanged. V2 is "one configuration" (Section 5
  below), so this is used with its existing 97.5% two-sided bounds
  ([1.25th, 98.75th] percentile) directly, not re-split by the family's
  3-trial count -- stated explicitly here, not left to be noticed later.
- `box_theory.nulls.build_timing_pool` / `timing_null_seed_mean` /
  `build_month_pool` / `selection_null_seed_mean` / `baseline_return` --
  unchanged. These functions know nothing about touch/confirmation
  logic at all -- TIMING and SELECTION nulls replace the ENTRY TRIGGER
  with a random one and keep everything downstream (room check against
  that stock-day's own PREV_HIGH, stop, arm, exit, cost) identical,
  which is exactly as true for V2 as it was for V1. Passing
  `config="FAST"` reuses V1's exact exit-style null machinery unmodified.
- `box_theory.test_seal` -- the SAME sealed-window guard instance V1
  uses (same `DEV_START`/`DEV_END`/`TEST_START`/`TEST_END`, same access
  log), not a new copy. V1 and V2 are the same study FAMILY sharing one
  TEST boundary definition; a fresh, duplicate seal would only create a
  second place to misconfigure the same dates.

**New in `src/box_theory/v2.py`**: the strength-filtered confirmation
check (Section 3, Change 1), the two-candle-patience entry search
(Change 2), and the 5% room check (Change 3) -- a new `find_entry_v2`
function, and a thin per-entity/per-run orchestration layer
(`evaluate_entity_v2`, `run_backtest_v2`) that calls `find_entry_v2`
instead of V1's `find_entry` but is otherwise structurally identical to
`backtest.py`'s own orchestration (same eligibility loop, same cost
attribution, same trade-record shape, same `errors` exception handling
added to V1 after its own DEV run).

## 1. The question

Among stock-days that touch the previous session's low, does a STRONG
reversal candle -- materially more range and volume than the preceding
40 minutes, confirmed within two candles, with materially more room to
the previous high than V1 required -- produce positive net return after
costs, and does it beat random entry on the same, much smaller set of
qualifying stock-days?

## 2. Universe, data, and box definition -- unchanged from V1, restated briefly

Point-in-time top-200 by trailing median turnover, annually
reconstituted (`fibo.universe.reconstitute_annually`, `top_n=200`), stub
year 2016 copied from 2017, filtered via `restrict_to_universe` and
guarded via `assert_universe_membership` -- identical to
`PREREGISTRATION_BOX.md` Section 2a, same code (`box_theory.backtest.
build_universe`), not re-derived.

1-minute bars from `data/fibo_intraday.duckdb`, aggregated to 5-minute
candles for every signal decision, same bucket convention
(`box_theory.bars.aggregate_to_5min`). PREV_HIGH/PREV_LOW = the previous
trading session's raw-scale 1-minute high/low, same two-step validity
check as V1 Section 2b (market-wide calendar previous-trading-day,
>= 350 one-minute bars that session), same scale-probe-derived raw-scale
conversion spanning both sessions, same ex-date/jump-guard exclusions.
All of this is `box_theory.context.eligible_day_context`, called
unchanged.

## 3. Box and signal rules -- the four changes, and nothing else

Everything stated in `PREREGISTRATION_BOX.md` Section 3 carries over
EXCEPT the four items below: touch detection (3a) is identical; stop
(3d), arming, and the red-candle exit (3e) are identical; the 15:15 time
exit, including its missing-15:15 archive-gap fallback, is identical.
**Only entry confirmation (3b) and the room filter (3c) change.**

### CHANGE 1 -- strong confirmation candle

A confirming candle must be **green** (`close > open`) **and** satisfy
**both**:

```
range  >= 1.5 x mean(high - low) of the trailing window
volume >= 1.5 x mean(volume)     of the trailing window
```

**The trailing window is the 8 five-minute candles ending at the touch
candle inclusive (the touch candle's own 40 minutes back from, and
including, itself)** -- fixed once per touch, at the touch candle, and
reused unchanged for evaluating BOTH candidate confirming candles in
Change 2 below. It is not recomputed relative to whichever candle is
being tested. This is the literal reading of "ending at the touch
candle inclusive," stated explicitly so it is not quietly reinterpreted
as "ending at the candidate" later.

**Fewer than 8 candles available**: if the touch candle is not preceded
by 7 full candles that day (i.e., touch_idx + 1 < 8), use however many
candles exist from the start of the day through the touch candle
inclusive, down to a floor of **4**. Below 4 (touch occurs in the first,
second, or third 5-minute candle of the day), **the day is skipped and
counted** under its own reason, `insufficient_candles` -- not folded
into `no_strong_candle`, so the report can distinguish "never had enough
data to judge strength" from "had enough data and the candle was weak."

### CHANGE 2 -- two-candle patience, no open-ended scan

V1 scanned forward indefinitely for the first green candle anywhere
after touch. V2 does not: **the confirming candle may only be the 1st or
2nd five-minute candle after the touch candle.** Checked in order: test
the 1st candle after touch against Change 1's three conditions (green,
range, volume) using the SAME touch-anchored trailing window; if it
qualifies, that is the confirmation, recorded as `which_candle=1`,
regardless of which specific condition would have made the 1st candle
fail if it hadn't passed. If the 1st candle does not qualify -- for any
reason, color included -- test the 2nd candle after touch the same way;
if IT qualifies, confirmation, `which_candle=2`. **If neither qualifies,
the day is skipped**, counted under `no_strong_candle`. There is no
third candle, no fallback, no further scanning.

Entry fills at the open of the next 1-minute bar after the confirming
candle closes -- identical mechanic to V1 (`fill_bar_after_candle_
close`, reused unchanged).

### CHANGE 3 -- room requirement raised to 5%

Skip (no trade, counted under `no_room`) unless:

```
(PREV_HIGH - entry_price) / entry_price >= 0.05
```

Replaces V1's 1% floor outright -- not an additional check, a
replacement. Evaluated once the fill price is known, exactly as in V1.

### CHANGE 4 -- nothing else changes

Stop: 3% below the entry fill, checked on 1-minute bars starting with
the entry bar itself, same same-bar STOP-wins tie rule. Arming: armed
once any 5-minute candle (entry candle onward) has high >=
0.995 x PREV_HIGH. Exit once armed: the first red candle after arming
(V1's FAST rule specifically -- **no SLOW variant is tested in this
study**; "equivalent to V1's FAST exit" is literal, via `config="FAST"`
passed into the reused `resolve_exit`). Time exit: close of the 15:15
candle, with V1's already-built fallback to the latest available candle
at or before 15:15 when the archive does not reach it that day.

**The 1.5x multipliers and the 8-candle lookback are FIXED by this
document and are not tuned.** If DEV fails, this document is not
amended to try 1.3x, 2x, a 6-candle window, or anything else -- per
Section 10.

## 4. Sizing and costs -- unchanged from V1

Fixed Rs 500 risk, `qty = floor(500 / (0.03 x entry))`, R = Rs 500 by
construction. Costs: Section 8c banded spread (2.0/4.0/7.0 bps by rank
band) plus `swing.costs` INTRADAY statutory/fixed formulas, raw-scale
position values -- `box_theory.costs.round_trip_cost_rs`, unchanged,
same code V1 used.

## 5. Inference plan

Day-clustered bootstrap (`box_theory.inference.day_clustered_bootstrap`,
unchanged code): resample whole trading days with replacement, 10,000
resamples, pooled mean net R as the point estimate. **97.5% two-sided
CI** ([1.25th, 98.75th] percentile of the resampled means) -- **no
further Bonferroni adjustment beyond this**, per instruction, since V2
is evaluated as one configuration on its own terms; the family's 3-trial
count (Section "Provenance" above) is recorded for the record, not
threaded into this CI's own width. Minimum detectable effect reported
from the bootstrap SE alone (`MDE = 2.2414 x SE`), never from the
observed mean -- same convention, same code, as V1.

**Seed count and runtime discipline, stated before any null is run**:
10,000 bootstrap resamples for inference are cheap (pure array
arithmetic on the real trade list, no DB access) and are not subject to
the 1000/500-seed null contingency below -- that applies only to the
TIMING and SELECTION null draw counts.

## 6. Nulls

Same three comparisons as V1 -- TIMING, SELECTION, BASELINE -- same
code (`box_theory.nulls`), `config="FAST"` throughout since that is V2's
actual exit style, not a label of convenience.

- **TIMING null**: restricted to the exact stock-days V2 actually
  traded. Random 5-minute entry bar in 09:30-14:30, **room rule at
  Change 3's 5% floor** (not V1's 1%), same stop/arm/exit/cost.
- **SELECTION null**: random stock-days from the same universe-year
  population used by the real backtest (every day passing Section 2b's
  eligibility, including non-touch days), **matched count per calendar
  month to V2's own much smaller per-month trade count** -- stated
  explicitly because V2's trade count will be far below V1's 82,365, so
  the matched counts themselves are reported (Section 8) rather than
  assumed comparable.
- **BASELINE** (descriptive only, not part of the gate): buy 09:30
  open, sell 15:15 close, every top-200 DEV stock-day passing Section
  2b's eligibility, net of the same cost model -- identical to V1's,
  and in fact identical in VALUE to V1's own BASELINE figure, since
  BASELINE depends only on the universe and window, not on the entry
  rule. Not recomputed from scratch; V1's own `dev_baseline.pkl` value
  is reused and cited if the month set is unchanged, with the reuse
  stated plainly in the report rather than silently re-presented as new.

**1000 seeds per null type, timed first exactly as V1's contingency
specifies**: a small run projects the full-seed runtime before
committing to it; if 1000 would exceed roughly an hour, 500 seeds are
used instead and the substitution is logged. **Unlike V1's first DEV
run, this measurement happens BEFORE the long stage starts, not
discovered partway through** -- `src/box_theory/v2.py`'s pool-builders
are measured for both per-seed timing and peak process memory
(`psutil`, OS-tracked peak working set) on a representative slice
before Stage 3/4 of the V2 run script ever commits to the full seed
count, per instruction.

## 7. Windows and gates

**DEV**: 2016-10-04 to 2022-12-31. **TEST (sealed)**: 2023-01-01 to
2026-09-18 -- `box_theory.test_seal`, the same instance V1 uses, same
dates, same access log. Not read unless DEV passes and the user
explicitly approves.

**DEV PASSES only if ALL hold**:
- mean net R > 0 with the day-clustered 97.5% CI excluding zero
- mean net R's percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls
- mean net R remains > 0 after dropping the single best calendar year
  (by that year's own mean net R) from the DEV sample
- mean net R > 0 within rank bands 1-100 alone (bands 1-50 and 51-100
  combined, band 101-200 excluded from this one check) -- same
  thin-band-dependency guard V1 carried

**Anything else = NO EDGE. The study closes, and the sealed TEST window
is never read.**

## 8. Report contents

Everything V1's Section 8 specified (trade count, distinct days, win
rate, mean/median net R with CI, exit-reason mix and how many trades
ever armed, by year, by band, peak/median concurrent positions and peak
capital, skip counts, diagnostics), plus, specific to V2:

- how many touch-days produced a qualifying strong candle, split by
  `which_candle` (1st vs. 2nd)
- skip/diagnostic counts broken out separately for: no strong candle
  found (`no_strong_candle`), insufficient room at the 5% floor
  (`no_room`), and too few prior candles to evaluate strength
  (`insufficient_candles`)
- the distribution of entry prices relative to the box (entry price as
  a fraction of the PREV_HIGH-PREV_LOW range, or the raw room-at-entry
  percentage distribution) -- so whether the 5% floor pushes entries
  materially lower within the box is visible, not assumed
- trade count against V1's 82,365 (FAST) / 100,338 (SLOW), stated
  plainly, since a much smaller sample widens the CI mechanically and
  that should be visible alongside the CI itself, not left for the
  reader to infer
- the SELECTION null's matched count per month, reported explicitly
  (Section 6)

## 9. Process, in this order, stopping where marked

1. Write this document. **Commit and push it alone**, before any
   backtest code exists. Report the commit hash.
2. Build `src/box_theory/v2.py` and test it. **Trace 5 trades by hand
   before any aggregate number is computed**: one where the 1st
   candidate candle confirmed, one where the 2nd did, one skipped for a
   weak candle, one skipped for insufficient room, one stop exit. Show
   the touch, the trailing-window mean range/volume, the candidate
   candle(s) checked and why they passed or failed, the fill, the stop,
   the exit, and the resulting net R.
3. Run **DEV only**, after a pre-flight timing/memory measurement on a
   representative slice. Report per Section 8. **>>> STOP. The user
   approves before the sealed TEST window is read.**
4. Only after that approval: authorize `box_theory.test_seal`, read
   TEST once, report per Section 8.

## 10. Discipline

**This is trial 3 of the box theory family** (Provenance, above). No
rule in this document changes after any number from V2's own DEV or
TEST has been seen. The 1.5x multipliers and 8-candle window are fixed
and are not retried at other values if DEV fails. **Bad results are
reported in the first sentence** of whatever reports them, not buried
after a methods recap -- same standing instruction as V1.

## Status

**>>> STOPPING HERE, per Process Step 1.** No V2 backtest code exists
yet. This document is being committed alone, before `src/box_theory/
v2.py` is written, so Step 2's hand-traces and Step 3's DEV run cannot
have shaped anything written above.
