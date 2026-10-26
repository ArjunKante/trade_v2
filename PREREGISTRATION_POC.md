# Pre-registration: POC (point of control) bounce, intraday, 5-minute candles

Frozen before any touch is counted, any trade is simulated, or any R value
exists, per this project's standing discipline (`PREREGISTRATION.md` and
family, including `PREREGISTRATION_BOX.md`/`PREREGISTRATION_BOX_V2.md`/
`PREREGISTRATION_FVG.md`/`PREREGISTRATION_DARVAS.md`). Nothing below
changes after this document is committed except by an explicit, recorded
amendment, made before the next result that amendment could have been
shaped by.

## Provenance -- stated plainly, as instructed

**This hypothesis comes from the user, based on volume-profile trading
material, not from academic literature.** It is not a replication of a
published factor or a peer-reviewed finding; it is a specific, fully
operationalized reading of a popular retail-trading concept (price reverts
to, or holds, the session's highest-volume price level), written down here
precisely enough to be run exactly once without ambiguity.

**This is a NEW family, trial count 1.** It shares no code, no trial
counter, and no Bonferroni correction with any prior study in this
project. The day-clustered bootstrap's 97.5% two-sided CI
(`box_theory.inference.day_clustered_bootstrap`, reused unchanged -- see
Section 0) is documented, in its own module docstring, as built for
exactly 2 pre-registered configurations; this study runs only ONE
configuration, so reusing that interval is, if anything, slightly
conservative for a 1-trial family -- stated here, the same way
`PREREGISTRATION_DARVAS.md` Section 0 already states it for its own reuse
of this module, so it is not mistaken for an unexplained correction being
smuggled in.

**Base rate, stated up front as instructed**: `box_theory` V1 and V2, FVG,
the IPO listing study, the per-stock weekly study, and Darvas Box theory
have ALL closed with NO EDGE in this project. Several of those closures
were driven by the strategy's OWN TIMING null (a random entry on the same
day beat the strategy's own signal) rather than by a negative mean return
outright. This study is structurally similar to that losing pattern: a
price level derived from recent history (here, a proxy volume-weighted
level instead of a prior high/low or a gap) plus a candle-pattern
confirmation rule layered on top of it. That structural similarity is not
evidence against this study by itself, but it is the honest prior this
study starts from, not a blank slate.

**All 2016-2026 data in this project's archives has already been read by
prior studies and the historical holdout is retired** (`FINDINGS.md`
Section 7, the same retirement `PREREGISTRATION_BOX.md`/`PREREGISTRATION_
FVG.md`/`PREREGISTRATION_IPO.md`/`PREREGISTRATION_DARVAS.md` already rely
on). Consequently **a DEV pass below is development evidence justifying
forward paper trading, never a validity claim** -- the same standing every
other non-IPO study's own DEV pass/fail carries here, not a stronger one.
The DEV/TEST split below (Section 10) is a forward-only discipline device,
not a claim of genuine-holdout cleanliness.

## DATA LIMITATION -- PROXY POC, stated up front, as instructed

**A true point of control needs volume broken down BY PRICE LEVEL within
a session. This project's intraday archive (`bars_1min` in `data/
fibo_intraday.duckdb`) does not have that** -- it has one volume figure
per 1-minute bar, not a trade-by-trade or level-by-level breakdown. Every
POC computed by this study is therefore a **PROXY POC**, built by
assigning each 1-minute bar's WHOLE volume to a single price bucket (the
bucket containing that bar's own typical price, Section 4) rather than
spreading it across every price the bar's range actually touched. **This
label -- PROXY POC -- is attached to every result this study produces**;
it is never reported as, or treated as equivalent to, a true volume-profile
POC computed from level-resolved trade or tick data. The bucket-width
parameter (Section 4) is this document's OWN filled choice, stated as such,
not sourced from any volume-profile text or reference implementation.

## 0. Scope and reuse boundaries

**New, separate module: `src/poc/`.** This study never modifies `src/
fibo/`, `src/box_theory/`, `src/fvg/`, `src/darvas/`, `src/ipo_listing/`,
`src/per_stock/`, or `src/swing/`. It is data-only: reads `data/warehouse.
duckdb` and `data/fibo_intraday.duckdb` read-only, writes only to its own
new paths (`data/poc/...`). It never places, modifies, or cancels an
order.

**Reused, read-only, unmodified** (imported, never copied or re-derived):

- `fibo.universe.reconstitute_annually(con, top_n=200)` / `effective_
  universe` / `restrict_to_universe` / `assert_universe_membership` -- the
  identical point-in-time, annually-reconstituted, trailing-median-
  turnover universe construction `box_theory.backtest.build_universe`
  already assembles, `top_n=200`, 2016 stub year copied from 2017
  (`effective_universe(universe, stub_year=2016)`).
- `fibo.scale_probe.probe_scale` / `passes_gap_guard` / `to_raw_scale` /
  `ScaleDecision` -- unchanged, the same per-day empirical scale
  resolution (D's RAW scale derived from D-1's bhavcopy-vs-Angel HIGH/LOW
  agreement, plus the 20%-gap guard on D's own converted open) every
  intraday study in this project already uses.
- `box_theory.holiday.previous_nse_trading_day` -- unchanged, the same
  market-wide NSE-trading-day stepper, called repeatedly (not just once)
  by this study's own multi-day lookback (Section 3) -- the only study so
  far in this project that needs to step back more than one day.
- `box_theory.universe_data.fetch_bhav_daily` / `fetch_ex_dates` /
  `fetch_bars_range` / `fetch_bars_single_day` -- unchanged, the same
  batched per-entity data-access helpers box theory and FVG both already
  reuse around `prices_eod`/`corporate_actions`/`bars_1min`.
- `box_theory.context.eligible_day_context` / `group_by_day` -- unchanged,
  called ONCE PER DAY needed (today, plus each of the 5 lookback days,
  plus each lookback day's own anchor day internally) rather than once per
  backtest-day, since this study is the first to need more than one day's
  worth of resolved RAW-scale bars per decision -- see Section 3 for why
  this is reuse, not a rewrite, of the exact same per-day pipeline.
- `box_theory.bars.aggregate_to_5min` -- unchanged. 09:45 is itself a
  5-minute-bucket boundary under the SAME 09:15-anchored flooring box
  theory's own 5-minute candles already use (09:15, 09:20, ... 09:45,
  ...), so no new bar-aggregation code is needed for this study's own
  "first 5-minute candle at or after 09:45" language.
- `fibo.daily_ohlc.build_daily_ohlc_panel` -- unchanged, the existing
  entity-adjusted daily OHLC panel, used ONLY for the 50-day SMA trend
  filter (Section 5) -- the one piece of this study that is explicitly a
  DAILY-bar rule layered on an otherwise fully intraday study, exactly
  the same daily-panel reuse `PREREGISTRATION_DARVAS.md` Section 1b
  already makes for its own, differently-defined trend filter.
- `fibo.jump_guard.combined_unexplained_jump_dates` -- unchanged, the same
  combined lineage-jump (Bug #1) and same-ISIN-jump (Bug #11) exclusion
  set every other daily/intraday study in this project already applies.
- `box_theory.costs.band_for_rank` / `round_trip_cost_rs` -- unchanged,
  the same INTRADAY statutory/Groww-fixed cost formula (`swing.costs.
  buy_leg_cost_rs`/`sell_leg_cost_rs`) plus the frozen `PREREGISTRATION_
  FIBO.md` Section 8c banded spread/impact model (2.0 / 4.0 / 7.0bps round
  trip for bands 1-50 / 51-100 / 101-200, unranked falling back to the
  101-200 figure) -- reused verbatim, on RAW-scale position values, per
  instruction.
- `box_theory.inference.day_clustered_bootstrap` / `excludes_zero` /
  `percentile_vs_null` -- unchanged, for the reason given in the
  Provenance section above.
- `data/box_theory/dev_baseline.pkl` -- **reused directly, not
  recomputed, as BASELINE only (not part of the gate)**. This study's own
  universe (top-200, annually reconstituted), DEV window (2016-10-04 to
  2022-12-31), and cost model (box theory's own INTRADAY + Section 8c
  bands) are IDENTICAL to box theory's own, which is exactly the
  condition under which instruction permits reuse without recomputation.
  Checked at the time of loading it (255,980 stock-days, mean net return
  -0.4262%, buy-09:30-open/sell-15:15-close, sized at box theory's OWN
  fixed-Rs-500-at-3%-stop convention -- **not this study's own sizing**,
  stated so the sizing mismatch is never mistaken for an oversight; it is
  why BASELINE is descriptive only and never fed into the Section 11
  gate).

**New in `src/poc/`, because nothing in this project computes a
proxy-volume POC, chains eligibility across multiple days, or confirms a
touch with a hammer candle**: the multi-day lookback eligibility wrapper
(`poc.context`, Section 3); PROXY POC / PREV_HIGH construction (`poc.poc`,
Section 4); the 50-day daily trend filter (`poc.trend`, Section 5); touch
and hammer/green confirmation, entry fill, and 1-minute-bar stop/target/
time-exit resolution (`poc.resolution`, Sections 6-8); this study's own
TIMING/SELECTION nulls adapted to this sizing (`poc.nulls`, Section 9);
and this study's own sealed-window guard (`poc.test_seal`), its own
window dates, its own log path, sharing no state with any other study's
seal.

## 1. Universe

Point-in-time top 200 by trailing median turnover, annually reconstituted,
identical to every other intraday study (`fibo.universe.
reconstitute_annually`, `top_n=200`, `effective_universe(stub_year=2016)`
copies 2017's membership onto 2016). A trade counts toward a given year's
results by its own ENTRY DATE's calendar year, filtered via
`restrict_to_universe` and guarded via `assert_universe_membership`,
identical convention to every other study here.

## 2. Data

1-minute bars from `data/fibo_intraday.duckdb` (`bars_1min`), Angel scale,
converted to RAW scale per day via `fibo.scale_probe`, exactly as box
theory/FVG already do. Daily bars from `data/warehouse.duckdb` via `fibo.
daily_ohlc.build_daily_ohlc_panel`, used only for the trend filter
(Section 5).

## 3. Multi-day lookback eligibility -- NEW, stated in full

**Nothing in this project, before this study, needed more than ONE prior
day's worth of resolved RAW-scale intraday bars for a single decision.**
`box_theory.context.eligible_day_context(day, ...)` resolves day `day`'s
OWN RAW scale from `day`'s own previous trading day (`box_theory.holiday.
previous_nse_trading_day(day)`) -- this study calls that exact function,
unmodified, **once per day needed**, not once per backtest-day, chained as
follows.

For a candidate "today" `T` (a trading day on which entry Section 6-8
logic might fire), define the five **lookback days** `L1..L5` by stepping
`previous_nse_trading_day` backward five times from `T`:
`L5 = previous_nse_trading_day(T)` (yesterday), `L4 = previous_nse_trading_
day(L5)`, ..., `L1 = previous_nse_trading_day(L4)` (five trading days
before `T`). **"The previous 5 TRADING DAYS, not including today"** is
read as exactly `{L1, L2, L3, L4, L5}`, market-wide trading days, per
instruction's own phrase.

`eligible_day_context` is called, in ascending date order, for each of
`L1, L2, L3, L4, L5, T` -- six calls, sharing the SAME per-entity
precomputed `day_groups`/`bhav`/`ex_dates`/`jump_dates`/`single_day_cache`/
`rank_lookup` structures `box_theory.backtest.evaluate_entity` already
builds once per entity (so a day outside the current streamed block, e.g.
`L1` falling in December when `T` is early January, is fetched via the
SAME `single_day_cache`/`fetch_bars_single_day` fallback box theory's own
`eligible_day_context` already implements for exactly this situation --
no new fallback code). Each call internally resolves THAT day's own RAW
scale from THAT day's own previous trading day (so `L1`'s own scale
anchor is the trading day before `L1`, one day further back than `L1`
itself, fetched the same way) -- this is six independent applications of
the one existing per-day pipeline, not a new eligibility definition.

**If ANY of the six calls returns a skip** (`jump_guard`, `ex_date`, or
`bad_previous_session`, per `eligible_day_context`'s own `SKIP_REASONS`),
the WHOLE six-day window is incomplete and `T` is skipped for POC purposes
entirely -- counted under a new, combined reason, **`LOOKBACK_
INCOMPLETE`**, with a breakdown by WHICH of the six relative days
(`L1`..`L5` or `T` itself) first failed and by which underlying
`eligible_day_context` reason, so this is not a single opaque bucket.
**No partial-window substitution is made** (a 4-day or 3-day POC is never
computed) -- per instruction's exact "previous 5 TRADING DAYS," read as a
requirement, not a target.

If all six pass, this wrapper returns: `T`'s own `day_raw` (RAW-scale
1-minute bars) and `candles5` (5-minute candles, from `aggregate_to_5min`,
reused unchanged), `T`'s own `band`/`rank`/`year` (from `T`'s own
`eligible_day_context` call -- the lookback days' own band/rank are
computed incidentally by the same call but never used, since banding is a
property of the TRADE's own entry day, not of the lookback window), and
the five lookback days' own `day_raw` frames, passed to Section 4.

## 4. PROXY POC and PREV_HIGH construction -- FROZEN

**Computed at 09:45 each trading day `T`, from `L1..L5`'s own `day_raw`
1-minute bars (RAW scale, Section 3) -- never from `T`'s own bars.**

**Reference price for bucket width**: `T`'s own 09:15 OPEN (`day_raw`'s
first 1-minute bar's own `open`, RAW scale) -- **our filled gap, stated
plainly**: instruction fixes bucket width as "0.25% of the stock's price
on the calculation day," and `T` (the day POC is being computed FOR) is
"the calculation day"; its own 09:15 open is the earliest price actually
recorded ON `T` itself, known before 09:45 and so introduces no lookahead
into the 09:45 computation that uses it only as a WIDTH parameter, never
as a price being bucketed. `BUCKET_WIDTH = 0.0025 * open_T_raw`.

**Bucketing**: for every 1-minute bar across `L1..L5` combined (RAW
scale), `typical_price = (high + low + close) / 3`, `bucket_index =
floor(typical_price / BUCKET_WIDTH)` (buckets anchored at price zero --
deterministic and origin-free, so no separate anchor choice is needed).
That bar's own `volume` is added in full to `bucket_index`'s running total
-- **the proxy step named in the DATA LIMITATION section**: one bar's
volume goes to exactly one bucket, never split across the bar's own
high-low range.

**POC**: the `bucket_index` with the largest summed volume across all of
`L1..L5`. **Tie-break**: the LOWER `bucket_index`, per instruction.
**`POC_PRICE`**: the winning bucket's own LOWER EDGE, `bucket_index *
BUCKET_WIDTH` -- **our filled gap, stated plainly**: instruction gives
POC as "the price bucket," not a single price, and every later rule
("low at or below the POC," "stop 0.5% below the POC") needs one number;
the lower edge is chosen for consistency with the tie-break rule already
specified (which also resolves toward the lower price), not because any
other representative point (midpoint, volume-weighted price within the
bucket) was tried and rejected.

**`PREV_HIGH`**: `MAX(high)` across every 1-minute bar in `L1..L5`
combined, RAW scale, per instruction verbatim.

## 5. Trend filter -- FROZEN

`adjusted_close[L5] > SMA(adjusted_close, 50)[L5]` (fibo.daily_ohlc's
entity-adjusted daily close, `min_periods=50` -- a day without 50 full
prior trading days of daily history cannot pass, **treated as a FAIL, not
a skip**, identical convention to `PREREGISTRATION_DARVAS.md` Section
1b). `L5` is `T`'s own immediately preceding trading day, per instruction
("the stock's daily close on the previous trading day"), already computed
in Section 3. If this fails, `T` is skipped under **`TREND_FILTER_
FAILED`** before any touch is ever sought -- POC/PREV_HIGH (Section 4) ARE
still computed first (needed for the SELECTION null's own pool, Section
9), but no entry logic runs for `T`.

## 6. Touch and confirmation -- FROZEN

**TOUCH**: scanning `T`'s own `candles5` restricted to `ts.time() >=
09:45` (09:45 is itself a 5-minute bucket start under `aggregate_to_5min`'s
09:15 anchor, so no special boundary handling is needed), the FIRST candle
with `low <= POC_PRICE`. `touch_idx` is its 0-based index into the full
`candles5` frame. No touch in `[09:45, 15:30)` -> **`NO_TOUCH`**.

**CONFIRMATION** is checked on up to two candidates, strictly in order,
starting at `touch_idx + 1`:

For a candidate candle `c`: `body = |close(c) - open(c)|`, `lower_wick =
min(open(c), close(c)) - low(c)`, `upper_wick = high(c) - max(open(c),
close(c))`, `full_range = high(c) - low(c)`.

1. **GREEN** (`close(c) > open(c)`) -> **ENTER**, confirming candle = `c`.
2. Else, **HAMMER test**:
   - If `body > 0`: hammer iff `lower_wick >= 2 * body` AND `upper_wick <=
     body`, per instruction verbatim.
   - If `body == 0` (a doji): **our filled edge case, exactly as
     instructed** -- the general test's "`lower_wick >= 2 x body`" is
     `lower_wick >= 0`, trivially always true, and would make every doji
     a hammer; instruction's own replacement is used as the COMPLETE test
     for this case (read as "only if X" meaning X alone decides it, not
     "X in addition to the general test's other half"): hammer iff
     `lower_wick >= 2 * full_range * 0.1` (= `0.2 * full_range`) **AND
     `full_range > 0`**.

     **AMENDMENT, recorded now, before any POC bucket, touch, or trade has
     been computed anywhere in this study (found while writing `src/poc/
     resolution.py`, the first code this study's build produced -- i.e.
     before any number this amendment could have been shaped by):** the
     `full_range > 0` guard above was missing from the original text. A
     truly FLAT bar (`open == high == low == close`, zero movement at
     all) also has `lower_wick == 0` and `full_range == 0`, so the
     doji-hammer test as originally written (`lower_wick >= 0.2 *
     full_range`) reduces to `0 >= 0`, which is vacuously TRUE -- it would
     classify a bar that did not move at all as a bullish hammer. That is
     the opposite of what a hammer is supposed to signal (a rejection of
     lower prices within the bar), so a zero-range bar is now explicitly
     excluded, never counted as a hammer.
   - If hammer: **ENTER**, confirming candle = `c`.
3. Else (not green, not a qualifying hammer): **our filled gap**, since
   instruction's remaining two branches are both phrased for a RED candle
   specifically (`close(c) < open(c)`) and do not name the third possible
   case, a non-hammer DOJI (`close(c) == open(c)`, which is also not RED):
   - **RED and `close(c) < POC_PRICE`**: the level has failed -- **`POC_
     FAILED`**, counted, no further candidate checked, `T` produces no
     trade.
   - **RED and `close(c) >= POC_PRICE`**, OR **a non-hammer DOJI** (which
     is neither green nor red, and so can never itself be "RED and close
     below POC_PRICE" -- it is treated as a non-event, exactly like a red
     candle that merely fails to close below the level): the setup stays
     live. If `c` was the FIRST candidate (`touch_idx + 1`), check the
     SECOND candidate (`touch_idx + 2`) by the same three-way test above.
     If `c` was already the SECOND candidate (or the first candidate does
     not exist -- touch fell on `candles5`'s own last row -- or the
     second candidate does not exist for the same reason), no third
     candidate is ever checked -- **`NO_CONFIRMATION`**.

## 7. Entry, stop, target, sizing -- FROZEN

**ENTRY FILL**: open of the next 1-minute bar whose `ts` equals the
confirming candle's own bucket-END timestamp (`box_theory.resolution.
fill_bar_after_candle_close`, reused unchanged, against `T`'s own
`day_raw`). **If no such bar exists** (the confirming candle is
`candles5`'s own last row) -- **`NO_FILL_BAR`**, same precedent box
theory/FVG already use for this exact edge case, no cross-day search.

**WINDOW**: the fill's own clock time must be in `[09:45, 14:30]`
inclusive, per instruction's "Window 09:45 to 14:30." Outside it --
**`FILL_OUTSIDE_WINDOW`**.

**STOP** = `POC_PRICE * (1 - 0.005)` (0.5% below POC, per instruction).

**AMENDMENT, recorded now, before any trade has been computed anywhere in
this study (found while running `src/poc/backtest.py` against real
DEV-window data, the first real data this study's build touched -- i.e.
before any number this amendment could have been shaped by):** neither
GREEN nor HAMMER (Section 6) requires the confirming candle to trade
anywhere near `POC_PRICE` -- a candle can be mechanically green (`close >
open`) or a hammer while both its open and close sit well BELOW
`POC_PRICE` (price kept falling after the touch, with only a small
intra-candle uptick or lower-wick rejection). When that happens, the
entry fill (Section 7, the NEXT bar's open after such a candle) can land
at or below STOP itself -- a non-positive or even negative per-share
risk, which the risk-bound filter below (written for "stop too WIDE")
does not catch: `(entry_price - STOP) / entry_price` is <= 0 in this
case, which is never `> 0.05`, so the check as originally written would
pass this case through into the sizing formula, which then divides by a
non-positive number. **New skip, checked FIRST, before the risk-bound
filter**: if `entry_price <= STOP`, skip, counted **`ENTRY_BELOW_STOP`**
-- a trade that would already be at or past its own stop at the moment of
entry is not a trade this strategy's own rules intended to take.

**Risk-bound filter**, now only ever reached with `entry_price > STOP`
guaranteed: skip, counted **`STOP_TOO_WIDE`**, if
`(entry_price - STOP) / entry_price > 0.05`.

**TARGET** = `PREV_HIGH * (1 - 0.02)` (2% below PREV_HIGH, per
instruction). Skip, counted **`NO_ROOM`**, if `TARGET <= entry_price`.

**SIZING**: `qty = floor(500 / (entry_price - STOP))`. **Our filled gap**,
same precedent as every fixed-risk study in this project (box theory,
Darvas, FVG): no minimum-1-share override is specified, so `qty < 1` is a
skip, counted **`ZERO_QTY`**, never forced to one share.

## 8. Resolution -- FROZEN

Scanning `T`'s own `day_raw` 1-minute bars from the entry fill bar onward
(inclusive), through the same `STOP_SCAN_END_TIME` = 15:19 cutoff box
theory/FVG already use: the first bar with `low <= STOP` or `high >=
TARGET`. **If both conditions are true within the same 1-minute bar, STOP
wins** (identical tie rule to `box_theory.resolution.resolve_exit` and
`fvg.resolution`'s own convention, per instruction verbatim: "If both the
stop and target are hit in the same 1-minute bar, the STOP wins").

**TIME EXIT**: if neither resolves by the cutoff, exit at the close of
`T`'s own 15:15 candle. **Fallback**, same precedent as box theory/FVG:
if the archive does not reach a candle exactly at 15:15 that day, the
latest available candle at or before 15:15 is used instead, and the
fallback is recorded (`time_exit_fallback`).

**Exit price**: STOP exits at the better of the triggering bar's own open
or the stop price itself (same convention as `box_theory.resolution.
resolve_exit`'s own STOP branch -- a bar that opens through the stop
cannot be assumed to fill exactly at the stop price); TARGET exits at the
TARGET price itself (the bar's own high only confirms the target was
touched, not that is the fill); TIME_EXIT exits at the 15:15 candle's own
close (or its fallback candle's close).

## 9. Sizing, costs, and net R -- FROZEN

**Costs**: `box_theory.costs.round_trip_cost_rs(position_size_rs, band)`,
unchanged -- INTRADAY statutory + Groww fixed costs (`swing.costs.
buy_leg_cost_rs`/`sell_leg_cost_rs`) plus the frozen Section 8c banded
spread (2.0 / 4.0 / 7.0bps by rank band 1-50 / 51-100 / 101-200, unranked
falls back to 101-200's figure), on RAW-scale `position_size_rs = qty *
entry_price`, per instruction.

**Net R** = `(pnl_rs - cost_rs) / 500.0` -- the nominal Rs 500 target is
the denominator throughout (identical convention to every fixed-risk study
in this project), not each trade's own realized `qty * (entry - STOP)`
(which is `<= 500` by construction of the floor in Section 7).

## 10. Nulls

**Both nulls below are restricted to the window being evaluated (DEV, then
later TEST) and share this study's own cost model and sizing formula from
Section 9.**

### TIMING null

Restricted to the exact `(entity_id, T)` pairs that produced a real entry.
For seed `s`, a random 5-minute candle is drawn (uniformly) from `T`'s own
`candles5`, restricted to `ts.time()` in `[09:45, 14:30]` -- per
instruction, "random entry 5-minute candle in 09:45-14:30." Entry fills at
that candle's own next-1-minute-bar open (`fill_bar_after_candle_close`,
same `NO_FILL_BAR` handling; a draw landing on `NO_FILL_BAR` or failing the
sizing/risk-bound checks below is retried with a fresh random candle, up
to 20 attempts, the same `MAX_ROOM_RETRY` convention `box_theory.nulls`
already uses, else this trade contributes no draw for this seed).

**Stop distance**: "same stop distance," read as the SAME RUPEE amount the
real trade used (`entry_real - STOP_real`), carried over unchanged:
`STOP_null = entry_null - (entry_real - STOP_real)`.

**Target**: "same ... target rule" -- **our filled gap, stated plainly**:
unlike this study's stop (an instructed rupee-distance carryover) the
target is a price LEVEL (2% below `PREV_HIGH`), not a distance from entry,
and `PREV_HIGH` is a property of `T`'s own lookback window (Section 4),
unchanged by which candle we pretend was entered on. `TARGET_null =
TARGET_real` -- the identical absolute price level the real trade used,
not re-derived relative to `entry_null`.

Same 1-minute-bar resolution mechanics (Section 8), same costs/sizing
(Section 9, re-applying the risk-bound/no-room/zero-qty checks to the
null's own `entry_null`/`STOP_null`/`TARGET_null`). 1000 seeds; a timed
20-seed probe decides, before the full run commits, whether 1000 is
affordable within roughly an hour -- if not, 500 seeds is substituted and
the substitution is stated at the time it happens, the same contingency
every prior study's own nulls use.

### SELECTION null

**Pool**: every `(entity, T)` pair, for every universe-year member, that
passes Section 3's six-day lookback-eligibility chain -- **INCLUDING days
that fail the trend filter (Section 5) or never touch the POC at all**,
per the same precedent `PREREGISTRATION_DARVAS.md`'s own SELECTION null
states explicitly for its own, differently-defined trend filter ("any
trading day for any that-year universe member -- no requirement that a
real box exist there"): the null's job is to test whether random entry
timing and a random-but-matched stop beat the strategy's signal, not to
replicate the strategy's own entry gates. Built and consumed ONE MONTH AT
A TIME (same streaming discipline `box_theory.nulls.build_month_pool`
already uses), matched count per calendar month to the real strategy's
own trade count that month.

Each pooled day also carries its own, genuinely computed `POC_PRICE` and
`PREV_HIGH` (Section 4 ran for every pooled day regardless of trend-filter
outcome, since POC/PREV_HIGH computation has no trend-filter dependency).

**Draw**: a random `(entity, T)` pair from that month's pool (with
replacement), entry = a random 5-minute candle in `[09:45, 14:30]` on that
day (same fill mechanic and retry-on-failure as the TIMING null above).

**Stop distance**: drawn (with replacement) from the REAL trades' own
pooled `(entry_price - STOP) / entry_price` distribution, per instruction
("stop distance from the strategy's own distribution"), applied
proportionally to the draw's own entry price: `STOP_null = entry_null *
(1 - sampled_pct)`.

**Target**: **our filled gap, stated plainly** -- instruction specifies
the stop distance's source but not the target's; rather than borrow some
OTHER trade's target (which would mix two unrelated days' price levels),
this null recomputes the target the SAME deterministic way a real trade
would, off the DRAWN day's own real `PREV_HIGH`: `TARGET_null = PREV_HIGH_
drawn_day * (1 - 0.02)` -- the natural, rule-following choice, not an
invented one, since `PREV_HIGH` requires no trend-filter pass to exist.

Same risk-bound/no-room/zero-qty checks, same resolution and cost model.
1000 seeds (500-seed fallback under the same timed-probe contingency).

### BASELINE (descriptive only, not part of the gate)

Reused directly from `data/box_theory/dev_baseline.pkl` (Section 0) --
stated as reuse in the report, not recomputed, with its sizing-convention
mismatch (box theory's own fixed-Rs-500-at-3%-stop, not this study's
POC-stop-distance sizing) stated alongside it, per instruction.

## 11. Inference and gate -- FROZEN

Day-clustered bootstrap (`box_theory.inference.day_clustered_bootstrap`,
unchanged, `trade_date = T`, 10,000 resamples, 97.5% two-sided CI).

**DEV PASSES only if ALL hold**:

- mean net R > 0 with the day-clustered 97.5% bootstrap CI excluding zero
- mean net R's percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls
- mean net R remains > 0 after dropping the single best calendar year (by
  that year's own mean net R) from the DEV sample
- mean net R > 0 within rank bands 1-100 alone (bands 1-50 and 51-100
  combined, band 101-200 excluded from this one check)

**Anything else = NO EDGE. The study closes; the sealed TEST window is
never read.** No partial credit for passing some but not all of the
above -- the same all-or-nothing standard every prior gate in this project
uses.

## 12. Windows

**DEV**: 2016-10-04 to 2022-12-31 (the intraday archive floor, identical
to box theory/FVG/Darvas's own intraday-archive-bound DEV window).
**TEST (sealed)**: 2023-01-01 to 2026-09-18 -- `poc.test_seal`, a new,
POC-only sealed-window guard instance (same mechanism as `box_theory.
test_seal`/`fvg.test_seal`/`darvas.test_seal`, same `authorize_test`
bypass shape, its own access log, **not** the same object or log file as
any of theirs). Not read unless DEV passes AND the user explicitly
approves.

## 13. Report contents

Trades, distinct entry days, win rate, mean net R with its 97.5% CI,
median net R (descriptive), MDE (from the bootstrap SE alone, never from
the observed mean), both null percentiles (with each null's own seed
count, and SELECTION's own matched count per month), breakdown by calendar
year (and the ex-best-year mean), breakdown by rank band, exit mix (STOP /
TARGET / TIME_EXIT, and `time_exit_fallback` count), peak concurrent
positions and peak deployed capital. **Skip/diagnostic breakdown**: days
skipped for `LOOKBACK_INCOMPLETE` (with its own sub-breakdown by which of
the six relative days and which underlying reason first failed),
`TREND_FILTER_FAILED`, `NO_TOUCH`, `POC_FAILED`, `NO_CONFIRMATION`,
`NO_FILL_BAR`, `FILL_OUTSIDE_WINDOW`, `ENTRY_BELOW_STOP`, `STOP_TOO_WIDE`,
`NO_ROOM`, `ZERO_QTY`. **The distribution of `(entry_price - POC_PRICE) / entry_
price`** across every real entry, per instruction, so how far above the
POC entries actually land is visible. BASELINE, stated as reused, shown
alongside but never contributing to `DEV_PASS`. **Bad results are
reported in the first sentence**, the same standing instruction every
prior study here follows.

## 14. Process, in this order, stopping where marked

1. Write this document. **Commit and push it alone**, before any POC
   bucket is computed, any touch is counted, or any trade exists anywhere
   in this study. Report the commit hash.
2. Build `src/poc/`. **Hand-trace 5 real DEV-window trades/skips before
   any aggregate number is computed**: one TARGET exit, one STOP exit,
   one TIME_EXIT, one `POC_FAILED` skip, one HAMMER confirmation
   (specifically NOT a plain green candle). Show the POC_PRICE
   calculation (which bucket won, and why), the touch candle, the
   confirming candle's own OHLC and why it qualified, the fill, the
   stop/target levels, and the resulting net R (or the reason for the
   skip). If the real DEV data does not happen to contain one of these
   five shapes, that is stated plainly rather than manufactured.
3. Run **DEV only** (real trades, then TIMING and SELECTION nulls, in that
   order), checkpointed at each stage, timing and memory measured before
   the long stages, from the start. Report per Section 13. **>>> STOP.
   The user approves before the sealed TEST window is read.**
4. Only after that approval: authorize `poc.test_seal`, read TEST once,
   report per Section 13.

## 15. Discipline

**Trial counter for this family = 1.** The 5-trading-day POC/PREV_HIGH
lookback, the 0.25% bucket width, the 50-day trend filter, the 0.5%
stop/2%-below-PREV_HIGH target, the 5% risk-bound, and the 2-candidate
confirmation window are all **FIXED** -- if DEV fails, none of them are
retried at other values, and no variant is folded into this document after
the fact; any such variant is a NEW trial requiring its own
pre-registration. **No rule in this document changes after any number
from DEV or TEST has been seen.** **Bad results are reported in the first
sentence** of whatever reports them, never buried after a methods recap.

## Status

**>>> STOPPING HERE, per Process Step 1.** No `src/poc/` code exists yet,
and no POC bucket, touch, trade, or R value has been computed anywhere in
this study. This document is being committed and pushed alone, before any
of that exists, so Step 2's hand-traces and Step 3's DEV run cannot have
shaped anything written above.
