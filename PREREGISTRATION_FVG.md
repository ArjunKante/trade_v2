# Pre-registration: Fair Value Gap (FVG), 1-hour candles, NSE stocks

Frozen before any touch is counted, any trade is simulated, or any R value
exists, per this project's standing discipline (`PREREGISTRATION.md` and
family, including `PREREGISTRATION_BOX.md`/`PREREGISTRATION_BOX_V2.md`).
Nothing below changes after this document is committed except by an
explicit, recorded amendment, made before the next result that amendment
could have been shaped by.

## Provenance -- stated plainly, as instructed

**This hypothesis comes from the user, based on ICT/smart-money trading
material, not from academic literature.** It is not a replication of a
published factor or a peer-reviewed finding; it is a specific, fully
operationalized reading of a popular retail-trading concept, written down
here precisely enough to be run exactly once without ambiguity.

**All 2016-2026 data has been read by prior studies and the historical
holdout is retired** (`FINDINGS.md` Section 7; the same retirement
`PREREGISTRATION_BOX.md`/`PREREGISTRATION_BOX_V2.md` and `PREREGISTRATION_
FIBO.md` already rely on). Consequently **a DEV pass below is development
evidence justifying forward paper trading, never a validity claim** -- the
same standing the box theory and Fibo studies' own DEV passes/fails carry,
not a stronger one. No sealed, never-before-touched holdout exists for
this dataset any more; the DEV/TEST split below is a forward-only
discipline device (TEST is read at most once, after DEV passes and after
explicit approval), not a claim of holdout cleanliness equivalent to a
genuinely unseen sample.

**Family trial count for FVG = 2** (Configuration A -- BREAKOUT, and
Configuration B -- RETEST, defined in Section 5). No third configuration
is pre-registered here, and the 97.5% two-sided CI used throughout
(`box_theory.inference`, reused unchanged -- see Section 7) is already
built as the Bonferroni-corrected bound for exactly 2 configurations, so
no further correction is layered on top of it.

## 0. Scope and reuse boundaries

**New code lives in `src/fvg/` only.** `src/box_theory/` and `src/fibo/`
are imported and reused **read-only, unmodified** -- neither study's own
closed result is touched. Specifically reused:

- `fibo.universe.reconstitute_annually` / `effective_universe` /
  `restrict_to_universe` / `assert_universe_membership` -- the identical
  point-in-time top-200-by-turnover, annually-reconstituted universe
  `box_theory.backtest.build_universe` already assembles, `top_n=200`,
  stub year 2016 copied from 2017. Not re-derived; `fvg.backtest.
  build_universe` is a byte-identical call to `box_theory.backtest.
  build_universe`'s own logic (same function names, same arguments),
  written fresh in `src/fvg/` only because Section 0 commits new code to
  `src/fvg/` and nothing is imported cross-study at the orchestration
  layer -- the underlying `fibo.universe` calls themselves are the actual
  reuse.
- `fibo.jump_guard.combined_unexplained_jump_dates`, `fibo.scale_probe.
  probe_scale` / `passes_gap_guard` / `to_raw_scale` -- unchanged, same
  per-day scale resolution and jump-guard exclusion box theory uses.
