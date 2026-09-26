# Swing trading (1-5 day horizon): a research question, not a trading bot

**Conclusion: `SWING_FINDINGS.md`.** This file is the phase-by-phase
process record (every intermediate number, every correction, in the
order it happened); the findings document is the polished answer.

**The question**: is there any 1-5 day horizon, universe, and condition set
on NSE equities where expected return exceeds realistic costs? "No viable
edge at any short horizon" is an acceptable and fairly likely answer. **It
is the answer** -- see `SWING_FINDINGS.md`.

**Correction to the project brief, stated here because it matters for
anyone reading this later**: the horizon table this project was briefed to
"read in FINDINGS.md before starting" (edge/cost 0.37x at 5d, 0.53x at
10d, IC=0.03) does not exist in this repository's `FINDINGS.md` --
confirmed by a full read of that file. It exists in the **sibling
`trade-info` project's `DESIGN.md`** ("Horizon selection" section,
`ops/report_horizon.py`), computed on that project's own rank[200,600]
capacity-constrained universe, at horizons of 5/10/21/42/63/126 trading
days (not 1/2/3/5), using the OLD flat 42.22bps placeholder round-trip
cost (`nsepit.costs`'s pre-ground-truth default, not the calibrated 26-39bps
figure this project's own cost model is built from, and not a Groww
fixed-fee model at all). None of that table's numbers are directly
reusable here -- different universe, different horizons, different, older
cost model, no fixed per-order costs at all. What IS reused from that
project: its `edge = IC x cross-sectional std of forward returns` formula
(same convention, confirmed present in both `report_horizon.py` and the
later ground-truth capacity script) and its ground-truth spread/impact
measurement (`src/swing/costs.py`'s own docstring has the full derivation
and every caveat on reusing it here).

**Separate from** the momentum/fundamentals work in `src/factors/` and
`src/reports/`: its own code (`src/swing/`), its own scripts
(`scripts/run_swing_phase1_cost_dispersion.py` and later phases), its own
experiments log (`experiments_swing.csv`, not `experiments.csv`). Shares
this project's data layer (`src/data_layer/`) strictly read-only -- no
change has been made or is planned to any data-layer table, guard, or
schema for this project. If a data-layer change is ever needed, the
standing instruction is to stop and ask before making it.

**Hard limit, stated upfront**: only daily bhavcopy data exists in this
warehouse. Intraday entry/exit timing cannot be tested. The shortest
testable construction is OPEN-TO-CLOSE (buy at open, sell at close, same
day). No script in this project simulates intraday bars or claims
finer-than-daily timing.

## Data-scope and holdout decision (made once, stated here, applies to every phase unless revisited)

Phase 1-4 (cost model, universe construction, baselines, simple rule
backtesting) use the **full pre-holdout price history**
(`data_layer.entity_panel.read_entity_panel`, physically truncated before
`SEALED_HOLDOUT_START` = 2025-03-19) -- never the live/current price panel,
and never `authorize_holdout=True`. This matches the main project's own
established precedent (`experiments.csv`'s `low_liq_tercile_cost_calibration`
entry: chose the pre-holdout-compliant path over requesting a holdout
exception, because the pre-holdout window already had enough data to
answer the question at hand). Nine years of daily data is enough to
measure cost/dispersion and to screen candidate rule sets; none of that
needs today's price.

This is deliberately different from how the momentum project's Study 1
used its holdout, and that difference is intentional, not an oversight:
**forward paper trading, not a historical holdout, is this project's
primary validation** (see the user's own framing: short horizons generate
~50 independent observations a year, so a forward log becomes informative
within months). Phase 1-4's historical work is exploratory / rule-screening
only; nothing here is a claim of an out-of-sample-tested result the way
Study 1's holdout pass was. `PREREGISTRATION_SWING.md` (not written yet --
due before any forward logging begins, per the phase plan) will freeze the
rule, costs, universe, and decision thresholds before a single forward
signal is logged.

## Phase 1: cost and dispersion, before any signal -- COMPLETE

Full methodology, all stated assumptions and their caveats, and the full
numeric output: `scripts/run_swing_phase1_cost_dispersion.py`'s module
docstring and `data/swing_logs/swing_phase1_cost_dispersion_20260926T143316.txt`.
Summary and the stop-gate verdict are reported to the user directly (see
`experiments_swing.csv` for the logged run). Cost model:
`src/swing/costs.py` -- see its module docstring for the full derivation,
including the explicit flag that the spread/impact component is ported
from the sibling `trade-info` project's ground-truth capacity study and is
**not yet validated for this project's own (more liquid) planned
universe**.

