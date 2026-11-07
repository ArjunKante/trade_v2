# Lead-Lag Feasibility and Power Analysis (Phase 2)

Read-only analysis, run against commit `c2a0d62` (plus the two uncommitted
Phase 0/1 docs this builds on: `LEAD_LAG_RECONNAISSANCE.md`,
`DATA_AUDIT_LEAD_LAG.md`). **No strategy code, no trading simulation, no
file written or modified other than this one.** All DuckDB access via
`duckdb.connect(path, read_only=True)`, run from throwaway scripts in the
session scratchpad (not committed), SQL reproduced inline below so every
number is re-derivable. Grouping-mechanism scope is fixed by the human
user's binding design decision (sector-agnostic; statistical-cluster
and/or liquidity-tier only) — not revisited here.

---

## 0. Verdict up front

**PASS.** The computed Minimum Detectable Effect (MDE) at every candidate
horizon (1.4-4.2 bps) is 5-20x *smaller* than this project's own
established economic-significance floor for a round-trip trade (20-30 bps,
`PROJECT_CONTEXT.md` §8). This is the opposite failure mode from the
Portfolio-construction and Combination studies (MDE 10-20x *larger* than any
plausible effect) — here the sample is **more than adequately powered** to
resolve an effect of tradeable size, conditional on the realistic
clustering-unit sample ceiling (~2,468 trading days) holding up once an
actual leader-signal detector is built. Recommendation: **proceed to Phase
3 (preregistration) using the liquidity-tier grouping mechanism and a
60-minute primary horizon**, per the evidence below.

---

## 1. Grouping-mechanism recommendation: liquidity-tier (primary), statistical-cluster (not needed to pass this gate)

### 1a. Liquidity-tier candidate structure (evidence)

Using `data/fibo_intraday.duckdb`'s own `bars_1min` table, total turnover
(`SUM(close * volume)`) per entity across its full available history:

```sql
SELECT entity_id, SUM(close*volume) AS total_turnover,
       COUNT(*) AS n_bars, COUNT(DISTINCT trade_date) AS n_days
FROM bars_1min GROUP BY entity_id;
```

- **386 distinct entities** (matches `DATA_AUDIT_LEAD_LAG.md` area 1 exactly
  — stage-reconciliation check passes).
- Top 20% by total turnover = **77 "leader" candidates**; bottom 80% =
  **309 "follower" candidates** — exactly the master spec §3.3 default
  split.
- Candidate leader x follower cross-pairs: **77 x 309 = 23,793** — this is
  the full cross-product if the design pairs every leader with every
  follower; a many-to-pool design (one leader's signal evaluated against
  the pooled 309-name follower population, the more natural reading of a
  "tier" mechanism) needs no pairing at all, just 77 leader-signal series
  and one pooled follower-return series per day. Either framing has ample
  breadth — eligible-pair count is not the binding constraint (§4 below).
- **Zero new infrastructure required.** This reuses the existing
  point-in-time annually-reconstituted top-200-by-turnover universe
  convention (`fibo.universe.reconstitute_annually`) already used,
  unmodified, by Box Theory, FVG, POC, and Liquidity A-D (per
  `LEAD_LAG_RECONNAISSANCE.md` §2). No new point-in-time correctness risk.

### 1b. Statistical-cluster candidate structure (evidence)

Trailing 252-trading-day daily-close correlation (most recent ~380
calendar days of `bars_1min`, aggregated to one close/entity/day via
`LAST(close ORDER BY ts)`), as a representative point-in-time-style
snapshot — not the final preregistered trailing window, just an
order-of-magnitude check:

```sql
SELECT entity_id, trade_date, LAST(close ORDER BY ts) AS close
FROM bars_1min WHERE trade_date >= ? GROUP BY entity_id, trade_date;
```

