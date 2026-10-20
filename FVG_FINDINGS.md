# Fair Value Gap (FVG) study: experiments log

Companion to `PREREGISTRATION_FVG.md` (frozen rules, commit `d0a343d`).
This file records what was actually run and found, in the order it
happened, per the preregistration's Process section.

**Provenance, repeated from the preregistration document and not
repeated again at each entry below**: this hypothesis is user-sourced
from ICT/smart-money trading material, not academic literature. The
2016-2026 historical holdout is already retired by prior studies
(`FINDINGS.md` Section 7), so a DEV pass below is development evidence
justifying forward paper trading, never a validity claim. Family trial
count = 2 (Configuration A, Configuration B).

## Step 2: hand-traced trades, before any aggregate number

Five real DEV-window cases, found by scanning real archive data for
entities in the 2017-2018 slice (`scripts/fvg_smoke.py`-style direct
calls into `fvg.context`/`fvg.patterns`/`fvg.resolution`), then
independently hand-checked against the raw candle values and the frozen
rules in `PREREGISTRATION_FVG.md` Sections 4-6. Costs/net R were cross-
checked against the REAL universe's own rank/band for each entity-year
(`fvg.backtest.build_universe`), not a placeholder -- both entities below
are rank <=50 ("1-50" band, 2.0bps) for 2017. All five check out exactly
against `fvg.backtest.run_backtest`'s own stored trade records.

### 1. Configuration A -- BREAKOUT entry, TARGET exit -- INE062A01020, 2017-01-16

Three gap-forming candles (global indices 71-73, all 2017-01-16):

| idx | ts | open | high | low | close |
|---|---|---|---|---|---|
| 71 (c1) | 10:15 | 252.55 | **253.35** | 252.25 | 252.80 |
| 72 (c2) | 11:15 | 252.80 | 254.25 | 252.40 | 253.80 |
| 73 (c3) | 12:15 | 253.80 | 254.70 | **253.60** | 253.95 |

FVG test: `high(c1)=253.35 < low(c3)=253.60` -- holds (a thin gap, range
0.25). Same-session: all three are 2017-01-16 -- passes. Inside-bar test
on c2: `high(c2)=254.25 <= high(c1)=253.35`? **False** -- not an inside
bar, gap is valid. `GAP_LOW=253.35`, `GAP_HIGH=253.60`.

Live window nominally [74, 103] (30 candles) but **truncated to [74,75]
by supersession** (a later gap forms at global idx 76's own c3, superseding
this one). Scanning [74,75] for the first close > 253.60: **candle 74**
(13:15, close=254.75) qualifies immediately -- `trigger_idx=74`.

Fill: candle 74's `bucket_end`=14:15. The 1-minute bar at ts=14:15 opens
at **254.65** -- entry. Room = (254.65-253.35)/254.65 = **0.5105%**,
just clearing the 0.5% floor. `qty = floor(500/(254.65-253.35)) =
floor(500/1.30) = 384`. Stop = 253.35. Target = 254.65 + 3x1.30 = **258.55**.

Exit: price gaps up overnight; the first 1-minute bar of 2017-01-17
(09:16) already has high >= 258.55 -- **TARGET**, exit_price=258.55 (the
cap, since that bar's open was below target). Entity is rank 2 for 2017
(band "1-50", 2.0bps spread). `pnl = 384 x (258.55-254.65) = Rs 1497.60`.
`position_size_rs = 384 x 254.65 = Rs 97,785.60`. `cost_rs =
round_trip_cost_rs(97785.60, "1-50") = Rs 101.2219`. `net_r =
(1497.60-101.2219)/500 = 2.792756` -- **matches `run_backtest`'s own
stored row exactly** (entity INE062A01020, trade_date 2017-01-16).

### 2. Configuration B -- RETEST entry, STOP exit -- INE062A01020, 2017-01-17

A second gap, formed from the SAME entity's candles 74-76 (global idx;
note candle 74 here is this gap's candle 1, the same physical candle that
was candle 3's breakout trigger for Case 1 above -- overlapping triples
are evaluated independently, per Section 4):

