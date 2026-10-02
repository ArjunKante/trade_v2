# Fibonacci/ORB day-selection with open entry (`src/fibo_open/`)

**Separate from `src/fibo/` (the sealed-test Fibonacci/ORB breakout module,
`FIBO.md`/`PREREGISTRATION_FIBO.md`): its own code (`src/fibo_open/`), its
own log directory (`data/fibo_open_logs/`), its own doc (this file). No
code, result, or conclusion in `src/fibo/`, `FIBO.md`, or
`PREREGISTRATION_FIBO.md` is modified by this module.**

## Origin -- stated plainly

This idea came from observing `src/fibo`'s own sealed-test result: the
ORB-breakout entry trigger scored at the **2.3rd percentile** against a
random-entry-time (TIMING) null, on the SAME good days the Fibonacci+ORB
confluence picked (`FIBO.md`, "THE SEALED TEST" section). That observation
was **not pre-specified** before the sealed test was read -- it is a
post-hoc reaction to seeing the entry mechanic look like the weak link in
an otherwise-passing selection mechanism.

**Consequence, stated without softening: the historical data has already
been seen, and no untouched window remains for this rule set.** Every
result in this document's Phase 1 is therefore a **DIAGNOSTIC**, not a
test. Its only purpose is to decide whether a two-year forward test
(Phase 2) is worth starting. It is explicitly NOT evidence that this
strategy works, no matter how the numbers land.

## THE RULES

Identical to `src/fibo` except entry. Every daily-side rule is reused
directly from `src/fibo` (`fibo.signals`, `fibo.indicators`), never
reimplemented:

- Same daily Alligator uptrend, 5-each-side fractals, 2xATR minimum move,
  50-61.8% golden zone, same ORB-overlap condition for SETUP ON.
- **ENTRY (the one rule that changes):** buy at the 09:30 price -- the
  OPEN of the first 1-minute bar immediately after the opening range
  closes -- on EVERY setup-ON day. No breakout trigger, no waiting, no
  11:30 cutoff.
- Stop: ORB low, same as `src/fibo`.
- Target: min(entry + 2R, swing high), same as `src/fibo`.
- Exit 15:15 if neither hit.
- Rs 500 fixed risk, same as `src/fibo`.
- **UNIVERSE: top-100 by turnover only** (point-in-time, annual,
  `fibo.universe.reconstitute_annually(top_n=100)`). Band 101-200 is where
  `src/fibo`'s own sealed test found cost killed the result (109/188
  trades, 58%, net loser at 4x the high-bound spread/impact assumption --
  `FIBO.md`, "THE SEALED TEST") and the 4x stress multiplier itself is an
  unmeasured assumption for that thin a population -- excluding band
  101-200 here avoids building Phase 1 on top of an assumption nobody has
  checked. The trade count this exclusion costs is reported below.

Code: `src/fibo_open/backtest_open.py` (`evaluate_entity_day_open`,
`find_open_entry`), 10/10 tests in `tests/test_fibo_open_backtest.py`,
including the one assumption that does NOT carry over unexamined from the
breakout rule -- see that module's docstring: `resolve_trade`'s "exclude
the entry bar from monitoring" convention is correct for a close-price
entry (the bar is over by the time the signal fires) but NOT for an
open-price entry (the entry bar's own subsequent high/low is still live
risk at the instant of fill). `evaluate_entity_day_open` passes
`resolve_trade` an entry timestamp one minute before the entry bar so the
monitoring window correctly includes it.

## Phase 1 -- DIAGNOSTIC ONLY, explicitly not a test

**STATUS: run 2026-10-02.** 866 open-entry trades found across all 386
downloaded entities, full range; 466 breakout-entry trades on the
identical (entity, day) pairs. Restricting to top-100 (Phase 1's
universe): **400 open-entry trades** (443 more trades sit in the excluded
band 101-200 -- the trade count that exclusion costs, per instruction;
23 further trades fall in years with no resolvable band and are also
excluded from every number below), **209 breakout-entry trades** (241
more in band 101-200, 16 unranked).

