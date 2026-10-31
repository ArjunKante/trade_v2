# Liquidity confluence, Study B (short only): experiments log

Companion to `PREREGISTRATION_LIQUIDITY_B.md` (frozen rules, commit
`1f4bd6f`). Liquidity family, trial 2 -- exact mirror of Study A (closed,
no edge, `LIQUIDITY_A_FINDINGS.md`) on the short side. Records what was
actually run and found, per the preregistration's own Process section.

## Synthetic unit tests (Process Step 2)

`scripts/liquidity_b_unit_test.py` -- pure-function scenarios, no DB
access, mirroring `liquidity_a_unit_test.py`'s own 14-scenario test:
HIGH-level confluence clustering (no cluster, a pair, all three mutually,
and the chain-via-shared-node case), plus the short-side scaled-exit
resolution shapes (full 3R across two bars, same-bar half-then-full, stop
before any half exit, half exit then stop on the remainder, half exit
then a 15:15 time exit on the remainder, qty=1's own simpler path, and
nothing-hit producing a full-position time exit). **All 14 checks passed
on the first run.**

## Hand-traced examples (Process Step 3)

All 5 required shapes -- a full 3R target, a stop before any half exit,
a half exit followed by a stop on the remainder, a 15:15 time exit with
the second half still open, and a `NO_CONFLUENCE` skip -- found by
`scripts/liquidity_b_handtrace.py` against the real DEV window, all
within the first 7 entities scanned (4 of the 5 on the very first entity,
`INE002A01018`, the same entity Study A's own hand-trace used). Every
number below was independently recomputed by hand from the script's own
printed inputs before being trusted; all matched to within display
rounding.

### 1. NO_CONFLUENCE -- INE002A01018, 2016-10-25

`HIGH levels: 3m=1129.5500, 1w=1098.0000, 1d=1074.0000`, `ATR_raw=23.7896`,
tolerance `0.5xATR=11.8948`. Pairwise diffs: `3m-1w=31.55`, `3m-1d=55.55`,
`1w-1d=24.00` -- all three far beyond tolerance, `NO_CONFLUENCE` confirmed
by hand from the three raw numbers alone.

### 2. STOP_NO_HALF (stop hit before any half exit) -- INE002A01018, 2017-01-03

`HIGH levels: 3m=1126.25, 1w=1090.00, 1d=1090.00`, `ATR_raw=17.6439`,
tolerance `8.8220`. `1w-1d` diff `0 <= 8.8220` -- the only qualifying
pair; `3m` sits far from both (diff 36.25). **Zone = mean(1090, 1090) =
1090.00**.

- Sweep at 09:45 (idx 6): high `1093.9975`. `depth = 1093.9975 - 1090 =
  3.9975`, `depth/ATR = 0.2266` -- within range. Reclaim at 10:00 (idx 9),
  close `1089.7436` clears back below the zone.
- Fill at 10:05 (reclaim candle's own close) -> **entry = 1089.6626**
  (SHORT). `STOP = 1093.9975 + 0.1x17.6439 = 1095.7619`
  (`stop_distance_pct = (1095.7619-1089.6626)/1089.6626 = 0.5597%`, just
  above the 0.5% floor). `HALF_TARGET = 1080.5135`, `FULL_TARGET =
  1071.3644`. `qty = floor(25000/1089.6626) = 22`, `half_qty = 11`.
- The stop (1095.7619) is hit at 13:00, before the half-target level is
  ever reached -- **`STOP_NO_HALF`, full 22 shares covered at
  1095.7619.**
- `pnl_rs = 22x(1089.6626-1095.7619) = -134.19`. `position_size_rs =
  23,972.58`. Cost model, independently re-summed by hand: entry leg is
  the SELL (open) -- `sell_leg_cost_rs(23972.58)` = STT 5.99 + exchange
  0.71 + SEBI 0.02 + brokerage 20.00 (capped) + GST 3.73 = 30.46, plus
  half-spread (band 1-50, 1.0bps) 2.40 -> **entry leg = 32.86**. Exit leg
  is the BUY (cover) on `22x1095.7619=24,106.76` -- `buy_leg_cost_rs` =
  stamp 0.72 + exchange 0.72 + SEBI 0.02 + brokerage 20.00 + GST 3.73 =
  25.20, plus half-spread 2.41 -> **exit leg = 27.61**. **`total_cost_rs
  = 60.47`**, matching the script's own figure exactly. `hypothetical_
  cost_rs = 60.44` (box theory's own two-order formula on the same entry
  value) -- `extra_cost_rs = +0.02`, negligible here since only two real
  orders happened (no half exit), the same shape Study A's own
  `STOP_NO_HALF` example showed. **`net_return_pct = -0.8120%`.**
- **STT confirmation of the Section 6 prediction**: the entry (sell) leg
  carried the full STT charge (Rs 5.99, on the FIXED entry value
  23,972.58) and the exit (buy) leg carried none -- the opposite
  assignment from Study A's own `STOP_NO_HALF` example, where the BUY
  (entry) carried no STT and the SELL (exit, at the stop) carried it.

### 3. HALF_THEN_STOP -- INE019A01020, 2020-11-11

`HIGH levels: 3m=1w=1d=337.6500` -- all three IDENTICAL, a genuine
three-way cluster. `ATR_raw=9.2387`, tolerance `4.6194`. **Zone =
337.6500**.

- Sweep at 09:55 (idx 8): high `338.8500`, `depth/ATR = 0.1299`. Reclaim
  at 10:05 (idx 10), close `337.4000` clears back below the zone.
- Fill at 10:10 -> **entry = 337.2500** (SHORT). `STOP = 338.8500 +
  0.1x9.2387 = 339.7739` (`stop_distance_pct = 0.7489%`). `HALF_TARGET =
  333.4642`, `FULL_TARGET = 329.6784`. `qty = floor(25000/337.2500) =
  74`, `half_qty = 37`.
- Half-target hit at 11:14 -> 37 shares covered at `333.4642` (realised
  profit `37x3.7858=140.08`, locked in). Remainder (37 shares) then hits
  the stop at 13:05 -> covered at `339.7739` (loss `37x(-2.5239)=
  -93.38`) -- **`HALF_THEN_STOP`**, the half's own realised profit never
  clawed back.
- `pnl_rs = 37x3.7858 + 37x(-2.5239) = 140.08 - 93.38 = 46.69`
  (matches the script's own `46.69`). `position_size_rs = 24,956.50`.
  Three real orders: sell-to-open 33.99 + half-cover-buy 16.17 +
  remainder-cover-buy 16.61 = **`total_cost_rs = 66.77`**, vs.
  **`hypothetical_cost_rs = 60.99`** -- **`extra_cost_rs = +5.79`**, a
  genuine third-order cost, the same shape Study A's own
  `HALF_THEN_STOP` example showed. **`net_return_pct = -0.0805%`** -- a
  small net LOSS despite the half exit's own real profit, because the
  remainder's stop loss plus the extra order cost outweighed it -- the
  exact mirror of Study A's own `HALF_THEN_STOP` finding (`-0.1487%`
  there), same shape, smaller magnitude here.

### 4. FULL_EXIT (full 3R target reached) -- INE002A01018, 2019-10-01

`HIGH levels: 3m=1w=1d=1335.7500` -- all three IDENTICAL. `ATR_raw=
34.4750`, tolerance `17.2375`. **Zone = 1335.7500**, another genuine
three-way cluster.

- Sweep at 11:15 (idx 24): high `1339.9854`, `depth/ATR = 0.1229`.
  Reclaim at 11:30 (idx 27), close `1334.9009` clears back below the
  zone.
- Fill at 11:35 -> **entry = 1334.9009** (SHORT). `STOP = 1339.9854 +
  0.1x34.4750 = 1343.4329` (`stop_distance_pct = 0.6391%`).
  `HALF_TARGET = 1322.1028`, `FULL_TARGET = 1309.3048`. `qty =
  floor(25000/1334.9009) = 18`, `half_qty = 9`.
- Half-target hit at 13:22 -> 9 shares covered at `1322.1028`
  (`+12.80/share` realised). Remainder rides on; full target hit at
  13:57 -> 9 shares covered at `1309.3048` (`+25.60/share`).
  **`FULL_EXIT`**, the strategy's own best-case shape.
- `pnl_rs = 9x12.7981 + 9x25.5961 = 345.52` (script's own: `345.55`,
  matching to display rounding). `position_size_rs = 24,028.22`.
  `total_cost_rs = 64.76` (sell-to-open 33.21 + half-cover 15.73 +
  full-cover 15.82). `hypothetical_cost_rs = 60.47` -- `extra_cost_rs =
  +4.29`. **`net_return_pct = +1.1686%`** -- confirms the mechanism CAN
  produce a genuine win large enough to absorb the extra-order cost on
  the short side too, the mirror of Study A's own `FULL_EXIT` finding
  (`+1.7517%` there).

### 5. HALF_THEN_TIME_EXIT -- INE002A01018, 2018-02-15

`HIGH levels: 1w=1d=942.5000` (tied), `3m=990.9500` far. `ATR_raw=
21.9102`, tolerance `10.9551`. `1w-1d` diff `0` -- the only qualifying
pair. **Zone = 942.5000**.

- Sweep at 10:00 (idx 9): high `945.7478`, `depth/ATR = 0.1482`. Reclaim
  at 10:05 (idx 10), close `942.3041` clears back below the zone.
- Fill at 10:10 -> **entry = 942.3041** (SHORT). `STOP = 945.7478 +
  0.1x21.9102 = 947.9388` (`stop_distance_pct = 0.5981%`).
  `HALF_TARGET = 933.8520`, `FULL_TARGET = 925.3998`. `qty =
  floor(25000/942.3041) = 26`, `half_qty = 13`.
- Half-target hit at 11:18 -> 13 shares covered at `933.8520`
  (`+8.45/share` realised). Remainder never reaches the full target or
  the stop for the rest of the day -> **15:15 time exit, 13 shares
  covered at 936.0041** (the second half still open when the clock ran
  out, the exact shape required by name).
- `pnl_rs = 13x8.4521 + 13x6.3000 = 191.78` (matches script). `position_
  size_rs = 24,499.91`. `total_cost_rs = 65.79` (sell-to-open 33.68 +
  half-cover 16.00 + time-exit-cover 16.11). `hypothetical_cost_rs =
  60.74` -- `extra_cost_rs = +5.05`. **`net_return_pct = +0.5142%`** -- a
  larger net win than Study A's own analogous example (`+0.1296%`
  there), since the remainder gave back less of its own gain by the
  close here than in Study A's example.

**All five hand traces are internally consistent with the
preregistration exactly as written.** The HIGH-level confluence
clustering (a clean pair and two genuine three-way matches, all
different concrete shapes from Study A's own five LOW-level traces), the
new direction-aware sweep/reclaim formulas (`find_sweep_short`/
`find_reclaim_short`), the half/full risk-multiple targets BELOW entry,
all four distinct scaled-exit outcome shapes, the new
`_stop_target_event_short` tie-break, and the swapped-role three-order
cost model (STT confirmed landing entirely on the fixed-value entry/sell
leg, never on either cover/buy leg -- the Section 6 prediction, verified
by hand on example 2 above) were each exercised and independently
re-verified by hand before any aggregate number was computed.

## DEV result: FAILS. No edge -- same gate shape as Study A, different magnitude.

**Three findings recorded prominently, before the detail below, because
each one changes how this result should be read.**

### Finding 1: the cost asymmetry was confirmed exactly as predicted, and, as with Study A, costs are not the deciding factor

The entry (sell-to-open) leg's STT is a genuinely FIXED 0.025% of
position value on every single one of the 9,222 trades -- mean
Rs 6.11/trade, **standard deviation of the percentage across trades:
5.8e-20, i.e. zero to floating-point precision**. This is the structural
difference Section 6 of the preregistration predicted: Study A's own
exit-leg STT varies trade-by-trade with the realised exit price (a
winning trade's exit leg has a larger trade value than a losing one's,
so pays slightly more STT); Study B's entry-leg STT cannot vary at all,
since it is computed once, at entry, before anything else happens.

**This did not translate into a materially different COST figure in
aggregate, exactly as it should not have** -- the extra three-order cost
vs. the hypothetical single-exit-at-3R comparison totalled **Rs
11,693.01** across all trades, a mean of **Rs 1.27/trade, 0.0051% of
position value** -- essentially identical in magnitude to Study A's own
**Rs 10,095.30 total, Rs 1.24/trade, 0.0050%**. Both studies lose for the
same underlying reason (Finding 3 below, not cost), and the STT
asymmetry, while real and precisely confirmed, is two orders of
magnitude too small on both sides of this family to be the deciding
factor between a passing and failing result.

### Finding 2: the preserved confluence flaw recurs, but is quantitatively DIFFERENT, not identical, between sides

**65.6% of zones (6,052 of 9,222 trades) clustered on the 1-day and
1-week HIGH alone** -- lower than Study A's own **78.6%** on the LOW
side, not the same number. The gap is explained by the THREE-way cluster
rate, which runs the other way: **31.3% of Study B's trades (2,889) had
all three HIGH levels cluster together**, more than Study A's own
**19.6%** (1,596 LOW trades). (`1w+3m`-only, with `1d` excluded, is the
small remainder on both sides -- 3.0% here vs. 1.8% for Study A; a pure
`3m`-or-`1d`-only pair that excludes `1w` never occurs on either side,
the same structural fact Study A's own report noted.)

**The likely cause is the DEV window's own secular upward price drift,
stated plainly as the probable mechanism, not re-derived from first
principles**: across most of 2016-2022, Indian equities trended up far
more than they trended down. In a sustained uptrend, the most recent
high is frequently ALSO the highest point of the past week AND the past
3 months simultaneously -- a stock making fresh highs tends to make them
across every lookback window at once, pulling all three HIGH levels into
a single cluster more often. The LOW side does not have the mirror
property in the same market regime: a 3-month low, once set, is
typically set early and then LEFT BEHIND as price grinds upward -- the
1-week and 1-day lows keep floating higher and essentially never revisit
it, so the 3-month low rarely joins the 1-day/1-week low cluster (Study
A's own 19.6% three-way rate vs. this study's 31.3%). This is a genuine,
direction-caused difference in how "definitional" the overlap is on each
side, not a wash -- recorded here exactly as the preregistration's own
Section 11 asked, rather than smoothed into "both studies have the same
overlap problem."

### Finding 3: the failure is symmetric in WHICH gate conditions fail, but NOT in magnitude -- and Claude's own follow-through prediction was wrong

**Mean net return: -0.1212%** (day-clustered 97.5% CI **[-0.1598%,
-0.0816%]**, both bounds negative) -- a real loss, but **well under half
the size of Study A's own -0.2841%**. The same three gate conditions
fail (mean/CI, ex-best-year, bands 1-100) and the same one passes (both
nulls at the 100th percentile) -- structurally identical gate shape to
Study A -- but the MAGNITUDE of the short side's own loss is
substantially smaller, not a restatement of the same number.

**The reason is follow-through, and it runs the OPPOSITE direction from
my own pre-committed prediction.** I predicted the short side would show
"similar or slightly worse" follow-through than Study A's own 21.6%/
23.1% figures, reasoning that shorting fights the market's long-run
upward drift. **The real figures run the other way**: of the 9,098
scaled-eligible trades, **26.5% reached the half target** (vs. Study A's
own 21.6%), and the fraction of ALL trades that never even reach the
half-target level (`STOP_NO_HALF` + `TIME_EXIT_FULL`) is **72.5%** here
vs. Study A's own **77.1%** -- Study B's signal follows through MORE
often, not less. Of trades that did reach the half target, a slightly
smaller share went on to the full 3R target (21.3% vs. Study A's 23.1%)
and a smaller share gave the half exit's own profit back on the
remainder (3.7% vs. Study A's 5.3%) -- both consistent with a cleaner,
somewhat more decisive short-side move once the sweep-and-reclaim signal
actually fires. **I was wrong about the direction of this effect, the
same kind of miss Study A's own Finding 1 recorded about its own cost
prediction** -- weighted accordingly: a future revision of this entry
mechanism focused on follow-through should not assume shorting is
structurally worse here just because of the market's own secular drift.
Peak deployed capital is correspondingly lower too -- **28 peak
concurrent positions, Rs 633,789.78 peak deployed capital**, roughly half
of Study A's own corrected 46 positions / Rs 1,124,725.31 -- consistent
with fewer trades reaching the capital-intensive scaled-exit tail.

**Gate: 3 of 4 conditions fail -- same pattern as Study A.**

| Condition | Result | Verdict |
|---|---|---|
| Mean > 0, CI excludes zero | mean -0.1212%, CI fully negative | FAIL |
| >= 95th percentile vs. BOTH nulls | TIMING 100.0, SELECTION 100.0 | **PASS** |
| Positive after dropping the best year | -0.1370% (2020 excluded) | FAIL |
| Positive within bands 1-100 | -0.1159% | FAIL |

The gate requires all four; 3 failures is NO EDGE regardless of the one
pass. TEST is not read, per the preregistration's own Section 10.

**The null comparison is, again, the one genuinely positive finding**:
the real strategy beat BOTH the TIMING null (same stock-days, random
entry) and the SELECTION null (random stock-days, matched count per
month) at the **100th percentile** out of 500 seeds each, identically to
Study A. The confluence-plus-sweep-plus-reclaim entry carries real,
non-random selection value on the short side too; it is simply not
enough, after costs, to turn a net loss into a net gain.

### Side-by-side against Study A, per the preregistration's own Section 11

| Figure | Study A (long) | Study B (short) |
|---|---|---|
| Trades | 8,131 | **9,222** |
| Mean net return | -0.2841% | **-0.1212%** |
| TIMING null percentile | 100.0 | 100.0 |
| SELECTION null percentile | 100.0 | 100.0 |
| Half-target reach rate (of scaled-eligible) | 21.6% | **26.5%** |
| Full-target rate (of half-reached) | 23.1% | 21.3% |
| Pure 1d+1w confluence share | 78.6% | **65.6%** |
| All-three (1d+1w+3m) confluence share | 19.6% | **31.3%** |
| Extra 3-order cost, mean/trade | Rs 1.24 (0.0050% of position) | Rs 1.27 (0.0051% of position) |
| Entry/exit-leg STT variance (% of position) | varies with exit price | **zero (fixed 0.025%)** |
| Peak concurrent positions / capital | 46 / Rs 1,124,725 | **28 / Rs 633,790** |
| Gate conditions failed | 3 of 4 | 3 of 4 (same 3) |

**Stated plainly, per instruction: the failure is symmetric in STRUCTURE
(same gate conditions fail, both nulls pass at the identical 100th
percentile, the same preserved-flaw confluence overlap recurs) but NOT
symmetric in MAGNITUDE.** Study B loses at less than half the rate of
Study A, on a trade count that is actually slightly larger, driven by
genuinely better signal follow-through on the short side in this DEV
window -- the opposite of what I predicted going in. This is not "both
sides failed the same way"; it is "the same mechanism, run in both
directions, fails for the same structural reason (insufficient
follow-through to clear costs) but to a measurably different degree,"
and the degree difference is traceable to a specific, understood cause
(Finding 2's own uptrend-driven confluence-overlap asymmetry, and
Finding 3's own follow-through-rate asymmetry) rather than left
unexplained.

**Skip counts** (278,695 total candidate-days checked, identical
population to Study A since the universe does not depend on direction):
`no_sweep` 111,271; `no_confluence` 93,561 (LOWER than Study A's own
105,437 -- HIGH-side confluence was found on 167,739 days vs. Study A's
own 155,863 LOW-side days, consistent with Finding 2's own uptrend
explanation); `not_reclaimed` 35,431; `bad_previous_session` 16,301;
`touch_too_shallow` 8,459; `breakout_not_sweep` 1,321;
`level_insufficient_history` 1,024; `fill_outside_window` 1,148;
`no_fill_bar` 402; `stop_too_tight` 401; `zero_qty` 64 (higher than Study
A's own 49, consistent with HIGH levels running at generally higher raw
prices than LOW levels by the time 3 months of upward drift have
elapsed); `ex_date` 70; `stop_too_wide` 20; `atr_unavailable` 0;
`jump_guard` 0; **`entry_above_stop` 0**, confirming the Section 3 guard
prediction empirically, the exact mirror of Study A's own
`entry_below_stop` count of 0. `multi_cluster_count` across all 9,222
trades: **0**, confirming the Section 2 proof empirically on the HIGH
side too -- the "multiple separate clusters" branch mathematically
cannot execute with exactly three candidate levels, exactly as proved
for Study A's own LOW levels.

**By year**: every year 2016-2022 lost, from -0.04% (2020, the best
year, still negative) to -0.17% (2022, the worst) -- no year ever
crossed zero. **By band**: all three rank bands lost similarly (-0.09%
to -0.14%), no band showing a materially different result.

### Base rate, updated

Fourteen prior strategies in this project have now closed with no edge
(the thirteen implied by Study A's own updated count, plus this one).
The liquidity-confluence family has now failed on BOTH sides it was
tested on, with the same root cause each time (real, non-random
selection value from the sweep-and-reclaim entry; insufficient
follow-through to clear costs) and the same specific definitional flaw
(1-day/1-week overlap by construction) recurring on both the LOW and
HIGH side, at different but comparably material rates.

**Study B (short only) is closed: NO EDGE on DEV, TEST not read.** Per
`PREREGISTRATION_LIQUIDITY_B.md` Section 14, these exact parameters are
not retried at other values. A corrected, non-nesting-timeframe
confluence definition (Study C) remains a separate, not-yet-undertaken
trial of this same family.

## Status

DEV run complete and reported above. **Stopping here for approval before
TEST**, per the preregistration's own Section 12/Process -- TEST has not
been read and `liquidity.b.guard_date_range` has not been called with
`authorize_test=True` anywhere in this study.
