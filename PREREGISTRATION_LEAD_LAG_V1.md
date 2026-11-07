# Cross-stock lead-lag propagation, Study V1 (liquidity-tier, sector-agnostic)

## Provenance, stated plainly and prominently

**This is a brand-new research family. No prior trial exists in this
project under this name.** Phase 0 (`lead_lag/LEAD_LAG_RECONNAISSANCE.md`),
Phase 1 (`lead_lag/DATA_AUDIT_LEAD_LAG.md`), and Phase 2
(`lead_lag/LEAD_LAG_FEASIBILITY.md`) preceded this document, in that
order, all read-only against the existing warehouse, no strategy code
written before this preregistration. This document is being committed
**alone** -- no `src/lead_lag/` implementation exists yet -- per Part 7's
explicit requirement that the preregistration be frozen before the first
outcome result exists.

**Two binding scope decisions were made by the human user before this
document was drafted, after Phase 1's audit surfaced them as a live
fork, and are not revisited here:**

1. **Intraday scope is capped at the existing `data/fibo_intraday.duckdb`
   universe** -- 386 distinct entities, 2016-10-04 to 2026-09-18, the
   project's standard annually-reconstituted top-200-by-turnover universe
   (`fibo.universe.reconstitute_annually`, reused unmodified, five other
   closed families' own universe). **No new Angel One fetch.** Any
   extension past 2026-09-18 or below the historical top-200 cutoff is
   out of scope for this trial and would be a separately costed follow-up
   (Phase 1 estimated days-to-a-week of supervised wall-clock time for a
   fresh N=200/10-year fetch).
2. **Grouping is sector-agnostic.** `DATA_AUDIT_LEAD_LAG.md` found: (a)
   `index_eod` has zero sectoral index series, only `NIFTY50` -- no
   ready-made sector benchmark exists; (b) the one sector/industry
   mapping file in the repo (`data/raw/sector/symbol_industry_map.csv`)
   is a current-only snapshot with no `known_date`/point-in-time version
   anywhere -- the same defect shape as the already-documented Bug #12
   (current-state-only fundamentals screener). Sector churn across
   2016-2026 is **UNVERIFIABLE with data that exists in this repo**, not
   merely unmeasured-but-assumed-small. This study therefore uses
   **liquidity-tier grouping** (trailing turnover rank within the
   existing point-in-time universe) instead of sector membership, per the
   human user's explicit choice between three offered options (drop
   sector entirely / keep sector with the blindness flagged / pause to
   build point-in-time sector history first) -- the first was chosen.

**The project's own structural prior, recorded here before any Study V1
result exists, not after**: eleven prior intraday strategies with
completely different entry logic (Darvas, Fibo zones, volume profile,
FVG, IPO openings, liquidity sweeps A-D) all landed in the same -0.1% to
-0.3% per-trade net-return band, read project-wide as "one constant seen
through eleven lenses" -- fixed per-trade cost against a shrinking
available move at short horizons (`PROJECT_CONTEXT.md` Section 8). Lead-lag
propagation is a different causal mechanism (information diffusion across
related names, not single-stock level-bounce or breakout), so it is not
automatically subject to that closed-class reasoning -- but the same cost
arithmetic applies regardless of mechanism, which is exactly why Phase 2's
MDE-vs-cost-floor check was run before this document was drafted, not
after.

**Claude's own calibration record on this exact manipulation shape,
recorded as a caution against this document's own horizon
recommendation**: Claude's mechanism predictions were wrong 5 times out of
5 in the Liquidity family, twice specifically on count/effect direction
for a coarser-vs-finer time-bucketing manipulation (Liquidity E and F
Phase 1, both predicted fewer setups on the coarser grid, both found more).
Section 17 below states this study's own horizon prediction explicitly as
a falsifiable guess, not a design assumption.

---

## Section 0: reuse boundaries, read-only

No existing strategy file is touched. The following are imported
read-only, never modified, per the master spec's absolute isolation
requirement:

- `src/data_layer/db.py` -- `get_read_connection()`, `read_latest()`,
  `query_as_of()`. All new code uses the read-only connection path only;
  no write connection is ever opened by this family.
- `src/data_layer/entity_panel.py` -- `read_full_entity_panel_authorized(con,
  authorize_holdout=True)`, **not** the bare `read_entity_panel()`.
  `DATA_AUDIT_LEAD_LAG.md` Section 3 found the latter silently stale,
  truncated at 2025-03-18 (the retired holdout boundary, never
  re-materialized). This family reads `prices_eod` current through
  2026-11-05 via the authorized full-panel path, or `prices_eod` directly.
