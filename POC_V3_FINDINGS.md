# POC bounce V3, hourly confirmation: experiments log

Companion to `PREREGISTRATION_POC_V3.md` (frozen rules, commit `c667e5c`).
POC family trial 3 -- a revision proposed by the user after seeing BOTH
V1 and V2 fail at DEV. Carries more selection pressure than V2 did; any
DEV pass below is development evidence only, never a validity claim, and
is the LEAST informative of the three trials per the preregistration's
own Provenance section. Records what was actually run and found, per
that document's Process section.

**Bottom line, stated first per this project's "bad results first"
discipline: DEV FAILS.** Mean net return = **-0.3176%** of position
value, 97.5% CI **[-0.3634%, -0.2718%]** -- excludes zero on the
NEGATIVE side, so the gate's first condition already fails, and the gate
requires ALL conditions. **Neither null was run to completion** -- the
TIMING null's pool had been built and its 20-seed timing probe had
already run (sized to 500 seeds) when the run was killed, but zero of
those 500 seeds had executed; the SELECTION null never started. The
sealed TEST window is never read. **POC family trial count is now 3 --
V1, V2, and V3 are all closed, all NO EDGE. Per `PREREGISTRATION_
POC_V3.md` Section 15: no V4 will be proposed. The POC family is
closed.**

## DEV result (partial -- nulls not run to completion)

18,121 trades, 1,451 distinct entry days, full top-200-by-turnover
universe, real DEV window 2016-10-04 to 2022-12-31. Runtime: 41.5 min
for the real backtest; stopped during Stage 3 (TIMING null pool built,
20-seed timing probe run to decide seed count, zero of the resulting 500
seeds executed) once the gate's primary condition was already decided.

| | |
|---|---|
| Trades / distinct entry days | 18,121 / 1,451 |
| Win rate | 34.4% |
| Mean net return (97.5% CI) | **-0.3176%** [-0.3634%, -0.2718%] |
| Median net return (descriptive) | -0.2680% |
| MDE | 0.0464% |
| TIMING null | **not run** -- gate already failed |
| SELECTION null | **not run** -- gate already failed |
| Exit mix | TIME_EXIT 12,400 / TARGET 3,702 / STOP 2,019 |
| By year | 2016 -0.283% (324) / 2017 -0.299% (2,639) / 2018 -0.310% (2,324) / 2019 -0.295% (2,808) / 2020 -0.279% (3,308) / 2021 -0.362% (3,589) / 2022 -0.353% (3,129) |
| By band | 1-50: -0.251% (4,775) / 51-100: -0.297% (5,128) / 101-200: -0.369% (8,218) |
| Ex-best-year (2020 excluded) mean | -0.326% |
| Bands 1-100 mean | -0.275% (9,903 trades) |
| Peak concurrent positions | 67 |
| Peak deployed capital | Rs 1,678,679 |
| **DEV_PASS** | **False** |

**Reminder, every time this figure is shown**: this is a PERCENTAGE OF
POSITION VALUE, not R. Not comparable to V1. Directly comparable to V2.

### THE MEASUREMENT THAT MATTERED: did hourly confirmation move entries further from the POC?

This was the study's entire stated rationale, so it is answered directly,
whether or not it helped:

| `(entry_price - POC_PRICE) / entry_price` | V2 (5-min confirm) | V3 (1-hour confirm) |
|---|---|---|
| Mean | -1.269% | **-1.380%** |
| Median | -0.689% | **-0.917%** |
| Min (furthest below POC) | -24.697% | **-37.224%** |
| Max (furthest above POC) | +2.541% | **+3.157%** |

**Yes -- entries moved further from the POC in magnitude, on every
statistic measured (mean, median, and both tails).** But the direction is
the opposite of the implicit picture in the rationale ("entries landed a
fraction above it"): **both V2 and V3 entries land BELOW the POC on
average, not above it, and hourly confirmation pushed them further
below, not further above.** A GREEN or HAMMER confirmation candle only
requires closing above its own open (or showing a hammer shape) -- it
says nothing about the candle's relationship to the POC level itself, so
there was never a mechanical reason to expect entries to land above POC
specifically; a wider candle simply has more room to move in either
direction before it confirms, and the data shows that room was used
mostly to the downside. **The rationale's directional premise (further
movement before confirmation) is confirmed. Its implicit framing (that
this movement would be upward, away from the level in the direction of
the bounce) is not -- and this did not produce an edge either way.**

### Realised stop distance (% of entry) -- unchanged from V2, as expected

| | min | median | max |
|---|---|---|---|
| V2 | 0.500% | 2.126% | 5.000% |
| V3 | 0.500% | **2.209%** | 5.000% |