**Gate result, recorded honestly**: the only viable configuration found
anywhere in the Phase 1 sweep is **IC=0.05, 5-day horizon, Rs 5,00,000
position, at 1.03x-1.49x break-even.** Every other (horizon, IC, position
size) combination fails break-even. **The standing 3x hurdle (imported
from trade-info's own capacity-study convention, not yet this project's
own established rule) fails everywhere without exception, including this
one viable cell.**

**IC=0.05 is not a modest bar.** Verified directly against this project's
own measured fundamentals-factor ICs (`FUNDAMENTALS.md`'s Phase E table,
63-day horizon, same underlying NSE universe): the seven tested factors'
mean_ic magnitudes ranged 0.0103-0.0431, with `earnings_yield` --
the strongest, and still only "suggestive, not established" after
multiple-comparisons correction -- at +0.0393. **IC=0.05 at a 5-day
horizon would need to exceed the best fundamentals result this project has
ever measured at a 63-day horizon**, and short horizons are structurally
harder to extract signal from, not easier: per-observation noise does not
shrink with the holding period the way a true signal's edge might, the
same "noise doesn't scale down with effect size" point this project's own
combination power analysis made in `FINDINGS.md` Section 12, here applied
to horizon instead of factor combination.

**Stated explicitly, per instruction: not a blocker, but the bar that
must be cleared before this project is worth pursuing further.** A
reversal/momentum-style price signal at 5 days would need to be an
exceptional one -- stronger than anything else measured in this project's
history -- to make Phase 1's cost structure survivable. This is recorded
now, before any signal is tested, specifically so a later positive-looking
backtest number cannot be read as "it worked" without first checking it
against this bar.

## Configuration fixed for Phase 2 onward (2026-09-26)

Decided now, based on Phase 1's results, and not revisited without a new
diagnostic:

- **Horizon: 5-day only.** 1/2/3-day horizons are below break-even at any
  IC tested in Phase 1's sweep, at every position size -- not close enough
  to be worth carrying forward as live candidates.
- **Universe**: momentum top decile ∩ {high_liq, mid_liq} turnover
  terciles (low_liq excluded) ∩ series='EQ' only (BE/BZ excluded) ∩
  ASM/GSM surveillance names excluded where obtainable (state as a
  limitation if not point-in-time obtainable) ∩ the existing fundamentals
  screener (`src/reports/fundamental_screener.py`) as a RISK filter only,
  never as the short-term signal itself -- quarterly fundamentals have no
  plausible mechanism at a 5-day horizon.
- **Minimum position size: Rs 3,00,000.** Corrected from an earlier
  Rs 2,00,000 estimate (the user's own number, corrected by the user after
  reviewing the actual cost-model output): Rs 2L's worst-case edge/cost
  (IC=0.05, 5d) is 0.98x -- below break-even, not viable, and stating a
  sub-1x configuration as "the floor, with a flag" invited reading the
  flag as optional rather than binding. Rs 3L is the first round position
  size where the WORST-CASE bound itself clears 1.0x (1.01x-1.44x), so it
  is the one recorded as the stated minimum. Full curve, verified against
  `src/swing/costs.py` (DELIVERY, worst-case cost end): Rs 50k
  42.4-55.4bps, Rs 1L 35.3-48.3bps, Rs 2L 31.8-44.8bps, Rs 3L
  30.6-43.6bps, Rs 5L 29.6-42.6bps -- steep below ~Rs 2-3L (fixed Groww
  brokerage + the flat Rs 23.60 DP charge dominate at small size), nearly
  flat above it. State this Rs 3L floor in every output from here on.
