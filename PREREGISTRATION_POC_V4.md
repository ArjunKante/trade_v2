# Pre-registration: POC family V4, liquidity sweep and reclaim

Frozen before any sweep is detected, any trade is simulated, or any
return value exists, per this project's standing discipline
(`PREREGISTRATION.md` and family, including `PREREGISTRATION_POC.md`,
`PREREGISTRATION_POC_V2.md`, `PREREGISTRATION_POC_V3.md`). Nothing below
changes after this document is committed except by an explicit, recorded
amendment, made before the next result that amendment could have been
shaped by.

## Provenance -- stated plainly and prominently, as instructed

**POC family trial count becomes 4.**

**`PREREGISTRATION_POC_V3.md` Section 15 stated: "if DEV fails, the POC
family closes. No V4 will be proposed." V3 failed
(`POC_V3_FINDINGS.md`: mean net return -0.3176%, gate's first condition
failed). That rule is being EXPLICITLY OVERRIDDEN by the user here, not
forgotten, not quietly reinterpreted. V3's own document is not edited --
it stays exactly as committed, closed, on the record, saying what it
said. This document is what overrides it, and this paragraph is the
override.**

| Trial | Result | What changed |
|---|---|---|
| V1 | -0.6733 R | original design -- **contaminated by a sizing pathology** (`OPERATIONS.md` standing rule) |
| V2 | -0.4077% | pathology removed (fixed-capital sizing); stop moved to the 5-day lookback low; still loses |
| V3 | -0.3176% | confirmation timeframe moved to hourly; still loses |

**Each revision was chosen after examining losing trades from the
revision before it.** V4 is the FOURTH such revision. It carries severe
selection pressure -- more than V3 carried over V2, which carried more
than V2 carried over V1. **Any DEV pass under V4 is the least informative
result this family has ever produced**, precisely because it is the one
most shaped by having watched three prior failures.

