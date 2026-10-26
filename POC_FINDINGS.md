# POC (point of control) bounce, intraday: experiments log

Companion to `PREREGISTRATION_POC.md` (frozen rules, commit `e2cbf44`,
amended three times before any real trade existed -- `ab6128e` guarded
the doji-hammer test against a flat/zero-range bar, `71c0b18` added the
`ENTRY_BELOW_STOP` skip found when GREEN/HAMMER confirmed while price
kept falling through the stop level). Records what was actually run and
found, per that document's Process section.

## Hand-traced examples (Process Step 2)

Found on the FIRST entity scanned, `INE002A01018` (rank 1-50 band
throughout), by `scripts/poc_handtrace.py` against the real DEV window --
no synthetic data. All five of the required shapes exist in the real
archive; none had to be searched for beyond the first entity.

### 1. POC_FAILED skip -- 2016-10-14

`POC_PRICE = 1108.1877`, `PREV_HIGH = 1126.2518` (from the 5 trading days
before 2016-10-14).

- Touch candle (09:45): O=1066.01 H=1070.99 **L=1065.20** C=1069.69 --
  `low <= POC_PRICE` (1065.20 <= 1108.19). TOUCH.
- Confirming candle (09:50): O=1069.69 H=1071.96 L=1069.01 **C=1069.01**
  -- RED (close < open) and `close (1069.01) < POC_PRICE (1108.19)` --
  **POC_FAILED**, per Section 6 point 1: the level has failed, no second
  candidate is checked.

### 2. STOP exit -- 2016-10-26

`POC_PRICE = 1061.3183`, `PREV_HIGH = 1098.0165`, band 1-50.

- Touch (09:45): L=1055.07 <= POC_PRICE. TOUCH.
- Confirm (09:50): O=1056.16 C=1056.28 -- GREEN. **ENTER**.
- Fill: open of the 09:55 1-minute bar = **1056.2812**.
- STOP = `1061.3183 x 0.995` = **1056.0117**. TARGET = `1098.0165 x 0.98`
  = **1076.0561**. `qty = floor(500 / (1056.2812 - 1056.0117)) = 1855`.
- Resolution: STOP hit at 10:09 (bar open 1056.0117 <= STOP, exits at
  STOP price itself). `pnl_rs = 1855 x (1056.0117 - 1056.2812) = -499.89`.
  `position_size_rs = 1855 x 1056.2812 = Rs 1,959,401.68`.
  `cost_rs = round_trip_cost_rs(1,959,401.68, "1-50") = 1129.68`.
  **`net_r = (-499.89 - 1129.68) / 500 = -3.2591`**.
- **Flagged, not a bug**: the 0.5%-below-POC stop can be MUCH tighter
  than box theory's own 3%-of-entry stop, so the fixed-Rs500-risk formula
  (`qty = floor(500 / per_share_risk)`) can size a position far larger
  than this project's other studies ever produce -- here, ~Rs 1.96
  million notional on a ~Rs 1056 stock, for a nominal Rs 500 risk.
  Transaction costs scale with POSITION SIZE (the banded spread
  component), not with the risk unit, so a tight-stop loser can cost
  several multiples of 1R once costs are included. This is a real,
  mechanical consequence of the frozen rules (Section 7/9), not a
  resolution bug -- but it means net R's distribution is NOT expected to
  resemble a bounded-at-"-1R" loss distribution the way box theory's own
  3%-stop trades do, and the DEV report below calls out the magnitude of
  this effect explicitly rather than letting a casual reading of "net R"
  assume a box-theory-like scale.

### 3. TIME_EXIT -- 2017-08-07

`POC_PRICE = 1619.3583`, `PREV_HIGH = 1664.9062`, band 1-50.

- Touch at 09:50 (09:45 candle's own low did not reach POC_PRICE): O=
  1620.94 H=1621.06 **L=1618.10** C=1618.91 -- touches.
- Confirm (09:55): O=1618.91 C=1620.17 -- GREEN. **ENTER**.
- Fill: open of the 10:00 1-minute bar = **1620.1702**.
- STOP = 1611.2615, TARGET = 1631.6081. `qty = floor(500/8.9087) = 56`.
- Neither level is hit by the 15:19 cutoff -> TIME_EXIT at the 15:15
  candle's own close, **1617.6988**, no fallback needed.
  `pnl_rs = 56 x (1617.6988 - 1620.1702) = -138.40`. `cost_rs = 97.32`.
  **`net_r = -0.4714`**.

### 4. HAMMER confirmation (the doji carve-out, not a plain hammer) -- 2018-01-24

`POC_PRICE = 969.4775`, `PREV_HIGH = 990.9391`, band 1-50 (rank 1).

- Touch (09:45): L=962.65 <= POC_PRICE. TOUCH.
- Confirm (09:50): O=967.00 H=969.21 L=965.26 **C=967.00** -- `close ==
  open` exactly: a DOJI, `body = 0`. Not green. General hammer test does
  not apply (`body = 0`). Doji carve-out (Section 6, amended): `full_
  range = 969.21 - 965.26 = 3.95 > 0`; `lower_wick = min(967.00,967.00)
  - 965.26 = 1.74`; threshold = `0.2 x 3.95 = 0.79`; `1.74 >= 0.79` --
  **HAMMER (doji case)**. This is specifically the amended edge case,
  not a body>0 hammer and not a plain green candle -- confirms the
  amendment is reachable on real data, not dead code.
- Fill: open of the 09:55 1-minute bar = **966.9616**.
- STOP = 964.6301, TARGET = 971.1203. `qty = floor(500/2.3315) = 214`.
- Resolution: STOP hit WITHIN THE ENTRY BAR ITSELF (same 1-minute bar as
  the fill, which the scan includes from `fill_ts` inclusive) --
  `exit_ts = fill_ts = 09:55`. `pnl_rs = 214 x (964.6301 - 966.9616) =
  -498.93`. `cost_rs = 161.52`. **`net_r = -1.3209`**.

### 5. TARGET exit -- 2018-02-22

`POC_PRICE = 924.3125`, `PREV_HIGH = 945.7478`, band 1-50 (rank 1).

- Touch (09:45): L=920.00 <= POC_PRICE. TOUCH.
- Confirm (09:50): O=920.99 C=923.10 -- GREEN. **ENTER**.
- Fill: open of the 09:55 1-minute bar = **923.0609**.
- STOP = 919.6909, TARGET = 926.8328. `qty = floor(500/3.3700) = 148`.
- Resolution: TARGET hit at 13:38. `pnl_rs = 148 x (926.8328 - 923.0609)
  = 558.25`. `cost_rs = 122.67`. **`net_r = 0.8712`**.

**All five hand traces are internally consistent with Sections 4, 6, 7,
and 8 exactly as written (including both amendments) -- verified by
recomputing POC_PRICE, STOP, TARGET, qty, and net R by hand from each
trace's own printed inputs before trusting any aggregate number.**
