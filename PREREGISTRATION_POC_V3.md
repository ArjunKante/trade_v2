# Pre-registration: POC bounce V3, hourly confirmation

Frozen before any touch is counted, any trade is simulated, or any return
value exists, per this project's standing discipline (`PREREGISTRATION.md`
and family, including `PREREGISTRATION_POC.md` and `PREREGISTRATION_
POC_V2.md`, V3's own direct parent). Nothing below changes after this
document is committed except by an explicit, recorded amendment, made
before the next result that amendment could have been shaped by.

## Provenance -- stated plainly, as instructed

**POC family trial count becomes 3.**

**V1 closed at DEV with NO EDGE** (`POC_FINDINGS.md`): mean net R
**-0.6733**, 97.5% CI excluding zero on the negative side. The loss was
later found to be contaminated by a sizing pathology (a stop pinned
arbitrarily close to entry, combined with fixed-Rs-risk sizing with no
ceiling, produced a Rs 434 million position against a nominal Rs 500 risk
unit on one trade) -- recorded as a project-wide standing rule in
`OPERATIONS.md`.

**V2 closed at DEV with NO EDGE** (`POC_V2_FINDINGS.md`) after that
pathology was structurally removed: fixed-capital sizing (`qty = floor(25000
/ entry)`, min 1 share -- no longer dependent on stop distance at all) and a
new stop (the same 5-day lookback window's own LOW, with a 5% maximum and a
0.5% minimum stop-distance floor). **Mean net return -0.4077% of position
value, 22,959 trades, costs capped at Rs 143.72 per trade** (down from V1's
Rs 239,868 worst case). The gate's first condition failed outright; neither
null finished running.

**V3 is a THIRD revision, proposed by the user after seeing BOTH V1 and V2
fail.** It carries substantial selection pressure -- more than V2 carried
over V1, since the person designing V3 has now watched two consecutive,
specifically-diagnosed failures of this same family and is choosing a third
adjustment in response. **This is development evidence only, never a
validity claim, and the standing emphasis from V2's own provenance section
applies with MORE force here, not less: each successive revision of a
failed family makes a passing result WEAKER evidence, not stronger.** A DEV
pass under V3, if one occurs, is the least informative of the three trials
precisely because it is the one most shaped by having watched the other two
fail. **No further within-family retries are permitted if V3 also
fails** -- per `PREREGISTRATION_POC.md` Section 15 and `PREREGISTRATION_
POC_V2.md` Section 15's own discipline, carried forward and restated with
emphasis in Section 15 below: **if DEV fails, the POC family closes. No V4
will be proposed.**

## ONE CHANGE FROM V2, nothing else

### CONFIRMATION TIMEFRAME moves from 5-minute candles to 1-hour candles

- The **TOUCH** is the first 1-hour candle at or after 09:45 whose LOW is
  at or below the POC -- the identical rule as V1/V2's own touch definition
  (`poc.resolution.find_touch_idx`), just evaluated against hourly candles
  instead of 5-minute ones. The function itself is unchanged; only what is
  passed to it changes.
- The **CONFIRMATION** candle is the 1-hour candle AFTER the touch candle,
  using the IDENTICAL green-or-hammer definition from V1/V2
  (`poc.resolution.classify_confirmation_candle`/`is_hammer`/
  `candle_shape` -- these operate on a single candle's own OHLC and have no
  timeframe-specific logic in them at all; reused byte-for-byte).
- **POC_FAILED** is unchanged in substance: no entry if the confirming
  hourly candle is RED and closes below the POC.
- **Two-candidate patience is unchanged**: up to 2 hourly candles after the
  touch are checked (`poc.resolution.find_confirmation`'s own offset-(1,2)
  loop, reused unchanged), then skip as `NO_CONFIRMATION`.
