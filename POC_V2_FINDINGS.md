# POC bounce V2, fixed-capital sizing: experiments log

Companion to `PREREGISTRATION_POC_V2.md` (frozen rules, commit `12ef33e`).
POC family trial 2 -- a revision proposed by the user after seeing V1's
own DEV failure and its specific sizing pathology (`POC_FINDINGS.md`,
`OPERATIONS.md`'s standing rule). Carries selection pressure; any DEV
pass below is development evidence only, never a validity claim.
Records what was actually run and found, per that document's Process
section.

**Bottom line, stated first per this project's "bad results first"
discipline: DEV FAILS.** Mean net return = **-0.4077%** of position
value, 97.5% CI **[-0.4564%, -0.3580%]** -- excludes zero on the
NEGATIVE side, so the gate's first condition already fails, and the
gate requires ALL conditions. **Neither null was run, not even
partially** -- the run was stopped as soon as the primary condition was
decided, before the TIMING null's first seed completed (its pool had
just finished building). The sealed TEST window is never read. **POC
family trial count is now 2 -- V1 and V2 are both closed, both NO
EDGE.**

**The important comparison is not whether V2 passed -- it didn't -- it
is whether Change 1 (fixed-capital sizing) actually fixed V1's sizing
pathology. It did, cleanly:**

| | V1 (fixed-risk) | V2 (fixed-capital) |
|---|---|---|
| Maximum single-trade cost | **Rs 239,868.84** | **Rs 143.72** |
| Maximum position value | Rs 434,104,028 | Rs 91,710 |
| Mechanism of the maximum | stop 0.0004% from entry -> qty exploded to 3.5M shares | stock priced above Rs 25,000 -> the minimum-1-share floor applied, position = 1 share's own price |

A **1,669x** reduction in worst-case cost, and the one remaining source
of an above-Rs-25,000 position is fully understood, bounded, and
expected (a single real share of an expensive stock, not a sizing
defect) -- not a residual version of the same pathology. **POC lost
under two different sizing conventions and two different stop
definitions. The sizing pathology was real and is fixed. The strategy
still loses money. That is the cleaner finding than V1's own, because
V2's headline number is not contaminated by a sizing artifact the way
V1's was.**

## DEV result (partial -- nulls not run)

22,959 trades, 1,460 distinct entry days, full top-200-by-turnover
universe, real DEV window 2016-10-04 to 2022-12-31. Runtime: 31.8 min
for the real backtest; stopped during Stage 3 (TIMING null pool build
had just finished, zero seeds run) once the gate's primary condition
was already decided.

| | |
|---|---|
| Trades / distinct entry days | 22,959 / 1,460 |
| Win rate | 35.2% |
| Mean net return (97.5% CI) | **-0.4077%** [-0.4564%, -0.3580%] |
| Median net return (descriptive) | -0.3229% |
| MDE | 0.0490% |
| TIMING null | **not run** -- gate already failed |
| SELECTION null | **not run** -- gate already failed |
| Exit mix | TIME_EXIT 12,501 / TARGET 5,928 / STOP 4,530 |
| By year | 2016 -0.424% (442) / 2017 -0.316% (3,571) / 2018 -0.465% (2,921) / 2019 -0.422% (3,471) / 2020 -0.398% (4,098) / 2021 -0.439% (4,683) / 2022 -0.407% (3,773) |
| By band | 1-50: -0.356% (5,901) / 51-100: -0.382% (6,570) / 101-200: -0.453% (10,488) |
| **DEV_PASS** | **False** |

**Reminder, every time this figure is shown**: this is a PERCENTAGE OF
POSITION VALUE, not R. Not comparable to V1 or to any other study in
this project.

### Cost distribution (the direct test of Change 1)

| | min | median | max |
|---|---|---|---|
| Cost (Rs) | 37.23 | 65.98 | **143.72** |
| Cost (% of position value) | 0.157% | 0.272% | 0.341% |
| Position value (Rs) | 12,543.57 | 24,795.00 | 91,709.98 |