Both guards still hold exactly at their frozen boundaries. The small
median shift (2.126% -> 2.209%) is consistent with slightly different
entry prices under hourly confirmation shifting which setups clear the
`STOP_TOO_WIDE`/`STOP_TOO_TIGHT` checks -- not a change to how STOP
itself is computed, which is byte-identical to V2 (the same 5-day
lookback low).

### Cost distribution

| | min | median | max |
|---|---|---|---|
| Cost (Rs) | 37.38 | 65.97 | 140.92 |
| Cost (% of position value) | 0.158% | 0.271% | 0.341% |
| Position value (Rs) | 12,590.03 | 24,786.65 | 89,048.90 |

Total costs: **Rs 1,226,649** across 18,121 trades. Same bounded shape as
V2 (fixed-capital sizing is unchanged), confirming costs are not what
shifted between V2 and V3.

### Trade count against V2's 22,959: WHERE the 4,838 fewer trades went

**18,121 trades, down 4,838 (-21.1%) from V2's 22,959.** The
preregistration's own stated expectation was that this gap would be
driven mainly by `FILL_OUTSIDE_WINDOW` (the 14:30 cutoff). **That
expectation was WRONG, stated plainly**: `fill_outside_window` actually
FELL slightly, from 1,800 (V2) to 1,542 (V3) -- 0.646% to 0.553% of all
setups checked. The shared, upstream stages (`lookback_incomplete`
42,802 and `trend_filter_failed` 108,905, both byte-identical to V2,
confirming neither is affected by the confirmation-timeframe change)
funnel into touch/confirmation/fill, where the REAL divergence happens:

| Skip reason (delta from V2) | V2 | V3 | Delta |
|---|---|---|---|
| `no_touch` | 47,425 | 49,061 | **+1,636** |
| `poc_failed` | 31,754 | 33,645 | **+1,891** |
| `no_confirmation` | 1,059 | 2,473 | **+1,414** |
| `no_fill_bar` | 551 | 2,709 | **+2,158** |
| `fill_outside_window` | 1,800 | 1,542 | -258 |
| `entry_below_stop` | 2,578 | 2,917 | +339 |
| `stop_too_wide` | 9,489 | 8,380 | -1,109 |
| `stop_too_tight` | 1,959 | 1,692 | -267 |
| `no_room` | 7,414 | 6,448 | -966 |
| **entered (trades)** | **22,959** | **18,121** | **-4,838** |

(Deltas sum to exactly zero against the trade-count delta -- 278,695
total setups checked is identical between V2 and V3, as it must be: same
universe, same dates, same lookback/trend-filter stages.)

**The dominant driver is `no_fill_bar` (+2,158, the single largest
delta)**: the exact 1-minute bar at the confirming hourly candle's own
`bucket_end` is missing from the archive meaningfully more often than
V2's 5-minute equivalent -- not yet explained by anything in this
study's own mechanics, reported honestly as observed rather than
guessed at. **`poc_failed` (+1,891) and `no_touch` (+1,636)** are both
plausibly explained by coarser granularity: a full hour gives more time
for a confirmation candle to decisively close red-and-below-POC than a
5-minute snapshot does, and the touch rule's own "first candle AT OR
AFTER 09:45" boundary discards the ENTIRE `[09:15,10:15)` hour (not just
the `[09:15,09:45)` portion a 5-minute grid would have excluded),
pushing some touches that 5-minute candles would have caught into
`no_touch` instead. **`no_confirmation` (+1,414)** more than doubled.
Partially offsetting, `stop_too_wide` (-1,109), `no_room` (-966), and
`stop_too_tight` (-267) all fell, consistent with the entry-POC-distance
finding above (different entry prices shift some setups across these
guards in both directions). **The 14:30 entry cutoff, the consequence
the preregistration specifically flagged in advance, turned out to be
the SMALLEST and only negative-signed term in this table** -- the real
cost of hourly confirmation is attrition at touch/confirmation/fill,
well before entry timing ever becomes the limiting factor.

## POC family: three trials, three failures -- closed

| Trial | Result | What changed |
|---|---|---|
| V1 | **-0.6733 R** | original design -- contaminated by a sizing pathology (`OPERATIONS.md` standing rule) |
| V2 | **-0.4077%** | pathology removed (fixed-capital sizing); stop moved to the 5-day lookback low; still loses |
| V3 | **-0.3176%** | confirmation timeframe moved to hourly; still loses |

Three trials, each a revision proposed after watching the one before it
fail, each measured loss smaller than the last -- **and not one of the
three ever crossed zero.** The signal does not work under any sizing
convention, stop definition, or confirmation timeframe tested here. Per
`PREREGISTRATION_POC_V3.md` Section 15, this is as far as the family
goes: **no V4. The POC family is closed.**

