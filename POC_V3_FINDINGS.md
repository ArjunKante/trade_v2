# POC bounce V3, hourly confirmation: experiments log

Companion to `PREREGISTRATION_POC_V3.md` (frozen rules, commit `c667e5c`).
POC family trial 3 -- a revision proposed by the user after seeing BOTH
V1 and V2 fail at DEV. Carries more selection pressure than V2 did; any
DEV pass below is development evidence only, never a validity claim, and
is the LEAST informative of the three trials per the preregistration's
own Provenance section. Records what was actually run and found, per
that document's Process section.

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