- Only **153 of the 386 entities** have sufficient (>=200 of 252) non-null
  daily closes in this most-recent window — the rest fell out of the
  annually-reconstituted top-200 in earlier years and stopped being
  fetched, confirming `fibo.universe`'s own "386 > 200 because membership
  turns over" framing from the data audit, and showing a statistical-cluster
  design must handle entity entry/exit explicitly (every year's cohort is
  smaller than 386).
- Of the 11,628 pairs evaluable among those 153 names: 44.0% have
  `|corr| >= 0.3`, 19.9% `>= 0.4`, 5.7% `>= 0.5`, 1.3% `>= 0.6`, 0.36%
  `>= 0.7` (median `|corr|` = 0.277). A plausible "real cluster" cutoff
  (`|corr| >= 0.5`) yields **~661 candidate pairs** — a sparser, more
  mechanism-plausible set than the liquidity-tier cross-product, but at
  the cost of **new infrastructure that does not exist anywhere in this
  repo today** (`LEAD_LAG_RECONNAISSANCE.md` §2 confirmed no
  `leave_one_out`/`benchmark_return`/correlation-cluster code exists in
  `src/`), a second point-in-time-correctness burden (the correlation
  window must itself be recomputed trailing-only, no lookahead, at every
  evaluation date), and a second axis of the candle/bar-width standing
  rule exposure (the correlation window's own length is itself a
  "lag-window-like" parameter subject to the same minutes-not-candles
  discipline flagged in `LEAD_LAG_RECONNAISSANCE.md` §6).

### 1c. Recommendation

**Liquidity-tier as the primary/only mechanism for Phase 3.** Reasoning:
(1) it reuses already-validated, already-point-in-time infrastructure with
zero new engineering or lookahead risk; (2) §2 below shows power is not the
binding constraint under either mechanism, so statistical-cluster's
sparser-but-more-plausible pair set buys no feasibility advantage worth its
cost; (3) every new axis of parameter choice (correlation window length,
threshold) is itself subject to the trial-ledger and candle/bar-width
standing rules and would expand the family's eventual correction
denominator for no measured benefit at this stage. Statistical-cluster
pairing is **not ruled out** as a later robustness check or as the
SELECTION null's matched-pairing mechanism, but is **not required to clear
this feasibility gate** and is not recommended as the Phase 3 primary
design.

---

## 2. MDE computation (the standing-rule-required step, done before any config grid)

### 2a. Convention reused (not invented)

Per the project's own standing rule (`OPERATIONS.md` ~line 1327-1362:
*"compute this from VARIANCE ONLY, never from a mean or an already-observed
effect"*) and its prior application in `PREREGISTRATION_PORTFOLIO.md`
Section 7 / `PORTFOLIO_FINDINGS.md`:

```
MDE = (z_{1-alpha/2} + z_power) * sigma / sqrt(N)
```

