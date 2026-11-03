# Liquidity confluence, Study D (ascending lows)

## Provenance, stated plainly and prominently

**Study A (long)**: mean net return **-0.2841%**, 8,131 trades, both
nulls **100th percentile**. Closed at DEV, NO EDGE, TEST not read.

**Study B (short)**: mean net return **-0.1212%**, 9,222 trades, both
nulls **100th percentile**. Closed at DEV, NO EDGE, TEST not read.

**Study C (retest confirmation)**: mean net return **-0.2694%** (long,
6,994 trades) / **-0.1096%** (short, 8,168 trades), both nulls **100th
percentile** on both sides. Closed at DEV, NO EDGE, TEST not read.

**All three closed at DEV with NO EDGE. Study D is a FOURTH revision,
proposed by the user after seeing three fail. This carries severe
selection pressure** -- stated here, not glossed over: this is the
fourth trial of the same family, and the base rate for a revision
proposed after three consecutive failures in the same mechanism is
materially worse than a first attempt's own base rate, and worse again
than Study C's own (already-flagged) third-trial pressure.

**The project's own precedent for how far a strong in-sample result can
mislead, recorded again here because the pressure is now higher than
when Study C recorded it**: swing V1 reached the **100th percentile on
65,219 development trades at p=0.001**, cleared both Bonferroni and
Benjamini-Hochberg correction, and scored only the **61.4th percentile**
on its own sealed holdout (`FINDINGS.md` Section 7's own second-read
entry). An extreme, multiply-corrected in-sample null result is not a
guarantee of anything once new data is read. This is recorded as a
caution against over-weighting any of Study D's own null results as
predictive of a TEST outcome, not as a reason to skip TEST if DEV
passes -- it is a reason to read TEST's own result skeptically if DEV
does pass, exactly as swing V1's own history argues for.