**The project's own precedent, recorded here because it is the single
most relevant piece of evidence for how to weigh anything V4 produces**
(`SWING_FINDINGS.md`): a swing-trading strategy in this project's OTHER
family, "swing V1," scored the **100th percentile, p=0.0010, on 65,219
pre-holdout trades**, clearing BOTH Bonferroni and Benjamini-Hochberg
correction across a pre-specified 6-variant family -- "the strongest
result this project's price-based work has ever produced, formally"
(`SWING_FINDINGS.md`'s own words). On its sealed holdout, under its own
frozen decision rule: **61.4th percentile, p=0.387, on 3,620 holdout
trades -- indistinguishable from random selection from the same pool on
the same days.** A result that cleared the two standard corrections for
multiple testing, on a sample two orders of magnitude larger than is
typical in this project, still did not survive its own holdout. **This
is the standing the bar V4 would have to clear is measured against, not
a pass/fail threshold that guarantees anything once crossed.**

## Parameter provenance -- stated plainly, as instructed

The sweep-depth bounds (0.1x-1.0x ATR), the reclaim window (3 candles),
and the stop buffer (0.1x ATR) below were chosen by Claude, on
construction principles -- volatility scaling (ATR-relative, not a fixed
rupee or percentage, so the rule adapts across stocks of different
volatility the way a fixed 0.5%-below-POC rule never could), bounded
ranges (a floor to exclude noise, a ceiling to exclude breakdowns), and a
stop placed below the swept extreme rather than ON it (the explicit
reasoning: a stop at exactly the swept low is itself sitting in the next
cluster of stops, the same failure mode a liquidity-sweep hypothesis is
built to exploit in OTHER traders, not reproduce in this one). **NOT from
any evidence that these specific values work. No literature, backtest, or
prior result in this project supports 0.1x, 1.0x, 3 candles, or 0.1x
specifically. They are one defensible specification among many that could
have been written from the same hypothesis**, stated here before any
number exists so this is never mistaken, after the fact, for a value that
was tuned.

The ATR(14) calculation itself is NOT a new specification -- it reuses
`fibo.indicators.atr` (Wilder SMMA smoothing, period 14) unchanged, the
same function `fibo_live`'s own 2x-ATR swing filter already uses in
production. Only the THRESHOLDS applied to that existing indicator (0.1x,
1.0x, 0.1x) are new and evidence-free.

## Hypothesis

Stops cluster below an obvious support level (here, the 5-day lookback
low V2's own POC window already defines). Price sweeps through that
level to take the liquidity sitting there, then reverses. Entering on the
RECLAIM of that level -- not on the sweep itself -- captures the reversal
rather than becoming the liquidity that got taken.

## V4 IS V2 WITH THE ENTRY CONDITION REPLACED. Everything else identical.

**What is DROPPED from V2**: the POC touch condition and the
green-or-hammer confirmation. **The POC itself is no longer part of the
entry logic.** It survives only as the 5-day window that defines
LOOKBACK_LOW (the level price must sweep and reclaim) and PREV_HIGH (the
level target is still measured from). **Stated plainly: V4 is a
liquidity-sweep-and-reclaim strategy, not a POC bounce strategy, and is
kept in the POC family only because its selection pressure derives from
POC's own repeated failures, not because its entry logic has anything to
do with a point of control anymore.**

## 0. Scope and reuse boundaries

**New module: `src/poc/v4.py` only.** V1's files (`src/poc/context.py`,
`poc.py`, `trend.py`, `resolution.py`, `backtest.py`, `nulls.py`,
`test_seal.py`), V2's file (`src/poc/v2.py`), and V3's file (`src/poc/
v3.py`) are **never modified** -- all three studies' closed results stay
exactly as reported. Everything V4 needs is imported and reused,
read-only:

- `poc.context.build_poc_context` -- unchanged. Universe, the six-day
  lookback-eligibility chain, PROXY POC/PREV_HIGH (PREV_HIGH still
  needed for TARGET; POC_PRICE itself is computed but never used for
  entry), and the 50-day trend filter are ALL identical to V1/V2/V3.
- `poc.v2.compute_lookback_low` -- unchanged. LOOKBACK_LOW is computed
  the identical way as V2/V3 (the 5-day window's own MIN(low)); the
  level V4 sweeps and reclaims is V2's own stop level, not a new value.
- `poc.v2.position_size_shares_v2`, `poc.v2.CAPITAL_RS`, `poc.v2.
  MIN_RISK_PCT`, `poc.resolution.MAX_RISK_PCT`, `poc.resolution.
  TARGET_BELOW_PREV_HIGH_PCT`, `poc.resolution.ENTRY_WINDOW_START/END`,
  `poc.resolution.fill_bar_after_candle_close`, `poc.resolution.
  resolve_exit` -- unchanged. Sizing, both risk guards, target, the
  entry window, the fill mechanic, and 1-minute-bar stop/target/
  time-exit resolution are ALL identical to V2.
- `poc.v2.build_timing_pool_v2` / `timing_null_seed_mean_v2` / `poc.v2.
  build_month_pool_v2` / `selection_null_seed_mean_v2` -- unchanged,
  reused DIRECTLY, same reasoning as V3's own reuse (Section 0 of
  `PREREGISTRATION_POC_V3.md`): both nulls test entry TIMING and
  SELECTION pressure using the real trade's own stop distance/target, or
  a drawn day's own `lookback_low`/`prev_high` -- neither depends on HOW
  the real entry was found, only on the resulting stop/target/entry
  values, which V4 produces in the same shape V2 does.
- `box_theory.costs.round_trip_cost_rs` / `box_theory.inference.
  day_clustered_bootstrap` -- unchanged, identical cost model and
  inference machinery.
- `fibo.universe`, `fibo.jump_guard` -- unchanged.
- `fibo.indicators.atr` -- unchanged, the EXISTING project ATR
  indicator (see Parameter Provenance above), not reimplemented.
- `fibo.price_scale.get_adjustment_factor` / `to_raw_scale` -- unchanged.
  **Required, not optional**: `fibo.indicators.atr` operates on `fibo.
  daily_ohlc`'s ENTITY-ADJUSTED daily panel, while LOOKBACK_LOW and the
  5-minute sweep candles are in trade-date T's own RAW archive scale (the
  same scale every other POC-family price has always been in). Comparing
  an adjusted-scale ATR against raw-scale sweep depths directly would be
  silently wrong by exactly whatever split/bonus ratio occurred between T
  and the present -- `fibo.price_scale`'s own docstring names "ATR
  distance" explicitly as one of the things it exists to convert. V4
  converts ATR to T's own raw scale via `to_raw_scale(atr_adjusted,
  factor)` with `factor = get_adjustment_factor(con, entity_id, T)`,
  looked up once per entity from the full `adjustment_factors` table
  (cached per-entity, same shape as the trend-filter/ATR lookups below --
  not one DB round trip per day).

**New in `src/poc/v4.py`**: the ATR lookup (per-entity, mirroring `poc.
backtest._build_trend_lookup_for_entity`'s own caching shape, built from
`fibo.daily_ohlc.build_daily_ohlc_panel` + `fibo.indicators.atr`, then
converted to each trade-date's own raw scale); the adjustment-factor
lookup described above; `find_sweep` and `find_reclaim` (replacing `find_
touch_idx`/`find_confirmation` -- genuinely new logic, Section 4 below);
`find_entry_v4` (orchestrates sweep -> reclaim -> fill -> stop/target/
sizing, in the shape of `poc.v2.find_entry_v2` but with the new entry
condition); this study's own backtest orchestration; this study's own
sealed-window guard (`poc.v4`'s own `DEV_START`/`DEV_END`/`TEST_START`/
`TEST_END`, same dates as V1/V2/V3, its own object and access log).

## 1-3. Universe, data, lookback chain -- UNCHANGED from V1/V2/V3

Identical to `PREREGISTRATION_POC.md` Sections 1-3 in full: point-in-time
top-200-by-turnover universe with annual reconstitution, 1-minute archive
via `fibo.scale_probe`, the six-day Section-3 lookback-eligibility chain,
all lineage/same-ISIN/scale guards. Not restated here; reused verbatim.

## 4. SWEEP and RECLAIM -- NEW, replaces V1/V2/V3's touch/confirmation entirely

All prices below are RAW scale for trade-date T (candles5 = the 5-minute
candles V1/V2/V3's own `today_candles5` already provides). `LOOKBACK_LOW`
is V2's own value (Section 0 above). `ATR` is T's own raw-scale ATR(14)
"through the previous trading day" -- looked up at `dates["L5"]` (the
trading day immediately before T, `poc.context.lookback_dates`'s own
label, the SAME day the 50-day trend filter is itself evaluated at),
converted from `fibo.daily_ohlc`'s adjusted scale to T's raw scale as
described in Section 0.

**SWEEP** -- scan `candles5` in session order, starting from the first
candle at or after 09:45:

```
saw_shallow_touch = False
for candle in candles5[time >= 09:45]:
    if candle.low >= LOOKBACK_LOW:
        continue                                   # no breach yet
    depth = LOOKBACK_LOW - candle.low
    if depth > 1.0 * ATR:
        -> BREAKDOWN_NOT_SWEEP, abandon the day     # too deep, stop scanning
    elif depth >= 0.1 * ATR:
        -> SWEEP found at this candle                # 0.1x <= depth <= 1.0x ATR
        sweep_idx = this candle's index
        sweep_low = candle.low
        break                                        # proceed to RECLAIM
    else:
        saw_shallow_touch = True                     # depth < 0.1x ATR
        continue                                      # "keep watching", per instruction