| idx | ts | open | high | low | close |
|---|---|---|---|---|---|
| 74 (c1) | 2017-01-16 13:15 | 253.90 | **255.35** | 253.85 | 254.75 |
| 75 (c2) | 2017-01-16 14:15 | 254.65 | 256.35 | 254.00 | 256.05 |
| 76 (c3) | 2017-01-16 15:15 | 256.00 | 256.40 | **255.75** | 255.75 |

FVG: `255.35 < 255.75` holds. Inside bar: `high(c2)=256.35<=255.35`?
False -- valid. `GAP_LOW=255.35`, `GAP_HIGH=255.75`. Live window truncated
by supersession to [77, 89].

Scanning forward: candle 77 (2017-01-17, 09:15) closes 258.00 -- NOT yet
touched (its low 257.30 never enters the gap), no invalidation. Candle 78
closes 256.90 (still above gap, no touch). **Candle 79** (11:15): low =
255.25 <= `GAP_HIGH`=255.75 -- **touch**, `touch_idx=79` (its own close,
255.50, does not confirm -- the touch candle can't also confirm, and
255.50 < 255.75 anyway). **Candle 80** (12:15): close = 257.00 >
255.75 -- confirms, strictly after the touch candle -- `trigger_idx=80`.

Fill: candle 80's `bucket_end`=13:15. 1-minute bar at 13:15 opens at
**257.00**. Room = (257.00-255.35)/257.00 = **0.642%**. `qty =
floor(500/1.65) = 303`. Stop=255.35. Target = 257.00+3x1.65 = **261.95**.