with **alpha = 0.05 (two-sided), power = 0.80** (Portfolio study's own
explicit, stated convention — "the standard target"), giving
`z_{0.975} = 1.95996`, `z_{0.80} = 0.84162`, sum = **2.80158**. Portfolio
used the t-distribution for its small per-frequency N (15-95); here N is in
the thousands, so the normal approximation is appropriate and used
directly. `sigma` is computed from **observed data only** (never from a
mean or prior effect), exactly as that study's own per-period-return-std
input. The day-clustering choice for `N` follows Box Theory's own
`day_clustered_bootstrap` convention (`src/box_theory/inference.py`:
*"trades on the same day are correlated, so resampling draws whole trading
days... The minimum detectable effect is computed from the bootstrap
standard error ALONE, never from the observed mean"*) and this project's
explicit standing instruction (task point 4) that the correct clustering
unit for a cross-stock intraday design is the **trading day**, not the bar
or the leader-signal event — events on the same volatile day are not
independent, and this project has no precedent null/SE framework for a
multi-entity design to borrow from (`LEAD_LAG_RECONNAISSANCE.md` §8, risk
6), so the conservative floor (treat each day as contributing at most one
independent unit of information to the aggregate effect) is used rather
than inventing an unvalidated intra-day design-effect correction.

### 2b. Observed variance (data, not assumption)

Forward N-minute **raw** 1-minute-bar returns, `close[t+h]/close[t] - 1`,
computed same-day only (no overnight gap: either a pandas per-(entity,day)
group, or a DuckDB `LEAD(...) OVER (PARTITION BY entity_id, trade_date
ORDER BY ts)` window, both used as a cross-check — see §2c).

**Stratified-sample check** (30 follower-pool entities — bottom-80%-by-
turnover tier, picked evenly across that pool's turnover-rank distribution
— full 2016-10-04 to 2026-09-18 history, 10.6M bars pulled in 8.1s):

| Horizon | n obs | mean | sigma (observed std) |
|---|---|---|---|
| 5 min | 10,492,456 | -0.156 bps | **24.13 bps** |
| 15 min | 10,202,270 | -0.462 bps | **39.23 bps** |
| 30 min | 9,767,864 | -0.871 bps | **53.49 bps** |
| 60 min | 8,902,569 | -1.892 bps | **72.70 bps** |

**Full-population cross-check** (all 386 entities, all ~168M same-day
forward-return observations, computed via chunked-by-calendar-year DuckDB
window functions — see §3 for why chunking was needed):

| Horizon | n obs | mean | sigma (observed std) |
|---|---|---|---|
| 5 min | 167,639,345 | -0.126 bps | **24.64 bps** |
| 15 min | 163,047,959 | -0.393 bps | **40.27 bps** |
| 30 min | 156,161,777 | -0.719 bps | **55.05 bps** |
| 60 min | 142,393,321 | -1.509 bps | **74.85 bps** |

The 30-name stratified sample and the full 386-name population agree to
within ~2-3% at every horizon — a stage-reconciliation cross-check that
passes cleanly (no defect to explain). The **mean** values are small and
negative at every horizon (consistent with intraday mean-reversion/cost
drag already documented project-wide) but, per the standing rule, **the
mean is not used anywhere in the MDE computation** — only `sigma`. Full-
population sigma values are used as the primary input going forward since
they are not sample-dependent.

### 2c. The day-clustering unit, confirmed

```sql
SELECT COUNT(DISTINCT trade_date) FROM bars_1min;  -- 2,468
```

Matches `DATA_AUDIT_LEAD_LAG.md` area 1 exactly ("2468 distinct
trade_dates") — second stage-reconciliation cross-check, passes. **N =
2,468** is used as the day-clustered sample ceiling: the largest number of
independent observations any lead-lag design could have, under the
conservative assumption that a day contributes at most one independent
unit of signal regardless of how many leader-events or follower-bars occur
within it (the true achievable N, once an actual signal detector exists,
will be <= 2,468, since signals will not fire on every single day — this
makes the MDE below a *best-case/lower-bound* figure, addressed directly in
§2e).

### 2d. MDE result

```
MDE_h = 2.80158 * sigma_h / sqrt(2468) = 2.80158 * sigma_h / 49.679
```

| Horizon | sigma (full pop.) | **MDE (80% power, alpha=0.05, N=2,468 days)** |
|---|---|---|
| 5 min | 24.64 bps | **1.39 bps** |
| 15 min | 40.27 bps | **2.27 bps** |
| 30 min | 55.05 bps | **3.10 bps** |
| 60 min | 74.85 bps | **4.22 bps** |

### 2e. Comparison against the economic-significance gate (Part 7.4)

Established economic floor, this project's own prior number, not invented
here: **round-trip cost ~0.2-0.3% (20-30 bps)**, `PROJECT_CONTEXT.md` §8
("A round trip costs roughly 0.2-0.3% regardless of holding period"), the
same figure underlying the "-0.1% to -0.3% per trade" band that closed 11
prior intraday strategies and the `swing/costs.py` spread+impact range
(6.0-19.0 bps round-trip) plus statutory components.

**MDE (1.4-4.2 bps) is 5-20x smaller than the 20-30 bps cost floor.** This
is the inverse of the Portfolio/Combination failure shape (there, MDE was
10-20x *larger* than any plausible effect — unresolvable; here, MDE is
far *smaller* than the threshold that would matter economically —
comfortably resolvable). Robustness check against the N=2,468 ceiling
being optimistic (true achievable N will be lower once a real detector
exists): solving for the break-even N at which MDE equals the cost floor,
for both the 20 bps and the stricter 10 bps bound:

| Horizon | sigma | N needed for MDE = 20 bps | N needed for MDE = 10 bps |
|---|---|---|---|
| 5 min | 24.64 bps | **12** | **48** |
| 15 min | 40.27 bps | **32** | **127** |
| 30 min | 55.05 bps | **59** | **238** |
| 60 min | 74.85 bps | **110** | **440** |

Even at the 60-minute horizon (the most variance-hungry) and the stricter
10 bps floor, only **440 independent trading days** are needed out of the
2,468 available — i.e. the design remains adequately powered even if real
leader-signal events turn out to fire on as few as ~18% of all trading
days. A design whose signal is rarer than that would need to be reconsidered
at Phase 3, but there is no evidence yet (no detector has been built) that
signal frequency will be anywhere near that sparse.

Also checked for robustness against an eventual Bonferroni correction
across a plausible DEV grid size (this feasibility check itself examines
4 horizons x up to 2 mechanisms; a Phase 3 grid of ~10-20 configurations
is plausible): even at `alpha = 0.05/20`, `z_{1-alpha/2} ~= 3.02` (vs.
1.96 uncorrected), inflating MDE by ~1.54x to 2.1-6.5 bps — still 3-14x
below the 20-30 bps floor. **The PASS verdict is not sensitive to this
choice.**

---

## 3. Computational tractability for a full DEV run

- **A single, unpartitioned DuckDB window-function pass over the full
  `bars_1min` table (169.9M rows, 386 entities, LEAD() partitioned by
  entity_id+trade_date) OOM'd** on this machine (~15.7GB total RAM, ~8.7GB
  free at the time) with `_duckdb.OutOfMemoryException: Allocation
  failure`. **This is itself a tractability finding, not just a
  performance note**: a full-universe scan is NOT a "run it as one query"
  operation on this hardware and must be chunked.
- **Chunked by calendar year (11 chunks, 2016-2026), accumulating
  sufficient statistics (count/sum/sum-of-squares) per chunk**, the same
  full-table scan completed easily:

| Horizon | n obs (full) | Total elapsed | Avg chunk | Max chunk |
|---|---|---|---|---|
| 5 min | 167.6M | 45.3s | 4.1s | 6.2s |
| 15 min | 163.0M | 61.9s | 5.6s | 6.7s |
| 30 min | 156.2M | 63.5s | 5.8s | 6.8s |
| 60 min | 142.4M | 64.1s | 5.8s | 6.9s |

All four horizons together: **~235 seconds (<4 minutes)** for a complete
386-entity, 10-year, same-day forward-return variance computation,
expressed as vectorized SQL (no Python-level per-pair or per-group loop).

- **Implication for the master spec's O(leaders x followers x days x
  bars/day) framing**: that product (e.g. 23,793 pairs x 2,468 days x 375
  bars = ~2.2 x 10^10) is only intractable if executed as a literal nested
  loop. Expressed instead as what this check demonstrates — one
  entity-indexed, time-ordered window/self-join pass per side (leader
  detection: one pass over 77 leader entities; follower forward-return
  join: one pass over the full table, or 309 follower entities, joined by
  `(trade_date, ts)` via an ASOF-style or windowed join, not a per-pair
  Cartesian loop) — the actual full-DEV-grid cost is of the same order as
  the ~4-minute figure above, multiplied by however many preregistered
  configurations (horizons x grouping variants x lag windows) Phase 3
  settles on. **A full DEV scan is tractable in minutes-to-low-tens-of-
  minutes per configuration on this single machine, using DuckDB directly,
  provided it is chunked (by year, or by entity-batch) rather than run as
  one unpartitioned query** — this is a real engineering requirement to
  design in from the start (checkpoint per chunk, per the project's own
  standing checkpointing rule and the Box Theory 17-hour-run lesson), not
  an optional optimization.