**The transferable finding, separate from whether POC itself works**:
POC's lasting contribution to this project is not a working strategy --
it is the **minimum-stop-distance-floor standing rule** (`OPERATIONS.md`),
found while diagnosing V1's own sizing pathology and now a project-wide
requirement for every future study whose stop is pinned to a price level
other than entry itself. Three trials of a strategy that never worked
still produced one piece of infrastructure the rest of this project keeps.

## Hand-traced examples (Process Step 2)

All 5 required shapes found on the FIRST entity scanned, `INE002A01018`
(the same entity V1's and V2's own hand-traces happened to use first), by
`scripts/poc_v3_handtrace.py` against the real DEV window -- no synthetic
data. Every number below was independently recomputed by hand from the
script's own printed inputs (touch/confirm candle OHLC, `bucket_end`,
`fill_ts`, `LOOKBACK_LOW`) before being trusted.

### 1. ENTERED, TIME_EXIT -- 2016-10-14

`POC_PRICE = 1108.1877`, `PREV_HIGH = 1126.2518`, `LOOKBACK_LOW =
1051.9892`, band 1-50, rank 7.

- **Touch** candle: the `[10:15,11:15)` hourly bucket (O=1072.85
  H=1075.00 L=1061.63 C=1065.64) -- low 1061.63 <= POC_PRICE. Note the
  `[09:15,10:15)` bucket is NEVER touch-eligible under V3's own rule ("the
  first hourly candle AT OR AFTER 09:45"), since its own start (09:15) is
  before 09:45 -- this is the first hand-traced confirmation that the rule
  behaves exactly as the preregistration states, not an oversight.
- **Confirm** candle: the `[11:15,12:15)` bucket, **GREEN** (O=1065.89,
  C=1071.64, close > open).
- **Fill**: the confirming candle's own `bucket_end` = **12:15** (a FULL
  hour bucket, so `bucket_end = ts + 60min` here) -> entry = open of the
  12:15 1-minute bar = **1071.6393**.
- STOP = LOOKBACK_LOW = 1051.9892 (`stop_distance_pct = (1071.6393 -
  1051.9892)/1071.6393 = 1.834%`, within [0.5%, 5%]). TARGET = `1126.2518
  x 0.98 = 1103.7268`. `qty = floor(25000/1071.6393) = 23`.
- Resolution: neither STOP nor TARGET hit by 15:19 -> **TIME_EXIT** at the
  15:15 **5-minute** candle's own close (NOT the hourly grid -- Section 8
  is unchanged, see below), exit_price = **1077.7975**, exit_ts = 15:20.
  `pnl_rs = 23 x (1077.7975 - 1071.6393) = 141.64`. `position_size_rs =
  23 x 1071.6393 = 24,647.70`. `cost_rs = 60.82` (independently
  recomputed via `box_theory.costs.round_trip_cost_rs`, matches).
  **`net_return_pct = (141.64 - 60.82)/24,647.70 = +0.3279%`**.
- `entry_above_poc_frac = (1071.6393 - 1108.1877)/1071.6393 = -3.4105%`
  -- entry landed BELOW the POC, by over 3%. **Noted plainly here since
  it bears directly on the study's own stated rationale** (Section 13's
  comparison against V2's distribution of this same quantity is where
  this gets resolved with a real sample, not asserted from one trace).

### 2. POC_FAILED -- 2016-10-17

`POC_PRICE = 1115.0884`.

- Touch: `[10:15,11:15)` bucket, low 1074.84 <= POC_PRICE.
- Confirm candidate 1: `[11:15,12:15)` bucket, O=1077.96 C=1069.25 --
  RED (close < open) AND close (1069.25) < POC_PRICE (1115.09), and NOT
  a hammer shape (`lower_wick=2.19` is less than `2 x body=17.42`) -- so
  the ordinary POC_FAILED branch applies (not the hammer override seen in
  trace 5 below). **`POC_FAILED`**, no trade. This entity-day has 7
  hourly candles total; touch is bucket index 1 (the `[10:15,11:15)`
  bucket -- index 0, `[09:15,10:15)`, is excluded from touch eligibility
  as stated above).

### 3. STOP_TOO_WIDE -- 2016-12-15

`POC_PRICE = 1057.6403`, `PREV_HIGH = 1064.4577`, `LOOKBACK_LOW =
1004.3450`.

- Touch: `[11:15,12:15)` bucket, low 1057.48 <= POC_PRICE (barely, by
  0.16).
- Confirm: `[12:15,13:15)` bucket, GREEN (O=1058.94, C=1060.64).
- Fill at the confirm candle's own `bucket_end` = 13:15 -> entry =
  **1060.6431**.
