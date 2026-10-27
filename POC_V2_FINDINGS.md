# POC bounce V2, fixed-capital sizing: experiments log

Companion to `PREREGISTRATION_POC_V2.md` (frozen rules, commit `12ef33e`).
POC family trial 2 -- a revision proposed by the user after seeing V1's
own DEV failure and its specific sizing pathology (`POC_FINDINGS.md`,
`OPERATIONS.md`'s standing rule). Carries selection pressure; any DEV
pass below is development evidence only, never a validity claim.
Records what was actually run and found, per that document's Process
section.

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
