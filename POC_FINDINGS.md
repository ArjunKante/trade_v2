# POC (point of control) bounce, intraday: experiments log

Companion to `PREREGISTRATION_POC.md` (frozen rules, commit `e2cbf44`,
amended three times before any real trade existed -- `ab6128e` guarded
the doji-hammer test against a flat/zero-range bar, `71c0b18` added the
`ENTRY_BELOW_STOP` skip found when GREEN/HAMMER confirmed while price
kept falling through the stop level). Records what was actually run and
found, per that document's Process section.

**Bottom line, stated first per this project's "bad results first"
discipline: DEV FAILS, decisively, on the very first gate condition.**
Mean net R = **-0.6733**, 97.5% CI **[-0.8360, -0.5183]** -- excludes
zero on the NEGATIVE side, and the gate requires ALL conditions to hold,
so the remaining three conditions (both null percentiles, the
ex-best-year check, the bands-1-100 check) cannot change the verdict
regardless of their own values. **The nulls were therefore NOT run to
completion** -- the TIMING null was stopped at 200 of its planned 500
seeds (checkpointed; the process was killed once the primary gate
condition was already decided) and the SELECTION null was never started.
Both are reported below only as far as they actually ran, explicitly
labeled partial, never presented as a finished comparison. **The loss is
not from a losing SIGNAL -- it is almost entirely transaction-cost
drag, concentrated in a small tail of trades whose stop distance
(0.5% below POC) happened to be a few paise wide**, which the fixed-
Rs500-risk sizing formula converts into grotesquely oversized positions.
The sealed TEST window is never read. **This is trial 1 of the POC
family -- closed.**

## DEV result

13,907 trades, 1,446 distinct entry days, full top-200-by-turnover
universe, real DEV window 2016-10-04 to 2022-12-31. Runtime: 43.9 min for
the real backtest; the TIMING null's pool build + 200/500 seeds took
another ~48 min before the run was stopped (gate already decided).

| | |
|---|---|
| Trades / distinct entry days | 13,907 / 1,446 |
| Win rate | 28.5% |
| Mean net R (97.5% CI) | **-0.6733** [-0.8360, -0.5183] |
| Median net R (descriptive) | -1.1837 |
| MDE | 0.1588 |
| TIMING null percentile | **PARTIAL, 200/500 seeds: 90.5** (not the formal 500/1000-seed comparison -- see below) |
| SELECTION null percentile | **not run** -- gate already failed |
| Exit mix | STOP 8,213 / TARGET 3,534 / TIME_EXIT 2,160 (fallback used 8x) |
| By year | 2016 -1.154 (274) / 2017 -0.667 (2,182) / 2018 -0.765 (1,705) / 2019 -0.502 (2,104) / 2020 -0.624 (2,687) / 2021 -0.567 (2,925) / 2022 -0.934 (2,030) |
| By band | 1-50: -0.636 (3,439) / 51-100: -0.495 (3,969) / 101-200: -0.802 (6,499) |
| `(entry - POC)/entry` | mean 0.00068, median 0.00063, range [-0.00502, 0.03829] |
| Peak concurrent positions / capital | 26 / **Rs 436,106,249** (dominated by the cost-pathology tail below -- not a realistic capital figure) |
| **DEV_PASS** | **False** |

**Skip/diagnostic breakdown**: `trend_filter_failed` 108,905 (by far the
largest gate -- most touch-candidate days are simply not in an uptrend),
`lookback_incomplete` 42,802 (mostly `bad_previous_session` on `L1`,
17,758 -- the archive-depth check closest to today, expected to be the
largest of the six since it fires independently on each of the six days
checked), `no_touch` 47,425, `poc_failed` 31,754, `entry_below_stop`
20,906 (the amendment's own new skip -- confirms it fires often in
practice, not a rare edge case), `no_room` 9,575, `fill_outside_window`
1,800, `no_confirmation` 1,059, `no_fill_bar` 551, `stop_too_wide` 5,
`zero_qty` 6.

