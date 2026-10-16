# Pre-registration: Box Theory intraday test (previous-session high/low reversal)

Frozen before any touch is counted, any trade is simulated, or any R value
exists, per this project's standing discipline (`PREREGISTRATION.md`,
`PREREGISTRATION_FIBO.md`, `PREREGISTRATION_SWING.md`,
`PREREGISTRATION_OPTIONS.md`, `PREREGISTRATION_PER_STOCK.md`). Nothing
below changes after this document is committed except by an explicit,
recorded amendment, made before the next result that amendment could have
been shaped by.

**Two statements that must travel with every result this study ever
reports, stated here before any result exists:**

1. **This is ONE mechanical interpretation of a discretionary idea the
   user described in conversation ("buy at the previous low with reversal
   candles, sell near the previous high"), reduced to fully specified,
   frozen rules below.** A human discretionary trader applying the same
   idea would use judgment this document cannot: which reversal candles
   look convincing, how much room is "enough," when a breakout looks
   likely to hold. Every one of those judgment calls has been replaced
   here with a fixed, mechanical rule (candle color, a fixed 0.995x
   arming threshold, a fixed 1% room floor) so the test is reproducible.
   **A pass or fail below is a statement about THIS VERSION ONLY** — it
   does not confirm or refute the broader discretionary idea, which this
   document cannot test.
2. **All 2016-2026 data in this project's archives has already been read
   by earlier projects** (Fibo, momentum, swing, per_stock, options). This
   hypothesis was not derived by looking at this data — it is a
   pre-existing discretionary idea the user described independently of
   any study in this repository — but there is **no genuinely untouched
   window** left to test it on, the same limitation `PREREGISTRATION_
   OPTIONS.md` and `FIBO_FINDINGS.md` Section 8's amended-cost re-test
   both already carry. **A DEV or TEST pass below is development
   evidence that justifies forward paper trading. It is never, on its
   own, a claim that this rule has genuine predictive validity** — that
   claim would require performance on data that did not exist when the
   rule was written, which no window in this archive can provide.

## 0. Scope, reuse boundaries, and the data-only guarantee

**New, separate module: `src/box_theory/`.** This study never modifies
Fibo (`src/fibo/`), momentum/per_stock-adjacent code (`src/per_stock/`),
swing (`src/swing/`), or options (`src/options_history/`, `src/options_
depth/`). It is data-only: it reads `data/warehouse.duckdb` and
`data/fibo_intraday.duckdb` read-only, and writes only to its own new
paths (`data/box_theory/...`). It never places, modifies, or cancels an
order.

**Reused, read-only, unmodified** (imported, never copied or re-derived):

- `fibo.universe.reconstitute_annually`, `effective_universe`,
  `restrict_to_universe`, `assert_universe_membership` — the exact same
  point-in-time, annually-reconstituted, trailing-median-turnover method
  the Fibo sealed test used, called with `top_n=200` instead of Fibo's
  `top_n=50` (the function already takes `top_n` as a parameter; no Fibo
  code changes). Membership for year Y is decided from year Y-1's own
  median daily turnover, ranked, held fixed all of year Y.
- `fibo.jump_guard.combined_unexplained_jump_dates` — the same combined
  lineage-jump (Bug #1) and same-ISIN-jump (Bug #11) exclusion set Fibo's
  own true-range computation uses. Applied here as a per-(entity, date)
  skip: any day on this set, for either D or D-1 (today's session or the
  session the box is drawn from), is excluded.
- `fibo.scale_probe.decide_scale_for_day`, `probe_scale`, `is_ex_date`,
  `ScaleDecision` — the empirical day-D raw-rupee scale factor for Angel
  One's intraday archive, measured from D-1's own HIGH/LOW agreement
  against bhavcopy, gap-guarded against an unflagged overnight event. See
  Section 2b below for exactly how this is applied to BOTH day D and the
  previous session's bars, which Fibo itself never needed to do (Fibo's
  own golden-zone levels come from the daily warehouse, not from Angel's
  own prior-day intraday bars).
- The **Section 8c frozen banded spread model** (`PREREGISTRATION_FIBO.md`
  Section 8c: round-trip spread/impact of 2.0 / 4.0 / 7.0 bps for bands
  1-50 / 51-100 / 101-200) combined with **`swing.costs`'s INTRADAY
  statutory + Groww fixed-fee formulas** (`buy_leg_cost_rs`, `sell_leg_
  cost_rs`, `order_type="INTRADAY"`) — the identical combination `scripts/
  fibo_test_amended_cost.py` already uses for Fibo's own amended re-test,
  reused here as a frozen cost model, not re-derived. Unranked (stub-year)
  entities use the band 101-200 figure, the same conservative convention
  that script applies.
- The **sealed test-window guard pattern** from `src/options_history/
  test_seal.py` — a raise-unless-authorized function with its own
  append-only access log, not a comment. Box theory gets its OWN copy
  (`src/box_theory/test_seal.py`) with its OWN window dates (Section 7
  below) and its OWN log path (`data/box_theory/test_window_access_log.
  txt`) — it does not import or share state with Fibo's or options'
  sealed windows, which are separate studies with separate boundaries.

**Not reused, written fresh in `src/box_theory/` because the mechanics
differ enough that reuse would mean bending someone else's rule, not
applying it**: 5-minute bar aggregation (Fibo's `aggregate_to_15min` is a
15-minute bucket for a different rule), the entry/stop/arming/exit state
machine (Fibo's `resolution.py` is a single-stop/single-target ORB rule;
this study's armed, candle-counted exit has no equivalent there), and the
holiday-aware previous-trading-day stepper (built on `data_layer.
nse_holidays.is_nse_holiday`, the same general-purpose NSE holiday master
every other live/backtest script in this project already reads — not
Fibo/swing/options-owned code).

## 1. The question

Does buying a stock after it touches the previous session's low and shows
mechanical reversal candles, then selling near the previous session's
high, produce positive net return after costs — and does it beat random
entry on the same stock-days? Two frozen, mechanical interpretations of
"shows reversal candles" are tested (FAST, SLOW; Section 3b); no others.

## 2. Universe and data

### 2a. Universe

Point-in-time **top 200 by trailing median turnover**, annually
reconstituted, `fibo.universe.reconstitute_annually(con, top_n=200)`
against `data/warehouse.duckdb` — identical method, identical warehouse,
only the `top_n` argument differs from Fibo's own sealed test.

**2016 stub year**, same gap Fibo documents and the same fix: the
warehouse has no 2015 data to rank 2016 against, so 2016 has no
reconstituted membership of its own. `effective_universe(universe,
stub_year=2016)` copies 2017's membership list onto 2016, the identical
convention Fibo's own download plan uses for its Oct-Dec 2016 stub. This
only matters here because DEV starts 2016-10-04 (Section 7) — the first
~3 months of DEV trade on 2017's membership list as a stated proxy, not a
silently-chosen one.

Every entity-day this study evaluates is passed through `restrict_to_
universe` and then checked with `assert_universe_membership` immediately
before simulation — the same filter-and-guard pair, not one fix per
script, Fibo's own `universe.py` module docstring already explains why
(BUGS.md Bug #11: a backtest that built its entity list from whatever the
archive happened to contain, not from the declared universe, silently
changed its own trade count on a rerun).

**Rank bands for reporting and for the Section 8c cost model**: 1-50,
51-100, 101-200, read off each entity-year's own `rank` column from
`reconstitute_annually`'s output.

### 2b. Data source, scale, and the previous-session box

**1-minute bars from `data/fibo_intraday.duckdb`'s `bars_1min` table**
(Angel One SmartAPI historical archive, 2016-10-04 to 2026-09-18 as of
this document, 386 distinct entities ever present, regular session only).
**Aggregated to 5-minute candles for every signal decision** (touch,
confirmation, arming, red-candle exit, time exit) — 1-minute bars are used
ONLY for the stop check (Section 3d) and for locating the exact fill
timestamp after a confirming candle closes. **No other interval is tried**
— this is one of the two pre-registered trials for this family (Section
10); trying 3-minute or 10-minute candles later would be a new trial
requiring its own pre-registration.

**Streamed per entity-year, never held fully in memory**: the archive is
~170M rows across its full history; this study's own per-entity-year read
(`WHERE entity_id = ? AND trade_date BETWEEN ? AND ?`) processes one
(entity, year) block at a time, aggregates to 5-minute candles, simulates
every candidate day in that block, and discards the 1-minute bars before
moving to the next block — the same bars-cache-per-entity-day pattern
`scripts/fibo_test_amended_cost.py` already uses, scoped tighter here
(per entity-year, not an unbounded cross-run cache) because this study's
own universe is 4x wider.

**PREV_HIGH / PREV_LOW** for day D = the MAX(high) / MIN(low) across the
previous trading session's own regular-session 1-minute bars, in RAW
scale. **"Previous trading session" is resolved in two independent steps,
both of which must pass, or the day is skipped as a bad previous session:**

1. **Calendar step**: `src/box_theory/holiday.py`'s `previous_nse_trading_
   day(D)` — a market-wide stepper (skip Saturday/Sunday, skip any date
   `data_layer.nse_holidays.is_nse_holiday` confirms) — computes which
   date D-1 is SUPPOSED to be, independent of what any one entity's
   archive actually contains. This is deliberately NOT `fibo.scale_probe.
   previous_trading_day` (that function returns entity E's own most recent
   `prices_eod` row before D, which could silently skip past a day E
   happened not to trade, masking exactly the Muhurat/gap case this rule
   needs to catch) — a different, market-wide question, answered by a
   fresh, small, box-theory-owned function built on the project's shared
   NSE holiday master, not by Fibo- or scale-probe-owned code.
2. **Archive step**: the calendar's D-1 must have **at least 350
   one-minute bars** for this entity in `bars_1min`. A regular 09:15-15:30
   session has ~375 one-minute bars; 350 is a floor below the ordinary
   count, not a tight one — chosen to pass an ordinary session with a few
   missing prints while failing a Muhurat day's ~60-bar token session or
   a day with a large archive gap. If the calendar's D-1 either has no
   `bars_1min` rows at all for this entity, or fewer than 350, the day is
   skipped — counted under the report's "bad previous session" reason.

**Same-scale requirement, resolved through the existing scale probe, not
a new mechanism**: `fibo.scale_probe.decide_scale_for_day(intraday_con,
warehouse_con, entity_id, D)` is called once per (entity, D). It is
anchored on D-1's own HIGH/LOW (Angel vs. bhavcopy) and D's own open vs.
D-1's bhav close — by construction, the single scale factor it returns
is "the raw-rupee multiplier that makes D-1's Angel bars agree with D-1's
confirmed bhavcopy, gap-checked against D's own open." Applying that SAME
factor to BOTH D-1's Angel bars (producing PREV_HIGH/PREV_LOW in raw
rupees) AND D's own Angel bars (producing D's touch/entry/stop/arming
prices in raw rupees) is exactly "same scale as day D," stated in code
rather than assumed: it is the one scale measurement that spans both
sessions already, reused instead of re-derived. If the decision is
`EX_DATE_SKIP`, the day is skipped under the report's "ex-date" reason
(an ex-date lies between D-1 and D, so no single scale factor is trusted
to span both). If it is `UNRESOLVED` or `GAP_GUARD_SKIP`, the day is
skipped under "bad previous session" (the scale link to the previous
session could not be verified) — four skip-reason buckets total (no
room, bad previous session, ex-date, jump guard), matching the report
spec exactly; UNRESOLVED/GAP_GUARD_SKIP are folded into "bad previous
session" rather than kept as a fifth bucket, stated here so the mapping
is explicit rather than discovered by reading the report.

**Jump guard**: `fibo.jump_guard.combined_unexplained_jump_dates(con)`
read once per run; if either D or D-1 is in an entity's flagged-date set,
the day is skipped under "jump guard."

## 3. Box, touch, and signal rules

### 3a. Touch

The **first 5-minute candle on day D whose low <= PREV_LOW**. Candles
are scanned in session order (floor-to-5-minute buckets anchored on
09:15, same anchoring convention as Fibo's 15-minute buckets, just a
5-minute bucket width). Only the FIRST touch of the day is ever
evaluated — if its confirmation path (3b-3c) fails to produce a valid
trade for any reason, no later touch that day is considered. This is the
stated reading of "one trade per stock per day, first qualifying signal
only": qualifying refers to the day's first touch, not the first touch
that happens to work out.

### 3b. Confirmation (FAST, SLOW — the only two configurations, both
pre-registered, no others)

Candle color: **green** = close > open; **red** = close < open (5-minute
candles, raw scale). A candle that closes exactly at its open is neither
and cannot serve as a confirming or exit candle in either direction.

Scanning forward from the candle immediately after the touch candle (the
touch candle's own color plays no role — confirmation must come strictly
after it, per instruction):

- **FAST**: the first green candle found, wherever it occurs relative to
  the touch candle (not required to be adjacent to it).
- **SLOW**: the first occurrence of **two consecutive green candles**
  (back-to-back 5-minute buckets, not necessarily adjacent to the touch
  candle), where the second candle's close is also above the first
  candle's close — the one extra condition the instruction states
  explicitly for SLOW and only for SLOW. No equivalent extra condition is
  applied to SLOW's exit-side red pair (Section 3e) — none was specified
  there, and this document does not invent one.

If the session ends with no qualifying confirmation found, there is no
trade that day (not a "skip reason" in the data-quality sense — a day
that genuinely never produced a signal, tracked separately in the report
as a diagnostic count, not one of the four skip-reason buckets).

### 3c. Entry fill and the room filter

Fill price = the **open of the next 1-minute bar after the confirming
candle (FAST: the single green candle; SLOW: the second of the two green
candles) closes.** Fill timestamp must fall in **09:30-14:30 inclusive**
(earliest/latest fill); a confirmation whose fill would land outside that
window produces no trade that day (same non-skip-reason diagnostic
bucket as "no confirmation found").

**Room filter**: skip (no trade) if `(PREV_HIGH - entry) / entry < 1.0%`
— evaluated once the fill price is known, using the PREV_HIGH computed
in Section 2b. Counted under the report's "no room" reason.

**Long only.**

### 3d. Stop

**3% below the entry fill price**, checked on **1-minute bars starting
with the entry bar itself** (the bar whose open IS the fill price) and
continuing forward. For each bar in order: if `low <= stop`, exit at the
stop price, or at that bar's open if the bar's open itself is below the
stop (a gap past the stop, which cannot be filled at the stop level).
**If the stop and any other exit trigger (armed red-candle exit, time
exit) fall in the same 1-minute bar, the STOP wins** — evaluated first,
every bar, before any other exit check for that bar is consulted.

### 3e. Arming and the red-candle exit

**Entry candle**, defined here precisely because the instruction's
"on or after the entry candle" needs one: the 5-minute candle whose
bucket contains the entry fill timestamp. Since the fill timestamp is
always the first 1-minute bar after the confirming candle(s) close, the
entry candle is, in practice, the 5-minute bucket that starts exactly
where the confirming candle(s) ended — the candle immediately following
confirmation. Arming is checked starting from this candle onward; candles
before it (including the touch and confirmation candles) are never
checked for arming, per instruction.

**Arming**: the position becomes armed the first time any 5-minute
candle (entry candle onward) has `high >= 0.995 x PREV_HIGH`. This is a
one-time latch — once armed, always armed for the rest of the trade; it
is never un-armed by price falling back below the threshold. Breaking
above PREV_HIGH outright needs no special handling, per instruction — the
position simply stays armed and continues toward the red-candle exit
rule below.

**Exit, once armed**: scanning forward from the arming candle (not
necessarily adjacent to it, same adjacency convention as 3b):
- **FAST**: the first red candle found. Exit at the open of the next
  1-minute bar after that candle closes.
- **SLOW**: the first occurrence of two consecutive red candles. Exit at
  the open of the next 1-minute bar after the second closes.

A candle can simultaneously be the arming candle and (if red) begin the
countable red-candle sequence — arming and exit-candle counting are
independent checks against the same candle stream, not mutually
exclusive.

### 3f. Time exit

If neither the stop nor an armed exit has triggered, the trade closes at
the **close of the 15:15 candle** (the 5-minute bucket starting 15:15,
covering 15:15-15:20) — this is deliberately NOT the session's actual
last candle (which would run to 15:30); the rule as given stops 10-15
minutes before the close, and this document applies it literally rather
than adjusting it toward the full session.

## 4. Sizing and costs

**Sizing**: fixed Rs 500 risk. `qty = floor(500 / (0.03 x entry))` —
3% of the entry fill price is the per-share risk, by construction of the
stop rule (3d). R = Rs 500 for every trade, by definition (not computed
from entry/stop the way Fibo's R is — here the stop distance is itself
defined as a fixed 3% of entry, so R is fixed by the sizing formula, not
measured after the fact).

**Costs** (`src/box_theory/costs.py`, raw-scale position values,
`swing.costs.buy_leg_cost_rs`/`sell_leg_cost_rs` with `order_type=
"INTRADAY"`, plus the Section 8c banded spread — see Section 0's reuse
note; this is the identical combination `scripts/fibo_test_amended_
cost.py` already applies, not a new formula):

```
cost_rs = buy_leg_cost_rs(position_size_rs, "INTRADAY")
        + sell_leg_cost_rs(position_size_rs, "INTRADAY")
        + position_size_rs * BAND_SPREAD_BPS[band] / 10_000
```
`BAND_SPREAD_BPS = {"1-50": 2.0, "51-100": 4.0, "101-200": 7.0,
"unranked": 7.0}`, `position_size_rs = qty * entry_price` (raw scale, via
the scale-probe-corrected prices of Section 2b).

**Net R** = `(pnl_rs - cost_rs) / 500`, where `pnl_rs = qty * (exit_price
- entry_price)`.

## 5. Inference plan

**Trades on the same day are correlated** (shared market conditions,
shared universe-wide moves) — inference is **day-clustered**: resample
whole trading days (not individual trades) with replacement, **10,000
bootstrap resamples**, for each configuration independently. A resampled
day carries every trade it produced into that resample (a 3-trade day
contributes 3 trades each time it is drawn).

- **Point estimate**: pooled mean net R across all trades in the real
  (unresampled) sample.
- **CI**: **97.5% two-sided**, Bonferroni-corrected for the 2
  configurations tested in this family (family-wise alpha 0.05, 2 tests,
  0.05/2 = 0.025 per test, i.e. the [1.25th, 98.75th] percentile of the
  10,000 resampled means) — a wider interval than an uncorrected 95% CI,
  by design, since two configurations are being evaluated against the
  same family-wise error budget.
- **No trade-level t-statistic is used as a gate anywhere in this study.**
- **Reported alongside, not used as a gate**: number of distinct trading
  days contributing at least one trade (the actual cluster count the
  bootstrap resamples from), and the **minimum detectable effect**,
  computed from the bootstrap standard error alone (`MDE = z x SE`, `z
  ≈ 2.2414` for a two-sided 97.5% interval, `SE` = the standard deviation
  of the 10,000 resampled means) — **never from the observed mean**,
  stated per instruction: this number answers "how big would a real
  effect have needed to be for this sample to detect it," not "how big
  is the effect we found."

## 6. Nulls

**Matched on NET R** (same cost model applied to every null draw, same as
the real strategy). **1000 seeds per null type** — before committing to
that figure, a small timed run (a handful of seeds) projects the full-
1000 runtime; **if the projection exceeds ~1 hour per null type, 500
seeds are used instead and stated as such in the report**, not silently
substituted.

- **TIMING null**: restricted to the exact stock-days the real strategy
  actually traded (for a given configuration). Entry at a random
  5-minute bar in 09:30-14:30 (uniform over that window's 5-minute
  buckets), same room rule (against that stock-day's own PREV_HIGH),
  same stop, same arming/exit/time-exit rules, same costs. Tests whether
  the DAY SELECTION (touch-and-reversal) carries value independent of
  intraday entry timing.
- **SELECTION null**: random stock-days drawn from the same universe-year
  population, **matched count per calendar month** to the real
  strategy's own per-month trade count (so the null's calendar
  composition mirrors the real sample, not a uniform draw across the
  whole window). Drawn from every day with a VALID box (Section 2b's
  previous-session/scale/jump-guard checks all pass) — **including days
  that never touched PREV_LOW**, per instruction, since the null is
  testing whether day SELECTION (touch-or-not) matters, not just entry
  timing. Random entry bar (same 09:30-14:30, 5-minute buckets), same
  room rule, same stop, same arming/exit/time-exit rules, same costs.
- **BASELINE (descriptive only, not fed into the percentile gate)**: buy
  at the 09:30 candle's open, sell at the 15:15 candle's close, every
  top-200 stock-day in the window, regardless of box validity, touch, or
  room — net of the same cost model, reported as a plain mean/median net
  return, labelled descriptive, giving a sense of what the universe did
  on an ordinary day without any signal at all.

**Reported**: the strategy's own mean net R expressed as a percentile
against the TIMING and SELECTION null distributions (10,000 — or 500-
seed-equivalent — means each), separately, per configuration, per window.

## 7. Windows and gates

**DEV**: 2016-10-04 to 2022-12-31 (the archive's own earliest available
date through end of 2022).

**TEST (sealed in code)**: 2023-01-01 to 2026-09-18 (the archive's own
latest available date), guarded by `src/box_theory/test_seal.py` —
raises `TestWindowViolationError` unless `authorize_test=True` is passed
explicitly, and logs every authorized access to `data/box_theory/
test_window_access_log.txt`. This is a NEW seal, independent of Fibo's
and options' own sealed windows — sharing no state, no log file, and no
authorization flag with either.

**A configuration PASSES only if ALL of the following hold:**

- **DEV**: mean net R > 0 with the day-clustered 97.5% CI excluding zero.
- **DEV**: mean net R's percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls.
- **DEV**: mean net R remains > 0 after dropping the single best calendar
  year (by that year's own mean net R) from the DEV sample.
- **DEV**: mean net R > 0 within rank bands 1-100 alone (bands 1-50 and
  51-100 combined, band 101-200 excluded from this one check) — added per
  instruction specifically because the Fibo result's profitability
  depended on thin, 101-200-band names; this study's pass bar requires
  the result NOT to depend on that same thin-name dependency.
- **TEST (read once)**: mean net R > 0 with the day-clustered 97.5% CI
  excluding zero, AND mean net R's percentile is >= 95th against both
  nulls, recomputed on the TEST window's own trades and its own null
  draws.

**Anything else = NO EDGE for that configuration. If both FAST and SLOW
fail DEV, the study closes at DEV — the sealed TEST window is never
read**, per the Process section below.

## 8. Report contents (per configuration, per window)

Trade count; distinct trading days; win rate; mean net R with its 97.5%
CI; median net R (labelled descriptive, not the test); exit-reason mix
(stop / armed red-candle exit / 15:15 time exit) and how many trades ever
reached armed status at all (vs. never arming and time-exiting
unarmed); breakdown by calendar year; breakdown by rank band; peak and
median concurrent open positions and peak deployed capital (each position
sized at roughly Rs 16,700 — `qty x entry`, since `qty = floor(500 /
(0.03 x entry))` implies `qty x entry ≈ 500/0.03 ≈ Rs 16,667`, before the
floor); skipped-day counts by the four reasons (no room, bad previous
session, ex-date, jump guard); and, as a diagnostic not a skip reason,
counts of touched-but-no-confirmation and confirmed-but-fill-outside-
window days.

## 9. Process, in this order, stopping where marked

1. Write this document. **Commit and push it alone**, before any result
   exists anywhere in this study — no backtest code is written before
   this commit lands. Report the commit hash.
2. Build `src/box_theory/` and test it. **Trace 5 trades by hand before
   any aggregate number is computed**: one stop exit, one armed exit, one
   15:15 time exit, one gap-down touch at the open, one skipped for no
   room. Each trace shows: date, PREV_HIGH/PREV_LOW, the touch candle,
   the confirming candle(s), the fill, the stop, the exit, and the
   resulting net R.
3. Run **DEV only**. Report per Section 8, both configurations. **>>>
   STOP. The user approves before the sealed TEST window is read.**
4. Only after that approval: call `src/box_theory/test_seal.py` with
   `authorize_test=True`, read TEST once, report per Section 8.

## 10. Discipline

**Trial counter for this family = 2** (FAST, SLOW — both pre-registered
above, both counted against the same family-wise error budget in Section
5's Bonferroni correction). Any later variant — a different candle
interval, a different stop percentage, a different room threshold, a
different arming threshold, an added filter of any kind — is a **NEW
trial** requiring its own pre-registration and enlarging this family's
multiple-testing correction; it does not get folded into this document
after the fact. **No rule in this document changes after any number from
DEV or TEST has been seen.** If DEV fails for both configurations, the
study closes and is reported as closed — it is not rescued by a variant,
a different interval, or a relaxed threshold. **Bad results are reported
in the first sentence of whatever reports them**, not buried after a
methods recap.

## Status

**>>> STOPPING HERE, per Process Step 1.** No backtest code exists yet.
This document is being committed alone, before `src/box_theory/` is
written, so Step 2's build and Step 3's DEV run cannot have shaped
anything written above.
