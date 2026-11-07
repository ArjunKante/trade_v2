# Cross-Liquidity-Tier Return Propagation in NSE Equities, Study V1

## Provenance

**This is a brand-new research family. No prior trial exists in this
project under this name.** Phase 0 (`lead_lag/LEAD_LAG_RECONNAISSANCE.md`),
Phase 1 (`lead_lag/DATA_AUDIT_LEAD_LAG.md`), and Phase 2
(`lead_lag/LEAD_LAG_FEASIBILITY.md`) preceded the original version of this
document (committed alone, commit `e1418a661a769c9f134d750bbe95dc1a831b0305`,
2026-11-07), all read-only against the existing warehouse, no strategy
code written before that commit.

**Two binding scope decisions were made by the human user before the
original version was drafted:**

1. **Intraday scope is capped at the existing `data/fibo_intraday.duckdb`
   universe** -- 386 distinct entities, 2016-10-04 to 2026-09-18. No new
   Angel One fetch.
2. **Grouping is liquidity-tier-based, not sector-based.** `DATA_AUDIT_LEAD_LAG.md`
   found no point-in-time sectoral index series and no point-in-time
   sector/industry classification anywhere in this repository (the same
   defect shape as the already-documented Bug #12).

---

## AMENDMENT LOG (2026-11-08) -- read this before the rest of the document

This document was amended once, following an independent methodology
review of the original (`e1418a66`) version. **The amendment process
itself surfaced a more serious problem than the one the review set out to
check** -- recorded here first, in order of actual severity, not in the
order the review happened to ask about it.

### 1. CRITICAL, newly discovered during this amendment (not by the original review): the original Section 8/9 `S_leader(t)` was algebraically degenerate

While building the real data needed to answer the review's power-calculation
question, `lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Section 3.0
found that the original signal construction --
`AR_leader(i,k) = r(i,k) - B_leader(k)` where `B_leader(k)` excluded only
`i` from the **same leader group**, then `S_leader(t) = mean_i(S_i(t))`
averaged back across that **same leader group** -- is **identically zero
by construction**, for any data, always: a leave-one-out deviation from a
group's own mean, averaged back across that same group, telescopes to
exactly zero (the same identity that makes OLS residuals against a
constant sum to zero). Measured directly on real data: mean `-1.8e-21`,
sigma `4.2e-20` -- machine-epsilon noise, 16+ orders of magnitude below one
basis point, across 230 real trading days. This was never caught in
Phase 2 (`LEAD_LAG_FEASIBILITY.md`'s own MDE calculation used only the
**follower-side** forward-return sigma, never `S_leader(t)`'s own) or in
the original preregistration (Section 18 explicitly deferred computing
`S_leader`'s sigma to Phase 6 -- nobody had actually computed it before
this amendment).

**Fix adopted in this amendment**: Section 8/9 are rewritten so the
leader side is benchmarked against the **follower pool**, not against
other leaders. `AR_leader(i,k) = r(i,k) - B_follower_pool(k)`, where
`B_follower_pool(k)` is the plain equal-weighted mean return across that
month's **entire follower tier** (no leave-one-out needed here, since a
leader is never a member of the follower pool -- there is no
self-contamination risk to guard against on this side). This makes
`S_leader(t)` resolve to (a rescaling of) the cumulative 5-minute return
**spread between the leader portfolio and the follower portfolio** --
algebraically guaranteed non-degenerate (verified below, Section 8), and
arguably a more literal operationalization of the hypothesis ("leaders
moved and followers have not yet caught up") than the original
construction was.

### 2. Selection null redesigned (`matched random-leader-portfolio null` replaces the follower-permutation null)

The independent review found the original Section 16b (random follower
reassignment) was likely a **near no-op**: `S_leader(t)` is not
follower-specific, so permuting which follower label attaches to a given
row does not change the set of (signal, response) pairs the regression
actually sees. Replaced with a null that varies the thing that actually
matters -- which stocks constitute "leader" -- see Section 16b below.

### 3. MDE/power (Section 17) rewritten; no unconditional PASS re-claimed

The original MDE (1.4-4.2 bps) was computed from raw individual-stock
1-minute-bar variance and a naive day-count, not from the actual
dependence structure of the regression coefficient the estimand uses.
Combined with finding #1 above (the predictor itself didn't exist as
specified), **no version of this document before today's amendment had a
working power calculation at all.** Section 17 is rewritten to report
real, computed numbers where they exist and state plainly where they do
not. **This amendment does not claim a renewed feasibility PASS.** The
breadth correction (real ~40 leaders / ~160 followers per month,
replacing the stale 77/309 lifetime-turnover proxy) and the per-minute
breadth floor are solid, adopted outright. The dependence-aware SE/power
question is reported as **conditional and provisional**, pending a
Phase 4 re-run of the placebo diagnostic on the corrected signal from
fix #1 -- see Section 17.

### 4. Trial ledger made machine-enforced

`lead_lag/trial_ledger.json` + `lead_lag/ledger.py` (7 passing tests,
`lead_lag/test_ledger.py`) now hold the family's 6 registered trials as a
computed fact (`len(trials)`), not a hand-typed number in prose. Phase 4
code is required to call `ledger.assert_registered(config_key)` before
any gate and `ledger.record_gate_run(...)` after -- see Section 15.

### 5. Hypothesis reframed; title changed

Renamed to **"Cross-Liquidity-Tier Return Propagation in NSE Equities"**.
The original title and Section 1 text ("cross-stock lead-lag
propagation... information diffusion") overclaimed what a sector-agnostic,
liquidity-tier-only design can actually test -- see Section 1.

### 6. Monthly tier breadth computed from the real construction; per-minute breadth floor added

`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Tasks 1-2 computed the
actual Section 6 construction (not Phase 2's lifetime-turnover proxy) --
see Section 6 and Section 8.

### 7. Free parameters consolidated and frozen

See Section 23 (new).

### 8. Master spec committed

`lead_lag/MASTER_SPEC_LEAD_LAG.md` now holds the governing research
directive verbatim, with provenance. "Part X.Y" citations throughout this
document now resolve to a real, committed file.

### 9. Second pass: adversarial re-review of this amendment's own first draft found and fixed two further issues

Per the user's explicit procedure, this amendment's Section 16b and
Section 17 were sent to a fresh adversarial reviewer before commit. Two
concrete problems were found in the first draft and are fixed in the
version below, not merely caveated: (a) Section 16b's candidate pool
(top `2*n_leaders` by turnover) overlapped the true leader tier by ~50%
on average (a hypergeometric-draw consequence never checked in the first
draft), biasing the null conservative, while independently redrawing a
fresh random portfolio every month within a repetition narrowed the
null's spread, biasing it anti-conservative in the opposite direction --
fixed by making the candidate pool disjoint from the true tier and
requiring both a per-month-redraw (B1) and a fixed-selection-rule (B2)
variant to independently pass; (b) Section 17's Bonferroni MDE multiplier
was arithmetically wrong (3.1909, inherited uncorrected from the
supporting pilot document; the correct value is 3.47988), and Section
21's "comfortably below the economic floor" language was left as the one
undefined, outcome-adjacent judgment call in an otherwise strictly frozen
document -- both corrected, with a specific numeric margin rule (>=5x
proceed, 1-5x stop for guidance, <1x abandon) frozen into Section 23
before any real Phase 4 number exists.

**What this amendment does NOT do**: it does not run Phase 4. It does not
run any outcome analysis (no regression anywhere in the supporting
documents pairs a leader signal with a contemporaneous follower response
for the real, corrected signal -- the degeneracy check and the placebo
pilot are diagnostic only, per `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`'s
own explicit scope boundary). It does not claim the hypothesis has
passed, is well-powered beyond what is stated, or is ready for
implementation without the remaining open items below being resolved.
**Phase 4 still requires the user's explicit approval, after this
amendment itself is reviewed.**

This amendment is committed as a **new commit**, not an amendment to or
replacement of commit `e1418a66` -- that commit remains in git history
unchanged, per the requirement to preserve original provenance.

---

## Section 0: reuse boundaries, read-only

Unchanged from the original version. No existing strategy file is
touched. See the original Section 0 reuse list (`entity_panel`,
`isin_lineage`, `corporate_actions`, `adjustment`, `fibo.universe`,
`fibo.intraday_db`, `factors.target`, `factors.ic_eval`,
`box_theory.inference.day_clustered_bootstrap`, `data_layer.holdout`),
plus, new in this amendment: `lead_lag/ledger.py` (trial-ledger
enforcement, governance tooling, not strategy logic) and
`lead_lag/MASTER_SPEC_LEAD_LAG.md` (reference document). No existing
family's module is modified anywhere in this amendment.

---

## Section 1: research hypothesis (REFRAMED)

**Original framing (overclaimed)**: "cross-stock lead-lag propagation...
information diffusion, common-factor transmission, or asynchronous
repricing across related securities."

**Corrected framing**: within the existing point-in-time
top-200-by-turnover universe, do abnormal 5-minute cumulative return
spreads between the most liquid stocks ("leaders," top ~20% by trailing
turnover) and the least liquid stocks ("followers," remaining ~80%)
predict the followers' subsequent abnormal returns, over a fixed forward
horizon, after controlling for the followers' own recent momentum and
contemporaneous follower-pool co-movement?

**This design, as specified, cannot distinguish between at least four
candidate mechanisms, and does not claim to**:

1. **Genuine delayed repricing** -- leaders possess or process
   firm-specific or market-wide information faster, and that information
   genuinely propagates to followers with a lag (the mechanism implied by
   the original "information diffusion" framing).
2. **Common market-factor reactions at different speeds** -- both tiers
   are reacting to the same observable or unobservable shock, with
   liquid names simply repricing faster because they trade more
   frequently, with no information flowing from specific leaders to
   specific followers at all.
3. **Non-synchronous trading** -- a classical market-microstructure
   effect (Lo-MacKinlay-style): illiquid names trade and update prices
   less frequently by construction, so their *observed* returns
   mechanically lag liquid names' *observed* returns, even when the
   *true* (unobserved, continuously-updating) prices of both groups move
   together with no lag at all.
4. **Stale-price effects** -- a related but distinct artifact of
   infrequent trading in the follower tier producing bars whose closing
   price has not been refreshed by a recent trade, independent of any
   genuine predictive relationship.

**OHLCV data alone cannot conclusively distinguish these four
mechanisms.** Doing so would require order-book-level data, trade-by-trade
timestamps, or an identified natural experiment -- none of which this
project has. The market-factor null (Section 16c) and the reverse-direction
diagnostic (Section 16d) narrow the space of plausible explanations but do
not resolve it; this is stated here explicitly so a PASS verdict (Section
20) is never read as having isolated mechanism (1) specifically. A PASS
means "a liquidity-tiered return-propagation pattern exists and survives
the stated controls and nulls" -- not "information diffuses between
specific leader and follower companies."

This is a **measurement** question, not a trading-strategy proposal. A
statistically detectable coefficient does not by itself authorize a
trading simulation -- see Section 20.

---

## Section 2: primary estimand

Unchanged in form from the original version; the error term's dependence
structure and the predictor's own construction are both addressed more
carefully below (Sections 8, 9, 17) following the degeneracy fix.

```
AR_follower(j, t -> t+h) = alpha + beta * S_leader(t) + gamma . X(j,t) + epsilon(j,t,h)
```

- `j` indexes a follower-tier entity, `t` indexes a completed 1-minute bar
  (the signal-end minute), `h` is the forward horizon (Section 10).
- One row = one (follower entity j, trading day, signal-minute t)
  observation. `S_leader(t)` is **not** follower-specific -- it is one
  pooled value shared by every follower row at a given (day, minute).
  This is stated explicitly because it is exactly the property that made
  the original Section 16b selection null ineffective (Amendment Log
  item 2) and is load-bearing for the corrected null's design (Section
  16b below).
- `AR_follower(j, t->t+h)` is entity j's forward h-minute abnormal
  (leave-one-out-benchmark-adjusted) return, Section 9.
- `S_leader(t)` is the equal-weighted leader-portfolio signal, Section 8
  (corrected construction).
- `X(j,t)` is the predetermined control vector, Section 11.
- Pooled across all eligible (follower, trading-day, signal-minute)
  observations; inference uses day-clustered standard errors (Section 14).

Reported alongside beta (not a bare p-value): standard error, 95% CI,
implied economic magnitude at +/-1 observed sigma of `S_leader`,
incremental R-squared over the controls-only model, stability across
years and across the liquidity-tier boundary.

---

## Section 3: data sources

Unchanged from the original version. No new data fetch of any kind is
required. No existing fact table is written to. (See the original
Section 3 table: `bars_1min` in `data/fibo_intraday.duckdb`; `prices_eod`
in `data/warehouse.duckdb` via `read_full_entity_panel_authorized`;
`isin_lineage`, `corporate_actions`/`adjustment_factors`;
`fibo.universe.reconstitute_annually`; `index_eod` -- NIFTY50 only, not
used as the intraday benchmark since no intraday index series exists;
sector/industry files -- explicitly not used.)

**Operational note added in this amendment**: `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
found `read_full_entity_panel_authorized(...)` raised a `MemoryError` on
its first call in the environment used for that analysis (succeeded on
retry). Phase 4 implementation should use the lighter direct
`prices_eod` + `isin_lineage` join for turnover-ranking purposes
specifically (turnover is split-invariant, so adjustment factors are not
needed for that one purpose), reserving the full adjusted panel for where
split/bonus-adjusted prices are actually required (return computation on
intraday bars, which uses `bars_1min` directly, not `entity_panel` at
all).

---

## Section 4: universe definition

Unchanged from the original version: `fibo.universe.reconstitute_annually`,
annual top-200-by-turnover, point-in-time, capped to the existing
`fibo_intraday.duckdb` date range (2016-10-04 to 2026-09-18). Known,
inherited survivorship-bias limitation, not re-solved here (see original
Section 4).

---

## Section 5: historical sector grouping

**None. Not used anywhere in this design.** Unchanged from the original
version. See Section 1's reframing above for why this changes what the
study can and cannot claim.

---

## Section 6: leader definition, WITH REAL MONTHLY BREADTH (corrected)

**Construction, unchanged from the original version**: within each
year's point-in-time top-200-by-turnover annual universe (Section 4), on
the first trading day of each calendar month, rank eligible entities by
trailing-60-trading-session median daily rupee turnover (raw, from
`prices_eod`, point-in-time -- no bar after the ranking date is used).
Top 20% of that month's eligible pool = leaders; held fixed for the
month. An entity with fewer than 60 trailing sessions of history as of
the ranking date is excluded from that month's eligible pool.

**Real monthly breadth, computed for the first time in this amendment**
(`LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1, read-only, against the
real construction above -- not Phase 2's lifetime-turnover proxy):

| Year | eligible min/med/max | leaders min/med/max | followers min/med/max |
|---|---|---|---|
| 2016 (stub, Oct-Dec) | 193/194/195 | 39/39/39 | 154/155/156 |
| 2017 | 196/200/200 | 40/40/40 | 156/160/160 |
| 2018 | 198/200/200 | 40/40/40 | 158/160/160 |
| 2019 | 200/200/200 | 40/40/40 | 160/160/160 |
| 2020 | 196/200/200 | 40/40/40 | 156/160/160 |
| 2021 | 194/200/200 | 39/40/40 | 155/160/160 |
| 2022 | 189/200/200 | 38/40/40 | 151/160/160 |
| 2023 | 198/200/200 | 40/40/40 | 158/160/160 |
| 2024 | 189/200/200 | 38/40/40 | 151/160/160 |
| 2025 | 181/200/200 | 37/40/40 | 144/160/160 |
| 2026 (through Sep) | 187/200/200 | 38/40/40 | 149/160/160 |

**Headline correction: the real construction gives ~40 leaders / ~160
followers per month (91 of 120 months, 76%, sit exactly at 40/160), not
the 77/309 lifetime-turnover-proxy figure that appeared in
`LEAD_LAG_FEASIBILITY.md` Section 1a and was carried into this document's
original Section 6 commentary.** The proxy used lifetime total turnover
across all 386 entities ever observed in the full 10-year archive (top
20% of 386 = 77); the real construction ranks within each year's current
~200-name annual universe (top 20% of ~196-200 = ~39-40) -- roughly half
the breadth. This does not change the qualitative feasibility conclusion
(40/160 is still an operationally ample candidate set, zero new
infrastructure required), but 40/160 replaces 77/309 as the number this
family's documents should cite going forward.

**2017-2019 are NOT materially thinner than later years** (contrary to
what the original amendment-planning hypothesis expected, based on a
different, unrelated thinness finding in `LEAD_LAG_FEASIBILITY.md`
Section 1b about a 252-day correlation-window check that does not apply
to this construction). The only recurring pattern is a **post-reconstitution
dip every January-March** (and the three 2016 stub months): new entrants
to that year's top-200 annual universe have not yet accumulated 60
trading sessions of history by the time the Jan/Feb/Mar ranking date
arrives. The pool recovers to the full ~200 by April every year without
exception. Worst month in the full 10-year range: **2025-01, 181
eligible / 37 leaders / 144 followers** -- still an ample sample, no
feasibility concern.

---

## Section 7: follower (laggard) definition

Unchanged from the original version: all entities eligible that month
(Section 4) not in that month's leader tier (Section 6) -- the bottom
~80% by trailing turnover (~160/month, per Section 6's corrected count).
Additional per-observation eligibility filters per Section 12.

---

## Section 8: leader signal construction (CORRECTED -- fixes the degeneracy)

**The original construction in this section was algebraically degenerate
and is replaced below.** See Amendment Log item 1 for the full discovery
and derivation.

For each leader-tier entity `i` and each completed 1-minute bar `k`:

```
B_follower_pool(k)  = equal-weighted mean of r(j,k) over ALL followers j in that month's follower tier
AR_leader(i,k)      = r(i,k) - B_follower_pool(k)
S_i(t)              = sum_{k=t-4}^{t} AR_leader(i,k)      [5-minute trailing cumulative, fixed in real minutes]
S_leader(t)         = (1/n_t) * sum_i S_i(t)              [equal-weighted across leader-tier entities with a valid bar at t, subject to the breadth floor below]
```

**Critical difference from the original**: the leader's own abnormal
return is now benchmarked against the **follower pool**, not against
other leaders. No leave-one-out exclusion is applied on this side,
because a leader is never itself a member of the follower pool -- there
is no self-contamination risk here, unlike the follower side (Section 9),
where a follower IS a member of the group its own benchmark is drawn
from and leave-one-out remains necessary there.

**Why this is non-degenerate (the algebra the original construction
failed)**:

```
S_leader(t) = (1/n_t) * sum_i sum_k [r(i,k) - B_follower_pool(k)]
            = [mean cumulative leader-portfolio return over the window]
              - [cumulative follower-pool return over the same window]
```

This is the cumulative 5-minute **return spread between the leader
portfolio and the follower portfolio** -- two different, non-identical
groups of stocks, so there is no algebraic reason for this quantity to be
zero, and empirically it is not (a diagnostic substitute of this same
form, `mean_leaders - mean_universe`, measured sigma = 3.92 bps over a
~230-day, 11-month pilot sample -- `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
Section 3.1; the exact `mean_leaders - mean_followers` form specified here
has not yet been measured on real data and must be the first thing Phase
4 verifies, per Section 21 below).

Equal weighting, not turnover-weighting, per the original design's
explicit instruction (master spec Part 4.3, now `lead_lag/MASTER_SPEC_LEAD_LAG.md`
Part 4.3 -- "do not choose weights after observing results").

**New: minimum per-minute breadth floor** (`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
Task 2): `S_leader(t)` is **not computed** for a given minute unless
`n_t >= 0.80 * (that month's leader-tier size)`. Evidence: pooled across
an 11-month, 1-per-year sample (86,250 leader-tier minute-observations,
post-open-auction-exclusion per Section 12), the frac-of-tier-present
distribution is 0.825/0.875/0.875/0.95 at the 1st/10th/25th/50th
percentiles -- leader-tier breadth is virtually always complete
(pooled zero-volume-bar fraction across the sample: 3.1e-7). A 0.80
floor excludes only the single genuine outlier minute found in the full
sample (`2020-06-11 14:21:00`, 13/40 = 32.5% breadth) -- roughly 0.001%
of minutes -- while a stricter floor (0.90+) would needlessly discard
~35.7% of minutes that are in fact fine (a handful of leaders missing a
bar by routine, non-systemic chance). This floor is frozen now, per
Section 23, not tuned after Phase 4 output exists.

`S_leader(t)` is only computed, and only usable as a predictor, after bar
`t` has fully closed. Its timestamp convention (bar-start vs bar-end) is
still to be verified empirically in Phase 4 hand-tracing (Section 21)
before any aggregate result is trusted -- unchanged requirement from the
original version.

---

## Section 9: benchmark construction (clarified following the Section 8 fix)

Two distinct follower-pool quantities are now in play, and this amendment
names them separately to avoid the ambiguity that contributed to the
original degeneracy going unnoticed:

```
B_follower_pool(k)     = equal-weighted mean of r(j,k) over ALL followers that month
                         [used ONLY in Section 8's leader-signal construction -- no exclusion, since no leader is ever a follower]

B_follower_LOO(j,k)    = equal-weighted mean of r(j',k) over OTHER followers j' != j, that month
                         [used for follower j's OWN abnormal return AND as a control for follower j -- leave-one-out IS required here, because j is itself a member of the group forming its own benchmark]

AR_follower(j,k)        = r(j,k) - B_follower_LOO(j,k)
```

`B_follower_pool(k)` and `B_follower_LOO(j,k)` differ only by whether `j`
itself is excluded from the average over a ~160-name pool -- numerically
almost indistinguishable for any single `j`, but conceptually distinct
and kept separately labeled, because conflating them is exactly the kind
of "collapse a leave-one-out quantity back into its own group" mistake
that produced Section 8's original degeneracy.

**No leader ever enters any follower's benchmark, in either direction**
-- `B_follower_pool` and `B_follower_LOO` are both built exclusively from
followers. This preserves the original intent behind Part 4.1's
leave-one-out requirement ("a leader's own movement must not mechanically
contaminate the laggard's benchmark") exactly, while fixing the
degeneracy by making the **leader's own signal** (not the follower's
benchmark) draw on a disjoint pool (followers) instead of a
self-referential one (other leaders).

**What this construction can and cannot rule out, stated explicitly per
the independent review's finding**: no intraday NIFTY or any other index
series exists (Section 3), so there is no benchmark external to this
two-tier split itself. The market-factor null (Section 16c) tests whether
`S_leader(t)` adds predictive power beyond `B_follower_LOO` and the
follower's own momentum -- this tests "is this more than a contemporaneous
bivariate correlation," but it **cannot** distinguish a genuine
leader-to-follower information flow from both tiers reacting to one
shared, unobserved factor at different speeds (Section 1's mechanisms 1
vs 2 vs 3). This limitation is structural, not a gap this study can close
with the data available, and is not resolved by the Section 8 fix.

---

## Section 10: prediction horizons

Unchanged from the original version. Primary horizon: 60 minutes.
Secondary/robustness: 30 minutes. Exploratory, non-gating: 5 and 15
minutes. All expressed in real trading minutes. Selection was variance-only
(Phase 2), not outcome-dependent -- reaffirmed, with the caveat noted in
Section 17 that since every horizon's original MDE cleared the (now
superseded) cost-floor comparison by a wide margin, the horizon choice was
always more of an economic bet ("more room for a real effect to clear
costs") than a power-maximizing choice, and should be read as such.

---

## Section 11: controls (X)

Unchanged from the original version (follower's own trailing-5-minute raw
return; `B_follower_LOO` over the same window; follower's trailing
30-day realized volatility; time-of-day bucket; follower's trailing-60-session
turnover rank within the follower pool). No control added or removed in
this amendment.

---

## Section 12: exclusions

Unchanged from the original version (pre-open/opening-auction bars;
final-5-minutes-before-close signal-end minutes whose forward window
would cross 15:30; <90%-bar-completeness entity-days; +/-1-trading-day
corporate-action windows; whole-day exclusion if <50% of that month's
leader tier lacks a valid bar). **New in this amendment, Section 8's
per-minute breadth floor (`n_t >= 0.80 * leader-tier size`) is an
additional, minute-level exclusion layered on top of the existing
day-level 50% floor** -- the two operate at different granularities and
both apply.

---

## Section 13: missing-data handling

Unchanged from the original version: <3-consecutive-minute gaps
forward-filled for return computation; >=3-minute gaps excluded, not
imputed. Frozen, per Section 23.

---

## Section 14: statistical methodology

Unchanged from the original version: day-clustered OLS standard errors
(cluster = `trade_date`); 1,000-draw day-level block bootstrap as a
cross-check, fixed seed 20261107; non-overlapping-sample robustness check
(one observation per follower per day); no individual-minute-level
resampling anywhere.

---

## Section 15: multiple-testing correction (now machine-enforced)

**The family trial ledger is now `lead_lag/trial_ledger.json`, validated
by `lead_lag/ledger.py` (7 passing tests, `lead_lag/test_ledger.py`),
rather than a hand-maintained table in this document.** The denominator
is `ledger.denominator()` = `len(trials)` = **6**, as of this amendment,
computed from the file, not retyped:

| # | `config_key` | Configuration | Status |
|---|---|---|---|
| 1 | `grouping:liquidity_tier` | Liquidity-tier grouping | Adopted primary |
| 2 | `grouping:statistical_cluster` | Statistical-cluster grouping (5 descriptive threshold cuts, 1 configuration) | Examined, not adopted |
| 3 | `horizon:5min` | 5-minute horizon | Exploratory, non-gating |
| 4 | `horizon:15min` | 15-minute horizon | Exploratory, non-gating |
| 5 | `horizon:30min` | 30-minute horizon | Secondary/robustness |
| 6 | `horizon:60min` | 60-minute horizon | **Primary gate** |

**New, structural enforcement requirement for Phase 4**: before any
configuration reaches a statistical gate (a regression fit that will be
interpreted against Section 20, a null draw, a horizon's DEV result),
Phase 4 code **must** call `ledger.assert_registered(config_key)` --
which raises `UnregisteredConfigurationError` for anything not already in
`trial_ledger.json` -- and **must** call `ledger.record_gate_run(config_key,
run_metadata)` immediately after, which appends an automatic,
timestamped record to the ledger file itself and raises if the
configuration was never registered. This directly addresses the
independent review's finding that this exact project's POC family let
its Bonferroni denominator stay pinned at 2 across three preregistrations
while its real trial count reached 5 (`PROJECT_CONTEXT.md` Section 3,
finding #15) -- a demonstrated failure of prose-only discipline that this
mechanism is built to prevent recurring here. Adding a new configuration
requires hand-editing `trial_ledger.json` and committing that change --
there is no runtime path to grow the trial count silently.

**Primary gate test**: `beta` at h=60 minutes, tested at Bonferroni
alpha = 0.05 / 6 ~= 0.0083, two-sided, day-clustered SE. Secondary/exploratory
horizons reported at the same corrected threshold, non-gating. Secondary
BH report via `factors.ic_eval.benjamini_hochberg`, never substituted for
the primary correction. The five null/diagnostic checks in Section 16 are
not counted as additional trials (necessary conditions on one trial's
interpretation, not a separate multiple-comparisons problem), unchanged
reasoning from the original version.

---

## Section 16: null hypotheses

**(a) Timing null (circular time-shift)**: unchanged from the original
version. Per-day circular shift of the follower's forward-return series,
leader-signal series keeps its real timestamps, 1,000 draws, fixed seed
20261107, real `|beta|` must exceed the 95th percentile of the null-draw
distribution.

**(b) Selection null -- REDESIGNED: matched random-leader-portfolio null**

The original design (random follower reassignment against a
follower-agnostic signal) is replaced, per the independent review's
finding that it did not vary the quantity the regression actually tests.

**New construction, REVISED following adversarial re-review** -- the
first draft of this redesign (sent to re-review before any commit, per
the user's explicit procedure) was itself found to have two concrete,
opposite-direction flaws, fixed below rather than caveated around.

**Flaw found in the first draft, fixed here**: the first draft's
candidate pool was "top `2*n_leaders` by turnover" -- but the true
leader tier (top `n_leaders`) is, by that same ranking, exactly the top
half of that pool. A uniform without-replacement draw of `n_leaders` from
a `2*n_leaders` pool containing the true tier as a fixed subset is a
hypergeometric draw with expected overlap `n_leaders / 2` -- **on
average, about half of every "random" portfolio was literally the real
leader tier**, diluting the null's reference distribution toward the
real one (biasing the test conservative -- too hard to pass). Separately,
drawing a **fresh, independent** random portfolio every calendar month
*within* a single repetition pools 120 independent monthly sub-draws into
one `beta_random,r` -- any composition-specific association averages away
across those 120 independent draws, which systematically *narrows* the
between-repetition spread of `beta_random,r` relative to holding one
coherent counterfactual selection rule fixed across the whole sample
(biasing the test anti-conservative -- too easy to pass). These two
biases point in opposite directions and neither was acknowledged in the
first draft; both are fixed below rather than left to cancel by
assumption.

1. **The real follower-side data is held fixed across every repetition**
   -- the same (follower, day, minute) rows, the same `AR_follower`
   values, the same controls `X(j,t)`, exactly as used in the primary
   test. This is "preserve the actual follower portfolio," per the
   redesign requirement, and is standard permutation-test practice
   (condition on the real outcome data, vary only the randomized
   predictor) -- unchanged from the first draft, not itself a flaw.
2. **Candidate pool, now disjoint from the true leader tier (fix for
   Flaw 1)**: that month's candidate pool is ranks `n_leaders+1` through
   `3*n_leaders` by the same trailing-60-session turnover rank used for
   real tiering (i.e., the next two liquidity bands immediately below the
   true leaders -- e.g. ranks 41-120 when `n_leaders=40`) -- **zero
   overlap with the true leader tier by construction**, while still
   liquidity-comparable (the band immediately adjacent to the real tier,
   not an arbitrary or illiquid draw).
3. **Two null variants, both required (fix for Flaw 2)**, rather than
   one:
   - **Null B1 (per-month independent redraw)**: for each repetition
     `r = 1..1000`, draw `n_leaders` entities uniformly at random, without
     replacement, from that month's disjoint candidate pool,
     **independently for each calendar month**.
   - **Null B2 (fixed selection rule per repetition)**: for each
     repetition `r = 1..1000`, draw **one** random subset of
     `n_leaders` **rank-positions** (not entity identities) within the
     disjoint band once, and apply that same rank-position rule to every
     month's actual roster at those positions for the rest of that
     repetition -- entity identities still vary month to month as universe
     membership and ranks shift, but which rank-positions are selected
     does not, so a single repetition reflects one coherent
     counterfactual selection rule held across the full sample, not an
     average over 120 independent monthly draws.
   A fresh draw (B1) or a fresh rank-position rule (B2) is made for every
   repetition; neither is reused across repetitions.
4. Using **the exact Section 8 signal-construction procedure, unchanged**
   -- same 5-minute window, same `B_follower_pool(k)` benchmark, same
   equal weighting, same per-minute breadth floor -- build
   `S_leader_random,r(t)` (separately for B1 and B2) from the
   randomly-drawn portfolio, on the **same real trading days and the same
   real signal-minutes** as the true `S_leader(t)`. Only the identity of
   which stocks populate "leader" changes; nothing about when or how the
   signal is computed changes.
5. Refit the primary regression (Section 2's equation, same controls,
   same horizon) with `S_leader_random,r(t)` in place of the real
   `S_leader(t)`, holding the real follower-side data fixed (step 1), once
   for B1 and once for B2. Collect `beta_random,r` across all 1,000
   repetitions, separately for each variant.
6. **Comparison**: the real `beta` (from the true, top-20%-by-turnover
   leader tier) must exceed the 95th percentile of `|beta_random|`
   (two-sided) **for both B1 and B2 independently** to pass this null
   (Section 20's gate condition 4 is updated accordingly). Requiring both
   is deliberate: B1 and B2 are sensitive to different, opposite-direction
   biases, so a result that only clears one of them is not trusted as a
   clean pass.

**Why this is not another near-no-op**: unlike the original follower-permutation
null, this construction varies `S_leader(t)`'s own realized time series
across repetitions (different stock composition on the same days produces
different realized 5-minute cumulative returns, since individual stocks'
returns are not identical even within a liquidity band) -- it does not
merely relabel rows while leaving the regressor's values untouched. This
was the specific, identified failure mode of the original design. The
revised construction additionally does not share the two further flaws
the adversarial re-review found in this redesign's own first draft
(contaminated candidate pool, narrowed-by-redraw null spread) --
acknowledged here explicitly rather than only rebutting the one failure
mode the independent review happened to name first, per that same
re-review's finding that the first draft's defense paragraph was
one-sided.

**Minor, non-blocking caveat carried forward**: the empirical 95th
percentile of 1,000 draws has its own estimation uncertainty (order
roughly +/-1.3 percentage points under a normal approximation) for a
single pass/fail threshold with no reported confidence interval. Phase 4
should re-run at 5,000 draws as a stability check and confirm the
pass/fail conclusion does not flip before relying on the 1,000-draw
result alone.

**This null must be run on the real, Section-8-corrected `S_leader(t)`,
not on the diagnostic substitute used in `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`'s
pilot** -- the pilot's placebo diagnostic (below) is a different check
answering a different question (sampling noise under zero true effect),
and does not substitute for actually running this redesigned selection
null once Phase 4 code exists.

**(c) Market-factor null**: unchanged in form from the original version
-- nested-model comparison (`X(j,t)` only vs. full model). See Section 9
for the explicit statement of what this can and cannot rule out.

**(d) Reverse-direction diagnostic**: unchanged from the original
version. Diagnostic only, both directions reported regardless of result.

**(e) Placebo diagnostic -- construction detail now pinned down**

`LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Section 3.3 found the original
text ("pair... against `S_leader` drawn from a different... trading day")
was ambiguous between two readings that produced bootstrap SE estimates
differing by more than 10x: an independent random placebo-day draw **per
follower-row**, versus one random placebo-day draw **shared by every
follower on the same real day** (matching how the real `S_leader(t)`
actually works -- one pooled value per day, broadcast to every follower
that day).

**Resolved in this amendment: the per-real-day-shared reading is
correct**, because it is the one that actually matches Section 2's model
(`S_leader(t)` is not follower-specific) -- the per-row-independent
reading implicitly treats the signal as if it varied by follower, which
it does not, and so does not faithfully reconstruct what is being tested.
**All Phase 4 implementations of this diagnostic must draw exactly one
random placebo day per real response day, shared across every follower
row on that day**, with the placebo day at least 20 trading days from the
real day, same intraday minute-of-day. This resolution is frozen now, per
Section 23, not chosen after seeing which reading looks better in a
future run (the pilot's own finding that the two readings disagree by
>10x, with the correct one giving the *smaller* estimate, is recorded
honestly here rather than defaulting to whichever was more conservative).

---

## Section 17: power and minimum detectable effect (MDE) -- REWRITTEN, NO UNCONDITIONAL PASS CLAIMED

**The original version's MDE (1.39-4.22 bps) is withdrawn as a power
statement for this estimand.** It was computed from individual-stock raw
1-minute-bar return variance and a naive day-count, not from the
day-clustered regression coefficient's actual sampling distribution, and
-- independent of that problem -- the predictor it would have applied to
did not exist as specified (Amendment Log item 1). Neither error is
cosmetic; both are acknowledged plainly rather than patched over.

**What is now known, following `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
Task 3**:

1. **The corrected `S_leader(t)` (Section 8) has not yet been measured on
   real data.** Its own empirical sigma -- the quantity Section 2's
   estimand actually needs -- remains unmeasured; this amendment commits
   to measuring it as the first step of Phase 4, before any gate is run
   (Section 21).
2. **A diagnostic substitute signal** (`mean_leaders - mean_universe`
   trailing-5-minute return, a close but not identical proxy for the
   corrected Section 8 construction, which uses `mean_leaders -
   mean_followers` specifically) was used to pilot the dependence-aware
   SE methodology on an 11-month, 230-trading-day, single-fixed-signal-minute
   (10:15) sample, via the Section 16e placebo construction (never
   fitting a contemporaneous, real signal-to-response relationship):
   - Day-clustered block bootstrap (resampling the 230 real response
     days with replacement, redrawing a fresh placebo pairing every
     replicate), 500/500 replicates achieved in 2.2-2.4 seconds -- the
     bootstrap itself is computationally cheap and tractable at this
     scope; full-scale (2,468-day) cost was not measured and should not
     be assumed comparable without checking.
   - Using the methodologically correct (per-real-day-shared, Section
     16e) pairing convention: `SE_boot = 0.0347` (coefficient units),
     giving a design effect of 0.089 relative to a naive non-clustered
     SE (i.e., the day-clustered SE is *smaller* than the naive one in
     this pilot -- a plausible, not yet fully explained, consequence of
     the leave-one-out follower benchmark already stripping out common
     same-day comovement that clustering would otherwise need to
     correct for). **This is a deliberate choice of the smaller,
     non-conservative of the two SE readings found in Task 3.3** (the
     per-row-independent reading gave `SE_boot = 0.1120`, over 3x larger)
     -- used here because it is the one that actually matches Section
     2's model (`S_leader(t)` is one pooled value per day, not
     follower-specific), not because it is favorable; this is stated
     explicitly, since the number happening to be smaller than the
     alternative could otherwise look like cherry-picking.
   - Resulting MDE, **corrected following adversarial re-review of this
     amendment's own first draft** (the first draft used an arithmetically
     wrong Bonferroni critical value, 3.1909; the correct value for a
     two-sided test at alpha=0.05/6 is `z_{1-alpha/2} + z_{power} =
     z_{0.995833} + z_{0.80} = 2.63826 + 0.84162 = 3.47988`):
     `0.0347 * 2.80158 ~= 0.0972` (uncorrected, alpha=0.05, power=0.80) to
     `0.0347 * 3.47988 ~= 0.1208` (Bonferroni, alpha=0.05/6) coefficient
     units. Converted via the *proxy's own* sigma (3.92 bps) purely for
     illustration: approximately **0.38-0.47 bps** -- **explicitly not a
     reliable number**, since it depends on a proxy signal, not the real,
     corrected Section 8 construction. (Algebraic note on how close a
     placeholder this proxy actually is: since the proxy is
     `mean_leaders - mean_universe` and, with stable tier sizes
     `n_L~=40, n_F~=160`, `mean_universe` is a turnover-weighted blend of
     both tiers, `mean_leaders - mean_universe ~= (n_F/(n_L+n_F)) *
     (mean_leaders - mean_followers) ~= 0.8 *` the real Section 8 signal
     -- i.e., the proxy is approximately a fixed linear rescaling of the
     real signal, not an unrelated quantity, which leaves t-stats and the
     bps-at-+/-1-sigma economic magnitude largely invariant to the
     substitution; the two residual, uncompensated gaps are that the 0.8
     ratio is not perfectly constant month to month (observed 0.796-0.80),
     and the real signal's own per-minute breadth floor, Section 8,
     excludes slightly different minutes than this proxy did.)
3. **Power at the project's economic-significance thresholds (10/20/30
   bps, Section 18) is not usefully reportable from this pilot** -- the
   proxy's small sigma relative to `SE_boot` makes power trivially >0.999
   at every threshold tested, which is an artifact of the proxy, not
   informative about the real signal.

**Explicit statement, per this family's own standing instruction not to
claim an unconditional PASS where one cannot be supported**: **this
amendment does not claim the study is adequately powered.** The evidence
available is consistent with "not alarming" (the bootstrap achieved full
target scale easily; the design effect is not large; the breadth
correction, Section 6, remains ample) but this is a materially weaker
statement than the original version's "5-20x margin," which was never
actually computed on anything that matches the real estimand. **The power
question is deferred to Phase 4's first analysis step** (Section 21):
measure the real, corrected `S_leader(t)`'s own sigma; re-run the
day-clustered placebo bootstrap (per-real-day-shared pairing, Section
16e) on the real signal at full scale; only then compute a trustworthy
MDE and compare it against Section 18's economic floor, before running
any primary-gate regression.

---

## Section 18: economic significance threshold

Unchanged from the original version: 20 bps (stricter bound of the
project's established 20-30bps round-trip cost figure, `PROJECT_CONTEXT.md`
Section 8), compared against the model-implied effect at +/-1 observed
sigma of the real (Section 8-corrected) `S_leader(t)` -- which Section 17
notes has not yet been measured. The spread/impact component of the
20-30bps figure remains unvalidated (`SPREAD_ESTIMATOR_VALIDATION.md`:
zero days of live collection as of this writing); this caveat is
unchanged and not newly introduced by this amendment.

---

## Section 19: execution-cost assumptions (for any future trading simulation)

Unchanged from the original version: not specified here, deferred entirely
to a separate Phase 7 preregistration, per the master spec's explicit
prohibition on folding execution mechanics into the primary measurement
(`lead_lag/MASTER_SPEC_LEAD_LAG.md` Part 9).

---

## Section 20: verdict rules

**Unchanged in structure from the original version, with one addition**:
a seventh, prior condition is added, since it is now a precondition for
the other six to even be meaningful.

**PASS requires ALL of the following; any single failure is a FAIL,
closing the measurement study automatically:**

0. **(New) Signal non-degeneracy check**: the real, corrected `S_leader(t)`
   (Section 8) has measurable, non-trivial variance on real data (i.e.,
   Phase 4's first analysis step, Section 21, confirms sigma is of a
   sane economic order of magnitude, not machine-epsilon noise). This is
   checked **before** any of the following six, since Amendment Log item
   1 demonstrates it cannot be assumed.
1. **Primary test**: `beta` at h=60 minutes is statistically significant
   at the Bonferroni-corrected alpha (0.0083, two-sided), day-clustered
   SE, economically interpretable sign.
2. **Economic magnitude**: the Section 18 implied effect at +/-1 sigma of
   the real `S_leader` exceeds the 20bps floor.
3. **Timing null**: real `|beta|` exceeds the 95th percentile of the
   circular-shift null distribution (Section 16a).
4. **Selection null (redesigned)**: real `|beta|` exceeds the 95th
   percentile of the matched-random-leader-portfolio null distribution
   **for both the B1 (per-month redraw) and B2 (fixed selection rule)
   variants independently** (Section 16b) -- passing only one is not a
   pass of this gate.
5. **Market-factor null**: the leader-signal term's incremental
   contribution (Section 16c) is statistically distinguishable from zero
   and not reducible to the controls alone.
6. **Stage-count reconciliation**: leader-tier construction -> signal
   construction -> follower-eligibility filtering -> final regression
   sample row counts reconcile against each prior stage, with no
   unexplained discrepancy.

**A PASS here means**: a statistically and economically significant,
null-surviving, incrementally-informative liquidity-tiered return
relationship was found at the preregistered primary horizon -- per
Section 1's reframing, this does not establish which of the four named
mechanisms (genuine information diffusion, common-factor differential
speed, non-synchronous trading, stale pricing) is responsible, and does
not by itself authorize a trading simulation.

**A PASS here does NOT mean**: that a live, tradeable edge exists, that
execution costs have been fully accounted for, that any historical
holdout-style validation has occurred, or that the specific mechanism of
"information propagation between related securities" (the original,
pre-amendment hypothesis framing) has been confirmed.

---

## Section 21: failure conditions and required Phase 4 first steps

**Beyond the headline gate, in addition to the original version's four
failure conditions (sign instability, non-overlapping-sample check,
signal sparsity, 10bps robustness), this amendment adds the following as
mandatory, ordered FIRST STEPS of Phase 4, to be completed and reported
before any primary-gate regression is run:**

1. **Measure the real, Section-8-corrected `S_leader(t)`'s own mean and
   sigma on real data** (all months, full date range). Confirm it is not
   degenerate (Section 20, check 0) before proceeding. If it is found to
   be degenerate or near-degenerate in some other, not-yet-anticipated
   way, **stop and report this honestly rather than patching the
   construction ad hoc** -- the same discipline this amendment itself
   followed when the original construction failed this exact check.
2. **Re-run the Section 16e placebo bootstrap on the real, corrected
   signal**, at full scale (all 2,468 trading days, not the 11-month
   pilot sample), using the per-real-day-shared pairing convention
   (Section 16e, resolved). Report the resulting `SE_boot`, MDE, and
   power at the Section 18 economic thresholds. Compare this against
   Section 18's floor **before** running the primary-gate regression,
   using the following frozen decision rule (margin ratio = Section 18's
   20bps floor divided by the full-scale corrected MDE, both expressed in
   bps via the real signal's own measured sigma, per step 1 above --
   **frozen now, per the adversarial re-review's finding that
   "comfortably below" was the one undefined, outcome-adjacent judgment
   call left in this document, inconsistent with Section 23's otherwise
   strict freezing discipline**):
   - margin ratio `>= 5`: proceed to the primary-gate regression.
   - margin ratio `>= 1` and `< 5`: **stop, report INCONCLUSIVE, and
     return to the user for explicit guidance before proceeding** -- do
     not auto-proceed on a borderline margin.
   - margin ratio `< 1` (MDE exceeds the floor): **stop and report
     ABANDONED** -- the sample cannot resolve an economically meaningful
     effect at all.
   The `>= 5` threshold is anchored to, but more conservative than, the
   original (withdrawn) version's "5-20x margin" language -- chosen now,
   before any real Phase 4 number exists, specifically so it cannot be
   adjusted after seeing whether a given run clears it.
3. **Run the redesigned selection null (Section 16b)** on the real signal
   and confirm it is genuinely discriminating in practice (i.e., the
   1,000 `beta_random` draws show real variation, not another
   unanticipated collapse) before relying on it as part of Section 20's
   gate.
4. Only after 1-3 above are complete and reported, proceed to the primary
   h=60-minute regression and the remaining Section 20 checks.

---

## Section 22: reproducibility requirements

Unchanged from the original version (read-only connections only; fixed
seed 20261107 for every null/bootstrap draw; 1,000 draws per randomized
procedure; chunking by calendar year with per-chunk checkpointing for the
full DEV run, per the Phase 2 OOM lesson; five-observation hand-tracing
before aggregate results are accepted), **plus**: every statistical gate
run in Phase 4 must call `lead_lag/ledger.assert_registered(config_key)`
before running and `lead_lag/ledger.record_gate_run(config_key,
run_metadata)` immediately after (Section 15), and the per-real-day-shared
placebo-pairing convention (Section 16e) must be used verbatim, not
re-chosen.

---

## Section 23: frozen free parameters (new, consolidated)

Every parameter identified across this family's documents that could
affect sample selection or results, in one place, so none can be
silently retuned after Phase 4 output exists:

| Parameter | Value | Source |
|---|---|---|
| Leader-tier cutoff | top 20% by trailing turnover | Section 6, master spec Part 3.3 default |
| Trailing turnover window | 60 trading sessions | Section 6, master spec Part 3.3 default |
| Tier reconstitution cadence | monthly, first trading day | Section 6 |
| Signal window width | 5 minutes, fixed | Section 8, master spec Part 4.2 |
| Per-minute leader breadth floor | `n_t >= 0.80 * tier size` | Section 8, this amendment, evidence-based (excludes ~0.001% of minutes) |
| Day-level leader breadth floor | >=50% of tier has a valid bar | Section 12 (original) |
| Entity-day completeness exclusion | <90% of expected bars | Section 12 (original) |
| Gap-fill forward-fill threshold | <3 consecutive minutes | Section 13 (original) |
| Gap exclusion threshold | >=3 consecutive minutes | Section 13 (original) |
| Corporate-action exclusion window | +/-1 trading day | Section 12 (original) |
| Prediction horizons | 5, 15, 30, 60 minutes | Section 10 |
| Primary horizon | 60 minutes | Section 10, chosen variance-only |
| Economic significance floor | 20 bps (stricter of 20-30bps) | Section 18 |
| Significance level | alpha=0.05, two-sided | Section 15 |
| Power target | 0.80 | Section 17 |
| Multiple-testing denominator | 6 (`lead_lag/trial_ledger.json`) | Section 15 |
| Null/bootstrap draw count | 1,000 (timing, selection); 500 achieved in pilot (placebo bootstrap, Phase 4 to confirm at full scale) | Section 14, 16 |
| Random seed | 20261107 | Section 22 |
| Placebo day-pairing granularity | one shared random day per real response day (not per follower-row) | Section 16e, resolved in this amendment |
| Placebo minimum day separation | >=20 trading days | Section 16e (original) |
| Matched-random-leader candidate pool | ranks `n_leaders+1` to `3*n_leaders` by trailing turnover (disjoint from the true leader tier) | Section 16b, revised following adversarial re-review (first draft's top-40%/2x-size pool overlapped the true tier by ~50% and is superseded) |
| Selection-null variants required | both B1 (per-month independent redraw) and B2 (fixed selection rule per repetition) must independently pass | Section 16b, Section 20 condition 4, revised following adversarial re-review |
| Selection-null repetitions | 1,000 (per variant) | Section 16b |
| Bonferroni two-sided z-critical (alpha=0.05/6) | 2.63826 (giving MDE multiplier 3.47988 with z_power=0.84162) | Section 17, corrected following adversarial re-review (first draft used 3.1909 in error) |
| Full-scale MDE-vs-floor decision margin | `>=5x`: proceed; `1x-5x`: INCONCLUSIVE, stop for guidance; `<1x`: ABANDONED | Section 21, frozen following adversarial re-review (first draft left "comfortably below" undefined) |

None of these were chosen after observing any outcome. Any future change
to a value in this table requires a new, explicitly versioned amendment
(or a V2 preregistration), with its own entry in `lead_lag/trial_ledger.json`
if the change constitutes a new configuration.

---

## Status

**Original version committed 2026-11-07**, commit `e1418a661a769c9f134d750bbe95dc1a831b0305`.

**This amendment drafted 2026-11-08**, following an independent
methodology review and the subsequent discovery (during this amendment's
own supporting analysis) that the original Section 8/9 signal construction
was algebraically degenerate. Supporting documents:
`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` (real breadth, per-minute
floor, placebo pilot), `lead_lag/MASTER_SPEC_LEAD_LAG.md` (governing
directive, now committed), `lead_lag/trial_ledger.json` +
`lead_lag/ledger.py` + `lead_lag/test_ledger.py` (machine-enforced trial
accounting, 7 passing tests).

**Adversarial re-review completed.** Two concrete issues were found in
this amendment's own first draft (Section 16b's candidate-pool overlap
and redraw-narrowing biases; Section 17's arithmetic error and
Section 21's undefined margin) and are fixed in the version now in this
file -- see Amendment Log item 9. The reviewer's other findings (the
Section 8 degeneracy fix itself, the breadth numbers, the ledger
mechanism, Sections 1/2/6/9/15/20/21/23 generally) held up under
adversarial reading and are unchanged.

**No `src/lead_lag/` code exists yet. Phase 4 implementation still
requires the user's explicit approval, now that this amendment has been
reviewed and is being committed.** This amendment does not claim the
hypothesis has passed, and does not claim an unconditional power PASS --
see Sections 17 and 20.

Amendment commit hash: _to be filled in immediately after this file is
committed._