- **Holding period: DELIVERY (overnight), not intraday.** Correction
  recorded and attributed: the original stated rationale ("the STT
  difference alone makes intraday unviable") was the user's own framing,
  checked against `src/swing/costs.py` and found backwards -- in this cost
  model INTRADAY is actually CHEAPER than DELIVERY (STT 0.025% sell-only
  vs. 0.1% both sides; no DP charge) -- at Rs 5L, intraday round-trip is
  10.5-23.5bps vs delivery's 29.6-42.6bps. Intraday is ruled out for a
  structural reason instead: the rule holds a position for 5 trading days,
  and an intraday position is definitionally closed the same day it
  opens -- the two are incompatible regardless of relative cost. The user
  accepted this correction and asked that it be recorded as theirs, not
  glossed over.

## Phase 2: candidate-count check, before any backtest -- COMPLETE

Mechanism correction applied first (the user caught this, not found
independently): the frozen rule's 5-day-return bottom-tercile condition
must rank across the FULL EQ universe, not within the momentum-top-decile
candidate subset -- ranking within a set already filtered to 12-month
winners would select "the weakest winners," a different, less plausible
population than "stocks that fell relative to the market." Implemented in
`src/swing/universe.py` (see its module docstring for the full mechanism
note and the interpretation adopted for "full liquid EQ universe" --
flagged as open to correction). `tests/test_swing_universe.py` has a
direct regression test constructing 9 synthetic momentum winners plus 1
genuine loser, confirming the bottom-tercile flag lands on the loser, not
on whichever winner drifted up slightly less than its peers.

Full funnel, `scripts/run_swing_phase2_candidate_counts.py`, run against
the pre-holdout warehouse (2274 trading days; results below exclude the
first 273 days, which are the momentum_12_1 lookback warm-up period
2016-01-01 to 2017-02-08 with zero candidates everywhere by construction,
not a rule finding):

| stage | mean/day | median/day | p10 | p90 | 0-candidate days |
|---|---|---|---|---|---|
| (1) momentum top decile ∩ {high_liq,mid_liq} | 92.7 | 103 | 0* | 120 | 12.0%* |
| (2) (1) ∩ bottom-tercile 5d return (full-universe ranked) | 30.2 | 32 | 0* | 48 | 12.0%* |
| (3) FULL RULE: (2) ∩ volume>1.5x ∩ Nifty regime-on | 2.2 (post-warmup) | 1 | 0 | 5 | 37.8% (post-warmup) |

*(1) and (2)'s 0-candidate days are entirely the warm-up period above --
zero post-warm-up dates have zero candidates at those two stages.*

**Full log**: `data/swing_logs/swing_phase2_candidate_counts_20260926T153443.txt`.

**Diagnosis, isolated one condition at a time (post-warm-up only)**: the
volume-ratio condition (20-day ratio > 1.5x), not the regime filter, is
the dominant bottleneck. Applied alone on top of stage 2's ~34/day
candidates: volume-ratio-alone leaves a mean of 3.6/day (only 10.4% of
stage-2 rows clear 1.5x); regime-filter-alone leaves a mean of 23.3/day
(mostly just removing the ~32% of days the market itself is below its
50-day average, not filtering names within an up-day). **The stated
1.5x threshold is what makes the full rule sparse, not the regime filter
and not the universe-narrowing conditions.**

**Viability reading, corrected**: the sparsity finding above was framed as
blocking Phase 3, and it is not -- the user's own arithmetic corrects this,
recorded here as stated: **2.2 candidates/day x ~2,000 usable pre-holdout
days ~= ~4,400 trades, well above the (then-provisional) 1,239-trade power
target.** A low daily rate is not the same thing as an insufficient total
sample when the backtest spans nine years; the earlier framing conflated
"sparse per day" with "not enough data," which does not follow. The volume
threshold stays frozen exactly as pre-registered (see PREREGISTRATION_SWING.md's
"why the threshold stays frozen" note: relaxing it now, after seeing the
sparsity, would make any subsequent test a search rather than a test of
the pre-registered rule).

**What the sparsity actually constrains, both recorded**:
- **Capital**: 2.2 entries/day at a 5-day hold implies ~11 concurrent
  positions on average by simple arithmetic (2.2 x 5) -- at the Rs 3L
  floor, ~Rs 33 lakh deployed. Phase 3's actual simulation (below) measures
  the real figure directly rather than relying on this approximation.
- **Forward test timeline**: ~550 trades/year (2.2/day x ~250 trading
  days), so the power target is roughly (target trades)/550 years of
  forward logging -- moot unless Phase 3's historical backtest shows
  something worth forward-testing.

## Phase 3: the frozen rule's backtest -- COMPLETE

First run: `scripts/run_swing_phase3_backtest.py`,
`data/swing_logs/swing_phase3_backtest_20260926T170135.txt`. Clean rerun
(BUGS.md Bug #11 entities excluded, drawdown reporting corrected):
`scripts/run_swing_phase3_clean_rerun.py`,
`data/swing_logs/swing_phase3_clean_rerun_20260926T202040.txt`.

### HEADLINE: the strategy underperforms random entry from its own candidate pool

**The strategy's own mean gross return sits at the 9.8th percentile of a
random-entry null distribution (matched trade count and timing, 1000
seeds, clean data) -- ~90% of random selections from the SAME candidate
pool, on the SAME days, did better.** Beating buy-and-hold (0.793% vs
0.118%) reflects the candidate universe's own drift, not the rule;
beating coin-flip (mean ~0%, as expected for a directionless null) only
shows the universe rises on average. The reported Sharpe (1.11-1.55
depending on cost bound and position size) is a property of the candidate
universe, not evidence the three-condition selection adds anything --
recorded as the primary finding, per instruction, not as one line among
several.

### Check 1: was the random benchmark contaminated the same way as the strategy?

Yes, exposed to the same risk -- checked directly, not assumed. **BUGS.md
Bug #11** (found while sanity-checking this backtest's single worst
trade): a same-ISIN, no-gap price collapse (MAJESCO, December 2020
demerger, `adjustment_factors` never corrected, `corporate_actions` has
zero records) is unguarded anywhere in this codebase --
`lineage_jump_guard` only checks ISIN-lineage-TRANSITION boundaries, and
this ISIN never changed. Full-warehouse scan
(`src/data_layer/same_isin_jump_guard.py`, 4 tests passing): 288 rows /
78 entities with a <=5-day gap (the un-guarded shape; 1,057 more rows have
a >5-day gap and are already excluded elsewhere by `STALE_GAP_DAYS`, not
part of this blast radius). Of the 78, 5 illiquid names contribute 208
rows via a repeating exact-ratio pattern (a different, undiagnosed
mechanism); the other 73 are one-off, a mix of genuine market crashes
(YES Bank, Jet Airways) needing no correction and plausible missed
splits (JSWSTEEL, GRASIM, TRENT -- zero `corporate_actions` coverage at
all) -- not individually verified, all 78 excluded conservatively per
instruction. **Clean rerun result: percentile moved from 9.0 to 9.8 --
the contamination was not material to the headline finding**, checked
rather than assumed.

### Check 2: drawdown, corrected

The original -700% "cumulative-return-units" figure was flagged as
uninterpretable and is retracted. Corrected version
(`equity_curve_drawdown` in `src/swing/backtest.py`): a real rupee equity
curve, starting capital stated as the measured peak concurrent capital
(the exact amount this unlimited-capital backtest required to never miss
a trade), realized P&L booked at each trade's exit date. **Clean result:
max drawdown -8.0% to -9.0% of peak capital** (Rs 300k: starting capital
Rs 2.43 crore [81 max concurrent x Rs 3L], drawdown Rs -21.4 to -24.0
lakh; Rs 500k: starting capital Rs 4.05 crore, drawdown Rs -35.3 to
-39.6 lakh, across the two cost-bound ends) -- now comparable to
anything else expressed as a percentage of capital.

### Recorded, both, as instructed

- **Peak concurrent positions 84 (contaminated run) / 81 (clean),
  peak capital Rs 2.52 crore / Rs 2.43 crore at the Rs 3L floor.** The
  user's own ~Rs 33 lakh arithmetic estimate (2.2/day x 5-day hold) was
  wrong by ~7.6x, because entries cluster (median 1/day, mean 2.2/day,
  but bursty) rather than spreading evenly -- recorded here as the
  user's correction of their own number, not glossed over. Even if the
  rule had shown an edge, it would require capital an order of magnitude
  beyond what was being discussed when the rule was designed.
- Full dispersion/power recomputation on clean data: n=4,146 trades
  (was 4,346), std=7.521% (was 7.656%), mean=0.793% (was 0.792%).
  Recomputed power target: **905 trades** (supersedes both the original
  1,239 placeholder and the 938 contaminated-data figure) --
  `PREREGISTRATION_SWING.md` updated.

### Bug #11 is independently valuable, per instruction

Recorded in `BUGS.md` regardless of the strategy's own verdict: a
same-ISIN uncorrected corporate action is unguarded anywhere in this
codebase, and the same gap would affect the MAIN momentum project's own
`momentum_12_1`/`trailing_vol_252`/forward-return computations for any
entity with this shape of event, not checked there. **Correction to the
initial plan**: the sibling `trade-info` project was checked before
writing anything into its `DESIGN.md`, and it already has an analogous,
pipeline-wired detector (`src/nsepit/quality.py`'s `PriceDiscontinuity`,
citing the identical `INE784B01035`/WINSOME long-gap case this session
independently re-found) -- **not** an unaddressed gap there. No entry was
added to `trade-info`; reported to the user instead of guessing.

## Phases 4-6: not started

Walk-forward validation and the forward pre-registration are still
pending. No interpretation of Phase 3's numbers has been offered, per
instruction.
