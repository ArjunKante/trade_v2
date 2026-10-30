# Liquidity confluence, Study A (long only)

## Provenance

Hypothesis from the user, stated plainly, not Claude's own: stop-loss
orders cluster at obvious swing highs and lows across multiple
timeframes, and levels where several timeframes agree hold the most
clustered liquidity. Price reaches those levels, takes the liquidity,
then reverses.

**NEW FAMILY, trial 1.** Not a POC-family revision. A Study B testing
the SHORT side is planned separately by the user and is explicitly NOT
part of this study -- Study A is long only, and the HIGH-level half of
the level construction below is computed but deliberately unused here.

**Base rate, recorded honestly, per instruction**: eleven prior
strategies in this project have closed with no edge, including five POC
revisions (`POC_FINDINGS.md`, `POC_V2_FINDINGS.md`, `POC_V3_FINDINGS.md`,
`POC_V4_FINDINGS.md`, `POC_V5_FINDINGS.md`), plus box theory V1/V2, FVG,
IPO listing, and Darvas. The POC family's V4 passed both null comparisons
and still lost after costs; extending its holding horizon in V5 made the
result more than twice as bad. This study reuses V4's own sweep-and-
reclaim entry structure (`poc.v4.find_sweep`/`find_reclaim`, imported
unchanged, never copied) with a DIFFERENT level definition feeding it --
a multi-timeframe confluence zone instead of V2-V4's single 5-day
lookback low. Nothing about that reuse implies this study is expected to
fare differently from the base rate; it is recorded so a pass here is
read against eleven priors, not zero.

## Section 0: reuse boundaries, read-only

Everything below is imported, never copied or modified. No closed
study's own files are touched.

- `poc.v4.{find_sweep, find_reclaim, STOP_BUFFER_ATR}` -- V4's own
  sweep-and-reclaim detection, unchanged. Study A passes the confluence
  zone's own price in place of V4's `lookback_low`; the function bodies
  do not know or care which kind of level they were given.
- `poc.v2.CAPITAL_RS` (25,000), `poc.v2.MIN_RISK_PCT` (0.005) -- unchanged.
- `poc.resolution.{ENTRY_WINDOW_START, ENTRY_WINDOW_END, MAX_RISK_PCT,
  fill_bar_after_candle_close, _stop_target_event}` -- unchanged.
  `_stop_target_event`'s own existing STOP-wins-on-tie convention is
  reused TWICE per trade (Section 4) -- it already implements the
  "stop wins a same-bar tie" rule this study independently asked for;
  no new tie-break code was needed.
- `box_theory.context.{eligible_day_context, group_by_day}` -- called
  ONCE per (entity, day), not chained across a multi-day lookback the
  way `poc.context.build_poc_context` chains L1..L5,T for V1-V4's own
  volume-profile POC. Study A's levels come from daily bars, not an
  intraday volume profile, so the 5-day intraday-eligibility chain V1-V4
  need is not needed here at all -- a single day's own eligibility
  (jump guard, ex-date, previous-session scale resolution) is sufficient
  context for this study's own entry.
- `box_theory.universe_data.{fetch_bars_range, fetch_bhav_daily,
  fetch_ex_dates}` -- unchanged.
- `box_theory.costs.{band_for_rank, round_trip_cost_rs}` -- `round_trip_
  cost_rs` reused directly ONLY for the "hypothetical single exit at 3R"
  comparison figure (Section 6); the real trade's own cost is a NEW
  per-leg model (Section 6), since this is the first POC-lineage study
  with more than two orders per trade.
- `box_theory.inference.{day_clustered_bootstrap, percentile_vs_null,
  excludes_zero}` -- unchanged. Same 97.5% two-sided, Bonferroni-for-2-
  configurations CI machinery every prior study in this lineage has used
  -- flagged again here as increasingly anti-conservative at trial N
  across the project as a whole, not re-parameterized, per the standing
  convention of keeping gate machinery identical across trials.
- `poc.backtest.{build_universe, _entity_years}` -- unchanged (top-200
  by turnover, annual reconstitution, `effective_universe`'s stub-year
  handling).
