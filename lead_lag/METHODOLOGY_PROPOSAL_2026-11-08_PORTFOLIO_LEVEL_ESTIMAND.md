# Methodology proposal: portfolio-level follower response + corrected selection null

**Status: PROPOSAL, NOT APPROVED, NOT COMMITTED.** This document investigates
the human-directed Option A (portfolio-level response) for Issue 1 and the
accepted group-exclusion correction for Issue 2
(`lead_lag/METHODOLOGY_REVIEW_2026-11-08_ESTIMAND_AND_NULL.md`). **No
regression was run, no outcome data was inspected, no code was written,
no file was modified, nothing was committed.** `PREREGISTRATION_LEAD_LAG_V1.md`
(commit `9f71b65`) and `lead_lag/trial_ledger.json` are both unchanged.
Every number below that depends on real data (follower-portfolio sigma,
actual breadth distribution, etc.) is explicitly marked **UNMEASURED** --
proposing a specification is not the same as fitting it, and nothing here
should be read as having measured anything.

---

## Proposed specification, precisely

```
L(t)           = sum_{k=t-4}^{t} mean_i( r(i,k) ), i in that month's true leader tier        [leader-portfolio-only cumulative 5-min return]
B_follower_pool(k) = mean_j( r(j,k) ), j in that month's true follower tier                   [unchanged from Section 9]
S_leader(t)    = L(t) - sum_{k=t-4}^{t} B_follower_pool(k)                                     [unchanged from Section 8 -- "the corrected leader-versus-follower spread"]

R_follower(t)  = sum_{k=t-4}^{t} B_follower_pool(k)                                            [follower portfolio's OWN trailing 5-min return -- same window as the signal]

Y(t,h)         = mean_j( sum_{k=t+1}^{t+h} r(j,k) ), j in that month's true follower tier      [follower portfolio's RAW forward h-minute return -- NOT benchmark-adjusted]

Y(t,h) = alpha + beta*S_leader(t) + gamma*R_follower(t) + delta.X(t) + epsilon(t,h)
```

One row per **(day, signal-minute t)** -- not per follower. `X(t)` is a
portfolio-level control vector, proposed in Section 4 below, not yet
finalized.

---

## 1. Are the signal and response mathematically non-degenerate?

**Yes, both -- by a different argument than before, not merely a repeat of the Section 8 check.**

`S_leader(t)`: already established non-degenerate in commit `9f71b65`
(it is `L(t)` minus a benchmark built from a **disjoint** group --
no self-referential leave-one-out, no telescoping identity).

`Y(t,h)` and `R_follower(t)`: **neither involves any leave-one-out
construction at all.** Both are plain equal-weighted portfolio
aggregates of raw returns -- there is no benchmark subtracted from the
same group being averaged, so there is no analog of the Section 8 or
Issue-1 zero-sum identity to even check for. A portfolio's own raw
return has no algebraic reason to be zero and empirically never would
be (it is literally "did the follower tier go up or down"). This is, in
fact, the simplest possible resolution of Issue 1: **removing the
leave-one-out demeaning from the response is what makes it
non-degenerate** -- the fix is subtraction of a design flaw, not
addition of a new safeguard.

---

## 2. Does this genuinely measure subsequent aggregate follower-portfolio movement?

**Yes, directly, unlike the specification it replaces.** `Y(t,h)` *is*
the follower tier's own aggregate subsequent return -- there is no
cross-sectional demeaning stripping out the common/aggregate component
that Section 1 asks about. A genuine "followers catch up after leaders
move" effect would show up exactly as `beta > 0`: leaders up in the
signal window predicting the follower **portfolio** up over the next
`h` minutes, in aggregate. This directly answers Section 1's literal
question. It does not, on its own, resolve which of Section 1's four
named mechanisms (genuine repricing, common-factor differential speed,
non-synchronous trading, stale pricing) is responsible -- that
limitation is structural and is not newly introduced or resolved by this
change (see Section 5 below, which is where it resurfaces most
concretely).