- `src/data_layer/isin_lineage.py`, `corporate_actions.py`,
  `adjustment.py` -- entity resolution and split/bonus-adjusted prices,
  inherited rather than re-derived, per the project's own "a fix applied
  only where noticed" lesson (`PROJECT_CONTEXT.md` Section 7 finding #4).
- `src/fibo/universe.py` (`reconstitute_annually`) -- the point-in-time
  top-200-by-turnover annual universe construction. **Unchanged.** This
  family does not build a second universe-construction mechanism.
- `src/fibo/intraday_db.py` -- the `bars_1min` schema and read helpers
  against `data/fibo_intraday.duckdb`. Read-only; this family never
  writes to this file.
- `src/factors/target.py` (`compute_forward_return`), `src/factors/ic_eval.py`
  (`daily_rank_ic`, `nonoverlapping_ic_report`, `benjamini_hochberg`) --
  the forward-return and significance-testing machinery, reused rather
  than re-implemented. `benjamini_hochberg` specifically is reused
  verbatim for the secondary FDR report (Section 15).
- `src/box_theory/inference.py` (`day_clustered_bootstrap`) -- the
  day-clustering convention for standard errors, reused unchanged
  (Section 14).
- `src/data_layer/holdout.py` -- imported for discipline/consistency only
  (date-range clipping if ever needed); the sealed holdout itself is
  retired project-wide and is not an active constraint on this DEV-only
  family.

**New code, lives entirely in `src/lead_lag/`** (created at Phase 4,
after this document is committed and approved -- not yet written):
`universe.py` (thin wrapper freezing the liquidity-tier split on top of
`fibo.universe`), `benchmarks.py` (the two disjoint leave-one-out
benchmarks, Section 9), `signal.py` (leader portfolio signal, Section 8),
`measurement.py` (the regression), `nulls.py` (Section 16), `statistics.py`
(day-clustered SE, bootstrap, BH wrapper), `validation.py` (hand-trace
support). No existing family's module is imported by name into a new
lead-lag-specific role beyond what is listed above as read-only reuse.

---

## Section 1: research hypothesis

Within the existing point-in-time top-200-by-turnover universe (386
distinct entities across 2016-10-04 to 2026-09-18), do abnormal 1-minute-bar
price moves in the most liquid subset of stocks ("leaders") predict
subsequent abnormal price moves in the remaining, less liquid stocks
("followers"), over a fixed forward horizon, after controlling for
broad-market co-movement and the follower's own recent momentum?

This is a **measurement** question, not a trading-strategy proposal. A
statistically detectable coefficient does not by itself authorize a
trading simulation -- see Section 20.

---

## Section 2: primary estimand

The regression coefficient **beta** in:

```
AR_follower(j, t -> t+h) = alpha + beta * S_leader(t) + gamma . X(j,t) + epsilon(j,t,h)
```

- `j` indexes a follower-tier entity, `t` indexes a completed 1-minute bar
  (the signal-end minute), `h` is the forward horizon (Section 10).
- `AR_follower(j, t->t+h)` is entity j's forward h-minute abnormal
  (leave-one-out-benchmark-adjusted) return, Section 9.
- `S_leader(t)` is the equal-weighted leader-portfolio signal, Section 8.
- `X(j,t)` is the predetermined control vector, Section 11.
- Pooled across all eligible (follower, trading-day, signal-minute)
  observations; inference uses day-clustered standard errors (Section 14).

Reported alongside beta, per Part 7.1 (not a bare p-value): standard
error, 95% CI, implied economic magnitude at +/-1 observed sigma of
`S_leader`, incremental R-squared over the controls-only model, stability
across years and across the liquidity-tier boundary (Section 6).

---

## Section 3: data sources

| Source | Table/file | Access path | Role |
|---|---|---|---|
| 1-minute bars | `bars_1min`, `data/fibo_intraday.duckdb` | `duckdb.connect(path, read_only=True)` direct, or `fibo.intraday_db` read helpers | Signal, response, benchmark construction |
| Daily bars | `prices_eod`, `data/warehouse.duckdb` | `entity_panel.read_full_entity_panel_authorized(con, authorize_holdout=True)` | Trailing turnover ranking (leader/follower tier), trailing volatility control |
| Entity resolution | `isin_lineage`, `data/warehouse.duckdb` | `isin_lineage.build_entity_resolver` | ISIN -> entity_id, point-in-time |
| Corporate actions | `corporate_actions`, `adjustment_factors` | `adjustment.read_adjusted_prices` | Split/bonus-adjusted prices; exclusion-window input (Section 12) |
| Universe | `fibo.universe.reconstitute_annually` | function call, read-only | Point-in-time top-200-by-turnover annual membership |
| Market index | `index_eod` (`NIFTY50` only) | `index_nse.load_index_day` | **Not used as the benchmark** -- no intraday series exists for any index, broad or sectoral (`DATA_AUDIT_LEAD_LAG.md` Section 2). Referenced only as a daily-frequency descriptive cross-check in robustness reporting, never as the intraday benchmark. |
| Sector/industry | `data/raw/sector/symbol_industry_map.csv` | -- | **Explicitly not used.** Current-only snapshot, no point-in-time version, no backtest ever reads it today. |