# scan ends with neither SWEEP nor BREAKDOWN:
if saw_shallow_touch:
    -> TOUCH_TOO_SHALLOW
else:
    -> NO_SWEEP                                       # price never breached LOOKBACK_LOW at all
```

**`NO_SWEEP` and `ATR_UNAVAILABLE` (below) are additions beyond the three
skip reasons instruction named (`TOUCH_TOO_SHALLOW`, `BREAKDOWN_NOT_
SWEEP`, `NOT_RECLAIMED`), stated here as a necessary, obvious extension,
not a silent invention**: a day where price never once dips below
LOOKBACK_LOW is a distinct, more basic outcome than one that dips but
only shallowly, exactly as `NO_TOUCH` was always distinct from `POC_
FAILED`/`NO_CONFIRMATION` in V1-V3's own taxonomy. `ATR_UNAVAILABLE`
(an entity's first ~14 trading days after listing, before ATR(14) has
enough history) is checked before the sweep scan can run at all, since
the 0.1x/1.0x thresholds are undefined without it.

**RECLAIM** -- within the next 3 five-minute candles after the sweep
candle (offsets 1, 2, 3):

```
for offset in (1, 2, 3):
    idx = sweep_idx + offset
    if idx >= len(candles5):
        break                                         # ran out of day
    candle = candles5[idx]
    if candle.low < sweep_low:
        sweep_low = candle.low      # update, per instruction: "do not reset" the clock
    if candle.close > LOOKBACK_LOW:
        -> RECLAIMED at this candle (reclaim_idx = idx)
        break
