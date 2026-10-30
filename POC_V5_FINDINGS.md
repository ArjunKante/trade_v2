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

## DEV result: FAILS. POC family closed permanently.

**V4 intraday: -0.2862% &nbsp;&nbsp;vs.&nbsp;&nbsp; V5 10-day hold: -0.6302%**
(bootstrap mean on the real gate population, midpoint cost; CI
`[-0.8029%, -0.4055%]`, `n_trades=3255`, `n_days=946`, both bounds
negative). The longer hold did not let the selection edge clear costs --
it made the result **more than twice as bad**.

This refutes the structural hypothesis V5 was built to test. V4's own
Section 15 argument (quoted in the preregistration's mandatory
fifth-trial section) was that the selection edge found in V1-V4 was
real but smaller than intraday friction, and that giving it more time
to develop would let it grow past costs. It did not: giving the trade
more time made the loss larger, not smaller. The edge was not being
suppressed by the horizon -- there is no evidence the horizon was ever
the constraint. Reaching for a longer hold did not uncover a
previously-hidden edge; it replaced a small, cost-bound loss (V4) with
a larger one (V5), while adding delivery costs, overnight gap risk, and
a structural inflation of the entry population as the price of testing
it.

Claude's own pre-committed prediction (DEV result in [-1.5%, +0.5%],
"meaningfully better chance than V1-V4") was numerically inside the
stated range, but directionally wrong about the mechanism: the
prediction's premise was that extending the horizon had a meaningfully
better chance of clearing costs than V1-V4 did. It did not clear costs
at all, and did worse than V4, the trial it was extending. A prediction
landing inside its own numeric band is not the same as being right
about the cause -- recorded here plainly rather than claimed as a
partial win.

**Gap-through-stop cost.** 173 of 3,255 gate trades (5.31%) exited
via a gap-through stop -- the entity's next trading day opened already
past the stop level, so the exit price was the open, not the stop.
Total extra loss attributable to gaps beyond what the stop distance
alone would have cost: **Rs 30,547.82**. This is the direct, measured
price of the preregistration's own deliberate choice not to widen the
stop for overnight risk (stated explicitly in the prereg's Overnight
Mechanics section as a design decision, not an oversight) -- holding
positions overnight and across weekends/holidays without a wider stop
cost real money beyond the stop's own stated risk, on about one trade
in nineteen.

**Capital was never realistic.** Peak concurrent open positions: **43**.
Peak deployed capital: **Rs 1,049,399.21** -- roughly **42x** the size
of a single ~Rs 25,000 position. This is a finding in its own right,
independent of the return result: a strategy that needs to simultaneously
hold 43 open multi-day positions, sized against a Rs 25,000-per-trade
risk model, was never runnable at the capital base that model implies.
Even had the return gate passed, the capital-concurrency profile alone
would have been a serious practicality problem.

**Population check: confirmed.** V5's total entries (gate population +
boundary-truncated) = 3,256, matching the preregistration's own
pre-stated prediction of 3,256 (V4's 3,225 `ENTERED` + V4's own 31
`NO_ROOM` skips, since a risk-multiple target computed from entry can
never sit at or below entry, making `NO_ROOM` structurally unreachable
under V5's rules -- confirmed exactly, `no_room: 0` in the real skip
breakdown). Entry and stop are byte-identical to V4's; only the exit
mechanics changed. This confirms the two trials are testing the single
variable they were designed to isolate -- the horizon -- and nothing
else.

Supplementary detail (not part of the user's required structure above,
included because it was already computed and costs nothing to report):
exit mix across the 3,255 gate trades was `STOP: 2449, TARGET: 791,
TIME_LIMIT: 15`; holding-period distribution (`trading_days_held`,
entry day = day 1) was heavily front-loaded -- 1,521 trades (46.7%)
resolved on the entry day itself, with a long thin tail out to the
11-day maximum (20 trades hit `TIME_LIMIT`'s own day-11 ceiling exactly,
3 more hit it in combination with the boundary); mean holding period
2.0 days, median 2.0 days. The TIMING null's pool (3,255 entries, 500/500
seeds) finished and was saved before the run was stopped; the SELECTION
null was still mid-build (57-59/75 months) when stopped. Neither null
was carried to a final percentile: DEV's own primary return condition
had already failed decisively (both CI bounds negative, more than twice
V4's own loss), and per the user's explicit instruction the run was
killed rather than let finish, since no null result could change a
verdict that had already failed on its first and most important
condition.

### POC family closure summary

| Trial | Result (DEV, net of costs) | Passed both nulls? |
|---|---|---|
| V1 | -0.6733R | No |
| V2 | -0.4077% | No |
| V3 | -0.3176% | No |
| V4 | -0.2862% | **Yes** |
| V5 | -0.6302% | Not reached -- failed its own primary return condition before nulls mattered |

Five trials, five failed-to-ship results. V4 was the only trial to pass
both nulls, and it was still a net loss after costs -- V4 was never
actionable on its own terms, only statistically distinguishable from
the null. Extending V4's own horizon, the one lever V4's Section 15
argued might still let the edge clear costs, made the result worse, not
better. There is no remaining, previously-unexamined lever this family's
own preregistration process has not already tried: entry definition
(V1-V2), stop/target placement and sizing (V2-V4), and now holding
horizon (V5).

**The POC family is closed permanently, per `PREREGISTRATION_POC_V5.md`
Section 14: no V6 under any argument.**
