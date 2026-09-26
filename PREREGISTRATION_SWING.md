# Pre-registration: 5-day short-term-reversal rule (swing project)

Frozen before any backtest is run, per instruction. Nothing below changes
after this document is written, except by an explicit, recorded amendment
the way the main project's `PREREGISTRATION.md` records its own
post-hoc annotations -- never a silent edit.

## Why now, not sooner

Phase 1 (`SWING.md`, `experiments_swing.csv`) established the cost/dispersion
ceiling this rule must clear: at a 5-day horizon, break-even requires
roughly IC=0.05 at a Rs 5L+ position -- above the strongest fundamentals
factor this project has ever measured (`earnings_yield`, IC +0.0393 at a
much longer 63-day horizon), and the standing 3x hurdle fails everywhere
in that sweep, including the best cell. This rule is being tested anyway,
with that bar stated upfront, not discovered after a favorable-looking
backtest number.

## Mechanism, stated so it can be judged on its own logic before any result exists

The candidate pool is stocks in the **momentum top decile** -- by
construction, names with strong trailing 12-month (skip-1-month) returns.
Layering a **bottom-tercile 5-day return** filter on top of that pool does
not select generic "oversold" stocks; it selects **established winners
that have just had a bad week**, which is a more specific and more
plausible short-term-reversal setup than an unconditional reversal screen
would be (it also structurally excludes stocks whose bad week is a genuine
trend change, since those would not have qualified for the momentum top
decile in the first place -- though this is a claim about the setup's
coherence, not a tested claim about its returns). The volume filter
(condition b) is meant to separate "genuine selling pressure that could
mean-revert" from "quiet drift on no news"; the regime filter (condition
c) is meant to avoid the specific failure mode this project's own momentum
work has already documented once (Section 4/8 of `FINDINGS.md`: momentum's
downside-protection mechanism can invert in a violent reversal) by
requiring the broader market to already be in an uptrend before betting on
a pullback resolving upward.

**Mechanism correction, attributed**: an earlier draft of condition (a)
below ranked the 5-day return WITHIN this momentum-top-decile candidate
pool. The user caught this: the bottom tercile of a set of winners is "the
weakest winners," not "stocks that fell relative to the market" -- a
different population, and one the short-term-reversal mechanism above does
not obviously apply to. Corrected to rank across the full EQ universe
first, then intersect with the candidate pool -- see condition (a) and
`src/swing/universe.py`.

## Universe (point-in-time at every signal date, no lookahead)

1. Momentum top decile: `factors.momentum`'s existing, tested
   `momentum_12_1` construction (gap-guarded, `lineage_jump_guard`-guarded),
   ranked and deciled AS OF each candidate date -- not a fixed annual
   cohort, since a 5-day-horizon rule needs a fresh candidate pool far more
   often than the main project's 63-day rebalance.
2. ∩ liquidity: high_liq + mid_liq turnover terciles only (same tercile
   construction already used by `fundamental_screener.py`'s
   `compute_liquidity_tercile`), low_liq excluded.
3. ∩ `series = 'EQ'` only (BE/BZ excluded).
4. ∩ ASM/GSM surveillance names excluded where point-in-time-obtainable.
   **Stated as a limitation now, not glossed over**: this project has not
   yet confirmed a point-in-time-correct historical source for ASM/GSM
   status (unlike BE/BZ, which is directly in `prices_eod.series`). If no
   such source is found, this exclusion applies going forward from
   whatever date live status becomes obtainable, and the historical
   backtest is run without it -- flagged in every backtest report, not
   silently treated as equivalent.
5. ∩ fundamentals screener (`fundamental_screener.py`) verdict != FAIL,
   used as a RISK filter only. Never as ranking input, never as a
   substitute for conditions (a)-(c) below.

## The rule, frozen

**(a) Short-term return filter, CORRECTED**: trailing 5-trading-day return
(plain close-to-close, gap-guarded the same way as every other return
computation in this project -- NOT momentum_12_1's skip-most-recent-month
construction, a different lookback entirely) ranks in the **bottom tercile
(bottom 33.3%) of the FULL EQ universe** (every EQ-series entity with a
computable 5-day return that date -- not restricted to the momentum top
decile, not restricted to the liquidity terciles either, per the
correction above). A name qualifies for this condition only if it fell
relative to the WHOLE MARKET; it is then separately required to also be in
the momentum-top-decile/liquidity/screener candidate pool from the
Universe section above. The two conditions are computed independently and
intersected, never one ranked inside the other. "Full liquid EQ universe"
is read as every EQ-series entity, no additional liquidity-tercile
restriction on this ranking population specifically (open to correction if
a narrower ranking population was intended) -- see
`src/swing/universe.py`'s module docstring for the same note.