**One residual identification risk worth naming, not previously
flagged**: because `Y(t,h)` is raw (not benchmark-adjusted), a slow,
multi-year drift common to both `S_leader(t)` and the follower
portfolio's own returns -- e.g. if leaders systematically earn different
average returns than followers over long stretches for reasons unrelated
to any short-horizon propagation mechanism (a size/liquidity-premium-style
effect) -- could in principle induce a spurious `beta` driven by
low-frequency co-trending rather than genuine short-horizon propagation.
`R_follower(t)` (recent momentum) only partially guards against this,
since it is itself a short (5-minute) window. **Proposed mitigation,
requiring a human decision**: add year (or quarter) fixed effects to
`X(t)` so `beta` is identified from within-year, short-horizon
co-movement only, not from any slow cross-year drift. This is a
structural addition, not a data-availability question, and does not
require inventing any new data -- but it is a modeling choice this
proposal does not make unilaterally.

---

## 3. Does the contemporaneous follower-return control create a mechanical relationship or collinearity problem?

**No perfect collinearity -- but a real, derivable, mechanical
relationship exists and should be documented so it is never mistaken
for an empirical finding.**

Since `S_leader(t) = L(t) - R_follower(t)` exactly (by Section 8/9's own
definition), the pair `(S_leader(t), R_follower(t))` is related to the
pair `(L(t), R_follower(t))` by an invertible linear transform:

```
[ S_leader(t) ]   [ 1  -1 ] [ L(t)          ]
[ R_follower(t) ] = [ 0   1 ] [ R_follower(t) ]
```

determinant = 1, so the transform is invertible and full rank whenever
`L(t)` has any variance independent of `R_follower(t)` -- which it
generally will, since the leader and follower tiers do not move in
lockstep. **This means including both `S_leader(t)` and `R_follower(t)`
as separate regressors is exactly equivalent, after reparameterization,
to regressing on `{L(t), R_follower(t)}` directly.** Under that
equivalent form, `beta` (the coefficient on `S_leader(t)`, holding
`R_follower(t)` fixed) has a clean reading: **the marginal effect of the
leader portfolio's own trailing return, net of the follower portfolio's
own trailing return** -- arguably a clearer interpretation than "the
spread's effect" in isolation.

**The mechanical part, worth flagging explicitly**: because
`R_follower(t)` enters `S_leader(t)`'s own definition with a *negative*
sign, there is a built-in, deterministic component of their covariance,
`Cov(S_leader(t), R_follower(t)) = Cov(L(t), R_follower(t)) - Var(R_follower(t))`.
If `L(t)` and `R_follower(t)` are only weakly correlated (plausible, not
yet measured), this covariance will be approximately `-Var(R_follower(t))`
-- i.e., a **negative correlation between the two regressors that is
expected by construction, not a sign of a problem or a finding.** Any
future report of a correlation or VIF diagnostic between `S_leader(t)`
and `R_follower(t)` should note this derivable baseline rather than
treat the (expected) negative correlation as noteworthy on its own.

**Unresolved human decision**: whether Phase 4 should report the
equivalent `{L(t), R_follower(t)}` parameterization alongside
`{S_leader(t), R_follower(t)}` as a standard interpretive cross-check
(same fit, same residuals, different labeling of the same two-dimensional
space) -- this proposal recommends it as good practice but does not
mandate it.

---

## 4. Which portfolio-level controls are defensible with the actual available intraday data?

Defensible (computable from existing data, no new fetch, no invented
series):

- `R_follower(t)` -- already specified, required.
- Time-of-day bucket (opening-30 / midday / closing-30) -- unchanged
  from the existing per-follower design, directly portable to the
  portfolio level.
- Follower portfolio's own trailing intraday realized volatility (e.g.
  trailing 60-minute sum of squared 1-minute follower-portfolio returns)
  -- computable directly from `bars_1min`, genuinely time-varying.
- Leader portfolio's own trailing realized volatility, same construction
  -- computable the same way; a very volatile leader-tier day may behave
  differently from a calm one.
- A coarse, no-new-data market-activity proxy: total traded value across
  the full eligible universe that day (from `prices_eod`), as a
  day-level liquidity/activity control.
- **Proposed, structural rather than data-driven**: year (or quarter)
  fixed effects, per Section 2 above, to absorb slow cross-year drift.

**Not defensible without inventing something**: any intraday sectoral or
broad-market index level (confirmed not to exist, Data Audit Section 2);
a "market" return built from the same 386-name universe used as if it
were an independent factor (it would just be a blend of leaders and
followers, not external to the two groups under study).

**Unresolved human decision**: which subset of the above becomes the
frozen Section 11-equivalent control list for this estimand -- this
proposal lists candidates, it does not choose among them.

---

## 5. Is an independent intraday market-factor control available?

