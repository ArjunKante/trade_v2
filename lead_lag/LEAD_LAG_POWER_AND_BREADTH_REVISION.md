# Lead-Lag Power and Breadth Revision (amendment-support analysis)

Read-only analysis supporting an amendment to `PREREGISTRATION_LEAD_LAG_V1.md`,
run against the state of the repo as of this writing. **No existing file was
modified.** All DuckDB access via `duckdb.connect(path, read_only=True)`.
All code lives in throwaway scripts in the session scratchpad (not
committed): `task1_monthly_tiers.py`, `task2_breadth.py`,
`task3_build_dataset.py`, `task3_placebo_bootstrap.py`. Every number below is
reproducible from the inline SQL/logic described in each section.

**This is feasibility/power-analysis work, not outcome analysis.** No
regression anywhere in this document pairs a leader-tier signal with a
contemporaneous, correctly-timed follower response. Task 3's only regression
is the preregistration's own Section 16e placebo diagnostic (leader signal
deliberately drawn from a different day >=20 trading days away), whose
fitted coefficient is zero by construction and is used purely to measure the
estimator's own sampling-noise/dependence structure.

---

## Top-level verdict

**The power conclusion changes materially, but not primarily for the reason
anticipated.** Two independent problems were found:

1. **Methodology problem (a), confirmed and quantified**: the real,
   point-in-time, trailing-60-session monthly leader/follower split
   (Section 6) is **~40 leaders / ~160 followers**, roughly **half** the
   breadth of Phase 2's 77/309 lifetime-turnover-proxy figure. This is a
   real, reproducible finding (Task 1) — but it is a breadth-count
   correction, not a power failure; 40/160 is still an operationally ample
   candidate set.

2. **Methodology problem (b), and a new, more serious finding not
   anticipated by the methodology review**: attempting the actual
   dependence-aware SE computation (Task 3) surfaced that **the literal
   Section 8/9 `S_leader(t)` construction is algebraically degenerate** —
   it evaluates to (numerically indistinguishable from) exactly zero
   whenever the leader tier has complete 1-minute data, which Task 2 shows
   is the overwhelming norm. This is a mathematical identity, not a
   data-quality artifact: averaging each leader's leave-one-out deviation
   from the *other leaders'* mean, back across that *same* leader group,
   sums to zero by construction (derivation in Task 3). **This means the
   preregistration's primary predictor, as literally specified, carries no
   usable cross-sectional variation to regress a follower response
   against — a bigger problem than an overstated MDE.**

Given finding 2, **no unconditional power "PASS" can be issued** for the
preregistration as literally written — the primary regression cannot be
run as specified until Section 8/9 is fixed. This document instead reports
(i) the real breadth correction (Task 1/2, solid, usable as-is), and (ii) a
placebo-bootstrap SE/MDE pilot computed on a clearly-labeled **diagnostic
substitute signal**, which supports a conditional statement: *if* Section
8/9 is repaired in a way that yields a leader-portfolio signal of
broadly similar scale to the diagnostic substitute used here, the
day-clustered dependence structure does not appear to blow up the MDE by
orders of magnitude — but this is explicitly not the same as re-affirming
Phase 2's 5-20x margin, because that margin was never computed on a signal
that actually exists. See Task 3 for the full honest accounting, including
why even the *conditional* number should not be read as precise.

---

## Task 1: real monthly leader/follower tier breadth (Section 6, run literally)

### Method