- **ENTRY** is at the open of the next 1-minute bar after the confirming
  hourly candle closes -- mechanically identical to V1/V2's own fill rule
  (`poc.resolution.fill_bar_after_candle_close`, reused unchanged: the
  1-minute bar whose own `ts` equals the confirming candle's close
  timestamp), with ONE necessary adjustment: a 5-minute candle's close is
  always `ts + 5min`, but an hourly candle's close is **NOT** always `ts +
  60min` -- the session's final bucket each day is a 15-minute partial
  (Hourly Candle Construction, below). V3 therefore passes the confirming
  candle's own actual `bucket_end` value as the close timestamp, never an
  assumed fixed offset.

**User's stated rationale, recorded as instructed**: a 5-minute candle
rarely moves far from the POC before confirming, so V1/V2 entries landed
only a fraction above it. An hourly candle should produce entries further
from the level, since more price action occurs within it before
confirmation is decided. **This is measured directly in Section 13's
reporting, not assumed.**

**Consequence, reported not fixed**: hourly candles consume far more of the
session before an entry can complete. A touch detected within the hour
ending at, say, 10:15 means the confirming candle (the next full hour) does
not close until 11:15, and entry follows shortly after. With the 14:30
entry cutoff unchanged from V1/V2, a touch occurring any time after
roughly midday has a shrinking or zero chance of producing a completed
entry before the window closes. **`FILL_OUTSIDE_WINDOW` is expected to
consume a materially larger share of would-be entries than it did under V2,
and is reported prominently (Section 13), not quietly folded into the
general skip breakdown.**

## HOURLY CANDLE CONSTRUCTION

1-minute bars are aggregated to 1-hour buckets anchored at the 09:15
session open (not midnight), via `fvg.bars.aggregate_to_1hour` -- the exact
same function and convention the research browser's own hourly chart view
uses (`src/viz/data.py::fetch_raw_hourly_bars`), and the same one the FVG
study's own (closed) backtest used. Buckets are `[09:15,10:15)`,
`[10:15,11:15)`, ..., `[14:15,15:15)`, and one **PARTIAL** bucket
`[15:15,15:30)` (15 minutes, not 60) -- the archive's last 1-minute bar is
`ts=15:29`, confirming the session ends at 15:30. Every bucket carries its
own `bucket_end` (the bucket's actual close timestamp: `ts+60min` for every
full bucket, `ts+15min` for the partial one) -- used directly by the ENTRY
rule above, never assumed.

**Can a partial candle serve as a touch or confirmation candle? YES --
stated explicitly, handled consistently, no special case.** The 15:15-15:30
bucket is evaluated by the identical TOUCH and GREEN/HAMMER/POC_FAILED
logic as any full-hour bucket -- the same convention `src/fvg/bars.py`
already documents for its own study ("The partial bucket counts as one
candle, identically to every full-hour candle"). In practice this almost
never produces a completed entry: confirmation at or touching the 15:15
bucket fills no earlier than 15:30, already past the unchanged 14:30 entry
cutoff. The rule is stated and applied uniformly rather than silently
excluding the partial bucket, so its rare effect (e.g. it CAN still serve
as touch candidate 2's confirmation check, contributing to `NO_CONFIRMATION`
or `POC_FAILED` counts even when it can never itself lead to `ENTERED`) is
accounted for honestly rather than hidden.

## 0. Scope and reuse boundaries

**New module: `src/poc/v3.py` only.** V1's files (`src/poc/context.py`,
`poc.py`, `trend.py`, `resolution.py`, `backtest.py`, `nulls.py`,
`test_seal.py`) and **V2's file (`src/poc/v2.py`) are never modified** --
both studies' closed results stay exactly as reported. Everything V3 needs
is imported and reused, read-only:

- `poc.context.build_poc_context` -- unchanged. Universe, the six-day
  lookback-eligibility chain, PROXY POC/PREV_HIGH, and the 50-day trend
  filter are ALL identical to V1/V2 (this study changes only the
  confirmation timeframe).
- `poc.resolution.find_touch_idx` / `candle_shape` / `is_hammer` /
  `classify_confirmation_candle` / `find_confirmation` /
  `fill_bar_after_candle_close` / `resolve_exit` -- unchanged, called
  against HOURLY candles for touch/confirmation (the one change) and
  against the SAME 1-minute bars / 5-minute candles as V1/V2 for fill,
  stop/target scanning, and the 15:15 time exit (all unchanged -- see
  Section 8).
- `poc.v2.compute_lookback_low` -- unchanged. STOP is still the same
  5-trading-day lookback window's own LOW; nothing about how it is
  computed changes in V3.
- `poc.v2.position_size_shares_v2`, `poc.v2.CAPITAL_RS`, `poc.v2.
  MIN_RISK_PCT`, `poc.resolution.MAX_RISK_PCT`, `poc.resolution.
  TARGET_BELOW_PREV_HIGH_PCT` -- unchanged. Sizing, target, and both
  stop-distance guards are IDENTICAL to V2.
- `poc.v2.build_timing_pool_v2` / `timing_null_seed_mean_v2` / `poc.v2.
  build_month_pool_v2` / `selection_null_seed_mean_v2` -- unchanged,
  reused DIRECTLY (not reimplemented). Both nulls test entry TIMING and
  SELECTION pressure using the real trades' own stop distance, target, and
  (for SELECTION) a drawn day's own `lookback_low`/`prev_high` -- none of
  this depends on HOW the real entry's confirmation was constructed
  (hourly vs. 5-minute), only on its resulting stop/target/entry values,
  so V2's own null code is exactly correct for V3 unchanged. This is also
  what "WINDOWS, NULLS, GATE: identical structure to V2" (the user's own
  instruction) means concretely.
- `box_theory.costs.round_trip_cost_rs` / `box_theory.inference.
  day_clustered_bootstrap` -- unchanged, identical cost model and
  inference machinery to V1/V2.
- `fibo.universe`, `fibo.jump_guard` -- unchanged.
- `fvg.bars.aggregate_to_1hour` -- unchanged, imported from the FVG study's
  own (closed) codebase; the identical hourly-bucketing function the
  research browser's hourly chart view also uses. **Not modified, not
  copied** -- a second user of an existing, already-verified function.

**New in `src/poc/v3.py`**: `find_entry_v3` (Section 7 below -- touch/
confirm against hourly candles, then V2's own stop/target/sizing checks in
the same order V2 uses them); this study's own backtest orchestration
(`evaluate_entity_v3`/`run_backtest_v3`, identical in SHAPE to `poc.v2`'s
own, but calling `find_entry_v3` and aggregating each day's hourly candles
first); this study's own sealed-window guard (`poc.v3`'s own `DEV_START`/
`DEV_END`/`TEST_START`/`TEST_END`, identical dates to V1/V2, its own object
and access log, sharing no state with either prior seal).

## 1-6. Universe, data, lookback chain, POC, trend filter -- UNCHANGED from V1/V2

Identical to `PREREGISTRATION_POC.md` Sections 1-5 and `PREREGISTRATION_
POC_V2.md`'s own Sections 1-6/4a in full: point-in-time top-200-by-turnover
universe, 1-minute archive via `fibo.scale_probe`, the six-day Section-3
lookback-eligibility chain, the PROXY POC construction (0.25% bucket width
off today's own 09:15 open), PREV_HIGH and LOOKBACK_LOW (both `MAX`/`MIN`
across the same 5-day window), and the 50-day daily SMA trend filter. Not
restated here; reused verbatim via the functions named in Section 0.

## 7. Entry, stop, target, sizing -- touch/confirm timeframe CHANGED; everything downstream UNCHANGED

```
candles_hourly = aggregate_to_1hour(today_day_raw)        # per entity-day