- `poc.nulls.{_random_fill, _valid_entry_idx}` -- unchanged.
- `fibo.daily_ohlc.build_daily_ohlc_panel`, `fibo.price_scale.
  to_raw_scale`, `fibo.indicators.atr` -- unchanged. This is the SAME
  raw-scale-conversion mechanism `poc.v4` already uses for its own ATR
  panel (`_build_atr_adjusted_lookup_for_entity`/`_build_adjustment_
  factor_lookup_for_entity`, both imported from `poc.v4` unchanged, not
  re-derived): an entity-adjusted daily value, converted to TODAY's raw
  scale via `adjusted_price / factor(today)`. Level construction
  (Section 1) uses this exact same mechanism for the three LOW (and,
  unused, HIGH) levels, for the same reason V4 used it for ATR -- a
  value derived from historical daily bars needs to be on TODAY's raw
  scale to be compared against today's intraday candles.

  **Stated plainly, because it matters and is not obvious**: this is a
  DIFFERENT raw-scale mechanism from `fibo.scale_probe`'s own (the one
  `eligible_day_context` uses internally to convert TODAY's own Angel
  intraday bars to raw, via a day-specific empirically-measured Angel-
  vs-bhavcopy ratio). The two mechanisms are structurally independent,
  exactly as they already are in V4 (V4's ATR conversion and V4's
  intraday-bar conversion never cross-check each other either). This is
  accepted, not newly introduced by this study -- `fibo.scale_probe`'s
  own module docstring explains why it was deliberately rebuilt to NOT
  depend on `adjustment_factors` (a prior version had 14.9% UNRESOLVED
  days, concentrated in entities with pre-2016 corporate-action blind
  spots); using it for multi-month level construction would reintroduce
  exactly the dependency it was built to avoid. `fibo.price_scale`'s
  mechanism is explicitly a split-adjustment table, which IS what a
  multi-month lookback level needs (a stop-order level from 3 months ago
  must be compared in POST-split terms if a split happened since).
  "RAW scale via the existing scale probe" in the instruction is read as
  "this project's existing mechanism for putting a historical daily-bar
  level on today's raw scale" -- i.e. V4's own precedent -- not literally
  `fibo.scale_probe`'s module, which serves a different, already-used-
  elsewhere purpose (today's own intraday archive, not a historical
  level).
- `box_theory.holiday.previous_nse_trading_day` -- unchanged, used only
  to look up ATR's own "through the previous trading day" timing (same
  convention V4 uses via its own `L5`); level construction itself uses
  each entity's own `prices_eod` trading-day index directly (via
  `fibo.daily_ohlc.build_daily_ohlc_panel`'s own row order), not this
  function, since the levels need EVERY one of an entity's own trading
  days in sequence, not just "yesterday."

**New code, lives entirely in `src/liquidity/a.py`**: level-window
construction and the raw-scale lookup that feeds it (Section 1),
confluence-zone detection (Section 2), the per-leg three-order cost model
and its "hypothetical single exit" comparison (Section 6), the scaled
exit resolution built from two calls to the reused `_stop_target_event`
(Section 4), sizing with the half/full split (Section 5), orchestration,
and both nulls' own pool-building and draw functions (Section 9). A
fresh sealed TEST-window guard, pattern-identical to V4's/V5's own but a
separate object (Section 8).

## Section 1: level construction

Six candidate levels per (entity, day), computed at 09:45 from data
through the PREVIOUS trading day only -- no same-day information, per
instruction:

| Level | Window | Trading days |
|---|---|---|
| 3-month high / low | rolling | 63 |
| 1-week high / low | rolling | 5 |
| 1-day high / low | single day | previous trading day |

All three windows are built from ONE rolling computation per entity
(not recomputed per day), on `fibo.daily_ohlc.build_daily_ohlc_panel`'s
entity-adjusted `adjusted_high`/`adjusted_low` columns, SHIFTED BY ONE
ROW before any rolling window is applied -- the shift is what enforces
"through the previous trading day only": row i's shifted value is row
(i-1)'s own high/low, so a `.rolling(5).min()` evaluated at row i covers
rows (i-5)..(i-1) -- the 5 trading days strictly before day i, never
including it.

```python
shifted_low  = panel["adjusted_low"].shift(1)
shifted_high = panel["adjusted_high"].shift(1)
lo_1d, hi_1d = shifted_low, shifted_high
lo_1w, hi_1w = shifted_low.rolling(5).min(),  shifted_high.rolling(5).max()
lo_3m, hi_3m = shifted_low.rolling(63).min(), shifted_high.rolling(63).max()
```

