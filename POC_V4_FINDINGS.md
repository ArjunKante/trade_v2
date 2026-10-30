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

**Bottom line, stated first per this project's "bad results first"
discipline: DEV FAILS.** Mean net return = **-0.2862%** of position
value, 97.5% CI **[-0.3836%, -0.1685%]** -- excludes zero on the
NEGATIVE side. The gate requires ALL FOUR conditions; **three of four
fail** (mean/CI, ex-best-year, bands 1-100) -- only the two null
percentiles individually clear 95th (see below, reported honestly, not
spun either direction). **The sealed TEST window is never read. Per
`PREREGISTRATION_POC_V4.md` Section 15: this was the last trial in the
POC family. No V5. The family is now closed, permanently.**

**Claude's pre-committed prediction (Section 13 of the preregistration)
was CONFIRMED**, recorded here as plainly as a wrong prediction would
have been: "DEV fails, mean net return between -0.5% and +0.1%, most
likely slightly negative, trade count well below V2's 22,959." Actual:
**-0.2862%** (inside the predicted range, slightly negative) and
**3,225 trades** (86% below V2's 22,959 -- "well below" turned out to
understate it).

## DEV result (complete -- both nulls ran to full completion)

3,225 trades, 943 distinct entry days, full top-200-by-turnover
universe, real DEV window 2016-10-04 to 2022-12-31. Runtime: 43.9 min
for the real backtest, 200.8 min total including both nulls (TIMING:
500 seeds; SELECTION: 1000 seeds, 75 months) -- the run was not stopped
early this time; the gate's full picture (including both null
percentiles) was worth seeing in full given two of its four conditions
turned out to pass.

| | |
|---|---|
| Trades / distinct entry days | 3,225 / 943 |
| Win rate | 35.0% |
| Mean net return (97.5% CI) | **-0.2862%** [-0.3836%, -0.1685%] |
| Median net return (descriptive) | -0.6246% |
| MDE | 0.1084% |
| TIMING null percentile | **100.0** (500 seeds) -- PASSES |
| SELECTION null percentile | **97.9** (1000 seeds, 75 months) -- PASSES |
| Ex-best-year (2020 excluded) mean | -0.3178% -- FAILS |
| Bands 1-100 mean | -0.2588% (1,804 trades) -- FAILS |
| Exit mix | TIME_EXIT 1,652 / STOP 1,353 / TARGET 220 |
| **DEV_PASS** | **False** (gate requires all four; 1 and 3 and 4 fail) |

**Reminder, every time this figure is shown**: percentage of position
value, NOT R. Not comparable to V1. Directly comparable to V2/V3.

**Reported honestly, not minimized**: both null percentiles individually
clear the 95th-percentile bar -- V4's real entries beat random timing
and random selection from the same eligible pool, on this DEV sample.
That is a genuinely different shape of result than V1-V3 ever produced
(none of which got past the mean/CI condition at all). It is also not
enough: the mean itself is negative with a CI that excludes zero on the
wrong side, and dropping the best year or restricting to bands 1-100
both flip it more negative, not less. A result that clears two of four
conditions is still NO EDGE under this gate's own all-or-nothing
standard, stated here with no asterisk.

### THE MEASUREMENT THAT MATTERED: do entries sit above the swept level?

The hypothesis's own direct test, required by the preregistration:

| `(entry_price - LOOKBACK_LOW) / entry_price` | V4 |
|---|---|
| Mean | **+0.2389%** |
| Median | **+0.1513%** |
| Min | -0.1793% |
| Max | +3.0438% |

**Yes -- entries sit ABOVE the swept level on average, the mechanism the
hypothesis describes.** This is a real contrast with V1-V3's own
`entry_above_poc_frac`, which was NEGATIVE on average in every one of
those studies (entries landed below their own reference level). The
liquidity-sweep-and-reclaim construction does what it was built to do,
mechanically: by requiring a CLOSE back above `LOOKBACK_LOW` before
entry is even considered, entries are structurally biased to sit above
it (unlike V1-V3's green/hammer confirmation, which never required
trading back above anything in particular). **The mechanism works. It
does not produce a net edge** -- the reclaim is real, but not reliably
followed by enough continuation to clear costs and the gate's other
three conditions.

### Sweep depth (x ATR) at detection

| min | median | max | n |
|---|---|---|---|
| 0.1000 | 0.1626 | 0.9994 | 15,822 |

Both boundaries are touched almost exactly at their own frozen edges
(min lands at the 0.1x floor, max just under the 1.0x ceiling) --
confirms both thresholds are doing real, binding work. **The median
(0.1626x) sits close to the floor** -- most real sweeps are shallow
ones, not deep ones, consistent with `TOUCH_TOO_SHALLOW` (2,987) being
a much smaller count than `NO_SWEEP` (107,824): most days never breach
`LOOKBACK_LOW` at all, and most of the ones that do breach qualify as a
sweep on the first breach rather than lingering in the too-shallow zone.