### Why this lost: cost drag, not signal, and it is concentrated in a tail

Splitting net R into its two components tells the whole story:

| | |
|---|---|
| Mean GROSS R (pre-cost, `pnl_rs / 500`) | **-0.0015** -- essentially zero |
| Mean cost R (`cost_rs / 500`) | **+0.6718** |
| Mean net R | -0.6733 |

**The strategy's raw entry/exit signal has approximately NO edge either
way (-0.0015R gross) -- the entire -0.6733R loss is transaction cost.**
This is the flagged observation from the hand-traced STOP example
(`POC_FINDINGS.md` trace #2) showing up at full scale, not a one-off:

- **792 of 13,907 trades (5.7%) had `cost_rs` exceeding one full R (Rs
  500)** -- i.e. costs alone, on just these trades, wiped out more than
  the entire nominal risk unit.
- Those 792 trades alone contribute **0.405 of the 0.672 total mean cost
  R** (60% of all cost drag, from 5.7% of trades) -- mean cost R among
  them is **7.11R**; among the other 94.3% of trades it is a
  much more ordinary **0.283R**.
- The tail is extreme, not merely heavy: cost R's 99.9th percentile is
  42.3R, and the single worst trade (`INE155A01022`, 2020-08-20) had
  `entry_price=124.052442` and `stop_price=124.052299` -- a per-share
  risk of **Rs 0.000143** -- forcing `qty = floor(500/0.000143) =
  3,499,359` shares, a **Rs 434 million** position, and a cost of **Rs
  239,869 (480R)** on a trade nominally risking Rs 500.
- **Mechanism**: STOP is fixed at 0.5% below POC_PRICE, a level with no
  necessary relationship to the ENTRY price (Section 6's GREEN/HAMMER
  confirmation does not require trading near POC_PRICE at all -- see the
  `ENTRY_BELOW_STOP` amendment). Whenever entry happens to land only
  fractionally above POC_PRICE, the per-share risk collapses toward
  zero, and `qty = floor(500 / per_share_risk)` explodes without bound.
  Unlike box theory's `3% x entry` stop (always a meaningful fraction of
  price, so `qty` is always bounded to a sane range), a FIXED percentage
  of a VOLUME-DERIVED level, combined with a FIXED-Rs-risk sizing
  formula, has no such floor. The 5% `STOP_TOO_WIDE` ceiling (Section 7)
  guards against a stop too far away; nothing in the frozen rules guards
  against a stop so NEAR that sizing blows up -- this is a real
  structural property of the combination the preregistration specified,
  not a resolution bug (consistent with Section 6's own
  `ENTRY_BELOW_STOP` amendment, which found the adjacent half of the same
  gap).

### Family tally

POC's **-0.6733** mean net R is markedly worse than either box theory
configuration's own DEV failure (`BOX_FINDINGS.md`: FAST **-0.1380**,
SLOW **-0.1260**) or box theory V2's **-0.1037** (`BOX_V2_FINDINGS.md`)
-- roughly 5-6x the loss magnitude. Combined with FVG, the IPO listing
study, the per-stock weekly study, and Darvas Box theory, this is the
**sixth** study in this project to close with NO EDGE.

### TIMING null -- partial, 200 of 500 seeds, not the formal comparison

Stopped once the primary gate condition (mean net R > 0) was already
decided. At 200 seeds, the null's own mean of means is **-0.7888**
(range [-0.9075, -0.4546] across seeds), and the real strategy's
-0.6733 sits at the **90.5th percentile** of this partial distribution
-- i.e. a random 5-minute entry on the same touched POC days, with the
same stop distance and target level, did WORSE than the real signal
about 90% of the time at this sample size. **This is directionally
informative but explicitly NOT the formal 500-seed TIMING comparison the
gate calls for**, is reported only because 200 seeds is enough to show
the real strategy is not simply "random entry with extra cost" (it
beats most random draws), and should not be read as a finished
percentile. The SELECTION null never started.

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
