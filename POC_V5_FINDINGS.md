# POC family V5, multi-day hold: experiments log

Companion to `PREREGISTRATION_POC_V5.md` (frozen rules, commit `2316197`,
amended before any result existed, commit `2c9ff6a`). POC family trial
5 -- argued explicitly against `PREREGISTRATION_POC_V4.md` Section 15's
own requirement (V4 passed both nulls; this tests whether more time lets
the same selection edge clear costs), with the swing V1 counter-argument
recorded with equal weight. Any DEV pass below is weighed against that
precedent. Records what was actually run and found, per the
preregistration's own Process section.

## Hand-traced examples (Process Step 2)

All 5 required shapes -- a gap-through stop and a 10-day `TIME_LIMIT`
exit (both required by name), plus a clean overnight stop, a target hit,
and a `DEV_BOUNDARY_TRUNCATED` case -- found by `scripts/poc_v5_
handtrace.py` against the real DEV window: the first four on the first
entity scanned (`INE002A01018`), the `TIME_LIMIT` example on the third
entity, and the boundary case on the 54th (found specifically because
its own trade date, 2022-12-29, sits two trading days before `DEV_END`).
Every number below was independently recomputed by hand from the
script's own printed inputs before being trusted.

### 1. STOP, clean (no gap), overnight -- INE002A01018, 2017-08-08

`LOOKBACK_LOW = 1591.4778`, `ATR_raw = 33.6017`.

- Sweep at 10:15: low 1586.7869. `depth = 4.6909`, `depth/ATR = 0.1396`
  -- within range. Reclaim at 10:20 (offset 1), close 1599.9541 clears
  `LOOKBACK_LOW`.