- `box_theory.holiday.previous_nse_trading_day` -- unchanged, reused
  directly for the backward-stepping half of day-eligibility (identical
  need: "what was the market-wide previous trading day," independent of
  any one entity's own archive).
- `box_theory.universe_data.fetch_bhav_daily` / `fetch_ex_dates` /
  `fetch_bars_range` / `fetch_bars_single_day` -- unchanged, the same
  batched per-entity data-access helpers box theory already built around
  `prices_eod`/`corporate_actions`/`bars_1min`.
- `box_theory.costs.band_for_rank` / `round_trip_cost_rs` -- unchanged,
  the same Section 8c banded spread model plus `swing.costs` INTRADAY
  statutory/fixed formulas.
- `box_theory.inference.day_clustered_bootstrap` / `percentile_vs_null` /
  `excludes_zero` -- unchanged. This module's own 97.5% two-sided CI is
  already documented, in its own docstring, as "Bonferroni-corrected for
  the 2 pre-registered configurations" -- which is exactly FVG's own
  family shape (Configuration A, Configuration B), so it is reused
  verbatim, not re-derived or re-split.
- `data/box_theory/dev_baseline.pkl` (box theory V1's own computed
  BASELINE: buy 09:30 open / sell 15:15 close, every eligible top-200 DEV
  stock-day, net of the same cost model) -- **reused directly, not
  recomputed**, because BASELINE depends only on the universe, the DEV
  window, and the cost model, and all three are identical between box
  theory and this study (same `TOP_N=200` reconstitution, same 2016-10-04
  to 2022-12-31 DEV window, same Section 8c + `swing.costs` cost model).
  The reuse is stated plainly in the report, per instruction, not
  silently re-presented as a new computation.

**New in `src/fvg/`, because nothing in box theory or Fibo does this
today**: 1-hour (not 5-minute) candle aggregation anchored to market open
(`fvg.bars`); a per-entity, per-day eligibility check structurally
parallel to `box_theory.context.eligible_day_context` but producing
1-hour candles instead of 5-minute ones (`fvg.context`) -- this is new
code, not an edit to `box_theory/context.py`, which stays untouched; a
forward-stepping NSE trading-day helper, the mirror image of `box_theory.
holiday.previous_nse_trading_day` (`fvg.holiday.next_nse_trading_day`),
needed for the 5-trading-day time exit and absent from box theory because
box theory never looks forward across days; FVG pattern detection,
gap-lifecycle/supersession tracking, and both configurations' entry/exit
mechanics (`fvg.patterns`, `fvg.resolution`); a new sizing formula (risk
is a rupee distance to `GAP_LOW`, not a fixed percentage of entry, so
`box_theory.resolution.position_size_shares` is not reused -- see Section
6); new TIMING/SELECTION nulls adapted to this sizing and to a
multi-day-forward trade lifecycle (`fvg.nulls`); a new sealed-window guard
instance, `fvg.test_seal`, with its own DEV/TEST dates (Section 9) --
**not shared with `box_theory.test_seal` or any Fibo seal**, per the same
reasoning `box_theory.test_seal`'s own docstring gives for not sharing
with Fibo's.

## 1. The question

Among NSE top-200 stocks, does a 1-hour-candle Fair Value Gap -- an
unfilled three-candle price void, entered either on a breakout close
above the gap or on a pullback retest of the gap followed by a breakout
close -- produce positive net return after costs, and does it beat random
entry on the same, or a comparably eligible, population of stock-days?

## 2. Universe and data

Point-in-time top-200 by trailing median turnover, annually
reconstituted, stub year 2016 copied from 2017 -- identical to
`PREREGISTRATION_BOX.md`/`PREREGISTRATION_BOX_V2.md` Section 2a, same
underlying code (`fibo.universe.reconstitute_annually`, `top_n=200`,
`effective_universe(stub_year=2016)`), filtered via `restrict_to_universe`
and guarded via `assert_universe_membership`.

1-minute bars from `data/fibo_intraday.duckdb` (confirmed present
2016-10-04 to 2026-09-18, 386 distinct entities across the full
reconstitution history), aggregated to **1-hour candles** for every
pattern/signal decision (Section 3). Per-day eligibility (jump guard,
ex-date, previous-session validity at the >=350-1-minute-bar floor, and
scale resolution onto RAW rupee scale) is the same four-check pipeline
`box_theory.context.eligible_day_context` runs, reimplemented in
`fvg.context.eligible_day_context` against the same primitives
(`fibo.scale_probe`, `box_theory.holiday`, `box_theory.universe_data`)
purely because it must aggregate to 1-hour candles instead of 5-minute
ones -- not a different eligibility standard. A day failing this check is
excluded from this entity's hourly timeline entirely, exactly as box
theory excludes it from evaluation.

## 3. Bar construction -- NEW, stated in full since nothing reuses this

**1-hour buckets are anchored to the market open (09:15), not to
midnight.** Unlike box theory's 5-minute buckets (which divide evenly
from a midnight floor because 09:15 already sits on a 5-minute boundary),
60 minutes does not divide the session this way: flooring from midnight
would produce a 09:00-10:00 first bucket (crossing the actual 09:15 open)
and would never produce a bucket boundary at 15:15 -- needed below for
the time-exit rule and for consistency with how NSE 1-hour charts are
conventionally built. Buckets are therefore `[09:15,10:15), [10:15,11:15),
[11:15,12:15), [12:15,13:15), [13:15,14:15), [14:15,15:15), [15:15,15:30)`
-- six full 60-minute candles plus **one partial 15-minute candle**
covering 15:15-15:30 (the archive's own last 1-minute bar is ts=15:29,
confirming the session is 09:15-15:30). **The partial 15:15 candle counts
as ONE candle, identically to every full-hour candle, for every counting
rule below** (the 30-candle live window, "subsequent candle," etc.) --
stated explicitly because "1-hour candles" could be misread as excluding
it, and the user's own common-rules language ("close of the 15:15 bar")
presupposes it is a distinct, addressable candle in exactly this scheme.

