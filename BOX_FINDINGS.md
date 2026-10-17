# Box Theory: experiments log

Companion to `BOX_THEORY.md` (process record) and `PREREGISTRATION_BOX.md`
(frozen rules). This file records what was actually run and found, in the
order it happened, per `PREREGISTRATION_BOX.md`'s Process section.

**Both of PREREGISTRATION_BOX.md's opening caveats apply to every result
below and are not repeated at each entry: (1) this tests ONE mechanical
interpretation of a discretionary idea, not the idea itself; (2) all
2016-2026 data has been read by earlier projects, so a pass is
development evidence for forward paper trading, never a validity claim.**

## Step 2: hand-traced trades, before any aggregate number

Five real DEV-window trades, picked from a 40-entity/2017 sample run
(`src/box_theory/backtest.run_backtest`) to cover each required exit
type, then independently hand-checked against the raw 1-minute archive
and the frozen rules in `PREREGISTRATION_BOX.md` Section 3. All five
check out exactly -- every intermediate value (touch candle, confirming
candle, fill price/time, room, stop, arming, exit) matches a value a
human could compute directly from the printed candles below.

### 1. STOP exit -- INE034A01011 (band 51-100), 2017-12-14, FAST

PREV_HIGH = 438.80, PREV_LOW = 424.00 (from 2017-12-13's raw-scale
session).

| ts | open | high | low | close | color |
|---|---|---|---|---|---|
| 09:15 | 428.886 | 429.000 | 425.257 | 426.857 | red |
| 09:20 | 426.800 | 427.086 | 423.457 | 424.743 | red -- **touch** (low 423.457 <= 424.00) |
| 09:25 | 424.743 | 426.400 | 424.743 | 426.000 | green -- **confirms FAST** |
| 09:30 | 426.057 | 426.686 | 425.286 | 425.486 | red -- **fill bar, open = entry = 426.057143** |