`fibo.universe.reconstitute_annually(con, top_n=200)` (read-only, unmodified)
gives the point-in-time, annually-reconstituted top-200-by-turnover
universe for each year; `fibo.universe.effective_universe(..., stub_year=2016)`
(the project's own existing convention for the first-year gap) supplies a
membership list for Oct-Dec 2016, which has no preceding full year to rank
against. For each calendar month in the `fibo_intraday.duckdb` date range
(2016-10-04 to 2026-09-18, 120 months), on that month's first trading day
(per the intraday store's own trading-day calendar), every entity in that
year's annual universe is ranked by trailing-60-trading-session median daily
rupee turnover (`prices_eod.turnover`, raw, via a direct `prices_eod` +
`isin_lineage` join — the full adjusted entity panel via
`read_full_entity_panel_authorized` triggered a `MemoryError` in this
environment on both of two attempts' first try, succeeded on a retry; the
lighter direct-turnover query, which needs no adjustment factors since
turnover is split-invariant, was used throughout for reliability and speed).
An entity with fewer than 60 trailing sessions of prior history as of the
ranking date is excluded from that month's eligible pool (no NaN trailing
median). Top 20% of the eligible pool (`ceil(0.2 * n_eligible)`) = leaders;
remainder = followers.

### Result

| Year | n_months | eligible min/med/max | leaders min/med/max | followers min/med/max |
|---|---|---|---|---|
| 2016 (stub) | 3 | 193/194/195 | 39/39/39 | 154/155/156 |
| 2017 | 12 | 196/200/200 | 40/40/40 | 156/160/160 |
| 2018 | 12 | 198/200/200 | 40/40/40 | 158/160/160 |
| 2019 | 12 | 200/200/200 | 40/40/40 | 160/160/160 |
| 2020 | 12 | 196/200/200 | 40/40/40 | 156/160/160 |
| 2021 | 12 | 194/200/200 | 39/40/40 | 155/160/160 |
| 2022 | 12 | 189/200/200 | 38/40/40 | 151/160/160 |
| 2023 | 12 | 198/200/200 | 40/40/40 | 158/160/160 |
| 2024 | 12 | 189/200/200 | 38/40/40 | 151/160/160 |
| 2025 | 12 | 181/200/200 | 37/40/40 | 144/160/160 |
| 2026 | 9 | 187/200/200 | 38/40/40 | 149/160/160 |

91 of 120 months (76%) sit at the steady-state 200 eligible / 40 leaders /
160 followers. The other 29 months are **every single January, February,
and March** of nearly every year (plus the three stub months of 2016) — a
recurring **post-reconstitution dip**: a handful of names newly entering
that year's top-200 annual universe on Jan 1 have not yet accumulated 60
trading sessions of history by the time January/February/March's ranking
date arrives (most likely driven by ISIN-lineage chain restarts or genuine
recent listings among the lowest-ranked new entrants), and the eligible
pool recovers to the full 200 by April every single year, without
exception. The worst month observed anywhere in the 10-year range is
**2025-01: 181 eligible, 37 leaders, 144 followers**.

Full per-month table (120 rows) is in the scratchpad CSV
(`task1_monthly_tiers.csv`); every sub-200-eligible month:

```
month   n_eligible  n_leaders  n_followers
2016-10    193         39         154
2016-11    194         39         155
2016-12    195         39         156
2017-01    196         40         156
2017-02    198         40         158
2017-03    198         40         158
2018-01    198         40         158
2018-02    199         40         159
2020-01    196         40         156
2020-02    197         40         157
2020-03    198         40         158
2021-01    194         39         155
2021-02    196         40         156
2021-03    198         40         158
2022-01    189         38         151
2022-02    189         38         151
2022-03    193         39         154
2023-01    198         40         158
2023-02    198         40         158
2023-03    198         40         158
2024-01    189         38         151
2024-02    189         38         151
2024-03    193         39         154
2025-01    181         37         144
2025-02    184         37         147
2025-03    187         38         149
2026-01    187         38         149
2026-02    189         38         151
2026-03    196         40         156
```

### Finding: 2017-2019 are NOT materially thinner than later years

The task hypothesis — that 2017-2019 might show materially smaller tiers
because `LEAD_LAG_FEASIBILITY.md` Section 1b found only 153/386 entities had
sufficient trailing history in one correlation-window check — **does not
hold for the Section-6 construction actually used here.** 2017-2019 look
statistically identical to every later year (198-200 eligible, 40 leaders,
156-160 followers), because the annual universe itself is already capped
at 200 names, and by the time an entity is already a member of a given
year's top-200 annual list, it has almost always also been trading
continuously for well over 60 sessions (membership in the annual top-200
requires a full prior qualifying year of turnover in the first place). The
thinness that Phase 2 Section 1b found was about a *different* mechanism
(statistical-cluster correlation windows needing 252 days of history across
the full 386-name *lifetime* set, most of which fell out of later top-200
lists) — it does not transfer to the liquidity-tier construction actually
adopted.

### Headline correction to Phase 2's 77/309

**The real monthly construction gives ~40 leaders / ~160 followers (40/160
in 91 of 120 months, dipping to as low as 37/144 for three months in
2025), not 77/309.** This is because Phase 2's proxy used **lifetime total
turnover across all 386 entities ever observed in the 10-year intraday
archive** (top 20% of 386 = 77), whereas the real Section 6 construction
operates **within each year's current 200-name annual top-turnover
universe** (top 20% of ~196-200 = ~39-40). The real breadth is **roughly
half** of what Phase 2 assumed. This does not change the *qualitative*
feasibility conclusion (40/160 is still an operationally large candidate
set, zero new infrastructure needed, no survivorship surprises), but it is
a real, previously-unverified number that the amendment should carry
forward in place of 77/309.

---

## Task 2: per-minute leader-signal breadth distribution

### Method

For one representative, steady-state (`n_eligible == 200`) month per year
(Nov 2016, then June of 2017-2026 — 11 months total), using that month's
real leader tier from Task 1, every completed 1-minute bar
(`bars_1min`, 09:15-15:29, 375 bars/day) across every trading day in that
month was pulled for that month's leader-tier entities only. A bar is
"valid" if open/high/low/close/volume are all non-null; `n_t` = count of
valid-bar leader entities at each (trade_date, ts). Zero-volume bars are
counted as valid-but-flagged (reported, not dropped).

### Result

Per-month (unfiltered, includes the 09:14 pre-open/auction bar where
present):

| Month | n_leaders_tier | overall p1/p5/p10/p25/p50 | zero_vol_frac |
|---|---|---|---|
| 2016-11 | 39 | 35/35/35/35/35 | 0.0 |
| 2017-06 | 40 | 35/35/35/35/35 | 0.0 |
| 2018-06 | 40 | 33/33/33/33/33 | 0.0 |
| 2019-06 | 40 | 35/35/35/35/35 | 0.0 |
| 2020-06 | 40 | 38/38/38/38/38 | 0.0 |
| 2021-06 | 40 | 39/39/39/39/39 | 0.0 |
| 2022-06 | 40 | 39/39/39/39/39 | 0.0 |
| 2023-06 | 40 | 38/38/38/38/38 | 0.0 |
| 2024-06 | 40 | 38/39/39/39/39 | 0.0 |
| 2025-06 | 40 | 40/40/40/40/40 | 0.0 |
| 2026-06 | 40 | 40/40/40/40/40 | 0.0 |

Zero-volume bars: **1 out of 3,224,355 valid leader-tier bars pooled across
all 11 months (3.1e-7 fraction)** — leaders are effectively never
illiquid at the 1-minute level, consistent with Phase 1's project-wide
spot-check finding (0.0041% zero-volume overall, and leaders are by
definition the most liquid subset).

**Session-boundary artifact found and corrected**: the single worst minute
in two of the eleven months (2021-06, 2022-06) was `n_t = 1` at `ts =
09:14:00` — this is the pre-open/opening-auction bar, which
Section 12 already excludes by design ("signal and response both start no
earlier than the second completed bar"). After dropping bars before 09:15
(matching Section 12 exactly), the pooled distribution (86,250 leader-tier
minute-observations, `frac = n_t / n_leaders_tier`) is:

| Percentile | 0.1 | 1 | 5 | 10 | 25 | 50 |
|---|---|---|---|---|---|---|
| frac (overall / opening-30 / closing-30, identical at this resolution) | 0.825 | 0.825 | 0.825 | 0.875 | 0.875 | 0.95 |

The single genuine worst-case minute within the regular session is
`2020-06-11 14:21:00`, `n_t = 13/40` (32.5%) — one isolated day/minute, not
a systemic pattern; the next-worst cases are 32/40 (80%, 2018-06-08 and
2018-06-21). Opening-30 and closing-30 windows show **no distinguishable
difference** from the overall distribution at this percentile resolution —
leader-tier staleness does not concentrate at the open or close in this
sample.

### Recommended floor

**Require `n_t >= 0.80 * (that month's leader-tier size)` before computing
a signal for that minute.** This threshold:
- Excludes **~0.001% of minutes** (effectively only the single 2020-06-11
  outlier) — a small, reportable, well-justified exclusion, not an
  arbitrary round number.
- A stricter floor (0.90 or 0.95) would discard **35.7% of all minutes**
  that are actually fine (just 2-7 of 40 leaders missing a bar by routine
  chance, not real staleness) — clearly overkill given the data.
- A looser floor (below ~0.80) buys nothing further, since the next cliff
  down is the single extreme outlier itself.

---

## Task 3: placebo-based, dependence-aware SE and power pilot

### 3.0 Critical finding: the literal Section 8/9 `S_leader(t)` is degenerate

Before any placebo pairing was attempted, Section 8/9's real `S_leader(t)`
was computed exactly as specified, using Task 1's real monthly leader
tiers, across the same 11 sampled months (one fixed signal-minute per day,
10:15, chosen to keep the pilot tractable — see 3.1):

```
B_leader(k)     = equal-weighted mean of r(i',k) over OTHER leaders i' != i
AR_leader(i,k)  = r(i,k) - B_leader(k)
S_i(t)          = sum_{k=t-4}^{t} AR_leader(i,k)
S_leader(t)     = mean_i( S_i(t) )   [over leaders with a valid S_i(t)]
```

**Observed, across 230 real trading days: mean = -1.8e-21, sigma =
4.2e-20.** This is not "small" in an economic sense — it is at
floating-point machine-epsilon scale, **16+ orders of magnitude below one
basis point**. This is not a data problem; it is an algebraic identity.
Derivation: writing the leave-one-out mean as
`LOO_i(k) = (sum_all(k) - r_i(k)) / (n-1)`, algebra gives
`AR_leader(i,k) = r_i(k) - LOO_i(k) = n/(n-1) * (r_i(k) - mean_all(k))` —
i.e., each leader's "leave-one-out abnormal return" is just a *rescaled*
version of its ordinary deviation from the full leader-group mean. Summing
(or averaging) any set of deviations-from-their-own-group-mean across that
*same* group is **identically zero**, for any data, always — this is the
same identity that makes residuals from an OLS regression against a
constant sum to zero. Section 8's step of averaging these `S_i(t)` values
back across the same leader tier that `B_leader` was computed from
(Section 9) reconstitutes exactly this zero-sum identity. Task 2 confirms
leader-tier breadth is virtually always complete (zero-volume fraction
3e-7, `n_t` at or near full tier size in the overwhelming majority of
minutes) — so this is not a rare edge case rescued by occasional
missingness; it is the dominant, essentially universal behavior.

**This appears to be a genuine gap in both Phase 2 and the preregistration
itself**: Phase 2's MDE calculation (`LEAD_LAG_FEASIBILITY.md` Section 2)
computed `sigma` only from the **follower-side forward-return** series,
never from `S_leader(t)` itself. The preregistration's own Section 18
explicitly defers computing `S_leader`'s empirical sigma to "Phase 6, from
the actual signal series" — this document is the first time anyone has
actually computed it, and it reveals the predictor side of the primary
regression has no real variance to regress against, as literally
specified. **This is a correctness/design problem for Section 8/9 to fix
at Phase 4, not a power-calibration issue** — no amount of additional
sample size or better bootstrap technique fixes a predictor that is
identically zero by construction.

A plausible fix for Phase 4 to consider (not adopted or endorsed here,
since redesigning Section 8/9 is out of this task's scope): benchmark
leaders against a broader or disjoint pool when building the *pooled*
signal `S_leader(t)` (e.g., against the full eligible universe, or against
the follower pool), rather than collapsing each leader's leave-one-out
deviation from the *other leaders* back into a group-mean scalar over
that *same* group. The follower side of Section 9 does not have this
problem, because `AR_follower(j,t->t+h)` is *never* collapsed into one
pooled scalar — each follower's individual, idiosyncratic abnormal return
is kept and used as its own response observation.

### 3.1 Diagnostic substitute signal, used only for this pilot

To still produce the requested placebo-bootstrap SE/power pilot, a
clearly-labeled, non-degenerate **diagnostic substitute** was used in place
of the broken `S_leader(t)`:

```
S_leader_proxy(t) = mean_leaders(trailing-5min raw return) - mean_universe(trailing-5min raw return)
```

(equal-weighted leader-group mean minus equal-weighted full-eligible-pool
mean, same 5-minute trailing window). This is **not a redefinition of the
preregistration** — it is a stand-in used solely to exercise the placebo
machinery and measure the day-dependence structure, which is a property
of the data's cross-sectional/serial correlation and the day-clustering
mechanism, not primarily of which exact signal formula is plugged in.
Observed: mean = -4.1e-5 (-0.41 bps), sigma = 3.92e-4 (3.92 bps) — a
sane, non-degenerate order of magnitude.

### 3.2 Scope reduction (documented, per the task's explicit allowance)

Running the full Section 16e placebo construction at every minute across
all 2,468 trading days was not attempted. Instead, mirroring the
preregistration's **own existing non-overlapping-sample robustness
convention** (Section 14: "one observation per follower per day, at a
single fixed signal-minute per day"), a **single fixed signal-minute,
10:15**, was used for every day in the 11 sampled months (same months as
Task 2), well clear of the session open/close and the 5-bar/60-bar windows
it needs (10:10-11:15 pulled per entity per day). The resulting dataset:
**230 real trading days (the clustering unit), 29,772 (follower, day)
response rows**, `AR_follower(j, D_r, 10:15->11:15)` computed exactly per
Section 2/9 (60-minute forward abnormal return, follower benchmarked
against the OTHER followers that month, leave-one-out). As a cross-check:
this sub-sample's observed `AR_follower` sigma is **74.52 bps**, matching
Phase 2's full-population 60-minute sigma (74.85 bps) to within 0.4% —
the sampled-month subsetting did not distort the follower-side variance.

Controls included: follower's own trailing-5-min raw return; follower-pool
LOO benchmark return over the same window (`B_follower`); follower's
trailing-60-session turnover-rank percentile within that month's follower
pool (reusing Task 1's trail60 computation). **Omitted, as explicitly
permitted**: trailing-30-day realized volatility (tractability). **Dropped
as collinear with the intercept**: the time-of-day-bucket control, because
fixing one signal-minute per day makes it constant (always "midday") —
a direct, documented consequence of the non-overlapping-sample scope
reduction, not an oversight.

### 3.3 Placebo construction and an ambiguity in Section 16e worth flagging

Section 16e's text ("for each ... row ... pair ... against `S_leader`
drawn from a different ... trading day D_s") is read literally per-row, but
is genuinely ambiguous about whether each (follower, day) row draws its
*own independent* placebo day, or whether all followers on the same real
day `D_r` share *one* randomly drawn placebo day `D_s` (which is how the
real, non-placebo `S_leader(t)` actually works in Section 2's model — one
value per day broadcast to every follower that day). **Both readings were
implemented**, since they give materially different answers:

- **Per-row independent draw** (each follower-day row gets its own random
  `D_s`): `SE_boot = 0.1120`, naive (single-fit, non-clustered) SE =
  0.1106, design effect `(SE_boot/SE_naive)^2 = 1.03`.
- **Per-real-day shared draw** (every follower on the same real day `D_r`
  shares one random `D_s`, matching how `S_leader(t)` is actually used in
  Section 2): `SE_boot = 0.0347`, naive SE = 0.1166, design effect = 0.089.

The second reading gives a *smaller* bootstrap SE than the naive formula —
the opposite of the usual "clustering inflates uncertainty" expectation.
A plausible mechanism: Section 9's leave-one-out follower benchmark is
specifically designed to strip out common same-day/market comovement from
each follower's `AR_follower`, which is exactly the kind of within-day
residual correlation that would otherwise justify a large clustering
penalty — so there may be little common-day signal left in the residuals
for clustering to inflate. This is a plausible, not confirmed, explanation;
the two readings disagree by >10x, which itself is the honest finding:
**this diagnostic is sensitive to a construction detail the
preregistration does not pin down, and Phase 4 should resolve that
ambiguity explicitly before relying on any one number.**

**The larger (more conservative) of the two, `SE_boot = 0.1120`, is used
for all MDE/power figures below**, as the more cautious choice.

### 3.4 Block bootstrap: achieved scale

Both day-clustered block bootstraps (resampling the 230 real response
days with replacement, matching `box_theory.inference.day_clustered_bootstrap`'s
cluster-resampling spirit; a fresh random placebo-day pairing redrawn every
replicate, never reused) **achieved the full target of 500/500 replicates,
in 2.2-2.4 seconds of wall-clock time each**. This is far inside the
tractable range — no chunking or checkpointing was needed at this (reduced,
11-month) scope. Scaling to the full 2,468-day population was not
attempted (a 11-month sample was judged sufficient for this SE/power
*pilot*, per the task's explicit allowance to reduce scope and document
it); a rough, explicitly-flagged extrapolation is given below.

### 3.5 MDE, power, and effective-N

Using `SE_boot = 0.1120` (coefficient units, conservative reading):

| Alpha | z-critical | MDE (coefficient units) |
|---|---|---|
| 0.05 (uncorrected) | 1.95996 | **0.3138** |
| 0.05/6 (Bonferroni, Section 15) | 3.1909 | **0.3898** |

**Converting to bps-of-`AR_follower`-at-±1σ(`S_leader_proxy`)**, using the
*proxy's own* observed sigma (3.92e-4) — flagged explicitly as
illustrative only, since this number is specific to the ad hoc proxy and
is **not** a reliable stand-in for whatever sigma a corrected Section 8/9
signal will actually have:

- MDE (uncorrected) ≈ 0.3138 x 3.92e-4 ≈ **1.23 bps**
- MDE (Bonferroni) ≈ 0.3898 x 3.92e-4 ≈ **1.53 bps**

At the three requested economic magnitudes (10/20/30 bps, converted to
coefficient units via the proxy's sigma: `beta_needed = econ_bps /
sigma_proxy`, giving beta_needed = 2.55 / 5.11 / 7.66), power against
`SE_boot = 0.1120` is **>0.9999 at all three magnitudes and both alpha
levels** — but this triviality is a direct artifact of the proxy's small
sigma relative to `SE_boot`, not a trustworthy real-world power
statement, for the reason stated in 3.0: the proxy is not the real signal.

**Effective sample size / design effect**: using the conservative (per-row)
reading, the ratio `(SE_boot/SE_naive)^2 = 1.03` — day-clustering barely
inflates uncertainty relative to a naive IID assumption *in this specific
placebo construction*. Using the alternative (per-real-day-shared) reading,
the ratio is 0.089 (net *deflation*). Given the two readings disagree by an
order of magnitude, **no single precise effective-N number is reported as
settled** — this is stated as a limitation, not resolved by picking
whichever number looks better.

**Illustrative-only full-sample extrapolation** (naive `sqrt(N_days)`
scaling, NOT an actual computation on the full 2,468-day population,
flagged explicitly as a projection): if the same per-day dependence
structure held uniformly across the full population,
`SE_boot_full ~= SE_boot * sqrt(230/2468) ~= 0.0342`, giving MDE
(uncorrected) ~= 0.0958 coefficient units ~= 0.38 bps (via the proxy's
sigma) — tighter than the 11-month pilot, as expected with more data, but
this number should not be quoted as a committed finding.

### 3.6 Honest limitations (per the task's explicit instruction)

1. **The headline predictor is degenerate as literally specified (3.0).**
   This alone is sufficient reason not to issue an unconditional power
   PASS for the preregistration as written — the primary regression
   cannot be run until Section 8/9 is fixed, independent of any SE/MDE
   number.
2. **All quantitative SE/MDE/power figures in 3.4-3.5 are computed on a
   diagnostic substitute signal, not the real (to-be-fixed) `S_leader(t)`.**
   Their bps-converted values are illustrative only; only the
   coefficient-unit MDE is even moderately robust to this substitution,
   and even that depends on the dependence structure of a design that may
   change once Section 8/9 is corrected.
3. **Two defensible readings of the placebo-pairing mechanics (3.3) give
   SE estimates differing by >10x.** The preregistration should pin this
   down explicitly before Phase 4.
4. **This is a null/placebo-structured SE.** If a real propagation effect
   exists, the residual variance under the true (non-null) data-generating
   process could differ from the null case — usually a second-order
   effect, but named here explicitly, per the task's instruction.
5. **Scope was reduced to 11 months / 230 days / one fixed signal-minute
   per day**, out of the full 2,468-day, continuous-signal design the
   preregistration specifies. The 500/500-replicate bootstrap achieved
   full target scale easily (2.2-2.4s each) at this reduced scope; a
   full-scale run was not attempted and its cost is not characterized
   here beyond the naive extrapolation in 3.5, which is explicitly not a
   substitute for actually running it.

**Given all of the above, this document does not claim an unconditional
feasibility PASS for the power/dependence-structure question.** The
breadth correction (Task 1/2) is solid and should be adopted. The power
question cannot be answered until Section 8/9's degeneracy is fixed and
the placebo-pairing ambiguity (3.3) is resolved; conditional on a fix of
similar scale to the diagnostic proxy used here, the preliminary signs
(design effect near 1, achievable bootstrap at full target scale, MDE in
bps still comparable to or smaller than Phase 2's original claim) are not
alarming — but "not alarming" is a materially weaker statement than
Phase 2's original "5-20x margin," and should be reported to the user as
such, not rounded up to a renewed PASS.

---

## Files referenced (absolute paths)

- `C:\projects\trade-new\PREREGISTRATION_LEAD_LAG_V1.md`
- `C:\projects\trade-new\lead_lag\LEAD_LAG_FEASIBILITY.md`
- `C:\projects\trade-new\lead_lag\DATA_AUDIT_LEAD_LAG.md`
- `C:\projects\trade-new\src\fibo\universe.py` (`reconstitute_annually`,
  `effective_universe` — reused read-only, unmodified)
- `C:\projects\trade-new\src\data_layer\entity_panel.py`
  (`read_full_entity_panel_authorized` — attempted, `MemoryError` on first
  try in this environment, succeeded on retry; direct `prices_eod` query
  used throughout instead for reliability)
- `C:\projects\trade-new\src\box_theory\inference.py`
  (`day_clustered_bootstrap` — cluster-resampling convention mirrored)
- `C:\projects\trade-new\data\fibo_intraday.duckdb`,
  `C:\projects\trade-new\data\warehouse.duckdb` (read-only access only)

Throwaway scripts (session scratchpad, not committed):
`task1_monthly_tiers.py`, `task2_breadth.py`, `task3_build_dataset.py`,
`task3_placebo_bootstrap.py`, plus their saved intermediate outputs
(`task1_monthly_tiers.csv`, `task1_leader_lists.pkl`, `task2_results.pkl`,
`task3_signal_df.pkl`, `task3_response_df.pkl`, `task3_boot_betas.npy`,
`task3_summary.json`).