- This is categorically different from Liquidity E/F's ~45-50h
  structurally-infeasible-without-confounding scan — no comparable
  infeasibility exists here.

---

## 4. Explicit PASS/ABANDON verdict

**PASS.** Both legs of Part 12 Phase 2's abandonment test are cleared:

1. **Identifiable**: the liquidity-tier mechanism reuses existing,
   already-validated, point-in-time universe construction with 77
   candidate leaders and 309 candidate followers (23,793 cross-pairs, or a
   many-to-pool design needing no pairing at all) — ample candidate
   structure, no sector-label dependency, no new lookahead risk.
2. **Adequately powered**: MDE at every candidate horizon (1.39-4.22 bps)
   is 5-20x below the project's own 20-30 bps economic-significance floor,
   using the conservative day-clustered sample ceiling (N=2,468), and the
   conclusion survives both a stricter 10 bps floor and a plausible
   eventual Bonferroni correction. The design remains powered even if the
   true, post-detector signal frequency turns out to be as sparse as ~18%
   of trading days.

**No parameters were manufactured or loosened to force this result** — the
sigma values come directly from the full observed population (both the
30-name stratified sample and the full 386-name population agree to within
2-3%), N is the actual, audited distinct-trading-day count, and the formula,
alpha, and power level are reused unchanged from the Portfolio study's own
precedent rather than chosen post hoc.

