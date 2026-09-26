# Swing Trading (1-5 Day Horizon): Findings

Full process record (phase-by-phase build, every intermediate number,
every correction): `SWING.md`. Frozen rule and methodology:
`PREREGISTRATION_SWING.md`. This document is the conclusion, written last,
in the main project's `FINDINGS.md` style.

## 1. The question

Is there any 1-5 day horizon, universe, and condition set on NSE equities
where expected return exceeds realistic retail transaction costs?

## 2. The answer

**No, for the one rule tested.** The frozen rule (momentum-top-decile
stocks in the bottom tercile of 5-day return market-wide, with elevated
volume and the broader market in an uptrend, held 5 trading days) sits at
the **9.8th percentile of a random-entry null distribution** drawn from
its own candidate pool, matched trade count and timing, 1,000 seeds, on
data cleaned of a known data-integrity defect (Section 6). Roughly 90% of
random selections from the same universe, on the same days, outperformed
it. This is below this project's own pre-stated decision criterion (the
random-entry median) -- a criterion fixed before the clean data existed,
not chosen after seeing the result.

## 3. What looked like an edge, and was not

Read in isolation, several numbers looked like a working strategy:
expectancy 0.356-0.495% net of cost, Sharpe 1.09-1.52, and a clear win
over buy-and-hold (0.793% vs 0.118% expectancy). **All of it is
attributable to the candidate universe's own upward drift, not to the
rule's selection.** The random-entry benchmark is the one that isolates
this, and it is the one that discriminates:

- **Buy-and-hold is a weak benchmark here.** It answers "does this
  universe rise on average," not "does this rule pick better names within
  it." The rule beat it because the universe itself (momentum-top-decile,
  high/mid liquidity) drifts up on average -- a fact about the universe,
  not the rule.
- **Coin-flip is a weak benchmark too.** Randomizing the sign of the
  rule's own trades centers the null at ~0% by construction; the rule's
  positive mean clearing that null (100th percentile) only confirms the
  universe has positive drift, the same fact buy-and-hold already showed.
- **Matched random entry is the benchmark that actually tests the rule's
  selection**, because it holds the universe, the trade count, and the
  entry timing fixed and randomizes only WHICH names get picked. On that
  test, the rule selects **worse than random** from its own candidate
  pool. A rule that cannot beat a random draw from the population it
  already narrowed down to has not demonstrated selection skill, whatever
  its absolute expectancy looks like against a benchmark that was never
  measuring the same thing.

## 4. The cost gate was never a plausible bar, and it was checked before any signal existed

Phase 1 (before any rule was designed) found that break-even at a 5-day
horizon required roughly IC=0.05 at a Rs 5L+ position -- and even that one
cell failed the standing 3x hurdle. IC=0.05 exceeds the strongest
signal this project has ever measured at any horizon: `earnings_yield`'s
IC +0.0393 at a 63-day horizon on a comparable NSE universe (the next
strongest, `margin_trend`, was +0.0244) -- and that result is itself only
"suggestive," failing multiple-comparisons correction. Short horizons are
not an easier place to find signal than the horizon this project's
fundamentals work already struggled at; if anything the opposite, since
per-observation noise does not shrink with the holding period the way a
true signal's edge might. **The rule was tested anyway, with this bar
stated upfront** (`PREREGISTRATION_SWING.md`), so that a favorable-looking
backtest number could not be mistaken for having cleared it. It has not
cleared it, and the rule did not need to reach that question at all --
Section 2's random-entry result fails on its own terms first.

## 5. Capital: the binding practical constraint, independent of the verdict

Even if the rule had shown an edge, it would have required capital an
order of magnitude beyond what was contemplated when it was designed.
**Peak concurrent positions: 81** (clean data). **Peak capital deployed:
Rs 2.43 crore at the Rs 3L position floor** (Rs 4.05 crore at Rs 5L). The
original back-of-envelope estimate -- 2.2 entries/day x a 5-day hold ~=
11 concurrent positions, ~Rs 33 lakh -- was wrong by **~7.6x**, because
entries cluster in bursts (median 1/day, mean 2.2/day) rather than
spreading evenly across the holding period. A rule that traded rarely on
average could still require crore-scale capital on its busiest days.

## 6. Bug #11: a real, independent finding, regardless of the strategy's fate

Found while sanity-checking this backtest's single worst trade (a -98.6%
"return" on MAJESCO that was actually the real December 2020 Majesco
demerger, never corrected by `adjustment_factors`): **a same-ISIN
uncorrected corporate action is unguarded anywhere in this codebase.**
`lineage_jump_guard` (Bug #1's fix) only checks the boundary between an
ISIN and its lineage successor; a jump within one ISIN's own continuous
row sequence is structurally invisible to it. A new detector
(`src/data_layer/same_isin_jump_guard.py`, 4 tests) scanned the full
warehouse: **288 rows across 78 entities** carry this exact,
previously-unguarded shape (excluding 1,057 rows that span a >5-day
calendar gap already handled elsewhere by `STALE_GAP_DAYS`). Of the 78,
5 illiquid names contribute 208 rows via a different, undiagnosed
repeating pattern; the remaining 73 are one-off events, a mix of genuine
market crashes needing no correction and plausible missed corporate
actions on names with zero `corporate_actions` coverage at all -- not
individually verified, all excluded conservatively from this backtest's
clean rerun. Excluding them moved the headline percentile from 9.0 to
9.8 -- immaterial to Section 2's conclusion, but the gap itself is real
and plausibly affects the main momentum project's own price-based
factors for any entity with this shape of event, unchecked there.

**Checked, not assumed, before writing this into the sibling `trade-info`
project**: `trade-info` already has a pipeline-wired detector for this
exact shape (`src/nsepit/quality.py`'s `PriceDiscontinuity`), and its own
docstring independently cites the identical `INE784B01035`/WINSOME
long-gap case this session's scan also surfaced on its own. That
agreement is the detector working correctly in two independently-built
systems, not a coincidence worth noting only in passing -- it is
corroborating evidence the underlying defect classification is real and
reproducible. No bug entry was added to `trade-info`; the instruction to
add one there was checked against the actual code rather than complied
with by default, and found to not apply.

## 7. What this does and does not conclude

**Concludes**: this one rule, at a 5-day horizon, on this universe, does
not have a demonstrated edge over picking randomly from the same
candidate pool. The cost structure at this horizon requires an
exceptional signal to be viable at all, and this rule is not that signal.

**Does not conclude**: that no 1-5 day edge exists on NSE equities under
any rule, universe, or condition set. One rule set, one horizon, one
universe construction was tested, pre-registered before the backtest ran.
A different mechanism, a different universe, or a different horizon
within the 1-5 day band remains untested. This finding rules out this
rule, not the broader question the project opened with.
