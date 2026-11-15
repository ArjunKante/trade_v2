# Decision 10 — Follower-Breadth Threshold Feasibility Measurement

Read-only sample-adequacy / retention measurement across 11 candidate
follower-basket breadth thresholds, for the Cross-Liquidity-Tier Return
Propagation (lead-lag) family.

**No existing file was modified. No trial was registered. No commit was
made.** All DuckDB access was through an in-memory working connection with
both stores `ATTACH`ed `(READ_ONLY)`. All working code lives in throwaway
scratchpad scripts (not committed): `step1_roster.py`,
`step2_eligibility.py`, `step3_measure.py`, `step4_diag.py`,
`step5_diag2.py`.

---

## 1. Purpose and explicit non-predictive scope

### Purpose

Decision 10 (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:1603`) is
OPEN: the follower-side completeness **threshold value and form** has never
been measured. This document supplies one half of the input that decision
needs — the **sample-size and temporal-coverage cost** of each candidate
threshold — for 11 candidate fractions of the monthly follower roster.

### What this document is NOT

This is **not** a predictive experiment, not a backtest, not a pilot
regression, and not a selection of a threshold.

- **No forward return, price change, abnormal return, beta, alpha, IC,
  correlation, or any other predictive statistic was read, computed,
  compared, ranked, or summarized anywhere in this measurement.**
- The `t+h` "future endpoint" check performed here is a **pure
  availability/validity boolean**: *does a usable price exist at that
  endpoint for every frozen-subset member, yes or no*. The price **value**
  at `t+h` was never selected out of the database, never differenced
  against another price, never ratioed.
- The only quantity read from a price table at all is raw
  `prices_eod.turnover`, which is the **ranking input to the already-approved
  Section 6 roster construction** (split-invariant rupee traded value, not a
  price level and not a return). It is used solely to reproduce the monthly
  leader/follower split, exactly as `fibo.universe` and
  `LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1 already do.
- `bars_1min.open/high/low/close` appear in exactly one place: inside a SQL
  **boolean structural-validity predicate** (`high>=low`, `low<=open<=high`,
  …). No OHLC value is ever returned to the client, stored, or arithmetically
  combined with another bar's value.

**This document does not select, endorse, rank, or recommend any candidate
threshold.** See Section 12.

---

## 2. Methodology and source-code paths inspected

Every rule below was read directly from the cited file and line before any
computation was run. Nothing was re-derived and nothing was deviated from.

| Component | Source (file:line) | What was taken from it |
|---|---|---|
| Annual point-in-time universe | `src/fibo/universe.py:78` (`reconstitute_annually`), `src/fibo/universe.py:155` (`effective_universe`) | Top-200-by-prior-year-median-turnover, annually reconstituted; `stub_year=2016` convention for the first-year gap. Called unmodified, with no extra year/date bound. |
| Monthly leader/follower split | `PREREGISTRATION_LEAD_LAG_V1.md:308` (Section 6), `:365` (Section 7) | First trading day of each month; trailing-60-trading-session median raw `prices_eod.turnover` (`EQ`, via `isin_lineage`), window inclusive of the ranking date, `>=60` sessions required; top 20% = leaders (`ceil(0.2*n_eligible)`), remainder = followers. |
| Published reference figures | `lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md:88-150` (Task 1) | The per-month eligible/leader/follower table used as the reconstruction's correctness check (Section 10.1 below). |
| Bar-category / endpoint validity | `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md:706-756` (Section 7 operational policy), `:693-704` (Section 6 decision table, categories A/B/C/D1/D2/E) | PRESENT-VALID / FUNCTIONALLY ABSENT / GENUINE ABSENCE classification; exact-elapsed-seconds (`EPOCH` difference, **not** `DATE_DIFF('minute',…)`) 180-second forward-fill threshold; never imputing at a category-C/E timestamp. |
| Regular-session scoping, off-session dates | `lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md:315-350` | Regular session `09:15`–`15:29` only; the 8 identified off-session (Muhurat-pattern) dates and the `09:14` pre-open cluster are never treated as adjacent to a regular-session bar. |
| Already-frozen exclusions | `PREREGISTRATION_LEAD_LAG_V1.md:512-522` (Section 12), `:526-530` (Section 13) | `<90%`-bar-completeness entity-days; pre-open bars; signal-end minutes whose forward window would cross the close; `+/-1`-trading-day corporate-action windows. |
| Signal schedule and anchor | `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:965-1008` (Section 5) | One fixed clock-time anchor per horizon; `h+5` spacing; failed slots **skipped, never shifted**; `ts` labels a bar's **start**. |
| Basket construction (Option 2) | `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:426-468` (Section 3C, 9-step ordered construction), `:286-312` (Section 3A/3B) | Roster is identity-only and never availability-filtered; unified `(t-35, t-5, t)` pre-signal eligibility; freeze subset and weights; threshold applied at step 4 and nowhere else; `t+h` check on the already-frozen subset; whole-observation discard on any forward failure. |
| Bootstrap block length (Decision 12) | `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:1605` | `L`, `R` and two further sub-parameters are OPEN. Consumed here only as a *limitation* (Section 8). |
| Existing power/MDE calculation | `PREREGISTRATION_LEAD_LAG_V1.md:746-834` (Section 17), `:911-958` (Section 21) | Inspected to determine whether this measurement supplies its missing inputs (Section 9). |
| Corporate-action lineage join convention | `src/box_theory/universe_data.py:49-58` (`fetch_ex_dates`), `scripts/fibo_step5_backtest.py:110-115` | `corporate_actions` joined to `entity_id` through `isin_lineage`, spanning the full lineage chain. |
| Trial ledger (read, not written) | `lead_lag/trial_ledger.json`, `lead_lag/ledger.py` | Confirmed untouched; no entry added. |

Data stores (both read-only): `data/fibo_intraday.duckdb`
(`bars_1min`: 169,935,257 rows, 386 entities, 2,468 trading dates,
2016-10-04 → 2026-09-18) and `data/warehouse.duckdb`
(`prices_eod`, `isin_lineage`, `corporate_actions`).

### Measured population

| Item | Value |
|---|---|
| Date range (unchanged) | 2016-10-04 → 2026-09-18 |
| Trading dates | 2,468 |
| Intraday-archive entity universe (unchanged) | 386 |
| Analysis months | 120 (2016-10 … 2026-09) |
| Monthly follower roster size `N` | 144 – 160 (median 160; 91 of 120 months at exactly 160) |
| Distinct follower-roster entities across all months | 416 |
| Follower-roster entity-days in scope | 391,501 |
| **Scheduled observations before any filtering** | **153,016** = 2,468 days × 62 slots/day |
| Slots per day, by horizon | h=5: 33 · h=15: 16 · h=30: 9 · h=60: 4 |
| Distinct target clock-minutes per day | 72 |

The schedule was re-derived from the rules, not hardcoded; the resulting
33/16/9/4 slot counts match the prior run's figures exactly.

---

## 3. Candidate threshold definitions

Eleven candidate fractions `θ` of **that month's actual follower-roster size
`N`** (never the count of names with available intraday data):

```
θ ∈ {50%, 55%, 60%, 65%, 70%, 75%, 80%, 85%, 90%, 95%, 100%}
required_count(month) = ceil(θ × N(month))
```

An observation is **pre-signal-eligible at θ** iff
`n_eligible >= ceil(θ × N)`, where `n_eligible` is the size of the frozen
subset defined by the unified `(t-35, t-5, t)` eligibility check.

### Two architectural facts, verified rather than assumed

1. **The frozen eligible subset's membership is θ-independent.** It is
   determined entirely by the Decision-17 validity of each roster member at
   `t-35`, `t-5`, `t`. θ enters only as a comparison against `n_eligible`
   *after* the subset exists. Verified in code: `n_eligible` and the subset
   identity are computed once per `(trade_date, h, t)` triple — uniqueness of
   that key was asserted — and the 11 θ values are applied afterwards as pure
   arithmetic on the same column.
2. **`forward_ok(observation, h)` is θ-independent.** Whether *every* frozen
   member is valid at `t+h` depends only on who is in the frozen subset,
   which by fact 1 does not depend on θ. Computed once per observation per
   horizon and reused for all 11 thresholds.

Consequence, confirmed empirically in Section 10.3: retained counts are
**non-increasing in θ** for every horizon.

---

## 4. Candidate comparison — strictness vs. sample size

All 4 horizons pooled (153,016 scheduled observations). `req` is the
required eligible count, shown as a range because `N` varies 144–160.

| θ | required count (N=144 … N=160) | pre-signal-eligible | % of scheduled | retained after forward check | % of scheduled | forward retention | distinct qualifying dates (of 2,468) | calendar months (of 120) | years (of 11) | first → last qualifying date |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 50% | 72 … 80 | 151,922 | 99.28% | **149,941** | **97.99%** | 98.70% | 2,451 | 120 | 11 | 2016-10-04 → 2026-09-18 |
| 55% | 80 … 88 | 151,922 | 99.28% | **149,941** | **97.99%** | 98.70% | 2,451 | 120 | 11 | 2016-10-04 → 2026-09-18 |
| 60% | 87 … 96 | 151,922 | 99.28% | **149,941** | **97.99%** | 98.70% | 2,451 | 120 | 11 | 2016-10-04 → 2026-09-18 |
| 65% | 94 … 104 | 151,922 | 99.28% | **149,941** | **97.99%** | 98.70% | 2,451 | 120 | 11 | 2016-10-04 → 2026-09-18 |
| 70% | 101 … 112 | 151,605 | 99.08% | **149,642** | **97.80%** | 98.71% | 2,446 | 120 | 11 | 2016-10-04 → 2026-09-18 |
| 75% | 108 … 120 | 146,491 | 95.74% | **144,716** | **94.58%** | 98.79% | 2,366 | 120 | 11 | 2016-10-04 → 2026-09-18 |
| 80% | 116 … 128 | 131,402 | 85.88% | **130,047** | **84.99%** | 98.97% | 2,122 | 113 | 11 | 2016-10-13 → 2026-09-18 |
| 85% | 123 … 136 | 108,338 | 70.80% | **107,544** | **70.28%** | 99.27% | 1,752 | 98 | 9 | 2018-02-01 → 2026-09-18 |
| 90% | 130 … 144 | 87,253 | 57.02% | **86,776** | **56.71%** | 99.45% | 1,408 | 69 | 6 | 2021-01-01 → 2026-09-18 |
| 95% | 137 … 152 | 69,726 | 45.57% | **69,377** | **45.34%** | 99.50% | 1,129 | 66 | 6 | 2021-04-05 → 2026-09-18 |
| **100%** | 144 … 160 | **0** | **0.00%** | **0** | **0.00%** | n/a | **0** | **0** | **0** | — |

### Observed eligible-count distribution (all 153,016 scheduled observations)

| statistic | `n_eligible` | `n_eligible / N` |
|---|---:|---:|
| min | 0 | 0.0000 |
| 1st percentile | 111 | 0.7115 |
| 5th percentile | 119 | 0.7500 |
| 25th percentile | 133 | 0.8375 |
| median | 148 | 0.9438 |
| 75th percentile | 153 | 0.9625 |
| **max** | **158** | **0.9875** |
| mean (sd) | 141.68 (16.74) | 0.8934 (0.1074) |

The distribution is near-identical across the four horizons (the pre-signal
endpoints `t-35, t-5, t` do not depend on `h`; only the slot *set* differs).

### The three structural facts this table makes visible

1. **θ = 100% is unattainable, not merely strict.** The maximum
   `n_eligible / N` observed anywhere in the 10-year, 153,016-observation
   population is **0.9875** (158 of 160). Every candidate above ~98.75%
   therefore retains exactly **zero** observations. This is a hard
   data-coverage ceiling, not a borderline result.
2. **θ = 50%, 55%, 60% and 65% are observationally indistinguishable.**
   Required counts of 72–104 are below the 1st percentile of `n_eligible`
   (111), so all four select the identical observation set. The only
   observations they exclude are the 15 dates on which the regular session
   effectively did not occur (Section 7).
3. **The sample-size cost is sharply non-linear above 75%.** Retention falls
   98.0% → 94.6% → 85.0% → 70.3% → 56.7% → 45.3% → 0% across
   70/75/80/85/90/95/100%. The steepest marginal cost is between 80% and 90%.

---

## 5. Horizon-specific endpoint-retention results

Per horizon × threshold. "Entered" = pre-signal-eligible observations
entering the forward check; "retained" = those whose entire frozen subset is
also valid at `t+h`; "discarded" = whole observations dropped for a
missing/invalid required future endpoint.

| θ | h=5 entered / retained / discarded (retention) | h=15 | h=30 | h=60 |
|---:|---|---|---|---|
| 50% | 80,847 / 79,822 / 1,025 (98.73%) | 39,215 / 38,710 / 505 (98.71%) | 22,057 / 21,749 / 308 (98.60%) | 9,803 / 9,660 / 143 (98.54%) |
| 55% | 80,847 / 79,822 / 1,025 (98.73%) | 39,215 / 38,710 / 505 (98.71%) | 22,057 / 21,749 / 308 (98.60%) | 9,803 / 9,660 / 143 (98.54%) |
| 60% | 80,847 / 79,822 / 1,025 (98.73%) | 39,215 / 38,710 / 505 (98.71%) | 22,057 / 21,749 / 308 (98.60%) | 9,803 / 9,660 / 143 (98.54%) |
| 65% | 80,847 / 79,822 / 1,025 (98.73%) | 39,215 / 38,710 / 505 (98.71%) | 22,057 / 21,749 / 308 (98.60%) | 9,803 / 9,660 / 143 (98.54%) |
| 70% | 80,678 / 79,662 / 1,016 (98.74%) | 39,134 / 38,633 / 501 (98.72%) | 22,012 / 21,708 / 304 (98.62%) | 9,781 / 9,639 / 142 (98.55%) |
| 75% | 77,957 / 77,038 / 919 (98.82%) | 37,814 / 37,362 / 452 (98.80%) | 21,267 / 20,989 / 278 (98.69%) | 9,453 / 9,327 / 126 (98.67%) |
| 80% | 69,927 / 69,225 / 702 (99.00%) | 33,919 / 33,577 / 342 (98.99%) | 19,079 / 18,866 / 213 (98.88%) | 8,477 / 8,379 / 98 (98.84%) |
| 85% | 57,659 / 57,249 / 410 (99.29%) | 27,965 / 27,769 / 196 (99.30%) | 15,727 / 15,601 / 126 (99.20%) | 6,987 / 6,925 / 62 (99.11%) |
| 90% | 46,425 / 46,184 / 241 (99.48%) | 22,527 / 22,408 / 119 (99.47%) | 12,670 / 12,595 / 75 (99.41%) | 5,631 / 5,589 / 42 (99.25%) |
| 95% | 37,095 / 36,918 / 177 (99.52%) | 18,000 / 17,915 / 85 (99.53%) | 10,130 / 10,074 / 56 (99.45%) | 4,501 / 4,470 / 31 (99.31%) |
| 100% | 0 / 0 / 0 (n/a) | 0 / 0 / 0 (n/a) | 0 / 0 / 0 (n/a) | 0 / 0 / 0 (n/a) |

### Observations

- **Endpoint retention is high and monotone in both directions.** It rises
  with θ (a stricter breadth filter has already removed the thin
  observations most likely to also fail forward) and falls with `h` (a longer
  horizon reaches a later, more failure-prone endpoint). The full observed
  range across all 44 cells is **98.54% – 99.53%** — a spread of under one
  percentage point.
- **Endpoint retention does not materially change the candidate comparison.**
  The breadth filter removes between 0.7% and 100% of scheduled observations
  depending on θ; the forward check then removes a further 0.5%–1.5%. The two
  effects differ by roughly two orders of magnitude at the strict end, and the
  ordering of candidates by retained sample size is identical before and after
  the forward check.

### Unconditional forward-failure rate, by horizon (all scheduled observations)

| h | forward-failure rate |
|---:|---:|
| 5 | 1.259% |
| 15 | 1.279% |
| 30 | 1.387% |
| 60 | 1.449% |

### Does missingness concentrate? Yes — in early years and midday

**By year** (all horizons pooled, unconditional forward-failure rate):

| Year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fail % | 3.46 | 3.01 | 2.00 | 2.67 | 1.29 | 0.78 | 0.75 | 0.58 | 0.58 | 0.32 | 0.13 |

A monotone-ish ~27× decline from 2016 to 2026. Forward-endpoint missingness
is overwhelmingly an **early-archive** phenomenon.

**By time of day** (h=5, 33 slots, failure rate per slot): rises from 0.37%
at `t=09:59` to a plateau of 2.1–2.8% between `t=12:09` and `t=13:29`
(peak 2.80% at `t=12:49`), then falls steeply to 0.04% at `t=15:09` and
0.08% at `t=15:19`. The h=60 pattern is the same shape at coarser
resolution (1.05% / 2.11% / 2.15% / 0.49% at `t` = 10:24 / 11:29 / 12:34 /
13:39). **Midday is the failure-prone window**, consistent with lunchtime
illiquidity in the thinner follower tier.

**By target minute** (pre-signal and forward endpoints pooled): of the
11,491 invalid `(entity, day, target-minute)` triples, **8,984 (78.2%)**
fall on just two clock minutes, `15:19` (4,491) and `15:24` (4,493) — the
latest target minutes in the schedule. Because `15:19` is a *pre-signal*
endpoint for the final h=5 slot, those names are removed from the frozen
subset before the forward check, which is why the measured forward-failure
rate at `t=15:19` is nonetheless only 0.08%.

---

## 6. Temporal coverage (yearly / quarterly / monthly)

### Distinct qualifying trading dates by year

Available trading days per year: 2016 — 61 (Oct–Dec only); 2017 — 248;
2018 — 246; 2019 — 244; 2020 — 252; 2021 — 248; 2022 — 248; 2023 — 246;
2024 — 249; 2025 — 249; 2026 — 177 (Jan–Sep only).

| θ | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 50% | 60 | 246 | 245 | 244 | 248 | 245 | 247 | 245 | 246 | 248 | 177 |
| 70% | 60 | 241 | 245 | 244 | 248 | 245 | 247 | 245 | 246 | 248 | 177 |
| 75% | 39 | 182 | 245 | 244 | 248 | 245 | 247 | 245 | 246 | 248 | 177 |
| 80% | 7 | 7 | 224 | 230 | 246 | 245 | 247 | 245 | 246 | 248 | 177 |
| 85% | 0 | 0 | 16 | 129 | 199 | 245 | 247 | 245 | 246 | 248 | 177 |
| 90% | 0 | 0 | 0 | 0 | 0 | 245 | 247 | 245 | 246 | 248 | 177 |
| 95% | 0 | 0 | 0 | 0 | 0 | 63 | 208 | 198 | 242 | 241 | 177 |
| 100% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### Retained observations by year (all 4 horizons pooled)

| θ | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 50% | 3,589 | 14,790 | 14,885 | 14,724 | 15,174 | 15,064 | 15,199 | 15,101 | 15,162 | 15,327 | 10,926 |
| 75% | 2,322 | 10,842 | 14,885 | 14,715 | 15,174 | 15,064 | 15,199 | 15,101 | 15,161 | 15,327 | 10,926 |
| 80% | 410 | 397 | 13,568 | 13,843 | 15,051 | 15,064 | 15,199 | 15,101 | 15,161 | 15,327 | 10,926 |
| 85% | 0 | 0 | 943 | 7,712 | 12,113 | 15,063 | 15,198 | 15,101 | 15,161 | 15,327 | 10,926 |
| 90% | 0 | 0 | 0 | 0 | 0 | 15,063 | 15,198 | 15,101 | 15,161 | 15,327 | 10,926 |
| 95% | 0 | 0 | 0 | 0 | 0 | 3,809 | 12,760 | 12,125 | 14,880 | 14,877 | 10,926 |

### Calendar-period representation and largest gaps

| θ | calendar months (of 120) | calendar quarters (of 40) | calendar years (of 11) | largest gap between consecutive qualifying dates (h=60) |
|---:|---:|---:|---:|---|
| 50–65% | 120 | 40 | 11 | 5 days |
| 70% | 120 | 40 | 11 | 5 days |
| 75% | 120 | 40 | 11 | 7 days (ending 2016-10-13) |
| 80% | 113 | 40 | 11 | **135 days** (ending 2017-05-19) |
| 85% | 98 | 34 | 9 | **97 days** (ending 2018-10-03) |
| 90% | 69 | 23 | 6 | 5 days (ending 2021-01-27) |
| 95% | 66 | 22 | 6 | 21 days (ending 2021-06-30) |
| 100% | 0 | 0 | 0 | n/a |

### The dominant temporal finding

**Above θ ≈ 85%, the surviving sample is not a thinned version of the full
period — it is a different, later period.**

- At **θ = 90%**, *every one of the 51 months from 2016-10 through 2020-12
  contributes zero qualifying observations.* The sample begins 2021-01-01.
  All 86,776 retained observations come from 2021–2026.
- At **θ = 95%**, the sample begins 2021-04-05 and 2021 itself is only
  partially covered (63 of 248 dates).
- At **θ = 80%**, 2016 and 2017 contribute just 7 qualifying dates each out
  of 60 and 248 — producing the 135-day gap above — while 2018 onward is
  near-complete. The headline "113 of 120 months" therefore understates the
  concentration: two of the eleven years are represented by a handful of
  dates.

Raw observation counts at θ ≥ 85% must **not** be read as evidence of
broad-period coverage. Per the required caution: raw observation count is
not proof of independent information, and here it is not even proof of
temporal breadth.

### Mechanism behind the concentration

The binding constraint is **intraday-archive coverage of the follower
roster**, not bar-level staleness. Of the 416 distinct follower-roster
entities, **41 have zero rows in `bars_1min` at any time**. Their count per
month declines steadily:

| Year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| archive-absent roster names (median per month) | 27 | 26.5 | 22 | 17 | 18 | 8 | 3 | 6 | 3 | 2 | 2 |

With 27 of 155 roster names structurally unavailable all month, the
attainable `n_eligible / N` ceiling in 2016 is ~0.82 — below the 85%, 90%,
95% and 100% candidates by construction, independent of any data-quality
behaviour on any given day. The per-month ceiling (`max n_eligible / N`) is
`>= 0.95` in only **66 of 120 months**, `>= 0.90` in 69, and `>= 0.80` in 113.

Median `n_eligible / N` by year: 0.761 (2016), 0.763 (2017), 0.819 (2018),
0.850 (2019), 0.856 (2020), 0.944 (2021), 0.963 (2022), 0.956 (2023),
0.963 (2024), 0.963 (2025), 0.975 (2026).

---

## 7. Exclusion accounting

### Filter order actually applied (exact, in order)

1. **Roster construction** — identity-only; no availability input. Produces
   `N(month)` and the fixed member list.
2. **Entity-day gates** (Section-12 90% rule → then corporate-action window).
   Removes `(entity, trade_date)` pairs wholesale.
3. **Decision-17 endpoint validity** at `t-35`, `t-5`, `t` for each surviving
   roster member. Produces the **frozen eligible subset** and `n_eligible`.
4. **Breadth threshold** `n_eligible >= ceil(θ × N)` — applied here and
   nowhere else.
5. **Forward endpoint check** at `t+h` on the already-frozen subset only.
   Whole-observation pass/fail.

Steps 2 and 3 are inputs to `n_eligible`; they therefore feed **into**
category 1 below, and are **not** counted again as a separate observation-level
category. This is stated explicitly and applied consistently.

### Observation-level categories (non-overlapping, exhaustive)

Four categories, by construction summing to the scheduled total:

| Category | Definition | Where counted |
|---|---|---|
| 1 | Insufficient pre-signal breadth (`n_eligible < ceil(θ×N)`) | `excl_breadth` column, Section 4 |
| 2 | Required future endpoint missing/invalid for ≥1 frozen member | `discarded` column, Section 5 |
| 3 | Other methodology-defined data-quality exclusions (Section-12 90% rule; corporate-action window) | **Counted inside category 1** — they reduce `n_eligible` and have no independent observation-level effect. Attributed separately below. |
| 4 | Unknown / unresolved | **0** |

Verified no double-counting, for every (θ, h) cell:
`category 1 + category 2 + retained = scheduled`. Worked example, θ=80%,
h=60: `1,395 + 98 + 8,379 = 9,872` ✓.

Category 4 is exactly zero: every one of the 153,016 scheduled observations
is assigned to retained, category 1, or category 2 with no residual.

### Category-3 attribution (entity-day level, feeding into category 1)

| Stage | entity-days | % of scope |
|---|---:|---:|
| Follower-roster entity-days in scope | 391,501 | 100.00% |
| — removed: roster name has **zero rows in `bars_1min` ever** | 27,590 | 7.05% |
| — removed: name is in the archive but has **zero bars that day** | 2,199 | 0.56% |
| — removed: name has partial data but **< 90% of 375 bars present-valid** | 11,640 | 2.97% |
| — removed: `+/-1`-trading-day **corporate-action window** | 213 | 0.05% |
| **Surviving entity-days** | **349,859** | **89.36%** |

Section-12 90%-rule failure rate by year (entity-days): 24.7% (2016),
24.4% (2017), 18.1% (2018), 15.5% (2019), 15.6% (2020), 6.7% (2021),
4.0% (2022), 4.9% (2023), 4.6% (2024), 3.7% (2025), 2.3% (2026).

Corporate actions: 161 ex-dates across the 416 roster entities' lineage
chains, of which 10 fall on a non-trading day.

### Decomposition of the breadth shortfall `N − n_eligible`

Per scheduled observation, mean values:

| Component | mean | median | 95th pct | max |
|---|---:|---:|---:|---:|
| `N − n_ok` (entity-day gates: archive absence, 90% rule, CA window) | **16.873** | 9 | 39 | 160 |
| `n_ok − n_eligible` (Decision-17 endpoint invalidity at `t-35/t-5/t`) | **0.075** | 0 | 0 | 133 |

The entity-day gate accounts for **99.6%** of the average shortfall.
Decision-17 bar-level endpoint invalidity is a ~225× smaller effect:
**96.1%** of all scheduled observations have *zero* members lost to it.
`n_ok − n_eligible` is 0 for every observation on 96.1% of the population,
and the 133 maximum occurs on one of the degenerate dates below.

### Fifteen dates where `n_eligible = 0` for every slot

Every roster name fails the day-level gates on 15 dates. Characterised from
`bars_1min` directly (regular-session vs. off-session row counts):

| Date | regular-session rows | off-session rows | earliest / latest `ts` | interpretation |
|---|---:|---:|---|---|
| 2016-10-30 (Sun) | 161 | 244 | 15:28:59 / 19:29:00 | off-session only |
| 2017-07-10 (Mon) | 23,251 | 0 | 11:59:00 / 15:29:00 | partial session (starts 11:59) |
| 2017-10-19 (Thu) | 0 | 10,720 | 18:21:00 / 19:46:28 | Muhurat-pattern, no regular session |
| 2018-11-07 (Wed) | 0 | 10,818 | 17:14:00 / 18:49:00 | Muhurat-pattern |
| 2020-03-13 (Fri) | 56,717 | 1 | 09:14:59 / 15:29:00 | full session, ~315 of 375 bars/entity — market-wide interruption |
| 2020-03-23 (Mon) | 56,619 | 1 | 09:14:59 / 15:29:00 | full session, ~315 of 375 bars/entity — market-wide interruption |
| 2020-11-14 (Sat) | 0 | 11,036 | 17:59:00 / 19:26:02 | Muhurat-pattern |
| 2021-02-24 (Wed) | 27,757 | 14,425 | 09:14:00 / 16:59:00 | the already-flagged unresolved date; ~147 regular bars/entity |
| 2021-11-04 (Thu) | 0 | 11,649 | 18:06:00 / 19:14:00 | Muhurat-pattern |
| 2022-10-24 (Mon) | 0 | 11,585 | 01:04:00 / 19:14:00 | Muhurat-pattern |
| 2023-11-12 (Sun) | 0 | 11,404 | 01:04:00 / 19:14:00 | Muhurat-pattern |
| 2024-03-02 (Sat) | 22,614 | 0 | 09:15:00 / 12:50:00 | short session (ends 12:50) |
| 2024-05-18 (Sat) | 20,477 | 0 | 09:15:00 / 12:29:00 | short session (ends 12:29) |
| 2024-11-01 (Fri) | 0 | 11,749 | 18:00:00 / 18:59:00 | Muhurat-pattern |
| 2025-10-21 (Tue) | 11,875 | 0 | 13:45:00 / 14:44:00 | one-hour session only |

All 8 previously-identified off-session (Muhurat-pattern) dates appear here
and are correctly reduced to zero by regular-session scoping plus the
Section-12 90% rule, with **no new rule invented** to handle them. The seven
remaining dates are short/partial/interrupted regular sessions. Their causes
are **not** independently verified here — that is Decision 21's open
question, and this document does not resolve it. They are reported as
observed.

---

## 8. Independent-information limitations (Decision 12 is OPEN)

**Decision 12 — bootstrap block length `L`, run-length `R`, series choice,
and switch-over rule — is unresolved** (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:1605`).
No block length is invented here, and **no claim is made that any raw
observation count in this document equals a count of independent
observations.**

What this measurement *can* establish:

| θ | retained observations | distinct qualifying trading dates | observations per qualifying date |
|---:|---:|---:|---:|
| 50–65% | 149,941 | 2,451 | 61.2 |
| 70% | 149,642 | 2,446 | 61.2 |
| 75% | 144,716 | 2,366 | 61.2 |
| 80% | 130,047 | 2,122 | 61.3 |
| 85% | 107,544 | 1,752 | 61.4 |
| 90% | 86,776 | 1,408 | 61.6 |
| 95% | 69,377 | 1,129 | 61.4 |
| 100% | 0 | 0 | n/a |

Because the design places up to 62 scheduled slots on every trading day,
retained observations exceed distinct dates by roughly **61×** at every
threshold. If the eventual dependence structure turns out to cluster at the
daily level or coarser — which the existing day-clustered-SE convention
(`PREREGISTRATION_LEAD_LAG_V1.md:534-540`) and the prior placebo pilot both
assume — then the **distinct-date column, not the observation column, is the
quantity that scales the effective sample**. This document reports both and
asserts neither as the operative one.

### Calendar-grouping sensitivity table — **calendar grouping, NOT a bootstrap/independence block**

The following groups qualifying dates into **fixed calendar periods**. These
are *calendar* blocks. They are **not** bootstrap blocks, **not** independence
blocks, and must not be read as such or substituted for Decision 12's `L`.

| θ | qualifying dates | calendar months with ≥1 qualifying date (of 120) | calendar quarters (of 40) | calendar years (of 11) |
|---:|---:|---:|---:|---:|
| 50–65% | 2,451 | 120 | 40 | 11 |
| 70% | 2,446 | 120 | 40 | 11 |
| 75% | 2,366 | 120 | 40 | 11 |
| 80% | 2,122 | 113 | 40 | 11 |
| 85% | 1,752 | 98 | 34 | 9 |
| 90% | 1,408 | 69 | 23 | 6 |
| 95% | 1,129 | 66 | 22 | 6 |
| 100% | 0 | 0 | 0 | 0 |

**Final usable independent-block counts cannot be established until Decision
12 is resolved.** Resolving it requires the ACF diagnostic described in
Section 7B of the methodology proposal, which operates on controls-only
baseline residuals — residuals that still contain `Y(t,h)` and are therefore
outside this task's non-predictive boundary. Nothing in this document
substitutes for that work.

---

## 9. Power-analysis limitations

No power figure is computed here, and none is estimable from this data.

### What IS establishable from this feasibility measurement alone

Observation counts, distinct qualifying trading dates, retained-sample
temporal distribution across years/quarters/months, endpoint-retention rates
by horizon and threshold, the `n_eligible` distribution, and the exclusion
accounting. All are in Sections 4–8. None of these is a power statement.

### Status of the preregistration's own Section 17 calculation

`PREREGISTRATION_LEAD_LAG_V1.md:746-834` **explicitly withdraws** the
original MDE (1.39–4.22 bps) and **does not claim the study is adequately
powered**. Its replacement calculation has the form

```
MDE = SE_boot × (z_{1-α/2} + z_{power})
```

with the Bonferroni critical value for denominator 6 fixed at
`z_{0.995833} + z_{0.80} = 2.63826 + 0.84162 = 3.47988`
(`PREREGISTRATION_LEAD_LAG_V1.md:792-798`).

**The inputs this calculation needs are NOT available from this feasibility
measurement, and I cannot responsibly complete it.** Specifically:

1. **`SE_boot` is not a function of a sample-size figure in this
   specification.** It is obtained by *running* a day-clustered block
   bootstrap and reading off the dispersion of the fitted coefficient. A
   count of observations or dates does not determine it. Supplying my counts
   does not supply this input.
2. **`SE_boot` on the real signal has never been measured.** The only
   existing figure (`0.0347`) was computed on an explicitly-labelled
   **diagnostic substitute** signal, on an 11-month / 230-day /
   single-fixed-signal-minute sub-sample
   (`PREREGISTRATION_LEAD_LAG_V1.md:764-791`). Section 21 step 1-2 makes
   measuring the real, Section-8-corrected `S_leader(t)`'s own sigma and
   re-running the bootstrap at full scale a mandatory **Phase 4 first step**.
3. **The real signal's own empirical sigma `σ(S_leader)` is unmeasured**, and
   Section 17 needs it to convert a coefficient-unit MDE into the bps units
   that Section 18's 20bps floor is expressed in. Measuring it would require
   computing a return series — **out of scope here by construction**.
4. **Decision 12's `L` and `R` are open**, so even the bootstrap's own block
   structure is unspecified.

**Named missing preregistered inputs:** `SE_boot` measured on the real
corrected `S_leader(t)` at full scale; `σ(S_leader)` for the bps conversion;
and Decision 12's `L`/`R` governing the bootstrap's blocks. Items 2 and 3
are both marked in the preregistration itself as deferred to Phase 4's first
analysis step.

**Consequently, Section 21's frozen margin-ratio decision rule**
(`>= 5` proceed · `>= 1 and < 5` INCONCLUSIVE · `< 1` ABANDONED,
`PREREGISTRATION_LEAD_LAG_V1.md:925-950`) **cannot be evaluated against any
candidate threshold from this measurement.** It is keyed to a full-scale MDE
in bps, not to an observation or date count. No new assumption about effect
size or variance was introduced to work around this, per instruction.

### Request for a sample-adequacy verdict

The task asks whether any candidate has insufficient coverage **per an
explicit, already-existing project sample-adequacy criterion**. Searching
`OPERATIONS.md`, `PROJECT_CONTEXT.md`, `PREREGISTRATION_LEAD_LAG_V1.md` and
every `lead_lag/` document found **no predeclared, outcome-independent
criterion expressed in terms of observation counts, trading-date counts, or
temporal coverage.** The two quantitative adequacy-adjacent rules that do
exist are:

- Section 21's margin-ratio rule — keyed to MDE in bps, inputs missing (above).
- The original Section 21 "signal sparsity" condition (`e1418a6`,
  Section 21 item 3) — keyed to how often `|S_leader(t)|` exceeds a
  descriptive threshold. That requires reading a signal magnitude, which is
  out of scope here, and the preregistration itself states it "is a trigger
  to re-examine power … not an automatic fail."

**No new criterion was invented to fill this gap**, so no
sufficient/insufficient verdict is issued for any candidate. The one
statement that requires no criterion at all is arithmetic: **θ = 100%
retains zero observations and therefore cannot support any analysis** — this
is a statement about an empty set, not a judgement about adequacy.

---

## 10. Data-quality and reproducibility checks

Deterministic throughout: no random number generator, no sampling, no seed,
no iteration order dependence anywhere in this task. Re-running the five
scripts reproduces every figure exactly.

### 10.1 Roster reconstruction validated against the published table

The reconstruction was compared, month by month, against
`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1:

- All **29** published sub-200-eligible months match exactly on
  `(n_eligible, n_leaders, n_followers)`.
- All remaining **91** months are exactly `200 / 40 / 160`, matching the
  published "91 of 120 months (76%)" claim.
- Worst month reproduced exactly: **2025-01 → 181 / 37 / 144**.

**Result: 0 mismatches across all 120 months.** No bug to fix, no correction
to report.

### 10.2 The window-boundary check the task required

`reconstitute_annually` was called with no year/date bound, and **does mint a
year beyond the analysis window**: it returned membership lists for
**2016 through 2027** (12 years × 200 rows). The 2027 list was produced
because `prices_eod` extends past the intraday store's 2026-09-18 cutoff.
Downstream analysis was restricted independently to the exact 120-month
window **2016-10 … 2026-09**, derived from `bars_1min`'s own distinct
`trade_date` calendar. Verified directly rather than trusted: the restricted
calendar has exactly 2,468 dates spanning 2016-10-04 → 2026-09-18, and
exactly 120 distinct months.

### 10.3 Monotonicity correctness check (built-in, as required)

For every horizon, `retained(θ)` must be non-increasing across
50% → 100%. **Verified: PASS for all four horizons.** `pre_eligible(θ)` was
independently checked and is also non-increasing for all four horizons. No
bug was triggered.

### 10.4 Duplicate rows and revisions

- `bars_1min` contains **0** duplicate `(entity_id, ts)` pairs and **0**
  duplicate `(entity_id, trade_date, minute-bucket)` triples.
- `revision_seq` takes the single value `1` across all 169,935,257 rows;
  `source` is uniformly `ANGEL_ONE_SMARTAPI_HISTORICAL`.
- **Therefore no de-duplication or revision-selection logic was applied or
  needed.** Stated explicitly rather than assumed.
- `ts::date = trade_date` for all 169,935,257 rows (0 mismatches), so
  session grouping by `trade_date` is safe.

### 10.5 Timestamp-jitter handling

**408,297 rows (0.24%) carry a non-zero seconds component**, and all of them
belong to **a single entity** (`INE628A01036`), spanning 1,094 trading dates
from 2016-10-04 to 2021-03-04. This matches the Decision-17 memo's finding
that the `DATE_DIFF`-vs-exact-duration divergence was "confined to one
entity". Handling, stated precisely:

- A bar is assigned to clock minute `date_trunc('minute', ts)`; uniqueness of
  that assignment per `(entity_id, trade_date)` was verified (0 collisions).
- The **exact raw `ts`** is used for the elapsed-seconds gap computation, per
  Decision C — never the truncated minute.
- The nominal timestamp of an absent target minute `M` is `M:00`.

### 10.6 Bar-classification counts

Over the 160,573,971 regular-session bars belonging to follower-roster
entities:

- **1,819** bars are NOT present-valid (categories C and E combined).
- **0** zero-volume OHLC-flat bars anywhere in `bars_1min` carry a
  null/non-finite/non-positive price — so the latent category-B-vs-E
  precedence ambiguity (is a flat bar at price 0 "flat" or "structurally
  invalid"?) is **empirically moot**; no rule had to be invented to break it.
- Within entity-days surviving the day-level gates, **590,948** in-session
  minutes are non-present-valid; **115,077** of those fall on one of the 72
  target clock-minutes; of those, **103,586 are forward-filled** (gap < 180 s)
  and **11,491 are INVALID**. Only **62** of the 11,491 are invalid because a
  category-C/E row physically occupies the minute; the rest are genuine
  absences at or beyond the 180-second threshold.

### 10.7 Exact SQL — the load-bearing predicates

**PRESENT-VALID classification** (Decision 17 rule 1; the only place any OHLC
field is touched, and it is touched only as a boolean):

```sql
  (b.open IS NOT NULL AND b.high IS NOT NULL AND b.low IS NOT NULL AND b.close IS NOT NULL
   AND isfinite(b.open) AND isfinite(b.high) AND isfinite(b.low) AND isfinite(b.close)
   AND b.open > 0 AND b.high > 0 AND b.low > 0 AND b.close > 0
   AND b.volume IS NOT NULL AND b.volume >= 0
   AND b.high >= b.low AND b.open >= b.low AND b.open <= b.high
   AND b.close >= b.low AND b.close <= b.high
   AND (b.volume > 0 OR (b.open = b.high AND b.high = b.low AND b.low = b.close)))
```

**Regular-session scoping** (off-session rows can never become an endpoint or
a gap neighbour):

```sql
WHERE date_trunc('minute', b.ts)::TIME >= TIME '09:15:00'
  AND date_trunc('minute', b.ts)::TIME <= TIME '15:29:00'
```

**Gap/forward-fill rule** (Decision 17 rule 3, exact elapsed seconds; a gap
minute is VALID only if no row occupies it AND it is under 180 s from the
preceding present-valid bar):

```sql
SELECT a.entity_id, a.trade_date, a.gm::TIME AS tm
FROM gaptgt a
LEFT JOIN nonpv n
  ON n.entity_id = a.entity_id AND n.trade_date = a.trade_date AND n.m = a.gm
WHERE NOT (a.p_ts IS NOT NULL
           AND (epoch(a.gm) - epoch(a.p_ts)) < 180
           AND n.m IS NULL)
```

Gap neighbours are drawn only from **present-valid** rows, so a
functionally-absent bar correctly **does not reset** a surrounding absence
span — exactly as Decision 17 requires, with no extra rule added.

**Section-12 90% entity-day rule:**

```sql
(COALESCE(d.n_pv, 0) >= 0.9 * 375) AS pass90
```

**Corporate-action `+/-1`-trading-day window** (single-entity rule as
originally written; see Section 11 item 4):

```sql
SELECT DISTINCT x.entity_id, cl.trade_date
FROM ca_di x JOIN cal cl
  ON cl.di BETWEEN (CASE WHEN x.on_td THEN x.lo_di - 1 ELSE x.lo_di END)
               AND (CASE WHEN x.on_td THEN x.hi_di + 1 ELSE x.hi_di END)
```

**Per-observation eligibility and the forward boolean** (θ appears nowhere):

```sql
SELECT s.sid, s.trade_date, s.month, s.h, s.t, d.N, d.n_ok,
       d.n_ok - COALESCE(a.n_pre_bad, 0)  AS n_eligible,
       (COALESCE(a.n_fwd_only_bad, 0) = 0) AS forward_ok
FROM slots s JOIN daybase d USING (trade_date)
LEFT JOIN slot_agg a USING (sid)
```

where `n_pre_bad` counts frozen-subset candidates invalid at any of
`t-35`/`t-5`/`t`, and `n_fwd_only_bad` counts members **of the frozen subset**
(i.e. `pre_bad = 0`) invalid at `t+h`.

### 10.8 Denominators used, stated explicitly

| Quantity | Denominator |
|---|---|
| `required_count` | `N` = that month's **full fixed follower roster size** (144–160) |
| `n_eligible / N` | same `N` |
| % of scheduled observations | 153,016 total, or 81,444 / 39,488 / 22,212 / 9,872 per horizon |
| forward retention % | observations **entering** the forward check at that (θ, h) |
| Section-12 90% rule | **375** expected regular-session bars per entity-day |
| entity-day exclusion rates | 391,501 in-scope follower entity-days |

At no point is any count of "names with available intraday data" used as a
denominator.

### 10.9 Validation checklist — how each item was verified

| # | Item | Verification | Result |
|---|---|---|---|
| 1 | Roster membership unchanged by θ | θ appears in the code only in `ceil(θ*N)` compared against an already-computed `n_eligible` column; the roster table is built in `step1_roster.py`, before θ exists anywhere in the pipeline | **PASS** |
| 2 | Denominator is the full monthly roster `N` | `N` sourced from `tiers.n_followers` (roster identity count), joined by month; archive availability enters only as a reason a name fails eligibility, never as a denominator | **PASS** |
| 3 | Eligibility uses only pre-signal info | `n_pre_bad` is computed from `b.tm IN (s.tm35, s.tm5, s.tm0)` only; `s.tmh` is in a separate aggregate | **PASS** |
| 4 | Subset and weights frozen before forward check | `n_eligible` (and thus the equal weight `1/n_eligible`) is computed from the pre-signal aggregate alone; `forward_ok` is evaluated afterwards and conditions on `pre_bad = 0` | **PASS** |
| 5 | Forward failure discards the whole observation | `forward_ok` is a single boolean per observation; a `False` removes the observation from `retained` entirely. No partial, reweighted or substituted quantity exists in the code | **PASS** |
| 6 | No missing constituent replaced | No substitution logic exists anywhere; roster is built once and never edited | **PASS** |
| 7 | No future-informed reweighting | No weight is ever computed numerically (weights are irrelevant to counting); `t+h` information enters only the boolean | **PASS** |
| 8 | No partial forward return calculated — no `t+h` price value read | Direct confirmation: no `SELECT` in any of the five scripts returns `open`, `high`, `low` or `close` as a value. The only appearance of those columns is inside the boolean predicate in 10.7. No subtraction, division or ratio of two prices appears anywhere in the codebase written for this task | **PASS** |
| 9 | `09:20` anchor and non-overlapping schedule respected, no extra anchors | Single anchor `t0 = 09:19` (known at wall-clock 09:20) for all four horizons; spacing `h+5`; constraints `t-35 >= 09:15` and `t+h <= 15:29`; failing slots `continue` (skipped), never shifted. Re-derived slot counts 33/16/9/4 match the prior run's independently | **PASS** |
| 10 | Decision 17's exact rules respected, no invented rule | Classification, 180-second exact-`EPOCH` threshold, non-interrupting functionally-absent bars, never imputing at a category-C/E timestamp, regular-session-only scoping — each traced to `DECISION_17_FINAL_POLICY_RECOMMENDATION.md:706-756`. The one latent ambiguity (flat-but-non-positive bar) was measured to be empty rather than resolved by fiat (10.6) | **PASS** |
| 11 | Deterministic | No RNG, no sampling, no seed, no parallel-order dependence | **PASS** |
| 12 | No predictive outcome or return field read anywhere | **Direct confirmation, not an assumption**: the complete set of value-bearing columns read across all five scripts is `entity_id`, `isin`, `trade_date`, `ts`, `volume`, `turnover` (`prices_eod`, roster ranking only), `ex_date`, plus the boolean derived from OHLC. No return, price change, beta, alpha, IC, correlation or any other predictive statistic was read or computed | **PASS** |

---

## 11. Implementation discrepancies and unresolved limitations

Reported, **not** silently resolved either way, per instruction.

1. **Approval-status conflict — the decisions this task describes as
   "approved" are recorded as OPEN in the project's own decision table.**
   `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:1592-1620` (Section 11,
   "Revised human decision table") lists:
   - Decision 10 (follower breadth threshold) — **OPEN**
   - Decision 11 (anchor and schedule) — **OPEN** (hierarchy approved; exact
     anchor not)
   - Decision 17 (missing-data/stale-price compatibility) — **OPEN**
     ("ambiguity sharpened, not resolved")
   - Decision 19 (Option 1 vs. corrected Option 2) — **OPEN**

   and tallies "6 APPROVED (rows 1-6), 1 RECOMMENDED (row 18), 14 OPEN".
   `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md:973` states plainly
   "**Decision 17 is not approved by this document**", and its Section 7.3
   lists Decision 11's anchor, Decision 19's basket option, and Decision 10's
   threshold as still requiring human decisions.

   The task brief describes Decision 17, Decision 11's anchor and Decision
   19's Option 2 as approved and instructs that they be applied exactly.
   **The substantive content of all three matches the documents precisely**
   (verified clause by clause — see the Section 2 table); the conflict is
   purely one of **recorded approval status**. This measurement applied the
   rules exactly as briefed and flags the status gap here rather than
   resolving it. **Nothing in this document should be read as evidence that
   any of those decisions has been approved.**

2. **Decision 11's exact anchor is genuinely unresolved, and this measurement
   committed to one branch.**
   `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:973-986` names two
   candidates: anchor `09:20` if `09:15` is a valid regular-session bar, and
   anchor `09:21` if a pre-open exclusion applies at `09:15`. The brief
   specified the `09:20` branch (first signal window = bars `09:15..09:19`)
   and that is what was used. The required targeted `MIN(ts)`-per-trading-day
   check was **not** performed here (it is separately authorized work). If the
   `09:21` branch is ultimately confirmed, every slot shifts by one minute.
   The *slot counts* (33/16/9/4) would be unaffected by a one-minute shift
   under the same constraints, but the target-minute set would change and all
   counts in this document would need re-running. **This is not a
   re-derivation: it is a dependency, stated.**

3. **Section 12 contains two leader-side exclusions that were deliberately not
   applied.** `PREREGISTRATION_LEAD_LAG_V1.md:512-522` also specifies a
   whole-day exclusion when `<50%` of the month's leader tier lacks a valid
   bar, and (new in the amendment) a per-minute leader-breadth floor
   `n_t >= 0.80 × leader-tier size`. Both act on the **leader** tier and gate
   whether `S_leader(t)` is computed at all. This task measures the
   **follower** roster only, and the brief enumerated the Section-12
   exclusions to apply without including these. They were therefore **not
   applied**, per the "do not add/invent any rule" instruction. Consequence,
   stated plainly: **the counts in this document are upper bounds on what a
   full pipeline would retain**, because a leader-side day or minute
   exclusion could remove further observations that this measurement counts
   as retained. The proposal itself warns at `:490-502` that the follower and
   leader breadth figures "must not be assumed equal, confused, or merged".

4. **The corporate-action window's portfolio-level meaning is ambiguous;
   the single-entity version was applied, as instructed.** Decision 20
   (`:1613`) is OPEN on exactly this, naming "keep the existing single-entity
   `+/-1`-day exclusion unchanged, applied naively to ~160-name rosters" as
   an alternative that is explicitly *not* assumed sufficient or excessive.
   Applied here at the **entity-day** level (an entity's own ex-date window
   removes only that entity from that day's eligible subset, reducing
   `n_eligible`); **no portfolio-level CA rule was invented**. Its effect is
   small (213 of 391,501 entity-days, 0.05%). A sub-ambiguity: 10 of the 161
   ex-dates fall on non-trading days; for those the window was taken as the
   two trading days bracketing the ex-date. Flagged.

5. **The `09:14` boundary interacts with the single jittered entity.** For
   `INE628A01036` (10.5), the bar covering the 09:15 minute is timestamped
   `09:14:5x` and therefore buckets to `09:14`, outside the regular session.
   That entity thus loses its 09:15 bar on the affected 1,094 dates, slightly
   raising its Section-12 90%-rule failure odds. Single entity, confined to
   2016-10 → 2021-03. Reported, not corrected — correcting it would require
   inventing a jitter-tolerant session-boundary rule that no approved
   document contains.

6. **Seven of the fifteen zero-eligible dates have unverified causes**
   (Section 7). They are short, partial or interrupted regular sessions. The
   Decision-21 question of how special/irregular sessions should be treated
   remains open; this measurement neither resolves it nor depends on its
   resolution, since all fifteen dates already contribute zero observations
   at every threshold.

7. **Archive coverage of the follower roster is a first-order constraint that
   no current project document quantifies.** 41 of 416 follower-roster
   entities have no intraday bars at all, and 27 of ~155 roster names are
   archive-absent for every month of 2016–2017. This — not bar staleness, not
   corporate actions, not the Decision-17 gap rules — is what makes θ ≥ 85%
   exclude the early years and θ = 100% impossible. It is a property of the
   **intraday download campaign's historical scope**, not of the market. Any
   threshold choice is implicitly a choice about which years enter the
   sample. Flagged as the single most consequential finding here.

8. **Decision 12 remains open**, so no independent-observation count is
   available at any threshold (Section 8).

9. **Section 17's power calculation cannot be completed**, and the specific
   missing preregistered inputs are named in Section 9.

---

## 12. Conclusion

This document measured, for 11 candidate follower-basket breadth thresholds
across 4 horizons over 153,016 scheduled observations spanning 2,468 trading
dates (2016-10-04 → 2026-09-18, 386-entity intraday universe, 120 monthly
rosters of 144–160 followers):

- pre-signal eligibility counts and the `n_eligible` / `n_eligible / N`
  distributions;
- future-endpoint retention as a pure availability boolean, by threshold,
  horizon, year, quarter and time of day;
- temporal coverage of the surviving sample, including distinct qualifying
  dates, calendar-period representation and largest inter-date gaps;
- a four-category, non-overlapping, fully-reconciled exclusion accounting
  with zero unexplained residual.

**Findings are measurements, not evaluations.** In particular:

- **No candidate threshold is selected, endorsed, recommended, ranked, or
  preferred by this document.**
- **No candidate is characterised as statistically valid, unbiased,
  profitable, predictive, optimal, adequate, or inadequate.** No such
  property was measured, and no project criterion exists that would let these
  counts speak to any of them (Section 9).
- **The strictness/sample-size tradeoff is reported, not adjudicated.** That
  larger θ yields fewer observations and narrower temporal coverage is an
  arithmetic consequence of the construction, not an argument for or against
  any value. The right balance depends on the return-distortion question
  (Section 3D-A's missingness-emulation diagnostic) and on Decision 12 — and
  neither is answered here.
- **The one non-discretionary statement**: θ = 100% retains zero observations
  in the measured population, because the observed maximum of
  `n_eligible / N` is 0.9875. This is arithmetic about an empty set, not a
  judgement; it does not imply that any other candidate is suitable.
- **The counts here are upper bounds**, because the two leader-side Section-12
  exclusions were out of this task's scope (Section 11 item 3), and because
  Decision 11's anchor branch is not finally confirmed (item 2).
- **Observation-selection / informative-censoring dependence on `t+h` is not
  eliminated by any threshold measured here**, exactly as
  `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:464-468` and `:504-511`
  already state. Between 0.5% and 1.5% of pre-eligible observations are
  discarded on a `t+h` availability criterion, and that discard rate varies
  systematically by year (3.5% in 2016 → 0.13% in 2026) and by time of day
  (peaking midday). Raising θ *reduces* the discard rate but does not remove
  the mechanism.

**Decision 10 remains OPEN.** Choosing a threshold requires the
return-distortion half of the Section 3D-A diagnostic, a resolution of
Decision 12, and a human decision — none of which this document supplies or
pre-empts.