**What a PASS here does NOT mean**: it does not mean a real propagation
effect exists, or that it is large enough to be net-profitable once a real
leader-detector and cost model are built — only that *if* such an effect
exists at a size comparable to or larger than the established cost floor,
this sample has enough independent observations to detect it. The Portfolio
and Combination studies were killed because the sample COULD NOT answer
the question at all; this study clears that specific bar, nothing more. The
same 11-strategies structural prior (`PROJECT_CONTEXT.md` §8: costs fixed,
available move shrinks with horizon) still applies once real signal
detection and cost modeling begin.

---

## 5. Primary horizon recommendation: 60 minutes

Given PASS, the horizon choice is governed by the same structural logic
that explains all 11 prior intraday failures: **round-trip cost is fixed
(~20-30 bps) regardless of horizon; the available move (proxied here by
`sigma`) grows with horizon** (24.6 bps at 5 min -> 74.9 bps at 60 min,
full population). A genuine information-diffusion effect, if it exists, has
more "room" to clear the fixed cost floor at the longer horizon:

- **5 min (sigma 24.6 bps) and 15 min (sigma 40.3 bps)**: available move is
  only ~1-2x the cost floor — the same geometry that sank Darvas, FVG, POC,
  Fibo zones, and Liquidity A-D. Not recommended as primary.
- **30 min (sigma 55.1 bps)**: ~2-2.75x the cost floor — viable secondary/
  robustness horizon.
- **60 min (sigma 74.9 bps)**: ~2.5-3.75x the cost floor — the most room
  for a real effect to clear costs among the four candidates, and still
  the best-powered in absolute MDE terms despite needing the largest
  break-even N (both well inside the 2,468-day ceiling, §2e). **Recommended
  primary horizon for Phase 3.**

This is a prediction, stated per this project's own calibration discipline
(`LEAD_LAG_RECONNAISSANCE.md` §7: Claude's mechanism predictions on this
exact manipulation shape have been wrong 5/5 times in the Liquidity family)
— flagged explicitly as a hypothesis for Phase 3/4 to falsify, not an
assumption to lock in. 30-minute is recommended as the preregistered
secondary/robustness horizon.