Range: 2016-10-04 to 2026-09-18 (full available history, no dev/test
split -- there is no untouched window left to split, per Origin above).
No `fibo.holdout` guard is called: that guard protects a DIFFERENT,
unrelated sealed window for a hypothesis whose rules WERE frozen before
any data was read; this module's rules were not, so the guard's premise
does not apply here.

**Engine** (`scripts/fibo_open_diagnostic_backtest.py`): one evaluation
pass over every (entity, day) pair with resolved scale and an active
(uptrend AND has_swing) daily signal across all 386 entities with
downloaded 1-minute bars (no universe pre-filter at evaluation time) --
every such pair gets BOTH `fibo.backtest.evaluate_entity_day` (breakout)
and `fibo_open.backtest_open.evaluate_entity_day_open` (open) evaluated on
IDENTICAL inputs, so SETUP_OFF vs SETUP_ON classification is identical
between the two by construction. Universe membership (top-100 AND
top-200, point-in-time, annual) is attached to every trade AFTERWARDS, as
a tag, so the top-100 headline and the "what did excluding band 101-200
cost us" count can both be read off one pass.

**OPEN entry, top-100, 400 trades: win rate 56.2%.** Exit reasons STOP
37.5% / TARGET 37.0% / TIME_EXIT 25.5%.

| scenario | mean net R | t | vs null (b) | vs null (b2) |
|---|---|---|---|---|
| (i) flat low | -0.0080 | -0.098 | 100.0th | 100.0th |
| (ii) flat high | -0.5335 | -4.423 | 100.0th | 100.0th |
| (iii) pessimistic banded (1x/2x) | -0.8902 | -5.747 | 100.0th | 100.0th |

By rank band: 1-50 (n=198) mean_gross +0.5072, mean_net_lo -0.0031;
51-100 (n=202) mean_gross +0.4340, mean_net_lo -0.0128. By year: every
year from 2017-2026 is gross-positive, but mean_net_hi and
mean_net_pess are negative in 8 of 10 years (2018 and 2020 are the only
exceptions). Full by-year table in
`data/fibo_open_logs/diagnostic_report_run1.log`.

**SAME metrics, BREAKOUT entry, restricted to the identical top-100
stock-days, 209 trades: win rate 71.3%.** Exit reasons TIME_EXIT 71.3% /
TARGET 18.2% / STOP 10.5%.

| scenario | mean net R | t |
|---|---|---|
| (i) flat low | +0.3685 | 5.871 |
| (ii) flat high | +0.2814 | 4.496 |
| (iii) pessimistic banded (1x/2x) | +0.2260 | 3.597 |

**Reading the comparison, descriptively, no rule changed in response:**
day SELECTION is equally strong under both entries -- the open-entry
strategy beats both selection nulls at the **100th percentile under every
cost scenario**, exactly as strong a selection signal as the breakout
rule's own sealed-test result. But net profitability does not survive
contact with costs the way breakout's does: open-entry's mean net R is
statistically indistinguishable from zero even at the LOW cost bound
(t=-0.098) and solidly negative at the HIGH and pessimistic bounds,
while breakout-entry (same stock-days, same universe) stays robustly
positive under all three. The STOP/TARGET/TIME_EXIT mix is consistent
with why: open-entry fires immediately at 09:30 with no confirmation,
so it is frequently entering close to the ORB low (its own stop) --
small R relative to entry price -- which inflates the SAME flat
spread/impact bps cost into a much larger cost-per-R than breakout's
entry, which only fires after price has already moved above the ORB
high, buying more room between entry and stop. This is the mirror image
of the TIMING-null finding that motivated this module: removing the
entry trigger does not fix the entry mechanic's cost sensitivity, it
makes it worse, because the trigger was itself what gave the breakout
rule its R cushion.

