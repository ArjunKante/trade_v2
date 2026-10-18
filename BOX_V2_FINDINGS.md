# Box Theory V2 (strength-filtered): experiments log

Companion to `PREREGISTRATION_BOX_V2.md` (frozen rules) and, for
everything V2 reuses unchanged, `BOX_THEORY.md`/`PREREGISTRATION_BOX.md`
(V1's own closed study). This file records what was actually run and
found, in the order it happened, per `PREREGISTRATION_BOX_V2.md`'s
Process section.

**Provenance, repeated from the preregistration document and not
repeated again at each entry below**: V1 closed at DEV with NO EDGE
(both FAST and SLOW, 0th percentile against the SELECTION null). V2 is
a revision proposed by the user after seeing that failure -- it carries
selection pressure V1 did not, is development evidence only, and is the
THIRD trial in the box theory family (V1 FAST, V1 SLOW, V2). A pass
below justifies forward paper trading at most, never a validity claim.

## Step 2: hand-traced trades, before any aggregate number

Five real DEV-window trades/skips, picked from a 40-entity/2017 sample
run (`src/box_theory/v2.run_backtest_v2`) to cover each required case,
then independently hand-checked against the raw 1-minute archive and
the frozen rules in `PREREGISTRATION_BOX_V2.md` Section 3. All five
check out exactly.

### 1. 1st-candidate confirms -- INE069I01010 (band 51-100), 2017-06-19

PREV_HIGH = 207.75, PREV_LOW = 195.35. Touch at **11:45** (low 194.30
<= 195.35). Trailing 8-candle window ending at touch: mean range
0.7000, mean volume 239,118.9 -> thresholds range >= 1.05, volume >=
358,678.3. **1st candidate (11:50)**: green (close 195.55 > open
194.75), range 1.40 >= 1.05, volume 395,574 >= 358,678.3 -- confirms,
`which_candle=1`. Fill at the 11:55 bar's open = **195.50**. Room =
(207.75-195.50)/195.50 = **6.27%** >= 5% -> enters. qty = floor(500 /
(0.03 x 195.50)) = **85**. Never armed; exits at the 15:15 close =
200.35. pnl = 85 x (200.35-195.50) = **+Rs 412.25**, net R matches the
backtest's own stored value exactly.

### 2. 2nd-candidate confirms -- INE002S01010 (band 101-200), 2017-05-24

PREV_HIGH = 983.00, PREV_LOW = 933.80. Touch at **13:15** (low 930.10
<= 933.80). Trailing window: mean range 3.4625, mean volume 1,589.0 ->
thresholds range >= 5.1937, volume >= 2,383.5. **1st candidate
(13:20)** is red (close 933.65 < open 934.00) -- fails on color alone,
regardless of its range/volume. **2nd candidate (13:25)**: green,
range 5.60 >= 5.1937, volume 3,904 >= 2,383.5 -- confirms,
`which_candle=2`. Fill at the 13:30 bar's open = **930.05**. Room =
(983.00-930.05)/930.05 = **5.69%** >= 5% -> enters. qty = 17. Exits at
15:15 close = 936.80. pnl = 17 x 6.75 = **+Rs 114.75**.

### 3. Skipped: no strong candle -- INE692A01016 (band 51-100), 2017-01-02

PREV_HIGH = 125.40, PREV_LOW = 121.65. Touch at **11:25** (low 121.65
<= 121.65, exactly at the boundary). Trailing window: mean range
0.4000, mean volume 30,949.0 -> thresholds range >= 0.60, volume >=
46,423.5. **1st candidate (11:30)** is red (close 122.05 < open
122.40) -- fails immediately. **2nd candidate (11:35)**: green, but
range 0.30 < 0.60 -- fails the range threshold. Neither of the only
two candidates checked qualifies -- **skipped, `NO_STRONG_CANDLE`**, no
third candle is ever considered.

### 4. Skipped: insufficient room at 5% -- INE692A01016 (band 51-100), 2017-02-15

PREV_HIGH = 148.00, PREV_LOW = 142.80. Touch at **10:45** (low 142.60
<= 142.80). Trailing window: mean range 0.6625, mean volume 54,816.9 ->
thresholds range >= 0.9938, volume >= 82,225.3. **1st candidate
(10:50)**: green, range 1.35 >= 0.9938, volume 223,384 >= 82,225.3 --
confirms cleanly, `which_candle=1`. Fill at the 10:55 bar's open =
**143.50**. Room = (148.00-143.50)/143.50 = **3.14%** -- below the 5%
floor, so the day is skipped under `no_room` even though confirmation
itself was clean and strong. This is the case the 5% floor (Change 3)
exists to filter: a genuinely strong reversal that simply does not
leave enough room to the previous high to be worth the risk under this
rule.

### 5. 1st-candidate confirms, STOP exit -- INE669E01016 (band 51-100), 2017-03-20

PREV_HIGH = 113.9953, PREV_LOW = 107.0044 (raw scale, scale-probe-
converted). Touch at **10:10** -- a sharp single-candle move (range
10.10 on its own) drops the low to 101.00, well through PREV_LOW.
Trailing window: mean range 1.7770, mean volume 5,794,506.9 ->
thresholds range >= 2.6655, volume >= 8,691,760.3. **1st candidate
(10:15)**: green, range 3.7129 >= 2.6655, volume 22,434,978 >=
8,691,760.3 -- confirms, `which_candle=1`. Fill at the 10:20 bar's own
open = **102.505467**. Room = (113.9953-102.5055)/102.5055 = **11.21%**
>= 5% -> enters. qty = floor(500 / (0.03 x 102.505467)) = **162**.
Stop = 102.505467 x 0.97 = **99.430303**. The very next few 1-minute
bars crash hard (the 10:20 candle's own low reaches 92.65) -- the stop
fires at **10:22**, filled exactly at the stop level (that bar's own
open was still above it). pnl = 162 x (99.430303-102.505467) = **-Rs
498.18**.

**All five traces independently reproduce the backtest's own stored
fields exactly** -- touch index, the trailing-window mean range/volume
and the derived thresholds, which candidate confirmed and why the other
failed (or why neither did), fill price and timestamp, room calculation,
stop level, exit price/timestamp, quantity, and net R/pnl. No
discrepancy found.

## Step 3: DEV result -- NO EDGE. Study closes.

**Bad result, stated first, per discipline**: V2 also fails DEV, on all
four criteria. Mean net R is negative (**-0.1037**, 97.5% CI
[-0.1960, -0.0119] -- excludes zero, on the losing side), the SELECTION
null percentile is **27.7**, far short of the 95th-percentile bar, the
mean stays negative (**-0.1264**) after dropping the single best
calendar year, and the bands-1-100 mean is also negative (**-0.0913**).
Per `PREREGISTRATION_BOX_V2.md` Section 7, **the study closes at DEV.
The sealed TEST window is never read.**

**The failure is quieter than V1's, and that difference is itself
informative, not a consolation.** V1's SELECTION-null percentile was
0.0 for both configs -- the touch population it traded lost to EVERY
one of 500 random day-selections. V2's is 27.7 -- it beats more than a
quarter of 1000 random day-selections on the same cost model, a real
improvement in kind, just nowhere near the 95th-percentile bar DEV
requires. The strength filter changed WHICH days get selected in a
direction that matters statistically; it did not change it enough to
clear a 95% confidence bar with a 401-trade sample.

### Scale, confirming the preregistration's own prediction

| | V1 FAST | V1 SLOW | V2 |
|---|---|---|---|
| Trades | 82,365 | 100,338 | **401** |
| Distinct days | 1,530 | 1,530 | 284 |

V2 trades at **0.49% of V1 FAST's rate** -- the strength filter and the
5% room floor together select a population more than two orders of
magnitude smaller, exactly the "much smaller subset" the preregistration
anticipated, not merely a retuned threshold on the same mechanism.

### Full result

| | |
|---|---|
| Trades / distinct days | 401 / 284 |
| Win rate | 39.40% |
| Mean net R (97.5% CI) | **-0.1037** [-0.1960, -0.0119] |
| Median net R (descriptive) | -0.1133 |
| MDE | 0.0933 (an order of magnitude wider than V1's ~0.0197-0.0198 -- the smaller sample's CI is mechanically wider, exactly as flagged in the preregistration) |
| TIMING null percentile | 100.0 |
| SELECTION null percentile | **27.7** |
| Seeds (both nulls) | 1000 (neither null's timed probe exceeded the 1-hour budget) |
| Ex-best-year mean (drops 2018) | -0.1264 |
| Bands 1-100 mean | -0.0913 |
| Exit mix | TIME_EXIT 309 (77.1%) / STOP 82 (20.4%) / ARMED_EXIT 10 (2.5%) |
| Ever armed | 14 of 401 (3.5%) -- far lower than V1's ~13% |
| Which candidate confirmed | 1st: 216 (53.9%) / 2nd: 185 (46.1%) -- roughly balanced |
| Room at entry (fraction) | mean 7.08%, median 6.17%, p25 5.44%, p75 7.59%, max 37.0%, min 5.01% -- the 5% floor is doing real work: the distribution sits just above the floor, not far above it |
| Missing-15:15 fallback | 0 trades |
| **DEV_PASS** | **False** |

**By year (net R)**: 2016 -0.236 (14 trades), 2017 -0.203 (30), **2018
+0.00001** (72 -- essentially flat, the only non-negative year), 2019
-0.167 (75), 2020 -0.146 (88), 2021 -0.042 (76), 2022 -0.079 (46).
Dropping 2018 (the best year, barely breakeven) makes the pooled mean
MORE negative, not less -- there is no good year propping this result
up; even the best year was a wash.

**By band (net R)**: 1-50 -0.108 (79 trades), 51-100 -0.080 (114),
101-200 -0.115 (208). Negative everywhere, no thin-band dependency.

**Internal consistency check, worth recording**: V1's `bad_previous_
session`/`ex_date`/`jump_guard` skip counts (16,301 / 70 / 0) are
IDENTICAL to V2's, and V1's `no_touch` diagnostic (277,128) is exactly
2x V2's (138,564) -- expected, since V1 evaluates its eligibility
pipeline once per day but then checks BOTH FAST and SLOW against it,
while V2 checks once. This is the reused `eligible_day_context`
pipeline behaving identically for both studies, not independently
re-derived -- a sanity check that passed, not a coincidence.

**Skip/diagnostic breakdown specific to V2**: `insufficient_candles`
63,430 (touch occurred in the first three 5-minute candles of the day,
too early to judge a trailing 40-minute window) -- by far the largest
single skip reason, larger than `bad_previous_session`. `no_strong_
candle` 54,662 (touch had enough history, but neither of the two
candidate candles was both green and materially bigger/busier than the
trailing window) -- confirms the strength filter is doing exactly what
it was designed to do: of roughly 193,000+ touch-days that reached a
real strength check, well over half never produced a qualifying
candle at all. `no_room` (at the 5% floor) 3,527 -- notably SMALLER
than V1's 9,916 at the 1% floor, which looks backwards until the
population each is drawn from is accounted for: V1's room check runs
against nearly every touch (confirmation was almost automatic), so a
large population hits a loose filter; V2's room check only runs
against the much smaller population that already survived the strength
filter, so a small population hits a strict filter. The raw counts are
not comparable without that context.

**SELECTION null matched counts**: 70 distinct calendar months had at
least one V2 trade (full breakdown in `v2_dev_report.json`'s
`selection_null_matched_counts_per_month`), ranging from 1 trade/month
(several months) to 20 (2020-03, the COVID crash month). The null was
matched per month to these exact counts, not an aggregate approximation.

**BASELINE**: reused directly from V1's own `dev_baseline.pkl`
(mean net return -0.43%, 255,980 stock-days) rather than recomputed --
correct, since BASELINE depends only on the universe, window, and cost
model, none of which differ between V1 and V2. Stated here so the reuse
is visible, not silently assumed.

**Day-error handler**: 0 trades skipped across the full run. Not a
finding.

**Runtime**: 56.8 minutes end to end, Stage 4 (SELECTION null) covering
70 months at ~30-38s/month pool build. No restart was needed -- the
checkpointing added after V1's run was available throughout but never
had to prove itself this time.

**Status: closed.** Per `PREREGISTRATION_BOX_V2.md` Sections 7 and 10,
this result is not rescued by retrying the 1.5x multipliers or the
8-candle window at other values. The box theory family has now spent
all three of its pre-registered trials (V1 FAST, V1 SLOW, V2). A
further revision needs its own new pre-registration and its own
trial-counter entry.