**No.** Confirmed directly from `DATA_AUDIT_LEAD_LAG.md` Section 2:
`index_eod` contains exactly one series, `NIFTY50`, and it is a **daily**
close-to-close series -- there is no intraday index of any kind (broad
or sectoral) anywhere in this project's data. The only intraday-frequency
data available at all is `bars_1min` for the 386-name fibo universe
itself, and that universe **is** the leader-plus-follower partition under
study -- any "market" return constructed from it would be a weighted
blend of the two groups being compared, not an external benchmark.

**This proposal does not invent an intraday proxy and does not silently
substitute daily NIFTY data as if it were equivalent.** The only
data-honest options, both requiring an explicit human choice rather than
a default:

- **(a) No independent market control at all.** Accept that the model's
  only common-factor control is `R_follower(t)` (the follower tier's own
  recent return) -- which is not external to the universe being studied,
  but is at least observable at the correct frequency.
- **(b) An explicitly-labeled, coarse daily control.** Include the prior
  trading day's NIFTY50 close-to-close return (available without
  look-ahead) as a day-level regime proxy, documented plainly as "a
  daily-frequency control for broad market regime, not an intraday
  benchmark and not a substitute for one." This is defensible *if*
  labeled this way; it would not be defensible if presented as if it
  resolved the lack of an intraday benchmark.

**Unresolved human decision: (a) or (b).** This proposal does not choose.

---

## 6. Effect of missing follower observations, incomplete bars, and changing monthly composition

