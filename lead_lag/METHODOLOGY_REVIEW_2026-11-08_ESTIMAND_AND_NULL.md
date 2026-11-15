# Methodology review: dependent-variable estimand and selection-null contamination

**Status: DRAFT, NOT COMMITTED.** This document is a read-only algebraic
review of `PREREGISTRATION_LEAD_LAG_V1.md` as amended (commit `9f71b65`).
No file has been modified. No code was written or run. No regression was
fit, no outcome data was inspected. **This review ends with items
requiring human decisions; nothing here should be read as an amendment
already made.** Per instruction, nothing is committed until those
decisions are made and the appropriate follow-up is explicitly requested.

---

## Issue 1: the dependent variable's own construction removes the thing Section 1 asks about

### 1. Exact mathematical identity

Section 9 defines, for follower `j` at minute `k`, over that month's
complete follower tier of `N` entities:

```
B_follower_LOO(j,k) = (1/(N-1)) * sum_{j' != j} r(j',k)
AR_follower(j,k)     = r(j,k) - B_follower_LOO(j,k)
```

Let `T(k) = sum_{j=1}^{N} r(j,k)` (the total return across the complete
follower tier at minute `k`) and `mean(k) = T(k)/N`.

```
B_follower_LOO(j,k) = (T(k) - r(j,k)) / (N-1)

AR_follower(j,k) = r(j,k) - (T(k) - r(j,k))/(N-1)
                 = [r(j,k)*(N-1) - T(k) + r(j,k)] / (N-1)
                 = [N*r(j,k) - T(k)] / (N-1)
                 = N/(N-1) * (r(j,k) - mean(k))
```

So `AR_follower(j,k)` is exactly a rescaled deviation of `j`'s own return
from the complete follower tier's own cross-sectional mean at that
instant -- the same algebraic shape as the identity that made the
original Section 8 leader signal degenerate.

Summing over the **complete** follower cross-section:

```
sum_{j=1}^{N} AR_follower(j,k) = N/(N-1) * sum_j (r(j,k) - mean(k))
                                = N/(N-1) * (T(k) - N*mean(k))
                                = N/(N-1) * (T(k) - T(k))
                                = 0   -- exactly, for any k, always.
```

**Yes: the sum (equivalently, the cross-sectional mean) of
`AR_follower(j,k)` over the complete follower tier is identically zero,
at every single minute, by construction.** This is not a data property;
it is the same zero-sum identity that caused the original Section 8
degeneracy, now sitting in the dependent variable instead of the
predictor.

### 2. What the current regression can and cannot measure

This matters because `S_leader(t)` (Section 2, Section 8) is **the same
number for every follower row sharing a given (day, minute)** -- it does
not vary across `j`. A regressor that is constant across the
cross-section at a given time can only ever explain the **between-time**
variation in whatever the response's **cross-sectional average** does at
that time. But Part 1's identity says that average is forced to
(approximately) zero at every single evaluation time, for the complete
follower tier.

Concretely: for a pooled OLS over `(j, t)` with a regressor `S_leader(t)`
constant in `j`,

```
Cov(S_leader(t), AR_follower(j, t+h))
  = E_t[ Cov_j(S_leader(t), AR_follower(j,t+h) | t) ]        -- = 0, since S_leader(t) has no within-t variation across j
  + Cov_t( S_leader(t), E_j[AR_follower(j,t+h) | t] )        -- E_j[...|t] ~ 0, by Part 1's identity (complete cross-section)
  ~ 0
```

**Under a perfectly balanced panel (every follower present at every
signal-minute and at every forward-horizon minute), the pooled
regression's `beta` is analytically forced toward zero, independent of
whether a genuine aggregate propagation effect exists or not.** This is
not a power problem (more data does not fix it) and not something
Section 11's controls can repair: every control in Section 11 (own
trailing return, `B_follower_LOO` over the signal window, time-of-day,
own trailing volatility, own turnover rank) is **follower-specific**, not
a day/minute-level aggregate factor. Partialling out follower-specific
controls (Frisch-Waugh-Lovell) cannot resurrect a common/aggregate
component that was removed from the response **before any regression is
run**, as a property of the data construction itself -- this is prior to
and independent of model specification.

In practice the panel is **not** perfectly balanced -- missing bars, the
`>=3`-minute gap exclusion, the per-minute leader-breadth floor (Section
8; a parallel floor does not yet exist for followers), and
horizon-crossing-close exclusions will all cause different followers to
be present on different days/minutes. This does **not** rescue the
regression; it changes the failure mode. With partial imbalance, the
observed cross-sectional average of `AR_follower(j,t+h)` over the
**surviving subsample** at a given `t+h` is no longer exactly zero (only
the complete-tier average is exactly zero), so `beta` can come out
numerically nonzero -- but that nonzero value is now driven by **whatever
determines which followers happen to be missing on which days**, not by
genuine propagation. If missingness correlates with anything that also
correlates with `S_leader(t)` (e.g., less-liquid followers are both more
likely to have a stale/missing bar and more likely to be active on
higher-volatility days, which are also the days leaders move most), the
regression would report a confound as a finding.