Each candle's bucket END timestamp is carried alongside its OHLCV (needed
because the last candle of a day closes at +15min, not +60min, so "the
next 1-minute bar after this candle closes" cannot assume a fixed
60-minute offset). `aggregate_to_1hour`, written fresh in `fvg/bars.py`
(not reusing `box_theory.bars.aggregate_to_5min`, which assumes a fixed
bucket width that would under-count the partial 15:15 bucket if divided
by 60 the same way), same floor-and-reduce vectorized technique as
`box_theory.bars.aggregate_to_5min`'s own profiled implementation.

**Per-entity continuous timeline**: unlike box theory, whose box pattern
and its full lifecycle resolve within one trading day, an FVG's 30-candle
live window and its up-to-5-trading-day holding period both span multiple
days. `fvg.context` therefore builds, per entity per streamed year-block,
an ordered list of **only its eligible days'** raw-scale 1-minute bars and
1-hour candles, concatenated in calendar order. **Ineligible days are
excised, not treated as a gap that pauses counting**: the 30-candle live
window and the "N candles forward" scans below simply continue into the
next eligible day as if the excluded day did not exist. This is a frozen
interpretation, recorded because the user's instructions do not address
it: the alternative (treating an excluded day as a width-consuming "blank"
candle, or as a hard break that kills the pattern) is not what either the
pattern definition or the live-window language implies, and excising
matches how box theory itself already treats an ineligible day -- as
absent from evaluation, not as a zero-signal placeholder. In practice this
is expected to matter rarely: box theory's own DEV run found 0 `jump_guard`
days and 70 `ex_date` days against 16,301 `bad_previous_session` days (a
PREVIOUS-day archive-depth problem that does not, by itself, make
"consecutive" eligible days topologically distant very often).

## 4. Pattern definition and lifecycle

On entity E's continuous 1-hour candle timeline (Section 3), scan EVERY
consecutive triple of candles `(i, i+1, i+2)` (a full sliding window, not
only non-overlapping triples -- the literal reading of "three consecutive
candles," which also lets one candle serve as, e.g., both candle 3 of one
candidate and candle 1 of the next):

**BULLISH FVG geometric test**: `high(i) < low(i+2)`. `GAP_LOW =
high(i)`, `GAP_HIGH = low(i+2)`, gap range `[GAP_LOW, GAP_HIGH]`.

**NO OVERNIGHT PATTERNS, checked second**: if `i`, `i+1`, `i+2` do not all
share the same `trade_date`, the candidate is **excluded and counted**
under `overnight_excluded` -- never evaluated further, regardless of how
cleanly it would otherwise qualify. Rationale, per instruction: NSE closes
overnight, so a gap one of whose three candles falls on a different
session is news/gap-driven, not the intraday structure this pattern
describes. This check runs against the GLOBAL continuous timeline
(Section 3), including across an excised ineligible day -- a triple
whose three candles' own `trade_date` values are not all equal is excluded
whether the skipped time in between was a weekend, holiday, or an
excised-ineligible trading day.

