# Cross-Liquidity-Tier Return Propagation / Lead-Lag V1: CLOSED

## 1. Study identity

- **Study**: Cross-Liquidity-Tier Return Propagation / Lead-Lag V1.
- **Research question**: Whether the leader portfolio's relative recent
  return predicts subsequent follower portfolio returns.
- **Primary horizon**: 60 minutes.
- **Primary estimand**: Portfolio-level incremental predictive
  association (`S_L(t)` -> `Y(t,60)`, controlling for `R_F`, `TOD`,
  `Momentum_F`).
- **Status**: CLOSED -- PREREGISTERED PRIMARY EVALUATION FAILED.
- **Closure date**: 2026-11-15.

## 2. Frozen methodology

Primary regression (unchanged throughout Phase 4/5 and the primary
evaluation):

```
Y ~ S_L + R_F + TOD_opening_30 + TOD_closing_30 + Momentum_F
```

- Primary inference: consecutive multi-day block bootstrap, **L=6**.
- Sensitivity inference: independent single-day-cluster bootstrap,
  **L=1**.
- Bootstrap draws: **10,500 requested, minimum 10,000 valid required**,
  for both L=6 and L=1.
- Random seed: **20261107** (Section 22).
- Two-sided significance threshold: **alpha = 0.00625**.
- Minimum economic effect: **strictly greater than 20 bps**.
- Required beta direction: **positive**.
- Formal trial count: **7**. Operative multiplicity denominator: **8**.
  Alpha = 0.05/8 = 0.00625.

Full methodology, decision history, and evidentiary record:
`PREREGISTRATION_LEAD_LAG_V1.md`, in particular **AMENDMENT 15 LOG /
Decision 25** (the frozen inference methodology, split-bootstrap
design, and draw-count convention) and the preceding amendments
(Decisions 6-24) governing universe, roster, calendar, Stage A/B
eligibility, returns, and controls. Not reproduced here.

## 3. Dataset identity

- **File**: `full_pipeline_observations.csv`
- **SHA-256**: `47ccb4d80294ab97d3093e01120f72c56f45c0e6e1470325f6d09527dcbab3c5`
- **Observations**: 3,761
- **Trading days**: 1,861
- **Date range**: 2016-10-04 to 2026-09-18
- **Horizon**: 60 minutes (exclusively)

The primary evaluation used this previously prepared, hash-verified
dataset exactly as-is. No regeneration, resampling, or replacement of
the dataset occurred at or after the primary evaluation.

## 4. Primary results

| Quantity | Result |
|---|---:|
| Observations | 3,761 |
| Trading days | 1,861 |
| Effective design rank | 4 |
| Beta (`S_L`) | +0.249623 |
| `R_F` coefficient | +0.429692 |
| `Momentum_F` coefficient | +0.021069 |
| `sigma(S_L)` | 0.00043936 (4.394 bps) |
| `beta x sigma(S_L)` | 1.097 bps |
| L=6 null-imposed p-value | 0.28702 |
| Unrestricted bootstrap SE | 0.4645 |
| 99.375% confidence interval | [-0.7576, 1.5372] |

## 5. Bootstrap and sensitivity results

**L=6 primary:**
- Requested: 10,500. Valid: 10,500. Failed: 0.
- Match rate: mean 0.3688, median 0.3688, minimum 0.2925, fifth
  percentile 0.3433.
- Seed: 20261107.

**L=1 sensitivity:**
- Null-imposed p-value: 0.28931.
- Requested: 10,500. Valid: 10,500. Failed: 0.
- Match rate: mean 0.3681, minimum 0.3337.
- Seed: 20261107.

L=1 and L=6 produced closely agreeing results (p=0.28931 vs. p=0.28702).
**L=1 did not replace the primary test** -- it is reported as a
sensitivity check only, per the frozen split-bootstrap design.

**Expected zero-variance regressors**: `TOD_opening_30`,
`TOD_closing_30` -- both predicted by the real-data structural preflight
(no h=60 schedule anchor falls in the closing-30 window; the first
anchor's own `t-35` endpoint precedes session open, so Momentum_F's
minimum-anchor requirement can never be satisfied there). This produced
the effective design rank of 4, exactly as predicted before the
primary evaluation ran. No other warnings or errors were reported.

## 6. Preregistered decision

| Criterion | Requirement | Actual | Result |
|---|---|---:|---|
| Direction | `beta > 0` | +0.249623 | PASS |
| Economic effect | Strictly >20 bps | 1.097 bps | FAIL |
| Statistical significance | L=6 p < 0.00625 | 0.28702 | FAIL |

**1 of 3 criteria passed. The preregistered primary evaluation FAILED.**

## 7. Interpretation

The historical sample showed a positive estimated coefficient, but the
estimated economic effect was only 1.097 bps, substantially below the
preregistered 20 bps threshold. The primary null-imposed L=6 p-value
was 0.28702, far above the required 0.00625 threshold. The confidence
interval also spanned zero. The L=1 sensitivity result was consistent
with the L=6 primary result.

**Therefore, the preregistered hypothesis is not supported by this
historical sample under the frozen specification.**

This is not evidence of causality, a profitable trading strategy,
live-trading readiness, or independent out-of-sample validation.

The previously documented conservative-calibration behavior under high
missingness (synthetic calibration, AMENDMENT 15 LOG Section 4) remains
relevant context: the real match rate (~37%) fell in the regime found
to be conservative, not anti-conservative, under synthetic testing. This
does not change the outcome here -- both the economic effect size and
the p-value failed by a wide margin, independent of any inference-
procedure nuance. The bootstrap's successful, clean execution (zero
failed draws, full accounting) does not establish exact real-data Type
I error calibration; that was, and remains, only characterized through
the separate synthetic calibration exercise.

## 8. Permanent closure and restrictions

- **V1 is closed** following its failed preregistered primary
  evaluation.
- **The primary outcome must not be retroactively reinterpreted as a
  pass.**
- **No thresholds, controls, horizons, roster rules, sample filters, or
  inference methods may be changed within V1 to rescue the result.**
- **No favorable subgroup or alternative specification may be promoted
  to replace the failed primary result.**
- **L=1 remains a sensitivity result, not a replacement primary test.**
- **The completed result and its dataset identity must remain
  preserved**, exactly as recorded in Section 3 and Section 4-5 above.
- **Any genuinely new research question must be treated as a separate
  exploratory study**, with its own preregistration, trial accounting,
  and appropriate multiplicity treatment.
- **Closing V1 does not authorize starting a successor study.**