Room = (438.80 - 426.057) / 426.057 = 2.99% >= 1% -> enters. Stop =
426.057143 x 0.97 = **413.275429**. qty = floor(500 / (0.03 x
426.057143)) = floor(39.12) = **39**. The stop was touched cleanly (the
breaching bar's own open was above the stop level) at **11:33**, exit
price = stop level exactly = 413.275429. Never armed (high never reached
0.995 x 438.80 = 433.586 before the stop fired).

pnl = 39 x (413.275429 - 426.057143) = **-Rs 498.49**. Net R (after
costs, band 51-100 = 4.0bps + swing INTRADAY statutory/fixed) =
**-1.100408** (matches the backtest's own `net_r` column for this trade
exactly).

### 2. ARMED_EXIT -- INE008A01015 (band 101-200), 2017-05-05, FAST

PREV_HIGH = 82.30, PREV_LOW = 80.40.

| ts | open | high | low | close | color |
|---|---|---|---|---|---|
| 09:15 | 81.80 | 81.85 | 80.80 | 81.00 | red |
| 09:20 | 80.95 | 80.95 | 80.30 | 80.75 | red -- **touch** (low 80.30 <= 80.40) |
| 09:25 | 80.75 | 81.25 | 80.70 | 81.05 | green -- **confirms FAST** |
| 09:30 | 81.05 | 81.25 | 80.85 | 81.00 | red -- **fill bar, entry = 81.05** |

Room = (82.30-81.05)/81.05 = 1.54% -> enters. qty = floor(500/(0.03 x
81.05)) = **205**. Arming threshold = 0.995 x 82.30 = 81.8885. Scanning
5-minute candles from the entry candle (09:30) onward, the **11:00**
candle is the first to reach it (high 81.95 >= 81.8885) -> **armed**.
First red candle after arming: **11:05** (open 81.85, close 81.50).
Confirming candle closes at 11:10 -> fill at the 11:10 1-minute bar's
own open = **81.60** (visible directly in the 5-minute table as that
candle's open).

pnl = 205 x (81.60 - 81.05) = **+Rs 112.75**. Net R = **+0.137566**
(matches).

### 3. 15:15 time exit -- INE987B01026 (band 101-200), 2017-11-29, FAST

PREV_HIGH = 944.996, PREV_LOW = 923.804.

Touch at **09:20** (low 921.202 <= 923.804); FAST confirms at **09:30**
(green, close 922.100 > open 921.898, after a red 09:25 candle that did
not confirm); fill at the 09:35 bar's open = **923.047501**. Room =
2.38% -> enters, stop = 895.356, qty = **18**. The day's high after entry
never exceeded ~924 (arming threshold was 940.271 -- never reached), and
the stop (895.356) was never touched either (lows stayed in the 913-925
range all day). Nothing triggered by the 15:15 candle's own close, so
the trade exits there: candle at ts=15:15 has close = **917.945953**,
exit_ts = 15:20 (the candle's own close-time boundary) per the frozen
rule.

pnl = 18 x (917.945953 - 923.047501) = **-Rs 91.83**. Net R =
**-0.297051** (matches).

### 4. Gap-down touch at the open -- INE002A01018 (band 1-50), 2017-03-09, FAST

PREV_HIGH = 1307.717, PREV_LOW = 1286.083 (previous session, 2017-03-08,
375 archive bars -- a clean, fully-covered prior session; the scale
factor recovered here, ~4.051, converts Angel's archive units into raw
rupees and was independently cross-checked: 1307.717/322.78 = 4.0509 and
1286.083/317.44 = 4.0510, agreeing to within the 0.1% tolerance `fibo.
scale_probe.probe_scale` requires).

The **very first candle of the day** (09:15, open 1290.013, low
1284.989) already touches PREV_LOW -- the session opened at/through
yesterday's low, so `touch_idx = 0` by construction; this is the "gap-
down touch at the open" case the hand-trace set specifically needed.
That candle's own green close does not count as confirmation (confirming
candles must come strictly AFTER the touch candle, per Section 3b) --
09:20 is red, 09:25 is green and confirms. Fill at the 09:30 bar's open
= **1290.053244**. Room = (1307.717-1290.053)/1290.053 = 1.37% -> enters
(just clears the 1% floor). qty = **12**. Neither the stop (1251.35) nor
the arming threshold (1301.18) was reached; the trade time-exits at
15:15's close = 1288.838.

pnl = 12 x (1288.838 - 1290.053) = **-Rs 14.59**. Net R = **-0.119343**
(matches).

### 5. Skipped for no room -- INE180A01020 (band 101-200), 2017-03-28, FAST

PREV_HIGH = 581.50, PREV_LOW = 573.95.

| ts | open | high | low | close | color |
|---|---|---|---|---|---|
| 12:50 | 576.70 | 576.90 | 576.00 | 576.10 | red |
| 12:55 | 577.00 | 577.75 | 573.00 | 575.30 | red -- **touch** (low 573.00 <= 573.95) |
| 13:00 | 575.10 | 577.00 | 575.10 | 576.40 | green -- **confirms FAST** |
| 13:05 | 575.90 | 576.40 | 574.10 | 574.80 | red -- **fill bar, would-be entry = 575.90** |

Room = (581.50 - 575.90) / 575.90 = **0.9724%** -- below the 1.0% floor,
so the day is skipped (no trade), under the "no room" reason. This is
the ONLY one of the five examples where no position is ever opened,
by design (the hand-trace set requires exactly this case per Process
Step 2).

**All five traces independently reproduce the backtest's own stored
fields exactly** -- touch/confirmation indices, fill price and
timestamp, room check, stop level, arming threshold and candle, exit
price/timestamp, quantity, and net R. No discrepancy found.

## Step 3: DEV result -- NO EDGE, both configurations. Study closes.

**Bad result, stated first, per discipline**: both FAST and SLOW fail
DEV decisively. Mean net R is significantly negative for both, with
the day-clustered bootstrap CI excluding zero on the LOSING side, and
both configurations land at the **0th percentile against the
SELECTION null** -- random-day entry on the same universe-year
population beat this touch-and-reversal signal in every one of 500
resampled draws. Per `PREREGISTRATION_BOX.md` Section 7, since both
configurations fail, **the study closes at DEV. The sealed TEST window
is never read** -- this is the pre-registered rule resolving itself,
not a separate decision made after seeing the number.

Full run: 182,703 trades (82,365 FAST + 100,338 SLOW) across 1,530
distinct trading days, 2016-10-04 to 2022-12-31, both configurations
evaluated against the full top-200 DEV universe. 500 seeds per null
(the preregistered fallback -- both configs' timed small runs projected
well past the 1-hour budget at 1000 seeds, logged at the time).

### FAST

| | |
|---|---|
| Trades / distinct days | 82,365 / 1,530 |
| Win rate | 36.65% |
| Mean net R (97.5% CI) | **-0.1380** [-0.1572, -0.1179] |
| Median net R (descriptive) | -0.1315 |
| MDE | 0.0197 |
| TIMING null percentile | 100.0 |
| SELECTION null percentile | **0.0** |
| Ex-best-year mean (drops 2020) | -0.1419 |
| Bands 1-100 mean | -0.1266 |
| Exit mix | TIME_EXIT 64,690 / ARMED_EXIT 9,860 / STOP 7,815 |
| Ever armed | 10,641 of 82,365 (12.9%) |
| Missing-15:15 fallback | 26 trades |
| **DEV_PASS** | **False** |

By year (net R): 2016 -0.186, 2017 -0.134, 2018 -0.133, 2019 -0.128,
2020 -0.118 (best year), 2021 -0.160, 2022 -0.144. By band: 1-50
-0.119, 51-100 -0.134, 101-200 -0.151.

### SLOW

| | |
|---|---|
| Trades / distinct days | 100,338 / 1,530 |
| Win rate | 36.76% |
| Mean net R (97.5% CI) | **-0.1260** [-0.1455, -0.1062] |
| Median net R (descriptive) | -0.1280 |
| MDE | 0.0198 |
| TIMING null percentile | 100.0 |
| SELECTION null percentile | **0.0** |
| Ex-best-year mean (drops 2020) | -0.1303 |
| Bands 1-100 mean | -0.1160 |
| Exit mix | TIME_EXIT 80,032 / ARMED_EXIT 11,684 / STOP 8,622 |
| Ever armed | 13,889 of 100,338 (13.8%) |
| Missing-15:15 fallback | 30 trades |
| **DEV_PASS** | **False** |

By year (net R): 2016 -0.167, 2017 -0.122, 2018 -0.127, 2019 -0.113,
2020 -0.104 (best year), 2021 -0.147, 2022 -0.132. By band: 1-50
-0.108, 51-100 -0.124, 101-200 -0.138.

**This is not one bad year or one thin band carrying an otherwise-
working rule.** Dropping the single best calendar year barely moves
either mean. The liquid names (bands 1-50/51-100) lose at essentially
the same rate as band 101-200 -- the result that sank Fibo's own sealed
test (thin-band dependency) does not apply here; this one fails
everywhere at once.

**Skipped days**: no_room 9,916, bad_previous_session 16,301, ex_date
70, jump_guard 0. **Diagnostics** (not skips -- days that reached a
signal check and found nothing): no_touch 277,128, no_confirmation
7,167, no_fill_bar 3,841, fill_outside_window 40,515, zero_qty 3,378.

**Per-trade exception handler**: 0 trades skipped, across both
configs, in the full run. Not a finding.

**Missing-15:15 fallback**: 56 trades total (26 + 30) of 182,703 --
0.03%. Negligible, as expected from an archive-completeness edge case.

**BASELINE (descriptive, not part of the gate)**: 255,980 stock-days,
mean net return -0.43%, median -0.51% -- plain buy-09:30/sell-15:15 on
an ordinary top-200 day is also mildly negative after costs, but
nowhere near the -12 to -14% per unit risk this strategy loses. The
signal does not merely fail to add value over doing nothing in
particular -- it picks worse entries than either the baseline or a
random time on the same touch-day (the TIMING null, which it did
beat). The failure is in which stock-days get selected, not when
within the day the trade fires.

**Engineering note, not a result**: this run needed six process starts
across two genuine code bugs (a short-day time-exit edge case; retained
DataFrames bloating `build_timing_pool`'s memory) and at least two
environment-level kills unrelated to either, totalling roughly 17 hours
of wall clock for about 4 hours of actual computation. Full retrospective
in `OPERATIONS.md`'s "The Box Theory DEV run cost ~17 hours..." section --
recorded there because the lesson (checkpoint unattended jobs from the
start; measure memory/timing before launch, not after) is general to
this project, not specific to this study.

**Status: closed.** Per `PREREGISTRATION_BOX.md` Section 7 and Section
10's discipline, this result is not rescued by a variant, a different
interval, or a relaxed threshold. If box theory is revisited, it needs
its own new pre-registration and its own trial-counter entry -- this
one is spent.