A day whose own `lo_3m` is still NaN (fewer than 63 prior trading days
exist yet for this entity) is skipped as `LEVEL_INSUFFICIENT_HISTORY` --
checking `lo_3m` alone is sufficient since it is the binding window (if
63 days exist, 5 and 1 trivially do too).

Each adjusted-scale level is converted to TODAY's raw scale via
`to_raw_scale(level_adjusted, factor_today)` (Section 0), where
`factor_today` is TODAY's own `adjustment_factors.factor`, reused from
`poc.v4._build_adjustment_factor_lookup_for_entity` unchanged.

**Only LOW levels matter for Study A, since this is long only.** The
three HIGH levels are computed (the rolling-window code above produces
both in one pass, at no extra cost) but are not used by anything in this
study -- recorded for Study B, which will need them for its own short-
side confluence zones.

## Section 2: confluence zone

**CONFLUENCE ZONE: two or more LOW levels within 0.5 x ATR(14) of each
other.** With exactly three candidate LOW levels (3m, 1w, 1d), this is
implemented as connected components over an adjacency graph: an edge
exists between two levels if `abs(level_a - level_b) <= 0.5 * atr_raw`;
a "zone" is any connected component of size >= 2; the zone's reference
price is the mean of its own members. This directly implements "if
three cluster, that counts as one zone with all three averaged" (all
three mutually within tolerance -> one connected component of size 3)
and the plain two-level case (one edge -> one component of size 2)
identically, with no special-casing between them.