**(b) Volume filter**: 20-day volume ratio > 1.5x, defined as
`volume[t] / mean(volume[t-20 .. t-1])` -- the signal date's own volume
against the PRIOR 20 days' average, excluding the signal date itself from
its own average (avoids the mild self-reference a same-day-inclusive
average would introduce).

**(c) Regime filter**: NIFTY50 close (`index_eod`, already in this
warehouse, 2016-01-01 to present, no data-layer change needed) > its own
50-trading-day simple moving average, evaluated as of the signal date's
close.

**Entry**: next trading day's open (t+1), per this project's own signal
timing rule -- never the signal-day close.

**Exit**: at the open of trading day t+6 (5 full trading days held from
entry: entry day counts as day 1, exit at the open immediately following
day 5). No stop loss that fires intraday -- daily bhavcopy data only, no
finer timing is available or claimed.

**Position size**: Rs 3,00,000 minimum. Corrected from an earlier Rs 2L
estimate (the user's own number, corrected after reviewing the actual
cost-model output): Rs 2L's worst-case edge/cost is 0.98x, below
break-even and not a viable configuration to state as a floor. Rs 3L is
the first round size where the worst-case bound itself clears 1.0x
(1.01x-1.44x) -- see SWING.md's Phase 2 configuration section for the full
curve.

**Order type**: DELIVERY. Cost model: `src/swing/costs.py`, worst-case and
optimistic ends of the range both reported, never blended to a midpoint.

**A construction note flagged before Phase 3 builds anything**: Phase 1's
measured 8.80% cross-sectional std at the 5-day horizon was computed
CLOSE-TO-CLOSE. This rule's actual exit construction is OPEN-to-OPEN
(entry at t+1's open, exit at t+6's open) -- a different, not-yet-measured
return construction that will be close to but not identical to Phase 1's
number. Phase 3 must remeasure dispersion (and therefore the power
calculation below) on the EXACT open-to-open construction this rule uses,
not reuse Phase 1's close-to-close figure unmodified.

## Costs

Round-trip DELIVERY cost at the Rs 3L position floor: 30.6-43.6bps
(`src/swing/costs.py`, verified in SWING.md's Phase 2 configuration
section). Every backtest report states net-of-cost expectancy using BOTH
ends of this range, never a single blended cost.

## Phase 2 candidate-count check -- COMPLETE, and it blocks Phase 3