**VALIDITY FILTER (inside bar), checked third, same-session triples
only**: if `high(i+1) <= high(i)` AND `low(i+1) >= low(i)` (candle 2 is an
inside bar relative to candle 1), the pattern is **invalid and counted**
under `inside_bar_rejected` -- never evaluated further.

A triple surviving all three checks is a **valid gap**, keyed by
`(entity_id, candle1_idx, candle2_idx, candle3_idx)` in the entity's
global candle index space, formed at candle 3's own `trade_date` and bucket
end timestamp (`formed_at`).

**Live window**: the gap is live for the **30 candles immediately
following candle 3** in the global continuous timeline (global index
`candle3_idx+1` through `candle3_idx+30` inclusive), continuing across day
boundaries and across excised-ineligible-day gaps per Section 3. If
Configuration A's trigger (Section 5a) and/or Configuration B's trigger
(Section 5b) never fire within this window, the gap **expires unused**
for that configuration (`expired_unused`, tracked per configuration
separately, since A and B can resolve differently on the same gap).

**One trade per stock per gap; most-recent-gap-wins when gaps overlap**,
operationalized as explicit supersession, since the instruction states
the rule but not its mechanics: gaps for one entity are processed in
ascending order of `candle3_idx`. If gap G2 forms (survives the three
checks above) while an earlier gap G1 for the SAME entity is still
within its own live window and has not yet produced a trade (either
configuration) or otherwise resolved, **G1's live window is truncated to
end at `G2.candle3_idx - 1`** -- any entry that would only have triggered
at or after G2's formation is never evaluated for G1. If this truncation
is what causes G1 to produce no trade for a configuration (rather than a
genuine 30-candle timeout), it is counted under `superseded_by_newer_gap`
for that configuration, distinct from `expired_unused`. A trade already
triggered for G1 strictly before G2 forms stands unaffected. G2 itself is
evaluated on its own full, untruncated 30-candle window (it can only be
superseded by some later G3, not by G1).

## 5. Two configurations -- both frozen now, no others, run independently

Both configurations are evaluated against every valid, non-superseded gap
(Section 4). A single gap may produce a trade in A, in B, in both, or in
neither -- **the overlap count (both configurations entered on the same
gap) is reported explicitly** (Section 10).

### 5a. Configuration A -- BREAKOUT

Scan the live window (Section 4) in order for the first candle `k` with
`close(k) > GAP_HIGH`. If found: the **entry trigger candle** is `k`.
Entry fills at the open of the next 1-minute bar whose timestamp equals
candle `k`'s own bucket-end timestamp (`fvg.resolution.fill_bar_after_
close`, same mechanic as `box_theory.resolution.fill_bar_after_candle_
close`, applied to the entity's continuous 1-minute series). **If no such
1-minute bar exists** -- which happens only when `k` is a day's own last
(15:15-15:30) candle and the archive does not reach the next day's first
bar at that exact next-session timestamp, the same edge case box theory's
`find_entry` already handles via its own `NO_FILL_BAR` status -- the trade
is skipped and counted under `no_fill_bar`, **not** rolled forward to the
next session's open; no cross-day fill search is implemented, matching
box theory's own precedent exactly rather than inventing a new rule the
specification does not ask for.

No entry-time-of-day window is imposed (box theory's 09:30-14:30 ENTRY_
WINDOW exists for reasons specific to box theory's own room check; nothing
in this study's instructions calls for one, so none is added).

If no candle in the window closes above `GAP_HIGH`: `expired_unused` for
Configuration A (unless already `superseded_by_newer_gap`, Section 4).

### 5b. Configuration B -- RETEST

Scan the live window in order, maintaining two flags (`touched`,
`touch_idx`), evaluated candle by candle in chronological order:

1. **Invalidation, checked first at every candle**: if `close < GAP_LOW`
   (closes fully below the gap's own bottom), the gap is **invalidated**
   -- counted under `invalidated_before_retest` for Configuration B, and
   no further candles in the window are evaluated for B. This check runs
   whether or not the gap has been touched yet -- a close fully below
   `GAP_LOW` breaks the bullish gap thesis regardless of retest state.
2. **Touch**: if not yet touched and `low <= GAP_HIGH` (the candle's low
   enters the gap range from above), set `touched = True`,
   `touch_idx = this candle's position in the window`. The touch candle
   itself is never eligible to also be the confirming candle below (see
   "subsequent," next).
