# Pre-registration: POC bounce V2, fixed-capital sizing

Frozen before any touch is counted, any trade is simulated, or any return
value exists, per this project's standing discipline (`PREREGISTRATION.md`
and family, including `PREREGISTRATION_POC.md`, V2's own direct parent).
Nothing below changes after this document is committed except by an
explicit, recorded amendment, made before the next result that amendment
could have been shaped by.

## Provenance -- stated plainly, as instructed

**V1 closed at DEV with NO EDGE** (`POC_FINDINGS.md`): mean net R
**-0.6733**, 97.5% CI excluding zero on the negative side, sealed TEST
window never read. Investigating the worst trades found a sizing
pathology: V1's stop (0.5% below POC_PRICE) could land a fraction of a
paisa from entry, and the fixed-Rs-500-risk sizing formula (`qty =
floor(500 / per_share_risk)`) then had no ceiling -- one trade sized a
**Rs 434 million** position against a nominal Rs 500 risk unit. This was
recorded as a project-wide standing rule in `OPERATIONS.md` ("a stop
pinned to a price level other than entry MUST have a minimum
stop-distance floor").

**V2 is a REVISION proposed by the user AFTER seeing V1's failure and
its specific failure mode.** It is not a blind second attempt -- the
person designing V2 had already seen which exact mechanism broke V1, and
V2's two changes respond directly to that. **This carries selection
pressure, and V2's own DEV pass (if it occurs) is development evidence
only, never a validity claim** -- the same standing every non-IPO study's
DEV pass already carries in this project, stated here with extra
emphasis because the pressure here is sharper than usual (a specific,
diagnosed failure being patched, not a fresh hypothesis). **POC family
trial count becomes 2** (V1, now V2). No further within-family retries
are permitted if V2 also fails -- per `PREREGISTRATION_POC.md`'s own
Section 15 discipline, carried forward: parameters below are FIXED, not
retried at other values.

## TWO CHANGES FROM V1, nothing else

### Change 1: FIXED-CAPITAL SIZING -- a METHODOLOGICAL FIX, not a tuned parameter

`qty = floor(25000 / entry_price)`, **minimum 1 share** (unlike V1, which
had no floor-at-1 override). Position value is therefore always
approximately Rs 25,000 regardless of stop distance. **This structurally
removes V1's own pathology by construction**: `qty` no longer depends on
`(entry_price - stop_price)` AT ALL, so a stop landing arbitrarily close
to entry can no longer produce an arbitrarily large position -- the
mechanism that broke V1 cannot recur under this formula, not because a
guard was added to catch it after the fact, but because the input that
drove it (stop distance) is no longer part of the sizing calculation.
Recorded as a methodological fix (fixing a broken sizing CONVENTION)
rather than a tuned parameter (no value here was chosen by fitting
anything -- Rs 25,000 is a stated, round, never-optimized capital
figure, in the same spirit as every other filled-gap constant in this
project's studies).

### Change 2: STOP moves to the 5-trading-day lookback LOW -- a TUNED parameter, changed after seeing V1 fail

STOP = the lowest price across the SAME 5 trading days the POC was
computed from (Section 4's own lookback window) -- the bottom of the
volume profile's own range, pairing with PREV_HIGH (already V1's own
definition: the highest price across that same window) as its top.
Recorded explicitly as a **TUNED parameter**: unlike Change 1 (a
structural fix with no free value), this specific choice of WHERE the
stop goes was selected by the user after seeing V1's own failure --
honest bookkeeping, since this is exactly the kind of choice selection
pressure can quietly distort.

**Guards on this new stop, both frozen**:
- **Maximum stop distance 5% of entry** (identical ceiling to V1's own
  `STOP_TOO_WIDE`, Section 7): skip, counted **`STOP_TOO_WIDE`**, if
  `(entry_price - STOP) / entry_price > 0.05`.
- **Minimum stop distance 0.5% of entry** -- **the exact standing rule
  `OPERATIONS.md` now requires** for any stop pinned to a price level
  other than entry itself: skip, counted **`STOP_TOO_TIGHT`**, if
  `(entry_price - STOP) / entry_price < 0.005`. Named differently from
  V1's `ENTRY_BELOW_STOP` (Section 7 below keeps that check too, for the
  same reason V1 needed it: GREEN/HAMMER confirmation still does not
  require trading near any particular level, so `entry_price <= STOP`
  remains a distinct, prior, more extreme case that this 0.5% floor
  alone would not catch if checked second) -- see Section 7 for the
  exact order both checks run in.

**Expectation, stated before any number exists**: a 5-trading-day LOW is
often well below where an intraday touch-and-confirm entry actually
fills, since the lookback window's own low may have occurred on any of
the 5 days, not necessarily near the current price action. **The
`STOP_TOO_WIDE` skip is expected to reject a large share of setups** --
this is reported prominently (Section 13), and if it consumes most of
the candidate setups, the resulting sample may be too small to resolve
anything, stated here as a real risk to this study's own power, not
discovered after the fact.

## 0. Scope and reuse boundaries

**New module: `src/poc/v2.py` only.** V1's own files (`src/poc/context.py`,
`poc.py`, `trend.py`, `resolution.py`, `backtest.py`, `nulls.py`,
`test_seal.py`) are **never modified** -- V1's closed result stays
exactly as reported in `POC_FINDINGS.md`. Everything V2 needs from V1 is
imported and reused, read-only:

- `poc.context.build_poc_context` -- unchanged, Section 3's six-day
  lookback-eligibility chain, POC/PREV_HIGH computation, and the 50-day
  trend filter are ALL identical between V1 and V2 (Change 2 only
  changes where the STOP comes from, not how POC/PREV_HIGH/the trend
  filter are computed) -- called exactly as V1's own backtest does,
  including its `eligible_ctx_cache` performance optimization.
- `poc.context.lookback_dates` / `poc.context._cached_eligible_day_context`
  -- reused directly so V2 can derive the 5-trading-day LOW (Section 4)
  from the SAME lookback days `build_poc_context` already resolved and
  cached, at zero extra `eligible_day_context` cost (a cache hit, not a
  second fetch) -- see Section 4 for why V1's own `build_poc_context`
  cannot be asked for this value directly without modifying it (it
  computes POC/PREV_HIGH from the lookback bars and discards them; V2
  needs one more number from the same bars, so it asks the SAME
  cached per-day contexts again, never a new eligibility computation).
- `poc.resolution.find_touch_idx` / `candle_shape` / `is_hammer` /
  `classify_confirmation_candle` / `find_confirmation` /
  `fill_bar_after_candle_close` / `resolve_exit` -- unchanged. The touch
  rule, the GREEN/HAMMER confirmation (including the doji-hammer
  amendment), the fill mechanic, and the mechanical stop/target/
  time-exit resolution are ALL identical to V1 (`resolve_exit` itself
  takes `stop_price`/`target_price` as plain arguments and has no
  R-specific logic inside it at all -- directly reusable with V2's own
  differently-computed stop, no wrapper needed).
- `poc.resolution.position_size_shares` -- **NOT reused**: V1's formula
  divides fixed risk by per-share risk; V2's sizing (Section 7) does not
  depend on stop distance at all. New code.
- `box_theory.costs.band_for_rank` / `round_trip_cost_rs` -- unchanged,
  identical cost model to V1 (Section 9).
- `box_theory.inference.day_clustered_bootstrap` / `excludes_zero` /
  `percentile_vs_null` -- unchanged, column-name-agnostic (`net_r_col`
  is a parameter), reused with a `net_return_pct` column instead of
  `net_r` (Section 11) -- no change to the module itself.
- `fibo.universe`, `fibo.jump_guard`, `fibo.daily_ohlc` -- unchanged,
  identical universe/jump-guard/trend-filter-source reuse to V1.

**New in `src/poc/v2.py`, because nothing in V1 computes a lookback LOW,
fixed-capital sizing, or percentage-return net results**: the
lookback-LOW helper (Section 4); entry/stop/sizing orchestration
(Section 7, reusing V1's touch/confirm/fill/resolve_exit as named
above); this study's own backtest orchestration (entity/year streaming,
identical in SHAPE to `poc.backtest.evaluate_entity`/`run_backtest` but
producing percentage-return trade records, not R); TIMING/SELECTION
nulls adapted to fixed-capital sizing and percentage returns (Section
10); and this study's own sealed-window guard, `poc.v2`'s own
`DEV_START`/`DEV_END`/`TEST_START`/`TEST_END` constants (identical dates
to V1's `poc.test_seal`, but its own object, own access log, sharing no
state with V1's seal, per this project's standing one-seal-per-study
convention).

