# Liquidity confluence, Study B (short only)

## Provenance

Hypothesis from the user, stated plainly, not Claude's own: stop-loss and
short-covering orders cluster at obvious swing highs and lows across
multiple timeframes, and levels where several timeframes agree hold the
most clustered liquidity. Price reaches those levels, takes the
liquidity, then reverses.

**Liquidity family, trial 2.** Study A (long side) closed at DEV with
**NO EDGE**: mean net return **-0.2841%**, **8,131 trades**, both nulls
passed at the **100th percentile**, **3 of 4** gate conditions failed
(`LIQUIDITY_A_FINDINGS.md`, preregistered in `PREREGISTRATION_LIQUIDITY_A.md`,
commit `214b3a6`). Study B is the **EXACT MIRROR** of Study A on the short
side, deliberately preserving Study A's known flaw so the two are directly
comparable. The question this study asks is narrow: **does the same
mechanism fail symmetrically on the short side?** Study B does not retry
Study A's parameters at other values and does not redefine the confluence
filter -- both are explicitly out of scope here (Study C, below).

**Base rate, carried forward from Study A plus this family's own prior
trial**: twelve prior strategies in this project have closed with no edge
(`LIQUIDITY_A_FINDINGS.md`'s own updated count), including five POC
revisions, box theory V1/V2, FVG, IPO listing, Darvas, and Study A itself.
Study A's own base-rate framing is reused verbatim: a pass here is read
against thirteen priors (if Study A is counted once more as this family's
own trial 1), not against zero.

## THE PRESERVED FLAW -- recorded explicitly as a deliberate choice

Study A found that **78.6% of its confluence zones (6,389 of 8,131
trades) clustered on the 1-day and 1-week LOW alone**
(`LIQUIDITY_A_FINDINGS.md`, Finding 2). This was not genuine
multi-timeframe agreement: a weekly low is, by construction, usually one
of that week's own daily lows -- the 1-week window is only 5 trading
days, and its own minimum is frequently SET by the previous day or by a
day inside the same short window the 1-day level is drawn from. The same
arithmetic applies identically to HIGHS: a weekly high is usually one of
that week's own daily highs, for the identical structural reason (a
5-day rolling max is frequently set by the most recent day or by a day
inside the same short window the 1-day level is drawn from). **This
study expects the same definitional overlap to recur on the high side,
and is NOT attempting to fix it.**

