# Liquidity confluence, Study A (long only): experiments log

Companion to `PREREGISTRATION_LIQUIDITY_A.md` (frozen rules, commit
`214b3a6`). New family, trial 1. Records what was actually run and
found, per the preregistration's own Process section.

## Synthetic unit tests (Process, pre-Step-2)

`scripts/liquidity_a_unit_test.py` -- pure-function scenarios, no DB
access, run before touching real data (same discipline as `poc.v5`'s own
8-scenario synthetic test): confluence clustering (no cluster, a pair,
all three mutually, and the "chain via a shared node" case -- 3m close
to 1w, 1w close to 1d, but 3m not close to 1d, confirming the single-
linkage connected-components rule groups all three, not just the
touching pair), plus 8 scaled-exit resolution shapes (full 3R across two
bars, same-bar half-then-full, stop before any half exit, half exit then
stop on the remainder, half exit then a 15:15 time exit on the
remainder, qty=1's own simpler path, and nothing-hit-at-all producing a
full-position time exit). All 14 checks passed on the first run.

## Hand-traced examples (Process Step 2)

All 5 required shapes -- a full 3R target, a stop before any half exit,
a half exit followed by a stop on the remainder, a 15:15 time exit with
the second half still open, and a `NO_CONFLUENCE` skip -- found by
`scripts/liquidity_a_handtrace.py` against the real DEV window, all on
the very first entity scanned (`INE002A01018`). Every number below was
independently recomputed by hand from the script's own printed inputs
before being trusted; all matched to within display rounding.

### 1. NO_CONFLUENCE -- INE002A01018, 2016-10-05

`LOW levels: 3m=975.5000, 1w=1066.3000, 1d=1092.0000`, `ATR_raw=23.6851`,
tolerance `0.5xATR=11.8426`. Pairwise diffs: `3m-1w=90.80`, `3m-
1d=116.50`, `1w-1d=25.70` -- all three far beyond tolerance, no edge in
the adjacency graph, `NO_CONFLUENCE` confirmed by hand from the three
raw numbers alone.

### 2. STOP_NO_HALF (stop hit before any half exit) -- INE002A01018, 2017-05-18

`LOW levels: 3m=1022.00, 1w=1333.50, 1d=1347.75`, `ATR_raw=28.7046`,
tolerance `14.3523`. `1w-1d` diff `14.25 <= 14.3523` -- the only
qualifying pair; `3m` sits far from both. **Zone = mean(1333.50,
1347.75) = 1340.625**.

- Sweep at 09:55 (idx 8): low `1335.5191`. `depth = 1340.625 - 1335.5191
  = 5.1059`, `depth/ATR = 0.1779` -- within range. Reclaim at 10:05
  (idx 10), close `1340.9886` clears the zone.