No new data fetch of any kind is required. No existing fact table is
written to.

---

## Section 4: universe definition

Unchanged from `fibo.universe.reconstitute_annually`: for each calendar
year Y >= 2017, membership = the top 200 entities by median daily rupee
turnover (price x volume, raw/unadjusted -- turnover is split-invariant)
over year Y-1, held fixed for all of year Y. Year 2016 is dropped (no
prior year to rank against, per `fibo/universe.py`'s own documented gap).
The in-progress final year is excluded from ranking, per the same
convention. This yields the 386 distinct entities observed over
2016-10-04 to 2026-09-18 (membership turns over year to year; 386 > 200).

This family additionally caps itself to the exact date range already
present in `fibo_intraday.duckdb` (2016-10-04 to 2026-09-18), per the
user's binding scope decision -- this is a hard filter on top of the
annual universe, not a change to the universe construction itself.

**Known, inherited limitation, not re-solved here**: `fibo/universe.py`'s
own docstring already flags that this is not survivorship-bias-free (a
present-day top-200 reconstruction from surviving + delisted names,
constructed from data as it exists today, not literally as it was known
on each historical date for names that later delisted). This family
inherits that limitation unchanged; no new survivorship quantification is
attempted here (`scripts/run_survivorship_quantification.py` exists but
was not run as part of this preregistration -- flagged, not actioned).

---

## Section 5: historical sector grouping

**None. Not used anywhere in this design.** See Provenance above and
`DATA_AUDIT_LEAD_LAG.md` Section 4 for the evidence (UNVERIFIABLE
point-in-time sector history). Any apparent "sector effect" that shows up
in robustness checks is a descriptive observation only, never a gating
criterion, since no point-in-time sector label exists to test it properly.

---

## Section 6: leader definition

**Two-level, point-in-time, trailing-only structure, frozen now:**

1. **Annual universe eligibility** (Section 4) determines who can be
   considered at all in year Y.
2. **Monthly liquidity-tier split**, computed on the first trading day of
   each calendar month, using the trailing 60 trading sessions' median
   daily rupee turnover (from `prices_eod`, via the authorized full-panel
   path, point-in-time -- no bar after the ranking date is used): within
   that month's eligible universe, the **top 20% by trailing-60-session
   median turnover = leaders** for that month; held fixed for the full
   month (avoids daily rank churn/noise, per the master spec's own
   framing of checking "how frequently group membership changes" before
   adopting a cadence). 60 sessions and the 20% cutoff are the master
   spec's own stated default (Part 3.3) and are adopted unmodified, not
   tuned.

Phase 2's feasibility check used lifetime total turnover as a quick
proxy (77/309 split) to establish that candidate counts are ample; the
preregistered design above (trailing-60-session, monthly) is the one
actually run in Phase 6 -- this is a refinement of the feasibility proxy,
not a new trial, since it doesn't change the feasibility conclusion
(ample breadth either way) and was specified before any Phase 6 output
exists.

---

## Section 7: follower (laggard) definition

All entities eligible that month (Section 4) that are **not** in that
month's leader tier (Section 6) -- i.e., the bottom 80% by trailing
turnover. Additional per-observation eligibility filters (Section 12):
the entity must have a valid, non-excluded bar at both the signal-end
minute and across the full forward window for that (date, horizon).

Per Part 4.4, this family does **not** collapse every lower-return stock
into "laggard" without investigating its own prior movement -- the
follower's own trailing-5-minute return is carried forward as an explicit
control (Section 11), separating "hasn't moved yet," "already moved the
same way," and "already moved the opposite way" rather than assuming
uniformity.

---

## Section 8: leader signal construction

For each leader-tier entity `i` and each completed 1-minute bar `k`:

```
AR_leader(i,k) = r(i,k) - B_leader(k)        [own-return minus the leader-pool LOO benchmark, Section 9]
S_i(t) = sum_{k=t-4}^{t} AR_leader(i,k)      [5-minute trailing cumulative abnormal return, fixed in real minutes]
S_leader(t) = (1/n_t) * sum_i S_i(t)         [equal-weighted across all leader-tier entities with a valid bar at t]
```

- Signal window width is **fixed at 5 minutes, in real time**, per the
  master spec's own default (Part 4.2) and per `OPERATIONS.md`'s
  candle-count-vs-minutes standing rule -- this window is never varied as
  part of this study's configuration grid, so no re-statement-in-minutes
  issue arises for it. Only the **forward horizon** (Section 10) is
  varied, and it is already expressed in minutes, not bars.
- Equal weighting, not turnover-weighting, per Part 4.3's explicit
  instruction ("do not choose weights after observing results").
- `S_leader(t)` is only computed, and only usable as a predictor, after
  bar `t` has fully closed -- its timestamp convention (bar-start vs
  bar-end) is verified empirically in Phase 4 hand-tracing (Section 21)
  before any aggregate result is trusted, per Part 4.2's explicit warning
  not to assume the convention.

---

## Section 9: benchmark construction (disjoint leave-one-out pools)

Part 4.1 requires leave-one-out construction so "a leader's own movement
must not mechanically contaminate the laggard's benchmark." Because this
design has no sector, and because a single universe-wide leave-one-out
benchmark would still let the leader tier's own abnormal move flow into
the follower's benchmark (leaders remain inside a universe-wide LOO pool
even when the specific follower is excluded), this family uses **two
disjoint leave-one-out pools instead of one**:

