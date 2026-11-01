# Liquidity confluence, Study C (retest confirmation)

## Provenance, stated plainly and prominently

**Study A (long)**: mean net return **-0.2841%**, 8,131 trades, both
nulls **100th percentile**. Closed at DEV, NO EDGE, TEST not read.

**Study B (short)**: mean net return **-0.1212%**, 9,222 trades, both
nulls **100th percentile**. Closed at DEV, NO EDGE, TEST not read.

**Both closed with no edge. Study C is a third revision, proposed by the
user after seeing both fail. It carries selection pressure** -- stated
here, not glossed over: this is the third trial of the same family, and
the base rate for a revision proposed after two failures in the same
mechanism is not the same as a first attempt's own base rate.

**The specific motivation, recorded as stated**: 77% of Study A's own
trades (`STOP_NO_HALF` + `TIME_EXIT_FULL`, `LIQUIDITY_A_FINDINGS.md`
Finding 1) never reached even the half target; Study B's own figure was
72.5%. The hypothesis is that requiring a SECOND hold of the level --
price returning to the zone after the original reclaim and holding,
rather than reclaiming once and being traded immediately -- filters out
trades that were never going to follow through, raising the mean without
necessarily raising the win count.

**The counter-evidence, recorded with equal weight, not as a formality**:

1. **Both A and B already passed both null comparisons at the 100th
   percentile.** The entries were already selecting better-than-random
   stock-days -- confirmed, not assumed. The documented failure mode in
   both studies was follow-through after a real, non-random entry, not
   bad selection. A retest is another SELECTION filter (it changes which
   setups qualify as a trade, not what happens after entry). Filtering
   selection harder when the measured problem was follow-through, not
   selection, is not obviously the right lever.
2. **The POC family tested a trend filter (50-day MA) across V2-V5, and
   all of them failed** (`POC_V2_FINDINGS.md` through `POC_V5_FINDINGS.md`,
   `FAMILY CLOSED PERMANENTLY`). Entry filtering has not rescued this
   general mechanism (sweep-and-reclaim-style entries in this project)
   before, across five prior attempts.
3. **Study B had NO trend filter and still outperformed Study A** (loss
   less than half the size, `LIQUIDITY_B_FINDINGS.md` Finding 3) --
   extra entry conditions are not what separated the two studies' own
   results; follow-through rate was.
4. **This project's own precedent for how a strong null result can still
   fail a held-out test**: swing V1 reached the 100th percentile on
   65,219 development trades at p=0.001, cleared both Bonferroni and
   Benjamini-Hochberg correction, and scored only the 61.4th percentile
   on its own sealed holdout (`FINDINGS.md` Section 7's own second-read
   entry). A strong in-sample null result, even an extreme one, is not
   a guarantee of anything once new data is read -- recorded here as a
   caution against over-weighting Study A/B's own 100th-percentile null
   results as predictive of Study C's own outcome, since Study C is a
   DIFFERENT mechanism, not a re-read of the same one.

Both sides of this are recorded before any Study C trade exists, so
neither can be read as having been added after the result was already
known.

## STUDY C IS A AND B WITH ONE ADDED REQUIREMENT