else:
    -> NOT_RECLAIMED
```

**Filled decision, stated as instructed**: when price makes a new low
below the running `sweep_low` during the reclaim wait, `sweep_low` is
updated (it feeds STOP below) but the 3-candle countdown is NOT reset --
it continues counting from the ORIGINAL sweep candle, not from the new
low. A day that sweeps, dips further on candidate 2, then reclaims on
candidate 3 is RECLAIMED at offset 3 (not given 3 fresh candles from the
new low). The 1.0x ATR breakdown ceiling is NOT re-applied during the
reclaim wait -- it is a SWEEP-detection rule only, per the instruction's
own placement of it in the SWEEP section; a deeper low during reclaim
updates `sweep_low` unconditionally, with no abandon-the-day case.

## 5. Entry, stop, target, sizing

```
reclaim_close_ts = candles5[reclaim_idx].ts + 5min    # the reclaiming candle's own close
fill_bar = fill_bar_after_candle_close(bars1, reclaim_close_ts)   # poc.resolution, unchanged
  -> NO_FILL_BAR if none

fill_time not in [09:45, 14:30] -> FILL_OUTSIDE_WINDOW

entry_price = fill_bar.open
stop_price  = sweep_low - 0.1 * ATR                    # the FINAL (possibly-updated) sweep_low

entry_price <= stop_price                    -> ENTRY_BELOW_STOP
(entry_price-stop_price)/entry_price > 0.05  -> STOP_TOO_WIDE
(entry_price-stop_price)/entry_price < 0.005 -> STOP_TOO_TIGHT

target_price = PREV_HIGH * (1 - 0.02)                   # unchanged from V1/V2/V3
target_price <= entry_price                  -> NO_ROOM