Exit: price drifts down through the 2017-01-17 afternoon (never close to
target); the 1-minute bar at **15:25** has low=255.15 <= stop (open of
that bar, 255.60, is above the stop level) -- **STOP**, exit_price=255.35
(the stop level, not that bar's open, per the tie convention). `pnl =
303 x (255.35-257.00) = -Rs 499.95`. `position_size_rs = Rs 77,871.00`.
`cost_rs = round_trip_cost_rs(77871.00, "1-50") = Rs 90.2200`. `net_r =
(-499.95-90.2200)/500 = -1.180340` -- **matches `run_backtest`'s own
stored row exactly**.

### 3. Configuration A -- STOP exit -- INE115A01026, 2017-01-30

| idx | ts | open | high | low | close |
|---|---|---|---|---|---|
| 134 (c1) | 10:15 | 553.00 | **553.40** | 551.50 | 552.80 |
| 135 (c2) | 11:15 | 552.95 | 563.00 | 552.75 | 559.90 |
| 136 (c3) | 12:15 | 559.90 | 561.95 | **557.40** | 558.60 |

FVG: `553.40 < 557.40` holds. Inside bar: `563.00 <= 553.40`? False --
valid. `GAP_LOW=553.40`, `GAP_HIGH=557.40`. Live window truncated to
[137, 152].

Candle 137 closes 556.20 (<=557.40, no trigger). **Candle 138** (14:15)
closes 559.65 > 557.40 -- `trigger_idx=138`. Fill: `bucket_end`=15:15,
1-minute bar opens at **559.65** (= the candle's own close, a thin last
hour). Room = (559.65-553.40)/559.65 = **1.117%**. `qty =
floor(500/6.25) = 80`. Stop=553.40. Target = 559.65+18.75 = **578.40**.

Exit: price fades through the rest of the day and into 2017-01-31;
stop (553.40) is finally breached at the **10:37** 1-minute bar (low
553.05, open 554.45 > stop) -- **STOP**, exit_price=553.40. Entity rank
39 for 2017 ("1-50" band). `pnl = 80 x (553.40-559.65) = -Rs 500.00`.
`position_size_rs = Rs 44,772.00`. `cost_rs =
round_trip_cost_rs(44772.00, "1-50") = Rs 71.9344`. `net_r =
(-500.00-71.9344)/500 = -1.143869` -- **matches `run_backtest`'s own
stored row exactly**. `time_exit_date` would have been 2017-02-06 (5 NSE
trading days after 2017-01-30) had the stop not fired first.

### 4. Expired unused (Configuration A, full 30-candle window) -- INE062A01020, 2017-02-22

| idx | ts | high | low | close |
|---|---|---|---|---|
| 252 (c1) | 2017-02-22 09:15 | **271.90** | 269.50 | 270.60 |
| 253 (c2) | 2017-02-22 10:15 | 274.50 | 270.55 | 273.60 |
| 254 (c3) | 2017-02-22 11:15 | 274.70 | **273.05** | 273.80 |

FVG: `271.90 < 273.05` holds. Inside bar: `274.50<=271.90`? False --
valid. `GAP_LOW=271.90`, `GAP_HIGH=273.05`. This gap is **not**
superseded (`superseded=False`), so its FULL 30-candle window applies:
global idx [255, 284], spanning 2017-02-22 through 2017-03-01.

The highest CLOSE anywhere in that 30-candle window is **272.60**
(candle 280, 2017-03-01 09:15) -- never exceeds `GAP_HIGH=273.05`. No
candle in the window ever closes above the gap. Configuration A:
**EXPIRED_UNUSED**, no entry, no trade. (For the record, Configuration B
would resolve differently on this same gap: the window touches the gap
range early (candle 255's low 272.00 <= 273.05) but candle 264 closes
270.15, below `GAP_LOW`=271.90 -- Configuration B would be
**INVALIDATED** on this gap, not expired. Both outcomes are legitimate
and independent, per Section 5's "a gap may produce a trade in A, in B,
in both, or in neither.")

### 5. Inside-bar rejection -- INE584A01023, 2018-08-07

| idx | ts | open | high | low | close |
|---|---|---|---|---|---|
| 2768 (c1) | 12:15 | 109.5549 | **113.3948** | **109.4050** | 112.2848 |
| 2769 (c2) | 13:15 | 112.2848 | **113.3048** | **111.6548** | 113.1848 |
| 2770 (c3) | 14:15 | 113.6048 | 115.2547 | **113.4548** | 113.5448 |

FVG test: `high(c1)=113.3948 < low(c3)=113.4548` -- holds, by a thin
0.0600 margin. Same session: all three 2018-08-07 -- passes. **Inside-bar
test on c2**: `high(c2)=113.3048 <= high(c1)=113.3948`? **True**.
`low(c2)=111.6548 >= low(c1)=109.4050`? **True**. Both hold -- candle 2 is
a genuine inside bar relative to candle 1 -- the pattern is **INVALID**,
counted under `inside_bar_rejected`, never evaluated by either
configuration, regardless of the otherwise-qualifying geometric gap.

**All five traces independently reproduce `fvg.backtest.run_backtest`'s
own stored trade rows exactly** (entry/stop/target/qty/exit/cost/net_r
for the three ENTERED cases; the correct non-entry classification for the
other two) -- cross-checked against the real universe's own rank/band
assignment, not a placeholder. No discrepancy found.

## Step 3: DEV result -- NO EDGE, both configurations. Study closes.

**Bad result, stated first, per discipline**: both configurations fail
DEV, decisively and on every criterion. Configuration A's mean net R is
**-0.1282** (97.5% CI [-0.1788, -0.0773] -- excludes zero, on the losing
side); Configuration B's is **-0.1693** (CI [-0.2193, -0.1195], same
losing side). Both TIMING-null percentiles are **0.0** (the real
strategy's mean underperforms every one of 500/1000 random-entry draws
on the same stock-days). Both SELECTION-null percentiles are far short
of the 95th-percentile bar (A: 14.3; B: 0.0). Both remain negative after
dropping each configuration's own single best calendar year (A:
-0.1524; B: -0.1982) and within bands 1-100 alone (A: -0.1164; B:
-0.1510). Per `PREREGISTRATION_FVG.md` Section 9, **the study closes at
DEV. The sealed TEST window is never read.**

### Performance notes, recorded because they shaped the run

Two real engineering problems were found and fixed via the
preregistration's own "measure memory and per-seed timing before the
long stages" discipline, before either null was allowed to commit to a
full seed count -- recorded here because they are part of what actually
happened, not polished away:

1. A first implementation of the TIMING null re-ran numpy-array
   extraction and timestamp construction inside the per-draw loop. A
   5-entity timed probe projected **~31 hours** for Configuration A's
   real 54,482-trade pool. Fixed by extracting every array and every
   per-day time-exit cutoff ONCE at pool-build time (the same fix
   `box_theory.nulls.prepare_ctx` already applies for box theory's own
   nulls) -- verified to produce numerically identical results, then
   re-measured at ~70 minutes projected for the full pool.
2. That fix's first version then sliced and copied a bounded window per
   TRADE rather than sharing one array per entity. The real pool's own
   preflight measurement put peak working set at **7.46 GB** on a
   machine with ~5.6 GB free of 15.7 GB total -- caught before
   committing, exactly as the discipline requires, and fixed by sharing
   one array per entity (never copied) and bounding each draw's scan via
   `np.searchsorted` instead of a physical slice, then batching the
   TIMING null by entity group (25/batch, accumulating (sum, count) per
   seed across batches, the same pooling principle the SELECTION null's
   own per-month accumulation already uses). Peak working set during the
   real run stayed under ~3 GB throughout both configurations.

Seed counts, decided by the preflight timing probe per PREREGISTRATION_
FVG.md Section 8's contingency: Configuration A's TIMING null and both
configurations' SELECTION nulls ran the full 1000 seeds; Configuration
B's TIMING null's probe projected over the 1-hour budget and fell back
to 500 seeds, logged at the time.

Total DEV run wall time: **51.7 minutes** for Stage 1 (the real
backtest, both configurations, full 200-stock universe, 2016-10-04 to
2022-12-31) plus **98.9 minutes** for inference and both nulls across
both configurations (after the fixes above) -- **~150 minutes total**,
fully checkpointed throughout (per-batch for TIMING, per-month for
SELECTION), surviving two unrelated background-process interruptions
without losing any completed work.

### Common counts (both configurations share the same gap population)

| | |
|---|---|
| Total valid gaps found | 109,766 |
| Inside-bar rejected | 5 |
| Overnight-excluded | 102,609 |
| A/B overlap (gaps trading in both configs) | 21,890 |
| `bad_previous_session` / `ex_date` / `jump_guard` skips | 16,301 / 70 / 0 |
| Day errors | 0 |
| BASELINE | **reused directly** from box theory's own `data/box_theory/dev_baseline.pkl` (mean net return -0.4262%, median -0.5059%, 255,980 stock-days) -- not recomputed, since BASELINE depends only on the universe, DEV window, and cost model, all identical here (stated per Section 0/8) |

**`bad_previous_session`/`ex_date`/`jump_guard` are IDENTICAL to box
theory's own DEV-window counts** (16,301 / 70 / 0) -- the same per-day
eligibility pipeline behaving identically for an unrelated study, not
independently re-derived; a sanity check that passed.

**Overnight-excluded (102,609) exceeds total valid gaps (109,766) by a
smaller margin than it first appears**: the sliding-window scan checks
every consecutive triple, including many that span a session boundary
by construction (the last one or two candles of a day paired with the
first one or two of the next) -- most such boundary-crossing triples
that happen to satisfy the bare geometric FVG test are exactly the
"overnight gap, not an intraday structure" case Section 4 excludes by
design, not a sign anything is wrong with the scan.

### Configuration A -- BREAKOUT

| | |
|---|---|
| Trades / distinct entry days | 54,482 / 1,533 |
| Win rate | 30.17% |
| Mean net R (97.5% CI) | **-0.1282** [-0.1788, -0.0773] |
| Median net R (descriptive) | -1.1245 |
| MDE | 0.0509 |
| TIMING null percentile | **0.0** (500 seeds -- preflight fell back from 1000, logged at the time) |
| SELECTION null percentile | **14.3** (1000 seeds) |
| Ex-best-year mean (drops 2020) | -0.1524 |
| Bands 1-100 mean | -0.1164 |
| Exit mix | STOP 36,287 (66.6%) / TARGET 12,038 (22.1%) / TIME_EXIT 6,157 (11.3%) |
| Peak concurrent positions / capital | 176 / Rs 64.63 lakh |
| Median concurrent positions (when >0) | 64 |
| Room-at-entry (fraction) | mean 1.71%, median 1.28%, p25 0.84%, p75 2.04%, max 29.1%, min 0.50% (floor) |
| Time-exit fallback count | 489 |
| Monitoring-gap days (aggregate) | 7,635 |
| **DEV_PASS** | **False** |

**By year (net R)**: 2016 -0.262 (1,686), 2017 -0.144 (7,570), 2018
-0.265 (8,441), 2019 -0.194 (8,409), **2020 -0.0154** (9,612 -- the best
year, barely less negative than breakeven), 2021 -0.0214 (9,152), 2022
-0.129 (9,612). **Negative in every single calendar year** -- there is
no good year propping this up; even the best year lost money.

**By band (net R)**: 1-50 -0.108 (14,810), 51-100 -0.125 (14,808),
101-200 -0.142 (24,864). Negative everywhere, mildly worse in the
thinner bands, no thin-band dependency that would explain the result.

**Skip/diagnostic breakdown**: `superseded_by_newer_gap` 26,275 (the
single largest reason -- gaps form often enough on the same entity that
a majority of candidates never get a full, untruncated window),
`stop_too_tight` 13,562 (the 0.5% floor is doing real, frequent work --
about one in six of all candidates that found a trigger candle (81,142
total) were rejected here), `no_fill_bar` 12,739 (the trigger candle was a day's own last
15:15-15:30 candle with no next-session bar at the exact next
timestamp), `expired_unused` 2,349, `zero_qty` 359.

### Configuration B -- RETEST

| | |
|---|---|
| Trades / distinct entry days | 28,801 / 1,532 |
| Win rate | 29.10% |
| Mean net R (97.5% CI) | **-0.1693** [-0.2193, -0.1195] |
| Median net R (descriptive) | -1.1247 |
| MDE | 0.0506 |
| TIMING null percentile | **0.0** (500 seeds -- preflight fell back from 1000) |
| SELECTION null percentile | **0.0** (1000 seeds) |
| Ex-best-year mean (drops 2020) | -0.1982 |
| Bands 1-100 mean | -0.1510 |
| Exit mix | STOP 19,449 (67.5%) / TARGET 5,952 (20.7%) / TIME_EXIT 3,400 (11.8%) |
| Peak concurrent positions / capital | 114 / Rs 36.22 lakh |
| Median concurrent positions (when >0) | 36 |
| Room-at-entry (fraction) | mean 1.72%, median 1.33%, p25 0.88%, p75 2.07%, max 29.1%, min 0.50% (floor) |
| Time-exit fallback count | 215 |
| Monitoring-gap days (aggregate) | 3,915 |
| Touched count | 28,801 of 28,801 (100% -- every B entry is, by construction, a touch-then-confirm) |
| **DEV_PASS** | **False** |

**By year (net R)**: 2016 -0.300 (860), 2017 -0.160 (4,112), 2018 -0.304
(4,525), 2019 -0.214 (4,468), **2020 -0.0255** (4,829 -- again the best
year, again barely short of breakeven), 2021 -0.128 (5,052), 2022 -0.173
(4,955). Also **negative in every single calendar year**.

**By band (net R)**: 1-50 -0.131 (7,783), 51-100 -0.171 (7,883), 101-200
-0.191 (13,135). Negative everywhere.

**Skip/diagnostic breakdown**: `invalidated_before_retest` 34,059 (the
single largest reason, and larger than B's own trade count -- most
touched gaps get invalidated, closing fully below GAP_LOW, before ever
confirming), `superseded_by_newer_gap` 33,151, `no_fill_bar` 7,457,
`stop_too_tight` 5,308, `expired_unused` 762, `touched_never_confirmed`
61 (distinguished from plain `expired_unused`, per Section 10 -- rare:
almost every touch resolves one way or the other, either invalidation or
confirmation, well before the 30-candle window runs out), `zero_qty`
167.

### Internal consistency and what the result actually says

Both configurations lose money in **every one of the seven calendar
years** in DEV, including the COVID-crash year (2020) that is the single
best year for both -- and even that year is only barely short of
breakeven, not genuinely profitable. The two configurations' TIMING-null
percentile is identically 0.0: a uniformly random entry time on the
exact same stock-days the real signal traded beats the real signal's
entry timing in essentially every one of 500-1000 random draws, for
both the breakout and the retest trigger. That is a strong, consistent
signal that the ENTRY TRIGGER itself -- "price closed above the top of
an unfilled three-candle gap," with or without a retest first -- carries
no exploitable timing information on this universe, at this time frame,
once realistic costs are applied; it is not a borderline result sensitive
to one bad year, one thin band, or one null construction choice.

**Status: closed.** Per `PREREGISTRATION_FVG.md` Sections 9 and 12, this
result is not rescued by retrying the 3:1 target, the 30-candle expiry,
or the 0.5% floor at other values. The sealed TEST window (2023-01-01 to
2026-09-18) is never read.