### New low during the reclaim wait

**8,962 of 15,822 days that reached RECLAIM (56.6%) saw a new low below
the running `sweep_low` before either reclaiming or running out of
candles.** The "track the low, don't reset the clock" rule (hand-traced
and verified in Process Step 2) is not an edge case -- it governs the
majority of reclaim attempts, meaning `STOP` is more often set from a
candle AFTER the original sweep than from the sweep candle itself.

### Realised stop distance (% of entry) and costs

| | min | median | max |
|---|---|---|---|
| Stop distance | 0.501% | 0.981% | 4.926% |
| Cost (% of position) | 0.160% | 0.270% | 0.341% |

Total costs: **Rs 217,868** across 3,225 trades. Both guards hold near
their own boundaries (min just above the 0.5% floor, max just under the
5% ceiling) -- unlike V2/V3, almost nothing gets rejected by either
guard (`stop_too_wide` 16, `stop_too_tight` 112, out of 3,384 fills that
reached this stage) -- the sweep-depth bounds (0.1x-1.0x ATR) already do
most of the work a fixed-percentage guard would otherwise need to.

### Trade count against V2's 22,959: the full funnel, not a category-by-category delta

V4's early-stage skip taxonomy shares nothing with V1-V3's touch/
confirmation categories (no `NO_TOUCH`/`POC_FAILED`/`NO_CONFIRMATION` --
replaced entirely by sweep/reclaim), so the honest comparison is a
funnel, not a side-by-side delta table:

| Stage | Count | Fraction of prior stage |
|---|---|---|
| Total setups checked | 278,695 | -- |
| ... minus `lookback_incomplete` (42,802), `trend_filter_failed` (108,905) | 126,988 eligible | 45.6% |
| ... minus `no_sweep` (107,824) | 19,164 ever breached `LOOKBACK_LOW` | 15.1% |
| ... minus `touch_too_shallow` (2,987), `breakdown_not_sweep` (355) | **15,822 reached SWEEP** | 82.6% |
| ... minus `not_reclaimed` (11,579) | 4,243 reached RECLAIM | 26.8% |
| ... minus `no_fill_bar` (187), `fill_outside_window` (672) | 3,384 filled | 79.8% |
| ... minus `entry_below_stop` (0), `stop_too_wide` (16), `stop_too_tight` (112), `no_room` (31) | **3,225 ENTERED** | 95.3% |

(Funnel balances exactly: 278,695 total setups, every skip category plus
3,225 trades sums to the total, confirmed before writing this up.)
**Claude's own pre-committed prediction -- "three filters now stack" --
is directly visible here**: the sweep-depth bound alone discards 84.9%
of eligible days outright (`no_sweep`), and the reclaim window then
discards 73.2% of what's left (`not_reclaimed`) -- the two new filters
together, not the carried-over V2 guards (which reject almost nothing,
see above), are entirely responsible for the 86% drop from V2's 22,959
to V4's 3,225.

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

## POC family: four trials, four failures -- closed permanently

| Trial | Result | What changed |
|---|---|---|
| V1 | -0.6733 R | original design -- contaminated by a sizing pathology (`OPERATIONS.md` standing rule) |
| V2 | -0.4077% | pathology removed (fixed-capital sizing); stop moved to the 5-day lookback low; still loses |
| V3 | -0.3176% | confirmation timeframe moved to hourly; still loses |
| V4 | -0.2862% | entry condition replaced entirely (liquidity sweep + reclaim); still loses |

Four trials, each a revision proposed after watching the one before it
fail, each measured loss smaller than the last -- **and not one of the
four ever crossed zero.** V4 came the closest (two of four gate
conditions passed, and the entry-above-level mechanism worked exactly
as designed) and still failed the gate's own all-or-nothing standard.
Weighed against this project's own swing V1 precedent -- a result that
cleared Bonferroni and Benjamini-Hochberg correction on 65,219 trades
still failed its sealed holdout -- a V4 that didn't even clear its own
DEV gate is not a result that should produce a V5.

**Per `PREREGISTRATION_POC_V4.md` Section 15: this was explicitly
declared the last trial in this family. The POC family is closed,
permanently.** No further override is anticipated; a V5 would require a
new pre-registration explicitly addressing the swing V1 precedent and
arguing why a fifth revision of a four-times-failed idea deserves to be
run.

## Status

**DEV run complete, gate failed, TEST never read.** Per Process Step 3,
stopping here for the user's approval before any sealed-window access --
and per Section 10/15 above, that approval will not be sought, since DEV
already failed decisively and the preregistration's own gate already
decided the outcome: the study closes, the sealed TEST window stays
unread, and the POC family is closed.