qty = max(1, floor(25000 / entry_price))                # poc.v2 sizing, unchanged
-> ENTERED
```

Every rule from `stop_price = sweep_low - 0.1*ATR` onward is in the exact
order, and uses the exact same guard values and sizing formula, as `poc.
v2.find_entry_v2`'s own Section 7 -- the only thing that changed anywhere
in this function is WHERE the sweep/reclaim/stop machinery comes from
(Section 4 above replaces touch/confirmation entirely; the stop FORMULA
itself, `sweep_low - 0.1*ATR`, is new, but the guards applied to its
resulting distance are not).

**One trade per stock per day, long only** -- unchanged from every prior
POC-family study; stated explicitly per instruction, not a new rule.

## 6. Resolution -- UNCHANGED

Identical to V1/V2/V3: `poc.resolution.resolve_exit`, 1-minute-bar scan
(STOP wins a same-bar tie), 15:15 time exit resolved on the 5-minute
candle grid.

## 7. Costs and net return -- UNCHANGED from V2/V3

Identical cost model and reporting unit (percentage of position value,
not R):

```
net_return_pct = (pnl_rs - cost_rs) / position_size_rs
```

**Results reported under V4 are NOT comparable to V1 (R-based) and ARE
directly comparable to V2 and V3** (both percentage-of-Rs-25,000-position
returns).

## 8. KEPT FROM V2, UNCHANGED -- restated per instruction

Point-in-time top-200 universe with annual reconstitution; all lineage,
same-ISIN, and scale guards; the 50-day MA trend filter on the previous
daily close; fixed-capital sizing (`qty = floor(25000/entry)`, minimum 1
share); minimum stop distance 0.5% of entry and maximum 5%, with skips
counted; target 2% below PREV_HIGH with `NO_ROOM` skips counted; the
15:15 time exit; stop and target resolved on 1-minute bars with STOP
winning same-bar ties; the same cost model; returns reported as a
percentage of the Rs 25,000 position.

## 9. Nulls -- IDENTICAL STRUCTURE to V2, reused unchanged

Per instruction and the reasoning in Section 0 above: `poc.v2.
build_timing_pool_v2`/`timing_null_seed_mean_v2` and `poc.v2.build_
month_pool_v2`/`selection_null_seed_mean_v2` are called DIRECTLY with
V4's own trades/universe/jump-dates as input. Same 1000-seed
(500-seed-fallback) contingency as V1/V2/V3.

## 10. Inference and gate -- same structure as V2/V3; the Bonferroni caveat is now WORSE, stated again

Day-clustered bootstrap (`box_theory.inference.day_clustered_bootstrap`,
unchanged module, `net_r_col="net_return_pct"`, 10,000 resamples, 97.5%
two-sided CI), identical mechanics to V2/V3.

**Caveat, carried forward from `PREREGISTRATION_POC_V3.md` Section 11 and
now more acute**: that module's CI is Bonferroni-built for 2
pre-registered configurations. The POC family is now at **4** trials. A
strict 4-way correction would use alpha 0.05/4 = 0.0125 per side (a
98.75% CI) -- tighter than V3's own already-unaddressed 3-trial gap. This
document does not re-parameterize `day_clustered_bootstrap`, for the same
reason V3 did not: the user's instruction is for gate structure identical
to V2, and silently changing the statistical machinery would itself be an
undisclosed methodological change. **Using the unchanged 97.5% level at
trial count 4 is more anti-conservative than it was at trial count 3**,
which was already anti-conservative relative to strict correction --
stated here plainly, on top of (not instead of) the selection-pressure
and swing-V1-precedent caveats above.

**DEV PASSES only if ALL hold** (identical structure to V1/V2/V3):

- mean net return % > 0 with the day-clustered 97.5% bootstrap CI
  excluding zero
- mean net return %'s percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls
- mean net return % remains > 0 after dropping the single best calendar
  year from the DEV sample
- mean net return % > 0 within rank bands 1-100 alone

**Anything else = NO EDGE. The study closes; the sealed TEST window is
never read.**

## 11. Windows -- identical to V1/V2/V3

**DEV**: 2016-10-04 to 2022-12-31. **TEST (sealed)**: 2023-01-01 to
2026-09-18 -- `poc.v4`'s own sealed-window guard, same mechanism and
dates as the three prior seals, its own object and access log, not
shared with any of them. Not read unless DEV passes AND the user
explicitly approves.

## 12. Report contents

Same structure as `PREREGISTRATION_POC_V2.md`/`_V3.md` Section 13 in
full: trades, distinct entry days, win rate, mean net return % with its
97.5% CI, median net return %, MDE, both null percentiles (seed counts,
SELECTION's matched count per month), breakdown by calendar year
(ex-best-year mean), breakdown by rank band, exit mix, peak concurrent
positions/deployed capital, the full skip/diagnostic breakdown, realised
stop-distance distribution, total costs (rupees and % of position), and
the standing "percentage-of-capital, not R" reminder every time a
headline number appears.

**New for V4, per instruction, all required**:

- **The sweep-depth distribution as a multiple of ATR** (`(LOOKBACK_LOW -
  sweep_low_at_detection) / ATR`, at the moment SWEEP is first detected):
  min, median, max.
- **Days lost to `TOUCH_TOO_SHALLOW`, `BREAKDOWN_NOT_SWEEP`, and `NOT_
  RECLAIMED`**, plus the full remaining skip breakdown (`NO_SWEEP`, `ATR_
  UNAVAILABLE`, and every V2 skip reason carried forward).
- **How often price made a new low below `SWEEP_LOW` during the reclaim
  wait** -- a count and a fraction of all days that reached RECLAIM.
- **The `(entry_price - LOOKBACK_LOW) / entry_price` distribution** -- the
  direct test of whether entries now sit ABOVE the swept level, as the
  hypothesis requires, replacing V1-V3's own `entry_above_poc_frac` (POC
  is no longer the reference level; LOOKBACK_LOW is).
- **Trade count against V2's 22,959.**

**Bad results are reported in the first sentence**, the same standing
instruction every prior study here follows.

## 13. Claude's pre-committed prediction, recorded before any run

**I expect DEV to fail**, with a mean net return between **-0.5% and
+0.1%**, most likely slightly negative, and a **trade count well below
V2's 22,959**, because three filters now stack (sweep depth in a bounded
ATR range, reclaim within 3 candles, the same stop/target guards V2
already loses a substantial share of setups to). **If DEV passes, I was
wrong, and that will be recorded as plainly as a failure would be** --
not reframed, not explained away after the fact.

## 14. Process, in this order, stopping where marked

1. Write this document. **Commit it alone**, before any sweep, reclaim,
   or trade is computed. Report the commit hash.
2. Build `src/poc/v4.py`. **Hand-trace 5 real DEV-window trades/skips
   before any aggregate number is computed**: at minimum, one `TOUCH_
   TOO_SHALLOW`, one `BREAKDOWN_NOT_SWEEP`, and one `NOT_RECLAIMED` skip
   (all three required by name), plus two more chosen from whatever
   other shapes (a real ENTERED trade, `STOP_TOO_WIDE`, a new-low-during-
   reclaim case) the real DEV data actually contains, stated plainly if
   a shape is not found rather than manufactured.
3. Run **DEV only** (real trades, then TIMING and SELECTION nulls),
   checkpointed at each stage, timing and memory measured before the
   long stages. Report per Section 12. **>>> STOP. The user approves
   before the sealed TEST window is read.**
4. Only after that approval: authorize `poc.v4`'s own test seal, read
   TEST once, report per Section 12.

## 15. Discipline

**Trial counter for the POC family = 4 (V1, V2, V3, V4).** All
parameters below are **FIXED**: the sweep-depth bounds (0.1x/1.0x ATR),
the reclaim window (3 candles), the stop buffer (0.1x ATR), and every
rule carried unchanged from V2 (sizing, both risk guards, target, time
exit, cost model, universe, lineage guards, trend filter). **If DEV
fails, none are retried at other values, and no variant is folded into
this document after the fact; any such variant is a NEW trial requiring
its own pre-registration.**

**THIS IS THE LAST TRIAL IN THIS FAMILY.** If V4 fails, the POC family
closes permanently. Unlike V3's own closure statement (which this
document has just overridden once), no further override is anticipated
or invited: **a V5 would require a new pre-registration explicitly
arguing why a fifth revision of a four-times-failed idea is worth
running, and that argument would have to address the swing V1 precedent
(Provenance, above) directly** -- a result that cleared Bonferroni and
Benjamini-Hochberg correction on 65,219 trades still failed its holdout,
and that is the standard a family at trial count 5 would be asking to be
trusted past.

**No rule in this document changes after any number from DEV or TEST has
been seen. Bad results are reported in the first sentence** of whatever
reports them, never buried after a methods recap.

## Status

**>>> STOPPING HERE, per Process Step 1.** No `src/poc/v4.py` code exists
yet, and no sweep, reclaim, stop, or trade has been computed anywhere in
this study. This document is being committed alone, before any of that
exists, so Step 2's hand-traces and Step 3's DEV run cannot have shaped
anything written above.