- STOP = LOOKBACK_LOW = 1004.3450. `risk_pct = (1060.6431 -
  1004.3450)/1060.6431 = 5.308%` -- **above the 5% ceiling** ->
  **`STOP_TOO_WIDE`**, no trade. Confirms the same dynamic V2's own
  hand-trace #1 found (a 5-day low landing just past the ceiling), now
  under hourly confirmation.

### 4. ENTERED, TARGET -- 2017-01-04

`POC_PRICE = 1079.2375`, `PREV_HIGH = 1096.9956`, `LOOKBACK_LOW =
1047.0835`, band 1-50, rank 7.

- Touch: `[10:15,11:15)` bucket, low 1071.55 <= POC_PRICE. Confirm:
  `[11:15,12:15)` bucket, GREEN (O=1073.65, C=1074.34).
- Fill at `bucket_end` = 12:15 -> entry = **1074.8296**.
- STOP = 1047.0835 (`stop_distance_pct = 2.581%`). TARGET = `1096.9956 x
  0.98 = 1075.0557` -- **only Rs 0.23 above entry**, since entry itself
  landed almost exactly at the 2%-below-PREV_HIGH line (the identical
  dynamic V2's own hand-trace #4 documented). `qty =
  floor(25000/1074.8296) = 23`.
- Resolution: TARGET hit at 12:25. `pnl_rs = 23 x (1075.0557 -
  1074.8296) = 5.20`. `cost_rs = 60.86` (independently recomputed,
  matches). **`net_return_pct = (5.20 - 60.86)/24,721.08 = -0.2251%`** --
  **negative despite a genuine TARGET exit**, same recurring dynamic as
  V2: a target landing very close to entry leaves little room for the
  fixed-cost component to clear.
- `entry_above_poc_frac = -0.4101%` -- again below the POC, not above.

### 5. FILL_OUTSIDE_WINDOW -- 2017-04-26

`POC_PRICE = 1417.0761`.

- Touch: `[13:15,14:15)` bucket, low 1416.98 <= POC_PRICE (barely, by
  0.10).
- Confirm candidate 1: `[14:15,15:15)` bucket, O=1418.61 H=1418.93
  L=1402.60 C=1414.96 -- **RED and closes below POC** (1414.96 <
  1417.08), which looks at first glance like it should be `POC_FAILED`
  (as trace 2 was) -- but the HAMMER test is checked BEFORE the
  RED-and-below-POC test in `classify_confirmation_candle` (V1's own,
  unchanged, already-verified ordering): `body = 3.65`, `lower_wick =
  min(O,C) - L = 1414.96 - 1402.60 = 12.36`, `upper_wick = H - max(O,C) =
  1418.93 - 1418.61 = 0.32`. `lower_wick (12.36) >= 2 x body (7.29)` and
  `upper_wick (0.32) <= body (3.65)` -> **a genuine hammer shape**,
  overriding the RED-close test -> **`ENTER_HAMMER`**, confirmed
  (independently re-run against `poc.resolution.classify_confirmation_
  candle` directly to be certain before writing this up, since the first
  manual check missed the hammer-precedence rule and wrongly expected
  `POC_FAILED` here).
- Confirm candle's own `bucket_end` = **15:15** (a FULL hour bucket --
  `[14:15,15:15)` -- not the session's partial one). `fill_bar_after_
  candle_close` finds the 1-minute bar at `ts = 15:15` -> `fill_ts =
  15:15:00`, which is **past the unchanged 14:30 entry cutoff** ->
  **`FILL_OUTSIDE_WINDOW`**, no trade. This is the first directly
  observed instance of the consequence the preregistration's own
  "Consequence, reported not fixed" section predicted: a touch in the
  early afternoon (13:15 here) consumed two full hourly candles (touch +
  confirm, closing at 15:15) before a fill was even possible, well past
  where a 5-minute-confirmation setup would already have filled.

**All five hand traces are internally consistent with the preregistration
exactly as written** -- touch/confirmation were independently re-run
against `poc.resolution.find_touch_idx`/`find_confirmation`/`classify_
confirmation_candle` directly (not just read from the hand-trace script's
own output) for trace 5, after the printed result did not match a first,
incomplete manual check; LOOKBACK_LOW, STOP, TARGET, qty, `cost_rs`, and
net return % were recomputed by hand (or via `box_theory.costs.round_
trip_cost_rs` directly) for every ENTERED example before trusting any
aggregate number. Position sizes landed in the Rs 24,600-24,700 range in
both ENTERED examples, consistent with V2's own fixed-capital formula
(unchanged here). Both ENTERED examples show entry BELOW the POC (-3.41%,
-0.41%), not above it -- noted here as a real, observed-twice pattern
worth watching in the full DEV sample, not yet a conclusion (two traces
are not a distribution; Section 13's own required comparison against V2
is where this is actually measured).