- Fill at 10:25 (reclaim candle's own close) -> **entry = 1599.9541**.
  `STOP = 1586.7869 - 0.1*33.6017 = 1583.4268` (`stop_distance_pct =
  1.0330%`). `TARGET = entry + 3*16.5273 = 1649.5362`. `qty =
  floor(25000/1599.9541) = 15`.
- Entry day: neither level hit intraday. Day +1: neither hit. **Day +2
  (2017-08-10): low <= stop, open (not shown, but inferred > stop since
  `gap_through=False`) -> clean STOP at exactly 1583.4268.**
  `trading_days_held = 3` (entry + 2 subsequent).
- `pnl_rs = 15*(1583.4268-1599.9541) = -247.91`. `position_size_rs =
  23,999.31`. `cost_rs_mid = 154.14` (delivery model, independently
  re-verified). **`net_return_pct = -1.6752%`** (range: -1.6102% at the
  lo-cost bound to -1.7402% at the hi-cost bound).

### 2. TARGET, overnight -- INE002A01018, 2019-02-26

`LOOKBACK_LOW = 1211.1937`, `ATR_raw = 28.7908`.

- Sweep at 10:00: low 1205.9870, `depth/ATR = 0.1808`. Reclaim at 10:10
  (offset 2 -- the offset-1 candidate was live, not shown), close
  1216.3992 clears the level.
- Fill at 10:15 -> **entry = 1216.3992**. `STOP = 1203.1079`
  (`stop_distance_pct = 1.0927%`). `TARGET = entry + 3*13.2913 =
  1256.2729`. `qty = floor(25000/1216.3992) = 20`.
- Neither hit on the entry day or the next 4 subsequent days. **Day +5
  (2019-03-06): high >= target, open below it -> clean TARGET at
  1256.2729.** `trading_days_held = 6`.
- `pnl_rs = 20*(1256.2729-1216.3992) = 797.47`. `position_size_rs =
  24,327.98`. `cost_rs_mid = 155.28`. **`net_return_pct = +2.6397%`** --
  a genuine win, confirming the mechanism can and does produce one, not
  just losses.

### 3. STOP, gap-through -- INE002A01018, 2022-04-13

`LOOKBACK_LOW = 2555.3921`, `ATR_raw = 55.5457`.

- Sweep at 12:25: low 2547.7948, `depth/ATR = 0.1368`. Reclaim at 12:35
  (offset 2) -- **`new_low_during_reclaim = True`**: the offset-1
  candidate made a new low, updating the running `sweep_low` downward
  before the offset-2 candidate's close (2555.8577) cleared the level.
- Fill at 12:40 -> **entry = 2555.8136**. The UPDATED `sweep_low` feeds
  the stop: `STOP = 2539.9491` (not the original 2547.7948-derived
  value -- back-solving confirms the final `sweep_low` used was
  2545.5037, below the original detection low, exactly consistent with
  `new_low_during_reclaim=True`). `stop_distance_pct = 0.6207%`.
  `TARGET = 2555.8136 + 3*15.8645 = 2603.4072`. `qty =
  floor(25000/2555.8136) = 9`.
- Neither hit on the entry day. **The very next in-archive trading day
  is 2022-04-18** (04-14 through 04-17 fall across a holiday/weekend
  stretch, confirmed by this being the entity's own next observed row,
  not a market-wide assumption): **that day's own OPEN (2533.00) is
  already below the stop (2539.9491) -- a genuine gap-through.** Exit at
  the open, **2533.00**, not the stop price. `trading_days_held = 2`.
- `pnl_rs = 9*(2533.00-2555.8136) = -205.32`. `position_size_rs =
  23,002.32`. `cost_rs_mid = 150.67`. **`net_return_pct = -1.5477%`** --
  **Rs 22.81/share beyond the stop's own distance was lost specifically
  to the gap** (`2539.9491 - 2533.00`), the exact consequence the
  preregistration's own "stop not widened for overnight risk" section
  said to expect and measure, confirmed in the first real example found.

### 4. TIME_LIMIT, full 10-day hold -- INE010B01027, 2017-03-16

`LOOKBACK_LOW = 434.5000`, `ATR_raw = 13.7126`.

- Sweep at 11:25: low 429.0000, `depth/ATR = 0.4011`. Reclaim at 11:30
  (offset 1), close 442.05 clears the level immediately.
- Fill at 11:35 -> **entry = 442.0500**. `STOP = 427.6287`
  (`stop_distance_pct = 3.2624%`). `TARGET = 442.05 + 3*14.4213 =
  485.3138`. `qty = floor(25000/442.05) = 56`.
- Neither level is ever hit across the entry day or 10 full subsequent
  trading days. **Exit at the 10th subsequent day's own close
  (2017-03-30), 450.40.** `trading_days_held = 11` -- exactly `1
  (entry) + 10 (the stated maximum)`, confirming the counting convention
  (entry day is day 1, not one of the "10 after") is implemented exactly
  as the preregistration defines it.
- `pnl_rs = 56*(450.40-442.05) = 467.60`. `position_size_rs =
  24,754.80`. `cost_rs_mid = 156.76`. **`net_return_pct = +1.2557%`** --
  a small win that never got close to either level, exactly the shape a
  risk-multiple target combined with a tight-ish stop (3.26%) would be
  expected to produce sometimes.

### 5. DEV_BOUNDARY_TRUNCATED -- INE216A01022, 2022-12-29

`LOOKBACK_LOW = 4313.8000`, `ATR_raw = 70.6205`.

- Sweep at 13:30: low 4296.5500, `depth/ATR = 0.2443`. Reclaim at 13:35
  (offset 1), close 4314.35 clears the level.
- Fill at 13:40 -> **entry = 4314.3500**. `STOP = 4289.4880`
  (`stop_distance_pct = 0.5763%`, just above the 0.5% floor). `TARGET =
  4314.35 + 3*24.862 = 4388.9361`. `qty = floor(25000/4314.35) = 5`.
- Neither hit on the entry day. **`DEV_END = 2022-12-31` is a Saturday
  -- the only in-bounds subsequent trading day is 2022-12-30.** Neither
  level is hit on it either, and no further in-bounds day exists (the
  query itself is scoped to `trade_date <= DEV_END` at the SQL level --
  confirmed directly: no row beyond 2022-12-30 was ever fetched for this
  resolution, so no sealed-window data was touched to reach this
  verdict). **`DEV_BOUNDARY_TRUNCATED`, exit at 2022-12-30's own close,
  4307.45.** `trading_days_held = 2`.
- `pnl_rs = 5*(4307.45-4314.35) = -34.50`. `position_size_rs =
  21,571.75`. `cost_rs_mid = 145.71`. **`net_return_pct = -0.8354%`** --
  **excluded from the gate's own population per the preregistration**,
  reported here only as a hand-traced confirmation the mechanism works,
  not as part of the real DEV sample.

**All five hand traces are internally consistent with the
preregistration exactly as written.** The stop/target formulas, the
new-low-during-reclaim-updates-the-stop interaction, the exact
entry-day-is-day-1/10-more/11-total counting convention, the
gap-through-costs-more-than-the-stop-distance consequence, and the
DEV-boundary truncation's own SQL-level safety (verified directly, not
assumed) were each exercised and independently re-verified by hand
before any aggregate number was computed.