**Per the task's explicit instruction: a nonzero, even statistically
significant, `beta` under the current specification does not resolve
this.** It would need to be independently diagnosed as either (a) a
genuine composition-imbalance artifact, or (b) evidence of something
else entirely (cross-sectional heterogeneity, Section 1.5 below) --
never taken at face value as "aggregate follower catch-up."

### 3. Does this match Section 1's research question?

**No.** Section 1 (as amended) asks whether the follower **tier**
exhibits predictable subsequent movement following a leader-tier
abnormal move -- an aggregate, portfolio-level question ("do followers
collectively catch up"). The current `AR_follower` construction
structurally removes almost exactly the aggregate/common component that
question is about, leaving (at best, under imbalance) a noisy
cross-sectional "who outperforms whom within the follower tier" signal --
a different, narrower question Section 1 does not ask and Section 2 does
not claim to be testing.

### 4. Alternative estimands that would genuinely measure portfolio-level propagation

Presented as options, not a chosen fix -- **this requires a human
decision** (see "Items requiring human decisions" below).

**Option A -- portfolio-level response (collapse the follower side, symmetric with the Section 8 fix on the leader side).**
Replace the per-follower response with the follower **portfolio's** own
aggregate forward return, benchmarked externally (not leave-one-out
against itself):
```
AR_follower_portfolio(t -> t+h) = mean_j( r(j, t->t+h) ) - [external benchmark, e.g. none, or a day-level control]
```
One row per (day, signal-minute), not per (follower, day, minute). This
directly tests the aggregate hypothesis Section 1 states.
*Tradeoff*: the regression's row count shrinks enormously (by a factor of
~160-309, the follower-tier size) -- **but** this may cost little real
statistical power, because Section 14's day-clustered inference already
treated within-day replication across followers as non-independent; the
effective sample size was always meant to be bounded by the number of
independent trading days (~2,468), not the raw row count. This needs to
be checked explicitly (re-run the Section 17 power pilot on this
estimand), not assumed either way.

**Option B -- keep per-follower rows, but stop demeaning the response via leave-one-out.**
Use follower `j`'s **raw** (non-abnormal) forward return as the response,
and move the common-factor control to the right-hand side explicitly
(e.g., include the full-universe or follower-pool's own contemporaneous
forward return as a control, rather than subtracting it from the
dependent variable):
```
r(j, t->t+h) = alpha + beta * S_leader(t) + gamma_1 * B_follower_pool(t->t+h) + gamma_2 . X(j,t) + epsilon
```
This keeps the larger per-follower-row sample, and lets a genuine
aggregate effect show up as `beta` on `S_leader(t)` without being
pre-subtracted out of the left-hand side. *Tradeoff*: `B_follower_pool(t->t+h)`
is itself partly a function of every follower's own forward return
(mild endogeneity, analogous to -- though smaller than -- the Issue 2
contamination below); needs its own leave-one-out treatment per follower
to avoid reintroducing a related artifact.

**Option C -- run both, explicitly labeled as different hypotheses.**
Option A (or B) as the **primary** test, matching Section 1 literally;
the current per-follower LOO-demeaned specification kept as an explicitly
**secondary, differently-named** test of cross-sectional heterogeneity
within the follower tier (Section 1.5 below) -- not a replacement for the
primary test, and would need its own trial-ledger entry (`lead_lag/trial_ledger.json`)
if run, since it is a materially different configuration from what is
currently registered.

### 5. Would an individual-follower outperformance hypothesis need a different signal or model?

**Yes, if that is actually the question of interest.** The current
`AR_follower` construction (LOO-demeaned) is *appropriate* for a
cross-sectional "which followers outperform their peers" hypothesis --
that is exactly what leave-one-out demeaning is designed to isolate. But
`S_leader(t)`, being identical for every follower at a given (day,
minute), **cannot explain why one follower would outperform another on
the same day** -- it has zero within-day, cross-follower variation, so it
carries no information about *which* follower should do better. A
genuine cross-sectional-heterogeneity model would need a
**follower-specific** predictor -- e.g. `S_leader(t) * (follower j's own
historical correlation/beta to the leader tier)`, or some other
interaction term that varies by `j` -- not a straight re-use of the
current pooled regression. This is a structurally distinct research
design from both Option A/B above and from the current specification;
it is not a small tweak.

**This review does not choose between Options A, B, C, or the
heterogeneity redesign. See "Items requiring human decisions" below.**

---

