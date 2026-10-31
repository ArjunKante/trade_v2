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

## Status

Hand-traces complete, all 5 shapes found and independently verified.
Next: run DEV only (Process Step 4), report, and **stop for approval
before TEST**.
