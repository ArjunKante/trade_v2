# Pre-registration: POC family V5, multi-day hold

Frozen before any sweep is detected, any trade is simulated, or any
return value exists, per this project's standing discipline
(`PREREGISTRATION.md` and family, including `PREREGISTRATION_POC.md`
through `PREREGISTRATION_POC_V4.md`). Nothing below changes after this
document is committed except by an explicit, recorded amendment, made
before the next result that amendment could have been shaped by.

## MANDATORY: the argument for a fifth trial -- required by `PREREGISTRATION_POC_V4.md` Section 15

**The argument, stated at the top, as instructed:**

V4's result was structurally different from V1-V3. It PASSED both null
comparisons (TIMING 100.0, SELECTION 97.9) -- its entries genuinely
selected better-than-random stock-days -- and still lost 0.2862% per
trade. V1-V3 never passed a single gate condition. That isolates the
failure: the selection edge was real but smaller than intraday friction.
This project's own Phase 1 cost gate reached the same conclusion
independently, before any strategy existed -- short horizons struggle
because fixed costs are large relative to the available move. V5
therefore tests a STRUCTURAL hypothesis -- that the same selection edge,
given more time, produces a move exceeding costs -- rather than another
entry-rule refinement.

**The counter-argument, recorded with equal weight:** swing V1 reached
the 100th percentile on 65,219 development trades at p=0.001, cleared
Bonferroni and BH, had a plausible mechanism, and scored 61.4th on its
sealed holdout (`SWING_FINDINGS.md`). A strong in-sample result from
this project has already failed to replicate once. V5 is the fifth
revision of one idea, every one chosen after seeing the previous fail.
Selection pressure is severe.

**POC family trial count becomes 5.**

| Trial | Result | What changed |
|---|---|---|
| V1 | -0.6733 R | original design -- contaminated by a sizing pathology |
| V2 | -0.4077% | pathology removed; stop moved to the 5-day lookback low |
| V3 | -0.3176% | confirmation timeframe moved to hourly |
| V4 | -0.2862% | entry condition replaced (liquidity sweep + reclaim); BOTH nulls passed |
| V5 | ? | holding period changed from intraday to up to 10 trading days |

## V5 IS V4 WITH THE HOLDING PERIOD CHANGED. Everything else identical.

**ENTRY: unchanged from V4.** Sweep below LOOKBACK_LOW by 0.1x-1.0x ATR
(too shallow = keep watching, too deep = abandon the day as a
breakdown), reclaim (close back above LOOKBACK_LOW) within 3 five-minute
candles (sweep_low tracked downward on a new low during the wait, clock
never reset), entry at the open of the next 1-minute bar after the
reclaiming candle closes, window 09:45-14:30. Reused via `poc.v4.
find_sweep`/`find_reclaim`, unchanged, not reimplemented.

**STOP: unchanged.** `sweep_low - 0.1 x ATR` (the FINAL, possibly-
updated sweep_low, same as V4). **The user has chosen NOT to widen it
for overnight risk, recorded here as a deliberate choice**: the stop is
a fixed rupee level computed once at entry, exactly as V4 computed it,
even though the position can now be held overnight and across weekends.
**Consequence, stated plainly**: realised losses will sometimes exceed
the stop's own distance when a day's open gaps below it -- this is
measured and reported (gap-through count and cost, Section 8 below), not
hidden inside an average.

**TARGET: CHANGED, as a FORCED change, not a tuned one.** V4's 2%-below-
PREV_HIGH target is an intraday level, chosen to be reachable within one
session; held for up to 10 days, it would be hit almost immediately in
the overwhelming majority of cases, making the 10-day hold meaningless
and the two changes (entry unchanged, hold extended) impossible to
isolate from each other's effect. Replaced with:

```
target_price = entry_price + 3 * (entry_price - stop_price)
```

**3x the initial risk-per-share, a structural requirement of testing a
multi-day hold, not a value chosen by fitting anything.** One direct,
stated consequence: since `entry_price > stop_price` is already
guaranteed by the `ENTRY_BELOW_STOP` check (Section 5 below, unchanged
from V4), `target_price > entry_price` ALWAYS holds -- **V5's own
`NO_ROOM` check is structurally unreachable** (V4's `NO_ROOM` fired on
31 real setups whose level-based target sat at or below entry; a
risk-multiple target computed FROM entry can never do that). The check
is kept in the code for symmetry and is never expected to fire --
stated here explicitly so its absence from the real run's skip counts
is never mistaken for a bug, the same convention `PREREGISTRATION_
POC_V2.md` used for its own structurally-impossible `ZERO_QTY`.