Null (b)/(b2) pool sizes: 223,860 / 65,806 (29.4% of (b)). Seed count
200 (not 1000): see `scripts/fibo_open_diagnostic_nulls.py`'s docstring
and `data/fibo_open_logs/diagnostic_nulls_run2.log` -- the candidate pool
is ~2 orders of magnitude larger than draws/seed, so the bars cache never
warms up and 1000 seeds would have cost ~7 hours for no precision this
diagnostic needs (0.5% resolution at 200 seeds is already far finer than
the decision requires).

**Null (b)/(b2) methodology, re-derived not copied**
(`scripts/fibo_open_diagnostic_nulls.py`): `src/fibo`'s own selection
nulls redraw entry randomly among 8 15-min candle starts (09:30-11:30)
specifically to avoid biasing the comparison toward or against the
breakout rule's own discretionary entry-timing choice. The open-entry
rule has no entry-timing choice at all -- every setup-ON day enters at a
fixed 09:30 open, by rule -- so there is nothing left to marginalize over
on the null side either. Holding entry mechanism FIXED and identical
between the real strategy and its selection null is what isolates
SELECTION specifically (the stated purpose of (b)/(b2)), so this null
fixes entry at the same 09:30 open the real strategy uses, rather than
blindly reusing the 8-candle-start redraw. Pool restricted to the top-100
universe (this module's Phase 1 universe). Stop distance drawn from the
open-entry strategy's own empirical R distribution; flat 2R target (a
random day has no real swing high to cap against); 200 seeds each for
(b) and (b2) -- see the pool-size note above for why.

## Phase 1 verdict: NO to Phase 2

**Decided 2026-10-02, after reading the diagnostic above: no two-year
forward test. This module stops here.** The diagnostic did exactly what
it was built to do -- it stopped a forward test on a strategy that loses
money, before any live data was collected.

**This module was proposed by the user, with an explicit, falsifiable
prediction, and the data refuted that prediction. That is the diagnostic
working as intended, not a failure of it.** The prediction, stated
plainly: that removing the breakout entry trigger would improve net
results, because `src/fibo`'s TIMING null had shown the breakout trigger
picked worse PRICES than a random entry time, on the same good days. The
Phase 1 result above shows the opposite -- net R is markedly worse under
open entry than under breakout entry, on the identical top-100
stock-days, under every cost scenario.

**The mechanism, stated for the record because it corrects a reasoning
error and generalises beyond this module:**

The TIMING null measured GROSS return, and correctly showed that breakout
entry picks worse gross prices than a random entry time. The inference
drawn from that -- that removing the breakout trigger would improve NET
results -- does not follow, and was wrong.

Entry price does not only set the gross price paid. Under this rule set,
entry price also determines STOP DISTANCE (stop = ORB low, fixed), and
stop distance sizes R (position size is `floor(fixed_risk_rs / R)`, so a
small R means a large position). An entry at 09:30 sits close to the ORB
low by construction -- the opening range has barely had time to develop
when the signal fires -- so R is small, and a FIXED spread/impact cost
(charged in rupees on position size, not on R) becomes enormous relative
to R once divided through. The breakout rule, by only firing after price
has already moved away from the stop, buys a larger R for the same
absolute cost -- not a better gross price, a bigger cost cushion.

**The breakout trigger was never providing a better entry price. It was
providing a cost cushion, by construction of how this rule set sizes
risk.** A null built on gross return cannot see that, because the
quantity it measures -- gross R -- is computed independently of position
sizing; the cushion only shows up once cost is divided through by R.

**GENERAL LESSON, for any future entry-rule comparison in this
project:** whenever risk is defined by the distance between entry and
stop (as every rule set in `src/fibo*` does), comparing entry rules on
GROSS return is not comparing the quantity the strategy actually
optimises, and can mislead in exactly this direction -- showing one
entry rule "picks worse prices" while hiding that the same rule is
buying a larger, cost-absorbing R in exchange. Any future entry-rule
comparison must be run on NET R (cost already divided through), never
gross, to see this.

## Phase 2 -- NOT started

Per instruction: STOP after Phase 1, and the answer is NO -- see verdict
above. No `PREREGISTRATION_FIBO_OPEN.md`, no forward-only logging, no
further work on this module.