touch_idx = find_touch_idx(candles_hourly, poc_price)      # >= 09:45, low <= POC
  -> NO_TOUCH if none

confirm = find_confirmation(candles_hourly, touch_idx, poc_price)  # up to 2 hourly candidates
  -> NO_CONFIRMATION / POC_FAILED as in V1/V2

confirm_close_ts = candles_hourly.iloc[confirm_idx]["bucket_end"]  # NOT ts+60min -- see above
fill_bar = fill_bar_after_candle_close(bars1, confirm_close_ts)
  -> NO_FILL_BAR if none

fill_time not in [09:45, 14:30] -> FILL_OUTSIDE_WINDOW   # expected to be materially more common

entry_price = fill_bar["open"]
stop_price  = lookback_low                                 # poc.v2.compute_lookback_low, unchanged

entry_price <= stop_price               -> ENTRY_BELOW_STOP
(entry_price-stop_price)/entry_price > 0.05   -> STOP_TOO_WIDE
(entry_price-stop_price)/entry_price < 0.005  -> STOP_TOO_TIGHT

target_price = prev_high * (1 - 0.02)
target_price <= entry_price             -> NO_ROOM

qty = max(1, floor(25000 / entry_price))                   # poc.v2 sizing, unchanged
-> ENTERED
```

Every rule from `stop_price = lookback_low` onward, in this exact order, is
**byte-identical to `poc.v2.find_entry_v2`** -- the only two differences
from V2 anywhere in this function are (a) touch/confirmation evaluated
against `candles_hourly` instead of `candles5`, and (b) the fill timestamp
computed from the confirming candle's own `bucket_end` instead of `ts +
5min`.

## 8. Resolution -- UNCHANGED (1-minute scan, 5-minute time-exit candle)

**Identical to V1/V2 Section 8 in full**, reused verbatim via `poc.
resolution.resolve_exit`, called with the SAME `today_day_raw` (1-minute)
and `today_candles5` (5-minute) frames `build_poc_context` already
provides -- NOT the hourly candles. This is a deliberate, stated choice:
the touch/confirmation change (Section "ONE CHANGE FROM V2") is scoped to
entry construction only. Stop/target resolution remains a 1-minute-bar
scan (STOP wins a same-bar tie), and the 15:15 time exit remains anchored
to the 5-minute candle grid exactly as V1/V2 define it -- substituting
hourly candles into `resolve_exit`'s own time-exit lookup would silently
change the TIME_EXIT price convention (a 5-minute candle's own close at
15:15-15:20 vs. an hourly partial bucket's close at session end, 15:30),
which is explicitly OUT of scope per "same 1-minute stop/target resolution
... same 15:15 time exit" (the user's own instruction).

## 9. Costs and net return -- UNCHANGED from V2

Identical cost model (`box_theory.costs.round_trip_cost_rs`) and identical
reporting unit (percentage of position value, not R):

```
net_return_pct = (pnl_rs - cost_rs) / position_size_rs
```

**Results reported under V3 are NOT comparable to V1 (R-based) and ARE
directly comparable to V2 (both percentage-of-Rs-25,000-position returns)**
-- stated here so a reader never lines up a V3 percentage against V1's R.

## 10. Nulls -- IDENTICAL STRUCTURE to V2, reused unchanged

Per the user's own instruction ("WINDOWS, NULLS, GATE: identical structure
to V2") and the reasoning in Section 0 above (neither null depends on
confirmation timeframe): `poc.v2.build_timing_pool_v2` /
`timing_null_seed_mean_v2` and `poc.v2.build_month_pool_v2` /
`selection_null_seed_mean_v2` are called DIRECTLY, with V3's own trades/
universe/jump-dates as input, producing V3's own null distributions. Same
1000-seed (500-seed-fallback) contingency as V1/V2 for both nulls.

## 11. Inference and gate -- same structure as V2; one honest caveat recorded

Day-clustered bootstrap (`box_theory.inference.day_clustered_bootstrap`,
unchanged module, `net_r_col="net_return_pct"`, `trade_date = T`, 10,000
resamples, 97.5% two-sided CI), identical mechanics to V2.

**Caveat, recorded plainly rather than silently resolved either way**: that
module's own 97.5% CI is Bonferroni-built for **2** pre-registered
configurations (family-wise alpha 0.05 / 2 = 0.025 per side). The POC
family is now at **3** trials. A strict 3-way Bonferroni correction would
use a tighter interval (alpha 0.05/3 = 0.0167 per side, a 98.33% CI), which
this document does **not** switch to -- per the user's explicit instruction
that the gate structure stay identical to V2, and because `day_clustered_
bootstrap` is not re-parameterized here (doing so unprompted would itself
be an undisclosed methodological change). **Using the unchanged 97.5%
level at trial count 3 is therefore slightly ANTI-CONSERVATIVE relative to
strict family-wise correction** -- stated here as a known limitation of
this study's own gate, on top of (not instead of) the selection-pressure
caveat in Provenance above, not discovered after a result exists.

**DEV PASSES only if ALL hold** (identical structure to V1/V2):

- mean net return % > 0 with the day-clustered 97.5% bootstrap CI
  excluding zero
- mean net return %'s percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls
- mean net return % remains > 0 after dropping the single best calendar
  year (by that year's own mean net return %) from the DEV sample
- mean net return % > 0 within rank bands 1-100 alone

**Anything else = NO EDGE. The study closes; the sealed TEST window is
never read.**

## 12. Windows -- identical to V1/V2

**DEV**: 2016-10-04 to 2022-12-31. **TEST (sealed)**: 2023-01-01 to
2026-09-18 -- `poc.v3`'s own sealed-window guard, same mechanism and dates
as `poc.test_seal`/`poc.v2`, its own object and access log, not shared with
either prior seal. Not read unless DEV passes AND the user explicitly
approves.

## 13. Report contents

Same structure as `PREREGISTRATION_POC_V2.md` Section 13 in full: trades,
distinct entry days, win rate, mean net return % with its 97.5% CI, median
net return % (descriptive), MDE, both null percentiles (seed counts,
SELECTION's matched count per month), breakdown by calendar year (and
ex-best-year mean), breakdown by rank band, exit mix, peak concurrent
positions/deployed capital, the full skip/diagnostic breakdown, realised
risk (stop-distance) distribution, total costs (rupees and % of position),
and the standing "percentage-of-capital, not R, not comparable to V1"
reminder every time a headline number appears.

**New for V3, per instruction, all required (not optional)**:

- **`(entry_price - POC_PRICE) / entry_price` distribution, reported
  directly against V2's own distribution of the same quantity** -- this is
  the stated rationale for the whole study (hourly confirmation should move
  entries further from the POC than 5-minute confirmation did), so it is
  measured and compared explicitly, not asserted.
- **Trade count against V2's 22,959**, with the full skip/loss breakdown by
  reason, and **`fill_outside_window` singled out and reported
  prominently** (not folded into the general list) -- per the stated
  consequence that hourly confirmation consumes far more of the session
  before an entry can complete.
- **The realised stop-distance distribution** (`stop_distance_pct`), same
  definition as V2's own Section 13 addition.

**Bad results are reported in the first sentence**, the same standing
instruction every prior study here follows.

## 14. Process, in this order, stopping where marked

1. Write this document. **Commit it alone**, before any touch, stop, or
   trade is computed. Report the commit hash.
2. Build `src/poc/v3.py`. **Hand-trace 5 real DEV-window trades/skips
   before any aggregate number is computed**: at minimum, one entry showing
   the hourly touch/confirm candles and the `bucket_end`-derived fill
   timestamp, and one skip demonstrating the expanded `FILL_OUTSIDE_WINDOW`
   consequence -- the remaining three chosen from whatever other shapes
   (`STOP_TOO_WIDE`, `TARGET`/`STOP`/`TIME_EXIT` outcomes, `NO_CONFIRMATION`,
   `POC_FAILED`) the real DEV data actually contains, stated plainly if a
   shape is not found rather than manufactured.
3. Run **DEV only** (real trades, then TIMING and SELECTION nulls),
   checkpointed at each stage, timing and memory measured before the long
   stages. Report per Section 13. **>>> STOP. The user approves before the
   sealed TEST window is read.**
4. Only after that approval: authorize `poc.v3`'s own test seal, read TEST
   once, report per Section 13.

## 15. Discipline

**Trial counter for the POC family = 3 (V1, V2, V3).** All parameters
below are **FIXED** -- the hourly confirmation timeframe itself, the 5%
maximum and 0.5% minimum stop-distance guards, the Rs 25,000 capital
figure, the 2% PREV_HIGH target offset, the 15:15 time exit, and every rule
carried unchanged from V1/V2 (universe, POC/PREV_HIGH/LOOKBACK_LOW
construction, trend filter, cost model). If DEV fails, **none are retried
at other values, and no variant is folded into this document after the
fact; any such variant is a NEW trial requiring its own pre-registration.**

**Stated explicitly, per instruction: if DEV fails, the POC family closes.
No V4 will be proposed.** Three trials, each responding to the specific,
diagnosed failure of the one before it, is already more selection pressure
than this project's own standing discipline tolerates for a single family;
a fourth would not be a new hypothesis, it would be curve-fitting one
family's own history of failures.

**No rule in this document changes after any number from DEV or TEST has
been seen. Bad results are reported in the first sentence** of whatever
reports them, never buried after a methods recap.

## Status

**>>> STOPPING HERE, per Process Step 1.** No `src/poc/v3.py` code exists
yet, and no touch, stop, or trade has been computed anywhere in this study.
This document is being committed alone, before any of that exists, so Step
2's hand-traces and Step 3's DEV run cannot have shaped anything written
above.