3. **Confirmation ("subsequent candle closes above GAP_HIGH")**: only
   evaluated once `touched` is True and only for a candle strictly after
   `touch_idx`: if `close > GAP_HIGH`, this is the **entry trigger
   candle**. Entry fills exactly as in 5a (next 1-minute bar at the
   trigger candle's bucket-end timestamp; same `no_fill_bar` handling,
   same no-entry-window policy).

If the window ends with no invalidation and no confirmation: `touched`
but never confirmed -> `expired_unused` for Configuration B; never
touched at all -> also `expired_unused` for Configuration B (both folded
into the one `expired_unused` counter per Section 10's "expired unused at
30 candles" line; `touched_never_confirmed` is additionally broken out in
the report so the two cases remain distinguishable).

## 6. Common rules -- stop, target, sizing, costs, time exit

**Stop = `GAP_LOW`.** **Target = `entry + 3 x (entry - GAP_LOW)`.**
Per-share risk is therefore the RUPEE distance `entry - GAP_LOW`, not a
fixed percentage of entry (box theory's `STOP_PCT=0.03` convention does
not apply here, and `box_theory.resolution.position_size_shares` -- which
hard-codes `stop_pct x entry_price` -- is accordingly not reused; `fvg.
resolution.position_size_shares(entry_price, gap_low)` is new code
computing `floor(500 / (entry_price - gap_low))` directly).

**0.5% floor, checked once the fill price is known**: skip (no trade,
counted under `stop_too_tight`) unless
`(entry_price - GAP_LOW) / entry_price >= 0.005`.

**Sizing**: `qty = floor(500 / (entry - GAP_LOW))`. `qty < 1` is skipped
and counted under `zero_qty` (same diagnostic box theory already tracks
for its own fixed-risk sizing, same reason -- a stop distance wide enough
relative to Rs 500 of risk that even one share would risk more).

