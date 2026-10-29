# POC family V4, liquidity sweep and reclaim: experiments log

Companion to `PREREGISTRATION_POC_V4.md` (frozen rules, commit `86734ea`).
POC family trial 4 -- the fourth revision, run only because the user
explicitly overrode `PREREGISTRATION_POC_V3.md` Section 15's own
"family closes if V3 fails" rule. Carries severe selection pressure; any
DEV pass below is the least informative result this family has produced,
weighed against this project's own swing V1 precedent (100th percentile,
p=0.001, 65,219 trades, cleared Bonferroni+BH -- then 61.4th percentile
on its sealed holdout; `SWING_FINDINGS.md`). Records what was actually
run and found, per the preregistration's own Process section.

## Hand-traced examples (Process Step 2)

All 5 required shapes -- `TOUCH_TOO_SHALLOW`, `BREAKDOWN_NOT_SWEEP`, and
`NOT_RECLAIMED` (all three required by name), plus a second `NOT_
RECLAIMED` exercising the "new low during reclaim, clock not reset"
rule, and a real `ENTERED` trade -- found on the FIRST entity scanned,
`INE002A01018` (the same entity every prior POC-family hand-trace
happened to use first), by `scripts/poc_v4_handtrace.py` against the
real DEV window. Every number below was independently recomputed by
hand from the script's own printed inputs before being trusted; the
`BREAKDOWN_NOT_SWEEP` example's triggering depth was additionally
re-derived in a separate, standalone query (not just read from the
script's own status-only output) before being written up here.

### 1. TOUCH_TOO_SHALLOW -- 2016-10-21

`LOOKBACK_LOW = 1058.7593`, `ATR_raw = 23.5151`. Price dipped below
`LOOKBACK_LOW` on at least one 5-minute candle after 09:45, but every
such dip stayed shallower than `0.1 x ATR = 2.352` below the level --
never deep enough to count as a sweep, never deep enough to count as a
breakdown either. **`TOUCH_TOO_SHALLOW`**, no trade, day abandoned by
the "keep watching" rule finding nothing to watch for by end of window.

### 2. BREAKDOWN_NOT_SWEEP -- 2017-01-17

`LOOKBACK_LOW = 1073.9482`, `ATR_raw = 16.5279` (breakdown ceiling =
`LOOKBACK_LOW - 1.0*ATR = 1057.4203`; sweep floor = `LOOKBACK_LOW -
0.1*ATR = 1072.2954`). The VERY FIRST eligible candle
(09:45) already has low **1051.1338**, depth **22.8144**, `depth/ATR =
1.3804` -- past the 1.0x ceiling immediately. **`BREAKDOWN_NOT_SWEEP`**,
day abandoned on the first check. Independently verified this was a
genuine breakdown, not a transient first-candle outlier: every single
5-minute candle for the rest of the session stayed between 1.12x and
2.19x ATR below `LOOKBACK_LOW` (re-queried directly, not sampled) --
the stock gapped down hard at the open and never recovered anywhere
near the level. Exactly the case this rule exists to exclude.

### 3. NOT_RECLAIMED (no new low during the wait) -- 2017-01-18

`LOOKBACK_LOW = 1038.4934`, `ATR_raw = 18.0438`.

- **Sweep** at 11:20: low **1035.2616**. `depth = 1038.4934 - 1035.2616 =
  3.2318`. `depth/ATR = 3.2318/18.0438 = 0.1791` -- within `[0.1, 1.0]`.
  **SWEEP**, `sweep_low = 1035.2616`.
- Reclaim candidates: 11:25 (low 1036.5176, close 1037.0037), 11:30 (low
  1036.0719, close 1036.9227), 11:35 (low 1036.0719, close 1036.5176).
  **None of the three lows ever drop below the running `sweep_low`
  (1035.2616) -- no update fires.** None of the three closes clear
  `LOOKBACK_LOW` (1038.4934). **`NOT_RECLAIMED`**, `new_low_during_
  reclaim = False`, `sweep_low` unchanged at the end.

### 4. NOT_RECLAIMED (new low during the wait, clock NOT reset) -- 2016-10-25

`LOOKBACK_LOW = 1058.3910`, `ATR_raw = 23.7896`. **The filled decision
from the preregistration, exercised in real data**:

- **Sweep** at 09:45: low **1055.5151**. `depth = 2.8759`, `depth/ATR =
  0.1209` -- within range. **SWEEP**, `sweep_low = 1055.5151`.
- Reclaim candidate 1 (09:50): low **1054.5427** -- BELOW the running
  `sweep_low` (1055.5151) -- **`sweep_low` updates to 1054.5427**. Close
  1056.1633, does not clear `LOOKBACK_LOW` (1058.3910).
- Reclaim candidate 2 (09:55): low 1055.0694 -- NOT below the now-updated
  `sweep_low` (1054.5427), no further update. Close 1057.2977, still
  short of `LOOKBACK_LOW`.
- Reclaim candidate 3 (10:00): low 1056.3659 -- not below `sweep_low`.
  Close 1057.5003, still short.
- **`NOT_RECLAIMED`**, `new_low_during_reclaim = True`, final `sweep_low
  = 1054.5427`. **The 3-candle clock ran its full course from the
  ORIGINAL sweep candle (09:45) through candidate 3 (10:00) -- it was
  NOT extended or restarted when the new low landed on candidate 1**,
  exactly as the preregistration's own stated rule requires. Had this
  day gone on to reclaim on a later candle, STOP would have used
  1054.5427 (the updated low), not 1055.5151 (the original) -- not
  exercised here since it never reclaimed, but the update itself is
  directly confirmed.

### 5. ENTERED, STOP exit -- 2017-06-28

`LOOKBACK_LOW = 1404.2615`, `PREV_HIGH = 1445.3760`, `ATR_raw =
24.0726`, band 1-50, rank 7.

- **Sweep** at 11:10: low **1401.1024**. `depth = 3.1591`, `depth/ATR =
  0.1312`. **SWEEP**, `sweep_low = 1401.1024`.
- Reclaim candidate 1 (11:15): low 1407.0175 -- not below `sweep_low`
  (no update, `new_low_during_reclaim = False`). Close **1409.0432** --
  clears `LOOKBACK_LOW` (1404.2615). **RECLAIMED** on the first
  candidate.
- **Fill**: the reclaiming candle's own close (11:15 + 5min = 11:20) ->
  entry = open of the 11:20 1-minute bar = **1409.0432**.
- `STOP = sweep_low - 0.1*ATR = 1401.1024 - 2.4073 = 1398.6952`.
  `stop_distance_pct = 0.7344%` (within `[0.5%, 5%]`). `TARGET =
  1445.3760 x 0.98 = 1416.4685`. `qty = floor(25000/1409.0432) = 17`.
- **`entry_above_lookback_low_frac = (1409.0432 - 1404.2615)/1409.0432 =
  +0.3393%` -- entry landed ABOVE the swept level**, as the hypothesis
  requires (one trace is not a distribution; Section 12's own required
  comparison is where this gets a real sample).
- Resolution: **STOP** hit at 13:37, exit_price = 1398.6952 (no gap
  through). `pnl_rs = 17 x (1398.6952 - 1409.0432) = -175.92`.
  `position_size_rs = 23,953.73`. `cost_rs = 60.43` (independently
  recomputed via `box_theory.costs.round_trip_cost_rs`, matches).
  **`net_return_pct = (-175.92 - 60.43)/23,953.73 = -0.9867%`**.

**All five hand traces are internally consistent with the
preregistration exactly as written.** Position sizing, stop/target
guards, and resolution match V2's own byte-identical formulas exactly;
the only genuinely new mechanics (sweep-depth classification, the
reclaim clock, the new-low-tracking-without-reset rule) were each
exercised at least once above and independently re-verified by hand,
including re-deriving `BREAKDOWN_NOT_SWEEP`'s own triggering depth from
the raw 5-minute candles directly rather than trusting the status-only
return value.