## Issue 2: selection-null benchmark self-inclusion (mechanical, demonstrated, moderate severity)

### 1. Demonstration

Section 16b draws pseudo-leaders from ranks `n_leaders+1` through
`3*n_leaders` (e.g. ranks 41-120 when `n_leaders=40`). The real follower
tier spans ranks `n_leaders+1` through approximately `5*n_leaders`
(ranks 41-200, since `n_leaders=40`, `n_followers~=160`, `40+160=200`).
**The entire pseudo-leader candidate pool (ranks 41-120) is a strict
subset of the real follower tier (ranks 41-200).**

Section 16b step 4 (per the committed amendment, `9f71b65`) reuses "the
exact Section 8 signal-construction procedure, unchanged -- same...
`B_follower_pool(k)` benchmark." `B_follower_pool(k)` is defined (Section
9) as the plain equal-weighted mean over **all** of that month's real
followers -- it was never made aware that a null repetition has
designated some of those same real followers as "pseudo-leaders" for that
draw.

So for a pseudo-leader `i` (a real follower, say rank 55, drawn into the
null's random portfolio this repetition):

```
AR_leader_random(i,k) = r(i,k) - B_follower_pool(k)
B_follower_pool(k)     = (1/n_F) * sum_{j in REAL follower tier} r(j,k)
                       = (1/n_F) * ( r(i,k) + sum_{j in REAL follower tier, j != i} r(j,k) )
```

Entity `i`'s own return `r(i,k)` appears **on both sides** of its own
"abnormal" return: once directly, and once again, diluted by weight
`1/n_F`, inside its own benchmark. This is mechanical self-inclusion --
**yes, it creates a real, demonstrable contamination**, though (unlike
Issue 1 or the original Section 8 bug) it is a **dilution**, not an exact
zero-sum identity. Expanding:

```
AR_leader_random(i,k) = r(i,k)*(1 - 1/n_F) - (1/n_F)*sum_{j in followers, j!=i} r(j,k)
                       = ((n_F-1)/n_F) * [ r(i,k) - (1/(n_F-1))*sum_{j!=i} r(j,k) ]
                       = ((n_F-1)/n_F) * AR_leader_random_CORRECTED(i,k)
```

i.e., the contaminated version is exactly a **shrunk** copy of what a
properly-excluded (leave-the-pseudo-group-out) construction would give,
scaled by `(n_F-1)/n_F` -- for `n_F ~= 160`, a shrinkage of about
`159/160 ~= 0.994`, roughly 0.6%. Small in raw magnitude, but **real,
systematic, and asymmetric**: the real signal's leader-side benchmark
(Section 8, post-fix) has **zero** overlap with the leaders themselves
(true leaders, ranks 1-40, are never inside the follower-pool benchmark,
ranks 41-200) -- so the real signal has no analogous contamination at
all. The null is therefore not a clean structural analog of the real
signal; it is a slightly different (self-diluted) construction being
compared against a clean one.

### 2. Proposed corrected benchmark

Exclude the **entire drawn pseudo-leader set** (not just one entity at a
time) from the benchmark average for that repetition and month:

```
B_follower_pool_minus_pseudo(k) = (1/(n_F - n_leaders)) * sum_{j in REAL follower tier, j NOT in this repetition's pseudo-leader draw} r(j,k)

AR_leader_random(i,k) = r(i,k) - B_follower_pool_minus_pseudo(k)   [for i in the drawn pseudo-leader set]
```

This recreates, for the null, the same **disjoint three-way split** the
real signal already has (true leaders / true followers), just applied to
a different partition: pseudo-leaders (drawn from ranks 41-120) vs.
**remaining followers** (the real follower tier minus whichever names
were drawn as pseudo-leaders this repetition -- a pool of `n_F - n_leaders`
names, e.g. ~120 when `n_F=160, n_leaders=40`).

### 3. Does the corrected null remain comparable to the real signal?

**Yes -- more so than before.** The corrected construction is the same
*shape* as the real signal (leader-like group return minus a fully
disjoint follower-like group return, both cumulated over the same
5-minute window), just with a randomly-drawn, liquidity-matched
substitute for "leader." This improves comparability relative to the
contaminated version, not just removes a flaw.

### 4. B1 and B2 under the corrected construction

Both already operate month-by-month (B1 redraws every month; B2 applies
a fixed rank-position rule to each month's actual roster), so recomputing
`B_follower_pool_minus_pseudo(k)` per month per repetition is a direct
extension of logic both variants already need, not new machinery:

- **B1**: for each repetition and each month, after drawing that month's
  `n_leaders` pseudo-leaders from ranks 41-120, define that month's
  `B_follower_pool_minus_pseudo(k)` as the mean over that month's real
  follower tier minus those specific drawn names.
- **B2**: for each repetition, the fixed rank-position rule selects
  different actual entities each month (as rosters shift) -- the
  benchmark exclusion must be recomputed each month to match whichever
  entities the fixed rank-positions resolve to that month, analogous to
  how B2 already recomputes entity identities monthly.

Both variants need this fix; neither is structurally harder to apply it
to.

### 5. New biases introduced by the correction

Two second-order effects, both worth naming, neither severe:

1. **Smaller benchmark pool, more benchmark noise.** The real signal's
   `B_follower_pool` averages over the full ~160 real followers
   (undiminished, since leaders are never part of that pool). The
   corrected null's `B_follower_pool_minus_pseudo` averages over only
   `n_F - n_leaders ~= 120` names (160 minus the 40 drawn pseudo-leaders)
   -- a smaller pool, hence a noisier benchmark mean (roughly
   `sqrt(160/120) ~= 1.15x` more idiosyncratic noise in the benchmark
   average, by standard averaging arithmetic). This could make the
   null's `beta_random` distribution somewhat wider than a perfectly
   matched comparison would produce -- biasing the null **conservative**
   (harder for the real beta to clear the resulting, slightly inflated,
   95th-percentile threshold), the opposite direction from Issue 2's own
   uncorrected bias. Not large (fixed name counts, ~15% noise inflation
   in one input), but should be reported alongside any null result, not
   silently absorbed.
2. **Benchmark composition varies repetition-to-repetition.** The real
   signal's follower-pool benchmark composition is fixed for a given
   month (deterministic). The null's "remaining followers" benchmark
   composition changes depending on which names got drawn as
   pseudo-leaders that repetition -- an additional source of
   repetition-to-repetition noise that has no counterpart in the real
   signal's construction. Same direction of effect as (1): likely widens
   the null's spread somewhat, biasing conservative rather than
   anti-conservative.

Neither new bias resembles Issue 1's structural nullification or the
original candidate-pool-overlap/redraw-narrowing biases already fixed in
`9f71b65` -- both are modest-magnitude, explainable, and point toward
making the null *harder* to pass, not easier, which is a safer direction
for a gate to err in than the reverse.

---

## Severity ranking

| # | Issue | Severity | Why |
|---|---|---|---|
| 1 | Dependent-variable estimand mismatch (Section 9/2) | **CRITICAL -- blocking** | Same root mechanism class as the original Section 8 degeneracy (leave-one-out-demean-then-aggregate), now on the response side of the pooled regression. Under a balanced panel, `beta` is analytically forced toward zero regardless of true effect; under a realistic imbalanced panel, a nonzero `beta` is confounded with missingness patterns rather than measuring the stated hypothesis. The Section 8 fix (committed in `9f71b65`) did **not** address this -- it fixed the predictor, not the response. **This should be resolved before any Phase 4 primary-gate regression is run**, independent of and in addition to the already-committed Section 8 fix. |
| 2 | Selection-null benchmark self-inclusion (Section 16b) | **MODERATE -- should fix, not independently blocking** | Real, demonstrated, systematic (~0.6% shrinkage plus asymmetric comparability with the real signal), but a dilution, not a zero-sum identity -- the null remains directionally informative even uncorrected, just not as clean a comparison as it should be. Should be fixed as part of whatever revision addresses Issue 1, so Phase 4 does not need two separate correction passes to Section 16b. |

Issue 1 is more severe than Issue 2 by a wide margin: Issue 2 shrinks a
quantity by under 1%; Issue 1 can zero out, or confound, the primary
estimand's own signal entirely.

---

## Items requiring human decisions (nothing below has been chosen)

1. **Which alternative estimand (Option A, B, C, or the heterogeneity
   redesign) should replace or supplement the current Section 2/9
   specification?** Each has different power, implementation cost, and
   fidelity to Section 1's literal question -- see Issue 1.4. This review
   takes no position.
2. **If Option C (run both) is chosen**: does the current per-follower
   specification get kept as a secondary/exploratory test, and if so,
   under what name and with what trial-ledger entry?
3. **Should the Issue 2 benchmark-exclusion fix be applied now, as part
   of whatever amendment addresses Issue 1** (since both touch Section
   16b/9), **or tracked separately?**
4. **If Option A (portfolio-level response) is adopted**: the Section 17
   power pilot (day-clustered placebo bootstrap) would need to be
   re-run on that estimand specifically -- its current numbers (computed
   on the per-follower specification) would not transfer. This is
   additional work this review does not schedule or authorize.
5. Does resolving Issue 1 require re-opening Section 11's control set
   (e.g., Option B's need for a leave-one-out treatment of its own
   `B_follower_pool(t->t+h)` control)? Not resolved here.

**No amendment has been made. No commit has been created. The
preregistration at commit `9f71b65` is unchanged.** This document itself
is also uncommitted, pending the decisions above.