---

## 6. Configurations examined at this feasibility stage (Phase 3 trial-ledger input)

Per `OPERATIONS.md`'s trial-ledger convention and Part 12 Phase 2 ("every
configuration examined at a feasibility gate still counts toward the
family's eventual trial count"), the following distinct configurations
were actually computed in this phase and must be carried into
`PREREGISTRATION_LEAD_LAG.md`'s own trial-count table:

| # | Configuration | What was computed | Outcome |
|---|---|---|---|
| 1 | Liquidity-tier grouping (top 20% / bottom 80% by turnover) | Candidate leader/follower counts, cross-pair count | 77 leaders, 309 followers, 23,793 cross-pairs — ample, recommended primary |
| 2 | Statistical-cluster grouping (trailing 252-trading-day daily-return correlation) | Candidate pair counts at 5 descriptive threshold cuts (0.3/0.4/0.5/0.6/0.7) of one correlation matrix — one configuration, sliced five ways for description, not five independent trials | 153/386 entities had sufficient recent coverage; ~661 pairs at \|corr\|>=0.5 — viable but not recommended as primary |
| 3 | MDE at horizon = 5 min | Forward-return sigma (follower sample + full population), MDE at N=2,468 | MDE 1.39 bps, well below cost floor |
| 4 | MDE at horizon = 15 min | Same | MDE 2.27 bps, well below cost floor |
| 5 | MDE at horizon = 30 min | Same | MDE 3.10 bps, well below cost floor; recommended secondary horizon |
| 6 | MDE at horizon = 60 min | Same | MDE 4.22 bps, well below cost floor; recommended primary horizon |

**6 configurations examined, all at the Phase 2 feasibility-gate level, 0
of which required a full DEV run.** None were killed (all passed the
feasibility bar); all 6 still count toward the family's eventual
Bonferroni/BH correction denominator once Phase 3 fixes the full
preregistered grid, per the stale-Bonferroni-denominator lesson
(`PROJECT_CONTEXT.md` §7 finding #15 — POC's flag-without-escalation
defect). This table should be copied forward into the preregistration's
own trial-count section, not re-derived.

---

## Files referenced in this analysis (absolute paths)

- `C:\projects\trade-new\lead_lag\LEAD_LAG_RECONNAISSANCE.md`
- `C:\projects\trade-new\lead_lag\DATA_AUDIT_LEAD_LAG.md`
- `C:\projects\trade-new\data\fibo_intraday.duckdb` (read-only access only)
- `C:\projects\trade-new\PREREGISTRATION_PORTFOLIO.md` (Section 7 — MDE
  formula/convention reused)
- `C:\projects\trade-new\PORTFOLIO_FINDINGS.md` (Section 7 power calc,
  MDE table, "compute the minimum detectable difference FIRST" standing
  lesson)
- `C:\projects\trade-new\src\box_theory\inference.py`
  (`day_clustered_bootstrap` — day-clustering convention reused)
- `C:\projects\trade-new\src\factors\ic_eval.py` (`daily_rank_ic`,
  `nonoverlapping_ic_report`, `benjamini_hochberg` — day-level/non-
  overlap independence conventions cross-checked, confirmed consistent
  with the day-clustering choice used here)
- `C:\projects\trade-new\PROJECT_CONTEXT.md` §8 (the 0.2-0.3% round-trip
  cost figure, the 11-strategies "-0.1% to -0.3%" structural finding)
- `C:\projects\trade-new\src\swing\costs.py` (spread+impact 6.0-19.0 bps
  round-trip range, cited as a cross-check on the 20-30 bps economic
  floor)

Throwaway scripts used (session scratchpad, not committed):
`lead_lag_feasibility.py`, `lead_lag_full_scan_timing.py` (OOM'd, kept for
the record of the unchunked-pass finding), `lead_lag_full_scan_timing2.py`
(chunked, produced §3's numbers).