**Direct consequence for the population check below**: V4's own entry
funnel reached the target/`NO_ROOM` stage with 3,256 fills (3,225
ENTERED + 31 `NO_ROOM`). Since V5's target can never trigger `NO_ROOM`,
**V5 is expected to produce 3,256 entries, not 3,225** -- stated as a
prediction here, before the run, precisely so Section 10's own
population check is a real confirmation, not a number chosen to match
after the fact.

## OVERNIGHT MECHANICS -- modelled explicitly, not assumed

Stops and targets are checked on **1-minute bars on the entry day**
(reusing `poc.resolution._stop_target_event` unchanged -- the identical
entry-day scan V1-V4 always used, fill_ts through 15:19, STOP wins a
same-bar tie) and on **DAILY bars for every trading day after the entry
day**, up to 10 such days:

- a day's LOW at or below the stop -> exit at the stop price, UNLESS
  that day's OPEN is already below the stop, in which case exit at the
  OPEN (a gap-through) -- checked FIRST each day.
- else, a day's HIGH at or above the target -> exit at the target,
  unless the day's OPEN already gapped above it, in which case exit at
  the OPEN.
- if NEITHER is hit by the close of the **10th trading day after
  entry** (entry day itself is day 0, not counted among the 10 -- so
  the maximum possible span is entry day plus 10 further trading days,
  11 trading days total), exit at that 10th day's own close.

Daily OHLC for the subsequent-day scan is fetched directly from
`prices_eod` (RAW scale, the SAME scale the entry day's own 1-minute
bars are in -- a 10-trading-day window is short enough that a
mid-window split/bonus is both rare and, if it occurred, would already
be reflected correctly in that specific day's own RAW print, exactly
the same convention every other RAW-scale price in this study already
relies on). A new, V5-local query (`_fetch_daily_ohlc_with_open`) is
used rather than extending `box_theory.universe_data.fetch_bhav_daily`
(which returns `[high, low, close]` only, no `open`) -- a new function,
not a modification to shared infrastructure other closed studies
depend on, per this project's own established convention.

**"Trading day" here means this specific entity's own next observed row
in `prices_eod`** (not a market-wide calendar stepper) -- if the entity
didn't trade on some day the market was open, there is no price to
check against, so that day is correctly absent from its own sequence,
not treated as a skipped decision point.

## COSTS -- DELIVERY, not intraday; this cuts against the hypothesis, stated plainly

Positions are now held overnight: **DELIVERY costs apply** (`src/swing/
costs.py`, this project's own already-built delivery cost model --
not reimplemented). STT is 0.1% on BOTH the buy and sell side (vs.
0.025% sell-side-only intraday), plus a DP charge (~Rs 23.60 per sell)
that does not exist intraday at all. **Delivery costs are substantially
higher than intraday** -- stated here because it means the longer hold
has to overcome MORE friction than V1-V4's own intraday cost model
charged, not less, directly cutting against the hypothesis this study
tests.

`swing.costs.round_trip_cost_rs(position_size_rs, "DELIVERY")` returns a
**range** (`lo`, `hi` -- spread/impact is the least-certain input in
that model, stated in its own docstring), unlike `box_theory.costs.
round_trip_cost_rs`'s single banded number V1-V4 used. **Decision,
stated explicitly**: the gate's own `net_return_pct` uses the
**midpoint** of that range (`(lo + hi) / 2`) as the single best estimate
-- not the pessimistic bound (which would stack the deck against the
hypothesis) and not the optimistic one (which would understate real
friction). Both `net_return_pct_lo_cost` and `net_return_pct_hi_cost`
are reported alongside the midpoint-based headline for every trade, so
the gate's own sensitivity to this choice is visible, not hidden behind
one number.

## SHORT SELLING -- NOT INCLUDED, a hard constraint, not a design choice