**A new requirement is needed that did not exist under the old per-follower design**: because `Y(t,h)` and `R_follower(t)` are now
cross-sectional averages, a thinly-populated minute (many followers
missing a bar) would produce a portfolio value that does not actually
represent that month's follower tier, rather than simply dropping one
follower's row as before. **Proposed (not yet measured or frozen)**: a
per-minute follower-breadth floor, symmetric to Section 8's existing
leader-side floor (`n_t >= 0.80 * leader-tier size`), applied to both the
`R_follower(t)` signal window and the `Y(t,h)` forward window. The
**0.80 value itself should not simply be copied over** -- it was derived
from the leader tier's own breadth distribution
(`LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 2), which is the most
liquid 20% of the universe and need not have the same staleness profile
as the bottom 80% (followers). **This requires its own data-driven check
(a Task-2-style breadth distribution computed for the follower tier
specifically) before any threshold is frozen** -- proposed as required
Phase-4-preparation work, not computed in this proposal, and explicitly
not chosen from outcome performance.

**Changing monthly composition**: unchanged in kind from the existing
design -- the follower tier (and hence the portfolio `Y(t,h)`/`R_follower(t)`
represent) is reconstituted monthly, so `Y(t,h)` is "that month's
follower tier's return," not a fixed, persistent security, exactly as
any monthly-rebalanced index would be. No boundary-crossing risk exists
within a single observation, because (a) tier membership is fixed for an
entire month, and (b) Section 12 already prohibits any forward window
from crossing a session close, so every `(t, t+h)` pair lives inside one
trading day, which always falls entirely inside one month's tier
definition. This should be stated explicitly in any amendment, as a
documented convention, not a newly discovered risk.

---

## 7. Changes required to day-clustered inference and the placebo bootstrap

**The clustering unit (trading day) is unchanged** -- `trade_date`
remains the correct unit, for the same reason as before (within-day
observations are not independent). What changes is the **source** of
within-day replication: previously it came from many followers sharing a
minute; now it comes only from **multiple signal-minutes within the same
day** (since there is one row per `(day, minute)`, not per
`(day, minute, follower)`). This is a large reduction in raw row count
(roughly a 160-to-309-times reduction, the removed follower multiplier)
-- **this does not necessarily reduce genuine statistical power**, since
Section 14's day-clustered inference already treated the old
follower-level replication as largely non-independent information; the
effective sample size was never meant to scale with follower count. This
needs to be **re-measured**, not assumed, on the real portfolio-level
series (Section 10 below).

**A sharper implication than existed before**: successive signal-minutes
within a day (`t` and `t+1`, say) share 4 of 5 bars in their respective
trailing signal windows, and their forward response windows overlap
almost entirely for `h > 1`. Previously, pooling across many followers
at least added genuinely distinct cross-sectional information to a
given day's cluster; now, with the follower dimension collapsed away,
**pooling many overlapping per-minute rows within a day adds far less
genuinely new information than before, relative to how many rows it
appears to add.** This makes Section 14's existing non-overlapping-sample
check (previously a secondary robustness check) **substantially more
important for this specification** -- arguably it should be promoted to
co-primary status (e.g. evaluating the signal only once every `h` minutes,
or at some other fixed, non-overlapping cadence, as the main specification,
with the continuous/overlapping version demoted to a robustness check,
rather than the reverse). **This is a human decision, not resolved here.**

**Placebo bootstrap**: the day-level block-bootstrap structure and the
already-resolved per-real-day-shared pairing convention (Section 16e)
both remain appropriate, and arguably become *cleaner* to reason about
-- there is no longer any cross-sectional (follower-level) dependence to
separately account for within a day, since the response itself is now a
single portfolio-level series, matching `S_leader(t)`'s own one-value-per-day-minute
structure exactly. **The numerical result of the existing Section 17
pilot (`SE_boot = 0.0347`, computed on a diagnostic proxy signal paired
against the OLD per-follower response) does not transfer to this new
response and must be re-run from scratch** -- this is new required work,
not assumed or estimated here.

---

## 8. Adapting the selection null to the portfolio-level response

The existing Section 16b mechanics (B1 per-month redraw, B2 fixed
selection rule, both drawn from a candidate pool disjoint from the true
leader tier, both now incorporating the Issue-2 group-exclusion fix)
**carry over with no structural change**, because the selection null's
randomization only ever touched the **leader side** (which names count
as "leader"), never the follower side. "Preserve the actual follower
portfolio" (the redesign's step 1 requirement) now means: hold the real
`Y(t,h)`, `R_follower(t)`, and `X(t)` series -- computed once, from the
true, full follower tier -- fixed and identical across every repetition.
For each repetition, compute `S_leader_random,r(t)` (B1 or B2, with the
Issue-2 fix) exactly as already specified, refit `Y(t,h) = alpha +
beta*S_leader_random,r(t) + gamma*R_follower(t) + delta.X(t) + epsilon`
holding the real follower-side series fixed, collect `beta_random,r`,
compare percentiles as before. **No new design flaw is introduced by
this adaptation** -- it inherits whichever properties the corrected
Section 8/9 leader-signal construction already has, and the response
side (now non-degenerate, per Section 1 above) has no analog of the
old demeaning-induced concern either.

---

## 9. Is the 20bps economic threshold still meaningful?

**Yes, and arguably more cleanly than before**, with one framing
clarification needed. Previously the threshold compared an
*individual-follower* abnormal-return magnitude against a *portfolio-level*
trading-cost figure -- a structural mismatch in units. Now both sides are
portfolio-level: the model-implied change in the follower **portfolio's**
own forward return, at `+/-1` observed sigma of the real `S_leader(t)`,
compared against the 20bps round-trip floor.

**One nuance to state explicitly, not silently assumed**: 20bps is a
**per-position** round-trip cost (the cost of trading one name). Trading
on this signal in practice would mean trading a **basket** of follower
names simultaneously (or some subset of them), not one portfolio-instrument
-- so the 20bps floor should be understood, and stated, as "the per-leg
cost each individual position in a basket implementation of this signal
would need to clear," not literally "the cost of trading the aggregate
portfolio as if it were a single instrument." This distinction matters
for any future Phase 7 trading simulation (which would need its own,
separately preregistered basket-execution cost model) but does not
change how the measurement-study threshold itself should be applied.

---

## 10. Changes required to power analysis and trial ledger

**Power analysis**: the existing Section 17 pilot numbers do not apply
and must be treated as fully superseded, not adjusted, for this
estimand -- both because the response's statistical properties are
different (a portfolio-level raw return likely has materially smaller
idiosyncratic variance than an individual follower's abnormal return,
since cross-sectional averaging over `~160` names typically reduces
idiosyncratic noise by a factor on the order of `1/sqrt(160)` relative
to a single name's own return variance -- **UNMEASURED**, stated here as
a plausible direction, not a number to rely on) and because the
dependence structure changes (Section 7 above). **A fresh day-clustered
placebo-bootstrap pilot, on the actual `Y(t,h)`/`R_follower(t)`/`S_leader(t)`
series, is required before any MDE or power claim can be made** -- this
proposal does not attempt that computation, consistent with the
instruction not to run outcome analysis.

**Trial ledger**: switching the dependent-variable construction from
per-follower abnormal return to portfolio-level raw return is a
**materially different configuration** from anything currently in
`lead_lag/trial_ledger.json` (whose six entries cover grouping mechanism
and horizon choice, under the prior response specification). Per the
ledger's own enforcement design (`lead_lag/ledger.py`,
`assert_registered`), this would need its **own new `config_key`** (e.g.
`estimand:portfolio_level_response`) added to the ledger, with its own
entry, **before** any gate is run under it. **This proposal does not add
that entry** -- per the explicit instruction to stop before modifying the
trial ledger. Note for the eventual decision: this is an additional,
orthogonal axis (estimand choice) alongside the existing grouping/horizon
axes, not a replacement of the existing six entries; adopting it grows
the family's eventual Bonferroni denominator by at least one.

---

## Issue 2 (accepted correction): consequences and comparability, portfolio-level context

The group-exclusion correction (exclude the entire drawn pseudo-leader
set, not one entity at a time, from that repetition's benchmark) is
**orthogonal to, and unaffected by, the Issue-1 portfolio-level
redesign** -- it operates entirely inside the null's own leader-signal
construction (`S_leader_random,r(t)`), which is architecturally unchanged
by switching the response from per-follower to portfolio-level. No new
interaction effect exists between the two fixes; they can be adopted
independently or together with no cross-contamination.

**Consequences, quantified** (unchanged from the prior review, restated
for completeness): excluding the `n_leaders` (~40) drawn pseudo-leaders
from the ~160-name real follower tier leaves a ~120-name "remaining
followers" benchmark pool for the null, versus the real signal's full,
undiminished 160-name pool -- a noise inflation factor of
`sqrt(160/120) ~= 1.15`, i.e. the null's benchmark carries about 15%
more idiosyncratic averaging noise than the real signal's benchmark.
This is **one mechanism, not two**: the "repetition-varying benchmark
composition" is not an independent second noise source layered on top --
it is the direct, deterministic consequence of the same single random
pseudo-leader draw that also determines the signal side, restated. Both
observations describe the same ~15% effect from different angles, not
compounding noise sources.

**Direction of bias**: conservative (widens the null's distribution
slightly, raising the 95th-percentile threshold the real beta must
clear) -- the safer direction for a gate to err in, consistent with the
prior review's finding.

**Structural comparability, confirmed**: both the real signal and the
corrected null signal are, after the fix, the *same shape* of
construction -- "one group's portfolio return minus a fully disjoint
group's portfolio return, same window, same procedure" -- differing only
in (a) which specific names populate each side, and (b) the ~15%
benchmark-noise difference above. **This size mismatch cannot be
eliminated without changing what the null tests**: any way of keeping
the benchmark pool at a full ~160 names would require either drawing
pseudo-leaders from outside the follower tier (defeating the null's
purpose, which specifically asks "would a similarly-liquid but
not-the-literal-top-tier group show similar power") or leaving the
pseudo-leaders inside their own benchmark (the original Issue-2 flaw).
**The ~15% noise gap should therefore be accepted as a known, quantified,
conservative-leaning, and inherent property of this null design -- not a
remaining defect requiring a further fix.**

---

## Summary table: unresolved human decisions

| # | Decision | Where |
|---|---|---|
| 1 | Add year/quarter fixed effects to `X(t)` to guard against slow cross-year drift? | Section 2 |
| 2 | Report the equivalent `{L(t), R_follower(t)}` parameterization alongside `{S_leader(t), R_follower(t)}`? | Section 3 |
| 3 | Final frozen control list for `X(t)` from the defensible candidates listed | Section 4 |
| 4 | No independent market control (5a) vs. an explicitly-labeled coarse daily-NIFTY regime control (5b) | Section 5 |
| 5 | Commission a follower-tier breadth distribution check before freezing a per-minute follower-breadth floor (value TBD, not 0.80 by default) | Section 6 |
| 6 | Promote the non-overlapping-sample specification to co-primary (vs. continuous/overlapping as primary with non-overlapping as robustness only) | Section 7 |
| 7 | Commission a fresh day-clustered placebo-bootstrap pilot on the real `Y(t,h)`/`R_follower(t)`/`S_leader(t)` series before any MDE/power claim | Sections 7, 10 |
| 8 | Add a new `estimand:portfolio_level_response` trial-ledger entry if this specification is adopted | Section 10 |

**Nothing above has been chosen. `PREREGISTRATION_LEAD_LAG_V1.md` (commit
`9f71b65`) and `lead_lag/trial_ledger.json` remain unmodified. This
document itself is uncommitted, pending the decisions above.**