**Resolution, on 1-minute bars, starting at the entry fill bar itself**:
scan forward from `fill_ts` for the first 1-minute bar whose `low <= stop`
or whose `high >= target`. **If both conditions are true within the same
1-minute bar, STOP wins** (identical tie rule to `box_theory.resolution.
resolve_exit`'s own STOP-wins convention). The scan's upper bound is the
time-exit cutoff below.

**Time exit**: let `entry_date` be the entry fill's own trade date.
`time_exit_date` = the 5th NSE trading day strictly after `entry_date`,
market-wide (`fvg.holiday.next_nse_trading_day`, stepped 5 times --
new code, the forward-stepping mirror of `box_theory.holiday.previous_
nse_trading_day`, same weekend/holiday-master stepping logic, same
fail-safe stance on an unverifiable weekday). If the stop/target scan
has not resolved by `time_exit_date`'s own 15:19 cutoff (same
`STOP_SCAN_END_TIME` convention as box theory, since the final partial
1-hour candle covers 15:15-15:30 and its own close is the time-exit
price), the trade exits at the **close of `time_exit_date`'s 15:15
candle** (the partial bucket's own close price). If the archive does not
reach a candle exactly at 15:15 that day, the same fallback box theory's
`resolve_exit` already implements applies: the latest available candle at
or before 15:15 is used instead, and the fallback is recorded
(`time_exit_fallback`).

**Monitoring-gap days**: while a trade is open, each subsequent calendar
day up to `time_exit_date` is independently scale-validated (Section 3's
same per-day check, re-run for THIS day specifically, independent of
whether it was used for pattern formation). A day that fails this check
contributes no bars to the scan -- a stop or target that might have
resolved intraday on that specific day cannot be detected and is not
retroactively inferred; the scan continues on the next validated day. The
count of such days per trade is recorded as `monitoring_gap_days` so its
(expected to be near-zero) frequency is visible, not silently absorbed.

**Costs**: identical combination box theory already uses --
`swing.costs` INTRADAY statutory/fixed formulas plus the frozen Section
8c banded spread model (`box_theory.costs.round_trip_cost_rs`, unchanged,
computed on RAW-scale position values).

**Long only. One trade per stock per gap** (a gap that already produced a
trade for a configuration is not re-evaluated for that configuration;
Section 4's supersession rule governs cross-gap overlap). Each
configuration is sized, resolved, and costed identically and
independently; a gap producing both an A and a B trade produces two
separate, independently-sized trade records.

## 7. Inference plan

Day-clustered bootstrap (`box_theory.inference.day_clustered_bootstrap`,
unchanged code, `trade_date` = the ENTRY fill's own trade date, since
that is the date whose cross-sectional correlation structure the
day-clustering is meant to capture): 10,000 resamples, pooled mean net R
per configuration. **97.5% two-sided CI** ([1.25th, 98.75th] percentile),
already Bonferroni-corrected for exactly 2 configurations by this
module's own construction (Section 0) -- run once per configuration, not
re-split further. MDE from the bootstrap SE alone (`MDE = 2.2414 x SE`),
never from the observed mean, same convention as box theory.

## 8. Nulls

Per configuration, same three comparisons box theory uses -- TIMING,
SELECTION, BASELINE -- adapted to this study's own sizing (Section 6) and
multi-day lifecycle:

- **TIMING null**: restricted to the exact `(entity_id, entry trade_date)`
  pairs the real strategy actually traded for that configuration. A
  random 1-hour candle on that SAME day replaces the real entry trigger;
  entry fills at that candle's own bucket-end next-1-minute-bar open (same
  `no_fill_bar` handling). **The stop distance is the SAME rupee amount
  the real trade used** (`entry_real - GAP_LOW_real`, carried over
  unchanged) -- so `stop_null = entry_null - (entry_real - GAP_LOW_real)`
  and `target_null = entry_null + 3 x (entry_real - GAP_LOW_real)` --
  and the same 5-trading-day time exit, same costs. Only the ENTRY TRIGGER
  is randomized; the risk amount, holding horizon, and cost model are
  identical to the real trade's own, per instruction ("same stop distance
  and 3R target").
- **SELECTION null**: random `(entity, day)` pairs drawn from the same
  universe-year eligible population `fvg.context.eligible_day_context`
  defines (every eligible day for every universe member that year,
  INCLUDING days that never formed or touched any gap), matched count per
  calendar month to the real strategy's own trade count that month, built
  and consumed one month at a time (same streaming discipline as
  `box_theory.nulls.build_month_pool`). Entry is a random 1-hour candle on
  the drawn day. **Stop distance is drawn (with replacement) from the real
  strategy's own empirical distribution of `(entry - GAP_LOW) / entry`**
  for that configuration, applied proportionally to the null draw's own
  entry price (`stop_null = entry_null x (1 - sampled_pct)`), 3R target,
  same 5-trading-day time exit and cost model.
- **BASELINE** (descriptive only, not part of the gate): reused directly
  from `data/box_theory/dev_baseline.pkl` (Section 0) -- stated as reuse
  in the report, not recomputed.

**1000 seeds per null type per configuration, timed and memory-measured
first, exactly as `PREREGISTRATION_BOX_V2.md` Section 6's own
contingency**: a small representative-slice run projects full-seed
runtime AND peak process memory (`psutil`, OS-tracked peak working set)
BEFORE either null's real stage commits to the full seed count. If 1000
seeds would exceed roughly an hour (per null, per configuration), 500
seeds are substituted and the substitution is logged -- never discovered
reactively partway through, per instruction.

## 9. Windows and gates

**DEV**: 2016-10-04 to 2022-12-31. **TEST (sealed)**: 2023-01-01 to
2026-09-18 -- `fvg.test_seal`, a new, FVG-only sealed-window guard
instance (same mechanism as `box_theory.test_seal`, same `authorize_test`
bypass shape, its own access log, **not** the same object or log file as
`box_theory.test_seal` or any Fibo seal). Not read unless DEV passes AND
the user explicitly approves.

**A CONFIGURATION PASSES DEV only if ALL hold** (evaluated independently
for A and for B):

- mean net R > 0 with the day-clustered 97.5% CI excluding zero
- mean net R's percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls
- mean net R remains > 0 after dropping the single best calendar year (by
  that year's own mean net R) from the DEV sample
- mean net R > 0 within rank bands 1-100 alone (bands 1-50 and 51-100
  combined, band 101-200 excluded from this one check)

**If both configurations fail, the study closes and the sealed TEST
window is never read.** If exactly one configuration passes, that
configuration alone may proceed to TEST (upon approval); the other closes
on its own DEV result, same as box theory's per-configuration-closure
precedent would imply if ever needed (V1's own two configurations both
failed together, so this exact split has not previously occurred in this
project, but the rule is stated here in case it does).

## 10. Report contents

**Per configuration** (A and B, separately): trade count, distinct entry
days, win rate, mean net R with 97.5% CI, median net R (descriptive), MDE,
TIMING null percentile, SELECTION null percentile (plus each null's seed
count and, for SELECTION, the matched count per month), mean net R by
calendar year (and the ex-best-year mean), mean net R by rank band, exit
mix (STOP / TARGET / TIME_EXIT counts), peak concurrent open positions and
peak capital deployed, and the skip/diagnostic breakdown: `expired_unused`
(split into never-touched vs. touched-but-unconfirmed for Configuration B
only), `invalidated_before_retest` (B only), `superseded_by_newer_gap`,
`no_fill_bar`, `zero_qty`, `stop_too_tight` (the 0.5% floor),
`monitoring_gap_days` (aggregate, across trades), and `time_exit_fallback`
count.

**Common to both configurations, reported once**: total valid gaps found
(post inside-bar and overnight filtering); `inside_bar_rejected` count;
`overnight_excluded` count; and the **A/B overlap count** -- the number of
gaps that produced a trade in BOTH configurations.

**DEV_PASS** reported per configuration, with the overall study
disposition (both fail / exactly one passes / both pass) stated plainly
in the first sentence of whatever reports it, per this project's standing
"bad results first" discipline.

## 11. Process, in this order, stopping where marked

1. Write this document. **Commit and push it alone**, before any FVG
   backtest code exists. Report the commit hash.
2. Build `src/fvg/`. **Hand-trace 5 real DEV-window trades/skips before
   any aggregate number is computed**: one Configuration A breakout
   entry, one Configuration B retest entry, one stop exit, one expired-
   unused gap (30 candles, no trigger), one inside-bar rejection. Show the
   three candles' own OHLC values, the gap range, the trigger candle, the
   fill, the stop/target levels, the exit, and the resulting net R (or the
   reason for rejection/expiry).
3. Run **DEV only**, after a pre-flight timing/memory measurement on a
   representative slice for each null. Report per Section 10.
   **>>> STOP. The user approves before the sealed TEST window is read.**
4. Only after that approval: authorize `fvg.test_seal`, read TEST once,
   report per Section 10.

Checkpointed in stages from the start (trades -> inference -> TIMING null
-> SELECTION null -> report), same discipline `box_theory_v2_dev_run.py`
was given from its own first run, per instruction here to use it "from
the start" rather than adding it reactively.

## 12. Discipline

**No rule in this document changes after any number from this study's own
DEV or TEST has been seen.** The 3:1 target multiple, the 30-candle
expiry, and the 0.5% stop-too-tight floor are FIXED by this document and
are not retried at other values if DEV fails -- per instruction, stated
here so it cannot be quietly revisited later. **Bad results are reported
in the first sentence** of whatever reports them, not buried after a
methods recap -- same standing instruction as every prior study in this
project.

## Status

**>>> STOPPING HERE, per Process Step 1.** No FVG backtest code exists
yet. This document is being committed and pushed alone, before `src/fvg/`
is written, so Step 2's hand-traces and Step 3's DEV run cannot have
shaped anything written above.