**Costs are now tightly clustered and bounded** -- max cost (Rs 143.72)
is barely 2.2x the median (Rs 65.98), nothing like V1's distribution
(where a handful of trades cost 100-480x their own nominal risk unit).
The single highest-cost trade, `INE883A01011` (2021-02-12 through
2021-02-19, three separate trades), is a genuinely expensive stock (Rs
~89,000-91,710/share) where `qty = max(1, floor(25000/entry))` floors to
exactly 1 share, pushing position value above Rs 25,000 by the amount of
one share's own price -- a fully understood, bounded case (bounded by
the single most expensive stock's own price, nowhere near unbounded),
not a residual pathology.

### Realised stop distance (% of entry)

| min | median | max |
|---|---|---|
| **0.500%** | 2.126% | **5.000%** |

Both guards hold exactly at their own frozen boundaries (min lands at
the 0.5% floor, max at the 5% ceiling, as designed) -- confirms both
`STOP_TOO_TIGHT` and `STOP_TOO_WIDE` are doing real, binding work, not
sitting unused.

### Why the trade count rose (13,907 -> 22,959)

The shared, UNCHANGED stages (lookback-eligibility, trend filter, touch,
POC_FAILED, confirmation, fill) produced **byte-identical counts between
V1 and V2** -- confirms Section 0's reuse claim directly, not just by
assertion: `lookback_incomplete` 42,802, `trend_filter_failed` 108,905,
`no_touch` 47,425, `poc_failed` 31,754, `no_confirmation` 1,059,
`no_fill_bar` 551, `fill_outside_window` 1,800 -- every one of these
matches V1's own reported count exactly. The two backtests diverge only
from the stop-computation stage onward, where **44,399 fills** reach the
stop check in both versions:

| Outcome at the stop-check stage | V1 | V2 |
|---|---|---|
| `ENTRY_BELOW_STOP` | 20,906 (47.1%) | 2,578 (5.8%) |
| `STOP_TOO_WIDE` | 5 (0.01%) | 9,489 (21.4%) |
| `STOP_TOO_TIGHT` | n/a (no floor existed) | 1,959 (4.4%) |
| `NO_ROOM` | 9,575 (21.6%) | 7,414 (16.7%) |
| `ZERO_QTY` (V1) / entered (V2) | 6 / **13,907 entered (31.3%)** | **22,959 entered (51.7%)** |

V1's stop (0.5% below POC) sat so close to POC that nearly half of all
fills landed below it entirely (`ENTRY_BELOW_STOP`) before a trade could
even be considered. V2's stop (the 5-day low) is typically much further
from entry, so far fewer fills fall below it -- but a new, substantial
rejection reason appears in its place: **`STOP_TOO_WIDE` rejected 9,489
setups, 21.4% of all fills that reached this stage** (7.47% of every
candidate that passed the trend filter; 3.40% of every setup checked at
all, including lookback/trend-filter rejections). The pre-registration's
own stated expectation -- that the 5% ceiling would "reject a large
share of setups" -- is directionally confirmed (a meaningfully large
minority, the single biggest reason V2 loses candidates that V1 did not)
but did not reach "reject most setups": V2 still entered more trades
than V1 overall (51.7% vs 31.3% of eligible fills), and the resulting
sample (22,959 trades, MDE 0.049%) was large enough to resolve the gate
decisively rather than leaving it underpowered.

## Hand-traced examples (Process Step 2)

Found on the FIRST entity scanned, `INE002A01018` (same entity V1's own
hand-traces happened to use first), by `scripts/poc_v2_handtrace.py`
against the real DEV window -- no synthetic data.

### 1. STOP_TOO_WIDE skip -- 2016-12-15

`POC_PRICE = 1057.6403`, `PREV_HIGH = 1064.4577`, `LOOKBACK_LOW =
1004.3450`.

- Touch (11:50): low 1057.48 <= POC_PRICE. TOUCH.
- Confirm (11:55): GREEN (close 1059.35 > open 1058.62). **ENTER**.
- Fill: open of the 12:00 1-minute bar = **1059.1846**.
- STOP = LOOKBACK_LOW = **1004.3450**. `risk_pct = (1059.1846 -
  1004.3450) / 1059.1846 = 5.178%` -- **above the 5% ceiling** ->
  **`STOP_TOO_WIDE`**, no trade. Confirms the stated expectation that a
  5-trading-day low can sit far enough below an intraday entry to
  exceed the risk ceiling routinely, not just in extreme cases -- this
  one missed the cutoff by only 0.178 percentage points.

### 2. STOP exit -- 2017-01-18