## 1-6. Universe, data, lookback chain, trend filter, touch/confirmation -- UNCHANGED from V1

Identical to `PREREGISTRATION_POC.md` Sections 1-6 in full: point-in-time
top-200-by-turnover universe, 1-minute archive via `fibo.scale_probe`,
the six-day Section-3 lookback-eligibility chain, the PROXY POC
construction (0.25% bucket width off today's own 09:15 open, tie-break
to the lower bucket), the 50-day daily SMA trend filter, and the
touch/GREEN/HAMMER-confirmation mechanic including the doji-hammer
amendment. Not restated in full here; reused verbatim via the functions
named in Section 0.

## 4a. Lookback LOW -- NEW, pairs with V1's own PREV_HIGH definition

`LOOKBACK_LOW` = `MIN(low)` across every 1-minute bar in `L1..L5`
combined, RAW scale -- the exact mirror of V1's own `PREV_HIGH =
MAX(high)` across the same window (`PREREGISTRATION_POC.md` Section 4).
Computed via the SAME five `L1..L5` RAW-scale `day_raw` frames
`poc.context.build_poc_context` already resolved for POC_PRICE/PREV_HIGH
-- re-requested from `poc.context._cached_eligible_day_context`'s own
cache (a hit, since `build_poc_context` already populated it for this
exact `(entity, today)` call), never re-fetched from the archive.

## 7. Entry, stop, target, sizing -- CHANGED (stop, sizing); touch/confirm/fill UNCHANGED

Touch (Section 6, reused `find_touch_idx`), confirmation (reused
`find_confirmation`), and fill (reused `fill_bar_after_candle_close`,
same `NO_FILL_BAR` / `FILL_OUTSIDE_WINDOW` [09:45-14:30] handling) are
byte-identical to V1. From the fill price onward, V2's own rules apply,
checked in this order:

1. **STOP = LOOKBACK_LOW** (Section 4a).
2. **`ENTRY_BELOW_STOP`** (carried forward from V1's own amendment,
   checked FIRST, same reasoning): skip if `entry_price <= STOP`. GREEN/
   HAMMER confirmation still does not require trading near any
   particular level, so entry landing at or below the lookback's own low
   remains possible and is still the most degenerate case, checked
   before either percentage guard.
3. **`STOP_TOO_WIDE`**: skip if `(entry_price - STOP) / entry_price >
   0.05` (V1's own 5% ceiling, unchanged).
4. **`STOP_TOO_TIGHT`**: skip if `(entry_price - STOP) / entry_price <
   0.005` -- the new minimum floor `OPERATIONS.md`'s standing rule
   requires (Change 2's own stated guard).
5. **TARGET** = `PREV_HIGH * (1 - 0.02)` (identical to V1). **`NO_ROOM`**:
   skip if `TARGET <= entry_price`.
6. **SIZING**: `qty = max(1, floor(25000 / entry_price))` (Change 1).
   No `ZERO_QTY` skip is possible under this formula (the minimum-1-share
   floor guarantees `qty >= 1` always) -- stated explicitly so its
   absence from Section 13's skip list is not mistaken for an omission.

## 8. Resolution -- UNCHANGED

Identical to V1 Section 8 in full, reused verbatim via `poc.resolution.
resolve_exit` (1-minute-bar scan from the fill bar, STOP wins a same-bar
tie, 15:15 time exit with the same fallback-to-latest-available-candle
convention).

## 9. Costs and net return -- CHANGED reporting unit, same cost model

**Costs**: `box_theory.costs.round_trip_cost_rs(position_size_rs, band)`,
unchanged -- identical INTRADAY + Section 8c banded cost model to V1,
applied to V2's own `position_size_rs = qty * entry_price` (now ~Rs
25,000, not whatever V1's fixed-risk formula happened to produce).

**Net return, as a PERCENTAGE of the position, not R** -- R no longer
means one thing once sizing is capital-based, not risk-based (stated
plainly, per instruction):

```
net_return_pct = (pnl_rs - cost_rs) / position_size_rs
```

where `pnl_rs = qty * (exit_price - entry_price)`. **Results reported
under this study are NOT directly comparable to V1 or to any other study
in this project** -- every other study here uses fixed-risk (R-based)
sizing; this is the first percentage-of-capital study in this project's
intraday family, stated here so a future reader never lines up a V2
percentage against a V1 R-value as if they were the same unit.

## 10. Nulls -- adapted to fixed-capital sizing and percentage returns

Same TWO-null structure as V1 (TIMING, SELECTION), same reasoning for
each, adapted only where sizing/stop construction requires it.

### TIMING null

Identical population and entry-randomization method to V1 (restricted to
the exact `(entity, T)` pairs the real strategy traded; a random
5-minute entry candle in `[09:45, 14:30]`, same fill mechanic). **Stop
distance**: the SAME rupee amount the real trade used, carried over
unchanged (`STOP_null = entry_null - (entry_real - STOP_real)`) --
identical reasoning to V1's own TIMING null (only entry timing is being
tested; the risk/reward shape stays fixed). **Target**: the SAME
absolute price level the real trade used (`TARGET_null = TARGET_real`,
unchanged from V1's own reasoning -- target is a PREV_HIGH-derived level,
not relative to entry). **Sizing**: V2's own formula, `qty_null =
max(1, floor(25000 / entry_null))`. Same `STOP_TOO_WIDE`/`STOP_TOO_TIGHT`
re-checks applied to the null's own draw (a draw failing either is
retried with a fresh random candle, up to 20 attempts, same convention
as V1's own nulls). 1000 seeds, same timed-probe/500-seed-fallback
contingency as V1.

### SELECTION null

Identical population to V1 (every `(entity, T)` pair passing Section 3's
lookback-eligibility chain for that universe-year, INCLUDING trend-filter
failures and days that never touch the POC, matched count per calendar
month), built one month at a time. Each pooled day now ALSO carries its
own `LOOKBACK_LOW` (Section 4a), computed the identical way a real day's
would be, alongside the `PREV_HIGH` V1's own pool already carries.

**Stop**: **our filled gap, stated plainly, mirroring V1's own precedent
for SELECTION's target** -- V1's SELECTION null drew a stop PERCENTAGE
from the real trades' own empirical distribution, because V1's stop was
itself a free percentage (0.5% below POC) with no natural value for an
arbitrary pooled day. V2's stop is no longer a free percentage -- it is
a deterministic price level (that day's own 5-day low), well-defined for
ANY pooled day regardless of real-trade status, the exact same situation
V1's own SELECTION null was already in for its TARGET (recomputed fresh
from the drawn day's own real PREV_HIGH, never borrowed from another
day). V2's SELECTION null therefore recomputes stop the SAME way:
`STOP_null = LOOKBACK_LOW` of the drawn day itself -- not a sampled
percentage. **Target**: `TARGET_null = PREV_HIGH_drawn_day * (1 - 0.02)`,
identical reasoning to V1. Entry: a random 5-minute candle in `[09:45,
14:30]` on the drawn day, same fill mechanic. Same `STOP_TOO_WIDE`/
`STOP_TOO_TIGHT`/`ENTRY_BELOW_STOP`-equivalent checks, same sizing
formula, same cost model. 1000 seeds (500-seed fallback, same
contingency).

## 11. Inference and gate -- rewritten in percentage terms, same structure as V1

Day-clustered bootstrap (`box_theory.inference.day_clustered_bootstrap`,
unchanged module, `net_r_col="net_return_pct"`, `trade_date = T`, 10,000
resamples, 97.5% two-sided CI -- same reasoning as V1 Section 11 for why
this interval needs no further correction at family trial count 2 run as
ONE configuration: the module's own CI is Bonferroni-built for 2
pre-registered configurations, and this is the SECOND configuration of
the POC family, so the interval is now used at exactly the count it was
built for, neither conservative nor anti-conservative).

**DEV PASSES only if ALL hold**:

- mean net return % > 0 with the day-clustered 97.5% bootstrap CI
  excluding zero
- mean net return %'s percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls
- mean net return % remains > 0 after dropping the single best calendar
  year (by that year's own mean net return %) from the DEV sample
- mean net return % > 0 within rank bands 1-100 alone

**Anything else = NO EDGE. The study closes; the sealed TEST window is
never read.** Identical all-or-nothing standard to V1 and every other
gate in this project.

## 12. Windows -- identical to V1

**DEV**: 2016-10-04 to 2022-12-31. **TEST (sealed)**: 2023-01-01 to
2026-09-18 -- `poc.v2`'s own sealed-window guard, same mechanism and
dates as `poc.test_seal`, its own object and access log, not shared with
V1's seal. Not read unless DEV passes AND the user explicitly approves.

## 13. Report contents

Trades, distinct entry days, win rate, **mean net return % with its
97.5% CI** (not R), median net return % (descriptive), MDE (from the
bootstrap SE alone), both null percentiles (with seed counts and
SELECTION's matched count per month), breakdown by calendar year (and
ex-best-year mean), breakdown by rank band, exit mix (STOP/TARGET/
TIME_EXIT, `time_exit_fallback` count), peak concurrent positions and
peak deployed capital (expected to sit near `qty_in_play * Rs 25,000`,
a sanity check on Section 7's own sizing formula). **Skip/diagnostic
breakdown**: `lookback_incomplete`, `trend_filter_failed`, `no_touch`,
`poc_failed`, `no_confirmation`, `no_fill_bar`, `fill_outside_window`,
`entry_below_stop`, **`stop_too_wide` (reported prominently, per the
stated expectation that this may reject most setups)**, `stop_too_tight`,
`no_room`. The `(entry_price - POC_PRICE)/entry_price` distribution, as
V1 reports.

**New for V2, per instruction**:
- **The realised risk distribution**: `(entry_price - STOP)/entry_price`
  across every real entry, min/median/max -- since STOP is no longer a
  fixed percentage, this distribution is itself a result, not a frozen
  constant the way V1's 0.5% was.
- **Total costs in rupees AND as a percentage of position value**
  (`cost_rs` summed, and `cost_rs / position_size_rs` per trade,
  min/median/max) -- costs no longer net against a fixed Rs 500 risk
  unit, so their own scale needs stating directly.
- **A stated reminder, every time a headline number is shown**: these
  results are percentage-of-capital returns, not R, and are not
  comparable to V1 or to any other study in this project.

**Bad results are reported in the first sentence**, the same standing
instruction every prior study here follows.

## 14. Process, in this order, stopping where marked

1. Write this document. **Commit and push it alone**, before any touch,
   stop, or trade is computed. Report the commit hash.
2. Build `src/poc/v2.py`. **Hand-trace 5 real DEV-window trades/skips
   before any aggregate number is computed**: at minimum, one TARGET
   exit, one STOP exit (showing the 5-day LOOKBACK_LOW the stop came
   from), and one `STOP_TOO_WIDE` skip (expected to be common, per the
   stated expectation above) -- the remaining two chosen from whatever
   other shapes (TIME_EXIT, `STOP_TOO_TIGHT`, `ENTRY_BELOW_STOP`,
   `POC_FAILED`) the real DEV data actually contains, stated plainly if
   a shape is not found rather than manufactured.
3. Run **DEV only** (real trades, then TIMING and SELECTION nulls),
   checkpointed at each stage, timing and memory measured before the
   long stages. Report per Section 13. **>>> STOP. The user approves
   before the sealed TEST window is read.**
4. Only after that approval: authorize `poc.v2`'s own test seal, read
   TEST once, report per Section 13.

## 15. Discipline

**Trial counter for the POC family = 2 (V1, V2).** The 5% maximum and
0.5% minimum stop-distance guards, the Rs 25,000 capital figure, and
every rule carried unchanged from V1 (universe, POC construction, trend
filter, touch/confirmation, target rule, time exit, cost model) are
**FIXED** -- if DEV fails, none are retried at other values, and no
variant is folded into this document after the fact; any such variant is
a NEW trial requiring its own pre-registration. **No rule in this
document changes after any number from DEV or TEST has been seen.**
**Bad results are reported in the first sentence** of whatever reports
them, never buried after a methods recap.

## Status

**>>> STOPPING HERE, per Process Step 1.** No `src/poc/v2.py` code
exists yet, and no touch, stop, or trade has been computed anywhere in
this study. This document is being committed and pushed alone, before
any of that exists, so Step 2's hand-traces and Step 3's DEV run cannot
have shaped anything written above.