**Everything from Studies A and B is preserved unchanged, reused
read-only, never modified**: the six levels computed at 09:45 from data
through the previous trading day only; the confluence rule (two or more
same-side levels within 0.5xATR(14), nearest to the previous close if
multiple clusters -- structurally unreachable with 3 levels, per A's and
B's own proofs); the sweep bounds (0.1-1.0xATR beyond the zone); the
3-candle reclaim window on 5-minute candles; the 09:45-14:30 entry
window; fixed-capital sizing (`qty = floor(25000/entry)`); the 0.5%
minimum / 5% maximum stop-distance guards; the scaled exit (half at
1.5R, remainder at 3.0R); the 15:15 time exit; the three-order intraday
cost model (entry leg + exit leg(s), swapped buy/sell roles for short
per Study B's own Section 6); the point-in-time top-200 universe and
every guard (jump, ex-date, same-ISIN, previous-session scale
resolution).

**THE KNOWN FLAW IS PRESERVED DELIBERATELY.** The 1-day and 1-week
levels nest by construction (a weekly extreme is usually also that
week's own daily extreme), producing degenerate confluence (two or more
clustered levels within 0.1% of each other) in 64.9% of Study A's own
trades and 71.4% of Study B's (`LIQUIDITY_B_FINDINGS.md`'s own post-DEV
diagnostic, tested across 17,353 trades). **That diagnostic found
degenerate trades performed NO WORSE than non-degenerate ones -- BETTER,
in Study A's own case.** The flaw is kept unchanged here, not because it
is harmless in the abstract, but because the evidence available says it
is not the thing holding this mechanism back, and because changing the
level definition here would confound any difference between Study C and
its predecessors -- a corrected, non-nesting-timeframe confluence
definition (Study D, following the same naming the family's own prior
documents have already reserved for it as "a separate study") is not
this trial.

## Section 0: reuse boundaries, read-only

No closed study's own file is touched. `src/liquidity/a.py` and `src/
liquidity/b.py` are imported exactly as Study B imported from Study A --
read-only, never modified.

**Reused unchanged**:
- `liquidity.a._build_level_lookup_for_entity` -- all six levels.
- `liquidity.a.find_confluence_zone` (LOW, long side) / `liquidity.b.
  find_confluence_zone_b` (HIGH, short side) -- the confluence rule,
  unchanged, including each side's own proven multi-cluster-
  unreachability property.
- `poc.v4.{find_sweep, find_reclaim, STOP_BUFFER_ATR, SWEEP_DEPTH_MIN_ATR,
  SWEEP_DEPTH_MAX_ATR, RECLAIM_WINDOW_CANDLES}` -- the ORIGINAL sweep and
  reclaim, unchanged, for the long side. `liquidity.b.{find_sweep_short,
  find_reclaim_short}` -- the same, for the short side (these are
  Study B's own new code, reused here exactly as Study B's own HIGH-level
  machinery was reused from Study A's LOW-level precedent).
- `liquidity.a.resolve_scaled_exit_a` / `liquidity.b.resolve_scaled_
  exit_b` -- exit mechanics are UNCHANGED by this study. Only entry
  timing changes; once filled, a Study C trade is resolved exactly like
  an A or B trade with the same entry price, stop, and targets.
- `liquidity.a.three_order_cost_rs` / `hypothetical_single_exit_cost_rs`
  (long) and `liquidity.b.three_order_cost_rs_b` / `hypothetical_single_
  exit_cost_rs_b` (short) -- unchanged. The cost STRUCTURE does not
  depend on when the entry fired, only on the entry/exit prices and
  quantities, which Study C computes the normal way once a fill exists.
- `poc.resolution.{ENTRY_WINDOW_START, ENTRY_WINDOW_END, MAX_RISK_PCT,
  fill_bar_after_candle_close}`, `poc.v2.{CAPITAL_RS, MIN_RISK_PCT}` --
  unchanged.
- `poc.nulls.{_random_fill, _valid_entry_idx}` -- unchanged (Section 9).
- All of `box_theory.*`, `fibo.*` universe/costs/inference/context
  machinery -- unchanged, identical to A and B's own Section 0.

**New code, lives entirely in `src/liquidity/c.py`**: the retest-
detection functions (`find_retest_long`, `find_retest_short`, Section 3
below) and the entry orchestration wrapping them
(`find_entry_c_long`/`find_entry_c_short`), plus the usual per-study
backtest orchestration and null pool-building, mirroring A/B's own
structure exactly but inserting the retest step between reclaim and
fill.

## Section 1: levels, confluence, universe, windows -- identical to A and B

No changes. See `PREREGISTRATION_LIQUIDITY_A.md` Sections 1-2 and
`PREREGISTRATION_LIQUIDITY_B.md`'s own mirrored sections for the long
and short construction respectively; not restated here beyond the
summary above.

DEV: **2016-10-04 to 2022-12-31**. TEST (sealed): **2023-01-01 to
2026-09-18** -- identical dates to A and B. A fresh `TestWindowViolationError`
/`guard_date_range` pair, own `ACCESS_LOG_PATH` at
`data/liquidity/c/test_window_access_log.txt`, per this project's own
"a fresh instance, not a shared one" convention, unaffected by A's or
B's own separate guard objects.

## Section 2: the original sweep and reclaim -- unchanged, and why the stop still uses it

Byte-identical to A (long) / B (short): sweep detection (0.1-1.0xATR
beyond the zone) and the 3-candle reclaim window, using `poc.v4`'s and
`liquidity.b`'s own unchanged functions. The reclaim's own FINAL swept
extreme (`final_sweep_low` / `final_sweep_high` -- possibly updated
during the 3-candle reclaim window if a new extreme occurred there,
exactly as A's and B's own `new_low_during_reclaim`/`new_high_during_
reclaim` diagnostic already tracks) is carried forward into Section 3
below as the retest's own breach floor/ceiling AND Section 4's own stop
level -- the SAME value, not two different numbers.

## Section 3: the new requirement -- retest confirmation

**After the sweep-and-reclaim that would have triggered entry in A or B,
DO NOT ENTER.** Scanning resumes from the candle immediately AFTER the
reclaim candle's own close (the reclaim candle itself already confirmed
a close back inside the zone; "since the reclaim" is read as starting
the clock there, not re-litigating the reclaim candle itself).

**LONG side** (`find_retest_long`): for each subsequent 5-minute candle,
in order, until the 14:30 window closes or the trading day ends:
1. If this candle's LOW is below `final_sweep_low` (the ORIGINAL sweep's
   own final extreme, Section 2) -- the setup is dead. **`RETEST_FAILED`**,
   stop scanning.
2. Otherwise, if this candle's own LOW is within `0.2 x ATR` of the zone
   price (`low <= zone_price + 0.2*ATR`) -- the "return to the zone"
   condition is satisfied, by this candle or any earlier one since the
   reclaim (a running flag, not required to be the immediately-preceding
   candle).
3. If the return condition has been satisfied (by this candle or
   earlier) AND this candle's own CLOSE is above the zone price --
   **`RETEST`** confirmed, at this candle. **Stated explicitly, since the
   instruction's own wording ("price must return... THEN a candle must
   close...") could be read either way: the SAME candle may satisfy both
   the return condition and the close-above confirmation** -- a single
   5-minute candle whose low dips to within 0.2xATR of the zone and
   whose own close is back above it is accepted as a valid retest, not
   required to span two separate candles. This is the more permissive,
   and more structurally natural, reading (a sharp V-shaped reclaim-of-
   the-retest within one bar is not mechanically different from the
   same move split across two bars), and is recorded as a deliberate
   interpretation before any trade exists.
4. If the window closes (14:30, or the day ends) with the return
   condition never satisfied, or satisfied but no qualifying close ever
   occurs, without a `RETEST_FAILED` breach having already ended the
   day -- **`NO_RETEST`**.

**SHORT side** (`find_retest_short`): the exact mirror -- a candle's
HIGH above `final_sweep_high` ends the setup (`RETEST_FAILED`); a
candle's HIGH within `0.2 x ATR` of the zone price (`high >= zone_price
- 0.2*ATR`) satisfies the return condition; a close BELOW the zone price,
on or after a candle satisfying the return condition, confirms
(`RETEST`).

**Entry**: the open of the next 1-minute bar after the RETEST candle's
own close (`fill_bar_after_candle_close`, unchanged -- the identical
fill mechanism A and B already use, just applied to the retest candle
instead of the original reclaim candle).

**Stop: still `final_sweep_low - 0.1xATR` for longs, `final_sweep_high +
0.1xATR` for shorts -- the ORIGINAL sweep extreme, not any new extreme
touched during the retest.** Stated as a deliberate choice, per
instruction: the original sweep is the level the thesis says was
defended -- the retest is evidence the ORIGINAL level held a second
time, not a new, tighter level to defend. (The retest's own `RETEST_
FAILED` condition, Section 3 point 1, already guarantees the original
sweep extreme was never breached between reclaim and entry -- so this
stop is never placed on the wrong side of price at fill by construction,
the same structural guarantee A's and B's own `ENTRY_BELOW_STOP`/`ENTRY_
ABOVE_STOP` checks already confirmed fires zero times.)

**R is recomputed from the actual (later) entry price** -- `R = entry -
stop` (long) / `R = stop - entry` (short), using the retest's own fill
price, not the original reclaim's. `HALF_TARGET`/`FULL_TARGET` (1.5R/
3.0R) and the 0.5%/5% stop-distance guards are evaluated against this
recomputed R, exactly as A's and B's own guards are evaluated against
their own single entry price -- no special-casing for the later entry.

## Section 4: exits -- unchanged

`liquidity.a.resolve_scaled_exit_a` / `liquidity.b.resolve_scaled_
exit_b`, called exactly as A and B call them, with Study C's own (later)
`fill_ts`, `entry_price`, `stop_price`, `half_target_price`,
`full_target_price`, `qty`. No new exit logic.

## Section 5: sizing and costs -- unchanged

`qty = floor(25000 / entry_price)` (Study C's own, later entry price).
`ZERO_QTY` guard unchanged. Cost model unchanged (Section 0).

## Section 6: both directions, run and reported separately

Study C runs LONG (`src/liquidity/c.py`'s own `*_long` functions, zone
from LOW levels) and SHORT (`*_short`, zone from HIGH levels)
independently, each with its own backtest, its own nulls, its own gate
evaluation, and its own verdict. **Mean net return, trade count, null
percentiles, half-target reach rate, and all four gate conditions are
reported SEPARATELY for each side, plus a combined figure -- never only
the combined number.** Studies A and B were run as separate studies
specifically so direction could be isolated, and that isolation revealed
a real asymmetry (Study B's loss under half Study A's size, a different
confluence-overlap rate, better follow-through than predicted) that a
single pooled number would have hidden. Study C preserves that
discipline within one study rather than two, since both sides share
every rule except which side of the market they trade.

## Section 7: nulls -- same population principle as A and B, built from Study C's own trades

**TIMING**: restricted to the exact (entity, day) pairs Study C's OWN
real strategy traded on that side -- which, by construction, only exist
because a retest actually succeeded. Reuses `liquidity.a._timing_draw_a`
/ `liquidity.b._timing_draw_b` UNCHANGED (a random 5-minute candle
replaces the real signal; the real trade's own stop distance and scaled-
exit structure are reused) -- called against Study C's own pool, built
from Study C's own trades' own stop distances.

**SELECTION**: the same single-day-eligibility-plus-level-history
population A and B already use, matched count per month to Study C's own
trade count that month. Stop distance drawn from Study C's OWN pooled
`stop_distance_pct` (computed from the retest-delayed entry, not
inherited from A's or B's own pool).

**Stated explicitly, since the instruction asks for the retest
requirement to be "applied to the null draws as well"**: neither null
ever modeled the SIGNAL-DETECTION step at all (TIMING replaces it with a
random candle; SELECTION replaces it with a random stock-day) -- there is
no sweep, zone, or reclaim inside either null's own draw to run a retest
against. **The retest requirement is reflected in Study C's own nulls
by construction, not by adding a new retest step inside the null's own
random-entry mechanism**: TIMING's own population is restricted to days
a retest actually succeeded on, and SELECTION's own stop-distance pool
is drawn from Study C's own (retest-delayed) entries, never from A's or
B's own pool. This is what "otherwise the comparison is against a
different strategy" requires -- every downstream number the null reuses
(stop distance, exit targets, cost model) is Study C's own, not
borrowed from an earlier study whose entries fired at a different time
with a different resulting stop/target geometry.

1000 seeds, or 500 with the usual timed-probe fallback -- identical
contingency to every prior study in this lineage, for each side
independently.

## Section 8: gate -- applied to each side independently

Mean net return > 0, day-clustered 97.5% bootstrap CI (unchanged
machinery) excluding zero; >= 95th percentile against BOTH nulls; still
positive after dropping the best year; positive within bands 1-100
alone. **All four required, evaluated separately for LONG and for
SHORT.** A side passes only if all four hold for that side. Both sides'
verdicts are reported regardless of each other's outcome -- one side
passing does not carry the other, and one side failing does not
preclude reporting the other's own pass if it occurs.

## Section 9: report

Everything A and B each reported (trades, distinct days, mean net return
with CI, median, both null percentiles, by year, by band, confluence-pair
breakdown, exit-mix, extra-cost figure, skip counts, peak concurrent
positions/capital) -- for LONG, for SHORT, and combined. Plus, specific
to this study:

- **Trade count against A's 8,131 and B's 9,222**, per side. A large
  drop is EXPECTED, not a surprise if it occurs -- the exact attrition
  at `NO_RETEST` and `RETEST_FAILED` is reported as its own line, not
  folded into a generic "skip" total, since these two are the entire
  mechanism this study is testing.
- **Half-target reach rate against A's 21.6% and B's 26.5%, per side --
  THIS IS THE HYPOTHESIS'S OWN TEST.** The claim is that requiring a
  retest raises the mean by removing trades that were never going to
  follow through, which should show up DIRECTLY as a higher half-target
  reach rate among the trades that survive the filter. **If the reach
  rate does not rise relative to the corresponding side's own A/B
  figure, the filter did not do what it was proposed to do -- reported
  as such regardless of the overall gate verdict.** A side could
  technically still fail the gate even if the reach rate rises (the
  hypothesis partially right, the magnitude still insufficient), and a
  side could pass the reach-rate test while still failing the gate, or
  vice versa -- both reported as separate findings, never conflated into
  a single pass/fail.
- **The delay between the original reclaim and the retest entry, in
  minutes** (fill_ts minus the original reclaim candle's own close
  time), reported as a distribution (mean, median, min, max), and **how
  much of the move was given up by waiting** -- the difference between
  what the ORIGINAL A/B-style entry price would have been (the reclaim
  candle's own fill, recomputed the same way A/B compute it, for every
  Study C trade that has one) and Study C's own actual (later, retest-
  based) entry price, as a percentage, reported as its own distribution.
- **Whether trades that would have entered in A or B but were filtered
  out by the retest were in fact worse than those that survived -- the
  direct test of the premise.** For every Study C `NO_RETEST` or
  `RETEST_FAILED` skip, the ORIGINAL A/B-style trade (the one that would
  have resulted from entering immediately at the reclaim, computed the
  same way, using A's/B's own entry/exit functions on the same sweep/
  reclaim) is ALSO computed and its own `net_return_pct` recorded --
  never executed as a Study C trade, used only for this one comparison.
  The mean net return of these "filtered-out" counterfactual trades is
  reported against the mean net return of Study C's own actual
  (retest-confirmed) trades, directly answering whether the retest
  filter removed the worse trades or merely the earlier ones.

## Section 10: verdict rule

Each side: if all four gate conditions hold, that side PASSES -- reported
plainly, including the reach-rate-vs-A/B comparison and the
filtered-out-trade comparison regardless of the verdict's own direction.
If any condition fails, that side is NO EDGE, same as A and B. **A pass
on one side and a fail on the other is reported as exactly that -- an
asymmetric result -- not resolved into one combined verdict.** TEST is
read only if the process reaches that point with explicit approval
(Section 12); if DEV fails on both sides, TEST is not read at all, per
this family's own standing discipline.

## Section 11: Claude's pre-committed prediction

I expect both sides to fail. I expect the trade count to fall sharply,
possibly by half or more, on both sides. I expect the half-target reach
rate to rise modestly, because later entries start closer to the target
by construction (less distance left to cover). I expect the mean to stay
negative, because the later entry gives up part of the move it was
waiting to confirm -- the same amount of edge is not free to delay. **I
have been wrong about the mechanism twice in this family already**
(Study A: predicted cost, found follow-through; Study B: predicted
similar-or-worse follow-through from fighting the market's own upward
drift, found better follow-through instead) **while right about the
verdict both times -- weighted accordingly**: if this prediction is also
right about the verdict but wrong about the mechanism a third time, that
itself would be worth recording as a pattern, not dismissed as
coincidence twice over.

## Section 12: process

1. Write this document. Commit and push ALONE. Report the hash.
2. **Five hand-traces per side (ten total)** before any aggregate,
   including one `NO_RETEST` and one `RETEST_FAILED` skip per side.
   Given five slots and two of them fixed to the new `NO_RETEST`/
   `RETEST_FAILED` shapes (the two mechanisms this study actually adds,
   and therefore the two most important to verify by hand), the
   remaining three per side cover the entered-trade outcome families:
   one full win (`FULL_EXIT`), one full loss (`STOP_NO_HALF`), and one
   scaled/mixed outcome (`HALF_THEN_TIME_EXIT`) -- not re-demonstrating
   `NO_CONFLUENCE`, which is unchanged, shared machinery already proven
   by hand in both A's and B's own process.
3. Run DEV only, both sides. Report. **STOP for approval before TEST.**

## Section 13: discipline

All parameters fixed now: the `0.2xATR` retest-proximity tolerance, the
same-candle-allowed interpretation of the return-then-close sequence,
the original-sweep-extreme stop convention, the recomputed-R target
formulas. If DEV fails on one or both sides, these exact parameters are
not retried at other values (a different tolerance, a stricter
different-candle-required retest, a retest-adjusted stop) -- a changed
retest design would be a new, separately pre-registered trial of this
same family, not a retry of this one. This governs Study C only; Study
A's and Study B's own closed results are unaffected regardless of
Study C's own outcome.

## Status

Preregistration complete. Not yet committed. Next: commit alone, report
hash, then build `src/liquidity/c.py` and hand-trace 5 real DEV-window
trades/skips per side.