`POC_PRICE = 1084.2985`, `PREV_HIGH = 1097.4927`, `LOOKBACK_LOW =
1038.4934`, band 1-50.

- Touch (09:45): low 1044.99 <= POC_PRICE. Confirm (09:50): GREEN. Fill
  at 09:55, **entry = 1045.5117**.
- STOP = LOOKBACK_LOW = **1038.4934** (`stop_distance_pct = 0.671%`,
  between the 0.5% floor and 5% ceiling). TARGET = `1097.4927 x 0.98 =
  1075.5428`. `qty = floor(25000 / 1045.5117) = 23`.
- Resolution: STOP hit at 11:12. `pnl_rs = 23 x (1038.4934 - 1045.5117)
  = -161.42`. `position_size_rs = 23 x 1045.5117 = 24,046.77`.
  `cost_rs = 60.48` (`cost_pct = 0.2515%` of position value).
  **`net_return_pct = (-161.42 - 60.48) / 24,046.77 = -0.9228%`**.

### 3. TIME_EXIT -- 2017-03-10

`POC_PRICE = 1303.1590`, `PREV_HIGH = 1326.9917`, `LOOKBACK_LOW =
1241.5636`, band 1-50.

- Touch/confirm/fill as above; **entry = 1285.0301** @ 09:55.
- STOP = 1241.5636 (`stop_distance_pct = 3.383%`). TARGET = 1300.4518.
  `qty = floor(25000/1285.0301) = 19`.
- Neither level hit by the cutoff -> TIME_EXIT at the 15:15 candle's own
  close, **1281.1407**. `pnl_rs = 19 x (1281.1407 - 1285.0301) =
  -73.90`. `cost_rs = 60.69`. **`net_return_pct = -0.5512%`**.

### 4. TARGET exit -- 2017-07-04

`POC_PRICE = 1428.2258`, `PREV_HIGH = 1443.0051`, `LOOKBACK_LOW =
1371.0035`, band 1-50.

- Touch/confirm/fill as above; **entry = 1413.9851** @ 09:55.
- STOP = 1371.0035 (`stop_distance_pct = 3.040%`). TARGET =
  `1443.0051 x 0.98 = 1414.1450` -- **only Rs 0.16 above entry**, since
  entry itself landed almost exactly at the 2%-below-PREV_HIGH line.
  `qty = floor(25000/1413.9851) = 17`.
- Resolution: TARGET hit at 14:09. `pnl_rs = 17 x (1414.1450 -
  1413.9851) = 2.72`. `cost_rs = 60.48`.
  **`net_return_pct = (2.72 - 60.48) / 24,037.75 = -0.2403%`** --
  **negative despite a genuine TARGET exit**, because fixed costs (Rs
  60.48) exceeded the entire gross gain (Rs 2.72). Flagged as a real
  dynamic this sizing/target combination can produce, not an error: a
  TARGET that lands very close to entry (which can happen whenever
  entry itself already sits near the 2%-below-PREV_HIGH line) leaves
  little room for the fixed-cost component to clear.

### 5. HAMMER confirmation, STOP exit -- 2018-09-21

`POC_PRICE = 1215.9449`, `PREV_HIGH = 1275.5992`, `LOOKBACK_LOW =
1201.0065`, band 1-50 (rank 1).

- Touch (12:45). Confirm at 12:55 (candidate 2 -- the first candidate
  after touch was live, not shown here): **HAMMER**, O=1216.91 H=1216.95
  L=1209.69 C=1215.85. Fill at 13:00, **entry = 1215.7917**.
- STOP = 1201.0065 (`stop_distance_pct = 1.216%`). TARGET = 1250.0872.
  `qty = floor(25000/1215.7917) = 20`.
- Resolution: STOP hit at 13:06. `pnl_rs = 20 x (1201.0065 - 1215.7917)
  = -295.70`. `cost_rs = 60.63`. **`net_return_pct = -1.4655%`**.

**All five hand traces are internally consistent with Section 7 exactly
as written -- verified by recomputing LOOKBACK_LOW, STOP, TARGET, qty,
and net return % by hand from each trace's own printed inputs before
trusting any aggregate number.** Position sizes landed in the
Rs 24,000-24,400 range throughout, as Change 1 predicts (always
approximately Rs 25,000, never driven by stop distance).