**THE HYPOTHESIS, as the user stated it**: rather than waiting for one
more confirmation (Study C's own mechanism), require the PATTERN of
lows to IMPROVE -- each successive dip toward the level shallower than
the last. Sellers losing strength, not just one more touch.

**The counter-evidence, recorded with equal weight, not as a
formality**:

1. **Study C already tested waiting for one more hold, and it did not
   do what was proposed.** The half-target reach rate FELL on both
   sides (21.6% -> 19.6% long, 26.5% -> 23.4% short,
   `LIQUIDITY_C_FINDINGS.md`'s own central finding) -- the retest
   requirement was proposed specifically to raise this number and did
   the opposite. The trades filtered out because price never returned
   to retest (`NO_RETEST`) averaged **+1.0% to +1.15%** -- these were,
   on average, the WINNERS, discarded by a filter built on the premise
   that a non-returning move was suspect rather than strong. **Any rule
   that waits for additional confirmation before entry risks the same
   failure mode**: the strongest moves are disproportionately the ones
   least likely to pause long enough to produce the additional
   structure a waiting rule requires, ascending lows included.
2. **Ascending lows above a defended level is structurally similar to
   what the 50-day Alligator trend filter approximated in POC V2-V5, all
   four of which failed** (`POC_V2_FINDINGS.md` through
   `POC_V5_FINDINGS.md`, family **CLOSED PERMANENTLY**). Not identical --
   POC's filter was a moving-average-based trend condition evaluated
   once at signal time, not a level-specific multi-touch sequence
   evaluated candle-by-candle after the sweep -- but both are, in
   substance, a bet that "evidence of strengthening demand/weakening
   supply, measured a different way, will rescue this entry mechanism
   where a plain sweep-and-reclaim did not." That bet has now failed
   four times under POC alone, independent of Study C's own
   retest-specific failure. The resemblance is recorded, not treated as
   proof Study D must also fail.

Both sides of this are recorded before any Study D trade exists, so
neither can be read as having been added after the result was already
known.

## STUDY D IS A AND B WITH ONE ADDED REQUIREMENT

**Everything from Studies A and B is preserved unchanged, reused
read-only, never modified**: the six levels computed at 09:45 from data
through the previous trading day only; the confluence rule (two or more
same-side levels within 0.5xATR(14), nearest to the previous close if
multiple clusters); sweep bounds (0.1-1.0xATR beyond the zone); the
09:45-14:30 entry window; fixed-capital sizing (`qty =
floor(25000/entry)`); the 0.5% minimum / 5% maximum stop-distance
guards; the scaled exit (half at 1.5R, remainder at 3.0R); the 15:15
time exit; the three-order intraday cost model; the point-in-time
top-200 universe and every guard (jump, ex-date, same-ISIN, previous-
session scale resolution).

**THE KNOWN LEVEL-OVERLAP FLAW IS PRESERVED DELIBERATELY, as in Study
C, so D stays comparable to A, B and C.** The 1-day/1-week nesting
confluence flaw is kept unchanged for the same reason Study C kept it:
`LIQUIDITY_B_FINDINGS.md`'s own post-DEV diagnostic found degenerate
trades performed no worse (better, in Study A's case) across 17,353
trades, and changing the level definition here would confound any
difference between Study D and its predecessors. A corrected,
non-nesting-timeframe confluence definition remains the one identified,
untried fix to this specific flaw -- not this trial, which is testing a
different lever entirely.

**What Study D does NOT reuse from Study C: the reclaim step.** Studies
A and B enter on the FIRST reclaim of the zone after a valid sweep.
Study C added a retest requirement AFTER that same reclaim. Study D
removes the reclaim/immediate-entry step entirely and replaces it with
a longer, structural requirement evaluated directly after the sweep --
the ascending-lows sequence below. This is a different lever from
Study C's (a required SECOND touch of the same kind vs. a required
PATTERN across several touches), stated explicitly so the two are not
read as variations of the same mechanism.

## Section 0: reuse boundaries, read-only

No closed study's own file is touched. `src/liquidity/a.py`,
`src/liquidity/b.py`, and `src/liquidity/c.py` are imported exactly as
Study C imported from A and B -- read-only, never modified. `src/
liquidity/d.py` is new.

**Reused unchanged**:
- `liquidity.a._build_level_lookup_for_entity` -- all six levels.
- `liquidity.a.find_confluence_zone` (LOW, long) / `liquidity.b.
  find_confluence_zone_b` (HIGH, short).
- `poc.v4.find_sweep` (long) / `liquidity.b.find_sweep_short` (short) --
  the ORIGINAL sweep detection, unchanged. **`find_reclaim`/
  `find_reclaim_short` are NOT used by Study D** -- see above.
- `liquidity.a.resolve_scaled_exit_a` / `liquidity.b.resolve_scaled_
  exit_b` -- exit mechanics unchanged. Once filled, a Study D trade is
  resolved exactly like an A or B trade with its own entry price, stop,
  and targets.
- `liquidity.a.three_order_cost_rs` / `hypothetical_single_exit_cost_rs`
  (long) and `liquidity.b.three_order_cost_rs_b` / `hypothetical_single_
  exit_cost_rs_b` (short) -- unchanged.
- `poc.resolution.{ENTRY_WINDOW_START, ENTRY_WINDOW_END, MAX_RISK_PCT,
  fill_bar_after_candle_close}`, `poc.v2.{CAPITAL_RS, MIN_RISK_PCT}`,
  `poc.v4.STOP_BUFFER_ATR` -- unchanged.
- `poc.nulls.{_random_fill, _valid_entry_idx}` -- unchanged.
- All of `box_theory.*`, `fibo.*` universe/costs/inference/context
  machinery -- unchanged, identical to A/B/C's own Section 0.

**New code, lives entirely in `src/liquidity/d.py`**: the ascending-lows
detection functions (`find_ascending_lows_long`,
`find_ascending_highs_short`, Section 3 below, each parameterized by
`n_required` in {2, 3} so one function serves both CONFIG 2LOW and
CONFIG 3LOW) and the entry orchestration wrapping them
(`find_entry_d_long`/`find_entry_d_short`), plus the usual per-study
backtest orchestration and null pool-building, mirroring A/B/C's own
structure but replacing the reclaim step with the ascending-lows scan.

## Section 1: levels, confluence, universe, windows -- identical to A, B, C

No changes. DEV: **2016-10-04 to 2022-12-31**. TEST (sealed):
**2023-01-01 to 2026-09-18** -- identical dates to A, B, C. A fresh
`TestWindowViolationError`/`guard_date_range` pair, own `ACCESS_LOG_PATH`
at `data/liquidity/d/test_window_access_log.txt`, per this family's own
"a fresh instance, not a shared one" convention.

## Section 2: the sweep -- unchanged, and why there is no reclaim step here

Byte-identical sweep detection to A/B/C (0.1-1.0xATR beyond the zone),
using `poc.v4.find_sweep` / `liquidity.b.find_sweep_short` unchanged.
`SWEEP_LOW` (long) / `SWEEP_HIGH` (short) is the sweep's own detected
extreme AT THE MOMENT OF DETECTION (`sweep_low_at_detection`/
`sweep_high_at_detection` in A/B/C's own terminology) -- there is no
reclaim window during which this value could be updated, because Study
D has no reclaim step. This is the value Section 3's invalidation check
and Section 4's stop both use, unchanged for the remainder of the
candle.

## Section 3: the new requirement -- ascending lows (mirrored for shorts)

**Scanning starts at the candle immediately after the sweep candle**
(`sweep_idx + 1`) and continues, in order, until the 14:30 window closes
or the trading day ends.

**A local low** (long side): a candle at index `i` whose LOW is lower
than both candle `i-1`'s own low and candle `i+1`'s own low. Because
candle `i+1` is required to confirm it, a local low at index `i` is only
KNOWN at index `i+1` -- the same one-candle confirmation lag Study C's
own retest-return condition already has no equivalent of (Study C's
condition is evaluated on each candle directly, not retrospectively);
stated explicitly here because it is new to this study.

**INVALIDATION, checked on every candle from `sweep_idx + 1` onward,
independent of local-low detection**: if any candle's LOW drops below
`SWEEP_LOW` (long) / HIGH rises above `SWEEP_HIGH` (short), the setup is
dead immediately, at that candle. **`PATTERN_BROKEN`.**

**Counting the ascending sequence (long side, mirrored for short)**:
maintain `last_counted_low` (initially none) and `count` (initially 0).
For each local low confirmed, in order of confirmation:
1. If this local low's own LOW value is ABOVE the confluence zone
   price, it is ignored entirely -- it does not count, does not reset,
   does not advance anything. Only lows at or below the zone qualify,
   per the instruction's own "at or below the confluence zone price."
2. Otherwise (at or below the zone): if `last_counted_low` is none, OR
   this low is NOT strictly higher than `last_counted_low` -- this low
   becomes the new `last_counted_low` and `count` resets to 1. **Stated
   as a deliberate interpretation, before any trade exists**: the
   instruction specifies "successive local lows where [each is]
   strictly higher than the [one] before," which does not by itself say
   what happens when a candidate breaks the ascending property. Reset-
   and-restart (this low becomes a fresh potential start) is used rather
   than "the whole setup dies" -- `PATTERN_BROKEN` is reserved
   exclusively for the explicit invalidation condition above (breaching
   the original sweep extreme), never for a merely non-ascending local
   low, which is a commonplace, structurally expected event (price does
   not reliably produce a clean monotonic staircase) and not evidence
   the level has failed.
3. Otherwise (strictly higher than `last_counted_low`): `count += 1`,
   `last_counted_low` updated to this low's value.
4. If `count` reaches `n_required` (2 for CONFIG 2LOW, 3 for CONFIG
   3LOW): **`PATTERN_CONFIRMED`**, at the CONFIRMING candle of this
   final qualifying low (index `i+1`, the candle whose own higher low
   established candle `i` as a local low).

**If the window closes (14:30) or the day ends with `count` never
reaching `n_required`, and `PATTERN_BROKEN` never fired first**:
**`PATTERN_INCOMPLETE`.**

**SHORT side** (`find_ascending_highs_short`): the exact mirror --
local highs (a candle's HIGH higher than both neighbours' highs), each
qualifying high must be at or above the zone price, each successive
qualifying high must be STRICTLY LOWER than the one before to extend the
count (ascending highs toward the level means descending VALUES, each
closer to the zone from above -- "shallower" on the short side means a
lower high, not a higher one), invalidation on any candle's HIGH rising
above `SWEEP_HIGH`.

**Entry**: the open of the next 1-minute bar after the CONFIRMING
candle's own close (`fill_bar_after_candle_close`, unchanged -- the
identical fill mechanism A, B, and C already use, applied to the final
ascending low/high's confirming candle).

## Section 4: stop, R, targets

**Stop: `SWEEP_LOW - 0.1xATR` for longs, `SWEEP_HIGH + 0.1xATR` for
shorts -- the ORIGINAL sweep extreme, same convention as Study C,
stated identically: the ascending-lows sequence is evidence the
ORIGINAL level held and strengthened across several tests, not a new,
tighter level to defend.** The invalidation check (Section 3) already
guarantees `SWEEP_LOW`/`SWEEP_HIGH` was never breached between the
sweep and entry, so this stop is never placed on the wrong side of
price at fill by construction -- the same structural guarantee A's, B's
and C's own entry-vs-stop checks already confirm fires zero times.

**R is recomputed from the actual entry price** -- `R = entry - stop`
(long) / `R = stop - entry` (short), using the ascending-lows-delayed
fill price. `HALF_TARGET`/`FULL_TARGET` (1.5R/3.0R) and the 0.5%/5%
stop-distance guards are evaluated against this recomputed R, exactly as
every prior study in this family evaluates its own guards against its
own entry price.

## Section 5: exits, sizing, costs -- unchanged

`liquidity.a.resolve_scaled_exit_a` / `liquidity.b.resolve_scaled_
exit_b`, called with Study D's own (later) `fill_ts`, `entry_price`,
`stop_price`, `half_target_price`, `full_target_price`, `qty`. `qty =
floor(25000/entry_price)` using Study D's own entry price. Cost model
unchanged (Section 0).

## Section 6: four tests, each run and reported separately

Study D runs FOUR configurations independently: **2LOW-long,
3LOW-long, 2LOW-short, 3LOW-short** -- each with its own backtest, its
own nulls, its own gate evaluation, its own verdict. **Mean net return,
trade count, null percentiles, half-target reach rate, and all four
gate conditions are reported SEPARATELY for each of the four, plus a
combined figure per configuration (2LOW combined across both
directions, 3LOW combined across both directions) -- never collapsed
into one overall number.** Same discipline Studies A/B/C already
established: isolating direction revealed real asymmetries in this
family every time it has been tried, and isolating `n_required` is
expected to do the same (Claude's own prediction, Section 11, expects
2LOW and 3LOW to differ sharply in trade count).

**BONFERRONI, stated explicitly**: four tests this trial (2LOW-long,
3LOW-long, 2LOW-short, 3LOW-short). alpha=0.05 / 4 = **p < 0.0125** is
the corrected significance threshold a configuration's own CI/t-test
must clear, in place of the uncorrected p < 0.05 a single test would
use. This is a stricter bar than Study C's own two-sided-but-single-
family comparison required, because Study D runs twice as many distinct
configurations in one trial.

## Section 7: nulls -- same population principle as A, B, C, built from each config's own trades

**TIMING**: restricted to the exact (entity, day) pairs that
configuration's OWN real strategy traded on -- which, by construction,
only exist because the ascending-lows pattern actually confirmed for
that `n_required`. Reuses `liquidity.a._timing_draw_a`-equivalent logic
(a random 5-minute candle replaces the real signal; the real trade's own
stop distance and scaled-exit structure are reused), called against
each configuration's own pool, built from that configuration's own
trades' own stop distances.

**SELECTION**: the same single-day-eligibility-plus-level-history
population A/B/C already use, matched count per month to each
configuration's own trade count that month. Stop distance drawn from
that configuration's OWN pooled `stop_distance_pct`.

**Stated explicitly, since the instruction asks for the ascending-lows
requirement to be "applied to the null draws as well," exactly as
Study C's Section 7 already stated for the retest requirement**:
neither null models the signal-detection step at all (TIMING replaces
it with a random candle; SELECTION replaces it with a random stock-day)
-- there is no sweep, zone, or ascending-lows sequence inside either
null's own draw to re-run the pattern against. **The ascending-lows
requirement is reflected in each configuration's own nulls by
construction, not by adding a pattern-matching step inside the null's
own random-entry mechanism**: TIMING's population is restricted to days
that configuration's own pattern actually confirmed on; SELECTION's
stop-distance pool is drawn from that configuration's own (pattern-
delayed) entries, never borrowed from A's, B's, or C's own pool, and
never shared between 2LOW and 3LOW even within the same direction.

1000 seeds, or 500 with the usual timed-probe fallback, for each of the
four configurations independently -- eight null distributions total
(four configs x two null types).

## Section 8: gate -- applied to each of the four configurations independently

Mean net return > 0, day-clustered 97.5% bootstrap CI (unchanged
machinery) excluding zero **at the Bonferroni-corrected threshold
(p < 0.0125)**; >= 95th percentile against BOTH nulls; still positive
after dropping the best year; positive within bands 1-100 alone. **All
four required, evaluated separately for each of the four
configurations.** A configuration passes only if all four hold for that
configuration. All four configurations' verdicts are reported
regardless of each other's outcome.

## Section 9: report

Everything A, B, and C each reported (trades, distinct days, mean net
return with CI, median, both null percentiles, by year, by band,
confluence-pair breakdown, exit-mix, extra-cost figure, skip counts,
peak concurrent positions/capital) -- for each of the four
configurations, plus the 2LOW-combined and 3LOW-combined figures. Plus,
specific to this study:

- **Trade count against A's 8,131, B's 9,222, and C's 6,994 (long) /
  8,168 (short)**, per configuration. Attrition at `PATTERN_BROKEN` and
  `PATTERN_INCOMPLETE` reported as its own line each, not folded into a
  generic skip total -- these two are the entire mechanism this study
  tests. **How 2LOW compares to 3LOW reported explicitly** (trade count,
  attrition split, and the gate outcome), since the two configurations
  are expected to diverge sharply (Section 11).
- **Half-target reach rate against A's 21.6%, B's 26.5%, C's 19.6%
  (long) / 23.4% (short), per configuration -- THIS IS THE HYPOTHESIS'S
  OWN TEST.** The claim is that ascending lows select trades that follow
  through. **If the reach rate does not rise relative to the
  corresponding side's own prior figure, the filter did not do what was
  proposed, reported as such regardless of the overall gate verdict** --
  identical framing to Study C's own Section 9, applied here to a
  different, stricter filter.
- **The delay from the original sweep to entry, in minutes, and how
  much of the move was given up by waiting** -- directly comparable to
  Study C's own measured 0.07-0.08% give-up. Computed the same way:
  the difference between what the ORIGINAL A/B-style entry (immediate
  reclaim fill, recomputed the same way A/B compute it from the same
  sweep) would have produced and each configuration's own actual,
  pattern-delayed entry price.
- **Whether trades filtered out by the ascending-lows requirement were
  in fact worse than those that survived, split by skip reason
  (`PATTERN_BROKEN` vs `PATTERN_INCOMPLETE`) -- the direct test of the
  premise.** For every Study D `PATTERN_BROKEN` or `PATTERN_INCOMPLETE`
  skip, the ORIGINAL A/B-style trade (immediate entry at the first
  reclaim-equivalent point reachable from the same sweep, using A's/B's
  own entry/exit functions) is ALSO computed and its own
  `net_return_pct` recorded -- never executed as a Study D trade, used
  only for this comparison. **Explicitly checked**: whether
  `PATTERN_INCOMPLETE` behaves the same way Study C's own `NO_RETEST`
  bucket did (positive counterfactual mean, i.e. these were actually
  good trades the filter discarded) -- reported as its own finding
  regardless of the overall verdict, per the instruction.

## Section 10: verdict rule

Each configuration: if all four gate conditions hold (at the
Bonferroni-corrected threshold), that configuration PASSES -- reported
plainly, including the reach-rate comparison and the filtered-out-trade
comparison regardless of the verdict's own direction. If any condition
fails, that configuration is NO EDGE. **A pass on one configuration and
a fail on another is reported as exactly that -- not resolved into one
combined verdict.** TEST is read only if the process reaches that point
with explicit approval (Section 12); if DEV fails on all four, TEST is
not read at all, per this family's own standing discipline.

## Section 11: Claude's pre-committed prediction

**I expect all four tests to fail.** I expect 3LOW to produce far fewer
trades than 2LOW, possibly under 2,000, since requiring a third
strictly-ascending qualifying low is a materially harder bar than
requiring a second, and each additional required low multiplies the
chance of a `PATTERN_BROKEN`/`PATTERN_INCOMPLETE` outcome before the
sequence completes. I expect the half-target reach rate to rise modestly
for 3LOW specifically, since a later entry starts closer to the target
by construction (less distance left to cover) -- but I expect the mean
to stay negative regardless, because the delay gives up part of the
move the same way Study C's own delay did, and because 3LOW's smaller
sample will struggle to clear the Bonferroni-corrected threshold even if
the point estimate improves.

**I have been wrong about the mechanism three times in this family
already** (Study A: predicted cost, found follow-through; Study B:
predicted similar-or-worse follow-through from fighting the market's
own upward drift, found better follow-through instead; Study C:
predicted a sharp trade-count collapse and a rising reach rate from a
small give-up cost, found a modest trade-count drop, a FALLING reach
rate, and a near-cancellation between correctly-filtered losers and
incorrectly-filtered winners) **while right about the verdict all three
times -- weighted accordingly.** If this prediction is also right about
the verdict a fourth time while wrong about the mechanism again, that
is a pattern recorded four times running, not three, and is itself
reported as such regardless of which specific mechanism prediction
turns out wrong this time.

## Section 12: process

1. Write this document. Commit and push ALONE. Report the hash.
2. Build `src/liquidity/d.py`. **Five hand-traces per configuration (20
   total)** before any aggregate, including at least one
   `PATTERN_BROKEN` and one `PATTERN_INCOMPLETE` per configuration --
   the two mechanisms this study actually adds, and therefore the two
   most important to verify by hand, exactly as Study C prioritized
   `NO_RETEST`/`RETEST_FAILED` in its own five-per-side allocation. The
   remaining three slots per configuration cover entered-trade outcome
   families (one full win, one full loss, one scaled/mixed outcome) --
   not re-demonstrating `NO_CONFLUENCE` or the sweep itself, unchanged
   shared machinery already proven by hand in A's, B's, and C's own
   process.
3. Run DEV only, all four configurations. Report. **STOP for approval
   before TEST.**

## Section 13: discipline

All parameters fixed now: the ascending-lows local-low/high definition
(3-candle confirmation), the "at or below/above the zone price"
qualification, the reset-and-restart interpretation of a non-ascending
candidate (Section 3), the original-sweep-extreme stop convention, the
recomputed-R target formulas, `n_required` in {2, 3} and no other value.
If DEV fails on some or all configurations, these exact parameters are
not retried at other values (a different `n_required`, a different
zone-proximity tolerance, a reclaim-style immediate check inserted
before the ascending-lows scan) -- a changed design would be a new,
separately pre-registered trial of this same family, not a retry of
this one. This governs Study D only; Studies A's, B's, and C's own
closed results are unaffected regardless of Study D's own outcome.

## Status

Preregistration complete. Not yet committed. Next: commit alone, report
hash, then build `src/liquidity/d.py` and hand-trace 5 real DEV-window
trades/skips per configuration (20 total).