```
B_leader(k)   = equal-weighted mean of r(i', k) over all OTHER leader-tier entities i' != i, that month
B_follower(k) = equal-weighted mean of r(j', k) over all OTHER follower-tier entities j' != j, that month
```

- A leader's own abnormal return (feeding `S_leader`) is benchmarked
  against the *other leaders*, never against any follower.
- A follower's own abnormal return (`AR_follower`, the response variable,
  Section 2) is benchmarked against the *other followers*, never against
  any leader.
- This makes the leader-signal side and the follower-response side
  **structurally independent constructions drawn from disjoint stock
  sets**, eliminating the specific mechanical-contamination failure mode
  Part 4.1 warns about, by construction rather than by a post-hoc
  adjustment. This is a deliberate, explicit adaptation of Part 4.1's
  literal "sector" leave-one-out language to this study's sector-agnostic
  two-tier design -- stated here, before any result exists, exactly so it
  cannot be read as a methodology change made after seeing a result.
- No intraday NIFTY50 (or any other index) series exists (Section 3), so
  no index-based benchmark is used. A daily-frequency NIFTY50 descriptive
  cross-check is reported in robustness output only (Section 14), never
  substituted into the primary benchmark.

---

## Section 10: prediction horizons

All expressed in **real trading minutes**, never candle counts, per the
standing rule (`OPERATIONS.md` line ~1424-1435) and because this family's
signal window (Section 8) is held fixed while the horizon varies -- the
one case the standing rule explicitly requires minute-denominated,
held-constant-elsewhere specification.

| Horizon | Role |
|---|---|
| 5 minutes | Exploratory, reported, corrected, non-gating |
| 15 minutes | Exploratory, reported, corrected, non-gating |
| 30 minutes | **Secondary / robustness horizon** |
| 60 minutes | **Primary horizon** -- the one that determines the Section 20 verdict |

Primary horizon selection (60 minutes) was made in Phase 2
(`LEAD_LAG_FEASIBILITY.md` Section 5), **before** any Phase 6 regression
output exists, on economic-reasoning and feasibility grounds (largest
ratio of observed sigma to the fixed cost floor among the four
candidates), not by picking the best-performing horizon after the fact --
satisfying Part 5's explicit requirement.

A forward window that would extend past 15:30 (session close) for that
trading day is **discarded for that observation**, never carried into the
next session -- no horizon is allowed to cross a session boundary
(Section 12).

---

## Section 11: controls (X)

All computed from information available strictly before or at the signal
minute `t`:

1. **Follower's own trailing-5-minute raw return** -- same-window
   convention as the leader signal; separates "hasn't moved,"
   "already moved with," "already moved against" (Part 4.4).
2. **Follower-pool benchmark return over the same trailing 5-minute
   window** (`B_follower`, Section 9) -- the broad co-movement control;
   this is also the quantity the market-factor null (Section 16c)
   formally tests incremental power against.
3. **Follower's own trailing 30-trading-day realized volatility**
   (daily close-to-close std, from `prices_eod`, point-in-time).
4. **Time-of-day bucket**: opening 30 minutes (09:15-09:45) / midday
   (09:45-14:30) / closing 30 minutes (14:30-15:30), categorical.
5. **Follower's own trailing-60-session turnover rank**, continuous,
   within the follower pool -- captures the within-tier liquidity
   gradient (a follower near the 80th-percentile boundary is not the same
   as one at the 1st percentile).

No control is added or removed after Phase 6 output exists.

---

## Section 12: exclusions

- Pre-open/opening-auction bars and the first completed bar of the
  session (09:15 bar) -- signal and response both start no earlier than
  the second completed bar, after verifying in hand-tracing (Section 21)
  whether the auction period is present in `bars_1min` at all.