The user asked for a symmetrical short version. **It is not possible
here**: SEBI permits retail short selling in cash equities on an
INTRADAY basis only. A 10-day short requires futures or options -- a
different instrument, with different costs, different margin
requirements, and a universe restricted to F&O-eligible names (a small
subset of this study's own top-decile-momentum-adjacent universe).
**V5 is LONG ONLY.** A short study is not a variant of this one; it
would need its own pre-registration, on the F&O universe, with its own
cost and margin model -- not attempted here.

## CAPITAL -- fixed, unchanged; concurrency is now a real constraint, reported prominently

`qty = max(1, floor(25000 / entry_price))`, unchanged from V2/V3/V4.
**Positions now overlap heavily**: a hold of up to 11 trading days means
many entities can be concurrently open at once, unlike V1-V4 where every
position closed same-day. **Peak concurrent positions and peak deployed
capital are reported prominently in Section 10, not buried** -- if the
strategy requires more capital than is plausible for the account size
this project's own `CAPITAL_RS = 25,000` per-position figure implies,
that is a finding regardless of what the return turns out to be.

## 0. Scope and reuse boundaries

**New module: `src/poc/v5.py` only.** V1-V4's own files are **never
modified** -- all four studies' closed results stay exactly as reported.
Reused, read-only:

- `poc.v4.find_sweep` / `find_reclaim` -- unchanged, the entry mechanism itself.
- `poc.v4._build_atr_adjusted_lookup_for_entity` / `_build_adjustment_
  factor_lookup_for_entity` -- unchanged, same ATR/scale machinery.
- `poc.v2.compute_lookback_low`, `poc.v2.CAPITAL_RS`, `poc.v2.
  position_size_shares_v2`, `poc.v2.MIN_RISK_PCT`, `poc.resolution.
  MAX_RISK_PCT`, `poc.resolution.ENTRY_WINDOW_START/END`, `poc.
  resolution.fill_bar_after_candle_close`, `poc.resolution.
  _stop_target_event` -- unchanged, same stop guards/fill mechanic/
  entry-day intraday scan.
- `poc.context.build_poc_context` -- unchanged, same universe/lookback/
  trend-filter chain.
- `swing.costs.round_trip_cost_rs` -- unchanged, the project's own
  delivery cost model (Costs section above).
- `box_theory.inference.day_clustered_bootstrap` -- unchanged.
- `fibo.universe`, `fibo.jump_guard` -- unchanged.

**New in `src/poc/v5.py`**: `find_entry_v5` (V4's own guard order, new
target formula); `_fetch_daily_ohlc_with_open` (RAW daily OHLC including
open, V5-local); `fetch_subsequent_daily_bars` (up to 10 trading days
forward for one entity from one date); `resolve_multiday_exit_from_bars`
(pure, the overnight mechanics, operating on already-fetched bars) and
`resolve_multiday_exit` (fetch-then-resolve convenience, used by the
real backtest); this study's own backtest orchestration, with the
DEV-boundary truncation rule (Section 9); TIMING/SELECTION nulls
rebuilt on `resolve_multiday_exit_from_bars` (Section 9) -- the pool-
construction SHAPE is unchanged from `poc.v2`'s own, but each pool entry
additionally caches its own pre-fetched subsequent-day bars (fetched
ONCE per pooled entity-day, not once per seed-draw -- a real performance
requirement, not a style choice: without this, a 1000-seed null would
issue a fresh database query per draw per seed, the same mistake
`OPERATIONS.md`'s own "ETA built from the throttle sleep alone" entry
warns against making again); this study's own sealed-window guard
(`poc.v5`'s own `DEV_START`/`DEV_END`/`TEST_START`/`TEST_END`).

## 5. Entry, stop, target, sizing

```
sweep = find_sweep(candles5, lookback_low, atr_raw)          # poc.v4, unchanged
  -> NO_SWEEP / TOUCH_TOO_SHALLOW / BREAKDOWN_NOT_SWEEP as in V4

reclaim = find_reclaim(candles5, sweep_idx, sweep_low, lookback_low)  # poc.v4, unchanged
  -> NOT_RECLAIMED as in V4

fill_bar = fill_bar_after_candle_close(bars1, reclaim_candle_close_ts)  # unchanged
  -> NO_FILL_BAR / FILL_OUTSIDE_WINDOW as in V4

entry_price = fill_bar.open
stop_price  = final_sweep_low - 0.1 * ATR                     # unchanged from V4

entry_price <= stop_price               -> ENTRY_BELOW_STOP   # unchanged
risk_pct > 0.05                         -> STOP_TOO_WIDE       # unchanged
risk_pct < 0.005                        -> STOP_TOO_TIGHT      # unchanged

target_price = entry_price + 3 * (entry_price - stop_price)   # CHANGED (forced, see above)
target_price <= entry_price             -> NO_ROOM             # structurally unreachable, see above

qty = max(1, floor(25000 / entry_price))                      # unchanged
-> ENTERED
```

## 6. Resolution -- NEW, the overnight mechanics (Section above), replacing V1-V4's single-day `resolve_exit`

```
outcome, bar = _stop_target_event(bars1, fill_ts, stop_price, target_price)  # entry day, 1-minute, unchanged
if outcome in ("STOP", "TARGET"):
    -> exit here, trading_days_held = 1

else:  # neither hit on the entry day
    for day in entity's own next up to 10 trading days (prices_eod order):
        if day > DEV_END:
            -> DEV_BOUNDARY_TRUNCATED: close at the last trading day's own
               close at or before DEV_END; counted SEPARATELY (Section 9)
        if day.low <= stop_price:
            exit_price = day.open if day.open <= stop_price else stop_price
            -> STOP (gap_through = day.open <= stop_price)
        elif day.high >= target_price:
            exit_price = day.open if day.open >= target_price else target_price
            -> TARGET
        # neither -> continue to the next day
    # loop exhausted all 10 days with neither hit:
    -> TIME_LIMIT, exit at the 10th day's own close
```

## 7. KEPT FROM V4, unchanged: universe, guards, trend filter, ATR, cost-model STRUCTURE

Point-in-time top-200-by-turnover-adjacent universe (via `poc.context.
build_poc_context`'s own chain), all lineage/same-ISIN/scale guards, the
50-day MA trend filter on the previous daily close, ATR(14) definition
and raw-scale conversion (`poc.v4`'s own machinery), the 0.5% minimum
and 5% maximum stop-distance guards. The cost-model STRUCTURE (round-trip
Rs cost from a position size) is unchanged; the STRUCTURE's own inputs
(delivery vs. intraday rates) are not -- see Costs section above.

## 8. Costs and net return

```
net_return_pct = (pnl_rs - cost_rs_midpoint) / position_size_rs
net_return_pct_lo_cost = (pnl_rs - cost_rs_lo) / position_size_rs
net_return_pct_hi_cost = (pnl_rs - cost_rs_hi) / position_size_rs
```

`cost_rs_lo`/`cost_rs_hi` from `swing.costs.round_trip_cost_rs
(position_size_rs, "DELIVERY")`; midpoint drives the gate (Section 10).
**NOT comparable to V1 (R). Directly comparable to V2/V3/V4 (percentage
of position value)** -- with the caveat that V2-V4's own cost model was
intraday and V5's is delivery, so the TWO cost components are not
interchangeable even though the reporting unit is the same.

## 9. Windows and the DEV-boundary rule

**DEV**: 2016-10-04 to 2022-12-31. **TEST (sealed)**: 2023-01-01 to
2026-09-18 -- `poc.v5`'s own sealed-window guard, same dates and
mechanism as V1-V4's own seals, its own object and access log.

**A trade opened near the end of DEV may need data past 2022-12-31 to
resolve its own up-to-11-trading-day hold.** Per instruction: closed at
DEV_END's own close instead, and counted SEPARATELY from the three real
outcomes (STOP/TARGET/TIME_LIMIT) -- **excluded from the gate's own
mean/CI/null comparisons** (a policy-forced truncation is not a trade
the strategy's own rule would have produced in live trading, and mixing
it into the real distribution would contaminate the gate with an
artifact of the backtest's own window edge), but its own count and
descriptive stats are reported in full, not hidden. The identical
treatment applies to the rare case where the entity's own archive simply
runs out of subsequent rows before 10 trading days or before DEV_END
(delisting, a long halt) -- flagged as a DISTINCT category
(`INSUFFICIENT_DATA`) from the boundary case, since one is a backtest-
window policy and the other is a real data-availability gap, and
conflating them would hide which is which.

## 10. Nulls -- same structure as V4, rebuilt on the 10-day resolution

Same TIMING/SELECTION structure and same populations as V2-V4. Each
draw's resolution now uses `resolve_multiday_exit_from_bars` (Section 6)
instead of the single-day `resolve_exit`, and V5's own target formula
(`entry + 3 * stop_distance`) instead of V2's PREV_HIGH-anchored one --
consistent with V5's own real entry logic, not a leftover from a prior
trial. Pool construction mirrors `poc.v2.build_timing_pool_v2`/`build_
month_pool_v2`'s own shape, with each pooled entity-day's own
subsequent-10-trading-day daily bars fetched ONCE at pool-build time
(Section 0's own stated performance reasoning) -- never once per draw.
Same 1000-seed (500-seed-fallback) contingency as V1-V4.

**DEV PASSES only if ALL hold** (identical structure to V1-V4):

- mean net return % > 0 with the day-clustered 97.5% bootstrap CI
  excluding zero
- mean net return %'s percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls
- mean net return % remains > 0 after dropping the single best calendar
  year from the DEV sample
- mean net return % > 0 within rank bands 1-100 alone

**Caveat carried forward, now at trial 5**: `day_clustered_bootstrap`'s
CI is Bonferroni-built for 2 configurations; strict 5-way correction
would need alpha 0.05/5 = 0.01 per side (a 99% CI). Not re-parameterized,
same reasoning as V3/V4 (gate structure kept identical to V4, per
instruction; silently changing the statistical machinery would itself
be an undisclosed methodological change). Stated plainly as increasingly
anti-conservative at this trial count, on top of the selection-pressure
and swing-V1-precedent caveats above.

**Anything else = NO EDGE. The study closes; the sealed TEST window is
never read.**

## 11. Report contents

Same structure as V2-V4's own Section 12/13: trades, distinct entry
days, win rate, mean net return % (midpoint cost) with its 97.5% CI,
lo/hi-cost sensitivity, median, MDE, both null percentiles, breakdown by
year/band, the full skip/diagnostic breakdown, realised stop-distance
distribution, total costs.

**New for V5, per instruction, all required**:

- **Holding-period distribution**: counts and % at STOP (entry-day vs.
  overnight), TARGET (entry-day vs. overnight), and the 10-day
  `TIME_LIMIT`; distribution of `trading_days_held`.
- **Gap-through count and its cost**: how many STOP exits were a
  gap-through (day's open already below stop) vs. a clean stop-price
  exit, and the total/mean Rs lost specifically to the gap (actual
  exit price vs. what the stop price alone would have given).
- **Peak concurrent positions and peak deployed capital**, reported
  prominently per instruction, not as a footnote.
- **`DEV_BOUNDARY_TRUNCATED` and `INSUFFICIENT_DATA` counts**, reported
  separately from the gate population, with their own descriptive mean
  return (excluded from the gate itself, per Section 9).
- **Population check against V4**: confirm 3,256 entries (V4's 3,225
  ENTERED + its own 31 `NO_ROOM`, per this document's own stated
  prediction above) -- reported as PASS/FAIL against that specific
  number, with the entry-pipeline funnel shown stage by stage if it
  does not match, not silently reconciled.

**Bad results are reported in the first sentence**, the same standing
instruction every prior study here follows.

## 12. Claude's pre-committed prediction, recorded before any run

**I expect DEV to fail**, with a **mean net return between -1.5% and
+0.5%**. The longer hold gives the move more room, but delivery costs
roughly quadruple the STT alone and overnight gaps will produce losses
beyond the stop. **I give this a meaningfully better chance than V1-V4**
because it addresses the identified failure mode (selection edge smaller
than friction) directly rather than refining entries again -- but the
base rate across this project, and specifically the swing V1 precedent
above, is poor. If DEV passes, that will be recorded as plainly as a
failure would be.

## 13. Process, in this order, stopping where marked

1. Write this document. **Commit it alone**, before any sweep, reclaim,
   or trade is computed. Report the commit hash.
2. Build `src/poc/v5.py`. **Hand-trace 5 real DEV-window trades/skips
   before any aggregate number is computed**, including AT LEAST one
   gap-through-stop exit and one 10-day-`TIME_LIMIT` exit (both required
   by name), the remaining three chosen from whatever other shapes
   (entry-day STOP/TARGET, an overnight clean-stop exit, a
   `DEV_BOUNDARY_TRUNCATED` case if one exists near the window edge) the
   real DEV data actually contains, stated plainly if a shape is not
   found rather than manufactured.
3. Run **DEV only** (real trades, then TIMING and SELECTION nulls),
   checkpointed at each stage, timing and memory measured before the
   long stages. Report per Section 11. **>>> STOP. The user approves
   before the sealed TEST window is read.**
4. Only after that approval: authorize `poc.v5`'s own test seal, read
   TEST once, report per Section 11.

## 14. Discipline

**Trial counter for the POC family = 5 (V1-V5).** All parameters are
**FIXED**: the 3x-risk target, the unchanged stop, the 10-trading-day
limit, delivery costs, and every rule carried unchanged from V4. If DEV
fails, none are retried at other values.

**IF V5 FAILS, THE POC FAMILY CLOSES PERMANENTLY. No V6 under any
argument** -- stated once, without the conditional softening V3's own
Section 15 had (which this document has already shown can be overridden
once; V4's own Section 15 left no such opening, and this document adds
none either).

**No rule in this document changes after any number from DEV or TEST has
been seen. Bad results are reported in the first sentence** of whatever
reports them, never buried after a methods recap.

## Status

**>>> STOPPING HERE, per Process Step 1.** No `src/poc/v5.py` code exists
yet, and no sweep, reclaim, stop, or trade has been computed anywhere in
this study. This document is being committed alone, before any of that
exists, so Step 2's hand-traces and Step 3's DEV run cannot have shaped
anything written above.