**"If multiple separate clusters exist, take the one nearest below the
previous close" is implemented, but proved structurally unreachable with
exactly three candidate levels**, stated plainly before any result
exists (same discipline as V5's own `NO_ROOM`-unreachability finding):
two DISJOINT clusters of size >= 2 each would need at least 4 distinct
nodes with no node shared between them; with only 3 nodes, any 2
qualifying edges necessarily share at least one node (there are only 3
possible node-pairs total among 3 nodes), so the edge set can produce at
most ONE connected component of size >= 2. The "multiple clusters, pick
nearest below previous close" branch is still coded (general connected-
components logic, not hardcoded to assume one component, and a real
tie-break using each component's own mean vs. the previous trading
day's own raw-scale close) for Study B's own reuse and for defensive
correctness, but is predicted, and will be confirmed in the Section 11
report, to execute zero times in Study A's own DEV run.

If no two LOW levels cluster at all: `NO_CONFLUENCE`, the day is skipped.

## Section 3: entry, reusing V4's sweep-and-reclaim structure

Byte-identical to `poc.v4.find_sweep`/`find_reclaim`, called with the
confluence zone's own price (Section 2) in place of V4's `lookback_low`:

**SWEEP**: the first 5-minute candle at or after 09:45 whose low sits
0.1x-1.0x ATR(14) below the zone price. Shallower -> `TOUCH_TOO_SHALLOW`
(keep watching); deeper -> `BREAKDOWN_NOT_SWEEP` (abandon the day).

**RECLAIM**: within the next 3 five-minute candles (clock never resets
on a new low, which only updates the running `sweep_low` -- same
"later box" precedent as V4), a candle must CLOSE back above the zone
price. None does -> `NOT_RECLAIMED`.

**ENTRY**: open of the next 1-minute bar after the reclaiming candle's
own close (`fill_bar_after_candle_close`, unchanged), window 09:45-14:30.
`STOP = final sweep_low - 0.1 x ATR` (`poc.v4.STOP_BUFFER_ATR`,
unchanged). One trade per stock per day, inherent in the per-day
evaluation loop (same structure V1-V4 already use) -- no explicit extra
guard needed.

Guards, in order, same formulas as V2-V4:
- `entry_price <= stop_price` -> `ENTRY_BELOW_STOP`
- `(entry - stop)/entry > 0.05` -> `STOP_TOO_WIDE`
- `(entry - stop)/entry < 0.005` -> `STOP_TOO_TIGHT`

## Section 4: exits, scaled -- the first study in this lineage to use them

R = entry - stop. `HALF_TARGET = entry + 1.5R` (50% of position).
`FULL_TARGET = entry + 3.0R` (remainder). `TIME_EXIT` = 15:15 candle
close (same convention as `poc.resolution.resolve_exit`'s own TIME_EXIT
branch, reused by direct composition, not copied).

**Resolution is built from exactly two calls to the reused
`_stop_target_event(bars1, fill_ts, stop_price, target_price)`**
(Section 0), never a new tie-break implementation:

1. Phase 1: `_stop_target_event(bars1, fill_ts, stop, HALF_TARGET)`.
   - Neither hit by 15:19 -> full position exits at the 15:15 close
     (`TIME_EXIT_FULL`), nothing was ever scaled.
   - `STOP` -> full position exits at the stop (gap-aware: the bar's own
     open if it already gapped through, else the stop price itself --
     `resolve_exit`'s own convention) -- `STOP_NO_HALF`. No half exit
     happened; this IS `_stop_target_event`'s existing same-bar
     STOP-wins convention, which is exactly the rule the instruction
     asked for ("if both the half-exit level and the stop are touched
     within the same 1-minute bar, the STOP wins for the whole
     position") -- no new code was needed to satisfy it.
   - `TARGET` (half-level hit) -> HALF EXIT: `floor(qty/2)` shares sell
     at `HALF_TARGET`, in this bar. Continue to phase 2.
2. Phase 2 (only reached after a half exit): `_stop_target_event(bars1,
   <phase-1's own bar timestamp>, stop, FULL_TARGET)`, re-scanning from
   the SAME bar the half exit happened in. This is safe and correct
   without a separate same-bar special case: phase 1 already proved
   this bar's low did not reach `stop` (TARGET won, not STOP) and this
   bar's high did not reach `FULL_TARGET` either would be checked fresh
   here -- if it DOES also reach `FULL_TARGET` in this same bar, phase 2
   returns `TARGET` immediately at this same timestamp, correctly
   capturing a same-bar half-then-full move with no extra logic.
   - Neither hit -> remainder rides to the 15:15 close --
     `HALF_THEN_TIME_EXIT`.
   - `STOP` -> remainder exits at the stop (same gap-aware rule) --
     `HALF_THEN_STOP`. The half already sold at 1.5R keeps its realised
     profit; it is never clawed back, per instruction.
   - `TARGET` -> remainder exits at `FULL_TARGET` -- `FULL_EXIT` (or
     `FULL_EXIT_SAME_BAR` if this bar is the same bar the half exit used,
     reported separately out of curiosity, not because it changes any
     formula).

**qty = 1 is a separate, simpler path, not a special case of the
above**: no half exit is possible, so phase 1 above is skipped entirely
and `poc.resolution.resolve_exit` (unchanged, 2-level: stop vs.
`FULL_TARGET` only) is called directly on the full quantity. Outcomes
`STOP`/`TARGET`/`TIME_EXIT` are relabelled `STOP_QTY1`/`TARGET_QTY1`/
`TIME_EXIT_QTY1` in the trade record so Section 11's report can count
these separately, per instruction, without conflating them with a
"stopped out before the half exit" (`STOP_NO_HALF`) trade that DID have
enough shares for a half exit but never reached 1.5R.

## Section 5: sizing

`qty = floor(25000 / entry_price)` (`poc.v2.CAPITAL_RS`, unchanged
value). **`qty < 1` is guarded as `ZERO_QTY` and skipped** -- the
instruction does not state a minimum-1-share floor for Study A the way
V2's own "TWO CHANGES FROM V1" explicitly did; rather than silently
assume one, entry prices above Rs 25,000 (plausible for a top-200-by-
turnover name) are counted and skipped, not forced to 1 share. This is a
pre-build amendment, found and fixed before any trade exists, in the
same spirit as V1's doji-hammer carve-out and V5's `INSUFFICIENT_DATA`
merge -- stated here rather than silently decided.

`half_qty = qty // 2`, `remainder_qty = qty - half_qty`. When `qty == 1`,
`half_qty` would be 0 -- this is exactly why qty=1 is routed to its own
simpler path (Section 4) instead of ever calling the half-exit logic
with a zero-share order.

**`NO_ROOM` cannot occur and is not coded as a skip reason**: both
`HALF_TARGET = entry + 1.5R` and `FULL_TARGET = entry + 3.0R` are risk-
multiples computed FROM entry and a strictly-positive R (guarded by
`ENTRY_BELOW_STOP` already having been checked and passed), so both
targets are always strictly greater than entry by construction -- the
same structural fact `PREREGISTRATION_POC_V5.md` found and confirmed
exactly for its own risk-multiple target. Stated here before any trade
exists, not discovered live.

## Section 6: costs

Intraday cost model (`swing.costs.buy_leg_cost_rs`/`sell_leg_cost_rs`,
unchanged), plus the frozen Section 8c banded spread (`box_theory.costs.
BAND_SPREAD_BPS`, unchanged: 2.0/4.0/7.0bps round trip for bands 1-50/
51-100/101-200, unranked falls back to 101-200's figure).

**Scaled exits mean THREE orders for most trades (one buy, two sells),
modeled explicitly, not collapsed into one round-trip figure**:

- BUY leg: `buy_leg_cost_rs(entry_value_rs, "INTRADAY")` + half the
  band's own round-trip spread bps, applied to `entry_value_rs`.
- Each SELL leg (half-exit sell, remainder/full sell, or the single sell
  when qty=1): `sell_leg_cost_rs(that_leg's_own_trade_value_rs,
  "INTRADAY")` + half the band's own round-trip spread bps, applied to
  THAT leg's own trade value.

**Why the spread is split half-and-half across the buy side and the
sell side(s), stated as a deliberate modeling choice, not assumed**: the
Section 8c bps figures are explicitly described as ROUND TRIP (crossing
the spread once entering, once exiting). Splitting evenly and applying
each half to its own leg's own actual trade value is the natural
generalisation when the exit itself is split across multiple orders --
it keeps the total spread charge's magnitude anchored to the same
round-trip assumption every other study in this lineage uses, while
still letting each of the three orders carry its own fair share for the
per-leg cost breakdown Section 11 reports.

`total_cost_rs = buy_leg_cost + sum(sell_leg_costs)` (two sell legs for a
scaled exit with `qty >= 2`, one for `qty == 1`). `net_return_pct =
(pnl_rs - total_cost_rs) / position_size_rs`, `position_size_rs = qty *
entry_price` (entry value, same convention as V1-V4's own
`position_size_rs`).

**Extra cost of the three-order structure vs. a hypothetical single exit
at 3R (Section 11's own required figure)**, defined per trade, computed
regardless of what actually happened: `hypothetical_cost_rs =
box_theory.costs.round_trip_cost_rs(entry_value_rs, band)` -- literally
V4's own cost formula applied to this same trade, i.e. "what would this
trade have cost under the POC family's own existing two-order
convention." `extra_cost_rs = total_cost_rs - hypothetical_cost_rs`,
reported in rupees (mean, sum) and as a percentage of `position_size_rs`
(mean). This isolates the COST-STRUCTURE difference (extra brokerage
floor, extra GST-on-brokerage, from a genuinely extra order) from the
RETURN difference a scaled exit also produces by selling part of the
position early -- the two are reported separately, never blended into
one number.

## Section 7: universe and guards

Point-in-time top 200 by turnover, annual reconstitution (`poc.backtest.
build_universe`, `TOP_N=200`, unchanged). All lineage, same-ISIN, and
scale guards reused unchanged (`fibo.universe.{restrict_to_universe,
assert_universe_membership}`, `fibo.jump_guard.combined_unexplained_
jump_dates`, `box_theory.context.eligible_day_context`'s own jump/ex-
date/previous-session checks).

**No trend filter -- the confluence structure is the selection mechanism
here, a deliberate difference from the POC family**, stated per
instruction. V1-V4's 50-day-SMA trend filter (`poc.trend.
trend_filter_passes`) is not imported or called anywhere in this module.

## Section 8: windows

DEV: 2016-10-04 to 2022-12-31. TEST (sealed): 2023-01-01 to 2026-09-18.
A fresh `TestWindowViolationError`/`guard_date_range` pair, pattern-
identical to V4's/V5's own but a separate object (own `ACCESS_LOG_PATH`
at `data/liquidity/a/test_window_access_log.txt`), per this project's
own "a fresh instance, not a shared one" convention.

## Section 9: nulls

Both nulls reuse `poc.nulls._random_fill`/`_valid_entry_idx` unchanged,
and both apply BOTH the 0.5% minimum and 5% maximum stop-distance
guards (Section 3) to every draw -- stated as a deliberate choice, not a
silent deviation: V2's own original null code (`poc.nulls._timing_draw`,
`poc.v2._timing_draw_v2`) checks only the maximum guard, not the
minimum, an inherited asymmetry with the real strategy's own entry
criteria. Study A applies both, since a null whose own entry criteria
differs from the real strategy's criteria understates how much of the
real result the null can actually explain.

**TIMING**: restricted to the exact (entity, day) pairs the real
strategy traded (one `eligible_day_context` call per real trade day, not
the full multi-day chain -- Section 0). A random 5-minute candle in
09:45-14:30 replaces the real sweep+reclaim signal. The real trade's own
stop DISTANCE (an absolute rupee amount, `entry_price - stop_price`,
carried over unchanged) and the real trade's own scaled-exit structure
(1.5R half, 3.0R full, same cost model) are reused; only entry TIMING is
randomized, per instruction.

**SELECTION**: random (entity, day) pairs from the same universe-year
population that passes this study's own single-day eligibility (jump
guard, ex-date, previous-session scale resolution), has sufficient level
history (`LEVEL_INSUFFICIENT_HISTORY` days excluded, matching the real
backtest's own gate), and has ATR available -- i.e. every day a real
signal COULD have been evaluated, whether or not a confluence zone or a
sweep actually occurred, matching this lineage's own established
SELECTION-null population principle. Matched count per calendar month to
the real strategy's own trade count that month. Stop distance is drawn
as a PERCENTAGE from the real strategy's own pooled `stop_distance_pct`
distribution (the original V1 `rho_pool` convention, not V2-V5's
deterministic-per-day stop, since Study A's stop is not anchored to a
single deterministic day-level the way V2-V5's lookback-low stop is).
Half/full targets are recomputed from the drawn day's own entry and the
sampled stop, same 1.5R/3.0R formula, same cost model.

1000 seeds, or 500 with the usual timed-probe fallback (same contingency
used by every prior study in this lineage).

## Section 10: gate

Mean net return > 0, day-clustered 97.5% bootstrap CI (Bonferroni for 2
configurations, unchanged machinery) excluding zero; >= 95th percentile
against BOTH nulls; still positive after dropping the best year;
positive within bands 1-100 alone. All four required; anything else is
NO EDGE, study closes, TEST is never read.

## Section 11: report

Trades, distinct days, mean net return (% of position) with CI, median,
both null percentiles, by year, by band. Plus, per instruction:
- confluence pair/triple breakdown (3m+1w, 3m+1d, 1w+1d, all three) and
  the result split by which combination formed the zone.
- half-exit reach rate; of those, full-target reach rate; of those that
  reached the half exit, how many then stopped out on the remainder.
- the extra cost of the three-order structure vs. a hypothetical single
  exit at 3R (Section 6), in rupees and as a percentage.
- skip counts: `NO_CONFLUENCE`, `TOUCH_TOO_SHALLOW`, `BREAKDOWN_NOT_
  SWEEP`, `NOT_RECLAIMED`, `STOP_TOO_TIGHT`, `STOP_TOO_WIDE`, `ZERO_QTY`,
  plus `qty == 1` trades counted separately (not a skip -- a real,
  simpler-path trade, Section 4).
- peak concurrent positions and capital, built from each trade's own
  entry/half-exit/final-exit timestamps as a chronological event sweep
  (capital drops by the half-exit's own value at its own exit time, not
  only at the final exit) -- a finer-grained version of V5's own single-
  exit-time proxy, needed because a scaled-exit trade's capital
  footprint shrinks in two steps, not one.

## Section 12: process

1. Write this document. Commit and push ALONE. Report the hash.
2. Five hand-traces before any aggregate: one reaching the full 3R
   target, one stopping out before the half exit, one taking the half
   exit then stopping out on the remainder, one 15:15 time exit with the
   second half still open, one `NO_CONFLUENCE` skip. Show the six levels
   and which two (or three) clustered.
3. Run DEV only. Report. STOP for approval before TEST.

## Section 13: Claude's pre-committed prediction

DEV fails, mean net return between -0.6% and +0.2%. The confluence
filter should produce far fewer and better-selected trades than V4's
3,225 -- possibly under 1,000 -- but the three-order cost structure
works against it and intraday friction has defeated every version of
this mechanism so far.

## Section 14: discipline

All parameters FIXED for this trial. If DEV fails, this exact
parameterization (these six levels, this 0.5xATR tolerance, this 1.5R/
3.0R split, this sizing) is not retried at other values. This governs
Study A only -- the user's own separately-planned Study B (short side)
is a different trial of the same new family, not a retry of this one,
and is unaffected by this study's own outcome either way.

## Status

Preregistration complete. Not yet committed. Next: commit alone, report
hash, then build `src/liquidity/a.py` and the hand-trace script.