- The final 5 minutes of the session (15:25-15:30) as a signal-end
  minute, if the required forward window would cross 15:30 -- the
  observation is dropped, not truncated or carried overnight.
- Any entity-day with fewer than 90% of the expected ~375 one-minute bars
  present (stale/halted that day).
- Entity-dates within +/-1 trading day of a recorded corporate action
  (`corporate_actions` table) for that entity, to avoid adjustment-factor
  edge effects -- reuses the existing table, no second corporate-action
  mechanism is built.
- Any trading day where fewer than 50% of that month's leader tier has a
  valid bar (exchange-wide disruption days) -- the whole day is dropped
  for signal construction that day.

---

## Section 13: missing-data handling

A missing 1-minute bar is treated as "no trade that minute," not as
missing information about price level. For return computation: if the
gap since the last valid bar for that entity that day is **under 3
consecutive minutes**, the last traded price is carried forward
(forward-fill) for return purposes. If the gap is **3 minutes or more**,
the observation touching that gap is **excluded**, not imputed -- a long
flat-filled gap would manufacture a fabricated "no movement" signal rather
than reflect a real absence of trading. This threshold (3 minutes) is
fixed here, before Phase 6 output exists, not tuned afterward.

---

## Section 14: statistical methodology

- **Primary inference**: OLS with **day-clustered standard errors**
  (cluster = `trade_date`), reusing the day-clustering convention already
  established in `box_theory.inference.day_clustered_bootstrap`
  ("trades on the same day are correlated, so resampling draws whole
  trading days... the minimum detectable effect is computed from the
  bootstrap standard error alone, never from the observed mean"). This
  project has no existing multi-entity lead-lag null/SE framework to
  borrow beyond this single-entity precedent (`LEAD_LAG_RECONNAISSANCE.md`
  Section 8, risk 6) -- the day is used as the clustering unit because it
  is the most defensible unit available, not because a multi-entity
  design has been validated here before; this is flagged as the single
  most novel methodological piece of this family, not a routine parameter
  choice.
- **Day-level block bootstrap** (resample whole trading days with
  replacement, 1,000 draws, fixed seed 20261107) as a cross-check on the
  day-clustered SE.
- **Non-overlapping-sample robustness check**: restrict to exactly one
  observation per follower per day, at a single fixed signal-minute per
  day (e.g. the first valid post-exclusion minute each day), to kill
  within-day overlap entirely -- per Part 7.2's explicit instruction to
  include this as a robustness check against overlapping-window
  dependence, reported alongside the primary pooled result, never
  replacing it.
- **No individual-minute-level bootstrap resampling** is used anywhere
  (explicitly prohibited by Part 7.2 -- minute-level resampling would
  shatter the exact cross-sectional/temporal dependence the day-cluster
  approach exists to respect).

---

## Section 15: multiple-testing correction

**Family trial ledger, carried forward verbatim from Phase 2
(`LEAD_LAG_FEASIBILITY.md` Section 6), not re-derived:**

| # | Configuration | Stage examined | Status |
|---|---|---|---|
| 1 | Liquidity-tier grouping (top 20% / bottom 80% by turnover) | Phase 2 feasibility | Adopted as primary mechanism |
| 2 | Statistical-cluster grouping (trailing 252-day correlation) | Phase 2 feasibility | Examined, not adopted -- still counts, carries selection pressure |
| 3 | Horizon = 5 minutes | Phase 2 feasibility (MDE) | Carried into Phase 6 as exploratory |
| 4 | Horizon = 15 minutes | Phase 2 feasibility (MDE) | Carried into Phase 6 as exploratory |
| 5 | Horizon = 30 minutes | Phase 2 feasibility (MDE) | Carried into Phase 6 as secondary |
| 6 | Horizon = 60 minutes | Phase 2 feasibility (MDE) | Carried into Phase 6 as **primary** |

**Total family trial count = 6.** Running the actual Phase 6 regression
at horizons 5/15/30/60 minutes does **not** add new trials -- these are
the same four configurations already counted at the feasibility gate
(per Part 12 Phase 2 and the "any configuration that reached a
pre-registered gate OR was killed at a Phase 1 feasibility check" trial
definition, `PROJECT_CONTEXT.md` Section 3); a configuration is counted
once; running the already-counted configuration to completion is not a
second trial. **This denominator (6) is fixed now and will not be
silently grown later**, per the POC family's own stale-Bonferroni-flag
lesson (`PROJECT_CONTEXT.md` Section 7 finding #15 -- a flag written in a
per-study doc that never escalated to the actual correction applied).

**Primary gate test**: `beta` at h=60 minutes, tested at **Bonferroni
alpha = 0.05 / 6 ≈ 0.0083**, two-sided, against the day-clustered SE.

**Secondary/exploratory horizons** (5, 15, 30 minutes): reported at the
same corrected threshold, for transparency (Part 5: "do not report only
the best-performing horizon"), but **do not gate the Section 20 verdict**
-- only the pre-specified primary (60 minutes) does.

**Secondary FDR report**: Benjamini-Hochberg across the four horizon
results, using the project's own existing implementation
(`factors.ic_eval.benjamini_hochberg`), reported alongside the Bonferroni
result, never substituted for it as the primary correction (Part 7.3).

**The five null/diagnostic checks in Section 16 are not counted as
additional trials in this denominator.** They are necessary conditions on
the interpretation of the one primary test (Section 20), matching the
convention already used across the Liquidity family (passing/failing a
null is part of the gate for a single trial, not a separate corrected
hypothesis competing for significance) -- not an additional multiple-comparisons
problem.

If any new configuration (a new horizon, a new grouping variant, a new
signal-window width) is proposed after this point, it becomes trial #7
and the denominator is updated **before** that configuration's result is
observed, not after.

---

## Section 16: null hypotheses

Five checks, per Part 8. **Adapted explicitly for a continuous,
always-on signal** (Part 4.5's "continuous signal first" design means
there is no sparse, discrete "leader event" the way a threshold-based
study would have -- every completed 5-minute window produces a signal
value) -- each adaptation is stated plainly so it is auditable as a
faithful translation of the master spec's intent, not a loosened
substitute.

**(a) Timing null (circular time-shift)**: for each trading day
independently, the follower's own forward-return series is shifted by a
random offset **within that same trading day** (circular shift, wrapping
at session boundaries), while the leader-signal series keeps its real
timestamps. This preserves each series' own stock identity, trading date,
and time-of-day marginal distribution (Part 8.1's explicit preservation
requirements) while destroying only the **synchronization** between
leader-signal-time and follower-response-time. 1,000 shift draws, fixed
seed 20261107. Real `beta` must exceed the 95th percentile of the
null-draw distribution of `|beta|` (two-sided).

**(b) Selection null (random follower reassignment)**: within each
trading day, follower identities are randomly permuted among that day's
eligible follower pool (same eligibility constraints as Section 7, same
liquidity-tier membership for that month), so the real, correctly-timed
leader signal is paired against a randomly selected follower rather than
the true one. 1,000 permutation draws, fixed seed 20261107. Per the
counterfactual-reuse standing rule (`PROJECT_CONTEXT.md` Section 7 finding
#14), this null **reuses the exact recorded leader-signal values and
timestamps from the real run** -- it never re-runs leader-signal detection
on a different population. Real `beta` must exceed the 95th percentile of
the null-draw distribution.

**(c) Market-factor null**: nested-model comparison -- a restricted model
with `X(j,t)` only (no `S_leader(t)` term) versus the full model
(Section 2). Reported: the partial F-test / incremental R-squared from
adding `S_leader(t)`, and whether `beta`'s significance survives this
comparison. This directly tests whether the leader signal carries
information beyond the follower-pool benchmark and the follower's own
momentum, not merely whether a bivariate correlation exists.

**(d) Reverse-direction diagnostic**: the identical regression with
leader and follower roles swapped (does the follower-pool's aggregate
5-minute signal predict the leader-tier's forward h-minute abnormal
return, same controls, same horizons) -- reported side by side with the
forward-direction result. **Diagnostic only.** Per Part 8.4, this is not
permission to select whichever direction looks better; both directions
are reported regardless of which (if either) passes.

**(e) Placebo diagnostic**: the real follower-day's forward return paired
against a leader signal drawn from a **different, randomly selected
trading day at least 20 trading days away** (same time-of-day minute,
different date), rather than the true contemporaneous signal. This tests
whether the regression apparatus itself manufactures a spurious `beta` out
of shared seasonal/structural artifacts (time-of-day volatility patterns,
etc.) rather than genuine cross-stock timing information. Documented
explicitly to confirm no overlapping information window exists between
the placebo leader-day and the real follower-day (the >=20-trading-day gap
exceeds every horizon tested by at least two orders of magnitude).

---

## Section 17: power and minimum detectable effect (MDE)

Carried forward verbatim from `LEAD_LAG_FEASIBILITY.md` Section 2, computed
**before** this configuration grid was finalized, from observed variance
only, per the standing rule:

```
MDE_h = (z_0.975 + z_0.80) * sigma_h / sqrt(N)
      = 2.80158 * sigma_h / sqrt(2468)
```

| Horizon | sigma (observed, full population) | MDE (alpha=0.05, power=0.80, N=2,468 days) |
|---|---|---|
| 5 min | 24.64 bps | 1.39 bps |
| 15 min | 40.27 bps | 2.27 bps |
| 30 min | 55.05 bps | 3.10 bps |
| 60 min | 74.85 bps | 4.22 bps |

At the Bonferroni-corrected alpha (0.05/6, Section 15), MDE inflates by
~1.54x to **2.1-6.5 bps across horizons** -- still 3-14x below the
economic floor (Section 18). N=2,468 is the full day-clustered ceiling;
Section 17 of `LEAD_LAG_FEASIBILITY.md` additionally verified the design
remains powered even if real signal events (once a detector exists) fire
on as few as ~18% of trading days (N as low as 440 at the 60-minute
horizon against a stricter 10bps floor).

**Claude's pre-committed prediction, stated before Phase 6 runs, for
calibration tracking**: given the structural prior that cost is fixed and
available move grows with horizon (Section "Provenance" above), and given
the 60-minute horizon's own largest sigma, the prediction is that **if
any propagation effect exists, it is more likely to be statistically
visible at 60 minutes than at 5 or 15 minutes** -- the same reasoning used
to select it as primary in Phase 2. This prediction is recorded as a
hypothesis to falsify, explicitly because this project's own calibration
record on this exact kind of coarser-vs-finer manipulation is 0-for-5 in
the Liquidity family, including twice on count/effect direction. A result
showing the *opposite* pattern (effect cleaner at 5 or 15 minutes) would
not be dismissed -- it would be the sixth data point on that same
calibration record.

---

## Section 18: economic significance threshold

The project's own established round-trip cost figure, not invented here:
**20-30 bps** (`PROJECT_CONTEXT.md` Section 8, "a round trip costs roughly
0.2-0.3% regardless of holding period" -- the same figure underlying the
-0.1%-to-0.3%-per-trade band that closed eleven prior intraday families).
This family uses the **stricter bound, 20 bps**, as its economic-significance
threshold.

**Definition**: at a leader-portfolio signal move of +/-1 observed standard
deviation of `S_leader(t)` (to be computed empirically in Phase 6 from the
actual signal series -- not assumed or invented in this document), the
model-implied change in the follower's forward abnormal return
(`beta * 1-sigma-move`) must exceed 20 bps in magnitude to be declared
economically significant, independent of and in addition to statistical
significance at the Bonferroni-corrected threshold (Section 15).

**Inherited caveat, not newly introduced**: the spread/market-impact
component of the broader 20-30bps figure is itself drawn from a
not-yet-independently-validated source (`SPREAD_ESTIMATOR_VALIDATION.md`:
specification complete, 24-name sample selected, **zero days of live
collection exist yet** as of this writing) and from a single prior
observation (Corwin-Schultz/Roll overstate Indian spreads by 12-31x,
`PROJECT_CONTEXT.md` Section 7 finding #2). This family does not wait on
that pending validation to run its own measurement study (the statutory
cost components alone -- STT, stamp duty, exchange charge, SEBI fee, GST
-- are known and sufficient to define a conservative floor), but explicitly
flags that the 20bps figure carries the same unresolved uncertainty every
other family in this project currently carries, and does not claim it as
newly validated here.

---

## Section 19: execution-cost assumptions (for any future trading simulation)

**Not specified in this document.** Per Part 9's explicit prohibition on
folding execution/cost/stop-loss machinery into the primary measurement
study ("Do not automatically create a trading strategy just because the
predictive regression is statistically significant... Do not change the
measurement study after observing results"), any trading-simulation cost
model is deferred entirely to a **separate Phase 7 preregistration**,
written only if Section 20's measurement gate passes, and only after
separate human approval. This section exists as a placeholder to confirm
the omission is deliberate, not an oversight.

---

## Section 20: verdict rules

**PASS requires ALL of the following; any single failure is a FAIL,
closing the measurement study automatically, per this project's own "a
failed DEV study is closed automatically" rule:**

1. **Primary test**: `beta` at h=60 minutes is statistically significant
   at the Bonferroni-corrected alpha (0.0083, two-sided), using the
   day-clustered SE, with a sign that is economically interpretable
   (i.e., consistent with the proposed information-diffusion mechanism,
   not an unexplained opposite-sign result that would itself require a
   fully separate account before being treated as support for the
   hypothesis).
2. **Economic magnitude**: the Section 18 implied effect at +/-1 sigma of
   `S_leader` exceeds the 20bps floor.
3. **Timing null**: real `|beta|` exceeds the 95th percentile of the
   circular-shift null distribution (Section 16a).
4. **Selection null**: real `|beta|` exceeds the 95th percentile of the
   random-follower-reassignment null distribution (Section 16b).
5. **Market-factor null**: the leader-signal term's incremental
   contribution (Section 16c) is both statistically distinguishable from
   zero and not reducible to the follower-pool benchmark / own-momentum
   controls alone.
6. **Stage-count reconciliation** (`OPERATIONS.md` standing rule, line
   ~1481): leader-tier construction -> signal construction -> follower-eligibility
   filtering -> final regression sample row counts reconcile against each
   prior stage at every step, with no unexplained discrepancy, checked
   **before** any of the above numbers are interpreted.

**A PASS here means**: the measurement study found a statistically and
economically significant, null-surviving, incrementally-informative
cross-stock lead-lag relationship at the preregistered primary horizon,
sufficient to justify a separate, independently preregistered Phase 7
trading-simulation study, subject to its own human approval gate.

**A PASS here does NOT mean**: that a live, tradeable edge exists, that
execution costs (still using an unvalidated spread/impact component, per
Section 18) have been fully accounted for, or that any historical
holdout-style validation has occurred -- the project's historical holdout
is retired; this is a DEV-only result by definition, per project-wide
convention.

---

## Section 21: failure conditions (beyond the headline gate)

Flagged explicitly as conditions that invalidate a nominal PASS even if
Section 20's six checks all clear on the pooled sample, to be checked
before declaring victory, not after a disappointing TEST-equivalent
result (this family has no sealed TEST/holdout at all, so these
within-DEV robustness checks are the only check this family will ever
get):

1. **Sign instability**: `beta`'s sign flips in more than 1 of the ~10
   annual sub-samples (year-by-year re-estimation, descriptive, reported
   regardless of the headline result).
2. **Non-overlapping-sample check fails**: the Section 14
   non-overlapping-sample robustness regression does not reproduce a
   result of the same sign and broadly comparable magnitude to the pooled
   result.
3. **Signal sparsity**: if, once Phase 4/6 code is built, real
   leader-signal events (defined loosely as `|S_leader(t)|` exceeding some
   descriptive threshold, reported but not used to gate) turn out to fire
   on fewer than ~18% of trading days (the Phase 2 break-even floor at the
   stricter 10bps bound, 60-minute horizon) -- this is a trigger to
   re-examine power before trusting the pooled result, not an automatic
   fail, but must be checked and reported either way.
4. **10bps robustness check fails**: re-running Section 20's economic
   test at the stricter 10bps floor (rather than 20bps) changes the
   verdict -- reported explicitly either way, per Phase 2's own
   pre-committed robustness framing.

---

## Section 22: reproducibility requirements

- This document is committed alone; the exact commit hash is recorded
  below once committed (Part 7's explicit requirement).
- All DuckDB access in Phase 4-6 uses `duckdb.connect(path,
  read_only=True)` or the project's `get_read_connection()` helper --
  no write connection is ever opened against `fibo_intraday.duckdb` or
  `warehouse.duckdb` by this family.
- Fixed random seed **20261107** for every null/bootstrap draw (timing
  null, selection null, block bootstrap), stated here, not chosen per-run.
  1,000 draws for each of the three randomized procedures, stated here,
  not adjusted after seeing preliminary results.
- Per the project's standing checkpointing rule and the Phase 2 finding
  that an unchunked full-table scan OOMs on this machine
  (`LEAD_LAG_FEASIBILITY.md` Section 3): the full DEV run **must** be
  chunked (by calendar year, matching the pattern already proven to work
  in Phase 2, ~4 minutes total for a full 386-entity/10-year/4-horizon
  variance scan) and must checkpoint per chunk, persisting intermediate
  sufficient statistics so a killed run can resume without
  recomputation or duplicated observations.
- Hand-tracing (Part 11.8) of at least five representative observations
  -- a successful positive leader signal, a successful negative leader
  signal, a failed prediction, a missing/stale-bar case, and a
  session-boundary case -- is required and must be recorded in
  `FINDINGS_LEAD_LAG_V1.md` **before** the aggregate DEV result is
  accepted, per Part 12 Phase 5.

---

## Status

**Preregistration drafted 2026-11-07.** Phases 0-2 complete and read-only
(`lead_lag/LEAD_LAG_RECONNAISSANCE.md`, `lead_lag/DATA_AUDIT_LEAD_LAG.md`,
`lead_lag/LEAD_LAG_FEASIBILITY.md`). No `src/lead_lag/` code exists yet.

**Per Part 12 Phase 3's explicit instruction, this family now STOPS for
human review.** The completed audit, feasibility assessment, and this
preregistered methodology are presented for approval. **Implementation
(Phase 4) does not begin, and no outcome analysis of any kind is run,
until this document is committed on its own and the user explicitly
approves proceeding.**

Commit hash: _to be filled in after this file is committed alone._