- Fill at 10:10 (reclaim candle's own close) -> **entry = 1340.9886**.
  `STOP = 1335.5191 - 0.1x28.7046 = 1332.6486` (`stop_distance_pct =
  0.6220%`). `HALF_TARGET = 1353.4984`, `FULL_TARGET = 1366.0083`.
  `qty = floor(25000/1340.9886) = 18`, `half_qty = 9`.
- The stop (1332.6486) is hit at 13:17, before the half-target level is
  ever reached -- **`STOP_NO_HALF`, full 18 shares exit at 1332.6486.**
- `pnl_rs = 18x(1332.6486-1340.9886) = -150.12`. `position_size_rs =
  24,137.79`. Three-order cost model collapses to two real orders here
  (no half exit happened): `total_cost_rs = 60.48` (buy leg 27.61 + one
  sell leg 32.86, independently re-summed by hand from each leg's own
  statutory/brokerage/GST/half-spread components). `hypothetical_cost_rs
  = 60.53` (box theory's own two-order formula on the same entry value) --
  `extra_cost_rs = -0.06`, slightly NEGATIVE here because the actual
  exit (at the stop, below entry) has a smaller trade value than the
  hypothetical's entry-value-based sell leg, confirming the comparison
  is sensitive to realized exit price, not just order count.
  **`net_return_pct = -0.8725%`.**

### 3. HALF_THEN_STOP -- INE002A01018, 2017-09-28

`LOW levels: 3m=685.50, 1w=795.50, 1d=795.50`, `ATR_raw=18.7401`,
tolerance `9.3700`. `1w` and `1d` are IDENTICAL (diff 0); `3m` sits far
from both. **Zone = 795.50.**

- Sweep at 09:45 (idx 6): low `793.3106`, `depth/ATR = 0.1168`. Reclaim
  at 09:50 (idx 7), close `795.9440` clears the zone.
- Fill at 09:55 -> **entry = 796.0048**. `STOP = 793.3106 - 0.1x18.7401
  = 791.4366` (`stop_distance_pct = 0.5739%`, just above the 0.5% floor).
  `HALF_TARGET = 802.8571`, `FULL_TARGET = 809.7094`. `qty =
  floor(25000/796.0048) = 31`, `half_qty = 15`.
- Half-target hit at 10:49 -> **15 shares exit at 802.8571** (realised
  profit `15x6.8523 = 102.78`, locked in). Remainder (16 shares) then
  hits the stop at 12:41 -> **exits at 791.4365** (the half's own
  realised profit is never clawed back, exactly as the preregistration
  requires).
- `pnl_rs = 15x(802.8571-796.0048) + 16x(791.4365-796.0048) = 102.78 -
  73.09 = 29.69`. `position_size_rs = 24,676.15`. Three real orders now:
  buy 27.70 + half-sell 18.86 + remainder-sell 19.83 = **`total_cost_rs
  = 66.40`**, vs. **`hypothetical_cost_rs = 60.83`** (same entry value,
  box theory's own two-order formula) -- **`extra_cost_rs = +5.56`**,
  the genuine extra-order cost this time (a real third order, not a
  smaller realized exit value). **`net_return_pct = -0.1487%`** -- a
  small net LOSS despite the half exit's own real profit, because the
  remainder's stop loss plus the extra order cost outweighed it.

### 4. FULL_EXIT (full 3R target reached) -- INE002A01018, 2019-07-22

`LOW levels: 3m=1227.50, 1w=1242.70, 1d=1242.70`, `ATR_raw=24.1860`,
tolerance `12.0930`. `1w`/`1d` identical; `3m` sits far (diff 15.20 >
tolerance). **Zone = 1242.70.**

- Sweep at 09:45 (idx 6): low `1238.2058`, `depth/ATR = 0.1858`. Reclaim
  at 09:50 (idx 7), close `1246.9975` clears the zone.
- Fill at 09:55 -> **entry = 1246.9975**. `STOP = 1235.7872`
  (`stop_distance_pct = 0.8991%`). `HALF_TARGET = 1263.8128`,
  `FULL_TARGET = 1280.6283`. `qty = floor(25000/1246.9975) = 20`,
  `half_qty = 10`.
- Half-target hit at 10:18 -> 10 shares exit at `1263.8128`
  (`+16.82/share` realised). Remainder rides on; full target hit at
  15:08 (same day, different bar) -> 10 shares exit at `1280.6282`
  (`+33.63/share`). **`FULL_EXIT`**, the strategy's own best-case shape.
- `pnl_rs = 10x16.8153 + 10x33.6307 = 504.46`. `position_size_rs =
  24,939.95`. `total_cost_rs = 67.60` (buy 27.75 + half-sell 19.79 +
  full-sell 20.06). `hypothetical_cost_rs = 60.98` -- `extra_cost_rs =
  +6.62`, the largest of the four real-trade examples (two full-value
  sell legs, both near or above the hypothetical's own entry-value
  proxy). **`net_return_pct = +1.7517%`** -- confirms the mechanism CAN
  produce a genuine win large enough to absorb the extra-order cost, not
  just losses.

### 5. HALF_THEN_TIME_EXIT -- INE002A01018, 2019-07-29

`LOW levels: 3m=1w=1d=1210.00` -- all three IDENTICAL. `ATR_raw =
28.3161`, tolerance `14.1580`. All three pairwise diffs are 0 -- a
genuine **three-way cluster, zone members `('1d','1w','3m')`, zone =
1210.00**, the "if three cluster, average all three" case, confirmed
not to trip the (structurally unreachable) `multi_cluster` flag.

- Sweep at 10:15 (idx 12): low `1207.0056`, `depth/ATR = 0.1057`.
  Reclaim at 10:25 (idx 14), close `1210.2468` clears the zone.
- Fill at 10:30 -> **entry = 1210.3480**. `STOP = 1204.1740`
  (`stop_distance_pct = 0.5098%`, just above the 0.5% floor).
  `HALF_TARGET = 1219.6091`, `FULL_TARGET = 1228.8702`. `qty =
  floor(25000/1210.3480) = 20`, `half_qty = 10`.
- Half-target hit at 11:02 -> 10 shares exit at `1219.6091`
  (`+9.26/share` realised). Remainder never reaches the full target or
  the stop for the rest of the day -> **15:15 time exit, 10 shares at
  1210.7937** (the second half still open when the clock ran out, the
  exact shape required by name).
- `pnl_rs = 10x9.2611 + 10x0.4457 = 97.07`. `position_size_rs =
  24,206.96`. `total_cost_rs = 65.69` (buy 27.62 + half-sell 19.10 +
  time-exit-sell 18.96). `hypothetical_cost_rs = 60.57` --
  `extra_cost_rs = +5.12`. **`net_return_pct = +0.1296%`** -- a small
  net win: the half's own locked-in profit outweighed the extra-order
  cost even though the remainder gave almost all of its own gain back
  by the close.

**All five hand traces are internally consistent with the
preregistration exactly as written.** The confluence clustering (a
clean pair, an exact tie collapsing two levels to one, and a genuine
three-way match), the sweep/reclaim formulas (byte-identical to V4's
own), the half/full risk-multiple targets, all four distinct scaled-exit
outcome shapes, and the three-order cost model's own extra-cost
comparison (observed both positive and slightly negative, each for a
specific, understood reason) were each exercised and independently
re-verified by hand before any aggregate number was computed.