Run against the pre-holdout warehouse
(`scripts/run_swing_phase2_candidate_counts.py`,
`data/swing_logs/swing_phase2_candidate_counts_20260926T153443.txt`; full
detail and the funnel table in SWING.md's "Phase 2" section). Headline:
**the full three-condition rule produces zero candidates on 37.8% of
trading days (excluding the momentum lookback warm-up period) and fewer
than 5 candidates on 85.9% of days.** Isolated one condition at a time:
the volume-ratio filter (20d ratio > 1.5x), not the regime filter, is the
dominant bottleneck -- only 10.4% of the momentum/liquidity/reversal
candidate pool clears it on a given day, versus the regime filter alone
removing only the ~32% of days the market itself is below its 50-day
average.

**This is reported for discussion before Phase 3 proceeds, per
instruction, and is not resolved in this document.** The frozen rule above
is written as originally specified (1.5x threshold, unchanged) --
resolving the sparsity (relaxing the threshold, accepting a low-frequency
rule, or something else) is the user's decision, to be made before any
backtest is built, not defaulted to silently.

## Sample size / power calculation -- computed from historical variance only, per instruction never from a fitted mean

**STATUS: REAL, computed from Phase 3's actual backtest of the frozen
rule** (`scripts/run_swing_phase3_backtest.py`,
`data/swing_logs/swing_phase3_backtest_20260926T170135.txt`). Supersedes
the 1,239-trade placeholder below, which used Phase 1's whole-market
close-to-close std, not this rule's own filtered, open-to-open
construction.

**Target**: detect a 0.5% net-of-cost edge per trade at t >= 2.

**Formula**: n = (t_threshold x std / effect)^2. The threshold (2.0) and
the effect (0.5%) are both decided now, before any data from this rule
exists -- neither is fit to a result. Only the std is a measured number.

**Preliminary std, explicitly flagged as a placeholder**: this rule has
not been backtested yet (per the instruction to stop before building
anything past this document), so its own conditional per-trade return std
is unknown. Using Phase 1's measured WHOLE-MARKET 5-day close-to-close
cross-sectional std (8.80%) as a conservative stand-in:

    n = (2.0 x 0.0880 / 0.005)^2 ~= 1,239 trades

**REDONE with the real std, per the above, then redone AGAIN after the
clean rerun** (BUGS.md Bug #11 entities excluded --
`scripts/run_swing_phase3_clean_rerun.py`,
`data/swing_logs/swing_phase3_clean_rerun_20260926T202040.txt`). First
pass (contaminated data): std=7.656%, n~=938. Clean data: std=7.521%,
mean=0.793%, n=4,146 trades:

    n = (2.0 x 0.0752 / 0.005)^2 ~= 905 trades

**This 905 figure -- not 1,239, and not the intermediate 938 -- is the
one that governs when the forward log may be evaluated**, if this rule
is carried to a forward log at all: see SWING.md's Phase 3 section, which
records the headline finding (the strategy underperforms random entry
from its own candidate pool at the 9.8th percentile, clean data) that
this power number would apply to. The 0.5% target and t>=2 threshold did
not change; only the std input was updated, now twice, each time real
data became available, per this document's own rule.

**Trade frequency, now measured**: Phase 3's clean backtest produced
4,146 trades over ~2,000 pre-holdout trading days (~9 years), all
signals taken (unlimited-capital assumption, per "What is NOT being
tested" below) -- approximately 525 trades/year, close to the ~550/year
arithmetic the user derived from Phase 2's candidate counts. Stated as an
estimate, not a guarantee -- live signal frequency could differ from the
historical rate for reasons this backtest cannot anticipate (regime shift,
liquidity changes, etc.).

## What is NOT being tested

- No stop-loss, no partial exits, no position scaling, no portfolio-level
  capital-constraint modeling across simultaneous concurrent signals.
- No composite score of any kind; the fundamentals screener is a pass/fail
  exclusion only, never a ranking input.
- No claim that this operationalizes "the" academic short-term-reversal
  effect precisely -- this is this project's own specific, frozen version
  of it, tested on its own terms.
- No intraday variant of this rule -- the 5-day hold structurally requires
  delivery; see SWING.md's Phase 2 configuration note on why intraday was
  ruled out for a structural reason, not a cost one.

## Interpretation, pre-committed

- **No interim result is judged before the power-calculation-determined
  trade count is reached** (recomputed with real data per above). Early
  trades are logged, not evaluated.
- The historical backtest (Phase 3) is exploratory: it screens whether
  this rule is worth spending the forward-log window on. It is NOT this
  project's primary validation.
- **Forward paper trading is the primary validation**, per this project's
  own founding framing (SWING.md): short horizons generate enough
  independent observations per year that a forward log becomes
  informative within months, unlike the main project's spent multi-year
  holdout.
- A historical backtest "pass" means "worth forward-testing," not
  "live-viable." A historical backtest "fail" ends the project at that
  point, the same way Phase 1's gate could have.

## Procedure

1. Build the point-in-time candidate-universe function (Phase 2 --
   COMPLETE, `src/swing/universe.py`) and its candidate-count check
   (COMPLETE -- see the sparsity finding above, which blocks the next
   step until discussed).
2. Backtest the frozen rule above on pre-holdout data only
   (`SEALED_HOLDOUT_START` not touched, matching SWING.md's data-scope
   decision) -- report trade count, win rate, avg win, avg loss,
   expectancy net of both ends of the Phase 2 cost range, profit factor,
   max drawdown, Sharpe. NO-TRADE must be the modal daily output; report
   what fraction of candidate-days actually produce a signal.
3. Recompute the power calculation above using the backtest's own real
   per-trade return std (never its mean).
4. Multiple-comparisons note: this is one rule, evaluated once, against
   this document's frozen thresholds -- if a second or third rule is ever
   tested later (the brief allows up to 3), that is additional trials
   requiring its own correction, decided when and if it happens, not
   assumed away now.
5. If the backtest cannot even clear its own historical break-even net of
   worst-case cost, stop -- do not proceed to forward logging on a rule
   that failed its own historical screen.
6. If it clears the historical screen, forward logging begins under this
   document's frozen rule, entry/exit timing, position size, and cost
   model -- no threshold changes after logging starts.