The filter is kept **UNCHANGED** -- same three HIGH levels (3-month,
1-week, 1-day), same `0.5 x ATR(14)` tolerance, same connected-components
clustering -- so that any difference between Study A's and Study B's
results is attributable to **direction alone** (shorting vs. buying,
reversal-from-resistance vs. reversal-from-support, STT falling on a
different leg), not to a level redefinition that would confound the
comparison. **A corrected version using non-nesting timeframes (for
example, a window that excludes the most recent N days already covered
by a shorter window, so "confluence" measures genuine agreement between
windows that don't trivially share data) would be a separate Study C**,
not in scope here, and not implied by anything in this document.

## Section 0: reuse boundaries, read-only -- and where the mirror needs genuinely new code

Everything in this section is imported, never copied or modified. No
closed study's own files are touched, including `src/liquidity/a.py`
itself -- Study B imports from it exactly as it would from any other
closed-study module (`poc.v4`, `box_theory.*`), per Study A's own Section
0 reuse convention, and nothing in `src/liquidity/a.py` is edited.

**Directly reusable, unchanged, because the function is direction-agnostic
or Study A already built the HIGH-side half of it for this study's own
future use:**

- `liquidity.a._build_level_lookup_for_entity` -- Study A's own level
  builder already computes `hi_1d`, `hi_1w`, `hi_3m` (Study A's own
  Section 1 docstring: "recorded for Study B, which will need them for
  its own short-side confluence zones"). Reused directly, not
  re-derived -- the six-level computation (shift-by-one-row, three
  rolling windows, raw-scale conversion via `to_raw_scale`/
  `_build_adjustment_factor_lookup_for_entity`) is identical infrastructure
  regardless of which three of the six columns a study reads.
- `liquidity.a.{LEVEL_WINDOW_1W_DAYS, LEVEL_WINDOW_3M_DAYS,
  CONFLUENCE_TOL_ATR, HALF_TARGET_R, FULL_TARGET_R}` -- Study A's own
  frozen parameter values, reused by reference, not retyped as new
  constants, so a future change to one cannot silently drift the two
  studies apart.
- `liquidity.a._time_exit_candle` -- Study A's own 15:15-close lookup
  helper. Direction-agnostic: it returns whichever candle's own close sits
  at or before 15:15, with no reference to stop/target/entry at all.
  Reused directly rather than duplicated a second time.
- `box_theory.context.{eligible_day_context, group_by_day}`,
  `box_theory.universe_data.{fetch_bars_range, fetch_bhav_daily,
  fetch_ex_dates}`, `box_theory.holiday.previous_nse_trading_day`,
  `box_theory.costs.{BAND_SPREAD_BPS, round_trip_cost_rs}`,
  `box_theory.inference.{day_clustered_bootstrap, percentile_vs_null,
  excludes_zero}` -- all unchanged, same role as in Study A's own Section
  0. `round_trip_cost_rs` in particular is reused for the SAME purpose as
  Study A used it (the Section 6 "hypothetical single exit" comparison
  figure) -- that figure represents "what this trade would have cost
  under the POC family's own existing two-order convention," a magnitude
  comparison that does not depend on which side of the order was the buy
  vs. the sell, so no short-side variant is needed.
- `fibo.daily_ohlc.build_daily_ohlc_panel`, `fibo.price_scale.
  to_raw_scale`, `fibo.jump_guard.combined_unexplained_jump_dates`,
  `fibo.universe.{restrict_to_universe, assert_universe_membership}` --
  unchanged.
- `poc.backtest.{build_universe, _entity_years}` -- unchanged.
- `poc.nulls.{_random_fill, _valid_entry_idx}` -- unchanged. Both are
  already direction-agnostic: they pick a random candle inside the entry
  window and return its own fill bar's open price, with no reference to
  which direction the real strategy trades. This is the same reasoning
  Study A used to justify reusing them for its own long-side null, now
  confirmed to apply identically on the short side.
- `poc.resolution.{ENTRY_WINDOW_START, ENTRY_WINDOW_END, MAX_RISK_PCT,
  fill_bar_after_candle_close}` -- unchanged. `fill_bar_after_candle_close`
  looks up a bar by timestamp only; `MAX_RISK_PCT`/`ENTRY_WINDOW_*` are
  plain bounds, neither direction-specific.
- `poc.v2.{CAPITAL_RS, MIN_RISK_PCT}` -- unchanged. `MIN_RISK_PCT` bounds
  `(stop - entry)/entry` in magnitude, which is already defined to be
  positive regardless of which side of entry the stop sits on.
- `poc.v4.{STOP_BUFFER_ATR, SWEEP_DEPTH_MIN_ATR, SWEEP_DEPTH_MAX_ATR,
  RECLAIM_WINDOW_CANDLES, _build_adjustment_factor_lookup_for_entity,
  _build_atr_adjusted_lookup_for_entity}` -- the tuning CONSTANTS are
  reused unchanged (same 0.1x/1.0x ATR sweep-depth band, same 3-candle
  reclaim window, same 0.1x ATR stop buffer); the ATR/adjustment-factor
  lookups are unchanged infrastructure. **The two FUNCTIONS `find_sweep`
  and `find_reclaim` are NOT reused** -- see below.
- `swing.costs.{buy_leg_cost_rs, sell_leg_cost_rs}` -- unchanged
  FORMULAS, reused in **swapped roles** from Study A (Section 6 below) --
  this is a deliberate consequence of the direction flip, not a new cost
  model.

**Stated plainly, because the task description's "EVERYTHING MIRRORS
STUDY A" could be misread as "every function is reused unchanged," and
that is not quite true for four pieces of logic that hard-code a
long-side direction into their own inequalities:**

1. **`poc.v4.find_sweep`/`find_reclaim` cannot be called for Study B.**
   `find_sweep`'s own body checks `low >= lookback_low: continue` and
   computes `depth = lookback_low - low` -- it is written specifically to
   detect a LOW breaching DOWN through a support level. Calling it with a
   HIGH level and a resistance zone would silently compute nonsense (a
   candle's low is almost always below a resistance level sitting above
   the previous close, so the function would immediately return `SWEEP`
   on the very first candle with no real breakout logic involved at all).
   `find_reclaim`'s own `close > lookback_low` check has the same
   direction baked in. **New functions `find_sweep_short`/
   `find_reclaim_short` are required** -- byte-identical in STRUCTURE
   (same loop shape, same "do not reset the clock on a new extreme"
   rule, same three-way status split), with every inequality mirrored:
   `high <= zone_price` (continue) / `high - zone_price` (depth) /
   `close < zone_price` (reclaim), using the SAME imported
   `SWEEP_DEPTH_MIN_ATR`/`SWEEP_DEPTH_MAX_ATR`/`RECLAIM_WINDOW_CANDLES`
   constants.
2. **`poc.resolution._stop_target_event` cannot be called for Study B.**
   Its own body checks `lows <= stop_price` for a stop hit and
   `highs >= target_price` for a target hit -- hard-coded to a stop BELOW
   entry and a target ABOVE entry (the long convention). Study B's stop
   sits ABOVE entry and its targets sit BELOW entry; calling the existing
   function with Study B's own stop/target values would check the wrong
   side of every bar. **A new `_stop_target_event_short` is required**,
   mirroring the same "scan from the fill bar through 15:19, same-bar tie
   goes to the stop" structure, with the two masks flipped: `highs >=
   stop_price` for STOP, `lows <= target_price` for TARGET.
3. **`poc.resolution.resolve_exit` cannot be called for Study B's qty=1
   path**, for the same reason as (2) -- it calls `_stop_target_event`
   internally and its own gap-aware stop-fill line (`bar["open"] <=
   stop_price`) assumes a stop below entry. **A new `resolve_exit_short`
   is required**, built the same way Study A's own `resolve_scaled_exit_a`
   was built -- by composition around the new `_stop_target_event_short`,
   never a parallel tie-break implementation -- reusing
   `liquidity.a._time_exit_candle` unchanged for its own TIME_EXIT branch.
4. **The STT asymmetry (preregistered instruction, Section 6 below)
   means Study A's own `three_order_cost_rs` cannot be called either** --
   it assumes the entry leg is a BUY (`buy_leg_cost_rs`, no STT) and every
   exit leg is a SELL (`sell_leg_cost_rs`, STT applied). Study B's entry
   is a SELL (to open) and every exit leg is a BUY (to cover) -- the
   roles are swapped, not merely relabeled, so a new `three_order_cost_
   rs_b` composing the SAME two `swing.costs` functions in the opposite
   assignment is required.

**New code, lives entirely in `src/liquidity/b.py`**: `find_sweep_short`,
`find_reclaim_short`, `_stop_target_event_short`, `resolve_exit_short`
(items 1-3 above), `find_confluence_zone_b` (Section 2, HIGH-level
mirror with the opposite tie-break direction), `find_entry_b` (Section 3
orchestration), `resolve_scaled_exit_b` (Section 4), the swapped-role cost
model (Section 6, item 4 above), sizing/orchestration/both nulls' pool
and draw functions (Sections 5, 7, 9), and a fresh sealed TEST-window
guard, pattern-identical to Study A's own but a separate object (Section
8).

## Section 1: level construction

**Identical to Study A's own Section 1, reused via
`liquidity.a._build_level_lookup_for_entity` unchanged** -- six candidate
levels per (entity, day), computed at 09:45 from data through the
PREVIOUS trading day only, on `fibo.daily_ohlc`'s entity-adjusted
`adjusted_high`/`adjusted_low` columns shifted by one row before any
rolling window:

| Level | Window | Trading days |
|---|---|---|
| 3-month high / low | rolling | 63 |
| 1-week high / low | rolling | 5 |
| 1-day high / low | single day | previous trading day |

A day whose `hi_3m` (the binding window for the HIGH side, same role as
Study A's own `lo_3m` check) is still NaN is skipped as
`level_insufficient_history`.

**Only HIGH levels matter for Study B, since this is short only.** The
three LOW levels are present in the same lookup dict (Study A already
uses them) but are not read by anything in this module.

## Section 2: confluence zone -- HIGH levels, opposite tie-break direction

**CONFLUENCE ZONE: two or more HIGH levels within 0.5 x ATR(14) of each
other.** Implemented in `find_confluence_zone_b` as the same
connected-components-over-an-adjacency-graph structure as Study A's own
`find_confluence_zone`, applied to `{"3m": hi_3m_raw, "1w": hi_1w_raw,
"1d": hi_1d_raw}` instead of the LOW dict. A zone is any connected
component of size >= 2; the zone's reference price is the mean of its own
members -- identical rule, identical "all three mutually within
tolerance -> one zone of 3" behavior.

**"If multiple separate clusters exist, take the one NEAREST ABOVE the
previous close"** -- the mirror image of Study A's own "nearest below."
Among components whose own mean price is `>= prev_close_raw`, take the
one with the SMALLEST such price (closest to the previous close from
above); if no component qualifies (every component's mean sits below
`prev_close_raw`), fall back to the MINIMUM price among all components --
the exact mirror of Study A's own fallback-to-maximum, flipped in the
same two places (`<=`->`>=`, `max`->`min` for the qualifying branch;
`max(...)` ->`min(...)` for the fallback).

**Proved structurally unreachable, by the identical argument Study A's
own Section 2 made for lows**, restated here for highs rather than
re-derived from scratch because the proof is purely about graph
structure, not about which values populate the three nodes: with exactly
three candidate HIGH levels, any two qualifying edges necessarily share a
node (there are only 3 possible node-pairs among 3 nodes), so the edge set
can produce at most ONE connected component of size >= 2. The
"multiple clusters" branch is still coded, for the same defensive-
correctness reason Study A gave, and is predicted -- and will be confirmed
in the Section 11 report exactly as Study A's own `multi_cluster_count`
was -- to execute zero times.

If no two HIGH levels cluster: `NO_CONFLUENCE`, the day is skipped.

## Section 3: entry -- new direction-aware sweep/reclaim, not V4's own functions

**SWEEP** (`find_sweep_short`, new -- see Section 0 item 1): the first
5-minute candle at or after 09:45 whose HIGH sits 0.1x-1.0x ATR(14) ABOVE
the confluence zone price (`SWEEP_DEPTH_MIN_ATR`/`MAX_ATR`, imported from
`poc.v4` unchanged). Shallower -> `TOUCH_TOO_SHALLOW` (keep watching);
deeper -> `BREAKOUT_NOT_SWEEP` (abandon the day -- the mirror name of
Study A's own `BREAKDOWN_NOT_SWEEP`, since what is abandoned here is a
genuine breakOUT through resistance, not a breakDOWN through support).

**RECLAIM** (`find_reclaim_short`, new -- see Section 0 item 1): within
the next 3 five-minute candles (`RECLAIM_WINDOW_CANDLES`, imported
unchanged; clock never resets on a new high, which only updates the
running `sweep_high` -- same "later box" precedent Study A's own
Section 3 cites from V4), a candle must CLOSE BELOW the confluence zone
price. None does -> `NOT_RECLAIMED`.

**ENTRY**: SHORT at the open of the next 1-minute bar after the
reclaiming candle's own close (`fill_bar_after_candle_close`, unchanged).
Window 09:45-14:30. One trade per stock per day, same per-day evaluation
loop structure as Study A. `STOP = final sweep_high + 0.1 x ATR`
(`STOP_BUFFER_ATR`, imported from `poc.v4` unchanged, now ADDED rather
than subtracted since the stop sits above entry for a short).

Guards, in order, mirroring Study A's own formulas with the inequality
flipped to match a stop above entry:
- `entry_price >= stop_price` -> `ENTRY_ABOVE_STOP` (the mirror of Study
  A's own `ENTRY_BELOW_STOP`; Study A found this guard fired ZERO times
  in its own DEV run, since its own sweep/reclaim geometry made it
  structurally near-impossible for the fill to land on the wrong side of
  the stop -- the identical geometry argument applies here by symmetry:
  the fill happens after price reclaims back BELOW the zone, while the
  stop sits ABOVE the zone by construction, so `entry_price < zone_price
  < stop_price` should hold on every `ENTERED` trade. Predicted to also
  fire zero times, confirmed empirically in Section 11, not assumed.)
- `(stop - entry)/entry > 0.05` -> `STOP_TOO_WIDE`
- `(stop - entry)/entry < 0.005` -> `STOP_TOO_TIGHT`

## Section 4: exits, scaled -- mirrored risk multiples, new direction-aware resolution

`R = stop - entry` (always positive for a short, the mirror of Study A's
`entry - stop`). `HALF_TARGET = entry - 1.5R` (50% of position, COVER
below entry). `FULL_TARGET = entry - 3.0R` (remainder, COVER further
below). `TIME_EXIT` = 15:15 candle close, via `liquidity.a._time_exit_
candle`, reused unchanged (Section 0).

**Resolution is built from exactly two calls to the new
`_stop_target_event_short`** (Section 0 item 2), in the identical
two-phase structure as Study A's own `resolve_scaled_exit_a`:

1. Phase 1: `_stop_target_event_short(bars1, fill_ts, stop, HALF_TARGET)`.
   - Neither hit by 15:19 -> full position covers at the 15:15 close
     (`TIME_EXIT_FULL`).
   - `STOP` -> full position covers at the stop (gap-aware: the bar's own
     open if it already gapped through -- i.e. `open >= stop_price` --
     else the stop price itself) -- `STOP_NO_HALF`.
   - `TARGET` (half-target hit, i.e. price fell to `HALF_TARGET`) -> HALF
     EXIT: `floor(qty/2)` shares COVERED at `HALF_TARGET`, in this bar.
     Continue to phase 2.
2. Phase 2 (only reached after a half exit): `_stop_target_event_short`
   re-scanning from the SAME bar the half exit happened in, against
   `(stop, FULL_TARGET)`. Same same-bar-correctness argument Study A's
   own Section 4 made (phase 1 already proved this bar's high did not
   reach `stop`, since `TARGET` won there, not `STOP`; phase 2 checks this
   same bar's low against `FULL_TARGET` fresh) applies identically here.
   - Neither hit -> remainder covers at the 15:15 close --
     `HALF_THEN_TIME_EXIT`.
   - `STOP` -> remainder covers at the stop (same gap-aware rule) --
     `HALF_THEN_STOP`. The half's own realised profit is never clawed
     back.
   - `TARGET` -> remainder covers at `FULL_TARGET` -- `FULL_EXIT` (or
     `FULL_EXIT_SAME_BAR` if same bar as the half exit).

**qty = 1** is the separate, simpler path, exactly as in Study A: no half
exit is possible, so the new `resolve_exit_short` (Section 0 item 3,
built by composition around `_stop_target_event_short`, mirroring
`poc.resolution.resolve_exit`'s own 2-level stop-vs-`FULL_TARGET`
structure and its TIME_EXIT branch) is called directly on the full
quantity. Outcomes relabelled `STOP_QTY1`/`TARGET_QTY1`/`TIME_EXIT_QTY1`,
same reason as Study A: keeping these out of `STOP_NO_HALF`'s own count
(a trade that DID have enough shares for a half exit but never reached
1.5R) per instruction.

## Section 5: sizing

Identical to Study A: `qty = floor(25000 / entry_price)` (`poc.v2.
CAPITAL_RS`, unchanged value). `qty < 1` -> `ZERO_QTY`, skipped, not
forced to 1 share -- same reasoning as Study A's own Section 5 (no stated
minimum-1-share floor for this study; counted and skipped rather than
silently assumed).

`half_qty = qty // 2`, `remainder_qty = qty - half_qty`. `qty == 1` routes
to the separate simpler path (Section 4) for the identical reason Study A
gives (a zero-share half-exit order would otherwise be attempted).

**`NO_ROOM` cannot occur, same structural argument as Study A's own
Section 5**: both `HALF_TARGET = entry - 1.5R` and `FULL_TARGET = entry -
3.0R` are risk-multiples computed FROM entry and a strictly-positive R
(guarded by `ENTRY_ABOVE_STOP` already having been checked and passed),
so both targets are always strictly LESS than entry by construction --
the short-side mirror of Study A's own "always strictly greater than
entry" fact. Stated here before any trade exists.

## Section 6: costs -- the STT asymmetry, modeled explicitly

Intraday cost model (`swing.costs.buy_leg_cost_rs`/`sell_leg_cost_rs`,
unchanged FORMULAS), plus the frozen Section 8c banded spread
(`box_theory.costs.BAND_SPREAD_BPS`, unchanged).

**The preregistered instruction's own asymmetry, stated precisely from
`swing.costs`'s own module docstring and code**: under the INTRADAY
model, STT (`STT_INTRADAY_SELL_BPS = 2.5`, i.e. 0.025%) is charged **ONLY
on the SELL leg**, via `sell_leg_cost_rs`; `buy_leg_cost_rs` charges NO
STT at all (the module's own comment: "No STT on the buy leg under
either order type"). For a LONG trade (Study A), the BUY is the entry and
every SELL is an exit -- so STT lands on the exit leg(s), split across up
to two legs whose own trade VALUE depends on where the exit actually
happened (profit or loss). **For a SHORT trade (Study B), the SELL is the
ENTRY (selling first, to open) and every BUY is an exit (covering)** -- so
STT lands ENTIRELY on the entry leg, computed on `qty * entry_price`, a
value that is FIXED and known at the moment of entry, never split and
never dependent on how the trade subsequently resolves.

**New cost functions, composing the SAME two `swing.costs` functions
Study A used, in swapped roles**:

```python
def _leg_cost_rs_b(trade_value_rs, band, is_entry_sell):
    half_spread_bps = BAND_SPREAD_BPS.get(band, 7.0) / 2.0
    fixed = (sell_leg_cost_rs(trade_value_rs, "INTRADAY") if is_entry_sell
             else buy_leg_cost_rs(trade_value_rs, "INTRADAY"))
    return fixed + trade_value_rs * half_spread_bps / 10_000

def three_order_cost_rs_b(entry_price, qty, legs, band):
    total = _leg_cost_rs_b(qty * entry_price, band, is_entry_sell=True)
    for leg in legs:
        total += _leg_cost_rs_b(leg["qty"] * leg["price"], band, is_entry_sell=False)
    return total
```

- ENTRY leg (SELL to open): `sell_leg_cost_rs(entry_value_rs, "INTRADAY")`
  + half the band's round-trip spread, on `entry_value_rs`.
- Each EXIT leg (half-cover, full/remainder-cover, or the single qty=1
  cover): `buy_leg_cost_rs(leg_value_rs, "INTRADAY")` + half the band's
  round-trip spread, on THAT leg's own value.

Same half-and-half spread-splitting convention as Study A, same
justification (the banded figures are round-trip; splitting evenly and
applying each half to its own leg's own actual value is the natural
generalisation to a 3-order trade).

`total_cost_rs = entry_leg_cost + sum(exit_leg_costs)`. `pnl_rs =
sum(leg_qty * (entry_price - leg_price))` for each leg (the short-side
mirror of Study A's `leg_price - entry_price`: profit accrues when a
cover happens BELOW entry). `net_return_pct = (pnl_rs - total_cost_rs) /
position_size_rs`, `position_size_rs = qty * entry_price` (entry value,
same convention as Study A).

**Extra cost vs. a hypothetical single exit at 3R**: identical to Study
A's own Section 6 figure, `hypothetical_cost_rs =
box_theory.costs.round_trip_cost_rs(entry_value_rs, band)` (Section 0 --
reused unchanged; the figure represents a generic two-order convention
and does not need a short-side variant). `extra_cost_rs = total_cost_rs -
hypothetical_cost_rs`, reported the same way (rupees, mean/sum, and as a
percentage of `position_size_rs`), and the **net STT difference against
Study A is reported explicitly in Section 11** -- see "what to report"
below.

**What the asymmetry predicts, stated before any result exists**: Study
A's own exit-leg STT varies trade-by-trade with the realised exit price
(a winning long's exit leg has a LARGER trade value than its entry, so
pays slightly MORE STT than a loss would; Study A's own Finding 1 showed
this effect was negligible in aggregate -- Rs 1.24/trade). Study B's own
entry-leg STT is FIXED at `entry_value_rs x 2.5bps` on every single
trade, with no dependence on outcome at all. The two are not expected to
differ by much in AGGREGATE magnitude (both are 0.025% applied to a
position-value-sized number, order Rs 0.5-1 per trade at this capital),
but Study B's figure should show essentially ZERO variance across trades
relative to position size, where Study A's own figure had a small amount
of variance driven by exit-price dispersion -- this is the kind of
"difference caused by STT falling on a different leg" the report is
asked to state plainly rather than smooth over.

## Section 7: universe and guards

Identical to Study A: point-in-time top 200 by turnover, annual
reconstitution (`poc.backtest.build_universe`, `TOP_N=200`, unchanged).
All lineage, same-ISIN, and scale guards reused unchanged. **No trend
filter**, same deliberate difference from the POC family Study A states --
`poc.trend.trend_filter_passes` is not imported or called here either.

## Section 8: windows

DEV: **2016-10-04 to 2022-12-31**. TEST (sealed): **2023-01-01 to
2026-09-18** -- identical dates to Study A. A fresh
`TestWindowViolationError`/`guard_date_range` pair, pattern-identical to
Study A's own but a SEPARATE object, own `ACCESS_LOG_PATH` at
`data/liquidity/b/test_window_access_log.txt` -- per this project's own
"a fresh instance, not a shared one" convention (Study A's own object is
never imported or reused for Study B's own guard calls).

## Section 9: nulls

Both nulls reuse `poc.nulls._random_fill`/`_valid_entry_idx` unchanged
(Section 0 -- confirmed direction-agnostic), and both apply the SAME
0.5%-minimum / 5%-maximum stop-distance guards to every draw, for the
identical reason Study A gives (a null whose own entry criteria differs
from the real strategy's criteria understates how much of the real
result the null can explain).

**TIMING**: restricted to the exact (entity, day) pairs the real
strategy traded. A random 5-minute candle in 09:45-14:30 replaces the
real sweep+reclaim signal. The real trade's own stop DISTANCE (now `stop_
price - entry_price`, always positive, the mirror of Study A's `entry -
stop`) and the real trade's own scaled-exit structure (1.5R half-target
BELOW the drawn entry, 3.0R full-target BELOW, same cost model) are
reused; only entry TIMING is randomized. `stop_price = entry_price +
ctx["stop_distance_rs"]` (ADDED, since the stop sits above a short's
entry) -- the one-line mirror of Study A's own `entry_price -
ctx["stop_distance_rs"]`.

**SELECTION**: random (entity, day) pairs from the same universe-year
population passing single-day eligibility, sufficient level history
(checked against `hi_3m`, the HIGH-side binding window, rather than
Study A's own `lo_3m`), and ATR availability -- matching the real
backtest's own gates, matched count per calendar month to the real
strategy's own trade count that month. Stop distance drawn as a
PERCENTAGE from the real strategy's own pooled `stop_distance_pct`
distribution (`rho_pool`, same V1-lineage convention Study A reused,
since this study's stop is not anchored to a single deterministic
day-level). `stop_price = entry_price * (1 + sampled_pct)` -- the stop
sits ABOVE entry by the sampled percentage, the mirror of Study A's own
`entry_price * (1 - sampled_pct)`. Half/full targets recomputed from the
drawn entry and sampled stop, same 1.5R/3.0R formula (below entry), same
cost model.

1000 seeds, or 500 with the usual timed-probe fallback -- identical
contingency to every prior study in this lineage.

## Section 10: gate

Identical structure to Study A: mean net return > 0, day-clustered 97.5%
bootstrap CI (Bonferroni for 2 configurations, unchanged machinery)
excluding zero; >= 95th percentile against BOTH nulls; still positive
after dropping the best year; positive within bands 1-100 alone. All four
required; anything else is NO EDGE, study closes, TEST is never read.

## Section 11: report -- the comparison against Study A is the point

Everything Study A reported (trades, distinct days, mean net return with
CI, median, both null percentiles, by year, by band, confluence-pair
breakdown, half/full-exit reach rates, extra-cost figure, skip counts,
peak concurrent positions/capital), **plus a direct side-by-side against
Study A's own named figures**:

- trade count against Study A's **8,131**
- mean net return against Study A's **-0.2841%**
- both null percentiles against Study A's **100th / 100th**
- fraction of trades reaching the half target, against Study A's **23%**
  (stated precisely in `LIQUIDITY_A_FINDINGS.md` as 21.6% of scaled-
  eligible trades reaching the half target, of which 23.1% went on to the
  full target -- the "23%" named in the task description is read as the
  second of these two figures, and BOTH are reported for Study B exactly
  as Study A reported them, not collapsed into one number)
- the confluence pair/triple breakdown, against Study A's **78.6% on
  1-day+1-week**
- the cost difference caused by STT falling on the entry leg rather than
  the exit leg(s) (Section 6's own prediction, confirmed or refuted with
  the actual numbers)

**State plainly whether the failure is symmetric** (same gate conditions
failing, same rough magnitude, same mechanism -- follow-through vs. cost
-- behind the failure), **and if the numbers differ materially, say so
rather than smoothing it into "both failed."** In particular: report
whether Study B's own confluence breakdown shows the same ~78.6%
1-day+1-week dominance Study A found (predicted to recur, per "THE
PRESERVED FLAW" above, but confirmed or refuted with the real number, not
assumed), and whether the follow-through-vs-cost diagnosis from Study A's
own Finding 1 (signal follow-through was the binding constraint, not
cost) also holds on the short side, where shorting fights the long-run
upward drift of equities and so might plausibly show WORSE follow-through
than Study A's own long-side number, not merely similar.

## Section 12: process

1. Write this document. Commit and push ALONE. Report the hash.
2. Synthetic unit tests for the new direction-aware logic (confluence
   clustering on highs, the new short-side scaled-exit resolution shapes)
   -- pure-function scenarios, no DB access, same discipline as Study A's
   own pre-Step-2 synthetic test, run before touching real data.
3. Five hand-traces before any aggregate, mirroring Study A's own five
   shapes exactly: one reaching the full 3R target, one stopping out
   before the half exit, one taking the half exit then stopping out on
   the remainder, one 15:15 time exit with the second half still open,
   one `NO_CONFLUENCE` skip. Show the six levels and which two (or three)
   HIGH levels clustered.
4. Run DEV only. Report. **STOP for approval before TEST.**

## Section 13: Claude's pre-committed prediction

I expect DEV to fail, mean net return between **-0.5% and 0%**. I expect
the trade count to be similar to Study A's own 8,131 (the same
definitional overlap -- a weekly high usually being one of that week's
own daily highs -- applies identically to highs, so I do not expect the
confluence filter to be meaningfully more or less selective on this
side), and the follow-through rate to be similar or slightly WORSE than
Study A's own 21.6%/23.1% figures, since shorting fights the long-run
upward drift of Indian equities over this DEV window the same way it
fights it everywhere else. **I was wrong about Study A's own mechanism --
I predicted costs and it was follow-through (`LIQUIDITY_A_FINDINGS.md`,
Finding 1) -- so this prediction is weighted accordingly**: if Study B
also fails, I expect it to again be a follow-through story rather than a
cost story, and I expect the STT-asymmetry effect sized in Section 6 to
again turn out to be a real but small (sub-0.01%-of-position) effect, not
the deciding factor.

## Section 14: discipline

All parameters FIXED for this trial. If DEV fails, this exact
parameterization (these three HIGH levels, this 0.5xATR tolerance, this
1.5R/3.0R split, this sizing) is not retried at other values. This
governs Study B only -- Study A's own closed result is unaffected, and a
future non-nesting-timeframe redefinition of the confluence filter
(Study C, "THE PRESERVED FLAW" above) is a different trial of the same
family, not a retry of this one.

## Status

Preregistration complete. Not yet committed. Next: commit alone, report
hash, then build `src/liquidity/b.py`, run the synthetic unit test, and
hand-trace 5 real DEV-window trades/skips.
